"""Probe harness: simulate the provider as test_v3_ordinary_notes does."""
import os, sys, json
TREE = os.environ.get('TREE', 'new')
ROOT = os.environ.get('ROOT') or ('/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/refute-notes/' + TREE + '/rebuild')
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
os.environ.setdefault('QUILLMD_SECRET_KEY', 'probe-only-not-a-secret')
os.environ.setdefault('QUILLMD_AI_MODE', 'fixture')
import django
django.setup()
from core import generation as g

def field(key, label, kind='text', options=None):
    f = {'key': key, 'label': label, 'kind': kind, 'context': '',
         'locator': {'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[%d]' % len(key),
                     'target': {'type': 'span', 'start': 0, 'end': 0, 'shape': 'after_label'}, 'fingerprint': '0' * 64}}
    if options is not None:
        f['options'] = options
    return f

def units_of(notes, fields):
    asked, context, v3_fields = g.v3_generation_fields(fields)
    units, inh = g.source_units(notes, asked, context_labels=context)
    return units, inh

def run(fields, notes, picks, conflicts=(), by_id=False):
    asked, context, v3_fields = g.v3_generation_fields(fields)
    units, _ = g.source_units(notes, asked, context_labels=context)
    by_quote = {u['quote']: u['id'] for u in units}
    sels = []
    for f in asked:
        ids = []
        for q in picks.get(f['label'], []):
            ids.append(q if isinstance(q, int) else by_quote[q])
        sels.append(g.UnitSelection(key=f['key'], unit_ids=ids, conflict=f['label'] in conflicts))
    selections = g.UnitSelections(fields=sels)
    selections = g.unit_selections(notes, asked, selections, context_labels=context)
    answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
    adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
    return {f['label']: adopted[f['key']] for f in fields}

def brief(a):
    d = {'status': a['status'], 'text': a['text']}
    if a.get('suggestion'): d['suggestion'] = a['suggestion']
    if a.get('held_candidate'): d['held'] = a['held_candidate'].get('text')
    return d

def live(fields, notes, picks, conflicts=(), context_labels=()):
    """generate() with a patched Anthropic client that selects units by quote, then validated()."""
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch
    cfg = {**g.configuration(), 'mode':'live','provider':'anthropic','model':'synthetic','input_rate':'3','output_rate':'15','cached_rate':'0.3'}
    sent = {}
    def create(**kw):
        sent.update(kw)
        payload = json.loads(kw['messages'][0]['content'])
        units = payload.get('source_units')
        by_quote = {u['quote']: u['id'] for u in units} if units is not None else None
        out = []
        for q in payload['questions']:
            lab = q['label']
            if by_quote is not None:
                out.append({'key': q['key'], 'unit_ids': [by_quote[x] for x in picks.get(lab, [])], 'conflict': lab in conflicts})
            else:
                out.append({'key': q['key'], 'quotes': list(picks.get(lab, [])), 'conflict': lab in conflicts})
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1), stop_reason='end_turn',
                               content=[SimpleNamespace(type='text', text=json.dumps({'fields': out}))], _request_id='synthetic')
    client = MagicMock(); client.messages.create.side_effect = create
    with patch('anthropic.Anthropic', return_value=client):
        raw, *_ = g.generate(notes, fields, cfg, context_labels=context_labels)
    ans = g.validated(raw)
    return {f['label']: ans[f['key']] for f in fields}, sent
