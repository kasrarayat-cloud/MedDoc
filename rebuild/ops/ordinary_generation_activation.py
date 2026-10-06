"""Pure configuration preparation for the private synthetic Sonnet 5.5 ordinary workflow.

This module neither reads an environment file nor installs anything. The reviewed preserving installer must supply
the privately retained bytes and the exact candidate's source bytes, after its source, CI, migration and state gates.
A source-bound rendering is preparation, never proof that those gates or provider qualification passed.
"""
import hashlib
from io import StringIO
import re

from dotenv import dotenv_values

from .email_activation import _line


MODEL = 'claude-sonnet-5-5'
CONTRACT = 'ordinary-field-relations-v4'
PROFILE = 'claude-sonnet-5-5-ordinary-v1'
SOURCE_PATHS = frozenset({
    'rebuild/core/generation.py', 'rebuild/core/v3_field_relations.py',
    'rebuild/quillmd/settings.py', 'rebuild/quillmd/application_profile.py',
})
VALUES = {
    'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': MODEL,
    'QUILLMD_AI_INPUT_RATE': '2', 'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20',
    'QUILLMD_AI_THINKING': 'between_tools', 'QUILLMD_AI_EFFORT': 'medium', 'QUILLMD_AI_INFERENCE_GEO': '',
    'QUILLMD_V3_FIELD_RELATIONS': '1',
}
KEYS = frozenset(VALUES) | {'QUILLMD_RELEASE_SHA'}


def environment(original, expected_release, target_release, *, source_identity, source_bytes):
    """Render exactly the declared delta, preserving every unrelated line and value.

    ``source_identity`` is the reviewed candidate manifest; ``source_bytes`` must come from that exact candidate,
    supplied by the installer, not from the installed older source. The manifest binds the model, contract and profile
    alongside the release and each source digest. This pure function does not run git, contact a provider, inspect
    current records or approve installation. No source rollback is provided: current redaction, holds and v3 mappings
    require the separate preserving installer's compatibility checks before any rollback decision.
    """
    if not all(re.fullmatch(r'[a-f0-9]{40}', value or '') for value in (expected_release, target_release)):
        raise ValueError('Use exact recorded source revisions.')
    if (not isinstance(source_identity, dict)
            or set(source_identity) != {'release', 'model', 'ordinary_field_contract', 'request_profile', 'sources'}
            or source_identity['release'] != target_release or source_identity['model'] != MODEL
            or source_identity['ordinary_field_contract'] != CONTRACT or source_identity['request_profile'] != PROFILE
            or not isinstance(source_identity['sources'], dict) or set(source_identity['sources']) != SOURCE_PATHS
            or not isinstance(source_bytes, dict) or set(source_bytes) != SOURCE_PATHS):
        raise ValueError('Candidate source and ordinary configuration identity differ.')
    for path in SOURCE_PATHS:
        if (not isinstance(source_bytes[path], bytes)
                or source_identity['sources'][path] != hashlib.sha256(source_bytes[path]).hexdigest()):
            raise ValueError('Candidate source digest differs.')
    if not isinstance(original, bytes):
        raise ValueError('Supply the privately retained environment bytes.')
    old = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    if old.get('QUILLMD_RELEASE_SHA') != expected_release:
        raise ValueError('The protected environment changed release.')
    if old.get('QUILLMD_DATA_MODE', 'synthetic') != 'synthetic':
        raise ValueError('This configuration preparation is synthetic-only.')
    if old.get('QUILLMD_AI_MODE', 'fixture') not in ('fixture', 'live'):
        raise ValueError('The existing provider mode must be explicit and recognised.')
    if any(old.get(name, '0') != '0' for name in (
            'QUILLMD_WM_NARRATIVE', 'QUILLMD_V3_HISTORY_CONTEXT', 'QUILLMD_V3_GENERATION_BATCHES')):
        raise ValueError('A different generation contract is enabled; inspect its qualification separately.')
    values = {'QUILLMD_RELEASE_SHA': target_release, **VALUES}
    remaining = dict(values)
    output, seen = [], set()
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=', line)
        key = match[1].decode() if match else None
        if key not in KEYS:
            output.append(line)
            continue
        if key in seen:
            raise ValueError('Duplicate controlled environment setting.')
        seen.add(key)
        output.append(_line(key, remaining.pop(key)))
    if output and not output[-1].endswith(b'\n'):
        output.append(b'\n')
    output.extend(_line(key, value) for key, value in remaining.items())
    updated = b''.join(output)
    actual = dotenv_values(stream=StringIO(updated.decode()), interpolate=False)
    if (any(actual.get(key) != value for key, value in values.items())
            or {k: v for k, v in old.items() if k not in KEYS}
            != {k: v for k, v in actual.items() if k not in KEYS}):
        raise ValueError('An undeclared environment setting changed.')
    return updated
