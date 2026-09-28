"""Expected DEV maps only; proposed request partition counts, not calls or qualification."""
from pathlib import Path
from collections import Counter
import json,re,hashlib
B=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus');R=Path(__file__).parent
ledger=json.loads((B/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records'];rows=[]
for name in ('D03','D10','D11','D28','D29'):
 rec=next(r for r in ledger if r['development_id']==name);assert rec['offline_filled_copy_replay_supported']
 p=Path(rec['prior_expected_map_path']);g=json.loads(p.read_text());areas=g['answer_areas']
 # Join source areas sharing a physical table row. Preserve an area spanning
 # multiple rows by union, never split the question/options to reduce a count.
 parent=list(range(len(areas)))
 def find(i):
  while parent[i]!=i:i=parent[i]
  return i
 owners={}
 for i,a in enumerate(areas):
  for slot in a['slots']:
   match=re.match(r'(.+?#.+?/tbl\[\d+\]/tr\[\d+\])(?:/|$)',slot)
   group=match.group(1) if match else slot
   if group in owners:parent[find(i)]=find(owners[group])
   owners[group]=i
 groups={}
 for i,a in enumerate(areas):groups.setdefault(find(i),[]).append(a['id'])
 groups=list(groups.values());chunks=[];current=[]
 for group in groups:
  if len(current)+len(group)>100 and current:chunks.append(current);current=[]
  current+=group
 if current:chunks.append(current)
 rows.append({'id':name,'old_expected_count':len(areas),'expected_kind_counts':dict(Counter(a['kind'] for a in areas)),
              'source_map_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'physical_row_groups':[len(x) for x in groups],
              'largest_physical_row_group':max(map(len,groups)),'proposed_physical_partition_sizes':list(map(len,chunks)),
              'proposed_partition_ids':chunks,'guard':'This is not clinical independence; keep full notes/catalog and all cross-group constraints.'})
p=B/'custodian-20260927/corpus-independent-renewal-20260927/dev-independent-maps/D28.original-first.json';new=json.loads(p.read_text())
print(json.dumps({'scope':'expected maps only; no detector/provider/score','rows':rows,'D28_new_map':{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'keys':list(new),'count':len(new.get('areas',[]))}},indent=2))
