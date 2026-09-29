"""Operator-run local renderer boundary; no application DB or provider configuration.

Only this separate service needs access to the container runtime. Its client accepts
no caller paths, renderer options, source coordinates, receipt or success boolean.
"""
import argparse
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layout_transport import canonical, receive, send

IMAGE = 'sha256:4bd4489d15b7326143e5575c789d93f675f77d85dc857900dd28ae1591d55a4b'
ROOT = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def worker(workspace, name):
    result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / name), str(workspace)],
        cwd=workspace, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC'},
        capture_output=True, timeout=20, start_new_session=True)
    if result.returncode or len(result.stdout) > 3 * 1024 * 1024: raise ValueError('Isolated worker failed')
    value = json.loads(result.stdout)
    if 'error' in value: raise ValueError('Isolated worker refused')
    return value


def render(workspace):
    output = workspace / 'rendered'; output.mkdir(mode=0o700)
    name = 'quillmd-layout-' + uuid.uuid4().hex
    # Fixed script and fixed file names. No DOCX text, paths or options enter shell code.
    script = ('fc-list -f "%{file}\\n" | sort -u | while IFS= read -r font; do sha256sum "$font"; done > /out/fonts.sha256; '
              'fc-list -f "%{family}\\n" | sort -u > /out/font-families.txt; '
              'while IFS= read -r font; do printf "%s\\t" "$font"; '
              'fc-match -f "%{family}|%{style}|%{file}\\n" -- "$font"; done '
              '< /in/requested-fonts.txt > /out/font-resolution.txt; '
              'exec timeout --kill-after=5 50 soffice -env:UserInstallation=file:///tmp/layout-profile --headless --norestore '
              '--convert-to \'pdf:writer_pdf_Export:{"ExportBookmarksToPDFDestination":{"type":"boolean","value":"true"}}\' '
              '--outdir /out /in/document.docx /in/instrumented.docx')
    command = ['docker', 'run', '--rm', '--name', name, '--pull', 'never', '--network', 'none', '--read-only',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=256m', '--user', str(os.getuid()), '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--pids-limit', '128', '--memory', '1g', '--cpus', '1',
        '-v', str(workspace) + ':/in:ro', '-v', str(output) + ':/out', '--entrypoint', '/bin/sh', IMAGE, '-c', script]
    try:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
                                env={'PATH': '/usr/bin:/bin'}, start_new_session=True)
        if result.returncode: raise ValueError('Renderer failed')
    finally:
        # Stop the named container even if the Docker client times out or is interrupted.
        subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=10, env={'PATH': '/usr/bin:/bin'})
    for name in ('document.pdf', 'instrumented.pdf', 'fonts.sha256', 'font-families.txt', 'font-resolution.txt'):
        file = output / name
        if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= 30 * 1024 * 1024:
            raise ValueError('Incomplete bounded renderer output')
    return output


def retain_verified(fields, warnings, manifest, proof, receipt):
    """Publish only measured destinations. An individually held optional proposal is removed and
    reported with its complete printed source; it is never silently dropped or verified."""
    candidates = {c['id']: c for c in manifest['candidates']}
    held = [item.get('candidate') if isinstance(item, dict) else None for item in proof.get('held', [])]
    if len(set(held)) != len(held) or any(identity not in candidates or candidates[identity].get('optional') is not True
                                         or candidates[identity].get('untouched') is not True for identity in held):
        raise ValueError('Unexpected held layout candidate')
    notes = list(warnings)
    for identity in held:
        source = candidates[identity]['source']
        notes.append('Layout verification held the coded-column answer at ' + source['row']['part'] + '#'
                     + source['row']['slot'] + ': the rendered form does not establish its printed columns. '
                     'Printed question: ' + source['label'] + '. Section: ' + source['context'])
    kept = []
    for field in fields:
        identity = field.get('layout_candidate')
        if identity in held:
            continue
        if identity:
            field['layout_verified'] = receipt(identity)
        kept.append(field)
    return kept, notes


def qualify(request, evidence_root):
    if not isinstance(request, dict) or set(request) - {'readings'} != {'source', 'mapping', 'answers'}:
        raise ValueError('Invalid layout request')
    readings = request.get('readings')
    if readings is not None and not isinstance(readings, dict):
        raise ValueError('Invalid layout request')
    data = base64.b64decode(request['source'], validate=True)
    if not 0 < len(data) <= 10 * 1024 * 1024 or not data.startswith(b'PK\x03\x04'):
        raise ValueError('Invalid layout original')
    mapping, answers = request['mapping'], request['answers']
    if (mapping is None) != (answers is None): raise ValueError('Incomplete export request')
    if len(canonical({'mapping': mapping, 'answers': answers})) > 2 * 1024 * 1024:
        raise ValueError('Oversized mapping request')
    # Unique private directory is retained for audit, including all refused renders.
    workspace = Path(tempfile.mkdtemp(prefix='layout-', dir=evidence_root))
    (workspace / 'input.docx').write_bytes(data)
    (workspace / 'request.json').write_bytes(canonical({'operation': 'layout_prepare', 'format': 'docx',
        'engine': 'v3', 'mapping': mapping, 'answers': answers, 'readings': readings}))
    try:
        prepared = worker(workspace, 'worker.py')
        manifest = prepared['manifest']
        (workspace / 'manifest.json').write_bytes(canonical(manifest))
        (workspace / 'requested-fonts.txt').write_text('\n'.join(manifest['requested_fonts'] or ['sans-serif']) + '\n')
        rendered = render(workspace)
        for name in ('document.pdf', 'instrumented.pdf'):
            (workspace / name).write_bytes((rendered / name).read_bytes())
        proof = worker(workspace, 'layout_pdf_worker.py')
        (workspace / 'proof.json').write_bytes(canonical(proof))
        profile = {'renderer_image': IMAGE, 'font_files_sha256': digest((rendered / 'fonts.sha256').read_bytes()),
            'font_families_sha256': digest((rendered / 'font-families.txt').read_bytes()),
            'pdf_parser_version': importlib.metadata.version('pypdf'),
            'font_parser_version': importlib.metadata.version('reportlab'),
            'verifier_sha256': digest((ROOT / 'layout_pdf_worker.py').read_bytes()),
            'geometry_sha256': digest((ROOT / 'layout_geometry.py').read_bytes()),
            'ownership_contract': manifest['contract'],
            'qualification': 'Pinned LibreOffice profile only; native Microsoft Word not qualified'}
        profile_sha = digest(canonical(profile))
        if mapping is not None:
            for candidate in manifest['candidates']:
                field = next((f for f in mapping if f.get('locator') == candidate['source']['row']), None)
                if field is None: continue  # A constraint reader may supply a field subset.
                existing = field.get('layout_verified')
                if not isinstance(existing, dict) or existing != {'source_sha256': digest(data),
                        'candidate': candidate['id'], 'profile_sha256': profile_sha}:
                    raise ValueError('Missing, changed or stale source/profile receipt')
        if not proof.get('passed'): raise ValueError('Rendered tab ownership unresolved')
        document = (workspace / 'document.docx').read_bytes()
        receipt = {'contract': manifest['contract'], 'source_sha256': digest(data), 'document_sha256': digest(document),
            'mapping_sha256': digest(canonical(mapping)) if mapping is not None else '',
            'answers_sha256': digest(canonical(answers)) if answers is not None else '',
            **({'readings_sha256': digest(canonical(readings))} if readings is not None else {}),
            'manifest_sha256': digest(canonical(manifest)), 'proof_sha256': digest(canonical(proof)),
            'profile': profile, 'profile_sha256': profile_sha,
            'requested_fonts': manifest['requested_fonts'],
            'font_resolution_sha256': digest((rendered / 'font-resolution.txt').read_bytes()),
            'source_preparer_sha256': digest((ROOT / 'layout_source.py').read_bytes()),
            'word_engine_sha256': digest((ROOT / 'word_v3.py').read_bytes())}
        fields, warnings = retain_verified(prepared['fields'], prepared['warnings'], manifest, proof,
            lambda identity: {'source_sha256': digest(data), 'candidate': identity, 'profile_sha256': profile_sha})
        response = {'verified': True, 'receipt': receipt, 'fields': fields, 'warnings': warnings,
                    'states': prepared['states'],
                    'document': base64.b64encode(document).decode()}
        (workspace / 'receipt.json').write_bytes(canonical(receipt))
        return response
    except Exception as exc:
        (workspace / 'refusal.json').write_bytes(canonical({'verified': False, 'failure_class': type(exc).__name__}))
        raise


def serve(endpoint, client_uid, evidence_root):
    if not endpoint.is_absolute() or endpoint.exists() or endpoint.is_symlink():
        raise ValueError('Use a new absolute socket path')
    evidence_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(endpoint)); endpoint.chmod(0o666); server.listen(2)
        try:
            while True:
                stream, _ = server.accept()
                with stream:
                    stream.settimeout(100)
                    _, uid, _ = struct.unpack('3i', stream.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != client_uid: continue
                    try: send(stream, qualify(receive(stream), evidence_root))
                    except Exception:
                        try: send(stream, {'verified': False})
                        except OSError: pass
        finally:
            endpoint.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, required=True)
    parser.add_argument('--client-uid', type=int, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    serve(args.socket, args.client_uid, args.evidence)
