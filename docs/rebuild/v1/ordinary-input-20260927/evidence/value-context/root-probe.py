import os,json,hashlib
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import FIELDS,run
rows=[]
for prefix in ['Father: MI at 50.','Family history is coronary disease.','Patient presents with knee pain.']:
 notes=prefix+' Smoker: No.'
 whole='Smoker: No.'
 selected=run(notes,{'Smoker':[whole]})['Smoker']
 for quote in [whole,'No.']:
  start=notes.index(quote)
  answer={'status':'supported','text':'No','reviewed':True,'evidence':[{'quote':quote,'start':start,'end':start+len(quote)}]}
  labels=g.recognized_labels(FIELDS)
  rows.append({'notes':notes,'quote':quote,'whole_generation':selected['status'],'valid_locator':g.v3_labelled_source(notes,labels,'smoker',answer['evidence']),'governed':g.governed_decisions(notes,FIELDS,{'v3_4':answer})})
print(json.dumps({'source_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
