import os,json,time,resource,socket
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from core import v3_syntax,generation as g
from pathlib import Path
socket.socket=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network denied'))
quote='The patient attends an art class every Monday.'
start=time.perf_counter();one=v3_syntax.complete_ids([{'id':1,'quote':quote}]);cold=time.perf_counter()-start
start=time.perf_counter();many=v3_syntax.complete_ids([{'id':i,'quote':quote} for i in range(64)]);warm=time.perf_counter()-start
rows=json.loads(Path('docs/rebuild/v1/patient-topics-20260927/evidence/remaining-51-classification.json').read_text())['rows'] if Path('docs').exists() else json.loads(Path('../docs/rebuild/v1/patient-topics-20260927/evidence/remaining-51-classification.json').read_text())['rows']
retained=[]
for row in rows:
 if row['classification']!='V':continue
 quotes=row['original_selection'];syntactic=v3_syntax.complete_ids([{'id':i,'quote':q} for i,q in enumerate(quotes)])
 retained.append({'case':row['case'],'field':row['field'],'original_selection':quotes,'existing_finite':[bool(g.FINITE_STATEMENT_V3.search(q)) for q in quotes],'syntax_only':[i in syntactic for i in range(len(quotes))],'explicit_patient':[bool(g.EXPLICIT_PATIENT_SUBJECT.match(q)) for q in quotes],'prior_status_unchanged':row['recorded_status']})
print(json.dumps({'cold_seconds':cold,'warm_64_seconds':warm,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'cold_ids':list(one),'warm_count':len(many),'retained34V_syntax_only_not_clinical_outcomes':retained},indent=2))
