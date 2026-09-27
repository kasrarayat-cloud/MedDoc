import sys,importlib.util,json,hashlib
from pathlib import Path
from unittest.mock import patch
root=Path('/opt/meddoc-pro/.worktrees/v1-word-d30/rebuild');sys.path.insert(0,str(root))
from documents import word_v3 as w
p=Path('/opt/meddoc-pro/.worktrees/v1-patient-topics/rebuild/.runtime/d30-refutation-20260927/probe.py')
spec=importlib.util.spec_from_file_location('independent_construction',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rows=[]
with patch('socket.socket.connect',side_effect=AssertionError('Network denied')):
 for name,doc,expected in m.cases():
  if name not in ['direct-donor-heading','inherited-donor-heading','two-paragraph-question']:continue
  raw=m.encode(doc);out=w.inspect(raw)
  rows.append({'name':name,'fields':out['fields'],'warnings':out['notes']})
print(json.dumps({'engine_sha256':hashlib.sha256(Path(w.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
