import hashlib,json,os
from pathlib import Path
from documents import word_v3 as w
C=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus');rows=json.loads((C/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records'];row=next(r for r in rows if r['development_id']=='D31');assert row['offline_filled_copy_replay_supported']
raw=(C/row['corpus_file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256']
out=w.inspect(raw);Path(__file__).with_name('D31-'+os.environ['SLICE_STAGE']+'.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(len(out['fields']))
