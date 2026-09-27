import os,json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import run,FIELDS
from core.tests.test_v3_ordinary_context import retained_note,ExactClinicalSubjects
from pathlib import Path
rows=[]
for name,fields,notes,picks in [
 ('inline-smoker',FIELDS,'Patient presents with right knee pain. Smoker: No.',{'Smoker':['Smoker: No.']}),
 ('tail-visit',FIELDS,'Smoker: yes\nPatient seen today.',{'Smoker':['Smoker: yes']}),
 ('tail-social',FIELDS,'Smoker: No.\nThe patient drinks socially.',{'Smoker':['Smoker: No.']})]:
 a=run(notes,picks,fields=fields);units=g.source_units(notes,fields)[0]
 reading=g.governance_for(notes,fields)[11]['preceding']
 rows.append({'name':name,'notes':notes,'units':units,'answers':{k:a[k] for k in picks},'blocks':reading['blocks'],'barriers':reading['barriers'],'patients':reading['patients']})
case=retained_note('r1-note9');notes=case['notes'].replace('\n',' ')
rows.append({'name':'inline-note9-layout-variant','notes':notes,'answers':run(notes,case['picks'],fields=ExactClinicalSubjects.fields)})
print(json.dumps(rows,indent=2))
