#!/usr/bin/env python3
"""The dependency stage of the LATER act D1b (interpretation 67): three security pins move in the live rebuild venv.

    pypdf    6.21.1 -> 6.21.4
    filelock 4.0.0  -> 4.2.1
    msgpack  1.2.2  -> 1.2.3   (cp312 manylinux x86_64 wheel with one native extension)

ONE offline pip process installs the three hash-pinned official wheels, while the owned units are drained (the
caller proves it before and after: ``drained``). Nothing else in the venv may change: every object outside the
three packages keeps its bytes, mode, owner and inode, and the 61 other distributions keep their versions. The
new packages must equal their wheels byte for byte, with pip's own generated metadata and no bytecode.

THE 63 UNRECORDED BYTECODE FILES (certifi 2, PIL 9, pypdf 52; written 2026-10-23T14:44Z) are recorded as found and
never deleted by this module. pip's uninstall of pypdf 6.21.1 removes pypdf's 52 itself, because each sits at the
cache path of a module pypdf's RECORD lists (pip's UninstallPathSet.add); that removal is measured and reported.
certifi's 2 and PIL's 9 must stay byte-identical.

NO DOWNGRADE EXISTS HERE (D2): TRANSITIONS only move forward, ``transition`` refuses any other direction, and no
old wheel is ever installed. A rollback of the release that carries these pins keeps them.

Import is inert. ``install_once`` refuses the live venv unless the declared act passes ``live=True``; the
``calibrate`` command runs the whole stage on a COPY of the live venv (``cp -a``), relocated in memory only, and
proves the live venv was not touched. ``fetch`` downloads the three wheels and verifies each sha256 against BOTH
of PyPI's published surfaces (the JSON API and the PEP 691 simple index).
"""
import argparse
import base64
import csv
import hashlib
import importlib
import io
import json
import os
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

SOURCE = Path(__file__).resolve().parents[2]
VENV = Path('/opt/meddoc-pro/rebuild/.venv')
SITE = 'lib/python3.12/site-packages'
FORMAT = 'quillmd-rebuild-dependency-stage-v1'
CALIBRATION_FORMAT = 'quillmd-rebuild-dependency-calibration-v1'
TRANSITIONS = {'filelock': ('4.0.0', '4.2.1'), 'msgpack': ('1.2.2', '1.2.3'), 'pypdf': ('6.21.1', '6.21.4')}
#: sha256 and size as published by BOTH PyPI surfaces on 2026-10-31 (JSON API digests == simple-index hashes).
WHEELS = {
    'filelock': {'filename': 'filelock-4.2.1-py3-none-any.whl', 'bytes': 162455,
                 'sha256': '7be2662e9e826b9bba28afc0f843a123280d799a2ea44bb5d35ccec67905ae44'},
    'msgpack': {'filename': 'msgpack-1.2.3-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.'
                            'manylinux_2_28_x86_64.whl', 'bytes': 472998,
                'sha256': 'ede33b2892ceb976283e009ad12fa1834cfdf1f9c43ee9c97849fc588d00a618'},
    'pypdf': {'filename': 'pypdf-6.21.4-py3-none-any.whl', 'bytes': 410430,
              'sha256': '33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c'}}
ROOTS = {'filelock': ('filelock',), 'msgpack': ('msgpack',), 'pypdf': ('pypdf',)}
NATIVE = {'filelock': (), 'msgpack': ('msgpack/_cmsgpack.cpython-312-x86_64-linux-gnu.so',), 'pypdf': ()}
DISTRIBUTIONS = 64
PIP_VERSION = '24.0'
PIP_TIMEOUT_SECONDS = 180
CHILD_UMASK = 0o022
MAX_WHEEL_BYTES = 16 * 1024 ** 2
PYPI = 'https://pypi.org'
FILE_HOST = 'files.pythonhosted.org'

CHECK_PROGRAM = r"""import hashlib,io,json,certifi,PIL,pypdf,filelock,msgpack
from PIL import Image
from msgpack import _cmsgpack
import cachecontrol.caches.file_cache as file_cache
image=Image.new('RGB',(3,2),(17,31,127));buffer=io.BytesIO();image.save(buffer,format='PNG');buffer.seek(0)
with Image.open(buffer) as png:png_ok=png.size==(3,2) and png.getpixel((1,1))==(17,31,127)
document=io.BytesIO();writer=pypdf.PdfWriter();writer.add_blank_page(width=72,height=144);writer.write(document);document.seek(0)
reader=pypdf.PdfReader(document);pdf_ok=len(reader.pages)==1 and [float(x) for x in reader.pages[0].mediabox]==[0.0,0.0,72.0,144.0]
value={'a':[1,2.5,b'x',None,True]};packed=msgpack.packb(value,use_bin_type=True)
print(json.dumps({'pypdf':pypdf.__version__,'pypdf_file':pypdf.__file__,'pdf_roundtrip':pdf_ok,
 'filelock':filelock.__version__,'filelock_file':filelock.__file__,'filelock_api':issubclass(filelock.FileLock,filelock.BaseFileLock),
 'msgpack':msgpack.version,'msgpack_extension':_cmsgpack.__file__,'msgpack_c_packer':msgpack.Packer is _cmsgpack.Packer,
 'msgpack_roundtrip':msgpack.unpackb(packed,raw=False)==value,'cachecontrol_file_cache':file_cache.__file__,
 'certifi_ca_sha256':hashlib.sha256(open(certifi.where(),'rb').read()).hexdigest(),'pillow':PIL.__version__,'png_roundtrip':png_ok},sort_keys=True))
"""


class Refusal(RuntimeError):
    """A fixed, non-sensitive label."""


def require(value, label):
    if not value:
        raise Refusal(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def footprint():
    rebuild = str(SOURCE / 'rebuild')
    if rebuild not in sys.path:
        sys.path.insert(0, rebuild)
    return importlib.import_module('ops.venv_footprint')


def version_key(version):
    require(re.fullmatch(r'[0-9]+(\.[0-9]+)*', version) is not None, 'numeric_release_version')
    return tuple(int(part) for part in version.split('.'))


def forward_only(transitions=TRANSITIONS):
    """D2 in code: every transition strictly raises the version; there is no reverse entry."""
    for package, (old, new) in transitions.items():
        require(version_key(new) > version_key(old), 'no_downgrade:' + package)
    return True


def umask():
    value = os.umask(0o077)
    os.umask(value)
    return value


def dist_info(package, version):
    return package + '-' + version + '.dist-info'


def owned(name, package):
    """Is this venv-relative path inside the package's import roots or either of its dist-info directories?"""
    old, new = TRANSITIONS[package]
    for root in (*ROOTS[package], dist_info(package, old), dist_info(package, new)):
        prefix = SITE + '/' + root
        if name == prefix or name.startswith(prefix + '/'):
            return True
    return False


def owned_by_any(name):
    return any(owned(name, package) for package in TRANSITIONS)


def record_hash(raw):
    return 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')


def wheel(path, package):
    """The pinned official wheel, proven: sha256, size, entries, RECORD, METADATA, native files."""
    pin = WHEELS[package]
    path = Path(path)
    info = path.lstat()
    require(path.is_absolute() and path.resolve(strict=True) == path and stat.S_ISREG(info.st_mode)
            and info.st_uid == os.getuid() and info.st_nlink == 1 and not info.st_mode & 0o022
            and path.name == pin['filename'], 'private_pinned_wheel_file')
    raw = path.read_bytes()
    require(len(raw) == pin['bytes'] == info.st_size and sha(raw) == pin['sha256'], 'exact_official_wheel_bytes')
    version = TRANSITIONS[package][1]
    prefix = dist_info(package, version) + '/'
    files = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for entry in archive.infolist():
            name = entry.filename.rstrip('/') if entry.is_dir() else entry.filename
            parts = PurePosixPath(name).parts
            require(name and not name.startswith('/') and '..' not in parts and '\\' not in name
                    and (parts[0] in ROOTS[package] or parts[0] == prefix[:-1]) and not entry.flag_bits & 1
                    and entry.file_size <= MAX_WHEEL_BYTES, 'bounded_wheel_entry')
            if entry.is_dir():
                continue
            kind = (entry.external_attr >> 16) & 0o170000
            require(kind in (0, stat.S_IFREG), 'regular_wheel_entry')
            data = archive.read(entry)
            files[name] = {'sha256': sha(data), 'bytes': len(data),
                           'executable': bool((entry.external_attr >> 16) & 0o111)}
        rows = list(csv.reader(io.StringIO(archive.read(prefix + 'RECORD').decode())))
        require(all(len(row) == 3 for row in rows) and {row[0] for row in rows} == set(files)
                and len(rows) == len(files), 'complete_wheel_record')
        for name, digest, size in rows:
            if name == prefix + 'RECORD':
                require(digest == size == '', 'wheel_record_self_row')
            else:
                require(digest == record_hash(archive.read(name)) and size == str(files[name]['bytes']),
                        'wheel_record_hashes')
        metadata = BytesParser().parsebytes(archive.read(prefix + 'METADATA'))
        require(metadata['Name'].lower() == package and metadata['Version'] == version, 'wheel_identity')
        requires = metadata.get_all('Requires-Dist') or []
    natives = sorted(name for name in files if '.so' in PurePosixPath(name).name)
    require(natives == sorted(NATIVE[package]) and all(files[name]['executable'] for name in natives),
            'native_extension_population')
    require(all(';' in requirement for requirement in requires), 'no_unconditional_new_requirement')
    return {'path': str(path), 'sha256': pin['sha256'], 'bytes': pin['bytes'], 'files': files,
            'requires': requires}


def wheels(directory):
    return {package: wheel(Path(directory) / WHEELS[package]['filename'], package) for package in sorted(WHEELS)}


def generated_metadata(package, wheel_path):
    """What pip 24.0 writes besides the payload, for a wheel installed from a local file path."""
    pin = WHEELS[package]
    prefix = SITE + '/' + dist_info(package, TRANSITIONS[package][1]) + '/'
    direct = {'archive_info': {'hash': 'sha256=' + pin['sha256'], 'hashes': {'sha256': pin['sha256']}},
              'url': Path(wheel_path).as_uri()}
    return {prefix + 'INSTALLER': b'pip\n', prefix + 'REQUESTED': b'',
            prefix + 'direct_url.json': json.dumps(direct, sort_keys=True).encode()}


def versions(snapshot):
    return {package: snapshot['census']['distributions'].get(package) for package in TRANSITIONS}


def transition(before, after, proven):
    """The only acceptable difference between the two snapshots of one venv."""
    module = footprint()
    require(before['venv'] == after['venv'] and before['format'] == after['format'] == module.FORMAT,
            'paired_snapshots_of_one_venv')
    forward_only()
    old = {package: pair[0] for package, pair in TRANSITIONS.items()}
    new = {package: pair[1] for package, pair in TRANSITIONS.items()}
    require(versions(before) == old and versions(after) == new, 'exact_transition_versions')
    b, a = dict(before['census']['distributions']), dict(after['census']['distributions'])
    require(len(b) == len(a) == DISTRIBUTIONS and b.get('pip') == a.get('pip') == PIP_VERSION, 'calibrated_population')
    for package in TRANSITIONS:
        b.pop(package)
        a.pop(package)
    require(b == a, 'every_other_distribution_unchanged')
    others_before = {n: r for n, r in before['files'].items() if not owned_by_any(n)}
    others_after = {n: r for n, r in after['files'].items() if not owned_by_any(n)}
    require(others_before == others_after, 'every_other_venv_object_byte_mode_identity_exact')
    uid, gid = os.getuid(), os.getgid()
    installed = {}
    for package, (old_version, new_version) in TRANSITIONS.items():
        require(not any(n == SITE + '/' + dist_info(package, old_version)
                        or n.startswith(SITE + '/' + dist_info(package, old_version) + '/') for n in after['files']),
                'old_distribution_removed')
        expected = {SITE + '/' + name: row for name, row in proven[package]['files'].items()}
        generated = generated_metadata(package, proven[package]['path'])
        record = SITE + '/' + dist_info(package, new_version) + '/RECORD'
        rows = {n: r for n, r in after['files'].items() if owned(n, package)}
        files = {n for n, r in rows.items() if r['kind'] == 'file'}
        require(files == set(expected) | set(generated), 'exact_installed_file_population')
        require(not any(n.endswith('.pyc') or '/__pycache__' in n for n in rows), 'installed_without_bytecode')
        directories = {str(parent) for name in files for parent in PurePosixPath(name).parents
                       if len(parent.parts) > len(PurePosixPath(SITE).parts)}
        require({n for n, r in rows.items() if r['kind'] == 'directory'} == directories
                and all(r['kind'] in ('file', 'directory') for r in rows.values()), 'exact_installed_directories')
        for name, row in rows.items():
            require(row['uid'] == uid and row['gid'] == gid, 'operator_owned_package_objects')
            if row['kind'] == 'directory':
                require(row['mode'] == 0o755, 'package_directory_mode')
                continue
            require(row['links'] == 1, 'single_link_package_file')
            if name in expected:
                require(row['mode'] == (0o755 if expected[name]['executable'] else 0o644), 'package_file_mode')
                if name != record:
                    require((row['sha256'], row['bytes']) == (expected[name]['sha256'], expected[name]['bytes']),
                            'official_payload_bytes')
            else:
                require(row['mode'] == 0o644 and row['sha256'] == sha(generated[name])
                        and row['bytes'] == len(generated[name]), 'pip_generated_metadata')
        listed = {}
        for row in csv.reader(io.StringIO(module.listed_bytes(after['venv'], after['files'], record).decode())):
            require(len(row) == 3, 'installed_record_rows')
            target = SITE + '/' + row[0]
            require(target not in listed, 'unique_installed_record_rows')
            listed[target] = row
        require(set(listed) == files, 'installed_record_lists_every_file')
        for name, (_, digest, size) in listed.items():
            if name == record:
                require(digest == size == '', 'installed_record_self_row')
            else:
                require(digest == 'sha256=' + base64.urlsafe_b64encode(bytes.fromhex(rows[name]['sha256'])).decode()
                        .rstrip('=') and size == str(rows[name]['bytes']), 'installed_record_hashes')
        installed[package] = {'version': new_version, 'files': len(files), 'directories': len(directories),
                              'wheel_sha256': proven[package]['sha256']}
    stray_before = set(before['census']['unrecorded_bytecode'])
    stray_after = set(after['census']['unrecorded_bytecode'])
    removed = sorted(stray_before - stray_after)
    require(stray_after <= stray_before and all(owned_by_any(name) for name in removed), 'stray_bytecode_accounting')
    return {'changes': [{'name': p, 'old_version': o, 'new_version': n} for p, (o, n) in sorted(TRANSITIONS.items())],
            'installed': installed, 'other_distributions_unchanged': len(b), 'other_objects_exact': len(others_after),
            'unrecorded_bytecode_before': len(stray_before), 'unrecorded_bytecode_after': len(stray_after),
            'unrecorded_bytecode_removed_by_pip_uninstall': removed,
            'unrecorded_bytecode_retained': sorted(stray_after), 'no_downgrade': True}


def child_environment():
    # PIP_CONFIG_FILE=/dev/null and --isolated: no global, site or user configuration, index, proxy or credential.
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PIP_CONFIG_FILE': os.devnull,
            'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1'}


def interpreter(venv, arguments, *, timeout=120, recorder=None, runner=subprocess.run):
    """One child of the venv's own interpreter (-I -B), child umask 022, parent 077, bounded output."""
    require(umask() == 0o077, 'private_parent_umask')
    argv = [str(Path(venv) / 'bin/python'), '-I', '-B', *arguments]
    result = runner(argv, cwd=str(venv), env=child_environment(), capture_output=True, timeout=timeout,
                    umask=CHILD_UMASK)
    require(umask() == 0o077, 'parent_umask_unchanged')
    require(len(result.stdout) <= 1024 ** 2 and len(result.stderr) <= 1024 ** 2, 'bounded_child_output')
    if recorder is not None:
        recorder({'argv': argv, 'returncode': result.returncode, 'stdout': result.stdout.decode(errors='replace'),
                  'stderr': result.stderr.decode(errors='replace'), 'child_umask': '0022', 'parent_umask': '0077',
                  'network_index': False, 'dependencies_resolved': False})
    require(result.returncode == 0, 'venv_child_failed')
    return result.stdout


def pip_arguments(proven):
    return ['-m', 'pip', '--isolated', '--disable-pip-version-check', 'install', '--no-index', '--no-deps',
            '--no-cache-dir', '--no-compile', '--only-binary=:all:', '--force-reinstall',
            *[proven[package]['path'] for package in sorted(TRANSITIONS)]]


def checks(venv, after, *, runner=subprocess.run):
    """Imports and round trips in the venv itself, then pip's own dependency check."""
    value = json.loads(interpreter(venv, ['-c', CHECK_PROGRAM], runner=runner))
    site = Path(venv) / SITE
    expected = {'pypdf': TRANSITIONS['pypdf'][1], 'pypdf_file': str(site / 'pypdf/__init__.py'), 'pdf_roundtrip': True,
                'filelock': TRANSITIONS['filelock'][1], 'filelock_file': str(site / 'filelock/__init__.py'),
                'filelock_api': True, 'msgpack': [int(x) for x in TRANSITIONS['msgpack'][1].split('.')],
                'msgpack_extension': str(site / NATIVE['msgpack'][0]), 'msgpack_c_packer': True,
                'msgpack_roundtrip': True, 'cachecontrol_file_cache': str(site / 'cachecontrol/caches/file_cache.py'),
                'certifi_ca_sha256': after['files'][SITE + '/certifi/cacert.pem']['sha256'],
                'pillow': after['census']['distributions']['pillow'], 'png_roundtrip': True}
    require(value == expected, 'installed_versions_locations_and_round_trips')
    output = interpreter(venv, ['-m', 'pip', '--isolated', '--disable-pip-version-check', 'check'], runner=runner)
    require(output.strip() == b'No broken requirements found.', 'pip_check')
    return value


def install_once(venv, wheel_directory, before, *, drained, recorder, live=False, runner=subprocess.run):
    """THE dependency mutation: one pip process. The caller keeps the units drained and never retries.

    pip uninstalls and installs each requirement in turn and rolls back only the one that failed, so a failure
    part-way can leave an earlier package moved: the receipts say which, and nothing retries automatically.
    """
    module = footprint()
    venv = Path(venv)
    live_path = VENV.exists() and venv.exists() and os.path.samefile(venv, VENV)
    require(live is live_path and (not live or venv == VENV), 'live_venv_only_through_the_declared_act')
    require(umask() == 0o077, 'private_parent_umask')
    forward_only()
    require(drained() is True, 'owned_units_drained_before_pip')
    module.require_exact(before, module.snapshot(venv), 'venv_unchanged_since_its_snapshot')
    require(versions(before) == {p: pair[0] for p, pair in TRANSITIONS.items()}, 'old_versions_installed')
    proven = wheels(wheel_directory)
    interpreter(venv, pip_arguments(proven), timeout=PIP_TIMEOUT_SECONDS, recorder=recorder, runner=runner)
    require(drained() is True, 'owned_units_drained_after_pip')
    require(wheels(wheel_directory) == proven, 'wheels_unchanged_during_install')
    after = module.snapshot(venv)
    proof = transition(before, after, proven)
    proof['checks'] = checks(venv, after, runner=runner)
    module.require_exact(after, module.snapshot(venv), 'venv_stable_after_install')
    return after, proof


# ------------------------------------------------------------------------------------------ fetch (network)
def _get(url, accept=None):
    parsed = urllib.parse.urlparse(url)
    require(parsed.scheme == 'https' and parsed.hostname in ('pypi.org', FILE_HOST), 'official_pypi_host')
    request = urllib.request.Request(url, headers={'Accept': accept} if accept else {})
    with urllib.request.urlopen(request, timeout=60) as response:
        require(urllib.parse.urlparse(response.geturl()).hostname in ('pypi.org', FILE_HOST), 'official_redirect')
        data = response.read(MAX_WHEEL_BYTES + 1)
    require(len(data) <= MAX_WHEEL_BYTES, 'bounded_download')
    return data


def published(package, json_api, simple_index):
    """The pinned file as BOTH PyPI surfaces publish it: one entry each, same sha256 and size, not yanked."""
    pin = WHEELS[package]
    api = [row for row in json.loads(json_api)['urls'] if row['filename'] == pin['filename']]
    simple = [row for row in json.loads(simple_index)['files'] if row['filename'] == pin['filename']]
    require(len(api) == 1 and len(simple) == 1, 'one_published_file_per_surface')
    require(api[0]['digests']['sha256'] == simple[0]['hashes']['sha256'] == pin['sha256']
            and api[0]['size'] == pin['bytes'] and not api[0].get('yanked') and not simple[0].get('yanked'),
            'published_digest_equals_pin')
    url = api[0]['url']
    require(urllib.parse.urlparse(url).hostname == FILE_HOST and urllib.parse.urlparse(url).scheme == 'https',
            'official_file_host')
    return url


def fetch(directory, getter=_get):
    """Download the three wheels into a new private directory, each verified against both surfaces."""
    directory = Path(directory)
    require(directory.is_absolute() and not directory.exists(), 'new_wheel_directory')
    parent = directory.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) == 0o700,
            'private_wheel_parent')
    directory.mkdir(mode=0o700)
    evidence = {}
    for package in sorted(WHEELS):
        version = TRANSITIONS[package][1]
        api = getter(PYPI + '/pypi/' + package + '/' + version + '/json')
        simple = getter(PYPI + '/simple/' + package + '/', accept='application/vnd.pypi.simple.v1+json')
        url = published(package, api, simple)
        data = getter(url)
        require(len(data) == WHEELS[package]['bytes'] and sha(data) == WHEELS[package]['sha256'], 'downloaded_digest')
        target = directory / WHEELS[package]['filename']
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        evidence[package] = {'url': url, 'sha256': sha(data), 'bytes': len(data),
                             'json_api_sha256': sha(api), 'simple_index_sha256': sha(simple)}
    for package in WHEELS:
        wheel(directory / WHEELS[package]['filename'], package)
    return evidence


# ------------------------------------------------------------------------------------------------ calibrate
def save(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    raw = json.dumps(value, indent=1, sort_keys=True).encode() + b'\n'
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    return {'path': str(path), 'sha256': sha(raw)}


def calibrate(copy, wheel_directory, output, *, live_snapshot=None, runner=subprocess.run):
    """The whole stage on a COPY of the live venv; the live venv's footprint is proven unchanged around it."""
    module = footprint()
    copy, output = Path(copy), Path(output)
    require(copy.is_absolute() and copy.resolve(strict=True) == copy and not copy.is_relative_to(VENV)
            and not (VENV.exists() and os.path.samefile(copy, VENV)), 'calibration_runs_on_a_copy')
    require(output.is_absolute() and not output.exists(), 'new_calibration_output')
    parent = output.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) == 0o700,
            'private_calibration_parent')
    output.mkdir(mode=0o700)
    live_snapshot = live_snapshot or module.snapshot
    live_before = live_snapshot(VENV)
    before = module.snapshot(copy)
    pins = {'before': save(output / 'venv-copy-before.json', before)}
    process = {}

    def record(value):
        process['pin'] = save(output / 'pip-process.json', value)
        process['value'] = value
    after, proof = install_once(copy, wheel_directory, before, drained=lambda: True, recorder=record, runner=runner)
    pins['after'] = save(output / 'venv-copy-after.json', after)
    live_after = live_snapshot(VENV)
    module.require_exact(live_before, live_after, 'live_venv_touched_during_calibration')
    receipt = {'format': CALIBRATION_FORMAT, 'venv_copy': str(copy), 'live_venv': str(VENV),
               'live_venv_footprint_sha256': live_before['footprint_sha256'], 'live_venv_unchanged': True,
               'copy_before': module.summary(before), 'copy_after': module.summary(after),
               'copy_before_matches_live': before['census'] == live_before['census'],
               'pip_process': {'pin': process['pin'], 'argv': process['value']['argv'],
                               'returncode': process['value']['returncode']},
               'wheels': {p: {'filename': WHEELS[p]['filename'], 'sha256': WHEELS[p]['sha256']} for p in WHEELS},
               'transition': proof, 'snapshots': pins, 'units_drained': 'not applicable: a copy serves nothing',
               'helper_sha256': sha(Path(__file__).read_bytes()),
               'footprint_helper_sha256': sha(Path(module.__file__).read_bytes())}
    receipt['receipt'] = save(output / 'calibration-receipt.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = parser.add_subparsers(dest='command', required=True)
    f = sub.add_parser('fetch')
    f.add_argument('--wheels', required=True, type=Path)
    c = sub.add_parser('calibrate')
    c.add_argument('--venv-copy', required=True, type=Path)
    c.add_argument('--wheels', required=True, type=Path)
    c.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    os.umask(0o077)
    sys.dont_write_bytecode = True
    if args.command == 'fetch':
        print(json.dumps(fetch(args.wheels), indent=1, sort_keys=True))
        return 0
    receipt = calibrate(args.venv_copy, args.wheels, args.output)
    print(json.dumps({key: receipt[key] for key in ('live_venv_unchanged', 'copy_before', 'copy_after', 'pip_process',
                                                    'receipt')}, indent=1, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        code = main()
    except SystemExit:
        raise
    except Refusal as refusal:
        print(json.dumps({'complete': False, 'refused': str(refusal)}), file=sys.stderr)
        code = 1
    sys.exit(code)
