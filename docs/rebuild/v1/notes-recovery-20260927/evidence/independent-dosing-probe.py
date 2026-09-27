"""Finite synthetic repeated-dose preservation probe. No database/provider calls or source mutation."""
import importlib.abc,importlib.util,json,os,sys
from pathlib import Path
root=Path('/opt/meddoc-pro/.worktrees/v1-notes/rebuild')
sys.path.insert(0,str(root))
source=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent/'finished-generation.py'
class GenerationCopy(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='core.generation':return importlib.util.spec_from_file_location(fullname,source)
sys.meta_path.insert(0,GenerationCopy())
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_ENV_MANAGED='1',
                  QUILLMD_SECRET_KEY='synthetic-refutation',QUILLMD_DB_PASSWORD='unused')
import django;django.setup()
from core.tests.test_v3_ordinary_notes import field
from core import generation as g
notes='The patient will take one tablet now. She will wait five minutes. The patient will take one tablet now.'
fields=[field('one','Plan','long_text')]
units,_=g.source_units(notes,fields)
selection=g.UnitSelections(fields=[g.UnitSelection(key='one',unit_ids=[u['id'] for u in units],conflict=False)])
selection=g.unit_selections(notes,fields,selection)
answer=g.validate_selections(notes,fields,selection,evidence_contract=g.TAB_CONTRACT)['one']
print('SOURCE',source)
print(json.dumps({'notes':notes,'unit_ids':[u['id'] for u in units],'answer':answer,
                  'finalization_governed':g.governed_decisions(notes,fields,{'one':{**answer,'reviewed':True}})},indent=2))
