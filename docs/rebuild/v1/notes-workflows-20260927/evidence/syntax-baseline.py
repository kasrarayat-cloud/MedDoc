import os, json, socket
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django
django.setup()
from core.tests.test_v3_ordinary_notes import run,field
from core import generation as g
socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network denied'))
cases=[('activities','The patient attends an art class every Monday.'),('history','He fell from a ladder yesterday and hurt his left wrist.'),('history','She developed a rash after amoxicillin.'),('social history','She smokes ten cigarettes a day.'),('history','The patient walks two blocks daily.'),('history','The patient sleeps through the night.'),('history','The patient attending an art class every Monday.'),('history','Warfarin 5 mg daily.'),('history','The patient who attends art classes.'),('history','Right knee.')]
results=[]
for label,notes in cases:
 fs=[field('v3_1',label,'long_text')]
 answer=run(notes,{label:[notes]},fields=fs)[label]
 results.append({'label':label,'notes':notes,'answer':answer})
print(json.dumps(results,indent=2))
