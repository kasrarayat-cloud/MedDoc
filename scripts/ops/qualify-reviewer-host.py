#!/usr/bin/env python3
"""Bounded actual-host SSH qualification. Requires root; never changes shared sshd.

Creates only two named synthetic accounts and exact transient service units. Run
only through the recorded project scope/privileged launcher, not on an arbitrary
host. All tests use synthetic owned sockets or read-only app health requests.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import grp
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shlex
import shutil
import signal
import socket
import socketserver
import stat
import subprocess
import sys
import threading
import time

SUBJECT = 'quillmd-reviewer'
CONTROL = 'quillmd-review-ctl'
UNITS = ['ssh.service', 'quillmd-fresh-doctor.service', 'quillmd-fresh-admin.service', 'quillmd-fresh-worker.service']
EXPECTED_RELEASE = 'dc4eb42ce021e436a3b717eb40edb10ace8e662c'
ALGORITHMS = ('ciphers', 'macs', 'kexalgorithms', 'hostkeyalgorithms', 'pubkeyacceptedalgorithms', 'casignaturealgorithms')


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, *, check=True, input=None, timeout=15):
    result = subprocess.run([str(x) for x in args], input=input, capture_output=True, timeout=timeout)
    if check and result.returncode:
        # Callers never put passwords/key material in arguments; do not print input.
        raise RuntimeError(f'{args[0]} exit {result.returncode}: {result.stderr.decode(errors="replace")[:1500]}')
    return result


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def process_identity(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        rest = raw[raw.rfind(')') + 2:].split()
        return {'pid': int(pid), 'start_ticks': rest[19], 'uid': Path(f'/proc/{pid}').stat().st_uid}
    except (OSError, IndexError):
        return None


def shared_state():
    services = {}
    for unit in UNITS:
        values = command(['systemctl', 'show', unit, '-p', 'Id', '-p', 'MainPID', '-p', 'ActiveState'], check=False).stdout.decode().splitlines()
        item = dict(line.split('=', 1) for line in values if '=' in line)
        item['process'] = process_identity(int(item.get('MainPID', '0')))
        services[unit] = item
    ssh_processes = []
    for directory in Path('/proc').iterdir():
        if directory.name.isdigit():
            try:
                if (directory / 'comm').read_text().strip() == 'sshd':
                    identity = process_identity(int(directory.name))
                    if identity:
                        ssh_processes.append(identity)
            except OSError:
                pass
    return {'services': services, 'sshd_processes': ssh_processes}


def config_hashes():
    """Hash main config and recursive Include matches; never host private keys."""
    import glob
    found = {}

    def visit(path):
        path = Path(path).resolve(strict=True)
        if str(path) in found:
            return
        if not path.is_file():
            raise RuntimeError('SSH configuration Include is not a regular file')
        content = path.read_text()
        found[str(path)] = digest(path)
        for line in content.splitlines():
            words = shlex.split(line, comments=True)
            if words and words[0].lower() == 'include':
                for pattern in words[1:]:
                    if not pattern.startswith('/'):
                        pattern = str(Path('/etc/ssh') / pattern)
                    for child in sorted(glob.glob(pattern)):
                        visit(child)
    visit('/etc/ssh/sshd_config')
    return found


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        try:
            self.request.sendall(self.request.recv(128))
        except OSError:
            pass


class Harness:
    def __init__(self, evidence, run_id):
        self.evidence = evidence
        self.run_id = run_id
        self.runtime = Path('/run') / f'quillmd-reviewer-qual-{run_id}'
        self.accounts = {}
        self.pending_accounts = {}
        self.services = []
        self.clients = []
        self.sockets = []
        self.servers = []
        self.created_runtime = False
        self.started = time.monotonic()
        self.next_request = 0.0
        self.report = {'run_id': run_id, 'started_at': utc(), 'scope': 'Actual host, project-specific root sshd services with normal privilege separation; shared SSH policy unchanged; synthetic identities and read-only app health only.', 'checks': [], 'failures': [], 'cleanup': {}}

    def save(self, name, data):
        path = self.evidence / name
        if path.exists() or path.is_symlink():
            raise RuntimeError(f'evidence already exists: {name}')
        raw = data if isinstance(data, bytes) else (data if isinstance(data, str) else json.dumps(data, indent=2) + '\n').encode()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        return path

    def event(self, name, passed, detail=None):
        item = {'at': utc(), 'name': name, 'passed': bool(passed), 'detail': detail}
        self.report['checks'].append(item)
        fd = os.open(self.evidence / 'events.jsonl', os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as stream:
            stream.write(json.dumps(item) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        if not passed:
            raise AssertionError(name)

    def account(self, name):
        home = self.runtime / f'home-{name}'
        home.mkdir(mode=0o755)
        home.chmod(0o755)
        marker = f'QuillMD synthetic qualification {self.run_id}'
        self.pending_accounts[name] = {'home': str(home), 'comment': marker}
        command(['useradd', '--system', '--user-group', '--no-create-home', '--comment', marker, '--home-dir', home, '--shell', '/usr/sbin/nologin', name])
        entry = pwd.getpwnam(name)
        self.accounts[name] = {'uid': entry.pw_uid, 'gid': entry.pw_gid, 'home': str(home)}
        # Unlock only this synthetic system account with an unknowable password.
        # Public-key-only sshd plus nologin prohibit interactive/password access.
        password = secrets.token_urlsafe(64).encode()
        hashed = command(['openssl', 'passwd', '-6', '-stdin'], input=password + b'\n').stdout.strip()
        command(['chpasswd', '-e'], input=name.encode() + b':' + hashed + b'\n')
        del password, hashed
        self.event(f'{name}: identity isolated', not entry.pw_uid == 0 and os.getgrouplist(name, entry.pw_gid) == [entry.pw_gid], {'uid': entry.pw_uid, 'gid': entry.pw_gid, 'shell': entry.pw_shell, 'home_owner': home.stat().st_uid})

    def effective(self, config, username, port, address, label):
        context = f'user={username},host=localhost,addr={address},laddr=127.0.0.1,lport={port}'
        args = ['/usr/sbin/sshd', '-T']
        if config:
            args += ['-f', str(config)]
        output = command([*args, '-C', context]).stdout
        self.save(label + '.txt', output)
        return dict(line.split(' ', 1) for line in output.decode().splitlines() if ' ' in line)

    def setup(self):
        if os.geteuid() != 0:
            raise RuntimeError('root required')
        for name in (SUBJECT, CONTROL):
            try:
                pwd.getpwnam(name)
            except KeyError:
                pass
            else:
                raise RuntimeError(f'refused pre-existing account: {name}')
            try:
                grp.getgrnam(name)
            except KeyError:
                pass
            else:
                raise RuntimeError(f'refused pre-existing group: {name}')
        if self.runtime.exists() or self.runtime.is_symlink():
            raise RuntimeError('refused pre-existing runtime path')
        for role in ('subject', 'control'):
            unit = f'quillmd-reviewer-qual-{self.run_id}-{role}.service'
            state = command(['systemctl', 'show', unit, '-p', 'LoadState', '--value'], check=False).stdout.decode().strip()
            if state and state != 'not-found':
                raise RuntimeError('refused pre-existing transient unit')
        self.report['shared_before'] = shared_state()
        self.report['config_hashes_before'] = config_hashes()
        command(['/usr/sbin/sshd', '-t'])
        self.event('shared sshd full configuration syntax', True)
        self.runtime.mkdir(mode=0o755)
        self.created_runtime = True
        self.runtime.chmod(0o755)
        (self.runtime / 'private').mkdir(mode=0o700)
        self.account(SUBJECT)
        self.account(CONTROL)
        self.shared_effective = self.effective(None, SUBJECT, 22, '127.0.0.1', 'shared-effective-subject-loopback')
        self.effective(None, SUBJECT, 22, '192.0.2.10', 'shared-effective-subject-hypothetical-source')
        self.event('shared-context captured, not granted', True, {'real_source': '127.0.0.1', 'hypothetical_source': '192.0.2.10', 'port': 22, 'future_reviewer_context_requires_actual_source': True})
        for key in ('host', 'subject', 'control'):
            command(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', self.runtime / 'private' / key])
        helper = Path(__file__).with_name('reviewer-tunnel-access.sh')
        source = helper.read_text()
        match = re.search(r"cat > \"\$prepared/sshd-match.conf\" <<'POLICY'\n(.*?)\nPOLICY", source, re.S)
        if not match:
            raise RuntimeError('could not locate literal reviewed Match policy')
        self.policy = match.group(1) + '\n'
        self.report['helper_sha256'] = digest(helper)
        self.report['harness_sha256'] = digest(__file__)
        self.save('subject-reviewed-match-policy.conf', self.policy)
        expiry = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=8)).strftime('%Y%m%d%H%M%SZ')
        key = (self.runtime / 'private/subject.pub').read_text().split()
        self.subject_key = f'restrict,port-forwarding,expiry-time="{expiry}",permitopen="127.0.0.1:9130",permitopen="127.0.0.1:9131",command="/bin/false" {key[0]} {key[1]} quillmd-synthetic-{self.run_id}\n'
        self.subject_auth = self.runtime / 'subject-authorized_keys'
        self.subject_auth.write_text(self.subject_key)
        self.subject_auth.chmod(0o644)
        control_key = (self.runtime / 'private/control.pub').read_text().split()
        (self.runtime / 'control-authorized_keys').write_text(f'restrict,port-forwarding,expiry-time="{expiry}",permitopen="127.0.0.1:9130",command="/bin/false" {control_key[0]} {control_key[1]} quillmd-control-{self.run_id}\n')
        (self.runtime / 'control-authorized_keys').chmod(0o644)
        self.save('subject-authorized-key-public.txt', self.subject_key)
        self.report['account_records'] = dict(self.accounts)
        self.ports = {'subject': free_port(), 'control': free_port()}
        while self.ports['control'] == self.ports['subject']:
            self.ports['control'] = free_port()
        hostkey = ' '.join((self.runtime / 'private/host.pub').read_text().split()[:2])
        self.known_hosts = self.runtime / 'private/known_hosts'
        self.known_hosts.write_text(''.join(f'[127.0.0.1]:{port} {hostkey}\n' for port in self.ports.values()))
        for path in Path('/etc/ssh').glob('ssh_host_*_key.pub'):
            public = ' '.join(path.read_text().split()[:2])
            with self.known_hosts.open('a') as stream:
                stream.write(f'127.0.0.1 {public}\n')
        self.known_hosts.chmod(0o600)
        for role, username in (('subject', SUBJECT), ('control', CONTROL)):
            policy = self.policy if role == 'subject' else '''Match User quillmd-review-ctl
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowTcpForwarding local
    AllowStreamLocalForwarding yes
    PermitOpen 127.0.0.1:9130
    PermitListen none
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PermitUserRC no
    PermitTunnel no
    MaxSessions 0
    ForceCommand /bin/false
Match all
'''
            config = f'''Port {self.ports[role]}
ListenAddress 127.0.0.1
HostKey {self.runtime}/private/host
AuthorizedKeysFile {self.runtime}/{role}-authorized_keys
AuthorizedKeysCommand none
AuthorizedPrincipalsFile none
AuthorizedPrincipalsCommand none
TrustedUserCAKeys none
PidFile {self.runtime}/{role}.pid
UsePAM no
PasswordAuthentication no
KbdInteractiveAuthentication no
StrictModes yes
LogLevel VERBOSE
AllowUsers {username}
''' + ''.join(f'{name} {self.shared_effective[name]}\n' for name in ALGORITHMS) + policy
            path = self.runtime / f'{role}-sshd.conf'
            path.write_text(config)
            path.chmod(0o600)
            self.save(f'{role}-sshd.conf', config)
            command(['/usr/sbin/sshd', '-t', '-f', path])
            effective = self.effective(path, username, self.ports[role], '127.0.0.1', f'{role}-effective-loopback')
            self.effective(path, username, self.ports[role], '192.0.2.10', f'{role}-effective-hypothetical-source')
            self.event(f'{role}: inherited cryptographic algorithms', all(effective[name] == self.shared_effective[name] for name in ALGORITHMS))
            if role == 'subject':
                expected = {'authenticationmethods': 'publickey', 'passwordauthentication': 'no', 'kbdinteractiveauthentication': 'no', 'allowtcpforwarding': 'local', 'allowstreamlocalforwarding': 'no', 'permitopen': '127.0.0.1:9130 127.0.0.1:9131', 'permitlisten': 'none', 'maxsessions': '0', 'forcecommand': '/bin/false', 'permittty': 'no', 'permituserrc': 'no', 'allowagentforwarding': 'no', 'x11forwarding': 'no', 'permittunnel': 'no', 'strictmodes': 'yes'}
                self.event('subject effective server restrictions', all(effective.get(name) == value for name, value in expected.items()), {name: effective.get(name) for name in expected})
                auth_expected = {'authorizedkeysfile': str(self.subject_auth), 'authorizedkeyscommand': 'none', 'authorizedprincipalsfile': 'none', 'authorizedprincipalscommand': 'none', 'trustedusercakeys': 'none'}
                self.event('subject effective authorization sources restricted', all(effective.get(name) == value for name, value in auth_expected.items()), {name: effective.get(name) for name in auth_expected})
                self.event('subject authorization root owned and home has no keys', self.subject_auth.stat().st_uid == 0 and stat.S_IMODE(self.subject_auth.stat().st_mode) == 0o644 and not (Path(self.accounts[SUBJECT]['home']) / '.ssh').exists())
            self.start_service(role)
        tcp = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Echo)
        unix_path = self.runtime / 'owned-target.sock'
        unix = socketserver.ThreadingUnixStreamServer(str(unix_path), Echo)
        unix_path.chmod(0o666)
        for server in (tcp, unix):
            server.daemon_threads = True
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.servers.append(server)
        self.echo_port = tcp.server_address[1]
        self.unix_target = unix_path
        self.event('owned denial-target TCP positive control', self.echo(port=self.echo_port) == b'quillmd-owned-synthetic')

    def unit(self, role):
        return f'quillmd-reviewer-qual-{self.run_id}-{role}.service'

    def start_service(self, role):
        unit = self.unit(role)
        if unit not in self.services:
            self.services.append(unit)  # Cleanup even if systemd-run partially succeeds.
        command(['systemd-run', '--quiet', '--collect', '--unit', unit, '--property', 'KillMode=control-group', '--property', 'RuntimeMaxSec=180', '--property', 'TimeoutStopSec=5', '/usr/sbin/sshd', '-D', '-e', '-f', self.runtime / f'{role}-sshd.conf'])
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', self.ports[role]), timeout=.2):
                    break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError(f'{role} sshd did not listen')
        props = dict(line.split('=', 1) for line in command(['systemctl', 'show', unit, '-p', 'MainPID', '-p', 'ControlGroup', '-p', 'KillMode', '-p', 'RuntimeMaxUSec']).stdout.decode().splitlines())
        identity = process_identity(int(props['MainPID']))
        self.event(f'{role}: normal host root sshd started', identity is not None and identity['uid'] == 0 and props['KillMode'] == 'control-group', {'unit': props, 'process': identity})
        descriptors = set()
        for path in Path(f"/proc/{identity['pid']}/fd").iterdir():
            try:
                descriptors.add(os.readlink(path))
            except FileNotFoundError:
                pass
        owned_listeners = []
        for family in ('tcp', 'tcp6'):
            for line in (Path('/proc/net') / family).read_text().splitlines()[1:]:
                fields = line.split()
                if fields[3] == '0A' and f'socket:[{fields[9]}]' in descriptors:
                    owned_listeners.append({'family': family, 'local_address_hex': fields[1], 'inode': fields[9]})
        self.event(f'{role}: only owned listener is approved loopback socket', len(owned_listeners) == 1 and owned_listeners[0]['family'] == 'tcp' and owned_listeners[0]['local_address_hex'] == f'0100007F:{self.ports[role]:04X}', {'address': '127.0.0.1', 'port': self.ports[role], 'listeners': owned_listeners, 'pid': identity['pid']})

    def ssh_args(self, role):
        name = SUBJECT if role == 'subject' else CONTROL
        return ['ssh', '-F', '/dev/null', '-p', str(self.ports[role]), '-i', str(self.runtime / 'private' / role), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'PreferredAuthentications=publickey', '-o', 'StrictHostKeyChecking=yes', '-o', f'UserKnownHostsFile={self.known_hosts}', '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=2', '-o', 'ExitOnForwardFailure=yes'], f'{name}@127.0.0.1'

    def ssh(self, role, *options, data=None, remote_command=None):
        base, target = self.ssh_args(role)
        return command([*base, *options, target, *([remote_command] if remote_command else [])], input=data, check=False, timeout=5)

    def forward(self, role, *options):
        base, target = self.ssh_args(role)
        error_path = self.evidence / f'client-{role}-{len(self.clients)}.stderr'
        handle = error_path.open('xb')
        error_path.chmod(0o600)
        process = subprocess.Popen([*base, '-vv', '-N', *options, target], stdout=subprocess.DEVNULL, stderr=handle)
        process.quillmd_log = error_path
        self.clients.append((process, handle))
        time.sleep(.15)
        return process

    def throttle(self):
        delay = self.next_request - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.next_request = time.monotonic() + .55

    def request_bytes(self):
        self.throttle()
        return b'GET /health/ HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n'

    def parse_health(self, response):
        headers, _, body = response.partition(b'\r\n\r\n')
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeError):
            return False, {'status_line': [line.decode(errors='replace') for line in headers.splitlines()[:1]], 'body_length': len(body)}
        status = headers.splitlines()[0].decode()
        return (' 200 ' in status and payload.get('data_mode') == 'synthetic-only' and payload.get('release') == EXPECTED_RELEASE), {'status_line': status, 'payload': payload}

    def health_direct(self, role, destination, name):
        result = self.ssh(role, '-W', destination, data=self.request_bytes())
        okay, detail = self.parse_health(result.stdout)
        if not okay:
            detail = {'status': str(detail), 'ssh_exit': result.returncode, 'stderr': result.stderr.decode(errors='replace')}
        self.event(name, result.returncode == 0 and okay, detail)

    def denied(self, result, name, token=b'administratively prohibited'):
        self.event(name, result.returncode != 0 and token in result.stderr and not result.stdout, {'exit': result.returncode, 'stderr': result.stderr.decode(errors='replace')})

    def connect(self, *, port=None, path=None):
        deadline = time.monotonic() + 3
        while True:
            sock = socket.socket(socket.AF_UNIX if path else socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                sock.connect(str(path) if path else ('127.0.0.1', port))
                return sock
            except (FileNotFoundError, ConnectionRefusedError):
                sock.close()
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.03)

    def echo(self, *, port=None, path=None):
        with self.connect(port=port, path=path) as sock:
            sock.sendall(b'quillmd-owned-synthetic')
            try:
                return sock.recv(128)
            except ConnectionResetError:
                return b''

    def health_forward(self, *, port=None, path=None):
        with self.connect(port=port, path=path) as sock:
            sock.sendall(self.request_bytes())
            chunks = []
            while True:
                data = sock.recv(8192)
                if not data:
                    break
                chunks.append(data)
            return self.parse_health(b''.join(chunks))

    def stop_client(self, process):
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=4)

    def run_checks(self):
        base, target = self.ssh_args('subject')
        base[base.index('-p') + 1] = '22'
        self.denied(command([*base, '-W', '127.0.0.1:9130', target], input=b'synthetic', check=False, timeout=5), 'temporary project key rejected by shared host port22', b'Permission denied')
        self.health_direct('subject', '127.0.0.1:9130', 'approved doctor destination actual health')
        self.health_direct('subject', '127.0.0.1:9131', 'approved admin destination actual health')
        self.denied(self.ssh('subject', '-W', f'127.0.0.1:{self.echo_port}', data=b'synthetic'), 'other owned TCP destination denied')
        self.denied(self.ssh('subject', '-W', 'localhost:9130', data=b'synthetic'), 'unapproved hostname spelling denied')
        self.denied(self.ssh('subject', '-N', '-R', f'127.0.0.1:{free_port()}:127.0.0.1:{self.echo_port}'), 'remote TCP denied', b'remote port forwarding failed')
        self.denied(self.ssh('subject', remote_command='true'), 'shell session denied', b'open failed')
        self.denied(self.ssh('subject', '-s', remote_command='sftp'), 'SFTP subsystem denied', b'open failed')
        # Positive and negative controls use the identical owned server Unix socket.
        for role, expected in (('control', b'quillmd-owned-synthetic'), ('subject', b'')):
            port = free_port()
            process = self.forward(role, '-L', f'127.0.0.1:{port}:{self.unix_target}')
            self.event(f'{role}: server Unix target differential', self.echo(port=port) == expected)
            self.stop_client(process)
        remote_socket = self.runtime / 'control-remote.sock'
        # The account may create only this disposable socket directory.
        remote_dir = self.runtime / 'control-writable'
        remote_dir.mkdir(mode=0o700)
        os.chown(remote_dir, self.accounts[CONTROL]['uid'], self.accounts[CONTROL]['gid'])
        remote_socket = remote_dir / 'remote.sock'
        positive = self.forward('control', '-R', f'{remote_socket}:127.0.0.1:{self.echo_port}')
        self.event('control: remote Unix listener positive control', self.echo(path=remote_socket) == b'quillmd-owned-synthetic')
        self.stop_client(positive)
        if remote_socket.exists():
            remote_socket.unlink()
        subject_dir = self.runtime / 'subject-writable'
        subject_dir.mkdir(mode=0o700)
        os.chown(subject_dir, self.accounts[SUBJECT]['uid'], self.accounts[SUBJECT]['gid'])
        subject_socket = subject_dir / 'remote.sock'
        self.denied(self.ssh('subject', '-N', '-R', f'{subject_socket}:127.0.0.1:{self.echo_port}'), 'subject: remote Unix listener denied', b'remote port forwarding failed')
        self.event('subject: denied Unix listener absent', not subject_socket.exists())
        local_socket = self.runtime / 'private/client-allowed.sock'
        allowed = self.forward('subject', '-L', f'{local_socket}:127.0.0.1:9130')
        okay, detail = self.health_forward(path=local_socket)
        self.event('client Unix listener to approved TCP is allowed, not a bypass', okay, detail)
        self.stop_client(allowed)
        denied_socket = self.runtime / 'private/client-denied.sock'
        denied = self.forward('subject', '-L', f'{denied_socket}:127.0.0.1:{self.echo_port}')
        self.event('client Unix listener cannot bypass TCP destination restriction', self.echo(path=denied_socket) == b'')
        self.stop_client(denied)
        # Prove key restrictions are independently enforced within broader policy.
        self.subject_auth.write_text(self.subject_key.replace(',permitopen="127.0.0.1:9131"', ''))
        self.health_direct('subject', '127.0.0.1:9130', 'narrowed key still allows doctor')
        self.denied(self.ssh('subject', '-W', '127.0.0.1:9131', data=b'synthetic'), 'key permitopen independently denies admin')
        self.subject_auth.write_text(re.sub(r'expiry-time="[^"]+"', 'expiry-time="200001010000Z"', self.subject_key))
        self.denied(self.ssh('subject', '-W', '127.0.0.1:9130', data=b'synthetic'), 'expired key denied by actual project sshd', b'Permission denied (publickey)')
        self.subject_auth.write_text(self.subject_key)
        self.revocation()

    def revocation(self):
        subject_port, control_port = free_port(), free_port()
        while control_port == subject_port:
            control_port = free_port()
        subject = self.forward('subject', '-L', f'127.0.0.1:{subject_port}:127.0.0.1:9130')
        control = self.forward('control', '-L', f'127.0.0.1:{control_port}:127.0.0.1:9130')
        for role, port in (('subject', subject_port), ('control', control_port)):
            okay, detail = self.health_forward(port=port)
            self.event(f'{role}: live tunnel established before revocation', okay, detail)
        control_identity = process_identity(control.pid)
        cgroups = {}
        for role, name in (('subject', SUBJECT), ('control', CONTROL)):
            cgroup = command(['systemctl', 'show', self.unit(role), '-p', 'ControlGroup', '--value']).stdout.decode().strip()
            entries = [process_identity(int(pid)) for pid in (Path('/sys/fs/cgroup') / cgroup.lstrip('/') / 'cgroup.procs').read_text().split()]
            cgroups[role] = {'path': cgroup, 'processes': entries}
            self.event(f'{role}: privilege separated processes in dedicated cgroup', any(p and p['uid'] == 0 for p in entries) and any(p and p['uid'] == self.accounts[name]['uid'] for p in entries), cgroups[role])
        self.event('subject and control have distinct cgroups', cgroups['subject']['path'] != cgroups['control']['path'])
        confirmation_count = subject.quillmd_log.read_text().count('open confirm')
        live = self.connect(port=subject_port)
        self.sockets.append(live)
        self.throttle()
        live.sendall(b'GET /health/ HTTP/1.1\r\nHost: localhost\r\n')
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and subject.quillmd_log.read_text().count('open confirm') <= confirmation_count:
            time.sleep(.05)
        self.event('incomplete HTTP channel received SSH open confirmation', subject.quillmd_log.read_text().count('open confirm') > confirmation_count)
        self.event('revocation write-ahead event', True, {'account': SUBJECT, 'authorization_sha256_before': digest(self.subject_auth), 'action': 'remove synthetic key then terminate only subject service cgroup'})
        self.subject_auth.write_text('')
        self.denied(self.ssh('subject', '-W', '127.0.0.1:9130', data=b'synthetic'), 'removed key prevents new authentication before service stop', b'Permission denied (publickey)')
        okay, detail = self.health_forward(port=subject_port)
        self.event('key removal alone leaves established tunnel active', okay, detail)
        self.event('control service before target stop', control.poll() is None and process_identity(control.pid) == control_identity)
        command(['systemctl', 'stop', self.unit('subject')], timeout=10)
        subject.wait(timeout=5)
        self.event('subject SSH client terminated by scoped service stop', subject.poll() is not None, {'exit': subject.returncode})
        try:
            closed = live.recv(1024) == b''
        except ConnectionResetError:
            closed = True
        self.event('already-open forwarded data channel terminated', closed)
        live.close()
        self.sockets.remove(live)
        try:
            with socket.create_connection(('127.0.0.1', subject_port), timeout=.5):
                listener_gone = False
        except OSError:
            listener_gone = True
        self.event('subject local tunnel listener gone', listener_gone)
        okay, detail = self.health_forward(port=control_port)
        self.event('unrelated control live session survives same PID and start time', okay and control.poll() is None and process_identity(control.pid) == control_identity, detail)
        self.start_service('subject')
        self.denied(self.ssh('subject', '-W', '127.0.0.1:9130', data=b'synthetic'), 'revoked identity cannot reconnect after listener restart', b'Permission denied (publickey)')
        command(['systemctl', 'stop', self.unit('subject')], timeout=10)
        self.stop_client(control)

    def cleanup(self):
        errors = []
        for sock in self.sockets:
            try:
                sock.close()
            except OSError as error:
                errors.append(str(error))
        for process, handle in self.clients:
            try:
                self.stop_client(process)
            except Exception as error:
                errors.append(f'client cleanup: {error}')
            handle.close()
        for unit in self.services:
            try:
                stopped = command(['systemctl', 'stop', unit], check=False, timeout=10)
                log = command(['journalctl', '--no-pager', '-u', unit, '-o', 'short-iso'], check=False, timeout=10)
                self.save(unit + '.journal.txt', log.stdout + log.stderr)
                query = command(['systemctl', 'show', unit, '-p', 'LoadState', '-p', 'ActiveState', '-p', 'MainPID', '-p', 'ControlGroup'], check=False)
                state = dict(line.split('=', 1) for line in query.stdout.decode().splitlines() if '=' in line)
                if query.returncode or not state or state.get('MainPID') != '0' or state.get('ActiveState') not in ('inactive', 'failed'):
                    errors.append(f'unit stop/absence not verified: {unit}; query={query.returncode}; state={state}')
                elif stopped.returncode and state.get('LoadState') != 'not-found':
                    errors.append(f'unit stop failed: {unit}; exit={stopped.returncode}')
                if state.get('ControlGroup'):
                    cgroup = Path('/sys/fs/cgroup') / state['ControlGroup'].lstrip('/') / 'cgroup.procs'
                    if cgroup.exists() and cgroup.read_text().strip():
                        errors.append(f'unit cgroup retains processes: {unit}')
            except Exception as error:
                errors.append(f'unit cleanup {unit}: {error}')
        for server in self.servers:
            try:
                server.shutdown()
                server.server_close()
            except Exception as error:
                errors.append(f'echo cleanup: {error}')
        # Recover a partially successful useradd using this run's exact marker.
        for name, pending in self.pending_accounts.items():
            if name in self.accounts:
                continue
            try:
                entry = pwd.getpwnam(name)
                if entry.pw_dir == pending['home'] and entry.pw_gecos == pending['comment']:
                    self.accounts[name] = {'uid': entry.pw_uid, 'gid': entry.pw_gid, 'home': entry.pw_dir}
                else:
                    errors.append(f'pending account marker differs; preserved {name}')
            except KeyError:
                pass
        for name, identity in self.accounts.items():
            try:
                entry = pwd.getpwnam(name)
                if entry.pw_uid != identity['uid'] or entry.pw_gid != identity['gid'] or entry.pw_dir != identity['home']:
                    raise RuntimeError('identity changed; refuse deletion')
                result = command(['userdel', name], check=False)
                if result.returncode:
                    raise RuntimeError(result.stderr.decode(errors='replace'))
                try:
                    pwd.getpwnam(name)
                    raise RuntimeError('account survived deletion')
                except KeyError:
                    pass
                try:
                    group = grp.getgrnam(name)
                    if group.gr_gid != identity['gid'] or group.gr_mem:
                        raise RuntimeError('group changed; refuse deletion')
                    command(['groupdel', name])
                except KeyError:
                    pass
            except Exception as error:
                errors.append(f'account cleanup {name}: {error}')
        if self.created_runtime:
            try:
                if self.runtime.is_symlink() or self.runtime.parent != Path('/run') or not self.runtime.name.startswith('quillmd-reviewer-qual-'):
                    raise RuntimeError('runtime identity changed; refuse removal')
                shutil.rmtree(self.runtime)
            except Exception as error:
                errors.append(f'runtime cleanup: {error}')
        listener_absent = {}
        for role, port in getattr(self, 'ports', {}).items():
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.3):
                    listener_absent[role] = False
            except OSError:
                listener_absent[role] = True
        groups_absent = {}
        for name in (SUBJECT, CONTROL):
            try:
                group = grp.getgrnam(name)
                groups_absent[name] = False
                errors.append(f'temporary group remains: {name}; gid={group.gr_gid}; preserve for scoped investigation')
            except KeyError:
                groups_absent[name] = True
        self.report['cleanup'] = {'finished_at': utc(), 'errors': errors, 'runtime_absent': not self.runtime.exists(), 'temporary_account_names_absent': all(not self.account_exists(name) for name in (SUBJECT, CONTROL)), 'temporary_group_names_absent': groups_absent, 'temporary_listeners_absent': listener_absent}
        self.report['shared_after'] = shared_state()
        try:
            self.report['config_hashes_after'] = config_hashes()
            self.report['shared_config_unchanged'] = self.report.get('config_hashes_before') == self.report['config_hashes_after']
            self.report['shared_service_identities_unchanged'] = self.report.get('shared_before', {}).get('services') == self.report['shared_after']['services']
            baseline = self.report.get('shared_before', {}).get('sshd_processes', [])
            self.report['shared_prior_sshd_processes_survive'] = all(process_identity(item['pid']) == item for item in baseline)
            self.report['shared_prior_sshd_processes_ended'] = [item for item in baseline if process_identity(item['pid']) != item]
        except Exception as error:
            errors.append(f'final preservation check: {error}')
        self.report['completed_at'] = utc()
        self.report['elapsed_seconds'] = round(time.monotonic() - self.started, 3)
        self.report['passed'] = not self.report['failures'] and not errors and bool(self.report['checks']) and self.report.get('shared_config_unchanged', False) and self.report.get('shared_service_identities_unchanged', False) and self.report.get('shared_prior_sshd_processes_survive', False) and self.report['cleanup']['runtime_absent'] and self.report['cleanup']['temporary_account_names_absent'] and all(groups_absent.values()) and all(listener_absent.values())
        self.save('report.json', self.report)
        manifest = {str(path.relative_to(self.evidence)): {'sha256': digest(path), 'size': path.stat().st_size} for path in self.evidence.iterdir() if path.is_file() and not path.is_symlink()}
        self.save('SHA256-MANIFEST.json', manifest)
        # Host-side finalization; no read-only container bind can perform this.
        for root, directories, filenames in os.walk(self.evidence, followlinks=False):
            for name in filenames:
                path = Path(root) / name
                if stat.S_ISREG(path.lstat().st_mode):
                    os.chown(path, 1000, 1000, follow_symlinks=False)
                    os.chmod(path, 0o600, follow_symlinks=False)
            for name in directories:
                path = Path(root) / name
                if stat.S_ISDIR(path.lstat().st_mode):
                    os.chown(path, 1000, 1000, follow_symlinks=False)
                    os.chmod(path, 0o700, follow_symlinks=False)
        os.chown(self.evidence, 1000, 1000, follow_symlinks=False)
        os.chmod(self.evidence, 0o700, follow_symlinks=False)

    @staticmethod
    def account_exists(name):
        try:
            pwd.getpwnam(name)
            return True
        except KeyError:
            return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,39}', args.run_id):
        parser.error('run-id must be 3-40 lowercase letters/digits/hyphens')
    evidence = args.evidence
    if not evidence.is_absolute() or evidence.is_symlink() or evidence.resolve() != evidence:
        parser.error('evidence must be an absolute resolved non-symlink path')
    if not evidence.is_dir() or evidence.stat().st_mode & 0o077:
        parser.error('evidence must be a pre-created private directory')
    entries = list(evidence.iterdir())
    if entries:
        if len(entries) != 1 or entries[0].name != 'launch.json' or not stat.S_ISREG(entries[0].lstat().st_mode):
            parser.error('evidence may contain only the immutable launch record')
        launch = json.loads(entries[0].read_text())
        if launch.get('run_id') != args.run_id or launch.get('evidence') != str(evidence) or launch.get('source') != str(Path(__file__).resolve()) or launch.get('source_sha256') != digest(__file__):
            parser.error('launch record does not match this exact harness/context')
    harness = Harness(evidence, args.run_id)

    def interrupted(signum, _frame):
        raise RuntimeError(f'interrupted by signal {signum}; scoped cleanup required')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGALRM, interrupted)
    signal.alarm(150)
    try:
        harness.setup()
        harness.run_checks()
    except BaseException as error:
        harness.report['failures'].append({'at': utc(), 'type': type(error).__name__, 'message': str(error)})
    finally:
        signal.alarm(0)
        # Permit cleanup to finish after the first termination request.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        harness.cleanup()
    print(json.dumps({'report': str(evidence / 'report.json'), 'passed': harness.report['passed'], 'checks': len(harness.report['checks']), 'failures': len(harness.report['failures']), 'cleanup_errors': len(harness.report['cleanup']['errors'])}))
    return 0 if harness.report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
