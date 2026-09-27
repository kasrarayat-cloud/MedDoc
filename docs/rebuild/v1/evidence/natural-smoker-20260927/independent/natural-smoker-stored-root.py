import os,json,hashlib
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import FIELDS
q='The patient is a nonsmoker.';rows=[]
for note in [q,q+'\n\nThe patient smokes daily.']:
 a={'status':'supported','text':'No','reviewed':True,'evidence':[{'quote':q,'start':0,'end':len(q)}]}
 rows.append({'notes':note,'governed':g.governed_decisions(note,FIELDS,{'v3_4':a}),'evidence':a['evidence']})
print(json.dumps({'source_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
