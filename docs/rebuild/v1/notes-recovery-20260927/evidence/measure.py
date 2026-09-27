"""Hold rate of the complete-sentence contract on v3 forms, provider simulated by unit selection (ideal picks).
ROOT selects the tree. Picks are QUOTES (round-1's unit indexes resolved once on a751794c's units)."""
import os, sys, json, re
sys.path.insert(0, os.environ['ROOT'])
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
import django; django.setup()
from unittest.mock import patch
from core import generation as g

def field(key, label, kind='text', options=None):
    f = {'key': key, 'label': label, 'kind': kind, 'context': '',
         'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[%d]' % len(key),
                     'target': {'type': 'span', 'start': 0, 'end': 0, 'shape': 'after_label'}, 'fingerprint': '0' * 64}}
    if options is not None: f['options'] = options
    return f

def units_for(notes, fields):
    asked, context, _ = g.v3_generation_fields(fields)
    return g.source_units(notes, asked, context_labels=context)

def run(notes, picks, fields):
    asked, context, v3_fields = g.v3_generation_fields(fields)
    units, _ = g.source_units(notes, asked, context_labels=context)
    ids = []
    sel = []
    for f in asked:
        chosen = []
        for q in picks.get(f['label'], []):
            exact = [u['id'] for u in units if u['quote'] == q]
            containing = [u['id'] for u in units if q in u['quote']]
            chosen.append((exact or containing)[0])
        sel.append(g.UnitSelection(key=f['key'], unit_ids=list(dict.fromkeys(chosen)), conflict=False))
    selections = g.unit_selections(notes, asked, g.UnitSelections(fields=sel), context_labels=context)
    answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
    adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
    return {f['label']: adopted[f['key']] for f in fields}

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'corpus.py')).read())

NEVER = re.compile('(?!)')
SWITCHES = {}
if hasattr(g, 'paragraph_neighbours'):
    SWITCHES = {
        'paragraph (a)+(b)': lambda: patch.object(g, 'paragraph_neighbours', lambda notes, units, *p: {u['id']: (None, None) for u in units}),
        'paragraph (a) only': (lambda real: lambda: patch.object(g, 'paragraph_neighbours', lambda notes, units, *p: {k: (b, None) for k, (b, a) in real(notes, units, *p).items()}))(g.paragraph_neighbours),
        'paragraph (b) only': (lambda real: lambda: patch.object(g, 'paragraph_neighbours', lambda notes, units, *p: {k: (None, a) for k, (b, a) in real(notes, units, *p).items()}))(g.paragraph_neighbours),
        '(c) inner sentence': lambda: patch.object(g, 'inner_sentence_end', lambda text: False),
        '(d) asks/trails off': lambda: patch.object(g, 'ASKS_OR_TRAILS_OFF', NEVER),
        '(e) pointer shape': lambda: patch.object(g, 'points_elsewhere', lambda text: False),
    }
    if hasattr(g, 'plain_value'):
        SWITCHES['R3-1 plain grammar (every value plain)'] = lambda: patch.object(g, 'plain_value', lambda value: True)
    if hasattr(g, 'runs_on'):
        SWITCHES['(g) run-on'] = lambda: patch.object(g, 'runs_on', lambda text: False)

def reasons(notes, fields, label, quotes):
    """Direct reading of the other causes of a hold (current tree only)."""
    asked, context, _ = g.v3_generation_fields(fields)
    units, inherited = g.source_units(notes, asked, context_labels=context)
    labels = g.recognized_labels(asked, context)
    out = []
    if inherited: out.append('note-wide governance')
    for q in quotes:
        u = next((u for u in units if u['quote'] == q), None) or next((u for u in units if q in u['quote']), None)
        parsed = g.tab_source_value(u['quote'], labels)
        if parsed and parsed[0] != label.strip().rstrip(':?').casefold(): out.append("another question's label (R6)")
        if ':' not in u['quote'] and not g.FINITE_STATEMENT_V3.search(u['quote']): out.append('no listed verb')
    kind = next(f.get('kind') for f in fields if f['label'] == label)
    if kind in ('choice', 'checkbox', 'multi_choice'): out.append('option kind')
    return out

total = supported = 0
detail = []
per_rule = {name: 0 for name in SWITCHES}
by_reason = {}
for name, fields, notes, picks in CORPUS:
    out = run(notes, picks, fields)
    flips = {}
    for rule, ctx in SWITCHES.items():
        with ctx():
            flips[rule] = run(notes, picks, fields)
    for label, quotes in picks.items():
        total += 1
        a = out[label]
        ok = a['status'] == 'supported'
        supported += ok
        if not ok:
            only = [rule for rule in SWITCHES if flips[rule][label]['status'] == 'supported']
            why = only or (reasons(notes, fields, label, quotes) if SWITCHES else [])
            for rule in only: per_rule[rule] += 1
            key = ' + '.join(why) if why else 'other'
            by_reason[key] = by_reason.get(key, 0) + 1
            detail.append(f'  {name:10} {label:28} HELD  [{key}]  {quotes[0][:60]!r}')
print(f'{os.environ.get("TAG")}: supported {supported}/{total}; held {total-supported} = {(total-supported)/total:.0%}')
if SWITCHES:
    print('  holds lifted by disabling ONE rule alone:', per_rule)
    for k, v in sorted(by_reason.items(), key=lambda kv: -kv[1]): print(f'    {v:3}  {k}')
if os.environ.get('DETAIL'): print('\n'.join(detail))
