"""Exact, read-only footprint of a Python virtual environment.

Nothing here imports from, executes or writes to the environment it measures. The footprint is every object
under the venv root, never following a link: kind, mode, owner, group, device, inode and link count, plus the
size, SHA-256 and mtime of every regular file and the target of every symbolic link. Two footprints are equal
only when nothing in the venv was added, removed, rewritten, re-moded or replaced (a replaced file has a new
inode even when its bytes are unchanged).

The census reads only what the footprint already measured: every ``*.dist-info`` METADATA (name and version)
and RECORD (the files pip recorded). Bytecode that no RECORD lists is reported by path. On 2026-10-31 the live
rebuild venv held 64 distributions and 63 such files (certifi 2, PIL 9, pypdf 52), written at
2026-10-23T14:44Z by a process that imported from the venv without ``-B``. They are recorded as found and never
deleted here.

Used by ``install_rebuild_release`` (interpretation 67, D1: the code-only act leaves the venv exactly as found)
and by ``rebuild_dependency_stage`` (the later dependency act, D1b).
"""
import csv
import hashlib
import io
import json
import os
import posixpath
import re
import stat
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

FORMAT = 'quillmd-venv-footprint-v1'
SITE = 'lib/python3.12/site-packages'
LIMIT_OBJECTS = 60000
LIMIT_BYTES = 1024 ** 3
LIMIT_FILE_BYTES = 128 * 1024 ** 2
LIMIT_METADATA_BYTES = 4 * 1024 ** 2
#: One exact requirement per line, ``name==version``; anything else (ranges, markers, includes, options,
#: hashes, URLs) cannot be compared with an installed version and is refused rather than guessed at.
PIN = re.compile(r'([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)')


class Refusal(RuntimeError):
    """A fixed, non-sensitive label."""


def require(value, label):
    if not value:
        raise Refusal(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def normalize(name):
    """PEP 503 project-name normalisation."""
    return re.sub(r'[-_.]+', '-', name).lower()


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def stable_bytes(path, limit=LIMIT_FILE_BYTES):
    """Read one regular file without following a link, refusing if it changes while it is read."""
    path = Path(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'bounded_regular_file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        raw = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size
            and _identity(before) == _identity(opened) == _identity(after) == _identity(path.lstat()),
            'stable_complete_file')
    return raw


def _relative(name):
    path = PurePosixPath(name)
    require(type(name) is str and name not in ('', '.') and name == str(path) and not path.is_absolute()
            and '..' not in path.parts, 'canonical_venv_relative_path')
    return name


def inventory(venv):
    """Every object under ``venv``; links are recorded, never followed."""
    venv = Path(venv)
    require(venv.is_absolute() and not venv.is_symlink() and venv.resolve(strict=True) == venv and venv.is_dir(),
            'canonical_existing_venv')
    info = venv.lstat()
    result = {'.': {'kind': 'directory', 'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid,
                    'gid': info.st_gid, 'device': info.st_dev, 'inode': info.st_ino, 'links': info.st_nlink}}
    total = 0
    for current, directories, files in os.walk(venv, followlinks=False):
        for leaf in sorted(directories + files):
            path = Path(current) / leaf
            name = _relative(path.relative_to(venv).as_posix())
            info = path.lstat()
            row = {'mode': stat.S_IMODE(info.st_mode), 'uid': info.st_uid, 'gid': info.st_gid,
                   'device': info.st_dev, 'inode': info.st_ino, 'links': info.st_nlink}
            if stat.S_ISLNK(info.st_mode):
                row.update(kind='symlink', target=os.readlink(path))
            elif stat.S_ISDIR(info.st_mode):
                row.update(kind='directory')
            elif stat.S_ISREG(info.st_mode):
                data = stable_bytes(path)
                row.update(kind='file', bytes=len(data), sha256=sha(data), mtime_ns=info.st_mtime_ns)
                total += len(data)
            else:
                raise Refusal('unexpected_venv_object_kind')
            require(name not in result, 'unique_venv_object')
            result[name] = row
            require(len(result) <= LIMIT_OBJECTS and total <= LIMIT_BYTES, 'bounded_venv_population')
    return result


def listed_bytes(venv, files, name, limit=LIMIT_METADATA_BYTES):
    """The bytes of a file the footprint measured, proven to be the bytes it measured."""
    row = files.get(name)
    require(type(row) is dict and row.get('kind') == 'file' and row['bytes'] <= limit, 'measured_metadata_file')
    raw = stable_bytes(Path(venv) / name, limit)
    require(len(raw) == row['bytes'] and sha(raw) == row['sha256'], 'metadata_matches_footprint')
    return raw


def census(venv, files):
    """Distributions, the files their RECORDs list, and every bytecode file no RECORD lists."""
    site = PurePosixPath(SITE)
    dist_infos = sorted(name for name, row in files.items()
                        if row.get('kind') == 'directory' and PurePosixPath(name).parent == site
                        and name.endswith('.dist-info'))
    distributions, recorded = {}, set()
    for dist_info in dist_infos:
        metadata = BytesParser().parsebytes(listed_bytes(venv, files, dist_info + '/METADATA'))
        require(isinstance(metadata['Name'], str) and isinstance(metadata['Version'], str)
                and metadata['Name'].strip() and metadata['Version'].strip(), 'distribution_identity')
        name = normalize(metadata['Name'].strip())
        require(name not in distributions, 'unique_distribution')
        distributions[name] = metadata['Version'].strip()
        record = listed_bytes(venv, files, dist_info + '/RECORD').decode()
        for row in csv.reader(io.StringIO(record)):
            if not row:
                continue
            require(1 <= len(row) <= 3 and row[0], 'typed_record_row')
            target = posixpath.normpath(posixpath.join(SITE, row[0]))
            require(not target.startswith('../') and target != '..' and not posixpath.isabs(target),
                    'record_stays_inside_venv')
            recorded.add(target)
    bytecode = sorted(name for name, row in files.items() if row.get('kind') == 'file' and name.endswith('.pyc'))
    return {'distributions': distributions, 'distribution_count': len(distributions),
            'bytecode_files': len(bytecode),
            'unrecorded_bytecode': [name for name in bytecode if name not in recorded],
            'objects': len(files),
            'file_bytes': sum(row['bytes'] for row in files.values() if row.get('kind') == 'file')}


def snapshot(venv):
    files = inventory(venv)
    return {'format': FORMAT, 'venv': str(venv), 'footprint_sha256': sha(canonical(files)),
            'census': census(venv, files), 'files': files}


def summary(value):
    """The snapshot without its object table: what a declaration or receipt quotes."""
    facts = value['census']
    return {'venv': value['venv'], 'footprint_sha256': value['footprint_sha256'],
            'distributions': facts['distribution_count'], 'objects': facts['objects'],
            'file_bytes': facts['file_bytes'], 'bytecode_files': facts['bytecode_files'],
            'unrecorded_bytecode': len(facts['unrecorded_bytecode'])}


def difference(before, after, limit=50):
    """Bounded, path-only description of how two object tables differ (venv paths carry no clinical data)."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(name for name in set(before) & set(after) if before[name] != after[name])
    return {'added': added[:limit], 'removed': removed[:limit], 'changed': changed[:limit],
            'counts': {'added': len(added), 'removed': len(removed), 'changed': len(changed)}}


def require_exact(before, after, label='venv_footprint_changed'):
    """Both snapshots describe the same venv and every object in it is identical."""
    require(type(before) is dict and type(after) is dict and before.get('format') == after.get('format') == FORMAT
            and before.get('venv') == after.get('venv'), 'comparable_venv_snapshots')
    require(before['footprint_sha256'] == sha(canonical(before['files']))
            and after['footprint_sha256'] == sha(canonical(after['files'])), 'self_consistent_venv_snapshots')
    require(before['footprint_sha256'] == after['footprint_sha256'] and before['files'] == after['files'], label)
    return True


def requirement_pins(text):
    """``{normalized name: version}`` from a requirements file made only of exact pins and comments."""
    pins = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        match = PIN.fullmatch(stripped)
        require(match is not None, 'literal_exact_requirement_pins_only')
        name = normalize(match[1])
        require(name not in pins, 'unique_requirement_pins')
        pins[name] = match[2]
    require(pins, 'non_empty_requirements')
    return pins


def requirements_mismatch(pins, distributions):
    """Every pin the venv does not satisfy exactly: ``{name: {'required': v, 'installed': w-or-None}}``."""
    return {name: {'required': version, 'installed': distributions.get(name)}
            for name, version in sorted(pins.items()) if distributions.get(name) != version}
