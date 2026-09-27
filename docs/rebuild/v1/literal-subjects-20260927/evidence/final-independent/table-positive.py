import os,sys,json,hashlib,socket
from pathlib import Path
from unittest.mock import patch
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-literal-subjects/rebuild');sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_input import ordinary_input_form
from core.tests.test_v3_ordinary_notes import run
from core.tests.test_word_v3_workflow import part_text
from documents import word_v3
D=Path(__file__).parent;records=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 original=ordinary_input_form(D/'synthetic-table.docx',['Allergies','Examination'])
 fields=word_v3.inspect(original)['fields']
 assert {f['label']:f['context'] for f in fields}=={'Allergies':'Allergies','Examination':'Examination'}
 for name,exam in [('neuro','Neurological examination is normal.'),('heart','Heart and lung examination was normal.')]:
  quote='No known drug allergies.';notes=quote+' '+exam
  answers=run(notes,{'Allergies':[quote],'Examination':[exam]},fields=fields)
  assert all(a['status']=='supported' for a in answers.values())
  stored={f['key']:{**answers[f['label']],'reviewed':True} for f in fields}
  assert g.governed_decisions(notes,fields,stored)==[]
  output=word_v3.fill(original,fields,{f['key']:answers[f['label']]['text'] for f in fields})
  (D/(name+'-export.docx')).write_bytes(output)
  text=part_text(output);assert quote in text and exam in text
  records.append({'case':name,'notes':notes,'fields':fields,'answers':answers,'governed_decisions':[],'export_sha256':hashlib.sha256(output).hexdigest(),'export_text':text})
print(json.dumps({'generation_sha256':hashlib.sha256((ROOT/'core/generation.py').read_bytes()).hexdigest(),'engine_sha256':hashlib.sha256((ROOT/'documents/word_v3.py').read_bytes()).hexdigest(),'original_sha256':hashlib.sha256(original).hexdigest(),'cases':records},indent=2))
