# Scratch-only network guard: refuse every socket connection that is not loopback or a unix socket.
import socket
_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
def _allowed(address):
    if isinstance(address, (str, bytes)):
        return True  # AF_UNIX
    host = address[0] if isinstance(address, tuple) and address else ''
    return host in ('127.0.0.1', '::1', 'localhost')
def connect(self, address):
    if not _allowed(address):
        raise OSError('network guard: non-localhost connection refused: %r' % (address,))
    return _real_connect(self, address)
def connect_ex(self, address):
    if not _allowed(address):
        raise OSError('network guard: non-localhost connection refused: %r' % (address,))
    return _real_connect_ex(self, address)
socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
