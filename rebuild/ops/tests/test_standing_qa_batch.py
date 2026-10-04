"""Finite pure preparation controls; no provider or database qualification."""
from dataclasses import replace
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from contextlib import redirect_stdout
from unittest import TestCase
from unittest.mock import patch
import hashlib
import io
import json
import socket
from zipfile import ZipFile
from lxml import etree

from ops import standing_qa as standing, standing_qa_batch as batch
from . import test_standing_qa as standing_contract

PREPARED_DECLARATION = batch.BASE / 'fixtures/ordinary-batch-declaration-3.prepared.source'


class SupplementalBatchPlan(TestCase):
    def setUp(self):
        deny = patch.object(socket.socket, 'connect', side_effect=AssertionError('No network or database in pure preparation'))
        deny.start();self.addCleanup(deny.stop)
        self.inputs = batch.frozen_inputs()
        self.sends = batch.plan_sends(self.inputs)

    def test_project_owned_original_has_exact_101_physical_rows(self):
        original = batch.original_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), batch.ORIGINAL_SHA)
        with ZipFile(io.BytesIO(original)) as z:
            root = etree.fromstring(z.read('word/document.xml'))
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        rows = root.xpath('./w:body/w:tbl/w:tr', namespaces=ns)
        self.assertEqual(len(rows), 101)
        labels = [''.join(r.xpath('./w:tc[1]//w:t/text()', namespaces=ns)) for r in rows]
        self.assertEqual(labels, ['Current symptoms'] + [f'Clinical detail {i:03d}' for i in range(2, 101)] + ['Plan'])
        self.assertTrue(all(not r.xpath('./w:tc[2]//w:t/text()', namespaces=ns) for r in rows))

    def test_two_children_have_distinct_once_only_identities(self):
        self.assertEqual([s.id for s in self.sends], [batch.FIRST, batch.SECOND])
        self.assertEqual([s.index for s in self.sends], [1, 2])
        self.assertEqual(standing.needs(self.sends[1]), batch.FIRST)
        self.assertIsNone(standing.needs(self.sends[0]))
        self.assertEqual(standing.select_batch(self.sends, 2), self.sends)

    def test_one_request_cap_cannot_admit_half_a_form(self):
        with self.assertRaisesRegex(standing.Refused, 'No send fits'):
            standing.select_batch(self.sends, 1)

    def test_second_child_never_reuses_a_first_attempt_from_an_earlier_run(self):
        with self.assertRaisesRegex(standing.Refused, 'first child'):
            standing.require_none_stranded('ordinary_batch', [self.sends[1]])

    def test_foreign_or_mutated_send_is_refused(self):
        for field, value in [('id', 'ordinary_batch:part-3'), ('path', batch.PATHS[1]), ('kind', 'mapping'),
                             ('form', 'foreign'), ('index', 2), ('pricing_key', 'ordinary_notes')]:
            with self.subTest(field=field), self.assertRaises(batch.pc.Refused):
                batch.send_inputs(replace(self.sends[0], **{field: value}), self.inputs)

    def test_original_and_notes_identities_are_both_retained(self):
        one = batch.send_inputs(self.sends[0], self.inputs)
        two = batch.send_inputs(self.sends[1], self.inputs)
        self.assertEqual(one, two)
        self.assertEqual(one['form_sha256'], batch.ORIGINAL_SHA)
        self.assertEqual(one['notes_sha256'], hashlib.sha256(self.inputs['batch']['notes'].encode()).hexdigest())

    def test_missing_and_unsafe_answers_are_not_a_useful_batch(self):
        fields = [{'key': 'first', 'label': 'Current symptoms'}, {'key': 'middle', 'label': 'Clinical detail 002'},
                  {'key': 'last', 'label': 'Plan'}]
        answers = {'first': {'status': 'supported', 'text': self.inputs['batch']['desired_supported']['Current symptoms']},
                   'middle': {'status': 'missing', 'text': ''},
                   'last': {'status': 'supported', 'text': self.inputs['batch']['desired_supported']['Plan']}}
        self.assertEqual(batch.usefulness(fields, answers, self.inputs['batch']),
                         {'first': 'supported_correct', 'middle': 'missing', 'last': 'supported_correct'})
        answers['last'] = {'status': 'conflict', 'text': ''}
        self.assertEqual(batch.usefulness(fields, answers, self.inputs['batch'])['last'], 'held_unadjudicated')
        answers['middle'] = {'status': 'supported', 'text': 'No disease.'}
        outcomes = batch.usefulness(fields, answers, self.inputs['batch'])
        self.assertEqual(outcomes['middle'], 'unsupported_accepted')
        self.assertTrue(batch.pc.classify_case(outcomes, [])['stops_stage'])

    def test_staged_is_known_cost_only_with_actual_receipt_and_usage(self):
        self.assertEqual(batch.child_class('staged', object(), object(), True, None), 'completed')
        for state, receipt, usage, deadline in [('running', None, None, None), ('staged', object(), None, None),
                                               ('staged', None, object(), None), ('staged', object(), object(), 'deadline')]:
            self.assertEqual(batch.child_class(state, receipt, usage, True, deadline), 'uncertain')
        self.assertEqual(batch.child_class('reconciliation', None, None, True, None), 'reconciliation')

    def test_generic_batch_flag_stays_off_and_pricing_is_separate(self):
        self.assertEqual(standing.STAGE_FLAGS['ordinary_batch']['QUILLMD_V3_GENERATION_BATCHES'], '0')
        self.assertEqual(standing.STAGE_FLAGS['ordinary_batch']['QUILLMD_V3_FIELD_RELATIONS'], '0')
        self.assertEqual({s.pricing_key for s in self.sends}, {'ordinary_notes_field_relations'})
        self.assertEqual(standing.STAGE_PRICING['ordinary_batch'], ('ordinary_notes', 'ordinary_notes_field_relations'))

    def test_changed_manifest_is_refused_before_any_provider_work(self):
        with patch.object(Path, 'read_bytes', return_value=b'{}'):
            with self.assertRaisesRegex(batch.pc.Refused, 'manifest changed'):
                batch.frozen_inputs()

    def test_modified_source_or_desired_answers_cannot_change_the_plan(self):
        for key, value in [('notes', 'A different patient.'), ('desired_missing_count', 98),
                           ('desired_supported', {'Plan': 'Invent a diagnosis.'})]:
            inputs = deepcopy(self.inputs)
            inputs['batch'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(batch.pc.Refused, 'exact frozen'):
                batch.plan_sends(inputs)

    def test_mapping_review_keeps_automatic_incomplete_status_and_refuses_real_omissions_or_edits(self):
        from documents.word_v3 import inspect
        from documents.import_selection import digest
        fields = inspect(batch.original_bytes())['fields']
        coverage = {'automatic_complete': False, 'review_required': True, 'block_generation': False,
                    'legacy_omissions': [], 'legacy_unmapped': [], 'v3_uncovered_legacy_places': []}
        manifest = {'engine': 'v3', 'source_sha256': batch.ORIGINAL_SHA, 'mapping_sha256': digest(fields),
                    'initial_mapping_sha256': digest(fields), 'coverage': coverage}
        self.assertEqual(batch.mapping_admission(manifest, fields), coverage)
        self.assertFalse(coverage['automatic_complete'])
        for mutate in [lambda m: m.update(source_sha256='f'*64),
                       lambda m: m.update(mapping_sha256='f'*64),
                       lambda m: m.update(initial_mapping_sha256='f'*64),
                       lambda m: m['coverage'].update(block_generation=True),
                       lambda m: m['coverage'].update(legacy_omissions=[{'label': 'Plan'}]),
                       lambda m: m['coverage'].update(v3_uncovered_legacy_places=[['lost']]),
                       lambda m: m['coverage'].update(selected_engine_issues=[{'label': 'Plan'}])]:
            changed = deepcopy(manifest);mutate(changed)
            with self.assertRaises(batch.pc.Refused):batch.mapping_admission(changed, fields)
        with self.assertRaises(batch.pc.Refused):batch.mapping_admission(manifest, fields[:-1])

    def test_actual_product_envelope_is_unwrapped_without_discarding_the_raw_message(self):
        message = {'id': 'msg_synthetic', 'model': 'claude-sonnet-5-5', 'usage': {'input_tokens': 100}}
        self.assertEqual(batch.provider_message({'provider_output': message}, None), message)
        self.assertEqual(batch.provider_message(None, {'status_code': 200, 'body_json': message}), message)
        self.assertEqual(batch.provider_message(None, {'status_code': 500, 'body_json': message}), {})
        self.assertEqual(batch.provider_message({'provider_output': []}, None), {})

    def test_intermediate_audit_keeps_all_money_checks_and_only_two_exact_expected_jobs(self):
        expected = {'first': ('generation_part', 'staged'), 'second': ('generation_part', 'queued')}
        report = {'all_checks_pass': True, 'unsettled_provider_receipts': [], 'durable_receipt_gaps': [],
                  'unresolved_jobs': [{'id': key, 'kind': kind, 'state': state}
                                      for key, (kind, state) in expected.items()],
                  'rows': [{'job_id': 'first', 'checks': {'ledger_debit_matches': True}}]}
        self.assertEqual(batch.staged_audit_problems(report, 'first', expected), [])
        for mutate in [lambda r: r.update(all_checks_pass=False),
                       lambda r: r['rows'][0]['checks'].update(ledger_debit_matches=False),
                       lambda r: r['unresolved_jobs'].append({'id': 'foreign', 'kind': 'generation', 'state': 'running'}),
                       lambda r: r['unresolved_jobs'][1].update(state='reconciliation'),
                       lambda r: r.update(unsettled_provider_receipts=[{'job_id': 'first'}]),
                       lambda r: r.update(durable_receipt_gaps=['first'])]:
            changed = deepcopy(report);mutate(changed)
            self.assertTrue(batch.staged_audit_problems(changed, 'first', expected))

    def test_abort_failure_is_retained_without_exposing_the_credential_or_claiming_success(self):
        worker = object.__new__(batch.BatchRun)
        worker.secret = 'SYNTHETIC_PRIVATE_TOKEN'
        with patch.object(worker, '_stop_remaining', side_effect=RuntimeError('cleanup failed SYNTHETIC_PRIVATE_TOKEN')):
            result = worker.abort_remaining('stop')
        self.assertEqual(result['error']['class'], 'RuntimeError')
        self.assertIn('cleanup failed', result['error']['message'])
        self.assertNotIn(worker.secret, json.dumps(result))
        self.assertTrue(result['error']['no_retry'])
        worker.batch = SimpleNamespace(refresh_from_db=lambda: (_ for _ in ()).throw(RuntimeError('readback failed')))
        with patch.object(worker, '_stop_remaining'):
            readback = worker.abort_remaining('stop')
        self.assertEqual(readback['error']['message'], 'readback failed')
        self.assertTrue(readback['batch_admitted'])

    def test_all_stage_report_binds_the_supplemental_inputs_separately(self):
        inputs = standing.sq.stages_module().frozen_inputs()
        report = standing.plan_definitions(inputs)
        self.assertEqual(report['ordinary_batch']['count'], 2)
        self.assertTrue(all(s['inputs']['form_sha256'] == batch.ORIGINAL_SHA
                            for s in report['ordinary_batch']['sends']))
        self.assertEqual(report['notes_comparison']['count'], 28)

    def test_historical_33_send_plan_is_unchanged(self):
        inputs = standing.sq.stages_module().frozen_inputs()
        notes = standing.standing_plan('notes_comparison', inputs)
        voice = standing.standing_plan('transcription', {'transcription_audio': ['soap-ankle-speech', 'colonoscopy-speech']})
        self.assertEqual(len(notes), 28)
        self.assertEqual(len(standing.standing_plan('model_check')), 1)
        self.assertEqual(len(voice), 4)
        self.assertEqual(len({s.id for s in notes}), 28)
        self.assertEqual(sum(s.path == 'default' for s in notes), 14)
        self.assertEqual(sum(s.path == 'field_relations' for s in notes), 14)

    def test_prepared_declaration_uses_its_own_normal_three_send_campaign(self):
        root, path = standing_contract.repository(self, PREPARED_DECLARATION.read_text(),
                            name='20261004-quillmd-v1-standing-api-testing-3.md')
        declaration = standing.declared_standing(path, repository=root, out=io.StringIO())
        places = standing.require_live(declaration)
        self.assertEqual(places['database'], 'quillmd_qa_standing_20261004_3')
        self.assertEqual([(s.id, s.sends, s.requires) for s in declaration.stages],
                         [('model_check', 1, None), ('ordinary_batch', 2, 'model_check')])
        self.assertEqual(declaration.max_sends_per_run, 2)
        self.assertIsNone(declaration.limits().total)
        self.assertEqual(declaration.pricing_version(batch.PRICING),
                         'configured-v1:f714798b73422cc8efe10325a2d9fedb2014bdd771f193df87c117d24aec89e8')

    def test_foreign_root_and_noncanonical_declaration_keep_normal_refusals(self):
        text = PREPARED_DECLARATION.read_text()
        for changed, name in [(text.replace('v1-standing-api-testing-20261004-3\n', 'v1-standing-api-testing-20261004-2\n'),
                               '20261004-quillmd-v1-standing-api-testing-3.md'),
                              (text, '20261004-quillmd-v1-standing-api-testing-2.md')]:
            root, path = standing_contract.repository(self, changed, name=name)
            with self.assertRaises(batch.pc.Refused):
                declaration = standing.declared_standing(path, repository=root, out=io.StringIO())
                standing.require_live(declaration)

    def test_previous_second_campaign_declaration_is_preserved_exactly(self):
        file = batch.BASE.parents[1] / 'docs/foundation/mutations/20261004-quillmd-v1-standing-api-testing-2.md'
        self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),
                         '52b6c5a4a6ceee357759500fc21ef529476e88d365e336f0f79c05662b44d172')

    def test_readonly_plan_marks_the_batch_undeclared_on_old_campaigns_and_binds_new_source(self):
        for text, name, expected in [(standing_contract.fixture_text(), standing_contract.DECLARATION_NAME, False),
                                    (PREPARED_DECLARATION.read_text(), '20261004-quillmd-v1-standing-api-testing-3.md', True)]:
            root, path = standing_contract.repository(self, text, name=name)
            runtime = standing_contract.scratch(self) / 'never-created-readonly-plan'
            with redirect_stdout(io.StringIO()):
                result = standing.plan_report(root=runtime, declaration_path=path, repository=root)
            row = result['stages']['ordinary_batch']
            if expected:
                self.assertEqual(row['remaining'], [batch.FIRST, batch.SECOND])
                self.assertTrue(all(s['inputs']['form_sha256'] == batch.ORIGINAL_SHA for s in row['sends']))
            else:
                self.assertFalse(row['declared'])
                self.assertNotIn('remaining', row)
            self.assertFalse(runtime.exists())
