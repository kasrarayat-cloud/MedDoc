from pathlib import Path
import ast,re,hashlib,json
root=Path('/opt/meddoc-pro/.worktrees/v1-release')
functions={};guards={}
for path in sorted((root/'rebuild/core/migrations').glob('*.py')):
 tree=ast.parse(path.read_text())
 for node in ast.walk(tree):
  if not isinstance(node,ast.Constant) or not isinstance(node.value,str):continue
  sql=node.value
  for name,body in re.findall(r'CREATE FUNCTION (quillmd_\w+)\(\) RETURNS trigger\s+LANGUAGE plpgsql AS \$\$(.*?)\$\$',sql,re.S):
   sha=hashlib.sha256(body.encode()).hexdigest();assert name not in functions or functions[name]==sha;functions[name]=sha
  for name,event,table,each,function in re.findall(r'CREATE TRIGGER (\w+)\s+BEFORE ([A-Z ]+?)\s+ON (\w+)\s+FOR EACH (ROW|STATEMENT) EXECUTE FUNCTION (quillmd_\w+)\(\)',sql):
   kind=2+(1 if each=='ROW' else 0)+sum({'INSERT':4,'DELETE':8,'UPDATE':16,'TRUNCATE':32}[x] for x in event.split(' OR '))
   guards[(table,name)]=(function,kind)
assert len(guards)==17 and len(functions)==10,(len(guards),len(functions))
header='''"""Release-bound PostgreSQL integrity definitions for a production restore drill.

Expected bodies come from reviewed migration SQL, never the inspected database.
This is a point-in-time catalog check, not protection against a privileged owner.
Keep the migration parity test and this contract in the same reviewed change.
"""
import hashlib

'''
header+='FUNCTION_SHA256 = '+repr(dict(sorted(functions.items())))+'\n\n'
header+='GUARDS = '+repr(tuple((t,n,f,k) for (t,n),(f,k) in sorted(guards.items())))+'\n\n'
(root/'rebuild/ops/integrity_contract.py').write_text(header)
print(json.dumps({'guards':len(guards),'functions':len(functions),'generation_source':'reviewed migration literal SQL; no database query'},indent=2))
