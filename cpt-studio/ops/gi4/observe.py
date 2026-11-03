"""What one tree reads in each text of a corpus (one tree per process; offline): the request side for H2 and the readers
for H3.

Per text: the section layout's digest (sections, sentences and clauses), the context date fact, the date channel in
every member state (what the request then carries: a date, DATELESS or HELD; whether the member's answer is taken), the
request sha256 for each state's date, and the analyze stage's mention counts (detect.service_mention_count and
services.mention_count). With ``--readers``: routing and the inventory, read for the text's true date.

  python -m ops.gi4.observe --tree DIR --corpus IN.jsonl --out OUT.jsonl [--readers] [--workers N]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import multiprocessing as mp
import sys

from ops.gi4 import boot, regression

FAR = regression.FAR_DATE
_M = None


def _modules():
    from django.conf import settings
    from studio import jobs
    from studio.gi import context, detect, sections, services
    from studio.providers.base import ProviderUnavailable
    from studio.providers.corti import ADAPTER_VERSION, build_coding_request
    from studio.types import to_jsonable
    return dict(settings=settings, jobs=jobs, context=context, detect=detect, sections=sections, services=services,
                ProviderUnavailable=ProviderUnavailable, ADAPTER_VERSION=ADAPTER_VERSION, build=build_coding_request,
                to_jsonable=to_jsonable)


def states_for(text: str, truth: dict | None) -> list:
    """(label, answer) member states for a text: none, the truth's answers, documented dates (at most four), a date no
    document states, and one day either side of the first documented (or true) date. One state per answer."""
    states = [('none', None)]
    for key, value in sorted(((truth or {}).get('answers') or {}).items()):
        states.append((f'answer:{key}', value))
    dates = regression.documented_dates(text)[:4]
    states += [(f'doc:{d}', d) for d in dates]
    states.append(('far', FAR))
    anchor = (truth or {}).get('date') or (dates[0] if dates else None)
    if anchor:
        a = dt.date.fromisoformat(anchor)
        states += [('minus1', (a - dt.timedelta(days=1)).isoformat()), ('plus1', (a + dt.timedelta(days=1)).isoformat())]
    out, seen = [], set()
    for label, answer in states:
        if answer not in seen:
            seen.add(answer)
            out.append((label, answer))
    return out


def layout_digest(m, text: str) -> str:
    lay = m['sections'].layout(text)
    data = [[(s.kind, s.label, s.start, s.end, None if s.heading is None else (s.heading.start, s.heading.end))
             for s in lay.sections], list(lay.sentences), list(lay.clauses)]
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def _request_sha(m, text, day):
    try:
        return m['build']('corti', m['ADAPTER_VERSION'], text, day, m['settings'].PROVIDER_MAX_REQUEST_BYTES).canonical_sha256
    except m['ProviderUnavailable'] as exc:
        return 'refused: ' + str(exc)[:80]


def text_record(m, text: str, truth: dict | None) -> dict:
    facts = m['context'].extract_context(text)
    sd = facts['service_date']
    record = {
        'layout': layout_digest(m, text),
        'fact': [sd.origin, sd.value, [[e.start, e.end] for e in sd.evidence], sd.note],
        'mentions': [m['detect'].service_mention_count(text),
                     m['services'].mention_count(text, m['settings'].MAX_SERVICE_MENTIONS)],
        'states': {},
    }
    for label, answer in states_for(text, truth):
        merged = m['jobs']._merged_facts(facts, {'service_date': answer} if answer else {})
        fact = merged['service_date']
        held = m['context'].is_member_conflict(fact)
        day = m['jobs']._service_date_of(merged)
        sends = 'HELD' if held else (day.isoformat() if day else 'DATELESS')
        record['states'][label] = {
            'answer': answer, 'sends': sends, 'held': held,
            'taken': bool(answer) and fact.get('origin') == 'user' and fact.get('value') == answer,
            'request': None if held else _request_sha(m, text, day)}
    return record


def reader_record(m, text: str, day) -> dict:
    routing = m['detect'].route(text, day)
    facts = m['context'].extract_context(text)
    inventory = m['services'].build(text, service_date=day, routing=routing, context_facts=facts)
    return {
        'document_kind': routing.document_kind,
        'routing': {f.family: {'status': f.status, 'facts': {x.name: [str(x.value), x.origin] for x in f.facts},
                               'missing': list(f.missing), 'mentions': sorted({x.status for x in f.mentions})}
                    for f in routing.findings},
        'inventory': [{'family': s.family, 'status': s.status, 'completion': s.completion, 'extent': s.extent,
                       'acts': [[a.kind, a.status, a.region] for a in s.acts],
                       'lesions': [[l.anatomy, l.disposition, l.region] for l in s.lesions]}
                      for s in inventory.services],
    }


def _setup(tree, readers):
    """Read ``tree`` offline in this process; the forked workers inherit it."""
    global _M
    boot.offline(tree)
    _M = _modules()
    _M['readers'] = readers


def _observe(line: str) -> str:
    doc = json.loads(line)
    m = _M
    rec = {'id': doc['id']}
    try:
        rec.update(text_record(m, doc['text'], doc.get('truth')))
        if m['readers'] and doc.get('truth'):
            day = dt.date.fromisoformat(doc['truth']['date']) if doc['truth'].get('date') else None
            rec.update(reader_record(m, doc['text'], day))
            states = rec['states']
            rec['sent_initial'] = states['none']['sends']
            rec['answers'] = {label.split(':', 1)[1]: s for label, s in states.items() if label.startswith('answer:')}
    except Exception as exc:  # recorded, never hidden: a crash is a finding
        rec['error'] = f'{type(exc).__name__}: {exc}'[:300]
    m['jobs'].release_routing_caches()
    for module in ('sections', 'services'):
        for value in vars(m[module]).values():
            if callable(getattr(value, 'cache_clear', None)) and hasattr(value, 'cache_info'):
                value.cache_clear()
    return json.dumps(rec, sort_keys=True)


def observe_file(tree, corpus_path, out_path, *, readers=False, workers=8) -> int:
    with open(corpus_path, encoding='utf-8') as fh:
        lines = fh.readlines()
    _setup(str(tree), readers)
    with mp.get_context('fork').Pool(int(workers)) as pool, open(out_path, 'w', encoding='utf-8') as out:
        for rec in pool.imap(_observe, lines, chunksize=8):
            out.write(rec + '\n')
    return len(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.observe')
    parser.add_argument('--tree', required=True)
    parser.add_argument('--corpus', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--readers', action='store_true')
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--json-out')
    args = parser.parse_args(argv)
    n = observe_file(args.tree, args.corpus, args.out, readers=args.readers, workers=args.workers)
    if args.json_out:
        boot.write_json(args.json_out, {'observed': n, 'tree': args.tree})
    return 0


if __name__ == '__main__':
    sys.exit(main())
