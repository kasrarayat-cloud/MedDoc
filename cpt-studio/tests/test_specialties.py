"""Owner direction 2026-11-22 (D390): Neurosurgery and Orthopedic Surgery beside Gastroenterology, the GI way. The
specialty is the member's workspace category, a label the page and the PDF report show; nothing codes from it (D358).
These pin that the page names the member's own specialty where it used to say Gastroenterology or GI."""
import json
import pathlib

from django.conf import settings
from django.test import Client, TestCase, override_settings

from studio import models, state
from tests.support import rounds as r
from tests.test_physician_report import flat, text_of

PLAIN_STATIC = {**settings.STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
APP_JS = pathlib.Path(__file__).resolve().parent.parent / 'studio' / 'static' / 'studio' / 'app.js'


def specialty_member(slug, name):
    category, _ = models.Category.objects.get_or_create(slug=slug, defaults={'name': name, 'profiles_version': 'fable-coding@1'})
    workspace = models.Workspace.objects.create(name=name, category=category)
    user = models.User.objects.create_user(username=f'owner-{slug}', password='synthetic-pass-123!', display_name=name)
    models.Membership.objects.create(user=user, workspace=workspace, role=models.Membership.OWNER)
    return user, workspace


@override_settings(STORAGES=PLAIN_STATIC)
class PageNamesTheMembersSpecialtyTests(TestCase):
    def page(self, user):
        client = Client()
        client.force_login(user)
        response = client.get('/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_each_specialty_sees_its_own_name_and_never_gastroenterology(self):
        for slug, name in (('neurosurgery', 'Neurosurgery'), ('orthopedic-surgery', 'Orthopedic Surgery')):
            with self.subTest(specialty=name):
                user, _ = specialty_member(slug, name)
                html = self.page(user)
                self.assertIn(f'<select id="specialty" disabled><option>{name}</option></select>', html)
                self.assertIn(f'data-specialty="{name}"', html)
                self.assertNotIn('Gastroenterology', html)
        user, _ = specialty_member('gastroenterology', 'Gastroenterology')
        html = self.page(user)
        self.assertIn('<select id="specialty" disabled><option>Gastroenterology</option></select>', html)

    def test_the_page_script_holds_no_specialty_of_its_own(self):
        source = APP_JS.read_text(encoding='utf-8')
        for fixed in ('GASTROENTEROLOGY', 'Gastroenterology', 'synthetic GI document'):
            self.assertNotIn(fixed, source)
        self.assertIn('document.body?.dataset?.specialty', source)


class ReportNamesTheWorkspaceSpecialtyTests(r.CustomerCase, TestCase):
    def test_the_pdf_report_prints_the_workspace_specialty(self):
        category, _ = models.Category.objects.get_or_create(
            slug='orthopedic-surgery', defaults={'name': 'Orthopedic Surgery', 'profiles_version': 'fable-coding@1'})
        models.Workspace.objects.filter(pk=self.ws.pk).update(category=category)
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('27447', 'ready')])
        client = self.client_for(self.reviewer)
        made = client.post(f'/api/encounters/{enc.pk}/reports', data=json.dumps(
            {'kind': 'draft', 'fmt': 'pdf', 'round': state.latest_round(enc).number}), content_type='application/json')
        self.assertEqual(made.status_code, 201, made.content)
        text = flat(text_of(client.get(made.json()['download_url']).content))
        self.assertIn('Orthopedic Surgery', text)
        self.assertNotIn('Gastroenterology', text)
