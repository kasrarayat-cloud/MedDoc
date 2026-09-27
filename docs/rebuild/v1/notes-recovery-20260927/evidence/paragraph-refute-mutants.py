MUTANTS = [
 ('P1 allow every named destination', [("and name in {'history', 'history of present illness', 'hpi', 'reason for visit',\n                                 'plan', 'treatment plan', 'management plan'}", 'and True')]),
 ('P2 drop repeated instruction occurrence', [("value not in texts or unit['id'] in complete_paragraphs.get(item.key, ())", 'value not in texts')]),
]
for name, edits in MUTANTS:
 trial=SRC
 for old,new in edits:
  assert trial.count(old)==1,(name,trial.count(old));trial=trial.replace(old,new)
 compile(trial,name,'exec')
