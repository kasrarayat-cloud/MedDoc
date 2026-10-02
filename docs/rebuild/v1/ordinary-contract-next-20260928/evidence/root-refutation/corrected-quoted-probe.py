import sys,os,json,hashlib,copy
from pathlib import Path
SOURCE=Path('/opt/meddoc-pro/.worktrees/v1-notes-workflows/rebuild');sys.path.insert(0,str(SOURCE));os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django;django.setup()
from django.test import override_settings
from unittest.mock import patch
from core.tests.test_v3_history_context import offered,field
from core import generation as g
R=Path(__file__).parent
fs=[field('chief','Chief complaint'),field('hpi','History of present illness','long_text')]
first='Patient presents with right knee pain.'
cases=[
 ('baseline',first+' The patient takes a vitamin.',first),
 ('explicit_correction',first+' Correction: left knee, not right knee.',first),
 ('corrected_history',first+' This history was copied from the donor; the recipient has no pain.',first),
 ('denied_scope','The following symptoms are denied:\n'+first,first),
 ('conditional_scope','Only if the patient develops symptoms:\n'+first,first),
 ('quoted_subject','The father said, "Patient presents with right knee pain."','The father said, "Patient presents with right knee pain."'),
 ('foreign_subject','The patient advocate presents with right knee pain. Plan: rest.','The patient advocate presents with right knee pain.'),
 ('patient_noun','Patient education includes cough management. Plan: rest.','Patient education includes cough management.'),
 ('coordinated_subject','The patient and the caregiver report right knee pain. Plan: rest.','The patient and the caregiver report right knee pain.'),
 ('father_pronoun','Patient presents with his father. He reports low-grade fevers.','He reports low-grade fevers.'),
 ('label_mismatch','Family history:\n'+first,first),
 ('foreign_scoped_tail',first+' Assessment: father has right knee pain.',first),
 ('resolved_tail',first+' The knee pain resolved two months ago and has not returned.',first),
]
out=[]
with override_settings(V3_HISTORY_CONTEXT=True),patch('socket.socket.connect',side_effect=AssertionError('Network disabled')):
 for key,notes,quote in cases:
  try:
   a=offered(notes,fs,{'Chief complaint':[quote]})['Chief complaint']
   forced={**a,'status':'supported','text':quote,'reviewed':True}
   out.append({'case':key,'notes':notes,'selected':quote,'relation':'all unselected=context_only (adversarial mock)','status':a['status'],'text':a['text'],'stored_forced_holds':g.governed_decisions(notes,fs,{'chief':forced})})
  except Exception as e:out.append({'case':key,'instrument_error':type(e).__name__+': '+str(e)})
(R/'corrected-quoted-probe.json').write_text(json.dumps({'source':hashlib.sha256((SOURCE/'core/generation.py').read_bytes()).hexdigest(),'results':out},indent=2));print(json.dumps(out,indent=2))
