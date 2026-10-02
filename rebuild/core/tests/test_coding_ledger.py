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

from core import coding
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
        response = self.client.post(f'/encounters/{encounter.pk}/coding/{code.pk}/withdraw/', {'revision': encounter.revision})
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
