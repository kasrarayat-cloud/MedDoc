"""Read-only verification of the 17 paid attempts of quillmd-v1-sonnet5-staged-40 (no provider call)."""
import hashlib, json, os, sys
from decimal import Decimal
C='/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign'
RATES={'in':Decimal('2'),'out':Decimal('10'),'cache_read':Decimal('0.20')}
def sha(p): return hashlib.sha256(open(p,'rb').read()).hexdigest()
rows=[]; problems=[]; stage_tot={}
for n in range(1,18):
    a=json.load(open(f'{C}/ledger/{n:03d}-attempt.json')); o=json.load(open(f'{C}/ledger/{n:03d}-outcome.json'))
    ev=f'{C}/evidence/{n:03d}'; man=json.load(open(f'{ev}/manifest.json'))
    bad=[k for k,v in man.get('evidence',{}).items() if not os.path.exists(f'{ev}/{k}') or sha(f'{ev}/{k}')!=v]
    listed=set(man.get('evidence',{}))
    present=set()
    for root,_,fs in os.walk(ev):
        for f in fs: present.add(os.path.relpath(os.path.join(root,f),ev))
    unlisted=sorted(present-listed-{'manifest.json'})
    u=o.get('usage') or {}
    cost=(Decimal(u.get('input_tokens',0))*RATES['in']+Decimal(u.get('output_tokens',0))*RATES['out']
          +Decimal(u.get('cache_read_input_tokens',0))*RATES['cache_read'])/Decimal(1000000)
    st=a.get('stage'); stage_tot[st]=stage_tot.get(st,Decimal(0))+Decimal(o.get('exposure','0'))
    s=o.get('settlement') or {}
    body_ok=None
    pr=o.get('provider_response') or {}
    if pr.get('body_sha256') and os.path.exists(f'{ev}/provider-response.body'):
        body_ok=sha(f'{ev}/provider-response.body')==pr['body_sha256']
    exp=None
    if os.path.exists(f'{ev}/export.json') and os.path.exists(f'{ev}/export.docx'):
        ej=json.load(open(f'{ev}/export.json')); want=ej.get('sha256') or ej.get('export_sha256')
        exp=(sha(f'{ev}/export.docx')==want) if want else 'no-sha-field'
    row=dict(n=n,stage=st,case=a.get('case'),cls=o.get('class'),req=o.get('provider_request_id'),msg=o.get('provider_resource_id'),
             model=o.get('served_model'),stop=o.get('stop_reason'),tokens=f"{u.get('input_tokens')}/{u.get('output_tokens')}",
             recomputed=str(cost),recorded=o.get('computed_cost'),exposure=o.get('exposure'),job_state=o.get('job_state'),
             reservations=s.get('reservations'),charged=s.get('charged_cost'),manifest_bad=bad,unlisted=unlisted,
             body_sha_ok=body_ok,export_sha_ok=exp,sends=o.get('sends_at_transport'))
    if bad: problems.append((n,'manifest mismatch',bad))
    if o.get('computed_cost') and Decimal(o['computed_cost'])!=cost: problems.append((n,'cost mismatch',str(cost),o['computed_cost']))
    if body_ok is False: problems.append((n,'body sha mismatch'))
    if exp is False: problems.append((n,'export sha mismatch'))
    rows.append(row)
for r in rows: print(json.dumps(r))
print('STAGE_EXPOSURE',{k:str(v) for k,v in stage_tot.items()},'TOTAL',str(sum(stage_tot.values())))
for f in sorted(os.listdir(f'{C}/ledger')):
    if f.startswith('stage-'): print('DECISION',f,json.dumps(json.load(open(f'{C}/ledger/{f}')))[:400])
print('PROBLEMS',problems)
