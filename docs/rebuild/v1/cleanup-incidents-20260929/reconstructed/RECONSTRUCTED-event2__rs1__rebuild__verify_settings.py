"""Verification settings: the copied tree's settings, a throwaway QA database, and no non-localhost sockets."""
import socket as _socket

from quillmd.settings import *  # noqa: F401,F403

DATABASES['default']['NAME'] = 'quillmd_qa_resid_verify_rs1'  # noqa: F405
DATABASES['default']['TEST'] = {'NAME': 'quillmd_qa_resid_verify_rs1'}  # noqa: F405

_LOCAL = {'127.0.0.1', '::1', 'localhost'}
_real_connect = _socket.socket.connect
_real_connect_ex = _socket.socket.connect_ex
_real_create_connection = _socket.create_connection


def _check(address):
    if isinstance(address, tuple) and address and address[0] not in _LOCAL:
        raise OSError(f'verification guard: non-localhost socket refused ({address[0]!r})')


def _connect(self, address):
    _check(address)
    return _real_connect(self, address)


def _connect_ex(self, address):
    _check(address)
    return _real_connect_ex(self, address)


def _create_connection(address, *args, **kwargs):
    _check(address)
    return _real_create_connection(address, *args, **kwargs)


_socket.socket.connect = _connect
_socket.socket.connect_ex = _connect_ex
_socket.create_connection = _create_connection
