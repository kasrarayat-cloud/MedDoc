import pathlib
import sys

helpers=pathlib.Path(__file__).with_name('probe.py').read_text().split("results = {'source':",1)[0]
exec(helpers,globals())
from documents.test_word_v3 import _sdt

result={'source':str(source),'word_v3_sha256':hashlib.sha256((source/'rebuild/documents/word_v3.py').read_bytes()).hexdigest(),'cases':[]}
for mode in ('glyph-then-fixed-link','linked-glyph-only'):
    d=Document();p=d.add_paragraph();control=_sdt('checkbox')
    content=control.find(w.q('w:sdtContent'))
    if mode == 'glyph-then-fixed-link':
        content.append(hyperlink(d,'forms@example.invalid'))
    else:
        content.clear();content.append(hyperlink(d,'☐'))
    p._p.append(control);p.add_run(' Send copies')
    stream=io.BytesIO();d.save(stream);raw=stream.getvalue()
    # If asked to replay an already captured source, use those exact original bytes.
    if len(sys.argv)>3:
        raw=(pathlib.Path(sys.argv[3])/(mode+'.docx')).read_bytes()
    (outdir/(mode+'.docx')).write_bytes(raw)
    record={'case':mode,'original_sha256':hashlib.sha256(raw).hexdigest(),'before_links':links(raw)}
    try:
        info=w.inspect(raw);record['fields']=info['fields'];record['notes']=info['notes']
        filled=w.fill(raw,info['fields'],{f['key']:True for f in info['fields']})
        (outdir/(mode+'-filled.docx')).write_bytes(filled)
        record['after_links']=links(filled);record['hyperlinks_changed']=record['before_links']!=record['after_links']
    except Exception as exc:
        record['exception']={'type':type(exc).__name__,'message':str(exc),'code':getattr(exc,'code',None)}
    result['cases'].append(record)
(outdir/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
