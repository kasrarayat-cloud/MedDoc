"""The model_check stage end to end on the synthetic QA database, with a FAKE provider (ops/sonnet5_qa.py).

Run it with Django's test runner against the QA server (the test database is test_quillmd_qa_*):

    QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731 QUILLMD_DB_NAME=quillmd_qa_sonnet5 … \
        python -B manage.py test ops.tests.test_sonnet5_qa

Anywhere else (no Django settings, or any other database) every test here is SKIPPED, visibly, with the reason.

The provider is the real Anthropic SDK around an in-process httpx.MockTransport answering with a realistic Sonnet 5
Messages response; `network_guard` refuses every other socket. What each test proves, and how it would fail:
  · the happy path writes stage_passed only after the real views, the real worker, the review, finalization, a verified
    export and a clean billing audit — and every declared piece of evidence exists, the attempt was durable BEFORE the
    one send, and no retained file carries the key;
  · each stop condition (wrong served model, max_tokens, output above 70%, metered `us`, reconciliation, a wrong
    destination) writes stage_failed, never stage_passed, and admits nothing afterwards;
  · a precondition that does not hold (pricing, database, credential) refuses before any send;
  · no code path opens a `.env` file.
"""
import dataclasses
import io
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc
from . import network_guard

REPOSITORY = Path(__file__).resolve().parents[3]
REAL_DECLARATION = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
SYNTHETIC_KEY = 'sk-ant-api03-SYNTHETIC-OFFLINE-QA-KEY-111111111111111111111111111111111111-BBBBBBBB'


def eligibility():
    """Only under Django's test runner, configured for the synthetic QA server."""
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        return False, 'needs Django settings: run with `manage.py test ops.tests.test_sonnet5_qa` against the QA database'
    try:
        from django.apps import apps
        from django.conf import settings
        database = settings.DATABASES['default']
    except Exception as error:                                       # pragma: no cover - environment dependent
        return False, f'Django is not configured ({type(error).__name__})'
    if not apps.ready:
        return False, 'Django apps are not loaded: run with `manage.py test`'
    if not str(database['NAME']).startswith(('quillmd_qa_', 'test_quillmd_qa_')):
        return False, 'the configured database is not the synthetic QA database (quillmd_qa_*)'
    if (str(database['HOST']), str(database['PORT'])) != ('127.0.0.1', '55731'):
        return False, 'the configured database is not the QA server on 127.0.0.1:55731'
    return True, ''


ELIGIBLE, WHY = eligibility()


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


if not ELIGIBLE:
    class ModelCheckNotRunHere(unittest.TestCase):
        @unittest.skip(WHY)
        def test_model_check_needs_the_qa_database(self):
            pass                                                     # pragma: no cover

else:
    import anthropic
    import httpx
    from django.db import connection
    from django.test import TestCase, override_settings

    from ops import sonnet5_qa as sq
    from .test_provider_campaign import NoEnvOpened

    SONNET_5 = dict(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5', AI_INPUT_RATE='2',
                    AI_OUTPUT_RATE='10', AI_CACHED_RATE='0.20', AI_THINKING='disabled', AI_EFFORT='medium',
                    AI_INFERENCE_GEO='', ADMIN_SITE=False, QUILLMD_DATA_MODE='synthetic', SYNTHETIC_ONLY=True,
                    WM_NARRATIVE=False, V3_FIELD_RELATIONS=False, V3_GENERATION_BATCHES=False, V3_HISTORY_CONTEXT=False,
                    QUILLMD_WORD_ENGINE='legacy', STORAGES=sq.STATIC_STORAGES)
    SELECTED = {'fields': [{'key': f'cell_{index}', 'quotes': [sq.EXPECTED[label]], 'conflict': False}
                           for index, label in enumerate(sq.FORM_LABELS)]}
    REAL_CLIENT = anthropic.Anthropic

    def sonnet5_message(selection=None, *, model='claude-sonnet-5', stop_reason='end_turn', input_tokens=1386,
                        output_tokens=97, geo='global', text=None):
        """A Sonnet 5 Messages API response, shaped as the API returns it."""
        return {'id': 'msg_01SyntheticModelCheck000000001', 'type': 'message', 'role': 'assistant', 'model': model,
                'content': [{'type': 'text', 'text': text if text is not None else json.dumps(selection or SELECTED)}],
                'stop_reason': stop_reason, 'stop_sequence': None, 'stop_details': None,
                'usage': {'input_tokens': input_tokens, 'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0,
                          'cache_creation': {'ephemeral_5m_input_tokens': 0, 'ephemeral_1h_input_tokens': 0},
                          'output_tokens': output_tokens, 'service_tier': 'standard', 'inference_geo': geo,
                          'server_tool_use': None}}

    class ModelCheckTests(TestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            name = connection.settings_dict['NAME']
            if not str(name).startswith('test_quillmd_qa_'):
                raise AssertionError(f'refusing to run outside the QA test database (connected to {name!r})')
            cls.declared = pc.declared(REAL_DECLARATION, repository=REPOSITORY, out=io.StringIO())

        def setUp(self):
            self.root = Path(tempfile.mkdtemp(prefix='sonnet5-qa-test-'))
            self.addCleanup(shutil.rmtree, self.root, True)
            credential = pc.private_directory(self.root / 'credential') / 'anthropic-api-key'
            credential.write_text(SYNTHETIC_KEY + '\n')
            os.chmod(credential, 0o600)
            self.credential = credential
            self.declaration = dataclasses.replace(self.declared, credential_file=str(credential))
            self.campaign = pc.Campaign(self.declaration, self.root)
            self.addCleanup(self.campaign.ledger.release)
            state = pc.private_directory(self.root / 'qa-state')
            config_dir = pc.private_directory(self.root / 'tmp' / 'anthropic-config')
            settings = override_settings(STATE_DIR=state, MEDIA_ROOT=state / 'files', **SONNET_5)
            settings.enable()
            self.addCleanup(settings.disable)
            environment = patch.dict(os.environ, {**sq.PRICE_SETTINGS, 'ANTHROPIC_API_KEY': SYNTHETIC_KEY,
                                                  'ANTHROPIC_CONFIG_DIR': str(config_dir)})
            environment.start()
            self.addCleanup(environment.stop)
            for name in [name for name in os.environ if pc.forbidden_name(name)]:
                del os.environ[name]                        # (restored by patch.dict when the test ends)
            pc.install_request_capture()
            self.addCleanup(pc.uninstall_request_capture)
            self.addCleanup(pc.CURRENT_ATTEMPT.clear)
            self.reply = lambda request: httpx.Response(200, headers={'request-id': 'req_011SyntheticModelCheck'},
                                                        json=sonnet5_message())
            self.sent = []
            provider = patch('anthropic.Anthropic', side_effect=self.provider_client)
            provider.start()
            self.addCleanup(provider.stop)

        # ── the fake provider ────────────────────────────────────────────────────────────────────────────────────
        def provider_client(self, **kwargs):
            # (not `client`: Django's TestCase sets `self.client` to its own test Client)
            return REAL_CLIENT(http_client=httpx.Client(transport=httpx.MockTransport(self.handler)), **kwargs)

        def handler(self, request):
            number = pc.CURRENT_ATTEMPT.get('number')
            ledger = self.campaign.ledger.dir
            self.sent.append({'attempt': number, 'key_sent': request.headers.get('x-api-key') == SYNTHETIC_KEY,
                              'attempt_durable': bool(number) and (ledger / f'{number:03d}-attempt.json').exists(),
                              'no_outcome_yet': bool(number) and not (ledger / f'{number:03d}-outcome.json').exists(),
                              'captured_first': bool(number) and (Path(pc.CURRENT_ATTEMPT['evidence_dir']) / 'request.json').exists(),
                              'body': json.loads(request.content)})
            return self.reply(request)

        def answer(self, **kwargs):
            self.reply = lambda request: httpx.Response(200, headers={'request-id': 'req_011SyntheticModelCheck'},
                                                        json=sonnet5_message(**kwargs))

        def run_check(self, **kwargs):
            return sq.run_model_check(self.campaign, secret=SYNTHETIC_KEY, provenance={'runner_commit': 'offline-test'},
                                      database_prefix=kwargs.pop('database_prefix', 'test_quillmd_qa_'), **kwargs)

        def evidence(self, number=1):
            return self.root / 'evidence' / f'{number:03d}'

        # ── the happy path ───────────────────────────────────────────────────────────────────────────────────────
        def test_the_model_check_passes_end_to_end_with_all_evidence(self):
            from core.models import Encounter, Job, Usage
            from core.management.commands.audit_billing import audit_report
            result = self.run_check()
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            ledger = self.campaign.ledger
            (attempt, outcome), = ledger.rows()
            self.assertIsNotNone(ledger.stage_record('model_check', 'passed'))
            self.assertIsNone(ledger.stage_record('model_check', 'failed'))
            # Exactly one send, made only after the attempt was durable and the request captured.
            self.assertEqual(len(self.sent), 1)
            self.assertTrue(all(self.sent[0][k] for k in ('key_sent', 'attempt_durable', 'no_outcome_yet', 'captured_first')))
            body = self.sent[0]['body']
            self.assertEqual((body['model'], body['max_tokens'], body['thinking'], body['output_config']['effort']),
                             ('claude-sonnet-5', 8000, {'type': 'disabled'}, 'medium'))
            self.assertNotIn('inference_geo', body)
            # The ledger: the declared maximum, then the provider-reported usage at the declared rates.
            self.assertEqual(Decimal(attempt['maximum_cost']), Decimal('0.104896'))
            self.assertEqual(attempt['pricing_version'], self.declaration.pricing_version('model_check'))
            cost = (Decimal(1386) * 2 + Decimal(97) * 10) / 1000000
            self.assertEqual((outcome['class'], outcome['served_model'], outcome['stop_reason']),
                             ('completed', 'claude-sonnet-5', 'end_turn'))
            self.assertEqual(Decimal(outcome['exposure']), cost)
            self.assertEqual(Decimal(outcome['settlement']['usage_actual_cost']), cost)
            self.assertEqual(Decimal(outcome['settlement']['charged_cost']), cost * Decimal('1.5'))
            self.assertEqual(self.campaign.totals()['exposure'], cost)
            # Every declared piece of evidence, and none of it carries the key.
            evidence = self.evidence()
            for name in ('case/sonnet5-model-check.docx', 'case/notes.txt', 'case/case.json', 'request.json',
                         'provider-result.json', 'records-after-run.json', 'answers-adopted.json', 'answers-reviewed.json',
                         'export.docx', 'export.json', 'audit-billing.json', 'manifest.json'):
                self.assertTrue((evidence / name).is_file(), name)
            self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY, exclude=(self.credential,)), [])
            self.assertNotIn(SYNTHETIC_KEY.encode(), (evidence / 'request.json').read_bytes())
            self.assertEqual(json.loads((evidence / 'provider-result.json').read_text())['provider_output']['model'],
                             'claude-sonnet-5')
            self.assertEqual(pc.file_sha256(evidence / 'case' / 'sonnet5-model-check.docx'), sq.FORM_SHA256)
            records = json.loads((evidence / 'records-after-run.json').read_text())
            self.assertEqual({k: len(v) for k, v in records.items() if k in ('job', 'usage', 'provider_receipts', 'reservations',
                                                                           'wallets', 'ledger_entries')},
                             {'job': 1, 'usage': 1, 'provider_receipts': 1, 'reservations': 1, 'wallets': 1, 'ledger_entries': 1})
            adopted = json.loads((evidence / 'answers-adopted.json').read_text())['answers']
            reviewed = json.loads((evidence / 'answers-reviewed.json').read_text())['answers']
            self.assertEqual({a['status'] for a in adopted.values()}, {'supported'})
            self.assertFalse(any(a['reviewed'] for a in adopted.values()))        # (the validator's decision, kept apart)
            self.assertTrue(all(a['reviewed'] for a in reviewed.values()))        # (the clinician review, kept apart)
            export = json.loads((evidence / 'export.json').read_text())
            self.assertEqual(export['problems'], [])
            self.assertEqual(export['sha256'], pc.file_sha256(evidence / 'export.docx'))
            manifest = json.loads((evidence / 'manifest.json').read_text())
            self.assertEqual(manifest['declaration']['commit_time'], self.declaration.commit_time)
            self.assertEqual(manifest['runner']['commit'], 'offline-test')
            self.assertEqual(set(manifest['runner']['files']), set(sq.ENGINE_FILES))
            self.assertEqual(manifest['settings']['pricing_version'], self.declaration.pricing_version('model_check'))
            self.assertEqual(manifest['evidence']['request.json'], pc.file_sha256(evidence / 'request.json'))
            # The product's own records agree.
            encounter = Encounter.objects.get(pk=attempt['encounter'])
            self.assertEqual(encounter.status, 'finalized')
            self.assertEqual(Job.objects.get(pk=attempt['job']).state, 'succeeded')
            self.assertEqual(Usage.objects.get(job_id=attempt['job']).actual_cost, cost)
            self.assertTrue(audit_report()['all_checks_pass'])
            # The access record lives under the campaign runtime directory only.
            self.assertTrue((self.root / 'access' / 'qa-doctor.json').is_file())
            # A passed model check is never re-run in place.
            with self.assertRaises(pc.Refused):
                self.campaign.admit('model_check', '0.104896')

        def test_no_code_path_opens_an_env_file(self):
            with NoEnvOpened() as guard, patch('dotenv.load_dotenv', side_effect=AssertionError('load_dotenv called')):
                result = self.run_check()
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            self.assertEqual(guard.attempts, [])

        def test_the_world_is_seeded_once(self):
            from core.models import LedgerEntry, Organization, Template, User, Wallet
            first = sq.seed_world(self.root)
            second = sq.seed_world(self.root)
            self.assertEqual((first.user.pk, first.template.pk), (second.user.pk, second.template.pk))
            self.assertEqual((User.objects.count(), Organization.objects.count(), Template.objects.count()), (1, 1, 1))
            self.assertEqual(LedgerEntry.objects.filter(kind='welcome').count(), 1)
            self.assertEqual(Wallet.objects.get(user=first.user, kind='promo').balance, Decimal('10'))
            self.assertEqual(first.template.sha256, sq.FORM_SHA256)

        # ── the stop conditions ──────────────────────────────────────────────────────────────────────────────────
        def stopped(self, fragment):
            result = self.run_check()
            self.assertEqual(result['verdict'], 'FAIL')
            ledger = self.campaign.ledger
            self.assertIsNone(ledger.stage_record('model_check', 'passed'))
            failed = ledger.stage_record('model_check', 'failed')
            self.assertIsNotNone(failed)
            self.assertTrue(any(fragment in reason for reason in failed['reasons']), failed['reasons'])
            self.assertEqual(len(self.sent), 1)
            (_, outcome), = ledger.rows()
            for stage in ('model_check', 'mapping', 'ordinary_notes'):
                with self.assertRaises(pc.Refused):
                    self.campaign.admit(stage, '0.104896')
            self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY, exclude=(self.credential,)), [])
            return outcome, failed

        def test_a_wrong_served_model_stops_the_campaign(self):
            self.answer(model='claude-sonnet-4-6')
            outcome, _ = self.stopped("the provider served 'claude-sonnet-4-6'")
            self.assertEqual(outcome['served_model'], 'claude-sonnet-4-6')

        def test_max_tokens_stops_the_campaign(self):
            self.answer(stop_reason='max_tokens', output_tokens=8000, text='{"fields": [{"key": "cell_0", "quo')
            outcome, _ = self.stopped("stopped with 'max_tokens'")
            self.assertEqual(outcome['class'], 'completed')            # (settled: its usage is known, and absorbed)

        def test_output_above_70_percent_stops_the_campaign(self):
            self.answer(output_tokens=5600)
            self.stopped('not below 70% of the 8000-token output limit')

        def test_metered_us_geography_stops_the_campaign(self):
            self.answer(geo='us')
            outcome, _ = self.stopped('metered inference_geo us')
            cost = (Decimal(1386) * 2 + Decimal(97) * 10) / 1000000 * Decimal('1.1')
            self.assertEqual(Decimal(outcome['exposure']), cost)

        def test_a_reconciliation_stops_the_campaign_and_counts_the_maximum(self):
            def refuse(request):
                raise httpx.ConnectError('synthetic connection reset after the request was written', request=request)
            self.reply = refuse
            outcome, _ = self.stopped('ended reconciliation')
            self.assertEqual(outcome['class'], 'reconciliation')
            self.assertTrue(outcome['request_captured'])
            self.assertEqual(Decimal(outcome['exposure']), Decimal('0.104896') * Decimal('1.1'))

        def test_an_answer_in_the_wrong_question_stops_the_campaign(self):
            swapped = {'fields': [{'key': 'cell_0', 'quotes': [sq.EXPECTED['History']], 'conflict': False},
                                  {'key': 'cell_1', 'quotes': [sq.EXPECTED['Plan']], 'conflict': False},
                                  {'key': 'cell_2', 'quotes': [sq.EXPECTED['Findings']], 'conflict': False}]}
            self.answer(selection=swapped)
            result = self.run_check()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.campaign.ledger.stage_record('model_check', 'failed')
            self.assertIsNotNone(failed)
            self.assertIsNone(self.campaign.ledger.stage_record('model_check', 'passed'))
            self.assertTrue(any('not a succeeded generation' in reason for reason in failed['reasons']), failed['reasons'])

        def test_the_validator_decision_is_judged_against_the_fixed_case(self):
            fields = [{'key': f'cell_{i}', 'label': label} for i, label in enumerate(sq.FORM_LABELS)]
            notes = sq.NOTES
            def supported(label, text=None):
                value = text if text is not None else sq.EXPECTED[label]
                start = notes.index(value)
                return {'text': value, 'status': 'supported', 'evidence': [{'quote': value, 'start': start, 'end': start + len(value)}]}
            good = {f'cell_{i}': supported(label) for i, label in enumerate(sq.FORM_LABELS)}
            self.assertEqual(sq.judge_answers(good, fields, notes), [])
            wrong = {**good, 'cell_1': supported('Findings', sq.EXPECTED['Plan'])}
            self.assertTrue(any('wrong destination' in r for r in sq.judge_answers(wrong, fields, notes)))
            unsupported = {**good, 'cell_2': {**good['cell_2'], 'evidence': []}}
            self.assertTrue(any('no source support' in r for r in sq.judge_answers(unsupported, fields, notes)))
            held = {**good, 'cell_0': {'text': '', 'status': 'conflict', 'evidence': []}}
            self.assertTrue(any('not a supported answer' in r for r in sq.judge_answers(held, fields, notes)))
            moved = {**good, 'cell_1': {**good['cell_1'], 'evidence': [{'quote': sq.EXPECTED['Findings'], 'start': 0, 'end': 24}]}}
            self.assertTrue(any('does not match the notes' in r for r in sq.judge_answers(moved, fields, notes)))

        def test_a_runner_failure_after_the_attempt_is_a_failed_stage_never_a_refusal(self):
            # (before the outcome is written: the attempt is recorded with an unknown outcome at its maximum)
            with patch.object(sq, 'raw_result', side_effect=RuntimeError('synthetic runner fault')):
                result = self.run_check()
            self.assertEqual(result['verdict'], 'FAIL')
            self.assertIn('RuntimeError', result['reasons'][0])
            (_, outcome), = self.campaign.ledger.rows()
            self.assertEqual(outcome['class'], 'uncertain')
            self.assertEqual(Decimal(pc.exposure(*self.campaign.ledger.rows()[0])), Decimal('0.104896') * Decimal('1.1'))
            self.assertIsNotNone(self.campaign.ledger.stage_record('model_check', 'failed'))
            self.assertEqual(len(self.sent), 1)

        def test_a_runner_failure_after_the_outcome_keeps_the_outcome_and_fails_the_stage(self):
            with patch.object(sq, 'judge_answers', side_effect=RuntimeError('synthetic runner fault')):
                result = self.run_check()
            self.assertEqual(result['verdict'], 'FAIL')
            (_, outcome), = self.campaign.ledger.rows()
            self.assertEqual(outcome['class'], 'completed')                  # (the recorded outcome is not overwritten)
            self.assertIsNone(self.campaign.ledger.stage_record('model_check', 'passed'))
            self.assertIsNotNone(self.campaign.ledger.stage_record('model_check', 'failed'))

        # ── refusals before any send ─────────────────────────────────────────────────────────────────────────────
        def refused_unsent(self, fragment, **kwargs):
            with self.assertRaises(pc.Refused) as caught:
                self.run_check(**kwargs)
            self.assertIn(fragment, str(caught.exception))
            self.assertEqual(self.sent, [])
            self.assertEqual([a for a, _ in self.campaign.ledger.rows()], [])

        def test_a_pricing_version_other_than_the_declared_one_refuses_before_any_send(self):
            with override_settings(AI_EFFORT='high'):
                with self.assertRaises(pc.Refused):
                    self.run_check()
            self.assertEqual(self.sent, [])
            with patch.dict(os.environ, {'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.0044'}):
                self.refused_unsent('not the declared model_check version')

        def test_another_database_refuses_before_any_send(self):
            self.refused_unsent('synthetic QA database', database_prefix='quillmd_qa_')

        def test_a_missing_or_foreign_credential_refuses_before_any_send(self):
            os.unlink(self.credential)
            self.refused_unsent('does not exist')
            self.credential.write_text('sk-ant-api03-ANOTHER-KEY-0000000000000000\n')
            os.chmod(self.credential, 0o600)
            self.refused_unsent('does not carry the declared credential')

        def test_a_key_already_in_retained_files_refuses_before_any_send(self):
            stray = pc.private_directory(self.root / 'evidence') / 'old-notes.txt'
            stray.write_text('pasted by mistake: ' + SYNTHETIC_KEY)
            self.refused_unsent('already present in retained files')

        def test_a_checkout_with_an_env_file_refuses_before_any_send(self):
            with patch.object(sq, 'env_file_present', return_value=True):
                self.refused_unsent('rebuild/.env')

        def test_an_interrupted_attempt_fails_its_stage_and_is_never_resent(self):
            self.campaign.ledger.acquire()
            self.campaign.ledger.write_attempt({'number': 1, 'campaign': self.declaration.campaign,
                                                'authority_id': self.declaration.authority_id, 'stage': 'model_check',
                                                'maximum_cost': '0.104896', 'rates': self.declaration.rates.as_dict()})
            with self.assertRaises(pc.Refused) as caught:
                self.run_check()
            self.assertIn('failed', str(caught.exception))
            self.assertEqual(self.sent, [])
            (_, outcome), = self.campaign.ledger.rows()
            self.assertEqual(outcome['class'], 'interrupted_unknown')
            self.assertIsNotNone(self.campaign.ledger.stage_record('model_check', 'failed'))
            self.assertEqual(self.campaign.totals()['exposure'], Decimal('0.104896') * Decimal('1.1'))

        def test_the_guard_is_on(self):
            network_guard.positive_control(self)
