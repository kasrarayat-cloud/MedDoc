"""Option C acceptance, run against the DEPLOYED bytes with a synthetic database.

⚠️ NON-GENERATIVE BY CONSTRUCTION. `AI_MODE=fixture` produces the suggestion from the note itself;
no provider is contacted and no allowance is spent. Producing a suggestion on the LIVE service
would require a real provider call, which is not authorized — so the suggestion half is
demonstrated here against the exact installed code, and the authenticated walk on the running
release covers create/save/reopen/review/finalize/export without generation.
"""
from io import BytesIO
from zipfile import ZipFile

from django.test import TestCase
from docx import Document

from core.jobs import run_one
from core.models import AuditEvent
from core.tests.test_workflow import DocumentWorkflow


class OptionCAcceptance(DocumentWorkflow):
    # Current sentence evidence treats a harmless synthetic disclaimer as its
    # own complete unit. Exercise an actual unresolved source pointer instead.
    NOTES = ('See the findings listed in the report.\n'
             'Symptoms: no chest pain\n'
             'Examination: normal gait')
    SUGGESTION = 'no chest pain'
    TYPED = 'reports intermittent palpitations'

    def generated(self):
        _template, mapping = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(mapping, self.NOTES)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/generate/').status_code, 302)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        by_label = {f['label'].rstrip(':'): f['key'] for f in mapping.fields}
        self.key, self.other = by_label['Symptoms'], by_label['Examination']
        return encounter

    def save(self, encounter, **extra):
        encounter.refresh_from_db()
        payload = {'revision': encounter.revision,
                   'accept_' + self.other: 'on', 'answer_' + self.other: '',
                   'reviewed_' + self.other: 'on'}
        payload.update(extra)
        response = self.client.post(f'/encounters/{encounter.pk}/save/', payload)
        encounter.refresh_from_db()
        return response

    def section(self, encounter, label):
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        parts = [p.split('</section>')[0] for p in page.split('<section class="answer">')
                 if f'{label}</h3>' in p]
        self.assertEqual(len(parts), 1)
        return parts[0]

    def test_1_valid_suggestions_and_evidence_remain_reviewable(self):
        encounter = self.generated()
        answer = encounter.answers[self.key]
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer['text'], '')
        self.assertEqual(answer['suggestion'], self.SUGGESTION)
        self.assertEqual(answer['evidence'],
                         [{'quote': encounter.notes, 'start': 0, 'end': len(encounter.notes)}],
                         'the governing context must stay attached to the answer')
        entry = answer['suggestion_evidence'][0]
        self.assertEqual(encounter.notes[entry['start']:entry['end']], entry['quote'])
        section = self.section(encounter, 'Symptoms')
        self.assertIn('Suggested answer', section)
        self.assertIn(self.SUGGESTION, section)
        self.assertIn(f'name="accept_{self.key}"', section)
        self.assertNotIn(f'>{self.SUGGESTION}</textarea>', section,
                         'a prefilled box would let an ordinary save accept it')

    def test_2_explicit_acceptance_survives_save_and_reopen(self):
        encounter = self.generated()
        self.save(encounter, **{'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                'reviewed_' + self.key: 'on'})
        self.assertTrue(encounter.answers[self.key]['accepted_suggestion'])
        self.assertEqual(encounter.answers[self.key]['text'], self.SUGGESTION)
        # reopen, then save again exactly as the page renders it — no accept box exists now
        for _ in range(3):
            self.client.get(f'/encounters/{encounter.pk}/')
            self.save(encounter, **{'answer_' + self.key: self.SUGGESTION,
                                    'reviewed_' + self.key: 'on'})
            self.assertTrue(encounter.answers[self.key]['accepted_suggestion'],
                            'an ordinary re-save revoked a decision nobody revoked')
        self.assertEqual(encounter.answers[self.key]['accepted_by'], str(self.user.pk))

    def test_3_required_review_remains_enforced(self):
        """⚠️ MY FIRST EXPECTATION HERE WAS WRONG, AND THE DIFFERENCE MATTERS.

        I asserted that an undecided suggestion can never finalize. It can, by one route: a
        clinician who TYPES an answer and then CLEARS it moves `status` from `conflict` to
        `edited`, because the saved value differs from the previous one. Ticking review then
        finalizes with an explicitly empty field.

        That is not a hole — it is the general path's long-standing "reviewed empty field is
        explicit missing information" behaviour, and it is a decision the clinician made. The
        safety question is therefore not whether it finalizes but WHAT REACHES THE EXPORT, which
        `test_4` answers. What must hold here is that review is genuinely required and that an
        UNTOUCHED conflict cannot slip through.
        """
        encounter = self.generated()
        # 1. an untouched conflict cannot finalize, reviewed or not
        self.save(encounter, **{'answer_' + self.key: '', 'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['status'], 'conflict')
        self.client.post(f'/encounters/{encounter.pk}/finalize/',
                         {'revision': encounter.revision, 'reviewed': 'on'})
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized',
                            'an untouched conflict must not finalize')
        self.assertEqual(self.client.get(f'/encounters/{encounter.pk}/export/').status_code, 404)

        # 2. review is genuinely required: an answer without it is refused
        self.save(encounter, **{'answer_' + self.key: self.TYPED})
        self.assertFalse(encounter.answers[self.key]['reviewed'])
        self.client.post(f'/encounters/{encounter.pk}/finalize/',
                         {'revision': encounter.revision, 'reviewed': 'on'})
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized',
                            'a field the clinician never reviewed must not finalize')

    def test_3b_an_explicitly_emptied_field_exports_no_suggestion(self):
        """The route above, followed through to the only thing that matters clinically."""
        encounter = self.generated()
        self.save(encounter, **{'answer_' + self.key: self.TYPED, 'reviewed_' + self.key: 'on'})
        self.save(encounter, **{'answer_' + self.key: '', 'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['text'], '')
        self.assertFalse(encounter.answers[self.key]['accepted_suggestion'])
        exported = self.finalize(encounter)
        with ZipFile(BytesIO(exported)) as archive:
            blob = b''.join(archive.read(n) for n in archive.namelist())
        self.assertNotIn(self.SUGGESTION.encode(), blob,
                         'a rejected suggestion reached the export of an emptied field')
        self.assertNotIn(self.TYPED.encode(), blob, 'the cleared text reached the export')

    def test_4_unaccepted_suggestions_cannot_enter_finalized_exports(self):
        encounter = self.generated()
        self.save(encounter, **{'answer_' + self.key: self.TYPED, 'reviewed_' + self.key: 'on'})
        self.assertEqual(encounter.answers[self.key]['suggestion'], self.SUGGESTION,
                         'the record of what was read is preserved')
        self.assertFalse(encounter.answers[self.key]['accepted_suggestion'])
        exported = self.finalize(encounter)
        self.assertEqual(Document(BytesIO(exported)).paragraphs[0].text, f'Symptoms: {self.TYPED}')
        with ZipFile(BytesIO(exported)) as archive:
            blob = b''.join(archive.read(n) for n in archive.namelist())
        self.assertIn(self.TYPED.encode(), blob)
        self.assertNotIn(self.SUGGESTION.encode(), blob,
                         'an UNACCEPTED suggestion reached the finalized export')

    def test_5_the_control_that_makes_case_4_mean_something(self):
        """If the byte search could not find the string when it IS there, case 4 proves nothing."""
        encounter = self.generated()
        self.save(encounter, **{'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                'reviewed_' + self.key: 'on'})
        exported = self.finalize(encounter)
        with ZipFile(BytesIO(exported)) as archive:
            blob = b''.join(archive.read(n) for n in archive.namelist())
        self.assertIn(self.SUGGESTION.encode(), blob)
        self.assertEqual(Document(BytesIO(exported)).paragraphs[0].text,
                         f'Symptoms: {self.SUGGESTION}')

    def test_6_the_acceptance_is_attributed_and_audited(self):
        encounter = self.generated()
        before = set(AuditEvent.objects.filter(action='encounter.answers_saved')
                     .values_list('pk', flat=True))
        self.save(encounter, **{'answer_' + self.key: '', 'accept_' + self.key: 'on',
                                'reviewed_' + self.key: 'on'})
        row = AuditEvent.objects.filter(action='encounter.answers_saved').exclude(pk__in=before).get()
        self.assertIn(self.key, row.details['accepted_suggestions'])
        self.assertEqual(encounter.answers[self.key]['accepted_by'], str(self.user.pk))
