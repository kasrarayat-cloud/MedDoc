"""Pure synthetic metadata controls; never application/corpus qualification."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
LITERAL = ROOT / 'rebuild/ops/fixtures/word_dev33_mixed_consolidation.source'
adapter = types.ModuleType('word_dev33_mixed_consolidation_test_literal')
exec(compile(LITERAL.read_bytes(), str(LITERAL), 'exec'), adapter.__dict__)


class VersionedInstrumentIdentity(unittest.TestCase):
    def call(self, version=None, families=None, helpers=None, peer=None):
        adapter.validate_qualification_identity(
            adapter.INSTRUMENT_VERSION if version is None else version,
            copy.deepcopy(adapter.INSTRUMENT_FAMILIES) if families is None else families,
            copy.deepcopy(adapter.INSTRUMENT_FIXED_HELPERS) if helpers is None else helpers,
            adapter.PEER_SHA if peer is None else peer)

    def test_reviewed_r3_and_unchanged_historical_identity_are_admitted(self):
        self.call()
        self.call(version=adapter.VERSION, families=copy.deepcopy(adapter.DRIVERS))

    def test_r4_calendar_instrument_is_additive_and_cannot_be_hybridized(self):
        self.call(version=adapter.INSTRUMENT_R4_VERSION,
                  families=copy.deepcopy(adapter.INSTRUMENT_R4_FAMILIES))
        with self.assertRaises(adapter.IntegrityError):
            self.call(version=adapter.INSTRUMENT_R4_VERSION)
        with self.assertRaises(adapter.IntegrityError):
            self.call(families=copy.deepcopy(adapter.INSTRUMENT_R4_FAMILIES))
        for family, files in adapter.INSTRUMENT_R4_FAMILIES.items():
            for name in files:
                with self.subTest(family=family, file=name):
                    changed = copy.deepcopy(adapter.INSTRUMENT_R4_FAMILIES)
                    changed[family][name] = '0' * 64
                    with self.assertRaises(adapter.IntegrityError):
                        self.call(version=adapter.INSTRUMENT_R4_VERSION, families=changed)
                    del changed[family][name]
                    with self.assertRaises(adapter.IntegrityError):
                        self.call(version=adapter.INSTRUMENT_R4_VERSION, families=changed)
        changed = copy.deepcopy(adapter.INSTRUMENT_R4_FAMILIES)
        changed['foreign'] = {}
        with self.assertRaises(adapter.IntegrityError):
            self.call(version=adapter.INSTRUMENT_R4_VERSION, families=changed)

    def test_final_r5_preserves_old_r4_and_refuses_hybrid_hashes(self):
        self.call(version=adapter.INSTRUMENT_R5_VERSION,
                  families=copy.deepcopy(adapter.INSTRUMENT_R5_FAMILIES))
        self.call(version=adapter.INSTRUMENT_R4_VERSION,
                  families=copy.deepcopy(adapter.INSTRUMENT_R4_FAMILIES))
        with self.assertRaises(adapter.IntegrityError):
            self.call(version=adapter.INSTRUMENT_R5_VERSION,
                      families=copy.deepcopy(adapter.INSTRUMENT_R4_FAMILIES))
        with self.assertRaises(adapter.IntegrityError):
            self.call(version=adapter.INSTRUMENT_R4_VERSION,
                      families=copy.deepcopy(adapter.INSTRUMENT_R5_FAMILIES))
        for family, files in adapter.INSTRUMENT_R5_FAMILIES.items():
            for name in files:
                changed = copy.deepcopy(adapter.INSTRUMENT_R5_FAMILIES)
                changed[family][name] = '0' * 64
                with self.assertRaises(adapter.IntegrityError):
                    self.call(version=adapter.INSTRUMENT_R5_VERSION, families=changed)

    def test_unknown_version_and_hybrid_family_are_refused(self):
        with self.assertRaises(adapter.IntegrityError):
            self.call(version='word48-shared-segmented-r4-v1')
        with self.assertRaises(adapter.IntegrityError):
            self.call(families=copy.deepcopy(adapter.DRIVERS))
        with self.assertRaises(adapter.IntegrityError):
            self.call(version=adapter.VERSION)

    def test_each_changed_missing_extra_family_or_file_is_refused(self):
        for family, files in adapter.INSTRUMENT_FAMILIES.items():
            for name in files:
                with self.subTest(family=family, file=name):
                    changed = copy.deepcopy(adapter.INSTRUMENT_FAMILIES)
                    changed[family][name] = '0' * 64
                    with self.assertRaises(adapter.IntegrityError):
                        self.call(families=changed)
                    del changed[family][name]
                    with self.assertRaises(adapter.IntegrityError):
                        self.call(families=changed)
            changed = copy.deepcopy(adapter.INSTRUMENT_FAMILIES)
            del changed[family]
            with self.assertRaises(adapter.IntegrityError):
                self.call(families=changed)
        changed = copy.deepcopy(adapter.INSTRUMENT_FAMILIES)
        changed['foreign'] = {}
        with self.assertRaises(adapter.IntegrityError):
            self.call(families=changed)
        changed = copy.deepcopy(adapter.INSTRUMENT_FAMILIES)
        changed['fixed33']['foreign.py'] = 'a' * 64
        with self.assertRaises(adapter.IntegrityError):
            self.call(families=changed)

    def test_every_fixed_helper_and_peer_remains_required(self):
        for name in adapter.INSTRUMENT_FIXED_HELPERS:
            changed = copy.deepcopy(adapter.INSTRUMENT_FIXED_HELPERS)
            changed[name] = '0' * 64
            with self.assertRaises(adapter.IntegrityError):
                self.call(helpers=changed)
            del changed[name]
            with self.assertRaises(adapter.IntegrityError):
                self.call(helpers=changed)
        changed = copy.deepcopy(adapter.INSTRUMENT_FIXED_HELPERS)
        changed['foreign.py'] = '0' * 64
        with self.assertRaises(adapter.IntegrityError):
            self.call(helpers=changed)
        with self.assertRaises(adapter.IntegrityError):
            self.call(peer='05c157aacd0c717ca9835bc8b8482f8c100101e7be3f6a3aa46d49cd145e8a23')


class MixedNativeV3(unittest.TestCase):
    def setUp(self):
        self.prepared = json.loads((ROOT / 'docs/rebuild/v1/word-dev33-supported-layout-plan-prepared-20261004.json').read_text())
        self.manifest = json.loads((ROOT / 'docs/rebuild/v1/word-corpus-manifest.json').read_text())
        self.records = {r['identity']: r for r in self.prepared['records']}
        self.rights = {'records': [
            {'development_id': Path(r['corpus_file']).stem.split('-')[0], 'sha256': r['sha256'],
             'offline_filled_copy_replay_supported': Path(r['corpus_file']).stem.split('-')[0] in self.records}
            for r in self.manifest['sets']['dev']]}
        self.inventory = {'rebuild/core/views.py': '1' * 64, 'rebuild/documents/word_v3.py': '2' * 64}
        self.seal = {'source_commit': 'a' * 40, 'frozen_for_word_acceptance': True,
                     'plan_version': adapter.VERSION, 'layout_peer_helper_sha256': adapter.PEER_SHA,
                     'sealed_before_execution': True, 'thresholds': adapter.THRESHOLDS, 'provider_calls': 0,
                     'manifest_sha256': adapter.MANIFEST_SHA, 'rights_sha256': adapter.RIGHTS_SHA,
                     'prepared_plan_sha256': adapter.PREPARED_SHA, 'drivers': copy.deepcopy(adapter.DRIVERS),
                     'driver_sources': {n: r['path'] for n, r in self.prepared['supported_layout_driver_sources'].items()},
                     'helpers': self.prepared['unchanged_helpers'], 'source_hashes': self.inventory,
                     'raw_capture_required': True,
                     'packet_memberships': {p['packet']: p['identities'] for p in self.prepared['packets']}}
        self.bundles = []
        for p in self.prepared['packets']:
            native = p['identities'] == ['D01', 'D02']
            engine = 'native' if native else 'v3'
            results, raw, originals = {}, {}, []
            for identity in p['identities']:
                expected = self.records[identity]
                profiles = {name: {'profile': name, 'fixed_answers': {}, 'chosen_groundtruth_options': {},
                                  'answer_plan_notes': [], 'passed': True, 'failures': [],
                                  'fixed_protocol_passed': True, 'fixed_mechanical_passed': True,
                                  'fixed_failures': [], 'independent_choice_reader': {'passed': True},
                                  'render': {'exit_code': 0, 'problems': [], 'supplemental_problems': []},
                                  'export_sha256': 'b' * 64}
                            for name in adapter.FIXED_PROFILES}
                result = {'identity': identity, 'source_commit': self.seal['source_commit'],
                          'source_sha256': expected['original_sha256'], 'groundtruth_sha256': expected['groundtruth_sha256'],
                          'destinations': expected['fixed_answer_area_denominator'], 'families': expected['families'],
                          'previously_exposed': True, 'manual_mapping_corrections': 0, 'failures': [],
                          'mapping': {'strict': True}, 'profiles': profiles,
                          'automatic_success': True, 'fixed_protocol_success': True}
                results[identity] = result
                raw[identity] = {'adjudication': copy.deepcopy(result), 'mapping': {'strict': True},
                                 'import_contract': '' if native else 'v3',
                                 'profile_plans': copy.deepcopy(profiles),
                                 'exports': {name: 'b' * 64 for name in profiles}}
                originals.append({'development_id': identity, 'sha256': expected['original_sha256'],
                                  'prior_expected_map_path': expected['groundtruth'], 'families': expected['families']})
            db = 'quillmd_qa_sol_ops_dev33' + p['packet']
            self.bundles.append({'packet': p['packet'],
                'plan': {'source_commit': self.seal['source_commit'], 'thresholds': adapter.THRESHOLDS,
                         'provider_calls': 0, 'set': 'dev', 'rights_sha256': adapter.RIGHTS_SHA,
                         'manifest_sha256': adapter.MANIFEST_SHA, 'helpers': self.prepared['unchanged_helpers'],
                         'records': originals, 'source_hashes': copy.deepcopy(self.inventory), 'database_name': db},
                'summary': {'source_commit': self.seal['source_commit'], 'thresholds': adapter.THRESHOLDS,
                            'provider_calls': 0, 'results': results, 'actual_test_exit': 0,
                            'database_teardown_verified': True},
                'harness_before': copy.deepcopy(adapter.DRIVERS[engine]), 'harness_after': copy.deepcopy(adapter.DRIVERS[engine]),
                'source_before': copy.deepcopy(self.inventory), 'source_after': copy.deepcopy(self.inventory),
                'freeze': copy.deepcopy(self.seal), 'freeze_sha256': 'c' * 64, 'expected_seal_sha256': 'c' * 64,
                'outer_receipt': {'actual_outer_child_exit': 0, 'timed_out': False},
                'process_teardown': {'worker_exit': 0, 'renderer_exit': -2, 'timed_out': False, 'socket_removed': True},
                'database_after': {'requested_database': db, 'checked_names': [db, 'test_' + db],
                                   'verified': True, 'all_absent': True, 'present': []},
                'pid_and_container_absence_verified': True, 'raw_capture_verified': True,
                'raw_cases': raw, 'raw_hashes': {'synthetic-unit-receipt-only': 'd' * 64}})

    def report(self):
        return adapter.consolidate(self.prepared, self.manifest, self.rights, self.seal, self.inventory, self.bundles)

    def test_pre_reauthentication_peer_hash_is_refused(self):
        self.prepared['layout_peer_helper_sha256'] = '05c157aacd0c717ca9835bc8b8482f8c100101e7be3f6a3aa46d49cd145e8a23'
        self.reject()

    def test_pre_reauthentication_version_is_refused(self):
        self.prepared['plan_version'] = 'dev33-supported-layout-peer-v2'
        self.reject()

    def reject(self):
        with self.assertRaises(adapter.IntegrityError):
            self.report()

    def case(self, identity='D03'):
        bundle = next(b for b in self.bundles if identity in b['summary']['results'])
        return bundle, bundle['summary']['results'][identity], bundle['raw_cases'][identity]

    def synchronize(self, identity='D03'):
        bundle, result, raw = self.case(identity)
        raw['adjudication'] = copy.deepcopy(result)

    def test_distinct_declared_native_and_v3_are_retained_without_green_release(self):
        report = self.report()
        self.assertTrue(report['execution_complete'])
        self.assertEqual(report['counts']['overall'], {'successes': 33, 'denominator': 60, 'required': 54})
        self.assertEqual(report['counts']['holdout'], {'successes': 0, 'denominator': 20, 'required': 18})
        self.assertEqual(len(report['original_members']), 60)
        self.assertEqual(report['maximum_overall_if_all_eligible_and_original_holdout_pass'], 53)
        self.assertFalse(report['gate_pass'])
        self.assertFalse(report['ci_pass_claim'])
        self.assertEqual(report['recommended_exit'], 1)

    def test_changed_family_and_denominator_are_refused(self):
        self.prepared['records'][0]['families'] = ['F1']
        self.reject()

    def test_missing_packet_is_refused(self):
        self.bundles.pop()
        self.reject()

    def test_duplicate_packet_is_refused(self):
        self.bundles[-1] = copy.deepcopy(self.bundles[0])
        self.reject()

    def test_foreign_packet_is_refused(self):
        self.bundles[-1]['packet'] = 'P99'
        self.reject()

    def test_duplicate_original_is_refused(self):
        self.bundles[1]['plan']['records'][1] = copy.deepcopy(self.bundles[1]['plan']['records'][0])
        self.reject()

    def test_foreign_original_result_is_refused(self):
        self.bundles[0]['summary']['results']['N01'] = {}
        self.reject()

    def test_held_original_cannot_be_declared_eligible(self):
        self.rights['records'][5]['offline_filled_copy_replay_supported'] = True
        self.reject()

    def test_changed_groundtruth_is_refused(self):
        _, result, _ = self.case()
        result['groundtruth_sha256'] = '0' * 64
        self.synchronize()
        self.reject()

    def test_changed_profile_plan_is_refused(self):
        _, result, _ = self.case()
        result['profiles']['long']['fixed_answers'] = {'v3_1': 'short substitute'}
        self.synchronize()
        self.reject()

    def test_recovery_cannot_replace_fixed_profile(self):
        _, result, _ = self.case('D02')
        result['profiles']['long']['profile_kind'] = 'native_manual_recovery'
        self.synchronize('D02')
        self.reject()

    def test_manual_mapping_cannot_receive_automatic_credit(self):
        _, result, _ = self.case()
        result['manual_mapping_corrections'] = 1
        self.synchronize()
        self.reject()

    def test_manual_value_correction_cannot_receive_automatic_credit(self):
        _, result, _ = self.case('D02')
        result['profiles']['ordinary']['manual_value_corrections'] = {'name': {'fixed': '', 'reviewed': 'someone'}}
        self.synchronize('D02')
        self.reject()

    def test_native_recovery_is_kept_separate(self):
        _, result, raw = self.case('D02')
        profile = copy.deepcopy(result['profiles']['long'])
        profile.update(profile='native-long', profile_kind='native_manual_recovery', fixed_automatic_gate_credit=False)
        result['profiles']['native-long'] = profile
        raw['profile_plans']['native-long'] = copy.deepcopy(profile)
        raw['exports']['native-long'] = profile['export_sha256']
        self.synchronize('D02')
        self.assertEqual(self.report()['counts']['overall']['successes'], 33)

    def test_undeclared_native_or_foreign_harness_is_refused(self):
        self.bundles[1]['harness_before'] = copy.deepcopy(adapter.DRIVERS['native'])
        self.bundles[1]['harness_after'] = copy.deepcopy(adapter.DRIVERS['native'])
        self.reject()

    def test_changed_harness_after_is_refused(self):
        self.bundles[0]['harness_after']['fixed_render_checker.py'] = '0' * 64
        self.reject()

    def test_changed_source_after_is_refused(self):
        self.bundles[0]['source_after']['rebuild/core/views.py'] = '0' * 64
        self.reject()

    def test_seal_partial_source_cannot_match_independent_inventory(self):
        self.seal['source_hashes'] = {'rebuild/core/views.py': '1' * 64}
        self.reject()

    def test_source_commit_substitution_is_refused(self):
        self.bundles[0]['plan']['source_commit'] = 'f' * 40
        self.reject()

    def test_changed_helper_and_seal_are_refused(self):
        self.seal['helpers'] = {**self.seal['helpers'], 'score.py': '0' * 64}
        self.reject()

    def test_unsealed_raw_results_are_refused(self):
        self.bundles[0]['raw_capture_verified'] = False
        self.reject()

    def test_missing_raw_case_retains_incomplete_failure(self):
        bundle, _, _ = self.case()
        bundle['summary']['results']['D03'] = {'automatic_success': False, 'failures': ['method did not finish']}
        bundle['raw_cases'].pop('D03')
        bundle['outer_receipt']['actual_outer_child_exit'] = 1
        report = self.report()
        self.assertFalse(report['execution_complete'])
        self.assertEqual(report['recommended_exit'], 2)
        self.assertEqual(report['counts']['overall']['successes'], 32)

    def test_caught_child_failure_is_distinct_from_product_failure(self):
        bundle, _, _ = self.case()
        bundle['summary']['actual_test_exit'] = 1
        bundle['process_teardown']['worker_exit'] = 1
        bundle['outer_receipt']['actual_outer_child_exit'] = 1
        report = self.report()
        self.assertFalse(report['execution_complete'])
        self.assertEqual(report['status'], 'execution_incomplete_product_gate_unmet')
        self.assertFalse(report['gate_pass'])

    def test_product_failure_with_child_zero_is_completed_execution(self):
        bundle, result, raw = self.case()
        result['mapping']['strict'] = False
        raw['mapping']['strict'] = False
        result.update(automatic_success=False, fixed_protocol_success=False)
        self.synchronize()
        bundle['outer_receipt']['actual_outer_child_exit'] = 1
        report = self.report()
        self.assertTrue(report['execution_complete'])
        self.assertEqual(report['recommended_exit'], 1)
        self.assertEqual(report['counts']['overall']['successes'], 32)

    def test_living_database_prevents_success_credit(self):
        bundle, _, _ = self.case()
        bundle['database_after'].update(all_absent=False, present=['test_still_here'])
        bundle['summary']['database_teardown_verified'] = False
        bundle['outer_receipt']['actual_outer_child_exit'] = 1
        report = self.report()
        self.assertFalse(report['execution_complete'])
        self.assertEqual(report['counts']['overall']['successes'], 30)

    def test_wrong_watched_database_is_refused(self):
        self.bundles[0]['database_after']['requested_database'] = 'foreign'
        self.reject()

    def test_timeout_cannot_have_successful_outer_receipt(self):
        self.bundles[0]['outer_receipt']['timed_out'] = True
        self.reject()

    def test_selected_processor_cannot_be_substituted(self):
        _, _, raw = self.case()
        raw['import_contract'] = ''
        self.reject()

    def test_caught_render_failure_cannot_claim_fixed_pass(self):
        _, result, _ = self.case()
        result['profiles']['long']['render']['exit_code'] = 1
        self.synchronize()
        self.reject()

    def test_changed_export_is_refused(self):
        _, _, raw = self.case()
        raw['exports']['long'] = '0' * 64
        self.reject()

    def test_summary_must_equal_archived_adjudication(self):
        _, result, _ = self.case()
        result['automatic_success'] = False
        self.reject()

    def test_missing_real_process_exit_is_refused(self):
        self.bundles[0]['summary']['actual_test_exit'] = None
        self.reject()

    def test_default_prepared_performs_no_reads_or_processes(self):
        with patch.object(adapter, 'read_raw', side_effect=AssertionError('read')), \
                patch.object(adapter.subprocess, 'check_output', side_effect=AssertionError('process')), \
                contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(adapter.main([]), 0)
        self.assertEqual(json.loads(stdout.getvalue())['state'], 'PREPARED_NOT_EXECUTED')

    def test_changed_bytes_and_symlink_evidence_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'raw.json'
            path.write_bytes(b'original')
            expected = adapter.sha(path.read_bytes())
            path.write_bytes(b'changed')
            with self.assertRaises(adapter.IntegrityError):
                adapter.read_raw(path, expected)
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(adapter.IntegrityError):
                adapter.read_raw(link)

    def test_missing_execute_inputs_refuse_before_source_or_output(self):
        with patch.object(adapter, 'verified_source', side_effect=AssertionError('source read')):
            with self.assertRaises(adapter.IntegrityError):
                adapter.main(['--execute'])

    def test_verified_source_checks_non_python_bytes_despite_clean_git_status(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / 'rebuild').mkdir()
            python = source / 'rebuild/views.py'
            html = source / 'rebuild/page.html'
            python.write_bytes(b'pass\n')
            html.write_bytes(b'<p>original</p>')
            def blob(raw):
                return adapter.hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            tree = (f'100644 blob {blob(python.read_bytes())}\trebuild/views.py\0'
                    f'100644 blob {blob(html.read_bytes())}\trebuild/page.html\0').encode()
            def git(command, timeout):
                if command[3:] == ['rev-parse', 'HEAD']:
                    return b'a' * 40 + b'\n'
                if command[3:] == ['status', '--porcelain']:
                    return b''
                return tree
            with patch.object(adapter.subprocess, 'check_output', side_effect=git):
                self.assertEqual(adapter.verified_source(source, 'a' * 40), {'rebuild/views.py': adapter.sha(b'pass\n')})
                html.write_bytes(b'<p>changed hidden by stale git status</p>')
                with self.assertRaises(adapter.IntegrityError):
                    adapter.verified_source(source, 'a' * 40)

    def write_raw_bundle(self, path):
        bundle = self.bundles[0]
        payloads = {name + '.json': bundle[key] for name, key in [
            ('plan', 'plan'), ('partial-summary', 'summary'),
            ('prospective-harness-before', 'harness_before'), ('prospective-harness-after', 'harness_after'),
            ('source-before', 'source_before'), ('source-after', 'source_after'),
            ('process-teardown', 'process_teardown'), ('database-after', 'database_after')]}
        payloads['freeze-provenance.json'] = {'sha256': 'c' * 64, 'freeze': self.seal}
        payloads['independent-teardown.json'] = {'source_commit': self.seal['source_commit'],
                                               'all_recorded_pids_absent': True,
                                               'active_layout_containers': [], 'socket_removed': True}
        for identity, case in bundle['raw_cases'].items():
            payloads[identity + '/adjudication.json'] = case['adjudication']
            payloads[identity + '/automatic-groundtruth.json'] = case['mapping']
            payloads[identity + '/initial-mapping.json'] = {'contract': case['import_contract']}
            for name, profile in case['profile_plans'].items():
                # A tiny technical file verifies hashing; this is not DOCX qualification.
                raw_export = b'mocked pure unit export'
                profile['export_sha256'] = adapter.sha(raw_export)
                case['adjudication']['profiles'][name]['export_sha256'] = adapter.sha(raw_export)
                payloads[identity + '/' + name + '-profile-plan.json'] = profile
                export = path / identity / (name + '-export.docx')
                export.parent.mkdir(parents=True, exist_ok=True)
                export.write_bytes(raw_export)
        payloads['partial-summary.json']['results'] = {
            key: copy.deepcopy(value['adjudication']) for key, value in bundle['raw_cases'].items()}
        for name, value in payloads.items():
            target = path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value))
        files = {str(p.relative_to(path)): adapter.sha(p.read_bytes()) for p in path.rglob('*') if p.is_file()}
        capture = path / 'raw-evidence-manifest.json'
        capture.write_text(json.dumps({'captured_after_child_exit': True, 'source_commit': self.seal['source_commit'], 'files': files}))
        outer = path / 'outer-result.json'
        outer.write_text(json.dumps({**bundle['outer_receipt'], 'raw_evidence_manifest_sha256': adapter.sha(capture.read_bytes())}))
        return adapter.sha(outer.read_bytes())

    def test_raw_loader_binds_profile_export_and_outer_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            receipt = self.write_raw_bundle(path)
            loaded = adapter.load_bundle(path, self.prepared['packets'][0], 'c' * 64, receipt)
            self.assertTrue(loaded['raw_capture_verified'])
            self.assertIn('D02/long-export.docx', loaded['raw_hashes'])

    def test_profile_changed_after_raw_capture_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            receipt = self.write_raw_bundle(path)
            changed = path / 'D02/long-profile-plan.json'
            data = json.loads(changed.read_text())
            data['fixed_answers'] = {'wrong': 'replacement'}
            changed.write_text(json.dumps(data))
            with self.assertRaises(adapter.IntegrityError):
                adapter.load_bundle(path, self.prepared['packets'][0], 'c' * 64, receipt)

    def test_raw_capture_missing_hash_cannot_turn_into_unchecked_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.write_raw_bundle(path)
            outer = path / 'outer-result.json'
            data = json.loads(outer.read_text())
            data.pop('raw_evidence_manifest_sha256')
            outer.write_text(json.dumps(data))
            with self.assertRaises(adapter.IntegrityError):
                adapter.load_bundle(path, self.prepared['packets'][0], 'c' * 64, adapter.sha(outer.read_bytes()))
