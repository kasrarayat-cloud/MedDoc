"""Signed instruction intents outside the clinical backup; no external-copy deletion.

Independent checkpoint signatures prove the admitted prefix. Filesystem location
alone proves neither independence nor freshness. Restore never grants admission.

One chain carries three signed entry kinds: disposition instructions, preservation
holds and hold releases. A hold or release is appended and fsynced before its
database row commits, so a restore older than it can be told what it lacks. A
release is valid only after its own hold, never by the hold's own custodian.
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


INSTRUCTION = 'disposition-journal-entry-v1'
HOLD = 'retention-hold-entry-v1'
RELEASE = 'retention-release-entry-v1'
KINDS = {INSTRUCTION: 'instruction', HOLD: 'hold', RELEASE: 'release'}


class Hold(p.Strict):
    """A preservation hold's identity: scope and target ids and an authority hash, never clinical prose."""
    id: str
    scope: Literal['global', 'organization', 'department', 'patient', 'encounter']
    target_id: str | None
    authority_sha256: p.Hash
    request_key: str
    created_by: str


class Release(p.Strict):
    id: str
    hold_id: str
    authority_sha256: p.Hash
    created_by: str


class HoldEntry(p.Strict):
    contract: Literal['retention-hold-entry-v1']
    namespace: str
    sequence: Annotated[int, Field(ge=1, le=MAX_ENTRIES)]
    previous_sha256: p.Hash
    written_at: str
    hold: Hold


class ReleaseEntry(p.Strict):
    contract: Literal['retention-release-entry-v1']
    namespace: str
    sequence: Annotated[int, Field(ge=1, le=MAX_ENTRIES)]
    previous_sha256: p.Hash
    written_at: str
    release: Release


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


def contract_of(envelope):
    body = envelope.get('body') if isinstance(envelope, dict) else None
    return body.get('contract') if isinstance(body, dict) else None


def kind(envelope):
    """'instruction', 'hold' or 'release' for an entry read_locked already verified."""
    return KINDS[contract_of(envelope)]


def validate_retention_entry(envelope, number, previous):
    """A signed hold or release entry at this exact chain position. Chain-wide rules are read_locked's."""
    schema = {HOLD: HoldEntry, RELEASE: ReleaseEntry}.get(contract_of(envelope))
    if schema is None: raise ValidationError('The journal entry kind is unknown.')
    body = p.verify(envelope, schema, getattr(settings, 'DISPOSITION_JOURNAL_KEYS', {}))
    if body.namespace != namespace() or body.sequence != number or body.previous_sha256 != previous:
        raise ValidationError('The disposition journal chain is incomplete or belongs to another namespace.')
    p.timestamp(body.written_at)
    if schema is HoldEntry:
        h = body.hold
        for value in (h.id, h.request_key, h.created_by): p.identity(value)
        if (h.scope == 'global') != (h.target_id is None):
            raise ValidationError('A journaled hold names a target exactly when its scope is not global.')
        if h.target_id is not None: p.identity(h.target_id)
    else:
        for value in (body.release.id, body.release.hold_id, body.release.created_by): p.identity(value)
    return body


def validate_any(envelope, number, previous):
    if contract_of(envelope) == INSTRUCTION: return validate_entry(envelope, number, previous)
    return validate_retention_entry(envelope, number, previous)


def read_locked(file):
    file.seek(0); raw = file.read(MAX_JOURNAL_BYTES + 1)
    if len(raw) > MAX_JOURNAL_BYTES or (raw and not raw.endswith(b'\n')):
        raise ValidationError('The complete disposition journal is unavailable.')
    entries = []; previous = p.ZERO; ids = set(); targets = set()
    holds = {}; keys = set(); released = set(); releases = set()
    for line in raw.splitlines():
        if len(entries) >= MAX_ENTRIES: raise ValidationError('The complete disposition journal exceeds its bound.')
        envelope = p.decode(line); body = validate_any(envelope, len(entries) + 1, previous)
        if isinstance(body, Entry):
            if body.instruction.id in ids or body.instruction.target_id in targets:
                raise ValidationError('The disposition journal contains conflicting instructions.')
            ids.add(body.instruction.id); targets.add(body.instruction.target_id)
        elif isinstance(body, HoldEntry):
            if body.hold.id in holds or body.hold.request_key in keys:
                raise ValidationError('The disposition journal contains conflicting preservation holds.')
            holds[body.hold.id] = body.hold; keys.add(body.hold.request_key)
        else:
            # A release is valid only after its own hold, once, and by a second custodian.
            hold = holds.get(body.release.hold_id)
            if (hold is None or body.release.hold_id in released or body.release.id in releases
                    or body.release.created_by == hold.created_by):
                raise ValidationError('The disposition journal contains a release without its earlier hold.')
            released.add(body.release.hold_id); releases.add(body.release.id)
        previous = p.digest(envelope); entries.append(envelope)
    return entries, previous


def instruction_entries(entries):
    return [e for e in entries if kind(e) == 'instruction']


def retention_records(entries):
    """Journaled holds in chain order, each with its release or None; `entries` come from read_locked."""
    records = {}
    for envelope in entries:
        if kind(envelope) == 'hold':
            hold = envelope['body']['hold']
            records[hold['id']] = {'hold': hold, 'hold_entry': envelope, 'release': None, 'release_entry': None}
        elif kind(envelope) == 'release':
            release = envelope['body']['release']
            records[release['hold_id']].update(release=release, release_entry=envelope)
    return records


def journaled_holds():
    """Every journaled hold, released or not; empty when no journal is configured. A configured but unreadable or
    unverifiable journal raises: it is never an empty answer."""
    if not getattr(settings, 'DISPOSITION_JOURNAL_PATH', ''): return {}
    return retention_records(verified())


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
        if entries and kind(entries[-1]) == 'instruction' and entries[-1]['body']['instruction']['id'] == instruction['id']:
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
               e['body']['instruction']['target_id'] == instruction['target_id'] for e in instruction_entries(entries)):
            raise ValidationError('That target already has a durable instruction.')
        body = {'contract': INSTRUCTION, 'namespace': namespace(),
                'sequence': len(entries) + 1, 'previous_sha256': head,
                'written_at': timezone.now().isoformat(), 'instruction': instruction}
        envelope = _sign(body)
        validate_entry(envelope, len(entries) + 1, head)
        _write(file, envelope)
        return envelope


def _sign(body):
    try:
        secret = getattr(settings, 'DISPOSITION_JOURNAL_PRIVATE_KEY', '')
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(secret))
        return {'key_id': settings.DISPOSITION_JOURNAL_KEY_ID, 'body': body,
                'signature': key.sign(p.signed_bytes(body)).hex()}
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('The disposition journal signer is unavailable.') from None


def _write(file, envelope):
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


def _append_retention(file, entries, head, contract, field, record):
    body = {'contract': contract, 'namespace': namespace(), 'sequence': len(entries) + 1, 'previous_sha256': head,
            'written_at': timezone.now().isoformat(), field: record}
    envelope = _sign(body)
    validate_retention_entry(envelope, len(entries) + 1, head)
    _write(file, envelope)
    return envelope


def append_hold(hold):
    """Journal a preservation hold and fsync it BEFORE its database row commits.

    No checkpoint is required: a hold only adds preservation, and it must not wait for an external signer. The chain it
    extends is still read and verified completely, and admission later proves that chain against a fresh independent
    checkpoint. The journal is never created here; a configured but missing or unverifiable journal refuses the hold,
    which is then recorded nowhere. A retry with the same request key returns the journaled entry (its id included)
    and appends nothing; the same key with any other scope, target, authority or custodian refuses.
    """
    with journal_file(write=True) as file:
        entries, head = read_locked(file)
        for record in retention_records(entries).values():
            old = record['hold']
            if old['request_key'] == hold['request_key'] or old['id'] == hold['id']:
                if {k: v for k, v in old.items() if k != 'id'} != {k: v for k, v in hold.items() if k != 'id'}:
                    raise ValidationError('Preservation request key was already used for another instruction.')
                os.fsync(file.fileno())
                return record['hold_entry']
        return _append_retention(file, entries, head, HOLD, 'hold', hold)


def append_release(release, hold):
    """Journal a release and fsync it BEFORE its database row commits, always after its own hold.

    `hold` is the database hold's journal record: a hold recorded before the journal was configured is journaled first,
    so no release ever precedes its hold. A retry by the same custodian with the same authority returns the journaled
    release; any other release of the same hold refuses, as does the hold's own custodian.
    """
    with journal_file(write=True) as file:
        entries, head = read_locked(file)
        record = retention_records(entries).get(release['hold_id'])
        if record is None:
            if hold['id'] != release['hold_id']: raise ValidationError('Unknown preservation instruction.')
            if any(r['hold']['request_key'] == hold['request_key'] for r in retention_records(entries).values()):
                raise ValidationError('Preservation request key was already used for another instruction.')
            entry = _append_retention(file, entries, head, HOLD, 'hold', hold)
            entries = entries + [entry]; head = p.digest(entry)
            record = {'hold': hold, 'release': None, 'release_entry': None}
        elif {k: v for k, v in record['hold'].items() if k != 'created_by'} != {k: v for k, v in hold.items() if k != 'created_by'}:
            # The custodian may differ only for a hold replayed while its journaled custodian's account was absent from
            # the restored database; the journaled custodian still may not release it (below and in read_locked).
            raise ValidationError('The database hold differs from its journal entry.')
        if record['release'] is not None:
            old = record['release']
            if (old['created_by'], old['authority_sha256']) != (release['created_by'], release['authority_sha256']):
                raise ValidationError('This preservation instruction was already released with other evidence.')
            os.fsync(file.fileno())
            return record['release_entry']
        if release['created_by'] == record['hold']['created_by']:
            raise ValidationError('A second administrator must record release authority.')
        return _append_retention(file, entries, head, RELEASE, 'release', release)


def pending_targets():
    """A durable intent still denies access after a database rollback/crash."""
    if not getattr(settings, 'DISPOSITION_JOURNAL_PATH', ''): return []
    return [e['body']['instruction']['target_id'] for e in instruction_entries(verified())]
