"""Prove bounded CI partitions retain the legacy commands and fail closed; no suite execution."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class CIGatePartitions(unittest.TestCase):
    def invoke(self, mode, fail_at=''):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'python'
            fake.write_text('#!' + sys.executable + '\n' +
                            'import json,os,sys\n'
                            'with open(os.environ["CI_PROBE_LOG"],"a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
                            'sys.exit(23 if os.environ.get("CI_PROBE_FAIL") in sys.argv[1:] else 0)\n')
            fake.chmod(0o700)
            log = root / 'calls.jsonl'
            env = dict(os.environ, QUILLMD_CI_PYTHON=str(fake), CI_PROBE_LOG=str(log),
                       CI_PROBE_FAIL=fail_at, QUILLMD_SECRET_KEY='synthetic', QUILLMD_DB_PASSWORD='synthetic')
            result = subprocess.run(['bash', str(ROOT/'scripts/ci/verify-fresh.sh'), mode],
                                    env=env, capture_output=True, text=True, timeout=10)
            return result.returncode, [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def test_partitions_exactly_cover_legacy_python_gate(self):
        rc, legacy = self.invoke('python')
        rc_core, core = self.invoke('python-core')
        rc_support, support = self.invoke('python-support')
        self.assertEqual((rc, rc_core, rc_support), (0, 0, 0))
        self.assertEqual(core + support, legacy)
        self.assertEqual(len(core), 3)
        self.assertEqual(core, [['manage.py', 'check'], ['manage.py', 'makemigrations', '--check', '--dry-run'],
                                ['manage.py', 'test', 'core.tests', '--verbosity', '2']])
        self.assertEqual(len(support), 2)
        self.assertEqual(support[0][:2], ['-m', 'unittest'])
        self.assertEqual(support[0][2:-1], ['documents.tests', 'documents.test_tab_form',
            'documents.test_sdk_sandbox', 'documents.test_sdk_service', 'documents.test_layout',
            'documents.test_unmapped_areas', 'documents.test_multicolumn_and_mixed',
            'documents.test_word_v3', 'documents.test_signing_areas', 'documents.test_question_boxes',
            'documents.test_composite_kind', 'documents.test_hyperlink_destinations', 'documents.test_document_relations',
            'documents.test_source_policy', 'documents.test_layout_verification', 'documents.test_guidance_preservation'])
        self.assertEqual(support[0][-1], '-v')
        self.assertEqual(support[1], ['-m', 'unittest', 'discover', '-s', 'ops', '-p', 'test_*.py', '-v'])

    def test_core_shards_keep_checks_and_use_the_same_full_discovery_label(self):
        for shard in (1, 2):
            code, commands = self.invoke(f'python-core-{shard}')
            self.assertEqual(code, 0)
            self.assertEqual(commands[:2], [['manage.py', 'check'], ['manage.py', 'makemigrations', '--check', '--dry-run']])
            self.assertEqual(commands[2], ['manage.py', 'test', 'core.tests', '--verbosity', '2',
                '--testrunner', 'ops.ci_test_runner.CoreShardRunner', '--core-shard', str(shard),
                '--core-shard-manifest', f'.runtime/core-shard-{shard}.json'])
            self.assertEqual(len(commands), 3)

    def test_each_failing_stage_stops_without_success_or_later_commands(self):
        for mode, stages in [('python-core', ['check', 'makemigrations', 'core.tests']),
                             ('python-core-1', ['check', 'makemigrations', 'core.tests']),
                             ('python-core-2', ['check', 'makemigrations', 'core.tests']),
                             ('python-support', ['documents.tests', 'discover'])]:
            for index, stage in enumerate(stages):
                with self.subTest(mode=mode, stage=stage):
                    code, calls = self.invoke(mode, stage)
                    self.assertEqual(code, 23)
                    self.assertEqual(len(calls), index + 1)

    def test_unknown_mode_refuses_without_any_suite(self):
        self.assertEqual(self.invoke('unknown'), (2, []))

    def test_required_aggregate_runs_always_and_accepts_only_success(self):
        workflow = (ROOT/'.github/workflows/test.yml').read_text()
        aggregate = workflow.split('\n  python:\n', 1)[1].split('\n  marketing:', 1)[0]
        for required in ['name: Fresh application tests', 'needs: [python-checks]', 'if: always()',
                         'QUILLMD_PYTHON_RESULT: ${{ needs.python-checks.result }}']:
            self.assertIn(required, aggregate)
        command = 'test "$QUILLMD_PYTHON_RESULT" = success'
        self.assertIn('run: ' + command, aggregate)
        self.assertIn('pattern: fresh-core-*-manifest', aggregate)
        self.assertIn('merge-multiple: true', aggregate)
        self.assertIn("run: python3 rebuild/ops/ci_test_shards.py --source-sha '${{ github.sha }}' core-manifests/core-shard-1.json core-manifests/core-shard-2.json", aggregate)
        self.assertIn('if-no-files-found: error', workflow)
        self.assertIn('include-hidden-files: true', workflow)
        self.assertLess(aggregate.index('run: ' + command), aggregate.index('actions/download-artifact'))
        for result in ['success', 'failure', 'cancelled', 'skipped', '']:
            with self.subTest(result=result):
                check = subprocess.run(['bash', '-c', command], env={'QUILLMD_PYTHON_RESULT': result})
                self.assertEqual(check.returncode == 0, result == 'success')
        self.assertIn('fail-fast: false', workflow)
        self.assertIn('lane: [core-1, core-2, support]', workflow)
        self.assertIn('timeout-minutes: 20', workflow.split('\n  python:\n', 1)[0])
