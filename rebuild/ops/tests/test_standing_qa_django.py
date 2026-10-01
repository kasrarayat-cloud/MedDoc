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
  · a bounded mapping run (two forms) goes through the frozen grader and closes partial;
  · an unsafe verdict on the default path (injected at the field classifier: on this base the application holds every
    frozen adversarial simulation) stops the stage: nothing further is sent, the run closes failed, the next run is
    refused before anything is created, and the failed evidence is kept;
  · the Stop file refuses a run before anything is written; appearing DURING a run it halts the run (the send in
    flight completes, the rest are not made, the run closes halted, exit 4) without failing the stage, and the next run
    resumes once it is lifted;
  · (L1:R1-F4 / L2:R2-F2) a Stop file appearing inside a send BEFORE its attempt record — the real notes worker's
    attempt record, whose refusal sits outside the code that cancels — halts the run and its queued job is cancelled;
  · TRANSCRIPTION end to end (T4b), Deepgram a stand-in behind the REAL transcription guard: each allowlisted synthetic
    recording through the real voice view, ONE QA-worker job whose request carries exactly the declared parameters
    and key (the key in the environment only during that request), its request id, duration, cost at the declared
    rate and settlement recorded, the transcript reviewed and saved as the notes through the real notes view, then
    the generation on that encounter, review, finalization and the authenticated export; the stage passes, is never
    run twice, and no key is anywhere in the evidence, the result or the QA database; a Stop file met at the
    transcription send's admission halts the run, the queued job is cancelled and nothing is sent; (L1:R1-F2) a
    declared Deepgram file of its own path holding the Anthropic key sends nothing.
"""
import dataclasses
import hashlib
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
#: What the stand-in Deepgram returns for each allowlisted recording: the provider's style (no punctuation, numbers as
#: words), the recording's own synthetic script.
TRANSCRIPTS = {
    'soap-ankle-speech': 'symptoms left ankle soreness began after twisting the left ankle yesterday pertinent negatives '
                         'denies fever numbness and right ankle pain examination mild swelling over the left lateral '
                         'ankle no open wound plan rest ice and follow up in three days',
    'colonoscopy-speech': 'indication screening colonoscopy for a synthetic patient findings the colon was examined to '
                          'the cecum no polyps were seen plan repeat colonoscopy in ten years'}


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
    from .test_standing_qa import DEEPGRAM_KEY, fixture_text, repository, rights_ledger

    REAL_CLIENT = anthropic.Anthropic
    HISTORICAL = (REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
                  ).read_text()
    AMENDMENT = (REPOSITORY / 'docs' / 'foundation' / 'mutations' /
                 '20260929-quillmd-v1-sonnet5-relations-contract-amendment.md').read_text()
    PLAIN = re.search(r'^pricing_version model_check: (\S+)$', HISTORICAL, re.M).group(1)
    RELATIONS = re.search(r'^amended_pricing_version: (\S+)$', AMENDMENT, re.M).group(1)

    def transcription_version():
        """The application's own `transcription` pricing version for claude-sonnet-5 at the TEST declaration's rate
        (0.0077 USD/minute) under the transcription stage's settings — computed as the `pricing` command computes it."""
        from core import generation
        with override_settings(**STAGE_SETTINGS['ordinary_notes'], QUILLMD_DEEPGRAM_MIP_OPT_OUT='true',
                               QUILLMD_DEEPGRAM_SMART_FORMAT='false'), \
                patch.dict(os.environ, {**sq.PRICE_SETTINGS, 'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.0077',
                                        'QUILLMD_DEEPGRAM_RATE_PER_SECOND': ''}):
            return generation.configuration()['pricing_version']

    def transcription_relations_version():
        """transcription_version() with field relations on: the version a transcript's generation is quoted under when
        the declaration states `transcription_notes_contract: field_relations`."""
        from core import generation
        with override_settings(**{**STAGE_SETTINGS['ordinary_notes'], 'V3_FIELD_RELATIONS': True},
                               QUILLMD_DEEPGRAM_MIP_OPT_OUT='true', QUILLMD_DEEPGRAM_SMART_FORMAT='false'), \
                patch.dict(os.environ, {**sq.PRICE_SETTINGS, 'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.0077',
                                        'QUILLMD_DEEPGRAM_RATE_PER_SECOND': ''}):
            return generation.configuration()['pricing_version']

    def sonnet5_declaration_text():
        """The committed TEST declaration with the one Sonnet 5 profile the application has (see the module note)."""
        text = fixture_text()
        old = 'pricing_version transcription: configured-v1:' + 'e' * 64
        assert text.count(old) == 1, old
        text = text.replace(old, 'pricing_version transcription: ' + transcription_version())
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
            if payload.get('contract') == 'blank-mapping-v3':
                from core import mapping_wire
                return httpx.Response(200, headers={'request-id': f'req_011SyntheticStanding{number:03d}'},
                                      json=message(mapping_wire.fixture(payload), number=number))
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

        def test_a_bounded_mapping_run_through_the_frozen_grader(self):
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            with override_settings(STATE_DIR=self.state, MEDIA_ROOT=self.state / 'files', **STAGE_SETTINGS['mapping']), \
                    patch.dict(os.environ, st.STAGE_FLAGS['mapping']):
                here = dataclasses.replace(self.declaration, qa_database=connection.settings_dict['NAME'])
                self.assertEqual(st.check_configuration(st.settings_snapshot('mapping'), here, 'mapping',
                                                        self.campaign.root), [])
                result = st.run_stage(self.campaign, 'mapping', secret=SYNTHETIC_KEY,
                                      provenance={'runner_commit': 'offline-test'}, database_prefix='test_quillmd_qa_',
                                      max_sends=2)
            self.assertEqual((result['verdict'], result['decision']), ('PASS', 'partial'), result['reasons'])
            rows = self.campaign.ledger.rows()[1:]
            self.assertEqual([a['send']['id'] for a, _ in rows], ['mapping:f1-guidance-confirmation',
                                                                  'mapping:f2-leave-checkboxes'])
            inputs = self.inputs['forms_sha256']
            for attempt, outcome in rows:
                self.assertEqual(outcome['class'], 'completed')
                self.assertEqual(attempt['form_sha256'], inputs[f'mapping/{attempt["send"]["form"]}.docx'])
                evidence = self.campaign.root / 'evidence' / f'{attempt["number"]:03d}'
                self.assertTrue((evidence / 'graded.json').is_file())               # (the frozen grader ran)
                classification = json.loads((evidence / 'classification.json').read_text())
                self.assertFalse(classification['stops_stage'], classification)
            self.assertTrue(all(s['max_tokens'] == 20000 for s in self.sent[1:]))
            self.assertEqual(self.campaign.ledger.stage_state('mapping')['state'], 'open')

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

        # ── a Stop file met by the real notes worker before its attempt record (L1:R1-F4 / L2:R2-F2) ────────────────
        def test_a_stop_file_at_the_attempt_record_halts_and_the_queued_job_is_cancelled(self):
            from core.models import Job
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            stages_module = sq.stages_module()
            real = stages_module.Run.attempt
            stop = self.campaign.stop_file()

            def attempt(worker, send, job, *args, **kwargs):
                stop.write_text('')                      # (after the loop's check and the admission, before the record)
                return real(worker, send, job, *args, **kwargs)
            with patch.object(stages_module.Run, 'attempt', attempt):
                result = self.notes_run(max_sends=2)
            self.assertEqual((result['decision'], result['verdict'], result['reasons']), ('halted', 'HALTED', []))
            self.assertIn('before its attempt was written', result['summary']['halted'])
            self.assertEqual(self.campaign.ledger.stage_state('notes_comparison')['state'], 'open')
            self.assertEqual(len(self.campaign.ledger.rows()), 1)           # (the model check's only: nothing sent)
            self.assertEqual(self.sent[1:], [])
            self.assertEqual(len(result['summary']['halt_jobs']['cancelled']), 1)
            self.assertFalse(Job.objects.filter(state='queued').exists())   # (the queued job did not stay queued)
            self.assertEqual(Job.objects.get(pk=result['summary']['halt_jobs']['cancelled'][0]).state, 'cancelled')
            stop.unlink()
            resumed = self.notes_run(max_sends=1)
            self.assertEqual(resumed['decision'], 'partial', resumed['reasons'])

        # ── transcription (T4b) ──────────────────────────────────────────────────────────────────────────────────
        def transcription_setup(self):
            """The Deepgram key file (synthetic, 0600) the declaration names, the real guard on the campaign guard
            with a stand-in network, and the generation answers for the transcripts."""
            from core.models import AuditEvent
            tr = st.transcription_module()
            key = pc.private_directory(self.root / 'credential') / 'deepgram-api-key'
            key.write_text(DEEPGRAM_KEY + '\n')
            os.chmod(key, 0o600)
            self.deepgram_file = key
            self.campaign.declaration = dataclasses.replace(self.declaration, transcription=dataclasses.replace(
                self.declaration.transcription, credential_file=str(key)))
            self.deepgram_requests = []
            self.transcripts = {}

            def network(transport, request):
                number = pc.CURRENT_ATTEMPT['number']
                prepared = AuditEvent.objects.filter(action='voice.submission_prepared').order_by('-created_at').first()
                seconds = float(prepared.details['seconds'])
                attempt = json.loads((self.campaign.ledger.dir / f'{number:03d}-attempt.json').read_text())
                transcript = TRANSCRIPTS[attempt['send']['case']]
                self.deepgram_requests.append({
                    'attempt': number, 'authorization': request.headers.get('authorization'),
                    'params': dict(request.url.params), 'body_sha256': hashlib.sha256(request.content).hexdigest(),
                    'key_in_environment': os.environ.get(st.TRANSCRIPTION_KEY_VARIABLE) == DEEPGRAM_KEY,
                    'captured_first': (Path(pc.CURRENT_ATTEMPT['evidence_dir']) / 'request.json').exists(),
                    'seconds': seconds})
                return httpx.Response(200, headers={'dg-request-id': f'synthetic-dg-{number:03d}'}, json={
                    'metadata': {'request_id': f'synthetic-dg-{number:03d}', 'duration': seconds, 'channels': 1,
                                 'models': ['synthetic-model'],
                                 'model_info': {'synthetic-model': {'name': 'synthetic-nova-3-medical',
                                                                    'arch': 'nova-3'}}},
                    'results': {'channels': [{'alternatives': [{'transcript': transcript, 'confidence': 0.99}]}]}})
            pc.install_transport_guard()
            self.addCleanup(pc.uninstall_transport_guard)
            tr.install_transcription_guard(network=network)
            self.addCleanup(tr.uninstall_transcription_guard)
            pc.SENT.clear()                       # (sends per attempt NUMBER: one campaign per request process, not
            self.addCleanup(pc.SENT.clear)        # per test process — another test's attempt 2 is not this one's)

            def chief_complaint(encounter, payload):
                asked, units = sq.stages_module().steps.source_units(encounter.notes, encounter.template_version.fields)
                return wire_answer(encounter.notes, encounter.template_version.fields, payload,
                                   {'v3_1': {'units': [units[0]['quote']]}})[0]
            for audio in st.TRANSCRIPTION_AUDIO:
                self.answers[f'generation:{audio.id}'] = chief_complaint

        def transcription_run(self, smart_format='false', **kwargs):
            with override_settings(STATE_DIR=self.state, MEDIA_ROOT=self.state / 'files',
                                   **STAGE_SETTINGS['ordinary_notes'], QUILLMD_DEEPGRAM_MIP_OPT_OUT='true',
                                   QUILLMD_DEEPGRAM_SMART_FORMAT=smart_format), \
                    patch.dict(os.environ, st.stage_flags('transcription', self.campaign.declaration)):
                here = dataclasses.replace(self.campaign.declaration, qa_database=connection.settings_dict['NAME'])
                self.assertEqual(st.check_configuration(st.settings_snapshot('transcription'), here, 'transcription',
                                                        self.campaign.root), [])
                kwargs.setdefault('transcription_secret', DEEPGRAM_KEY)
                result = st.run_stage(self.campaign, 'transcription', secret=SYNTHETIC_KEY,
                                      provenance={'runner_commit': 'offline-test'}, database_prefix='test_quillmd_qa_',
                                      **kwargs)
                from django.conf import settings
                self.relations_after_run = settings.V3_FIELD_RELATIONS     # (read INSIDE the run's own settings)
                return result

        def test_a_transcription_then_its_generation_end_to_end(self):
            from decimal import Decimal
            from core.models import AuditEvent, Encounter, Job, ProviderReceipt, Usage
            for audio in st.TRANSCRIPTION_AUDIO:
                if not os.path.exists(audio.path):
                    self.skipTest(f'{audio.path} is not on this host')
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            self.transcription_setup()
            result = self.transcription_run()
            self.assertEqual((result['verdict'], result['decision']), ('PASS', 'passed'), result['reasons'])
            rows = [(a, o) for a, o in self.campaign.ledger.rows() if a['stage'] == 'transcription']
            self.assertEqual([a['send']['id'] for a, _ in rows],
                             ['transcription:soap-ankle-speech', 'generation:soap-ankle-speech',
                              'transcription:colonoscopy-speech', 'generation:colonoscopy-speech'])
            self.assertEqual(len(self.deepgram_requests), 2)                       # (ONE request per recording)
            for request in self.deepgram_requests:
                self.assertEqual(request['params'], {'model': 'nova-3-medical', 'smart_format': 'false',
                                                     'mip_opt_out': 'true'})
                self.assertEqual(request['authorization'], f'Token {DEEPGRAM_KEY}')   # (positive control: it was sent)
                self.assertTrue(request['key_in_environment'] and request['captured_first'])
            self.assertNotIn(st.TRANSCRIPTION_KEY_VARIABLE, os.environ)            # (gone again after each request)
            rate = Decimal('0.0077')
            for (attempt, outcome), (generation, generated) in zip(rows[0::2], rows[1::2]):
                audio = st.AUDIO_BY_ID[attempt['send']['case']]
                self.assertEqual((attempt['audio_sha256'], attempt['audio']['label']), (audio.sha256, st.AUDIO_LABEL))
                self.assertEqual(attempt['transcription']['parameters'], {'model': 'nova-3-medical',
                                                                          'smart_format': 'false', 'mip_opt_out': 'true'})
                self.assertEqual(attempt['pricing_version'], self.declaration.pricing_version('transcription'))
                self.assertEqual(outcome['class'], 'completed')
                self.assertEqual((outcome['provider_request_id'], outcome['response_request_id']),
                                 (f'synthetic-dg-{attempt["number"]:03d}',) * 2)
                cost = (Decimal(outcome['duration_seconds']) * rate / 60).quantize(Decimal('0.0000000001'))
                self.assertEqual(Decimal(outcome['provider_cost']), cost)
                receipt = ProviderReceipt.objects.get(job=attempt['job'])
                usage = Usage.objects.get(job=attempt['job'])
                self.assertEqual((receipt.provider, receipt.actual_cost, usage.actual_cost),
                                 ('deepgram:nova-3-medical', cost, cost))
                self.assertLessEqual(cost, Decimal(attempt['maximum_cost']))
                evidence = self.campaign.root / 'evidence' / f'{attempt["number"]:03d}'
                request = json.loads((evidence / 'request.json').read_text())
                self.assertNotIn('authorization', request['headers'])
                self.assertEqual(request['body_sha256'], receipt.units['submission_sha256'])
                self.assertEqual(hashlib.sha256((evidence / 'request.body').read_bytes()).hexdigest(),
                                 request['body_sha256'])
                self.assertEqual(hashlib.sha256((evidence / 'case' / f'{audio.id}.wav').read_bytes()).hexdigest(),
                                 audio.sha256)
                encounter = Encounter.objects.get(pk=attempt['encounter'])
                transcript = TRANSCRIPTS[audio.id]
                applied = json.loads((evidence / 'notes-applied.json').read_text())
                self.assertEqual(applied['notes_sha256'], hashlib.sha256(transcript.encode()).hexdigest())
                self.assertEqual(AuditEvent.objects.get(action='transcription.applied', target=attempt['job'])
                                 .details['corrected'], False)
                self.assertEqual((generation['encounter'], generation['notes_sha256'], generation['audio_sha256']),
                                 (attempt['encounter'], applied['notes_sha256'], audio.sha256))
                self.assertEqual(generated['class'], 'completed')
                encounter.refresh_from_db()
                self.assertEqual((encounter.notes, encounter.status), (transcript, 'finalized'))
                export = json.loads((self.campaign.root / 'evidence' / f'{generation["number"]:03d}' / 'export.json')
                                    .read_text())
                self.assertEqual(export['sha256'], encounter.export_sha256)
                made = next(row for row in result['summary']['sends'] if row.get('attempt') == attempt['number'])
                self.assertEqual((made['transcription']['provider_request_id'], made['transcription']['model_requested']),
                                 (outcome['provider_request_id'], 'nova-3-medical'))
                self.assertTrue({'request.json', 'request.body', 'provider-response.json', 'provider-response.body',
                                 'provider-result.json', f'case/{audio.id}.wav'} <= set(made['transcription']['artifacts']))
            # (the generations were judged: an adopted answer's source support was checked against the saved notes)
            support = [json.loads((self.campaign.root / 'evidence' / f'{g["number"]:03d}' / 'classification.json')
                                  .read_text()) for g, _ in rows[1::2]]
            self.assertTrue(any('adopted' in c['verdict']['fields'].values() for c in support), support)
            self.assertTrue(all(not entry['problems'] for c in support for entry in c['source_support'].values()))
            self.assertTrue(all(c['verdict']['verdict'] == 'usefulness' for c in support))
            # (no key anywhere: the evidence, the run's result, the QA database's records)
            self.assertEqual(pc.leaked(self.campaign.root, DEEPGRAM_KEY, exclude=(self.deepgram_file,)), [])
            self.assertEqual(pc.leaked(self.campaign.root, SYNTHETIC_KEY, exclude=(self.credential,)), [])
            self.assertNotIn(DEEPGRAM_KEY, json.dumps(result, default=str))
            stored = json.dumps([list(AuditEvent.objects.values_list('details', flat=True)),
                                 list(Job.objects.values_list('config', 'error')),
                                 list(ProviderReceipt.objects.values_list('units', 'rates'))], default=str)
            self.assertNotIn(DEEPGRAM_KEY, stored)
            self.assertNotIn(SYNTHETIC_KEY, stored)
            with self.assertRaisesRegex(pc.Refused, 'already passed'):
                self.transcription_run()                                           # (never twice)
            self.assertEqual(len(self.deepgram_requests), 2)

        def test_a_declared_smart_formatted_transcription_sends_exactly_that(self):
            """Refutation r1 B-F2: no test ran a `true` declaration through the transcription preconditions, so a
            precondition reverted to demand 'false' stayed green. Here the declaration states true: the process, the
            preconditions, the job's recorded parameters and the one request each carry smart_format=true."""
            for audio in st.TRANSCRIPTION_AUDIO:
                if not os.path.exists(audio.path):
                    self.skipTest(f'{audio.path} is not on this host')
            flipped = dataclasses.replace(self.declaration, transcription=dataclasses.replace(
                self.declaration.transcription, smart_format='true'))
            self.declaration = self.campaign.declaration = flipped
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            self.transcription_setup()
            result = self.transcription_run(smart_format='true')
            self.assertEqual((result['verdict'], result['decision']), ('PASS', 'passed'), result['reasons'])
            self.assertEqual(len(self.deepgram_requests), 2)
            for request in self.deepgram_requests:
                self.assertEqual(request['params'], {'model': 'nova-3-medical', 'smart_format': 'true',
                                                     'mip_opt_out': 'true'})
            for attempt, _ in [(a, o) for a, o in self.campaign.ledger.rows() if a['stage'] == 'transcription'][0::2]:
                self.assertEqual(attempt['transcription']['parameters']['smart_format'], 'true')

        def test_a_transcript_generated_under_the_field_relations_contract(self):
            """The candidate's claude-sonnet-5-5 default: the generation on each transcript runs under field relations
            (switched on around that send only), is quoted and priced under voice_notes_field_relations, and the
            process is back at every contract flag off afterwards."""
            from django.conf import settings
            from core.models import Job
            for audio in st.TRANSCRIPTION_AUDIO:
                if not os.path.exists(audio.path):
                    self.skipTest(f'{audio.path} is not on this host')
            # (the transcript is a frozen notes case's own punctuated notes, answered with its reference selection, so
            # the relations generation adopts answers and the transcript judge checks them — refutation r1 F5)
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == 'N01')
            selection = {k: e['raw_model_expectation']['acceptable'][0] for k, e in case['fields'].items()}
            self.enterContext(patch.dict(TRANSCRIPTS, {key: case['notes'] for key in TRANSCRIPTS}))
            relations = dataclasses.replace(
                self.declaration,
                transcription=dataclasses.replace(self.declaration.transcription, notes_contract='field_relations'),
                pricing_versions=tuple(sorted(self.declaration.pricing_versions
                                              + (('voice_notes_field_relations', transcription_relations_version()),))))
            self.assertNotEqual(relations.pricing_version('voice_notes_field_relations'),
                                relations.pricing_version('ordinary_notes_field_relations'))   # (another voice rate)
            self.declaration = self.campaign.declaration = relations
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            self.transcription_setup()
            for audio in st.TRANSCRIPTION_AUDIO:
                self.answers[f'generation:{audio.id}'] = (lambda encounter, payload: wire_answer(
                    encounter.notes, encounter.template_version.fields, payload, selection)[0])
            result = self.transcription_run()
            self.assertEqual((result['verdict'], result['decision']), ('PASS', 'passed'), result['reasons'])
            generations = [(a, o) for a, o in self.campaign.ledger.rows()
                           if a['stage'] == 'transcription' and a['send']['path'] == 'transcription_generation']
            self.assertEqual(len(generations), 2)
            for attempt, outcome in generations:
                self.assertEqual(attempt['send']['pricing_key'], 'voice_notes_field_relations')
                self.assertEqual(attempt['pricing_version'], relations.pricing_version('voice_notes_field_relations'))
                self.assertEqual(outcome['class'], 'completed')
                job = Job.objects.get(pk=attempt['job'])
                self.assertTrue(job.config.get('ordinary_field_contract'))
            self.assertFalse(self.relations_after_run)       # (switched on around the send only, read inside the run)
            # Positive control: a punctuated transcript under field relations adopts an answer, and the judge checked
            # its source support against the saved notes (refutation r1 of 6c8d79d6, F5).
            support = [json.loads((self.campaign.root / 'evidence' / f'{a["number"]:03d}' / 'classification.json')
                                  .read_text()) for a, _ in generations]
            self.assertTrue(any('adopted' in c['verdict']['fields'].values() for c in support), support)
            self.assertTrue(all(not entry['problems'] for c in support for entry in c['source_support'].values()))

        def test_a_wrong_voice_relations_price_is_refused_before_any_deepgram_request(self):
            """Refutation r1 of 6c8d79d6, F1: the transcript generation's price version (and profile) is checked with the
            run's preconditions, so a stale or mistyped `voice_notes_field_relations` line costs no Deepgram request and
            leaves the stage open — as a wrong plain `transcription` line always did."""
            for audio in st.TRANSCRIPTION_AUDIO:
                if not os.path.exists(audio.path):
                    self.skipTest(f'{audio.path} is not on this host')
            wrong = dataclasses.replace(
                self.declaration,
                transcription=dataclasses.replace(self.declaration.transcription, notes_contract='field_relations'),
                pricing_versions=tuple(sorted(self.declaration.pricing_versions + (
                    ('voice_notes_field_relations', self.declaration.pricing_version('ordinary_notes_field_relations')),))))
            self.declaration = self.campaign.declaration = wrong
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            self.transcription_setup()
            with self.assertRaisesRegex(pc.Refused, 'prices the transcript generation'):
                self.transcription_run()
            self.assertEqual(self.deepgram_requests, [])
            self.assertEqual(self.campaign.ledger.stage_state('transcription')['state'], 'open')

        def test_an_empty_transcript_stops_the_stage_before_its_generation(self):
            audio = st.AUDIO_BY_ID['soap-ankle-speech']
            if not os.path.exists(audio.path):
                self.skipTest(f'{audio.path} is not on this host')
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            self.transcription_setup()
            with patch.dict(TRANSCRIPTS, {'soap-ankle-speech': ''}):
                result = self.transcription_run()
            self.assertEqual((result['verdict'], result['decision']), ('FAIL', 'failed'))
            self.assertIn('the provider returned no transcript for synthetic speech', '; '.join(result['reasons']))
            self.assertEqual(result['summary']['not_sent'], ['generation:soap-ankle-speech',
                                                             'transcription:colonoscopy-speech',
                                                             'generation:colonoscopy-speech'])
            self.assertEqual(len(self.deepgram_requests), 1)
            self.assertEqual(self.campaign.ledger.stage_state('transcription')['state'], 'failed')
            failed = self.campaign.ledger.stage_record('transcription', 'failed')
            self.assertEqual(failed['summary']['sends'][0]['verdict']['contract'], ['transcript_unusable'])
            with self.assertRaisesRegex(pc.Refused, 'path is stopped'):
                self.transcription_run()

        def test_a_stop_file_at_the_transcription_admission_halts_and_nothing_is_sent(self):
            from core.models import Job
            audio = st.AUDIO_BY_ID['soap-ankle-speech']
            if not os.path.exists(audio.path):
                self.skipTest(f'{audio.path} is not on this host')
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            self.transcription_setup()
            tr = st.transcription_module()
            real = tr.voice_quote
            stop = self.campaign.stop_file()

            def voice_quote(client, encounter):
                stop.write_text('')                      # (after the loop's check; the voice view still queues the job)
                return real(client, encounter)
            with patch.object(tr, 'voice_quote', voice_quote):
                result = self.transcription_run()
            self.assertEqual((result['decision'], result['verdict'], result['reasons']), ('halted', 'HALTED', []))
            self.assertEqual(self.deepgram_requests, [])                           # (nothing was sent)
            self.assertEqual([a for a, _ in self.campaign.ledger.rows() if a['stage'] == 'transcription'], [])
            self.assertEqual(self.campaign.ledger.stage_state('transcription')['state'], 'open')
            jobs = list(Job.objects.filter(kind='transcription'))
            self.assertEqual([job.state for job in jobs], ['cancelled'])           # (refused at admission: released)
            stop.unlink()
            resumed = self.transcription_run(max_sends=2)
            self.assertEqual(resumed['decision'], 'partial', resumed['reasons'])
            self.assertEqual(len(self.deepgram_requests), 1)

        def test_a_deepgram_file_holding_the_anthropic_key_sends_nothing(self):
            """L1:R1-F2 end to end: the declared Deepgram file — its own path, 0600, one name, one line — holds the
            ANTHROPIC key. Whether the run is handed that value or the campaign's own Deepgram key, the real run_stage
            refuses before any transcription job, attempt or request: the stand-in Deepgram sees nothing."""
            from core.models import Job
            for audio in st.TRANSCRIPTION_AUDIO:
                if not os.path.exists(audio.path):
                    self.skipTest(f'{audio.path} is not on this host')
            self.assertEqual(self.model_check()['verdict'], 'PASS')
            self.transcription_setup()
            self.deepgram_file.write_text(SYNTHETIC_KEY + '\n')               # (a copy of the Anthropic key)
            os.chmod(self.deepgram_file, 0o600)
            self.assertNotEqual(self.deepgram_file, Path(self.credential))      # (the paths differ)
            for given in ('the file value', 'the campaign Deepgram key'):
                with self.subTest(given=given):
                    secret = SYNTHETIC_KEY if given == 'the file value' else DEEPGRAM_KEY
                    with self.assertRaisesRegex(pc.Refused, 'The Deepgram credential is not a key of its own'):
                        self.transcription_run(transcription_secret=secret)
            self.assertEqual(self.deepgram_requests, [])                           # (nothing was sent)
            self.assertEqual([a for a, _ in self.campaign.ledger.rows() if a['stage'] == 'transcription'], [])
            self.assertEqual(Job.objects.filter(kind='transcription').count(), 0)
            self.assertNotEqual(self.campaign.ledger.stage_state('transcription')['state'], 'passed')

        def test_the_stop_file_refuses_a_run_before_anything_is_written(self):
            self.campaign.stop_file().write_text('')
            with self.assertRaisesRegex(pc.Refused, 'Stop file'):
                self.model_check()
            self.assertEqual(self.campaign.ledger.rows(), [])
            self.assertEqual(self.campaign.runs.listing(), [])
            self.assertEqual(self.sent, [])
