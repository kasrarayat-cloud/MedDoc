from pathlib import Path
import os, json, hashlib
scratch=Path('/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/notes-repair3')
os.environ['ROOT']='/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild'
os.environ['GROUP']='all'
exec((scratch/'measure.py').read_text().split("exec(open")[0])
exec((scratch/'corpus.py').read_text())
cases=[]
for name,fields,notes,picks in CORPUS:
 answers=run(notes,picks,fields)
 cases.append({'name':name,'fields':fields,'notes':notes,'unchanged_picks':picks,'answers':answers,
               'selected_supported':sum(answers[label]['status']=='supported' for label in picks),'selected_total':len(picks)})
report={'scope':'Repaired known synthetic inputs and unchanged simulated selections; no live model or new campaign. Original first-pass denominators/results remain retained separately.',
        'generation_sha256':hashlib.sha256(Path(os.environ['ROOT'],'core/generation.py').read_bytes()).hexdigest(),
        'input_sha256':{name:hashlib.sha256((scratch/name).read_bytes()).hexdigest() for name in ('measure.py','corpus.py','r1-corpus.json')},
        'cases':cases}
Path('/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild/.runtime/ordinary-context-20260927/round2/known-results.json').write_text(json.dumps(report,indent=2)+'\n')
for prefix in ('t-','r1-'):
 subset=[c for c in cases if c['name'].startswith(prefix)]
 print(prefix,sum(c['selected_supported'] for c in subset),'/',sum(c['selected_total'] for c in subset))
for case in cases:
 print(case['name'],case['selected_supported'],'/',case['selected_total'],[(label,a['status']) for label,a in case['answers'].items() if label in case['unchanged_picks']])
