import json,os,socket,sys,time
from pathlib import Path
OUT=Path(__file__).parent
WT=Path('/opt/meddoc-pro/.worktrees/v1-elicited-passive-6fee1665')
def deny(*args,**kwargs):raise AssertionError('Offline diagnosis prohibits network/DB')
socket.socket.connect=deny
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_ENV_MANAGED='1',QUILLMD_SECRET_KEY='synthetic-offline-elicited-reference',QUILLMD_STATE_DIR=str(OUT/'state'),QUILLMD_DB_HOST='127.0.0.1',QUILLMD_DB_PORT='1',QUILLMD_DB_NAME='unreachable',QUILLMD_DB_USER='unreachable',QUILLMD_DB_PASSWORD='synthetic-unused',QUILLMD_DATA_MODE='synthetic',QUILLMD_AI_MODE='fixture')
sys.path.insert(0,str(WT/'rebuild'))
import django;django.setup()
from django.test import override_settings
from core import generation as g,v3_field_relations as r,v3_syntax as syntax,reviewed_source
from core.tests.test_v3_literal_facts import FIXTURE,fields
from core.tests.test_v3_field_relations import offered
from core.tests.test_v3_ordinary_notes import LIVE
start=time.monotonic()
target=next(f for f in fields()if f['key']=='v3_25')
quote=next(row['quote']for row in FIXTURE['cases']if row['key']==target['key'])
rows=[]
with override_settings(**dict(LIVE,V3_FIELD_RELATIONS=True,V3_HISTORY_CONTEXT=False)):
    for tail in ('That report was denied by the patient.', 'That statement was not made by the patient.', 'That statement was not true.'):
        notes=quote+'\n'+tail
        answers=offered(notes,[target],{target['key']:[quote]})
        answer=answers[target['key']]
        governance=g.governance_for(notes,[target]);reading=governance[11]['preceding']
        docs=syntax.docs(u['quote']for u in reading['units']);labels=syntax.docs([target['label']])
        selected=[u for u in reading['units']if u['quote']==quote]
        stale={k:v for k,v in answer.items()if k!='held_candidate'};stale.update(status='supported',text=quote)
        stale_page=g.as_currently_governed(governance,notes,{**target,**stale})
        stale_final=g.governed_decisions(notes,[target],{target['key']:stale})
        assert stale_page['status']=='conflict' and stale_page['text']=='' and stale_final==[target['label']]
        read=r.read(reading,target['label'],[{k:u[k]for k in ('quote','start','end')}for u in selected],answer['ordinary_relation'],field_key=target['key'])
        rows.append({'notes':notes,'target':target,'answer':answer,
            'page':g.as_currently_governed(governance,notes,{**target,**answer}),
            'final_decisions':g.governed_decisions(notes,[target],answers),'stale_supported_page':stale_page,'stale_supported_final_decisions':stale_final,'ordinary_read':read,
            'existing_backward_attribution':reviewed_source.backward_attribution(reading,selected,docs,labels[0]),
            'tail_parse':[{'text':t.text,'lemma':t.lemma_,'pos':t.pos_,'tag':t.tag_,'dep':t.dep_,'head':t.head.text,'morph':str(t.morph)}for t in docs[-1]]})
(OUT/'corrected-three-concrete-stale-final.json').write_text(json.dumps({'source_base':'6fee1665edb3d1b4d3fb346f2de36a351604730f','source_current_is_corrective_writer':True,'rows':rows,'provider_calls':0,'DB_calls':0,'elapsed_seconds':time.monotonic()-start},indent=2,default=list)+'\n')
print(json.dumps({'rows':[{'tail':row['notes'].split('\n')[-1],'answer':row['answer']['status'],'page':row['page']['status'],'final':row['final_decisions'],'existing_backward_attribution':row['existing_backward_attribution'],'tail_parse':row['tail_parse']}for row in rows]}))
