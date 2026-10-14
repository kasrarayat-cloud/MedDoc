"""The applicable ICD-10-CM release is the one in effect on the date of service.

ICD-10-CM is published per federal fiscal year: FY27 codes apply to services
provided from 1 October 2026 through 30 September 2027. A note is frequently
written, coded and corrected after the visit, so selecting by today's date
silently applies the wrong fiscal year to any encounter coded across a
boundary — and, once the last loaded release expires, silently returns nothing.
"""
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core.coding import applicable_releases, cpt_licensed, suggest
from django.db import connection
from exercised import requires_input
import re

# The token regex `suggest` uses, quoted here so the coverage guard asks the same question the code does.
TOKEN_PATTERN = r'\b(?:[A-Z][0-9A-Z]{2}(?:\.[0-9A-Z]{1,4})?|[0-9]{5}|[0-9]{4}[FTU])\b'
from core.context import integration_status
from core.forms import EncounterForm
from core.management.commands.import_terminology import save_release
from core.models import AuditEvent, Code, CodeSet, CodeSuggestion, CodingDecision, CodingRun, Encounter, latest_service_date
from core.tests.test_coding_imports import LicensedCptImportFixture
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

    def test_retired_accept_endpoint_preserves_the_historical_dated_suggestion(self):
        """A valid historical release remains evidence, not a new-style approval."""
        before = CodeSuggestion.objects.filter(pk=self.suggestion.pk).values().get()
        with patch('core.coding.timezone.localdate', return_value=date(2027, 6, 1)):
            self.assertEqual([r.version for r in applicable_releases(self.encounter)], ['FY2026-April'])
            response = self.client.post(f'/encounters/{self.encounter.pk}/coding/{self.suggestion.pk}/accept/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/encounters/{self.encounter.pk}/?tab=coding')
        self.suggestion.refresh_from_db()
        self.assertIsNone(self.suggestion.accepted_at)
        self.assertEqual(CodeSuggestion.objects.filter(pk=self.suggestion.pk).values().get(), before)
        self.assertFalse(AuditEvent.objects.filter(action='coding.accept').exists())
        self.assertFalse(CodingDecision.objects.exists())

    def test_a_suggestion_whose_release_does_not_cover_the_date_of_service_cannot_be_accepted(self):
        Encounter.objects.filter(pk=self.encounter.pk).update(service_date=date(2026, 10, 1))
        response = self.client.post(f'/encounters/{self.encounter.pk}/coding/{self.suggestion.pk}/accept/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'/encounters/{self.encounter.pk}/?tab=coding')
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


@override_settings(AI_MODE='fixture', CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='',
                   STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class WhatTheRefutationPassFound(LicensedCptImportFixture, SyntheticFixture, TestCase):
    """Each test here is a defect a refutation lens demonstrated on the finished diff."""

    def setUp(self):
        self.user, _org, self.department, _patient, _template, self.encounter, _blob = self.make_scope('refuted')
        save_release({'M25.532': 'Synthetic wrist description, FY2026 wording',
                      'M25.53': 'Synthetic wrist description, shorter code',
                      'M25': 'Synthetic joint disorder, category code'}, dict(FY26))
        self.client.force_login(self.user)

    def code_with_notes(self, notes, service_date=date(2026, 9, 30)):
        Encounter.objects.filter(pk=self.encounter.pk).update(notes=notes, service_date=service_date)
        CodeSuggestion.objects.filter(encounter=self.encounter).delete()
        self.encounter.refresh_from_db()
        return suggest(self.encounter, self.user)

    def test_a_code_that_ends_a_sentence_is_still_documented(self):
        """The trailing dot of a sentence is punctuation, not part of the code."""
        for notes in ('Assessment: synthetic finding documented as M25.532.',
                      'Assessment: synthetic finding documented as M25.532',
                      'Assessment: synthetic finding documented as M25.532, and more.'):
            with self.subTest(notes=notes):
                result = self.code_with_notes(notes)
                self.assertEqual(result.count, 1)
                self.assertEqual(CodeSuggestion.objects.get(encounter=self.encounter).code, 'M25.532')

    def test_a_category_code_quotes_its_own_line_and_not_the_one_documenting_its_child(self):
        """The three-character parent is the case that separates the two lookaheads.

        Both 'M25' and 'M25.532' are documented, and the CHILD appears first. A lookahead that only
        rejects word characters lets the search for 'M25' match inside 'M25.532' — the dot is not a
        word character — so the category code's suggestion would quote the line documenting the
        wrist finding: evidence for something the clinician never wrote about that code. Rejecting
        every following dot instead, as the code did before this pass, drops BOTH codes silently,
        because each ends its sentence.
        """
        notes = ('Assessment: synthetic right wrist finding documented as M25.532.\n'
                 'Assessment: synthetic general joint finding documented as M25.')
        # THE INPUT THESE ASSERTIONS DEPEND ON, and the reason two earlier versions of this test were
        # empty: the evidence lookahead only ever runs on codes the TOKEN regex extracted. Neither
        # earlier version checked that, and in both the shorter code was never a token — so the
        # lookahead under test was never applied to it and the test passed under the broken form too.
        tokens = set(re.findall(TOKEN_PATTERN, notes.upper()))
        requires_input({'M25', 'M25.532'} <= tokens,
                       'BOTH the category code M25 and its child M25.532 extracted as tokens from '
                       'these notes (extracted: %s), or the lookahead under test never runs on the '
                       'shorter code and this test is about nothing' % sorted(tokens))
        requires_input(Code.objects.filter(code__in=['M25', 'M25.532'], release__version='FY2026-April').count() == 2,
                       'both codes present in the release being searched, or one of them can never '
                       'be suggested whatever the lookahead does')
        result = self.code_with_notes(notes)
        self.assertEqual(result.count, 2)
        evidence = {s.code: s.evidence for s in CodeSuggestion.objects.filter(encounter=self.encounter)}
        self.assertIn('right wrist', evidence['M25.532'])
        self.assertIn('general joint', evidence['M25'])
        self.assertNotIn('right wrist', evidence['M25'])

    def test_why_both_earlier_versions_of_the_prefix_check_were_empty(self):
        """Pin the two dead ends, so the prefix check is never rewritten back into either.

        Two versions of this test passed under BOTH the correct and the broken lookahead. Neither
        was a careless assertion; each was aimed at a case that cannot discriminate, and nothing
        said so. This test states why, in terms of the code's own token regex.
        """
        # DEAD END 1 — the shorter code is never extracted as a token, so the lookahead under test
        # never runs on it. `re.findall` does not produce overlapping matches: 'M25.532' consumes
        # the text, and 'M25.53' is never a candidate however the evidence search is written.
        notes = 'Assessment: synthetic right wrist finding documented as M25.532.'
        tokens = set(re.findall(TOKEN_PATTERN, notes.upper()))
        self.assertIn('M25.532', tokens)
        self.assertNotIn('M25.53', tokens,
                         'if this ever becomes a token, dead end 1 is gone and the first version of '
                         'the test would have been meaningful after all')

        # DEAD END 2 — even when both ARE tokens, a digit following the prefix makes the two
        # lookaheads agree: `(?!\w)` already rejects 'M25.53' inside 'M25.532' because '2' is a word
        # character. The broken form and the correct form give the same answer, so the case is blind.
        both = 'Line one documents M25.532.\nLine two documents M25.53.'
        for pattern, label in ((r'(?!\w)(?!\.[0-9A-Za-z])', 'shipped'), (r'(?!\w)', 'broken')):
            with self.subTest(lookahead=label):
                hit = bool(re.search(r'(?<![\w.])' + re.escape('M25.53') + pattern, both.splitlines()[0]))
                self.assertFalse(hit, 'neither lookahead matches the prefix here — which is exactly '
                                      'why the second version of the test could not tell them apart')

        # THE CASE THAT DOES DISCRIMINATE — a three-character parent, where the next character is a
        # dot rather than a digit. Only here do the two lookaheads disagree.
        parent_line = 'Line one documents M25.532.'
        shipped = bool(re.search(r'(?<![\w.])M25(?!\w)(?!\.[0-9A-Za-z])', parent_line))
        broken = bool(re.search(r'(?<![\w.])M25(?!\w)', parent_line))
        self.assertFalse(shipped, 'the shipped lookahead must not match M25 inside M25.532')
        self.assertTrue(broken, 'the broken lookahead does match it — this is the discriminating case')

    def test_historical_licensed_cpt_result_survives_retirement_of_the_old_post_action(self):
        """Real protected artificial entitlement, independently date-scoped from ICD."""
        self.set_up_licensed_cpt()
        self.manifest['content_release'].update(version='CPT-2026',effective_until='2026-03-31')
        self.write_entitlement()
        call_command('import_terminology', **{**self.args,'release_version':'CPT-2026','effective_until':'2026-03-31'})
        result = self.code_with_notes('Assessment: synthetic procedure documented as 00000 in the record.',
                                      service_date=date(2026, 3, 31))
        self.assertEqual((result.count, result.covered, result.versions), (1, False, ['CPT CPT-2026']))
        before = list(CodeSuggestion.objects.filter(encounter=self.encounter).values())
        response = self.client.post(f'/encounters/{self.encounter.pk}/coding/', follow=True)
        text = ' '.join(str(m) for m in response.context['messages'])
        self.assertIn('Open the current coding record', text)
        self.assertEqual(list(CodeSuggestion.objects.filter(encounter=self.encounter).values()), before)
        self.assertEqual(CodeSuggestion.objects.filter(encounter=self.encounter).count(), 1)
        self.assertFalse(CodingRun.objects.exists())
        self.assertFalse(CodingDecision.objects.exists())

    def test_retired_post_does_not_create_work_when_no_release_covers_the_date(self):
        result = self.code_with_notes('Assessment: synthetic finding documented as M25.532.', service_date=date(2026, 3, 31))
        self.assertEqual((result.count,result.covered,result.versions),(0,False,[]))
        response = self.client.post(f'/encounters/{self.encounter.pk}/coding/', follow=True)
        text = ' '.join(str(m) for m in response.context['messages'])
        self.assertIn('Open the current coding record', text)
        self.assertFalse(CodeSuggestion.objects.filter(encounter=self.encounter).exists())
        self.assertFalse(CodingRun.objects.exists())
        self.assertFalse(CodingDecision.objects.exists())

    def test_a_clinic_one_day_ahead_of_utc_can_record_the_visit_it_just_finished(self):
        """UTC is the stored zone; real offsets reach UTC+14, so the local date can lead by a day."""
        form = EncounterForm(user=self.user, data={})
        self.assertEqual(latest_service_date(), timezone.localdate() + timedelta(days=1))
        encounter = Encounter(department=self.encounter.department, patient=self.encounter.patient,
                              template_version=self.encounter.template_version, created_by=self.user,
                              notes='Synthetic', service_date=timezone.localdate() + timedelta(days=1))
        encounter.clean()
        encounter.service_date = timezone.localdate() + timedelta(days=2)
        with self.assertRaises(ValidationError):
            encounter.clean()
        self.assertIn('local time', form.fields['service_date'].help_text)

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2020-01-01')
    def test_an_expired_cpt_licence_is_not_reported_as_configured(self):
        status = {row['name']: row['status'] for row in integration_status()}
        self.assertEqual(status['CPT terminology'], 'License expired')
        self.assertFalse(cpt_licensed())

    @override_settings(CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='')
    def test_an_absent_cpt_licence_still_reports_license_required(self):
        self.assertEqual({row['name']: row['status'] for row in integration_status()}['CPT terminology'],
                         'License required')


@override_settings(AI_MODE='fixture')
class TheBackfillMustReachAFinalizedDocument(SyntheticFixture, TransactionTestCase):
    # TransactionTestCase, not TestCase, and that is load-bearing: a row written earlier in the SAME transaction leaves
    # pending trigger events and PostgreSQL then refuses `ALTER TABLE ... DISABLE TRIGGER` outright. The migration writes
    # no rows before it suspends the guard, so this class must not either, or the test would exercise a shape the
    # migration never meets and fail for a reason production would not have.
    """The first attempt at migration 0014 died here, and no test had a finalized encounter in it.

    `encounter_scope` refuses every update to a finalized document. Six of the eleven production encounters are
    finalized, so the backfill could not reach them — while every test fixture was a draft, and the migration test
    therefore passed without exercising the case that mattered.
    """

    def setUp(self):
        self.user, _org, _dept, _patient, _template, self.encounter, _blob = self.make_scope('finalized')
        Encounter.objects.filter(pk=self.encounter.pk).update(status='finalized')
        # THE INPUT THIS WHOLE CLASS DEPENDS ON. Every fixture encounter used to be a draft, so the
        # immutability guard was never reached and the migration proof passed without exercising the
        # case that failed in production. If make_scope ever stops producing a row this can finalize,
        # these tests must say so rather than pass.
        requires_input(Encounter.objects.filter(status='finalized').exists(),
                       'a FINALIZED encounter, or encounter_scope is never reached and every '
                       'assertion in this class is about a draft')
        with connection.cursor() as cursor:
            cursor.execute("SELECT tgenabled FROM pg_trigger WHERE tgrelid='core_encounter'::regclass "
                           "AND tgname='encounter_scope'")
            row = cursor.fetchone()
        requires_input(row is not None and row[0] == 'O',
                       'the encounter_scope trigger present and ENABLED in the test database, or a '
                       'refusal here would prove nothing about a guard that is not running')

    def test_the_guard_still_refuses_an_ordinary_update_to_a_finalized_document(self):
        from django.db import IntegrityError, InternalError, ProgrammingError, transaction
        with self.assertRaises((IntegrityError, InternalError, ProgrammingError, Exception)) as caught:
            with transaction.atomic():
                Encounter.objects.filter(pk=self.encounter.pk).update(notes='edited after finalization')
        self.assertIn('immutable', str(caught.exception).lower())
        self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.notes, 'edited after finalization')

    def test_suspending_the_guard_for_one_statement_lets_the_backfill_reach_it_and_restores_it(self):
        """This is exactly what the migration does, and it is the shape that failed in production when it did not."""
        from django.db import connection, transaction
        target = date(2026, 5, 4)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('ALTER TABLE core_encounter DISABLE TRIGGER encounter_scope')
            try:
                Encounter.objects.filter(pk=self.encounter.pk).update(service_date=target)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute('ALTER TABLE core_encounter ENABLE TRIGGER encounter_scope')
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.service_date, target)
        with connection.cursor() as cursor:
            cursor.execute("SELECT tgenabled FROM pg_trigger WHERE tgrelid='core_encounter'::regclass "
                           "AND tgname='encounter_scope'")
            self.assertEqual(cursor.fetchone()[0], 'O', 'the guard must be enabled again')

    def test_the_migration_suspends_and_restores_the_guard_around_the_backfill(self):
        source = (Path(__file__).resolve().parents[1] / 'migrations' / '0014_encounter_service_date.py').read_text()
        self.assertIn('DISABLE TRIGGER encounter_scope', source)
        self.assertIn('ENABLE TRIGGER encounter_scope', source)
        self.assertLess(source.index('DISABLE TRIGGER'), source.index('Encounter.objects.filter(pk=encounter.pk)'))
        self.assertGreater(source.index('ENABLE TRIGGER'), source.index('Encounter.objects.filter(pk=encounter.pk)'))
        self.assertIn('finally:', source)
