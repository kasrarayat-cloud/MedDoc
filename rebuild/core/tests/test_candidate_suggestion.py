"""A candidate held for review is shown, not discarded — and is never accepted by accident.

⚠️ WHY THIS EXISTS. A real provider response returned three correct answers, each quoting its own
question's line with `conflict: false`, and all three were blanked because the note also carried
an opening disclaimer and two closing sentences. The doctor had to retype every one. Receipt
`810ba1fc…`, job `80778c0c`.

The scope rule is NOT changed here. What changes is what a clinician is shown when it fires: the
extracted value and its own evidence are kept as a SUGGESTION, `text` stays empty and `status`
stays `conflict`, so finalization still demands an explicit decision.

Everything below is offline. No provider call is made by any test in this module.
"""
import json

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.generation import Selection, Selections, validate_selections, SCOPE_REVIEW_REASON
from io import BytesIO
from zipfile import ZipFile

from docx import Document

from core.jobs import run_one
from core.tests.test_billing_boundary import BoundaryFixture
from core.tests.test_workflow import DocumentWorkflow
from core.tests.test_billing_policy import STORAGES

SCOPED = 'EXTENT: the scope reached the cecum'
NOTE = 'Fictional software test only.\n' + SCOPED


def judge(notes, quotes, *, conflict=False, label='EXTENT', key='k'):
    fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': 0}}]
    chosen = Selections(fields=[Selection(key=key, quotes=quotes, conflict=conflict)])
    return validate_selections(notes, fields, chosen, evidence_contract='legacy')[key]


class ScopeUncertaintyKeepsTheCandidate(TestCase):
    def test_the_candidate_and_its_own_evidence_survive(self):
        answer = judge(NOTE, [SCOPED])
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['text'], '', 'nothing may be accepted by the validator')
        self.assertEqual(answer['suggestion'], 'the scope reached the cecum')
        self.assertEqual(answer['evidence'][0]['quote'], SCOPED,
                         'the evidence shown must be this answer\'s own line, not the whole note')

    def test_the_reason_says_scope_and_denies_being_a_contradiction(self):
        """⚠️ Uncertainty about scope must not be presented as a proven clinical contradiction."""
        reason = judge(NOTE, [SCOPED])['reason']
        self.assertEqual(reason, SCOPE_REVIEW_REASON)
        self.assertIn('scope', reason.lower())
        self.assertIn('not a contradiction', reason.lower())
        self.assertIn('not been accepted', reason.lower())

    def test_the_offsets_still_index_the_source(self):
        entry = judge(NOTE, [SCOPED])['evidence'][0]
        self.assertEqual(NOTE[entry['start']:entry['end']], entry['quote'])

    def test_both_contracts_use_one_implementation(self):
        """A second copy of this rule would drift from the first the day either moved."""
        import inspect
        from core import generation
        source = inspect.getsource(generation)
        self.assertEqual(source.count('def scope_review('), 1)
        self.assertEqual(source.count('output[item.key]=scope_review('), 2,
                         'the tab contract and the legacy contract must both call it')


class GenuineObjectionsAreNotDressedUpAsSuggestions(TestCase):
    """A real objection offered as a suggestion would invite a wrong acceptance."""

    def test_two_explicit_values_offer_no_suggestion(self):
        answer = judge('CONSENT: written\nCONSENT: verbal\nSomething else.',
                       ['CONSENT: written', 'CONSENT: verbal'], label='CONSENT')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_a_failed_subject_guard_offers_no_suggestion(self):
        answer = judge('Some prose here.\nThe scope was advanced to the cecum.',
                       ['The scope was advanced to the cecum.'], label='CONSENT')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_a_model_declared_conflict_offers_no_suggestion(self):
        answer = judge('Prose.\nCONSENT: written', ['CONSENT: written'],
                       conflict=True, label='CONSENT')
        self.assertIsNone(answer.get('suggestion'))

    def test_invalid_provenance_is_still_refused_outright(self):
        with self.assertRaises(ValidationError):
            judge('Prose.\nCONSENT: written', ['CONSENT: never said this'], label='CONSENT')

    def test_a_clinician_identity_field_is_untouched(self):
        answer = judge(NOTE, [SCOPED], label='Electronically signed by')
        self.assertEqual(answer['status'], 'missing')
        self.assertIsNone(answer.get('suggestion'))


@override_settings(STORAGES=STORAGES)
class ASuggestionBecomesAnAnswerOnlyByAnExplicitAct(BoundaryFixture, TestCase):
    """⚠️ Saving, reopening, reading the API or exporting must never accept it."""

    SUGGESTION = 'the scope reached the cecum'

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.encounter.answers = {
            field['key']: {'text': '', 'status': 'conflict', 'reviewed': False,
                           'evidence': [{'quote': SCOPED, 'start': 0, 'end': len(SCOPED)}],
                           'suggestion': self.SUGGESTION, 'reason': SCOPE_REVIEW_REASON}
            for field in self.encounter.template_version.fields}
        self.encounter.save(update_fields=['answers'])
        self.key = self.encounter.template_version.fields[0]['key']

    def save(self, **extra):
        self.encounter.refresh_from_db()
        data = {'revision': str(self.encounter.revision)}
        data.update(extra)
        return self.client.post(f'/encounters/{self.encounter.pk}/save/', data, follow=True)

    def stored(self):
        self.encounter.refresh_from_db()
        return self.encounter.answers[self.key]

    def test_saving_without_accepting_leaves_the_answer_empty(self):
        self.save(**{f'answer_{self.key}': ''})
        answer = self.stored()
        self.assertEqual(answer['text'], '')
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['suggestion'], self.SUGGESTION, 'the suggestion must survive')

    def test_reopening_does_not_accept_it_and_does_not_prefill_the_box(self):
        self.save(**{f'answer_{self.key}': ''})
        page = self.client.get(f'/encounters/{self.encounter.pk}/').content.decode()
        self.assertIn('Suggested answer', page)
        self.assertIn('not accepted', page)
        self.assertNotIn(f'>{self.SUGGESTION}</textarea>', page,
                         'prefilling the textarea would let an ordinary save accept it')
        self.assertEqual(self.stored()['text'], '')

    def test_the_api_never_presents_the_suggestion_as_the_answer(self):
        response = self.client.get(f'/api/encounters/{self.encounter.pk}/')
        answers = json.loads(response.content)['answers']
        self.assertEqual(answers[self.key]['text'], '')
        self.assertEqual(answers[self.key]['suggestion'], self.SUGGESTION)

    def test_accepting_explicitly_is_what_makes_it_an_answer(self):
        self.save(**{f'answer_{self.key}': '', f'accept_{self.key}': 'on'})
        answer = self.stored()
        self.assertEqual(answer['text'], self.SUGGESTION)
        self.assertEqual(answer['status'], 'edited',
                         'an accepted suggestion is a clinician action, not a model result')

    def test_anything_typed_wins_over_the_accept_box(self):
        self.save(**{f'answer_{self.key}': 'the scope reached the splenic flexure',
                     f'accept_{self.key}': 'on'})
        self.assertEqual(self.stored()['text'], 'the scope reached the splenic flexure')

    def test_finalization_is_still_refused_while_the_conflict_stands(self):
        self.save(**{f'answer_{self.key}': ''})
        self.encounter.refresh_from_db()
        response = self.client.post(f'/encounters/{self.encounter.pk}/finalize/',
                                    {'revision': str(self.encounter.revision), 'reviewed': 'on'},
                                    follow=True)
        self.encounter.refresh_from_db()
        self.assertNotEqual(self.encounter.status, 'finalized')
        self.assertContains(response, 'conflict')


class AnUnacceptedSuggestionCannotReachAnExport(DocumentWorkflow):
    """The whole authenticated chain on a real document: upload, generate, save, reopen, finalize, export.

    The notes are the §1e shape — an ordinary opening remark above ordinary labelled lines. That remark is
    what makes every answer review-required, and those answers are what a doctor should not have to retype.
    """
    NOTES = 'Fictional software test only.\nSymptoms: no chest pain\nExamination: normal gait'
    SUGGESTION = 'no chest pain'
    OTHER = 'normal gait'
    TYPED = 'reports intermittent palpitations'

    def generated(self):
        template, mapping = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(mapping, self.NOTES)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/generate/').status_code, 302)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        by_label = {f['label'].rstrip(':'): f['key'] for f in mapping.fields}
        self.key, self.other = by_label['Symptoms'], by_label['Examination']
        return encounter

    def resolve_other(self, encounter, payload):
        """The second field is accepted explicitly, so only the field under test is in question."""
        payload.update({'accept_' + self.other: 'on', 'answer_' + self.other: '',
                        'reviewed_' + self.other: 'on', 'revision': encounter.revision})
        response = self.client.post(f'/encounters/{encounter.pk}/save/', payload)
        self.assertEqual(response.status_code, 302)
        encounter.refresh_from_db()

    def test_the_suggestion_survives_generation_and_is_shown_as_unaccepted(self):
        encounter = self.generated()
        answer = encounter.answers[self.key]
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['text'], '')
        self.assertEqual(answer['suggestion'], self.SUGGESTION)
        entry = answer['evidence'][0]
        self.assertEqual(encounter.notes[entry['start']:entry['end']], entry['quote'],
                         'the shown evidence must still index the doctor\'s own notes')
        self.assertEqual(entry['quote'], self.SUGGESTION)
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        self.assertIn('Suggested answer', page)
        self.assertIn(self.SUGGESTION, page, 'the doctor must be able to see what was read')
        self.assertNotIn(f'>{self.SUGGESTION}</textarea>', page)

    def test_an_unaccepted_suggestion_blocks_finalization_and_never_becomes_a_document(self):
        encounter = self.generated()
        # Saved and reopened repeatedly — none of it is an acceptance.
        for _ in range(2):
            self.resolve_other(encounter, {'answer_' + self.key: '', 'reviewed_' + self.key: 'on'})
            self.client.get(f'/encounters/{encounter.pk}/')
            self.assertEqual(encounter.answers[self.key]['text'], '')
            self.assertEqual(encounter.answers[self.key]['suggestion'], self.SUGGESTION)
        self.client.post(f'/encounters/{encounter.pk}/finalize/',
                         {'reviewed': 'on', 'revision': encounter.revision})
        encounter.refresh_from_db()
        self.assertEqual(encounter.status, 'review', 'an undecided suggestion must not finalize')
        self.assertEqual(self.client.get(f'/encounters/{encounter.pk}/export/').status_code, 404)

    def test_a_different_typed_answer_exports_and_the_suggestion_does_not(self):
        """⚠️ THE LOAD-BEARING ONE. The suggestion is still stored; the document must not contain it."""
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: self.TYPED, 'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['suggestion'], self.SUGGESTION,
                         'the record of what the model read is preserved, not overwritten')
        exported = self.finalize(encounter)
        document = Document(BytesIO(exported))
        self.assertEqual(document.paragraphs[0].text, f'Symptoms: {self.TYPED}')
        self.assertEqual(document.tables[0].cell(0, 1).text, self.OTHER)
        with ZipFile(BytesIO(exported)) as archive:
            blob = b''.join(archive.read(n) for n in archive.namelist())
        self.assertIn(self.TYPED.encode(), blob)
        self.assertNotIn(self.SUGGESTION.encode(), blob,
                         'an unaccepted suggestion reached the exported bytes')

    def test_accepting_it_explicitly_is_what_puts_it_in_the_document(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                       'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['text'], self.SUGGESTION)
        self.assertEqual(encounter.answers[self.key]['status'], 'edited')
        exported = self.finalize(encounter)
        self.assertEqual(Document(BytesIO(exported)).paragraphs[0].text, f'Symptoms: {self.SUGGESTION}')
        # ⚠️ POSITIVE CONTROL for the negative above: the same byte search finds this string when an
        # acceptance really did put it in the document, so its absence there is a fact and not a typo.
        with ZipFile(BytesIO(exported)) as archive:
            blob = b''.join(archive.read(n) for n in archive.namelist())
        self.assertIn(self.SUGGESTION.encode(), blob)

    def test_the_finalized_document_is_not_rewritten_by_a_later_acceptance(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: self.TYPED, 'reviewed_' + self.key: 'on'})
        self.finalize(encounter)
        sha = encounter.export_sha256
        response = self.client.post(f'/encounters/{encounter.pk}/save/',
                                    {'revision': encounter.revision, 'answer_' + self.key: '',
                                     'accept_' + self.key: 'on'})
        self.assertEqual(response.status_code, 409)
        encounter.refresh_from_db()
        self.assertEqual(encounter.export_sha256, sha)
        self.assertEqual(encounter.answers[self.key]['text'], self.TYPED)


class TheClinicianActionIsRecordedSeparately(AnUnacceptedSuggestionCannotReachAnExport):
    """⚠️ A finalized document that says "not accepted" over an answer the doctor DID accept is a lie
    about a clinical record. Acceptance is stored as its own fact, not inferred by comparing strings."""

    def section(self, encounter, label):
        """The page carries every answer, so an assertion about one must be scoped to its own section."""
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        sections = [part for part in page.split('<section class="answer">') if f'{label}</h3>' in part]
        self.assertEqual(len(sections), 1, f'expected exactly one {label} section')
        return sections[0]

    def test_accepting_records_the_action_and_the_finalized_page_says_so(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                       'reviewed_' + self.key: 'on'})
        self.assertTrue(encounter.answers[self.key]['accepted_suggestion'])
        self.finalize(encounter)
        section = self.section(encounter, 'Symptoms')
        self.assertIn('Suggestion accepted', section)
        self.assertNotIn('not accepted', section)

    def test_rejecting_records_the_action_and_the_finalized_page_says_so(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: self.TYPED, 'reviewed_' + self.key: 'on'})
        self.assertFalse(encounter.answers[self.key]['accepted_suggestion'])
        self.finalize(encounter)
        section = self.section(encounter, 'Symptoms')
        self.assertIn('was not accepted', section)
        self.assertNotIn('Suggestion accepted', section)
        # Positive control: the field the clinician DID accept reads the other way on the same page.
        self.assertIn('Suggestion accepted', self.section(encounter, 'Examination'))

    def test_editing_away_from_an_accepted_suggestion_withdraws_the_acceptance(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                       'reviewed_' + self.key: 'on'})
        self.assertTrue(encounter.answers[self.key]['accepted_suggestion'])
        self.resolve_other(encounter, {'answer_' + self.key: self.TYPED, 'reviewed_' + self.key: 'on'})
        self.assertFalse(encounter.answers[self.key]['accepted_suggestion'],
                         'a withdrawn acceptance must not stay recorded as one')
        self.assertEqual(encounter.answers[self.key]['text'], self.TYPED)

    def test_the_accept_box_is_not_offered_once_the_document_is_finalized(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: self.TYPED, 'reviewed_' + self.key: 'on'})
        self.finalize(encounter)
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        self.assertNotIn(f'name="accept_{self.key}"', page)
