"""Refuse every non-loopback socket connection in this test process (no provider/network calls)."""
import ipaddress
import socket

_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_getaddrinfo = socket.getaddrinfo
LOCAL_NAMES = {'localhost', 'localhost.localdomain', 'testserver'}


def _allowed_host(host):
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode('ascii', 'replace')
    if host in LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.split('%')[0]).is_loopback
    except ValueError:
        return False


def _check(address):
    if isinstance(address, tuple) and not _allowed_host(address[0]):
        raise OSError('resid2 sitecustomize: non-loopback connection refused: %r' % (address[0],))


def connect(self, address):
    _check(address)
    return _connect(self, address)


def connect_ex(self, address):
    _check(address)
    return _connect_ex(self, address)


def getaddrinfo(host, *args, **kwargs):
    if not _allowed_host(host):
        raise socket.gaierror('resid2 sitecustomize: name resolution refused: %r' % (host,))
    return _getaddrinfo(host, *args, **kwargs)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
