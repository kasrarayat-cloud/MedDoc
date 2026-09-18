"""The applicable ICD-10-CM release is the one in effect on the date of service.

ICD-10-CM is published per federal fiscal year: FY27 codes apply to services
provided from 1 October 2026 through 30 September 2027. A note is frequently
written, coded and corrected after the visit, so selecting by today's date
silently applies the wrong fiscal year to any encounter coded across a
boundary — and, once the last loaded release expires, silently returns nothing.
"""
from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.coding import applicable_releases, suggest
from core.management.commands.import_terminology import save_release
from core.models import AuditEvent, Code, CodeSet, CodeSuggestion, Encounter
from core.tests.test_security import SyntheticFixture

FY26 = dict(system='ICD-10-CM', version='FY2026-April', effective_from=date(2026, 4, 1),
            effective_until=date(2026, 9, 30), source_url='https://www.cms.gov/files/synthetic-fy26.txt',
            sha256='a' * 64, license_reference='')
FY27 = dict(system='ICD-10-CM', version='FY2027', effective_from=date(2026, 10, 1),
            effective_until=date(2027, 9, 30), source_url='https://ftp.cdc.gov/synthetic-fy27.txt',
            sha256='b' * 64, license_reference='')


@override_settings(AI_MODE='fixture', CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='')
class TheReleaseFollowsTheDateOfService(SyntheticFixture, TestCase):
    def setUp(self):
        self.user, _org, self.department, _patient, _template, self.encounter, _blob = self.make_scope('coding')
        self.encounter.notes = 'Assessment: synthetic finding documented as M25.532 in the record.'
        self.encounter.save(update_fields=['notes'])
        save_release({'M25.532': 'Synthetic wrist description, FY2026 wording'}, dict(FY26))
        save_release({'M25.532': 'Synthetic wrist description, FY2027 wording',
                      'Q99.999': 'Synthetic code introduced in FY2027'}, dict(FY27))

    def code_on(self, service_date, *, today=None):
        Encounter.objects.filter(pk=self.encounter.pk).update(service_date=service_date)
        CodeSuggestion.objects.filter(encounter=self.encounter).delete()
        self.encounter.refresh_from_db()
        if today is None:
            return suggest(self.encounter, self.user)
        with patch('core.coding.timezone.localdate', return_value=today):
            return suggest(self.encounter, self.user)

    def test_the_last_day_of_the_fiscal_year_and_the_first_day_of_the_next_select_different_releases(self):
        for service_date, expected in [(date(2026, 9, 30), 'FY2026-April'), (date(2026, 10, 1), 'FY2027')]:
            with self.subTest(service_date=service_date):
                result = self.code_on(service_date)
                self.assertEqual(result.count, 1)
                self.assertEqual(result.versions, [f'ICD-10-CM {expected}'])
                suggestion = CodeSuggestion.objects.get(encounter=self.encounter)
                self.assertEqual(suggestion.terminology.release.version, expected)
                self.assertIn(expected, suggestion.explanation)
                self.assertIn(service_date.isoformat(), suggestion.explanation)

    def test_the_wording_that_reaches_the_note_is_the_wording_of_that_year(self):
        self.assertEqual(self.code_on(date(2026, 9, 30)).count, 1)
        self.assertEqual(CodeSuggestion.objects.get(encounter=self.encounter).description,
                         'Synthetic wrist description, FY2026 wording')
        self.assertEqual(self.code_on(date(2026, 10, 1)).count, 1)
        self.assertEqual(CodeSuggestion.objects.get(encounter=self.encounter).description,
                         'Synthetic wrist description, FY2027 wording')

    def test_a_september_encounter_coded_in_december_still_gets_the_september_release(self):
        """The clock must not choose the fiscal year; only the date of service may."""
        result = self.code_on(date(2026, 9, 30), today=date(2027, 12, 1))
        self.assertEqual(result.versions, ['ICD-10-CM FY2026-April'])
        self.assertEqual(CodeSuggestion.objects.get(encounter=self.encounter).terminology.release.version,
                         'FY2026-April')

    def test_a_code_introduced_in_the_next_release_is_not_applied_to_an_earlier_visit(self):
        Encounter.objects.filter(pk=self.encounter.pk).update(
            notes='Assessment: synthetic finding documented as Q99.999 in the record.')
        self.encounter.refresh_from_db()
        self.assertEqual(self.code_on(date(2026, 9, 30)).count, 0)
        self.assertEqual(self.code_on(date(2026, 10, 1)).count, 1)

    def test_a_date_no_release_covers_is_disclosed_rather_than_answered_with_silence(self):
        result = self.code_on(date(2026, 3, 31))
        self.assertEqual((result.count, result.covered, result.versions), (0, False, []))
        event = AuditEvent.objects.filter(action='coding.suggest').latest('created_at')
        self.assertEqual(event.details['icd_covered'], False)
        self.assertEqual(event.details['service_date'], '2026-03-31')

    def test_the_audit_row_records_which_release_answered(self):
        self.code_on(date(2026, 10, 1))
        event = AuditEvent.objects.filter(action='coding.suggest').latest('created_at')
        self.assertEqual(event.details['releases'], ['ICD-10-CM FY2027'])
        self.assertEqual(event.details['service_date'], '2026-10-01')
        self.assertEqual(event.details['icd_covered'], True)

    @override_settings(CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='')
    def test_cpt_stays_out_of_the_answer_while_it_is_unlicensed(self):
        save_release({'99213': 'Synthetic office visit'},
                     dict(system='CPT', version='synthetic-cpt', effective_from=date(2026, 10, 1),
                          effective_until=date(2027, 9, 30), source_url='https://example.com/licensed',
                          sha256='c' * 64, license_reference='synthetic-license'))
        Encounter.objects.filter(pk=self.encounter.pk).update(
            notes='Assessment: synthetic visit documented as 99213 in the record.')
        self.encounter.refresh_from_db()
        result = self.code_on(date(2026, 10, 1))
        self.assertEqual((result.count, result.versions), (0, ['ICD-10-CM FY2027']))


@override_settings(AI_MODE='fixture', CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='',
                  STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                            'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class AcceptanceReadsTheSameRuleAsSuggestion(SyntheticFixture, TestCase):
    def setUp(self):
        self.user, _org, self.department, _patient, _template, self.encounter, _blob = self.make_scope('accept')
        self.user.membership_set.update(role='clinician')
        self.encounter.notes = 'Assessment: synthetic finding documented as M25.532 in the record.'
        Encounter.objects.filter(pk=self.encounter.pk).update(
            notes=self.encounter.notes, service_date=date(2026, 9, 30))
        self.encounter.refresh_from_db()
        save_release({'M25.532': 'Synthetic wrist description, FY2026 wording'}, dict(FY26))
        save_release({'M25.532': 'Synthetic wrist description, FY2027 wording'}, dict(FY27))
        suggest(self.encounter, self.user)
        self.suggestion = CodeSuggestion.objects.get(encounter=self.encounter)
        self.client.force_login(self.user)

    def test_an_expired_fiscal_year_still_accepts_for_a_visit_inside_it(self):
        """The release is not 'no longer current' for an encounter it covers."""
        with patch('core.coding.timezone.localdate', return_value=date(2027, 6, 1)):
            response = self.client.post(f'/encounters/{self.encounter.pk}/coding/{self.suggestion.pk}/accept/')
        self.assertEqual(response.status_code, 302)
        self.suggestion.refresh_from_db()
        self.assertIsNotNone(self.suggestion.accepted_at)
        self.assertEqual(AuditEvent.objects.filter(action='coding.accept').get().details['release'], 'FY2026-April')

    def test_a_suggestion_whose_release_does_not_cover_the_date_of_service_cannot_be_accepted(self):
        Encounter.objects.filter(pk=self.encounter.pk).update(service_date=date(2026, 10, 1))
        response = self.client.post(f'/encounters/{self.encounter.pk}/coding/{self.suggestion.pk}/accept/')
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'date of service', response.content)
        self.suggestion.refresh_from_db()
        self.assertIsNone(self.suggestion.accepted_at)
        self.assertFalse(AuditEvent.objects.filter(action='coding.accept').exists())

    def test_both_readers_answer_from_one_rule(self):
        self.assertEqual([r.version for r in applicable_releases(self.encounter)], ['FY2026-April'])
        Encounter.objects.filter(pk=self.encounter.pk).update(service_date=date(2026, 10, 1))
        self.encounter.refresh_from_db()
        self.assertEqual([r.version for r in applicable_releases(self.encounter)], ['FY2027'])


class ANewFiscalYearIsAddedBesideItsPredecessor(TestCase):
    def test_importing_the_next_release_neither_replaces_nor_rewrites_the_previous_one(self):
        first, created_first = save_release({'M25.532': 'Synthetic wrist description, FY2026 wording'}, dict(FY26))
        second, created_second = save_release({'M25.532': 'Synthetic wrist description, FY2027 wording'}, dict(FY27))
        self.assertTrue(created_first and created_second)
        self.assertEqual(CodeSet.objects.filter(system='ICD-10-CM').count(), 2)
        self.assertEqual(Code.objects.get(release=first).description,
                         'Synthetic wrist description, FY2026 wording')
        self.assertEqual(Code.objects.get(release=second).description,
                         'Synthetic wrist description, FY2027 wording')
        self.assertEqual(first.effective_until, date(2026, 9, 30))
        self.assertEqual(second.effective_from, date(2026, 10, 1))
        self.assertEqual(AuditEvent.objects.filter(action='terminology.import').count(), 2)
