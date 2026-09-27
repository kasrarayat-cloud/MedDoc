import json,sys,hashlib
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'rebuild'))
from anthropic import transform_schema
from core.mapping_wire import Proposal
schema=Proposal.model_json_schema();before=json.dumps(schema,sort_keys=True)
def unsupported(value,path='$'):
 out=[]
 if isinstance(value,dict):
  for key,item in value.items():
   if key in {'minimum','maximum','exclusiveMinimum','exclusiveMaximum','maxItems'} or key=='minItems' and item not in [0,1]:out.append([path+'.'+key,item])
   out+=unsupported(item,path+'.'+key)
 elif isinstance(value,list):
  for n,item in enumerate(value):out+=unsupported(item,path+f'[{n}]')
 return out
fixed=transform_schema(Proposal)
assert json.dumps(schema,sort_keys=True)==before
assert not unsupported(fixed)
print(json.dumps({'raw_unsupported':unsupported(schema),'transformed_unsupported':unsupported(fixed),
 'raw_schema_sha256':hashlib.sha256(before.encode()).hexdigest(),
 'transformed_schema_sha256':hashlib.sha256(json.dumps(fixed,sort_keys=True).encode()).hexdigest(),
 'raw_bytes':len(before.encode()),'transformed_bytes':len(json.dumps(fixed,sort_keys=True).encode())},indent=2))
