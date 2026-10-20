"""Whole frozen fictional Rowan source through time facts and bounded review.

The LF fixture is byte-identical to the prospective synthetic source, not a
simplified replacement. The CRLF form also matches the frozen wire SHA. Every
receipt constructed below is an inert unit fixture: no provider or DB is used.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_engine, corti_semantics as semantics


FIXTURE = Path(__file__).parent / 'fixtures/rowan'
LF = (FIXTURE / 'documented-time-source.txt').read_bytes().decode()
# The frozen request wire has CRLF and no terminal newline; preserve that exact
# transport form rather than assume LF's final newline was transmitted.
WIRE = LF.removesuffix('\n').replace('\n', '\r\n')
CONTRACT = semantics.DOCUMENTED_TIME_CONTRACT
OFFICE = 'Nessa is a 52-year-old woman attending an in-person visit in a United States outpatient gastroenterology office.'
QUALIFICATION = 'All three activities were completed by the treating physician on the service date.'
EXCLUSION = 'No time for separately reported services is included in the 33-minute total.'


class WholeRowanDocumentedTimeTests(SimpleTestCase):
    def facts(self, note, contract=CONTRACT):
        return (semantics.office_time_facts(note, contract=contract),
                semantics.office_service_eligibility(note, date(2026, 10, 19), contract=contract))

    def assert_supported(self, note):
        facts, errors = self.facts(note)
        self.assertEqual(facts['status'], 'documented', facts)
        self.assertEqual(errors, [])
        self.assertEqual({item['key'] for item in facts['facts']}, set(semantics.REQUIRED_TIME_FACTS))
        self.assertEqual(next(item['value'] for item in facts['facts'] if item['key'] == 'time_minutes'), 33)
        self.assertFalse(facts['clinician_confirmed'])
        for item in facts['facts']:
            self.assertEqual(note[item['start']:item['end']], item['quote'])
        return facts

    def assert_held(self, note):
        facts, errors = self.facts(note)
        self.assertTrue(facts['status'] != 'documented' or errors, (facts, errors))

    def test_exact_whole_lf_and_frozen_wire_have_eight_facts_and_no_service_error(self):
        self.assertEqual(hashlib.sha256(LF.encode()).hexdigest(),
                         '5b3b1f1dc34ba9f55b75db5827f880e475a39cfc56b0c4ac285b5d0a53ab39f0')
        self.assertEqual(hashlib.sha256(WIRE.encode()).hexdigest(),
                         '6a018d0e7ae38a935aa39f7755d541b8a2ce2f3fc5e5054f91477e4398c04bde')
        for form, note in (('lf', LF), ('crlf', WIRE)):
            with self.subTest(form=form):
                facts = self.assert_supported(note)
                self.assertEqual(next(item['quote'] for item in facts['facts']
                                      if item['key'] == 'time_excludes_separately_reported'), EXCLUSION)

    def test_all_historical_v2_through_v7_outputs_remain_byte_equivalent(self):
        historical = json.loads((FIXTURE / 'documented-time-historical-v2-v7.json').read_bytes())
        for form, note in (('lf', LF), ('crlf', WIRE)):
            for contract, expected in historical['results'][form].items():
                with self.subTest(form=form, contract=contract):
                    facts, errors = self.facts(note, contract)
                    self.assertEqual({'facts': facts, 'eligibility': errors}, expected)
        facts, unused = self.facts(LF, coding_engine.QUALIFIED_SOURCE_CONTRACT)
        self.assertEqual(facts['status'], 'requires_clarification')
        self.assertEqual([item['key'] for item in facts['facts']], ['patient_status'])

    def test_facility_and_specialty_compose_without_admitting_unknown_or_competing_words(self):
        for wording in ('outpatient gastroenterology', 'clinical gastroenterology',
                        'medical gastroenterology', 'outpatient internal medicine'):
            with self.subTest(wording=wording):
                self.assert_supported(LF.replace('outpatient gastroenterology office', wording + ' office'))
        for wording in ('outpatient post', 'outpatient astrology', 'gastroenterology cardiology',
                        'outpatient outpatient gastroenterology', 'outpatient virtual gastroenterology'):
            with self.subTest(wording=wording):
                self.assert_held(LF.replace('outpatient gastroenterology office', wording + ' office'))

    def test_attendance_stays_whole_owned_and_unqualified(self):
        for replacement in (
            OFFICE.replace('Nessa is a', 'Her sister is a'),
            OFFICE.replace('Nessa is a', 'Another patient is a'),
            OFFICE.replace('attending an', 'possibly attending an'),
            OFFICE.replace('attending an', 'not attending an'),
            OFFICE.replace('attending an', 'only attending an'),
            OFFICE.replace('in-person', 'telephone'),
            OFFICE.removesuffix('.') + ', but the visit was cancelled.',
            OFFICE.replace('United States outpatient gastroenterology office', 'United States emergency department'),
        ):
            with self.subTest(replacement=replacement):
                self.assert_held(LF.replace(OFFICE, replacement))

    def test_complete_same_day_qualification_preserves_total_but_invalid_ones_hold(self):
        self.assert_supported(LF.replace(QUALIFICATION, QUALIFICATION.replace('three', '3')))
        for replacement in (
            QUALIFICATION.replace('three', 'two'),
            QUALIFICATION.replace('three', 'four'),
            QUALIFICATION.replace('were completed', 'were not completed'),
            QUALIFICATION.replace('were completed', 'were possibly completed'),
            QUALIFICATION.replace('the treating physician', 'the staff'),
            QUALIFICATION.replace('the treating physician', 'Dr. Other'),
            QUALIFICATION.replace('on the service date', 'on the previous date'),
            QUALIFICATION.replace('on the service date', 'on 18 October 2026'),
            QUALIFICATION.removesuffix('.') + ' unless the physician was unavailable.',
        ):
            for position in ('replace', 'append'):
                note = LF.replace(QUALIFICATION, replacement) if position == 'replace' else LF + ' ' + replacement
                with self.subTest(replacement=replacement, position=position):
                    self.assert_held(note)

    def test_no_included_service_time_has_exclusion_polarity_only_for_the_complete_frame(self):
        for replacement in (
            EXCLUSION.replace('No time', 'Some time'),
            EXCLUSION.replace('No time', 'Time'),
            EXCLUSION.replace('is included', 'is not included'),
            EXCLUSION.replace('is included', 'is excluded'),
            EXCLUSION.replace('is included', 'may be included'),
            EXCLUSION.replace('33-minute', '34-minute'),
            EXCLUSION.removesuffix('.') + ', except five minutes.',
            EXCLUSION.removesuffix('.') + ' unless performed.',
            EXCLUSION.removesuffix('.') + ', but the physician total is incorrect.',
        ):
            for position in ('replace', 'append'):
                note = LF.replace(EXCLUSION, replacement) if position == 'replace' else LF + ' ' + replacement
                with self.subTest(replacement=replacement, position=position):
                    self.assert_held(note)

    def test_exclusions_keep_total_calendar_and_performer_checks(self):
        for before, after in (
            ('The 33 minutes exclude', 'The 34 minutes exclude'),
            ('The 33 minutes exclude', 'The 33 minutes include'),
            ('chart review on 18 October 2026', 'chart review on 19 October 2026'),
            ('chart review on 18 October 2026', 'chart review on 20 October 2026'),
            ('chart review on 18 October 2026', 'chart review on 31 February 2026'),
            ('Dr. Park personally spent', 'Dr. Other personally spent'),
            ('33 minutes on 19 October 2026:', '33 minutes on 18 October 2026:'),
            ('21 minutes obtaining', '20 minutes obtaining'),
        ):
            with self.subTest(before=before, after=after):
                self.assert_held(LF.replace(before, after))

    def bounded_fixture(self, note, *, context_source=None):
        from core.tests.test_coordinated_coding import CoordinatedCPTOutputTests
        from core.tests.test_coding_output_live import bind_request
        fixture = CoordinatedCPTOutputTests('test_retained_selected_cpt_number_uses_complete_source_and_keeps_descriptor_limit')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.encounter.notes = note
        fixture.encounter.service_date = date(2026, 10, 19)
        fixture.run.inputs.update(notes=note, service_date='2026-10-19')
        fixture.run.config.update(clinical_source_contract=coding_engine.QUALIFIED_SOURCE_CONTRACT,
                                  cpt_time_source_contract=CONTRACT)
        facts = self.assert_supported(note if context_source is None else context_source)['facts']
        fixture.run.context.update({item['key']: item['value'] for item in facts})
        fixture.run.context.update(time_minutes='33', time_evidence=next(
            item['quote'] for item in facts if item['key'] == 'time_minutes'))
        # A fixed intact header citation keeps the raw unit response identical
        # across whole-source variants. Neither stale offsets nor changed
        # provider bytes can mask the source predicate being exercised.
        citation = note.splitlines()[0]
        raw = {'codes': [{'system': 'cpt', 'code': '99214', 'display': 'Unverified synthetic unit wording',
                         'evidences': [{'contextIndex': 0, 'start': 0, 'end': len(citation), 'text': citation}]}]}
        body = json.dumps(raw)
        spans, status = semantics.checked_spans(raw['codes'][0]['evidences'], note)
        fixture.run.result['suggestions'] = [{'id': 'selected:0', 'system': 'CPT', 'code': '99214',
            'eligible': False, 'evidence_status': status, 'evidence_spans': spans}]
        fixture.run.requests[0].update(raw_response={'body': body, 'redacted': False},
            response_sha256=hashlib.sha256(body.encode()).hexdigest())
        from core import coding_service
        fixture.run.input_digest = coding_service.digest({'inputs': fixture.run.inputs,
            'context': fixture.run.context, 'releases': []})
        bind_request(fixture.run)
        return fixture

    def test_exact_whole_sources_reach_existing_bounded_numeric_99214_consumer(self):
        for form, note in (('lf', LF), ('crlf', WIRE)):
            with self.subTest(form=form):
                fixture = self.bounded_fixture(note)
                before = deepcopy(fixture.run.requests)
                result = fixture.assessment()
                self.assertEqual(result['selection']['code'], '99214')
                self.assertEqual(result['selection']['basis'], 'documented_total_time')
                self.assertEqual(len(result['facts']), 8)
                self.assertEqual(result['scope']['service_date'], '2026-10-19')
                self.assertEqual(next(item['value'] for item in result['facts'] if item['key'] == 'time_minutes'), 33)
                self.assertEqual(result['description_status'], 'withheld_unverified_provider_text')
                self.assertEqual(fixture.run.requests, before)
                # No reclassification of a changed source behind intact receipt spans.
                fixture.encounter.notes += ' All three activities were completed by staff on the service date.'
                with self.assertRaises(ValidationError):
                    fixture.assessment()

    def test_complete_foreign_exclusions_leave_current_whole_source_and_receipt_intact(self):
        response_hash = None
        for note in (LF, WIRE):
            baseline = self.assert_supported(note)
            for prefix in ('For her sister, ', "Regarding her sister's visit, ",
                           'For her daughter, ', 'For a previous visit, ',
                           'However, for her sister, '):
                variant = note + ' ' + prefix + EXCLUSION[0].lower() + EXCLUSION[1:]
                with self.subTest(prefix=prefix, form='crlf' if '\r\n' in note else 'lf'):
                    fixture = self.bounded_fixture(variant, context_source=note)
                    actual_hash = fixture.run.requests[0]['response_sha256']
                    response_hash = response_hash or actual_hash
                    self.assertEqual(actual_hash, response_hash)
                    result = fixture.assessment()
                    self.assertEqual(result['selection']['code'], '99214')
                    self.assertEqual(self.assert_supported(variant)['facts'], baseline['facts'])

    def test_foreign_frame_cannot_hide_current_reassignment_or_unconsumed_qualifiers(self):
        foreign = 'For her sister, ' + EXCLUSION[0].lower() + EXCLUSION[1:].removesuffix('.')
        tails = (
            foreign + ', but the above physician time is incorrect.',
            foreign + ' and these activities were performed by staff.',
            foreign + '; the current physician total should be 29 minutes.',
            foreign + '. The above physician time belongs to her sister.',
            foreign + '. No services were provided to the current patient on the service date.',
            foreign + ' unless needed.',
            foreign + ', except five minutes.',
            foreign.replace('For her sister, ', 'For her sister unless needed, ') + '.',
        )
        response_hash = None
        for note in (LF, WIRE):
            for tail in tails:
                variant = note + ' ' + tail
                with self.subTest(tail=tail, form='crlf' if '\r\n' in note else 'lf'):
                    fixture = self.bounded_fixture(variant, context_source=note)
                    actual_hash = fixture.run.requests[0]['response_sha256']
                    response_hash = response_hash or actual_hash
                    self.assertEqual(actual_hash, response_hash)
                    self.assert_held(variant)
                    with self.assertRaises(ValidationError):
                        fixture.assessment()

    def test_separate_exclusion_cannot_supply_patient_facts_or_bridge_patient_adjacency(self):
        foreign = 'For her sister, ' + EXCLUSION[0].lower() + EXCLUSION[1:]
        for note in (LF, WIRE):
            for variant in (
                note.replace(EXCLUSION, foreign),
                note.replace(QUALIFICATION, QUALIFICATION + ' ' + foreign),
            ):
                with self.subTest(form='crlf' if '\r\n' in note else 'lf', variant=variant):
                    fixture = self.bounded_fixture(variant, context_source=note)
                    self.assert_held(variant)
                    with self.assertRaises(ValidationError):
                        fixture.assessment()
