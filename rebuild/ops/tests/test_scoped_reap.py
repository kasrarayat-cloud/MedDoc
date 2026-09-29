"""The recorded reaper and the sweep refusal: scripts/scratch-ledger.sh, scripts/reap-recorded-scratch.sh,
scripts/lib/sweep-guard.sh, the bulk guard in scripts/reap-session-scratch.sh, and the shared declaration check in
scripts/lib/inflight.sh (which also serves the pre-push hook, merge-pr.sh and push-with-cancellation.sh).

2026-09-29: `find <whole session scratchpad> -type f | xargs bash scripts/reap-session-scratch.sh` shredded 30
files other agents owned; a later `find … | xargs -0 -n 200 …` shredded 6,537, the cleanup's own logs included.
These tests prove every refusal that stops that with a concrete input, and a positive control for each door.
The refutation round on df80fa58 (F1-F8 and the lows) is covered class by class below; each test names its finding.

Every file touched lives in a private tree this test creates under /tmp/claude-<euid>/ (derived exactly as the
scripts derive it — the effective uid, nothing else) or in a private state directory OUTSIDE that sandbox. No
real scratchpad is ever named, and XDG_STATE_HOME is always pointed at the test's own state directory, so the
session reaper's cross-call window never reads or writes a real one. `shred` for reap-session-scratch.sh is always
a logging stand-in; `gh` and `git push` for the push/merge doors are always failing stand-ins, so no test can reach
the network. The trees are removed by the test that made them.
"""
import hashlib
import hmac
import importlib.util
import inspect
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
SCRIPTS = REPOSITORY / 'scripts'
RECORD = SCRIPTS / 'scratch-ledger.sh'
REAP = SCRIPTS / 'reap-recorded-scratch.sh'
SESSION_REAP = SCRIPTS / 'reap-session-scratch.sh'
INFLIGHT = SCRIPTS / 'lib' / 'inflight.sh'
PRE_PUSH = SCRIPTS / 'hooks' / 'pre-push'
MERGE_PR = SCRIPTS / 'merge-pr.sh'
PUSH_WITH_CANCELLATION = SCRIPTS / 'push-with-cancellation.sh'
MODULE = SCRIPTS / 'lib' / 'scratch_ledger.py'
SANDBOX = Path(f'/tmp/claude-{os.geteuid()}')
# reap-session-scratch.sh hard-codes /tmp/claude-1000/ (unchanged): for any other uid it refuses every real path
# at its sandbox check, before the refusals under test, so those tests skip there (CI runs as uid 1001).
SESSION_SANDBOX_UID = 1000
STRIPPED = ('REAP_SESSION_BULK_DECLARATION', 'SCRATCH_LEDGER_BULK_DECLARATION', 'DECLARE_CANCELLATION',
            'DECLARE_TYPECHECK_SKIP', 'INFLIGHT_REPO', 'XDG_STATE_HOME')
MAC_DOMAIN = b'scratch-ledger-v2\n'
NBSP = ' '


def environment(**extra):
    env = {k: v for k, v in os.environ.items() if k not in STRIPPED and not k.startswith('GIT_')}
    # Never the real state directory: a path nobody can create makes the session reaper refuse instead.
    env['XDG_STATE_HOME'] = '/nonexistent-scoped-reap-test-state'
    env.update({k: str(v) for k, v in extra.items()})
    return env


def run(cmd, env=None, cwd=None, input_text=None, timeout=120):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=env or environment(), cwd=cwd,
                          input=input_text, stdin=None if input_text is not None else subprocess.DEVNULL,
                          timeout=timeout)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def in_sandbox(path):
    real = os.path.realpath(path)
    return real == str(SANDBOX) or real.startswith(str(SANDBOX) + '/')


def load_module():
    spec = importlib.util.spec_from_file_location('scratch_ledger_under_test', MODULE)
    module = importlib.util.module_from_spec(spec)
    previous, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def git_env():
    return environment(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')


def git(*args, cwd=None):
    result = run(['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *args], env=git_env(), cwd=cwd)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


class ScratchTree(unittest.TestCase):
    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest('both tools refuse to run as root by design')
        if not SANDBOX.exists():
            SANDBOX.mkdir(mode=0o700)  # a fresh CI runner has no sandbox root yet
        st = SANDBOX.lstat()
        self.assertTrue(stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and not st.st_mode & 0o022,
                        f'{SANDBOX} must be a real directory you own and only you can write')
        self.tree = Path(tempfile.mkdtemp(prefix='scoped-reap-test-', dir=SANDBOX))
        self.addCleanup(self.remove_own_tree, self.tree)
        for parent in (REPOSITORY / 'rebuild' / '.runtime', Path(tempfile.gettempdir())):
            if not in_sandbox(parent):
                break
        else:
            self.skipTest('no directory outside the sandbox is available for the ledger')
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.state = Path(tempfile.mkdtemp(prefix='scoped-reap-state-', dir=parent))
        self.addCleanup(self.remove_own_tree, self.state)
        self.assertFalse(in_sandbox(self.state))
        self.ledger = self.state / 'agent.ledger'
        self.xdg = self.state / 'xdg-state'
        self.bindir = None

    def remove_own_tree(self, path):
        # Only the mkdtemp trees this test created: the prefix and the parent are asserted first.
        assert path.name.startswith(('scoped-reap-test-', 'scoped-reap-state-')), path
        if path.exists():
            shutil.rmtree(path)

    def env(self, **extra):
        path = os.environ.get('PATH', '')
        if self.bindir is not None:
            path = f'{self.bindir}{os.pathsep}{path}'
        return environment(**{'XDG_STATE_HOME': self.xdg, 'PATH': path, **extra})

    def make(self, relative, data=b'scratch\n', mode=None):
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if mode is not None:
            path.chmod(mode)
        return path

    def spawn(self, *args, **kwargs):
        proc = subprocess.Popen(list(args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        self.addCleanup(lambda: (proc.kill(), proc.wait()))
        return proc

    def record(self, *files, retain=False, env=None, ledger=None, agent='test-agent'):
        return run(['bash', RECORD, 'record', '--agent', agent, *(['--retain'] if retain else []), '--',
                    ledger or self.ledger, *files], env=env or self.env())

    def reap(self, *paths, retained=(), dry_run=False, env=None, ledger=None, cwd=None):
        flags = [x for m in retained for x in ('--retained', m)] + (['--dry-run'] if dry_run else [])
        return run(['bash', REAP, *flags, '--', ledger or self.ledger, *paths], env=env or self.env(), cwd=cwd)

    def session_reap(self, *paths, env=None):
        return run(['bash', SESSION_REAP, *paths], env=env or self.env())

    def ledger_records(self, ledger=None):
        ledger = Path(ledger or self.ledger)
        if not ledger.exists():
            return []
        return [json.loads(line) for line in ledger.read_text().splitlines()]

    def log(self, ledger=None):
        return [json.loads(line) for line in Path(str(ledger or self.ledger) + '.reap-log').read_text().splitlines()]

    def decisions(self, path, ledger=None):
        return [e['decision'] for e in self.log(ledger) if e.get('path') == str(path)]

    def mac(self, ledger, record):
        key = bytes.fromhex(Path(str(ledger) + '.key').read_text().strip())
        body = json.dumps({k: v for k, v in record.items() if k != 'mac'}, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=True).encode('ascii')
        return hmac.new(key, MAC_DOMAIN + body, hashlib.sha256).hexdigest()

    def forge(self, path, sign=True, ledger=None, drop=(), **fields):
        """Append a hand-written record — what a damaged, edited or tree-walked ledger could hold. With sign=True
        it carries a VALID MAC (computed with the ledger's own key, as a deliberate forger could) so the check
        under test is the one AFTER the binding; with sign=False it carries none a recorder would have made."""
        ledger = Path(ledger or self.ledger)
        st = os.stat(path) if os.path.exists(path) else None
        record = {'v': 2, 'kind': 'record', 'seq': len(self.ledger_records(ledger)) + 1, 'path': str(path),
                  'dev': st.st_dev if st else 1, 'ino': st.st_ino if st else 1, 'size': st.st_size if st else 0,
                  'sha256': sha(path) if st else '0' * 64, 'uid': os.geteuid(), 'btime': None,
                  'ctime_ns': st.st_ctime_ns if st else 0, 'mtime_ns': st.st_mtime_ns if st else 0,
                  'recorded_at': '2026-09-29T00:00:00Z', 'agent': 'forged', 'retain': False, 'recorder_pid': 1}
        record.update(fields)
        record['mac'] = self.mac(ledger, record) if sign else '0' * 64
        for key in drop:
            record.pop(key)
        fd = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps(record) + '\n').encode())
        finally:
            os.close(fd)
        return record

    def fake(self, name, body):
        """A stand-in executable first on PATH for every door this test runs."""
        if self.bindir is None:
            self.bindir = self.state / 'fakebin'
            self.bindir.mkdir()
        exe = self.bindir / name
        exe.write_text(f'#!/bin/sh\n{body}\n')
        exe.chmod(0o700)
        return exe

    def fake_shred(self, body='exit 0'):
        log = self.state / 'shred-calls.log'
        self.fake('shred', f'printf "%s\\n" "$*" >> {shlex.quote(str(log))}\n{body}')
        return log

    def shred_calls(self):
        log = self.state / 'shred-calls.log'
        return log.read_text().splitlines() if log.exists() else []

    def require_session_sandbox(self):
        if os.geteuid() != SESSION_SANDBOX_UID:
            self.skipTest('reap-session-scratch.sh hard-codes /tmp/claude-1000/; at any other uid every real path '
                          'is refused at the sandbox check, before the refusal under test')

    def assertRecorded(self, result, *files, ledger=None):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual({r['path'] for r in self.ledger_records(ledger)} & {str(f) for f in files},
                         {str(f) for f in files})

    def assertKeptIntact(self, path, digest):
        self.assertTrue(Path(path).is_file() and not Path(path).is_symlink(), f'{path} must survive')
        self.assertEqual(sha(path), digest, f'{path} must survive UNCHANGED')


class RecordedReapPositiveControls(ScratchTree):
    def test_a_recorded_unchanged_unopened_own_file_is_shredded_and_the_log_records_it(self):
        f = self.make('work/out.json', b'{"synthetic": true}\n')
        digest, st = sha(f), f.stat()
        self.assertRecorded(self.record(f), f)
        (entry,) = self.ledger_records()
        self.assertEqual((entry['v'], entry['seq'], entry['path'], entry['dev'], entry['ino'], entry['size'],
                          entry['sha256'], entry['uid'], entry['agent'], entry['retain']),
                         (2, 1, str(f), st.st_dev, st.st_ino, st.st_size, digest, os.geteuid(), 'test-agent', False))
        self.assertEqual(entry['mac'], self.mac(self.ledger, entry), 'the line is bound to the ledger key')
        self.assertEqual(stat.S_IMODE(self.ledger.stat().st_mode), 0o600)
        key = Path(str(self.ledger) + '.key')
        self.assertEqual((stat.S_IMODE(key.stat().st_mode), key.stat().st_nlink), (0o600, 1))
        ledger_before = sha(self.ledger)

        result = self.reap()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'shredded: {f}', result.stdout)
        self.assertFalse(os.path.lexists(f))
        self.assertEqual(self.decisions(f), ['SHREDDING', 'SHREDDED'])
        self.assertEqual([e['decision'] for e in self.log()][0], 'RUN-START')
        self.assertEqual([e['decision'] for e in self.log()][-1], 'RUN-END')
        self.assertEqual(sha(self.ledger), ledger_before, 'the reaper never rewrites the ledger')
        self.assertEqual(stat.S_IMODE(Path(str(self.ledger) + '.reap-log').stat().st_mode), 0o600)

    def test_a_second_run_finds_it_absent_and_only_appends_to_the_log(self):
        f = self.make('again/f')
        self.assertRecorded(self.record(f), f)
        self.assertEqual(self.reap().returncode, 0)
        first = Path(str(self.ledger) + '.reap-log').read_bytes()
        result = self.reap()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(f'absent (already gone): {f}', result.stdout)
        after = Path(str(self.ledger) + '.reap-log').read_bytes()
        self.assertTrue(after.startswith(first) and len(after) > len(first), 'the log is append-only')

    def test_naming_one_recorded_file_reaps_only_that_file(self):
        a, b = self.make('two/a', b'a'), self.make('two/b', b'b')
        self.assertRecorded(self.record(a, b), a, b)
        result = self.reap(a)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(a.exists())
        self.assertKeptIntact(b, hashlib.sha256(b'b').hexdigest())

    def test_a_dry_run_decides_and_logs_but_destroys_nothing(self):
        f = self.make('dry/f')
        self.assertRecorded(self.record(f), f)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertKeptIntact(f, sha(f))
        self.assertEqual(self.decisions(f), ['WOULD-SHRED'])

    def test_a_missing_ledger_directory_is_created_private(self):
        f = self.make('mk/f')
        ledger = self.state / 'new' / 'agent.ledger'
        self.assertEqual(self.record(f, ledger=ledger).returncode, 0)
        self.assertEqual(stat.S_IMODE((self.state / 'new').stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(ledger.stat().st_mode), 0o600)

    def test_a_ledger_must_be_named_dot_ledger_by_both_tools(self):
        f = self.make('nm/f')
        for name in ('agent.log', 'agent', '.ledger'):
            result = self.record(f, ledger=self.state / name)
            self.assertEqual(result.returncode, 2, name)
            self.assertIn('.ledger', result.stderr)
            self.assertFalse((self.state / name).exists())
            self.assertEqual(self.reap(ledger=self.state / name).returncode, 2)


class RecordedReapRefusals(ScratchTree):
    def test_a_sibling_that_is_not_in_the_ledger_is_never_taken(self):
        a, b = self.make('sib/a', b'mine'), self.make('sib/b', b'not mine')
        self.assertRecorded(self.record(a), a)
        result = self.reap(b)
        self.assertEqual(result.returncode, 1)
        self.assertIn('NOT IN THE LEDGER', result.stdout)
        self.assertKeptIntact(b, hashlib.sha256(b'not mine').hexdigest())
        self.assertKeptIntact(a, hashlib.sha256(b'mine').hexdigest())
        result = self.reap()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(a.exists())
        self.assertKeptIntact(b, hashlib.sha256(b'not mine').hexdigest())

    def test_a_file_replaced_after_recording_new_inode_same_content_is_refused(self):
        f = self.make('rep/f', b'same bytes')
        self.assertRecorded(self.record(f), f)
        os.replace(self.make('rep/f.new', b'same bytes'), f)
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('REPLACED', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'same bytes').hexdigest())

    def test_a_file_rewritten_in_place_same_inode_same_size_is_refused(self):
        f = self.make('mod/f', b'aaaa')
        self.assertRecorded(self.record(f), f)
        with open(f, 'r+b') as fh:
            fh.write(b'bbbb')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('CHANGED: content sha256', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'bbbb').hexdigest())

    def test_a_recorded_path_that_became_a_symlink_escaping_the_sandbox_is_refused(self):
        outside = self.state / 'outside-target'
        outside.write_bytes(b'precious')
        f = self.make('sym/f', b'precious')
        self.assertRecorded(self.record(f), f)
        f.unlink()
        f.symlink_to(outside)
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('SYMLINK', result.stdout)
        self.assertKeptIntact(outside, hashlib.sha256(b'precious').hexdigest())
        self.assertTrue(f.is_symlink())

    def test_a_symlinked_parent_directory_escaping_the_sandbox_is_refused(self):
        f = self.make('par/f', b'data')
        self.assertRecorded(self.record(f), f)
        escape = self.state / 'escape'
        escape.mkdir()
        (escape / 'f').write_bytes(b'data')
        (self.tree / 'par').rename(self.tree / 'par.moved')
        (self.tree / 'par').symlink_to(escape)
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn(f'SYMLINK COMPONENT: {self.tree / "par"}', result.stdout)
        self.assertKeptIntact(escape / 'f', hashlib.sha256(b'data').hexdigest())
        self.assertKeptIntact(self.tree / 'par.moved' / 'f', hashlib.sha256(b'data').hexdigest())

    def test_a_symlinked_parent_reaching_the_very_same_inode_is_still_refused(self):
        f = self.make('same/f', b'data')
        self.assertRecorded(self.record(f), f)
        (self.tree / 'same').rename(self.tree / 'same.real')
        (self.tree / 'same').symlink_to(self.tree / 'same.real')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('SYMLINK COMPONENT', result.stdout)
        self.assertKeptIntact(self.tree / 'same.real' / 'f', hashlib.sha256(b'data').hexdigest())

    def test_the_recorder_refuses_symlinks_anywhere_on_the_path(self):
        real = self.make('rs/real', b'r')
        (self.tree / 'rs' / 'link').symlink_to(real)
        (self.tree / 'rsdir').symlink_to(self.tree / 'rs')
        for given in (self.tree / 'rs' / 'link', self.tree / 'rsdir' / 'real'):
            result = self.record(given)
            self.assertEqual(result.returncode, 1, given)
            self.assertIn('SYMLINK', result.stdout)
        self.assertEqual(self.ledger_records(), [])

    def test_a_shared_hard_link_is_refused_by_both_tools(self):
        f = self.make('hl/f', b'shared')
        self.assertRecorded(self.record(f), f)
        os.link(f, self.tree / 'hl' / 'g')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('SHARED HARD LINK: link count 2', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'shared').hexdigest())
        self.assertKeptIntact(self.tree / 'hl' / 'g', hashlib.sha256(b'shared').hexdigest())
        result = self.record(self.tree / 'hl' / 'g')
        self.assertEqual(result.returncode, 1)
        self.assertIn('SHARED HARD LINK', result.stdout)

    def test_a_file_open_by_a_live_process_is_refused_until_it_is_closed(self):
        f = self.make('open/f', b'in use')
        self.assertRecorded(self.record(f), f)
        with open(f, 'rb') as fh:
            proc = self.spawn('sleep', '120', stdin=fh)
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn(f'OPEN: live process {proc.pid}', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'in use').hexdigest())
        proc.kill()
        proc.wait()
        result = self.reap()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(f.exists(), 'the live process was the only reason it was kept')

    def test_a_file_whose_directory_holds_a_live_processs_cwd_is_refused(self):
        f = self.make('cwd/f', b'workspace')
        (self.tree / 'cwd' / 'sub').mkdir()
        self.assertRecorded(self.record(f), f)
        proc = self.spawn('sleep', '120', cwd=self.tree / 'cwd' / 'sub', stdin=subprocess.DEVNULL)
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn(f'IN USE: live process {proc.pid}', result.stdout)
        self.assertIn('working directory', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'workspace').hexdigest())
        proc.kill()
        proc.wait()
        self.assertEqual(self.reap().returncode, 0)
        self.assertFalse(f.exists())

    def test_a_retain_flagged_file_is_kept_and_the_flag_is_never_lifted(self):
        f = self.make('keep/evidence.json', b'evidence')
        self.assertRecorded(self.record(f, retain=True), f)
        self.assertRecorded(self.record(f), f)  # a later plain record does not lift retain
        result = self.reap()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('kept (RETAIN', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'evidence').hexdigest())
        result = self.reap(f)
        self.assertEqual(result.returncode, 1)
        self.assertIn('REFUSED (RETAIN', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'evidence').hexdigest())

    def test_files_listed_aliased_or_contained_by_a_retained_manifest_are_kept(self):
        listed, aliased, contained = self.make('m/listed', b'1'), self.make('m/aliased', b'2'), self.make('kept/c', b'3')
        self.assertRecorded(self.record(listed, aliased, contained), listed, aliased, contained)
        alias = self.state / 'alias-of-aliased'
        alias.symlink_to(aliased)
        manifest = self.state / 'retained.txt'
        manifest.write_text(f'# retained artifacts\n{sha(listed)}  {listed}\n{alias}\n\n{self.tree / "kept"}\n')
        result = self.reap(retained=[manifest])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path, data in ((listed, b'1'), (aliased, b'2'), (contained, b'3')):
            self.assertKeptIntact(path, hashlib.sha256(data).hexdigest())
            self.assertEqual(self.decisions(path), ['KEPT'])
        result = self.reap(listed, retained=[manifest])
        self.assertEqual(result.returncode, 1)
        self.assertIn('RETAINED: listed in a --retained manifest', result.stdout)
        self.assertEqual(self.reap().returncode, 0, 'without the manifest they are ordinary recorded scratch')
        self.assertFalse(listed.exists() or aliased.exists() or contained.exists())

    def test_an_unreadable_retained_manifest_refuses_the_whole_run(self):
        f = self.make('um/f')
        self.assertRecorded(self.record(f), f)
        manifest = self.state / 'bad-manifest.txt'
        manifest.write_text('relative/path/that/protects/nothing\n')
        result = self.reap(retained=[manifest])
        self.assertEqual(result.returncode, 2)
        self.assertIn('protects nothing', result.stderr)
        result = self.reap(retained=[self.state / 'no-such-manifest'])
        self.assertEqual(result.returncode, 2)
        escaped = self.state / 'escaped-manifest.txt'
        escaped.write_text(f'\\{"0" * 64}  {self.tree}/odd\\nname\n')  # sha256sum's form for an unusual name
        result = self.reap(retained=[escaped])
        self.assertEqual(result.returncode, 2)
        self.assertIn('escaped sha256sum line', result.stderr)
        self.assertKeptIntact(f, hashlib.sha256(b'scratch\n').hexdigest())

    def test_a_directory_argument_is_refused_and_never_walked(self):
        f = self.make('dirarg/f', b'inside')
        self.assertRecorded(self.record(f), f)
        for given in (self.tree / 'dirarg', f'{self.tree / "dirarg"}/'):
            result = self.reap(given)
            self.assertEqual(result.returncode, 1)
            self.assertIn('DIRECTORY ARGUMENT', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'inside').hexdigest())
        result = self.record(self.tree / 'dirarg')
        self.assertEqual(result.returncode, 1)
        self.assertIn('DIRECTORY', result.stdout)
        result = run(['bash', REAP, '--', self.state], env=self.env())
        self.assertEqual(result.returncode, 2)
        self.assertIn('is a directory', result.stderr)

    def test_a_path_outside_the_sandbox_is_refused_by_both_tools(self):
        outside = self.state / 'outside.txt'
        outside.write_bytes(b'not scratch')
        result = self.record(outside)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f'OUTSIDE THE SANDBOX: not under {SANDBOX}/', result.stdout)
        self.assertEqual(self.ledger_records(), [])
        # A ledger that nonetheless holds such a path, with a VALID binding and every identity field TRUE: the
        # only thing standing between it and the shredder is the sandbox check.
        self.forge(outside)
        self.forge(f'{SANDBOX}/../..{outside}')
        self.forge(f'{SANDBOX}x/sibling-prefix')
        result = self.reap()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('OUTSIDE THE SANDBOX'), 2, result.stdout)
        self.assertIn('not in normal form', result.stdout)
        self.assertKeptIntact(outside, hashlib.sha256(b'not scratch').hexdigest())

    def test_a_file_tracked_by_git_is_refused(self):
        if not shutil.which('git'):
            self.skipTest('git is not installed')
        repo = self.tree / 'repo'
        repo.mkdir()
        git('init', '-q', repo)
        f = self.make('repo/fixture.docx.txt', b'blank fixture')
        git('-C', repo, 'add', f.name)
        self.assertRecorded(self.record(f), f)
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('TRACKED by git', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'blank fixture').hexdigest())

    def test_a_failed_shred_is_never_followed_by_an_unlink(self):
        f = self.make('sf/f', b'must stay recoverable')
        self.assertRecorded(self.record(f), f)
        self.fake_shred('exit 3')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('SHRED-FAILED (shred exited 3', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'must stay recoverable').hexdigest())
        self.assertEqual(self.decisions(f), ['SHREDDING', 'SHRED-FAILED'])

    def test_a_shred_that_claims_success_without_overwriting_is_not_believed(self):
        f = self.make('su/f', b'still here')
        self.assertRecorded(self.record(f), f)
        self.fake_shred('exit 0')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('SHRED-UNVERIFIED', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'still here').hexdigest())

    def test_a_ledger_inside_the_sandbox_is_refused(self):
        f = self.make('li/f')
        inside = self.tree / 'ledger-dir' / 'agent.ledger'
        result = self.record(f, ledger=inside)
        self.assertEqual(result.returncode, 2)
        self.assertIn('OUTSIDE the scratch sandbox', result.stderr)
        self.assertFalse(inside.exists())
        self.assertEqual(self.reap(ledger=inside).returncode, 2)

    def test_a_ledger_or_ledger_directory_that_is_not_private_refuses_the_run(self):
        f = self.make('lp/f')
        self.assertRecorded(self.record(f), f)
        self.ledger.chmod(0o644)
        result = self.reap()
        self.assertEqual(result.returncode, 2)
        self.assertIn('must be private (0600)', result.stderr)
        self.ledger.chmod(0o600)
        self.state.chmod(0o755)
        try:
            result = self.reap()
        finally:
            self.state.chmod(0o700)
        self.assertEqual(result.returncode, 2)
        self.assertIn('must be private (0700)', result.stderr)
        self.assertKeptIntact(f, hashlib.sha256(b'scratch\n').hexdigest())

    def test_a_torn_or_unreadable_ledger_refuses_the_run(self):
        f = self.make('tl/f')
        self.assertRecorded(self.record(f), f)
        with open(self.ledger, 'ab') as fh:
            fh.write(b'{"v": 2, "kind": "rec')
        result = self.reap()
        self.assertEqual(result.returncode, 2)
        self.assertIn('torn append', result.stderr)
        self.assertKeptIntact(f, hashlib.sha256(b'scratch\n').hexdigest())

    def test_the_recorder_refuses_a_bulk_call_unless_declared_and_exempts_retain(self):
        files = [self.make(f'bulk/{i:02d}', str(i).encode()) for i in range(17)]
        result = self.record(*files)
        self.assertEqual(result.returncode, 1)
        self.assertIn('17 paths in one call (the bound is 16)', result.stderr)
        self.assertEqual(self.ledger_records(), [])
        result = self.record(*files, env=self.env(SCRATCH_LEDGER_BULK_DECLARATION='yes'))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.ledger_records(), [])
        self.assertEqual(self.record(*files[:16]).returncode, 0)
        self.assertEqual(self.record(*files, retain=True).returncode, 0, 'a retain record only prevents')
        reason = 'synthetic fixture set generated by this test, all mine'
        result = self.record(*files, env=self.env(SCRATCH_LEDGER_BULK_DECLARATION=reason))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'BULK CALL DECLARED (17 paths in one call (the bound is 16)) — '
                      f'SCRATCH_LEDGER_BULK_DECLARATION: {reason}', result.stderr)

    def test_the_recorder_refuses_to_be_driven_by_xargs(self):
        f = self.make('xa/f')
        result = run(['xargs', '-0', 'bash', RECORD, 'record', '--agent', 't', '--', self.ledger],
                     input_text=f'{f}\0', env=self.env())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('driven by xargs', result.stderr)
        self.assertEqual(self.ledger_records(), [])


class AnotherUidsFileSimulated(unittest.TestCase):
    """SIMULATED: an unprivileged test cannot create a file owned by another uid, and a user namespace maps
    every file it can see onto the same identity. So the reaper's pure identity comparison — the one it applies
    to the fstat of the opened file — is driven directly with a stat whose ONLY difference is st_uid."""

    def test_the_identity_check_refuses_a_file_owned_by_another_uid(self):
        module = load_module()
        with tempfile.NamedTemporaryFile() as fh:
            st = os.fstat(fh.fileno())
        record = {'dev': st.st_dev, 'ino': st.st_ino, 'size': st.st_size}
        fields = dict(st_mode=st.st_mode, st_dev=st.st_dev, st_ino=st.st_ino, st_nlink=1, st_size=st.st_size)
        self.assertIsNone(module.identity_refusal(record, types.SimpleNamespace(st_uid=os.geteuid(), **fields),
                                                  os.geteuid()), 'control: the same stat as yours passes')
        reason = module.identity_refusal(record, types.SimpleNamespace(st_uid=os.geteuid() + 1, **fields),
                                         os.geteuid())
        self.assertEqual(reason, f'NOT YOURS: owned by uid {os.geteuid() + 1}; you are uid {os.geteuid()}')

    def test_the_sandbox_root_has_no_override(self):
        module = load_module()
        self.assertEqual(module.sandbox_root(), str(SANDBOX))
        self.assertEqual(list(inspect.signature(module.sandbox_root).parameters), [])
        code = [line for line in inspect.getsource(module.sandbox_root).splitlines()
                if not line.strip().startswith('#')]  # the comment explains the rule in words the probe would hit
        self.assertEqual(code[-1].strip(), "return f'/tmp/claude-{os.geteuid()}'")
        self.assertFalse(any('environ' in line or 'getenv' in line or 'argv' in line for line in code), code)


class SessionReapRefusesSweeps(ScratchTree):
    def test_more_than_the_bound_is_refused_before_any_path_is_touched(self):
        files = [self.make(f'sweep/{i:02d}', str(i).encode()) for i in range(17)]
        result = self.session_reap(*files)
        self.assertEqual(result.returncode, 1)
        self.assertIn('REFUSED — this call has the shape of a whole-tree sweep: 17 paths in one call '
                      '(the bound is 16)', result.stderr)
        self.assertIn('bash scripts/reap-recorded-scratch.sh', result.stderr)
        self.assertEqual(result.stdout, '')
        for i, f in enumerate(files):
            self.assertKeptIntact(f, hashlib.sha256(str(i).encode()).hexdigest())

    def test_at_the_bound_the_guard_does_not_fire(self):
        absent = [self.tree / 'absent' / f'{i:02d}' for i in range(16)]
        result = self.session_reap(*absent)
        self.assertNotIn('whole-tree sweep', result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 16, result.stdout + result.stderr)
        self.assertTrue(all('skipped (absent)' in line or 'REFUSED (outside /tmp/claude-1000/)' in line
                            for line in lines), result.stdout)

    def test_a_token_or_short_declaration_is_refused(self):
        absent = [self.tree / 'absent' / f'{i:02d}' for i in range(17)]
        for token, message in (('true', 'must be a REASON'), ('too short', 'a declaration is prose')):
            result = self.session_reap(*absent, env=self.env(REAP_SESSION_BULK_DECLARATION=token))
            self.assertEqual(result.returncode, 1)
            self.assertIn(message, result.stderr)
            self.assertEqual(result.stdout, '')

    def test_a_declared_bulk_call_proceeds_and_echoes_its_reason(self):
        absent = [self.tree / 'absent' / f'{i:02d}' for i in range(17)]
        reason = 'test of the declared path; every operand is an absent path'
        result = self.session_reap(*absent, env=self.env(REAP_SESSION_BULK_DECLARATION=reason))
        self.assertIn(f'REAP_SESSION_BULK_DECLARATION: {reason}', result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 17, result.stdout)

    def test_a_single_path_fed_by_xargs_is_refused(self):
        result = run(['xargs', '-0', 'bash', SESSION_REAP], input_text=f'{self.tree / "absent"}\0', env=self.env())
        self.assertIn('driven by xargs', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_a_single_path_fed_by_find_exec_is_refused(self):
        result = run(['find', self.tree, '-maxdepth', '0', '-exec', 'bash', SESSION_REAP, self.tree / 'absent', ';'],
                     env=self.env())
        self.assertIn('driven by find', result.stderr)
        self.assertEqual(result.stdout, '')


# ─── F1: reap-session-scratch.sh shredded a file whose inode another name shares ───────────────────────────────
class F1SessionReaperRefusesSharedInodes(ScratchTree):
    def setUp(self):
        super().setUp()
        self.require_session_sandbox()
        self.fake_shred()

    def test_a_hard_linked_file_is_refused_and_shred_is_never_invoked(self):
        f = self.make('hl1/f', b'shared data')
        other = self.state / 'outside-hard-link'
        try:
            os.link(f, other)  # a name OUTSIDE the sandbox, when /tmp and this directory share a filesystem
        except OSError:
            other = self.tree / 'hl1' / 'other-name'
            os.link(f, other)
        result = self.session_reap(f)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('SHARED HARD LINK: link count 2', result.stdout)
        self.assertEqual(self.shred_calls(), [])
        self.assertKeptIntact(f, hashlib.sha256(b'shared data').hexdigest())
        self.assertKeptIntact(other, hashlib.sha256(b'shared data').hexdigest())

    def test_a_local_clones_object_files_are_refused(self):
        """The verified vector: `git clone <path on /opt> <scratch>` hard-links .git/objects to the SOURCE."""
        if not shutil.which('git'):
            self.skipTest('git is not installed')
        src = self.state / 'src-repo'
        src.mkdir()
        git('init', '-q', src)
        (src / 'a.txt').write_text('synthetic\n')
        git('-C', src, 'add', 'a.txt')
        git('-C', src, 'commit', '-q', '-m', 'synthetic')
        git('-C', src, 'gc', '-q')
        git('clone', '-q', '--no-checkout', src, self.tree / 'clone')
        targets = sorted(p for p in (self.tree / 'clone' / '.git' / 'objects').rglob('*') if p.is_file())
        self.assertTrue(targets)
        before = {p: sha(p) for p in targets}
        for target in targets[:16]:
            result = self.session_reap(target)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn('REFUSED', result.stdout)
        self.assertEqual(self.shred_calls(), [])
        for p, digest in before.items():
            self.assertEqual(sha(p), digest)


# ─── F2: the sweep guard trusted process NAMES; the bound is now counted across calls ──────────────────────────
class F2TheBoundHoldsWhateverDrivesTheCalls(ScratchTree):
    def files(self, n, prefix='w'):
        return [self.make(f'{prefix}/{i:02d}', f'{prefix}{i}'.encode()) for i in range(n)]

    def test_the_recorder_refuses_past_the_bound_across_direct_calls_with_no_driver(self):
        files = self.files(40)
        first = self.record(*files[:16])
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.record(*files[16:32])
        self.assertEqual(second.returncode, 1)
        self.assertIn('undeclared in the last', second.stderr)
        third = self.record(*files[32:])
        self.assertEqual(third.returncode, 1)
        self.assertEqual(len(self.ledger_records()), 16)
        reason = 'the remaining synthetic fixtures of this test, all created here'
        declared = self.record(*files[16:], env=self.env(SCRATCH_LEDGER_BULK_DECLARATION=reason))
        self.assertEqual(declared.returncode, 0, declared.stderr)
        self.assertIn(f'SCRATCH_LEDGER_BULK_DECLARATION: {reason}', declared.stderr)
        self.assertEqual(len(self.ledger_records()), 40)

    def test_the_recorder_is_bounded_under_busybox_xargs(self):
        busybox = shutil.which('busybox')
        if not busybox:
            self.skipTest('busybox is not installed')
        files = self.files(40)
        result = run([busybox, 'xargs', '-0', '-n', '16', 'bash', RECORD, 'record', '--agent', 't', '--', self.ledger],
                     input_text=''.join(f'{f}\0' for f in files), env=self.env())
        self.assertNotEqual(result.returncode, 0)
        self.assertLessEqual(len(self.ledger_records()), 16)

    def test_a_driver_cannot_mint_a_fresh_ledger_per_file(self):
        """`xargs -I{}` can build the LEDGER name from each file, and a fresh ledger is a fresh window. Such a
        name needs a chain of new directories, and only the final ledger directory is ever created."""
        files = self.files(3, prefix='mint')
        for f in files:
            result = self.record(f, ledger=f'{self.state}/x{f}.ledger')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('cannot be created', result.stderr)
        self.assertFalse((self.state / 'x').exists())
        self.assertEqual(self.record(files[0], ledger=self.state / 'one-level' / 'agent.ledger').returncode, 0,
                         'control: the ledger directory itself is still created')

    def test_the_recorder_is_bounded_under_xargs_run_by_another_name(self):
        batch = self.state / 'batch'
        batch.symlink_to(shutil.which('xargs'))
        files = self.files(40)
        result = run([batch, '-0', '-n', '16', 'bash', RECORD, 'record', '--agent', 't', '--', self.ledger],
                     input_text=''.join(f'{f}\0' for f in files), env=self.env())
        self.assertNotEqual(result.returncode, 0)
        self.assertLessEqual(len(self.ledger_records()), 16)

    def test_the_session_reaper_refuses_past_the_bound_across_calls(self):
        absent = [self.tree / 'absent' / f'{i:02d}' for i in range(40)]
        first = self.session_reap(*absent[:16])
        self.assertEqual(len(first.stdout.splitlines()), 16, first.stdout + first.stderr)
        second = self.session_reap(absent[16])
        self.assertEqual(second.returncode, 1)
        self.assertIn('undeclared in the last', second.stderr)
        self.assertEqual(second.stdout, '')
        reason = 'every operand of this test is an absent path'
        declared = self.session_reap(*absent[16:], env=self.env(REAP_SESSION_BULK_DECLARATION=reason))
        self.assertEqual(len(declared.stdout.splitlines()), 24, declared.stdout + declared.stderr)

    def test_the_session_reaper_is_bounded_under_busybox_xargs(self):
        self.require_session_sandbox()
        busybox = shutil.which('busybox')
        if not busybox:
            self.skipTest('busybox is not installed')
        self.fake_shred()
        files = self.files(40)
        run([busybox, 'xargs', '-0', '-n', '16', 'bash', SESSION_REAP],
            input_text=''.join(f'{f}\0' for f in files), env=self.env())
        self.assertLessEqual(len(self.shred_calls()), 16)
        self.assertGreater(len(self.shred_calls()), 0, 'control: the first batch is inside the bound')

    def test_the_session_reaper_is_bounded_under_setsid_f(self):
        self.require_session_sandbox()
        if not shutil.which('setsid'):
            self.skipTest('setsid is not installed')
        self.fake_shred()
        files = self.files(40)
        done = self.state / 'done'
        script = f'bash {shlex.quote(str(SESSION_REAP))} "$@"; echo x >> {shlex.quote(str(done))}'
        run(['xargs', '-0', '-n', '16', 'setsid', '-f', 'sh', '-c', script, 'sh'],
            input_text=''.join(f'{f}\0' for f in files), env=self.env())
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and (not done.exists() or len(done.read_text().split()) < 3):
            time.sleep(0.1)
        self.assertEqual(len(done.read_text().split()), 3, 'all three detached calls finished')
        self.assertLessEqual(len(self.shred_calls()), 16)

    def test_a_window_state_inside_the_sandbox_is_refused(self):
        result = self.session_reap(self.tree / 'absent', env=self.env(XDG_STATE_HOME=self.tree / 'xdg'))
        self.assertEqual(result.returncode, 1)
        self.assertIn('CANNOT TELL', result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertFalse((self.tree / 'xdg').exists(), 'nothing is created inside the sandbox')

    def guard(self, window, count, declaration=None):
        env = self.env(**({'PROBE_DECLARATION': declaration} if declaration else {}))
        return run(['bash', '-c', '. "$1" && sweep_guard probe "$2" 16 PROBE_DECLARATION "$3"', 'probe',
                    SCRIPTS / 'lib' / 'sweep-guard.sh', count, window], env=env)

    def test_the_guard_itself_refuses_a_window_inside_the_sandbox(self):
        """The guard's own check, isolated from sweep_guard_state_file's (the two stand in series)."""
        inside = self.tree / 'wdir'
        inside.mkdir(mode=0o700)
        result = self.guard(inside / 'x.window', 1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('CANNOT TELL', result.stderr)
        self.assertFalse((inside / 'x.window').exists())
        outside = self.state / 'wdir'
        outside.mkdir(mode=0o700)
        result = self.guard(outside / 'x.window', 1)
        self.assertEqual(result.returncode, 0, 'control: the same call with the window outside the sandbox passes')
        self.assertRegex((outside / 'x.window').read_text(), r'\A[1-9][0-9]* 1 u\n\Z')
        self.assertEqual(stat.S_IMODE((outside / 'x.window').stat().st_mode), 0o600)

    def test_a_damaged_window_is_cannot_tell(self):
        wdir = self.state / 'damaged'
        wdir.mkdir(mode=0o700)
        now = int(time.time())
        cases = {
            'a torn last line': f'{now} 1 u\n{now} 1',
            'a leading zero, which bash reads as octal': f'{now} 010 u\n',
            'a count past 2^63, which bash wraps negative': f'{now} 16 u\n{now} 9223372036854775808 u\n',
            'a fourth field': f'{now} 1 u extra\n',
            'an unknown flag': f'{now} 1 z\n',
        }
        for label, content in cases.items():
            with self.subTest(window=label):
                window = wdir / f'{len(label)}.window'
                fd = os.open(window, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.write(fd, content.encode())
                os.close(fd)
                result = self.guard(window, 1)
                self.assertEqual(result.returncode, 1, label)
                self.assertIn('CANNOT TELL', result.stderr)
                self.assertEqual(window.read_text(), content, 'a refused call appends nothing')
        for label, mode in (('writable but unreadable, so a read sees nothing', 0o200),
                            ('readable by others', 0o644)):
            with self.subTest(window=label):
                window = wdir / f'mode-{mode:o}.window'
                fd = os.open(window, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.write(fd, f'{now} 16 u\n'.encode())
                os.close(fd)
                window.chmod(mode)
                self.addCleanup(window.chmod, 0o600)
                result = self.guard(window, 1)
                self.assertEqual(result.returncode, 1, label)
                self.assertIn('CANNOT TELL', result.stderr)
        control = wdir / 'control.window'
        fd = os.open(control, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.write(fd, f'{now - 10} 15 u\n{now - 3600} 500 u\n{now} 99 d\n'.encode())
        os.close(fd)
        self.assertEqual(self.guard(control, 1).returncode, 0, 'control: 15 recent + 1 is inside the bound')
        self.assertEqual(self.guard(control, 1).returncode, 1, 'and the next path is not')

    def test_a_symlinked_window_file_is_refused(self):
        self.xdg.mkdir(mode=0o700)
        (self.xdg / 'scratch-sweep-guard').mkdir(mode=0o700)
        target = self.state / 'elsewhere'
        target.write_text('')
        (self.xdg / 'scratch-sweep-guard' / 'reap-session-scratch.window').symlink_to(target)
        result = self.session_reap(self.tree / 'absent')
        self.assertEqual(result.returncode, 1)
        self.assertIn('CANNOT TELL', result.stderr)
        self.assertIn('is a symbolic link', result.stderr)
        self.assertEqual(target.read_text(), '')


# ─── F3: the reaper trusted any well-formed ledger line ───────────────────────────────────────────────────────
class F3LedgerLinesAreBoundToTheRecorder(ScratchTree):
    def test_a_ledger_written_by_a_tree_walk_reaps_nothing(self):
        files = [self.make(f'walk/{i}', str(i).encode()) for i in range(5)]
        fd = os.open(self.ledger, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        for f in files:  # exactly the df80fa58 line shape, written without the recorder
            st = f.stat()
            line = {'v': 1, 'kind': 'record', 'path': str(f), 'dev': st.st_dev, 'ino': st.st_ino,
                    'size': st.st_size, 'sha256': sha(f), 'uid': os.geteuid(), 'agent': 'nobody-recorded-this',
                    'retain': False, 'recorded_at': 'tree-walk'}
            os.write(fd, (json.dumps(line) + '\n').encode())
        os.close(fd)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('would shred', result.stdout)
        for i, f in enumerate(files):
            self.assertKeptIntact(f, hashlib.sha256(str(i).encode()).hexdigest())

    def test_one_unbound_line_refuses_the_whole_ledger(self):
        a, b = self.make('ub/a', b'a'), self.make('ub/b', b'b')
        self.assertRecorded(self.record(a), a)
        self.forge(b, sign=False)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('not bound to the recorder', result.stderr)
        self.assertNotIn('would shred', result.stdout)
        self.assertKeptIntact(a, hashlib.sha256(b'a').hexdigest())
        self.assertKeptIntact(b, hashlib.sha256(b'b').hexdigest())
        again = self.record(self.make('ub/c', b'c'))
        self.assertEqual(again.returncode, 2, 'the recorder will not extend a ledger that can never be reaped')
        self.assertIn('not bound to the recorder', again.stderr)

    def test_a_line_copied_from_another_ledger_is_unbound_here(self):
        a, b = self.make('cp/a', b'a'), self.make('cp/b', b'b')
        other = self.state / 'other.ledger'
        self.assertRecorded(self.record(a), a)
        self.assertRecorded(self.record(b, ledger=other), b, ledger=other)
        line = other.read_bytes().splitlines()[0]
        copied = json.loads(line)
        copied['seq'] = 2
        with open(self.ledger, 'ab') as fh:  # the other ledger's MAC does not verify under this ledger's key
            fh.write((json.dumps(copied) + '\n').encode())
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('not bound to the recorder', result.stderr)

    def test_a_signed_line_with_an_extra_field_is_not_a_record(self):
        """The field check, isolated from the MAC: this line's MAC is VALID (it covers the extra field too)."""
        a, b = self.make('xf/a', b'a'), self.make('xf/b', b'b')
        self.assertRecorded(self.record(a), a)
        self.forge(b, note='a field the recorder never writes')
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('not a version-2 record', result.stderr)
        self.assertNotIn('would shred', result.stdout)

    def test_a_line_without_its_mac_is_refused_not_crashed(self):
        a, b = self.make('nm2/a', b'a'), self.make('nm2/b', b'b')
        self.assertRecorded(self.record(a), a)
        self.forge(b, drop=('mac',))
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('not a version-2 record', result.stderr)

    def test_a_reordered_or_duplicated_line_is_refused(self):
        a = self.make('rd/a', b'a')
        self.assertRecorded(self.record(a), a)
        with open(self.ledger, 'ab') as fh:
            fh.write(self.ledger.read_bytes())  # line 1 again, as line 2: valid MAC, wrong position
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('sequence', result.stderr)

    def test_a_ledger_with_records_and_no_key_is_refused_by_both_tools(self):
        a = self.make('nk/a', b'a')
        self.assertRecorded(self.record(a), a)
        key = Path(str(self.ledger) + '.key')
        key.rename(self.state / 'moved-key')
        self.assertEqual(self.reap(dry_run=True).returncode, 2)
        self.assertEqual(self.record(self.make('nk/b', b'b')).returncode, 2)
        self.assertKeptIntact(a, hashlib.sha256(b'a').hexdigest())


# ─── F4: a --retained line with anything extra protected nothing, silently ───────────────────────────────────
class F4RetainedManifestsParseStrictly(ScratchTree):
    def setUp(self):
        super().setUp()
        self.keep = self.make('f4/keep.txt', b'keep me')
        self.other = self.make('f4/other.txt', b'other')
        self.assertRecorded(self.record(self.keep, self.other), self.keep, self.other)

    def manifest(self, text, name='m.txt'):
        path = self.state / name
        path.write_text(text)
        return path

    def test_every_inexact_line_refuses_the_whole_run(self):
        keep, digest = self.keep, sha(self.keep)
        alias = self.state / 'alias'
        alias.symlink_to(keep)
        shapes = {
            'trailing space': f'{keep} \n',
            'trailing tab': f'{keep}\t\n',
            'trailing comment': f'{keep}  # evidence for the round-3 report\n',
            'find -printf %p\\t%s': f'{keep}\t7\n',
            'find -printf %p %s': f'{keep} 7\n',
            'stat -c %n %s': f'{keep} 7\n',
            'ls -l of an alias': f'lrwxrwxrwx 1 u u 10 Sep 29 14:00 {alias} -> {keep}\n',
            'ls -l of the file': f'-rw-rw-r-- 1 u u 7 Sep 29 14:00 {keep}\n',
            'sha256sum with a trailing blank': f'{digest}  {keep} \n',
            'sha256sum with one space': f'{digest} {keep}\n',
            'leading space': f' {keep}\n',
            'a whitespace-only line': f'{keep}\n   \n',
            'an exact path that reaches nothing': f'{self.tree}/f4/no-such-file\n',
            'a dot-dot path': f'{self.tree}/f4/../f4/keep.txt\n',
            'a double slash': f'/{keep}\n',
        }
        for label, text in shapes.items():
            with self.subTest(shape=label):
                result = self.reap(retained=[self.manifest(text)], dry_run=True)
                self.assertEqual(result.returncode, 2, f'{label}: {result.stdout}{result.stderr}')
                self.assertIn('nothing is reaped', result.stderr)
                self.assertNotIn('would shred', result.stdout)
                self.assertKeptIntact(keep, hashlib.sha256(b'keep me').hexdigest())

    def test_an_inexact_line_refuses_even_when_its_literal_text_names_a_real_file(self):
        """The form rules, isolated from the reaches-nothing rule: a file whose NAME is the line's literal text
        exists, so only the form rule stands between the manifest and protecting the wrong file."""
        for label, name in (('trailing space', 'keep.txt '), ('trailing comment', 'keep.txt  # evidence')):
            with self.subTest(shape=label):
                decoy = self.make(f'f4/{name}', b'decoy')
                result = self.reap(retained=[self.manifest(f'{decoy}\n')], dry_run=True)
                self.assertEqual(result.returncode, 2, f'{label}: {result.stdout}{result.stderr}')
                self.assertNotIn('would shred', result.stdout)
                self.assertKeptIntact(self.keep, hashlib.sha256(b'keep me').hexdigest())

    def test_the_exact_forms_are_accepted_and_protect(self):
        keep, digest = self.keep, sha(self.keep)
        (self.tree / 'f4d').mkdir()
        inner = self.make('f4d/inner', b'inner')
        self.assertRecorded(self.record(inner), inner)
        for label, text in {
            'bare path, comment and blank lines': f'# evidence\n\n{keep}\n',
            'sha256sum text mode': f'{digest}  {keep}\n',
            'sha256sum binary mode': f'{digest} *{keep}\n',
            'CRLF line endings': f'# evidence\r\n{keep}\r\n',
        }.items():
            with self.subTest(form=label):
                result = self.reap(keep, retained=[self.manifest(text)], dry_run=True)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn('RETAINED: listed in a --retained manifest', result.stdout)
        result = self.reap(inner, retained=[self.manifest(f'{self.tree / "f4d"}/\n')], dry_run=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('a directory listed in a --retained manifest', result.stdout)
        result = self.reap(self.other, retained=[self.manifest(f'{keep}\n')], dry_run=True)
        self.assertEqual(result.returncode, 0, 'control: an unlisted recorded file is still reapable')
        self.assertIn('would shred', result.stdout)


# ─── F5: retain was per ledger; it is global across the ledger directory ─────────────────────────────────────
class F5RetainIsGlobalAcrossTheLedgerDirectory(ScratchTree):
    def test_a_file_retained_in_one_ledger_is_kept_through_another(self):
        f = self.make('f5/evidence.txt', b'evidence')
        a, b = self.state / 'agentA.ledger', self.state / 'agentB.ledger'
        self.assertRecorded(self.record(f, retain=True, ledger=a, agent='agentA'), f, ledger=a)
        self.assertRecorded(self.record(f, ledger=b, agent='agentB'), f, ledger=b)
        result = self.reap(ledger=b)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('kept (RETAIN', result.stdout)
        self.assertIn(str(a), result.stdout)
        result = self.reap(f, ledger=b)
        self.assertEqual(result.returncode, 1)
        self.assertKeptIntact(f, hashlib.sha256(b'evidence').hexdigest())

    def test_retain_follows_the_file_by_identity_after_a_rename(self):
        f = self.make('f5r/evidence.txt', b'evidence')
        a, b = self.state / 'agentA.ledger', self.state / 'agentB.ledger'
        self.assertRecorded(self.record(f, retain=True, ledger=a), f, ledger=a)
        moved = self.tree / 'f5r' / 'renamed.txt'
        f.rename(moved)
        self.assertRecorded(self.record(moved, ledger=b), moved, ledger=b)
        result = self.reap(ledger=b)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('kept (RETAIN', result.stdout)
        self.assertKeptIntact(moved, hashlib.sha256(b'evidence').hexdigest())

    def test_a_reused_inode_does_not_inherit_retain(self):
        """The retain line is SIMULATED (signed with the ledger's own key, as the recorder would have written it
        for a file that was later replaced): it carries new-0.txt's device and inode but the retained file's
        content hash. Inode reuse itself was measured by the verifier (5 of 5 on this filesystem)."""
        new0, new1 = self.make('f5i/new-0.txt', b'unrelated 0'), self.make('f5i/new-1.txt', b'unrelated 1')
        self.assertRecorded(self.record(new1), new1)
        st = new0.stat()
        self.forge(self.tree / 'f5i' / 'evidence.json', dev=st.st_dev, ino=st.st_ino, size=8,
                   sha256=hashlib.sha256(b'evidence').hexdigest(), retain=True)
        self.assertRecorded(self.record(new0), new0)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'would shred: {new0}', result.stdout)
        self.assertIn(f'would shred: {new1}', result.stdout)

    def test_a_sibling_ledger_that_cannot_be_read_refuses_the_run(self):
        f = self.make('f5s/f', b'f')
        self.assertRecorded(self.record(f), f)
        for label, content in (('garbage', b'not json\n'), ('torn', b'{"path": "/x", "retain": tr'),
                               ('wrong shape', b'[1, 2, 3]\n')):
            with self.subTest(sibling=label):
                sibling = self.state / f'{label.replace(" ", "-")}.ledger'
                fd = os.open(sibling, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.write(fd, content)
                os.close(fd)
                result = self.reap(dry_run=True)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn(str(sibling), result.stderr)
                sibling.rename(self.state / f'{label.replace(" ", "-")}.set-aside')
        self.assertEqual(self.reap(dry_run=True).returncode, 0, 'control: with the siblings set aside it runs')
        self.assertKeptIntact(f, hashlib.sha256(b'f').hexdigest())

    def test_a_symlinked_sibling_ledger_refuses_the_run(self):
        f = self.make('f5l/f', b'f')
        self.assertRecorded(self.record(f), f)
        target = self.state / 'target.txt'
        target.write_text('')
        (self.state / 'linked.ledger').symlink_to(target)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('linked.ledger', result.stderr)


# ─── F6: the git check failed open on exit 128 and on git's own files ────────────────────────────────────────
class F6GitCheckFailsClosed(ScratchTree):
    def setUp(self):
        super().setUp()
        if not shutil.which('git'):
            self.skipTest('git is not installed')
        self.repo = self.tree / 'repo6'
        self.repo.mkdir()
        git('init', '-q', self.repo)
        self.tracked = self.make('repo6/tracked.txt', b'tracked')
        git('-C', self.repo, 'add', 'tracked.txt')
        git('init', '-q', '--bare', self.tree / 'bare.git')
        shape = self.tree / 'shape'
        (shape / 'objects').mkdir(parents=True)
        (shape / 'refs').mkdir()
        (shape / 'HEAD').write_text('not a ref\n')
        self.shaped = self.make('shape/objects/blob', b'object data')

    def unreadable_index(self):
        index = self.repo / '.git' / 'index'
        index.chmod(0)
        self.addCleanup(index.chmod, 0o644)

    def test_an_unreadable_index_is_cannot_tell_not_untracked(self):
        self.assertRecorded(self.record(self.tracked), self.tracked)
        self.unreadable_index()
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('CANNOT TELL', result.stdout)
        self.assertKeptIntact(self.tracked, hashlib.sha256(b'tracked').hexdigest())

    def test_files_inside_a_git_directory_are_refused(self):
        head, bare_head = self.repo / '.git' / 'HEAD', self.tree / 'bare.git' / 'HEAD'
        self.assertRecorded(self.record(head, bare_head, self.shaped), head, bare_head, self.shaped)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn('would shred', result.stdout)
        self.assertEqual(result.stdout.count('🔴 REFUSED ('), 3, result.stdout)
        self.assertIn('3 REFUSED', result.stdout)
        self.assertIn('INSIDE A .git DIRECTORY', result.stdout)
        self.assertIn('INSIDE A GIT DIRECTORY', result.stdout)
        self.assertIn('CANNOT TELL — a repository marker', result.stdout)

    def test_the_session_reaper_fails_closed_the_same_way(self):
        self.require_session_sandbox()
        self.fake_shred()
        self.unreadable_index()
        for target, message in ((self.tracked, 'CANNOT TELL — git exited 128'),
                                (self.repo / '.git' / 'HEAD', 'INSIDE A .git DIRECTORY'),
                                (self.tree / 'bare.git' / 'HEAD', 'INSIDE A GIT DIRECTORY'),
                                (self.shaped, 'CANNOT TELL — a repository marker')):
            with self.subTest(target=str(target)):
                result = self.session_reap(target)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(message, result.stdout)
        self.assertEqual(self.shred_calls(), [])

    def test_a_git_file_at_a_work_tree_root_is_refused_by_both_tools(self):
        """A worktree's or separate-git-dir's `.git` is a FILE that git answers for as untracked. Only the
        name rule refuses it; neither `rev-parse` nor `ls-files` does."""
        wt = self.tree / 'wt6'
        git('init', '-q', '--separate-git-dir', self.tree / 'sep6.git', wt)
        gitfile = wt / '.git'
        self.assertTrue(gitfile.is_file() and not gitfile.is_symlink())
        self.assertRecorded(self.record(gitfile), gitfile)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('INSIDE A .git DIRECTORY', result.stdout)
        self.assertNotIn('would shred', result.stdout)
        if os.geteuid() == SESSION_SANDBOX_UID:
            self.fake_shred()
            result = self.session_reap(gitfile)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('INSIDE A .git DIRECTORY', result.stdout)
            self.assertEqual(self.shred_calls(), [])


# ─── F7: nothing re-checked the file between the scans and the overwrite ─────────────────────────────────────
class F7TheFileIsRecheckedImmediatelyBeforeTheOverwrite(ScratchTree):
    def concurrent_actor(self, action):
        """A stand-in `git` first on PATH acts once — during the reaper's git scan, after the identity and sha256
        checks — then runs the real git, exactly as the verifier's instrumented reproduction did."""
        real = shutil.which('git')
        if not real:
            self.skipTest('git is not installed')
        marker = self.state / 'actor-ran'
        self.fake('git', f'if [ ! -e {shlex.quote(str(marker))} ]; then : > {shlex.quote(str(marker))}; {action}; fi\n'
                         f'exec {shlex.quote(real)} "$@"')
        return marker

    def hard_link_during_the_scans(self, dry_run):
        f = self.make('f7/f.txt', b'late link')
        self.assertRecorded(self.record(f), f)
        self.assertEqual(f.stat().st_nlink, 1)
        late = self.state / 'late-hard-link'
        marker = self.concurrent_actor(f'ln {shlex.quote(str(f))} {shlex.quote(str(late))}')
        result = self.reap(dry_run=dry_run)
        self.assertTrue(marker.exists(), 'the actor ran')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('SHARED HARD LINK: link count 2 at the moment of overwriting', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'late link').hexdigest())
        self.assertKeptIntact(late, hashlib.sha256(b'late link').hexdigest())

    def test_a_hard_link_made_during_the_scans_is_refused_in_a_dry_run(self):
        self.hard_link_during_the_scans(dry_run=True)

    def test_a_hard_link_made_during_the_scans_is_refused_in_a_real_run(self):
        self.hard_link_during_the_scans(dry_run=False)

    def test_a_link_made_after_the_recheck_is_caught_on_the_write_descriptor(self):
        """SIMULATED, in-process: the reaper's own re-check is wrapped so that a hard link appears the instant
        AFTER it returns — the gap between the re-check and the reopen for writing. Only the link count taken
        on the write descriptor stands in that gap."""
        import argparse
        import contextlib
        import io
        f = self.make('f7w/f.txt', b'gap link')
        self.assertRecorded(self.record(f), f)
        late = self.state / 'gap-hard-link'
        module = load_module()
        original = module.Reaper.recheck

        def recheck_then_link(reaper, path, leaf_fd, st):
            reason = original(reaper, path, leaf_fd, st)
            os.link(path, late)
            return reason

        module.Reaper.recheck = recheck_then_link
        args = argparse.Namespace(retained=[], dry_run=False, ledger=str(self.ledger), paths=[])
        out = io.StringIO()
        saved = os.environ.get('XDG_STATE_HOME')
        with contextlib.redirect_stdout(out):
            rc = module.Reaper(args).main()
        self.assertEqual(saved, os.environ.get('XDG_STATE_HOME'))
        self.assertEqual(rc, 1, out.getvalue())
        self.assertIn('changed at the moment of overwriting (link count 2); nothing was written', out.getvalue())
        self.assertKeptIntact(f, hashlib.sha256(b'gap link').hexdigest())
        self.assertKeptIntact(late, hashlib.sha256(b'gap link').hexdigest())

    def test_a_file_moved_away_during_the_scans_is_refused(self):
        f = self.make('f7m/f.txt', b'moved away')
        self.assertRecorded(self.record(f), f)
        away = self.state / 'moved-away.txt'
        self.concurrent_actor(f'mv {shlex.quote(str(f))} {shlex.quote(str(away))}')
        result = self.reap()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('CHANGED while it was being checked', result.stdout)
        self.assertKeptIntact(away, hashlib.sha256(b'moved away').hexdigest())


# ─── F8: a declaration of twelve spaces was accepted as prose ────────────────────────────────────────────────
class F8DeclarationsNeedTwelveVisibleCharacters(ScratchTree):
    def declaration_ok(self, decl):
        return run(['bash', '-c', '. "$1" && inflight_declaration_ok "$2"', 'probe', INFLIGHT, decl], env=self.env())

    def test_the_shared_check(self):
        refused = {'twelve spaces': ' ' * 12, 'twelve tabs': '\t' * 12, 'twelve newlines': '\n' * 12,
                   'mixed blanks': ' \t\n\r\v\f' * 4, 'eleven visible': 'abcdefghijk', 'eleven and blanks': ' a b c d e f g h i j k ',
                   'twelve no-break spaces': NBSP * 12, 'token true': 'true', 'token yes': 'yes'}
        for label, decl in refused.items():
            with self.subTest(refused=label):
                result = self.declaration_ok(decl)
                self.assertEqual(result.returncode, 1, label)
                self.assertIn('REFUSED', result.stderr)
        for label, decl in {'twelve visible': 'abcdefghijkl', 'spaced': 'a b c d e f g h i j k l',
                            'prose': 'merging two pull requests as one declared batch',
                            'empty means none offered': ''}.items():
            with self.subTest(accepted=label):
                self.assertEqual(self.declaration_ok(decl).returncode, 0, label)

    def test_the_sweep_guard_refuses_a_blank_declaration(self):
        absent = [self.tree / 'absent' / f'{i:02d}' for i in range(17)]
        result = self.session_reap(*absent, env=self.env(REAP_SESSION_BULK_DECLARATION=' ' * 12))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        files = [self.make(f'f8/{i:02d}', str(i).encode()) for i in range(17)]
        result = self.record(*files, env=self.env(SCRATCH_LEDGER_BULK_DECLARATION=' ' * 12))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.ledger_records(), [])

    def gh_stand_in(self):
        log = self.state / 'gh-calls.log'
        self.fake('gh', f'printf "%s\\n" "$*" >> {shlex.quote(str(log))}\nexit 97')
        return log

    def test_the_pre_push_hook_refuses_a_blank_declaration_before_touching_gh(self):
        log = self.gh_stand_in()
        result = run(['bash', PRE_PUSH, 'origin'], env=self.env(DECLARE_CANCELLATION=' ' * 12), cwd=self.state)
        self.assertEqual(result.returncode, 1)
        self.assertIn('REFUSED', result.stderr)
        self.assertFalse(log.exists(), 'gh was never consulted: the declaration was refused first')
        control = run(['bash', PRE_PUSH, 'origin'], env=self.env(DECLARE_CANCELLATION='a real reason, in words'),
                      cwd=self.state)
        self.assertNotEqual(control.returncode, 0)
        self.assertTrue(log.exists(), 'control: a real declaration passes the check and reaches gh (a stand-in)')

    def test_merge_pr_refuses_a_blank_declaration_before_touching_gh(self):
        log = self.gh_stand_in()
        repo = self.state / 'wt'
        repo.mkdir()
        git('init', '-q', repo)
        result = run(['bash', MERGE_PR, '1'], env=self.env(DECLARE_CANCELLATION='\t' * 12), cwd=repo)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(log.exists())
        control = run(['bash', MERGE_PR, '1'], env=self.env(DECLARE_CANCELLATION='a real reason, in words'), cwd=repo)
        self.assertNotEqual(control.returncode, 0)
        self.assertTrue(log.exists(), 'control: a real declaration reaches gh (a stand-in)')

    def test_push_with_cancellation_refuses_invisible_prose_before_git_push(self):
        log = self.state / 'git-calls.log'
        self.fake('git', f'printf "%s\\n" "$*" >> {shlex.quote(str(log))}\nexit 97')
        result = run(['bash', PUSH_WITH_CANCELLATION, NBSP * 12], env=self.env(), cwd=self.state)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(log.exists(), 'git was never run')


# ─── The lows: the caller's own cwd, read-only own files, an unwritable directory, record-at-creation ─────────
class LowsFalseRefusalsAndPartialDestruction(ScratchTree):
    def test_the_callers_own_shell_cwd_is_not_a_foreign_process(self):
        f = self.make('cwdself/out.json', b'mine')
        self.assertRecorded(self.record(f), f)
        parent = run(['bash', '-c', 'cd "$1" && bash "$2" --dry-run -- "$3"; exit $?', 'caller', f.parent, REAP,
                      self.ledger], env=self.env())
        self.assertEqual(parent.returncode, 0, parent.stdout + parent.stderr)
        self.assertIn(f'would shred: {f}', parent.stdout)
        grandparent = run(['bash', '-c', 'cd "$1" && bash -c "bash \\"\\$0\\" --dry-run -- \\"\\$1\\"; exit \\$?" '
                           '"$2" "$3"; exit $?', 'caller', f.parent, REAP, self.ledger], env=self.env())
        self.assertEqual(grandparent.returncode, 0, grandparent.stdout + grandparent.stderr)
        proc = self.spawn('sleep', '120', cwd=f.parent, stdin=subprocess.DEVNULL)
        control = self.reap(dry_run=True)
        self.assertEqual(control.returncode, 1, 'control: a process that is not our caller still refuses')
        self.assertIn(f'IN USE: live process {proc.pid}', control.stdout)

    def test_a_read_only_own_file_is_reaped(self):
        f = self.make('ro/token.txt', b'synthetic key material', mode=0o400)
        self.assertRecorded(self.record(f), f)
        result = self.reap(dry_run=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o400, 'a dry run changes nothing')
        result = self.reap()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(os.path.lexists(f))

    def test_a_read_only_file_whose_shred_fails_gets_its_mode_back(self):
        f = self.make('ro2/token.txt', b'synthetic key material', mode=0o400)
        self.assertRecorded(self.record(f), f)
        self.fake_shred('exit 3')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('SHRED-FAILED', result.stdout)
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o400)
        self.assertEqual(f.read_bytes(), b'synthetic key material')

    def test_a_file_in_an_unwritable_directory_is_not_overwritten(self):
        f = self.make('ronly-dir/f', b'would be zeroed and left behind')
        self.assertRecorded(self.record(f), f)
        f.parent.chmod(0o500)
        self.addCleanup(f.parent.chmod, 0o700)
        result = self.reap()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('not writable', result.stdout)
        self.assertEqual(f.read_bytes(), b'would be zeroed and left behind')

    def test_a_file_written_after_recording_is_refused_with_the_remedy(self):
        f = self.make('late/run.log', b'')
        self.assertRecorded(self.record(f), f)
        with open(f, 'ab') as fh:
            fh.write(b'written after it was recorded\n')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('CHANGED', result.stdout)
        self.assertIn('record it again', result.stdout)
        self.assertRecorded(self.record(f), f)
        result = self.reap()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(f.exists(), 'the latest record for a path is the one reaped')


if __name__ == '__main__':
    unittest.main()
