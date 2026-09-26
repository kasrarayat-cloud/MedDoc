#!/usr/bin/env python3
"""A loopback stand-in for the provider's Messages endpoint, for validating the campaign runner offline ONLY.

It binds 127.0.0.1, answers POST /v1/messages from a script of behaviours consumed one per request, and logs every
request it receives (never a header value). Responses are the frozen benchmark's retained careful responses, so the
product's validator judges exactly what it judges in replay tests. It is never a provider and never sees a key: the
runner refuses offline mode unless the key is the fixed offline marker and the base URL is loopback.

    python ops/wm_narrative_mock_provider.py --port P --script S.json --log L.jsonl

Behaviours: {"kind": "replay", "case": ID} | {"kind": "status", "code": 429|500|529|400|401|404}
            | {"kind": "hang", "seconds": N} | {"kind": "drop"} | {"kind": "truncated", "case": ID}
            | {"kind": "overcost", "case": ID} | {"kind": "model", "case": ID, "model": M}
            | {"kind": "text", "case": ID, "append": S}   (a replay whose text carries S — the leak-scan check)
A request beyond the script is answered 500 and logged as `unscripted`.
"""
import argparse
import hashlib
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BENCHMARKS = Path(__file__).resolve().parents[1] / 'core' / 'tests' / 'benchmarks' / 'wm_narrative'
ERRORS = {400: 'invalid_request_error', 401: 'authentication_error', 404: 'not_found_error', 429: 'rate_limit_error',
          500: 'api_error', 529: 'overloaded_error'}


def careful():
    cases = {}
    for name in ('responses-careful.json', 'heldout-responses-careful.json'):
        cases.update(json.loads((BENCHMARKS / name).read_text(encoding='utf-8'))['cases'])
    return cases


class State:
    def __init__(self, script, log):
        self.script, self.log, self.lock, self.count = list(script), Path(log), threading.Lock(), 0
        self.responses = careful()

    def next(self):
        with self.lock:
            self.count += 1
            return self.count, (self.script.pop(0) if self.script else {'kind': 'unscripted'})

    def record(self, entry):
        with self.lock, self.log.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(entry, sort_keys=True) + '\n')


def handler_for(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('content-length', '0') or 0))
            number, behaviour = state.next()
            try:
                request = json.loads(body)
            except ValueError:
                request = {}
            state.record({'number': number, 'at': time.time(), 'path': self.path, 'behaviour': behaviour['kind'],
                          'model': request.get('model'), 'max_tokens': request.get('max_tokens'),
                          'body_sha256': hashlib.sha256(body).hexdigest(), 'body_bytes': len(body),
                          'has_output_config': 'output_config' in request,
                          'credential_is_offline_marker': self.headers.get('x-api-key') == 'offline-mock-provider-no-credential'})
            kind = behaviour['kind']
            if self.path != '/v1/messages' or kind in ('unscripted', 'status'):
                code = behaviour.get('code', 500) if kind == 'status' else 500
                return self.reply(code, {'type': 'error', 'error': {'type': ERRORS.get(code, 'api_error'),
                                                                    'message': f'mock {kind} {code}'}})
            if kind == 'hang':
                time.sleep(behaviour['seconds'])
                return self.reply(500, {'type': 'error', 'error': {'type': 'api_error', 'message': 'mock hang ended'}})
            if kind == 'drop':
                self.close_connection = True
                self.connection.shutdown(2)
                return None
            text = json.dumps(state.responses[behaviour['case']])
            if kind == 'text':
                text = text[:-1] + ', "_note": ' + json.dumps(behaviour['append']) + '}'
            output_tokens = len(text) // 3 + 1
            if kind == 'overcost':
                output_tokens = 20000          # above max_tokens: the settled cost exceeds the quoted maximum
            return self.reply(200, {
                'id': f'msg_offline_{number:04d}', 'type': 'message', 'role': 'assistant',
                'model': behaviour.get('model', request.get('model')),
                'content': [{'type': 'text', 'text': text}],
                'stop_reason': 'max_tokens' if kind == 'truncated' else 'end_turn', 'stop_sequence': None,
                'usage': {'input_tokens': len(body) // 4 + 1, 'output_tokens': output_tokens,
                          'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0}},
                request_id=f'req_offline_{number:04d}')

        def reply(self, code, document, request_id='req_offline_error'):
            data = json.dumps(document).encode()
            self.send_response(code)
            self.send_header('content-type', 'application/json')
            self.send_header('request-id', request_id)
            self.send_header('content-length', str(len(data)))
            if code == 429:
                self.send_header('retry-after', '0')
            self.end_headers()
            self.wfile.write(data)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--script', required=True)
    parser.add_argument('--log', required=True)
    args = parser.parse_args()
    state = State(json.loads(Path(args.script).read_text()), args.log)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(state))
    server.daemon_threads = True
    print(f'mock provider on 127.0.0.1:{args.port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    sys.exit(main())
