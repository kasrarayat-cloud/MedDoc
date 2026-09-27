import json as _json
_r1 = _json.load(open('/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/notes-repair3/r1-corpus.json'))
_BASE = [field('v3_1', 'Chief complaint'), field('v3_2', 'Allergies'), field('v3_3', 'Plan', 'long_text'),
         field('v3_4', 'Smoker', 'choice', ['Yes', 'No']), field('v3_5', 'Consent obtained', 'checkbox', ['Consent obtained']),
         field('v3_6', 'Clinician signature', 'signature')]
_INTAKE = [field('v3_r', 'Referring physician'), field('v3_v', 'Reason for visit'), field('v3_s', 'Smoker?', 'choice', ['Yes', 'No'])]
GROUP = os.environ.get('GROUP', 'all')
CORPUS = []
if GROUP in ('all', 'test'):
    CORPUS += [
     ('t-prose', _BASE, 'Patient presents with right knee pain for three weeks. Allergies: penicillin. '
      'Plan is physiotherapy twice weekly and review in six weeks.',
      {'Chief complaint': ['Patient presents with right knee pain for three weeks.'], 'Allergies': ['Allergies: penicillin.'],
       'Plan': ['Plan is physiotherapy twice weekly and review in six weeks.']}),
     ('t-lines', _BASE, 'Patient presents with right knee pain for three weeks.\nAllergies: penicillin.\nSmoker: No.\n'
      'Plan is physiotherapy twice weekly and review in six weeks.',
      {'Chief complaint': ['Patient presents with right knee pain for three weeks.'], 'Allergies': ['Allergies: penicillin.'],
       'Smoker': ['Smoker: No.'], 'Plan': ['Plan is physiotherapy twice weekly and review in six weeks.']}),
     ('t-worker', _INTAKE, 'Referring physician: Dr Example\nPatient presents with right knee pain.\nSmoker: yes',
      {'Referring physician': ['Referring physician: Dr Example'], 'Reason for visit': ['Patient presents with right knee pain.'],
       'Smoker?': ['Smoker: yes']}),
     ('t-r10', _BASE, 'Smoker: yes\nPatient seen today.', {'Smoker': ['Smoker: yes']}),
     ('t-social', _BASE, 'Smoker: No.\nThe patient drinks socially.', {'Smoker': ['Smoker: No.']}),
    ]
if GROUP in ('all', 'r1'):
    CORPUS += [(o['name'], _r1['fields'], o['notes'], o['picks']) for o in _r1['notes']]
