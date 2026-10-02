from pathlib import Path
import importlib.util,sys,json,subprocess,hashlib
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-notes-workflows/rebuild/.runtime/word-paired-independent-20260927')
FINAL='649f65c2bd32b5b994611de91f9cb24cd6522034'
raw=subprocess.check_output(['git','show',FINAL+':rebuild/documents/word_v3.py'],cwd='/opt/meddoc-pro')
p=ROOT/'final-word_v3.py';p.write_bytes(raw)
spec=importlib.util.spec_from_file_location('documents.independent_final',p);w=importlib.util.module_from_spec(spec);sys.modules[spec.name]=w;spec.loader.exec_module(w)
prior=json.loads((ROOT/'probe.json').read_text());out={'candidate':FINAL,'engine_sha256':hashlib.sha256(raw).hexdigest(),'cases':[]}
for row in prior['cases']:
 source=(ROOT/(row['kind']+'.docx')).read_bytes();assert hashlib.sha256(source).hexdigest()==row['source_sha256']
 result=w.inspect(source);actual={'fields':[{'label':f['label'],'slot':f['locator']['slot'],'target':f['locator']['target']} for f in result['fields']], 'warnings':result.get('warnings'),'notes':result.get('notes')}
 expected=row['candidate'] if row['kind']=='plain' else row['base']
 out['cases'].append({'kind':row['kind'],'source_sha256':row['source_sha256'],'actual':actual,'matches_expected':actual==expected})
(ROOT/'replay-final.json').write_text(json.dumps(out,indent=2));print(json.dumps({'source_sha256':out['engine_sha256'],'cases':[(row['kind'],row['matches_expected']) for row in out['cases']]}))
assert all(row['matches_expected'] for row in out['cases'])
