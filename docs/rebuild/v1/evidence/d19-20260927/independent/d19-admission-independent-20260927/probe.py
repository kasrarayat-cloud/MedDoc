import os,sys,json,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-word-d19/rebuild');OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1',QUILLMD_STATE_DIR=str(OUT/'state'))
import django;django.setup()
from core import v3_mapping as v
from core.security import private_path
from documents import DocumentError
from documents.word_v3 import FLOATING_INITIALS_REFUSAL
from documents.test_signing_areas import signing_form
floating=signing_form();ordinary=signing_form(table=False)
for name,data in [('floating',floating),('ordinary',ordinary)]:
    p=private_path('templates/'+name+'.docx');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

def version(path,data,warnings=None):return SimpleNamespace(contract='v3',template=SimpleNamespace(original_path='templates/'+path+'.docx',sha256=hashlib.sha256(data).hexdigest(),warnings=[] if warnings is None else warnings))
results=[]
def check(name,version,expected):
    answer=v.generation_refusal(version);assert answer==expected,(name,answer,expected)
    results.append({'case':name,'refusal':answer})
check('floating-warnings-omitted',version('floating',floating),v.GENERATION_EXPORT_REFUSAL)
check('floating-unrelated-old-warning',version('floating',floating,['Historical mapping warning']),v.GENERATION_EXPORT_REFUSAL)
check('ordinary-positive',version('ordinary',ordinary),'')
check('copied-ordinary-file-with-floating-hash',version('ordinary',floating),v.GENERATION_SOURCE_REFUSAL)
check('missing-original',version('missing',floating),v.GENERATION_SOURCE_REFUSAL)
with patch('documents.inspect_template',side_effect=AssertionError('must not inspect')) as inspect:
    check('known-refusal-warning',version('floating',floating,[FLOATING_INITIALS_REFUSAL]),v.GENERATION_EXPORT_REFUSAL)
    check('copied-warning-only-refuses',version('ordinary',ordinary,[FLOATING_INITIALS_REFUSAL]),v.GENERATION_EXPORT_REFUSAL)
    assert inspect.call_count==0
for name,result in [('wrong-contract',{'contract':'v2','sha256':hashlib.sha256(ordinary).hexdigest(),'warnings':[]}),('missing-contract',{'sha256':hashlib.sha256(ordinary).hexdigest(),'warnings':[]}),('wrong-digest',{'contract':'v3','sha256':'0'*64,'warnings':[]}),('missing-digest',{'contract':'v3','warnings':[]})]:
    with patch('documents.inspect_template',return_value=result):check(name,version('ordinary',ordinary),v.GENERATION_SOURCE_REFUSAL)
for name,error in [('parser-unavailable',DocumentError('PRIVATE SOURCE DETAIL')),('unsafe-path',ValueError('PRIVATE PATH DETAIL')),('missing-os-source',FileNotFoundError('PRIVATE FILE DETAIL'))]:
    with patch('documents.inspect_template',side_effect=error):
        check(name,version('ordinary',ordinary),v.GENERATION_SOURCE_REFUSAL)
        assert 'PRIVATE' not in results[-1]['refusal']
print(json.dumps({'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('core/jobs.py','core/v3_mapping.py','core/views.py','documents/word_v3.py')},'cases':results},indent=2))
