"""Signed instruction intents outside the clinical backup; no external-copy deletion.

Independent checkpoint signatures prove the admitted prefix. Filesystem location
alone proves neither independence nor freshness. Restore never grants admission.
"""
import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from pydantic import Field

from . import disposition_policy as p

MAX_JOURNAL_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 1000


class Instruction(p.Strict):
    id: str
    department_id: str
    target_id: str
    snapshot_sha256: p.Hash
    source_created_at: str
    policy: dict
    policy_admitted_at: str
    created_by: str
    created_at: str
    approved_by: str
    approved_at: str


class Entry(p.Strict):
    contract: Literal['disposition-journal-entry-v1']
    namespace: str
    sequence: Annotated[int, Field(ge=1, le=MAX_ENTRIES)]
    previous_sha256: p.Hash
    written_at: str
    instruction: Instruction


def namespace():
    return p.identity(getattr(settings, 'DISPOSITION_NAMESPACE', ''))


def validate_entry(envelope, number, previous):
    body = p.verify(envelope, Entry, getattr(settings, 'DISPOSITION_JOURNAL_KEYS', {}))
    if body.namespace != namespace() or body.sequence != number or body.previous_sha256 != previous:
        raise ValidationError('The disposition journal chain is incomplete or belongs to another namespace.')
    i = body.instruction
    for value in (i.id, i.department_id, i.target_id, i.created_by, i.approved_by): p.identity(value)
    written = p.timestamp(body.written_at)
    policy = p.verify_policy(i.policy, getattr(settings, 'DISPOSITION_AUTHORITY_KEYS', {}), namespace=namespace(), now=written)
    admitted, created, approved = map(p.timestamp, (i.policy_admitted_at, i.created_at, i.approved_at))
    source = p.timestamp(i.source_created_at)
    if (i.created_by == i.approved_by or i.department_id != policy.department_id
            or not admitted <= p.timestamp(policy.not_before) <= source <= created <= approved <= written
            or (written - source).total_seconds() < policy.minimum_age_seconds):
        raise ValidationError('The journal instruction lacks prospective scope or distinct exact review.')
    return body


def read_locked(file):
    file.seek(0); raw = file.read(MAX_JOURNAL_BYTES + 1)
    if len(raw) > MAX_JOURNAL_BYTES or (raw and not raw.endswith(b'\n')):
        raise ValidationError('The complete disposition journal is unavailable.')
    entries = []; previous = p.ZERO; ids = set(); targets = set()
    for line in raw.splitlines():
        if len(entries) >= MAX_ENTRIES: raise ValidationError('The complete disposition journal exceeds its bound.')
        envelope = p.decode(line); body = validate_entry(envelope, len(entries) + 1, previous)
        if body.instruction.id in ids or body.instruction.target_id in targets:
            raise ValidationError('The disposition journal contains conflicting instructions.')
        ids.add(body.instruction.id); targets.add(body.instruction.target_id)
        previous = p.digest(envelope); entries.append(envelope)
    return entries, previous


@contextmanager
def journal_file(*, create=False, write=False):
    configured = getattr(settings, 'DISPOSITION_JOURNAL_PATH', '')
    if not configured: raise ValidationError('An independently configured disposition journal is required.')
    path = Path(configured)
    if not path.is_absolute() or any(path.resolve().is_relative_to(Path(root).resolve())
                                   for root in (settings.STATE_DIR, settings.MEDIA_ROOT)):
        raise ValidationError('The instruction journal must be outside the selected clinical state root.')
    flags = (os.O_RDWR if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_CLOEXEC | (os.O_CREAT if create else 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, 'r+b' if write else 'rb', buffering=0) as file:
            meta = os.fstat(file.fileno())
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_mode & 0o077:
                raise ValidationError('The instruction journal is not a private regular file.')
            fcntl.flock(file, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            yield file
    except OSError:
        raise ValidationError('The independent instruction journal is unavailable.') from None


def checkpoint(envelope):
    return p.verify_checkpoint(envelope, getattr(settings, 'DISPOSITION_CHECKPOINT_KEYS', {}),
                               namespace=namespace(), now=timezone.now())


def verified(checkpoint_envelope=None):
    with journal_file() as file:
        entries, head = read_locked(file)
        if checkpoint_envelope is not None:
            proof = checkpoint(checkpoint_envelope)
            if (proof.sequence, proof.head_sha256) != (len(entries), head):
                raise ValidationError('The independent checkpoint does not identify the complete journal head.')
        return entries


def initialize(checkpoint_envelope):
    """Only an independently signed exact genesis/current head creates the file."""
    proof = checkpoint(checkpoint_envelope)
    with journal_file(create=True, write=True) as file:
        entries, head = read_locked(file)
        if (proof.sequence, proof.head_sha256) != (len(entries), head):
            raise ValidationError('The independent checkpoint does not identify this journal.')
        os.fsync(file.fileno())
    return {'sequence': len(entries), 'head_sha256': head}


def append(instruction, checkpoint_envelope):
    """Persist before any target deletion; an identical interrupted intent retries.

    A retry may use the immediately preceding checkpoint only for the exact last
    instruction already signed and fsynced. A new instruction needs the head's
    independently signed checkpoint, never a locally invented freshness claim.
    """
    proof = checkpoint(checkpoint_envelope)
    with journal_file(create=True, write=True) as file:
        entries, head = read_locked(file)
        if entries and entries[-1]['body']['instruction']['id'] == instruction['id']:
            old = entries[-1]
            if old['body']['instruction'] != instruction:
                raise ValidationError('The durable instruction identity already has another body.')
            if (proof.sequence, proof.head_sha256) not in (
                    (len(entries), head), (len(entries) - 1, old['body']['previous_sha256'])):
                raise ValidationError('The interrupted instruction checkpoint does not match.')
            os.fsync(file.fileno())
            return old
        if (proof.sequence, proof.head_sha256) != (len(entries), head):
            raise ValidationError('A current independent checkpoint is required before a new instruction.')
        if any(e['body']['instruction']['id'] == instruction['id'] or
               e['body']['instruction']['target_id'] == instruction['target_id'] for e in entries):
            raise ValidationError('That target already has a durable instruction.')
        body = {'contract': 'disposition-journal-entry-v1', 'namespace': namespace(),
                'sequence': len(entries) + 1, 'previous_sha256': head,
                'written_at': timezone.now().isoformat(), 'instruction': instruction}
        try:
            secret = getattr(settings, 'DISPOSITION_JOURNAL_PRIVATE_KEY', '')
            key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(secret))
            envelope = {'key_id': settings.DISPOSITION_JOURNAL_KEY_ID, 'body': body,
                        'signature': key.sign(p.signed_bytes(body)).hex()}
        except (ValueError, TypeError, AttributeError):
            raise ValidationError('The disposition journal signer is unavailable.') from None
        validate_entry(envelope, len(entries) + 1, head)
        encoded = p.canonical(envelope) + b'\n'
        file.seek(0, os.SEEK_END)
        if file.tell() + len(encoded) > MAX_JOURNAL_BYTES:
            raise ValidationError('The complete disposition journal exceeds its bound.')
        # A partial append or unknown fsync outcome refuses subsequent use. It is
        # never truncated or repaired by this adapter; operator recovery keeps it.
        if file.write(encoded) != len(encoded): raise ValidationError('The journal append outcome is unresolved.')
        os.fsync(file.fileno())
        directory = os.open(Path(settings.DISPOSITION_JOURNAL_PATH).parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
        return envelope


def pending_targets():
    """A durable intent still denies access after a database rollback/crash."""
    if not getattr(settings, 'DISPOSITION_JOURNAL_PATH', ''): return []
    return [e['body']['instruction']['target_id'] for e in verified()]
