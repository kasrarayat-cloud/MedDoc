from pathlib import Path
import hashlib,json,sys
from zipfile import ZipFile
from lxml import etree
from documents import service,word_v3 as w
R=Path(__file__).parent;B=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
ledger=json.loads((B/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records']
for identity in ('D03','D10'):
 rec=next(r for r in ledger if r['development_id']==identity);assert rec['offline_filled_copy_replay_supported']
 original=B/rec['corpus_file'];raw=original.read_bytes();assert hashlib.sha256(raw).hexdigest()==rec['sha256']
 expected=Path(rec['prior_expected_map_path']);(R/(identity+'-expected-original.json')).write_bytes(expected.read_bytes())
 if identity=='D03':
  independent=B/'custodian-20260927/corpus-independent-renewal-20260927/dev-independent-maps/D03.original-first.json'
  assert hashlib.sha256(independent.read_bytes()).hexdigest()=='ec0cea4f1eb9842af3ae841ac3720f5ef265319aa4276cedf3d8ba49cc32f2fc'
  (R/'D03-expected-independent.json').write_bytes(independent.read_bytes())
 package=w.open_package(raw);idx=w.SlotIndex(package)
 cells=['b/tbl[0]/tr[9]/tc[0]','b/tbl[0]/tr[16]/tc[0]','b/tbl[0]/tr[19]/tc[0]'] if identity=='D03' else ['b/tbl[0]/tr[1]/tc[0]','b/tbl[1]/tr[1]/tc[0]','b/tbl[1]/tr[2]/tc[0]']
 source=[]
 for path in cells:
  slot=idx.by_id['word/document.xml#'+path]
  source.append({'cell':path,'direct_children':[{'slot':x.path,'kind':x.kind,'text':w.text_of(x.el),'xml':etree.tostring(x.el).decode()} for x in slot.children]})
 (R/(identity+'-source-before-output.json')).write_text(json.dumps({'original_sha256':rec['sha256'],'selected_cells':source},ensure_ascii=False,indent=2))
 result=service.inspect_template(original,engine='v3')
 p=R/(identity+'-current.json');assert not p.exists();p.write_text(json.dumps({'original_sha256':rec['sha256'],'source_commit':'649f65c2bd32b5b994611de91f9cb24cd6522034','engine_sha256':hashlib.sha256(Path(w.__file__).read_bytes()).hexdigest(),'result':result},ensure_ascii=False,indent=2))
 print(identity,len(result['fields']))
 for cell in source:
  print('CELL',cell['cell'])
  for child in cell['direct_children']:print(child['kind'],child['slot'],repr(child['text'][:200]))
  for f in result['fields']:
   if f['locator']['slot'].startswith(cell['cell']+'/'):print('FIELD',f['key'],f['kind'],f['label'],f.get('context'),f['locator']['slot'],f['locator']['target'])
