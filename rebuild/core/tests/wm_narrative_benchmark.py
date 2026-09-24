"""The frozen WM narrative benchmark: run retained provider-shaped responses through the real validator and score
them against the independently written expectations (cases.json). Two numbers are reported separately and never
netted: WRONG SUPPORTED answers (a value pre-filled that the case does not support) and UNNECESSARY HOLDS (a correct,
supported value sent back for a decision). Refusing everything scores zero wrong and fails on holds and misses.

    python -m core.tests.wm_narrative_benchmark        # prints the report (Django settings required, no database)
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent / 'benchmarks' / 'wm_narrative'


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def responses(model):
    """The careful set covers every case; the weak set overrides the cases it changes."""
    careful = load('responses-careful.json')['cases']
    if model == 'careful':
        return careful
    return {**careful, **load('responses-weak.json')['cases']}


def expected_of(case, key):
    return case['expected_fields'].get(key, {'outcome': 'missing'})


def _space(text):
    return ' '.join(str(text or '').split())


def score_case(case, answers, proposals, requirements):
    counts, rows = Counter(), []
    for key, answer in answers.items():
        expected = expected_of(case, key)
        status, text = answer['status'], answer.get('text', '')
        outcome = expected['outcome']
        if status == 'supported':
            if outcome == 'supported' and _space(text) == _space(expected['value']):
                counts['correct_supported'] += 1
                continue
            counts['wrong_supported'] += 1
            kind = 'wrong_value' if outcome == 'supported' else 'supported_when_' + outcome
        elif status == 'conflict':
            held = (answer.get('held_candidate') or {}).get('text', '')
            # Holding a WRONG value for a decision is the gate working, not an unnecessary hold.
            if outcome == 'supported' and _space(held) != _space(expected['value']):
                kind = 'held_wrong_value'
            else:
                kind = {'supported': 'unnecessary_hold', 'missing': 'held_where_blank_expected', 'decision': 'correct_hold'}[outcome]
        else:
            kind = {'supported': 'missed', 'missing': 'correct_missing', 'decision': 'decision_shown_missing'}[outcome]
        counts[kind] += 1
        if kind not in ('correct_missing', 'correct_hold', 'held_wrong_value'):
            rows.append({'case': case['id'], 'key': key, 'kind': kind, 'expected': expected, 'status': status, 'text': text,
                         'reason': (answer.get('held_candidate') or {}).get('reason', '')})
    for row in requirements:
        if row.get('kind') != 'assertion':
            continue
        want = case['expected_statements'].get(row['key'])
        got = (proposals.get(row['key']) or {}).get('variant')
        if got and got == want:
            counts['statement_correct'] += 1
        elif got:
            counts['statement_wrong'] += 1
            rows.append({'case': case['id'], 'key': row['key'], 'kind': 'statement_wrong', 'expected': want, 'got': got})
        elif want:
            counts['statement_missed'] += 1
    return counts, rows


def run(model, shaped=None):
    from core import wm_narrative
    mapping, cases = load('mapping.json'), load('cases.json')['cases']
    fields, requirements = mapping['fields'], mapping['review_requirements']
    shaped = shaped or responses(model)
    total, rows = Counter(), []
    for case in cases:
        selections = wm_narrative.NarrativeSelections.model_validate(shaped[case['id']])
        answers, proposals = wm_narrative.validate(case['notes'], fields, selections, requirements)
        counts, found = score_case(case, answers, proposals, requirements)
        total.update(counts)
        rows.extend(found)
    return total, rows


#: The gate the careful set must meet (and a regression in either direction is visible): no wrong pre-filled answer,
#: no correct answer sent back, and at least this many correct answers pre-filled. Refusing everything fails it.
CAREFUL_GATE = {'wrong_supported': 0, 'unnecessary_hold': 0, 'correct_supported': 338}


def passes(total, gate=CAREFUL_GATE):
    return (total['wrong_supported'] <= gate['wrong_supported'] and total['unnecessary_hold'] <= gate['unnecessary_hold']
            and total['correct_supported'] >= gate['correct_supported'])


def report():
    out = []
    for model in ('careful', 'weak'):
        total, rows = run(model)
        out.append(f'== {model}: ' + ', '.join(f'{k}={total[k]}' for k in sorted(total)))
        out.extend('   ' + json.dumps(row, ensure_ascii=False) for row in rows)
    return '\n'.join(out)


if __name__ == '__main__':
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
    django.setup()
    print(report())
