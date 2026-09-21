"""Bounded lifetime for trusted operator Docker helpers, not a Docker privilege broker.

A Docker client timeout does not stop its daemon-owned container. Each call owns
an unpredictable name/label, bounds transport before reading, and removes only a
verified immutable container ID. An in-container absolute alarm also survives
parent SIGKILL. It does not undo a systemd operation already sent to the host.
"""
import json
import math
import os
from pathlib import Path
import re
import secrets
import selectors
import signal
import stat
import subprocess
import threading
import time

DOCKER = '/usr/bin/docker'
IMAGE = 'sha256:9b84b0c75adf7a34fb1b00b406a50dc9f7bebd3bfbe3e7fd9ff168a6f9d0dfb9'
LABEL = 'org.quillmd.managed-helper'
ENV = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'DOCKER_HOST': 'unix:///run/docker.sock'}
MAX_INPUT = 2 * 1024 * 1024
MAX_RESULT = 2 * 1024 * 1024
MAX_STDERR = 65536
CONTROL_SECONDS = 8


class HelperFailure(RuntimeError):
    """Safe diagnostic only; never retains a subprocess or its sensitive output."""
    def __init__(self, reason, *, container_name=None, cleanup_complete=False, operation_reason=None):
        self.reason = reason
        self.container_name = container_name
        self.cleanup_complete = cleanup_complete
        self.operation_reason = operation_reason
        super().__init__('Managed helper refused or failed: ' + reason + '; protected output suppressed.')


def _stream(argv, data, seconds, stdout_limit, stderr_limit):
    """Read at most each permitted byte count plus a one-byte refusal sentinel."""
    process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, env=ENV)
    selector = selectors.DefaultSelector()
    output = {'stdout': bytearray(), 'stderr': bytearray()}
    limits = {'stdout': stdout_limit, 'stderr': stderr_limit}
    offset = 0
    deadline = time.monotonic() + seconds
    try:
        for pipe, name in ((process.stdout, 'stdout'), (process.stderr, 'stderr')):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        if data:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
        else:
            process.stdin.close()
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise HelperFailure('deadline')
            for key, _ in selector.select(min(remaining, 0.2)):
                pipe, name = key.fileobj, key.data
                if name == 'stdin':
                    try:
                        offset += os.write(pipe.fileno(), memoryview(data)[offset:offset + 65536])
                    except BrokenPipeError:
                        offset = len(data)
                    if offset == len(data):
                        selector.unregister(pipe)
                        pipe.close()
                    continue
                piece = os.read(pipe.fileno(), min(65536, limits[name] - len(output[name]) + 1))
                if not piece:
                    selector.unregister(pipe)
                    pipe.close()
                    continue
                if len(output[name]) + len(piece) > limits[name]:
                    raise HelperFailure('output_limit')
                output[name].extend(piece)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HelperFailure('deadline')
        try:
            code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise HelperFailure('deadline') from None
        # Return no stderr: it is never an operational data channel.
        return subprocess.CompletedProcess(argv, code, bytes(output['stdout']), b'')
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            raise HelperFailure('client_cleanup_failed') from None
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe and not pipe.closed:
                pipe.close()


def _control(argv):
    return _stream([DOCKER, *argv], b'', CONTROL_SECONDS, 65536, MAX_STDERR)


def _absent(name):
    # Positive-control the daemon; a failed inspect is not evidence of absence.
    result = _control(['container', 'ls', '--all', '--quiet', '--no-trunc',
                       '--filter', 'name=^/' + name + '$'])
    return result.returncode == 0 and not result.stdout.strip()


def cleanup(name, token):
    """Return only after removal/absence; a foreign replacement is never removed."""
    template = ('{"Id":{{json .Id}},"Name":{{json .Name}},"Image":{{json .Image}},'
                '"Token":{{json (index .Config.Labels "' + LABEL + '")}}}')
    result = _control(['inspect', '--type=container', '--format', template, name])
    if result.returncode:
        if _absent(name):
            return 'absent'
        raise HelperFailure('cleanup_unconfirmed')
    try:
        row = json.loads(result.stdout)
    except (ValueError, TypeError):
        raise HelperFailure('cleanup_identity_invalid') from None
    if (type(row) is not dict or set(row) != {'Id', 'Name', 'Image', 'Token'}
            or row['Name'] != '/' + name or row['Token'] != token or row['Image'] != IMAGE
            or not isinstance(row['Id'], str) or not re.fullmatch('[a-f0-9]{64}', row['Id'])):
        raise HelperFailure('cleanup_identity_mismatch')
    # Inspect by name, act by immutable ID: name reuse cannot target another task.
    removed = _control(['rm', '--force', row['Id']])
    if removed.returncode and not _absent(name):
        raise HelperFailure('cleanup_failed')
    if not _absent(name):
        raise HelperFailure('cleanup_unconfirmed')
    return 'removed'


def _prepared(argv, data, timeout, name, token):
    if (type(argv) is not list or any(type(part) is not str for part in argv)
            or argv[:2] not in (['docker', 'run'], [DOCKER, 'run'])
            or '--rm' not in argv or '--pull=never' not in argv or '--log-driver=none' not in argv
            or argv.count(IMAGE) != 1 or any(part.startswith(('--name', '--label', '--cidfile')) for part in argv)):
        raise HelperFailure('command_invalid')
    image_at = argv.index(IMAGE)
    command = argv[image_at + 1:]
    # Only the two existing Python protocols are supported; no shell or caller-selected image.
    if command not in (['python', '-'], ['python', '-B', '-']) and not (
            len(command) == 4 and command[:3] == ['python', '-B', '-c']):
        raise HelperFailure('command_invalid')
    deadline = time.time() + timeout
    alarm = ('import os,signal,time\n'
             'signal.signal(signal.SIGALRM,lambda *_: os._exit(124))\n'
             'signal.setitimer(signal.ITIMER_REAL,max(0.001,' + repr(deadline) + '-time.time()))\n')
    if command[-2:-1] == ['-c']:
        command[-1] = alarm + command[-1]
    else:
        # Python '-' reads all source before executing it. Arm in an argv
        # bootstrap first so interrupted/partial stdin cannot defer the alarm.
        bootstrap = (alarm + 'import sys\n'
                     'source=sys.stdin.buffer.read(' + str(MAX_INPUT + 1) + ')\n'
                     'if len(source)>' + str(MAX_INPUT) + ': os._exit(125)\n'
                     'exec(compile(source,"<quillmd-managed-stdin>","exec"))\n')
        command = ['python', '-B', '-c', bootstrap]
    arguments = [DOCKER, 'run', '--name', name, '--label', LABEL + '=' + token,
                 *argv[2:image_at], IMAGE, *command]
    return arguments, data


def _failure_receipt(directory, token, failure):
    """Keep a redacted cleanup record when outer callers suppress exception text."""
    path = Path(directory)
    if not path.is_absolute() or path.resolve() != path:
        raise HelperFailure('failure_receipt_unsafe')
    parent = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(parent)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise HelperFailure('failure_receipt_unsafe')
        fd = os.open('helper-failure-' + token + '.json',
                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        record = {'version': 1, 'kind': 'managed-helper-failure',
                  'recorded_at_epoch_seconds': time.time(), 'reason': failure.reason,
                  'operation_reason': failure.operation_reason,
                  'container_name': failure.container_name,
                  'cleanup_complete': failure.cleanup_complete}
        with os.fdopen(fd, 'w') as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)


def run_helper(argv, *, input=b'', timeout, max_stdout=MAX_RESULT, failure_directory=None):
    """Trusted generated Python only; output is returned only after verified cleanup."""
    if (type(input) is not bytes or len(input) > MAX_INPUT or type(timeout) not in (int, float)
            or not math.isfinite(timeout) or not 0 < timeout <= 1100
            or type(max_stdout) is not int or not 0 < max_stdout <= 256 * 1024 * 1024 + 257):
        raise HelperFailure('bounds_invalid')
    token = secrets.token_hex(16)
    name = 'quillmd-helper-' + token
    arguments, data = _prepared(argv, input, timeout, name, token)
    old_term = None
    if threading.current_thread() is threading.main_thread():
        old_term = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(HelperFailure('interrupted')))
    result, failure = None, None
    cleanup_state = None
    try:
        try:
            result = _stream(arguments, data, timeout, max_stdout, MAX_STDERR)
            if result.returncode:
                raise HelperFailure('helper_exit')
        except BaseException as error:
            failure = error
        try:
            cleanup_state = cleanup(name, token)
        except BaseException:
            original = failure.reason if isinstance(failure, HelperFailure) else (
                'interrupted_or_transport_failed' if failure is not None else None)
            raise HelperFailure('cleanup_failed', container_name=name, cleanup_complete=False,
                                operation_reason=original) from None
        if failure is not None:
            reason = failure.reason if isinstance(failure, HelperFailure) else 'interrupted_or_transport_failed'
            # A killed client may have lost the daemon's create acknowledgement.
            # Empty listing alone does not prove a queued create cannot complete.
            raise HelperFailure(reason, container_name=name,
                                cleanup_complete=cleanup_state == 'removed') from None
        result.helper_container = name
        result.helper_cleanup_complete = True
        result.helper_cleanup_state = cleanup_state
        return result
    except HelperFailure as error:
        if failure_directory is not None:
            try:
                _failure_receipt(failure_directory, token, error)
            except Exception:
                raise HelperFailure('failure_receipt_failed', container_name=name,
                                    cleanup_complete=error.cleanup_complete,
                                    operation_reason=error.reason) from None
        raise
    finally:
        if old_term is not None:
            signal.signal(signal.SIGTERM, old_term)
