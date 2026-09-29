# Scratch-only settings wrapper: the test database name carries the required quillmd_qa_resid_ prefix.
import os
from quillmd.settings import *  # noqa: F401,F403
DATABASES['default']['TEST'] = {'NAME': os.environ.get('RESID_TEST_DB', 'quillmd_qa_resid_t1')}
