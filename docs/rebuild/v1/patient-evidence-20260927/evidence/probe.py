"""Finite source-relationship diagnosis; no model, database or application writes."""
import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
import django
django.setup()
from core import generation as g
from core.tests.test_v3_patient_topics import retained
from core.tests.test_v3_ordinary_notes import run

HERE = Path(__file__).resolve().parent
TARGETS = ('Chief complaint', 'History of present illness', 'Medications', 'Smoker')


def main():
    case = retained()
    # The adversarial sources vary only the Assessment. They are independent
    # design controls, not replacements for any retained note or selected quote.
    cases = [
        ('original', None, 'Original four source selections are currently held.'),
        ('smoking-assessment', 'daily cigarette smoking.',
         'The nonsmoker source cannot be declared independent of this opposing Assessment by actor alone.'),
        ('medication-cessation-assessment', 'ibuprofen cessation.',
         'The medication source cannot be declared independent of this changed medication status by actor alone.'),
        ('allergy-anaphylaxis-assessment', 'penicillin anaphylaxis.',
         'Retain the earlier exact NKA-class hold.'),
        ('allergy-hypersensitivity-assessment', 'penicillin hypersensitivity.',
         'Retain the earlier exact NKA-class hold.'),
    ]
    (HERE / 'predeclared.json').write_text(json.dumps(cases, indent=2) + '\n')
    result = []
    with patch('socket.socket.connect', side_effect=AssertionError('Network denied')):
        for name, assessment, expected in cases:
            notes = case['notes'] if assessment is None else case['notes'].replace('tension-type headache.', assessment)
            # The intended Assessment quotation is omitted from this probe's
            # offers because the challenge concerns the other field's context.
            picks = {label: case['unchanged_picks'][label] for label in (*TARGETS, 'Allergies')}
            answers = run(notes, picks, fields=case['fields'])
            governance = g.governance_for(notes, case['fields'])
            reading = governance[11]['preceding']
            ledger = reading['actor_relations']
            rows = {}
            for label, quotes in picks.items():
                evidence = [{'quote': q, 'start': notes.index(q), 'end': notes.index(q) + len(q)} for q in quotes]
                value = 'No' if label == 'Smoker' else '\n'.join(quotes)
                stored = {'status': 'supported', 'text': value, 'reviewed': True, 'evidence': evidence}
                key = next(f['key'] for f in case['fields'] if f['label'] == label)
                rows[label] = {'quotes': quotes, 'answer': answers[label],
                    'forced_stored_governed': g.governed_decisions(notes, case['fields'], {key: stored}),
                    'source_scope': {k: sorted(v) for k,v in g.v3_scope_selection(reading, label, evidence).items()}}
            result.append({'case':name, 'notes':notes, 'design_expectation':expected,
                'all_units_have_actor_relation': set(ledger['units']) == {u['id'] for u in reading['units']},
                'actor_relations': ledger,
                'units': [{k:u[k] for k in ('id','start','end','quote')} for u in reading['units']],
                'blocks': [{'owner':b['owner'],'units':[u['id'] for u in b['units']]} for b in reading['blocks']],
                'actor_destinations': sorted(reading['actor_destinations']), 'answers':rows})
    output = {'scope':'Five predeclared structural diagnosis controls; no eligibility override or simulated repair.',
              'base':'e37e17f041cb9e080f2a8f176b2ad8b6930aa880',
              'generation_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(), 'cases':result}
    (HERE/'result.json').write_text(json.dumps(output,indent=2,default=lambda x: sorted(x))+'\n')
    for row in result:
        print(row['case'], 'complete_actor_ledger=',row['all_units_have_actor_relation'],
              'states=', {k:v['answer']['status'] for k,v in row['answers'].items()},
              'stored_governed=',{k:v['forced_stored_governed'] for k,v in row['answers'].items()})


if __name__ == '__main__':
    main()
