"""Offline controls for the new code/static publication boundary."""
from copy import deepcopy
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import tarfile
import unittest
from unittest.mock import patch

from ops import activate_core_workflow_repair as op


class CoreWorkflowInstallationTests(unittest.TestCase):
    def plan(self, directory):
        return {'format': op.FORMAT, 'base': op.BASE, 'candidate': 'b' * 40,
                'source_sha256': {'rebuild/static/app.js': 'c' * 64},
                'source_worktree': str(op.SOURCE), 'evidence_directory': str(directory / 'new'),
                'environment_before_sha256': 'd' * 64, 'environment': {}, 'static': ['app.js']}

    def test_default_command_is_inert_without_reading_a_plan(self):
        output = io.StringIO()
        with patch('sys.argv', ['operator']), redirect_stdout(output), \
                patch.object(op.prior, 'private_json') as read, patch.object(op, 'execute') as execute:
            op.main()
        self.assertEqual(json.loads(output.getvalue()),
                         {'inert': True, 'database_queries': 0, 'provider_calls': 0, 'service_actions': 0})
        read.assert_not_called(); execute.assert_not_called()

    def test_plan_refuses_unrelated_paths_configuration_and_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); root.chmod(0o700)
            original = self.plan(root); op.validate_plan(original)
            variants = []
            for name in ('rebuild/core/models.py', 'rebuild/core/migrations/9999.py',
                         'rebuild/.env', '../app.js', 'docs/unrelated.md'):
                value = deepcopy(original); value['source_sha256'][name] = 'c' * 64; variants.append(value)
            for key, value in [('environment', {'QUILLMD_AI_MODE': 'live'}),
                               ('static', []), ('static', ['app.js', 'coding.js']), ('base', '0' * 40)]:
                changed = deepcopy(original); changed[key] = value; variants.append(changed)
            for variant in variants:
                with self.subTest(variant=variant), self.assertRaises(op.Refusal): op.validate_plan(variant)
            (root / 'new').mkdir()
            with self.assertRaises(op.Refusal): op.validate_plan(original)

    def test_release_stamp_changes_only_its_original_line(self):
        before = ('# retained settings\r\nQUILLMD_AI_MODE=live\r\n'
                  f'QUILLMD_RELEASE_SHA="{op.BASE}"\r\nKEEP_LITERAL="a # b"\r\n').encode()
        result = op.render_environment(before, 'b' * 40, {})
        self.assertEqual(result, before.replace(op.BASE.encode(), b'b' * 40))
        with self.assertRaises(op.Refusal): op.render_environment(before, 'b' * 40, {'QUILLMD_AI_MODE': 'fixture'})
        with self.assertRaises(op.Refusal):
            op.render_environment(before + f'QUILLMD_RELEASE_SHA={op.BASE}\n'.encode(), 'b' * 40, {})

    def test_full_database_comparison_allows_only_existing_health_row_ticks(self):
        before = {'tables': {'core_servicehealth': [2, 'old'], 'core_encounter': [7, 'original']},
                  'sequences': {'audit': [18, True]}, 'pending': {'jobs': 0}, 'schema': ['unchanged']}
        tick = deepcopy(before); tick['tables']['core_servicehealth'][1] = 'new'
        op.unchanged(before, tick, health_may_tick=True)
        with self.assertRaises(op.Refusal): op.unchanged(before, tick)
        variants = []
        for key, value in [('core_servicehealth', [3, 'new']), ('core_encounter', [7, 'changed'])]:
            changed = deepcopy(tick); changed['tables'][key] = value; variants.append(changed)
        for key, value in [('sequences', {'audit': [19, True]}), ('schema', ['changed']), ('pending', {'jobs': 1})]:
            changed = deepcopy(tick); changed[key] = value; variants.append(changed)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(op.Refusal):
                op.unchanged(before, variant, health_may_tick=True)

    def test_static_staging_preserves_other_routes_and_old_hashed_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); app = root / 'app'; source = root / 'source'; out = root / 'out'
            static = app / 'staticfiles'; static.mkdir(parents=True); out.mkdir()
            static.chmod(0o755)
            (source / 'rebuild/static').mkdir(parents=True)
            old = b'old application'; new = b'new application'
            for name, raw in [('app.js', old), ('app.old.js', old), ('unrelated.css', b'unchanged')]:
                (static / name).write_bytes(raw); (static / name).chmod(0o644)
            manifest = {'paths': {'app.js': 'app.old.js', 'unrelated.css': 'unrelated.css'},
                        'version': '1.1', 'hash': 'old'}
            (static / 'staticfiles.json').write_text(json.dumps(manifest))
            (static / 'staticfiles.json').chmod(0o644)
            (source / 'rebuild/static/app.js').write_bytes(new)
            plan = {'source_sha256': {'rebuild/static/app.js': hashlib.sha256(new).hexdigest()}}
            primitives = op.prior.legacy.static_primitives()
            with op.bound_primitives(), patch.object(op.prior, 'APP', app), patch.object(op.prior, 'SOURCE', source):
                primitives.static_delta = op.prior.static_delta
                stage, before, staged = op.prior.stage_static(plan, out, primitives)
                after = primitives.install_static(static, stage, before, staged)
                self.assertEqual((static / 'app.js').read_bytes(), new)
                self.assertEqual((static / 'app.old.js').read_bytes(), old)
                self.assertEqual((static / 'unrelated.css').read_bytes(), b'unchanged')
                self.assertEqual(json.loads((static / 'staticfiles.json').read_text())['paths']['unrelated.css'],
                                 'unrelated.css')
                self.assertEqual(after['app.old.js'], before['app.old.js'])
                self.assertTrue((out / 'static-before.tar').is_file())
                proof = op.verify_static_rollback(out / 'static-before.tar', before)
                self.assertTrue(proof['all_file_bytes_match'])
                self.assertEqual(proof['extracted_files'], 0)
                changed = deepcopy(before); changed['app.js']['sha256'] = '0' * 64
                with self.assertRaises(op.Refusal):
                    op.verify_static_rollback(out / 'static-before.tar', changed)
                # Exercise the reverse publication on an isolated public asset
                # tree. New immutable hashes remain available after rollback.
                reverse = out / 'rollback-stage'; primitives.create_static_stage(reverse)
                with tarfile.open(out / 'static-before.tar', 'r:') as archive:
                    for member in archive:
                        with archive.extractfile(member) as stream:
                            (reverse / member.name).write_bytes(stream.read())
                        (reverse / member.name).chmod(0o644)
                restored = primitives.install_static(static, reverse, after, primitives.static_inventory(reverse))
                for name, row in before.items():
                    self.assertEqual({key: value for key, value in restored[name].items() if key != 'inode'},
                                     {key: value for key, value in row.items() if key != 'inode'})
                self.assertEqual((static / 'app.js').read_bytes(), old)
                self.assertEqual(json.loads((static / 'staticfiles.json').read_text()), manifest)
                self.assertTrue(set(after) <= set(restored))


if __name__ == '__main__':
    unittest.main()
