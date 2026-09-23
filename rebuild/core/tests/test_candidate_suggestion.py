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

from core import generation
from core.generation import (INHERITED_SCOPE, SCOPE_POINTERS, SCOPE_REFRAMERS, Selection, negative_heading,
                             Selections, validate_selections, validate_tab_selections,
                             SCOPE_REVIEW_REASON)
from io import BytesIO
from zipfile import ZipFile

from docx import Document

from django.utils import timezone

from core.jobs import run_one
from core.models import AuditEvent, Membership, User
from core.tests.test_billing_boundary import BoundaryFixture
from core.tests.test_workflow import DocumentWorkflow
from core.tests.test_billing_policy import STORAGES

SCOPED = 'EXTENT: the scope reached the cecum'
NOTE = 'Fictional software test only.\n' + SCOPED


def judge(notes, quotes, *, conflict=False, label='EXTENT', key='k'):
    fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': 0}}]
    chosen = Selections(fields=[Selection(key=key, quotes=quotes, conflict=conflict)])
    return validate_selections(notes, fields, chosen, evidence_contract='legacy')[key]


def judge_tab(notes, quotes, *, conflict=False, label='EXTENT', key='k'):
    """⚠️ THE CONTRACT THE OWNER'S WORD FORMS ACTUALLY USE, AND IT HAD NO COVERAGE HERE AT ALL.

    A refutation lens instrumented the suite and measured `validate_tab_selections` called ZERO
    times across 44 tests, because `judge` pins `evidence_contract='legacy'` and the DOCX/PDF
    fixtures route legacy too. It then widened the tab validator's guard to fire on a model-
    DECLARED contradiction — offering `written` for one-click acceptance under a note that
    contradicts it — and the whole suite stayed green. The §1e encounter that motivated this
    entire feature ran on the tab contract.

    Tab evidence is a complete offered source sentence, not a bare value, so callers pass whole
    lines here where the legacy helper above takes values.
    """
    fields = [{'key': key, 'label': label, 'kind': 'text',
               'locator': {'cell': 0, 'tab_form': {'version': 1}}}]
    chosen = Selections(fields=[Selection(key=key, quotes=quotes, conflict=conflict)])
    # ⚠️ DISPATCHED THROUGH THE MODULE, NOT THROUGH THE NAME IMPORTED AT THE TOP OF THIS FILE.
    # A direct call cannot be observed: patching `generation.validate_tab_selections` leaves a
    # module-level `from ... import` binding untouched, so the counter in `setUp` below counted
    # nothing and the control that exists to catch a mislabelled helper could not catch one.
    return generation.validate_tab_selections(notes, fields, chosen)[key]


class ScopeUncertaintyKeepsTheCandidate(TestCase):
    def test_the_candidate_and_its_own_evidence_survive(self):
        answer = judge(NOTE, [SCOPED])
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['text'], '', 'nothing may be accepted by the validator')
        self.assertEqual(answer['suggestion'], 'the scope reached the cecum')
        # ⚠️ `evidence` still carries the WHOLE note, exactly as before this feature existed —
        # that is what shows a denial or a hypothetical frame. The answer's own passage is a
        # separate, additional key.
        self.assertEqual(answer['evidence'], [{'quote': NOTE, 'start': 0, 'end': len(NOTE)}])
        self.assertEqual(answer['suggestion_evidence'][0]['quote'], SCOPED)

    def test_the_reason_claims_no_more_than_the_validator_knows(self):
        """⚠️ Uncertainty must not be presented as a proven clinical contradiction — AND THE
        MIRROR IS EQUALLY FALSE. This text once asserted "not a contradiction found in the notes",
        which the validator cannot know: it checks provenance and two labelled values, and a
        correction on a later unlabelled line trips neither. A refutation lens produced a note
        whose next line read "severe crushing chest pain" under a suggestion of "no chest pain",
        with that sentence above it saying there was nothing to find."""
        reason = judge(NOTE, [SCOPED])['reason'].lower()
        self.assertEqual(judge(NOTE, [SCOPED])['reason'], SCOPE_REVIEW_REASON)
        self.assertIn('not been accepted', reason)
        self.assertIn('read the full note', reason)
        self.assertIn('may govern', reason, 'it must still say why a decision is needed')
        for overclaim in ('not a contradiction', 'no contradiction', 'is correct', 'verified',
                          'confirmed', 'consistent with'):
            self.assertNotIn(overclaim, reason, f'the reason must not assert {overclaim!r}')

    def test_the_offsets_still_index_the_source(self):
        for entry in judge(NOTE, [SCOPED])['suggestion_evidence'] + judge(NOTE, [SCOPED])['evidence']:
            self.assertEqual(NOTE[entry['start']:entry['end']], entry['quote'])

    def test_both_contracts_use_one_implementation(self):
        """A second copy of this rule would drift from the first the day either moved."""
        import inspect
        from core import generation
        source = inspect.getsource(generation)
        self.assertEqual(source.count('def with_scope_suggestion('), 1)
        self.assertEqual(source.count('answer=with_scope_suggestion('), 2,
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

    def section(self, encounter, label):
        """The page carries every answer, so an assertion about one must be scoped to its own section."""
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        # Bounded at the closing tag: unbounded, the LAST answer's "section" swallows the page
        # tail including the source-notes panel, which would make these assertions false-red or
        # false-green depending on render order.
        sections = [part.split('</section>')[0]
                    for part in page.split('<section class="answer">') if f'{label}</h3>' in part]
        self.assertEqual(len(sections), 1, f'expected exactly one {label} section')
        return sections[0]

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
        self.assertEqual(answer['evidence'],
                         [{'quote': encounter.notes, 'start': 0, 'end': len(encounter.notes)}],
                         'the governing context stays attached to the answer, unchanged')
        entry = answer['suggestion_evidence'][0]
        self.assertEqual(encounter.notes[entry['start']:entry['end']], entry['quote'])
        self.assertEqual(entry['quote'], self.SUGGESTION)
        # The API, against state the generator produced rather than a dict this test wrote.
        api = json.loads(self.client.get(f'/api/encounters/{encounter.pk}/').content)['answers']
        self.assertEqual(api[self.key]['text'], '')
        self.assertEqual(api[self.key]['suggestion'], self.SUGGESTION)
        # ⚠️ SCOPED TO THIS ANSWER'S OWN SECTION. Page-wide, every assertion here is vacuous:
        # the other answer's block satisfies 'Suggested answer', and the source-notes panel at
        # encounter_detail.html:52 renders the whole note, so the suggestion string is present
        # even with every suggestion block stripped from the page. Measured by a lens.
        section = self.section(encounter, 'Symptoms')
        self.assertIn('Suggested answer', section)
        self.assertIn(self.SUGGESTION, section, 'the doctor must be able to see what was read')
        self.assertIn(f'name="accept_{self.key}"', section)
        self.assertNotIn(f'>{self.SUGGESTION}</textarea>', section)

    def test_an_unaccepted_suggestion_blocks_finalization_and_never_becomes_a_document(self):
        encounter = self.generated()
        # ⚠️ ASSERTED BEFORE ANY SAVE. Checking it after `resolve_other` posts an empty answer
        # made this test pass even when generation auto-accepted the suggestion, because the
        # save wiped the very value it was meant to catch.
        self.assertEqual(encounter.answers[self.key]['text'], '')
        self.assertEqual(encounter.answers[self.key]['status'], 'conflict')
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


class APolarityOrAttRIBUTIONMarkerSuppressesTheOfferEntirely(TestCase):
    """⚠️ THE FIRST VERSION OF THIS FEATURE WOULD HAVE PUT AN ACCEPT BUTTON UNDER A DENIAL.

    Each note below is taken from a reviewed test written by an earlier refutation pass. In every
    one the extracted value is real and the governing context inverts it, so the candidate must
    not be offered for one-click acceptance at all — showing it would dress a real objection up
    as a formatting quibble.
    """

    def offer(self, notes, quote, label='Finding'):
        return judge(notes, [quote], label=label).get('suggestion')

    def test_a_denial_heading_suppresses_it(self):
        notes = 'The following findings are denied:\nFinding: diabetes'
        self.assertEqual(judge(notes, ['diabetes'], label='Finding')['status'], 'conflict')
        self.assertIsNone(self.offer(notes, 'diabetes'))

    def test_a_hypothetical_frame_suppresses_it(self):
        notes = 'Suppose bleeding were present.\nBleeding was observed.'
        self.assertIsNone(self.offer(notes, 'Bleeding was observed.', label='Bleeding'))

    def test_family_history_attribution_suppresses_it(self):
        notes = 'Family history: polyps.\nPolyps were observed.'
        self.assertIsNone(self.offer(notes, 'Polyps were observed.', label='Polyps'))

    def test_reported_speech_suppresses_it(self):
        notes = 'The patient said "it hurts here".\nFinding: tenderness'
        self.assertIsNone(self.offer(notes, 'tenderness'))

    def test_a_plain_pointer_does_not_suppress_it(self):
        """POSITIVE CONTROL: without it, every assertion above could pass because nothing is ever
        offered. `following` is a pointer, so scope is open but polarity is not asserted."""
        notes = 'See the findings listed in the report.\nFinding: diabetes'
        self.assertEqual(judge(notes, ['diabetes'], label='Finding')['status'], 'conflict')
        self.assertEqual(self.offer(notes, 'diabetes'), 'diabetes')

    def test_the_two_halves_are_still_one_vocabulary(self):
        """Splitting the list must not add, drop or alter a single word."""
        original = ('following|these|those|above|below|listed|family history|'
                    'if|would|could|might|hypothetical|imagine|suppose')
        self.assertEqual(SCOPE_POINTERS + '|' + SCOPE_REFRAMERS, original)
        self.assertEqual(INHERITED_SCOPE.pattern, r'\b(?:' + original + r')\b')


class WhatTheRefutationPassFound(AnUnacceptedSuggestionCannotReachAnExport):
    """Every test here is a defect three isolated refutation lenses demonstrated in this diff.

    Each ran in its own sealed worktree with its own database, so none could see the others'
    work — and the first two rows below were found independently by three of them.
    """

    def test_an_ordinary_later_save_does_not_withdraw_an_acceptance(self):
        """⚠️ THE ONE ALL THREE LENSES FOUND. Once accepted, the page renders the accepted branch,
        which has NO checkbox to re-post. Recomputing the flag from the POST therefore wrote False
        over a real True on the very next save — and the finalized record then told the doctor
        their own decision had not been made."""
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                       'reviewed_' + self.key: 'on'})
        self.assertTrue(encounter.answers[self.key]['accepted_suggestion'])
        # Re-post exactly the form the page now renders — no accept box exists in it.
        page = self.section(encounter, 'Symptoms')
        self.assertNotIn(f'name="accept_{self.key}"', page, 'the premise of this test')
        for _ in range(3):
            self.resolve_other(encounter, {'answer_' + self.key: self.SUGGESTION,
                                           'reviewed_' + self.key: 'on'})
            self.assertTrue(encounter.answers[self.key]['accepted_suggestion'],
                            'an ordinary re-save must not revoke a decision nobody revoked')
        self.finalize(encounter)
        self.assertIn('Suggestion accepted', self.section(encounter, 'Symptoms'))

    def saved_audit_row(self, before):
        """⚠️ SELECTED BY WHAT IS NEW, NOT BY `order_by('-id')`. `Entity` uses a UUID primary key,
        so ordering by it sorts hex strings and returns an arbitrary row — which read exactly like
        a real failure until I looked."""
        rows = AuditEvent.objects.filter(action='encounter.answers_saved').exclude(pk__in=before)
        self.assertEqual(rows.count(), 1)
        return rows.get()

    def audit_ids(self):
        return set(AuditEvent.objects.filter(action='encounter.answers_saved')
                   .values_list('pk', flat=True))

    def test_the_acceptance_is_attributed_and_audited(self):
        encounter = self.generated()
        before = self.audit_ids()
        self.resolve_other(encounter, {'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                       'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['accepted_by'], str(self.user.pk))
        self.assertIn(self.key, self.saved_audit_row(before).details['accepted_suggestions'])
        # Carrying it forward must not re-attribute it, and is not itself a new act.
        before = self.audit_ids()
        self.resolve_other(encounter, {'answer_' + self.key: self.SUGGESTION,
                                       'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['accepted_by'], str(self.user.pk))
        self.assertNotIn(self.key, self.saved_audit_row(before).details['accepted_suggestions'])

    def test_typing_the_same_words_by_hand_is_not_an_acceptance(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: self.SUGGESTION,
                                       'reviewed_' + self.key: 'on'})
        self.assertFalse(encounter.answers[self.key]['accepted_suggestion'])
        self.assertIsNone(encounter.answers[self.key]['accepted_by'])

    def test_accepting_requires_the_same_role_as_reviewing(self):
        """The template renders the box `disabled` for everyone else; that is client-side only.
        `accept_code`, the other accept-a-suggestion action, is role-gated, attributed and audited."""
        weak = User.objects.create_user(username='weak-role', email='weak@synthetic.invalid',
                                        verified_at=timezone.now())
        Membership.objects.create(user=weak, department=self.department, role='employee')
        encounter = self.generated()
        self.client.force_login(weak)
        response = self.client.post(f'/encounters/{encounter.pk}/save/',
                                    {'revision': encounter.revision,
                                     'answer_' + self.key: '', 'accept_' + self.key: 'on'})
        self.assertEqual(response.status_code, 403)
        encounter.refresh_from_db()
        self.assertEqual(encounter.answers[self.key]['text'], '')
        self.assertFalse(encounter.answers[self.key].get('accepted_suggestion'))
        # POSITIVE CONTROL — the same user, the same request, against the sibling control.
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/',
                                          {'revision': encounter.revision,
                                           'reviewed_' + self.key: 'on'}).status_code, 403)


class ACandidateIsNotOfferedWhenTheNoteDisagreesWithIt(TestCase):
    """Three shapes a refutation lens drove to a signed document, each offered for one click."""

    def test_a_line_initial_correction_suppresses_the_offer(self):
        notes = ('Symptoms: no chest pain\n'
                 'Correction: the patient reports severe crushing chest pain.\n'
                 'Examination: normal gait')
        answer = judge(notes, ['no chest pain'], label='Symptoms')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'),
                          'the next line retracts this answer; it is not a formatting quibble')

    def test_a_labelled_answer_contradicted_by_free_text_suppresses_the_offer(self):
        notes = ('Fictional test note. Findings follow:\n'
                 'Extent: the scope reached the splenic flexure\n'
                 'The scope was advanced to the cecum.')
        answer = judge(notes, ['The scope was advanced to the cecum.'], label='Extent')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'),
                          'splenic flexure versus caecum is a completeness claim, not a quibble')

    def test_two_candidate_values_suppress_the_offer(self):
        notes = ('Fictional software test only. Prior records reviewed:\n'
                 'Allergies: penicillin\n'
                 'Patient now reports no known drug allergies.')
        answer = judge(notes, ['penicillin', 'Patient now reports no known drug allergies.'],
                       label='Allergies')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'),
                          'one checkbox must not write a drug allergy and its retraction together')

    def test_the_ordinary_case_is_still_offered(self):
        """POSITIVE CONTROL. Without it every assertion above passes if nothing is ever offered."""
        self.assertEqual(judge(NOTE, [SCOPED])['suggestion'], 'the scope reached the cecum')


class EveryRuleHoldsUnderTheTabContractToo(TestCase):
    """⚠️ THE CONTRACT THE OWNER'S WORD FORMS USE, WHICH HAD ZERO COVERAGE IN THIS MODULE.

    A refutation lens measured `validate_tab_selections` called zero times across all 44 tests,
    then widened its guard so a model-DECLARED contradiction became a one-click suggestion — and
    the suite stayed green. Every rule the legacy tests assert is re-asserted here against the tab
    validator, which reaches the code by a different path with a different evidence shape.

    ⚠️ EVERY NOTE HERE IS REVIEW-REQUIRED, AND THAT IS LOAD-BEARING. The tab validator only holds
    an answer when something leaves scope open; otherwise these notes come back `supported` and
    every "offers nothing" assertion passes because nothing is ever offered. Some notes carry
    `PREFIX`, whose `listed` is a plain POINTER — review-required without asserting anything about
    polarity, which is exactly the state in which a candidate SHOULD be offered. The rest are held
    by their own marker, and each of those tests asserts `status == 'conflict'` to show it.
    `test_the_prefix_alone_still_offers` is the control that proves an offer happens at all.
    """
    PREFIX = 'See the findings listed in the report.\n'
    SCOPED_LINE = 'EXTENT: the scope reached the cecum.'
    TAB_NOTE = PREFIX + SCOPED_LINE

    def setUp(self):
        """⚠️ THE CONTROL FOR THE WHOLE CLASS, AND IT RUNS ON EVERY TEST IN IT.

        A lens rewrote `judge_tab` to call the LEGACY validator — the exact "mislabelled helper"
        the old control named — and all twelve tests here passed. Counting the calls is the only
        thing that catches that, so the count is asserted per test rather than in one test that
        can itself be bypassed.
        """
        self.tab_calls = []
        original = generation.validate_tab_selections
        def counted(*args, **kwargs):
            self.tab_calls.append(1)
            return original(*args, **kwargs)
        generation.validate_tab_selections = counted
        self.addCleanup(setattr, generation, 'validate_tab_selections', original)
        self.addCleanup(lambda: self.assertTrue(
            self.tab_calls, 'this test never reached validate_tab_selections'))

    def test_the_prefix_alone_still_offers(self):
        """THE CONTROL FOR EVERY SUPPRESSION TEST IN THIS CLASS."""
        answer = judge_tab(self.TAB_NOTE, [self.SCOPED_LINE])
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['text'], '')
        self.assertEqual(answer['suggestion'], 'the scope reached the cecum.')
        self.assertEqual(answer['evidence'],
                         [{'quote': self.TAB_NOTE, 'start': 0, 'end': len(self.TAB_NOTE)}],
                         'the governing context stays attached, exactly as before')
        entry = answer['suggestion_evidence'][0]
        self.assertEqual(entry['quote'], self.SCOPED_LINE)
        self.assertEqual(self.TAB_NOTE[entry['start']:entry['end']], entry['quote'])

    def test_the_real_mixed_word_shape_still_offers(self):
        """The §1e shape: the doctor's own heading, which this form does not use, and no full
        stop. That is what made `inherited` true on the encounter this feature came from."""
        notes = 'Fictional software test only.\nEXTENT: the scope reached the cecum'
        fields = [{'key': 'k', 'label': 'Extent of examination', 'kind': 'text',
                   'locator': {'cell': 0, 'tab_form': {'version': 1}}}]
        chosen = Selections(fields=[Selection(key='k', quotes=['EXTENT: the scope reached the cecum'],
                                              conflict=False)])
        answer = generation.validate_tab_selections(notes, fields, chosen)['k']
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['suggestion'], 'EXTENT: the scope reached the cecum')

    def test_a_model_declared_conflict_is_never_dressed_as_a_suggestion(self):
        """The exact mutation that passed 44 of 44 while this contract had no coverage."""
        answer = judge_tab(self.TAB_NOTE, [self.SCOPED_LINE], conflict=True)
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_a_denial_heading_suppresses_the_offer(self):
        notes = 'The following findings are denied:\nFinding: diabetes.'
        answer = judge_tab(notes, ['Finding: diabetes.'], label='Finding')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_a_hypothetical_frame_suppresses_the_offer(self):
        notes = 'Suppose bleeding were present.\nBleeding was observed.'
        answer = judge_tab(notes, ['Bleeding was observed.'], label='Bleeding')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_reported_speech_suppresses_the_offer(self):
        notes = 'The patient said "it hurts here".\nFinding: tenderness.'
        answer = judge_tab(notes, ['Finding: tenderness.'], label='Finding')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_a_line_initial_correction_suppresses_the_offer(self):
        notes = self.PREFIX + ('Symptoms: no chest pain.\n'
                               'Correction: the patient reports severe crushing chest pain.')
        answer = judge_tab(notes, ['Symptoms: no chest pain.'], label='Symptoms')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_two_explicit_values_offer_nothing(self):
        notes = self.PREFIX + 'CONSENT: written.\nCONSENT: verbal.'
        answer = judge_tab(notes, ['CONSENT: written.', 'CONSENT: verbal.'], label='CONSENT')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_a_failed_subject_guard_offers_nothing(self):
        notes = self.PREFIX + 'The scope was advanced to the cecum.'
        answer = judge_tab(notes, ['The scope was advanced to the cecum.'], label='CONSENT')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))

    def test_an_identity_field_offers_nothing(self):
        answer = judge_tab(self.TAB_NOTE, [self.SCOPED_LINE], label='Electronically signed by')
        self.assertEqual(answer['status'], 'missing')
        self.assertIsNone(answer.get('suggestion'))

    def test_invalid_provenance_is_still_refused(self):
        with self.assertRaises(ValidationError):
            judge_tab(self.TAB_NOTE, ['EXTENT: a sentence never written.'])

    def test_the_two_helpers_reach_different_validators(self):
        """The class-wide counter above proves each test REACHES the tab validator. This proves
        the two helpers are not the same code wearing two names — by the error each one raises,
        which is written in the validator itself and differs between the contracts."""
        with self.assertRaises(ValidationError) as tab:
            judge_tab(self.TAB_NOTE, ['EXTENT: a sentence never written.'])
        with self.assertRaises(ValidationError) as legacy:
            judge(NOTE, ['a value never written'])
        self.assertIn('complete offered source sentence', str(tab.exception))
        self.assertIn('complete source line', str(legacy.exception))
        self.assertNotEqual(str(tab.exception), str(legacy.exception))


class TypedTextWinsOnTheRealDocumentPath(AnUnacceptedSuggestionCannotReachAnExport):
    """A lens noted "typed text wins" was asserted only against a hand-written answers dict, so
    the rule had no coverage on the authenticated docx path it actually governs."""

    def test_typed_text_beats_a_ticked_accept_box_and_is_what_exports(self):
        encounter = self.generated()
        self.resolve_other(encounter, {'answer_' + self.key: self.TYPED,
                                       'accept_' + self.key: 'on',
                                       'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['text'], self.TYPED)
        self.assertFalse(encounter.answers[self.key]['accepted_suggestion'])
        exported = self.finalize(encounter)
        self.assertEqual(Document(BytesIO(exported)).paragraphs[0].text, f'Symptoms: {self.TYPED}')
        with ZipFile(BytesIO(exported)) as archive:
            blob = b''.join(archive.read(n) for n in archive.namelist())
        self.assertNotIn(self.SUGGESTION.encode(), blob)


class WhatTheSecondRefutationPassFound(TestCase):
    """Five more, on the repairs themselves. A fix in this codebase is wrong before it is right."""

    def test_a_denial_heading_below_an_ordinary_line_still_suppresses(self):
        """⚠️ THE HIGH. `UNSCOPED_NEGATIVE_HEADING` is anchored and compiled without `re.M`, and
        its `[^:]*` spans newlines, so searching a whole note could only ever see the span before
        the note's FIRST colon. One ordinary labelled line above the heading hid it, and
        `chest pain` was offered for one-click acceptance under `findings are denied`."""
        notes = ('Indication: screening colonoscopy\n'
                 'The following findings are denied:\n'
                 'Symptoms: chest pain')
        answer = judge(notes, ['chest pain'], label='Symptoms')
        self.assertEqual(answer['status'], 'conflict')
        self.assertIsNone(answer.get('suggestion'))
        # CONTROL: the heading rule is what suppresses it, not the pointer word `following`.
        self.assertFalse(negative_heading('Indication: screening colonoscopy\nSymptoms: chest pain'))
        self.assertTrue(negative_heading(notes))

    def test_the_heading_rule_does_not_fire_on_ordinary_prose(self):
        """The same anchor defect, the other way: `[^:]*` spanning newlines made any note with
        `no`/`not`/`never` before its first colon a negative heading."""
        self.assertFalse(negative_heading(
            'The patient did not tolerate oral preparation.\nFindings: a 5 mm sessile polyp'))

    def test_a_bulleted_or_plural_correction_still_suppresses(self):
        for prefix in ('- ', '* ', '• ', '1. ', '1) ', '  ', ''):
            for word in ('Correction', 'Corrections', 'CORRECTION'):
                notes = f'Symptoms: no chest pain\n{prefix}{word}: severe crushing chest pain.'
                self.assertIsNone(judge(notes, ['no chest pain'], label='Symptoms').get('suggestion'),
                                  f'{prefix!r}{word} must suppress the offer')
        # CONTROL: the word mid-sentence is not a correction line.
        notes = 'Prose that leaves scope open.\nSymptoms: no chest pain\nThe correction was noted.'
        self.assertEqual(judge(notes, ['no chest pain'], label='Symptoms').get('suggestion'),
                         'no chest pain')



class ADenialThatGovernsOtherLinesSuppressesTheOffer(TestCase):
    """⚠️ THE SAME ANCHOR, INSIDE ONE LINE. Found by the pilot's third refutation pass.

    `UNSCOPED_NEGATIVE_HEADING` sees a denial word only AHEAD of a line's first colon, so a label in
    front of the denial (`ROS: negative for the following:`) or no colon at all (`Patient denies the
    following`) left it blind, and `chest pain` was offered for one-click acceptance under a note
    that denies it — on both evidence contracts.
    """
    GOVERNING = ('ROS: negative for the following:', 'Review of systems: patient denies:',
                 'Patient denies the following', 'The patient denied each of the symptoms below.',
                 'Negative for the following',
                 # Round 4: a plural the old word boundary could not see, and colons nobody can tell apart.
                 'Pertinent negatives:', 'Pertinent negatives: fever, chest pain',
                 'ROS: negative for\uff1a', 'ROS: negative for:\u200b')

    def test_each_governing_denial_suppresses_the_offer_on_both_contracts(self):
        for heading in self.GOVERNING:
            with self.subTest(heading=heading):
                self.assertTrue(negative_heading(heading + '\nSymptoms: chest pain'))
                legacy = judge(heading + '\nSymptoms: chest pain', ['chest pain'], label='Symptoms')
                self.assertEqual(legacy['status'], 'conflict')
                self.assertIsNone(legacy.get('suggestion'))
                tab = judge_tab(heading + '\nSymptoms: chest pain.', ['Symptoms: chest pain.'], label='Symptoms')
                self.assertEqual(tab['status'], 'conflict')
                self.assertIsNone(tab.get('suggestion'))

    def test_a_denial_that_governs_no_other_line_still_allows_the_offer(self):
        """POSITIVE CONTROL: without it every assertion above could pass because nothing is offered.
        A denial inside a labelled answer, or in prose that neither ends in a colon nor points
        anywhere, is not a heading; a pointer with no denial is the case this feature exists for."""
        notes = 'Allergies: no known drug allergies\nSee the findings listed in the report.\nSymptoms: chest pain'
        self.assertFalse(negative_heading(notes))
        self.assertEqual(judge(notes, ['chest pain'], label='Symptoms').get('suggestion'), 'chest pain')
        tab = judge_tab(notes + '.', ['Symptoms: chest pain.'], label='Symptoms')
        self.assertEqual(tab['status'], 'conflict')
        self.assertEqual(tab.get('suggestion'), 'chest pain.')
        self.assertFalse(negative_heading('The patient did not tolerate oral preparation.\nFindings: a 5 mm polyp'))

    def test_the_status_vocabulary_is_unchanged_and_suppression_only_widens_it(self):
        self.assertEqual(generation.UNSCOPED_NEGATIVE_HEADING.pattern,
                         r'^[^:]*\b(?:denied|denies|absent|negative|no|not|without|never)\b[^:]*:')
        self.assertEqual(generation.SUPPRESSING_DENIAL_WORDS.split('|')[:8], generation.DENIAL_WORDS.split('|'))
        self.assertEqual(generation.DENIAL.pattern, r'\b(?:' + generation.SUPPRESSING_DENIAL_WORDS + r')\b')

    def test_a_pointer_beside_a_denial_withholds_offers_even_in_an_ordinary_sentence(self):
        """The documented, deliberate cost: over-suppressing costs a retyped answer."""
        notes = 'Extent: the scope reached the cecum\nDischarge: no driving for the following 24 hours'
        self.assertTrue(negative_heading(notes))
        self.assertIsNone(judge(notes, ['the scope reached the cecum'], label='Extent').get('suggestion'))

    def judge_pair(self, value):
        fields = [{'key': 'f', 'label': 'Findings', 'kind': 'text', 'locator': {'cell': 0}},
                  {'key': 'i', 'label': 'Impression', 'kind': 'text', 'locator': {'cell': 1}}]
        chosen = Selections(fields=[Selection(key='f', quotes=[value], conflict=False),
                                    Selection(key='i', quotes=['Normal venous study.'], conflict=False)])
        return validate_selections(f'Findings: {value}\nImpression: Normal venous study.', fields, chosen,
                                   evidence_contract='legacy')

    def test_a_denial_beside_an_ordinary_pointer_word_is_still_that_questions_answer(self):
        """⚠️ A GUARD, NOT A FEATURE. Rounds 4-6 of the pilot tried to decide a legacy STATUS from the mere
        co-occurrence of denial and pointer words, and every version blanked realistic notes. A pointer
        INSIDE a sentence is anatomy or time and governs nothing: both answers stay ready."""
        for value in ('No reflux below the knee.', 'No bleeding following polypectomy.',
                      'No driving for the following 24 hours.', 'Soft, no tenderness above the umbilicus.',
                      'Benign nevi; these are not concerning.', 'Good, without residual stool in the segments listed here.',
                      'No change from the study above.', 'No DVT in the veins listed above.',
                      # The lines pointed at are the EXCEPTIONS, stated as positives (second refutation pass).
                      'Negative except as noted below.'):
            with self.subTest(value=value):
                answers = self.judge_pair(value)
                self.assertEqual((answers['f']['status'], answers['i']['status']), ('supported', 'supported'))
                self.assertEqual(answers['f']['text'], value)

    def test_a_denial_that_ends_on_a_forward_pointer_leaves_what_follows_to_a_decision(self):
        """⚠️ THE DOCUMENTED TRADE of the denial-heading repair (2026-09-23). A sentence that ENDS on
        `below`/`following` beside a denial points at what comes next exactly as `negative for the symptoms
        below.` does, and without grammar the two cannot be told apart. The sentence stays its own question's
        answer; the answer after it needs a decision (no one-click offer), instead of a denied finding being
        pre-filled. `…negative for the symptoms below.` is the case this is for."""
        for value in ('Reflux at the SFJ, 1200 ms; no reflux at mid-thigh or below.',
                      'Normal above the knees, absent below.', 'Lateral calf, not visualized below',
                      'No immediate complications following.'):
            with self.subTest(value=value):
                answers = self.judge_pair(value)
                self.assertEqual((answers['f']['status'], answers['f']['text']), ('supported', value))
                self.assertEqual((answers['i']['status'], answers['i']['text']), ('conflict', ''))
                self.assertNotIn('suggestion', answers['i'])
                self.assertEqual(answers['i']['held_candidate']['text'], 'Normal venous study.')

    def test_a_heading_that_visibly_ends_in_a_colon_counts_on_both_contracts(self):
        """Round 5: the tab contract read only an ASCII colon, and a bidi mark or soft hyphen after the
        colon hid it from the gate. Format characters and default-ignorable marks are invisible."""
        for tail in ('\uff1a', ':\u200b', ':\u200e', ':\u200f', ':\u00ad', ':\u2063', ':\ufeff', ':\u034f', ':\ufe0f'):
            with self.subTest(tail=repr(tail)):
                self.assertTrue(generation.ends_in_colon('pertinent negatives' + tail))
                self.assertTrue(negative_heading(f'Review of systems: pertinent negatives{tail}\nSymptoms: chest pain'))
                fields = [{'key': 'ros', 'label': 'Review of systems', 'kind': 'text', 'locator': {'cell': 0, 'tab_form': {'version': 1}}},
                          {'key': 'k', 'label': 'Symptoms', 'kind': 'text', 'locator': {'cell': 1, 'tab_form': {'version': 1}}}]
                tab, *_ = generation.generate(f'Review of systems: pertinent negatives{tail}\nSymptoms: chest pain.', fields,
                                              {'mode': 'fixture', 'prompt_version': generation.CURRENT_PROMPT_VERSION})
                self.assertNotEqual(tab['k']['status'], 'supported')
        self.assertFalse(generation.ends_in_colon('negative for the following'))

    def test_an_invisible_character_inside_a_word_can_neither_join_nor_split_a_denial(self):
        """Round 5: deleting U+200B joined `no` and `ne` into `none`. Round 6: keeping it split `de`+`nied`,
        and a soft hyphen from copied hyphenated text does the same. Both readings are searched."""
        self.assertTrue(negative_heading('Review of systems: no\u200bne of the following:\nSymptoms: chest pain'))
        for heading in ('The following findings are de\u200bnied:', 'The following findings are de\u00adnied:',
                        'Patient de\u200bnies the following', 'Pertinent nega\u200btives: fever'):
            with self.subTest(heading=repr(heading)):
                notes = f'Indication: screening colonoscopy\n{heading}\nSymptoms: chest pain'
                self.assertTrue(negative_heading(notes))
                self.assertIsNone(judge(notes, ['chest pain'], label='Symptoms').get('suggestion'))



class AnAcceptanceIsAttributedOnThePageAndDefendedFromWithdrawal(
        AnUnacceptedSuggestionCannotReachAnExport):
    """Two more from the second pass, both about who owns a clinical decision."""

    def accept_as(self, encounter, user):
        self.client.force_login(user)
        self.resolve_other(encounter, {'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                       'reviewed_' + self.key: 'on'})

    def colleague(self, role='clinician', name='second-clinician'):
        other = User.objects.create_user(username=name, email=f'{name}@synthetic.invalid',
                                         verified_at=timezone.now())
        Membership.objects.create(user=other, department=self.department, role=role)
        return other

    def test_a_second_clinician_is_told_who_accepted_it_not_that_they_did(self):
        """⚠️ The page said "You accepted this as your answer" to every reader, so a colleague was
        informed, about somebody else's clinical decision, that they had made it. `accept_code`
        has named its accepter in this same template all along."""
        encounter = self.generated()
        self.accept_as(encounter, self.user)
        self.client.force_login(self.colleague())
        section = self.section(encounter, 'Symptoms')
        self.assertIn(self.user.email, section)
        self.assertNotIn('You accepted this', section)
        # CONTROL: the person who did accept it is still addressed directly.
        self.client.force_login(self.user)
        self.assertIn('You accepted this', self.section(encounter, 'Symptoms'))

    def test_withdrawing_an_acceptance_needs_the_authority_that_granted_it(self):
        encounter = self.generated()
        self.accept_as(encounter, self.user)
        weak = self.colleague(role='employee', name='weak-withdrawer')
        self.client.force_login(weak)
        response = self.client.post(f'/encounters/{encounter.pk}/save/',
                                    {'revision': encounter.revision,
                                     'answer_' + self.key: 'something else entirely'})
        self.assertEqual(response.status_code, 403)
        encounter.refresh_from_db()
        self.assertTrue(encounter.answers[self.key]['accepted_suggestion'])
        self.assertEqual(encounter.answers[self.key]['accepted_by'], str(self.user.pk))
        # CONTROL: a clinician may withdraw it, and the withdrawal is recorded as an act.
        self.client.force_login(self.user)
        before = set(AuditEvent.objects.filter(action='encounter.answers_saved')
                     .values_list('pk', flat=True))
        self.resolve_other(encounter, {'answer_' + self.key: 'something else entirely',
                                       'reviewed_' + self.key: 'on'})
        self.assertFalse(encounter.answers[self.key]['accepted_suggestion'])
        row = AuditEvent.objects.filter(action='encounter.answers_saved').exclude(pk__in=before).get()
        self.assertIn(self.key, row.details['withdrawn_acceptances'])
