"""Review guards ported from the draft branch feat/wm-narrative (4396c801): its flag-independent fixes only.

Offline and synthetic. Ordinary forms generate in fixture mode. The qualified Word form's resolver is replaced by
`synthetic_resolver`, which resolves the way the engine does for this fixture's statements (the chosen wording, and the
signer: the finalizing clinician once finalized, else the viewer); no Word runtime and no provider is involved.
"""
from datetime import timedelta
from decimal import Decimal
import hashlib
import html
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
import time
from unittest.mock import patch

import threading

from django.db import connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import coding as coding_module, views, wm_review
from core.jobs import run_one
from core.security import private_path
from core.models import AuditEvent, Code, CodeSet, CodeSuggestion, Encounter, Job, Membership, TemplateVersion, User
from core.wm_review import BACKEND, ORIGINAL_SHA256
from .test_security import SyntheticFixture
from . import test_workflow
from .test_workflow import TEST_SETTINGS

REFUSED = 'a new draft would replace them. Nothing was sent or charged.'
CLEAR_ACTION = 'Clear answers and review to generate again'
UNCHANGED = 'Notes unchanged — nothing was cleared.'


class BrowserSaveForm(HTMLParser):
    """What a browser posts for the save form AS RENDERED: every enabled control, unchanged (a `disabled` control is
    never posted)."""
    def __init__(self):
        super().__init__(); self.values = {}; self.inside = False; self.text = None; self.select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.inside = (attrs.get('action') or '').endswith('/save/')
        if not self.inside or 'disabled' in attrs or not attrs.get('name') and tag != 'option':
            return
        if tag == 'input':
            if attrs.get('type') != 'checkbox' or 'checked' in attrs:
                self.values[attrs['name']] = attrs.get('value', 'on' if attrs.get('type') == 'checkbox' else '')
        elif tag == 'textarea':
            self.text = attrs['name']; self.values[self.text] = ''
        elif tag == 'select':
            self.select = attrs['name']; self.values.setdefault(self.select, '')
        elif tag == 'option' and self.select and 'selected' in attrs:
            self.values[self.select] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'textarea': self.text = None
        elif tag == 'select': self.select = None
        elif tag == 'form': self.inside = False

    def handle_data(self, data):
        if self.text: self.values[self.text] += data

    @classmethod
    def of(cls, page):
        form = cls(); form.feed(page.content.decode())
        # (the HTML parser drops exactly one line feed right after a <textarea> start tag)
        return {name: html.unescape(value[1:] if value.startswith('\n') else value) for name, value in form.values.items()}


# ── ordinary forms ────────────────────────────────────────────────────────────────────────────────────────────────
class OrdinaryDraft:
    """DocumentWorkflow's fixture and helpers, without re-running its own tests (imported by module for the same reason:
    a TestCase class in this module's namespace would be collected here again)."""
    workflow = test_workflow.DocumentWorkflow
    setUp, make_docx, upload = workflow.setUp, workflow.make_docx, workflow.upload
    create_encounter, generate = workflow.create_encounter, workflow.generate
    NOTES = 'Symptoms: No chest pain.\nExamination: Normal gait.'

    def drafted(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        self.generate(encounter)
        return encounter

    def post(self, url, encounter, payload=None):
        encounter.refresh_from_db()
        response = self.client.post(url, {'revision': encounter.revision, **(payload or {})}, follow=True)
        encounter.refresh_from_db()
        return response

    def reviewed_draft(self, **extra):
        """A generated draft the clinician saved with every answer reviewed (plus `extra` posted fields)."""
        encounter = self.drafted()
        keys = sorted(encounter.answers)
        self.post(f'/encounters/{encounter.pk}/save/', encounter,
                  {**{'answer_' + key: encounter.answers[key]['text'] for key in keys},
                   **{'reviewed_' + key: 'on' for key in keys}, **extra})
        self.assertTrue(all(answer['reviewed'] for answer in encounter.answers.values()))   # (the control)
        return encounter, keys

    def member(self, name, role):
        user = User.objects.create_user(username=name, email=name + '@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=user, department=self.department, role=role)
        return user

    def transcript_awaiting_review(self, encounter, text='Synthetic words.'):
        payload = json.dumps({'raw_transcript': text, 'transcript': text}).encode()
        relative = 'receipts/synthetic-review-guards-transcript.json'
        path = private_path(relative); path.parent.mkdir(parents=True, exist_ok=True, mode=0o700); path.write_bytes(payload)
        return Job.objects.create(encounter=encounter, user=self.user, kind='transcription', state='succeeded',
                                  revision=encounter.revision, request_key='synthetic-transcript-' + str(encounter.pk),
                                  config={'transcript_review_required': True}, result_path=relative,
                                  result_sha256=hashlib.sha256(payload).hexdigest())

    def accepted_code(self, encounter):
        return CodeSuggestion.objects.create(encounter=encounter, terminology=synthetic_code(), explanation='Synthetic documented code',
                                             evidence='No chest pain.', accepted_by=self.user, accepted_at=timezone.now())


def synthetic_code():
    """R00.0 in a synthetic ICD-10-CM release in effect today (the encounters' date of service)."""
    today = timezone.localdate()
    release = CodeSet.objects.create(system='ICD-10-CM', version='synthetic-review-guards', sha256='0' * 64,
                                     effective_from=today - timedelta(days=1), effective_until=today + timedelta(days=1),
                                     source_url='https://synthetic.invalid/codes')
    return Code.objects.create(release=release, code='R00.0', description='Synthetic fixture; no clinical use')


@override_settings(**TEST_SETTINGS)
class GenerationRefusedOverReviewOnOrdinaryForms(OrdinaryDraft, TestCase):
    """A generation replaces every answer and review decision (`jobs.py` adoption). The page offers it only before any
    answer exists, but the server queued it for any POST carrying the current revision."""

    def refused_after(self, *saves):
        encounter = self.drafted()
        keys = sorted(encounter.answers)
        for decision in saves:
            payload = {'answer_' + key: answer['text'] for key, answer in encounter.answers.items()}
            self.post(f'/encounters/{encounter.pk}/save/', encounter, {**payload, **decision(keys)})
        saved = encounter.answers
        response = self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertFalse(run_one(), 'a second generation was queued and run over the saved decisions')
        encounter.refresh_from_db()
        self.assertEqual(Job.objects.filter(encounter=encounter, kind='generation').count(), 1)
        self.assertEqual(encounter.answers, saved)
        self.assertContains(response, REFUSED)
        self.assertContains(response, CLEAR_ACTION)
        self.assertNotContains(response, 'save the source notes again')
        return saved

    def test_generation_is_refused_over_reviewed_answers(self):
        saved = self.refused_after(lambda keys: {'reviewed_' + key: 'on' for key in keys})
        self.assertTrue(all(answer['reviewed'] for answer in saved.values()))           # (the control)

    def test_generation_is_refused_over_an_edited_answer(self):
        saved = self.refused_after(lambda keys: {'answer_' + keys[0]: 'No chest pain, typed by the clinician.'})
        self.assertEqual(sorted(answer['status'] for answer in saved.values()), ['edited', 'supported'])
        self.assertFalse(any(answer['reviewed'] for answer in saved.values()))           # (nothing ticked)

    def test_generation_is_refused_over_a_left_blank_decision(self):
        """Left blank, then carried forward by a later save without its review tick (as the page re-posts the box):
        the decision stands with nothing reviewed and nothing edited."""
        blank = lambda keys: {'blank_' + keys[0]: 'on', 'blank_shown_' + keys[0]: '1', 'answer_' + keys[0]: ''}
        saved = self.refused_after(blank, blank)
        self.assertEqual(sorted((answer['status'], answer['reviewed']) for answer in saved.values()),
                         [('left_blank', False), ('supported', False)])               # (the control)

    def test_a_finalized_record_is_refused_as_immutable_not_advised(self):
        """R2: on a finalized record the refusal advised clearing the draft — an action the record refuses."""
        encounter, _keys = self.reviewed_draft()
        Encounter.objects.filter(pk=encounter.pk).update(status='finalized', finalized_by=self.user, finalized_at=timezone.now())
        response = self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertEqual(Job.objects.filter(encounter=encounter, kind='generation').count(), 1)
        self.assertContains(response, 'Finalized documents are immutable.')
        self.assertNotContains(response, REFUSED)
        self.assertNotContains(response, CLEAR_ACTION)

    def test_a_draft_nobody_has_decided_is_not_refused(self):
        """The refusal reads decisions, not the presence of answers: an untouched draft reaches the existing
        same-revision reuse (nothing new is requested either way)."""
        encounter = self.drafted()
        response = self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertNotContains(response, REFUSED)
        self.assertContains(response, 'No new request was made')


def last_event(action, encounter):
    """The details of the latest audit row of `action` for `encounter` ({} when there is none, so a missing row fails an
    assertion rather than raising)."""
    event = AuditEvent.objects.filter(action=action, target=str(encounter.pk)).order_by('-created_at').first()
    return event.details if event else {}


def cleared(accepted_suggestion=0, left_blank=0, edited_not_accepted=0, reviewed_unedited=0, unreviewed_unedited=0,
            with_clinician_review=0, statements_reviewed=0, statements_recorded_unreviewed=0, codes=0):
    """The audit's counts of what a clearing discarded. Disjoint, as the names say: each answer is counted once in its
    state, and each statement decision once; `with_clinician_review` counts across the answer states (F3)."""
    return {'answers_accepted_suggestion': accepted_suggestion, 'answers_left_blank': left_blank,
            'answers_edited_not_accepted': edited_not_accepted, 'answers_reviewed_unedited': reviewed_unedited,
            'answers_unreviewed_unedited': unreviewed_unedited, 'answers_with_clinician_review': with_clinician_review,
            'statements_reviewed': statements_reviewed, 'statements_recorded_unreviewed': statements_recorded_unreviewed,
            'codes_accepted': codes}


def notes_help(page):
    return re.search(r'<p class="helptext" id="notes-help">(.*?)</p>', page.content.decode(), re.S).group(1)


@override_settings(**TEST_SETTINGS)
class ANotesSaveNeverClearsSilently(OrdinaryDraft, TestCase):
    """R1 (refutation of this branch): saving the notes UNCHANGED wiped every answer, review decision and accepted code,
    by any member, with only the revision in its audit row — and the generation refusal told people to do exactly that."""

    def test_an_unchanged_notes_save_clears_nothing(self):
        encounter, _keys = self.reviewed_draft()
        code = self.accepted_code(encounter)
        before = (encounter.answers, encounter.revision, encounter.status)
        audited = AuditEvent.objects.filter(action='encounter.notes_saved', target=str(encounter.pk)).count()
        self.client.force_login(self.member('guards-notes-employee', 'employee'))
        # (as a browser posts the textarea: its line breaks as CRLF)
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes.replace('\n', '\r\n')})
        self.assertEqual((encounter.answers, encounter.revision, encounter.status), before)
        code.refresh_from_db()
        self.assertEqual(code.accepted_by_id, self.user.pk)
        self.assertContains(response, UNCHANGED)
        self.assertEqual(AuditEvent.objects.filter(action='encounter.notes_saved', target=str(encounter.pk)).count(), audited)

    def test_a_changed_notes_save_clears_as_before_and_records_what_it_cleared(self):
        # Notes whose unlabelled line holds every answer for a decision, each with a one-click suggestion.
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, 'Fictional software test only.\nSymptoms: no chest pain\nExamination: normal gait')
        self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        first, second = sorted(encounter.answers)
        self.assertTrue(encounter.answers[first].get('suggestion'))                  # (the control: an offer to accept)
        self.post(f'/encounters/{encounter.pk}/save/', encounter, {
            'answer_' + first: '', 'accept_' + first: 'on', 'reviewed_' + first: 'on',
            'answer_' + second: '', 'blank_' + second: 'on', 'blank_shown_' + second: '1', 'reviewed_' + second: 'on'})
        self.assertEqual(sorted((a['status'], bool(a.get('accepted_suggestion'))) for a in encounter.answers.values()),
                         [('edited', True), ('left_blank', False)])                     # (the control)
        self.accepted_code(encounter)
        self.assertIn('Saving changed notes clears the answer draft (2 answers: 1 accepted suggestion and 1 decision to leave '
                      'blank; 2 reviewed by a clinician) and 1 accepted code, whoever saves them;',     # (R4-7: from the counts)
                      ' '.join(notes_help(self.client.get(f'/encounters/{encounter.pk}/')).split()))
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic follow-up.'})
        self.assertEqual((encounter.answers, encounter.template_review, CodeSuggestion.objects.filter(encounter=encounter).count()),
                         ({}, {}, 0))
        event = last_event('encounter.notes_saved', encounter)
        # R2-4: each answer is counted once — the accepted suggestion (also `edited` and reviewed) only as accepted.
        self.assertEqual(event.get('cleared'), cleared(accepted_suggestion=1, left_blank=1, with_clinician_review=2, codes=1))

    def test_a_reviewed_transcript_is_applied_even_when_it_leaves_the_notes_as_they_were(self):
        """The unchanged-notes no-op is for a notes save only: a reviewed transcript is always applied (and recorded), or
        it would stay awaiting review with nothing to show why."""
        encounter, _keys = self.reviewed_draft()
        job = self.transcript_awaiting_review(encounter)
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {
            'transcript_job': str(job.pk), 'corrected_transcript': encounter.notes, 'transcript_mode': 'replace',
            'transcript_reviewed': 'on'})
        self.assertTrue(AuditEvent.objects.filter(action='transcription.applied', target=str(job.pk)).exists())
        self.assertNotContains(response, UNCHANGED)


@override_settings(**TEST_SETTINGS)
class TheClearedCountsTellAReviewFromNone(OrdinaryDraft, TestCase):
    """Refutation round 3, F3: the disjoint answer categories dropped the reviewed count, so a changed notes save over two
    answers a clinician edited and ticked reviewed audited exactly as one over two edits nobody reviewed
    (answers_edited_not_accepted: 2); and a draft nobody had touched was not counted at all."""

    def cleared_after_edits(self, reviewed):
        encounter = self.drafted()
        keys = sorted(encounter.answers)
        self.post(f'/encounters/{encounter.pk}/save/', encounter,
                  {**{'answer_' + key: 'Typed by the clinician, synthetic.' for key in keys},
                   **({'reviewed_' + key: 'on' for key in keys} if reviewed else {})})
        self.assertEqual(sorted((a['status'], a['reviewed']) for a in encounter.answers.values()),
                         [('edited', reviewed)] * 2)                                  # (the control)
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic.'})
        self.assertEqual(encounter.answers, {})
        return last_event('encounter.notes_saved', encounter).get('cleared', {})

    def test_a_clinicians_review_of_edited_answers_is_recorded_when_they_are_cleared(self):
        counts = self.cleared_after_edits(reviewed=True)
        self.assertEqual((counts.get('answers_edited_not_accepted'), counts.get('answers_with_clinician_review')), (2, 2))

    def test_edits_nobody_reviewed_are_recorded_as_unreviewed(self):
        counts = self.cleared_after_edits(reviewed=False)
        self.assertEqual((counts.get('answers_edited_not_accepted'), counts.get('answers_with_clinician_review')), (2, 0))

    def test_every_answer_is_counted_once_in_its_state_and_its_review_across_them(self):
        """The states partition the answers that carry text or a decision (a malformed entry included: the save clears it
        too; an empty field nobody decided is not an answer — R4-3); the review count spans them. Unsaved, so no code is
        counted."""
        encounter = Encounter(template_review={}, answers={
            'accepted': {'accepted_suggestion': True, 'status': 'edited', 'reviewed': True},
            'blank': {'status': 'left_blank', 'reviewed': True}, 'edited': {'status': 'edited'},
            'edited_reviewed': {'status': 'edited', 'reviewed': True}, 'reviewed': {'status': 'supported', 'reviewed': True},
            'untouched': {'text': 'Synthetic.', 'status': 'supported', 'reviewed': False}, 'missing': {'status': 'missing'},
            'malformed': 'legacy'})
        counts = views.review_state_counts(encounter, codes=False)
        self.assertEqual({state: counts[state] for state in views.ANSWER_STATES},
                         {'answers_accepted_suggestion': 1, 'answers_left_blank': 1, 'answers_edited_not_accepted': 2,
                          'answers_reviewed_unedited': 1, 'answers_unreviewed_unedited': 2})
        self.assertEqual(sum(counts[state] for state in views.ANSWER_STATES), len(encounter.answers) - 1)   # (not 'missing')
        self.assertEqual(counts['answers_with_clinician_review'], 4)

    def test_a_draft_nobody_reviewed_or_edited_is_counted_when_it_is_cleared(self):
        encounter = self.drafted()
        self.assertEqual(len(encounter.answers), 2)                                       # (the control)
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic.'})
        counts = last_event('encounter.notes_saved', encounter).get('cleared', {})
        self.assertEqual((counts.get('answers_unreviewed_unedited'), counts.get('answers_with_clinician_review')), (2, 0))


def textarea(page, element_id):
    """The raw content of a rendered <textarea> (before the HTML parser drops its first line feed)."""
    return html.unescape(re.search(r'<textarea id="%s"[^>]*>(.*?)</textarea>' % re.escape(element_id),
                                   page.content.decode(), re.S).group(1))


def as_browser_posts(content):
    """What a browser submits for that textarea untouched: the parser drops exactly one line feed right after the start
    tag, and form submission normalizes every line break to CRLF."""
    value = content[1:] if content.startswith('\n') else content
    return value.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')


@override_settings(**TEST_SETTINGS)
class AnUntouchedNotesSaveRoundTrips(OrdinaryDraft, TestCase):
    """Refutation round 2, R2-1: notes stored with a leading line break were shown without it (the HTML parser drops the
    first line feed after <textarea>), posted without it, and an untouched "Save source notes" cleared the whole review."""
    EDITED = OrdinaryDraft.NOTES + '\nPlan: synthetic follow-up.'          # (the doctor's edit: a change, so it is stored)

    def reviewed_with_notes(self, notes):
        encounter, _keys = self.reviewed_draft()
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': notes})   # (the doctor's own edit)
        self.assertEqual(encounter.notes, notes)
        self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        keys = sorted(encounter.answers)
        self.post(f'/encounters/{encounter.pk}/save/', encounter, {**{'answer_' + k: encounter.answers[k]['text'] for k in keys},
                                                                   **{'reviewed_' + k: 'on' for k in keys}})
        self.assertTrue(encounter.answers and all(a['reviewed'] for a in encounter.answers.values()))   # (the control)
        return encounter

    def untouched_save(self, encounter, posted):
        before = (encounter.answers, encounter.revision)
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': posted})
        self.assertEqual((encounter.answers, encounter.revision), before)
        self.assertContains(response, UNCHANGED)

    def test_notes_stored_with_a_leading_line_break_survive_an_untouched_save(self):
        notes = '\r\n' + self.EDITED.replace('\n', '\r\n')
        encounter = self.reviewed_with_notes(notes)
        content = textarea(self.client.get(f'/encounters/{encounter.pk}/'), 'source-notes-edit')
        self.assertEqual(content, '\n' + notes)                    # a line feed right after the start tag, as Django's widget
        self.untouched_save(encounter, as_browser_posts(content))  # (the page as it now renders)

    def test_a_page_rendered_before_the_fix_is_still_an_untouched_save(self):
        """A tab opened before this release shows the notes without their leading break: exactly one is ignored."""
        notes = '\n' + self.EDITED
        encounter = self.reviewed_with_notes(notes)
        self.untouched_save(encounter, as_browser_posts(notes))    # (the old page: no line feed was emitted, one dropped)

    def test_only_one_leading_line_break_is_ignored(self):
        notes = '\r\n\r\n' + self.EDITED.replace('\n', '\r\n')
        encounter = self.reviewed_with_notes(notes)
        self.untouched_save(encounter, notes[2:])                  # (one break dropped: the same notes)
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': notes[4:]})
        self.assertEqual(encounter.answers, {})                    # (both dropped: the doctor removed a line — a change)

    MEASURED = '12 mm at the synthetic junction.\n' + OrdinaryDraft.NOTES

    def changed_save(self, encounter, posted):
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': posted})
        self.assertEqual((encounter.answers, encounter.notes), ({}, posted))
        self.assertNotContains(response, UNCHANGED)

    def test_deleting_the_first_character_is_a_change(self):
        """M1 (the leading-break condition removed from same_text): "12 mm" saved as "2 mm" was "Notes unchanged"."""
        encounter = self.reviewed_with_notes(self.MEASURED)
        self.changed_save(encounter, self.MEASURED[1:])

    def test_deleting_a_leading_space_is_a_change(self):
        """M2 (any leading whitespace ignored, not only the line break the parser drops)."""
        encounter = self.reviewed_with_notes(' ' + self.MEASURED)
        self.changed_save(encounter, self.MEASURED)

    def test_deleting_one_leading_blank_line_is_the_one_deletion_ignored(self):
        """F5, accepted as harmless and pinned: one missing leading line break is what a page rendered before R2-1 posts,
        so deleting one leading blank line reads as "Notes unchanged". The next character is not ignored."""
        encounter = self.reviewed_with_notes('\n' + self.MEASURED)
        self.untouched_save(encounter, self.MEASURED)
        self.changed_save(encounter, self.MEASURED[1:])

    def test_the_same_text_boundary(self):
        same = [('12 mm', '\n12 mm'), ('12 mm', '\r\n12 mm'), ('12 mm', '\r12 mm'), ('a\r\nb', 'a\nb'), ('a\r\nb', 'a\rb')]
        changed = [('2 mm', '12 mm'), ('12 mm', ' 12 mm'), ('12 mm', '\t12 mm'), ('12 mm', '\u00a012 mm'),
                   ('12 mm', '\n\n12 mm'), ('\n12 mm', '12 mm'), ('2 mm', '\n12 mm')]
        self.assertEqual([views.same_text(posted, stored) for posted, stored in same + changed],
                         [True] * len(same) + [False] * len(changed))

    def test_lone_carriage_returns_are_line_breaks_too(self):
        """R2-3 A6: notes stored with lone CRs come back from a browser as CRLF — the same notes."""
        notes = self.EDITED.replace('\n', '\r')
        encounter = self.reviewed_with_notes(notes)
        content = textarea(self.client.get(f'/encounters/{encounter.pk}/'), 'source-notes-edit')
        self.assertEqual(as_browser_posts(content), self.EDITED.replace('\n', '\r\n'))   # (the control: what is posted)
        self.untouched_save(encounter, as_browser_posts(content))

    def test_the_transcript_textarea_keeps_a_leading_line_break_too(self):
        encounter, _keys = self.reviewed_draft()
        self.transcript_awaiting_review(encounter, '\nSynthetic words.')
        job = Job.objects.get(encounter=encounter, kind='transcription')
        content = textarea(self.client.get(f'/encounters/{encounter.pk}/'), f'transcript-{job.pk}')
        self.assertEqual(content, '\n\nSynthetic words.')


def transcript_help(page, job):
    return re.search(r'<p class="helptext" id="transcript-help-%s">(.*?)</p>' % job.pk, page.content.decode(), re.S).group(1)




@override_settings(**TEST_SETTINGS)
class TheNotesPageSaysWhatAChangedSaveClears(OrdinaryDraft, TestCase):
    """Refutation round 2, R2-2 and its INFO: a changed notes save clears the answers, the review decisions and the
    accepted codes, whoever saves it. The page said so only while answers existed, and not plainly."""

    def test_accepted_codes_alone_are_warned_about_in_the_notes_and_transcript_help(self):
        encounter, _keys = self.reviewed_draft()
        self.accepted_code(encounter)
        self.post(f'/encounters/{encounter.pk}/clear-review/', encounter, {'confirm_clear': 'on'})
        self.assertEqual(encounter.answers, {})                                     # (the control: only the code is left)
        job = self.transcript_awaiting_review(encounter)
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertIn('Saving changed notes clears 1 accepted code,', notes_help(page))        # (R4-7: named from the counts)
        self.assertIn('Saving clears 1 accepted code;', transcript_help(page, job))

    def test_statement_decisions_alone_are_warned_about(self):
        encounter, _keys = self.reviewed_draft()
        Encounter.objects.filter(pk=encounter.pk).update(answers={}, template_review={'decisions': {'claim_1': {'variant': 'a'}}})
        self.assertIn('Saving changed notes clears 1 saved prewritten statement wording (not reviewed),',
                      notes_help(self.client.get(f'/encounters/{encounter.pk}/')))

    def test_nothing_to_clear_says_nothing_about_clearing(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        code = self.accepted_code(encounter)
        CodeSuggestion.objects.filter(pk=code.pk).update(accepted_by=None, accepted_at=None)   # (a suggestion nobody accepted)
        self.assertNotIn('clears', notes_help(self.client.get(f'/encounters/{encounter.pk}/')))

    def test_the_person_saving_is_told_plainly_before_and_after(self):
        """INFO: any member's changed save clears a clinician's review. Left as it is, and said plainly to whoever saves."""
        encounter, _keys = self.reviewed_draft()
        self.client.force_login(self.member('guards-notes-employee-2', 'employee'))
        help_text = notes_help(self.client.get(f'/encounters/{encounter.pk}/'))
        for words in ('Saving changed notes clears the answer draft (2 answers, 2 reviewed by a clinician), whoever saves them',
                      'recorded under your name', 'Saving them unchanged clears nothing'):   # (R4-7: what is there, by count)
            self.assertIn(words, ' '.join(help_text.split()))
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic.'})
        self.assertEqual(encounter.answers, {})
        self.assertIn('Notes saved. Cleared, and recorded under your name: the answer draft (2 answers, 2 reviewed by a '
                      'clinician). Generate and review a new answer draft.', shown_messages(response))
        # (and a save that had nothing to clear does not claim it cleared anything)
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: again.'})
        self.assertEqual(shown_messages(response).strip(), 'Notes saved. Generate and review a new answer draft.')


SAVED = 'Notes saved. '
NEXT = 'Generate and review a new answer draft.'


@override_settings(**TEST_SETTINGS)
class TheSaveSaysExactlyWhatItCleared(OrdinaryDraft, TestCase):
    """Refutation round 3, F2: after a changed notes save the message named the answer draft, its review decisions and
    accepted codes whenever anything at all was cleared. After "Clear answers and review" left only an accepted code it
    said all three were cleared while the audit recorded codes_accepted: 1; a fresh draft nobody reviewed, with no code,
    got the same sentence. The message is now read from the counts the save audits."""

    def saved(self, encounter):
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic.'})
        self.assertEqual(encounter.answers, {})
        return shown_messages(response)

    def test_a_save_after_clearing_the_review_names_only_the_accepted_code(self):
        encounter, _keys = self.reviewed_draft()
        self.accepted_code(encounter)
        self.post(f'/encounters/{encounter.pk}/clear-review/', encounter, {'confirm_clear': 'on'})
        self.assertEqual((encounter.answers, encounter.template_review), ({}, {}))           # (the control: only the code)
        said = self.saved(encounter)
        self.assertEqual(last_event('encounter.notes_saved', encounter)['cleared']['codes_accepted'], 1)
        self.assertIn(SAVED + 'Cleared, and recorded under your name: 1 accepted code. ' + NEXT, said)
        for claim in ('answer draft', 'review decision', 'statement'):
            self.assertNotIn(claim, said.split(NEXT)[0])                           # (what it says it cleared)

    def test_a_save_over_a_draft_nobody_reviewed_names_only_the_draft(self):
        encounter = self.drafted()
        said = self.saved(encounter)
        self.assertIn(SAVED + 'Cleared, and recorded under your name: the answer draft (2 answers, none reviewed). ' + NEXT, said)
        for claim in ('review decision', 'accepted code', 'statement'):
            self.assertNotIn(claim, said.split(NEXT)[0])

    def test_the_sentence_names_each_part_only_when_its_count_is_not_zero(self):
        counts = dict.fromkeys(views.review_state_counts(Encounter(answers={}, template_review={}), codes=False), 0)
        self.assertEqual(views.cleared_sentence(counts), '')
        self.assertEqual(views.cleared_sentence({**counts, 'answers_left_blank': 1, 'answers_with_clinician_review': 1}),
                         'Cleared, and recorded under your name: the answer draft (1 answer: 1 decision to leave blank; 1 '
                         'reviewed by a clinician). ')                               # (R4-4: the decision is named)
        self.assertEqual(views.cleared_sentence({**counts, 'answers_edited_not_accepted': 1, 'statements_reviewed': 1,
                                                 'statements_recorded_unreviewed': 1, 'codes_accepted': 2}),
                         'Cleared, and recorded under your name: the answer draft (1 answer, not reviewed), 2 saved prewritten '
                         'statement wordings (1 reviewed by a clinician) and 2 accepted codes. ')

    def test_the_page_warns_exactly_when_the_save_will_name_something(self):
        """The page's warning and the saved message read one set of counts, so they agree even on a malformed entry."""
        encounter, _keys = self.reviewed_draft()
        Encounter.objects.filter(pk=encounter.pk).update(answers={}, template_review={'decisions': {'claim_1': 'legacy'}})
        self.assertIn('Saving changed notes clears', notes_help(self.client.get(f'/encounters/{encounter.pk}/')))
        self.assertIn('Cleared, and recorded under your name: 1 saved prewritten statement wording (not reviewed). ',
                      self.saved(encounter))
        self.assertNotIn('Saving changed notes clears', notes_help(self.client.get(f'/encounters/{encounter.pk}/')))

    def test_a_save_over_statement_wordings_alone_names_them(self):
        """M9's other half: a message whose clearing is read from the answers alone says nothing here."""
        encounter, _keys = self.reviewed_draft()
        Encounter.objects.filter(pk=encounter.pk).update(answers={}, template_review={'decisions': {'claim_1': {'variant': 'a'}}})
        said = self.saved(encounter)
        self.assertIn(SAVED + 'Cleared, and recorded under your name: 1 saved prewritten statement wording (not reviewed). '
                      + NEXT, said)


@override_settings(**TEST_SETTINGS)
class ClearAnswersAndReviewToGenerateAgain(OrdinaryDraft, TestCase):
    """R1(c): the explicit way to generate again over a decided draft — POST only, owner or clinician, confirmed, refused
    while a job is pending or once finalized, audited with the same counts, and a new revision."""

    def clear(self, encounter, **payload):
        encounter.refresh_from_db()
        response = self.client.post(f'/encounters/{encounter.pk}/clear-review/', {'revision': encounter.revision, **payload})
        encounter.refresh_from_db()
        return response

    def test_a_clinician_clears_with_confirmation_and_generates_again(self):
        encounter, _keys = self.reviewed_draft()
        code = self.accepted_code(encounter)
        refused = self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertContains(refused, REFUSED)
        self.assertContains(refused, CLEAR_ACTION)
        self.assertContains(refused, 'data-clear-review')                         # (offered to this clinician)
        before = (encounter.answers, encounter.revision)
        self.assertEqual(self.clear(encounter).status_code, 400)                   # (no confirmation: nothing cleared)
        self.assertEqual((encounter.answers, encounter.revision), before)
        self.assertEqual(self.client.get(f'/encounters/{encounter.pk}/clear-review/').status_code, 405)
        response = self.clear(encounter, confirm_clear='on')
        self.assertEqual(response.status_code, 302)
        self.assertEqual((encounter.answers, encounter.template_review, encounter.status, encounter.revision),
                         ({}, {}, 'draft', before[1] + 1))
        event = AuditEvent.objects.filter(action='encounter.review_cleared', target=str(encounter.pk)).first()
        self.assertEqual((getattr(event, 'actor_id', None), last_event('encounter.review_cleared', encounter).get('revision'),
                          last_event('encounter.review_cleared', encounter).get('cleared')),
                         (self.user.pk, encounter.revision,
                          cleared(reviewed_unedited=2, with_clinician_review=2)))
        code.refresh_from_db()
        self.assertEqual(code.accepted_by_id, self.user.pk)                        # (the notes did not change)
        self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        self.assertEqual(Job.objects.filter(encounter=encounter, kind='generation', state='succeeded').count(), 2)
        self.assertFalse(any(answer['reviewed'] for answer in encounter.answers.values()))

    def test_an_employee_cannot_clear_and_is_not_offered_it(self):
        encounter, _keys = self.reviewed_draft()
        before = (encounter.answers, encounter.revision)
        self.client.force_login(self.member('guards-clear-employee', 'employee'))
        self.assertNotContains(self.client.get(f'/encounters/{encounter.pk}/'), 'data-clear-review')
        self.assertEqual(self.clear(encounter, confirm_clear='on').status_code, 403)
        self.assertEqual((encounter.answers, encounter.revision), before)
        self.assertFalse(AuditEvent.objects.filter(action='encounter.review_cleared').exists())

    def test_clearing_is_refused_while_a_job_is_pending_on_a_stale_page_or_once_finalized(self):
        encounter, _keys = self.reviewed_draft()
        before = (encounter.answers, encounter.revision)
        for state in ('queued', 'running', 'reconciliation'):                     # (R2-3 A7: every pending state)
            job = Job.objects.create(encounter=encounter, user=self.user, kind='generation', revision=encounter.revision,
                                     request_key='synthetic-pending-' + state + str(encounter.pk), state=state)
            self.assertEqual(self.clear(encounter, confirm_clear='on').status_code, 409, state)
            job.state = 'failed'; job.request_key = 'synthetic-ended-' + state + str(encounter.pk); job.save()
        stale = self.client.post(f'/encounters/{encounter.pk}/clear-review/', {'revision': encounter.revision - 1, 'confirm_clear': 'on'})
        self.assertEqual(stale.status_code, 409)
        Encounter.objects.filter(pk=encounter.pk).update(status='finalized', finalized_by=self.user, finalized_at=timezone.now())
        self.client.raise_request_exception = False      # (the database's own guard would answer 500; the page says why)
        self.assertEqual(self.clear(encounter, confirm_clear='on').status_code, 409)
        self.assertEqual((encounter.answers, encounter.revision), before)
        self.assertFalse(AuditEvent.objects.filter(action='encounter.review_cleared').exists())


@override_settings(**TEST_SETTINGS)
class ClearingOutsideTheTestTransaction(OrdinaryDraft, TransactionTestCase):
    """R2-3 A1 and A8, where each request commits on its own (no test-case transaction to hide behind)."""

    def test_a_clear_runs_in_its_own_transaction(self):
        """A8: clear_review locks the row, which needs a transaction of its own."""
        encounter, _keys = self.reviewed_draft()
        self.client.raise_request_exception = False
        response = self.client.post(f'/encounters/{encounter.pk}/clear-review/',
                                    {'revision': encounter.revision, 'confirm_clear': 'on'})
        encounter.refresh_from_db()
        self.assertEqual((response.status_code, encounter.answers), (302, {}))

    def test_a_colleagues_save_waits_for_the_clear_and_is_then_refused_as_stale(self):
        """A1: a colleague's save arriving while a clear is between its checks and its write waits on the row lock, then
        meets the new revision and is refused — never saved and then silently wiped by the clear."""
        encounter, keys = self.reviewed_draft()
        colleague = self.member('guards-race-colleague', 'clinician')
        revision = encounter.revision
        outcome = {}

        def colleague_save():
            try:
                client = Client(); client.force_login(colleague); client.raise_request_exception = False
                payload = {'revision': revision, **{'answer_' + k: encounter.answers[k]['text'] for k in keys},
                           **{'reviewed_' + k: 'on' for k in keys}}
                outcome['status'] = client.post(f'/encounters/{encounter.pk}/save/', payload).status_code
            finally:
                connection.close()

        thread = threading.Thread(target=colleague_save)
        real = views.review_state_counts

        def between_checks_and_write(e, codes=True):
            if not codes:                                  # (the clear's own call: its checks passed, its write is next)
                thread.start(); thread.join(timeout=3)
                outcome['colleague_finished_first'] = not thread.is_alive()
            return real(e, codes=codes)

        self.client.raise_request_exception = False
        with patch.object(views, 'review_state_counts', between_checks_and_write):
            response = self.client.post(f'/encounters/{encounter.pk}/clear-review/', {'revision': revision, 'confirm_clear': 'on'})
        if thread.ident is not None:                       # (started only once the clear reached its write)
            thread.join(timeout=60)
        encounter.refresh_from_db()
        self.assertEqual((response.status_code, outcome.get('colleague_finished_first'), outcome.get('status')), (302, False, 409))
        self.assertEqual((encounter.answers, encounter.revision), ({}, revision + 1))
        self.assertFalse(AuditEvent.objects.filter(action='encounter.answers_saved', actor=colleague).exists())


def shown_messages(response):
    """The page's flash messages, as text."""
    found = re.search(r'<ul class="message-list"[^>]*>(.*?)</ul>', response.content.decode(), re.S)
    return html.unescape(re.sub(r'<[^>]+>', ' ', found.group(1))) if found else ''


def answered_or_blocked(outcome, deadline=60):
    """Waits until the other thread's request has been answered (it sets outcome['status']) or is waiting on a lock (any
    lock not granted in this private test cluster): a positive observation either way, not a guessed timeout; 'timeout'
    if neither happens within `deadline` seconds. The request is the only thing that thread does before it answers."""
    end = time.monotonic() + deadline
    while time.monotonic() < end:
        if 'status' in outcome:
            return 'answered'
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM pg_locks WHERE NOT granted')
            if cursor.fetchone()[0] and 'status' not in outcome:
                return 'waiting'
        time.sleep(0.02)
    return 'timeout'


@override_settings(**TEST_SETTINGS)
class CodeWritersSerializeWithANotesSave(OrdinaryDraft, TransactionTestCase):
    """Refutation round 3, F1: `accept_code` read the encounter without its row lock, so an acceptance could commit after
    a notes save had counted what it would clear and before it cleared the codes: answered 302 and audited, then deleted
    by the save, which told the employee only "Notes saved…" and audited codes_accepted: 0. The refuter's input: an
    encounter with no answers and one offered code; a clinician accepts it while an employee saves changed notes. Each
    request commits on its own, the second in its own thread, as in production."""
    CODED = OrdinaryDraft.NOTES + '\nAssessment: documented as R00.0.'
    CHANGED = OrdinaryDraft.NOTES + '\nPlan: synthetic follow-up.'

    def offered(self, notes=OrdinaryDraft.NOTES, suggestion=True):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, notes)
        self.employee = self.member('guards-code-race-employee', 'employee')
        code = synthetic_code()
        offer = CodeSuggestion.objects.create(encounter=encounter, terminology=code, explanation='Synthetic documented code',
                                              evidence='No chest pain.') if suggestion else None
        self.assertEqual((encounter.answers, CodeSuggestion.objects.filter(accepted_by__isnull=False).count()), ({}, 0))
        return encounter, offer

    def in_thread(self, user, url, payload, outcome):
        client = Client(); client.force_login(user); client.raise_request_exception = False

        def request():
            try:
                response = client.post(url, payload)
                outcome['text'] = html.unescape(response.content.decode()); outcome['status'] = response.status_code
                if response.status_code == 302:                      # (the page it lands on, once answered)
                    outcome['messages'] = shown_messages(client.get(response['Location']))
            finally:
                connection.close()
        return threading.Thread(target=request)

    def run_while(self, thread, target, name, outcome):
        """Patches `target` so that, the first time it is reached, `thread` runs and this request waits until that thread
        has finished or is blocked on a lock."""
        module, attribute = target
        real = getattr(module, attribute)

        def reached(*args, **kwargs):
            result = real(*args, **kwargs)
            if thread.ident is None:
                thread.start(); outcome[name] = answered_or_blocked(outcome)
            return result
        return patch.object(module, attribute, reached)

    def test_an_acceptance_arriving_while_a_save_clears_waits_and_then_finds_its_code_gone(self):
        encounter, offer = self.offered()
        revision, accept = encounter.revision, {}
        thread = self.in_thread(self.user, f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/', {'revision': revision}, accept)
        self.client.force_login(self.employee); self.client.raise_request_exception = False
        # (the save has counted what it will clear, and its write is next)
        with self.run_while(thread, (views, 'review_state_counts'), 'accept_ran', accept):
            saved = self.client.post(f'/encounters/{encounter.pk}/notes/', {'revision': revision, 'notes': self.CHANGED}, follow=True)
        thread.join(timeout=60)
        encounter.refresh_from_db()
        self.assertEqual((accept.get('accept_ran'), accept.get('status')), ('waiting', 409))
        self.assertIn('This code suggestion is unavailable.', accept.get('text', ''))
        self.assertIn('Nothing was accepted.', accept.get('text', ''))
        self.assertFalse(AuditEvent.objects.filter(action='coding.accept').exists())
        self.assertEqual((encounter.notes, CodeSuggestion.objects.filter(encounter=encounter).count()), (self.CHANGED, 0))
        self.assertEqual(last_event('encounter.notes_saved', encounter).get('cleared', {}).get('codes_accepted'), 0)
        self.assertNotIn('accepted code', shown_messages(saved))

    def test_a_save_arriving_while_an_acceptance_commits_waits_and_then_states_the_accepted_code(self):
        encounter, offer = self.offered()
        revision, save = encounter.revision, {}
        thread = self.in_thread(self.employee, f'/encounters/{encounter.pk}/notes/', {'revision': revision, 'notes': self.CHANGED}, save)
        # (the acceptance's checks are under way, and its write is next)
        with self.run_while(thread, (coding_module, 'applicable_releases'), 'save_ran', save):
            accepted = self.client.post(f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/', {'revision': revision})
        thread.join(timeout=60)
        encounter.refresh_from_db()
        self.assertEqual((accepted.status_code, save.get('save_ran'), save.get('status')), (302, 'waiting', 302))
        self.assertTrue(AuditEvent.objects.filter(action='coding.accept', target=str(offer.pk)).exists())
        self.assertEqual((encounter.notes, CodeSuggestion.objects.filter(encounter=encounter).count()), (self.CHANGED, 0))
        self.assertEqual(last_event('encounter.notes_saved', encounter).get('cleared', {}).get('codes_accepted'), 1)
        self.assertIn('accepted code', save.get('messages', ''))

    def test_suggestions_are_never_drawn_from_notes_a_concurrent_save_replaced(self):
        """`coding` wrote suggestions from the notes it had read, unlocked, before a save replaced them. Since R4-2 it reads
        them unlocked on purpose, so a save is not held up by the pass, and re-checks the page's revision under the lock
        before writing: a save landing meanwhile is answered at once, and the suggestion is refused with nothing written."""
        encounter, _offer = self.offered(self.CODED, suggestion=False)
        revision, save = encounter.revision, {}
        thread = self.in_thread(self.employee, f'/encounters/{encounter.pk}/notes/', {'revision': revision, 'notes': self.CHANGED}, save)
        # (the suggestion has read the notes and is working out what they support, holding no lock)
        with self.run_while(thread, (coding_module, 'applicable_releases'), 'save_ran', save):
            suggested = self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': revision})
        thread.join(timeout=60)
        encounter.refresh_from_db()
        self.assertEqual((suggested.status_code, save.get('save_ran'), save.get('status')), (409, 'answered', 302))
        self.assertIn('Nothing was suggested.', html.unescape(suggested.content.decode()))
        self.assertEqual((encounter.notes, CodeSuggestion.objects.filter(encounter=encounter).count(),
                          AuditEvent.objects.filter(action='coding.suggest').count()), (self.CHANGED, 0, 0))

    def test_a_save_arriving_while_suggestions_are_written_waits_and_then_clears_them(self):
        """The write half: under the lock, a save waits for the suggestions and their audit row, then clears them."""
        encounter, _offer = self.offered(self.CODED, suggestion=False)
        revision, save = encounter.revision, {}
        thread = self.in_thread(self.employee, f'/encounters/{encounter.pk}/notes/', {'revision': revision, 'notes': self.CHANGED}, save)
        # (the suggestions and their audit row are written, and the commit is next)
        with self.run_while(thread, (coding_module, 'audit'), 'save_ran', save):
            suggested = self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': revision})
        thread.join(timeout=60)
        encounter.refresh_from_db()
        self.assertEqual((suggested.status_code, save.get('save_ran'), save.get('status')), (302, 'waiting', 302))
        self.assertEqual(AuditEvent.objects.filter(action='coding.suggest').count(), 1)
        self.assertEqual((encounter.notes, CodeSuggestion.objects.filter(encounter=encounter).count()), (self.CHANGED, 0))


def page_form(page, action_suffix):
    """The action and hidden fields of the page's form that posts to a URL ending `action_suffix`, as a browser posts them."""
    for form in re.finditer(r'<form method="post" action="([^"]*)"[^>]*>(.*?)</form>', page.content.decode(), re.S):
        if form.group(1).endswith(action_suffix):
            return form.group(1), dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', form.group(2)))
    return None, {}


@override_settings(**TEST_SETTINGS)
class TheCodingTabPostsTheRevisionItShows(OrdinaryDraft, TestCase):
    """F1's repair refuses a code write from a page older than the document, so the page posts the revision it shows."""
    CODED = OrdinaryDraft.NOTES + '\nAssessment: documented as R00.0.'

    def coded(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        synthetic_code()
        return encounter

    def test_suggesting_and_accepting_as_the_page_posts_them(self):
        encounter = self.coded()
        url, fields = page_form(self.client.get(f'/encounters/{encounter.pk}/?tab=coding'), '/coding/')
        self.assertEqual(fields.get('revision'), str(encounter.revision))
        self.assertEqual(self.client.post(url, fields).status_code, 302)
        offer = CodeSuggestion.objects.get(encounter=encounter)
        url, fields = page_form(self.client.get(f'/encounters/{encounter.pk}/?tab=coding'), f'/coding/{offer.pk}/accept/')
        self.assertEqual(fields.get('revision'), str(encounter.revision))
        self.assertEqual(self.client.post(url, fields).status_code, 302)
        offer.refresh_from_db()
        self.assertEqual(offer.accepted_by_id, self.user.pk)

    def test_a_page_older_than_the_document_suggests_and_accepts_nothing_and_says_why(self):
        encounter = self.coded()
        self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        offer = CodeSuggestion.objects.get(encounter=encounter)
        stale = encounter.revision
        Encounter.objects.filter(pk=encounter.pk).update(revision=stale + 1)     # (as an answers save elsewhere renumbers it)
        refused = self.client.post(f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/', {'revision': stale})
        self.assertContains(refused, 'This document changed after you opened it', status_code=409)
        self.assertContains(refused, 'Nothing was accepted.', status_code=409)
        offer.refresh_from_db()
        self.assertIsNone(offer.accepted_by_id)
        self.assertFalse(AuditEvent.objects.filter(action='coding.accept').exists())
        suggested = AuditEvent.objects.filter(action='coding.suggest').count()
        self.assertContains(self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': stale}),
                            'Nothing was suggested.', status_code=409)
        self.assertEqual(AuditEvent.objects.filter(action='coding.suggest').count(), suggested)
        # (a page rendered before this release posts no revision, and is refused the same way)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/').status_code, 409)

    def test_an_acceptance_from_before_a_changed_save_says_its_code_is_gone(self):
        encounter = self.coded()
        self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        offer = CodeSuggestion.objects.get(encounter=encounter)
        stale = encounter.revision
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': self.CODED + '\nPlan: synthetic.'})
        self.assertFalse(CodeSuggestion.objects.filter(pk=offer.pk).exists())            # (the control: the save cleared it)
        refused = self.client.post(f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/', {'revision': stale})
        self.assertContains(refused, 'This code suggestion is unavailable.', status_code=409)
        self.assertContains(refused, 'Nothing was accepted.', status_code=409)
        # (a suggestion that was never on this document is not found, at any revision)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/',
                                          {'revision': encounter.revision}).status_code, 404)


# ── the qualified Word form, offline ─────────────────────────────────────────────────────────────────────────────
def statement(key, paragraph, label, text, variants, kind='assertion'):
    return {'key': key, 'kind': kind, 'body_paragraph': paragraph, 'label': 'Prewritten statement: ' + label,
            'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'control_keys': [],
            'default_variant': variants[0][0],
            'variants': [{'id': identifier, 'label': identifier, 'text_template': template,
                          'required_control_keys': [], 'empty_control_keys': []} for identifier, template in variants]}


FIELDS = [
    {'key': 'sdt_-213273323', 'label': 'Right impression: reflux or absence', 'kind': 'choice',
     'options': ['reflux positive.', 'is absent.'], 'locator': {'part': 'word/document.xml', 'sdt_id': '-213273323'}},
    {'key': 'measurement_1_1', 'label': 'Right GSV at the SFJ: diameter (mm)', 'kind': 'measurement', 'options': [],
     'locator': {'table': 0, 'row': 1, 'column': 1, 'unit': 'mm'}},
    {'key': 'patient_name', 'label': 'Patient name', 'kind': 'text', 'options': [], 'locator': {'body_paragraph': 3}},
    {'key': 'location_11', 'label': 'Right tributary row 11: anatomical location', 'kind': 'text', 'options': [],
     'locator': {'table': 0, 'row': 11, 'column': 0, 'marker': '<<insert location>>'}},
]
NOT_ASSESSED = 'Right saphenous reflux was not assessed.'
REQUIREMENTS = [
    statement('claim_9', 9, 'Exam type', 'TYPE OF EXAM: Full Study', [('original', 'TYPE OF EXAM: Full Study')]),
    statement('claim_32', 32, 'Right saphenous reflux finding', 'No saphenous reflux in right lower extremity.',
              [('negative', 'No saphenous reflux in right lower extremity.'), ('not_assessed', NOT_ASSESSED)]),
    statement('claim_46', 46, 'Signer identity', 'SYNTHETIC PREPRINTED SIGNER', [('trusted', '{signer_name}')], kind='identity'),
]
VALUES = {'sdt_-213273323': 'is absent.', 'measurement_1_1': '3.2 mm', 'patient_name': 'SYNTHETIC WM GUARD PATIENT',
          'location_11': 'medial calf'}
NOTES = '\n'.join([field['label'] + ': ' + VALUES[field['key']] for field in FIELDS] + [
    'Prewritten statement: Exam type: TYPE OF EXAM: Full Study',
    'Prewritten statement: Right saphenous reflux finding: ' + NOT_ASSESSED])


def synthetic_resolver(encounter, actor, decisions=None):
    """`views.wm_resolve` as the engine answers it for these statements (none has an answer token): the chosen wordings,
    signed by the finalizing clinician once finalized and otherwise by the viewer (`trusted_context.signer_name`)."""
    decisions = decisions if decisions is not None else encounter.template_review.get('decisions', {})
    signer = encounter.finalized_by if encounter.status == 'finalized' else actor
    name = ' '.join(signer.get_full_name().split()) or signer.email
    rows = []
    for original in encounter.template_version.review_requirements:
        chosen = decisions.get(original['key'], {}).get('variant', original['default_variant'])
        text = next(v for v in original['variants'] if v['id'] == chosen)['text_template'].replace('{signer_name}', name)
        rows.append({**original, 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                     'original_text': original['text'], 'original_text_sha256': original['text_sha256'],
                     'selected_variant': chosen, 'changed': text != original['text']})
    return rows


@override_settings(**TEST_SETTINGS)
class OfflineWordForm(SyntheticFixture, TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=Path(directory.name)); override.enable(); self.addCleanup(override.disable)
        self.user, _, self.department, self.patient, self.template, self.encounter, _ = self.make_scope('wm-guards')
        User.objects.filter(pk=self.user.pk).update(first_name='SYNTHETIC', last_name='Clinician A')
        self.user.refresh_from_db()
        self.template.sha256 = ORIGINAL_SHA256; self.template.save(update_fields=['sha256'])
        self.version = TemplateVersion.objects.create(
            template=self.template, number=2, fields=FIELDS, review_requirements=REQUIREMENTS, created_by=self.user,
            document_backend={'backend': BACKEND, 'source_sha256': ORIGINAL_SHA256, 'mapping_digest': 'a' * 64})
        answers = {}
        for field in FIELDS:
            line = field['label'] + ': ' + VALUES[field['key']]
            start = NOTES.index(line)
            answers[field['key']] = {'text': VALUES[field['key']], 'status': 'supported', 'reviewed': False,
                                     'evidence': [{'quote': line, 'start': start, 'end': start + len(line)}]}
        self.encounter.template_version = self.version; self.encounter.notes = NOTES; self.encounter.answers = answers
        self.encounter.status = 'review'; self.encounter.template_review = {}
        self.encounter.save()
        resolver = patch('core.views.wm_resolve', side_effect=synthetic_resolver); resolver.start(); self.addCleanup(resolver.stop)
        self.client.force_login(self.user)

    def member(self, name, role, full_name=''):
        user = User.objects.create_user(username=name, email=name + '@synthetic.invalid', verified_at=timezone.now(),
                                        first_name='SYNTHETIC', last_name=full_name)
        Membership.objects.create(user=user, department=self.department, role=role)
        return user

    def page(self):
        response = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertEqual(response.status_code, 200)
        return response

    def save(self, change=(), ticks=False):
        """The page as a browser posts it, with `change` applied (and, for a clinician, every review box ticked)."""
        page = self.page()
        payload = BrowserSaveForm.of(page)
        if ticks:
            payload.update({'reviewed_' + field['key']: 'on' for field in FIELDS})
            payload.update({'claim_reviewed_' + row['key']: 'on' for row in REQUIREMENTS})
        payload.update(dict(change))
        response = self.client.post(f'/encounters/{self.encounter.pk}/save/', payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.encounter.refresh_from_db()
        return response

    STATEMENT_SOURCES = {'claim_source_claim_9': 'Prewritten statement: Exam type: TYPE OF EXAM: Full Study',
                         'claim_source_claim_32': 'Prewritten statement: Right saphenous reflux finding: ' + NOT_ASSESSED}

    def clinician_reviews(self):
        """The clinician chooses "not assessed" for claim_32, saves to see the wording, then reviews everything."""
        self.save({'claim_variant_claim_32': 'not_assessed', **self.STATEMENT_SOURCES})
        self.save(ticks=True)
        review = self.encounter.template_review
        self.assertEqual((review['schema'], review['assessment']['complete']), (1, True), review.get('assessment'))
        self.assertEqual({key: (d['variant'], d['reviewed']) for key, d in review['decisions'].items()},
                         {'claim_9': ('original', True), 'claim_32': ('not_assessed', True), 'claim_46': ('trusted', True)})
        return review


class GenerationRefusedOverWordStatementDecisions(OfflineWordForm):
    def test_statement_decisions_alone_refuse_generation(self):
        """The draft branch's focused pass: statement decisions with no answer ticked — here a wording chosen and saved
        without its tick — were replaced by a second, billed draft."""
        self.save({'claim_variant_claim_32': 'not_assessed'})
        self.assertFalse(any(answer.get('reviewed') for answer in self.encounter.answers.values()))   # (the control)
        self.assertEqual(self.encounter.template_review['decisions']['claim_32']['variant'], 'not_assessed')
        before = (self.encounter.answers, self.encounter.template_review)
        response = self.client.post(f'/encounters/{self.encounter.pk}/generate/', {'revision': self.encounter.revision}, follow=True)
        self.encounter.refresh_from_db()
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(), 0)
        self.assertEqual((self.encounter.answers, self.encounter.template_review), before)
        self.assertContains(response, REFUSED)


class EmployeeSaveKeepsStatementDecisions(OfflineWordForm):
    """An employee's save rebuilt nothing of the clinician's statement review: `invalidate_review` emptied it, only a
    clinician's save rebuilds one, so the chosen wordings, their sources and the reviews vanished without a word and the
    next page fell back to the mapping's defaults."""

    def test_an_employees_plain_save_keeps_the_decisions_unreviewed_bound_and_says_so(self):
        reviewed = self.clinician_reviews()
        employee = self.member('wm-guards-employee', 'employee')
        self.client.force_login(employee)
        response = self.save()
        review = self.encounter.template_review
        self.assertEqual(set(review.get('decisions') or {}), {'claim_9', 'claim_32', 'claim_46'})
        for key, decision in reviewed['decisions'].items():
            self.assertEqual(review['decisions'][key], {**decision, 'reviewed': False}, key)
        self.assertEqual(review['schema'], 0)                              # (never accepted by finalization)
        self.assertEqual(review['binding'], wm_review.binding(self.encounter))
        self.assertEqual(last_event('encounter.answers_saved', self.encounter).get('withdrawn_statement_reviews'),
                         ['claim_32', 'claim_46', 'claim_9'])
        self.assertContains(response, 'were kept but are no longer reviewed')
        self.assertNotContains(response, 'was not kept')                   # (nothing was changed under a wording)
        # The clinician's page shows the kept wording, not the default, and asks for the review again.
        self.client.force_login(self.user)
        page = self.page()
        self.assertEqual(BrowserSaveForm.of(page)['claim_variant_claim_32'], 'not_assessed')
        self.assertIn(NOT_ASSESSED, {row['key']: row['text'] for row in page.context['wm_requirements']}['claim_32'])

    def test_a_source_an_employee_changes_under_the_clinicians_wording_is_not_kept_and_the_saver_is_told(self):
        reviewed = self.clinician_reviews()
        self.client.force_login(self.member('wm-guards-employee-2', 'employee'))
        response = self.save({'claim_source_claim_32': 'Prewritten statement: Exam type: TYPE OF EXAM: Full Study'})
        self.assertEqual(self.encounter.template_review['decisions']['claim_32']['evidence'],
                         reviewed['decisions']['claim_32']['evidence'])
        self.assertContains(response, 'A statement source you changed was not kept')

    def test_a_wording_the_employee_replaces_is_named_as_replaced_and_audited(self):
        """R3: an employee replacing the wording a clinician reviewed was told the reviewed choices were "kept", and the
        audit recorded only the withdrawn review — not that the wording changed."""
        self.clinician_reviews()
        self.client.force_login(self.member('wm-guards-employee-3', 'employee'))
        response = self.save({'claim_variant_claim_32': 'negative'})
        decision = self.encounter.template_review['decisions']['claim_32']
        self.assertEqual((decision['variant'], decision['reviewed']), ('negative', False))
        warnings = [str(message) for message in response.context['messages']]
        self.assertIn('Review remains incomplete: Your save replaced the chosen statement wording for: Prewritten statement: '
                      'Right saphenous reflux finding. A clinician must review the new wording.', warnings)
        self.assertIn('Review remains incomplete: The statement choices a clinician reviewed were kept but are no longer '
                      'reviewed: Prewritten statement: Exam type; Prewritten statement: Signer identity. A clinician must '
                      'review them again.', warnings)
        event = last_event('encounter.answers_saved', self.encounter)
        self.assertEqual(event.get('statement_wording_changes'), [{'statement': 'claim_32', 'from': 'not_assessed', 'to': 'negative'}])
        self.assertNotIn('reflux', json.dumps(event))                      # (identifiers only, never clinical text)


    def test_a_clinicians_unreviewed_statement_choices_survive_an_employees_save(self):
        """R4 (the refutation's P5): choices a clinician saved without ticking them are decisions too; and R5: nothing
        reviewed was withdrawn, so the saver is not told so and the audit lists nothing."""
        self.save({'claim_variant_claim_32': 'not_assessed', **self.STATEMENT_SOURCES})     # (the clinician, no ticks)
        chosen = self.encounter.template_review['decisions']
        self.assertEqual((chosen['claim_32']['variant'], any(d['reviewed'] for d in chosen.values())), ('not_assessed', False))
        self.client.force_login(self.member('wm-guards-employee-4', 'employee'))
        response = self.save()
        self.assertEqual((self.encounter.template_review or {}).get('decisions'), chosen)
        self.assertNotContains(response, 'no longer reviewed')
        self.assertNotContains(response, 'replaced the chosen statement wording')
        event = last_event('encounter.answers_saved', self.encounter)
        self.assertEqual((event.get('withdrawn_statement_reviews'), event.get('statement_wording_changes')), ([], []))


class WithdrawnStatementReviewsAreThoseTheSaveDidNotKeep(OfflineWordForm):
    def test_a_clinicians_re_save_withdraws_only_the_review_it_unticks(self):
        """R5: `withdrawn_statement_reviews` compares what was reviewed with what the save stored reviewed."""
        self.clinician_reviews()
        self.save()                                          # (the same clinician: the page re-posts the ticks as rendered)
        self.assertTrue(all(d['reviewed'] for d in self.encounter.template_review['decisions'].values()))   # (the control)
        self.assertEqual(last_event('encounter.answers_saved', self.encounter).get('withdrawn_statement_reviews'), [])
        payload = BrowserSaveForm.of(self.page())
        self.assertEqual(payload.pop('claim_reviewed_claim_32'), 'on')
        self.client.post(f'/encounters/{self.encounter.pk}/save/', payload)
        self.assertEqual(last_event('encounter.answers_saved', self.encounter).get('withdrawn_statement_reviews'), ['claim_32'])


class WordNotesSaveAndClear(OfflineWordForm):
    """R1 on the Word form: statement decisions are review state too."""

    def test_an_unchanged_notes_save_keeps_the_statement_decisions_and_a_changed_one_counts_them(self):
        reviewed = self.clinician_reviews()
        self.client.force_login(self.member('wm-guards-notes-employee', 'employee'))
        url = f'/encounters/{self.encounter.pk}/notes/'
        response = self.client.post(url, {'revision': self.encounter.revision, 'notes': self.encounter.notes}, follow=True)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.template_review, reviewed)
        self.assertContains(response, UNCHANGED)
        self.client.post(url, {'revision': self.encounter.revision, 'notes': self.encounter.notes + '\nSynthetic addendum.'})
        self.encounter.refresh_from_db()
        self.assertEqual((self.encounter.answers, self.encounter.template_review), ({}, {}))
        event = last_event('encounter.notes_saved', self.encounter)
        self.assertEqual(event.get('cleared'), cleared(reviewed_unedited=4, with_clinician_review=4, statements_reviewed=3))

    def test_mixed_review_states_are_each_counted_in_their_own_category(self):
        """R2-3 A2-A5: reviewed and unreviewed answers and statement choices, accepted and unaccepted codes."""
        self.clinician_reviews()
        payload = BrowserSaveForm.of(self.page())                    # (the same clinician; the ticks re-posted as rendered)
        self.assertEqual((payload.pop('claim_reviewed_claim_32'), payload.pop('reviewed_patient_name')), ('on', 'on'))
        self.client.post(f'/encounters/{self.encounter.pk}/save/', payload)
        self.encounter.refresh_from_db()
        self.assertEqual(sum(bool(a.get('reviewed')) for a in self.encounter.answers.values()), 3)          # (the controls)
        self.assertEqual(sum(bool(d['reviewed']) for d in self.encounter.template_review['decisions'].values()), 2)
        code = OrdinaryDraft.accepted_code(self, self.encounter)
        unaccepted = Code.objects.create(release=code.terminology.release, code='R00.1', description='Synthetic fixture')
        CodeSuggestion.objects.create(encounter=self.encounter, terminology=unaccepted, explanation='Synthetic', evidence='x')
        self.client.post(f'/encounters/{self.encounter.pk}/notes/', {'revision': self.encounter.revision,
                                                                     'notes': self.encounter.notes + '\nSynthetic addendum.'})
        self.assertEqual(last_event('encounter.notes_saved', self.encounter).get('cleared'),
                         cleared(reviewed_unedited=3, unreviewed_unedited=1, with_clinician_review=3, statements_reviewed=2,
                                 statements_recorded_unreviewed=1, codes=1))

    def test_a_changed_save_names_each_thing_it_cleared(self):
        self.clinician_reviews()
        OrdinaryDraft.accepted_code(self, self.encounter)
        response = self.client.post(f'/encounters/{self.encounter.pk}/notes/', {'revision': self.encounter.revision,
                                    'notes': self.encounter.notes + '\nSynthetic addendum.'}, follow=True)
        self.assertIn('Notes saved. Cleared, and recorded under your name: the answer draft (4 answers, 4 reviewed by a '
                      'clinician), 3 saved prewritten statement wordings (3 reviewed by a clinician) and 1 accepted code. '
                      'Generate and review a new answer draft.', shown_messages(response))

    def test_clearing_counts_the_statement_decisions_it_clears(self):
        self.clinician_reviews()
        response = self.client.post(f'/encounters/{self.encounter.pk}/clear-review/',
                                    {'revision': self.encounter.revision, 'confirm_clear': 'on'})
        self.assertEqual(response.status_code, 302)
        self.encounter.refresh_from_db()
        self.assertEqual((self.encounter.answers, self.encounter.template_review), ({}, {}))
        event = last_event('encounter.review_cleared', self.encounter)
        self.assertEqual(event.get('cleared'), cleared(reviewed_unedited=4, with_clinician_review=4, statements_reviewed=3))


class StatementCountsSayWhatTheyCount(OfflineWordForm):
    """Refutation round 3, F4: `statements_chosen_unreviewed` counted wordings nobody chose. A plain save posts every
    statement's wording as the page renders it (its default), and each is recorded as a decision; a changed notes save
    then audited three "chosen". The record cannot tell a deliberate choice of the default wording from none, so the key
    says what it counts: statement decisions recorded and unreviewed."""

    def test_wordings_saved_as_rendered_are_not_counted_as_chosen(self):
        self.save()                                          # (as the page renders it: nobody chose a wording)
        self.assertEqual({key: (d['variant'], d['reviewed']) for key, d in self.encounter.template_review['decisions'].items()},
                         {'claim_9': ('original', False), 'claim_32': ('negative', False), 'claim_46': ('trusted', False)})
        self.client.post(f'/encounters/{self.encounter.pk}/notes/', {'revision': self.encounter.revision,
                                                                     'notes': self.encounter.notes + '\nSynthetic addendum.'})
        counts = last_event('encounter.notes_saved', self.encounter).get('cleared', {})
        self.assertNotIn('statements_chosen_unreviewed', counts)
        self.assertEqual((counts.get('statements_recorded_unreviewed'), counts.get('statements_reviewed')), (3, 0))


class AFinalizedRecordIsNotReReviewedByItsReader(OfflineWordForm):
    """A finalized record was re-evaluated as the reader's own review: for any clinician but the signer, the signer's
    identity no longer resolved to the reader and the page said the Word review was incomplete, showing the template's
    original wordings instead of the finalized ones."""

    def finalized(self):
        self.clinician_reviews()
        self.encounter.status = 'finalized'; self.encounter.finalized_by = self.user
        self.encounter.finalized_at = timezone.now(); self.encounter.export_path = 'exports/synthetic.docx'
        self.encounter.export_sha256 = '0' * 64
        self.encounter.save()

    def test_a_second_clinician_sees_the_finalized_record_as_finalized(self):
        self.finalized()
        self.client.force_login(self.member('wm-guards-clinician-b', 'clinician', full_name='Clinician B'))
        page = self.page()
        self.assertEqual(page.context['wm_review_error'], '')
        shown = {row['key']: row for row in page.context['wm_requirements']}
        self.assertEqual(shown['claim_32']['text'], NOT_ASSESSED)          # the finalized wording
        self.assertEqual(shown['claim_46']['text'], 'SYNTHETIC Clinician A')  # its signer, not the reader
        self.assertEqual({row['key']: row['review_errors'] for row in shown.values()},
                         {'claim_9': [], 'claim_32': [], 'claim_46': []})
        self.assertEqual({row['key']: (row['status'], row['review_errors']) for row in page.context['answer_rows']},
                         {field['key']: ('supported', []) for field in FIELDS})
        self.assertNotContains(page, 'Word review is incomplete')

    def test_a_record_not_yet_finalized_is_still_the_readers_own_review(self):
        """The control: before finalization the reader's page is their own review, so another clinician's ticks are not
        theirs."""
        self.clinician_reviews()
        self.client.force_login(self.member('wm-guards-clinician-c', 'clinician', full_name='Clinician C'))
        page = self.page()
        errors = {row['key']: row['review_errors'] for row in page.context['answer_rows']}
        self.assertTrue(all(errors.values()), errors)


# ── refutation round 4 ────────────────────────────────────────────────────────────────────────────────────────────
FINALIZED = 'This document is finalized.'


@override_settings(**TEST_SETTINGS)
class CodeWritersRefuseAFinalizedRecord(OrdinaryDraft, TestCase):
    """Refutation round 4, R4-1: finalization does not renumber the revision, so a Coding tab opened before it (an offer on
    the page, at revision R) still posts the current revision afterwards. Its Accept answered 302, set accepted_by and
    audited coding.accept after encounter.finalize; its Suggest added a suggestion and audited coding.suggest. Every other
    writer already refused a finalized record."""
    CODED = 'Symptoms: No chest pain.\nExamination: Normal gait, documented as R00.0 and R00.1.'
    finalize = OrdinaryDraft.workflow.finalize

    def test_a_coding_page_opened_before_finalization_changes_nothing_after_it(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        code = synthetic_code()
        self.generate(encounter)
        self.post(f'/encounters/{encounter.pk}/save/', encounter, {**{'answer_' + k: a['text'] for k, a in encounter.answers.items()},
                                                                   **{'reviewed_' + k: 'on' for k in encounter.answers}})
        url, fields = page_form(self.client.get(f'/encounters/{encounter.pk}/?tab=coding'), '/coding/')
        self.assertEqual(self.client.post(url, fields).status_code, 302)
        offer = CodeSuggestion.objects.get(encounter=encounter)
        # (a second documented code, in the release but not yet suggested: what a stale Suggest would add)
        Code.objects.create(release=code.release, code='R00.1', description='Synthetic fixture; no clinical use')
        page = self.client.get(f'/encounters/{encounter.pk}/?tab=coding')
        stale = [(page_form(page, f'/coding/{offer.pk}/accept/'), 'Nothing was accepted.'), (page_form(page, '/coding/'), 'Nothing was suggested.')]
        revision = encounter.revision
        self.finalize(encounter)
        self.assertEqual((encounter.status, encounter.revision), ('finalized', revision))   # (the premise: the revision stayed)
        said = []
        for (url, fields), nothing in stale:
            self.assertEqual(fields.get('revision'), str(revision))
            refused = self.client.post(url, fields)
            text = html.unescape(refused.content.decode())
            said.append((refused.status_code, FINALIZED in text, nothing in text))
        offer.refresh_from_db()
        # (as a whole, so a failure shows both writers: status and words; then the acceptance, the suggestions, the audit)
        self.assertEqual((said, offer.accepted_by_id, CodeSuggestion.objects.filter(encounter=encounter).count(),
                          AuditEvent.objects.filter(action='coding.accept').count(),
                          AuditEvent.objects.filter(action='coding.suggest').count()),   # (1: the one before finalization)
                         ([(409, True, True)] * 2, None, 1, 0, 1))


ALNUM = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
#: 12,000 distinct three-character codes: joined by one separator they are 47,999 characters of notes.
MANY_CODES = [letter + second + third for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' for second in ALNUM for third in ALNUM][:12000]


@override_settings(**TEST_SETTINGS)
class SuggestingCodesDoesNotHoldTheDocument(OrdinaryDraft, TransactionTestCase):
    """Refutation round 4, R4-2: `coding` held the encounter's row lock for its whole suggestion pass, and the pass rescanned
    the notes once per code. The refuter's input: any department member (an employee) saves 48,000 characters holding
    12,000 synthetic codes, all in the release in effect, and posts Suggest codes — the lock was held 70.6 s, a page view
    of that encounter waited 77.2 s, and with 2 workers the site stalls. Measured here, each request committing on its own:
    how long the request holds the row lock once it has taken it (from the locking query to its answer — an upper bound,
    since it commits before answering), what another request waits for that lock, and the request's own time."""
    LOCK_BOUND = 5.0          # seconds the encounter row may stay locked by one Suggest codes request
    REQUEST_BOUND = 30.0      # seconds the whole request may take on this input

    def suggested(self, separator):
        today = timezone.localdate()
        release = CodeSet.objects.create(system='ICD-10-CM', version='synthetic-review-guards-cost', sha256='0' * 64,
                                         effective_from=today - timedelta(days=1), effective_until=today + timedelta(days=1),
                                         source_url='https://synthetic.invalid/codes')
        Code.objects.bulk_create([Code(release=release, code=code, description='Synthetic fixture; no clinical use')
                                  for code in MANY_CODES])
        notes = separator.join(MANY_CODES)
        self.assertEqual(len(notes), 47999)                                          # (the control: the refuter's size)
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, notes)
        self.client.force_login(self.member('guards-cost-employee', 'employee'))
        measured = {}

        def other_request():
            try:
                started = time.monotonic()
                with transaction.atomic():
                    Encounter.objects.select_for_update().get(pk=encounter.pk)
                measured['other_waited'] = time.monotonic() - started
            finally:
                connection.close()
        other = threading.Thread(target=other_request)

        def locking(execute, sql, params, many, context):
            result = execute(sql, params, many, context)
            if 'locked' not in measured and 'FOR UPDATE' in sql and 'core_encounter' in sql:
                measured['locked'] = time.monotonic(); other.start()
            return result

        started = time.monotonic()
        with connection.execute_wrapper(locking):
            response = self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        answered = time.monotonic()
        other.join(timeout=600)
        held = round(answered - measured.get('locked', started), 1)
        self.said = shown_messages(self.client.get(response['Location'])) if response.status_code == 302 else ''
        self.encounter = encounter
        return (response.status_code, CodeSuggestion.objects.filter(encounter=encounter).count(),
                held, round(measured.get('other_waited', -1), 1), round(answered - started, 1))

    def within_bounds(self, separator):
        status, count, held, waited, took = self.suggested(separator)
        # A document holds at most 100 suggestions: the first 100 the notes document, and the other 11,900 said and audited.
        details = last_event('coding.suggest', self.encounter)
        self.assertEqual((status, count, details.get('count'), details.get('not_suggested_over_limit')), (302, 100, 100, 11900))
        self.assertEqual(set(CodeSuggestion.objects.filter(encounter=self.encounter).values_list('terminology__code', flat=True)),
                         set(MANY_CODES[:100]))
        self.assertIn('11900 further documented codes were not suggested: a document holds at most 100 code suggestions.', self.said)
        self.assertTrue(held < self.LOCK_BOUND and waited < self.LOCK_BOUND and took < self.REQUEST_BOUND,
                        f'lock held {held} s, another request waited {waited} s, the request took {took} s')

    def test_codes_one_per_line(self):
        self.within_bounds('\n')

    def test_codes_on_one_line(self):
        self.within_bounds(' ')


def searched_line_by_line(notes, wanted):
    """What `core.coding` read before R4-2: for each code, the first line the per-code search matches, or None."""
    return {code: next((line for line in notes.splitlines()
                        if re.search(r'(?<![\w.])' + re.escape(code) + r'(?!\w)(?!\.[0-9A-Za-z])', line, re.I)), None)
            for code in wanted}


class TheLinearScanReadsAsThePerCodeSearchDid(TestCase):
    """R4-2's one-pass scan (`evidence_lines`) against the per-code search it replaced, on generated notes built from the
    pieces that decide a match: codes and their neighbours, dots, underscores, the four non-ASCII letters `re.I` folds to
    ASCII ones, a non-ASCII digit, and every line break `splitlines` honours."""
    PIECES = ['R00', 'R00.0', 'r00.0', 'M25.532', 'M25.5320', '99213', '0001F', '\u017f12', 'S12', 'K21.9', '\u212a21.9',
              '\u0131a1', 'Ia1', '\u0130A1', '.', '..', '_', ' ', '\n', '\r\n', '\r', '\u2028', '\x1c', '\u00e9', '\u0663',
              '\u00df', 'A', '1', '9', 'x', ',', '-', 'Z', '(', '\u0301']
    CODES = ['R00', 'R00.0', 'M25.532', 'M25.5320', '99213', '0001F', 'S12', 'K21.9', 'IA1', 'A1Z', 'Z1A', 'X19', 'A11',
             'A00.0000', 'R00.0X', 'S12.1']

    def test_generated_notes_read_the_same(self):
        import random
        chance = random.Random(20260927)
        compared = found = 0
        for _trial in range(4000):
            notes = ''.join(chance.choice(self.PIECES) for _ in range(chance.randint(0, 40)))
            wanted = set(chance.sample(self.CODES, chance.randint(1, len(self.CODES))))
            expected = {code: line for code, line in searched_line_by_line(notes, wanted).items() if line is not None}
            scanned = {code: line for code, (_order, line) in coding_module.evidence_lines(notes, wanted).items()}
            self.assertEqual(scanned, expected, repr(notes))
            compared += 1; found += len(expected)
        self.assertGreater(found, 1000)                                  # (the control: the corpus does hold codes)

    def test_the_letters_re_folds_are_folded(self):
        notes = 'Seen: \u017f12, \u212a21.9 and \u0131a1.\nNot: S12x K21.9.1'
        expected = {'S12': 'Seen: \u017f12, \u212a21.9 and \u0131a1.', 'K21.9': 'Seen: \u017f12, \u212a21.9 and \u0131a1.',
                    'IA1': 'Seen: \u017f12, \u212a21.9 and \u0131a1.'}
        self.assertEqual(searched_line_by_line(notes, set(expected)), expected)          # (the control: the old reading)
        self.assertEqual({code: line for code, (_order, line) in coding_module.evidence_lines(notes, set(expected)).items()},
                         expected)

    def test_the_order_is_the_order_the_notes_document_them(self):
        notes = 'Seen for S12.\nThen R00.0 and M25.532, then S12 again.\nK21.9'
        scanned = coding_module.evidence_lines(notes, {'K21.9', 'M25.532', 'R00.0', 'S12'})
        self.assertEqual(sorted(scanned, key=lambda code: scanned[code][0]), ['S12', 'R00.0', 'M25.532', 'K21.9'])


@override_settings(**TEST_SETTINGS)
class AnEmptyFieldIsNotAClearedAnswer(OrdinaryDraft, TestCase):
    """Refutation round 4, R4-3: every entry of the draft was counted as a cleared answer, an empty field nobody decided
    included. The refuter's input: notes `Symptoms: No chest pain.` generate one supported answer and one `missing` empty
    field; a changed save then said "the answer draft (2 answers, none reviewed)" and audited answers_unreviewed_unedited: 2.
    Only an answer that carries text, or a decision (reviewed, accepted, left blank or edited), is cleared."""

    def test_the_refuters_draft_clears_one_answer(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, 'Symptoms: No chest pain.')
        self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        self.assertEqual(sorted((a['status'], a['text']) for a in encounter.answers.values()),
                         [('missing', ''), ('supported', 'No chest pain.')])                # (the control: one empty field)
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic.'})
        said = shown_messages(response)
        self.assertEqual((last_event('encounter.notes_saved', encounter).get('cleared'),
                          'the answer draft (1 answer, not reviewed).' in said, '2 answers' in said),
                         (cleared(unreviewed_unedited=1), True, False))

    def test_a_wm_answer_deliberately_cleared_is_a_preserved_and_counted_edit(self):
        # WM saves empty answers as missing while preserving who cleared them. This
        # differs from a never-answered missing field; generation may not replace it.
        untouched = Encounter(template_review={}, answers={'a': {'text': '', 'status': 'missing'}})
        cleared_answer = Encounter(template_review={}, answers={
            'a': {'text': '', 'status': 'missing', 'edited_by': 'synthetic-employee'}})
        self.assertFalse(views.clinician_decided(untouched))
        self.assertTrue(views.clinician_decided(cleared_answer))
        counts = views.review_state_counts(cleared_answer, codes=False)
        self.assertEqual(counts['answers_edited_not_accepted'], 1)
        self.assertEqual(counts['answers_with_clinician_review'], 0)
        self.assertEqual(sum(counts[state] for state in views.ANSWER_STATES), 1)

    def test_each_counted_answer_carries_text_or_a_decision(self):
        """The five states stay disjoint and sum to the answers they count; an empty field is counted only once somebody
        decided something about it."""
        encounter = Encounter(template_review={}, answers={
            'empty': {'text': '', 'status': 'missing', 'reviewed': False}, 'spaces': {'text': ' ​ ', 'status': 'supported'},
            'conflict': {'text': '', 'status': 'conflict', 'suggestion': 'Synthetic'}, 'none': None, 'bare': {},
            'text': {'text': 'Synthetic.', 'status': 'supported'}, 'legacy': 'legacy',
            'empty_reviewed': {'text': '', 'status': 'missing', 'reviewed': True},
            'emptied': {'text': '', 'status': 'edited'}, 'blank': {'text': '', 'status': 'left_blank'},
            'accepted': {'text': 'Synthetic.', 'status': 'edited', 'accepted_suggestion': True}})
        counts = views.review_state_counts(encounter, codes=False)
        self.assertEqual({state: counts[state] for state in views.ANSWER_STATES},
                         {'answers_accepted_suggestion': 1, 'answers_left_blank': 1, 'answers_edited_not_accepted': 1,
                          'answers_reviewed_unedited': 1, 'answers_unreviewed_unedited': 2})
        self.assertEqual(counts['answers_with_clinician_review'], 1)
        # (and a draft of empty fields alone clears nothing the page warns of or the save names)
        empty = Encounter(template_review={}, answers={'a': {'text': '', 'status': 'missing'}, 'b': {'text': '', 'status': 'conflict'}})
        self.assertEqual(views.cleared_sentence(views.review_state_counts(empty, codes=False)), '')


@override_settings(**TEST_SETTINGS)
class TheSaveNamesAClinicianDecisions(OrdinaryDraft, TestCase):
    """Refutation round 4, R4-4: the sentence named only how many answers a clinician had reviewed, so an acceptance made
    without the review tick vanished from it. The refuter's input: a clinician accepts one suggestion without ticking
    reviewed and leaves the other blank; an employee saves changed notes — told "the answer draft (2 answers, 1 reviewed by
    a clinician)" while the audit recorded answers_accepted_suggestion: 1. The sentence now names accepted suggestions and
    decisions to leave blank, from the counts the audit records."""

    def test_the_refuters_acceptance_and_blank_decision_are_named(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, 'Fictional software test only.\nSymptoms: no chest pain\nExamination: normal gait')
        self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        first, second = sorted(encounter.answers)
        self.assertTrue(encounter.answers[first].get('suggestion'))                  # (the control: an offer to accept)
        self.post(f'/encounters/{encounter.pk}/save/', encounter, {
            'answer_' + first: '', 'accept_' + first: 'on',
            'answer_' + second: '', 'blank_' + second: 'on', 'blank_shown_' + second: '1'})
        self.assertEqual(sorted((a['status'], bool(a.get('accepted_suggestion')), a['reviewed']) for a in encounter.answers.values()),
                         [('edited', True, False), ('left_blank', False, True)])       # (the control: accepted, not ticked)
        self.client.force_login(self.member('guards-decisions-employee', 'employee'))
        response = self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic.'})
        self.assertEqual((last_event('encounter.notes_saved', encounter).get('cleared'), shown_messages(response).strip()),
                         (cleared(accepted_suggestion=1, left_blank=1, with_clinician_review=1),
                          'Notes saved. Cleared, and recorded under your name: the answer draft (2 answers: 1 accepted suggestion '
                          'and 1 decision to leave blank; 1 reviewed by a clinician). Generate and review a new answer draft.'))

    def test_decisions_are_named_within_the_answers_they_are_part_of(self):
        counts = dict.fromkeys(views.review_state_counts(Encounter(answers={}, template_review={}), codes=False), 0)
        said = lambda **states: views.cleared_sentence({**counts, **{'answers_' + key: value for key, value in states.items()}})
        self.assertEqual(said(accepted_suggestion=1),
                         'Cleared, and recorded under your name: the answer draft (1 answer: 1 accepted suggestion; not reviewed). ')
        self.assertEqual(said(accepted_suggestion=1, edited_not_accepted=1),
                         'Cleared, and recorded under your name: the answer draft (2 answers, including 1 accepted suggestion; '
                         'none reviewed). ')
        self.assertEqual(said(left_blank=2, unreviewed_unedited=3, with_clinician_review=2),
                         'Cleared, and recorded under your name: the answer draft (5 answers, including 2 decisions to leave '
                         'blank; 2 reviewed by a clinician). ')
        self.assertEqual(said(accepted_suggestion=2, left_blank=1, with_clinician_review=3),
                         'Cleared, and recorded under your name: the answer draft (3 answers: 2 accepted suggestions and 1 '
                         'decision to leave blank; 3 reviewed by a clinician). ')
        self.assertEqual(said(reviewed_unedited=2, with_clinician_review=2),    # (no decision: the sentence as before)
                         'Cleared, and recorded under your name: the answer draft (2 answers, 2 reviewed by a clinician). ')


@override_settings(**TEST_SETTINGS)
class AnAcceptedCodeIsNotTakenOver(OrdinaryDraft, TestCase):
    """Refutation round 4, R4-6 (pre-existing): accepting a code does not renumber the revision, so a Coding tab opened
    before clinician A accepted it still posts the current revision. Clinician B's Accept from that page answered 302,
    re-stamped accepted_by as B and audited a second coding.accept. It is now refused, 409, naming who accepted it and when
    (their email, as the page shows it), with no audit row — chosen over an idempotent no-op, which would have answered B as
    if B's own acceptance had been recorded."""
    CODED = OrdinaryDraft.NOTES + '\nAssessment: documented as R00.0.'

    def test_a_stale_accept_from_a_second_clinician_is_refused_and_keeps_the_first(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        synthetic_code()
        self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        offer = CodeSuggestion.objects.get(encounter=encounter)
        second = Client(); second.force_login(self.member('guards-second-clinician', 'clinician'))
        url, fields = page_form(second.get(f'/encounters/{encounter.pk}/?tab=coding'), f'/coding/{offer.pk}/accept/')
        self.assertEqual(self.client.post(url, fields).status_code, 302)                 # (A accepts; B's page is older)
        offer.refresh_from_db()
        first = (offer.accepted_by_id, offer.accepted_at)
        self.assertEqual(first[0], self.user.pk)                                         # (the control)
        refused = second.post(url, fields)
        text = html.unescape(refused.content.decode())
        when = timezone.localtime(first[1]).strftime('%Y-%m-%d %H:%M %Z')
        offer.refresh_from_db()
        self.assertEqual((refused.status_code, f'already accepted by {self.user.email}, at {when}.' in text,
                          'Nothing was accepted.' in text, (offer.accepted_by_id, offer.accepted_at),
                          AuditEvent.objects.filter(action='coding.accept').count()),
                         (409, True, True, first, 1))


@override_settings(**TEST_SETTINGS)
class CodeRefusalsSayWhatHappened(OrdinaryDraft, TestCase):
    """Refutation round 4, R4-7: two 409 texts were false. A code id from another encounter, posted at a stale revision of
    this one, was told "its source notes were changed" — they were not, and the code was never on this document: it is a
    404, as it already was at the current revision. A page rendered before this release posts no revision and was told
    "This document changed after you opened it" even when nothing had changed: it is told the page is out of date."""
    CODED = OrdinaryDraft.NOTES + '\nAssessment: documented as R00.0.'

    def offered(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        synthetic_code()
        self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        return encounter, CodeSuggestion.objects.get(encounter=encounter)

    def test_never_existing_code_after_notes_save_has_no_invented_history(self):
        encounter, _offer = self.offered()
        stale = encounter.revision
        self.post(f'/encounters/{encounter.pk}/notes/', encounter,
                  {'notes': self.CODED + '\nPlan: synthetic.'})
        code = '00000000-0000-4000-8000-000000000000'
        self.assertFalse(CodeSuggestion.objects.filter(pk=code).exists())
        before = AuditEvent.objects.filter(action='coding.accept').count()
        refused = self.client.post(f'/encounters/{encounter.pk}/coding/{code}/accept/', {'revision': stale})
        self.assertContains(refused, 'This code suggestion is unavailable.', status_code=409)
        self.assertNotContains(refused, 'no longer on this document', status_code=409)
        self.assertNotContains(refused, 'its source notes', status_code=409)
        self.assertEqual(AuditEvent.objects.filter(action='coding.accept').count(), before)

    def test_a_code_never_on_this_document_is_not_found_at_a_stale_revision(self):
        encounter, offer = self.offered()
        elsewhere = Encounter.objects.create(department=self.department, patient=self.patient, created_by=self.user,
                                             template_version=encounter.template_version, notes=self.CODED,
                                             service_date=encounter.service_date)
        foreign = CodeSuggestion.objects.create(encounter=elsewhere, terminology=offer.terminology, evidence=offer.evidence,
                                                explanation='Synthetic documented code')
        stale = encounter.revision
        Encounter.objects.filter(pk=encounter.pk).update(revision=stale + 1)    # (as an answers save renumbers it: notes kept)
        answered = [self.client.post(f'/encounters/{encounter.pk}/coding/{code}/accept/', {'revision': stale}).status_code
                    for code in (foreign.pk, '00000000-0000-4000-8000-000000000000')]
        foreign.refresh_from_db()
        self.assertEqual((answered, foreign.accepted_by_id), ([404, 404], None))

    def test_a_code_a_notes_save_cleared_is_still_said_to_be_gone(self):
        """The control for the text kept: after a changed notes save the code is gone, and says so."""
        encounter, offer = self.offered()
        stale = encounter.revision
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': self.CODED + '\nPlan: synthetic.'})
        refused = self.client.post(f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/', {'revision': stale})
        self.assertContains(refused, 'This code suggestion is unavailable.', status_code=409)

    def test_a_page_from_before_this_release_is_told_it_is_out_of_date(self):
        encounter, offer = self.offered()
        suggested = AuditEvent.objects.filter(action='coding.suggest').count()
        said = []
        for url, nothing in ((f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/', 'Nothing was accepted.'),
                             (f'/encounters/{encounter.pk}/coding/', 'Nothing was suggested.')):
            refused = self.client.post(url)                                        # (no revision, as an old page posts)
            text = html.unescape(refused.content.decode())
            said.append((refused.status_code, 'This page is out of date' in text, 'This document changed' in text, nothing in text))
        offer.refresh_from_db()
        self.assertEqual((said, offer.accepted_by_id, AuditEvent.objects.filter(action='coding.suggest').count()),
                         ([(409, True, False, True)] * 2, None, suggested))

    def test_the_notes_warning_names_only_what_a_changed_save_would_clear(self):
        """R4-7's last part: the page's warning named the answer draft, every review decision and accepted codes whatever
        was there. It now names the parts, from the counts the save audits and states."""
        encounter, _keys = self.reviewed_draft()
        self.assertEqual(' '.join(notes_help(self.client.get(f'/encounters/{encounter.pk}/')).split()),
                         'Include only documented facts. Saving changed notes clears the answer draft (2 answers, 2 reviewed '
                         'by a clinician), whoever saves them; the clearing is recorded under your name. Saving them '
                         'unchanged clears nothing.')
        self.accepted_code(encounter)
        self.post(f'/encounters/{encounter.pk}/clear-review/', encounter, {'confirm_clear': 'on'})
        job = self.transcript_awaiting_review(encounter)
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertIn('Saving changed notes clears 1 accepted code, whoever saves them;', ' '.join(notes_help(page).split()))
        self.assertIn('Saving clears 1 accepted code; the clearing is recorded under your name.',
                      ' '.join(transcript_help(page, job).split()))
        for claim in ('answer draft', 'review decision'):
            self.assertNotIn(claim, notes_help(page) + transcript_help(page, job))


@override_settings(**TEST_SETTINGS)
class RoundFourMutantPins(OrdinaryDraft, TestCase):
    """Refutation round 4, R4-5: two mutants of round 3 survived. M2 — the page's warning read without
    answers_unreviewed_unedited — showed no warning on a fresh draft while the save named the draft; M1 — Suggest codes
    accepting a request that posts no revision — wrote from a page that cannot say which notes it showed."""
    CODED = OrdinaryDraft.NOTES + '\nAssessment: documented as R00.0.'

    def test_m2_a_fresh_draft_is_warned_about_as_the_save_then_names_it(self):
        encounter = self.drafted()
        self.assertFalse(any(a['reviewed'] or a['status'] == 'edited' for a in encounter.answers.values()))   # (the control)
        warned = ' '.join(notes_help(self.client.get(f'/encounters/{encounter.pk}/')).split())
        said = shown_messages(self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes + '\nPlan: synthetic.'}))
        part = 'the answer draft (2 answers, none reviewed)'
        self.assertEqual((f'Saving changed notes clears {part}, whoever saves them;' in warned,
                          f'Cleared, and recorded under your name: {part}.' in said), (True, True))

    def test_m1_suggest_codes_writes_nothing_for_a_page_that_posts_no_revision(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        synthetic_code()
        refused = self.client.post(f'/encounters/{encounter.pk}/coding/')
        self.assertEqual((refused.status_code, CodeSuggestion.objects.filter(encounter=encounter).count(),
                          AuditEvent.objects.filter(action='coding.suggest').count()), (409, 0, 0))
        # (the control: the same page with its revision suggests the documented code)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision}).status_code, 302)
        self.assertEqual(CodeSuggestion.objects.filter(encounter=encounter).count(), 1)

    def test_a_code_from_another_document_is_not_found_after_this_documents_notes_changed(self):
        """R4-7's discriminator, pinned: a code that exists elsewhere was never on this document, even when this document's
        notes did change after the page — not "no longer on this document"."""
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        code = synthetic_code()
        elsewhere = Encounter.objects.create(department=self.department, patient=self.patient, created_by=self.user,
                                             template_version=version, notes=self.CODED, service_date=encounter.service_date)
        foreign = CodeSuggestion.objects.create(encounter=elsewhere, terminology=code, evidence='No chest pain.',
                                                explanation='Synthetic documented code')
        stale = encounter.revision
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': self.CODED + '\nPlan: synthetic.'})
        self.assertGreater(encounter.revision, stale)                                   # (the control: the notes changed)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/{foreign.pk}/accept/', {'revision': stale}).status_code, 404)

    def test_a_notes_change_before_the_page_is_not_a_change_since_it(self):
        """notes_changed_since compares with the page's revision: a notes save the page already showed does not make an
        unknown code "no longer on this document"."""
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': self.CODED + '\nPlan: synthetic.'})
        shown = encounter.revision                                                      # (the page opens after that save)
        Encounter.objects.filter(pk=encounter.pk).update(revision=shown + 1)            # (an answers save renumbers it)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/coding/00000000-0000-4000-8000-000000000000/accept/',
                                          {'revision': shown}).status_code, 404)

    def test_suggestions_are_written_only_from_the_notes_they_were_read_from(self):
        """The write re-checks the notes as well as the revision: notes changed under an unchanged revision (no writer does
        this today; every notes change renumbers) are not written from."""
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        synthetic_code()
        real = coding_module.applicable_releases

        def notes_change_meanwhile(e):
            Encounter.objects.filter(pk=e.pk).update(notes=self.NOTES)                 # (the revision is left as it was)
            return real(e)
        with patch.object(coding_module, 'applicable_releases', notes_change_meanwhile):
            refused = self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        self.assertEqual((refused.status_code, CodeSuggestion.objects.filter(encounter=encounter).count(),
                          AuditEvent.objects.filter(action='coding.suggest').count()), (409, 0, 0))

    def test_suggestions_are_written_only_while_the_writer_is_still_a_member(self):
        """The write re-checks membership under the lock: an account suspended while the plan is read (its department
        membership still active, so the encounter is still in scope) writes nothing."""
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        synthetic_code()
        employee = self.member('guards-withdrawn-employee', 'employee')
        self.client.force_login(employee)
        real = coding_module.applicable_releases

        def access_withdrawn_meanwhile(e):
            User.objects.filter(pk=employee.pk).update(is_active=False)
            return real(e)
        self.client.raise_request_exception = False
        with patch.object(coding_module, 'applicable_releases', access_withdrawn_meanwhile):
            refused = self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        self.assertEqual((refused.status_code, CodeSuggestion.objects.filter(encounter=encounter).count(),
                          AuditEvent.objects.filter(action='coding.suggest').count()), (403, 0, 0))

    def test_a_code_an_unreviewed_transcript_cleared_is_said_to_be_gone(self):
        """A transcript of an earlier release, appended to the notes unreviewed by the worker, records the revision it made
        (core/jobs.py), so a code it cleared, accepted from a page opened before it, is "no longer on this document"."""
        from core.generation import configuration
        from core.jobs import enqueue
        from core.tests.audio_fixtures import wav_bytes
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.CODED)
        synthetic_code()
        self.client.post(f'/encounters/{encounter.pk}/coding/', {'revision': encounter.revision})
        offer = CodeSuggestion.objects.get(encounter=encounter)
        stale = encounter.revision
        audio = private_path('audio/synthetic-guards.wav'); audio.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        audio.write_bytes(wav_bytes(tag='guards')); audio.chmod(0o600)
        enqueue(encounter, self.user, kind='transcription', input_path='audio/synthetic-guards.wav',
                config={**configuration(), 'voice_rate_second': '0', 'voice_max_cost': '0'})   # (no transcript review asked)
        transcript = ('SYNTHETIC appended words', Decimal('0'), {'duration_seconds': '1'}, {'usd_per_minute': '0'},
                      'synthetic-transcription', '', True)
        with patch('core.jobs.transcribe', return_value=transcript):
            self.assertTrue(run_one())
        encounter.refresh_from_db()
        self.assertEqual((encounter.revision, CodeSuggestion.objects.filter(encounter=encounter).count()), (stale + 1, 0))
        refused = self.client.post(f'/encounters/{encounter.pk}/coding/{offer.pk}/accept/', {'revision': stale})
        self.assertContains(refused, 'This code suggestion is unavailable.', status_code=409)
