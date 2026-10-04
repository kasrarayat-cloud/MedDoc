"""Pure project-authored envelopes; no corpus originals or runtime are opened."""
import ast
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / 'rebuild/ops/fixtures/word_holdout20_preparation.source'
m = types.ModuleType('holdout20_preparation_test')
m.__file__ = str(MODULE)
exec(compile(MODULE.read_bytes(), str(MODULE), 'exec'), m.__dict__)


class HoldoutPreparation(unittest.TestCase):
    def setUp(self):
        self.plan_raw = (ROOT / m.PREPARED).read_bytes()
        self.plan = json.loads(self.plan_raw)
        self.manifest = json.loads((ROOT / 'docs/rebuild/v1/word-corpus-manifest.json').read_bytes())
        # Synthetic validation envelopes only. Never retained as permission for
        # any actual original and never passed to the application or a provider.
        self.rights = {'version': 'original-holdout20-offline-rights-v1',
            'manifest_sha256': m.MANIFEST_SHA, 'scope': 'offline-synthetic-filled-copy-of-immutable-original',
            'provider_upload_authorized': False, 'adjudicated_by': 'Project-authored synthetic test',
            'adjudicated_at': '2026-10-04', 'records': [
                {'holdout_id': r['holdout_id'], 'original_sha256': r['original_sha256'],
                 'decision': 'allowed', 'offline_filled_copy_replay_supported': True,
                 'decision_basis': 'PROJECT-AUTHORED ENVELOPE ONLY; NOT ORIGINAL PERMISSION.',
                 'evidence': [{'path': 'synthetic-evidence-not-an-owner-ledger.json',
                              'sha256': m.sha(('synthetic:' + r['holdout_id']).encode())}]}
                for r in self.plan['records']]}
        self.observed = {'rebuild/project_authored_synthetic_only.py': m.sha(b'project-authored envelope')}
        self.freeze = {'source_commit': 'a' * 40, 'frozen_for_word_acceptance': True,
            'sealed_before_execution': True, 'thresholds': m.THRESHOLDS, 'provider_calls': 0,
            'manifest_sha256': m.MANIFEST_SHA, 'holdout_plan_sha256': m.sha(self.plan_raw),
            'holdout_rights_sha256': m.sha(json.dumps(self.rights).encode()), 'holdout_rights_reviewed': True,
            'parent_driver_sha256': m.PARENT, 'source_hashes': self.observed,
            'originals_previously_exposed': True, 'new_independence_claim': False}

    def test_exact_prepared_original20_and_synthetic_permission_envelopes_validate(self):
        self.assertEqual(m.sha(self.plan_raw), m.PREPARED_SHA)
        self.assertEqual(list(m.validate_plan(self.plan, self.manifest)), m.IDS)
        self.assertEqual(len(m.validate_rights(self.plan, self.rights)), 20)
        m.validate_freeze(self.plan, self.rights, self.freeze, self.observed,
                          m.sha(self.plan_raw), self.freeze['holdout_rights_sha256'])
        self.assertEqual(self.plan['unsupported_originals'], ['H03', 'H20'])
        self.assertFalse(self.plan['gate_pass'])
        self.assertIsNone(self.plan['final_source_commit'])

    def test_missing_duplicate_foreign_or_disappeared_originals_refuse(self):
        for target in ('records', 'packets', 'manifest'):
            for mode in ('missing', 'duplicate', 'foreign'):
                with self.subTest(target=target, mode=mode):
                    plan, manifest = deepcopy(self.plan), deepcopy(self.manifest)
                    if target == 'records':
                        if mode == 'missing': plan['records'].pop()
                        elif mode == 'duplicate': plan['records'][-1] = deepcopy(plan['records'][0])
                        else: plan['records'][-1]['holdout_id'] = 'N20'
                    elif target == 'packets':
                        if mode == 'missing': plan['packets'][-1]['identities'].pop()
                        elif mode == 'duplicate': plan['packets'][-1]['identities'][-1] = 'H01'
                        else: plan['packets'][-1]['identities'][-1] = 'D01'
                    else:
                        if mode == 'missing': manifest['sets']['holdout'].pop()
                        elif mode == 'duplicate': manifest['sets']['holdout'][-1] = deepcopy(manifest['sets']['holdout'][0])
                        else: manifest['sets']['holdout'][-1]['corpus_file'] = 'holdout/originals/N20-foreign.docx'
                    with self.assertRaises(ValueError): m.validate_plan(plan, manifest)

    def test_source_profiles_original_formats_families_and_protocol_cannot_change(self):
        mutations = [lambda p: p['records'][0].update(original_sha256='0' * 64),
                     lambda p: p['records'][0].update(corpus_file='dev/originals/D01.docx'),
                     lambda p: p['records'][0].update(families=['F1']),
                     lambda p: p['records'][2].update(format='docx'),
                     lambda p: p['records'][0].update(fixed_profiles=['ordinary']),
                     lambda p: p['thresholds'].update(holdout_required=17),
                     lambda p: p.update(originals_previously_exposed=False),
                     lambda p: p.update(provider_calls=1),
                     lambda p: p.update(gate_pass=True)]
        for change in mutations:
            with self.subTest(change=change):
                p = deepcopy(self.plan); change(p)
                with self.assertRaises(ValueError): m.validate_plan(p, self.manifest)

    def test_groundtruth_path_hash_and_exact_preparation_bytes_refuse_mutation(self):
        p = deepcopy(self.plan); p['records'][0]['groundtruth'] = '/tmp/easier-groundtruth.json'
        with self.assertRaises(ValueError): m.validate_plan(p, self.manifest)
        for change in (lambda p: p['records'][0].update(groundtruth_sha256='0' * 64),
                       lambda p: p['protocol'].update(sha256='0' * 64),
                       lambda p: p['unchanged_helpers'].update({'score.py': '0' * 64})):
            p = deepcopy(self.plan); change(p); altered = m.sha(json.dumps(p).encode())
            f = deepcopy(self.freeze); f['holdout_plan_sha256'] = altered
            with self.assertRaises(ValueError):
                m.validate_freeze(p, self.rights, f, self.observed, altered, f['holdout_rights_sha256'])

    def test_absent_triage_foreign_or_inconsistent_permission_fails_closed(self):
        for change in (lambda r: r.clear(), lambda r: r.update(version='015-triage-not-adjudicated'),
                       lambda r: r['records'].pop(),
                       lambda r: r['records'][-1].update(holdout_id='H01'),
                       lambda r: r['records'][0].update(original_sha256='0' * 64),
                       lambda r: r['records'][0].update(offline_filled_copy_replay_supported=False),
                       lambda r: r['records'][0].update(evidence=[]),
                       lambda r: r.update(provider_upload_authorized=True),
                       lambda r: r.update(adjudicated_by='')):
            with self.subTest(change=change):
                ledger = deepcopy(self.rights); change(ledger)
                with self.assertRaises(ValueError): m.validate_rights(self.plan, ledger)
        held = deepcopy(self.rights)
        held['records'][0].update(decision='held', offline_filled_copy_replay_supported=False)
        self.assertFalse(m.validate_rights(self.plan, held)['H01']['offline_filled_copy_replay_supported'])

    def test_unsealed_wrong_source_or_unreviewed_rights_refuse(self):
        for change in (lambda f: f.update(source_commit='a' * 8),
                       lambda f: f.update(frozen_for_word_acceptance=False),
                       lambda f: f.update(sealed_before_execution=False),
                       lambda f: f.update(holdout_rights_reviewed=False),
                       lambda f: f.update(holdout_rights_sha256='0' * 64),
                       lambda f: f.update(source_hashes={}),
                       lambda f: f.update(parent_driver_sha256={}),
                       lambda f: f.update(new_independence_claim=True)):
            with self.subTest(change=change):
                f = deepcopy(self.freeze); change(f)
                with self.assertRaises(ValueError):
                    m.validate_freeze(self.plan, self.rights, f, self.observed,
                                      m.sha(self.plan_raw), self.freeze['holdout_rights_sha256'])

    def test_permission_evidence_must_exist_with_exact_bytes_and_triage_cannot_allow(self):
        raw = b'Project-authored synthetic evidence only; no original permission.'
        ledger = deepcopy(self.rights)
        for row in ledger['records']:
            row['evidence'] = [{'path': '/synthetic-envelope-only.json', 'sha256': m.sha(raw)}]
        with patch.object(m, 'read_decision_raw', return_value=raw) as reader:
            m.verify_rights_evidence(ledger)
            self.assertEqual(reader.call_count, 20)
        for failure in (FileNotFoundError('missing synthetic evidence'), ValueError('foreign namespace')):
            with patch.object(m, 'read_decision_raw', side_effect=failure):
                with self.assertRaises(type(failure)): m.verify_rights_evidence(ledger)
        with patch.object(m, 'read_decision_raw', return_value=raw + b'changed'):
            with self.assertRaises(ValueError): m.verify_rights_evidence(ledger)
        for row in ledger['records']:
            row['evidence'] = [{'path': '/metadata/' + m.TRIAGE_NAME, 'sha256': m.sha(raw)}]
        with self.assertRaisesRegex(ValueError, 'triage is not permission'):
            m.validate_rights(self.plan, ledger)
        for path in ('/etc/environment', '/opt/meddoc-pro/rebuild/.env', '/tmp/missing-permission.json',
                     str(m.DECISION_ROOTS[0]) + '/../../../foreign.json'):
            with self.assertRaises(ValueError): m.read_decision_raw(Path(path))

    def test_missing_rights_refuses_actual_binding_before_output_or_full_source_helper(self):
        template = json.loads((ROOT / 'docs/rebuild/v1/word-eval/holdout20-offline-rights-PREPARED.json').read_bytes())
        with self.assertRaises(ValueError): m.validate_rights(self.plan, template)
        with tempfile.TemporaryDirectory(prefix='project-authored-holdout-envelope-') as name:
            source = Path(name)
            files = [m.PREPARED, 'docs/rebuild/v1/word-corpus-manifest.json', self.plan['protocol']['path']]
            files.extend('docs/rebuild/v1/word-eval/' + n for n in self.plan['unchanged_helpers'])
            for file in files:
                target = source / file; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / file).read_bytes())
            output = m.OWNED / 'synthetic-envelope-never-created-by-this-test'
            with patch.object(m, 'verify_rights_evidence', side_effect=AssertionError('must not read decision evidence')):
                with self.assertRaises(FileNotFoundError):
                    m.bind(source, source / 'unused-freeze.json', source / 'absent-rights.json', output)
            self.assertFalse(output.exists())

    def test_derivative_keeps_provider_protection_routes_and_unchanged_render_checker(self):
        literals = {n: (ROOT / m.LITERALS / n).read_bytes() for n in m.PARENT}
        derived = m.derive(literals, self.plan, self.rights, m.sha(self.plan_raw), self.freeze['holdout_rights_sha256'])
        inner = derived['holdout_application.py'].decode()
        outer = derived['run_holdout_application.py'].decode()
        self.assertIn("patch('anthropic.Anthropic',side_effect=AssertionError('Original corpus provider transmission forbidden'))", inner)
        self.assertIn("plan['set'] == 'holdout'", inner)
        self.assertIn("C/'holdout/originals'", inner)
        self.assertIn("digest(groundtruth_raw)==record['groundtruth_sha256']", inner)
        self.assertIn('quillmd_qa_sol_ops_h20', outer)
        self.assertEqual(derived['fixed_render_checker.py'], literals['fixed_render_checker.py.source'])
        original_ast = ast.parse(literals['dev_application_gate_v2.py.source'])
        derivative_ast = ast.parse(inner)
        originals = {n.name: ast.dump(n, include_attributes=False) for n in original_ast.body if isinstance(n, ast.FunctionDef)}
        actual = {n.name: ast.dump(n, include_attributes=False) for n in derivative_ast.body if isinstance(n, ast.FunctionDef)}
        self.assertEqual(originals, actual)  # all standalone primitives/guards unchanged
        for text in (inner, outer): ast.parse(text)
        for bad in ('provider', 'profile', 'route', 'scorer'):
            changed = dict(literals)
            original = changed['dev_application_gate_v2.py.source']
            replace = {'provider': (b"Original corpus provider transmission forbidden", b"disabled"),
                       'profile': (b"'empty','ordinary','long'", b"'ordinary'"),
                       'route': (b"'action':'v3_confirm'", b"'action':'unsafe'"),
                       'scorer': (b'd9e0c5bbb7c51d10bb30c1e65f2ec5b7cd1569e6baed6db95d8207c66938e88c', b'0' * 64)}[bad]
            self.assertIn(replace[0], original)
            changed['dev_application_gate_v2.py.source'] = original.replace(*replace, 1)
            with self.assertRaises(ValueError):
                m.derive(changed, self.plan, self.rights, m.sha(self.plan_raw), self.freeze['holdout_rights_sha256'])

    def test_default_invocation_reads_and_executes_nothing(self):
        with patch.object(sys, 'argv', ['prepared']), patch.object(Path, 'read_bytes', side_effect=AssertionError('read')):
            with redirect_stdout(io.StringIO()) as output: m.main()
        self.assertEqual(json.loads(output.getvalue()), {'state': 'PREPARED_ONLY', 'application_runs': 0, 'gate_pass': False})


if __name__ == '__main__':
    unittest.main()
