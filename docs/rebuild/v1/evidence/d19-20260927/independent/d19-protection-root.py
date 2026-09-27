from documents.test_signing_areas import signing_form
from documents import word_v3 as w
from copy import deepcopy
import json,hashlib
rows=[]
for floating in (False,True):
 original=signing_form(table=floating);fields=w.inspect(original)['fields']
 safe=next(x for x in fields if not x.get('write_protected'))
 name=next(x for x in fields if x['label']=='Name of Participant')
 for mode in ('paragraph_options','stripped_flag','copy','normal','blank'):
  f=deepcopy(safe); answer='SYNTHETIC-123'
  if mode=='paragraph_options':
   f['kind']='choice';f['options']=['Yes'];f['locator']['target']={'type':'paragraph_options','paragraphs':[name['locator']['slot']],'printed':['Yes']};answer='Yes'
  elif mode=='stripped_flag':f=deepcopy(name);f.pop('write_protected');f['kind']='text'
  elif mode=='copy':f['locator']['target']['copies']=[{k:name['locator'][k] for k in ('part','slot','fingerprint')}]
  elif mode=='blank':answer=''
  should_refuse=(mode not in ('normal','blank')) or (floating and mode=='normal')
  row={'floating':floating,'mode':mode,'expected_refusal':should_refuse}
  try:
   out=w.fill(original,[f],{f['key']:answer});row['refused']=False
   oldindex=w.SlotIndex(w.open_package(original));newindex=w.SlotIndex(w.open_package(out))
   loc=name['locator']['part']+'#'+name['locator']['slot']
   from lxml import etree
   row['signing_bytes_unchanged']=etree.tostring(oldindex.by_id[loc].el)==etree.tostring(newindex.by_id[loc].el)
   assert not should_refuse,row
   assert row['signing_bytes_unchanged'],row
  except w.V3Failure as exc:
   row['refused']=True;row['message']=str(exc);assert should_refuse,row
  rows.append(row)
print(json.dumps({'source_sha256':hashlib.sha256(open('documents/word_v3.py','rb').read()).hexdigest(),'cases':rows,'passed':True},indent=2))
