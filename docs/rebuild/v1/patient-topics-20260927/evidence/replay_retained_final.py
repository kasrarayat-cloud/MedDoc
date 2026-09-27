import os,sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
root=Path('/opt/meddoc-pro/.worktrees/v1-patient-topics')
sys.path.insert(0,str(root/'rebuild'))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core.tests.test_v3_ordinary_notes import run
from core import generation as g
source=Path(__file__).with_name('aa4e8-retained-baseline.json')
old=json.loads(source.read_text()); cases=[]; changes=[]
with patch('socket.socket.connect',side_effect=AssertionError('Network denied')):
 for c in old['cases']:
  answers=run(c['notes'],c['unchanged_picks'],fields=c['fields'])
  cases.append({**{k:c[k] for k in ['name','fields','notes','unchanged_picks']},'answers':answers,'selected_supported':sum(answers[k]['status']=='supported' for k in c['unchanged_picks']),'selected_total':len(c['unchanged_picks'])})
  for k in c['unchanged_picks']:
   before={j:c['answers'][k][j] for j in ['status','text']};after={j:answers[k][j] for j in ['status','text']}
   if before!=after:changes.append({'case':c['name'],'field':k,'before':before,'after':after})
out={'scope':'One unchanged fifteen-input deterministic replay; not provider or document compatibility qualification. All previous results retained.','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'generation_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':cases,'status_text_changes':changes}
Path(__file__).with_name('12-retained-final.json').write_text(json.dumps(out,indent=2)+'\n')
for prefix in ['t-','r1-']:
 subset=[c for c in cases if c['name'].startswith(prefix)]; print(prefix,sum(c['selected_supported'] for c in subset),sum(c['selected_total'] for c in subset))
print(json.dumps(changes,indent=2))
