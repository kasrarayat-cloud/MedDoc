from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path.cwd()/'rebuild'))
from documents import word_v3 as w
R=Path(__file__).parent
expected=json.loads((R.parent/'word-nested-diagnosis-20260928/D03-expected-original.json').read_text())['answer_areas']
delta=json.loads((R/'06-original-map-delta.json').read_text())
trace=[]
for added in delta['added']:
 identity=added['locator']['part']+'#'+added['locator']['slot']
 matches=[a for a in expected if a['kind']=='text' and identity in a['slots']]
 assert len(matches)==1
 trace.append({'expected':matches[0],'actual':added})
actual=w.inspect((R/'D03-http-after/original.docx').read_bytes())
assert actual['fields']==json.loads((R/'D03-http-after/uploaded-map.json').read_text())
(R/'09-expected-destination-trace.json').write_text(json.dumps({'source_engine_sha256':hashlib.sha256(Path(w.__file__).read_bytes()).hexdigest(),'added_trace':trace,'remaining_notes':actual['notes'],'document_success':False},indent=2,ensure_ascii=False))
print([(a['expected']['id'],a['expected']['context']) for a in trace])
