"""Closed, signed prospective authority. No default key, schedule or permission."""
import hashlib
import json
import uuid
from datetime import datetime
from typing import Annotated, Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from django.core.exceptions import ValidationError
from pydantic import BaseModel, ConfigDict, Field

ADAPTER = 'empty-unreviewed-draft-v1'
ZERO = '0' * 64
MAX_BYTES = 65536
Hash = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Policy(Strict):
    contract: Literal['disposition-policy-v1']
    policy_id: str
    namespace: str
    department_id: str
    adapter: Literal['empty-unreviewed-draft-v1']
    anchor: Literal['created_at']
    minimum_age_seconds: Annotated[int, Field(ge=1, le=31536000000)]
    not_before: str
    expires_at: str
    schedule_sha256: Hash
    purpose: Literal['authorize_prospective_empty_draft_disposition']


class Checkpoint(Strict):
    contract: Literal['disposition-journal-checkpoint-v1']
    namespace: str
    sequence: Annotated[int, Field(ge=0, le=10000)]
    head_sha256: Hash
    issued_at: str
    expires_at: str


class Envelope(Strict):
    key_id: Annotated[str, Field(pattern=r'^[a-zA-Z0-9_-]{1,80}$')]
    body: dict
    signature: Annotated[str, Field(pattern=r'^[0-9a-f]{128}$')]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        if result.utcoffset() is None: raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('An explicit timezone-aware authority timestamp is required.') from None


def identity(value):
    try:
        if str(uuid.UUID(value)) != value: raise ValueError()
        return value
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Authority identities must be canonical UUIDs.') from None


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise ValueError()
            result[key] = value
        return result
    try:
        if not isinstance(raw, bytes) or len(raw) > MAX_BYTES: raise ValueError()
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError, RecursionError, UnicodeError):
        raise ValidationError('The complete signed authority document is invalid.') from None


def signed_bytes(body):
    return b'quillmd.disposition.signed.v1\x00' + canonical(body)


def verify(envelope, schema, keys):
    """The independently configured public key is the trust root, never a hash."""
    try:
        if len(canonical(envelope)) > MAX_BYTES: raise ValueError()
        e = Envelope.model_validate(envelope)
        body = schema.model_validate(e.body)
        public = keys[e.key_id]
        if not isinstance(public, str) or len(public) != 64: raise ValueError()
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(bytes.fromhex(e.signature), signed_bytes(e.body))
        identity(body.namespace)
        return body
    except (ValueError, TypeError, KeyError, InvalidSignature):
        raise ValidationError('Signed disposition authority could not be verified.') from None


def verify_policy(envelope, keys, *, namespace, now):
    body = verify(envelope, Policy, keys)
    identity(body.policy_id); identity(body.department_id)
    start, end = timestamp(body.not_before), timestamp(body.expires_at)
    if body.namespace != namespace or start >= end or now >= end:
        raise ValidationError('Disposition policy scope or admission window is unavailable.')
    return body


def verify_checkpoint(envelope, keys, *, namespace, now):
    body = verify(envelope, Checkpoint, keys)
    start, end = timestamp(body.issued_at), timestamp(body.expires_at)
    if (body.namespace != namespace or not start <= now < end
            or (body.sequence == 0) != (body.head_sha256 == ZERO)):
        raise ValidationError('The independent journal checkpoint is unavailable or expired.')
    return body
