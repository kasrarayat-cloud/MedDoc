"""The mapping and ordinary_notes stages end to end on the synthetic QA database, with a FAKE provider
(ops/sonnet5_stages.py).

Run with Django's test runner against the QA server (a distinct test database, test_quillmd_qa_*):

    QUILLMD_DB_HOST=127.0.0.1 QUILLMD_DB_PORT=55731 QUILLMD_DB_NAME=quillmd_qa_<tag> … \
        python -B manage.py test ops.tests.test_sonnet5_stages

Anywhere else every test here is SKIPPED, visibly. The provider is the real Anthropic SDK around an in-process
httpx.MockTransport; `network_guard` refuses every other socket. The fake answers each request as a model would: the
mapping requests with the application's own offline wire fixture (or a harmful proposal), the generation requests with
each frozen case's REFERENCE selection built against the request the application actually sent (app_path_steps, the
walk's own builder). What each test proves:
  · each stage passes end to end through the real views and the real worker, every send admitted at the job's own
    maximum, written before its ONE request, captured first, settled, audited, scanned, and graded or classified by the
    FROZEN graders (subprocesses, provenance checked); the plan's order is the order sent; the relations flag is on for
    the relations sends only, each priced at its declared version;
  · an unsafe mapping proposal and an unsafe default-path adoption STOP the stage (nothing further is sent); an unsafe
    relations-path adoption is recorded as veto evidence and does not;
  · every contract stop class (served model, stop reason, output share, geography, a lost response, the deadline, a
    leak) stops the stage, the lost response is never re-sent, and nothing is admitted afterwards;
  · admission near the limit refuses the next send BEFORE its attempt is written, and its queued job is cancelled;
  · (refutation F1) a held forbidden selection is a caught model error (held_correct) and a held unlisted one is left
    for adjudication (held_unadjudicated) — neither is an over-hold;
  · (refutation EXPORT-CHECK-DOES-NOT-READ) a defective writer that exports a mark other than the reviewed one, or fills
    a held field, stops the stage through the stage's own read-back although the frozen check passes it;
  · (refutation RAW-RESPONSE-LOST-200) a billed response the product cannot settle is retained as received (id,
    request-id, served model, stop reason, usage) with the money at the bound, and a response not retained stops;
  · (relations contract v2) the relations sends answer with the KEYED body (the frozen reference_answer's list body,
    translated here in test code — app_path_steps.py is frozen); they run only under a contract-identity amendment
    (in memory here: its committed-file rules are proved in test_provider_campaign), at its pricing version and at a
    maximum recomputed by the same compiler; without it they refuse before anything is created;
  · (REMAINDER) a stage reopened after the live failure's shape sends ONLY the six relations sends that failure did not
    make, never one already made — and, since N02:field_relations stopped it and is never sent again, is decided FAILED
    naming that stop (refutation F1: a remainder completes the evidence, never the pass); a stage whose earlier failure
    stopped before any attempt passes on its remainder.
"""
import dataclasses
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc
from . import network_guard
from .test_sonnet5_qa import ELIGIBLE, WHY

REPOSITORY = Path(__file__).resolve().parents[3]
REAL_DECLARATION = REPOSITORY / 'docs' / 'foundation' / 'mutations' / '20260928-quillmd-v1-sonnet5-staged-campaign.md'
SYNTHETIC_KEY = 'sk-ant-api03-SYNTHETIC-OFFLINE-STAGE-KEY-222222222222222222222222222222222222-CCCCCCCC'


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


if not ELIGIBLE:
    class StagesNotRunHere(unittest.TestCase):
        @unittest.skip(WHY)
        def test_the_stages_need_the_qa_database(self):
            pass                                                     # pragma: no cover

else:
    import anthropic
    import httpx
    from django.db import connection
    from django.test import TestCase, override_settings

    from ops import sonnet5_qa as sq
    from ops import sonnet5_stages as st
    from .test_provider_campaign import NoEnvOpened, limits_record, terms_record
    from .test_sonnet5_qa import SONNET_5

    from core.tests.test_v3_field_relations import wired
    from .test_provider_campaign import RELATIONS_BASE, RELATIONS_V1, RELATIONS_V2
    UNSENT = ['notes:N03:field_relations', 'notes:N10:field_relations', 'notes:N13:field_relations',
              'notes:N14:field_relations', 'notes:N15:field_relations', 'notes:N16:field_relations']

    def test_amendment(declaration):
        """The contract-identity amendment the lead would commit, IN MEMORY (declared_amendment's file rules are proved
        in test_provider_campaign.AmendmentTests; the campaign still proves it against the pinned terms)."""
        return pc.Amendment(path='(in-memory test amendment)', sha256='0' * 64, commit='0' * 40, commit_time='',
                            campaign=declaration.campaign, authority_id=declaration.authority_id,
                            declaration_sha256=declaration.sha256, pricing_key=pc.AMENDABLE_PRICING_KEY,
                            pinned_pricing_version=RELATIONS_V1, previous_pricing_version=RELATIONS_BASE,
                            previous_contract='ordinary-field-relations-v1', contract='ordinary-field-relations-v2',
                            pricing_version=RELATIONS_V2)

    def wire_answer(notes, fields, payload, selection):
        """The provider body for `selection` against the request actually sent: the frozen reference_answer, and on the
        relations path its list body translated into the contract-v3 wire (test code only; the frozen file is unchanged)."""
        answer, units = st.steps.reference_answer(notes, fields, payload, selection)
        if 'catalogue' in payload:
            asked, offered = st.steps.source_units(notes, fields)
            return wired(answer, asked, offered), units
        return answer, units

    STAGE_SETTINGS = {
        'mapping': dict(SONNET_5, QUILLMD_WORD_ENGINE='v3', QUILLMD_MAPPING_ASSISTANCE=True,
                        QUILLMD_MAPPING_ASSISTANCE_LIVE=True, QUILLMD_LAYOUT_SOCKET=''),
        'ordinary_notes': dict(SONNET_5, QUILLMD_WORD_ENGINE='v3', QUILLMD_MAPPING_ASSISTANCE=False,
                               QUILLMD_MAPPING_ASSISTANCE_LIVE=False, QUILLMD_LAYOUT_SOCKET='')}
    REAL_CLIENT = anthropic.Anthropic

    def message(answer, *, number=0, model='claude-sonnet-5', stop_reason='end_turn', input_tokens=2000,
                output_tokens=300, geo='global', cache_written=0, cache_split=(0, 0)):
        return {'id': f'msg_01SyntheticStage{number:012d}', 'type': 'message', 'role': 'assistant', 'model': model,
                'content': [{'type': 'text', 'text': json.dumps(answer)}], 'stop_reason': stop_reason,
                'stop_sequence': None, 'stop_details': None,
                'usage': {'input_tokens': input_tokens, 'cache_creation_input_tokens': cache_written,
                          'cache_read_input_tokens': 0,
                          'cache_creation': {'ephemeral_5m_input_tokens': cache_split[0],
                                             'ephemeral_1h_input_tokens': cache_split[1]},
                          'output_tokens': output_tokens, 'service_tier': 'standard', 'inference_geo': geo,
                          'server_tool_use': None}}

    def slot_id(payload, slot):
        return next(n for n, row in enumerate(payload['slots']) if row['slot'].split('#', 1)[1] == slot)

    def addition(payload, slot, kind, label):
        """The app's own offline fixture plus ONE added field at `slot`, labelled with its printed `label`."""
        from core import mapping_wire
        sid = slot_id(payload, slot)
        text = payload['slots'][sid]['text']
        start = text.index(label)
        answer = mapping_wire.fixture(payload)
        answer['s'] = {group: [n for n in ids if n != sid] for group, ids in answer['s'].items()}
        answer['s']['c'].append(sid)
        answer['x'] = [[-1, sid, mapping_wire.KINDS.index(kind), payload['text_refs'].index([sid, 0, 0]), start,
                        start + len(label), -1]]
        return answer

    class StageTestCase(TestCase):
        STAGE = None

        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            name = connection.settings_dict['NAME']
            if not str(name).startswith('test_quillmd_qa_'):
                raise AssertionError(f'refusing to run outside the QA test database (connected to {name!r})')
            cls.declared = pc.declared(REAL_DECLARATION, repository=REPOSITORY, out=io.StringIO())
            cls.inputs = st.frozen_inputs()

        def fresh_campaign(self, amended=True, **changes):
            """A new temporary campaign root (its own state directory and provider configuration directory) whose
            ledger holds the passed model_check — the live ledger's shape."""
            self.root = Path(tempfile.mkdtemp(prefix='sonnet5-stage-test-'))
            self.addCleanup(shutil.rmtree, self.root, True)
            credential = pc.private_directory(self.root / 'credential') / 'anthropic-api-key'
            credential.write_text(SYNTHETIC_KEY + '\n')
            os.chmod(credential, 0o600)
            self.credential = credential
            self.declaration = dataclasses.replace(self.declared, credential_file=str(credential), **changes)
            self.amendment = test_amendment(self.declaration) if amended else None
            self.campaign = pc.Campaign(self.declaration, self.root, watched_files=sq.WATCHED_FILES,
                                        amendment=self.amendment)
            self.addCleanup(self.campaign.ledger.release)
            self.pass_model_check()
            state = pc.private_directory(self.root / 'qa-state')
            config_dir = pc.private_directory(self.root / 'tmp' / 'anthropic-config')
            settings = override_settings(STATE_DIR=state, MEDIA_ROOT=state / 'files', **STAGE_SETTINGS[self.STAGE])
            settings.enable()
            self.addCleanup(settings.disable)
            environment = patch.dict(os.environ, {**sq.PRICE_SETTINGS, **st.STAGE_FLAGS[self.STAGE],
                                                  'ANTHROPIC_API_KEY': SYNTHETIC_KEY,
                                                  'ANTHROPIC_CONFIG_DIR': str(config_dir)})
            environment.start()
            self.addCleanup(environment.stop)
            for name in [name for name in os.environ if pc.forbidden_name(name)]:
                del os.environ[name]                        # (restored by patch.dict when the test ends)
            self.sent = []

        def setUp(self):
            self.fresh_campaign()
            pc.install_request_capture()
            self.addCleanup(pc.uninstall_request_capture)
            self.addCleanup(pc.CURRENT_ATTEMPT.clear)
            self.sent, self.shapes, self.answers = [], {}, {}
            self.transport_error = self.delay = None
            provider = patch('anthropic.Anthropic', side_effect=self.provider_client)
            provider.start()
            self.addCleanup(provider.stop)

        def pass_model_check(self):
            """The live ledger's shape: model_check passed on one completed attempt (its prerequisite)."""
            ledger = self.campaign.ledger
            ledger.acquire()
            d = self.declaration
            ledger.write_attempt({'number': 1, 'campaign': d.campaign, 'authority_id': d.authority_id,
                                  'stage': 'model_check', 'maximum_cost': '0.104896', 'rates': d.rates.as_dict(),
                                  'limits': limits_record(d), 'terms': terms_record(d)})
            ledger.write_outcome(1, {'class': 'completed', 'usage': {'input_tokens': 840, 'output_tokens': 118,
                                                                      'inference_geo': 'global'}})
            ledger.write_stage('model_check', 'passed', {'attempt': 1})
            ledger.release()

        # ── the fake provider ────────────────────────────────────────────────────────────────────────────────────
        def provider_client(self, **kwargs):
            return REAL_CLIENT(http_client=httpx.Client(transport=httpx.MockTransport(self.handler)), **kwargs)

        def handler(self, request):
            number = pc.CURRENT_ATTEMPT.get('number')
            ledger = self.campaign.ledger.dir
            body = json.loads(request.content)
            payload = json.loads(body['messages'][0]['content'])
            attempt = json.loads((ledger / f'{number:03d}-attempt.json').read_text()) if number else {}
            send = attempt.get('send', {})
            self.sent.append({'attempt': number, 'send': send.get('id'), 'max_tokens': body['max_tokens'],
                              'relations': 'catalogue' in payload, 'mapping': payload.get('contract') == 'blank-mapping-v3',
                              'key_sent': request.headers.get('x-api-key') == SYNTHETIC_KEY,
                              'attempt_durable': bool(number) and (ledger / f'{number:03d}-attempt.json').exists(),
                              'no_outcome_yet': bool(number) and not (ledger / f'{number:03d}-outcome.json').exists(),
                              'captured_first': bool(number) and (Path(pc.CURRENT_ATTEMPT['evidence_dir'])
                                                                  / 'request.json').exists()})
            if self.transport_error and send.get('id') == self.transport_error:
                raise httpx.ConnectError('synthetic connection reset after the request was written', request=request)
            if self.delay and send.get('id') == self.delay[0]:
                time.sleep(self.delay[1])
            answer = self.answers.get(send.get('id'))
            answer = answer(payload) if callable(answer) else answer
            if answer is None:
                answer = self.default_answer(send, attempt, payload)
            return httpx.Response(200, headers={'request-id': f'req_011SyntheticStage{number:03d}'},
                                  json=message(answer, number=number or 0, **self.shapes.get(send.get('id'), {})))

        def default_answer(self, send, attempt, payload):
            from core import mapping_wire
            from core.models import Encounter
            if payload.get('contract') == 'blank-mapping-v3':
                return mapping_wire.fixture(payload)          # (the app's own offline fixture: keep every field)
            encounter = Encounter.objects.get(pk=attempt['encounter'])
            fields = encounter.template_version.fields
            if send.get('case'):
                case = next(c for c in self.inputs['cases']['cases'] if c['id'] == send['case'])
                selection = st.steps.reference_selection(case, send['path'])
            elif send.get('form') == 'f6a-long-answer':
                # every source unit, once each, for the long-answer field (the narrative repeats sentences, so it is
                # selected by id, never by quote)
                region = 'b/tbl[0]/tr[1]/tc[0]'
                key = next(f['key'] for f in fields if f['locator']['slot'].startswith(region))
                ids = [u['id'] for u in payload['source_units']]
                return {'fields': [{'key': q['key'], 'unit_ids': ids if q['key'] == key else [], 'conflict': False}
                                   for q in payload['questions']]}
            else:
                selection = {}
            answer, units = wire_answer(encounter.notes, fields, payload, selection)
            if units is not None:
                self.assertEqual(units['sent'], units['expected'])
            return answer

        # ── running a stage ──────────────────────────────────────────────────────────────────────────────────────
        def run_stage(self, **kwargs):
            return st.run_stage(self.campaign, self.STAGE, secret=SYNTHETIC_KEY, provenance={'runner_commit': 'offline-test'},
                                database_prefix='test_quillmd_qa_', **kwargs)

        def only(self, *ids):
            """The stage's frozen plan, cut to these sends (in plan order) — for the stop tests."""
            real = st.plan_sends

            def cut(stage, inputs):
                return [s for s in real(stage, inputs) if s.id in ids]
            return patch.object(st, 'plan_sends', side_effect=cut)

        def rows(self):
            return self.campaign.ledger.rows()[1:]            # (after the model_check attempt)

        def stopped(self, fragment, attempts=1):
            ledger = self.campaign.ledger
            self.assertIsNone(ledger.stage_record(self.STAGE, 'passed'))
            failed = ledger.stage_record(self.STAGE, 'failed')
            self.assertIsNotNone(failed)
            self.assertTrue(any(fragment in reason for reason in failed['reasons']), failed['reasons'])
            self.assertEqual(len(self.rows()), attempts)
            self.assertEqual(len(self.sent), attempts)                 # (nothing further, and nothing re-sent)
            self.assertEqual(sorted(os.listdir(self.root / 'ledger')).count('campaign-stop.json'), 0)
            with self.assertRaises(pc.Refused):
                self.campaign.admit(self.STAGE, '0.10', runner_commit='offline-test')
            self.assertEqual(pc.leaked(self.root, SYNTHETIC_KEY, exclude=(self.credential,)), [])
            return failed

        def assert_every_send_was_durable_and_captured_first(self):
            self.assertTrue(self.sent)
            for sent in self.sent:
                self.assertTrue(all(sent[k] for k in ('key_sent', 'attempt_durable', 'no_outcome_yet', 'captured_first')),
                                sent)
            self.assertEqual(len({s['attempt'] for s in self.sent}), len(self.sent))   # (one request per attempt)

    class MappingStageTests(StageTestCase):
        STAGE = 'mapping'

        def test_the_mapping_stage_passes_end_to_end_with_all_evidence(self):
            from core.models import Template
            result = self.run_stage()
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            ledger = self.campaign.ledger
            passed = ledger.stage_record('mapping', 'passed')
            self.assertIsNotNone(passed)
            plan = [s.id for s in st.plan_sends('mapping', self.inputs)]
            self.assertEqual(passed['summary']['plan'], plan)
            rows = self.rows()
            self.assertEqual([a['send']['id'] for a, _ in rows], plan)             # (sent in the fixed order)
            self.assert_every_send_was_durable_and_captured_first()
            self.assertEqual([s['send'] for s in self.sent], plan)
            self.assertEqual([s['max_tokens'] for s in self.sent], [20000] * 8 + [8000] * 2)
            for attempt, outcome in rows:
                with self.subTest(send=attempt['send']['id']):
                    self.assertEqual(outcome['class'], 'completed')
                    self.assertEqual(attempt['pricing_version'], self.declaration.pricing_version('mapping'))
                    self.assertEqual(Decimal(attempt['exposure_bound']), Decimal(attempt['maximum_cost']) * Decimal('1.1'))
                    self.assertEqual(Decimal(attempt['hold']), Decimal(attempt['maximum_cost']) * Decimal('1.5'))
                    self.assertEqual((attempt['terms'], attempt['limits']), (terms_record(self.declaration),
                                                                             limits_record(self.declaration)))
                    self.assertEqual(set(attempt['engine_files']), set(sq.WATCHED_FILES))
                    self.assertEqual(attempt['freeze_manifest_sha256'], self.inputs['freeze']['manifest_sha256'])
                    evidence = self.root / 'evidence' / f'{attempt["number"]:03d}'
                    for name in ('request.json', 'provider-result.json', 'classification.json', 'manifest.json',
                                 'audit-billing.json', 'provider-response.json', 'provider-response.body'):
                        self.assertTrue((evidence / name).is_file(), name)
                    self.assertEqual(outcome['message_source'], 'product_result')
                    self.assertEqual(outcome['provider_response']['request_id'],
                                     f'req_011SyntheticStage{attempt["number"]:03d}')
                    classification = json.loads((evidence / 'classification.json').read_text())
                    self.assertFalse(classification['stops_stage'], classification)
            mapping_rows = [a for a, _ in rows if a['send']['kind'] == 'mapping']
            for attempt in mapping_rows:
                evidence = self.root / 'evidence' / f'{attempt["number"]:03d}'
                for name in ('proposal.json', 'deterministic-fields.json', 'graded.json', 'graded-deterministic.json',
                             'clinician-view.json', 'expressible.json'):
                    self.assertTrue((evidence / name).is_file(), name)
                graded = json.loads((evidence / 'graded.json').read_text())
                self.assertEqual(graded['provenance']['manifest_sha256'], self.inputs['freeze']['manifest_sha256'])
                proposal = json.loads((evidence / 'proposal.json').read_text())
                self.assertIn('unresolved', proposal['review'])
                self.assertEqual(Template.objects.get(pk=attempt['template']).versions.count() >= 2, True)
            f1 = json.loads((self.root / 'evidence' / f'{mapping_rows[0]["number"]:03d}' / 'classification.json').read_text())
            self.assertEqual(f1['verdict']['fields']['f1.A2'], 'wrong')            # (the kept leaked label: recorded)
            f5 = next(a for a in mapping_rows if a['send']['form'] == 'f5-negative-controls')
            f5c = json.loads((self.root / 'evidence' / f'{f5["number"]:03d}' / 'classification.json').read_text())
            self.assertEqual(f5c['protected_areas_left_answerable'], ['f5.C2'])     # (engine defect, N8: recorded)
            encounters = [a for a, _ in rows if a['send']['path'] == 'mapping_encounter']
            self.assertEqual([a['send']['form'] for a in encounters], ['f6a-long-answer', 'f6b-admin-missing'])
            for attempt in encounters:
                self.assertEqual(attempt['confirmation'], 'assisted')              # (the fixture leaves records open)
                evidence = self.root / 'evidence' / f'{attempt["number"]:03d}'
                export = json.loads((evidence / 'export.json').read_text())
                self.assertTrue(export['workflow_success'], export)
                self.assertEqual((export['read_back']['passed'], export['read_back']['problems']), (True, []))
                self.assertEqual(export['sha256'], pc.file_sha256(evidence / 'export.docx'))
            f6a = json.loads((self.root / 'evidence' / f'{encounters[0]["number"]:03d}' / 'classification.json').read_text())
            f6b = json.loads((self.root / 'evidence' / f'{encounters[1]["number"]:03d}' / 'classification.json').read_text())
            self.assertEqual(f6b['destinations_changed'], [])
            self.assertEqual(set(f6b['verdict']['fields'].values()), {'held_correct'})
            self.assertIn(f6a['long_answer']['adopted'], (True, False))
            if f6a['long_answer']['adopted']:
                self.assertTrue(f6a['long_answer']['whole'], f6a['long_answer'])
            with self.assertRaises(pc.Refused):
                self.campaign.admit('mapping', '0.10', runner_commit='offline-test')   # (a passed stage never re-runs)

        def test_a_harmful_proposal_stops_the_stage_and_nothing_further_is_sent(self):
            # f1: a text field added ON the section heading (a not_an_answer control): a wrong destination left un-held
            self.answers['mapping:f1-guidance-confirmation'] = lambda payload: addition(
                payload, 'b/p[0]', 'text', 'Section 3: Public protection')
            result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('mapping:f1-guidance-confirmation')
            record = failed['summary']['sends'][0]
            self.assertEqual(record['verdict']['unsafe'], ['wrong_destination'])
            self.assertEqual(len(failed['summary']['not_sent']), 9)

        def test_a_wrong_served_model_on_a_mapping_send_stops_the_stage(self):
            self.shapes['mapping:f1-guidance-confirmation'] = {'model': 'claude-sonnet-4-6'}
            with self.only('mapping:f1-guidance-confirmation', 'mapping:f2-leave-checkboxes'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('mapping:f1-guidance-confirmation')
            self.assertIn('validator_failure', failed['summary']['sends'][0]['verdict']['contract'])
            self.assertEqual(failed['summary']['not_sent'], ['mapping:f2-leave-checkboxes'])

    class NotesStageTests(StageTestCase):
        STAGE = 'ordinary_notes'

        def test_the_notes_stage_passes_end_to_end_in_its_order(self):
            result = self.run_stage()
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            plan = st.plan_sends('ordinary_notes', self.inputs)
            rows = self.rows()
            self.assertEqual([a['send']['id'] for a, _ in rows], [s.id for s in plan])
            self.assert_every_send_was_durable_and_captured_first()
            for sent, send in zip(self.sent, plan):
                with self.subTest(send=send.id):
                    relations = send.path == 'field_relations'
                    self.assertEqual((sent['relations'], sent['max_tokens']), (relations, 20000 if relations else 8000))
            classes = {}
            for (attempt, outcome), send in zip(rows, plan):
                with self.subTest(send=send.id):
                    relations = send.path == 'field_relations'
                    self.assertEqual(outcome['class'], 'completed')
                    case = next(c for c in self.inputs['cases']['cases'] if c['id'] == send.case)
                    frozen = Decimal(case['cost_bound_usd'][send.path]['provider_cost_max'])
                    self.assertEqual(attempt['amendment'], self.amendment.record())
                    if relations:
                        # (the amended version; a maximum the same compiler recomputed for the keyed request)
                        self.assertEqual(attempt['pricing_version'], RELATIONS_V2)
                        self.assertGreater(Decimal(attempt['maximum_cost']), frozen)
                    else:
                        self.assertEqual(attempt['pricing_version'], self.declaration.pricing_version(send.pricing_key))
                        self.assertEqual(Decimal(attempt['maximum_cost']), frozen)
                    self.assertEqual(attempt['terms'], terms_record(self.declaration))     # (the pinned terms, unchanged)
                    evidence = self.root / 'evidence' / f'{attempt["number"]:03d}'
                    for name in ('raw-selection.json', 'answers-adopted.json', 'answers-reviewed.json', 'replay.json',
                                 'export.docx', 'export.json', 'classification.json', 'manifest.json',
                                 'provider-response.json', 'provider-response.body'):
                        self.assertTrue((evidence / name).is_file(), name)
                    self.assertEqual((outcome['message_source'], outcome['provider_response']['message_id']),
                                     ('product_result', f'msg_01SyntheticStage{attempt["number"]:012d}'))
                    replayed = json.loads((evidence / 'replay.json').read_text())
                    self.assertEqual(replayed['provenance']['manifest_sha256'], self.inputs['freeze']['manifest_sha256'])
                    classification = json.loads((evidence / 'classification.json').read_text())
                    self.assertFalse(classification['stops_stage'], classification)
                    self.assertEqual(classification['verdict']['unsafe'], [])
                    export = json.loads((evidence / 'export.json').read_text())
                    self.assertTrue(export['workflow_success'])
                    self.assertEqual((export['read_back']['passed'], export['read_back']['problems']), (True, []))
                    for key, outcome_class in classification['verdict']['fields'].items():
                        classes[outcome_class] = classes.get(outcome_class, 0) + 1
            self.assertIn('supported_correct', classes)
            self.assertIn('over_held', classes)                                    # (the documented V over-holds)
            self.assertIsNotNone(self.campaign.ledger.stage_record('ordinary_notes', 'passed'))

        def test_an_unsafe_default_adoption_stops_the_stage(self):
            # N13 on the DEFAULT path, the documented exposure: a model that does not set conflict gets 'none.' adopted
            # against 'The patient is suicidal.' — a contradiction adopted, which stops the stage
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == 'N13')
            exposure = next(sim for sim in case['adversarial_simulations']
                            if sim['name'] == 'default_label_after_statement_no_conflict')

            def answer(payload):
                from core.models import Encounter
                encounter = Encounter.objects.latest('created_at')
                return wire_answer(encounter.notes, encounter.template_version.fields, payload,
                                                 exposure['selection'])[0]
            self.answers['notes:N13:default'] = answer
            with self.only('notes:N13:default', 'notes:N16:default'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('notes:N13:default')
            record = failed['summary']['sends'][0]
            self.assertEqual(record['verdict']['fields']['v3_1'], 'contradiction_adopted')
            self.assertEqual(record['verdict']['unsafe'], ['contradiction_adopted'])
            self.assertEqual(failed['summary']['not_sent'], ['notes:N16:default'])

        def test_an_unsafe_relations_adoption_is_veto_evidence_and_the_stage_goes_on(self):
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == 'N13')
            veto = next(sim for sim in case['adversarial_simulations']
                        if sim['purpose'] == 'veto_qa' and sim['path'] in ('field_relations', 'both'))

            def answer(payload):
                from core.models import Encounter
                encounter = Encounter.objects.latest('created_at')
                return wire_answer(encounter.notes, encounter.template_version.fields, payload,
                                                 veto['selection'])[0]
            self.answers['notes:N13:field_relations'] = answer
            with self.only('notes:N13:field_relations', 'notes:N14:field_relations'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            self.assertEqual([s['send'] for s in self.sent], ['notes:N13:field_relations', 'notes:N14:field_relations'])
            summary = self.campaign.ledger.stage_record('ordinary_notes', 'passed')['summary']
            self.assertEqual([v['send'] for v in summary['veto_evidence']], ['notes:N13:field_relations'])
            self.assertIn('contradiction_adopted', summary['veto_evidence'][0]['unsafe'])
            first = summary['sends'][0]
            self.assertEqual((first['recorded_as'], first['stops_stage']), ('veto_evidence', False))

        def selection_answer(self, case_id, changes):
            """The provider body for `case_id`'s reference selection with `changes` ({key: selection}) applied."""
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == case_id)
            selection = {**st.steps.reference_selection(case, 'default'), **changes}

            def answer(payload):
                from core.models import Encounter
                encounter = Encounter.objects.latest('created_at')
                return wire_answer(encounter.notes, encounter.template_version.fields, payload,
                                                 selection)[0]
            return answer

        def held_v3_9(self, chosen, outcome, verdict):
            """N06 sent once with Plan's selection replaced by `chosen`: the stage passes, the application holds Plan, the
            frozen replay gives `verdict` and the field is classified `outcome`."""
            self.answers['notes:N06:default'] = self.selection_answer('N06', {'v3_9': chosen})
            with self.only('notes:N06:default'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            (attempt, _), = self.rows()
            evidence = self.root / 'evidence' / f'{attempt["number"]:03d}'
            replayed = json.loads((evidence / 'replay.json').read_text())['responses']['N06']['default']
            self.assertEqual((replayed['v3_9']['status'], replayed['v3_9']['verdict']), ('held', verdict))
            classification = json.loads((evidence / 'classification.json').read_text())
            self.assertEqual(classification['verdict']['fields']['v3_9'], outcome)
            self.assertEqual(classification['fields']['v3_9']['replay_verdict'], verdict)
            self.assertEqual(classification['verdict']['unsafe'], [])
            return classification

        def test_a_held_forbidden_selection_is_a_caught_model_error_not_an_over_hold(self):
            # Refutation F1, end to end: N06's Plan gets the frozen FORBIDDEN two-unit selection (the tolerance sentence
            # with the plan); the application holds it and the frozen replay says 'caught' — a model error the
            # application caught (README scoring step 4), never an application over-hold.
            case = next(c for c in self.inputs['cases']['cases'] if c['id'] == 'N06')
            forbidden = case['fields']['v3_9']['raw_model_expectation']['forbidden'][0]
            classification = self.held_v3_9({'units': forbidden['units'], 'conflict': forbidden['conflict']},
                                             'held_correct', 'caught')
            self.assertEqual(classification['fields']['v3_9']['attribution'], 'model_error_caught')

        def test_a_held_unlisted_selection_is_left_for_adjudication(self):
            # (README scoring step 2: an unlisted response is adjudicated by hand, never auto-scored)
            classification = self.held_v3_9({'units': ['She tolerated the procedure well.'], 'conflict': False},
                                             'held_unadjudicated', 'adjudicate_by_hand')
            self.assertEqual(classification['fields']['v3_9']['attribution'], 'adjudicate_by_hand')

        def defective_export(self, send, key, value):
            """`send` with a defective writer (core.v3_mapping.fill_answers patched to also write `value` into `key`): the
            frozen check passes the export (it never reads a mark or a held field); the stage's own read-back fails it,
            and the stage stops."""
            from core import v3_mapping
            real = v3_mapping.fill_answers

            def defective(fields, answers):
                return {**real(fields, answers), key: value}
            with self.only(send), patch.object(v3_mapping, 'fill_answers', side_effect=defective):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped(send)
            record = failed['summary']['sends'][0]
            self.assertEqual((record['verdict']['contract'], record['verdict']['unsafe']),
                             (['export_verification_failed'], []))
            evidence = self.root / 'evidence' / f'{record["attempt"]:03d}'
            export = json.loads((evidence / 'export.json').read_text())
            self.assertTrue(export['workflow_success'])                          # (the frozen check: vacuous here)
            self.assertFalse(export['read_back']['passed'])
            self.assertIn(key, {p['where'] for p in export['read_back']['problems']})

        def test_an_exported_mark_that_is_not_the_reviewed_answer_stops_the_stage(self):
            # Refutation EXPORT-CHECK-DOES-NOT-READ (a): N04's reviewed Smoker 'No' exported as 'Yes'
            self.defective_export('notes:N04:default', 'v3_6', 'Yes')

        def test_a_held_field_the_export_fills_stops_the_stage(self):
            # Refutation EXPORT-CHECK-DOES-NOT-READ (b): N11's HELD allergy field (left blank at review) exported with the
            # corrected-away 'penicillin.'
            self.defective_export('notes:N11:default', 'v3_2', 'penicillin.')

        def test_a_response_the_product_cannot_settle_is_retained_as_received(self):
            # Refutation RAW-RESPONSE-LOST-200: HTTP 200, a normal Sonnet 5 message, but a cache-write split that does
            # not reconcile — the product refuses to settle it (reconciliation) and stores no result. The response is
            # retained as received: its id, request-id, served model, stop reason and usage; the money stays at the
            # bound.
            self.shapes['notes:N01:default'] = {'cache_written': 0, 'cache_split': (7, 0)}
            with self.only('notes:N01:default', 'notes:N02:default'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            self.stopped('notes:N01:default')
            (attempt, outcome), = self.rows()
            number = attempt['number']
            self.assertEqual((outcome['class'], outcome['raw_result_sha256']), ('reconciliation', None))
            evidence = self.root / 'evidence' / f'{number:03d}'
            self.assertFalse((evidence / 'provider-result.json').exists())      # (the product kept nothing)
            record = pc.received_response(evidence)
            self.assertEqual((record['status_code'], record['request_id'], record['body_json']['id']),
                             (200, f'req_011SyntheticStage{number:03d}', f'msg_01SyntheticStage{number:012d}'))
            self.assertEqual((outcome['message_source'], outcome['served_model'], outcome['stop_reason']),
                             ('provider_response', 'claude-sonnet-5', 'end_turn'))
            self.assertEqual(outcome['usage']['cache_creation'], {'ephemeral_5m_input_tokens': 7,
                                                                  'ephemeral_1h_input_tokens': 0})
            self.assertEqual(outcome['provider_response']['request_id'], f'req_011SyntheticStage{number:03d}')
            self.assertEqual(Decimal(outcome['exposure']), Decimal(attempt['maximum_cost']) * Decimal('1.1'))
            manifest = json.loads((evidence / 'manifest.json').read_text())
            self.assertEqual(manifest['evidence']['provider-response.json'], pc.file_sha256(evidence / 'provider-response.json'))

        def test_a_response_that_was_not_retained_stops_the_stage(self):
            # the provider answered and the product settled, but no response was retained as received: the declared
            # evidence is incomplete — a contract stop, never a pass
            with self.only('notes:N01:default', 'notes:N02:default'), \
                    patch.object(pc, 'received_response', return_value=None):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('notes:N01:default')
            self.assertIn('response_not_captured', failed['summary']['sends'][0]['verdict']['contract'])

        def stop_class(self, fragment, **shape):
            self.shapes['notes:N01:default'] = shape
            with self.only('notes:N01:default', 'notes:N02:default'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            return self.stopped(fragment)

        def test_every_contract_stop_class_stops_the_stage(self):
            cases = (('wrong_served_model', {'model': 'claude-sonnet-4-6'}),
                     ('stop_reason_not_end_turn', {'stop_reason': 'max_tokens'}),
                     ('output_over_70_percent', {'output_tokens': 5600}),
                     ('metered_us_while_unset', {'geo': 'us'}))
            for code, shape in cases:
                with self.subTest(code=code):
                    self.fresh_campaign()
                    failed = self.stop_class('notes:N01:default', **shape)
                    self.assertIn(code, failed['summary']['sends'][0]['verdict']['contract']
                                  + failed['summary']['sends'][0]['verdict']['unsafe'])

        def test_a_lost_response_stops_the_stage_counts_the_maximum_and_is_never_resent(self):
            self.transport_error = 'notes:N01:default'
            with self.only('notes:N01:default', 'notes:N02:default'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            self.stopped('notes:N01:default')
            (attempt, outcome), = self.rows()
            self.assertEqual(outcome['class'], 'reconciliation')
            self.assertEqual(Decimal(outcome['exposure']), Decimal(attempt['maximum_cost']) * Decimal('1.1'))

        def test_the_per_send_deadline_abandons_a_send_and_stops_the_stage(self):
            self.delay = ('notes:N01:default', 3)
            with self.only('notes:N01:default', 'notes:N02:default'):
                result = self.run_stage(deadline=1)
            self.assertEqual(result['verdict'], 'FAIL')
            self.stopped('did not return within 1 s')
            (attempt, outcome), = self.rows()
            self.assertIn(outcome['class'], ('uncertain', 'reconciliation'))
            self.assertEqual(Decimal(pc.exposure(attempt, outcome)), Decimal(attempt['maximum_cost']) * Decimal('1.1'))

        def test_a_leaked_credential_in_the_evidence_is_a_campaign_stop(self):
            from core.management.commands import audit_billing
            real = audit_billing.audit_report

            def plant():
                (self.root / 'evidence' / '002' / 'pasted.log').write_text('pasted by mistake: ' + SYNTHETIC_KEY)
                return real()
            with self.only('notes:N01:default', 'notes:N02:default'), \
                    patch.object(audit_billing, 'audit_report', side_effect=plant):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            self.assertIsNotNone(self.campaign.ledger.campaign_stop())
            self.assertEqual(len(self.sent), 1)
            for stage in ('mapping', 'ordinary_notes'):
                with self.assertRaises(pc.Refused):
                    self.campaign.admit(stage, '0.10', runner_commit='offline-test')

        def test_admission_near_the_limit_refuses_the_next_send_before_it_is_written(self):
            from core.models import Job, Reservation
            limit = Decimal('0.20')
            self.fresh_campaign(stages=tuple(dataclasses.replace(s, limit=limit) if s.id == 'ordinary_notes' else s
                                             for s in self.declared.stages))
            # N01 costs 40,000 input tokens ($0.083): the next send's bound (~$0.1176) no longer fits $0.20
            self.shapes['notes:N01:default'] = {'input_tokens': 40000}
            with self.only('notes:N01:default', 'notes:N02:default'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('stopped before its attempt was written')
            self.assertTrue(any('limit' in reason for reason in failed['reasons']), failed['reasons'])
            self.assertEqual(failed['summary']['not_sent'], ['notes:N02:default'])
            self.assertFalse(Job.objects.filter(state='queued').exists())
            self.assertFalse(Reservation.objects.filter(state='held').exists())
            self.assertLessEqual(self.campaign.totals('ordinary_notes')['exposure'], limit)
            # (refused on the PLANNED maximum before anything was created for it: no form, no encounter, no job)
            from core.models import Template
            self.assertFalse(Template.objects.filter(name__contains='N02').exists())

        def test_the_jobs_own_maximum_is_admitted_whatever_the_plan_said(self):
            # the plan under-prices every send tenfold; the job's own reserved maximum ($0.1168, bound $0.1285) does
            # not fit a $0.05 stage: refused before the attempt, the queued job cancelled, nothing sent
            from core.models import Job, Reservation
            real = st.price_sends

            def underpriced(*args, **kwargs):
                return {k: {**v, 'maximum_cost': v['maximum_cost'] / 10} for k, v in real(*args, **kwargs).items()}
            self.fresh_campaign(stages=tuple(dataclasses.replace(s, limit=Decimal('0.05')) if s.id == 'ordinary_notes'
                                             else s for s in self.declared.stages))
            with self.only('notes:N01:default'), patch.object(st, 'price_sends', side_effect=underpriced):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('stopped before its attempt was written', attempts=0)
            self.assertTrue(any('limit' in reason for reason in failed['reasons']), failed['reasons'])
            job = Job.objects.get(kind='generation')
            self.assertEqual(job.state, 'cancelled')
            self.assertFalse(Reservation.objects.filter(state='held').exists())

        def test_a_job_priced_at_another_version_is_refused_before_its_attempt(self):
            # after the plan was priced, the application prices generation at another version: the page's quote is
            # refused before Generate (nothing queued, nothing sent)
            from core import generation
            real_price, real_configuration, tweaked = st.price_sends, generation.configuration, []

            def priced_then_tweaked(*args, **kwargs):
                priced = real_price(*args, **kwargs)
                tweaked.append(True)
                return priced

            def configuration(fields=None):
                config = real_configuration(fields)
                return {**config, 'pricing_version': 'configured-v1:' + 'e' * 64} if tweaked else config
            with self.only('notes:N01:default'), patch.object(st, 'price_sends', side_effect=priced_then_tweaked), \
                    patch.object(generation, 'configuration', side_effect=configuration):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('not the declared ordinary_notes version', attempts=0)
            self.assertEqual(failed['summary']['not_sent'], ['notes:N01:default'])

        def test_a_generation_that_does_not_queue_exactly_one_job_is_refused_unsent(self):
            # Generate queues something other than one generation job (here: a second queued generation, as a batch
            # would; or nothing at all): refused before any attempt, whatever was queued is cancelled, nothing is sent
            from core import views
            from core.models import Encounter, Job
            real = views.enqueue

            def not_a_generation(encounter, user, **kwargs):
                job = real(encounter, user, **kwargs)
                twin = Encounter.objects.create(department=encounter.department, patient=encounter.patient,
                                                template_version=encounter.template_version, created_by=user,
                                                notes=encounter.notes, service_date=encounter.service_date)
                real(twin, user, config=kwargs.get('config'))
                return job

            def nothing(encounter, user, **kwargs):
                from django.core.exceptions import ValidationError
                raise ValidationError('synthetic: nothing was queued')
            for name, side_effect in (('two generations', not_a_generation), ('nothing', nothing)):
                with self.subTest(name=name):
                    self.fresh_campaign()
                    with self.only('notes:N01:default'), patch.object(views, 'enqueue', side_effect=side_effect):
                        result = self.run_stage()
                    self.assertEqual(result['verdict'], 'FAIL')
                    self.stopped('exactly one generation job', attempts=0)
                    self.assertFalse(Job.objects.filter(state='queued').exists())

        def test_the_ledger_is_reconciled_after_every_send(self):
            # the provider reports usage above the job's maximum: the product cannot settle it (reconciliation), and the
            # exposure counted at the reported cost is past the stage limit that admitted the attempt — the stage stops
            # with the reconciliation named
            self.fresh_campaign(stages=tuple(dataclasses.replace(s, limit=Decimal('0.13')) if s.id == 'ordinary_notes'
                                             else s for s in self.declared.stages))
            self.shapes['notes:N01:default'] = {'input_tokens': 70000}
            with self.only('notes:N01:default', 'notes:N02:default'):
                result = self.run_stage()
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.stopped('notes:N01:default')
            findings = failed['summary']['sends'][0]['findings']
            self.assertTrue(any(f['code'] == 'reconciliation' and 'past a limit in force' in f['why'] for f in findings),
                            findings)

        def test_the_guard_is_on(self):
            network_guard.positive_control(self)

    class NotesRemainderTests(StageTestCase):
        """REMAINDER, end to end: the live failure's shape (15 sends made, the six relations sends not), reopened for a
        repair this checkout contains, sends ONLY those six — under the amendment — and never one already made."""
        STAGE = 'ordinary_notes'

        def head(self):
            import subprocess
            done = subprocess.run(['git', '-C', str(REPOSITORY), 'rev-parse', 'HEAD'], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0)
            return done.stdout.strip()

        def failed_and_reopened(self, not_sent=UNSENT, stopper='notes:N02:field_relations'):
            """Attempts 2..: the plan's sends minus `not_sent`, each completed, with the per-send rows Run.finish writes
            (`stopper`, if made, stopped the stage — the live shape: attempt 17 there); failure 1 lists `not_sent`;
            reopening 1 names this checkout's HEAD as the repair."""
            from .test_provider_campaign import attempt, limits_record, usage
            plan = [s.id for s in st.plan_sends('ordinary_notes', self.inputs)]
            made = [send for send in plan if send not in not_sent]
            ledger = self.campaign.ledger
            ledger.acquire()
            d = self.declaration
            for number, send in enumerate(made, 2):
                record = attempt(number, 'ordinary_notes', '0.2332', campaign=d.campaign, authority=d.authority_id,
                                 limits=limits_record(d), terms=terms_record(d))
                record['send'] = {'id': send}
                ledger.write_attempt(record)
                ledger.write_outcome(number, {'class': 'completed', 'usage': usage(input_tokens=2000, output_tokens=300)})
            rows = [{'send': {'id': send}, 'attempt': number, 'stops_stage': send == stopper,
                     'recorded_as': 'contract' if send == stopper else None} for number, send in enumerate(made, 2)]
            ledger.write_stage('ordinary_notes', 'failed', {'reasons': ['synthetic'], 'summary': {
                'plan': plan, 'not_sent': list(not_sent), 'sends': rows}})
            head = self.head()
            ledger.write_reopen('ordinary_notes', 1, {'ledger_attempts': len(ledger.rows()), 'repair_commit': head,
                                                      'runner_commit': head})
            ledger.release()
            return len(made) + 1, head

        def test_a_reopened_stage_sends_only_what_its_failure_did_not_send_and_cannot_pass(self):
            # the live shape: N02:field_relations stopped the stage and is never sent again, so the six complete the
            # stage's evidence and the stage is decided FAILED, naming that stop — never passed (refutation F1)
            before, head = self.failed_and_reopened()
            result = st.run_stage(self.campaign, self.STAGE, secret=SYNTHETIC_KEY, provenance={'runner_commit': head},
                                  database_prefix='test_quillmd_qa_')
            self.assertEqual(result['verdict'], 'FAIL', result['reasons'])
            self.assertEqual(result['reasons'], [result['reasons'][0]])
            self.assertIn('cannot pass', result['reasons'][0])
            self.assertIn('notes:N02:field_relations', result['reasons'][0])
            self.assertEqual([s['send'] for s in self.sent], UNSENT)
            self.assert_every_send_was_durable_and_captured_first()
            rows = self.campaign.ledger.rows()
            made = [a['send']['id'] for a, _ in rows[1:before]]
            new = rows[before:]
            self.assertEqual([a['send']['id'] for a, _ in new], UNSENT)
            self.assertFalse(set(made) & set(UNSENT))                              # (nothing made is ever sent again)
            self.assertEqual(len(made) + len(UNSENT), 21)
            for attempt, outcome in new:
                with self.subTest(send=attempt['send']['id']):
                    self.assertEqual((outcome['class'], attempt['pricing_version'], attempt['amendment']),
                                     ('completed', RELATIONS_V2, self.amendment.record()))
                    self.assertEqual(attempt['runner_commit'], head)
            self.assertIsNone(self.campaign.ledger.stage_record('ordinary_notes', 'passed'))
            failed = self.campaign.ledger.stage_record('ordinary_notes', 'failed')
            self.assertEqual(failed['number'], 2)
            self.assertEqual((failed['summary']['plan'], failed['summary']['not_sent']), (UNSENT, []))
            self.assertEqual([r['stops_stage'] for r in failed['summary']['sends']], [False] * 6)
            self.assertEqual([(e['send'], e['attempt']) for e in failed['summary']['earlier_stops']],
                             [('notes:N02:field_relations', before)])            # (the last one made)
            self.assertEqual(failed['summary']['remainder']['sends'], UNSENT)
            self.assertEqual(failed['summary']['remainder']['failure'], 1)
            self.assertEqual(failed['summary']['amendment'], self.amendment.record())
            self.assertFalse(failed['summary']['frozen_walk']['valid'])          # (refutation F2-FROZEN-WALK)
            with self.assertRaises(pc.Refused) as caught:                           # (nothing is left to send)
                st.pending_sends(self.campaign, self.STAGE, st.plan_sends(self.STAGE, self.inputs))
            self.assertIn('no remainder', str(caught.exception))

        def test_a_remainder_after_a_stop_before_any_attempt_passes_the_stage(self):
            # nothing was ever sent for N02:field_relations (it stopped before its attempt was written): it is in the
            # remainder, and seven clean sends complete the plan with every send made once — a pass that was earned
            relations = ['notes:N02:field_relations'] + UNSENT
            before, head = self.failed_and_reopened(not_sent=relations)
            result = st.run_stage(self.campaign, self.STAGE, secret=SYNTHETIC_KEY, provenance={'runner_commit': head},
                                  database_prefix='test_quillmd_qa_')
            self.assertEqual(result['verdict'], 'PASS', result['reasons'])
            self.assertEqual([s['send'] for s in self.sent], relations)
            passed = self.campaign.ledger.stage_record('ordinary_notes', 'passed')
            self.assertEqual((passed['summary']['plan'], passed['summary']['earlier_stops']), (relations, []))
            made = sorted(a['send']['id'] for a, _ in self.campaign.ledger.rows() if a['stage'] == 'ordinary_notes')
            self.assertEqual(made, sorted(s.id for s in st.plan_sends(self.STAGE, self.inputs)))

        def test_without_the_amendment_the_remainder_refuses_before_anything(self):
            from core.models import Job, Template
            self.fresh_campaign(amended=False)
            before, head = self.failed_and_reopened()
            with self.assertRaises(pc.Refused) as caught:
                st.run_stage(self.campaign, self.STAGE, secret=SYNTHETIC_KEY, provenance={'runner_commit': head},
                             database_prefix='test_quillmd_qa_')
            self.assertIn('not the declared ordinary_notes_field_relations', str(caught.exception))
            self.assertEqual((self.sent, len(self.campaign.ledger.rows()), Job.objects.count(),
                              Template.objects.count()), ([], before, 0, 0))

        def test_a_job_maximum_that_is_not_the_amended_plans_is_refused_before_its_attempt(self):
            # the plan's recomputed maximum (the one fitted to the limits left) differs from the job's own by $0.000001:
            # the job is cancelled unsent before its attempt is written
            from core.models import Job, Reservation
            before, head = self.failed_and_reopened()
            real = st.price_sends

            def drifted(*args, **kwargs):
                return {k: {**v, 'maximum_cost': v['maximum_cost'] + Decimal('0.000001') if v['amended']
                            else v['maximum_cost']} for k, v in real(*args, **kwargs).items()}
            with patch.object(st, 'price_sends', side_effect=drifted):
                result = st.run_stage(self.campaign, self.STAGE, secret=SYNTHETIC_KEY,
                                      provenance={'runner_commit': head}, database_prefix='test_quillmd_qa_')
            self.assertEqual(result['verdict'], 'FAIL')
            self.assertEqual(self.sent, [])
            self.assertEqual(len(self.campaign.ledger.rows()), before)
            failed = self.campaign.ledger.stage_record('ordinary_notes', 'failed')
            self.assertTrue(any("is not the amended plan's" in reason for reason in failed['reasons']), failed['reasons'])
            self.assertEqual(failed['summary']['not_sent'], UNSENT)
            self.assertEqual(Job.objects.get(kind='generation').state, 'cancelled')
            self.assertFalse(Reservation.objects.filter(state='held').exists())

        def test_a_relations_quote_priced_at_another_version_is_refused_before_its_attempt(self):
            # after the plan was priced, the application prices the relations quote at another version: refused before
            # Generate — nothing queued, nothing sent
            from core import generation
            from core.models import Job
            before, head = self.failed_and_reopened()
            real_price, real_configuration, tweaked = st.price_sends, generation.configuration, []

            def priced_then_tweaked(*args, **kwargs):
                priced = real_price(*args, **kwargs)
                tweaked.append(True)
                return priced

            def configuration(fields=None):
                config = real_configuration(fields)
                return ({**config, 'pricing_version': 'configured-v1:' + 'e' * 64}
                        if tweaked and config.get('ordinary_field_contract') else config)
            with patch.object(st, 'price_sends', side_effect=priced_then_tweaked), \
                    patch.object(generation, 'configuration', side_effect=configuration):
                result = st.run_stage(self.campaign, self.STAGE, secret=SYNTHETIC_KEY,
                                      provenance={'runner_commit': head}, database_prefix='test_quillmd_qa_')
            self.assertEqual(result['verdict'], 'FAIL')
            failed = self.campaign.ledger.stage_record('ordinary_notes', 'failed')
            self.assertTrue(any('not the amended ordinary_notes_field_relations version' in reason
                                for reason in failed['reasons']), failed['reasons'])
            self.assertEqual((self.sent, len(self.campaign.ledger.rows())), ([], before))
            self.assertFalse(Job.objects.filter(state='queued').exists())

    class StagePlanTests(StageTestCase):
        STAGE = 'mapping'

        def test_the_plan_report_is_priced_offline_without_the_credential(self):
            with patch.object(pc, 'load_credential', side_effect=AssertionError('the credential was read')):
                for stage, count in (('mapping', 10), ('ordinary_notes', 21)):
                    with self.subTest(stage=stage), override_settings(**STAGE_SETTINGS[stage]), \
                            patch.dict(os.environ, st.STAGE_FLAGS[stage]):
                        scratch = pc.private_directory(self.root / 'tmp' / f'plan-{stage}')
                        report = st.plan_report(stage, self.declaration, self.root, scratch,
                                                self.amendment if stage == 'ordinary_notes' else None)
                        self.assertEqual([row['id'] for row in report['order']],
                                         [s.id for s in st.plan_sends(stage, self.inputs)])
                        self.assertEqual(report['sends'], count)
                        self.assertTrue(report['worst_case_fits'])
                        self.assertTrue(report['requires_met'])
                        self.assertEqual(report['total_exposure'], '0.00286')
                        self.assertEqual(Decimal(report['stage_remaining']),
                                         {'mapping': Decimal('25.00'), 'ordinary_notes': Decimal('10.00')}[stage])
            self.assertEqual(len(self.campaign.ledger.rows()), 1)                   # (nothing was written)
