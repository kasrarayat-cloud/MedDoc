"""Scratch-only settings wrapper for independent reproduction. Not part of the tree under test."""
import os, socket
from quillmd.settings import *  # noqa: F401,F403
DATABASES['default']['TEST'] = {'NAME': os.environ['VERIFY_TEST_DB']}
assert DATABASES['default']['TEST']['NAME'].startswith('quillmd_qa_rr2_verify')
_real_connect = socket.socket.connect
def _guarded_connect(self, address, *args, **kwargs):
    host = address[0] if isinstance(address, tuple) else None
    if host is not None and host not in ('127.0.0.1', '::1', 'localhost'):
        raise OSError(f'verify harness: non-localhost socket denied ({host})')
    return _real_connect(self, address, *args, **kwargs)
socket.socket.connect = _guarded_connect
