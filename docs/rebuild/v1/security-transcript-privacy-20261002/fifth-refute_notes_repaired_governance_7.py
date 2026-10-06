import os,sys,json,socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,"/opt/meddoc-pro/.worktrees/v1-sol-notes-voice/rebuild")
os.environ.update(QUILLMD_ENV_MANAGED="1",QUILLMD_SECRET_KEY="synthetic-refutation-only",QUILLMD_DATA_MODE="synthetic",QUILLMD_AI_MODE="fixture",DJANGO_SETTINGS_MODULE="quillmd.settings",QUILLMD_DB_PASSWORD="synthetic-unusable-no-connection",QUILLMD_DB_HOST="127.0.0.1",QUILLMD_DB_PORT="1",QUILLMD_STATE_DIR="/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security/refute-state")
import django
django.setup()
from django.test import override_settings
from core import generation as g,v3_field_relations as r,transcript_context as tc
from core.tests.test_v3_supersession_floor import SONNET_55_DEFAULT,form,raw
from core.tests.test_v3_field_relations import relation_wire
from core.tests.test_transcript_context import proof
cases=[('Current medications', 'Takes warfarin 5 mg daily.', 'No longer the daily medication.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'No longer a daily medication.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Her father is not the only warfarin user.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Her father is the only person not taking warfarin.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Only her father is not taking warfarin.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Her father is the sole warfarin user.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Her father is the only patient on warfarin.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Her father is the sole apixaban user.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Only her father does not take warfarin.', True), ('Current medications', 'Does not take warfarin.', 'Only her father does not take warfarin.', True), ('Current medications', 'Does not take warfarin.', 'Only her father takes warfarin.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Her father is not the only person taking warfarin.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Her father is the only person without warfarin.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'No longer this daily medication.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'No longer my daily medication.', True), ('Current medications', 'Takes warfarin 5 mg daily.', 'Only her father used to take warfarin.', True)]
results=[]
with override_settings(**SONNET_55_DEFAULT),patch.object(socket.socket,"connect",side_effect=AssertionError("Network forbidden")):
 for label,pick,tail,context in cases:
  notes=pick+(" "+tail if tail else "")
  fields=form(label,"Plan")
  result=raw(notes,fields,relation_wire(notes,fields,{"f1":[pick]}),g.SONNET_5_5)
  if context:result["patient_default_context"]=proof(notes)
  try:
   answer=r.validated(result)["f1"]
   governed=g.as_currently_governed(g.governance_for(notes,fields),notes,{**fields[0],**answer})
   results.append(dict(label=label,notes=notes,pick=pick,context=context,status=answer["status"],text=answer["text"],governed_status=governed["status"],governed_text=governed["text"],review_required=g.governed_decisions(notes,fields,{"f1":answer})))
  except Exception as ex:results.append(dict(label=label,notes=notes,error=str(ex)))
Path("/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security/refute-notes-repaired-governance-7.json").write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
