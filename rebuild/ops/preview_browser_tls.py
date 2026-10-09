"""Loopback-only TLS proxy for isolated account browser qualification.

Only the two exact certificate files are mounted read-only. No shared ingress,
DNS, certificate store, application service or real database is modified.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import http.client
import json
import re
from pathlib import Path
import ssl
import stat

ORIGIN_HOST = 'app.quillmd.com:19443'
CERT = Path('/certificate.pem')
KEY = Path('/private-key.pem')


class Proxy(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def handle_request(self):
        if self.headers.get('Host') != ORIGIN_HOST or not self.path.startswith('/') or self.path.startswith('//'):
            self.send_error(400)
            return
        length = int(self.headers.get('Content-Length', '0'))
        if length < 0 or length > 2 * 1024 * 1024:
            self.send_error(413)
            return
        body = self.rfile.read(length) if length else None
        headers = {key: value for key, value in self.headers.items() if key.lower() not in {
            'host', 'connection', 'x-real-ip', 'authorization', 'proxy-authorization', 'x-forwarded-for', 'x-forwarded-proto', 'x-quillmd-preview', 'x-quillmd-account'}}
        # The port belongs only to this isolated TLS harness. The application's
        # trusted transport is the same exact normal hostname/header as native.
        headers.update({'Host': 'app.quillmd.com', 'X-Forwarded-Proto': 'https', 'X-QuillMD-Account': '1', 'X-Real-IP': '127.0.0.1', 'Connection': 'close'})
        upstream = http.client.HTTPConnection('127.0.0.1', 19430, timeout=30)
        try:
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            payload = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in {'connection', 'transfer-encoding', 'content-length'}:
                    self.send_header(key, value)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Connection', 'close')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(payload)
        finally:
            upstream.close()

    do_GET = handle_request
    do_POST = handle_request
    do_HEAD = handle_request


if __name__ == '__main__':
    for path in (CERT, KEY):
        info = path.stat()
        assert stat.S_ISREG(info.st_mode) and info.st_size < 128 * 1024
    assert KEY.stat().st_mode & 0o007 == 0
    certificate = ssl.PEM_cert_to_DER_cert(re.search(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', CERT.read_text(), re.S).group(0))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(CERT, KEY)
    server = ThreadingHTTPServer(('127.0.0.1', 19443), Proxy)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(json.dumps({'listen': '127.0.0.1:19443', 'upstream': '127.0.0.1:19430',
                      'certificate_sha256': hashlib.sha256(certificate).hexdigest(),
                      'only_exact_certificate_files_mounted': True}), flush=True)
    server.serve_forever()
