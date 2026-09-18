"""Static guards of the fresh-storage migration: reviewed units, helper script and script invariants."""
import importlib.util
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load_migration():
    spec = importlib.util.spec_from_file_location('migrate_fresh_storage', ROOT / 'scripts/migrate-fresh-storage.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UnitPolicy(unittest.TestCase):
    def test_application_units_require_the_database_unit_and_encrypted_tmp(self):
        for surface in ('doctor', 'admin', 'worker'):
            text = (ROOT / f'rebuild/deploy/quillmd-fresh-{surface}.service').read_text()
            self.assertIn('Requires=quillmd-fresh-database.service', text)
            self.assertIn('After=docker.service network-online.target quillmd-fresh-database.service', text)
            self.assertIn('Environment=TMPDIR=/var/lib/quillmd/tmp', text)
            self.assertIn('ReadWritePaths=/var/lib/quillmd/files /var/lib/quillmd/mail /var/lib/quillmd/proofs /var/lib/quillmd/tmp', text)
            self.assertIn('InaccessiblePaths=/run/docker.sock', text)
            self.assertIn('User=quillmd-app\n', text)
            self.assertIn('PrivateTmp=true', text)

    def test_volume_unit_orders_before_docker_and_database_binds_to_it(self):
        volume = (ROOT / 'rebuild/deploy/quillmd-fresh-volume.service').read_text()
        database = (ROOT / 'rebuild/deploy/quillmd-fresh-database.service').read_text()
        self.assertIn('Before=docker.service', volume)
        self.assertIn('ExecStart=/usr/local/bin/quillmd-fresh-volume open', volume)
        self.assertIn('ExecStop=/usr/local/bin/quillmd-fresh-volume close', volume)
        self.assertIn('BindsTo=quillmd-fresh-volume.service', database)
        self.assertIn('ExecStartPre=/usr/local/bin/quillmd-fresh-volume status', database)
        self.assertIn('ExecStart=/usr/bin/docker start quillmd-fresh-postgres', database)
        for text in (volume, database):
            self.assertNotIn('%', text)
            self.assertNotIn('$', text)

    def test_helper_script_is_strict_and_verifies_the_marker_before_binding(self):
        text = (ROOT / 'rebuild/deploy/quillmd-fresh-volume.sh').read_text()
        self.assertTrue(text.startswith('#!/usr/bin/env bash'))
        self.assertIn('set -euo pipefail', text)
        self.assertLess(text.index('MARKER'), text.index('mount --bind'))
        self.assertIn('refuse "volume marker missing', text)
        for word in ('open)', 'close)', 'status)', 'wait-database)'):
            self.assertIn(word, text)
        result = subprocess.run(['bash', '-n', str(ROOT / 'rebuild/deploy/quillmd-fresh-volume.sh')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class MigrationInvariants(unittest.TestCase):
    def setUp(self):
        self.migration = load_migration()

    def test_allowed_set_names_every_tracked_change_and_the_declaration(self):
        for path in ('rebuild/deploy/quillmd-fresh-volume.service', 'rebuild/deploy/quillmd-fresh-database.service', 'rebuild/deploy/quillmd-fresh-volume.sh',
                     'scripts/migrate-fresh-storage.py', 'rebuild/ops/test_storage_migration.py', 'docs/rebuild/storage-encryption.md', self.migration.DECL):
            self.assertIn(path, self.migration.ALLOWED)
            self.assertTrue((ROOT / path).is_file(), path)
        probe = subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', self.migration.BASELINE + '^{commit}'], capture_output=True)
        if probe.returncode == 0:
            changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', self.migration.BASELINE, 'HEAD'], text=True).split())
            self.assertEqual(sorted(changed - self.migration.ALLOWED), [])

    def test_root_steps_never_delete_data_and_move_originals_to_rollback(self):
        source = (ROOT / 'scripts/migrate-fresh-storage.py').read_text()
        for forbidden in ('shutil.rmtree', 'rm -rf', 'docker rm', 'docker volume rm', 'wipefs', 'luksErase', 'luksRemoveKey'):
            self.assertNotIn(forbidden, source)
        self.assertIn("os.rename(P['pg_data'],P['rollback']+'/pg_data')", source)
        self.assertIn("os.rename(str(P['state']),P['rollback']+'/state')", source)
        self.assertIn("sh('/usr/bin/chattr','+i',P['pg_data'])", source)
        self.assertIn('--checksum', source)
        self.assertLess(source.index("--checksum"), source.index("os.rename(P['pg_data']"))
        self.assertIn("'--restart=no'", source)
        self.assertIn("'--restart=unless-stopped'", source)

    def test_root_steps_use_host_systemd_for_mounts_and_never_a_writable_root(self):
        source = (ROOT / 'scripts/migrate-fresh-storage.py').read_text()
        self.assertIn("'type=bind,src=/,dst=/host,readonly'", source)
        self.assertNotIn("'type=bind,src=/,dst=/host'", source.replace("'type=bind,src=/,dst=/host,readonly'", ''))
        for operation in ("'luksFormat'", "'/bin/mount'", "'/usr/sbin/mkfs.ext4'", "'/bin/umount'"):
            self.assertIn(operation, source)
        for match in re.finditer(r"host\('(/[^']+)'", source):
            self.assertTrue(match.group(1).startswith(('/usr/sbin/cryptsetup', '/usr/sbin/mkfs.ext4', '/bin/mount', '/bin/umount')), match.group(1))
        self.assertIn('systemd-run', source)
        self.assertEqual(self.migration.IMAGE_BYTES, 16 * 2 ** 30)
        self.assertEqual(self.migration.KEY, '/etc/quillmd/quillmd-fresh-luks.key')
        self.assertEqual(self.migration.MOUNT, '/mnt/quillmd-fresh-encrypted')

    def test_declaration_and_drill_are_part_of_the_act(self):
        source = (ROOT / 'scripts/migrate-fresh-storage.py').read_text()
        self.assertIn("'unavailability_drill'", source)
        self.assertIn('ROOT_WRITE_PROBE', source)
        self.assertIn("declaration.name == Path(DECL).name", source)
        self.assertIn('--rollback', source)
        text = (ROOT / self.migration.DECL).read_text()
        for phrase in ('quillmd-fresh.luks', 'restart policy changes from unless-stopped to no', 'immutable', 'Rollback', 'swap'):
            self.assertIn(phrase, text)


if __name__ == '__main__':
    unittest.main()
