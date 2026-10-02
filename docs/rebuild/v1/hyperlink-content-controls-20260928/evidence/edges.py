import pathlib
import sys

# Reuse the retained fixture helpers without rerunning or overwriting its first capture.
helpers = pathlib.Path(__file__).with_name('probe.py').read_text().split("results = {'source':", 1)[0]
exec(helpers, globals())

result = {'source':str(source), 'word_v3_sha256':hashlib.sha256((source/'rebuild/documents/word_v3.py').read_bytes()).hexdigest(), 'cases':[]}
for case in ('ordinary-glyph-linked-option', 'ordinary-glyph-adjacent-link', 'direct-sdt-with-link-ancestor'):
    d = Document(); p = d.add_paragraph()
    if case == 'ordinary-glyph-linked-option':
        p.add_run('☐ '); p._p.append(hyperlink(d,'Send copies'))
    elif case == 'ordinary-glyph-adjacent-link':
        p._p.append(hyperlink(d,'Clinic instructions')); p.add_run(' ☐ Send copies')
    else:
        el, content=sdt(placeholder=True); content.append(run('Enter name'))
        link=hyperlink(d); link.append(el); p._p.append(link)
    stream=io.BytesIO(); d.save(stream); raw=stream.getvalue()
    record={'case':case, 'before_links':links(raw)}
    (outdir/(case+'.docx')).write_bytes(raw)
    try:
        info=w.inspect(raw);record['fields']=info['fields'];record['notes']=info['notes']
        if case == 'direct-sdt-with-link-ancestor':
            package=w.open_package(raw);node=next(package.tree('word/document.xml').iter(w.SDT))
            w.write_sdt_text(node, 'Synthetic patient answer')
            filled=package.write({'word/document.xml':package.tree('word/document.xml')})
        else:
            filled=w.fill(raw,info['fields'],{f['key']:True for f in info['fields']})
        (outdir/(case+'-filled.docx')).write_bytes(filled)
        record['after_links']=links(filled)
        record['hyperlinks_changed']=record['before_links']!=record['after_links']
    except Exception as exc:
        record['exception']={'type':type(exc).__name__,'message':str(exc),'code':getattr(exc,'code',None)}
    result['cases'].append(record)
(outdir/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
