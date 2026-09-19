"""Guards of the fresh-storage migration: reviewed units, helper scripts, root steps and stage ordering."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

try:
    from . import source_module
except ImportError:
    import source_module

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/migrate-fresh-storage.py'


def load_migration():
    return source_module.load('migrate_fresh_storage', SCRIPT)


def function_source(name):
    source = SCRIPT.read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(source, node)


class UnitPolicy(unittest.TestCase):
    def test_application_units_require_the_database_unit_and_encrypted_tmp(self):
        for surface in ('doctor', 'admin', 'worker'):
            text = (ROOT / f'rebuild/deploy/quillmd-fresh-{surface}.service').read_text()
            self.assertIn('\nRequires=quillmd-fresh-database.service\n', text)
            self.assertIn('After=docker.service network-online.target quillmd-fresh-database.service\n', text)
            self.assertIn('Environment=TMPDIR=/var/lib/quillmd/tmp', text)
            self.assertIn('ReadWritePaths=/var/lib/quillmd/files /var/lib/quillmd/mail /var/lib/quillmd/proofs /var/lib/quillmd/tmp\n', text)
            self.assertIn('InaccessiblePaths=/run/docker.sock', text)
            self.assertIn('User=quillmd-app\n', text)
            self.assertIn('PrivateTmp=true', text)
            self.assertIn('LimitCORE=0\n', text)
            self.assertIn('MemorySwapMax=0\n', text)
            # EnvironmentFile overrides Environment, so the private .env must not set TMPDIR; the launcher enforces it.
            self.assertLess(text.index('Environment=TMPDIR='), text.index('EnvironmentFile='))

    def test_volume_unit_never_delays_docker_and_database_binds_to_it(self):
        volume = (ROOT / 'rebuild/deploy/quillmd-fresh-volume.service').read_text()
        database = (ROOT / 'rebuild/deploy/quillmd-fresh-database.service').read_text()
        self.assertNotIn('Before=docker.service', volume)
        self.assertIn('RequiresMountsFor=/var/lib/quillmd-encrypted', volume)
        self.assertIn('TimeoutStartSec=120\n', volume)
        self.assertIn('ExecStart=/usr/local/bin/quillmd-fresh-volume open\n', volume)
        self.assertIn('ExecStop=/usr/local/bin/quillmd-fresh-volume close\n', volume)
        self.assertIn('BindsTo=quillmd-fresh-volume.service\n', database)
        self.assertIn('Requires=docker.service\n', database)
        self.assertIn('After=docker.service quillmd-fresh-volume.service\n', database)
        self.assertIn('ExecStartPre=/usr/local/bin/quillmd-fresh-volume status\n', database)
        self.assertIn('ExecStart=/usr/bin/docker start quillmd-fresh-postgres\n', database)
        self.assertIn('ExecStartPost=/usr/local/bin/quillmd-fresh-volume wait-database\n', database)
        # ExecStopPost, not ExecStop: it also runs after a failed start, so a never-ready container is not left running.
        self.assertIn('ExecStopPost=/usr/bin/docker stop -t 90 quillmd-fresh-postgres\n', database)
        self.assertNotIn('\nExecStop=', database)
        stop = int(re.search(r'TimeoutStopSec=(\d+)', database).group(1))
        self.assertGreater(stop, 90)
        for text in (volume, database):
            self.assertIn('WantedBy=multi-user.target', text)
            self.assertNotIn('%', text)
            self.assertNotIn('$', text)

    def test_helper_script_verifies_marker_and_key_before_binding(self):
        path = ROOT / 'rebuild/deploy/quillmd-fresh-volume.sh'
        text = path.read_text()
        self.assertTrue(text.startswith('#!/usr/bin/env bash'))
        self.assertIn('set -euo pipefail', text)
        self.assertIn('IMAGE=/var/lib/quillmd-encrypted/quillmd-fresh.luks\n', text)
        self.assertLess(text.index('[ -f "$MARKER" ] || fail_closed'), text.index('mount --bind'))
        self.assertIn('fail_closed "volume marker missing', text)
        # Every step after the mapper opens cleans up on failure: no decrypted mount or open mapper is left behind.
        self.assertEqual(text.count('mount --bind'), text.count('|| fail_closed "could not bind'))
        self.assertIn('"$MOUNT" || fail_closed "could not mount', text)
        self.assertIn('[ -f "$KEY" ] || refuse "key file absent', text)
        # Unlock pins no key slot: after a rotation the recovery passphrase lives in whichever slot luksAddKey chose.
        self.assertIn('      cryptsetup open "$IMAGE" "$NAME"\n', text)
        self.assertNotIn('--key-slot', text)
        self.assertIn('mount -o nodev,nosuid', text)
        for word in ('open)', 'unlock)', 'close)', 'status)', 'wait-database)'):
            self.assertIn(word, text)
        result = subprocess.run(['bash', '-n', str(path)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unlock_script_reads_the_passphrase_from_a_terminal_only(self):
        path = ROOT / 'scripts/ops/unlock-fresh-volume.sh'
        text = path.read_text()
        self.assertIn('[ -t 0 ]', text)
        self.assertIn('read -rs', text)
        self.assertIn("'type=bind,src=/,dst=/host,readonly'".strip("'"), text)
        self.assertIn('"unlock",stdin=line', text)
        self.assertNotIn('--key-file', text)
        mode = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-s', 'scripts/ops/unlock-fresh-volume.sh'], text=True)
        if mode:
            self.assertTrue(mode.startswith('100755'), mode)
        result = subprocess.run(['bash', '-n', str(path)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class MigrationInvariants(unittest.TestCase):
    def setUp(self):
        self.migration = load_migration()
        self.source = SCRIPT.read_text()

    def test_allowed_set_names_every_tracked_change_and_the_declaration(self):
        for path in ('rebuild/deploy/quillmd-fresh-volume.service', 'rebuild/deploy/quillmd-fresh-database.service', 'rebuild/deploy/quillmd-fresh-volume.sh',
                     'scripts/migrate-fresh-storage.py', 'scripts/ops/unlock-fresh-volume.sh', 'scripts/verify-post-reboot.sh',
                     'rebuild/ops/test_storage_migration.py', 'docs/rebuild/storage-encryption.md', self.migration.DECL):
            self.assertIn(path, self.migration.ALLOWED)
            self.assertTrue((ROOT / path).is_file(), path)
        commits = (self.migration.BASELINE, self.migration.MIGRATED)
        probe = [subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', c + '^{commit}'], capture_output=True).returncode for c in commits]
        if any(probe):
            # A shallow CI checkout lacks both commits; the migration preflight enforces the same set at run time.
            self.skipTest('release commits not fetched; the preflight enforces ALLOWED against the target')
        # The act is complete, so the set constrains the target it migrated (and any later rollback target), not every later main.
        changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', *commits], text=True).split())
        self.assertEqual(sorted(changed - self.migration.ALLOWED), [])
        self.assertLessEqual(self.migration.REAP_PATHS, self.migration.ALLOWED)

    def test_the_completed_migration_can_roll_back_to_a_later_reviewed_target(self):
        m = self.migration
        migrate_result = {'mode': 'migrate', 'target': m.MIGRATED, 'stage': 'complete', 'complete': True}
        later = 'a' * 40
        self.assertTrue(m.rollback_source_ok(migrate_result, m.MIGRATED, lambda a, b: True))
        self.assertTrue(m.rollback_source_ok(migrate_result, later, lambda a, b: (a, b) == (m.MIGRATED, later)))
        self.assertFalse(m.rollback_source_ok(migrate_result, later, lambda a, b: False))
        # An interrupted migrate rolls back only to its own target.
        interrupted = {'mode': 'migrate', 'target': 'b' * 40, 'stage': 'unavailability_drill', 'complete': False}
        self.assertTrue(m.rollback_source_ok(interrupted, 'b' * 40, lambda a, b: True))
        self.assertFalse(m.rollback_source_ok(interrupted, later, lambda a, b: True))
        # Another act's result (the reap's, with stage 'complete') is not a migrate result.
        self.assertFalse(m.rollback_source_ok({'target': later, 'stage': 'complete', 'complete': True}, later, lambda a, b: True))
        self.assertFalse(m.rollback_source_ok(dict(migrate_result, stage='formatting_encrypted_volume'), m.MIGRATED, lambda a, b: True))

    def test_rollback_does_not_need_the_removed_plaintext_snapshot(self):
        main = function_source('main')
        rollback_branch = main.split("        require(args.from_result, 'Rollback needs --from-result naming the migrate result.')")[1].split('    installed = ')[0]
        self.assertIn("probe['image']", rollback_branch)
        self.assertNotIn("probe['rollback']", rollback_branch)
        rollback = function_source('execute_rollback')
        self.assertNotIn('ROLLBACK', rollback)
        self.assertIn('ROOT_COPY_BACK', rollback)
        self.assertIn("M+'/postgres'", self.migration.ROOT_COPY_BACK)

    def test_root_steps_compile(self):
        for name in ('ROOT_PROBE', 'ROOT_PREPARE', 'ROOT_COPY', 'ROOT_ARCHIVE_LOG', 'ROOT_SWITCH', 'ROOT_INSTALL', 'ROOT_STATE',
                     'ROOT_WRITE_PROBE', 'ROOT_REVERT', 'ROOT_DISCARD', 'ROOT_COPY_BACK', 'ROOT_SWITCH_BACK'):
            compile(self.migration.ROOT_LIBRARY + getattr(self.migration, name), name, 'exec')

    def test_root_steps_never_delete_data_and_move_originals_to_rollback(self):
        for forbidden in ('shutil.rmtree', 'rm -rf', "'-rf'", 'docker rm', "'volume', 'rm'", 'wipefs', 'luksErase', 'luksRemoveKey', 'luksKillSlot'):
            self.assertNotIn(forbidden, self.source)
        switch = self.migration.ROOT_SWITCH
        self.assertIn("os.rename(P['pg_data'],P['rollback']+'/pg_data')", switch)
        self.assertIn("os.rename(P['state'],P['rollback']+'/state')", switch)
        self.assertIn("host('/usr/bin/chattr','+i',P['pg_data'])", switch)
        self.assertIn("host('/usr/bin/chattr','+i',P['state'])", switch)
        self.assertIn("raise RuntimeError('rollback directory already exists')", switch)
        self.assertIn("'--checksum'", self.migration.ROOT_LIBRARY)
        # Copy and its verification precede the switch in the act.
        migrate = function_source('execute_migrate')
        self.assertLess(migrate.index('ROOT_COPY,'), migrate.index('ROOT_SWITCH,'))
        self.assertIn("'--restart=no'", migrate)
        self.assertIn("'--restart=unless-stopped'", function_source('automatic_revert'))
        self.assertIn("'--restart=unless-stopped'", function_source('execute_rollback'))
        # Revert only restores directories that were moved aside and refuses a non-empty target.
        self.assertIn("raise RuntimeError('target not empty during revert: '+target)", self.migration.ROOT_REVERT)
        self.assertIn("raise RuntimeError('rollback material exists", self.migration.ROOT_DISCARD)

    def test_host_commands_are_the_reviewed_set(self):
        allowed = ('/usr/sbin/cryptsetup', '/usr/sbin/mkfs.ext4', '/bin/mount', '/bin/umount', '/usr/bin/rsync', '/usr/bin/chattr', '/usr/bin/lsattr',
                   '/usr/bin/id', '/usr/bin/touch', '/usr/bin/rm', '/usr/bin/shred', '/usr/bin/truncate', '/usr/bin/systemd-analyze')
        found = re.findall(r"host\('(/[^']+)'", self.source)
        self.assertTrue(found)
        for command in found:
            self.assertIn(command, allowed)
        self.assertIn("host('/usr/bin/rm','-f',p+'/.plaintext-probe'", self.source)
        self.assertEqual(len(re.findall(r"host\('/usr/bin/rm'", self.source)), 1)
        self.assertIn("'type=bind,src=/,dst=/host,readonly,bind-propagation=rslave'", self.source)
        self.assertIn("f'type=bind,src={path},dst=/host{path},bind-propagation=rslave'", self.source)
        self.assertEqual(self.source.count('type=bind,'), 2)
        self.assertNotIn("'type=bind,src=/,dst=/host'", self.source)
        self.assertIn("host('/usr/bin/systemd-analyze','verify'", self.migration.ROOT_INSTALL)
        self.assertNotIn("subprocess.run(['systemd-analyze'", self.migration.ROOT_INSTALL)
        self.assertIn("'systemd-run','--wait','--pipe','--collect','--quiet','--property=Type=oneshot'", self.migration.ROOT_LIBRARY)

    def test_luks_parameters_keys_and_paths_are_fixed(self):
        m = self.migration
        self.assertEqual(m.IMAGE_BYTES, 16 * 2 ** 30)
        self.assertEqual(m.IMAGE, '/var/lib/quillmd-encrypted/quillmd-fresh.luks')
        self.assertEqual(m.KEY, '/etc/quillmd/quillmd-fresh-luks.key')
        self.assertEqual(m.RECOVERY, '/etc/quillmd/quillmd-fresh-luks.recovery-passphrase')
        self.assertEqual(m.MOUNT, '/mnt/quillmd-fresh-encrypted')
        self.assertEqual(m.LUKS_FORMAT, ['--type', 'luks2', '--cipher', 'aes-xts-plain64', '--key-size', '512', '--hash', 'sha256',
                                         '--pbkdf', 'argon2id', '--pbkdf-memory', '262144', '--iter-time', '2000'])
        prepare = m.ROOT_PREPARE
        self.assertIn("os.mkdir(P['image_dir'],0o700)", prepare)
        self.assertIn('os.urandom(64)', prepare)
        # The recovery passphrase is stored without a newline and tested as typed (newline-terminated), wrong and slot 0.
        self.assertIn('f.write(phrase)', prepare)
        self.assertIn("stdin=phrase+'\\n'", prepare)
        self.assertIn("stdin=phrase+'x\\n'", prepare)
        self.assertIn("if typed!=0 or wrong==0 or slot0!=0", prepare)
        migrate = function_source('execute_migrate')
        # 'cipher:' (lower case) is the data segment and 'Key:' the volume key; 'Cipher:' names only the key-slot area.
        for expected in ("['cipher: aes-xts-plain64']", "['Key: 512 bits']", "['Cipher: aes-xts-plain64']", "['Cipher key: 512 bits']",
                         "['PBKDF: argon2id']", "['Version: 2']"):
            self.assertIn(expected, migrate)

    def test_main_advances_only_after_verification_and_revert_only_from_the_baseline(self):
        migrate = function_source('execute_migrate')
        order = [migrate.index(f"stage(result, '{s}')") for s in (
            'formatting_encrypted_volume', 'copying_and_verifying_data', 'switching_to_immutable_bind_targets', 'installing_units_and_helper',
            'opening_volume_and_database', 'suppressing_statement_logging', 'verifying_data_on_encrypted_volume', 'advancing_reviewed_main',
            'starting_private_services_on_encrypted_volume', 'archiving_database_container_log', 'unavailability_drill', 'recovery_after_drill',
            'final_checks', 'complete')]
        self.assertEqual(order, sorted(order))
        self.assertLess(migrate.index("run(['git', 'merge', '--ff-only', args.target])"), migrate.index("stage(result, 'starting_private_services_on_encrypted_volume')"))
        self.assertIn("if output(['git', 'rev-parse', 'HEAD']) == BASELINE:\n            automatic_revert(", migrate)
        # Only the protected population is read before anything changes; the data baseline is taken once the services are down.
        self.assertLess(migrate.index("stage(result, 'capturing_protected_population')"), migrate.index('units_installed = False'))
        self.assertLess(migrate.index("stage(result, 'stopping_private_services')"), migrate.index("stage(result, 'capturing_baseline')"))
        self.assertLess(migrate.index("stage(result, 'capturing_baseline')"), migrate.index("stage(result, 'stopping_database_container')"))
        self.assertIn("if 'database_before' in result:", function_source('automatic_revert'))

    def test_every_stage_after_main_advances_is_eligible_for_rollback(self):
        stages = re.findall(r"stage\(result, '([a-z_]+)'\)", function_source('execute_migrate'))
        cut = stages.index('advancing_reviewed_main')
        self.assertEqual(sorted(set(stages[cut:]) | {'complete'}), sorted(self.migration.POST_START_STAGES))
        self.assertFalse(set(stages[:cut]) & set(self.migration.POST_START_STAGES))

    def test_terminate_signal_runs_the_failure_handlers(self):
        self.assertIn('signal.signal(signal.SIGTERM, _terminate)', function_source('main'))
        self.assertTrue(issubclass(self.migration.Terminated, BaseException))
        self.assertFalse(issubclass(self.migration.Terminated, Exception))
        for name in ('execute_migrate', 'execute_rollback'):
            self.assertIn('except BaseException as error:', function_source(name))

    def test_plaintext_units_remove_only_the_encrypted_database_dependency(self):
        units = {u: (ROOT / 'rebuild/deploy' / u).read_bytes() for u in self.migration.APP_UNITS}
        plain = self.migration.plaintext_units(units)
        for name, text in plain.items():
            decoded = text.decode()
            self.assertNotIn('quillmd-fresh-database', decoded)
            self.assertIn('After=docker.service network-online.target\n', decoded)
            removed = [line for line in units[name].decode().splitlines() if line not in decoded.splitlines()]
            self.assertEqual(removed, ['After=docker.service network-online.target quillmd-fresh-database.service', 'Requires=quillmd-fresh-database.service'])

    def test_log_archive_happens_after_main_advances_and_statement_logging_is_suppressed(self):
        migrate = function_source('execute_migrate')
        self.assertGreater(migrate.index('ROOT_ARCHIVE_LOG,'), migrate.index("run(['git', 'merge', '--ff-only', args.target])"))
        self.assertIn("ALTER SYSTEM SET log_min_messages = 'fatal'", migrate)
        self.assertIn("ALTER SYSTEM SET log_min_error_statement = 'panic'", migrate)
        self.assertIn("'--memory-swap', str(ORIGINAL_MEMORY[0])", migrate)

    def test_declaration_and_drill_are_part_of_the_act(self):
        migrate = function_source('execute_migrate')
        self.assertIn("stage(result, 'unavailability_drill')", migrate)
        self.assertIn('ROOT_WRITE_PROBE', migrate)
        self.assertIn("'manual_container_start_while_closed'", migrate)
        self.assertIn('declaration.name == Path(DECL).name', function_source('main'))
        text = (ROOT / self.migration.DECL).read_text()
        for phrase in ('quillmd-fresh.luks', 'unless-stopped to no', 'immutable', 'rollback', 'swap', 'key custody', 'recovery passphrase',
                       'billing boundary', 'decrypted_files_written'):
            self.assertIn(phrase, text.lower() if phrase.islower() else text)


class FailurePathsSurviveTheWatchdog(unittest.TestCase):
    """The ruled-mutation watchdog sends SIGTERM and then SIGKILL 15 s later, so the act must fail on its own well before the
    ceiling, record its progress as it goes, and leave a mode that finishes an interrupted revert."""

    def setUp(self):
        self.migration = load_migration()
        self.source = SCRIPT.read_text()

    def test_every_external_command_is_bounded(self):
        m = self.migration
        self.assertLessEqual(m.COMMAND_TIMEOUT, 600)
        self.assertIn("kwargs.setdefault('timeout', COMMAND_TIMEOUT)", function_source('output'))
        self.assertIn("kwargs.setdefault('timeout', COMMAND_TIMEOUT)", function_source('run'))
        self.assertIn('timeout=900', function_source('root').splitlines()[0])
        self.assertIn('timeout=600', m.ROOT_LIBRARY.split('def host(')[1].splitlines()[0])
        self.assertIn('timeout=15', function_source('wait_database'))
        self.assertNotIn("'docker', 'stop', '-t', '90', CONTAINER], stdout=subprocess.DEVNULL)", self.source)

    def test_phase_one_stops_on_its_own_budget_and_the_revert_is_exempt(self):
        m = self.migration
        stages = re.findall(r"stage\(result, '([a-z_]+)'\)", function_source('execute_migrate'))
        cut = stages.index('advancing_reviewed_main')
        self.assertEqual(set(stages[1:cut + 1]), set(m.PHASE_ONE_STAGES))
        self.assertNotIn('automatic_revert_to_plaintext', m.PHASE_ONE_STAGES)
        result = {}
        # Relative to now: the monotonic clock counts from boot, so a fresh CI runner may be younger than the budget.
        import time
        m.ACT['started'] = time.monotonic() - m.PHASE_ONE_BUDGET - 5
        try:
            with self.assertRaises(RuntimeError):
                m.stage(result, 'formatting_encrypted_volume')
            m.stage(result, 'automatic_revert_to_plaintext')
            self.assertEqual(result['stage'], 'automatic_revert_to_plaintext')
        finally:
            m.ACT['started'] = None

    def test_progress_is_written_at_every_stage(self):
        import tempfile
        m = self.migration
        with tempfile.TemporaryDirectory() as directory:
            m.ACT['progress'] = Path(directory) / 'fresh-storage-migrate-test-progress.json'
            try:
                m.stage({'mode': 'migrate'}, 'stopping_private_services')
                written = json.loads(m.ACT['progress'].read_text())
                self.assertEqual(written['stage'], 'stopping_private_services')
                self.assertEqual(oct(m.ACT['progress'].stat().st_mode & 0o777), '0o600')
            finally:
                m.ACT['progress'] = None

    def test_an_in_flight_root_step_is_settled_before_any_revert_or_rollback(self):
        self.assertIn("'--name', name", function_source('root'))
        revert = function_source('automatic_revert')
        self.assertLess(revert.index('settle_root_step(result)'), revert.index('systemctl('))
        migrate = function_source('execute_migrate')
        end = migrate.index("result['failure_services_stopped'] = True")
        failure = migrate[migrate.rindex('except BaseException as error:', 0, end):end]
        self.assertLess(failure.index('settle_root_step(result)'), failure.index("systemctl('stop', APP_UNITS, image)"))
        rollback = function_source('execute_rollback')
        failure = rollback[rollback.index('except BaseException as error:'):]
        self.assertLess(failure.index('settle_root_step(result)'), failure.index("systemctl('stop'"))

    def test_an_interrupted_migrate_has_a_revert_mode(self):
        main = function_source('main')
        self.assertIn("'revert-interrupted'", main)
        self.assertIn("locks['migrate'].exists()", main)
        self.assertIn("source.get('stage') not in POST_START_STAGES", main)
        self.assertIn("elif args.mode in ('discard-failed-attempt', 'revert-interrupted'):", main)
        self.assertIn("locks['migrate'].unlink()", main)

    def test_interrupted_revert_refuses_a_live_migrate_and_fails_loudly(self):
        main = function_source('main')
        self.assertIn("require(not migrate_alive(owner.get('pid'))", main)
        self.assertIn('require(not running_root_steps()', main)
        self.assertIn("source.get('stage') == 'advancing_reviewed_main'", main)
        self.assertIn("require(result.get('complete'), 'The interrupted revert did not complete", main)
        m = self.migration
        self.assertTrue(m.migrate_alive(os.getpid()) is False or b'migrate-fresh-storage.py' in Path(f'/proc/{os.getpid()}/cmdline').read_bytes())
        self.assertFalse(m.migrate_alive(None)); self.assertFalse(m.migrate_alive(0)); self.assertFalse(m.migrate_alive(2 ** 22 + 7))
        import time
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)', 'migrate-fresh-storage.py'])
        try:
            # Between fork and exec /proc/<pid>/cmdline still shows the parent; wait for the exec to land.
            deadline = time.monotonic() + 10
            while not m.migrate_alive(child.pid) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(m.migrate_alive(child.pid))
        finally:
            child.kill(); child.wait()
        self.assertFalse(m.migrate_alive(child.pid))

    def test_a_slow_readiness_probe_is_retried(self):
        source = function_source('wait_database')
        self.assertIn('except subprocess.TimeoutExpired:', source)
        self.assertLess(source.index('for _ in range(120):'), source.index('except subprocess.TimeoutExpired:'))

    def test_retained_reports_allow_additions_but_not_changes(self):
        import tempfile
        m = self.migration
        with tempfile.TemporaryDirectory() as directory:
            original = m.ROOT
            m.ROOT = Path(directory)
            try:
                (m.ROOT / 'a.md').write_bytes(b'kept')
                os.chmod(m.ROOT / 'a.md', 0o644)
                before = {'a.md': {'sha256': m.sha(b'kept'), 'size': 4, 'mode': 0o644}}
                (m.ROOT / 'b.md').write_bytes(b'added by another session')
                self.assertTrue(m.retained_unchanged(before))
                (m.ROOT / 'a.md').write_bytes(b'KEPT')
                self.assertFalse(m.retained_unchanged(before))
                (m.ROOT / 'a.md').unlink()
                self.assertFalse(m.retained_unchanged(before))
            finally:
                m.ROOT = original
        self.assertNotIn('word.retained_reports() == retained', self.source)


class RootStepsImportBeforeChroot(unittest.TestCase):
    """After os.chroot('/host') the helper image's standard library is gone; a root step may use only modules imported before it."""

    def test_no_root_step_imports_after_the_chroot(self):
        migration = load_migration()
        preamble = migration.ROOT_LIBRARY.split("os.chroot('/host')")[0]
        imported = set(re.search(r'^import ([\w,]+)$', preamble, re.M).group(1).split(','))
        for name in [n for n in dir(migration) if n.startswith('ROOT_') and n != 'ROOT_LIBRARY']:
            code = getattr(migration, name)
            tree = ast.parse(code)
            self.assertFalse([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))], name)
            used = {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
            modules = used & {'os', 'sys', 'json', 'subprocess', 'stat', 'hashlib', 'time', 'secrets', 'shutil', 're', 'base64', 'random', 'tempfile', 'datetime'}
            self.assertLessEqual(modules, imported, name)
        library_after = migration.ROOT_LIBRARY.split("os.chroot('/host')")[1]
        self.assertFalse([n for n in ast.walk(ast.parse(library_after.split('\n', 1)[1])) if isinstance(n, (ast.Import, ast.ImportFrom))])


class RootHelperTransport(unittest.TestCase):
    """The helper program travels as an argument and only the parameters on stdin; CPython reads ALL of stdin as the program
    for `python -`, which made every root step fail in the first design."""

    def test_parameters_are_the_only_stdin_and_are_read_before_chroot(self):
        migration = load_migration()
        library = migration.ROOT_LIBRARY
        self.assertLess(library.index('P=json.loads(sys.stdin.readline())'), library.index("os.chroot('/host')"))
        captured = {}
        def fake_run(args, input=None, **kwargs):
            captured.update(args=args, input=input)
            return subprocess.CompletedProcess(args, 0, stdout='{"ok": true}\n', stderr='')
        original = migration.subprocess.run
        migration.subprocess.run = fake_run
        try:
            self.assertEqual(migration.root("emit({'ok':True})", {'k': True}, 'sha256:' + '0' * 64, writable=['/mnt']), {'ok': True})
        finally:
            migration.subprocess.run = original
        args = captured['args']
        self.assertEqual(args[-4:-1], ['python', '-B', '-c'])
        self.assertTrue(args[-1].startswith(library))
        self.assertEqual(captured['input'], '{"k": true}\n')
        self.assertIn('type=bind,src=/mnt,dst=/host/mnt,bind-propagation=rslave', args)

    def test_the_transport_pattern_round_trips_through_a_real_interpreter(self):
        program = 'import sys,json\nP=json.loads(sys.stdin.readline())\nprint(json.dumps({"got": P["value"]}))\n'
        result = subprocess.run([sys.executable, '-B', '-c', program], input='{"value": true}\n', capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), {'got': True})


if __name__ == '__main__':
    unittest.main()
