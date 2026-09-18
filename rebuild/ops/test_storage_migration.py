"""Guards of the fresh-storage migration: reviewed units, helper scripts, root steps and stage ordering."""
import ast
import importlib.util
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/migrate-fresh-storage.py'


def load_migration():
    spec = importlib.util.spec_from_file_location('migrate_fresh_storage', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        self.assertIn('ExecStop=/usr/bin/docker stop -t 90 quillmd-fresh-postgres\n', database)
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
        self.assertLess(text.index('[ ! -f "$MARKER" ]'), text.index('mount --bind'))
        self.assertIn('refuse "volume marker missing', text)
        self.assertIn('[ -f "$KEY" ] || refuse "key file absent', text)
        self.assertIn('cryptsetup open --key-slot 1 "$IMAGE" "$NAME"', text)
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
        probe = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', self.migration.BASELINE + '^{commit}'], capture_output=True)
        if probe.returncode == 0:
            changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', self.migration.BASELINE, 'HEAD'], text=True).split())
            self.assertEqual(sorted(changed - self.migration.ALLOWED), [])

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
                   '/usr/bin/id', '/usr/bin/touch', '/usr/bin/rm', '/usr/bin/shred', '/usr/bin/truncate')
        found = re.findall(r"host\('(/[^']+)'", self.source)
        self.assertTrue(found)
        for command in found:
            self.assertIn(command, allowed)
        self.assertIn("host('/usr/bin/rm','-f',p+'/.plaintext-probe'", self.source)
        self.assertEqual(len(re.findall(r"host\('/usr/bin/rm'", self.source)), 1)
        self.assertIn("'type=bind,src=/,dst=/host,readonly'", self.source)
        self.assertNotIn("'type=bind,src=/,dst=/host'", self.source)
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
        self.assertIn("['Cipher:     aes-xts-plain64']", migrate)
        self.assertIn("['Cipher key: 512 bits']", migrate)
        self.assertIn("['PBKDF:      argon2id']", migrate)

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
        # The baseline capture fails without touching services.
        self.assertLess(migrate.index("stage(result, 'capturing_baseline')"), migrate.index('units_installed = False'))

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


if __name__ == '__main__':
    unittest.main()
