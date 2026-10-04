"""Offline exact batch101 replay; no application secrets, ORM, or transport."""
import argparse
import hashlib
import json
import socket
import subprocess
import sys
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

def refuse_network(*args, **kwargs):
    raise AssertionError('No network is authorized in this pure transfer lens')
socket.socket.connect = refuse_network
socket.create_connection = refuse_network
parser = argparse.ArgumentParser()
parser.add_argument('source',type=Path)
parser.add_argument('commit')
parser.add_argument('out',type=Path)
args=parser.parse_args()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source).decode().strip()==args.commit
assert not subprocess.check_output(['git','status','--porcelain'],cwd=args.source).strip()
assert not (args.source/'rebuild/.env').exists()
sys.path.insert(0,str(args.source/'rebuild'))
from django.conf import settings
# This explicit offline switch is the retained campaign's qualified contract;
# no settings module, protected key, database, account, or environment is read.
settings.configure(V3_FIELD_RELATIONS=True,AI_MODEL='claude-sonnet-5-5')
from core import generation as g, generation_batch as batch, v3_mapping
from documents import word_v3 as w

P=Path('/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-3')
sha=lambda b:hashlib.sha256(b).hexdigest()
args.out.mkdir(mode=0o700)
plan=json.loads((P/'evidence/002/batch-plan.json').read_text())
assert plan==json.loads((P/'evidence/003/batch-plan.json').read_text())
original=(P/'evidence/002/case/form.docx').read_bytes()
fields=json.loads((P/'evidence/002/case/mapping.json').read_text())
notes=(P/'evidence/002/case/notes.txt').read_text()
assert fields==plan['fields'] and notes==plan['notes']
assert sha(original)==plan['original_sha256'] and sha(notes.encode())==plan['notes_sha256']
inspection=w.inspect(original)
assert inspection['fields']==fields
requests=[]
for ordinal,attempt in ((1,'002'),(2,'003')):
    wire=batch.request(plan,ordinal)
    captured=json.loads((P/('evidence/'+attempt+'/compiled-child-request.json')).read_text())
    transport=json.loads((P/('evidence/'+attempt+'/request.json')).read_text())
    assert wire==captured==transport['body_json']
    part=plan['parts'][ordinal-1]
    assert batch.digest(wire)==part['request_sha256']
    size=len(json.dumps(wire).encode())
    rate=g.rates(plan['config'])
    amount=(Decimal(size+12000)*rate['input_per_million']+Decimal(wire['max_tokens'])*rate['output_per_million'])/1000000
    if plan['config']['request_profile'].get('inference_geo')=='us':amount*=g.US_INFERENCE_MULTIPLIER
    amount=amount.quantize(g.COST_QUANTUM,rounding=ROUND_CEILING)
    assert size+12000==part['input_token_bound']
    assert amount==Decimal(part['maximum_cost'])
    assert amount*Decimal('1.5')==Decimal(part['maximum_charge'])
    path=args.out/('compiled-'+attempt+'.json')
    path.write_text(json.dumps(wire,indent=2)+'\n')
    requests.append({'ordinal':ordinal,'attempt':attempt,'request_digest':batch.digest(wire),
        'retained_request_object_equal':True,'input_token_bound':size+12000,
        'maximum_cost':str(amount),'maximum_charge':str(amount*Decimal('1.5'))})
review=json.loads((P/'evidence/003/answers-reviewed.json').read_text())['answers']
assert set(review)=={f['key'] for f in fields}
values=v3_mapping.fill_answers(fields,review)
export=w.fill(original,fields,values)
(args.out/'export.docx').write_bytes(export)
paid_export=(P/'evidence/003/export.docx').read_bytes()
assert export==paid_export
before=w.SlotIndex(w.open_package(original));after=w.SlotIndex(w.open_package(export))
checks=[]
for field in fields:
    text=review[field['key']]['text']
    got=w.constrained_scalar_value(before,after,field,True)
    assert got==text,(field['key'],got,text)
    checks.append({'key':field['key'],'expected_text_sha256':sha(text.encode()),'complete_readback':True})
assert sum(bool(v['text']) for v in review.values())==2
result={'source':str(args.source),'commit':args.commit,'original_sha256':sha(original),
        'mapping_file_sha256':sha((P/'evidence/002/case/mapping.json').read_bytes()),
        'mapping_digest':batch.digest(fields),'fresh_inspector_fields_equal':True,
        'notes_sha256':sha(notes.encode()),'requests':requests,
        'aggregate_maximum_charge':str(sum((Decimal(p['maximum_charge']) for p in plan['parts']),Decimal(0))),
        'export_sha256':sha(export),'paid_export_byte_equal':True,'answer_readbacks':checks,
        'nonempty_answers':2,'empty_answers':99,'network_calls':0,'DB_calls':0,
        'limitation':'Provider ran on04fb only. This checks the exact retained synthetic input, request, configuration, reviewed answers and writer; it does not execute adoption, signatures, new settings, or a new provider response.'}
(args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=args.source).strip()
print(json.dumps({k:v for k,v in result.items() if k in ('commit','fresh_inspector_fields_equal','paid_export_byte_equal','export_sha256','nonempty_answers','empty_answers')}))
