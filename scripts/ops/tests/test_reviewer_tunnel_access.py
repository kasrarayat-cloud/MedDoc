"""Real OpenSSH qualification using synthetic keys, loopback sockets and a private sshd.

No host sshd/authorized_keys, application endpoint, real account grant or HOME override.
The two production destinations are substituted with owned ephemeral echo listeners;
the prepared policy's literal production destinations are separately asserted.
Run: python3 -B scripts/ops/tests/test_reviewer_tunnel_access.py -v
"""
import contextlib
import datetime as dt
import getpass
import os
from pathlib import Path
import shutil
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'reviewer-tunnel-access.sh'
LEGACY_OPTIONS = 'restrict,port-forwarding,permitopen="127.0.0.1:9130",permitopen="127.0.0.1:9131",command="/bin/false"'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            self.request.sendall(self.request.recv(64))
        except OSError:
            pass


class Qualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('ssh') or not Path('/usr/sbin/sshd').exists():
            raise RuntimeError('OpenSSH client and server required; do not silently skip execution')
        # A private owned directory, not a HOME override; strict SSH ownership stays on.
        base = Path.home() / '.cache' / 'quillmd-reviewer-qualification'
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(prefix='fixture-', dir=base)
        cls.root = Path(cls.temp.name)
        cls.keys = cls.root / 'authorized_keys'
        cls.records = cls.root / 'records'
        cls.helper = cls.root / 'helper.sh'
        script = SCRIPT.read_text()
        assert script.count('keys="$HOME/.ssh/authorized_keys"') == 1
        assert script.count('record_dir="/opt/meddoc-pro/rebuild/.runtime/reviewer-access"') == 1
        cls.helper.write_text(script.replace('keys="$HOME/.ssh/authorized_keys"', f'keys="{cls.keys}"')
                             .replace('record_dir="/opt/meddoc-pro/rebuild/.runtime/reviewer-access"', f'record_dir="{cls.records}"'))
        for name in ('host', 'client'):
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(cls.root / name)], check=True)
        cls.pub = (cls.root / 'client.pub').read_text().strip()
        cls.window = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H:%MZ')
        cls.prepared = cls.prepare()
        cls.prepared_key = (cls.prepared / 'authorized_keys').read_text()
        cls.policy = (cls.prepared / 'sshd-match.conf').read_text()
        cls.echoes = []
        for _ in range(3):
            server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Echo)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            cls.echoes.append(server)
        cls.ports = [s.server_address[1] for s in cls.echoes]
        cls.unix_target = cls.root / 'target.sock'
        cls.unix_echo = socketserver.ThreadingUnixStreamServer(str(cls.unix_target), Echo)
        threading.Thread(target=cls.unix_echo.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for server in [*cls.echoes, cls.unix_echo]:
            server.shutdown()
            server.server_close()
        cls.temp.cleanup()

    @classmethod
    def run_helper(cls, *args):
        return subprocess.run(['bash', str(cls.helper), *args], capture_output=True, text=True, timeout=5)

    @classmethod
    def prepare(cls, key=None):
        result = cls.run_helper('prepare', 'synthetic-reviewer', str(key or cls.root / 'client.pub'), cls.window)
        if result.returncode:
            raise AssertionError(result.stderr)
        return Path(result.stdout.splitlines()[0].removeprefix('PREPARED ONLY: '))

    def setUp(self):
        self.keys.write_text('')
        self.keys.chmod(0o600)

    @contextlib.contextmanager
    def sshd(self, hardened=True, expired=False):
        key = self.prepared_key if hardened else LEGACY_OPTIONS + ' ' + self.pub + '\n'
        key = key.replace('127.0.0.1:9130', f'127.0.0.1:{self.ports[0]}').replace('127.0.0.1:9131', f'127.0.0.1:{self.ports[1]}')
        if expired:
            import re
            key = re.sub(r'expiry-time="[^"]+"', 'expiry-time="200001010000Z"', key)
        self.keys.write_text(key)
        port = free_port()
        conf = self.root / f'sshd-{port}.conf'
        policy = self.policy.replace('Match User quillmd-reviewer', f'Match User {getpass.getuser()}')
        policy = policy.replace('127.0.0.1:9130', f'127.0.0.1:{self.ports[0]}').replace('127.0.0.1:9131', f'127.0.0.1:{self.ports[1]}')
        conf.write_text(f'''Port {port}
ListenAddress 127.0.0.1
HostKey {self.root}/host
AuthorizedKeysFile {self.keys}
PidFile {self.root}/sshd-{port}.pid
UsePAM no
PasswordAuthentication no
KbdInteractiveAuthentication no
StrictModes yes
LogLevel VERBOSE
AllowUsers {getpass.getuser()}
''' + (policy if hardened else ''))
        log = (self.root / f'sshd-{port}.log').open('w')
        process = subprocess.Popen(['/usr/sbin/sshd', '-D', '-e', '-f', str(conf)], stderr=log)
        try:
            deadline = time.monotonic() + 3
            while True:
                if process.poll() is not None:
                    raise AssertionError(f'isolated sshd exited {process.returncode}')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=.1):
                        break
                except OSError:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(.02)
            self.ssh_base = ['ssh', '-F', '/dev/null', '-p', str(port), '-i', str(self.root / 'client'), '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=2', '-o', 'ExitOnForwardFailure=yes']
            yield
        finally:
            process.terminate()
            process.wait(timeout=3)
            log.close()

    def ssh(self, *args, data=None, command=None):
        return subprocess.run([*self.ssh_base, *args, f'{getpass.getuser()}@127.0.0.1', *([command] if command else [])], input=data, capture_output=True, timeout=4)

    @contextlib.contextmanager
    def forward(self, *args):
        process = subprocess.Popen([*self.ssh_base, '-N', *args, f'{getpass.getuser()}@127.0.0.1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            time.sleep(.15)
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=3)

    def echo(self, port=None, path=None):
        deadline = time.monotonic() + 3
        while True:
            sock = socket.socket(socket.AF_UNIX if path else socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                sock.connect(str(path) if path else ('127.0.0.1', port))
                break
            except (ConnectionRefusedError, FileNotFoundError):
                sock.close()
                if time.monotonic() > deadline:
                    raise
                time.sleep(.02)
        with sock:
            sock.sendall(b'owned-synthetic-fixture')
            return sock.recv(64)

    def test_prepare_is_not_grant_and_retains_each_event(self):
        first = self.prepare()
        second = self.prepare()
        self.assertNotEqual(first, second)
        self.assertEqual(self.keys.read_text(), '')
        self.assertIn('"event":"prepared_not_granted"', (first / 'event.json').read_text())
        self.assertIn('PermitOpen 127.0.0.1:9130 127.0.0.1:9131', self.policy)
        self.assertIn('expiry-time="', self.prepared_key)
        self.assertEqual((first.stat().st_mode & 0o777), 0o700)
        self.assertEqual(((first / 'authorized_keys').stat().st_mode & 0o777), 0o600)

    def test_shared_account_grant_refuses_without_changing_keys(self):
        self.keys.write_text('sentinel\n')
        result = self.run_helper('grant', 'synthetic-reviewer', str(self.root / 'client.pub'), self.window)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('shared-account', result.stderr)
        self.assertEqual(self.keys.read_text(), 'sentinel\n')

    def test_two_keys_without_final_newline_refused(self):
        keyfile = self.root / 'two.pub'
        keyfile.write_text(self.pub + '\n' + self.pub)
        result = self.run_helper('prepare', 'synthetic-reviewer', str(keyfile), self.window)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exactly one', result.stderr)

    def test_invalid_calendar_refused(self):
        result = self.run_helper('prepare', 'synthetic-reviewer', str(self.root / 'client.pub'), '2099-02-31T18:00Z')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('calendar', result.stderr)

    def test_revoke_only_line_succeeds_and_preserves_grant_record(self):
        self.keys.write_text(LEGACY_OPTIONS + ' ' + self.pub + ' quillmd-reviewer:synthetic-reviewer window-end=' + self.window + '\n')
        history = self.records / 'synthetic-reviewer.json'
        history.write_text('{"historical_grant":"immutable"}\n')
        result = self.run_helper('revoke', 'synthetic-reviewer')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.keys.read_text(), '')
        self.assertEqual(history.read_text(), '{"historical_grant":"immutable"}\n')
        event = sorted(self.records.glob('revoked-synthetic-reviewer-*.jsonl'))[-1].read_text()
        self.assertIn('"event":"revocation_requested"', event.splitlines()[0])
        self.assertIn('"established_connections_terminated":false', event)

    def test_revoke_preserves_unrelated_lines(self):
        self.keys.write_text('unrelated-key sentinel\n' + LEGACY_OPTIONS + ' ' + self.pub + ' quillmd-reviewer:synthetic-reviewer window-end=' + self.window + '\n')
        result = self.run_helper('revoke', 'synthetic-reviewer')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.keys.read_text(), 'unrelated-key sentinel\n')

    def test_unavailable_audit_refuses_before_authorization_changes(self):
        self.keys.write_text(self.prepared_key)
        blocked = self.root / 'not-a-directory'
        blocked.write_text('owned synthetic fixture')
        helper = self.root / 'audit-blocked-helper.sh'
        helper.write_text(self.helper.read_text().replace(f'record_dir="{self.records}"', f'record_dir="{blocked}"'))
        result = subprocess.run(['bash', str(helper), 'revoke', 'synthetic-reviewer'], capture_output=True, text=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.keys.read_text(), self.prepared_key)

    def test_concurrent_revokes_do_not_resurrect_a_key(self):
        self.keys.write_text(self.prepared_key.replace('synthetic-reviewer ', 'alice-reviewer ') + self.prepared_key.replace('synthetic-reviewer ', 'bob-reviewer '))
        # Hold the real helper lock until both callers are waiting; then release.
        import fcntl
        with (self.root / '.quillmd-reviewer-revoke.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            processes = [subprocess.Popen(['bash', str(self.helper), 'revoke', who], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for who in ('alice-reviewer', 'bob-reviewer')]
            time.sleep(.05)
            self.assertTrue(all(p.poll() is None for p in processes))
            fcntl.flock(lock, fcntl.LOCK_UN)
            for process in processes:
                _, err = process.communicate(timeout=3)
                self.assertEqual(process.returncode, 0, err)
        self.assertEqual(self.keys.read_text(), '')

    def test_legacy_key_allows_remote_tcp_despite_permitopen(self):
        port = free_port()
        with self.sshd(hardened=False), self.forward('-R', f'127.0.0.1:{port}:127.0.0.1:{self.ports[2]}') as process:
            self.assertIsNone(process.poll())
            self.assertEqual(self.echo(port=port), b'owned-synthetic-fixture')

    def test_unprivileged_sshd_cannot_positive_control_unix_forwarding(self):
        # OpenSSH also requires root/privsep for streamlocal. This is an explicit
        # fixture coverage limit, NOT evidence the legacy key safely denied Unix.
        port = free_port()
        with self.sshd(hardened=False), self.forward('-L', f'127.0.0.1:{port}:{self.unix_target}') as process:
            self.assertIsNone(process.poll())
            try:
                response = self.echo(port=port)
            except ConnectionResetError:
                response = b''
            self.assertEqual(response, b'')

    def test_hardened_allows_both_named_destinations(self):
        with self.sshd():
            for port in self.ports[:2]:
                result = self.ssh('-W', f'127.0.0.1:{port}', data=b'owned-synthetic-fixture')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, b'owned-synthetic-fixture')

    def test_hardened_denies_other_tcp_destination(self):
        with self.sshd():
            result = self.ssh('-W', f'127.0.0.1:{self.ports[2]}', data=b'owned-synthetic-fixture')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'administratively prohibited', result.stderr)
            self.assertEqual(result.stdout, b'')

    def test_hardened_denies_remote_tcp(self):
        with self.sshd():
            result = self.ssh('-N', '-R', f'127.0.0.1:{free_port()}:127.0.0.1:{self.ports[0]}')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'remote port forwarding failed', result.stderr)

    def test_hardened_denies_remote_unix_socket(self):
        path = self.root / 'remote.sock'
        with self.sshd():
            result = self.ssh('-N', '-R', f'{path}:127.0.0.1:{self.ports[0]}')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'remote port forwarding failed', result.stderr)
            self.assertFalse(path.exists())

    def test_hardened_denies_local_unix_socket(self):
        port = free_port()
        with self.sshd(), self.forward('-L', f'127.0.0.1:{port}:{self.unix_target}') as process:
            self.assertIsNone(process.poll())
            try:
                response = self.echo(port=port)
            except ConnectionResetError:
                response = b''
            self.assertEqual(response, b'')
            process.terminate()
            _, err = process.communicate(timeout=3)
            self.assertIn(b'open failed', err)

    def test_hardened_denies_shell_and_subsystem(self):
        with self.sshd():
            for args, command in [([], None), (['-s'], 'sftp')]:
                result = self.ssh(*args, command=command)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'channel 0: open failed', result.stderr)

    def test_expired_key_is_rejected_by_sshd(self):
        with self.sshd(expired=True):
            result = self.ssh('-W', f'127.0.0.1:{self.ports[0]}', data=b'owned-synthetic-fixture')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Permission denied (publickey)', result.stderr)

    def test_key_removal_denies_new_auth_but_existing_channel_needs_termination(self):
        port = free_port()
        with self.sshd(), self.forward('-L', f'127.0.0.1:{port}:127.0.0.1:{self.ports[0]}') as process:
            self.assertEqual(self.echo(port=port), b'owned-synthetic-fixture')
            result = self.run_helper('revoke', 'synthetic-reviewer')
            self.assertEqual(result.returncode, 0, result.stderr)
            denied = self.ssh('-W', f'127.0.0.1:{self.ports[0]}', data=b'owned-synthetic-fixture')
            self.assertIn(b'Permission denied (publickey)', denied.stderr)
            self.assertEqual(self.echo(port=port), b'owned-synthetic-fixture')
            self.assertIsNone(process.poll())

    def test_status_unreadable_file_fails_instead_of_reporting_empty(self):
        self.keys.chmod(0o000)
        try:
            result = self.run_helper('status')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('status unknown', result.stderr)
            self.assertNotIn('no reviewer grants', result.stdout)
        finally:
            self.keys.chmod(0o600)

    def test_status_distinguishes_missing_file_from_empty_file(self):
        self.keys.unlink()
        result = self.run_helper('status')
        self.assertEqual(result.returncode, 0)
        self.assertIn('does not exist', result.stdout)
        self.keys.write_text('')
        result = self.run_helper('status')
        self.assertEqual(result.returncode, 0)
        self.assertIn('readable authorization file', result.stdout)


if __name__ == '__main__':
    unittest.main()
