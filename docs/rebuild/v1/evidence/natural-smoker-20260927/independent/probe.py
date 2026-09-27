import os, sys, json, copy, hashlib, socket
from pathlib import Path
ROOT = Path('/opt/meddoc-pro/.worktrees/v1-natural-smoker/rebuild')
sys.path.insert(0, str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings', QUILLMD_SECRET_KEY='synthetic', QUILLMD_AI_MODE='fixture', QUILLMD_ENV_MANAGED='1', QUILLMD_DB_PASSWORD='synthetic', QUILLMD_DB_PORT='1')
import django; django.setup()
from core import generation as g
if os.environ.get('TASK_GENERATION_BASE'):
    exec(compile(Path(os.environ['TASK_GENERATION_BASE']).read_text(), os.environ['TASK_GENERATION_BASE'], 'exec'), g.__dict__)
from core.tests.test_v3_ordinary_notes import field, run
from core.v3_nonsmoker import current_nonsmoker
from unittest.mock import patch
Q = 'The patient is a nonsmoker.'
F = [field('smoker', 'Smoker', 'choice', ['Yes', 'No'])]
out=[]
def compact(answer):
    return {k: answer[k] for k in ('status','text','evidence','held_candidate') if k in answer}
def generated(name, notes, fields=F, quote=Q):
    ans=run(notes, {fields[0]['label']: [quote]}, fields=fields)[fields[0]['label']]
    row=g.as_currently_governed(g.governance_for(notes,fields),notes,{**ans,'label':fields[0]['label']})
    out.append({'case':name,'notes':notes,'fields':fields,'answer':compact(ans),'page':compact(row),'refusals':g.governed_decisions(notes,fields,{fields[0]['key']:{**ans,'reviewed':True}})})
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
    for name,notes,quote in [('exact',Q,Q),('no-the','Patient is a nonsmoker.','Patient is a nonsmoker.'),('whitespace',' \n\t'+Q+'\n ',Q),('foreign','For the donor:\n'+Q,Q),('opposite',Q+'\n\nThe patient smokes daily.',Q),('conditional','If true:\n'+Q,Q),('invisible','\u200b'+Q,Q),('labelled-positive','Smoker: No.','Smoker: No.')]:
        try: generated(name,notes,quote=quote)
        except KeyError as exc: out.append({'case':name,'notes':notes,'unit_selection_refusal':str(exc),'units':g.source_units(notes,F)[0]})
    for name, change in [('reverse-options',{'options':['No','Yes']}),('extra-option',{'options':['Yes','No','Former']}),('scoped',{'context':'Mother'}),('case-label',{'label':'smoker'}),('punct-label',{'label':'Smoker?'}),('text',{'kind':'text'}),('long-text',{'kind':'long_text'}),('multi-choice',{'kind':'multi_choice'}),('duplicate-printed',{'locator':{**F[0]['locator'],'target':{'printed':['Yes','No','No']}}})]:
        fs=copy.deepcopy(F);fs[0].update(change);generated(name,Q,fs)
    generated('duplicate',Q,F+[field('other','Smoker?','choice',['Yes','No'])])
    for name,notes,mut in [('stored-positive',Q,{}),('stored-opposite',Q+'\n\nThe patient smokes daily.',{}),('stored-foreign','For the donor:\n'+Q,{}),('stored-wrong-end',Q,{'end':len(Q)-1}),('stored-off-start',Q,{'start':1}),('stored-missing-end',Q,{'end':None}),('stored-partial',Q,{'quote':'nonsmoker.','start':17}),('stored-wrong-answer',Q,{'answer':'Yes'})]:
        at=notes.index(Q); ev={'quote':Q,'start':at,'end':at+len(Q)}
        for k,v in mut.items():
            if k!='answer':
                if v is None:ev.pop(k,None)
                else:ev[k]=v
        ans={'text':mut.get('answer','No'),'status':'supported','reviewed':True,'evidence':[ev]}
        row=g.as_currently_governed(g.governance_for(notes,F),notes,{**ans,'label':'Smoker'})
        out.append({'case':name,'notes':notes,'stored':ans,'page':compact(row),'refusals':g.governed_decisions(notes,F,{'smoker':ans})})
    for name,mut in [('wrong-quote',{'quote':'Patient is a nonsmoker.'}),('bool-start',{'start':True}),('extra-evidence',{'extra':True}),('missing-end',{'remove':'end'})]:
        ev={'quote':Q,'start':0,'end':len(Q)};ev.update({k:v for k,v in mut.items() if k not in ('extra','remove')})
        if 'remove'in mut:ev.pop(mut['remove'])
        evidence=[ev]+([dict(ev)] if mut.get('extra') else [])
        ans={'status':'supported','text':Q,'evidence':evidence}
        out.append({'case':'direct-'+name,'answer':compact(g.v3_option_answer(F[0],ans,Q,g.recognized_labels(F)))})
print(json.dumps({'generation_sha256':hashlib.sha256((ROOT/'core/generation.py').read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256((ROOT/'core/v3_nonsmoker.py').read_bytes()).hexdigest(),'override':os.environ.get('TASK_GENERATION_BASE'),'cases':out},indent=2))
