import os,json,time,resource,socket
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core.tests.test_v3_ordinary_notes import field,run
from core import generation as g,v3_syntax
socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network denied'))
cases=['Her father attends an art class every Monday.','Patient reports her father attends an art class every Monday.','The patient asks whether her father attends an art class every Monday.','Patient hopes to attend an art class every Monday.','The patient never attends an art class.','The patient is escorted to an art class by her father.','The patient, whose father attends art classes, attends the group.','The patient says "her father attends an art class".','If the patient improves, the patient attends an art class.','The patient attends an art class every Monday.']
out=[]
for notes in cases:
 fs=[field('v3_1','What activities does the patient attend?','long_text')]
 units=g.source_units(notes,g.v3_generation_fields(fs)[0])[0]
 a=run(notes,{fs[0]['label']:[u['quote'] for u in units]},fields=fs)[fs[0]['label']]
 out.append({'notes':notes,'new_syntax_candidate':not bool(g.FINITE_STATEMENT_V3.search(notes)),'answer':a})
print(json.dumps(out,indent=2))
