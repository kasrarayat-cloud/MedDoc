"""Render-only UI checks using constructed synthetic state; no DB/provider calls."""
from copy import deepcopy
from datetime import date, datetime, timezone
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse
from lxml import html

from core.coding_service import CONTEXT_DEFAULTS


class CodingReviewPresentationTests(SimpleTestCase):
    def setUp(self):
        self.encounter = SimpleNamespace(
            pk='7752b8fa-dbfb-4e03-a6c3-3af2a581feef', status='finalized',
            template_version=SimpleNamespace(template=SimpleNamespace(format='docx')))
        self.decision = SimpleNamespace(
            user=SimpleNamespace(email='reviewer@synthetic.invalid'),
            approved_at=datetime(2026, 10, 17, 2, 24, tzinfo=timezone.utc),
            facts_confirmed=True)
        self.facts = [dict(key=key, label=label, value=value,
                           quote=f'Exact retained note quotation {index}.',
                           start=index * 40, end=index * 40 + 32, source='Saved original note')
                      for index, (key, label, value) in enumerate([
                          ('setting', 'Setting', 'outpatient_office'),
                          ('patient_status', 'Patient status', 'established'),
                          ('time_minutes', 'Total physician minutes', 24),
                          ('time_same_day', 'Time on date of service', True),
                          ('time_qualified_clinician', 'Physician time', True),
                          ('time_excludes_staff', 'Staff time excluded', True),
                          ('time_excludes_separately_reported', 'Separately reported services excluded', True),
                          ('em_basis', 'Selection basis', 'time'),
                      ])]
        self.review = dict(
            available=True, state='accepted', decision=self.decision, can_decide=False,
            code='99213', identifier='selected:3', facts=self.facts,
            display_token='output-display-token', source_summary='Retained dated-source assessment.',
            permission_summary='Bounded internal-fictional API-output permission.',
            provider_citation_adequacy={'status': 'insufficient_for_time_review'},
            review_execution='agent_executed_synthetic',
            sources=[dict(url='https://www.cms.gov/reference', title='Dated CMS reference', edition='2026')])
        self.coding = dict(
            version='saved-view', pending=False, current=True, state='approved',
            state_label='Selections approved; CPT number accepted with description withheld',
            can_edit=True, can_review=False, can_request=False, corti=True,
            service_date=date(2026, 10, 16), decision=self.decision,
            summary=dict(approved=3, awaiting_review=0, unresolved_questions=2, not_included=2),
            run=SimpleNamespace(pk='b8afb59d-5647-475d-ab90-9aa81025f7c6', selection_revision=3),
            display_token='context-display-token', context_derived=True,
            context={**CONTEXT_DEFAULTS, 'setting': 'outpatient_office',
                     'patient_status': 'established', 'em_basis': 'time'},
            mdm_rows=[dict(key=key, label=label, value='unknown', evidence='')
                      for key, label in [('mdm_problems', 'Problems addressed'),
                                         ('mdm_data', 'Data reviewed'),
                                         ('mdm_risk', 'Risk of management')]],
            levels=['unknown', 'straightforward', 'low', 'moderate', 'high'],
            suggestions=[dict(id='selected:3', code='99213', system='CPT',
                              provider_display='Original defective provider text',
                              semantic_support={'provider_citation_adequacy': {'status': 'insufficient_for_time_review'}})],
            questions=[dict(id='selected:3', system='CPT', question='Separate review below.'),
                       dict(id='selected:2', system='HCPCS Level II', question='Quality-measure eligibility remains unresolved.')],
            output_review=self.review)

    def render(self):
        before = deepcopy((self.review, self.coding))
        rendered = render_to_string('coding_panel.html', {
            'encounter': self.encounter, 'coding': self.coding, 'csrf_token': 'synthetic-csrf-token'})
        # Templates must only display the supplied state.
        self.assertEqual((self.review, self.coding), before)
        return html.fromstring(rendered)

    def output(self, document):
        sections = document.xpath('//*[@data-coding-output-review]')
        self.assertEqual(len(sections), 1)
        return sections[0]

    def assert_facts(self, section):
        rows = section.xpath('.//*[@data-output-note-fact]')
        self.assertEqual(len(rows), 8)
        for row, fact in zip(rows, self.facts):
            self.assertEqual(row.xpath('.//blockquote')[0].text_content(), fact['quote'])
            self.assertIn(f"{fact['label']}: {fact['value']}", row.text_content())
            self.assertIn(f"characters {fact['start']}–{fact['end']}", row.text_content())

    def test_accepted_decision_is_read_only_with_saved_facts_and_reviewer_first(self):
        document = self.render(); section = self.output(document)
        self.assertEqual(section.find('h3').text_content(), 'Accepted CPT 99213')
        receipt = section.xpath('./p[@data-output-persisted-decision]')[0]
        self.assertIn('Accepted by reviewer@synthetic.invalid', receipt.text_content())
        self.assertIn('17 Oct 2026, 02:24', receipt.text_content())
        self.assertLess(section.index(receipt), section.index(section.find('h4')))
        self.assertIn('8 read-only facts are retained with the saved acceptance', section.text_content())
        self.assertFalse(section.xpath('.//form | .//input | .//button'))
        self.assert_facts(section)
        self.assertLess(list(document.iter()).index(section), list(document.iter()).index(document.xpath('//*[@data-coding-item]')[0]))

    def test_rejected_decision_retains_facts_without_implying_confirmation_or_acceptance(self):
        self.review.update(state='rejected')
        self.decision.facts_confirmed = False
        section = self.output(self.render())
        self.assertEqual(section.find('h3').text_content(), 'Rejected CPT 99213')
        self.assertIn('Rejected by reviewer@synthetic.invalid', section.text_content())
        self.assertIn('saved rejection excludes the code', section.text_content())
        self.assertIn('They do not approve this code', section.text_content())
        self.assertNotIn('saved acceptance', section.text_content())
        self.assertNotIn('Confirm that', section.text_content())
        self.assertFalse(section.xpath('.//form | .//input | .//button'))
        self.assert_facts(section)

    def test_pending_review_remains_after_cards_with_unchecked_required_confirmation(self):
        self.review.update(state='pending', decision=None, can_decide=True)
        document = self.render(); section = self.output(document)
        self.assertEqual(section.find('h3').text_content(), 'Review CPT 99213 for this fictional note')
        self.assertGreater(list(document.iter()).index(section), list(document.iter()).index(document.xpath('//*[@data-coding-item]')[0]))
        form = section.xpath('.//form[@data-coding-form="output-decision"]')[0]
        self.assertEqual(form.get('action'), reverse('coding_output_decision', args=[self.encounter.pk, self.coding['run'].pk]))
        confirm = form.xpath('.//input[@name="confirm_note_facts"]')[0]
        self.assertIn('required', confirm.attrib); self.assertNotIn('checked', confirm.attrib)
        self.assertEqual(form.xpath('.//input[@name="output_display_token"]/@value'), ['output-display-token'])
        self.assertEqual(form.xpath('.//input[@name="csrfmiddlewaretoken"]/@value'), ['synthetic-csrf-token'])
        self.assertEqual(form.xpath('.//button/@value'), ['accepted', 'rejected'])
        self.assertFalse(section.xpath('.//*[@data-output-persisted-decision]'))
        self.assertIn('no confirmation has been filled in for you', section.text_content())

    def test_completed_state_never_offers_repeat_confirmation_even_if_flag_is_true(self):
        for state in ('accepted', 'rejected'):
            with self.subTest(state=state):
                self.review.update(state=state, can_decide=True)
                self.assertFalse(self.output(self.render()).xpath('.//form'))

    def test_context_editor_is_native_closed_and_retains_every_guarded_form_field(self):
        document = self.render()
        editor = document.xpath('//details[@data-coding-context-editor]')[0]
        self.assertNotIn('open', editor.attrib)
        summary = editor.find('summary')
        self.assertEqual(summary.get('id'), 'coding-context-toggle')
        self.assertEqual(summary.text_content(), 'Edit coding context')
        form = editor.xpath('./form[@data-coding-form="context"]')[0]
        self.assertEqual(form.get('method'), 'post')
        self.assertEqual(form.get('action'), reverse('coding_context', args=[self.encounter.pk]))
        fields = form.xpath('.//*[@name]/@name')
        self.assertCountEqual(fields, [*CONTEXT_DEFAULTS, 'csrfmiddlewaretoken', 'display_token'])
        self.assertEqual(form.xpath('.//input[@name="display_token"]/@value'), ['context-display-token'])
        self.assertEqual(form.xpath('.//input[@name="csrfmiddlewaretoken"]/@value'), ['synthetic-csrf-token'])
        self.assertTrue(document.xpath('//*[@data-coding-dirty and not(ancestor::details)]'))
        self.assertTrue(document.xpath('//a[@data-export-with-codes and not(ancestor::details)]'))

    def test_blank_context_time_and_checks_never_borrow_the_accepted_note_facts(self):
        document = self.render()
        context = document.xpath('//*[@data-coding-context-summary]')[0].text_content()
        self.assertIn('Not recorded in coding context', context)
        self.assertNotIn('24', context)
        self.assertEqual(document.xpath('//input[@name="time_minutes"]/@value'), [''])
        self.assertFalse(document.xpath('//form[@data-coding-form="context"]//input[@checked]'))
        self.assertIn('saved separately from these coding-context fields', document.text_content())

    def test_nonblank_saved_context_time_is_displayed_without_changing_review_facts(self):
        self.coding['context'].update(time_minutes='35', time_same_day=True)
        document = self.render()
        context = document.xpath('//*[@data-coding-context-summary]')[0].text_content()
        self.assertIn('35 minutes', context); self.assertNotIn('24', context)
        self.assertEqual(document.xpath('//input[@name="time_minutes"]/@value'), ['35'])
        self.assertTrue(document.xpath('//input[@name="time_same_day" and @checked]'))
        self.assertIn('Total physician minutes: 24', self.output(document).text_content())

    def test_read_only_role_sees_context_and_saved_review_without_edit_form(self):
        self.coding['can_edit'] = False
        document = self.render()
        self.assertFalse(document.xpath('//*[@data-coding-context-editor]'))
        self.assertTrue(document.xpath('//*[@data-coding-context-summary]'))
        self.assert_facts(self.output(document))

    def test_mdm_and_unknown_context_summaries_are_not_fabricated_as_time(self):
        self.coding['context']['em_basis'] = 'mdm'
        self.coding['mdm_rows'][0]['value'] = 'low'
        context = self.render().xpath('//*[@data-coding-context-summary]')[0].text_content()
        self.assertIn('Medical decision making', context)
        self.assertIn('Problems addressed: Low', context)
        self.assertNotIn('Context time:', context)
        self.coding['context'] = dict(CONTEXT_DEFAULTS)
        context = self.render().xpath('//*[@data-coding-context-summary]')[0].text_content()
        self.assertEqual(context.count('Not confirmed'), 3)
        self.assertNotIn('24', context)

    def test_completed_copy_removes_repeat_prompts_but_keeps_unresolved_restrictions(self):
        for state in ('accepted', 'rejected'):
            with self.subTest(state=state):
                self.review['state'] = state
                text = self.render().text_content()
                for prompt in ('Confirm that they support', 'no confirmation has been filled in',
                               'Time facts still require', 'Review the code and note evidence separately below',
                               'Separate review below.', 'when available below'):
                    self.assertNotIn(prompt, text)
                for restriction in ('upstream terminology version remain unresolved',
                                    'Quality-measure eligibility remains unresolved',
                                    'Provider citations are insufficient',
                                    'do not represent human clinical review',
                                    'not permission to import an independent CPT catalogue'):
                    self.assertIn(restriction, text)

    def test_unavailable_stale_review_does_not_show_completed_approval_or_facts(self):
        self.coding.update(stale=True, current=False,
                           output_review={'available': False, 'reason': 'Saved source binding changed.'})
        document = self.render()
        self.assertFalse(document.xpath('//*[@data-coding-output-review]'))
        self.assertIn('Saved source binding changed.', document.text_content())
        self.assertIn('cannot be approved as current', document.text_content())

    def test_saved_facts_and_reviewer_are_escaped_as_text(self):
        self.decision.user.email = '<script>reviewer</script>'
        self.facts[0]['quote'] = '<img src=x onerror=alert(1)>'
        section = self.output(self.render())
        self.assertFalse(section.xpath('.//script | .//img'))
        self.assertIn(self.facts[0]['quote'], section.text_content())
