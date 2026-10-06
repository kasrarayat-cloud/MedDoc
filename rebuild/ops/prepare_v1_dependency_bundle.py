"""Recover the exact reviewed wheels and test them in one task-owned venv.

Default is preparation only. This reversible step never changes the installed
interpreter, source, services, database, credentials or shared cache. No network
is needed: the complete retained wheel inventory must validate before copying.
The integration owner controls any later declared installed-venv promotion.
"""
import argparse
import email
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
import zipfile

from ops import dependency_lock as lock

ROOT = Path('/opt/meddoc-pro')
CACHE = ROOT / 'rebuild/.runtime/v1-word-corpus/custodian-20260927/dependency-lock-repair-20260928/wheelhouse'
OUTPUT = ROOT / 'rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations/private-dependencies-20261004'
MAX_BYTES = 2_000_000_000
DEADLINE_SECONDS = 600


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, raw):
    if not isinstance(raw, bytes):
        raw = (json.dumps(raw, indent=2, sort_keys=True) + '\n').encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    require(sha(path.read_bytes()) == sha(raw), 'Retained bytes changed.')


def size(path):
    total = 0
    for directory, names, files in os.walk(path, followlinks=False):
        require(all(not (Path(directory) / name).is_symlink()
                    or (Path(directory) / name).resolve().is_relative_to(path)
                    for name in names), 'Owned asset has an external linked directory.')
        for name in files:
            item = Path(directory) / name
            # venv --copies still creates conventional lib64/interpreter links
            # on some Python builds. Links do not copy or charge target bytes.
            if item.is_symlink():
                require(item.resolve().is_relative_to(path), 'Owned asset has an external linked file.')
                continue
            try:
                total += item.stat().st_size
            except FileNotFoundError:
                # pip atomically publishes/removes temporary files while this
                # monitor walks our own directory. An already removed file
                # consumes no bytes; other filesystem errors still stop work.
                continue
    return total


def bounded(command, label, directory, *, deadline):
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC',
        'HOME': str(directory / 'home'), 'TMPDIR': str(directory / 'tmp'),
        'PIP_CONFIG_FILE': '/dev/null', 'PIP_NO_CACHE_DIR': '1', 'PYTHONDONTWRITEBYTECODE': '1',
        'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
    log = directory / (label + '.log')
    with open(log, 'xb') as stream:
        os.chmod(log, 0o600)
        process = subprocess.Popen(command, cwd=directory, env=environment,
            stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
        reason = monitor_error = None
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    reason = 'technical_deadline'
                elif size(directory) > MAX_BYTES:
                    reason = 'owned_growth_bound'
                if reason:
                    break
                time.sleep(0.2)
        except BaseException as error:
            reason = 'owned_monitor_failure'
            monitor_error = error
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
    try:
        owned_bytes = size(directory)
    except BaseException as error:
        owned_bytes = None
        reason = reason or 'owned_monitor_failure'
        monitor_error = monitor_error or error
    record = {'step': label, 'exit_code': process.returncode, 'stop_reason': reason,
              'log_sha256': sha(log.read_bytes()), 'owned_bytes': owned_bytes}
    if monitor_error is not None:
        import traceback
        raw = ''.join(traceback.format_exception(type(monitor_error), monitor_error,
                    monitor_error.__traceback__)).encode()
        write(directory / (label + '-monitor-failure.txt'), raw)
        record['monitor_failure'] = {'kind': type(monitor_error).__name__, 'original_sha256': sha(raw)}
    write(directory / (label + '.json'), record)
    require(process.returncode == 0 and reason is None and owned_bytes is not None and owned_bytes <= MAX_BYTES,
            'Owned dependency verification failed; inspect protected step evidence.')
    return record


def offline_lock(raw):
    old = lock.MODEL_REQUIREMENT + ' --hash=sha256:' + lock.MODEL_SHA256
    require(raw.decode().count(old) == 1, 'Exact reviewed model source line required.')
    # --no-index does not disable direct URL requirements. This hash-identical
    # projection changes only that model locator to its verified local wheel.
    return raw.replace(old.encode(), (lock.MODEL_NAME + '==' + lock.MODEL_VERSION
        + ' --hash=sha256:' + lock.MODEL_SHA256).encode())


def wheel_metadata(path, artifact):
    with zipfile.ZipFile(path) as archive:
        entries = [name for name in archive.namelist()
                   if name.endswith('.dist-info/METADATA') and len(Path(name).parts) == 2]
        require(len(entries) == 1, 'Single wheel metadata required.')
        raw = archive.read(entries[0]); metadata = email.message_from_bytes(raw)
        require(lock.canonical(metadata['Name']) == lock.canonical(artifact['name'])
                and metadata['Version'] == artifact['version'], 'Wheel internal package identity differs.')
        license_text = metadata.get('License')
        return {'metadata_sha256': sha(raw), 'license_expression': metadata.get('License-Expression'),
            'license_text': license_text[:1024] if license_text else None,
            'license_text_sha256': sha(license_text.encode()) if license_text else None,
            'license_classifiers': [value for value in metadata.get_all('Classifier', []) if value.startswith('License ::')],
            'license_files': {name: sha(archive.read(name)) for name in archive.namelist()
                if '/licenses/' in name or name.rsplit('/', 1)[-1].upper().startswith(('LICENSE', 'COPYING'))}}


def prepare(source, expected, run_id):
    require(isinstance(run_id, str) and re.fullmatch('[a-z0-9][a-z0-9-]{1,55}', run_id), 'Distinct bounded run identity required.')
    directory = OUTPUT.parent / (OUTPUT.name + '-' + run_id)
    require(source == source.resolve() and source.is_relative_to(ROOT / '.worktrees')
            and re.fullmatch('[a-f0-9]{40}', expected), 'Exact isolated source identity required.')
    require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, timeout=20).decode().strip() == expected
        and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, timeout=20), 'Freeze exact clean dependency source.')
    app = source / 'rebuild'
    names = ('requirements.txt', 'requirements-production.lock', 'requirements-production.manifest.json')
    sources = {name: (app / name).read_bytes() for name in names}
    for name, raw in sources.items():
        require(subprocess.check_output(['git', 'show', expected + ':rebuild/' + name], cwd=source, timeout=20) == raw,
                'Committed dependency bytes differ.')
    summary = lock.verify(app, CACHE)
    manifest = json.loads(sources['requirements-production.manifest.json'])
    for artifact in manifest['artifacts']:
        path = CACHE / artifact['filename']; info = path.lstat()
        require(not path.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and info.st_uid == os.getuid(), 'Retained reviewed wheel has unsafe metadata.')
    require(not directory.exists() and directory.resolve() == directory, 'Never overwrite a previous owned dependency packet.')
    require(os.statvfs(directory.parent).f_bavail * os.statvfs(directory.parent).f_frsize > 8 * 1024 ** 3,
            'Preserve at least 8 GiB headroom for bounded preparation.')
    directory.mkdir(mode=0o700)
    for name in ('wheelhouse', 'home', 'tmp'):
        (directory / name).mkdir(mode=0o700)
    started = time.monotonic(); deadline = started + DEADLINE_SECONDS
    record = {'source_commit': expected, 'run_id': run_id, 'root': str(directory),
        'source_sha256': {name: sha(raw) for name, raw in sources.items()},
        'reviewed_cache': str(CACHE), 'packages': summary['packages'], 'complete': False,
        'max_owned_bytes': MAX_BYTES, 'deadline_seconds': DEADLINE_SECONDS,
        'network_requests': 0, 'installed_mutation_performed': False, 'provider_calls': 0, 'steps': []}
    try:
        artifacts = []
        for artifact in manifest['artifacts']:
            raw = (CACHE / artifact['filename']).read_bytes()
            require(len(raw) == artifact['bytes'] and sha(raw) == artifact['sha256'], 'Retained wheel changed before copy.')
            write(directory / 'wheelhouse' / artifact['filename'], raw)
            artifacts.append({**artifact, **wheel_metadata(directory / 'wheelhouse' / artifact['filename'], artifact)})
            require(time.monotonic() < deadline and size(directory) <= MAX_BYTES, 'Bounded wheel copy exceeded.')
        for name, raw in sources.items():
            write(directory / name, raw)
        write(directory / 'offline.lock', offline_lock(sources['requirements-production.lock']))
        lock.verify(directory, directory / 'wheelhouse')
        write(directory / 'wheel-manifest.json', {'reviewed_artifacts': artifacts,
            'license_limit': 'Observed wheel metadata and retained license-file hashes; no new legal approval is inferred.'})
        python = directory / 'verified-venv/bin/python'
        record['steps'].append(bounded(['/usr/bin/python3', '-B', '-m', 'venv', '--copies',
            str(directory / 'verified-venv')], 'create-owned-venv', directory, deadline=deadline))
        network_guard = ('import socket\n'
            'def refuse(*args,**kwargs): raise RuntimeError("Offline dependency verification forbids network")\n'
            'socket.socket.connect=refuse\n')
        installer = network_guard + ('from pip._internal.cli.main import main\nraise SystemExit(main('
            + repr(['install', '--no-index', '--only-binary=:all:', '--require-hashes', '--no-compile', '--find-links',
                    str(directory / 'wheelhouse'), '-r', str(directory / 'offline.lock')]) + '))\n')
        record['steps'].append(bounded([str(python), '-B', '-c', installer], 'offline-install', directory, deadline=deadline))
        checker = network_guard + 'from pip._internal.cli.main import main\nraise SystemExit(main(["check"]))\n'
        record['steps'].append(bounded([str(python), '-B', '-c', checker], 'pip-check', directory, deadline=deadline))
        native = network_guard + (
            'import importlib.metadata as m,json,sys\nimport numpy,spacy,cymem,murmurhash,preshed,blis,thinc,srsly,wrapt\n'
            'assert spacy.__version__=="3.8.16"\nnlp=spacy.load("en_core_web_sm")\n'
            'assert nlp.meta["version"]=="3.8.0"\ndoc=nlp("The patient reports cough and denies fever.")\n'
            'assert doc.has_annotation("DEP") and len(doc)>5\n'
            'print(json.dumps({"python":sys.version.split()[0],"spacy":spacy.__version__,"model":nlp.meta["version"],'
            '"native_imports":True,"synthetic_parser_tokens":len(doc),"pip":m.version("pip")}))\n')
        record['steps'].append(bounded([str(python), '-B', '-c', native], 'native-model', directory, deadline=deadline))
        require({name: (app / name).read_bytes() for name in names} == sources, 'Dependency source changed during preparation.')
        lock.verify(app, CACHE); lock.verify(directory, directory / 'wheelhouse')
        record.update(complete=True, elapsed_seconds=time.monotonic() - started, owned_bytes=size(directory))
        write(directory / 'result.json', record)
        return record
    except BaseException as error:
        import traceback
        write(directory / 'original-failure.txt', traceback.format_exc().encode())
        record.update(complete=False, failure_kind=type(error).__name__, elapsed_seconds=time.monotonic() - started,
                      owned_bytes=size(directory))
        write(directory / 'result.json', record)
        raise RuntimeError('Owned dependency preparation failed; preserve and inspect its protected original evidence.') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--expected-commit')
    parser.add_argument('--run-id')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'prepared_only': True, 'installed_mutation_performed': False,
            'network_requests': 0, 'max_owned_bytes': MAX_BYTES, 'deadline_seconds': DEADLINE_SECONDS}))
        return
    require(args.source is not None and args.expected_commit is not None and args.run_id is not None, 'Confirmed source/run required.')
    print(json.dumps(prepare(args.source, args.expected_commit, args.run_id), sort_keys=True))


if __name__ == '__main__':
    main()
