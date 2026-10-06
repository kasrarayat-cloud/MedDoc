"""Prospective bounded supervisor. Requires a separate root execution grant; preparing it does not grant QA.

The existing protected wrapper reads only the permitted QA DB credential internally. This supervisor
neither reads credential files nor touches a paid campaign ledger. Catalog queries use that wrapper too.
"""
from pathlib import Path
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from transfer_inputs import GROUPS

os.umask(0o077)
B=Path(__file__).resolve().parent
PY='/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python'
WRAPPER=Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/qa_test2.py')
WRAPPER_SHA='74e0c52014939e534b4e2231bf4da0b23a01a17ba62abea1c62b58799258dff3'
WT,HEAD,GROUP,DB,OUT=Path(sys.argv[1]).resolve(),sys.argv[2],sys.argv[3],sys.argv[4],Path(sys.argv[5]).resolve()
if GROUP not in GROUPS or len(HEAD)!=40 or not DB.startswith('quillmd_qa_sol_') or len(DB)>45:
    raise ValueError('Only a fixed packet, frozen full SHA and owned QA namespace are eligible.')
if hashlib.sha256(WRAPPER.read_bytes()).hexdigest()!=WRAPPER_SHA:
    raise ValueError('The reviewed protected wrapper differs.')
OUT.mkdir(mode=0o700,parents=True,exist_ok=False)


def bounded(command,label,seconds):
    start=time.monotonic();timeout=False
    with (OUT/(label+'.stdout.log')).open('w') as out,(OUT/(label+'.stderr.log')).open('w') as err:
        child=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
        try:code=child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timeout=True;os.killpg(child.pid,signal.SIGTERM)
            try:code=child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL);code=child.wait(timeout=8)
    return {'command':command,'exit_status':code,'elapsed_seconds':time.monotonic()-start,
            'timeout':timeout,'reaped':child.poll() is not None}


def catalog(label):
    code="""import json,sys,os\nimport psycopg\nfrom pathlib import Path\nwith psycopg.connect(host='127.0.0.1',port=55731,user=os.environ['QUILLMD_DB_USER'],dbname='postgres',password=os.environ['QUILLMD_DB_PASSWORD']) as c:\n with c.cursor() as q:\n  q.execute('SELECT datname FROM pg_database WHERE datname = ANY(%s)',([sys.argv[1],'test_'+sys.argv[1]],))\n  rows=q.fetchall()\nPath(sys.argv[2]).write_text(json.dumps(rows)+'\\n')\nraise SystemExit(bool(rows))\n"""
    file=OUT/(label+'.py');file.write_text(code)
    return bounded([PY,'-B',str(WRAPPER),str(WT),DB,str(OUT/'protected-state'),str(file),DB,str(OUT/(label+'.json'))],label,20)


before=catalog('catalog-before')
if before['exit_status'] or before['timeout']:raise SystemExit('Owned normal/test DB already exists or catalog cannot be proven.')
command=[PY,'-B',str(WRAPPER),str(WT),DB,str(OUT/'protected-state'),str(B/'cached_provider_transfer.py'),
         str(WT),HEAD,str(OUT/'captures'),GROUP]
result=bounded(command,'application',180)
after=catalog('catalog-after')
record={'source':HEAD,'group':GROUP,'fixed_attempts':GROUPS[GROUP],'catalog_before':before,'application':result,
        'catalog_after':after,'bound_seconds':180,'termination_grace_seconds':10,'provider_calls':0,
        'paid_campaign_ledger_mutations':0,'scope':'Prospective cached-response application transfer; no new paid acceptance'}
(OUT/'supervisor-result.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
raise SystemExit(0 if result['exit_status']==0 and not result['timeout'] and after['exit_status']==0 and not after['timeout'] else 1)
