"""Refuse every network connection but the synthetic QA database (127.0.0.1:55731) for the life of a test module.

Refused BEFORE anything leaves the process: a name lookup (getaddrinfo) or a connect() to any other address raises
`NetworkDenied`, so neither a DNS query nor a packet is sent. A local (AF_UNIX) path is not a network address and is
allowed. The database driver's own C-level connection is to the one allowed address anyway.
"""
import socket

ALLOWED = frozenset({('127.0.0.1', 55731)})
LOOKUP_HOSTS = frozenset({'127.0.0.1', 'localhost'})


class NetworkDenied(AssertionError):
    pass


_saved = {}


def _allowed(address):
    if isinstance(address, (str, bytes)):
        return True                                   # (a unix socket path is not the network)
    return (str(address[0]), int(address[1])) in ALLOWED


def start():
    if _saved:
        return
    _saved.update(connect=socket.socket.connect, connect_ex=socket.socket.connect_ex, getaddrinfo=socket.getaddrinfo,
                  create_connection=socket.create_connection)

    def connect(self, address):
        if not _allowed(address):
            raise NetworkDenied(f'network connection refused by the test guard: {address!r}')
        return _saved['connect'](self, address)

    def connect_ex(self, address):
        if not _allowed(address):
            raise NetworkDenied(f'network connection refused by the test guard: {address!r}')
        return _saved['connect_ex'](self, address)

    def getaddrinfo(host, port, *args, **kwargs):
        host = host.decode() if isinstance(host, bytes) else host
        if host not in LOOKUP_HOSTS or str(port) != '55731':
            raise NetworkDenied(f'name lookup refused by the test guard: {host!r}:{port!r}')
        return _saved['getaddrinfo'](host, port, *args, **kwargs)

    def create_connection(address, *args, **kwargs):
        if not _allowed(address):
            raise NetworkDenied(f'network connection refused by the test guard: {address!r}')
        return _saved['create_connection'](address, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo
    socket.create_connection = create_connection


def stop():
    if not _saved:
        return
    socket.socket.connect = _saved['connect']
    socket.socket.connect_ex = _saved['connect_ex']
    socket.getaddrinfo = _saved['getaddrinfo']
    socket.create_connection = _saved['create_connection']
    _saved.clear()


def positive_control(test):
    """Asserts the guard refuses a real provider host and a public address, before any lookup or packet."""
    with test.assertRaises(NetworkDenied):
        socket.create_connection(('api.anthropic.com', 443), timeout=1)
    with test.assertRaises(NetworkDenied):
        socket.getaddrinfo('api.anthropic.com', 443)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with test.assertRaises(NetworkDenied):
            probe.connect(('192.0.2.1', 443))
    finally:
        probe.close()
