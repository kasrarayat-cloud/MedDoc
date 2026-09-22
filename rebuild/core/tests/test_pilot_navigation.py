"""Doctor-facing navigation and refusal messages found by the 2026-09-22 invited-pilot walkthrough.

1  "Use this form" (?template=<id>) preselects that form's CURRENT mapping version, and an
   out-of-scope or malformed id preselects nothing.
2  A refused finalization names the questions still needing a decision, in form order.
3  A refused document edit renders a page that says nothing was saved and links back to the
   document, instead of a bare text response with no way back — and it really saved nothing.
"""
import re

from django.utils import timezone

from core.models import Department, Encounter, Membership, Organization, Template, TemplateVersion, User
from core.tests.test_workflow import DocumentWorkflow


def selected_option(page, name):
    select = re.search(rf'<select name="{name}"[^>]*>(.*?)</select>', page, re.S).group(1)
    return re.findall(r'<option value="([^"]*)"[^>]*selected', select)


class PilotNavigation(DocumentWorkflow):
    NOTES = 'Fictional software test only.\nSymptoms: no chest pain\nExamination: normal gait'

    def test_use_this_form_preselects_the_current_mapping_version(self):
        template, first = self.upload(self.make_docx(), 'docx')
        labels = {f['key']: f['label'] for f in first.fields}
        response = self.client.post(f'/templates/{template.pk}/', {'mapping_version': first.pk, 'labels': __import__('json').dumps({k: v + ' (renamed)' for k, v in labels.items()})})
        self.assertEqual(response.status_code, 302)
        second = template.versions.get(number=2)
        page = self.client.get(f'/encounters/new/?template={template.pk}').content.decode()
        self.assertEqual(selected_option(page, 'template_version'), [str(second.pk)], 'the current version, never the superseded one')
        # The detail page and the library both link here with exactly this parameter.
        self.assertIn(f'/encounters/new/?template={template.pk}', self.client.get(f'/templates/{template.pk}/').content.decode())
        self.assertIn(f'/encounters/new/?template={template.pk}', self.client.get('/').content.decode())
        # Without the parameter nothing is chosen for the doctor.
        self.assertEqual(selected_option(self.client.get('/encounters/new/').content.decode(), 'template_version'), [''])

    def test_out_of_scope_or_malformed_template_preselects_nothing(self):
        other_user = User.objects.create_user(username='other-org', email='other@synthetic.invalid', verified_at=timezone.now())
        other_department = Department.objects.create(organization=Organization.objects.create(name='Synthetic other practice'), name='Other')
        Membership.objects.create(user=other_user, department=other_department, role='owner')
        foreign = Template.objects.create(department=other_department, name='Foreign form', format='docx', original_name='f.docx', original_path='x', sha256='0' * 64, created_by=other_user)
        TemplateVersion.objects.create(template=foreign, number=1, fields=[], created_by=other_user)
        for value in (str(foreign.pk), 'not-a-uuid', '00000000-0000-0000-0000-000000000000', ''):
            response = self.client.get('/encounters/new/', {'template': value})
            self.assertEqual(response.status_code, 200, value)
            self.assertEqual(selected_option(response.content.decode(), 'template_version'), [''], value)
            self.assertNotIn('Foreign form', response.content.decode())

    def test_finalize_refusal_names_the_unreviewed_questions(self):
        _template, mapping = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(mapping, self.NOTES)
        self.client.post(f'/encounters/{encounter.pk}/generate/')
        from core.jobs import run_one
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        response = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'reviewed': 'on', 'revision': encounter.revision}, follow=True)
        page = response.content.decode()
        self.assertIn('A clinician must review every field, including missing information. Not yet reviewed: Examination, Symptoms.', page, 'form order: the table cell precedes the paragraph blank')
        encounter.refresh_from_db()
        self.assertEqual(encounter.status, 'review')

    def test_finalize_refusal_names_the_conflicts_and_both_ways_to_resolve_them(self):
        _template, mapping = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(mapping, self.NOTES)
        self.client.post(f'/encounters/{encounter.pk}/generate/')
        from core.jobs import run_one
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        keys = {f['label'].rstrip(':'): f['key'] for f in mapping.fields}
        self.assertEqual({encounter.answers[k]['status'] for k in keys.values()}, {'conflict'})
        # Accept one suggestion, leave the other untouched, review both.
        payload = {'revision': encounter.revision, 'answer_' + keys['Symptoms']: '', 'accept_' + keys['Symptoms']: 'on'}
        payload.update({'reviewed_' + k: 'on' for k in keys.values()})
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
        encounter.refresh_from_db()
        page = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'reviewed': 'on', 'revision': encounter.revision}, follow=True).content.decode()
        self.assertIn('Resolve every conflict before finalizing', page)
        self.assertIn('Accept this suggestion', page)
        self.assertIn('Still in conflict: Examination.', page, 'only the unresolved one is named')
        encounter.refresh_from_db()
        self.assertEqual(encounter.status, 'review')

    def test_long_forms_are_bounded(self):
        from core.views import field_list
        self.assertEqual(field_list(['A', 'B']), 'A, B.')
        labels = [f'Q{i}' for i in range(30)]
        self.assertEqual(field_list(labels), ', '.join(labels[:12]) + ', and 18 more.')

    def test_stale_save_renders_a_way_back_and_saves_nothing(self):
        _template, mapping = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(mapping, 'Symptoms: No chest pain.\nExamination: Normal gait.')
        self.generate(encounter)
        stale = self.review(encounter)
        encounter.refresh_from_db()
        before = (encounter.answers, encounter.revision, encounter.status)
        response = self.client.post(f'/encounters/{encounter.pk}/save/', {**stale, 'answer_' + mapping.fields[0]['key']: 'Stale concurrent edit'})
        self.assertEqual(response.status_code, 409)
        page = response.content.decode()
        self.assertIn('Nothing was saved.', page)
        self.assertIn('changed after you opened it', page)
        self.assertIn(f'href="/encounters/{encounter.pk}/"', page)
        self.assertNotIn('Stale concurrent edit', page)
        encounter.refresh_from_db()
        self.assertEqual((encounter.answers, encounter.revision, encounter.status), before)
        # The notes form refuses a stale revision the same way.
        response = self.client.post(f'/encounters/{encounter.pk}/notes/', {'revision': encounter.revision - 1, 'notes': 'Stale notes'})
        self.assertEqual(response.status_code, 409)
        self.assertIn('Nothing was saved.', response.content.decode())
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.notes, 'Stale notes')
        # A finalized document refuses edits with the same page.
        self.finalize(encounter)
        response = self.client.post(f'/encounters/{encounter.pk}/save/', {'revision': encounter.revision})
        self.assertEqual(response.status_code, 409)
        self.assertIn('Finalized documents are immutable.', response.content.decode())
        self.assertIn('finalized and read-only', response.content.decode())
        self.assertNotIn('enter it again', response.content.decode(), 'advice a finalized document cannot follow')
