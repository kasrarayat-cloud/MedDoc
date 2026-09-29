import socket, ipaddress
_real = socket.socket.connect
def _guard(self, address, *a, **k):
    host = address[0] if isinstance(address, tuple) else None
    if host is not None:
        try:
            ip = ipaddress.ip_address(host)
            if not ip.is_loopback:
                raise PermissionError('non-loopback socket denied in refutation scratch: %r' % (address,))
        except ValueError:
            if host not in ('localhost',):
                raise PermissionError('non-loopback socket denied in refutation scratch: %r' % (address,))
    return _real(self, address, *a, **k)
socket.socket.connect = _guard
