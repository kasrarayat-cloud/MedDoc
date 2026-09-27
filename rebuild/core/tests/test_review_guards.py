"""Review guards ported from the draft branch feat/wm-narrative (4396c801): its flag-independent fixes only.

Offline and synthetic. Ordinary forms generate in fixture mode. The qualified Word form's resolver is replaced by
`SyntheticResolver`, which resolves the way the engine does (the chosen wording, its answer tokens, and the signer —
the finalizing clinician once finalized, else the viewer); no Word runtime and no provider is involved.
"""
import hashlib
import html
from html.parser import HTMLParser
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core import wm_review
from core.jobs import run_one
from core.models import AuditEvent, Job, Membership, TemplateVersion, User
from core.wm_review import BACKEND, ORIGINAL_SHA256
from .test_security import SyntheticFixture
from .test_workflow import TEST_SETTINGS, DocumentWorkflow

REFUSED = 'a new draft would replace them. Nothing was sent or charged.'


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
        return {name: html.unescape(value).lstrip('\n') for name, value in form.values.items()}


# ── ordinary forms ────────────────────────────────────────────────────────────────────────────────────────────────
@override_settings(**TEST_SETTINGS)
class GenerationRefusedOverReviewOnOrdinaryForms(TestCase):
    """A generation replaces every answer and review decision (`jobs.py` adoption). The page offers it only before any
    answer exists, but the server queued it for any POST carrying the current revision."""
    # DocumentWorkflow's fixture and helpers, without re-running its own tests.
    setUp, make_docx, upload = DocumentWorkflow.setUp, DocumentWorkflow.make_docx, DocumentWorkflow.upload
    create_encounter, generate = DocumentWorkflow.create_encounter, DocumentWorkflow.generate
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
        self.assertContains(response, 'save the source notes again')
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

    def test_the_way_forward_is_saving_the_notes_which_clears_the_draft(self):
        encounter = self.drafted()
        keys = sorted(encounter.answers)
        self.post(f'/encounters/{encounter.pk}/save/', encounter,
                  {**{'answer_' + key: encounter.answers[key]['text'] for key in keys},
                   **{'reviewed_' + key: 'on' for key in keys}})
        self.assertContains(self.post(f'/encounters/{encounter.pk}/generate/', encounter), REFUSED)   # (the control)
        self.post(f'/encounters/{encounter.pk}/notes/', encounter, {'notes': encounter.notes})
        self.assertEqual((encounter.answers, encounter.template_review), ({}, {}))
        self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        self.assertEqual(Job.objects.filter(encounter=encounter, kind='generation', state='succeeded').count(), 2)
        self.assertFalse(any(answer['reviewed'] for answer in encounter.answers.values()))

    def test_a_draft_nobody_has_decided_is_not_refused(self):
        """The refusal reads decisions, not the presence of answers: an untouched draft reaches the existing
        same-revision reuse (nothing new is requested either way)."""
        encounter = self.drafted()
        response = self.post(f'/encounters/{encounter.pk}/generate/', encounter)
        self.assertNotContains(response, REFUSED)
        self.assertContains(response, 'No new request was made')


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
    """`views.wm_resolve` as the engine answers it: the chosen wordings, filled from the answers, signed by the finalizing
    clinician once finalized and otherwise by the viewer (`trusted_context.signer_name`)."""
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
