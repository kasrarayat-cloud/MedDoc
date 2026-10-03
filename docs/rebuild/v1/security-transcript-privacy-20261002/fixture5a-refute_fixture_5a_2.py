import os,sys,json,socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,"/opt/meddoc-pro/.worktrees/v1-sol-continuation/rebuild")
os.environ.update(QUILLMD_ENV_MANAGED="1",QUILLMD_SECRET_KEY="synthetic-refutation-only",QUILLMD_DATA_MODE="synthetic",QUILLMD_AI_MODE="fixture",DJANGO_SETTINGS_MODULE="quillmd.settings",QUILLMD_DB_PASSWORD="synthetic-unusable-no-connection",QUILLMD_DB_HOST="127.0.0.1",QUILLMD_DB_PORT="1",QUILLMD_STATE_DIR="/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security/refute-state")
import django
django.setup()
from django.test import override_settings
from core import generation as g,v3_field_relations as r
from core.tests.test_v3_supersession_floor import SONNET_55_DEFAULT,form,raw
from core.tests.test_v3_field_relations import relation_wire

from core import relations_fixture as fixture, batch_jobs
from core.tests.test_v3_ordinary_notes import field
from django.db.backends.base.base import BaseDatabaseWrapper
from django.core.exceptions import ValidationError
import ast,subprocess,copy,hashlib

cases=[
 ('labelled_positive','Symptoms: cough.\n\nAllergies: penicillin.',form('Symptoms','Allergies')),
 ('unlabelled','The patient reports cough.',form('Symptoms','Allergies')),
 ('unknown_context','Symptoms: cough.\n\nIt was not the patient.',form('Symptoms','Allergies')),
 ('unknown_label','Symptoms: cough.\n\nOther: not this patient.',form('Symptoms','Allergies')),
 ('duplicate_labels','Symptoms: cough.',form('Symptoms','Symptoms')),
 ('repeated_values','Symptoms: cough.\n\nSymptoms: no cough.',form('Symptoms','Allergies')),
 ('signing_context','Symptoms: cough.\n\nClinician signature: Dr Example.',[field('f1','Symptoms'),field('f2','Clinician signature','signature')]),
 ('signature_only','Clinician signature: Dr Example.',[field('f1','Clinician signature','signature')]),
 ('signing_longtext','Clinician signature: Dr Example.',form('Clinician signature','Allergies')),
 ('negated_option','Smoker: No.\n\nSymptoms: cough.',[field('f1','Smoker','choice',['Yes','No']),field('f2','Symptoms')]),
 ('ambiguous_option','Smoker: Yes. Corrected to no.',[field('f1','Smoker','choice',['Yes','No']),field('f2','Symptoms')]),
 ('crosslabel_stop','Current medications: warfarin 5 mg daily.\n\nPlan: Hold warfarin today.',form('Current medications','Plan')),
 ('inherited_family','Family history:\nSymptoms: cough.',form('Symptoms','Allergies')),
]
out=[]
with override_settings(**dict(SONNET_55_DEFAULT,AI_MODE='fixture')),patch.object(socket.socket,'connect',side_effect=AssertionError('Network denied')),patch.object(BaseDatabaseWrapper,'ensure_connection',side_effect=AssertionError('Database denied')):
 for name,notes,fields in cases:
  try:
   result=g.generate(notes,fields)
   answers,cost,units,rates,provider,request,simulated=result
   governed={k:g.as_currently_governed(g.governance_for(notes,fields),notes,{**next(f for f in fields if f['key']==k),**v}) for k,v in answers.items()}
   asked,context,_=g.v3_generation_fields(fields)
   wire=fixture.body(notes,fields,asked,context) if asked else {'fields':[]}
   source_units=g.source_units(notes,asked,context_labels=context)[0]
   partitions=[]
   for row in wire['fields']:
    ids=[i for rel in r.PARTITION for i in row['context'][rel]]
    partitions.append({'key':row['key'],'all_units_exactly_once':len(ids)==len(set(ids))==len(source_units) and set(ids)=={u['id'] for u in source_units}})
   out.append({'name':name,'notes':notes,'answers':{k:{'status':v['status'],'text':v['text']} for k,v in answers.items()},'governed':{k:{'status':v['status'],'text':v['text']} for k,v in governed.items()},'settlement':[str(cost),units,rates,provider,request,simulated],'partition_checks':partitions,'wire':wire})
  except Exception as ex:out.append({'name':name,'notes':notes,'error_type':type(ex).__name__,'error':str(ex)})
 # Explicitly adversarial truncated fixture units must fail actualvalidator.
 fields=form('Symptoms','Allergies');notes='Symptoms: cough.\n\nIt was not the patient.'
 offered=g.source_units(notes,fields)[0]
 bad=fixture.body(notes,fields,fields,[],units=offered[:1])
 try:r.validated(raw(notes,fields,bad,g.SONNET_5_5));truncated='ACCEPTED'
 except ValidationError:truncated='refused'
 out.append({'name':'truncated_units_adversary','result':truncated,'body':bad})
 # Part response must keep whole-source context while selectingonly partfields.
 fields=[field('f1','Symptoms'),field('f2','Smoker','choice',['Yes','No'])];notes='Symptoms: cough.\n\nSmoker: No.'
 config=g.configuration(fields);asked,context,_=g.v3_generation_fields(fields);units=g.source_units(notes,asked,context_labels=context)[0]
 plan={'notes':notes,'fields':fields,'asked':asked,'context_labels':context,'units':units,'config':config,'history_targets':[]}
 response=batch_jobs.fixture_response(plan,SimpleNamespace(pk='synthetic-read-only-part',field_ids=['f1']))
 wire=json.loads(response['content'][0]['text']);parsed=r.parse(response['content'][0]['text'],[fields[0]],units)
 out.append({'name':'part_partition','wire':wire,'partition_units':[u['id'] for u in units],'selection_count':len(parsed.fields),'synthetic_source':response['synthetic_source'],'no_option_ids_in_text_part':'option_ids' not in wire['fields'][0]})
# Independent AST check excludes onlythe changed nonliveblock.
wt='/opt/meddoc-pro/.worktrees/v1-sol-continuation'
prior=subprocess.check_output(['git','show','888a8d03^:rebuild/core/v3_field_relations.py'],cwd=wt,text=True)
current=Path(wt+'/rebuild/core/v3_field_relations.py').read_text()
def live_ast(source):
 fn=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='generate')
 for n in ast.walk(fn):
  if isinstance(n,ast.With):
   n.body=[child for child in n.body if not (isinstance(child,ast.If) and ast.unparse(child.test)=="config.get('mode') != 'live'")]
 return ast.dump(fn,include_attributes=False)
out.append({'name':'live_generate_ast_byte_transport_settlement','unchanged_after_removing_only_nonlive_branch':live_ast(prior)==live_ast(current)})
Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security/refute-fixture-5a-2.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
