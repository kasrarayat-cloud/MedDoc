"""Synthetic filesystem/SQL-command fixtures only; no Docker, DB or service acts."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

try:
    from . import source_module
except ImportError:
    import source_module
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'scripts/activate-word-beta.py'
activation = source_module.load('word_activation_tested', SOURCE)


class WordActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def artifact(self):
        runtime = self.root / 'runtime'
        runtime.mkdir(mode=0o700)
        values = {'WordHost': b'synthetic-executable', 'libcoreclr.so': b'synthetic-library',
                  'System.Private.CoreLib.dll': b'synthetic-managed-library',
                  'WordHost.runtimeconfig.json': json.dumps({'runtimeOptions': {
                      'includedFrameworks': [{'name': 'Microsoft.NETCore.App', 'version': '8.0.31'}]}}).encode()}
        for name, data in values.items():
            (runtime / name).write_bytes(data)
            (runtime / name).chmod(0o600)
        manifest = self.root / 'manifest.json'
        manifest.write_text(json.dumps({'format': 1, 'runtime': 'dotnet8-self-contained-linux-x64',
            'executable': 'WordHost', 'files': {name: activation.sha(data) for name, data in values.items()}}))
        manifest.chmod(0o600)
        pin = activation.sha(manifest.read_bytes())
        inputs = {'rebuild/documents/sdk_word/WordHost/Program.cs': 'a' * 64}
        proof = self.root / 'proof.json'
        proof.write_text(json.dumps({'format': 1, 'sdk_version': '8.0.425', 'runtime_version': '8.0.31',
            'runtime_identifier': 'linux-x64', 'runtime_executable': 'WordHost', 'restored_locked': True,
            'self_contained': True, 'ambient_scm_metadata': False,
                 'source_revision_id': '', 'repository_commit': '', 'runtime_manifest_sha256': pin, 'build_inputs': inputs,
            'sdk_executable_sha256': 'b' * 64, 'dependencies': {'Aspose.Words.FOSS': '26.3.0'}, 'license': 'MIT'}))
        proof.chmod(0o600)
        return runtime, manifest, proof, pin, inputs

    def test_exact_runtime_and_reviewed_source_proof_then_exclusive_install(self):
        runtime, manifest, proof, pin, inputs = self.artifact()
        verified = activation.verify_artifact(runtime, manifest, proof, pin, inputs)
        app = self.root / 'application'; app.mkdir()
        previous_umask = os.umask(0o077)
        try:
            with patch.object(activation, 'APP', app):
                installed, installed_manifest = activation.install_artifact('c' * 40, runtime, manifest, proof, verified)
                self.assertEqual(installed_manifest.read_bytes(), manifest.read_bytes())
                self.assertEqual((installed / 'WordHost').stat().st_mode & 0o777, 0o755)
                self.assertEqual((installed / 'libcoreclr.so').stat().st_mode & 0o777, 0o644)
                self.assertEqual(installed.parent.stat().st_mode & 0o777, 0o755)
                with self.assertRaises(FileExistsError):
                    activation.install_artifact('c' * 40, runtime, manifest, proof, verified)
                self.assertEqual((installed / 'WordHost').read_bytes(), b'synthetic-executable')
        finally:
            os.umask(previous_umask)

    def test_unmanifested_file_and_modified_build_source_refused(self):
        runtime, manifest, proof, pin, inputs = self.artifact()
        extra = runtime / 'unexpected.dll'; extra.write_bytes(b'extra')
        with self.assertRaises(RuntimeError): activation.verify_artifact(runtime, manifest, proof, pin, inputs)
        extra.unlink()
        with self.assertRaises(RuntimeError):
            activation.verify_artifact(runtime, manifest, proof, pin, {**inputs, 'unreviewed.cs': 'c' * 64})
        (runtime / 'WordHost').write_bytes(b'modified')
        with self.assertRaises(RuntimeError): activation.verify_artifact(runtime, manifest, proof, pin, inputs)

    def test_links_traversal_and_wrong_executable_refused(self):
        runtime, manifest, proof, pin, inputs = self.artifact()
        (runtime / 'outside').symlink_to('/etc/passwd')
        with self.assertRaises(RuntimeError): activation.verify_artifact(runtime, manifest, proof, pin, inputs)
        for name in ('../key', '/etc/passwd', 'a/../key', 'a//b', 'a\\b'):
            with self.subTest(name=name), self.assertRaises(RuntimeError): activation.relative(name)
        (runtime / 'outside').unlink()
        os.link(runtime / 'WordHost', runtime / 'hardlink')
        with self.assertRaises(RuntimeError): activation.verify_artifact(runtime, manifest, proof, pin, inputs)

    def test_only_exact_three_json_additions_are_approved(self):
        activation.validate_migration(activation.EXPECTED_MIGRATION)
        for altered in (activation.EXPECTED_MIGRATION.replace('default=list', 'default=dict'),
                        activation.EXPECTED_MIGRATION.replace("name='template_review'", "name='notes'"),
                        activation.EXPECTED_MIGRATION + '\nprint("unexpected code")\n'):
            with self.assertRaises(RuntimeError): activation.validate_migration(altered)

    def test_schema_rejects_old_column_loss_or_changed_type_and_checks_new_defaults(self):
        before = [{'table_name': name, 'column_name': 'id', 'ordinal_position': 1,
                   'data_type': 'uuid', 'udt_name': 'uuid', 'is_nullable': 'NO', 'column_default': None}
                  for name in sorted(activation.NEW_COLUMNS)]
        after = deepcopy(before)
        for table, columns in activation.NEW_COLUMNS.items():
            after += [{'table_name': table, 'column_name': column, 'ordinal_position': index + 2,
                       'data_type': 'jsonb', 'udt_name': 'jsonb', 'is_nullable': 'NO', 'column_default': None}
                      for index, column in enumerate(columns)]
        after.sort(key=lambda row: (row['table_name'], row['ordinal_position']))
        activation.check_schema(before, after)
        for transform in ('loss', 'type', 'nullable', 'default'):
            bad = deepcopy(after)
            if transform == 'loss': bad.pop(0)
            elif transform == 'type': bad[0]['data_type'] = 'text'
            elif transform == 'nullable': bad[1]['is_nullable'] = 'YES'
            else: bad[1]['column_default'] = "'{}'::jsonb"
            with self.subTest(transform=transform), self.assertRaises(RuntimeError): activation.check_schema(before, bad)
        with patch.object(activation, 'output', side_effect=['1', '0', '0', '1']):
            with self.assertRaises(RuntimeError): activation.check_new_defaults()

    def test_fingerprints_preserve_every_previous_column_and_schema_history(self):
        tables = sorted(['core_encounter', 'core_templateversion', 'django_migrations', 'core_job', 'core_usage']
                        + ['fixture_' + str(index) for index in range(28)])
        with patch.object(activation, 'output', return_value='\n'.join(tables)), \
                patch.object(activation.subprocess, 'check_output', return_value=b'{}\n') as capture:
            result = activation.fingerprints()
        self.assertEqual(set(result), set(tables))
        sql = '\n'.join(call.args[0][-1] for call in capture.call_args_list)
        self.assertIn("-'review_requirements'-'document_backend'", sql)
        self.assertIn("-'template_review'", sql)
        self.assertIn("WHERE NOT (app='core' AND name='0011_template_clinical_review')", sql)
        for old in ('provider_resource_id', 'request_key', 'status', 'object_data'):
            self.assertNotIn("-'" + old + "'", sql)

    def test_configuration_changes_only_release_and_three_word_keys(self):
        original = ('# synthetic fixture only\nQUILLMD_RELEASE_SHA=' + activation.BASELINE
                    + '\nQUILLMD_STATE_DIR=/var/lib/quillmd\nEXAMPLE_KEY=fixture-only-value\n').encode()
        updated = activation.updated_environment(original, 'd' * 40, Path('/runtime'), Path('/manifest'), 'e' * 64)
        preserved = [line for line in updated.decode().splitlines()
                     if not line.startswith((*[key + '=' for key in activation.ENV_KEYS], 'QUILLMD_RELEASE_SHA='))]
        self.assertEqual(preserved, [line for line in original.decode().splitlines() if not line.startswith('QUILLMD_RELEASE_SHA=')])
        with self.assertRaises(RuntimeError): activation.updated_environment(updated, 'd' * 40, Path('/runtime'), Path('/manifest'), 'e' * 64)
        with self.assertRaises(RuntimeError):
            activation.updated_environment(original + b'QUILLMD_WORD_QUALIFICATION=1\n', 'd' * 40, Path('/runtime'), Path('/manifest'), 'e' * 64)

    def test_root_helper_only_fixed_services_and_existing_local_image(self):
        with patch.object(activation.subprocess, 'run') as call:
            call.return_value.returncode = 0
            activation.systemd('stop', 'sha256:' + 'a' * 64)
            command = call.call_args.args[0]
            source = call.call_args.kwargs['input']
            self.assertIn('--pull=never', command)
            self.assertIn('--network=none', command)
            self.assertIn('type=bind,src=/,dst=/host,readonly', command)
            self.assertNotIn('--privileged', command)
            self.assertNotIn('--cap-add', command)
            self.assertIn(repr(['systemctl', 'stop', *activation.UNITS]), source)
            with self.assertRaises(RuntimeError): activation.systemd('restart-all', 'sha256:' + 'a' * 64)
            with self.assertRaises(RuntimeError): activation.systemd('stop', 'python:3-slim')
            self.assertEqual(call.call_count, 1)

    def test_only_exact_retained_preflight_reports_are_permitted_and_hashed(self):
        relative = 'docs/preflight-reports/preflight-20260917T190000Z.md'
        path = self.root / relative; path.parent.mkdir(parents=True)
        path.write_bytes(b'synthetic retained report\n')
        with patch.object(activation, 'ROOT', self.root), \
                patch.object(activation.subprocess, 'check_output', return_value=relative.encode() + b'\0'):
            before = activation.retained_reports()
            self.assertEqual(before[relative]['sha256'], activation.sha(path.read_bytes()))
            path.write_bytes(b'changed retained report\n')
            self.assertNotEqual(activation.retained_reports(), before)
            path.unlink(); path.symlink_to('/etc/passwd')
            with self.assertRaises(RuntimeError): activation.retained_reports()
        with patch.object(activation, 'ROOT', self.root), \
                patch.object(activation.subprocess, 'check_output', return_value=b'docs/preflight-reports/anything.txt\0'):
            with self.assertRaises(RuntimeError): activation.retained_reports()


if __name__ == '__main__':
    unittest.main()
