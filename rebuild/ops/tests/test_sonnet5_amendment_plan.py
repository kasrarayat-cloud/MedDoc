"""The ordinary_notes plan under a contract-identity amendment and in REMAINDER mode, priced offline by the stage's own
functions in a fresh process (ops/tests/amendment_plan_driver.py): a synthetic declaration and amendment committed in a
temporary checkout, and a temporary ledger shaped like the live one after failure 1 (attempts 3–17 made, the six
field-relations sends N03, N10, N13, N14, N15 and N16 not sent). No credential, network or database; nothing real is
read or written.

What each test proves, and how it would fail:
  · the exact contract-only change is accepted: the plan is exactly the six unsent relations sends, in plan order, each
    at the amended pricing version with a maximum recomputed by the same compiler, and every bound and their sum fit
    the limits left; with a fresh ledger the whole plan keeps every default send at its frozen maximum;
  · without the amendment the relations sends refuse at the declared version;
  · a changed rate, an amendment whose base is not the pinned one, one naming a contract the engine does not run, a
    maximum (or the sum) that does not fit the limit left, and a failure record that would re-send a made send all
    refuse before anything is planned.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from ops import provider_campaign as pc
from ops import sonnet5_stages as st
from . import network_guard
from .test_provider_campaign import (REAL_TEXT, RELATIONS_BASE, RELATIONS_V1, RELATIONS_V2, amendment_text, attempt, git,
                                     limits_record, repository_with, scratch, terms_record, usage)

REBUILD = Path(__file__).resolve().parents[2]
DRIVER = Path(__file__).resolve().parent / 'amendment_plan_driver.py'
UNSENT = ['notes:N03:field_relations', 'notes:N10:field_relations', 'notes:N13:field_relations',
          'notes:N14:field_relations', 'notes:N15:field_relations', 'notes:N16:field_relations']


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


def live_shape(test, declaration, *, not_sent=UNSENT, reopened=False, exposure_tokens=2000, extra_attempted=()):
    """A temporary campaign root whose ledger is the live one's shape after ordinary_notes failure 1 (RECONSTRUCTED from
    the live stage-ordinary_notes-failed-1.json: its plan, its attempts 3..17 and its not_sent list): model_check passed
    on attempt 1, mapping failed on attempt 2, ordinary_notes attempts 3..17 completed, failure 1 recorded."""
    root = scratch(test)
    campaign = pc.Campaign(declaration, root)
    ledger = campaign.ledger
    ledger.acquire()
    d = declaration
    plan = [s.id for s in st.plan_sends('ordinary_notes', st.frozen_inputs())]
    made = [send for send in plan if send not in not_sent] + list(extra_attempted)

    def write(number, stage, send=None, maximum='0.104896', tokens=840):
        record = attempt(number, stage, maximum, campaign=d.campaign, authority=d.authority_id, limits=limits_record(d),
                         terms=terms_record(d))
        if send:
            record['send'] = {'id': send}
        ledger.write_attempt(record)
        ledger.write_outcome(number, {'class': 'completed', 'usage': usage(input_tokens=tokens, output_tokens=118)})
    write(1, 'model_check')
    ledger.write_stage('model_check', 'passed', {'attempt': 1})
    write(2, 'mapping', 'mapping:f1-guidance-confirmation', '0.60')
    ledger.write_stage('mapping', 'failed', {'reasons': ['synthetic'], 'summary': {'plan': [], 'not_sent': []}})
    for number, send in enumerate(made, 3):
        write(number, 'ordinary_notes', send, '0.2332', exposure_tokens)
    ledger.write_stage('ordinary_notes', 'failed', {
        'reasons': ['notes:N02:field_relations: the attempt ended completed with the job failed (ValidationError)'],
        'summary': {'plan': plan, 'sends': [{'send': {'id': send}, 'attempt': number} for number, send in enumerate(made, 3)],
                    'not_sent': list(not_sent), 'attempts': list(range(3, 3 + len(made)))}})
    if reopened:
        ledger.write_reopen('ordinary_notes', 1, {'ledger_attempts': len(ledger.rows()), 'repair_commit': '0' * 40})
    ledger.release()
    return root


class AmendedPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = st.frozen_inputs()

    def setUp(self):
        self.repo, self.path = repository_with(self, REAL_TEXT)
        import io
        self.declaration = pc.declared(self.path, repository=self.repo, out=io.StringIO())

    def amendment(self, name='20260929-amendment.md', **changes):
        path = self.path.parent / name
        path.write_text(amendment_text(self.declaration.sha256, **changes), encoding='utf-8')
        git(self.repo, 'add', '--', str(path.relative_to(self.repo)))
        git(self.repo, 'commit', '-q', '-m', 'Synthetic amendment')
        return path

    def plan(self, root, amendment=None, settings=None, drift_default=False):
        state = scratch(self)
        spec = {'declaration': str(self.path), 'repository': str(self.repo), 'root': str(root), 'state': str(state),
                'amendment': str(amendment) if amendment else None, 'stage': 'ordinary_notes', 'settings': settings,
                'drift_default': drift_default}
        spec_path = state / 'spec.json'
        spec_path.write_text(json.dumps(spec))
        env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TMPDIR': str(state), 'HOME': str(state),
               'PYTHONDONTWRITEBYTECODE': '1'}
        done = subprocess.run([sys.executable, '-B', str(DRIVER), str(spec_path)], cwd=REBUILD, capture_output=True,
                              text=True, timeout=900, env=env)
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        return json.loads(done.stdout)

    def test_the_exact_contract_only_change_plans_only_the_six_unsent_sends_at_recomputed_maxima(self):
        for reopened in (False, True):
            with self.subTest(reopened=reopened):
                out = self.plan(live_shape(self, self.declaration, reopened=reopened), self.amendment(f'a-{reopened}.md'))
                report = out['report']
                self.assertEqual([row['id'] for row in report['order']], UNSENT)
                self.assertEqual(report['sends'], 6)
                self.assertEqual(report['remainder']['sends'], UNSENT)
                self.assertEqual(report['remainder']['failure'], 1)
                self.assertEqual(report['amendment']['pricing_version'], RELATIONS_V2)
                for row in report['order']:
                    self.assertEqual((row['pricing_version'], row['pricing_version_is_declared'], row['amended']),
                                     (RELATIONS_V2, True, True))
                    case = next(c for c in self.inputs['cases']['cases'] if c['id'] == row['case'])
                    frozen = Decimal(case['cost_bound_usd']['field_relations']['provider_cost_max'])
                    self.assertGreater(Decimal(row['maximum_cost']), frozen)        # (the keyed schema is larger)
                    self.assertLess(Decimal(row['maximum_cost']), frozen + Decimal('0.01'))
                    self.assertEqual(Decimal(row['bound_x1_1']), Decimal(row['maximum_cost']) * Decimal('1.1'))
                self.assertTrue(report['worst_case_fits'])
                self.assertEqual(Decimal(report['stage_worst_case']),
                                 sum(Decimal(row['bound_x1_1']) for row in report['order']))
                self.assertEqual(report['stage_state'], 'open' if reopened else 'failed')

    def test_a_fresh_ledger_plans_every_send_and_keeps_every_default_send_at_its_frozen_maximum(self):
        root = scratch(self)
        out = self.plan(root, self.amendment())
        report = out['report']
        self.assertIsNone(report['remainder'])
        self.assertEqual(report['sends'], 21)
        for row in report['order']:
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == row['case'])
            frozen = Decimal(case['cost_bound_usd'][row['path']]['provider_cost_max'])
            if row['path'] == 'default':
                self.assertEqual((Decimal(row['maximum_cost']), row['amended'], row['pricing_version']),
                                 (frozen, False, self.declaration.pricing_version('ordinary_notes')))
            else:
                self.assertEqual((row['amended'], row['pricing_version']), (True, RELATIONS_V2))
                self.assertNotEqual(Decimal(row['maximum_cost']), frozen)
        self.assertEqual(Decimal(report['order'][0]['maximum_cost']), Decimal('0.116794'))

    def test_every_other_send_keeps_its_frozen_maximum_under_an_amendment(self):
        out = self.plan(scratch(self), self.amendment(), drift_default=True)
        self.assertIn('notes:N01:default: the maximum', out['refused'])
        self.assertIn('is not the frozen 0.116794', out['refused'])

    def test_without_the_amendment_the_relations_sends_refuse_at_the_declared_version(self):
        out = self.plan(live_shape(self, self.declaration))
        self.assertEqual(out['at'], 'plan')
        self.assertIn('notes:N03:field_relations: the application prices', out['refused'])
        self.assertIn('not the declared ordinary_notes_field_relations', out['refused'])

    def test_a_changed_rate_refuses(self):
        out = self.plan(live_shape(self, self.declaration), self.amendment(), settings={'QUILLMD_AI_INPUT_RATE': '3'})
        self.assertIn('not the amended ordinary_notes_field_relations', out['refused'])

    def test_a_base_other_than_the_pinned_one_refuses(self):
        other = 'configured-v1:' + '1' * 64
        out = self.plan(live_shape(self, self.declaration), self.amendment(
            previous_pricing_version=other,
            amended_pricing_version=pc.contract_pricing_version(other, 'ordinary-field-relations-v2')))
        self.assertEqual(out['at'], 'declaration')
        self.assertIn('the base price is not the pinned one', out['refused'])

    def test_a_contract_the_engine_does_not_run_refuses(self):
        out = self.plan(live_shape(self, self.declaration), self.amendment(
            ordinary_field_contract='ordinary-field-relations-v3',
            amended_pricing_version=pc.contract_pricing_version(RELATIONS_BASE, 'ordinary-field-relations-v3')))
        self.assertIn('this engine runs ordinary-field-relations-v2', out['refused'])

    def test_a_maximum_or_the_sum_that_does_not_fit_the_limit_left_refuses(self):
        # 15 completed sends at 2/10 per million: 327,700 input tokens each expose $9.8487 (one bound, ~$0.257, does not
        # fit the $0.1513 left); 306,000 expose $9.1977 (each bound fits the $0.8023 left, the six together do not)
        for tokens, fragment in ((327700, 'does not fit'), (306000, 'together')):
            with self.subTest(fragment=fragment):
                root = live_shape(self, self.declaration, exposure_tokens=tokens)
                campaign = pc.Campaign(self.declaration, root)
                left = campaign.limits().stage('ordinary_notes').limit - campaign.totals('ordinary_notes')['exposure']
                self.assertGreater(left, Decimal(0))
                out = self.plan(root, self.amendment(f'fit-{tokens}.md'))
                self.assertIn(fragment, out.get('refused', ''), (left, out))

    def test_a_failure_that_would_resend_a_made_send_refuses(self):
        root = live_shape(self, self.declaration, not_sent=UNSENT + ['notes:N02:field_relations'],
                          extra_attempted=['notes:N02:field_relations'])
        out = self.plan(root, self.amendment())
        self.assertIn('already has an attempt; a send is never made twice', out['refused'])

    def test_the_driver_carries_the_measured_versions(self):
        self.assertEqual(pc.contract_pricing_version(RELATIONS_BASE, 'ordinary-field-relations-v1'), RELATIONS_V1)
        self.assertEqual(self.declaration.pricing_version('ordinary_notes_field_relations'), RELATIONS_V1)

    def test_the_guard_is_on(self):
        network_guard.positive_control(self)


if __name__ == '__main__':
    unittest.main()
