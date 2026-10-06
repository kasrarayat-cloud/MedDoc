import os,sys,json,socket,hashlib,time
from pathlib import Path
from unittest.mock import patch
SOURCE=Path('/opt/meddoc-pro/.worktrees/v1-sol-notes-voice')
SCRATCH=Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/security')
prior=json.loads((SCRATCH/'refute-clinical-6f0f647a.json').read_text())
manifest=prior['source_manifest']
def verify():
    for row in manifest['files']:
        assert hashlib.sha256((SOURCE/row['path']).read_bytes()).hexdigest()==row['sha256']
verify()
sys.path.insert(0,str(SOURCE/'rebuild'))
os.environ.update(QUILLMD_ENV_MANAGED='1',QUILLMD_SECRET_KEY='synthetic-refutation-only',
    QUILLMD_DATA_MODE='synthetic',QUILLMD_AI_MODE='fixture',DJANGO_SETTINGS_MODULE='quillmd.settings',
    QUILLMD_DB_PASSWORD='synthetic-unusable-no-connection',QUILLMD_DB_HOST='127.0.0.1',
    QUILLMD_DB_PORT='1',QUILLMD_STATE_DIR=str(SCRATCH/'refute-state'))
import django
django.setup()
from django.test import override_settings
from django.db.backends.base.base import BaseDatabaseWrapper
from core import generation as g,transcript_context as tc,v3_syntax as syntax,source_scope
from core.tests.test_v3_supersession_floor import SONNET_55_DEFAULT,form
from core.tests.test_transcript_context import proof
def safe(value):
    if isinstance(value,dict):return {str(k):safe(v) for k,v in value.items()}
    if isinstance(value,(set,frozenset)):return sorted((safe(v) for v in value),key=repr)
    if isinstance(value,(list,tuple)):return [safe(v) for v in value]
    return value
results=[]
started=time.monotonic()
with override_settings(**SONNET_55_DEFAULT), \
    patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')), \
    patch.object(BaseDatabaseWrapper,'ensure_connection',side_effect=AssertionError('Database forbidden')):
    for case in prior['cases']:
        if not (case.get('demonstrated_unsafe_release') or case.get('unnecessary_hold')):continue
        assert time.monotonic()-started<90
        notes=case['notes'];label='Examination' if case['selected_quote'].startswith('Examination') else 'Symptoms'
        fields=form(label,'Plan')
        reading=g.governance_for(notes,fields)[-1]['preceding']
        reading=tc.apply(reading,proof(notes))
        docs=syntax.docs(unit['quote'] for unit in reading['units'])
        units=[]
        for unit,doc in zip(reading['units'],docs):
            uid=unit['id']
            units.append({'source':unit,'actors':safe(reading['actors'][uid]),
                'resolved':safe(reading['resolved'][uid]),'claim_keys':safe(reading['claim_keys'][uid]),
                'negated_keys':safe(reading['negated_keys'][uid]),'predicates':safe(reading['predicates'][uid]),
                'tokens':[{'i':t.i,'text':t.text,'lemma':t.lemma_,'pos':t.pos_,'tag':t.tag_,
                    'dep':t.dep_,'head_i':t.head.i,'head_text':t.head.text} for t in doc]})
        picked=next(u for u in reading['units'] if u['quote']==case['selected_quote'])
        results.append({'name':case['name'],'notes':notes,'units':units,
            'confirmed_patient':safe(reading.get('confirmed_patient',())),
            'nominal_patient':safe(reading.get('nominal_patient',())),
            'dependent_reach':safe(reading.get('dependent_reach')),
            'elliptical_dependencies':safe(source_scope.elliptical_dependencies(reading)),
            'exclusive_reattributions':safe(source_scope.exclusive_reattributions(reading)),
            'malformed_denial_dependencies':safe(source_scope.malformed_denial_dependencies(reading)),
            'prefixed_modifier_dependencies':safe(source_scope.prefixed_modifier_dependencies(reading)),
            'relation_causes':safe(g.v3_relation_causes(reading,picked,label,{picked['id']},field_key='f1'))})
verify()
out={'source_commit':manifest['commit'],'all_source_hashes_unchanged':True,'database_connections':0,
    'provider_requests':0,'cases':results,'elapsed_seconds':round(time.monotonic()-started,3)}
p=SCRATCH/'diagnose-clinical-6f0f647a.json'
fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
with os.fdopen(fd,'w') as f:json.dump(out,f,indent=2)
print(json.dumps({'source_commit':out['source_commit'],'cases':len(results),'elapsed_seconds':out['elapsed_seconds'],
    'witness':str(p),'summaries':[{'name':c['name'],'causes':c['relation_causes'],
        'actors':[{'quote':u['source']['quote'],'kind':u['actors']['kind'],'other_floor':u['actors']['other_floor'],
            'claim_keys':u['claim_keys'],'negated_keys':u['negated_keys'],'named_keys':u['actors'].get('named_keys')}
            for u in c['units']]} for c in results]},indent=2))
