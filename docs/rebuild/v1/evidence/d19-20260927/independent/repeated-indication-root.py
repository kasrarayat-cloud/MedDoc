import os,json,sys,subprocess,hashlib
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import generation as g
if len(sys.argv)>1:
 code=subprocess.check_output(['git','show',sys.argv[1]+':rebuild/core/generation.py'],text=True)
 exec(compile(code,'<historical-generation>', 'exec'),g.__dict__)
else:code=Path(g.__file__).read_text()
from core.tests.test_word_v3_workflow import two_knees_form_bytes
from documents import word_v3
fields=word_v3.inspect(two_knees_form_bytes())['fields']
notes='Indication: synthetic knee review\nPain: yes\nComments: settled'
answers=g.generate(notes,fields)[0]
print(json.dumps({'source_sha256':hashlib.sha256(code.encode()).hexdigest(),'fields':fields,'answers':answers},indent=2))
