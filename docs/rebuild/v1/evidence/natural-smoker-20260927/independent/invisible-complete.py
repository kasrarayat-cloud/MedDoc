import os, sys, json
from pathlib import Path
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-natural-smoker/rebuild')
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
notes='\u200bThe patient is a nonsmoker.';fields=[field('smoker','Smoker','choice',['Yes','No'])]
units=g.source_units(notes,fields)[0]
print(json.dumps({'notes':notes,'units':units,'answer':run(notes,{'Smoker':[units[0]['quote']]},fields=fields)['Smoker']},indent=2))
