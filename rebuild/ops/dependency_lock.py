#!/usr/bin/env python3
"""Check the production wheel lock against every original version pin and recorded artifact.

Uses only the standard library, before a production venv or dependency is installed.
This is an integrity/consistency check; provenance remains the reviewed acquisition.
Only the explicitly reviewed official model wheel may bypass the PyPI index.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


# Adding another URL or model version requires a new source/artifact review.
MODEL_NAME = 'en-core-web-sm'
MODEL_VERSION = '3.8.0'
MODEL_SHA256 = '1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85'
MODEL_URL = ('https://github.com/explosion/spacy-models/releases/download/'
             'en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl')
MODEL_REQUIREMENT = f'{MODEL_NAME} @ {MODEL_URL}#sha256={MODEL_SHA256}'
PYPI = 'https://pypi.org/simple'


def canonical(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def verify(root, wheelhouse=None):
    root = Path(root)
    original = (root / 'requirements.txt').read_bytes()
    locked = (root / 'requirements-production.lock').read_bytes()
    manifest = json.loads((root / 'requirements-production.manifest.json').read_bytes())
    if (manifest['format'] != 2 or manifest['index'] != PYPI
            or manifest['target'] != {'os': 'Ubuntu 24.04', 'python': 'CPython 3.12', 'machine': 'x86_64'}
            or manifest['requirements_sha256'] != hashlib.sha256(original).hexdigest()
            or manifest['lock_sha256'] != hashlib.sha256(locked).hexdigest()):
        raise ValueError('dependency_manifest_mismatch')

    def entries(raw, hashes=False):
        result = {}
        pattern = r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([0-9]+(?:\.[0-9]+)*(?:[a-z]+[0-9]+)?)'
        if hashes:
            pattern += r' --hash=sha256:([0-9a-f]{64})'
        for line in raw.decode('utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            model_line = MODEL_REQUIREMENT + (f' --hash=sha256:{MODEL_SHA256}' if hashes else '')
            if line == model_line:
                if MODEL_NAME in result:
                    raise ValueError('dependency_pin_invalid')
                result[MODEL_NAME] = ((MODEL_VERSION, MODEL_SHA256) if hashes else (MODEL_VERSION,))
                continue
            match = re.fullmatch(pattern, line)
            if not match or canonical(match[1]) in result:
                raise ValueError('dependency_pin_invalid')
            if canonical(match[1]) == MODEL_NAME:
                raise ValueError('dependency_model_source_invalid')
            result[canonical(match[1])] = tuple(match.groups()[1:])
        if not result:
            raise ValueError('dependency_pins_empty')
        return result

    pins, locks = entries(original), entries(locked, True)
    if {name: value[:1] for name, value in locks.items()} != pins:
        raise ValueError('dependency_versions_differ')
    artifacts = {}
    filenames = set()
    for artifact in manifest['artifacts']:
        name = canonical(artifact['name'])
        filename = artifact['filename']
        # Wheel names encode distribution and version; no paths, options or alternate artifacts.
        wheel = re.fullmatch(r'([A-Za-z0-9_.]+)-([A-Za-z0-9_.]+)-([A-Za-z0-9_.]+)-([A-Za-z0-9_.]+)-([A-Za-z0-9_.]+)\.whl', filename)
        source = MODEL_URL if name == MODEL_NAME else PYPI
        if (name in artifacts or filename in filenames or not wheel
                or canonical(wheel[1]) != name or wheel[2] != artifact['version']
                or set(artifact) != {'name', 'version', 'filename', 'sha256', 'bytes', 'source'}
                or artifact['source'] != source
                or not re.fullmatch(r'[0-9a-f]{64}', artifact['sha256'])
                or type(artifact['bytes']) is not int or artifact['bytes'] <= 0
                or (name == MODEL_NAME and filename != MODEL_URL.rsplit('/', 1)[1])):
            raise ValueError('dependency_artifact_invalid')
        filenames.add(filename)
        artifacts[name] = (artifact['version'], artifact['sha256'])
        if wheelhouse is not None:
            path = Path(wheelhouse) / filename
            if (path.is_symlink() or not path.is_file() or path.stat().st_size != artifact['bytes']
                    or hashlib.sha256(path.read_bytes()).hexdigest() != artifact['sha256']):
                raise ValueError('dependency_wheel_bytes_differ')
    if artifacts != locks:
        raise ValueError('dependency_artifacts_differ')
    if wheelhouse is not None and {p.name for p in Path(wheelhouse).iterdir()} != filenames:
        raise ValueError('dependency_wheel_inventory_differ')
    return {'packages': len(pins), 'lock_sha256': hashlib.sha256(locked).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--wheelhouse', help='also verify an exact local wheel inventory; no downloads')
    args = parser.parse_args()
    try:
        result = verify(args.root, args.wheelhouse)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, 'dependency lock: REFUSED: files, pins or manifest do not agree\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
