"""Adjacent independent checks, source90297ea9, without changing first probe."""
from pathlib import Path
base=Path(__file__).with_name('probe.py').read_text()
exec(compile(base.split('\nrows=[]\n')[0], 'retained-independent-helpers', 'exec'))

rows=[]
for kind in ('scalar','dropdown'):
    for flag in ('present','1','true','on'):
        rows.append(execute(kind+'-genuine-placeholder-'+flag,
            lambda d,kind=kind,flag=flag:pair(d,kind,a='Choose an item.',z='2',marker=flag),expected='ACCEPTED'))
    for flag in ('','FALSE','TRUE','2',' 0'):
        rows.append(execute(kind+'-invalid-flag-'+repr(flag),
            lambda d,kind=kind,flag=flag:pair(d,kind,a='1',z='2',marker=flag),second='1'))
    for flag in ('0','false','off'):
        rows.append(execute(kind+'-false-flag-unknown-'+flag,
            lambda d,kind=kind,flag=flag:pair(d,kind,a='4',z='2',marker=flag)))
    for flags in (('0','0'),('0','1'),('1','1')):
        def maker(doc,kind=kind,flags=flags):
            pair(doc,kind,a='1',z='2',marker=flags[0])
            control=next(doc.element.iter(qn('w:sdt')))
            control.find(qn('w:sdtPr')).append(el('w:showingPlcHdr',val=flags[1]))
        rows.append(execute(kind+'-duplicate-flags-'+''.join(flags),maker,second='1'))
    # Source malformation cannot itself prove a known empty selection/value.
    def duplicate_content(doc,kind=kind):
        pair(doc,kind,a='',z='2')
        control=next(doc.element.iter(qn('w:sdt')))
        content=el('w:sdtContent');text(content,'1');control.append(content)
    rows.append(execute(kind+'-duplicate-content-empty-then-one',duplicate_content,second='1'))
    rows.append(execute(kind+'-explicit-invalid-flag-repair',
        lambda d,kind=kind:pair(d,kind,a='1',z='2',marker='bogus'),first='3',expected='ACCEPTED'))

for marker in ('begin','separate','end'):
    def maker(doc,marker=marker):
        pair(doc,a='',z='2')
        p=doc.paragraphs[1]._p
        fc=next(x for x in p.iter(qn('w:fldChar')) if x.get(qn('w:fldCharType'))==marker)
        t=el('w:t');t.text='1';fc.getparent().append(t)
    rows.append(execute('legacy-text-inside-'+marker,maker,second='1'))
def duplicate_separator(doc):
    pair(doc,a='1',z='2')
    p=doc.paragraphs[1]._p
    fc=next(x for x in p.iter(qn('w:fldChar')) if x.get(qn('w:fldCharType'))=='separate')
    fc.getparent().append(el('w:fldChar',fldCharType='separate'))
rows.append(execute('legacy-duplicate-separators-in-one-run',duplicate_separator))

result={'frozen_head':'90297ea971528b0b90f68a0e770ea89088672761',
 'source_hashes':{p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in ['core/generation_batch.py','documents/word_v3.py','core/v3_mapping.py']},
 'network_database_provider_calls':0,'cases':rows,'unexpected':[r['name'] for r in rows if not r['match']]}
print(json.dumps(result,indent=2,ensure_ascii=False))
