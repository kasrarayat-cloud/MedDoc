#!/usr/bin/env python3
"""Exercise GET-only recovery with retained bytes. Never contacts a provider."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.corti_agent_recovery import recover_existing_task


def _no_network(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto'}:
        raise RuntimeError('Network is disabled for this offline replay.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.addaudithook(_no_network)
    os.umask(0o077)
    source, output = args.evidence_dir.resolve(), args.output.absolute()
    if output.resolve() != output or output.is_relative_to(source):
        raise ValueError('Write a new private result outside the retained evidence directory.')
    hashes = lambda: {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in source.rglob('*') if p.is_file()}
    before = hashes()
    read = lambda name: json.loads((source / name).read_text())
    manifest = read('sha256-manifest-final.json')
    if any(before.get(name) != digest for name, digest in manifest.items()):
        raise ValueError('Retained evidence hash mismatch.')
    original = read('transport.json')
    accepted = read('003-submit-task.raw.json')
    recorded = read('observation-recovery/001-existing-task.raw.json')
    old_recovery = read('observation-recovery/transport.json')
    saved_get = old_recovery['http_requests'][0]
    assert original['failure_reason'] == 'unexpected_identifier_shape'
    assert saved_get['method'] == 'GET' and saved_get['label'] == 'existing-task'
    expected_path = '/v2/agentic' + saved_get['path']

    class RecordedTaskReader:
        status_code = 200

        def __init__(self):
            self.calls = []

        def get(self, path, *, allow_redirects):
            if path != expected_path or allow_redirects is not False or self.calls:
                raise AssertionError('Only the one recorded task GET is permitted.')
            self.calls.append({'method': 'GET', 'path': path, 'network_executed': False})
            return self

        def json(self):
            return recorded

    reader = RecordedTaskReader()
    recovered = recover_existing_task(accepted, agent_id=original['agent_id'], reader=reader)
    assert recovered.raw_response == recorded
    assert recovered.identity.task_id == accepted['task']['id']
    assert recovered.identity.context_id == accepted['task']['contextId']
    assert len(reader.calls) == 1
    assert before == hashes()
    result = {
        'mode': 'offline_saved_response_only', 'passed': True,
        'historical_parser_failure': original['failure_reason'],
        'context_id_preserved': recovered.identity.context_id,
        'task_id_preserved': recovered.identity.task_id, 'state': recovered.state,
        'simulated_reads': reader.calls, 'provider_calls': 0, 'task_submissions': 0,
        'original_evidence_unchanged': True,
        'source_sha256': {name: before[name] for name in (
            '003-submit-task.raw.json', 'transport.json', 'run-agent-once.py',
            'observation-recovery/001-existing-task.raw.json')},
    }
    with output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'passed': True, 'provider_calls': 0, 'task_submissions': 0,
                      'simulated_gets': 1, 'result': str(output)}))


if __name__ == '__main__':
    main()
