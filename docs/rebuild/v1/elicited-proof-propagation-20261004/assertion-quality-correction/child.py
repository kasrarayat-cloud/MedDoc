import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time
import unittest

START = time.monotonic()
OUT = Path(__file__).parent
WT = Path('/opt/meddoc-pro/.worktrees/v1-elicited-quality-87628551')
attempts = []
def deny(sock, address):
    attempts.append(repr(address))
    raise AssertionError('Pure elicited-proof packet prohibits network and DB')
socket.socket.connect = deny
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings', QUILLMD_ENV_MANAGED='1',
                  QUILLMD_SECRET_KEY='synthetic-offline-elicited-proof', QUILLMD_STATE_DIR=str(OUT / 'state'),
                  QUILLMD_DB_HOST='127.0.0.1', QUILLMD_DB_PORT='1', QUILLMD_DB_NAME='unreachable',
                  QUILLMD_DB_USER='unreachable', QUILLMD_DB_PASSWORD='synthetic-unused',
                  QUILLMD_DATA_MODE='synthetic', QUILLMD_AI_MODE='fixture')
sys.path.insert(0, str(WT / 'rebuild'))
import django
django.setup()
selectors = [
    'core.tests.test_elicited_assertion_quality.ElicitedAssertionQuality',
    'core.tests.test_v3_literal_facts.OrdinaryLiteralFacts',
    'core.tests.test_v3_notes_floors.EveryArm.test_every_exemption_keeps_its_control_useful',
]
suite = unittest.defaultTestLoader.loadTestsFromNames(selectors)
packet = unittest.TextTestRunner(verbosity=2).run(suite)
result = {'selectors': selectors, 'tests_run': packet.testsRun, 'failures': len(packet.failures),
          'errors': len(packet.errors), 'successful': packet.wasSuccessful(),
          'network_attempts': attempts, 'provider_calls': 0, 'DB_calls': 0,
          'elapsed_seconds': time.monotonic() - START}
(OUT / 'child-result-r1.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
sys.exit(0 if packet.wasSuccessful() and not attempts else 1)
