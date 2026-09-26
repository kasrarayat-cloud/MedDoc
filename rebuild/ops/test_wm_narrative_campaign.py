"""The campaign runner's money and key rules, without a database, a provider or Django (ops/wm_narrative_campaign.py).

The end-to-end offline validation (every stop condition through the real product path against a loopback mock) is
ops/wm_narrative_campaign_offline.py; these pin the arithmetic and the refusals it rests on."""
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    from . import wm_narrative_campaign as c
except ImportError:
    import wm_narrative_campaign as c


def attempt(number, case='C14', stage=1, kind='initial', maximum='0.2999'):
    return {'number': number, 'case': case, 'stage': stage, 'kind': kind, 'maximum_cost': maximum}


class Arithmetic(unittest.TestCase):
    def test_an_attempt_is_bounded_by_its_maximum_times_the_inference_margin_rounded_up(self):
        self.assertEqual(c.attempt_bound('0.2999'), Decimal('0.32989'))
        self.assertEqual(c.attempt_bound('0.1234567'), Decimal('0.135803'))      # 0.13580237 rounded UP

    def test_only_a_product_proven_unsent_attempt_costs_nothing(self):
        a = attempt(1)
        self.assertEqual(c.exposure(a, None), c.attempt_bound('0.2999'))                       # no outcome: unknown
        self.assertEqual(c.exposure(a, {'class': 'interrupted_unknown'}), c.attempt_bound('0.2999'))
        self.assertEqual(c.exposure(a, {'class': 'transport_failure', 'provider_actual_cost': None}),
                         c.attempt_bound('0.2999'))                                         # a timeout may be billed
        self.assertEqual(c.exposure(a, {'class': 'not_sent'}), Decimal('0'))
        self.assertEqual(c.exposure(a, {'class': 'adopted', 'provider_actual_cost': '0.1'}), Decimal('0.11'))
        # Absorbed output: the customer's charge is reversed; the provider's cost still counts.
        self.assertEqual(c.exposure(a, {'class': 'output_unusable', 'provider_actual_cost': '0.1',
                                        'wallet_charged': '0'}), Decimal('0.11'))

    def test_the_stage_limits_cover_every_allowed_attempt_at_the_largest_case(self):
        for stage in c.STAGES:
            worst = c.stage_worst_case({'X': Decimal('0.3066'), 'Y': Decimal('0.2975')}, stage)
            self.assertTrue(worst['fits'], (stage, worst))
        self.assertLessEqual(sum(p['provider_limit'] for p in c.STAGES.values()), c.CAMPAIGN_PROVIDER_LIMIT)
        self.assertLessEqual(sum(p['wallet_limit'] for p in c.STAGES.values()), c.CAMPAIGN_WALLET_LIMIT)
        # A case whose maximum would break the stage is refused before anything is sent.
        self.assertFalse(c.stage_worst_case({'X': Decimal('0.40')}, 1)['fits'])

    def test_the_declared_pricing_version_is_the_applications_own_formula_over_its_recorded_fields(self):
        price = {'provider': 'anthropic', 'model': c.EXPECTED_MODEL, 'input_rate': '3', 'output_rate': '15',
                 'cached_rate': '0.30', 'voice_rate_minute': '0.0043', 'voice_rate_second': '', 'discount_rate': '0',
                 'cost_basis': 'configured_usd_rates', 'voice_provider': 'deepgram:nova-3-medical',
                 'voice_cost_quantum': '0.0000000001', 'voice_rounding': 'half_even', 'multiplier': '1.5'}
        digest = hashlib.sha256(json.dumps(price, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual('configured-v1:' + digest, c.EXPECTED_PRICING_VERSION)


class Limits(unittest.TestCase):
    def rows(self, *outcomes, stage=1, kinds=None):
        return [(dict(attempt(i + 1, stage=stage), kind=(kinds or {}).get(i + 1, 'initial')), o)
                for i, o in enumerate(outcomes)]

    def test_the_attempt_ceiling_refuses_the_next_request(self):
        rows = self.rows(*[{'class': 'adopted', 'provider_actual_cost': '0.01', 'wallet_charged': '0.015'}] * 7)
        with self.assertRaisesRegex(c.Refused, 'all 7 attempts'):
            c.next_attempt_allowed(rows, 1, Decimal('0.2999'))

    def test_unknown_outcomes_consume_the_provider_limit_at_their_maximum(self):
        unknown = {'class': 'unknown', 'provider_actual_cost': None}
        rows = self.rows(*[unknown] * 6)
        # 6 x 0.32989 = 1.97934; a 7th fits 2.40; a larger case would not.
        self.assertEqual(c.next_attempt_allowed(rows, 1, Decimal('0.2999')), Decimal('0.32989'))
        with self.assertRaisesRegex(c.Refused, 'provider limit'):
            c.next_attempt_allowed(rows, 1, Decimal('0.39'))

    def test_the_wallet_limit_is_checked_separately_from_the_provider_limit(self):
        # Cheap provider cost, but charges near the wallet limit: the WALLET refuses.
        rows = self.rows({'class': 'adopted', 'provider_actual_cost': '0.01', 'wallet_charged': '3.20'})
        with self.assertRaisesRegex(c.Refused, 'wallet limit'):
            c.next_attempt_allowed(rows, 1, Decimal('0.2999'))

    def test_the_campaign_limit_counts_every_stage(self):
        stage_one = [(attempt(i + 1, stage=1), {'class': 'unknown'}) for i in range(7)]
        stage_two = [(attempt(i + 8, stage=2, maximum='0.33'), {'class': 'unknown'}) for i in range(27)]
        with self.assertRaisesRegex(c.Refused, 'Campaign provider limit|Stage 2 provider limit'):
            c.next_attempt_allowed(stage_one + stage_two, 2, Decimal('0.33'))

    def test_outcome_classes_come_from_the_products_own_record(self):
        self.assertEqual(c.classify('succeeded', '', True, ''), 'adopted')
        self.assertEqual(c.classify('failed', 'NoProviderRequest', False, 'not_processed'), 'not_sent')
        self.assertEqual(c.classify('failed', 'ValidationError', True, 'platform_failure'), 'output_unusable')
        self.assertEqual(c.classify('reconciliation', 'ValidationError', True, 'uncertain'), 'settlement_reconciliation')
        for name in ('APITimeoutError', 'APIConnectionError', 'RateLimitError', 'InternalServerError', 'OverloadedError'):
            self.assertEqual(c.classify('reconciliation', name, False, 'uncertain'), 'transport_failure')
        for name in ('AuthenticationError', 'NotFoundError', 'BadRequestError'):
            self.assertEqual(c.classify('reconciliation', name, False, 'uncertain'), 'configuration_failure')
        self.assertEqual(c.classify('reconciliation', 'KeyError', False, 'uncertain'), 'unknown')
        # A receipt makes it settled whatever the exception says: the provider answered.
        self.assertEqual(c.classify('failed', 'APITimeoutError', True, 'platform_failure'), 'output_unusable')


class Ledger(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: [p.unlink() for p in self.dir.glob('*')] and None)

    def test_a_record_is_written_once(self):
        c.write_new(self.dir / '001-C14-attempt.json', attempt(1))
        with self.assertRaises(FileExistsError):
            c.write_new(self.dir / '001-C14-attempt.json', attempt(1))
        self.assertEqual(os.stat(self.dir / '001-C14-attempt.json').st_mode & 0o777, 0o600)

    def test_an_attempt_without_an_outcome_is_read_as_unknown_and_a_gap_is_refused(self):
        c.write_new(self.dir / '001-C14-attempt.json', attempt(1))
        c.write_new(self.dir / '001-C14-outcome.json', {'class': 'adopted', 'provider_actual_cost': '0.1'})
        c.write_new(self.dir / '002-C18-attempt.json', attempt(2, 'C18'))
        rows = c.load_ledger(self.dir)
        self.assertEqual([o and o['class'] for _, o in rows], ['adopted', None])
        self.assertEqual(c.totals(rows)['unknown'], 1)
        c.write_new(self.dir / '004-C19-attempt.json', attempt(4, 'C19'))
        with self.assertRaisesRegex(c.Refused, 'gapless'):
            c.load_ledger(self.dir)


class Credentials(unittest.TestCase):
    def private(self, text, mode=0o600):
        handle = tempfile.NamedTemporaryFile('w', delete=False)
        handle.write(text); handle.close()
        os.chmod(handle.name, mode)
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_only_the_allowlisted_provider_fields_are_taken(self):
        path = self.private('ANTHROPIC_API_KEY=synthetic-value-for-test\nQUILLMD_AI_PROVIDER=anthropic\n'
                            'QUILLMD_AI_MODEL=claude-sonnet-4-6\nQUILLMD_AI_INPUT_RATE=3\nQUILLMD_AI_OUTPUT_RATE=15\n'
                            'QUILLMD_AI_CACHED_RATE=0.30\nQUILLMD_DB_PASSWORD=never-taken\nSTRIPE_SECRET_KEY=never-taken\n'
                            'QUILLMD_DEEPGRAM_RATE_PER_MINUTE=0.0043\n')
        values = c.provider_fields_from(path)
        self.assertEqual(set(values), set(c.PROVIDER_FIELDS))
        self.assertNotIn('never-taken', json.dumps(values))

    def test_a_readable_by_others_or_incomplete_configuration_is_refused(self):
        with self.assertRaisesRegex(c.Refused, 'private file'):
            c.provider_fields_from(self.private('ANTHROPIC_API_KEY=x\n', mode=0o644))
        with self.assertRaisesRegex(c.Refused, 'lacks'):
            c.provider_fields_from(self.private('ANTHROPIC_API_KEY=x\n'))

    def test_offline_mode_accepts_only_the_loopback_mock_and_the_offline_marker(self):
        good = {'ANTHROPIC_API_KEY': c.OFFLINE_KEY, 'ANTHROPIC_BASE_URL': 'http://127.0.0.1:55999'}
        for bad in ({**good, 'ANTHROPIC_BASE_URL': 'https://api.anthropic.com'},
                    {**good, 'ANTHROPIC_BASE_URL': 'http://127.0.0.1.example.com:1'},
                    {**good, 'ANTHROPIC_API_KEY': 'sk-ant-anything'}):
            with self.assertRaises(c.Refused):
                c.offline_provider(self.private(json.dumps(bad)))
        self.assertEqual(c.offline_provider(self.private(json.dumps(good)))['ANTHROPIC_API_KEY'], c.OFFLINE_KEY)

    def test_live_mode_is_refused_before_the_protected_configuration_is_opened(self):
        campaign = tempfile.mkdtemp()
        os.chmod(campaign, 0o700)
        args = SimpleNamespace(stage=1, mode='live', campaign_dir=campaign, declaration=None, provider=None,
                               db='unused', engine='unused', offline_timeout=5, offline_retry_wait=1,
                               expectation_override=None)
        with patch.object(c, 'candidate_identity', return_value={'commit': 'x' * 40, 'runner_sha256': 'y'}), \
                patch.object(c, 'provider_fields_from', side_effect=AssertionError('opened')) as opened:
            with self.assertRaisesRegex(c.Refused, 'declaration'):
                c.outer(args)
        opened.assert_not_called()

    def test_the_process_that_makes_requests_sees_only_the_scrubbed_environment(self):
        directory = Path(tempfile.mkdtemp())
        (directory / 'runtime-manifest.json').write_text('{}')
        db = directory / 'db.json'
        db.write_text(json.dumps({'name': 'quillmd_wmn_campaign_t', 'user': 'u', 'password': 'p',
                                  'host': '127.0.0.1', 'port': 5}))
        args = SimpleNamespace(db=str(db), engine=str(directory), mode='offline')
        with patch.dict(os.environ, {'STRIPE_SECRET_KEY': 'inherited', 'QUILLMD_DB_NAME': 'quillmd_fresh'}):
            env = c.scrubbed_environment(args, {'ANTHROPIC_API_KEY': c.OFFLINE_KEY,
                                                'ANTHROPIC_BASE_URL': 'http://127.0.0.1:1', 'QUILLMD_AI_MODEL': 'm'},
                                         directory)
        self.assertNotIn('STRIPE_SECRET_KEY', env)
        self.assertEqual(env['QUILLMD_DB_NAME'], 'quillmd_wmn_campaign_t')
        self.assertEqual((env['QUILLMD_AI_MODE'], env['QUILLMD_WM_NARRATIVE']), ('live', '1'))
        db.write_text(json.dumps({'name': 'quillmd_fresh', 'user': 'u', 'password': 'p', 'host': '127.0.0.1', 'port': 5}))
        with self.assertRaisesRegex(c.Refused, 'quillmd_wmn_campaign'):
            c.scrubbed_environment(args, {}, directory)

    def declaration(self, authorization):
        import subprocess
        repo = Path(tempfile.mkdtemp())
        subprocess.run(['git', 'init', '-q', str(repo)], check=True)
        plan = c.STAGES[1]
        (repo / 'd.md').write_text(f'campaign: {c.CAMPAIGN}\nstage: 1\nprovider_limit_usd: {plan["provider_limit"]}\n'
                                   f'wallet_limit_usd: {plan["wallet_limit"]}\nmodel: {c.EXPECTED_MODEL}\n'
                                   f'pricing_version: {c.EXPECTED_PRICING_VERSION}\n{authorization}\n')
        subprocess.run(['git', '-C', str(repo), 'add', 'd.md'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@synthetic.invalid',
                        '-c', 'core.hooksPath=/dev/null', 'commit', '-q', '-m', 'd'], check=True)
        return SimpleNamespace(declaration=str(repo / 'd.md'), stage=1)

    def test_live_mode_needs_a_committed_declaration_with_a_real_owner_authorization(self):
        for placeholder in ('authorization: PENDING-OWNER-APPROVAL', 'authorization: owner <quote the approval here>',
                            'authorization: owner TBD after the owner answers', 'authorization: owner 2026-09-26?'):
            with self.assertRaisesRegex(c.Refused, 'no owner authorization'):
                c.declared(self.declaration(placeholder))
        ok = c.declared(self.declaration('authorization: owner 2026-09-26 approved stage 1 at the stated limits'))
        self.assertTrue(ok['authorization'].startswith('owner 2026-09-26'))
        uncommitted = self.declaration('authorization: owner 2026-09-26 approved stage 1 at the stated limits')
        Path(uncommitted.declaration).write_text(Path(uncommitted.declaration).read_text() + 'edited after commit\n')
        with self.assertRaisesRegex(c.Refused, 'committed and unmodified'):
            c.declared(uncommitted)

    def test_key_shaped_text_is_found_in_evidence(self):
        directory = Path(tempfile.mkdtemp())
        (directory / 'a.json').write_text('{"x": "sk-ant-api03-AbCdEfGh123"}')
        (directory / 'b.json').write_text('{"x": "nothing here"}')
        (directory / 'c.json').write_text('{"x": "plain-secret-value"}')
        self.assertEqual(c.leaked(directory, ''), ['a.json'])
        self.assertEqual(sorted(c.leaked(directory, 'plain-secret-value')), ['a.json', 'c.json'])


if __name__ == '__main__':
    unittest.main()
