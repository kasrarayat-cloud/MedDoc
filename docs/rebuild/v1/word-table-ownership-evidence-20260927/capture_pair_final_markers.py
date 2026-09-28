"""Two authorized DEV originals; isolated deterministic parser only, never corpus scoring."""
import hashlib,json,sys
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
out=Path(__file__).parent
stage,tree=sys.argv[1:];assert stage in ('baseline','paired','final','final-style','final-markers')
sys.path.insert(0,str(Path(tree)/'rebuild'))
from documents.service import inspect_template
base=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
ledger=json.loads((base/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records']
for identity in ('D30','D31'):
 r=next(r for r in ledger if r['development_id']==identity);assert r['offline_filled_copy_replay_supported']
 original=base/r['corpus_file'];raw=original.read_bytes();assert hashlib.sha256(raw).hexdigest()==r['sha256']
 expected=Path(r['prior_expected_map_path']);g=json.loads(expected.read_text())
 if stage=='baseline':
  with ZipFile(original) as z:xml=z.read('word/document.xml')
  (out/(identity+'-source.xml')).write_bytes(xml)
  (out/(identity+'-expected.json')).write_bytes(expected.read_bytes())
 result=inspect_template(original,engine='v3')
 (out/f'{identity}-{stage}.json').write_text(json.dumps({'original_sha256':r['sha256'],'engine_sha256':hashlib.sha256((Path(tree)/'rebuild/documents/word_v3.py').read_bytes()).hexdigest(),'result':result},ensure_ascii=False,indent=2))
 print(identity,stage,len(result['fields']))
