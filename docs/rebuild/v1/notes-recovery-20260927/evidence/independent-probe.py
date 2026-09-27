"""Two finite synthetic wrong-destination probes, no database/provider access; source never mutated."""
import importlib.abc,importlib.util,json,os,sys
from pathlib import Path
root=Path('/opt/meddoc-pro/.worktrees/v1-notes/rebuild')
sys.path.insert(0,str(root))
source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else root/'core/generation.py'
class GenerationCopy(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='core.generation':return importlib.util.spec_from_file_location(fullname,source)
sys.meta_path.insert(0,GenerationCopy())
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_ENV_MANAGED='1',
                  QUILLMD_SECRET_KEY='synthetic-refutation',QUILLMD_DB_PASSWORD='unused')
import django
django.setup()
from core.tests.test_v3_ordinary_notes import field,run
from core import generation as g
print('SOURCE',source)
for label,notes in [
 ('Lt knee','The patient has right knee pain. He reports stiffness in the morning.'),
 ('Allergies','The patient takes aspirin daily. She also takes vitamin D.')]:
 fields=[field('one',label,'long_text')]
 units,_=g.source_units(notes,fields)
 picks={label:[u['quote'] for u in units]}
 answer=run(notes,picks,fields=fields)[label]
 print(json.dumps({'label':label,'notes':notes,'provider_unit_ids':[u['id'] for u in units],
                   'status':answer['status'],'text':answer['text'],'held':bool(answer.get('held_candidate'))},sort_keys=True))
