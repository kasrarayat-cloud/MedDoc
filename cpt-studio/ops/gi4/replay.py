"""H1: offline replay of the regression encounters (h4-01..h4-06, h2-08, h2-10). NOT a live replay: nothing is sent,
no database is read, sockets refuse to connect.

Each document is read by the tree's own readers in every member state (regression.member_states: none, the walk's
answer, each documented date, 1998-01-01, one day either side, a plan date), exactly as the stages read it: the analyze
child's facts merged with the member's answer (jobs._merged_facts), the date the request then carries
(jobs._service_date_of) or the member-date hold, the request bytes (the Corti request builder), and the assess child
(jobs._assess_child) with the retained provider answer whose request is byte-identical. A state whose request no
retained run answers is assessed with the walk's answer as a COUNTERFACTUAL (marked so); a held state is assessed as the
pipeline assesses a hold: provider status 'failed', no answer. Reference rows are synthetic and the same on every tree
(the minimal design's rows), so fingerprints compare across trees, not with the live service's.

Per document the JSON records the context fact and which answers are accepted, the dateless and dated request sha256s,
routing and inventory readings, every proposal (bucket, status, non-pass checks, fingerprint), the clarifications, the
second-review offers and completeness, and the manifest expectations scored HARD (safety) or SOFT (the author's,
provisional).

  python -m ops.gi4.replay --fixtures [--tree DIR] [--out DIR]
  python -m ops.gi4.replay --inputs DIR --h210-runs FILE [--tree DIR]
  python -m ops.gi4.replay --fixtures --base REF --head REF          (difference two trees; exit 1 on any difference)
  python -m ops.gi4.replay --fixtures --base REF --controls          (the positive controls)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from ops.gi4 import boot, regression

# The minimal design's synthetic reference rows (the judge reproduced its replay byte for byte with them).
PFS_ROW = {'status': 'A', 'global_days': '000', 'mult_proc': '2', 'endo_base': '43235', 'pctc': '0'}
MUE_ROW = {'value': 1, 'mai': {'indicator': '2', 'label': 'Date of service edit'}, 'rationale': 'Anatomic'}
# The dates of service the authors read in each source (the manifests' expected_context and review_plan; h4-03's walk
# note: both dates are the same case's, so either may be the member's answer; h2-08: the owner's 2026-10-28 decision, a
# charge block's other date is never an answer; h2-10 has no manifest: its labelled date of service). A request may carry
# no date or one of these, never another (HARD).
TRUTH_DATES = {'h4-01': ('2026-10-26',), 'h4-02': ('2026-10-21',), 'h4-03': ('2026-10-06', '2026-10-08'),
               'h4-04': ('2026-10-19',), 'h4-05': ('2026-10-15',), 'h4-06': ('2026-10-27',), 'h2-08': ('2026-10-05',),
               'h2-10': ('2026-10-23',)}
POSITIVE = ('performed', 'incomplete')


def modules():
    """The tree's modules the replay reads (imported lazily: the tree is chosen before anything imports studio)."""
    from django.conf import settings
    from studio import jobs
    from studio.gi import context, detect, services
    from studio.providers.base import ProviderUnavailable
    from studio.providers.corti import ADAPTER_VERSION, build_coding_request, normalize_coding_response
    from studio.reference.store import PFS, PrefetchedReferenceLookup, selected_codes
    from studio.types import PageSpan, ReferenceSourceInfo
    return SimpleNamespace(settings=settings, jobs=jobs, context=context, detect=detect, services=services,
                           ProviderUnavailable=ProviderUnavailable, ADAPTER_VERSION=ADAPTER_VERSION,
                           build=build_coding_request, normalize=normalize_coding_response, PFS=PFS,
                           Prefetched=PrefetchedReferenceLookup, selected=selected_codes, PageSpan=PageSpan,
                           SourceInfo=ReferenceSourceInfo)


def _short(value, n=240):
    value = ' '.join(str(value or '').split())
    return value if len(value) <= n else value[:n] + '...'


def _reference(m, doc, normalized):
    fields = m.SourceInfo.__dataclass_fields__
    sources = tuple(m.SourceInfo(**{k: str(e.get(k, '')) for k in fields}) for e in doc['reference_sources'])
    codes = m.selected(normalized)
    rows = {s.key: {(c, ''): dict(PFS_ROW if s.kind == m.PFS else MUE_ROW) for c in codes} for s in sources}
    return m.Prefetched(sources, rows, codes)


def _request(m, text, day):
    try:
        return m.build('corti', m.ADAPTER_VERSION, text, day, m.settings.PROVIDER_MAX_REQUEST_BYTES)
    except m.ProviderUnavailable as exc:
        return SimpleNamespace(canonical_sha256='', refused=str(exc))


def fact_view(fact) -> dict:
    get = fact.get if isinstance(fact, dict) else (lambda k, d=None: getattr(fact, k, d))
    evidence = get('evidence') or ()
    return {'origin': get('origin'), 'value': get('value'),
            'evidence': [_short(e['text'] if isinstance(e, dict) else e.text, 120) for e in evidence],
            'note': _short(get('note'), 400)}


def routing_view(data: dict) -> dict:
    return {f['family']: {'status': f['status'], 'facts': [[x['name'], x['value'], x['origin']] for x in f['facts']],
                          'missing': list(f['missing']), 'mentions': sorted({x['status'] for x in f['mentions']})}
            for f in data['findings']}


def inventory_view(services: dict) -> list:
    return [{'id': s['id'], 'family': s['family'], 'status': s['status'], 'completion': s['completion'],
             'extent': s['extent'], 'routing': s['routing_status'], 'scope': [s.get('scope_start'), s.get('scope_end')],
             'acts': [[a['kind'], a['status']] for a in s['acts']]} for s in (services or {}).get('services', [])]


def proposal_view(p) -> dict:
    return {'code': p.code, 'family': p.family, 'bucket': p.bucket, 'status': p.status, 'fingerprint': p.fingerprint,
            'exclusion_reason': _short(p.exclusion_reason, 160),
            'checks': [[c.id, c.status] for c in p.checks if c.status not in ('pass', 'not_verified', 'not_applicable')],
            'clarifications': sorted(c.fact for c in p.clarifications)}


def replay_state(m, doc, document_facts, label, answer, walk_run) -> dict:
    text = doc['text']
    user = {'service_date': answer} if answer else {}
    facts_json = m.jobs._merged_facts(document_facts, user)
    sd = facts_json['service_date']
    held = m.context.is_member_conflict(sd)
    day = m.jobs._service_date_of(facts_json)
    sends = 'HELD' if held else (day.isoformat() if day else 'DATELESS')
    request = None if held else _request(m, text, day)
    by_sha = {r['request_sha256']: r for r in doc['runs'] if r['request_sha256'] and r['response'] is not None}
    if held:
        provider_status, normalized, response = 'failed', None, 'held: the member-date hold sends nothing'
    elif request.canonical_sha256 in by_sha:
        run = by_sha[request.canonical_sha256]
        provider_status, response = 'succeeded', f'retained {run["run"]}'
        normalized = m.normalize('corti', request, json.dumps(run['response']).encode())
    elif walk_run is not None and request.canonical_sha256:
        provider_status, response = 'succeeded', f'COUNTERFACTUAL: the answer of {walk_run["run"]} (no retained run answers this request)'
        normalized = m.normalize('corti', request, json.dumps(walk_run['response']).encode())
    else:
        provider_status, normalized, response = 'not_run', None, 'no answer'
    reference = _reference(m, doc, normalized)
    context = m.jobs.context_facts(SimpleNamespace(facts=facts_json))
    data, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context, normalized, reference,
                                        provider_status, 'ok', ())
    m.jobs.release_routing_caches()
    completeness = result.completeness or {}
    return {
        'answer': answer, 'fact': fact_view(sd), 'held': held, 'sends': sends,
        'taken': sd.get('origin') == 'user' and sd.get('value') == answer if answer else None,
        'request_sha256': getattr(request, 'canonical_sha256', None) if request is not None else None,
        'response': response, 'document_kind': data.get('document_kind'), 'routing': routing_view(data),
        'inventory': inventory_view(result.services),
        'proposals': [proposal_view(p) for p in result.proposals],
        'clarifications': [[q.scope, q.family, q.fact, _short(q.question, 160)] for q in result.clarifications],
        'proposal_clarifications': sorted({(q.scope, p.family, q.fact) for p in result.proposals
                                           for q in p.clarifications}),
        'completeness': {'state': completeness.get('state'), 'unresolved': completeness.get('unresolved')},
        'offers': [{'family': u.get('family'), 'reason': u.get('reason'), 'second_review': u.get('second_review'),
                    'label': _short(u.get('label'), 120)} for u in completeness.get('unresolved_items', [])],
        'encounter_checks': [[c.id, c.status] for c in result.encounter_checks
                             if c.status not in ('pass', 'not_verified', 'info')],
    }


def replay_document(m, doc) -> dict:
    text = doc['text']
    document_facts = m.context.extract_context(text)
    states = regression.member_states(doc)
    succeeded = [r for r in doc['runs'] if r['response'] is not None and r['state'] == 'succeeded']
    walk = doc.get('walk_answer') or (TRUTH_DATES.get(doc['id']) or (None,))[0]
    walk_run = next((r for r in reversed(succeeded) if r['service_date'] == walk), succeeded[-1] if succeeded else None)
    record = {
        'text_sha256': boot.sha256_text(text), 'walk_answer': doc.get('walk_answer'),
        'fact': fact_view(document_facts['service_date']),
        'other_facts': {n: [f.origin, f.value] for n, f in sorted(document_facts.items()) if n != 'service_date'},
        'requests': {'dateless': _request(m, text, None).canonical_sha256,
                     'stored': {r['run']: [r['service_date'], r['request_sha256']] for r in doc['runs']}},
        'states': {},
    }
    for label, answer in states:
        record['states'][label] = replay_state(m, doc, document_facts, label, answer, walk_run)
    record['accepted_answers'] = sorted(s['answer'] for s in record['states'].values() if s['answer'] and s['taken'])
    record['held_answers'] = sorted(s['answer'] for s in record['states'].values() if s['answer'] and s['held'])
    record['requests']['dated'] = {s['sends']: s['request_sha256'] for s in record['states'].values()
                                   if s['sends'] not in ('HELD', 'DATELESS')}
    record['expectations'] = score(doc, record)
    return record


# --- manifest expectations -------------------------------------------------------------------------------------------

def _ready(state, family=None, code=None):
    return [p for p in state['proposals'] if p['bucket'] == 'selected' and p['status'] == 'ready'
            and (family is None or p['family'] == family) and (code is None or p['code'] == code)]


def score(doc, rec) -> list:
    """The manifest's expectations against the replay: HARD (safety), SOFT (the author's, provisional) or INFO."""
    out = []

    def add(level, ident, ok, state, detail=''):
        out.append({'level': level, 'id': ident, 'ok': bool(ok), 'state': state, 'detail': _short(detail, 300)})

    states, man = rec['states'], doc.get('manifest') or {}
    before = states['none']
    after = states.get('walk', before)
    truth = TRUTH_DATES.get(doc['id'], ())
    for label, st in states.items():  # HARD: a request carries no date or the document's own
        add('HARD', f'date.sends-only-the-truth[{label}]', st['sends'] in ('HELD', 'DATELESS') or st['sends'] in truth,
            label, f"sends {st['sends']}; truth {list(truth)}")
    stored = {r[0]: r[1] for r in rec['requests']['stored'].values() if r[1]}
    for day, sha in sorted(stored.items(), key=lambda kv: str(kv[0])):
        if day is None:
            ok, detail = rec['requests']['dateless'] == sha, f"dateless now {rec['requests']['dateless'][:8]}, stored {sha[:8]}"
        else:
            now = next((s['request_sha256'] for s in states.values() if s['sends'] == day), None)
            ok, detail = now == sha, f"{day}: now {(now or '-')[:8]}, stored {sha[:8]}"
        add('HARD', f'request.bytes-equal-stored[{day or "dateless"}]', ok, 'all', detail)
    context = man.get('expected_context') or {}
    if 'conflict' in ((context.get('service_date') or {}).get('origin_in') or ()):
        add('HARD', 'date.conflict-never-sent-before-the-answer', before['sends'] in ('HELD', 'DATELESS'), 'none',
            f"sends {before['sends']}")
    for item in man.get('expected_clarifications') or ():
        level = 'HARD' if item['fact'] == 'service_date' else 'SOFT'
        found = [q for q in before['clarifications'] if q[2] == item['fact']
                 and (not item.get('scope_in') or q[0] in item['scope_in'])]
        add(level, f"clarification.open[{item['fact']}]", found, 'none', str(found[:1]))
    for item in man.get('must_not_code') or ():
        ready = _ready(after, item['family'])
        add('HARD', f"must-not-code[{item['family']}]", not ready, 'walk', str([p['code'] for p in ready]))
        held = [p['code'] for p in after['proposals'] if p['bucket'] == 'selected' and p['family'] == item['family']
                and p['status'] != 'ready']
        if held:
            add('INFO', f"must-not-code-selected[{item['family']}]", False, 'walk', f'selected, not excluded: {held}')
    routing = man.get('expected_routing') or {}
    for family in routing.get('not_performed') or ():
        f = before['routing'].get(family)
        bad = f is not None and (f['status'] in POSITIVE or any(s in POSITIVE for s in f['mentions']))
        add('HARD', f'not-performed[{family}]', not bad, 'none', f and f"{f['status']} {f['mentions']}")
    for family in man.get('incomplete_services') or ():
        family = family['family'] if isinstance(family, dict) else family
        bad = [p['code'] for p in _ready(after, family) if not p['checks']]
        add('HARD', f'incomplete-signalled[{family}]', not bad, 'walk', str(bad))
    for name, want in context.items():
        got = before['fact'] if name == 'service_date' else dict(zip(('origin', 'value'),
                                                                     rec['other_facts'].get(name, [None, None])))
        ok = got['origin'] in want.get('origin_in', [got['origin']]) and (
            'value_in' not in want or got['value'] in want['value_in'])
        add('SOFT', f'context[{name}]', ok, 'none', f"{got['origin']} {got['value']}; want {want}")
    for family, want in (routing.get('families') or {}).items():
        f = before['routing'].get(family)
        if want.get('presence') == 'required' or f is not None:
            add('SOFT', f'routing.status[{family}]', f is not None and f['status'] in want.get('status_in', [f['status']]),
                'none', f"{f and f['status']}; want {want.get('status_in')}")
        facts = {x[0]: x for x in (f or {}).get('facts', [])}
        for fact, rule in (want.get('facts') or {}).items():
            got = facts.get(fact)
            ok = got is not None and got[2] == 'document' and (
                not rule.get('value_contains_any')
                or any(w.lower() in str(got[1]).lower() for w in rule['value_contains_any']))
            add('SOFT', f'routing.fact[{family}.{fact}]', ok, 'none', str(got))
        for fact in want.get('missing_excludes') or ():
            add('SOFT', f'routing.not-missing[{family}.{fact}]', f is not None and fact not in f['missing'], 'none',
                str(f and f['missing']))
        for fact in want.get('missing_includes') or ():
            add('SOFT', f'routing.missing[{family}.{fact}]', f is not None and fact in f['missing'], 'none',
                str(f and f['missing']))
        info = want.get('informational') or {}
        for fact, rule in (info.get('facts') or {}).items():
            got = facts.get(fact)
            add('INFO', f'routing.fact[{family}.{fact}]', got is not None and any(
                w.lower() in str(got[1]).lower() for w in rule.get('value_contains_any', [])), 'none', str(got))
        if info.get('mention_statuses_include'):
            add('INFO', f'routing.mentions[{family}]', f is not None and set(info['mention_statuses_include'])
                <= set(f['mentions']), 'none', str(f and f['mentions']))
    plan = man.get('review_plan') or {}
    for code in plan.get('approve_codes') or ():
        add('SOFT', f'approvable[{code}]', _ready(after, code=code), 'walk',
            str([[p['code'], p['bucket'], p['status']] for p in after['proposals'] if p['code'] == code]))
    for code in man.get('author_codes') or ():
        add('INFO', f'author-code-ready[{code}]', _ready(after, code=code), 'walk',
            str([[p['code'], p['bucket'], p['status']] for p in after['proposals'] if p['code'] == code]))
    return out


def summary(result: dict) -> dict:
    rows = {}
    for doc_id, rec in result['documents'].items():
        counts = {}
        for e in rec['expectations']:
            c = counts.setdefault(e['level'], [0, 0])
            c[0] += e['ok']
            c[1] += 1
        rows[doc_id] = {
            'fact': f"{rec['fact']['origin']} {rec['fact']['value']}", 'accepted': rec['accepted_answers'],
            'walk': {k: v for k, v in (rec['states'].get('walk') or rec['states']['none']).items()
                     if k in ('sends', 'request_sha256', 'response')},
            'ready': sorted(p['code'] for p in _ready(rec['states'].get('walk') or rec['states']['none'])),
            'hard': counts.get('HARD', [0, 0]), 'soft': counts.get('SOFT', [0, 0]), 'info': counts.get('INFO', [0, 0]),
            'failed_hard': [e['id'] for e in rec['expectations'] if e['level'] == 'HARD' and not e['ok']],
        }
    return rows


def replay(docs: dict, m=None) -> dict:
    m = m or modules()
    return {'versions': {'context': m.jobs.CONTEXT_VERSION, 'routing': m.detect.ROUTING_VERSION,
                         'inventory': m.services.INVENTORY_VERSION,
                         'engine': __import__('studio.validation.engine', fromlist=['ENGINE_VERSION']).ENGINE_VERSION},
            'documents': {doc_id: replay_document(m, doc) for doc_id, doc in docs.items()}}


# --- command line ----------------------------------------------------------------------------------------------------

def _docs(args):
    if args.inputs:
        return regression.load_inputs(args.inputs, args.h210_runs, args.h210_text)
    if args.fixtures:
        return regression.load_fixtures()
    raise regression.Missing('no regression inputs given: pass --inputs DIR (local only) or --fixtures (committed)')


def _print_summary(result, label):
    print(f'== replay {label}: {json.dumps(result["versions"])}')
    for doc_id, row in summary(result).items():
        print(f"  {doc_id}: fact {row['fact']}; accepted {row['accepted']}; walk sends {row['walk'].get('sends')} "
              f"({(row['walk'].get('request_sha256') or '-')[:8]}, {row['walk'].get('response')}); READY {row['ready']}; "
              f"HARD {row['hard'][0]}/{row['hard'][1]} SOFT {row['soft'][0]}/{row['soft'][1]} "
              f"INFO {row['info'][0]}/{row['info'][1]}" + (f"; HARD failed {row['failed_hard']}" if row['failed_hard']
                                                          else ''))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.replay', description=__doc__.split('\n\n')[0])
    parser.add_argument('--fixtures', action='store_true', help='read the committed derived fixtures')
    parser.add_argument('--inputs', help='the regression inputs directory (local only; skipped when absent)')
    parser.add_argument('--h210-runs')
    parser.add_argument('--h210-text')
    parser.add_argument('--tree', help='the cpt-studio directory to read (default: this harness\'s tree)')
    parser.add_argument('--base', help='git ref (exported, sealed) or cpt-studio directory of the base tree')
    parser.add_argument('--head', help='git ref (exported, sealed) or cpt-studio directory of the head tree')
    parser.add_argument('--controls', action='store_true', help='run the positive controls on --base (or --tree)')
    parser.add_argument('--scratch', help='scratch directory (default: CPT_STUDIO_GI4_SCRATCH or a new temp dir)')
    parser.add_argument('--out', help='write one JSON per document (and summary.json) here')
    parser.add_argument('--json-out', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        docs = _docs(args)
    except regression.Missing as exc:
        print(f'SKIPPED: {exc}')
        return 0
    source = ['--inputs', args.inputs] + (['--h210-runs', args.h210_runs] if args.h210_runs else []) + (
        ['--h210-text', args.h210_text] if args.h210_text else []) if args.inputs else ['--fixtures']
    if args.base or args.head or args.controls:
        scratch = boot.scratch_dir(args.scratch)
        base_tree = boot.tree_arg(args.base, scratch) if args.base else boot.tree_of(args, scratch)
        base = boot.run_tool('replay', base_tree, source, scratch=scratch, label='base')
        _print_summary(base, f'base {base_tree}')
        failed = 0
        if args.head:
            head = boot.run_tool('replay', boot.tree_arg(args.head, scratch), source, scratch=scratch, label='head')
            _print_summary(head, f'head {args.head}')
            diffs = boot.differences(base, head)
            print(f'== base -> head: {"EQUAL" if not diffs else f"{len(diffs)} DIFFERENCES"}')
            print('\n'.join('  ' + d for d in diffs[:80]))
            failed += bool(diffs)
        if args.controls:
            from ops.gi4 import mutants
            again = boot.run_tool('replay', base_tree, source, scratch=scratch, label='again')
            same = boot.differences(base, again)
            print(f'== control 0, base against itself: {"EQUAL" if not same else "DIFFERENT (harness not deterministic)"}')
            failed += bool(same)
            for name in mutants.REPLAY_CONTROLS:
                with mutants.applied(base_tree, name, scratch) as tree:
                    planted = boot.run_tool('replay', tree, source, scratch=scratch, label=name)
                diffs = boot.differences(base, planted)
                print(f'== control {name}: {"DIFFERS" if diffs else "EQUAL (the replay missed a planted mutation)"} '
                      f'({len(diffs)} paths)')
                print('\n'.join('     ' + d for d in diffs[:6]))
                failed += not diffs
        return 1 if failed else 0
    boot.offline(args.tree)
    result = replay(docs)
    if args.json_out:
        boot.write_json(args.json_out, result)
        return 0
    _print_summary(result, str(boot.tree_of(args, Path('.'))))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        for doc_id, rec in result['documents'].items():
            boot.write_json(out / f'{doc_id}.json', rec)
        boot.write_json(out / 'summary.json', {'versions': result['versions'], 'documents': summary(result)})
    return 0


if __name__ == '__main__':
    sys.exit(main())
