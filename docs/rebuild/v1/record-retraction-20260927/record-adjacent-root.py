import os,sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
root=Path('/opt/meddoc-pro/.worktrees/v1-release/rebuild');sys.path.insert(0,str(root));os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import run
from core.tests.test_v3_literal_subjects import FIELDS
cases=json.loads(Path(os.environ.get('CASES','/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/clinical-repair-5b95a725-20260927/adjacent-cases.json')).read_text());rows=[]
with patch('socket.socket.connect',side_effect=AssertionError('Network denied')):
 for c in cases:
  a=run(c['notes'],c['picks'],fields=FIELDS)[c['target']];q=c['picks'][c['target']][0];start=c['notes'].index(q);key=next(f['key'] for f in FIELDS if f['label']==c['target'])
  old={'status':'supported','text':q,'reviewed':True,'evidence':[{'quote':q,'start':start,'end':start+len(q)}]}
  rows.append({'id':c['id'],'expected':c['expected'],'status':a['status'],'text':a['text'],'forced_refusals':g.governed_decisions(c['notes'],FIELDS,{key:old})})
print(json.dumps({'generation_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
