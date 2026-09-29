"""Settings for run_app_path_walk.py only: the candidate's own settings, with the TEST database pinned to a
quillmd_qa_diag_* name on the campaign QA PostgreSQL (127.0.0.1:55731, user quillmd_qa). Never the installed
database: the host, port, user and name prefix are asserted before anything connects. The environment file is not
read (QUILLMD_ENV_MANAGED=1 is set by the runner, so settings never calls load_dotenv)."""
import os
from quillmd.settings import *  # noqa: F401,F403
from quillmd.settings import DATABASES

assert os.environ.get('QUILLMD_ENV_MANAGED') == '1'
assert DATABASES['default']['HOST'] == '127.0.0.1' and DATABASES['default']['PORT'] == '55731'
assert DATABASES['default']['USER'] == 'quillmd_qa'
_name = os.environ['DIAG_TEST_DB']
assert _name.startswith('quillmd_qa_diag_')
DATABASES['default']['TEST'] = {'NAME': _name}
