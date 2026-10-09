"""Two-setting private-preview activation and protection rollback."""
from io import StringIO
import re
from dotenv import dotenv_values
from .email_activation import _line, replace_environment

KEYS = {'QUILLMD_RELEASE_SHA', 'QUILLMD_PREVIEW_AUTH_ENABLED'}


def environment(original, expected_release, target_release, enabled):
    from .direct_account_access import reject_legacy_environment
    reject_legacy_environment(original)
    if not all(re.fullmatch(r'[a-f0-9]{40}', value or '') for value in (expected_release, target_release)):
        raise ValueError('Use exact recorded source revisions.')
    if not isinstance(enabled, bool):
        raise ValueError('Preview mode must be explicit.')
    old = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    if old.get('QUILLMD_RELEASE_SHA') != expected_release:
        raise ValueError('The protected environment changed release.')
    values = {'QUILLMD_RELEASE_SHA': target_release, 'QUILLMD_PREVIEW_AUTH_ENABLED': '1' if enabled else '0'}
    remaining = dict(values)
    output, seen = [], set()
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=', line)
        key = match[1].decode() if match else None
        if key not in KEYS:
            output.append(line)
        else:
            if key in seen:
                raise ValueError('Duplicate controlled environment setting.')
            seen.add(key)
            output.append(_line(key, remaining.pop(key)))
    if output and not output[-1].endswith(b'\n'):
        output.append(b'\n')
    output.extend(_line(key, value) for key, value in remaining.items())
    updated = b''.join(output)
    actual = dotenv_values(stream=StringIO(updated.decode()), interpolate=False)
    if any(actual.get(key) != value for key, value in values.items()) or (
            {k: v for k, v in old.items() if k not in KEYS} !=
            {k: v for k, v in actual.items() if k not in KEYS}):
        raise ValueError('An undeclared setting changed.')
    return updated
