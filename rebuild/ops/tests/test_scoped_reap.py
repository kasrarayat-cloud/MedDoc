"""The recorded reaper and the sweep refusal: scripts/scratch-ledger.sh, scripts/reap-recorded-scratch.sh,
scripts/lib/sweep-guard.sh and the bulk guard added to scripts/reap-session-scratch.sh.

2026-09-29: `find <whole session scratchpad> -type f | xargs bash scripts/reap-session-scratch.sh` shredded 30
files other agents owned; a later `find … | xargs -0 -n 200 …` shredded 6,537, the cleanup's own logs included.
These tests prove every refusal that stops that with a concrete input, and a positive control for each door.

Every file touched lives in a private tree this test creates under /tmp/claude-<euid>/ (derived exactly as the
scripts derive it — the effective uid, nothing else) or in a private state directory OUTSIDE that sandbox. No
real scratchpad is ever named. The trees are removed by the test that made them.
"""
import hashlib
import importlib.util
import inspect
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[3]
SCRIPTS = REPOSITORY / 'scripts'
RECORD = SCRIPTS / 'scratch-ledger.sh'
REAP = SCRIPTS / 'reap-recorded-scratch.sh'
SESSION_REAP = SCRIPTS / 'reap-session-scratch.sh'
MODULE = SCRIPTS / 'lib' / 'scratch_ledger.py'
SANDBOX = Path(f'/tmp/claude-{os.geteuid()}')
DECLARATIONS = ('REAP_SESSION_BULK_DECLARATION', 'SCRATCH_LEDGER_BULK_DECLARATION', 'DECLARE_CANCELLATION')


def environment(**extra):
    env = {k: v for k, v in os.environ.items() if k not in DECLARATIONS}
    env.update(extra)
    return env


def run(cmd, env=None, cwd=None, input_text=None):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=env or environment(), cwd=cwd,
                          input=input_text, stdin=None if input_text is not None else subprocess.DEVNULL, timeout=120)


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

    def remove_own_tree(self, path):
        # Only the mkdtemp trees this test created: the prefix and the parent are asserted first.
        assert path.name.startswith(('scoped-reap-test-', 'scoped-reap-state-')), path
        if path.exists():
            shutil.rmtree(path)

    def make(self, relative, data=b'scratch\n'):
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def spawn(self, *args, **kwargs):
        proc = subprocess.Popen(list(args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        self.addCleanup(lambda: (proc.kill(), proc.wait()))
        return proc

    def record(self, *files, retain=False, env=None, ledger=None, agent='test-agent'):
        return run(['bash', RECORD, 'record', '--agent', agent, *(['--retain'] if retain else []), '--',
                    ledger or self.ledger, *files], env=env)

    def reap(self, *paths, retained=(), dry_run=False, env=None, ledger=None):
        flags = [x for m in retained for x in ('--retained', m)] + (['--dry-run'] if dry_run else [])
        return run(['bash', REAP, *flags, '--', ledger or self.ledger, *paths], env=env)

    def ledger_records(self):
        if not self.ledger.exists():
            return []
        return [json.loads(line) for line in self.ledger.read_text().splitlines()]

    def log(self):
        return [json.loads(line) for line in Path(str(self.ledger) + '.reap-log').read_text().splitlines()]

    def decisions(self, path):
        return [e['decision'] for e in self.log() if e.get('path') == str(path)]

    def forge(self, path, **fields):
        """Append a hand-written record — what a damaged or edited ledger could hold."""
        st = os.stat(path) if os.path.exists(path) else None
        record = {'v': 1, 'kind': 'record', 'path': str(path), 'dev': st.st_dev if st else 1,
                  'ino': st.st_ino if st else 1, 'size': st.st_size if st else 0,
                  'sha256': sha(path) if st else '0' * 64, 'uid': os.geteuid(), 'agent': 'forged',
                  'retain': False, 'recorded_at': '2026-09-29T00:00:00Z'}
        record.update(fields)
        fd = os.open(self.ledger, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps(record) + '\n').encode())
        finally:
            os.close(fd)

    def assertRecorded(self, result, *files):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual({r['path'] for r in self.ledger_records()} & {str(f) for f in files}, {str(f) for f in files})

    def assertKeptIntact(self, path, digest):
        self.assertTrue(path.is_file() and not path.is_symlink(), f'{path} must survive')
        self.assertEqual(sha(path), digest, f'{path} must survive UNCHANGED')


class RecordedReapPositiveControls(ScratchTree):
    def test_a_recorded_unchanged_unopened_own_file_is_shredded_and_the_log_records_it(self):
        f = self.make('work/out.json', b'{"synthetic": true}\n')
        digest, st = sha(f), f.stat()
        self.assertRecorded(self.record(f), f)
        (entry,) = self.ledger_records()
        self.assertEqual((entry['path'], entry['dev'], entry['ino'], entry['size'], entry['sha256'], entry['uid'],
                          entry['agent'], entry['retain']),
                         (str(f), st.st_dev, st.st_ino, st.st_size, digest, os.geteuid(), 'test-agent', False))
        self.assertEqual(stat.S_IMODE(self.ledger.stat().st_mode), 0o600)
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
        manifest.write_text(f'# retained artifacts\n{sha(listed)}  {listed}\n{alias}\n'
                            f'claude 644 4096 2026-09-29T00:00:00Z {self.tree / "kept"}\n')
        result = self.reap(retained=[manifest])
        self.assertEqual(result.returncode, 0, result.stdout)
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
        result = run(['bash', REAP, '--', self.state])
        self.assertEqual(result.returncode, 2)
        self.assertIn('is a directory', result.stderr)

    def test_a_path_outside_the_sandbox_is_refused_by_both_tools(self):
        outside = self.state / 'outside.txt'
        outside.write_bytes(b'not scratch')
        result = self.record(outside)
        self.assertEqual(result.returncode, 1)
        self.assertIn(f'OUTSIDE THE SANDBOX: not under {SANDBOX}/', result.stdout)
        self.assertEqual(self.ledger_records(), [])
        # A ledger that nonetheless holds such a path (damaged or edited): every identity field is TRUE,
        # so the only thing standing between it and the shredder is the sandbox check.
        self.forge(outside)
        self.forge(f'{SANDBOX}/../..{outside}')
        self.forge(f'{SANDBOX}x/sibling-prefix')
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout.count('OUTSIDE THE SANDBOX'), 2, result.stdout)
        self.assertIn('not in normal form', result.stdout)
        self.assertKeptIntact(outside, hashlib.sha256(b'not scratch').hexdigest())

    def test_a_file_tracked_by_git_is_refused(self):
        if not shutil.which('git'):
            self.skipTest('git is not installed')
        repo = self.tree / 'repo'
        repo.mkdir()
        quiet = dict(env=environment(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1'))
        self.assertEqual(run(['git', 'init', '-q', repo], **quiet).returncode, 0)
        f = self.make('repo/fixture.docx.txt', b'blank fixture')
        self.assertEqual(run(['git', '-C', repo, 'add', f.name], **quiet).returncode, 0)
        self.assertRecorded(self.record(f), f)
        result = self.reap()
        self.assertEqual(result.returncode, 1)
        self.assertIn('TRACKED by git', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'blank fixture').hexdigest())

    def fake_shred(self, body):
        bindir = self.state / 'fakebin'
        bindir.mkdir()
        shred = bindir / 'shred'
        shred.write_text(f'#!/bin/sh\n{body}\n')
        shred.chmod(0o700)
        return environment(PATH=f'{bindir}{os.pathsep}{os.environ.get("PATH", "")}')

    def test_a_failed_shred_is_never_followed_by_an_unlink(self):
        f = self.make('sf/f', b'must stay recoverable')
        self.assertRecorded(self.record(f), f)
        result = self.reap(env=self.fake_shred('exit 3'))
        self.assertEqual(result.returncode, 1)
        self.assertIn('SHRED-FAILED (shred exited 3', result.stdout)
        self.assertKeptIntact(f, hashlib.sha256(b'must stay recoverable').hexdigest())
        self.assertEqual(self.decisions(f), ['SHREDDING', 'SHRED-FAILED'])

    def test_a_shred_that_claims_success_without_overwriting_is_not_believed(self):
        f = self.make('su/f', b'still here')
        self.assertRecorded(self.record(f), f)
        result = self.reap(env=self.fake_shred('exit 0'))
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
            fh.write(b'{"v": 1, "kind": "rec')
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
        result = self.record(*files, env=environment(SCRATCH_LEDGER_BULK_DECLARATION='yes'))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.ledger_records(), [])
        self.assertEqual(self.record(*files[:16]).returncode, 0)
        self.assertEqual(self.record(*files, retain=True).returncode, 0, 'a retain record only prevents')
        reason = 'synthetic fixture set generated by this test, all mine'
        result = self.record(*files, env=environment(SCRATCH_LEDGER_BULK_DECLARATION=reason))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'BULK CALL DECLARED (17 paths in one call (the bound is 16)) — '
                      f'SCRATCH_LEDGER_BULK_DECLARATION: {reason}', result.stderr)

    def test_the_recorder_refuses_to_be_driven_by_xargs(self):
        f = self.make('xa/f')
        result = run(['xargs', '-0', 'bash', RECORD, 'record', '--agent', 't', '--', self.ledger],
                     input_text=f'{f}\0')
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
    def session_reap(self, *paths, env=None):
        return run(['bash', SESSION_REAP, *paths], env=env)

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
        self.assertEqual(len(lines), 16, result.stdout)
        self.assertTrue(all('skipped (absent)' in line or 'REFUSED (outside /tmp/claude-1000/)' in line
                            for line in lines), result.stdout)

    def test_a_token_or_short_declaration_is_refused(self):
        absent = [self.tree / 'absent' / f'{i:02d}' for i in range(17)]
        for token, message in (('true', 'must be a REASON'), ('too short', 'a declaration is prose')):
            result = self.session_reap(*absent, env=environment(REAP_SESSION_BULK_DECLARATION=token))
            self.assertEqual(result.returncode, 1)
            self.assertIn(message, result.stderr)
            self.assertEqual(result.stdout, '')

    def test_a_declared_bulk_call_proceeds_and_echoes_its_reason(self):
        absent = [self.tree / 'absent' / f'{i:02d}' for i in range(17)]
        reason = 'test of the declared path; every operand is an absent path'
        result = self.session_reap(*absent, env=environment(REAP_SESSION_BULK_DECLARATION=reason))
        self.assertIn(f'REAP_SESSION_BULK_DECLARATION: {reason}', result.stderr)
        self.assertEqual(len(result.stdout.splitlines()), 17, result.stdout)

    def test_a_single_path_fed_by_xargs_is_refused(self):
        result = run(['xargs', '-0', 'bash', SESSION_REAP], input_text=f'{self.tree / "absent"}\0')
        self.assertIn('driven by xargs', result.stderr)
        self.assertEqual(result.stdout, '')

    def test_a_single_path_fed_by_find_exec_is_refused(self):
        result = run(['find', self.tree, '-maxdepth', '0', '-exec', 'bash', SESSION_REAP, self.tree / 'absent', ';'])
        self.assertIn('driven by find', result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
