import os, sys, json, copy, socket
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-mapping-capacity/rebuild')
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic-only',QUILLMD_DB_PASSWORD='unused',QUILLMD_DB_PORT='1',QUILLMD_AI_MODE='fixture')
import django
django.setup()
socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Network forbidden'))
from core import mapping_wire as w
from pydantic import ValidationError as PV
from django.core.exceptions import ValidationError as DV
slots=[{'slot':f'b/p[{i}]','text':'Plan 🙂 rest','heading':'Visit','row_label':'','options':['Yes','No']} for i in range(4)]
p={'fields':[{'key':'a','label':'Plan','slots':['b/p[0]']}],'slots':slots}
p['text_refs']=w.catalog(p)
base={'f':{'k':[0],'r':[],'n':[],'u':[]},'s':{'c':[0],'n':[],'u':[1,2,3]},'x':[],'e':False}
checks=[]
def reject(name,fn):
 try: fn()
 except (PV,DV): checks.append(name);return
 raise AssertionError('ACCEPTED '+name)
def variant(fn):
 b=copy.deepcopy(base);fn(b);return b
assert w.expand(p,base)[0]['fields'][0]['key']=='a';checks.append('positive keep')
for typ in ('f','s'):
 for name,fn in [('missing',lambda b,t=typ:b[t].update({k:[] for k in b[t]})),('duplicate',lambda b,t=typ:b[t][next(iter(b[t]))].append(0)),('boolean',lambda b,t=typ:b[t][next(iter(b[t]))].__setitem__(0,False)),('out of range',lambda b,t=typ:b[t][next(iter(b[t]))].__setitem__(0,9999))]:
  reject(typ+' '+name,lambda fn=fn:w.expand(p,variant(fn)))
refs=p['text_refs']; ref=refs.index([1,0,0])
good=variant(lambda b:b['x'].append([-1,1,0,ref,0,4,-1]))
assert w.expand(p,good)[0]['additions'][0]['label']=='Plan';checks.append('positive source span')
emoji=copy.deepcopy(good);emoji['x'][0][4:6]=[5,6]
assert w.expand(p,emoji)[0]['additions'][0]['label']=='🙂';checks.append('unicode codepoint')
for index,value,name in [(0,-2,'bad prior'),(1,4,'bad slot'),(2,8,'bad kind'),(3,-1,'negative ref'),(3,refs.index([0,0,0]),'foreign ref'),(3,refs.index([0,4,0]),'foreign prior label'),(4,-1,'negative start'),(5,999,'long end'),(6,200,'glyph bound')]:
 b=copy.deepcopy(good);b['x'][0][index]=value
 reject(name,lambda b=b:w.expand(p,b))
for index in range(7):
 b=copy.deepcopy(good);b['x'][0][index]=True
 reject('strict number '+str(index),lambda b=b:w.expand(p,b))
b=copy.deepcopy(good);b['x'][0].append(0);reject('partial option triple',lambda:w.expand(p,b))
b=copy.deepcopy(good);b['x']=b['x']*101;reject('101 changes',lambda:w.expand(p,b))
b=copy.deepcopy(base);b['f']={'k':[],'r':[0],'n':[],'u':[]};reject('unbound replacement',lambda:w.expand(p,b))
b['x']=[[0,1,0,ref,0,4,-1]];reject('replacement moves source',lambda:w.expand(p,b))
b=copy.deepcopy(base);b['x']=[[-1,i,4,refs.index([i,0,0]),0,4,-1]+[refs.index([i,3,0]),0,3]*100 for i in range(4)]
assert len(w.expand(p,b)[0]['additions'])==4;checks.append('400 option spans boundary')
b['x'].append([-1,1,4,ref,0,4,-1,refs.index([1,3,0]),0,3]);reject('401 options',lambda:w.expand(p,b))
b=copy.deepcopy(base);b['e']=True;assert w.expand(p,b)[1] is True;checks.append('capacity exhaustion retained')
print(json.dumps({'result':'PASS','count':len(checks),'checks':checks,'scope':'wire validation only; no clinical judgment or actual endpoint proof'},indent=2))
