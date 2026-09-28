import hashlib,json,re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
R=Path(__file__).parent
base=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
original=base/'dev/originals/D30-fdeafbee872f.docx';expected=base/'dev/groundtruth/D30-fdeafbee872f.json'
x=json.loads(expected.read_text());assert hashlib.sha256(original.read_bytes()).hexdigest()==x['sha256']
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
with ZipFile(original) as z: root=etree.fromstring(z.read('word/document.xml'))
body=root.find('w:body',ns);slots={}
def visit(node,path):
    counts={}
    for child in node:
        tag=etree.QName(child).localname
        if tag not in ('p','tbl','tr','tc','sdt','sdtContent'):continue
        n=counts.get(tag,0);counts[tag]=n+1;p=f'{path}/{tag}[{n}]';slots['word/document.xml#'+p]=child;visit(child,p)
visit(body,'b')
source=[]
for a in x['answer_areas']:
    refs=[]
    for s in a['slots']:
        e=slots[s];previous=e.getprevious()
        refs.append({'slot':s,'existing_text':' '.join(e.xpath('.//w:t/text()',namespaces=ns)),
          'previous_sibling_text':' '.join(previous.xpath('.//w:t/text()',namespaces=ns)) if previous is not None else None})
    source.append({'expected':a,'source':refs})
(R/'01-D30-independent-source.json').write_text(json.dumps({'original_sha':x['sha256'],'expected_sha':hashlib.sha256(expected.read_bytes()).hexdigest(),'source':source},ensure_ascii=False,indent=2))
# Only after the independent expected/source snapshot is retained, consult the
# already captured current map. This script does not run candidate detection.
actual=json.loads(Path('/opt/meddoc-pro/.worktrees/v1-word-long-questions/rebuild/.runtime/d30-long-questions-20260927/31-final-map.json').read_text())
rows=[];used=set()
for a in x['answer_areas']:
    matches=[]
    for f in actual['fields']:
        s=f['locator']['part']+'#'+f['locator']['slot']
        if any(s==t or s.startswith(t+'/') or t.startswith(s+'/') for t in a['slots']):
            matches.append(f);used.add(f['key'])
    rows.append({'expected':a,'actual':matches})
extras=[f for f in actual['fields'] if f['key'] not in used]
result={'source_commit':'4caa34431a60e6ce3409ecadbbb6989b50659d7b','expected':62,'actual':len(actual['fields']),'rows':rows,'extras':extras,'warnings':actual['warnings'],'score':None,'qualification':False}
(R/'02-D30-destination-trace.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
for row in rows:
    a=row['expected'];fs=row['actual'];print(a['id'],a['kind'],a['label'][:45],'=>',[(f['key'],f['kind'],f['label'],f.get('context',''),f['locator']['target']) for f in fs])
print('EXTRAS')
for f in extras:print(json.dumps(f,ensure_ascii=False))
