"""Trusted parent for the isolated blank-form inventory and candidate writer."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from .service import DocumentError, MAX_UPLOAD, TIMEOUT_SECONDS

def read_original(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= MAX_UPLOAD:
            raise DocumentError('Choose a regular blank DOCX up to 10 MiB.', 'upload_limit')
        data = stream.read(MAX_UPLOAD+1)
        after = os.fstat(stream.fileno())
    identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_uid, s.st_gid,
                           s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if identity(before) != identity(after) or len(data) != before.st_size or not data.startswith(b'PK\x03\x04'):
        raise DocumentError('The original changed or is not a DOCX.', 'source_changed')
    return data

def run(path, request, output=None):
    data = read_original(path)
    raw = json.dumps(request, ensure_ascii=False).encode()
    if len(raw) > 2*1024*1024:
        raise DocumentError('Split this form: its inventory exceeds the processing limit.', 'preparation_limit')
    with tempfile.TemporaryDirectory(prefix='quillmd-preparation-') as directory:
        workspace = Path(directory)
        (workspace/'input.docx').write_bytes(data)
        (workspace/'request.json').write_bytes(raw)
        try:
            result = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).with_name('preparation_worker.py')),
                                     str(workspace)], cwd=workspace,
                                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC'},
                                    capture_output=True, timeout=TIMEOUT_SECONDS, start_new_session=True)
        except subprocess.TimeoutExpired:
            raise DocumentError('Preparation parsing exceeded its time limit.', 'parser_timeout') from None
        if result.returncode or len(result.stdout) > 2*1024*1024:
            raise DocumentError('The isolated preparation processor failed.', 'parser_failed')
        try:
            response = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise DocumentError('The isolated preparation response is invalid.', 'parser_failed') from None
        if 'error' in response:
            raise DocumentError(response['error'], response['code'])
        if output is not None:
            prepared = read_original(workspace/'output.docx')
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(prepared); stream.flush(); os.fsync(stream.fileno())
            response['prepared_sha256'] = hashlib.sha256(prepared).hexdigest()
        return response

def inspect_preparation(path, known=None, *, protocol=None, signing_context=None, question_context=None):
    request = {'operation': 'inventory', 'known': known}
    if protocol is not None:
        request['protocol'] = protocol
    if signing_context is not None:
        request['signing_context'] = signing_context
    if question_context is not None:
        from .question_context import validate_context
        validate_context(question_context)
        request['question_context'] = question_context
    return run(path, request)

def prepare_candidate(path, inventory, selected, output,placements=None):
    return run(path, {'operation': 'candidate', 'inventory': inventory, 'selected': selected,'placements':placements}, output)
