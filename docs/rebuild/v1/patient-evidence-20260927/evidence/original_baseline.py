"""Exact retained note4 and all original eight picks; pure baseline only."""
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

case = retained()
with patch('socket.socket.connect', side_effect=AssertionError('Network denied')):
    answers = run(case['notes'], case['unchanged_picks'], fields=case['fields'])
result = {'base': 'e37e17f041cb9e080f2a8f176b2ad8b6930aa880',
          'generation_sha256': hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),
          'name': case['name'], 'notes': case['notes'], 'fields': case['fields'],
          'unchanged_picks': case['unchanged_picks'], 'answers': answers,
          'selected_supported': sum(answers[label]['status'] == 'supported' for label in case['unchanged_picks']),
          'selected_total': len(case['unchanged_picks'])}
Path(__file__).with_name('original-baseline.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({label: {'status': answers[label]['status'], 'text': answers[label]['text']}
                  for label in case['unchanged_picks']}, indent=2))
