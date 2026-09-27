#!/usr/bin/env python3
"""Check the production wheel lock against every original version pin and recorded artifact.

Uses only the standard library, before a production venv or dependency is installed.
This is an integrity/consistency check; provenance remains the reviewed PyPI acquisition.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def verify(root):
    root = Path(root)
    original = (root / 'requirements.txt').read_bytes()
    locked = (root / 'requirements-production.lock').read_bytes()
    manifest = json.loads((root / 'requirements-production.manifest.json').read_bytes())
    if (manifest['format'] != 1 or manifest['index'] != 'https://pypi.org/simple'
            or manifest['target'] != {'os': 'Ubuntu 24.04', 'python': 'CPython 3.12', 'machine': 'x86_64'}
            or manifest['requirements_sha256'] != hashlib.sha256(original).hexdigest()
            or manifest['lock_sha256'] != hashlib.sha256(locked).hexdigest()):
        raise ValueError('dependency_manifest_mismatch')

    def entries(raw, hashes=False):
        result = {}
        pattern = r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s;]+)'
        if hashes:
            pattern += r' --hash=sha256:([0-9a-f]{64})'
        for line in raw.decode('utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.fullmatch(pattern, line)
            if not match or canonical(match[1]) in result:
                raise ValueError('dependency_pin_invalid')
            result[canonical(match[1])] = tuple(match.groups()[1:])
        if not result:
            raise ValueError('dependency_pins_empty')
        return result

    pins, locks = entries(original), entries(locked, True)
    if {name: value[:1] for name, value in locks.items()} != pins:
        raise ValueError('dependency_versions_differ')
    artifacts = {}
    for artifact in manifest['artifacts']:
        name = canonical(artifact['name'])
        filename = artifact['filename']
        if (name in artifacts or Path(filename).name != filename or not filename.endswith('.whl')
                or not isinstance(artifact['bytes'], int) or artifact['bytes'] <= 0):
            raise ValueError('dependency_artifact_invalid')
        artifacts[name] = (artifact['version'], artifact['sha256'])
    if artifacts != locks:
        raise ValueError('dependency_artifacts_differ')
    return {'packages': len(pins), 'lock_sha256': hashlib.sha256(locked).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    try:
        result = verify(args.root)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'dependency lock: REFUSED: files, pins or manifest do not agree\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
