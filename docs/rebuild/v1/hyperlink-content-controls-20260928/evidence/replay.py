import hashlib
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).resolve()
retained = pathlib.Path(sys.argv[2]).resolve()
output = pathlib.Path(sys.argv[3]).resolve()
output.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(source/'rebuild'))
from documents import word_v3 as w

before = json.loads((retained/'results.json').read_text())
result = {'source': str(source), 'word_v3_sha256': hashlib.sha256((source/'rebuild/documents/word_v3.py').read_bytes()).hexdigest(), 'cases': []}
def links(raw):
    tree = w.open_package(raw).tree('word/document.xml')
    return [w.etree.tostring(h).decode() for h in tree.iter(w.q('w:hyperlink'))]

for case in before['cases']:
    name = case['case']; raw = (retained/(name+'.docx')).read_bytes()
    record = {'case': name, 'original_sha256': hashlib.sha256(raw).hexdigest()}
    assert record['original_sha256'] == case['original_sha256']
    try:
        info = w.inspect(raw)
        record['fields'] = info['fields']; record['notes'] = info['notes']
        answers = {f['key']: (True if f['kind']=='checkbox' else 'Synthetic patient answer') for f in info['fields']}
        filled = w.fill(raw, info['fields'], answers)
        (output/(name+'-current.docx')).write_bytes(filled)
        record['current_links_unchanged'] = links(raw) == links(filled)
        record['current_answer_visible'] = b'Synthetic patient answer' in w.open_package(filled).zip.read('word/document.xml')
    except Exception as exc:
        record['current_exception'] = {'type': type(exc).__name__, 'message': str(exc), 'code': getattr(exc, 'code',None)}
    try:
        old = w.fill(raw, case.get('fields',[]), case.get('answers',{}))
        (output/(name+'-historical.docx')).write_bytes(old)
        record['historical_links_unchanged'] = links(raw)==links(old)
    except Exception as exc:
        record['historical_exception'] = {'type': type(exc).__name__, 'message': str(exc), 'code': getattr(exc,'code',None)}
    result['cases'].append(record)
(output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
