import os, sys, json, socket, time, hashlib, stat
from pathlib import Path
from unittest.mock import patch

SOURCE = Path('/opt/meddoc-pro/.worktrees/v1-sol-notes-voice')
SCRATCH = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security')
manifest = json.loads((SCRATCH/'refute-clinical-6f0f647a-source/manifest.json').read_text())
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
    ('prior_only_father_does', 'Current medications', warfarin, 'Only her father does.', True),
    ('prior_not_today', 'Current medications', warfarin, 'Not today.', True),
    ('prior_not_since_monday', 'Current medications', warfarin, 'Not since Monday.', True),
    ('prior_no_longer_the', 'Current medications', warfarin, 'No longer the daily medication.', True),
    ('prior_exclusive_same', 'Current medications', warfarin, 'Her father is the sole warfarin user.', True),
    ('prior_false_hold_without', 'Current medications', warfarin, 'Her father is the only person without warfarin.', False),
    ('prior_false_hold_past', 'Current medications', warfarin, 'Only her father used to take warfarin.', False),
    ('wrong_subject', 'Current medications', 'Her father takes warfarin 5 mg daily.', '', True),
    ('stopped_medication', 'Current medications', warfarin, 'Warfarin was stopped.', True),
    ('independent_other_drug', 'Current medications', warfarin, 'Her father is the sole apixaban user.', False),
    ('without_same_swelling', 'Examination', exam, 'The patient has a left ankle without swelling.', True),
    ('without_different_side', 'Examination', exam, 'The patient has a right ankle without swelling.', False),
    ('absent_same_swelling', 'Examination', exam, 'The patient has absent swelling over the left ankle.', True),
    ('free_same_swelling', 'Examination', exam, 'The patient has a swelling-free left ankle.', True),
    ('non_same_swelling', 'Examination', exam, 'The patient has non-swollen left ankle.', True),
    ('deny_any_same', 'Examination', exam, 'The patient denies any swelling over the left ankle.', True),
    ('different_topic_same_side', 'Examination', exam, 'The patient has no pain over the left ankle.', False),
    ('same_topic_explicit_other', 'Examination', exam, 'Her father has no swelling over the left ankle.', False),
    ('same_nominal_temporal', 'Examination', exam, 'No longer swollen over the left ankle.', True),
    ('exam_inherited_family', 'Examination', exam, '', True, 'Family history. '),
    ('exam_inherited_hypothetical', 'Examination', exam, '', True, 'Hypothetical. '),
    ('deny_either_knee', 'Symptoms', pain, 'The patient denies pain in either knee.', True),
    ('without_left_pain', 'Symptoms', pain, 'The patient has a left knee without pain.', True),
    ('opposite_polarity_exclusive', 'Symptoms', pain, 'Only her father denies left knee pain.', False),
    ('same_polarity_exclusive', 'Symptoms', pain, 'Only her father has left knee pain.', True),
    ('explicit_different_side', 'Symptoms', pain, 'Only her father has right knee pain.', False),
    ('local_temporal', 'Current medications', warfarin, 'Reports cough. Not until next week.', False),
    ('same_temporal', 'Current medications', warfarin, 'Not until next week.', True),
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
p=SCRATCH/'refute-clinical-6f0f647a.json'
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2)
print(json.dumps({'source_commit':manifest['commit'],'cases':len(results),'elapsed_seconds':report['elapsed_seconds'],
    'unsafe':[x['name'] for x in results if x.get('demonstrated_unsafe_release')],
    'unnecessary_holds':[x['name'] for x in results if x.get('unnecessary_hold')],
    'errors':[x['name'] for x in results if 'instrument_or_validation_error' in x],
    'original_replay':replay},indent=2))
