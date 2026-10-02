"""Bounded sibling of F-B7: duplicate SDT property bodies with conflicting flags."""
from pathlib import Path
base=Path(__file__).with_name('probe.py').read_text()
exec(compile(base.split('\nrows=[]\n')[0], 'retained-independent-helpers', 'exec'))
rows=[]
for kind in ('scalar','dropdown'):
    def maker(doc,kind=kind):
        pair(doc,kind,a='1',z='2',marker='present')
        control=next(doc.element.iter(qn('w:sdt')))
        second=copy.deepcopy(control.find(qn('w:sdtPr')))
        second.find(qn('w:showingPlcHdr')).set(qn('w:val'),'0')
        control.insert(1,second)
    rows.append(execute(kind+'-duplicate-properties-conflicting-placeholder',maker,second='1'))
result={'frozen_head':'90297ea971528b0b90f68a0e770ea89088672761',
 'source_hashes':{p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in ['core/generation_batch.py','documents/word_v3.py']},
 'network_database_provider_calls':0,'cases':rows,'unexpected':[r['name'] for r in rows if not r['match']]}
print(json.dumps(result,indent=2,ensure_ascii=False))
