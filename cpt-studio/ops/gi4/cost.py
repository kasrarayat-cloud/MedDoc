"""H7: cost probes. Each adversarial shape is grown by doubling (25,000 to 400,000 characters by default) and read
cold: the context reader, routing and the inventory one by one, then the analyze child and the assess child exactly as
the stages run them (studio/bounded.py, under the stage deadline and memory allowance). Gates: every doubling ratio at
most 2.3 (steps under the noise floor of 0.05 s are not judged), the analyze child at most 30 s, the assess child at
most 60 s, and neither past ASSESS_MEMORY_BYTES (an overrun is a failure, never a skip).

  python -m ops.gi4.cost [--tree DIR] [--sizes 25000,50000,100000,200000,400000] [--only NAME ...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import resource
import sys
import time
from types import SimpleNamespace

from ops.gi4 import boot

RATIO_LIMIT = 2.3
NOISE_FLOOR = 0.05
ANALYZE_LIMIT = 30.0
ASSESS_LIMIT = 60.0
B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\nDate of service: 10/19/2026\n'
# The minimal design's shapes (its cost.py) and the shapes the PS helpers read.
SHAPES = {
    'colonoscope sentences, one line': lambda n: B + 'The colonoscope reached the cecum. ' * n,
    'colonoscope lines': lambda n: B + 'The colonoscope reached the cecum.\n' * n,
    'instrument words, one sentence': lambda n: B + 'colonoscope ' * n + 'reached the cecum.\n',
    'long line then gastroscope': lambda n: B + 'x ' * n + ' The gastroscope was advanced to the duodenum.\n',
    'framed time lines': lambda n: B + 'Subjective\nPain.\n' + 'Physician time on the service date: 44 minutes.\n' * n,
    'worded date labels': lambda n: B + 'Service date logged for this case: 10/08/2026\n' * n,
    'acts far from carry': lambda n: (B + 'The gastroscope was advanced to the duodenum. The colonoscope reached the '
                                      'cecum.\n' + 'A polyp was removed with a snare. ' * n),
    'em time with activities': lambda n: (B + 'Office visit\nTotal time: 40 minutes, covering ' + 'the orders, ' * n
                                          + 'and documentation.\n'),
    'headings beyond reach': lambda n: (B + 'Prior Studies\n' + 'Some Heading Line\nA line of text here.\n' * n
                                        + 'A linear echoendoscope was introduced by mouth.\n'),
    'blank lines before the head': lambda n: '\n' * n + B + 'The colonoscope reached the cecum.\n',
    'one long title line': lambda n: 'Pre-procedure telephone call ' * n + '\n' + B,
    'heading-like lines': lambda n: B + 'Prior Studies\n' + 'Outside Records Reviewed Today\n' * n + 'Findings here.\n',
}


def modules():
    from django.conf import settings
    from studio import bounded, jobs
    from studio.gi import context, detect, sections, services
    from studio.reference.store import InMemoryReferenceLookup
    from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode
    return SimpleNamespace(settings=settings, bounded=bounded, jobs=jobs, context=context, detect=detect,
                           sections=sections, services=services, Lookup=InMemoryReferenceLookup,
                           EvidenceSpan=EvidenceSpan, NormalizedResponse=NormalizedResponse, PageSpan=PageSpan,
                           ProviderCode=ProviderCode)


def _clear(m):
    m.jobs.release_routing_caches()
    for module in (m.sections, m.services, m.context, m.detect):
        for value in vars(module).values():
            if callable(getattr(value, 'cache_clear', None)) and hasattr(value, 'cache_info'):
                value.cache_clear()


def _peak(fn, *args):
    """fn(*args) in the bounded child, returning (result, the child's peak resident set in bytes)."""
    result = fn(*args)
    return result, resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _analyze(m, text):
    read = m.jobs._analyze_child(text, {}, m.settings.MAX_SERVICE_MENTIONS)
    return 'mentions over the limit' if isinstance(read, int) else 'read'


def _assess(m, text):
    day = dt.date(2026, 10, 19)
    quote = 'Date of service: 10/19/2026'
    start = text.find(quote)
    codes = () if start < 0 else (m.ProviderCode(role='selected', system='cpt', code='45378', display='SYNTHETIC',
                                                 evidence=(m.EvidenceSpan(0, start, start + len(quote), quote, True,
                                                                          1),)),)
    normalized = m.NormalizedResponse(provider='corti', adapter_version='corti-coding-v2@cptstudio-1', codes=codes)
    facts = m.jobs._merged_facts(m.context.extract_context(text), {})
    context = m.jobs.context_facts(SimpleNamespace(facts=facts))
    m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context, normalized, m.Lookup([], {}), 'succeeded',
                         'ok', ())
    return 'assessed'


def _bounded(m, fn, text, seconds):
    t0 = time.perf_counter()
    try:
        outcome, peak = m.bounded.run_bounded(_peak, fn, m, text, seconds=seconds,
                                              memory_bytes=m.settings.ASSESS_MEMORY_BYTES)
    except m.bounded.Overrun as exc:
        return {'seconds': round(time.perf_counter() - t0, 2), 'overrun': exc.reason}
    return {'seconds': round(time.perf_counter() - t0, 2), 'peak_mib': round(peak / 2 ** 20), 'outcome': outcome}


def probe(m, name, make, sizes) -> list:
    rows = []
    unit = max(1, len(make(1)) - len(make(0)))
    for size in sizes:
        text = make(max(1, (size - len(make(0))) // unit))
        _clear(m)
        t0 = time.perf_counter()
        facts = m.context.extract_context(text)
        t1 = time.perf_counter()
        routing = m.detect.route(text, None)
        t2 = time.perf_counter()
        m.services.build(text, service_date=None, routing=routing, context_facts=facts)
        t3 = time.perf_counter()
        m.sections.around_procedure_title(text) if hasattr(m.sections, 'around_procedure_title') else None
        m.sections.procedure_report_head(text) if hasattr(m.sections, 'procedure_report_head') else None
        t4 = time.perf_counter()
        _clear(m)
        analyze = _bounded(m, _analyze, text, m.settings.JOB_DEADLINE_SECONDS['analyze'])
        assess = _bounded(m, _assess, text, m.settings.JOB_DEADLINE_SECONDS['assess'])
        rows.append({'chars': len(text), 'context': round(t1 - t0, 3), 'route': round(t2 - t1, 3),
                     'inventory': round(t3 - t2, 3), 'ps_helpers': round(t4 - t3, 4), 'analyze': analyze,
                     'assess': assess})
    return rows


def judge(name, rows) -> list:
    problems = []
    for key in ('context', 'route', 'inventory', 'ps_helpers'):
        for a, b in zip(rows, rows[1:]):
            if min(a[key], b[key]) >= NOISE_FLOOR and b[key] / a[key] > RATIO_LIMIT:
                problems.append(f'{name}: {key} {a[key]}s -> {b[key]}s at {b["chars"]:,} characters '
                                f'(ratio {b[key] / a[key]:.2f} > {RATIO_LIMIT})')
    for child, limit in (('analyze', ANALYZE_LIMIT), ('assess', ASSESS_LIMIT)):
        for row in rows:
            r = row[child]
            if 'overrun' in r:
                problems.append(f'{name}: the {child} child overran ({r["overrun"]}) at {row["chars"]:,} characters')
            elif r['seconds'] > limit:
                problems.append(f'{name}: the {child} child took {r["seconds"]}s at {row["chars"]:,} (limit {limit}s)')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.cost')
    parser.add_argument('--tree')
    parser.add_argument('--sizes', default='25000,50000,100000,200000,400000')
    parser.add_argument('--only', nargs='*', default=())
    parser.add_argument('--json-out', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    boot.offline(args.tree)
    m = modules()
    sizes = [int(s) for s in args.sizes.split(',')]
    results, problems = {}, []
    for name, make in SHAPES.items():
        if args.only and name not in args.only:
            continue
        rows = probe(m, name, make, sizes)
        results[name] = rows
        problems += judge(name, rows)
        print(f'{name}:', flush=True)
        for r in rows:
            print(f"  {r['chars'] // 1000:4d}k ctx {r['context']:6.2f}s route {r['route']:6.2f}s inv {r['inventory']:6.2f}s "
                  f"ps {r['ps_helpers']:7.4f}s | analyze child {r['analyze'].get('seconds')}s "
                  f"{r['analyze'].get('peak_mib', r['analyze'].get('overrun'))} MiB ({r['analyze'].get('outcome', '')}) "
                  f"| assess child {r['assess'].get('seconds')}s {r['assess'].get('peak_mib', r['assess'].get('overrun'))}"
                  f" MiB", flush=True)
    print(f"== limits: ratio <= {RATIO_LIMIT}, analyze child <= {ANALYZE_LIMIT}s, assess child <= {ASSESS_LIMIT}s, "
          f"memory within ASSESS_MEMORY_BYTES ({m.settings.ASSESS_MEMORY_BYTES // 2 ** 20} MiB growth)")
    print('== COST', 'WITHIN LIMITS' if not problems else 'OVER: ' + '; '.join(problems))
    if args.json_out:
        boot.write_json(args.json_out, {'results': results, 'problems': problems})
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
