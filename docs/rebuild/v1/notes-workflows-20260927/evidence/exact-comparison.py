import os,json,types,subprocess,hashlib,socket
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from unittest.mock import patch
from pathlib import Path
from core import generation as current
from core.tests import test_v3_ordinary_notes as helper
from core.tests.test_v3_sentence_syntax import POSITIVES
base_source=subprocess.check_output(['git','show','4caa34431a60e6ce3409ecadbbb6989b50659d7b:rebuild/core/generation.py'])
base=types.ModuleType('core._v1syntax_base');base.__package__='core';exec(compile(base_source,'4caa-generation.py','exec'),base.__dict__)
socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network denied'))
out={'base_generation_sha256':hashlib.sha256(base_source).hexdigest(),'candidate_generation_sha256':hashlib.sha256(Path('core/generation.py').read_bytes()).hexdigest(),'positive_pairs':[],'source_controls':[]}
for label,notes in POSITIVES:
 pair={'label':label,'notes':notes}
 fs=[helper.field('v3_1',label,'long_text')]
 for name,module in [('base',base),('candidate',current)]:
  with patch.object(helper,'g',module):pair[name]=helper.run(notes,{label:[notes]},fields=fs)[label]
 out['positive_pairs'].append(pair)
for row in json.loads(Path('.runtime/notes-workflows-20260927/source-controls.json').read_text()):
 notes=row['notes'];label='What activities does the patient attend?';fs=[helper.field('v3_1',label,'long_text')];pair={'notes':notes}
 for name,module in [('base',base),('candidate',current)]:
  with patch.object(helper,'g',module):
   units=module.source_units(notes,module.v3_generation_fields(fs)[0])[0]
   pair[name]=helper.run(notes,{label:[u['quote'] for u in units]},fields=fs)[label]
 out['source_controls'].append(pair)
retained=json.loads(Path('/opt/meddoc-pro/rebuild/.runtime/v1-astra-recovery-20260927/patient-topics-union-retained.json').read_text())
case=next(c for c in retained['cases'] if c['name']=='r1-note4')
row={'original_case':case}
for name,module in [('base',base),('candidate',current)]:
 with patch.object(helper,'g',module):row[name]=helper.run(case['notes'],case['unchanged_picks'],fields=case['fields'])
out['retained_note4']=row
print(json.dumps(out,indent=2))
