"""Local layout-service protocol. Web/worker processes never receive Docker access."""
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct

MAX_FRAME = 48 * 1024 * 1024
#: ⚠️ TWO CALLERS ASK THE VERIFIER, AND ONLY ONE OF THEM KNOWS WHAT ITS ABSENCE COSTS. Said in one place each:
#: - EXPORT (a mapping and answers: documents.service after `word_v3.fill` or `effective_values` refused for want of it).
#:   That gate fires on the original's proposal-mode tab-column candidates for ANY non-empty answer set — one answer in an
#:   unrelated text field included — so without the verifier no answer on this form can be exported, only the unchanged
#:   form. The previous wording read as if the other answers could be; D10 was generated, held and charged, and refused
#:   only at finalization.
#: - INSPECTION (no mapping: documents.service when the inspection counts a tab-column candidate, at upload and at every
#:   fresh inspection). It does NOT know that: fill's reader can withdraw what the inspection counted (a complete question
#:   or section past the mapping limit, refutation FV:F1), and such a form exports without any verifier. So the note
#:   stored at upload keeps the base wording, which claims nothing about the other answers. Whether generation is
#:   refused is fill's own answer, asked at admission (core.v3_mapping.admission_refusals).
LAYOUT_UNAVAILABLE = ('This form has tab-column answers that only the isolated layout verifier can check, and it is not '
                      'available here. Until it is, no answer on this form can be exported; the unchanged form can '
                      'still be downloaded.')
LAYOUT_NEEDED = 'This form needs the isolated layout verifier before its tab-column answers can be used.'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def receive(stream):
    def exact(size):
        chunks = []; remaining = size
        while remaining:
            chunk = stream.recv(min(remaining, 65536))
            if not chunk: raise ValueError('Incomplete layout response')
            chunks.append(chunk); remaining -= len(chunk)
        return b''.join(chunks)
    length = struct.unpack('!I', exact(4))[0]
    if not 0 < length <= MAX_FRAME: raise ValueError('Layout message exceeds its limit')
    return json.loads(exact(length))


def send(stream, value):
    payload = canonical(value)
    if not 0 < len(payload) <= MAX_FRAME: raise ValueError('Layout message exceeds its limit')
    stream.sendall(struct.pack('!I', len(payload)) + payload)


def verify_document(data, mapping=None, answers=None):
    from .service import DocumentError
    try:
        from django.conf import settings
        endpoint = getattr(settings, 'QUILLMD_LAYOUT_SOCKET', '')
        expected_uid = getattr(settings, 'QUILLMD_LAYOUT_SERVICE_UID', None)
    except Exception:
        endpoint = os.getenv('QUILLMD_LAYOUT_SOCKET', '')
        expected_uid = os.getenv('QUILLMD_LAYOUT_SERVICE_UID', '')
    if not endpoint or expected_uid in (None, ''):
        raise DocumentError(LAYOUT_NEEDED if mapping is None else LAYOUT_UNAVAILABLE, 'layout_unavailable')
    try:
        path = Path(endpoint)
        meta = path.lstat()
        if not path.is_absolute() or not stat.S_ISSOCK(meta.st_mode) or meta.st_uid != int(expected_uid):
            raise ValueError('Untrusted layout endpoint')
        request = {'source': base64.b64encode(data).decode(), 'mapping': mapping, 'answers': answers}
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(100)
            stream.connect(str(path))
            _, peer_uid, _ = struct.unpack('3i', stream.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if peer_uid != int(expected_uid): raise ValueError('Untrusted layout peer')
            send(stream, request); response = receive(stream)
        if not isinstance(response, dict) or not response.get('verified'):
            raise DocumentError('The rendered form does not establish these tab-column answer destinations. Review the original.',
                                'layout_unresolved')
        receipt = response['receipt']
        if receipt['source_sha256'] != hashlib.sha256(data).hexdigest(): raise ValueError('Wrong source receipt')
        for name, value in [('mapping', mapping), ('answers', answers)]:
            expected = hashlib.sha256(canonical(value)).hexdigest() if value is not None else ''
            if receipt[name + '_sha256'] != expected: raise ValueError('Wrong request receipt')
        output = base64.b64decode(response['document'], validate=True)
        if not 0 < len(output) <= 30 * 1024 * 1024 or hashlib.sha256(output).hexdigest() != receipt['document_sha256']:
            raise ValueError('Wrong output receipt')
        if mapping is None and output != data: raise ValueError('Inspection changed original')
        return response, output
    except DocumentError:
        raise
    except Exception:
        raise DocumentError('The isolated layout verifier is unavailable or returned incomplete evidence.',
                            'layout_unavailable') from None
