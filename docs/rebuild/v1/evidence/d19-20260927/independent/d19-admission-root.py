import os,json,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import v3_mapping as m
from documents import DocumentError
from documents.word_v3 import FLOATING_INITIALS_REFUSAL
rows=[]
for name,stored,result,error,expected,called in [
 ('early-warning',[FLOATING_INITIALS_REFUSAL],None,None,m.GENERATION_EXPORT_REFUSAL,False),
 ('source-warning',[],{'sha256':'a'*64,'contract':'v3','warnings':[FLOATING_INITIALS_REFUSAL]},None,m.GENERATION_EXPORT_REFUSAL,True),
 ('hash-mismatch',[],{'sha256':'b'*64,'contract':'v3','warnings':[]},None,m.GENERATION_SOURCE_REFUSAL,True),
 ('contract-mismatch',[],{'sha256':'a'*64,'contract':'v2','warnings':[]},None,m.GENERATION_SOURCE_REFUSAL,True),
 ('missing-source',[],None,OSError('synthetic missing'),m.GENERATION_SOURCE_REFUSAL,True),
 ('ordinary',[],{'sha256':'a'*64,'contract':'v3','warnings':[]},None,'',True),
]:
 v=SimpleNamespace(contract='v3',fields=[],template=SimpleNamespace(warnings=stored,original_path='synthetic.docx',sha256='a'*64))
 with patch.object(m,'is_v3_version',return_value=True),patch('core.security.private_path',return_value=Path('/nonexistent/synthetic.docx')),patch('documents.inspect_template',return_value=result,side_effect=error) as inspect:
  got=m.generation_refusal(v)
 rows.append({'name':name,'pass':got==expected and bool(inspect.call_count)==called,'result':got,'inspections':inspect.call_count})
print(json.dumps({'source_sha256':hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
assert all(r['pass'] for r in rows)
