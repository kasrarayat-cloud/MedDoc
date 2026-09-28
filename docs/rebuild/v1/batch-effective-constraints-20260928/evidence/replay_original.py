import os,json,hashlib,socket
from pathlib import Path
from types import SimpleNamespace
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
def denied(*a,**kw):raise AssertionError('Network forbidden')
socket.socket.connect=denied;socket.create_connection=denied
import django;django.setup()
from django.test import override_settings
from django.core.exceptions import ValidationError
from core import generation_batch as b,v3_mapping
from documents import word_v3 as w
R=Path(__file__).parent.resolve();prior=json.loads((R/'prechecked-result.json').read_text());data=(R/'prechecked-original.docx').read_bytes()
assert hashlib.sha256(data).hexdigest()==prior['input_sha256']
fields=w.inspect(data)['fields'];assert b.digest(fields)==prior['constraints']['fields_sha256']
selected={f['label']:f for f in fields if f['label'] in ('Group A','Group B')}
version=SimpleNamespace(fields=fields,template=SimpleNamespace(sha256=prior['input_sha256'],original_path='prechecked-original.docx'),generation_constraints=prior['constraints'])
answers={f['key']:{'text':'','status':'missing','reviewed':True,'left_blank':True} for f in fields}
answers[selected['Group B']['key']]={'text':'Active','status':'supported','reviewed':True,'edited_by':'synthetic-clinician'}
with override_settings(MEDIA_ROOT=R):
 try:b.check_answers(version,answers)
 except ValidationError as exc:reason=str(exc)
 else:raise AssertionError('Original failure still accepted')
 assert 'maximum selection' in reason
 answers[selected['Group A']['key']]['text']='Inactive';b.check_answers(version,answers)
 out=w.fill(data,fields,v3_mapping.fill_answers(fields,answers));(R/'prechecked-repaired-export.docx').write_bytes(out)
 physical={}
 for label,f in selected.items():
  slot=w.SlotIndex(w.open_package(out)).by_id[f['locator']['part']+'#'+f['locator']['slot']]
  physical[label]=w.paragraph_text(slot.el)[0]
 assert physical=={'Group A':'☐ Active ☒ Inactive','Group B':'☒ Active ☐ Inactive'},physical
 row={'original_sha256':prior['input_sha256'],'original_bad_answer':'refused','reason':reason,'explicit_override':'accepted','physical_export':physical,'export_sha256':hashlib.sha256(out).hexdigest(),'source_sha256':hashlib.sha256(Path('rebuild/core/generation_batch.py').read_bytes()).hexdigest(),'provider_calls':0}
 (R/'original-repaired.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
