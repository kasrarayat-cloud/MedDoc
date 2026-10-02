from pathlib import Path
import ast,copy,hashlib,importlib.util,json,socket,subprocess,sys,types
from unittest.mock import patch
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-custodian-cost-review')
OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'rebuild'))
# No network and no Django application/DB initialization in this pure probe.
def denied(*args,**kwargs):raise AssertionError('network forbidden')
socket.create_connection=denied
socket.socket.connect=denied
from django.conf import settings
settings.configure(V3_HISTORY_CONTEXT=True)
from core import generation as g
from core import v3_history_context as h
from ops import test_production_deploy as scan
source=(ROOT/'rebuild/core/generation.py').read_text()
tree=ast.parse(source);function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='maximum_cost')
parent_source=subprocess.check_output(['git','show','2023b9c2^:rebuild/ops/test_production_deploy.py'],cwd=ROOT,text=True)
(OUT/'parent-scanner.py').write_text(parent_source)
spec=importlib.util.spec_from_file_location('ops.parent_cost_scan',OUT/'parent-scanner.py');parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
parent.REBUILD=ROOT/'rebuild';parent.GENERATION=ROOT/'rebuild/core/generation.py'
config={'mode':'live','provider':'anthropic','model':'claude-sonnet-5','input_rate':'2','output_rate':'10','cached_rate':'0.2','prompt_version':g.CURRENT_PROMPT_VERSION,'v3_evidence_contract':g.V3_EVIDENCE_CONTRACT,'history_context_contract':h.CONTRACT,'request_profile':g.request_profile('anthropic','claude-sonnet-5','disabled','medium','')}
fields=[{'key':'chief','label':'Chief complaint','kind':'text','context':'','locator':{'contract':'v3','part':'word/document.xml','slot':'b/p[1]','target':{'type':'span','start':0,'end':0,'shape':'after_label'},'fingerprint':'0'*64}}]
notes='Patient presents with a cough.'
results=[]
for case in ('unchanged','false_wrapper','early_return'):
 t=copy.deepcopy(tree);f=next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='maximum_cost');idx=next(i for i,n in enumerate(f.body) if isinstance(n,ast.If) and ast.unparse(n.test)=="config.get('history_context_contract')")
 if case=='false_wrapper':f.body[idx]=ast.If(test=ast.Constant(value=False),body=[f.body[idx]],orelse=[])
 elif case=='early_return':f.body.insert(idx,ast.Return(value=ast.Name(id='bound',ctx=ast.Load())))
 ast.fix_missing_locations(t);mutated=source if case=='unchanged' else ast.unparse(t)+'\n';p=OUT/(case+'-generation.py');p.write_text(mutated)
 row={'case':case,'source_sha256':hashlib.sha256(mutated.encode()).hexdigest(),'scanners':{}}
 for name,s in [('parent',parent),('finished',scan)]:
  with patch.object(s,'GENERATION',p):
   try:row['scanners'][name]={'accepted':True,'terms':repr(s.maximum_cost_terms())}
   except AssertionError as exc:row['scanners'][name]={'accepted':False,'reason':str(exc)}
 # Evaluate the actual maximum_cost function with the unchanged real module globals.
 f=next(n for n in ast.parse(mutated).body if isinstance(n,ast.FunctionDef) and n.name=='maximum_cost')
 code=compile(ast.Module(body=[f],type_ignores=[]),str(p),'exec');scope=dict(vars(g));exec(code,scope)
 row['cost_usd']=str(scope['maximum_cost'](notes,fields,config))
 results.append(row)
(OUT/'results.json').write_text(json.dumps({'source_commit':'2023b9c212bab9d94471a670a10d556e036a7836','input':{'notes':notes,'fields':fields,'config':config},'cases':results},indent=2)+'\n')
print(json.dumps(results,indent=2))
