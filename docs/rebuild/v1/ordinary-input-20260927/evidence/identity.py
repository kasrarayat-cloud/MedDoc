"""Byte-identity: tab, WM and legacy forms, request + pricing + fixture + validated results."""
from harness import *
if os.environ.get('TASK_GENERATION_BASE'):
    exec(compile(open(os.environ['TASK_GENERATION_BASE']).read(), os.environ['TASK_GENERATION_BASE'], 'exec'), g.__dict__)
import json, hashlib, decimal, sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from documents.engine import docx_inspect
from documents.service import inspect_template
ROOTP = Path(ROOT)
tab = docx_inspect(ROOTP/'documents/__fixtures__/Colonoscopy_Operative_Template.docx')[3]
wm = [{'key': 'sdt_-213273323', 'label': 'Right impression: reflux or absence', 'kind': 'choice',
       'options': ['reflux positive.', 'is absent.'], 'locator': {'sdt_id': '-213273323'}},
      {'key': 'measurement_1_1', 'label': 'Right GSV at the SFJ: diameter (mm)', 'kind': 'measurement',
       'options': [], 'locator': {'table': 0, 'row': 1, 'column': 1, 'unit': 'mm'}},
      {'key': 'patient_name', 'label': 'Patient name', 'kind': 'text', 'options': [], 'locator': {}},
      {'key': 'location_11', 'label': 'Right leg', 'kind': 'text', 'options': [], 'locator': {'row': 11, 'column': 0}},
      {'key': 'sm', 'label': 'Smoker', 'kind': 'choice', 'options': ['Yes','No'], 'locator': {'sdt_id': '5'}}]
legacy = [{'key':'q%d'%i,'label':lab,'locator':{'table':0,'row':i,'col':1}} for i,lab in enumerate(
    ['Allergies','Smoker','Chief complaint','Plan','Consent obtained','Clinician signature','Visit — 1','Visit — 2'])]
from core.tests.test_natural_tab_generation import NOTES as TAB_NOTES
CORPUS = [TAB_NOTES, 'Allergies: penicillin.\nSmoker: yes?\nPlan: rest.', 'Patient presents with knee pain. Return if symptoms worsen.',
          'Smoker: Yes. Quit in 2015.', 'Father: MI at 50. Smoker: yes.', 'The wound is healing well.',
          'PATIENT NAME: Synthetic\nProcedure: colonoscopy\nThe scope was advanced to the cecum.', 'Consent obtained: yes. To be obtained tomorrow.',
          'Findings: none of the following:\nPolyps.\nMass.', 'Right leg: no reflux.\nLeft leg: reflux 2 seconds.']
from core.tests.test_v3_ordinary_notes import live_config
LIVE = live_config()
def default(o):
    if isinstance(o, decimal.Decimal): return str(o)
    if isinstance(o, SimpleNamespace): return vars(o)
    return repr(o)
def request(notes, fields):
    cap = {}
    def create(**kw):
        cap.update(kw); raise RuntimeError('stop')
    client = MagicMock(); client.messages.create.side_effect = create
    with patch('anthropic.Anthropic', return_value=client):
        try: g.generate(notes, fields, LIVE)
        except RuntimeError: pass
        except Exception as e: return 'RAISE ' + repr(e)
    return cap
def response_for(notes, fields, payload):
    labels = g.recognized_labels(fields)
    out = []
    units = payload.get('source_units')
    for q in payload['questions']:
        lab = q['label'].strip().rstrip(':?').casefold()
        if units is not None:
            ids = [u['id'] for u in units if (p := g.labelled_value(u['quote'], labels)) and p[0] == lab and p[1]]
            out.append({'key': q['key'], 'unit_ids': ids, 'conflict': False})
        else:
            qs = [line.strip() for line in notes.splitlines() if (p := g.labelled_value(line, labels)) and p[0] == lab and p[1]]
            out.append({'key': q['key'], 'quotes': qs, 'conflict': False})
    return SimpleNamespace(model='claude-sonnet-5', usage=SimpleNamespace(input_tokens=1, output_tokens=1), stop_reason='end_turn',
                           content=[SimpleNamespace(type='text', text=json.dumps({'fields': out}))], _request_id='synthetic')
def live_validated(notes, fields):
    cap = {}
    def create(**kw):
        cap.update(kw); return response_for(notes, fields, json.loads(kw['messages'][0]['content']))
    client = MagicMock(); client.messages.create.side_effect = create
    with patch('anthropic.Anthropic', return_value=client):
        try:
            raw, *_ = g.generate(notes, fields, LIVE)
            return g.validated(raw)
        except Exception as e: return 'RAISE ' + repr(e)
results = {}
for name, fields in [('tab', tab), ('wm', wm), ('legacy', legacy)]:
    for i, notes in enumerate(CORPUS):
        k = f'{name}/{i}'
        r = {}
        try: r['maxcost'] = str(g.maximum_cost(notes, fields, LIVE))
        except Exception as e: r['maxcost'] = 'RAISE ' + repr(e)
        req = request(notes, fields)
        r['request'] = req if isinstance(req, str) else {'system': req['system'], 'content': req['messages'][0]['content'], 'schema': req['output_config']}
        try: r['fixture'] = g.generate(notes, fields, g.configuration())[0]
        except Exception as e: r['fixture'] = 'RAISE ' + repr(e)
        r['live'] = live_validated(notes, fields)
        results[k] = r
blob = json.dumps(results, sort_keys=True, default=default)
open(os.path.join(os.path.dirname(__file__), f'identity-{TREE}.json'), 'w').write(blob)
print(TREE, len(results), 'cases', hashlib.sha256(blob.encode()).hexdigest(), 'fields', len(tab), len(wm), len(legacy))
