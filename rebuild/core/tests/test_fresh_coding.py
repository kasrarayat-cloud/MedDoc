"""Offline fresh-note controls. Provider responses below are constructed controls.

The source is the retained synthetic failure, never a hand-corrected answer.
No fixture result is represented as a prediction or a native approval.
"""
from copy import deepcopy
from datetime import date, datetime, timezone as dt_timezone, timedelta
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import (coding_dispatch, coding_engine, coding_output, coding_service,
                  corti_coding, corti_prediction, corti_semantics, testing_authority)
from core.coding_terminology import parse_reference
from core.corti_response import CatalogRelease, DatedTerminology
from core.models import CodingDecision, CodingRun, Membership
from core.tests.test_coding_output_live import ReferenceMixin, bind_request
from core.tests.test_corti_workflow import CortiWorkflowTests, FIXTURE, STORAGES

NOTE = (Path(__file__).parent / 'fixtures/nadia/source.txt').read_bytes().decode()
BUNDLE = Path(__file__).parents[2] / 'ops/fixtures/corti_office_time_output_reference.json'
LEGACY = Path(__file__).parents[2] / 'ops/fixtures/corti_rowan_output_reference.json'
ROWAN = json.loads((Path(__file__).parent / 'fixtures/rowan_semantic_retained.json').read_text())['notes']
ACTOR = UUID('e1a20625-455d-4603-a874-794327b19d10')


def context(notes=NOTE):
    facts = corti_semantics.office_time_facts(notes)['facts']
    values = {fact['key']: fact['value'] for fact in facts}
    return {**coding_service.CONTEXT_DEFAULTS, **{key: values.get(key) for key in
        ('setting', 'patient_status', 'em_basis', 'time_same_day', 'time_qualified_clinician',
         'time_excludes_separately_reported')}, 'time_minutes': str(values.get('time_minutes', '')),
        'time_evidence': next((fact['quote'] for fact in facts if fact['key'] == 'time_minutes'), '')}


class FreshTimeSemanticsTests(SimpleTestCase):
    def test_consultation_location_and_episode_minutes_are_distinct_from_service_time(self):
        support = corti_semantics.office_time_facts(NOTE)
        self.assertEqual(support['status'], 'documented', support['blockers'])
        facts = {fact['key']: fact for fact in support['facts']}
        self.assertEqual(facts['time_minutes']['value'], 36)
        self.assertNotIn('15 minutes', facts['time_minutes']['quote'])
        self.assertEqual(facts['setting']['value'], 'outpatient_office')
        self.assertEqual(corti_semantics.office_service_eligibility(NOTE, date(2026, 10, 17)), [])
        self.assertEqual(corti_semantics.confirmed_time_context(context(), NOTE, support['facts']), [])

    def test_clinical_service_and_full_source_remain_separate_from_exact_time_quote(self):
        changes = [
            NOTE + '\r\nActual physician time was 15 minutes.',
            NOTE + '\r\nThe office consultation was not performed today.',
            NOTE + '\r\nDate of service: 2026-10-18',
            NOTE + '\r\nCorrection: the physician spent 12 minutes today, not 36.',
            NOTE + '\r\nThe appointment was cancelled. No visit occurred today.',
            NOTE.replace('obtaining history, performing the examination, ', ''),
        ]
        for changed in changes:
            with self.subTest(changed=changed[-100:]):
                self.assertTrue(corti_semantics.office_service_eligibility(changed, date(2026, 10, 17)))
        for key, value in [('time_minutes', '15'), ('patient_status', 'new'), ('time_same_day', False),
                           ('time_qualified_clinician', False), ('time_excludes_separately_reported', False),
                           ('time_evidence', 'Episodes last about 15 minutes.')]:
            with self.subTest(key=key):
                self.assertTrue(corti_semantics.confirmed_time_context({**context(), key: value}, NOTE,
                    corti_semantics.office_time_facts(NOTE)['facts']))

    def test_explanation_uses_exact_denial_instead_of_missingness_claim(self):
        concept = {'term': 'Nausea', 'index_terms': ['Nausea'],
                   'evidence': 'There has also been intermittent nausea for three days.'}
        explanation = coding_engine.source_explanation(NOTE, concept,
            {'path': ['Nausea(without vomiting)']})
        self.assertIn('The patient denies vomiting', explanation)
        self.assertNotIn('no vomiting mentioned', explanation)
        self.assertNotIn('persistent vomiting', explanation)

    def test_only_supported_selected_symptoms_cross_the_official_routes(self):
        # Reduced official route shapes, explicitly a unit reference rather than
        # a claim that an entire dated release was imported into this test.
        codes={'R10.11':'Right upper quadrant pain','R11.0':'Nausea'}
        parsed=parse_reference('''<ICD10CM.index><version>2027</version><letter>
          <mainTerm><title>Pain(s)</title><term><title>abdominal</title><term><title>upper</title>
          <term><title>right quadrant</title><code>R10.11</code></term></term></term></mainTerm>
          <mainTerm><title>Nausea<nemod>(without vomiting)</nemod></title><code>R11.0</code></mainTerm>
          </letter></ICD10CM.index>''', '''<ICD10CM.tabular><version>2027</version><chapter><name>unit</name>
          <section id="unit"><diag><name>R10.11</name><desc>Right upper quadrant pain</desc></diag>
          <diag><name>R11.0</name><desc>Nausea</desc></diag></section></chapter></ICD10CM.tabular>''',codes)
        reference=SimpleNamespace(**parsed,release_id='unit',release=SimpleNamespace(version='FY2027-unit'))
        terms=DatedTerminology([CatalogRelease('icd10cm-outpatient','FY2027-unit',date(2026,10,1),date(2027,9,30),
            'https://www.cms.gov/unit','a'*64,codes,'unit')])
        def selected(code,system,quote):
            start=NOTE.index(quote)
            return {'code':code,'system':system,'display':'UNVERIFIED DISPLAY',
                'evidences':[{'contextIndex':0,'start':start,'end':start+len(quote),'text':quote}]}
        response={'codes':[
            selected('R10.11','icd10cm-outpatient','Synthetic Nadia Fenwick reports right upper quadrant abdominal pain after fatty meals for six days.'),
            selected('R11.0','icd10cm-outpatient','There has also been intermittent nausea for three days.'),
            selected('99214','cpt','Blood pressure is 126/78 mmHg'),
            selected('G8754','cpt','Blood pressure is 126/78 mmHg'),
            selected('G8752','cpt','Blood pressure is 126/78 mmHg')],
            'candidates':[{'system':'cpt','code':'99999'} for _ in range(10)]}
        request={'system':['icd10cm-outpatient','cpt'],'context':[{'type':'text','text':NOTE}]}
        run=SimpleNamespace(inputs={'engine_contract':corti_coding.CONTRACT,'notes':NOTE,'service_date':'2026-10-17'},
                            context=context(),config={'mode':'live'})
        with patch.object(corti_coding,'terminology',return_value=(terms,{'available':False})), \
             patch.object(corti_coding,'identity_blockers',return_value=[]), \
             patch.object(corti_prediction,'payload',return_value=request), \
             patch.object(coding_engine,'reference_for',return_value=reference), \
             patch.object(coding_engine,'contextual_validation',return_value={'valid':True,'instructions':[]}):
            result=corti_coding.retained_result(run,request,response,'a'*64)
        self.assertEqual([(r['code'],r['eligible']) for r in result['suggestions']],
            [('R10.11',True),('R11.0',True),('99214',False),('G8754',False),('G8752',False)])
        self.assertIn('The patient denies vomiting',result['suggestions'][1]['explanation'])
        self.assertEqual(result['diagnostics_summary']['candidate_count'],10)
        self.assertNotIn('99999',[r['code'] for r in result['suggestions']])


class FreshOutputReferenceTests(ReferenceMixin, SimpleTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.bundle = json.loads(BUNDLE.read_text()); self.install()
        self.make()

    def make(self, notes=NOTE, code='99214', when=date(2026, 10, 17), actor=ACTOR):
        self.encounter = SimpleNamespace(pk=uuid4(), patient_id=uuid4(), created_by_id=actor,
            created_by=SimpleNamespace(pk=actor), department_id=uuid4(),
            created_at=datetime(2026, 10, 17, tzinfo=dt_timezone.utc),
            service_date=when, notes=notes, status='finalized')
        quote = 'This is an established patient' if 'established patient' in notes else 'This is a new patient'
        start = notes.index(quote)
        raw = {'codes': [{'system': 'cpt', 'code': code, 'display': 'UNVERIFIED DISPLAY',
            'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}]}],
            'candidates': [{'system': 'cpt', 'code': 'G8754'}, {'system': 'cpt', 'code': '99999'}]}
        body = json.dumps(raw)
        receipt = {'state': 'succeeded', 'sent': True, 'simulated': False,
            'raw_response': {'body': body, 'redacted': False}, 'response_sha256': hashlib.sha256(body.encode()).hexdigest()}
        spans, status = corti_semantics.checked_spans(raw['codes'][0]['evidences'], notes)
        row = {'id': 'selected:0', 'system': 'CPT', 'code': code, 'description': '',
            'provider_display': 'UNVERIFIED DISPLAY', 'eligible': False, 'evidence_status': status, 'evidence_spans': spans}
        self.run = SimpleNamespace(pk=uuid4(), encounter_id=self.encounter.pk, user_id=actor,
            user=SimpleNamespace(pk=actor), config={'provider': 'corti', 'mode': 'live'}, state='needs_detail',
            inputs={'notes': notes, 'service_date': when.isoformat()}, context=context(notes), releases=[],
            result={'replay': False, 'global_blockers': [], 'suggestions': [row]}, requests=[receipt],
            selection={'selected_ids': [], 'overrides': {}}, selection_revision=0)
        self.run.input_digest=corti_prediction.receipts.digest({'inputs':self.run.inputs,
            'context':self.run.context,'releases':self.run.releases})
        bind_request(self.run)
        self.base=SimpleNamespace(pk=uuid4(),input_digest=self.run.input_digest,selections=deepcopy(self.run.selection),
            selection_digest=coding_service.selection_digest(self.run))

    def assessment(self):
        with patch.object(coding_dispatch, 'authorized_synthetic_actor', return_value=True):
            return coding_output.live_assessment(self.encounter, self.run)

    def reviewed(self):
        with patch.object(coding_dispatch, 'authorized_synthetic_actor', return_value=True), \
             patch.object(coding_service, 'assert_current', return_value=self.run), \
             patch.object(CodingDecision.objects, 'filter', return_value=[self.base]):
            return coding_output.reviewed(self.encounter, self.run)

    def test_arbitrary_fresh_identity_uses_full_note_and_dated_selected_code(self):
        for name in ('Nadia Fenwick', 'Cameron Hollis'):
            with self.subTest(name=name):
                self.make(NOTE.replace('Nadia Fenwick', name))
                result = self.assessment()
                self.assertEqual(result['selection']['code'], '99214')
                self.assertEqual(len(result['facts']), 8)
                self.assertEqual(result['description_status'], 'withheld_unverified_provider_text')
                self.assertEqual(result['provider_citation_adequacy']['status'], 'insufficient_for_time_review')
                self.assertTrue(any('36 minutes' in fact['quote'] for fact in result['facts']))

    def test_office_family_boundaries_come_from_entries_not_one_code_or_expected_answer(self):
        for entry in self.bundle['entries']:
            criteria = entry['criteria']
            for minutes in (criteria['minimum_minutes'], criteria['maximum_minutes']):
                note = NOTE.replace('36 minutes', str(minutes) + ' minutes')
                if criteria['patient_status'] == 'new':
                    note = note.replace('This is an established patient who was seen by this same gastroenterologist eight months ago.',
                                        'This is a new patient.')
                with self.subTest(code=entry['code'], minutes=minutes):
                    self.make(note, entry['code']); self.assertEqual(self.assessment()['selection']['code'], entry['code'])
            self.make(NOTE.replace('36 minutes', str(criteria['maximum_minutes'] + 1) + ' minutes'), entry['code'])
            with self.subTest(outside=entry['code']), self.assertRaises(ValidationError): self.assessment()

    def test_holds_cannot_be_waived_by_provider_quotes_or_context_confirmations(self):
        for change in (
            lambda: self.run.context.update(time_minutes='15'),
            lambda: self.run.context.update(time_same_day=False),
            lambda: self.run.context.update(time_evidence='Episodes last about 15 minutes.'),
            lambda: self.run.result['suggestions'][0].update(id='candidate:0'),
            lambda: self.run.result['suggestions'][0].update(code='G8754'),
            lambda: self.run.result.update(global_blockers=['Different patient']),
        ):
            self.make(); change()
            with self.subTest(change=change), self.assertRaises(ValidationError): self.assessment()
        for source in (NOTE.replace('excludes clinical staff', 'includes clinical staff'),
                       NOTE + '\r\nTotal physician time on the date of service was 10 minutes.',
                       NOTE + '\r\nActual physician time was 10 minutes.',
                       NOTE + '\r\nCorrection: the physician spent 12 minutes today, not 36.',
                       NOTE + '\r\nThe appointment was cancelled. No visit occurred today.',
                       NOTE + '\r\nThe time above was copied from a prior encounter.',
                       NOTE + '\r\nThe encounter did not take place.',
                       NOTE + '\r\nI did not see or evaluate the patient today.',
                       NOTE + '\r\nThe documented total time is incorrect and must not be used.',
                       NOTE + '\r\nClinical staff time is included in the total.',
                       NOTE + '\r\nTime for separately reported services is included in the total.',
                       NOTE + '\r\nOf these 36 minutes, 12 were spent by clinical staff.',
                       NOTE + '\r\nThe physician spent twelve minutes today.',
                       NOTE + '\r\nThe total was twelve minutes.',
                       NOTE.replace('Total physician time', 'Previous visit:\r\nTotal physician time'),
                       NOTE.replace('obtaining history, performing the examination, ', ''),
                       NOTE + '\r\nDate of service: 2026-10-18'):
            self.make(source)
            with self.subTest(source=source[-100:]), self.assertRaises(ValidationError): self.assessment()

    def test_non_enrolled_actor_and_out_of_period_service_remain_unavailable(self):
        with patch.object(coding_dispatch, 'authorized_synthetic_actor', return_value=False), self.assertRaises(ValidationError):
            coding_output.live_assessment(self.encounter, self.run)
        self.make(when=date(2027, 1, 1))
        with self.assertRaises(ValidationError): self.assessment()

    def test_rowan_saved_review_is_identical_under_preserved_v2_reference(self):
        actor=UUID('5f4d1a3d-eeb6-4207-b1df-4597dc696e82')
        self.make(ROWAN, '99213', date(2026, 10, 16), actor)
        # Existing v2 accepted an empty saved context; do not retroactively change
        # its review contract or require another confirmation.
        self.run.context={}
        self.run.input_digest=corti_prediction.receipts.digest({'inputs':self.run.inputs,
            'context':self.run.context,'releases':self.run.releases})
        bind_request(self.run);self.base.input_digest=self.run.input_digest
        self.base.selection_digest=coding_service.selection_digest(self.run)
        self.install(json.loads(LEGACY.read_text()));before=self.reviewed()
        self.install(self.bundle);after=self.reviewed()
        self.assertEqual(before,after)


@override_settings(CODING_PROVIDER='existing', CORTI_CODING_MODE='replay', CORTI_REPLAY_FIXTURE=FIXTURE,
    CODING_ALLOW_TEST_FIXTURES=True, SYNTHETIC_ONLY=True, ADMIN_SITE=False, STORAGES=STORAGES,
    CORTI_NEW_ENCOUNTER_SCOPE='authorized_synthetic_clinicians',
    TESTING_AUTHORITY_MODE=testing_authority.MODE, TESTING_AUTHORITY_ID=testing_authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=testing_authority.AUTHORITY_SHA256)
class GeneralProspectiveRoutingTests(TestCase):
    setUp = CortiWorkflowTests.setUp

    def test_first_ordinary_generation_run_pins_zero_send_context_review_contract(self):
        from core.coding_recovery import CONTEXT_CONTRACT
        with override_settings(CORTI_NEW_ENCOUNTERS_SINCE=(timezone.now()-timedelta(days=1)).isoformat()):
            run=coding_service.ensure_run(self.encounter,self.actor,automatic=True)
        self.assertEqual(run.config['context_review_contract'],CONTEXT_CONTRACT)
        self.assertEqual(run.config['source_context_contract'],coding_dispatch.SOURCE_CONTEXT_CONTRACT)
        self.assertFalse(run.context['time_same_day'])
        self.assertFalse(run.context['time_qualified_clinician'])
        self.assertFalse(run.context['time_excludes_separately_reported'])
        self.send.assert_not_called()

    def test_enrollment_and_clinical_role_route_new_encounters_without_patient_or_actor_exception(self):
        with override_settings(CORTI_NEW_ENCOUNTERS_SINCE=(timezone.now()-timedelta(days=1)).isoformat(),
                               CORTI_NEW_ENCOUNTER_ACTORS=()):
            self.assertEqual(coding_dispatch.provider(self.encounter),'corti')
            Membership.objects.filter(user=self.actor).update(role='manager')
            self.assertEqual(coding_dispatch.provider(self.encounter),'existing')
            Membership.objects.filter(user=self.actor).update(role='clinician',active=False)
            self.assertEqual(coding_dispatch.provider(self.encounter),'existing')
        self.send.assert_not_called()

    def test_first_run_engine_binding_survives_general_admission(self):
        with override_settings(CORTI_NEW_ENCOUNTER_SCOPE=''):
            inputs,ctx,releases,key=coding_service.input_snapshot(self.encounter)
        saved=CodingRun.objects.create(encounter=self.encounter,user=self.actor,input_digest=key,
            inputs=inputs,context=ctx,releases=releases,config={'provider':'anthropic'},state='needs_detail')
        with override_settings(CORTI_NEW_ENCOUNTERS_SINCE=(timezone.now()-timedelta(days=1)).isoformat()):
            self.assertEqual(coding_dispatch.provider(self.encounter),'existing')
            self.assertEqual(coding_service.input_snapshot(self.encounter)[3],saved.input_digest)
        self.send.assert_not_called()
