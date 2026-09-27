import os,json,hashlib
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import FIELDS
notes='Father: MI at 50. Smoker: No.';start=notes.index('No.');rows=[]
for end in [None,start+2,start+3,start+4]:
 evidence={'quote':'No.','start':start}
 if end is not None:evidence['end']=end
 answer={'status':'supported','text':'No','reviewed':True,'evidence':[evidence]}
 rows.append({'end':end,'valid_locator':g.v3_labelled_source(notes,g.recognized_labels(FIELDS),'smoker',[evidence]),'governed':g.governed_decisions(notes,FIELDS,{'v3_4':answer})})
print(json.dumps({'source_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
