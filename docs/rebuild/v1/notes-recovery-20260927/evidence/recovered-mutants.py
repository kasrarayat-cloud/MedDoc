MUTANTS = [
 ('N1 no note-wide spoken-correction hold', [("warnings = list(scope['corrections'])", 'warnings = []')]),
 ('N2 no consent context hold', [("if re.search(SUBJECTS[0], str(label or ''), re.I):", 'if False:')]),
 ('N3 no shared note context', [('if len(governance) > 11 and evidence:', 'if False:')]),
 ('N4 incomplete paragraph allowed', [('ids <= picked[key] and target.get', 'True and target.get')]),
 ('N5 competing destinations allowed', [('len(owners) != 1', 'not owners')]),
 ('N6 duplicate destination allowed', [('labels_count[name] == 1', 'True')]),
 ('N7 option paragraph allowed', [("target.get('kind') in ('text', 'long_text')", 'True')]),
 ('N8 labelled paragraph allowed', [("or any(parsed_of[unit['id']] for unit in group)", '')]),
 ('N9 side row label allowed', [("and not re.search(r'\\b(?:left|right|bilateral)\\b|[—–:]|\\d', name, re.I)", '')]),
 ('N10 model order retained', [("choices=sorted(choices, key=lambda unit: unit['start'])", 'choices=choices')]),
 ('N11 full paragraph disabled', [("complete_paragraphs.setdefault(key, set()).update(ids)", 'pass')]),
]
for name, edits in MUTANTS:
 trial=SRC
 for old,new in edits:
  assert trial.count(old)==1,(name,trial.count(old));trial=trial.replace(old,new)
 compile(trial, name, 'exec')
