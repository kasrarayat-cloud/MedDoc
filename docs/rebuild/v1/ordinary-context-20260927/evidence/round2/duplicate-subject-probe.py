import os,json,sys
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
fields=[field('m','Medications','long_text')]
quotes=['Current medications are aspirin daily.','Current medications are metformin twice daily.']
notes='\n'.join(quotes)
answer=run(notes,{'Medications':[quotes[0]]},fields=fields)['Medications']
print(json.dumps({'notes':notes,'picks':[quotes[0]],'answer':answer,'finalize':g.governed_decisions(notes,fields,{'m':{**answer,'reviewed':True}})},indent=2))
