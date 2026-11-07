"""The completion repair's regression corpus (owner directive 2026-11-06, checklist item 1; HARNESS.md "Completion repair
(2026-11-06)"), measured and pinned.

The corpus (tests/fixtures/gi4/completion/corpus.json) holds:
- group A: every counterexample that defeated a withdrawn or narrowed releasing rule (F-ACTS in both forms, F-SECTIONS T
  and L, F-TIME R, F-NEG S's stage form, the package rules of harness repair 2, the round-1 and cycle-3 narrowings,
  competition by act identity, the provider-neutral admission's broad form), each measured on that rule's own tree;
- group B: the installed base's recorded false READYs;
- group C: the installed base's recorded false holds, among them every target the withdrawn rules were built to release;
- group D: the stage-1 lenses' minimal pairs (labelled procedure paragraphs, a failed sub-act, a title with an aside,
  extent, time and performer binding, the bolus's antecedent) and the two fictional retained walk documents (d44a77b3,
  e888f9ce) with the codes Corti, Astra and Fable recorded for them.

Every entry carries the outcome its meaning requires and why:
  R             READY on every path it is measured on
  H:<fact>      held (needs_clarification) for that fact
  L:<reason>    listed or excluded with that reason (an alternative for a participant, excluded for Corti)
  RULING:<q>    a coding ruling is needed before the outcome can be judged (owner class (a))
and, per code, a dict of those for a multi-code entry. ``pinned`` is what this tree reads; ``baseline`` is what the
installed release fd8040d71e44 read (it never moves: no entry may become a false READY that was not one there).

  python -m ops.gi4.completion --report    # the ledger, and every entry whose reading moved from its pin
  python -m ops.gi4.completion --repin     # rewrite the pins from this tree (only beside a declaration)

Synthetic documents only. The retained cases with realistic identifiers (39f0ac49, 88d9db32) are present only through
the paraphrases the earlier repairs' tests use."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / 'tests' / 'fixtures' / 'gi4' / 'completion' / 'corpus.json'

LABEL = {('selected', 'ready'): 'READY', ('selected', 'needs_clarification'): 'HELD',
         ('alternative', 'informational'): 'ALT', ('excluded', 'excluded'): 'EXCL'}
FALSE_READY = frozenset(('FALSE READY', 'needs ruling (installed READY)'))
QUIET = frozenset(('pass', 'not_applicable', 'not_verified', 'info'))


def load(path: Path = FIXTURE) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _lab(p) -> str:
    return LABEL.get((p.bucket, p.status), f'{p.bucket}/{p.status}')


def _facts(p) -> list:
    return sorted({getattr(c, 'fact', '') for c in (p.clarifications or ())})


def _flagged(p) -> list:
    return sorted({c.id for c in p.checks if c.status not in QUIET})


def _dated(text, codes, participants):
    """The pipeline's own date of service (jobs._service_date_of over the context reader's facts), as dated_both."""
    from studio import jobs
    from studio.gi import context as gi_context
    from studio.gi import detect
    from studio.types import NormalizedResponse, to_jsonable
    from studio.validation.engine import assess
    from tests.test_harness_engine import REFERENCE
    facts = gi_context.extract_context(text)
    day = jobs._service_date_of(to_jsonable(facts))
    result = assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                    normalized=NormalizedResponse('corti', 'test@1', tuple(codes)), reference=REFERENCE,
                    service_date=day, provider_status='succeeded', participants=tuple(participants))
    return result, str(day)


def _selected(text, primary):
    """Corti's selected codes, each with one or more exact passages: [[code, quote, quote...], ...]."""
    from studio.types import ProviderCode
    from tests.test_harness_engine import span
    return tuple(ProviderCode('selected', 'cpt', row[0], 'UNVERIFIED PROVIDER WORDING',
                              tuple(span(text, q) for q in row[1:])) for row in primary)


def _readings(text, participants):
    from tests.test_harness_engine import code, read
    by = {}
    for provider, value, *quotes in participants:
        by.setdefault(provider, []).append(code(text, value, *quotes))
    return [read(provider, codes) for provider, codes in by.items()]


def measure(entry: dict, texts: list) -> dict:
    """What this tree reads of one entry, compactly (the same helpers the earlier repairs' pinned tests use)."""
    from tests.test_harness_engine import code, corti, read, run, span
    text = texts[entry['text']]
    kind = entry['kind']
    if kind in ('both', 'dated'):
        which, quote = entry['code'], entry['quote']
        primary = [(c, span(text, q)) for c, q in entry.get('primary', [])]

        def go(codes, participants):
            if kind == 'dated':
                result, day = _dated(text, codes, participants)
            else:
                from tests.test_harness_engine import DAY
                result, day = run(text, codes, participants), str(DAY)
            items = [p for p in result.proposals if p.code == which]
            return '+'.join(_lab(p) for p in items) or '-', [_facts(p) for p in items], \
                result.completeness.get('state'), day, sorted({f for p in items for f in _flagged(p)})
        c = go(corti(*primary, (which, span(text, quote))), ())
        p = go(corti(*primary), [read('astra', [code(text, which, quote)])])
        reading = {'corti': c[0], 'participant': p[0], 'corti_facts': c[1], 'participant_facts': p[1],
                   'completeness': [c[2], p[2]], 'day': c[3]}
        if entry.get('absent_checks'):
            reading['flags'] = [c[4], p[4]]
        return reading
    if kind in ('multi', 'dated_multi'):
        if kind == 'multi':
            result = run(text, corti(*[(c, span(text, q)) for c, q in entry['primary']]),
                         _readings(text, entry['participants']))
            selected = None
        else:
            result, selected = _dated(text, _selected(text, entry['primary']), _readings(text, entry['participants']))
        from studio.validation import engine
        competing = getattr(engine, 'COMPETING_CHECK', None)
        out = {}
        for value in entry['codes']:
            rows = []
            for p in result.proposals:
                if p.code != value:
                    continue
                row = [_lab(p), any(c.id == competing for c in p.checks) if competing else None, _facts(p)]
                if kind == 'dated_multi':
                    row.append(_flagged(p))
                rows.append(row)
            out[value] = rows
        reading = {'outcome': out, 'completeness': result.completeness.get('state')}
        if selected is not None:
            reading['day'] = selected
        return reading
    if kind == 'admission':
        sel = (entry['base'], span(text, entry['base_quote']))
        alone = run(text, corti(sel))
        rows = []
        for who, quote in entry['rows']:
            result = run(text, corti(sel), [read(who, [code(text, entry['act'], quote)])])
            rows.append([who, quote, [_lab(p) for p in result.proposals if p.code == entry['act']],
                         [_lab(p) for p in result.proposals if p.code == entry['base']],
                         result.completeness.get('state')])
        return {'alone': [[_lab(p) for p in alone.proposals if p.code == entry['base']],
                          alone.completeness.get('state')], 'rows': rows}
    raise ValueError(f'unknown entry kind {kind!r}')


def _cat(req: str) -> str:
    return {'R': 'READY', 'H': 'HOLD', 'L': 'LIST', 'RULING': 'HOLD'}[req.split(':')[0]]


def _verdict_single(req, c, p):
    if req.startswith('RULING'):
        return 'needs ruling (installed READY)' if 'READY' in (c + p) else 'held pending ruling'
    k = _cat(req)
    if k == 'READY':
        return 'matches' if (c, p) == ('READY', 'READY') else 'FALSE HOLD'
    if 'READY' in c or 'READY' in p:
        return 'FALSE READY'
    if k == 'HOLD':
        return 'matches' if c == 'HELD' else 'listed where a hold is required'
    return 'matches' if c in ('EXCL', 'ALT') else 'safe side (held where listed is required)'


def _verdict_multi(req, outcome):
    out = {code: [o[0] + ('*' if o[1] else '') for o in rows] for code, rows in outcome.items()}
    one_act = all(v == 'H:competing_codes' for v in req.values())
    ready = [c for c, labels in out.items() if any(o.startswith('READY') for o in labels)]
    wrong = []
    if one_act and len(ready) >= 2:
        wrong.append('two READY')
    for code, r in req.items():
        labels = out.get(code, [])
        if _cat(r) == 'READY' and not any(o.startswith('READY') for o in labels):
            wrong.append('false hold')
        if _cat(r) != 'READY' and any(o.startswith('READY') for o in labels) and not (one_act and len(ready) >= 2):
            wrong.append('false READY')
    if any(r.startswith('RULING') for r in req.values()):
        return 'held pending ruling' if not any(o.startswith('READY') for v in out.values() for o in v) else \
            'needs ruling (installed READY)'
    if not wrong:
        return 'matches'
    if 'two READY' in wrong or 'false READY' in wrong:
        return 'FALSE READY'
    return 'FALSE HOLD'


def _verdict_admission(req, reading):
    wrong = set()
    for who, quote, act, base, state in reading['rows']:
        if _cat(req['participant']) != 'READY' and 'READY' in act:
            wrong.add('false READY')
        if _cat(req['corti_base']) == 'READY' and 'READY' not in base:
            wrong.add('false hold')
        if _cat(req['corti_base']) != 'READY' and 'READY' in base:
            wrong.add('false READY')
    return 'matches' if not wrong else ('FALSE READY' if 'false READY' in wrong else 'FALSE HOLD')


def verdict(entry: dict, reading: dict) -> str:
    """The entry's class. An entry with ``absent_checks`` that otherwise matches is WRONG FLAG when a code it reads
    carries one of those checks unpassed (U3: a READY code carrying a false 'incomplete')."""
    req = entry['required']
    if entry['kind'] in ('both', 'dated'):
        out = _verdict_single(req, reading['corti'], reading['participant'])
        flagged = {f for path in reading.get('flags', ()) for f in path}
    elif entry['kind'] in ('multi', 'dated_multi'):
        out = _verdict_multi(req, reading['outcome'])
        flagged = {f for rows in reading['outcome'].values() for row in rows if len(row) > 3 for f in row[3]}
    else:
        return _verdict_admission(req, reading)
    if out == 'matches' and flagged & set(entry.get('absent_checks') or ()):
        return 'WRONG FLAG'
    return out


def ledger(fixture: dict) -> list[tuple[dict, dict, str]]:
    return [(e, r, verdict(e, r)) for e in fixture['entries'] for r in (measure(e, fixture['texts']),)]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--report', action='store_true')
    parser.add_argument('--repin', action='store_true')
    args = parser.parse_args(argv)
    from ops.gi4 import boot
    boot.offline()
    fixture = load()
    rows = ledger(fixture)
    moved = [(e, r, v) for e, r, v in rows if r != e['pinned']['reading'] or v != e['pinned']['verdict']]
    print('entries', len(rows), 'moved from the pins', len(moved))
    for e, r, v in moved:
        print(f"  {e['id']}: {e['pinned']['verdict']} -> {v}  required {json.dumps(e['required'])}")
    for group in sorted({e['group'] for e, _, _ in rows}):
        print(' group', group, dict(Counter(v for e, _, v in rows if e['group'] == group)))
    print(' all', dict(Counter(v for _, _, v in rows)))
    new_false = [e['id'] for e, _, v in rows if v in FALSE_READY and e['baseline']['verdict'] not in FALSE_READY]
    print(' false READY where the baseline had none:', len(new_false), new_false[:20])
    if args.repin:
        for e, r, v in rows:
            e['pinned'] = {'verdict': v, 'reading': r}
        FIXTURE.write_text(json.dumps(fixture, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        print('re-pinned', FIXTURE)
    return 1 if new_false else 0


if __name__ == '__main__':
    sys.exit(main())
