"""Three retained development-note diagnostics only; no provider, corpus acquisition or result replacement."""
import hashlib,json
from pathlib import Path
from unittest.mock import patch
from core import generation as g
from core.tests.test_v3_ordinary_notes import run
ROOT=Path(__file__).resolve().parents[3]
source=ROOT/'docs/rebuild/v1/ordinary-input-20260927/evidence/known-results.json'
rows=[]
with patch('socket.socket.connect',side_effect=AssertionError('Network denied')):
 for old in json.loads(source.read_text())['cases']:
  if old['name'] not in ('r1-note4','r1-note7','r1-note8'):continue
  fields,notes,picks=old['fields'],old['notes'],old['unchanged_picks']
  result=run(notes,picks,fields=fields)
  asked,context,_=g.v3_generation_fields(fields)
  reading=g.governance_for(notes,fields)[11]['preceding']
  rows.append({'name':old['name'],'outcomes':{label:{'status':result[label]['status'],'text':result[label]['text']} for label in picks},
    'units':[{'id':u['id'],'quote':u['quote'],'subject':reading['subjects'][u['id']],
              'unresolved':u['id'] in reading['unresolved_subjects'],'block':reading['block_of'][u['id']]} for u in reading['units']],
    'blocks':[{'owner':b['owner'],'units':[u['id'] for u in b['units']],'barrier':reading['barriers'][i]} for i,b in enumerate(reading['blocks'])],
    'coupled':{k:sorted(v) for k,v in reading['coupled'].items()},'inherited':reading['inherited_causes']})
result={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'generation_sha256':hashlib.sha256((ROOT/'rebuild/core/generation.py').read_bytes()).hexdigest(),
        'scope':'diagnostic only; no original result or denominator replaced','cases':rows}
Path(__file__).with_name('01-retained-before.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(rows,indent=2))
