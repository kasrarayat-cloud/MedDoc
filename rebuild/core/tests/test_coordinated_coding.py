"""Retained synthetic provider output plus unfamiliar/adversarial source controls.

No provider calls, native writes, invented approvals, or changed retained answers.
The reduced reference is a projection of the retained official dated reference.
"""
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as N
from tempfile import TemporaryDirectory
from uuid import UUID, uuid4
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import coding_dispatch, coding_output, coding_service, coding_engine as engine, corti_coding, corti_prediction, corti_semantics as semantics
from core.tests.test_coding_output_live import ReferenceMixin, bind_request
from core.corti_response import CatalogRelease, DatedTerminology

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/elias_coding_retained.json').read_text())
NOTE = FIXTURE['notes']
RAW = json.loads(FIXTURE['raw_response'])
CONTRACT = engine.SOURCE_CONTRACT


def reference():
    value = deepcopy(FIXTURE['reference'])
    value['release'] = N(**value['release'])
    return N(**value)


def run(notes=NOTE, modern=True):
    return N(inputs={'notes': notes, 'service_date': '2026-10-17', 'engine_contract': corti_coding.CONTRACT,
        'patient_identity': {'display_name': 'Synthetic Elias Mercer'}, 'patient_name_answers': []},
        context={'setting': 'outpatient_office'}, config={'mode': 'live', 'provider': 'corti',
        **({'clinical_source_contract': CONTRACT} if modern else {})})


def selected(code, quote, notes):
    start = notes.index(quote)
    return {'id': 'selected:0', 'code': code, 'system': 'icd10cm-outpatient',
        'terminology': {'description': FIXTURE['reference']['tabular']['codes'][code]},
        'evidence': [{'text': quote, 'start': start, 'end': start + len(quote),
                      'status': 'valid', 'context_index': 0}]}


class DatedSourceRouteTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass(); cls.reference = reference()

    def result(self, modern=True):
        current = run(modern=modern)
        release = self.reference.release
        terms = DatedTerminology([CatalogRelease('icd10cm-outpatient', release.version,
            date(2026, 10, 1), date(2027, 9, 30), release.source_url, release.sha256,
            self.reference.tabular['codes'], release.source_url)])
        with patch.object(corti_coding, 'terminology', return_value=(terms, {'available': False})), \
             patch.object(engine, 'reference_for', return_value=self.reference):
            current.result = corti_coding.retained_result(current, FIXTURE['request'], RAW,
                FIXTURE['provenance']['original_response_sha256'])
        return current, terms

    def test_retained_raw_prediction_routes_without_promoting_candidates(self):
        self.assertEqual(hashlib.sha256(FIXTURE['raw_response'].encode()).hexdigest(),
                         FIXTURE['provenance']['original_response_sha256'])
        legacy, _ = self.result(False)
        self.assertEqual([(r['code'], r['eligible']) for r in legacy.result['suggestions']],
                         [('R19.7', False), ('R10.33', False), ('99214', False)])
        fresh, _ = self.result()
        self.assertEqual([(r['code'], r['eligible']) for r in fresh.result['suggestions']],
                         [('R19.7', True), ('R10.33', True), ('99214', False)])
        self.assertEqual(fresh.result['diagnostics_summary'],
            {'candidate_count': 9, 'alternative_count': 4, 'rejected_selected_count': 0})
        self.assertEqual(fresh.result['adapter']['diagnostics']['provider_response'], RAW)
        self.assertEqual(fresh.result['suggestions'][2]['description'], '')
        self.assertEqual(fresh.result['suggestions'][2]['semantic_support']['documented_time_facts']['status'], 'documented')
        self.assertEqual(fresh.result['global_blockers'], [])

    def test_approval_and_export_revalidation_rebuild_the_same_official_route(self):
        current, terms = self.result()
        selections = {'selected_ids': ['selected:0', 'selected:1'], 'overrides': {}}
        descriptions = self.reference.tabular['codes']
        def catalog(**kwargs):
            return N(first=lambda: N(description=descriptions[kwargs['code']]))
        with patch.object(corti_coding, 'terminology', return_value=(terms, {'available': False})), \
             patch.object(engine, 'reference_for', return_value=self.reference), \
             patch.object(engine.Code.objects, 'filter', side_effect=catalog):
            self.assertEqual(corti_coding.validate_selection(current, selections), selections)
            # Bound code membership still cannot admit uncertain diseases,
            # selected-only candidates, or a forged procedure eligibility bit.
            for key in ('candidate:0', 'selected:2'):
                with self.subTest(key=key), self.assertRaises(ValidationError):
                    corti_coding.validate_selection(current, {'selected_ids': [key], 'overrides': {}})
            current.inputs['notes'] += '\r\nThe patient denies diarrhea.'
            with self.assertRaises(ValidationError):
                corti_coding.validate_selection(current, selections)

    def route(self, code, quote, notes=None):
        notes = notes or ('Patient: Synthetic Elias Mercer\r\nAssessment:\r\n' + quote)
        return corti_coding._icd_source(run(notes), self.reference, selected(code, quote, notes), [code])[1]

    def test_connected_specific_description_can_imply_classification_parent(self):
        for quote in ('Periumbilical abdominal pain was evaluated today.',
                      'The patient reports periumbilical pain.',
                      'The patient reports epigastric pain.',
                      'Right upper quadrant abdominal pain is present.'):
            code = 'R10.13' if 'epigastric' in quote else 'R10.11' if 'quadrant' in quote else 'R10.33'
            with self.subTest(quote=quote): self.assertIsNotNone(self.route(code, quote))
        for quote in ('The patient has periumbilical fullness and shoulder pain.',
                      'The patient has pain and a periumbilical scar.',
                      'The patient denies periumbilical pain.',
                      'The patient reports possible periumbilical pain.'):
            with self.subTest(quote=quote): self.assertIsNone(self.route('R10.33', quote))

    def test_comma_head_is_corroborated_and_default_does_not_erase_a_subtype(self):
        self.assertIsNotNone(self.route('R19.7', 'Diarrhea was evaluated today.'))
        for quote in ('The patient denies diarrhea.', 'The patient has functional diarrhea.',
                      'The patient reports infectious diarrhea.'):
            with self.subTest(quote=quote): self.assertIsNone(self.route('R19.7', quote))
        self.assertEqual(engine.index_head_terms({'term': 'Finding, lateral'}, 'Other finding'),
                         ['Finding, lateral'])
        self.assertEqual(engine.index_head_terms({'term': 'Condition, due to agent'}, 'Condition'),
                         ['Condition, due to agent'])

    def test_unrelated_owners_prior_encounters_uncertain_causes_and_resolved_symptoms_stay_held(self):
        quote = 'Diarrhea was evaluated today.'
        for heading in ('Mother:\r\n\r\n', 'Previous encounter:\r\n\r\n', 'Example:\r\n'):
            note = 'Patient: Synthetic Elias Mercer\r\n' + heading + quote
            with self.subTest(heading=heading): self.assertIsNone(self.route('R19.7', quote, note))
        self.assertIsNone(self.route('K59.00', 'His constipation resolved.'))
        self.assertIsNone(self.route('K59.1', 'Functional diarrhea has not been established.'))

    def test_current_condition_requires_assertion_modality_and_its_own_timing(self):
        for quote in ('Diarrhea is a possibility only, not an established symptom.',
                      'There is a possibility of diarrhea.',
                      'Diarrhea remains under consideration.',
                      'The patient was evaluated for diarrhea last year.',
                      'Last year the patient was evaluated for diarrhea.',
                      'The patient was previously evaluated for diarrhea.',
                      'Diarrhea was assessed yesterday.',
                      'Diarrhea three weeks ago.',
                      'There is a history of diarrhea.'):
            with self.subTest(quote=quote): self.assertIsNone(self.route('R19.7', quote))
        for quote in ('Diarrhea has persisted since last year.',
                      'Diarrhea began after antibiotics last week.',
                      'Diarrhea was evaluated today.'):
            with self.subTest(quote=quote): self.assertIsNotNone(self.route('R19.7', quote))
        current, terms = self.result()
        selection = {'selected_ids': ['selected:0'], 'overrides': {}}
        # An already eligible displayed row cannot bypass the same source check
        # when approval/export revalidates its stored concept and complete note.
        for quote in ('Diarrhea is a possibility only, not an established symptom.',
                      'The patient was evaluated for diarrhea last year.'):
            current.inputs['notes'] = 'Patient: Synthetic Miri Oakes\nAssessment:\n' + quote
            current.inputs['patient_identity']['display_name'] = 'Synthetic Miri Oakes'
            current.result['suggestions'][0]['concept']['evidence'] = quote
            with patch.object(corti_coding, 'terminology', return_value=(terms, {'available':False})), \
                 patch.object(engine, 'reference_for', return_value=self.reference), \
                 self.subTest(quote=quote), self.assertRaisesMessage(ValidationError, 'not established'):
                corti_coding.validate_selection(current, selection)
        current, terms = self.result()
        current.inputs['notes'] += '\r\nDiarrhea remains only a possibility.'
        with patch.object(corti_coding, 'terminology', return_value=(terms, {'available':False})), \
             patch.object(engine, 'reference_for', return_value=self.reference), \
             self.assertRaisesMessage(ValidationError, 'not established'):
            corti_coding.validate_selection(current, selection)


class SourceBoundTimeTests(SimpleTestCase):
    def support(self, notes):
        return semantics.office_time_facts(notes, contract=CONTRACT)

    def errors(self, notes):
        return semantics.office_service_eligibility(notes, date(2026, 10, 17), contract=CONTRACT)

    def test_retained_named_total_and_allocation_exclude_other_day_and_nursing(self):
        result = self.support(NOTE)
        self.assertEqual(result['status'], 'documented', result['blockers'])
        self.assertEqual(self.errors(NOTE), [])
        facts = {f['key']: f for f in result['facts']}
        self.assertEqual(set(facts), set(semantics.REQUIRED_TIME_FACTS))
        self.assertEqual(facts['time_minutes']['value'], 37)
        self.assertIn('Dr. Farrow personally spent 37 minutes', facts['time_minutes']['quote'])
        self.assertIn('nine minutes of nursing rooming work', facts['time_excludes_staff']['quote'])
        for fact in result['facts']: self.assertEqual(NOTE[fact['start']:fact['end']], fact['quote'])
        self.assertFalse(result['clinician_confirmed'])

    def test_unfamiliar_names_style_and_time_allocation_are_general(self):
        changed = NOTE.replace('Leena Farrow', 'Amira Ellison').replace('Dr. Farrow', 'Dr. Ellison')
        changes = (changed,
            changed+'\r\nNo history of diabetes. No examination abnormalities were identified.',
            changed.replace('Dr. Ellison personally spent', 'Doctor Amira Ellison spent'),
            changed.replace('37 minutes', '38 minutes').replace('six minutes reviewing', 'seven minutes reviewing'),
            changed.replace('37 minutes', '32 minutes').replace('six minutes reviewing prior records', 'four minutes reviewing the chart before the visit')
                .replace('24 minutes obtaining the history, performing the examination and counseling the patient', '22 minutes directly with the patient obtaining history, examining and counseling her')
                .replace('seven minutes entering', 'six minutes entering').replace('The total also excludes', 'They also exclude'),
            changed.replace('Established-patient', 'Established patient').replace('nursing rooming work', 'clinical staff time'),
            changed.replace('performing the examination and counseling the patient', 'examining and counseling him')
                .replace('nursing rooming work', 'staff rooming').replace('The total also excludes', 'They also exclude'))
        for note in changes:
            with self.subTest(note=note[-560:]):
                self.assertEqual(self.support(note)['status'], 'documented')
                self.assertEqual(self.errors(note), [])

    def test_legacy_fact_payloads_remain_exact_and_new_reading_supports_previous_sources(self):
        fixtures = Path(__file__).parent / 'fixtures'
        for folder, minutes, when in [('nadia', 36, date(2026,10,17)), ('rowan', 24, date(2026,10,16))]:
            note = (fixtures/folder/'source.txt').read_bytes().decode()
            legacy = semantics.office_time_facts(note)
            fresh = self.support(note)
            self.assertEqual(fresh, legacy)
            self.assertEqual(next(f['value'] for f in fresh['facts'] if f['key']=='time_minutes'), minutes)
            self.assertEqual(semantics.office_service_eligibility(note, when, contract=CONTRACT), [])

    def test_context_and_provider_substrings_cannot_create_missing_or_contradicted_time(self):
        changes = (
            NOTE.replace('Dr. Farrow personally spent', 'Dr. Other personally spent'),
            NOTE.replace('37 minutes', '38 minutes'),
            NOTE.replace('on the encounter date:', 'on the preceding day:'),
            NOTE.replace('exclude nine minutes', 'include nine minutes'),
            NOTE.replace('exclude nine minutes', 'exclude some nine minutes'),
            NOTE.replace('The 37 minutes exclude', 'The 52 minutes exclude'),
            NOTE.replace('24 minutes obtaining', '24 minutes of nursing rooming and obtaining'),
            NOTE.replace('Office E/M selection', 'Previous encounter:\r\n\r\nOffice E/M selection'),
            NOTE.replace('Office E/M selection', 'Mother:\r\n\r\nOffice E/M selection'),
            NOTE + '\r\nDr. Farrow personally spent 52 minutes today.',
            NOTE + '\r\nThe physician spent twelve minutes today.',
            NOTE + '\r\nThe total also includes five minutes from the preceding day.',
            NOTE + '\r\nThe total does not exclude nursing time.',
            NOTE + '\r\nThe office consultation was not performed today.',
            NOTE + '\r\nNo evaluation was performed today.',
            NOTE + '\r\nNo clinic visit occurred today. The encounter was cancelled.',
            NOTE + '\r\nActually all 37 minutes were nursing work, not physician work.',
            NOTE.replace('The total also excludes', 'Other encounter summary. They also exclude'),
            NOTE + '\r\nOnly 30 of the 37 minutes were on the encounter date.',
            NOTE + '\r\nThe time above was copied from a prior encounter.',
            NOTE + '\r\nThe stated 37 minutes were for the appointment yesterday, not today.',
            NOTE + '\r\nDate of service: 2026-10-18',
        )
        for note in changes:
            with self.subTest(note=note[-600:]):
                self.assertTrue(self.support(note)['status'] != 'documented' or self.errors(note))
        facts = self.support(NOTE)['facts']
        values = {f['key']: f['value'] for f in facts}
        context = {**values, 'time_minutes': '37', 'time_evidence': next(f['quote'] for f in facts if f['key']=='time_minutes')}
        self.assertEqual(semantics.confirmed_time_context(context, NOTE, facts), [])
        for key, value in [('time_minutes','52'), ('patient_status','new'), ('time_same_day',False),
                           ('time_evidence','watery diarrhea lasting 11 days')]:
            with self.subTest(key=key): self.assertTrue(semantics.confirmed_time_context({**context,key:value},NOTE,facts))


class ProspectiveCodingContractTests(SimpleTestCase):
    @override_settings(CORTI_NEW_ENCOUNTER_SCOPE=coding_dispatch.AUTHORIZED_SYNTHETIC_SCOPE)
    def test_new_run_adopts_and_old_encounter_pins_its_first_contract(self):
        for first, expected in [(None, engine.PROSPECTIVE_SOURCE_CONTRACT), (N(config={}), None),
                                (N(config={'clinical_source_contract':CONTRACT}), CONTRACT),
                                (N(config={'clinical_source_contract':engine.CURRENT_SOURCE_CONTRACT}), engine.CURRENT_SOURCE_CONTRACT),
                                (N(config={'clinical_source_contract':engine.PROSPECTIVE_SOURCE_CONTRACT}), engine.PROSPECTIVE_SOURCE_CONTRACT)]:
            query = N(order_by=lambda *args: N(first=lambda:first))
            with patch.object(coding_dispatch,'provider',return_value='corti'), \
                 patch.object(coding_dispatch,'source_context_enabled',return_value=True), \
                 patch.object(corti_prediction,'configuration',return_value={'provider':'corti','mode':'live'}), \
                 patch('core.models.CodingRun.objects.filter',return_value=query):
                actual = coding_dispatch.configuration(N(),N())
            self.assertEqual(actual.get('clinical_source_contract'),expected)


class CoordinatedCPTOutputTests(ReferenceMixin, SimpleTestCase):
    """Unit-bound retained bytes through the existing synthetic output review.

    Receipt binding below is an isolated control, not a new provider receipt or
    clinical approval. Only the actual root-owned browser flow can create those.
    """
    def setUp(self):
        self.reference = reference()
        self.temporary = TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.bundle = json.loads((Path(__file__).parents[2]/'ops/fixtures/corti_office_time_output_reference.json').read_text())
        self.install()
        self.run, _ = DatedSourceRouteTests.result(self)
        actor = UUID('e1a20625-455d-4603-a874-794327b19d10')
        self.encounter = N(pk=uuid4(), patient_id=uuid4(), created_by_id=actor, created_by=N(pk=actor),
            department_id=uuid4(), created_at=datetime(2026,10,17,tzinfo=timezone.utc),
            service_date=date(2026,10,17), notes=NOTE, status='finalized')
        self.run.pk=uuid4(); self.run.encounter_id=self.encounter.pk
        self.run.user_id=actor; self.run.user=N(pk=actor); self.run.state='needs_detail'; self.run.releases=[]
        facts=semantics.office_time_facts(NOTE,contract=CONTRACT)['facts']
        values={f['key']:f['value'] for f in facts}
        self.run.context={**coding_service.CONTEXT_DEFAULTS, **values, 'time_minutes':'37',
            'time_evidence':next(f['quote'] for f in facts if f['key']=='time_minutes')}
        self.run.requests=[{'state':'succeeded','sent':True,'simulated':False,
            'raw_response':{'body':FIXTURE['raw_response'],'redacted':False},
            'response_sha256':FIXTURE['provenance']['original_response_sha256']}]
        self.run.input_digest=coding_service.digest({'inputs':self.run.inputs,'context':self.run.context,'releases':[]})
        bind_request(self.run)

    def assessment(self):
        with patch.object(coding_dispatch,'authorized_synthetic_actor',return_value=True):
            return coding_output.live_assessment(self.encounter,self.run)

    def source(self, notes):
        self.encounter.notes = notes
        self.run.inputs['notes'] = notes
        self.run.requests[0]['raw_response']['body'] = FIXTURE['raw_response']
        self.run.requests[0]['response_sha256'] = FIXTURE['provenance']['original_response_sha256']
        for index, row in enumerate(RAW['codes']):
            spans, status = semantics.checked_spans(row['evidences'], NOTE)
            self.run.result['suggestions'][index]['evidence_spans'] = spans
            self.run.result['suggestions'][index]['evidence_status'] = status
        self.run.input_digest = coding_service.digest({'inputs':self.run.inputs,'context':self.run.context,'releases':[]})
        bind_request(self.run)

    def controlled_source(self, notes, replacements=()):
        """Bind constructed unit receipt spans to a transformed source.

        These are offline controls, never edited retained provider receipts.
        Keeping exact valid spans avoids an incidental stale-offset refusal
        masking the source ownership predicate under examination.
        """
        self.run.context['time_evidence'] = next(f['quote'] for f in
            semantics.office_time_facts(NOTE, contract=CONTRACT)['facts'] if f['key']=='time_minutes')
        for old, new in replacements:
            self.run.context['time_evidence'] = self.run.context['time_evidence'].replace(old, new)
        self.source(notes)
        raw = deepcopy(RAW)
        for index, selected_row in enumerate(raw['codes']):
            for evidence in selected_row['evidences']:
                for old, new in replacements:
                    evidence['text'] = evidence['text'].replace(old, new)
                evidence['start'] = notes.index(evidence['text'])
                evidence['end'] = evidence['start'] + len(evidence['text'])
            spans, status = semantics.checked_spans(selected_row['evidences'], notes)
            self.assertEqual(status, 'valid')
            self.run.result['suggestions'][index]['evidence_spans'] = spans
            self.run.result['suggestions'][index]['evidence_status'] = status
        body = json.dumps(raw)
        self.run.requests[0]['raw_response']['body'] = body
        self.run.requests[0]['response_sha256'] = hashlib.sha256(body.encode()).hexdigest()

    def test_retained_selected_cpt_number_uses_complete_source_and_keeps_descriptor_limit(self):
        result=self.assessment()
        self.assertEqual(result['selection']['code'],'99214')
        self.assertEqual(result['selection']['basis'],'documented_total_time')
        self.assertEqual(len(result['facts']),8)
        self.assertEqual(result['description_status'],'withheld_unverified_provider_text')
        self.assertEqual(result['provider_citation_adequacy']['status'],'insufficient_for_time_review')
        self.assertEqual(result['evidence_origin'],'independently_checked_saved_note_time_facts')
        self.assertEqual(next(f['value'] for f in result['facts'] if f['key']=='time_minutes'),37)
        self.assertEqual(self.run.result['adapter']['diagnostics']['provider_response'],RAW)

    def test_output_approval_export_gate_rejects_context_or_source_bypass(self):
        self.run.context['time_minutes']='52'
        with self.assertRaises(ValidationError): self.assessment()
        self.run.context['time_minutes']='37'
        self.run.result['suggestions'][2]['id']='candidate:0'
        with self.assertRaises(ValidationError): self.assessment()
        self.run.result['suggestions'][2]['id']='selected:2'
        self.encounter.notes=NOTE+'\r\nThe total also includes nursing time.'
        with self.assertRaises(ValidationError): self.assessment()


    def test_full_source_cancellation_and_nursing_substitution_refuse_actual_review_boundary(self):
        for suffix, message in (
            ('No clinic visit occurred today. The encounter was cancelled.', 'denies a completed'),
            ('Actually all 37 minutes were nursing work, not physician work.', 'includes ineligible'),
            ('This was an administrative chart review only; the patient was not present and no history or examination was obtained.', 'denies participation'),
            ('Only nursing staff saw the patient today; the physician did not participate.', 'denies participation'),
            ('The patient was seen only by nursing staff.', 'denies participation'),
            ('Dr. Farrow did not participate in this encounter.', 'denies participation'),
            ('The stated 37 minutes were for the appointment yesterday, not today.', 'Missing documented time'),
            ('That total actually belongs to yesterday\'s appointment.', 'Missing documented time'),
        ):
            self.source(NOTE+'\r\n'+suffix)
            with self.subTest(suffix=suffix), self.assertRaisesMessage(ValidationError, message):
                self.assessment()

    def test_error_negations_are_not_retractions_or_new_time_and_do_not_hide_new_claims(self):
        for suffix in ('The physician time is not erroneous.',
                       'The stated physician time was not copied from an earlier encounter.',
                       'Mother:\r\nThe stated physician time is erroneous.',
                       'Previous encounter:\r\nThe stated physician time is erroneous.',
                       'The time total is not wrong but the assessment is wrong.',
                       'The assessment is wrong but the time total is not wrong.',
                       'The assessment is wrong but the physician time is not wrong.',
                       'The assessment is wrong but now the physician time is not wrong.',
                       'The time total is not wrong but for his mother the physician time is wrong.',
                       'The time total is not wrong but in the previous encounter the physician time is wrong.',
                       'The assessment and time account do not refer to his mother.',
                       'It is false that the assessment is not wrong.',
                       'It is uncertain whether the assessment is not wrong.',
                       'The assessment is erroneous and must not be used.'):
            self.source(NOTE+'\r\n'+suffix)
            with self.subTest(suffix=suffix): self.assertEqual(self.assessment()['selection']['code'],'99214')
        self.controlled_source(NOTE.replace('Office E/M selection',
            'The stated physician time was not copied from an earlier encounter.\r\nOffice E/M selection'))
        self.assertEqual(self.assessment()['selection']['code'],'99214')
        for suffix in ('The physician time is erroneous.',
                       'The physician time is not erroneous but includes nursing work.',
                       'The stated physician time was not copied from an earlier encounter, but all 37 minutes were nursing work.',
                       'The physician time is not erroneous and incorrect.',
                       'The physician time is wrong but the time total is not wrong.',
                       'The assessment is not wrong but the time total is wrong.',
                       'The assessment is not wrong but now the physician time is wrong.',
                       'The time total is wrong but the assessment is not wrong.',
                       'It is false that the time total is not wrong.',
                       'It is uncertain whether the physician time is not wrong.',
                       'After assuming the time total is not wrong.',
                       'That total actually belongs to yesterday\'s appointment.'):
            self.source(NOTE+'\r\n'+suffix)
            with self.subTest(suffix=suffix), self.assertRaises(ValidationError): self.assessment()

    def test_treating_clinician_headers_bind_only_current_patient_and_encounter(self):
        for section in ("Mother's medical history:", 'Previous encounter:'):
            for reset in ('Current patient: Synthetic Elias Mercer',
                          'Patient: Synthetic Elias Mercer\r\nCurrent encounter:'):
                notes = NOTE.replace('Visit: ', section+'\r\nTreating clinician: Dr. Corwin\r\n'+reset+'\r\nVisit: ')
                notes = notes.replace('Dr. Farrow personally', 'Dr. Corwin personally')
                self.controlled_source(notes, [('Farrow personally', 'Corwin personally')])
                with self.subTest(section=section, reset=reset), self.assertRaises(ValidationError):
                    self.assessment()
        # A different clinician explicitly bound to the current encounter is
        # supported, including a harmless foreign treating-clinician header.
        notes = NOTE.replace('Treating clinician: Dr. Leena Farrow', 'Treating clinician: Dr. Mira Corwin')
        notes = notes.replace('Dr. Farrow personally', 'Dr. Corwin personally')
        self.controlled_source(notes, [('Farrow personally', 'Corwin personally')])
        self.assertEqual(self.assessment()['selection']['code'], '99214')
        notes = notes.replace('Visit: ', "Mother's medical history:\r\nTreating clinician: Dr. Davison\r\n"
                              'Current patient: Synthetic Elias Mercer\r\nVisit: ')
        self.controlled_source(notes, [('Farrow personally', 'Corwin personally')])
        self.assertEqual(self.assessment()['selection']['code'], '99214')
