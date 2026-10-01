"""The standing-authority runner end to end on the synthetic QA database, with a FAKE provider (ops/standing_qa.py).

Run with Django's test runner against the QA server (a distinct test database, test_quillmd_qa_*):

    QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731 QUILLMD_DB_NAME=quillmd_qa_v2_auth_<tag> … \
        python -B manage.py test ops.tests.test_standing_qa_django

Anywhere else every test here is SKIPPED, visibly. The provider is the real Anthropic SDK around an in-process
httpx.MockTransport; `network_guard` refuses every other socket.

⚠️ THE MODEL HERE IS claude-sonnet-5, NOT claude-sonnet-5-5, AND THAT IS STATED SO IT IS NOT READ AS MORE THAN IT IS.
The application has no request profile for claude-sonnet-5-5 until the 5.5 profile (task T2) is integrated, so no
generation can be built for it here. These tests prove the STANDING RUNNER's path — its admission, identities, runs,
duplicate prevention, inputs, reconciliation and decisions through the historical per-send machinery, the real views
and the real worker — on the one Sonnet 5 profile the application has. The test declaration (declaration_use: test) is
the committed TEST declaration with that model, its rates and the application's own pricing versions substituted; a
live declaration must name claude-sonnet-5-5 (standing_qa.require_live).

What each test proves:
  · the preflight, then the model check, then two bounded notes runs pass end to end: every attempt carries the
    standing identities (mode, monetary_ceiling null, run, attempt id, send key), every send is made once, the runs
    close (decided, partial, partial), the stage stays open between runs, and status reports no ceiling;
  · an unsafe verdict on the default path (injected at the field classifier: on this base the application holds every
    frozen adversarial simulation) stops the stage: nothing further is sent, the run closes failed, the next run is
    refused before anything is created, and the failed evidence is kept;
  · the Stop file refuses a run before anything is written; appearing DURING a run it halts the run (the send in
    flight completes, the rest are not made, the run closes halted, exit 4) without failing the stage, and the next run
    resumes once it is lifted.
"""
import dataclasses
import io
import json
import os
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc
from . import network_guard
from .test_sonnet5_qa import ELIGIBLE, WHY

REPOSITORY = Path(__file__).resolve().parents[3]
SYNTHETIC_KEY = 'sk-ant-api03-SYNTHETIC-STANDING-E2E-KEY-333333333333333333333333333333333333-DDDDDDDD'


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


if not ELIGIBLE:
    class StandingNotRunHere(unittest.TestCase):
        @unittest.skip(WHY)
        def test_the_standing_runner_needs_the_qa_database(self):
            pass                                                     # pragma: no cover

else:
    import anthropic
    import httpx
    from django.db import connection
    from django.test import TestCase, override_settings

    from ops import sonnet5_qa as sq
    from ops import standing_qa as st
    from .test_sonnet5_qa import SONNET_5, sonnet5_message
    from .test_sonnet5_stages import STAGE_SETTINGS, message, wire_answer
    from .test_standing_qa import fixture_text, repository, rights_ledger

    REAL_CLIENT = anthropic.Anthropic
    HISTORICAL = (REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
                  ).read_text()
    AMENDMENT = (REPOSITORY / 'docs' / 'foundation' / 'mutations' /
                 '20260929-quillmd-v1-sonnet5-relations-contract-amendment.md').read_text()
    PLAIN = re.search(r'^pricing_version model_check: (\S+)$', HISTORICAL, re.M).group(1)
    RELATIONS = re.search(r'^amended_pricing_version: (\S+)$', AMENDMENT, re.M).group(1)

    def sonnet5_declaration_text():
        """The committed TEST declaration with the one Sonnet 5 profile the application has (see the module note)."""
        text = fixture_text()
        for old, new in (('model: claude-sonnet-5-5', 'model: claude-sonnet-5'),
                         ('rates: input 3 output 15 cached 0.30', 'rates: input 2 output 10 cached 0.20'),
                         ('pricing_version model_check: configured-v1:' + 'a' * 64, 'pricing_version model_check: ' + PLAIN),
                         ('pricing_version mapping: configured-v1:' + 'b' * 64, 'pricing_version mapping: ' + PLAIN),
                         ('pricing_version ordinary_notes: configured-v1:' + 'c' * 64,
                          'pricing_version ordinary_notes: ' + PLAIN),
                         ('pricing_version ordinary_notes_field_relations: configured-v1:' + 'd' * 64,
                          'pricing_version ordinary_notes_field_relations: ' + RELATIONS)):
            assert text.count(old) == 1, old
            text = text.replace(old, new)
        return text

    class StandingEndToEndTests(TestCase):
        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            name = connection.settings_dict['NAME']
            if not str(name).startswith('test_quillmd_qa_'):
                raise AssertionError(f'refusing to run outside the QA test database (connected to {name!r})')
            cls.inputs = sq.stages_module().frozen_inputs()

        def setUp(self):
            root, path = repository(self, sonnet5_declaration_text())
            declared = st.declared_standing(path, repository=root, uses=('test',), out=io.StringIO())
            self.root = Path(tempfile.mkdtemp(prefix='standing-e2e-'))
            self.addCleanup(shutil.rmtree, self.root, True)
            credential = pc.private_directory(self.root / 'credential') / 'anthropic-api-key'
            credential.write_text(SYNTHETIC_KEY + '\n')
            os.chmod(credential, 0o600)
            self.credential = credential
            ledger, digest = rights_ledger(self, ('f' * 64,))
            self.declaration = dataclasses.replace(declared, credential_file=str(credential),
                                                   restricted_inputs_ledger=ledger,
                                                   restricted_inputs_ledger_sha256=digest)
            self.campaign = st.StandingCampaign(self.declaration, self.root / 'campaign')
            self.campaign.ledger.acquire()
            self.addCleanup(self.campaign.ledger.release)
            self.state = pc.private_directory(self.campaign.root / 'qa-state')
            config_dir = pc.private_directory(self.campaign.root / 'tmp' / 'anthropic-config')
            environment = patch.dict(os.environ, {**sq.PRICE_SETTINGS, 'ANTHROPIC_API_KEY': SYNTHETIC_KEY,
                                                  'ANTHROPIC_CONFIG_DIR': str(config_dir)})
            environment.start()
            self.addCleanup(environment.stop)
            for name in [name for name in os.environ if pc.forbidden_name(name)]:
                del os.environ[name]                        # (restored by patch.dict when the test ends)
            self.sent, self.answers = [], {}
            self.preflight()
            pc.install_request_capture()
            self.addCleanup(pc.uninstall_request_capture)
            self.addCleanup(pc.CURRENT_ATTEMPT.clear)
            pc.REQUEST_BOUNDS.update(model=self.declaration.model,
                                     max_tokens=self.declaration.max_output_tokens_per_request)
            self.addCleanup(pc.REQUEST_BOUNDS.clear)
            provider = patch('anthropic.Anthropic', side_effect=self.provider_client)
            provider.start()
            self.addCleanup(provider.stop)

        def preflight(self):
            def models(request):
                return httpx.Response(200, json={'id': self.declaration.model, 'type': 'model',
                                                 'display_name': 'Claude Sonnet 5', 'created_at': '2026-09-01T00:00:00Z'})
            result = st.run_preflight(self.campaign, secret=SYNTHETIC_KEY, transport=httpx.MockTransport(models))
            self.assertTrue(result['matches_declared'])

        # ── the fake provider ────────────────────────────────────────────────────────────────────────────────────
        def provider_client(self, **kwargs):
            return REAL_CLIENT(http_client=httpx.Client(transport=httpx.MockTransport(self.handler)), **kwargs)

        def handler(self, request):
            from core.models import Encounter
            number = pc.CURRENT_ATTEMPT.get('number')
            ledger = self.campaign.ledger.dir
            body = json.loads(request.content)
            attempt = json.loads((ledger / f'{number:03d}-attempt.json').read_text())
            send = attempt.get('send', {})
            self.sent.append({'attempt': number, 'send': send.get('id'), 'max_tokens': body['max_tokens'],
                              'attempt_durable': True, 'captured_first': (Path(pc.CURRENT_ATTEMPT['evidence_dir'])
                                                                          / 'request.json').exists()})
            if attempt['stage'] == 'model_check':
                return httpx.Response(200, headers={'request-id': 'req_011SyntheticStandingMC'}, json=sonnet5_message())
            payload = json.loads(body['messages'][0]['content'])
            encounter = Encounter.objects.get(pk=attempt['encounter'])
            answer = self.answers.get(send.get('id'))
            if answer is None:
                case = next(c for c in self.inputs['cases']['cases'] if c['id'] == send['case'])
                selection = sq.stages_module().steps.reference_selection(case, send['path'])
                answer = wire_answer(encounter.notes, encounter.template_version.fields, payload, selection)[0]
            else:
                answer = answer(encounter, payload)
            return httpx.Response(200, headers={'request-id': f'req_011SyntheticStanding{number:03d}'},
                                  json=message(answer, number=number))

        def model_check(self):
            with override_settings(STATE_DIR=self.state, MEDIA_ROOT=self.state / 'files', **SONNET_5):
                snapshot = st.settings_snapshot('model_check')
                here = dataclasses.replace(self.declaration, qa_database=connection.settings_dict['NAME'])
                problems = st.check_configuration(snapshot, here, 'model_check', self.campaign.root)
                # (the test database is test_quillmd_qa_*, and the QA server is the same one; nothing else differs)
                self.assertEqual(problems, [])
                return st.run_model_check(self.campaign, secret=SYNTHETIC_KEY,
                                          provenance={'runner_commit': 'offline-test'}, database_prefix='test_quillmd_qa_')

        def notes_run(self, **kwargs):
            flags = {**st.STAGE_FLAGS['notes_comparison']}
            with override_settings(STATE_DIR=self.state, MEDIA_ROOT=self.state / 'files',
                                   **STAGE_SETTINGS['ordinary_notes']), patch.dict(os.environ, flags):
                snapshot = st.settings_snapshot('notes_comparison')
                here = dataclasses.replace(self.declaration, qa_database=connection.settings_dict['NAME'])
                self.assertEqual(st.check_configuration(snapshot, here, 'notes_comparison', self.campaign.root), [])
                return st.run_stage(self.campaign, 'notes_comparison', secret=SYNTHETIC_KEY,
                                    provenance={'runner_commit': 'offline-test'}, database_prefix='test_quillmd_qa_',
                                    **kwargs)

        # ── the path, end to end ─────────────────────────────────────────────────────────────────────────────────
        def test_the_preflight_model_check_and_two_bounded_notes_runs(self):
            result = self.model_check()
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            self.assertEqual(result['run'], 'run-0001')
            ledger = self.campaign.ledger
            (attempt, outcome), = ledger.rows()
            self.assertEqual((attempt['mode'], attempt['monetary_ceiling'], attempt['run_id'], attempt['send_key']),
                             (st.MODE, None, 'run-0001', 'model_check:' + st.MODEL_CHECK_SEND))
            self.assertEqual(attempt['attempt_id'], f'{st.CAMPAIGN}/run-0001/attempt-001')
            self.assertIsNone(attempt['limits']['monetary_ceiling'])
            self.assertEqual(outcome['class'], 'completed')
            self.assertEqual(outcome['deadline'], None)                    # (the deadline was armed and never fired)
            self.assertEqual(ledger.stage_state('model_check')['state'], 'passed')
            self.assertEqual(self.campaign.runs.listing()[0][1]['closed_as'], 'decided')
            with self.assertRaises(pc.Refused):                            # (never twice)
                self.model_check()

            plan = st.standing_plan('notes_comparison', self.inputs)
            first = self.notes_run(max_sends=2)
            self.assertEqual((first['verdict'], first['decision']), ('PASS', 'partial'), first['reasons'])
            second = self.notes_run(max_sends=1)
            self.assertEqual((second['verdict'], second['decision']), ('PASS', 'partial'), second['reasons'])
            rows = ledger.rows()[1:]
            self.assertEqual([a['send']['id'] for a, _ in rows], [s.id for s in plan[:3]])
            self.assertEqual([a['run_id'] for a, _ in rows], ['run-0002', 'run-0002', 'run-0003'])
            self.assertEqual(len({a['send_key'] for a, _ in ledger.rows()}), 4)
            self.assertEqual([s['send'] for s in self.sent[1:]], [s.id for s in plan[:3]])       # (each sent once)
            self.assertTrue(all(s['captured_first'] for s in self.sent))
            self.assertTrue(all(s['max_tokens'] <= 20000 for s in self.sent))
            self.assertTrue(all(o['class'] == 'completed' for _, o in rows))
            self.assertEqual(ledger.stage_state('notes_comparison')['state'], 'open')
            self.assertEqual([c['closed_as'] for _, c in self.campaign.runs.listing()], ['decided', 'partial', 'partial'])
            self.assertEqual([s.id for s in st.remaining_sends(self.campaign, 'notes_comparison', plan)],
                             [s.id for s in plan[3:]])
            self.assertEqual(st.earlier_stops(self.campaign, 'notes_comparison'), [])
            self.assertEqual(pc.leaked(self.campaign.root, SYNTHETIC_KEY, exclude=(self.credential,)), [])
            self.campaign.ledger.release()
            out = io.StringIO()
            root, path = repository(self, sonnet5_declaration_text())
            with redirect_stderr(io.StringIO()):
                report = st.status(self.campaign.root, path, repository=root, out=out)
            self.campaign.ledger.acquire()
            self.assertIsNone(report['monetary_ceiling'])
            self.assertEqual((report['total']['attempts'], report['total']['open']), (4, 0))
            self.assertGreater(Decimal(report['total']['calculated_exposure_usd']), 0)

        def test_an_unsafe_default_adoption_stops_the_path(self):
            # (the frozen cases' adversarial simulations are all held by the application on this base — the historical
            # stage test that relied on N13's default exposure now passes where it expected a stop — so the UNSAFE
            # verdict is injected at the field classifier; everything after it — classify_case, the stop decision, the
            # stage failure, the run's close, nothing further sent, the next run refused — is the real machinery)
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            stages_module = sq.stages_module()
            real = st.standing_plan

            def cut(stage, inputs=None):
                return [s for s in real(stage, inputs) if s.id in ('notes:N13:default', 'notes:N16:default')]

            def unsafe(expectation, field, adopted, reviewed, replayed, *, model_disagrees=False):
                return 'unsupported_accepted', {'injected': 'synthetic unsafe adoption'}
            stages = tuple(dataclasses.replace(s, sends=2) if s.id == 'notes_comparison' else s
                           for s in self.declaration.stages)
            self.campaign.declaration = dataclasses.replace(self.declaration, stages=stages)
            with patch.object(st, 'standing_plan', side_effect=cut), \
                    patch.object(stages_module, 'notes_field_outcome', side_effect=unsafe):
                result = self.notes_run()
                self.assertEqual((result['verdict'], result['decision']), ('FAIL', 'failed'), result['reasons'])
                failed = self.campaign.ledger.stage_record('notes_comparison', 'failed')
                self.assertEqual(failed['summary']['not_sent'], ['notes:N16:default'])
                self.assertEqual(failed['summary']['sends'][0]['verdict']['unsafe'], ['adopted_without_source_support'])
                self.assertEqual([s['send'] for s in self.sent[1:]], ['notes:N13:default'])
                self.assertEqual(self.campaign.runs.listing()[-1][1]['closed_as'], 'failed')
                with self.assertRaisesRegex(pc.Refused, 'path is stopped'):
                    self.notes_run()
            self.assertEqual(len(self.campaign.ledger.rows()), 2)                    # (nothing further was written)
            self.assertEqual(len(self.campaign.runs.listing()), 2)                   # (the refused run never opened)
            evidence = self.campaign.root / 'evidence' / '002'
            self.assertTrue((evidence / 'classification.json').is_file())          # (the failed evidence is kept)
            self.assertEqual(st.earlier_stops(self.campaign, 'notes_comparison')[0]['send'], 'notes:N13:default')

        def test_a_stop_file_during_a_run_halts_it_without_failing_the_stage(self):
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            plan = st.standing_plan('notes_comparison', self.inputs)
            stop = self.campaign.stop_file()
            real = self.handler

            def handler(request):
                stop.write_text('')                                        # (the operator halts mid-send)
                return real(request)
            with patch.object(self, 'handler', side_effect=handler):
                result = self.notes_run(max_sends=3)
            self.assertEqual((result['verdict'], result['decision']), ('HALTED', 'halted'), result['reasons'])
            self.assertEqual([s['send'] for s in self.sent[1:]], [plan[0].id])     # (the send in flight completed)
            self.assertEqual(result['summary']['not_sent'], [plan[1].id, plan[2].id])
            self.assertEqual(self.campaign.ledger.stage_state('notes_comparison')['state'], 'open')   # (not failed)
            self.assertEqual(self.campaign.runs.listing()[-1][1]['closed_as'], 'halted')
            self.assertEqual(st.EXIT[result['verdict']], 4)
            with self.assertRaisesRegex(pc.Refused, 'Stop file'):
                self.notes_run(max_sends=1)
            stop.unlink()                                                  # (the operator lifts the halt)
            resumed = self.notes_run(max_sends=1)
            self.assertEqual(resumed['decision'], 'partial', resumed['reasons'])
            self.assertEqual([s['send'] for s in self.sent[1:]], [plan[0].id, plan[1].id])

        def test_the_stop_file_refuses_a_run_before_anything_is_written(self):
            self.campaign.stop_file().write_text('')
            with self.assertRaisesRegex(pc.Refused, 'Stop file'):
                self.model_check()
            self.assertEqual(self.campaign.ledger.rows(), [])
            self.assertEqual(self.campaign.runs.listing(), [])
            self.assertEqual(self.sent, [])
