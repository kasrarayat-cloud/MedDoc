import os, sys, json, socket, time, hashlib, stat
from pathlib import Path
from unittest.mock import patch

SOURCE = Path('/opt/meddoc-pro/.worktrees/v1-sol-notes-voice')
SCRATCH = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security')
manifest = json.loads((SCRATCH/'refute-clinical-3b9e8bf8-source/manifest.json').read_text())
def verify_source():
    for row in manifest['files']:
        assert hashlib.sha256((SOURCE/row['path']).read_bytes()).hexdigest() == row['sha256']
verify_source()
sys.path.insert(0, str(SOURCE/'rebuild'))
os.environ.update(QUILLMD_ENV_MANAGED='1', QUILLMD_SECRET_KEY='synthetic-refutation-only',
    QUILLMD_DATA_MODE='synthetic', QUILLMD_AI_MODE='fixture', DJANGO_SETTINGS_MODULE='quillmd.settings',
    QUILLMD_DB_PASSWORD='synthetic-unusable-no-connection', QUILLMD_DB_HOST='127.0.0.1',
    QUILLMD_DB_PORT='1', QUILLMD_STATE_DIR=str(SCRATCH/'refute-state'))
import django
django.setup()
from django.test import override_settings
from django.db.backends.base.base import BaseDatabaseWrapper
from core import generation as g, v3_field_relations as r
from core.tests.test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw
from core.tests.test_v3_field_relations import relation_wire
from core.tests.test_transcript_context import proof

warfarin = 'Takes warfarin 5 mg daily.'
exam = 'Examination mild swelling over the left lateral ankle.'
pain = 'The patient reports pain in the left knee.'
# Expected hold is a statement about the exact source, not a parser score.
cases = [
    ('modified_operator_completely', 'Examination', exam, 'The patient has completely absent swelling over the left ankle.', True),
    ('nominal_predicative_absent', 'Examination', exam, 'Swelling over the left ankle is absent.', True),
    ('predicative_possessive_patient', 'Examination', exam, "The patient's swelling over the left ankle is absent.", True),
    ('predicative_swelling_first', 'Examination', exam, 'Swelling is absent over the left ankle.', True),
    ('predicative_ankle_free', 'Examination', exam, 'The left ankle is free of swelling.', True),
    ('predicative_different_side', 'Examination', exam, 'Swelling over the right ankle is absent.', False),
    ('modified_operator_different_side', 'Examination', exam, 'The patient has completely absent swelling over the right ankle.', False),
    ('predicative_cancelled', 'Examination', exam, 'Swelling over the left ankle is not absent.', False),
    ('modifier_cancelled', 'Examination', exam, 'The patient has not absent swelling over the left ankle.', False),
    ('predicative_explicit_foreign', 'Examination', exam, "Her father's swelling over the left ankle is absent.", False),
    ('independent_clinical_topic', 'Examination', exam, 'The patient has completely absent pain over the left ankle.', False),
    ('same_side_symmetry_without', 'Examination', 'The patient has a left ankle without swelling.', 'The patient has swelling over the left ankle.', True),
    ('same_side_symmetry_absent', 'Examination', 'The patient has absent swelling over the left ankle.', 'The patient has swelling over the left ankle.', True),
    ('same_side_symmetry_no', 'Examination', 'No swelling over the left ankle.', 'The patient has swelling over the left ankle.', True),
    ('side_symmetry_without', 'Examination', 'The patient has a left ankle without swelling.', 'The patient has swelling over the right ankle.', False),
    ('non_medication_switch', 'Current medications', warfarin, 'The patient switched to the supine position.', False),
    ('prior_family_denial', 'Examination', exam, 'Her father has no swelling over the left ankle.', False),
    ('prior_without_negation', 'Examination', exam, 'The patient has a left ankle without swelling.', True),
]

results=[]
started=time.monotonic()
with override_settings(**SONNET_55_DEFAULT), \
     patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')), \
     patch.object(BaseDatabaseWrapper,'ensure_connection',side_effect=AssertionError('Database forbidden')):
    for case in cases:
        assert time.monotonic()-started < 120, 'bounded clinical refutation deadline'
        name,label,pick,tail,expected_hold,*prefix = case
        notes=(prefix[0] if prefix else '')+pick+(' '+tail if tail else '')
        fields=form(label,'Plan')
        try:
            wire=relation_wire(notes,fields,{'f1':[pick]})
            result=raw(notes,fields,wire,g.SONNET_5_5)
            result['patient_default_context']=proof(notes)
            answer=r.validated(result)['f1']
            row=g.as_currently_governed(g.governance_for(notes,fields),notes,{**fields[0],**answer})
            decisions=g.governed_decisions(notes,fields,{'f1':answer})
            released=row.get('status')=='supported' and row.get('text')==pick and not decisions
            results.append({'name':name,'notes':notes,'selected_quote':pick,'expected_hold':expected_hold,
                'validated_status':answer.get('status'),'validated_text':answer.get('text'),
                'governed_status':row.get('status'),'governed_text':row.get('text'),
                'finalization_governed_decisions':decisions,'released':released,
                'demonstrated_unsafe_release':expected_hold and released,
                'unnecessary_hold':not expected_hold and not released,
                'held_context':answer.get('held_candidate',{}).get('context',[])})
        except Exception as e:
            results.append({'name':name,'notes':notes,'selected_quote':pick,'expected_hold':expected_hold,
                'instrument_or_validation_error':type(e).__name__,'message':str(e)})
    original=json.loads((SOURCE/'rebuild/core/tests/voice_first_pass_controls.json').read_text())
    notes=original['notes'];fields=original['fields']
    replay=[]
    for context in (False,True):
        result=raw(notes,fields,original['first_model_body'],g.SONNET_5_5)
        if context:result['patient_default_context']=proof(notes)
        answers=r.validated(result)
        governed=g.governed_decisions(notes,fields,answers)
        replay.append({'patient_context':context,'supported':[key for key,a in answers.items() if a['status']=='supported'],
            'original_held_controls':{key:{'status':answers[key]['status'],'text':answers[key]['text']}
                for key in original['held_controls']},'finalization_governed_decisions':governed})
verify_source()
report={'source_commit':manifest['commit'],'source_manifest':manifest,'provider_requests':0,'database_connections':0,
    'model_context_relations':'all unselected units adversarially independent','cases':results,
    'original_first_pass_voice_replay':replay,'elapsed_seconds':round(time.monotonic()-started,3)}
p=SCRATCH/'refute-clinical-3b9e8bf8.json'
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2)
print(json.dumps({'source_commit':manifest['commit'],'cases':len(results),'elapsed_seconds':report['elapsed_seconds'],
    'unsafe':[x['name'] for x in results if x.get('demonstrated_unsafe_release')],
    'unnecessary_holds':[x['name'] for x in results if x.get('unnecessary_hold')],
    'errors':[x['name'] for x in results if 'instrument_or_validation_error' in x],
    'original_replay':replay},indent=2))
