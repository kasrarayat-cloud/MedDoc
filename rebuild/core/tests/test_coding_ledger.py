"""The ICD coding ledger (0034, core.coding): release identity on every suggestion and acceptance, append-only releases,
codes frozen at finalization, accepted codes never deleted by a notes save, dotless codes read or said, and the CPT
lock in code. Offline and synthetic: fixture generation, synthetic releases, no download and no provider.
"""
import io
import json
import zipfile
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from core import coding, models as m
from core.context import integration_status
from core.management.commands.import_terminology import save_release
from core.models import AuditEvent, Code, CodeSet, CodeSuggestion, Encounter
from . import test_workflow
from .test_workflow import TEST_SETTINGS

CURRENT = dict(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY=(timezone.localdate() + timedelta(days=365)).isoformat())


def icd_release(rows=None, sha='c' * 64, version='synthetic-ledger'):
    today = timezone.localdate()
    return save_release(rows or {'R07.9': 'Synthetic chest pain code', 'R00.0': 'Synthetic code two'},
                        dict(system='ICD-10-CM', version=version, effective_from=today - timedelta(days=30),
                             effective_until=today + timedelta(days=30), source_url='https://www.cms.gov/files/synthetic.txt',
                             sha256=sha, license_reference=''))[0]


def cpt_release():
    today = timezone.localdate()
    return save_release({'99213': 'SYNTHETIC CPT DESCRIPTOR NOT CPT CONTENT'},
                        dict(system='CPT', version='synthetic-cpt', effective_from=today - timedelta(days=30),
                             effective_until=today + timedelta(days=30), source_url='https://example.invalid/licensed',
                             sha256='d' * 64, license_reference='synthetic-license'))[0]


@override_settings(**TEST_SETTINGS)
class CodingLedger(TestCase):
    workflow = test_workflow.DocumentWorkflow
    setUp, make_docx, upload = workflow.setUp, workflow.make_docx, workflow.upload
    create_encounter, generate, review, finalize = workflow.create_encounter, workflow.generate, workflow.review, workflow.finalize
    NOTES = 'Symptoms: No chest pain.\nExamination: Normal gait.\nAssessment: documented as R07.9.'

    def document(self, notes=NOTES):
        _template, version = self.upload(self.make_docx(), 'docx')
        return self.create_encounter(version, notes)

    def suggest(self, encounter):
        encounter.refresh_from_db()
        return self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision}, follow=True)

    def accept(self, encounter, code):
        encounter.refresh_from_db()
        return self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/accept/', {'revision': encounter.revision})

    def save_notes(self, encounter, notes):
        encounter.refresh_from_db()
        return self.client.post(f'/encounters/{encounter.pk}/notes/', {'revision': encounter.revision, 'notes': notes}, follow=True)

    def text(self, response):
        return ' '.join(str(message) for message in response.context['messages'])

    def test_each_suggestion_and_acceptance_names_its_release_and_releases_are_append_only(self):
        release = icd_release()
        encounter = self.document(); self.suggest(encounter)
        code = CodeSuggestion.objects.get(encounter=encounter)
        self.assertEqual((code.code, code.release_sha256), ('R07.9', release.sha256))  # ac43e379: no identity recorded
        self.assertEqual(self.accept(encounter, code).status_code, 302)
        accepted = AuditEvent.objects.get(action='coding.accept', target=str(code.pk))
        self.assertEqual(accepted.details['release_sha256'], release.sha256)
        suggested = AuditEvent.objects.filter(action='coding.suggest').latest('created_at')
        self.assertEqual(suggested.details['release_sha256'], [release.sha256])
        refused = {
            'release edited': lambda: CodeSet.objects.filter(pk=release.pk).update(sha256='e' * 64),
            'release deleted': lambda: connection.cursor().execute('DELETE FROM core_codeset WHERE id=%s', [release.pk]),
            'code edited': lambda: Code.objects.filter(release=release).update(description='SYNTHETIC REWRITE'),
            'code deleted': lambda: connection.cursor().execute('DELETE FROM core_code WHERE release_id=%s', [release.pk]),
            'wrong identity': lambda: CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(code='R00.0'),
                                                                    evidence='x', explanation='x', release_sha256='f' * 64),
            'evidence rewritten': lambda: CodeSuggestion.objects.filter(pk=code.pk).update(evidence='SYNTHETIC OTHER'),
            'code swapped': lambda: CodeSuggestion.objects.filter(pk=code.pk).update(terminology=Code.objects.get(code='R00.0')),
        }
        for label, action in refused.items():
            with self.subTest(label), self.assertRaises(DatabaseError), transaction.atomic(): action()
        self.assertEqual(CodeSet.objects.get(pk=release.pk).sha256, release.sha256)

    def test_a_changed_notes_save_keeps_an_accepted_code_for_re_review_and_finalizing_waits_for_it(self):
        icd_release()
        encounter = self.document('Symptoms: No chest pain, R07.9.\nExamination: Normal gait.'); self.suggest(encounter)
        code = CodeSuggestion.objects.get(encounter=encounter); self.accept(encounter, code)
        CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(code='R00.0'), evidence='No chest pain.',
                                      explanation='Synthetic unaccepted suggestion')
        response = self.save_notes(encounter, 'Symptoms: No chest pain, R07.9.\nExamination: Normal gait, steady.')
        rows = list(CodeSuggestion.objects.filter(encounter=encounter).values_list('pk', 'accepted_by_id', 'review_required'))
        self.assertEqual(rows, [(code.pk, self.user.pk, True)])  # ac43e379: deleted with the unaccepted one
        self.assertIn('Kept and marked for re-review: 1 accepted code.', self.text(response))
        page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding').content.decode()
        self.assertIn('data-code-review', page); self.assertIn('Accept again', page); self.assertIn('Withdraw acceptance', page)
        # The database never lets an accepted code be deleted directly.
        with self.assertRaisesMessage(DatabaseError, 'An accepted code is never deleted'), transaction.atomic():
            CodeSuggestion.objects.filter(pk=code.pk).delete()
        # Finalizing waits until the clinician confirms or withdraws it.
        self.generate(encounter); self.review(encounter)
        refused = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'reviewed': 'on', 'revision': encounter.revision}, follow=True)
        self.assertIn('marked for re-review', self.text(refused))
        encounter.refresh_from_db(); self.assertEqual(encounter.status, 'review')
        self.assertEqual(self.accept(encounter, code).status_code, 302)  # accepted again: the mark clears
        code.refresh_from_db(); self.assertFalse(code.review_required)
        self.assertTrue(AuditEvent.objects.filter(action='coding.reaccept', target=str(code.pk)).exists())
        exported = self.finalize(encounter)
        # Frozen with the document: nothing added, changed or removed afterwards.
        for label, action in {'accept cleared': lambda: CodeSuggestion.objects.filter(pk=code.pk).update(accepted_by=None),
                              'deleted': lambda: connection.cursor().execute('DELETE FROM core_codesuggestion WHERE id=%s', [code.pk]),
                              'added': lambda: CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(code='R00.0'),
                                                                             evidence='x', explanation='x')}.items():
            with self.subTest(label), self.assertRaisesMessage(DatabaseError, 'finalized document are frozen'), transaction.atomic():
                action()
        # The export is the clinician's filled form: it has no coding section, so no coding output (a code's release
        # descriptor) reaches it; text the clinician wrote into an answer is the clinician's (recorded, nothing added).
        with zipfile.ZipFile(io.BytesIO(exported)) as archive:
            body = archive.read('word/document.xml').decode()
        self.assertNotIn('Synthetic chest pain code', body)

    def test_F7_a_hidden_cpt_acceptance_marked_for_re_review_can_be_withdrawn_without_being_shown(self):
        """Refutation F7 (dc33e094): a CPT acceptance recorded under a licence, then marked for re-review by a notes change,
        blocked finalizing while the coding tab hid it (CPT is locked) and offered no way to withdraw it."""
        icd_release(); cpt = cpt_release()
        encounter = self.document('Symptoms: No chest pain, CPT 99213.\nExamination: Normal gait.')
        stored = CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(release=cpt, code='99213'),
            evidence='Symptoms: No chest pain, CPT 99213.', explanation='Stored CPT', accepted_by=self.user, accepted_at=timezone.now())
        self.save_notes(encounter, 'Symptoms: No chest pain, CPT 99213.\nExamination: Normal gait, steady.')
        stored.refresh_from_db(); self.assertTrue(stored.review_required)
        page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding').content.decode()
        self.assertNotIn('SYNTHETIC CPT DESCRIPTOR NOT CPT CONTENT', page); self.assertNotIn('99213', page)  # still hidden
        self.assertIn(f'/coding/{stored.pk}/withdraw/', page)        # dc33e094: no way to withdraw it
        self.assertIn('data-hidden-cpt', page)
        self.generate(encounter); self.review(encounter)
        refused = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'reviewed': 'on', 'revision': encounter.revision},
                                   follow=True)
        self.assertIn('marked for re-review', self.text(refused))
        encounter.refresh_from_db()
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/{stored.pk}/withdraw/',
                                          {'revision': encounter.revision, 'accepted': self.acceptance(stored)}).status_code, 302)
        self.assertFalse(CodeSuggestion.objects.filter(pk=stored.pk).exists())
        encounter.refresh_from_db()
        self.finalize(encounter)  # nothing blocks it any more

    def test_F12_withdraw_needs_an_owner_or_clinician_and_the_current_revision(self):
        icd_release()
        encounter = self.document(); self.suggest(encounter)
        code = CodeSuggestion.objects.get(encounter=encounter); self.accept(encounter, code)
        encounter.refresh_from_db()
        employee = m.User.objects.create_user(username='coding-employee', email='coding-employee@synthetic.invalid',
                                              verified_at=timezone.now())
        m.Membership.objects.create(user=employee, department=self.department, role='employee')
        from django.test import Client
        other = Client(); other.force_login(employee)
        self.assertEqual(other.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/',
                                    {'revision': encounter.revision, 'accepted': self.acceptance(code)}).status_code, 403)
        stale = self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/',
                                 {'revision': encounter.revision - 1, 'accepted': self.acceptance(code)})
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(CodeSuggestion.objects.filter(pk=code.pk, accepted_by__isnull=False).exists())
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/',
                                          {'revision': encounter.revision, 'accepted': self.acceptance(code)}).status_code,
                         302)  # the control

    def test_reversing_0034_refuses_while_ledger_evidence_exists(self):
        import importlib
        reverse = importlib.import_module('core.migrations.0034_coding_ledger').REVERSE
        icd_release(); encounter = self.document(); self.suggest(encounter)
        with self.assertRaisesMessage(DatabaseError, 'requires a forward migration'), transaction.atomic():
            with connection.cursor() as cursor: cursor.execute(reverse)
        self.assertEqual(CodeSuggestion.objects.exclude(release_sha256='').count(), 1)

    def test_an_accepted_code_can_be_withdrawn_explicitly_and_is_audited(self):
        icd_release()
        encounter = self.document(); self.suggest(encounter)
        code = CodeSuggestion.objects.get(encounter=encounter); self.accept(encounter, code)
        encounter.refresh_from_db()
        response = self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/',
                                    {'revision': encounter.revision, 'accepted': self.acceptance(code)})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CodeSuggestion.objects.filter(pk=code.pk).exists())
        event = AuditEvent.objects.get(action='coding.withdraw', target=str(code.pk))
        self.assertEqual(event.details['previously_accepted_by'], str(self.user.pk))
        stale = self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/', {'revision': encounter.revision})
        self.assertEqual(stale.status_code, 409)

    # Refutation F4 (dc33e094): reading a dotless token as the dotted diagnosis it would name turned HCPCS Level II codes
    # into diagnoses (G0439 -> G04.39 encephalopathy, J1100 -> J11.00 influenza), suggested and accepted. A dotless token
    # is never looked up; it is said, so it is never dropped silently either.
    P4 = ('Visit: Medicare annual wellness visit, subsequent, billed as G0439.\n'
          'Prior year: initial preventive physical examination G0402.\n'
          'Medication administered: J1100 dexamethasone sodium phosphate 10 mg IM.\n'
          'Assessment: Z00.00.')
    DOTLESS_SAID = 'written without a dot; not looked up'

    def test_dotless_and_hcpcs_tokens_are_never_read_as_diagnoses_and_are_said(self):
        icd_release({'G04.39': 'Synthetic encephalopathy', 'G04.02': 'Synthetic encephalitis', 'J11.00': 'Synthetic influenza',
                     'Z00.00': 'Synthetic general examination', 'R07.9': 'Synthetic chest pain code',
                     'S72.001A': 'Synthetic fracture, initial encounter'})
        encounter = self.document(self.P4)
        response = self.suggest(encounter)
        self.assertEqual(list(CodeSuggestion.objects.filter(encounter=encounter).values_list('terminology__code', flat=True)),
                         ['Z00.00'])  # dc33e094: G04.39, G04.02 and J11.00 too
        self.assertIn('3 entries in the notes look like a code ' + self.DOTLESS_SAID, self.text(response))
        self.assertIn('Type a diagnosis code with its dot', self.text(response))
        # The 4-character and the 7-character dotless forms of real diagnosis codes are said and not looked up either.
        for notes, said in (('Assessment: documented as R079.', '1 entry in the notes looks like a code '),
                            ('Assessment: documented as S72001A.', '1 entry in the notes looks like a code ')):
            with self.subTest(notes=notes):
                CodeSuggestion.objects.filter(encounter=encounter).delete()
                Encounter.objects.filter(pk=encounter.pk).update(notes='Symptoms: No chest pain.\n' + notes)
                response = self.suggest(encounter)
                self.assertFalse(CodeSuggestion.objects.filter(encounter=encounter).exists())
                self.assertIn(said + self.DOTLESS_SAID, self.text(response))

    def test_lab_names_units_and_zip_codes_are_not_counted_as_codes(self):
        icd_release({'R07.9': 'Synthetic chest pain code'})
        notes = ('Labs: A1C 7.2, B12 normal, CO2 24, G6PD normal, H1N1 negative.\n'
                 'Plan: heparin 10000 units SC; follow up at clinic ZIP 90210.\nAssessment: R07.9.')
        response = self.suggest(self.document(notes))
        text = self.text(response)
        self.assertIn('1 new suggestions', text)
        for wrong in ('not a code in that release', 'written like a CPT code', 'not looked up: CPT content'):
            self.assertNotIn(wrong, text)  # dc33e094: 5 lab names as diagnosis codes, 10000 and 90210 as CPT codes
        self.assertNotIn(self.DOTLESS_SAID, text)

    def test_a_dotted_code_missing_from_the_release_and_a_named_cpt_code_are_said(self):
        icd_release({'R07.9': 'Synthetic chest pain code'})
        response = self.suggest(self.document('Assessment: R07.99 and R07.9.\nPlan: office visit, CPT 99213.'))
        text = self.text(response)
        self.assertIn('1 entry in the notes written like a diagnosis code is not a code in that release', text)
        self.assertIn('1 CPT code named in the notes was not looked up: CPT content is not licensed for use in this product', text)

    # Refutation round 2 of 4cfa4301, coding lens (C1-C5, C10, FG-6, FG-7, FG-8).
    UNLABELLED_SAID = 'not labelled as one; not suggested'

    def suggested(self, encounter):
        return sorted(CodeSuggestion.objects.filter(encounter=encounter).values_list('terminology__code', flat=True))

    def another(self, notes):
        """A further document on one uploaded template (uploading the same synthetic form twice is refused)."""
        if not hasattr(self, '_version'):
            _template, self._version = self.upload(self.make_docx(), 'docx')
        response = self.client.post('/encounters/new/', {'patient': self.patient.pk, 'template_version': self._version.pk,
                                    'notes': notes, 'service_date': timezone.localdate().isoformat(), 'synthetic_only': 'on'})
        self.assertEqual(response.status_code, 302)
        return Encounter.objects.filter(template_version=self._version).order_by('-created_at').first()

    def test_C1_a_dotless_code_whose_third_character_is_a_letter_is_said(self):
        """aa3eead4 required two digits after the letter, so Z3A20, O9A211 and M1A0710 (categories Z3A, O9A, M1A) fell
        through every path: nothing suggested, said or audited. They are said like R079, and never looked up."""
        icd_release({'Z3A.20': 'Synthetic 20 weeks gestation', 'O9A.211': 'Synthetic injury complicating pregnancy',
                     'M1A.0710': 'Synthetic chronic gout right ankle', 'R07.9': 'Synthetic chest pain code'})
        encounter = self.another('Assessment: 20 weeks gestation, Z3A20; injury in pregnancy O9A211; gout M1A0710.')
        response = self.suggest(encounter)
        self.assertEqual(self.suggested(encounter), [])
        self.assertIn('3 entries in the notes look like a code ' + self.DOTLESS_SAID, self.text(response))  # 4cfa4301: silent
        self.assertEqual(AuditEvent.objects.filter(action='coding.suggest').latest('created_at').details['written_without_dot'], 3)

    def test_C3_a_dotless_shape_whose_category_no_release_holds_is_not_counted(self):
        """A gene variant or a dose (C282Y, H63D, q12h) has the dotless shape too; it is counted only when its first three
        characters are a category of the release in effect. G6PD and H1N1 name no category, R079's R07 does."""
        icd_release({'R07.9': 'Synthetic chest pain code'})
        notes = ('Plan: vancomycin q12h.\nLabs: HFE C282Y homozygous, H63D negative; G6PD normal, H1N1 negative.\n'
                 'Assessment: R07.9.')
        encounter = self.another(notes)
        response = self.suggest(encounter)
        self.assertEqual(self.suggested(encounter), ['R07.9'])
        self.assertNotIn(self.DOTLESS_SAID, self.text(response))  # 4cfa4301: "3 entries ... without a dot"
        control = self.suggest(self.another('Symptoms: chest pain, r079 written in lower case.\nAssessment: R07.9.'))
        self.assertIn('1 entry in the notes looks like a code ' + self.DOTLESS_SAID, self.text(control))  # FG-7: case-folded

    def test_C2_words_joined_by_a_dot_are_not_told_as_diagnosis_codes(self):
        icd_release({'R07.9': 'Synthetic chest pain code'})
        response = self.suggest(self.another('Denies SOB.Has cough.\nVit.D low; Labs: CBC.BMP pending.\nAssessment: R07.9.'))
        self.assertNotIn('not a code in that release', self.text(response))  # 4cfa4301: "3 entries ... not a code"
        control = self.suggest(self.another('Assessment: R07.99 and R07.9.'))
        self.assertIn('1 entry in the notes written like a diagnosis code is not a code in that release', self.text(control))

    def test_C4_FG6_every_named_cpt_code_is_counted_in_every_labelled_form(self):
        icd_release({'R07.9': 'Synthetic chest pain code'})
        for notes, count in (('Plan: CPT 99213, 99214 and 36415.', 3),        # 4cfa4301: 1
                             ('Plan: CPT® 99213; CPT-4 99214.', 2),      # 4cfa4301: nothing said
                             ('Plan: office visit, CPT code 99213.', 1), ('Plan: office visit, CPT: 99213.', 1),
                             ('Plan: CPT 99213, heparin 10000 units.', 1), ('Plan: CPT 49000.', 1)):
            with self.subTest(notes=notes):
                text = self.text(self.suggest(self.another(notes + '\nAssessment: R07.9.')))
                said = (f'{count} CPT code{"" if count == 1 else "s"} named in the notes '
                        f'{"was" if count == 1 else "were"} not looked up: CPT content')
                self.assertIn(said, text)

    def test_C10_a_three_character_entry_is_suggested_only_where_a_code_label_names_it(self):
        """4cfa4301 looked up every three-character token of the case-folded notes, so 'p53 wild-type' (an immunostain)
        was suggested as P53, hemorrhagic disease of newborn, 'explicitly documented', and accepted. A three-character code
        is suggested only where the line that first documents it labels it as a code ('ICD-10: I10'); otherwise it is
        counted and said, never suggested (fail closed: lab and gene names such as p53, B12, A1C and CO2 have this shape)."""
        icd_release({'P53': 'Synthetic hemorrhagic disease of newborn', 'B12': 'Synthetic three-character code',
                     'A1C': 'Synthetic three-character code', 'CO2': 'Synthetic three-character code',
                     'R51': 'Synthetic headache', 'I10': 'Synthetic essential hypertension',
                     'C18.7': 'Synthetic malignant neoplasm of sigmoid colon'})
        notes = ('Pathology: sigmoid adenocarcinoma, C18.7. Immunostains: p53 wild-type pattern, MMR proficient.\n'
                 'Labs: CO2 24, B12 normal, A1C 6.1, G6PD normal.\n'
                 'Assessment: headache and hypertension, ICD-10: R51, I10.')
        encounter = self.another(notes)
        response = self.suggest(encounter)
        self.assertEqual(self.suggested(encounter), ['C18.7', 'I10', 'R51'])  # 4cfa4301: P53, CO2, B12 and A1C too
        self.assertIn('4 three-character entries in the notes match a diagnosis code but are ' + self.UNLABELLED_SAID,
                      self.text(response))
        evidence = dict(CodeSuggestion.objects.filter(encounter=encounter).values_list('terminology__code', 'evidence'))
        self.assertIn('ICD-10: R51, I10', evidence['I10'])
        self.assertEqual(AuditEvent.objects.filter(action='coding.suggest').latest('created_at').details[
            'three_character_unlabelled'], 4)
        for written, labelled in (('Assessment: hypertension I10.', False), ('Assessment: hypertension (I10).', False),
                                  ('Assessment: ICD-10-CM code: I10.', True), ('Assessment: Dx code I10.', True),
                                  ('Assessment: ICD10 I10 and R51.', True), ('Assessment: diagnosis codes R51; I10', True),
                                  ('Assessment: icd-10: i10.', True)):
            with self.subTest(written=written):
                again = self.another(written)
                text = self.text(self.suggest(again))
                self.assertEqual('I10' in self.suggested(again), labelled)
                self.assertEqual('1 three-character entry in the notes matches a diagnosis code but is ' + self.UNLABELLED_SAID
                                 in text, not labelled)
        # The line that FIRST documents the code decides: a later label does not turn an earlier unlabelled mention into one.
        first = self.another('Immunostains: P53 positive.\nICD-10: P53.')
        self.suggest(first)
        self.assertEqual(self.suggested(first), [])

    def test_C10_the_label_scan_is_linear(self):
        import time
        icd_release({'I10': 'Synthetic essential hypertension'})
        encounter = self.another('Assessment: ' + ('ICD-10' + ' ' * 5000) * 8 + 'I10.')
        started = time.monotonic()
        planned = coding.plan(encounter)
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertEqual([code.code for code, _line in planned.found], ['I10'])

    def acceptance(self, code):
        code.refresh_from_db()
        return code.acceptance

    def test_C5_a_withdraw_from_a_page_older_than_another_acceptance_is_refused(self):
        """Accepting does not renumber the revision, so a withdraw from a page loaded before clinician B accepted again
        deleted B's fresh acceptance (4cfa4301: 302, suggestion gone). The form posts the acceptance it showed."""
        icd_release()
        encounter = self.another(self.NOTES); self.suggest(encounter)
        code = CodeSuggestion.objects.get(encounter=encounter); self.accept(encounter, code)
        self.save_notes(encounter, self.NOTES + '\nPlan: follow up.')
        encounter.refresh_from_db()
        shown = self.acceptance(code)  # what A's page shows: accepted by A, needs re-review
        page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding').content.decode()
        self.assertIn(f'name="accepted" value="{shown}"', page)
        b = m.User.objects.create_user(username='coding-b', email='coding-b@synthetic.invalid', verified_at=timezone.now())
        m.Membership.objects.create(user=b, department=self.department, role='clinician')
        from django.test import Client
        b_client = Client(); b_client.force_login(b)
        self.assertEqual(b_client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/accept/',
                                       {'revision': encounter.revision}).status_code, 302)
        stale = self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/',
                                 {'revision': encounter.revision, 'accepted': shown})
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(CodeSuggestion.objects.filter(pk=code.pk, accepted_by=b).exists())  # B's acceptance stands
        missing = self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/', {'revision': encounter.revision})
        self.assertEqual(missing.status_code, 409)
        current = self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/',
                                   {'revision': encounter.revision, 'accepted': self.acceptance(code)})
        self.assertEqual(current.status_code, 302)  # the control: the page showing B's acceptance withdraws it
        self.assertFalse(CodeSuggestion.objects.filter(pk=code.pk).exists())

    def test_FG8_an_unaccepted_hidden_cpt_suggestion_is_not_offered_for_withdrawal(self):
        icd_release(); cpt = cpt_release()
        encounter = self.another('Symptoms: No chest pain, CPT 99213.\nExamination: Normal gait.')
        CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(release=cpt, code='99213'),
                                      evidence='Symptoms: No chest pain, CPT 99213.', explanation='Stored CPT')
        page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding').content.decode()
        self.assertNotIn('data-hidden-cpt', page); self.assertNotIn('/withdraw/', page)
        self.assertIn('No code suggestions yet', page)

    # Refutation round 3 of 75d11c09, coding lens (R3C-1..R3C-5) and its false greens (R3F-7, R3F-8, R3F-12..R3F-14).
    def said_unlabelled(self, text):
        return 'not labelled as one; not suggested' in text

    def test_R3C1_a_labelled_list_reads_only_items_written_as_codes(self):
        """75d11c09: CODE_LIST took any code-shaped token after a separator, so a label followed by a synoptic line absorbed
        the stain or gene name next to it ('ICD-10 C18.7, p53 wild-type' suggested P53, hemorrhagic disease of newborn, as
        explicitly documented, and it was accepted). The code right after a label is labelled; each LATER item of its list
        must be written in capitals and end its item (a separator, a closing mark or the end of the line)."""
        icd_release({'C18.7': 'Synthetic sigmoid colon', 'P53': 'Synthetic hemorrhagic disease of newborn',
                     'L45': 'Synthetic papulosquamous disorder', 'M51.26': 'Synthetic lumbar disc', 'I10': 'Synthetic hypertension',
                     'R51': 'Synthetic headache'})
        for notes, suggested in (
                ('Pathology: sigmoid adenocarcinoma, ICD-10 C18.7, p53 wild-type pattern, MMR proficient.', ['C18.7']),
                ('Diagnosis codes: C18.7; p53 wild-type; MMR proficient.', ['C18.7']),
                ('ICD-10: TBD, p53 wild-type, MMR intact.', []),
                ('ICD-10: M51.26; L45 herniation with radiculopathy.', ['M51.26']),
                ('Assessment: ICD-10: I10 and p53 wild-type on the biopsy.', ['I10']),
                ('ICD-10: C18.7, p53, MMR proficient.', ['C18.7']),                # a later item in lower case
                ('ICD-10: R51, I10 hypertension.', ['R51']),                        # the cost: an item followed by words
                ('ICD-10: R51, I10.', ['I10', 'R51']), ('ICD-10: R51, and I10', ['I10', 'R51']),
                ('ICD-10: R51 or I10', ['I10', 'R51']), ('ICD-10: R51 & I10', ['I10', 'R51']),     # R3C-5, R3F-13
                ('ICD: R51/I10', ['I10', 'R51']), ('ICD: I10.', ['I10'])):                      # R3F-13, R3F-14
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                text = self.text(self.suggest(encounter))
                self.assertEqual(self.suggested(encounter), suggested)          # 75d11c09: P53 and L45 suggested
                three = [code for code in ('P53', 'L45', 'I10', 'R51') if code.lower() in notes.lower()]
                self.assertEqual(self.said_unlabelled(text), bool(set(three) - set(suggested)), text)

    def test_R3C2_a_code_written_touching_other_characters_is_said(self):
        """75d11c09 (and before): a code the release holds, written '1.R07.9' or 'R07.9.Plan', was found by the lookup but
        refused by the evidence reading, which reached no counter: nothing suggested, nothing said."""
        icd_release({'R07.9': 'Synthetic chest pain code', 'I10': 'Synthetic hypertension', 'E11.9': 'Synthetic diabetes'})
        for notes, said in (('Assessment:\n1.R07.9 Chest pain\n2.ICD-10 I10 Hypertension\n3.E11.9 Type 2 diabetes\nPlan: follow up.',
                             '2 codes from the release in effect are written touching'),
                            ('Assessment: chest pain R07.9.Plan: follow up.', '1 code from the release in effect is written touching'),
                            ('Assessment: chest pain.R07.9 noted.', '1 code from the release in effect is written touching')):
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                text = self.text(self.suggest(encounter))
                self.assertIn(said, text)                                         # 75d11c09: nothing said
                self.assertEqual(AuditEvent.objects.filter(action='coding.suggest').latest('created_at').details[
                    'written_touching'], int(said[0]))
        control = self.another('Assessment:\n1. R07.9 Chest pain\n2. ICD-10 I10 Hypertension\n3. E11.9 Type 2 diabetes')
        self.assertNotIn('written touching', self.text(self.suggest(control)))
        self.assertEqual(self.suggested(control), ['E11.9', 'I10', 'R07.9'])

    def test_R3C3_a_category_with_a_letter_second_is_counted_with_or_without_its_dot(self):
        """FY2026 holds QA0.* (a letter second). C2's 'digit second' made a mistyped QA0 code silent."""
        icd_release({'QA0.0101': 'Synthetic FY2026 code', 'QA0.8': 'Synthetic FY2026 code', 'R07.9': 'Synthetic chest pain code'})
        for notes, said in (('Assessment: QA0.019 documented.', '1 entry in the notes written like a diagnosis code is not a code'),
                            ('Assessment: QA00101 documented.', '1 entry in the notes looks like a code written without a dot')):
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                self.assertIn(said, self.text(self.suggest(encounter)))          # 75d11c09: nothing said
                self.assertEqual(self.suggested(encounter), [])
        control = self.another('Assessment: QA0.0101 documented; denies SOB.Has cough.')
        text = self.text(self.suggest(control))
        self.assertEqual(self.suggested(control), ['QA0.0101'])
        self.assertNotIn('not a code in that release', text)                      # C2 still holds for words joined by a dot

    def test_R3C5_R3F12_R3F13_every_labelled_cpt_form_and_separator_is_counted(self):
        icd_release({'R07.9': 'Synthetic chest pain code'})
        for notes, count in (('Plan: CPT 99213 & 36415.', 2), ('Plan: CPT 99213, 99214 & 36415.', 3),   # 75d11c09: 1, 2
                             ('Plan: CPT 99213 + 36415.', 2), ('Plan: office visit, CPT(R) 99213.', 1),
                             ('Plan: CPT 99213/36415.', 2), ('Plan: CPT 99213 or 36415.', 2), ('Plan: CPT 99213, and 36415.', 2)):
            with self.subTest(notes=notes):
                text = self.text(self.suggest(self.another(notes + '\nAssessment: R07.9.')))
                self.assertIn(f'{count} CPT code{"" if count == 1 else "s"} named in the notes '
                              f'{"was" if count == 1 else "were"} not looked up: CPT content', text)

    def hidden_cpt_acceptance(self):
        icd_release(); cpt = cpt_release()
        encounter = self.another('Symptoms: No chest pain, CPT 99213.\nExamination: Normal gait.')
        stored = CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(release=cpt, code='99213'),
            evidence='Symptoms: No chest pain, CPT 99213.', explanation='Stored CPT', accepted_by=self.user, accepted_at=timezone.now())
        return encounter, stored

    def test_R3C4_withdrawing_a_hidden_cpt_acceptance_never_records_its_code(self):
        encounter, stored = self.hidden_cpt_acceptance()
        encounter.refresh_from_db()
        response = self.client.post(f'/encounters/{encounter.pk}/coding/{stored.pk}/withdraw/',
                                    {'revision': encounter.revision, 'accepted': self.acceptance(stored)})
        self.assertEqual(response.status_code, 302)
        event = AuditEvent.objects.get(action='coding.withdraw', target=str(stored.pk))
        self.assertNotIn('99213', json.dumps(event.details))                      # 75d11c09: {'code': '99213', ...}
        self.assertEqual(event.details['system'], 'CPT')

    def test_R3F7_the_hidden_form_posts_the_acceptance_it_renders(self):
        import re
        encounter, stored = self.hidden_cpt_acceptance()
        self.save_notes(encounter, 'Symptoms: No chest pain, CPT 99213.\nExamination: Normal gait, steady.')
        page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding').content.decode()
        section = re.search(r'<section class="answer" data-hidden-cpt>.*?</section>', page, re.S).group()
        action = re.search(r'<form method="post" action="([^"]+)"', section).group(1)
        fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', section))
        self.assertEqual(self.client.post(action, fields).status_code, 302)       # without 'accepted': 409 for good
        self.assertFalse(CodeSuggestion.objects.filter(pk=stored.pk).exists())

    def test_R3F8_a_withdraw_from_a_page_older_than_the_same_clinicians_re_acceptance_is_refused(self):
        icd_release()
        encounter = self.another(self.NOTES); self.suggest(encounter)
        code = CodeSuggestion.objects.get(encounter=encounter); self.accept(encounter, code)
        self.save_notes(encounter, self.NOTES + '\nPlan: follow up.')
        shown = self.acceptance(code)                                            # B's page shows A's acceptance
        b = m.User.objects.create_user(username='coding-b2', email='coding-b2@synthetic.invalid', verified_at=timezone.now())
        m.Membership.objects.create(user=b, department=self.department, role='clinician')
        from django.test import Client
        b_client = Client(); b_client.force_login(b)
        self.assertEqual(self.accept(encounter, code).status_code, 302)          # A accepts again: same clinician
        encounter.refresh_from_db()
        self.assertEqual(b_client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/',
                                       {'revision': encounter.revision, 'accepted': shown}).status_code, 409)
        self.assertTrue(CodeSuggestion.objects.filter(pk=code.pk, accepted_by=self.user).exists())

    # Refutation round 4 of b3d8111d, coding lens (R4C-1..R4C-4) and its false greens (R4F-7..R4F-12).
    def test_R4C1_a_stain_beside_a_labelled_code_is_never_read_as_a_listed_code(self):
        """b3d8111d: '+' separated and ended ICD list items, and '/' or 'and' ended an item whatever followed it, so 'ICD-10
        C18.7, P53+' (stain-positive) and 'C18.7 & P53/MLH1' suggested P53 as an explicitly documented diagnosis. Later
        items of a labelled list are read only when the WHOLE list is codes, to its clause end."""
        icd_release({'C18.7': 'Synthetic sigmoid colon', 'P53': 'Synthetic hemorrhagic disease of newborn',
                     'I10': 'Synthetic hypertension', 'R51': 'Synthetic headache', 'R07.9': 'Synthetic chest pain code'})
        for notes, suggested in (
                ('Pathology: sigmoid adenocarcinoma, ICD-10 C18.7, P53+, MMR proficient.', ['C18.7']),     # 1a
                ('Pathology: ICD-10: C18.7 & P53/MLH1 loss.', ['C18.7']),                                 # 1b
                ('Pathology: ICD-10 C18.7 + P53, MLH1 retained.', ['C18.7']),                             # 1c
                ('Pathology: ICD-10: C18.7, P53 and MLH1 retained.', ['C18.7']),                          # 1d
                ('ICD-10: R51, I10 and R07.9.', ['I10', 'R07.9', 'R51']),                                 # R4F-7
                ('Assessment (ICD-10: R51, I10) reviewed.', ['I10', 'R51']),                              # R4F-8
                ('Assessment [ICD-10: R51, I10] reviewed.', ['I10', 'R51']),
                ('Seen by Dr Strauß. ICD-10: R51, I10.', ['I10', 'R51']),                             # R4F-9
                ('Pathology: ICD-10 C18.7 + P53.', ['C18.7']),               # '+' never separates an ICD list
                ('Pathology: ICD-10: C18.7, p53.', ['C18.7'])):              # a later item in lower case, list complete
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                self.suggest(encounter)
                self.assertEqual(self.suggested(encounter), suggested)    # b3d8111d: P53 suggested in 1a-1d

    def test_R4C2_R4F12_a_compact_lab_value_is_not_told_as_a_mistyped_code(self):
        """b3d8111d: the QA0 widening counted any letter-letter-digit token with a dot, with no category check, so 'Cr1.2',
        'pH7.38' or 'Mg2.0' were said to be mistyped diagnosis codes. A dotted token is counted only when its first three
        characters are a category of the release in effect, as a dotless one is."""
        icd_release({'R07.9': 'Synthetic chest pain code', 'QA0.0101': 'Synthetic FY2026 code'})
        for notes in ('Assessment: R07.9.\nLabs: Na140, K4.1, Cr1.2, Ca9.5, Mg2.0, pH7.38, Hb7.9.',
                      'ABG: pH7.35, pCO2 45, pO2 80. Assessment: R07.9.'):
            with self.subTest(notes=notes):
                self.assertNotIn('not a code in that release', self.text(self.suggest(self.another(notes))))
        for notes in ('Assessment: R07.99 documented.', 'Assessment: QA0.019 documented.'):     # still counted
            with self.subTest(notes=notes):
                self.assertIn('1 entry in the notes written like a diagnosis code is not a code in that release',
                              self.text(self.suggest(self.another(notes))))

    def test_R4C3_a_dotted_code_written_against_a_word_is_said(self):
        """No TOKEN ends or starts where a letter or digit touches a dotted code ('R07.9chest', 'painR07.9', '1R07.9'), so
        the lookup never saw it: nothing suggested, nothing said."""
        icd_release({'R07.9': 'Synthetic chest pain code', 'I21.4': 'Synthetic NSTEMI', 'E11.65': 'Synthetic diabetes',
                     'M25.53': 'Synthetic wrist, shorter code', 'M25.532': 'Synthetic wrist'})
        for notes in ('Assessment: R07.9chest pain since Monday.', 'Assessment: chest painR07.9 noted.',
                      'Assessment: 1R07.9 chest pain.', 'Assessment: I21.4with troponin rise.',
                      'Assessment: E11.65hyperglycemia, on metformin.'):
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                self.assertIn('1 code from the release in effect is written touching', self.text(self.suggest(encounter)))
                self.assertEqual(self.suggested(encounter), [])
        control = self.another('Assessment: R07.9 chest pain.')
        self.assertNotIn('written touching', self.text(self.suggest(control)))
        self.assertEqual(self.suggested(control), ['R07.9'])
        whole = self.another('Assessment: wrist finding documented as M25.532.')     # its prefix M25.53 is a code too
        self.assertNotIn('written touching', self.text(self.suggest(whole)))
        self.assertEqual(self.suggested(whole), ['M25.532'])

    def test_R4C4_a_three_character_entry_touching_its_neighbour_is_not_called_a_code(self):
        """The touching sentence ('a code from the release ... leave a space to have it suggested') was said for '1.I10' and
        '1.P53': a three-character entry is not presumed to be a code (C10), and spacing it does not get it suggested."""
        icd_release({'I10': 'Synthetic hypertension', 'P53': 'Synthetic hemorrhagic disease of newborn',
                     'C18.7': 'Synthetic sigmoid colon'})
        for notes in ('Assessment:\n1.I10 Hypertension\nPlan: follow up.',
                      'Pathology: sigmoid adenocarcinoma.\nIHC:\n1.P53 wild-type\n2.MLH1 retained\nAssessment: C18.7.'):
            with self.subTest(notes=notes):
                text = self.text(self.suggest(self.another(notes)))
                self.assertNotIn('written touching', text)                      # b3d8111d: said
                self.assertIn('1 three-character entry in the notes matches a diagnosis code but is not labelled', text)

    def test_R5C1_a_transposed_digit_in_a_dotted_code_is_said(self):
        """a0bc4fd8: R4C-2's category check also dropped a code whose typo is inside its category ('J54.909' for J45.909):
        neither suggested nor said, against the rule held since aa3eead4. A dotted entry whose second character is a digit
        is counted whatever its category; the lab-value shape (a letter second) still needs a held category."""
        icd_release({'R07.9': 'Synthetic chest pain code', 'J45.909': 'Synthetic asthma', 'G43.909': 'Synthetic migraine'})
        for notes in ('Assessment: J54.909 asthma exacerbation.', 'Assessment: G34.909 migraine without aura.'):
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                self.assertIn('1 entry in the notes written like a diagnosis code is not a code in that release',
                              self.text(self.suggest(encounter)))           # a0bc4fd8: nothing said
                self.assertEqual(self.suggested(encounter), [])
        self.assertNotIn('not a code in that release',                       # the R4C-2 lab shapes stay quiet
                         self.text(self.suggest(self.another('Assessment: R07.9.\nLabs: Cr1.2, Ca9.5, Mg2.0, pH7.38.'))))

    def test_R5C2_a_value_written_against_its_name_is_not_called_a_code(self):
        """a0bc4fd8: the touching scan read a dotted shape inside a word, so 'WBC11.2' was C11.2, 'Temp37.2' P37.2 and
        'BMI31.2' I31.2: 'a code from the release in effect ... written touching other characters'."""
        icd_release({'R07.9': 'Synthetic chest pain code', 'C11.2': 'Synthetic nasopharynx', 'P37.2': 'Synthetic listeriosis',
                     'I31.2': 'Synthetic hemopericardium', 'R60.1': 'Synthetic edema', 'F60.5': 'Synthetic personality'})
        for notes in ('Labs: WBC11.2, Hgb9.8, Plt210.\nAssessment: R07.9 chest pain.',
                      'Vitals: Temp37.2, HR 80, BMI31.2.\nAssessment: R07.9 chest pain.',
                      'eGFR60.1, LVEF60.5%.\nAssessment: R07.9 chest pain.'):
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                self.assertNotIn('written touching', self.text(self.suggest(encounter)))     # a0bc4fd8: 1, 2 and 2
                self.assertEqual(self.suggested(encounter), ['R07.9'])
        for notes in ('Assessment: chest painR07.9 noted.', 'Assessment: 1R07.9 chest pain.',        # still said
                      'Seen by Dr Strauß: chest painR07.9 noted.'):      # positions read character for character
            with self.subTest(notes=notes):
                self.assertIn('1 code from the release in effect is written touching',
                              self.text(self.suggest(self.another(notes))))

    def test_R5C3_an_entry_the_release_lacks_is_said_once_not_as_touching(self):
        """a0bc4fd8: 'M54.50' (a code the release lacks, holding M54.5 as a prefix) was said twice, the second time as a held
        code 'written touching' with advice to leave a space, which then suggested M54.5 instead."""
        icd_release({'M54.5': 'Synthetic low back pain (FY2021)', 'R07.9': 'Synthetic chest pain code'})
        for notes in ('Assessment: M54.50 low back pain.', 'Assessment: R07.99 chest pain.'):
            with self.subTest(notes=notes):
                text = self.text(self.suggest(self.another(notes)))
                self.assertIn('1 entry in the notes written like a diagnosis code is not a code in that release', text)
                self.assertNotIn('written touching', text)                                  # a0bc4fd8: said as well

    def test_R5C4_a_labelled_three_character_code_touching_the_next_word_is_said_as_touching(self):
        """a0bc4fd8: every refused three-character code was 'not labelled as one', so 'ICD-10: I10.Follow up' was told to
        write a code label it already has; the remedy that works is a space."""
        icd_release({'I10': 'Synthetic hypertension'})
        for notes in ('Assessment: ICD-10: I10.Follow up in 2 weeks.', 'Assessment: stable.\nICD-10 code I10.Recheck BP.'):
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                text = self.text(self.suggest(encounter))
                self.assertIn('1 code from the release in effect is written touching', text)
                self.assertNotIn('not labelled', text)                                      # a0bc4fd8: said
                self.assertEqual(self.suggested(encounter), [])
        spaced = self.another('Assessment: ICD-10: I10. Follow up in 2 weeks.')            # the advice followed
        self.suggest(spaced)
        self.assertEqual(self.suggested(spaced), ['I10'])

    def test_R5F4_a_semicolon_or_comma_after_a_listed_stain_is_no_clause_end(self):
        """R4C-1's list ends at a full stop, a closing bracket or the end of the line; nothing pinned that ';' and ',' are
        not ends, and either one widened into CLAUSE_END suggested P53 again."""
        icd_release({'C18.7': 'Synthetic sigmoid colon', 'P53': 'Synthetic hemorrhagic disease of newborn'})
        for notes in ('Pathology: ICD-10: C18.7, P53; MLH1 retained.', 'Pathology: ICD-10: C18.7, P53, MLH1 retained.'):
            with self.subTest(notes=notes):
                encounter = self.another(notes)
                self.suggest(encounter)
                self.assertEqual(self.suggested(encounter), ['C18.7'])

    def test_R5F10_a_touching_code_only_another_release_holds_is_not_said(self):
        """The touching scan looks codes up in the ICD-10-CM releases in effect only: a retired release's code is not 'a
        code from the release in effect', and leaving a space would not get it suggested."""
        icd_release({'R07.9': 'Synthetic chest pain code'})
        today = timezone.localdate()
        save_release({'X99.9': 'Synthetic code of a retired release'},
                     dict(system='ICD-10-CM', version='synthetic-retired', effective_from=today - timedelta(days=400),
                          effective_until=today - timedelta(days=370), source_url='https://www.cms.gov/files/retired.txt',
                          sha256='e' * 64, license_reference=''))
        self.assertNotIn('written touching', self.text(self.suggest(self.another('Assessment: chest painX99.9 noted.'))))
        self.assertIn('written touching', self.text(self.suggest(self.another('Assessment: chest painR07.9 noted.'))))

    def cpt_release_under(self, reference, version, sha, days_ago):
        today = timezone.localdate()        # an earlier, closed period: a stored acceptance's release need not be in effect
        return save_release({'99213': 'SYNTHETIC CPT DESCRIPTOR NOT CPT CONTENT'},
                            dict(system='CPT', version=version, effective_from=today - timedelta(days=days_ago),
                                 effective_until=today - timedelta(days=days_ago - 20), source_url='https://example.invalid/licensed',
                                 sha256=sha, license_reference=reference))[0]

    def test_R4F10_R4F11_a_hidden_cpt_code_is_never_audited_under_either_half_of_hidden(self):
        """R3C-4's `shown` has two halves, each pinned alone: CPT licensed but the acceptance from ANOTHER licence (R4F-10),
        and CPT locked in code while the environment's licence id matches the acceptance's release (R4F-11)."""
        icd_release()
        for name, rights, reference in (('another licence', {'synthetic': 'rights'}, 'retired-license'),
                                        ('locked, matching licence id', None, 'synthetic-license')):
            with self.subTest(case=name), override_settings(**CURRENT), patch('core.coding.CPT_PRODUCT_USE_RIGHTS', rights):
                release = self.cpt_release_under(reference, f'synthetic-cpt-{reference}-{bool(rights)}',
                                                 ('e' if rights else 'f') * 64, 100 if rights else 60)
                encounter = self.another('Symptoms: No chest pain, CPT 99213.\nExamination: Normal gait.')
                stored = CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(release=release, code='99213'),
                    evidence='Symptoms: No chest pain, CPT 99213.', explanation='Stored CPT', accepted_by=self.user,
                    accepted_at=timezone.now())
                self.assertEqual(coding.cpt_licensed(), rights is not None)
                page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding').content.decode()
                self.assertNotIn('99213', page)                                 # hidden on the page in both cases
                encounter.refresh_from_db()
                self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/{stored.pk}/withdraw/',
                                                  {'revision': encounter.revision, 'accepted': self.acceptance(stored)}).status_code, 302)
                event = AuditEvent.objects.get(action='coding.withdraw', target=str(stored.pk))
                self.assertNotIn('99213', json.dumps(event.details))

    def test_no_cpt_code_is_imported_suggested_shown_accepted_or_exported_in_any_mode(self):
        icd_release(); cpt = cpt_release()
        encounter = self.document('Symptoms: No chest pain.\nExamination: Normal gait.\nPlan: visit documented as CPT 99213 and R07.9.')
        stored = CodeSuggestion.objects.create(encounter=encounter, terminology=Code.objects.get(release=cpt, code='99213'),
                                               evidence='Plan: visit documented as CPT 99213 and R07.9.', explanation='Synthetic stored CPT')
        modes = [dict(QUILLMD_DATA_MODE=data, SYNTHETIC_ONLY=data == 'synthetic', AI_MODE=ai)
                 for data in ('synthetic', 'real') for ai in ('fixture', 'live')]
        for mode in modes:
            with self.subTest(mode=mode), override_settings(**mode, **CURRENT):
                self.assertTrue(coding.cpt_license_current())  # the environment licence is current and matching
                self.assertFalse(coding.cpt_licensed())         # the lock in code holds anyway
                encounter.refresh_from_db()
                planned = coding.plan(encounter)
                self.assertEqual([code.release.system for code, _ in planned.found], ['ICD-10-CM'])
                self.assertEqual(planned.cpt_withheld, 1)
                self.assertNotIn('CPT', [release.system for release in coding.applicable_releases(encounter)])
                page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding')
                self.assertNotContains(page, 'SYNTHETIC CPT DESCRIPTOR NOT CPT CONTENT')
                self.assertIn(self.accept(encounter, stored).status_code, (400, 403))  # its release is not even in effect
                self.assertEqual({row['name']: row['status'] for row in integration_status()}['CPT terminology'],
                                 'Locked: no product-use rights recorded')
                with self.assertRaisesMessage(CommandError, 'CPT content is locked in this product'):
                    call_command('import_terminology', system='CPT', path='/nonexistent', sha256='0' * 64,
                                 release_version='synthetic-cpt-2', effective_from='2026-01-01', effective_until='2026-12-31',
                                 source_url='https://example.com/licensed-feed', expected_count=1, stdout=io.StringIO())
        with override_settings(**CURRENT):
            response = self.suggest(encounter)
        self.assertIn('1 CPT code named in the notes was not looked up: CPT content is not licensed for use in this product',
                      self.text(response))
        self.assertEqual(sorted(CodeSuggestion.objects.filter(encounter=encounter).values_list('terminology__release__system',
                                                                                            'accepted_by')),
                         [('CPT', None), ('ICD-10-CM', None)])  # only the stored row; nothing new from CPT, nothing accepted
        stored.refresh_from_db(); self.assertIsNone(stored.accepted_at)
        # Positive control: the gated path still works once rights are recorded in code (a reviewed release decision).
        with override_settings(**CURRENT), patch('core.coding.CPT_PRODUCT_USE_RIGHTS', {'synthetic': 'rights'}):
            self.assertTrue(coding.cpt_licensed())
            self.assertIn('CPT', [code.release.system for code, _ in coding.plan(encounter).found])
