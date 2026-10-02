import pathlib
import sys

helpers=pathlib.Path(__file__).with_name('probe.py').read_text().split("results = {'source':",1)[0]
exec(helpers,globals())
from documents.test_word_v3 import _sdt

retained=pathlib.Path(__file__).parent/'checkbox-first'
first=json.loads((retained/'results.json').read_text())
result={'source':str(source),'word_v3_sha256':hashlib.sha256((source/'rebuild/documents/word_v3.py').read_bytes()).hexdigest(),'cases':[]}
for case in first['cases']:
    raw=(retained/(case['case']+'.docx')).read_bytes()
    record={'case':case['case'],'original_sha256':hashlib.sha256(raw).hexdigest()}
    assert record['original_sha256']==case['original_sha256']
    record['blank_byte_identical']=w.fill(raw,case['fields'],{})==raw
    assert record['blank_byte_identical']
    try:
        w.fill(raw,case['fields'],{f['key']:True for f in case['fields']})
        raise AssertionError('Historical link-owning checkbox write returned')
    except w.V3Failure as exc:
        assert exc.code=='protected_hyperlink'
        record['historical_code']=exc.code
    package=w.open_package(raw);node=next(package.tree('word/document.xml').iter(w.SDT));original=w.etree.tostring(node)
    try:
        w.set_sdt_checkbox(node,True)
        raise AssertionError('Direct link-owning checkbox write returned')
    except w.V3Failure as exc:
        assert exc.code=='protected_hyperlink'
        record['direct_code']=exc.code
    record['direct_xml_unchanged']=w.etree.tostring(node)==original
    assert record['direct_xml_unchanged']
    result['cases'].append(record)

d=Document();p=d.add_paragraph();p._p.append(_sdt('checkbox'));p._p.append(hyperlink(d,'Send copies'))
stream=io.BytesIO();d.save(stream);raw=stream.getvalue()
info=w.inspect(raw);assert len(info['fields'])==1
filled=w.fill(raw,info['fields'],{info['fields'][0]['key']:True})
assert links(raw)==links(filled)
tree=w.open_package(filled).tree('word/document.xml')
checked=next(tree.iter(w.q('w14:checked'))).get(w.q('w14:val'))
assert checked=='1'
result['native_checkbox_separate_link_positive']={'field_count':1,'links_unchanged':True,'checked':checked}
(outdir/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
