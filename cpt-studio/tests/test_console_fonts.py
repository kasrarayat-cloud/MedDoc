"""Release 2 (R2-26, lists L11; audit PERF-12): the operator console's four fonts by their hashed names.

Release 1's console named its fonts by plain addresses (/static/studio/fonts/*.ttf), which WhiteNoise serves for 60 s, so
every console page kept revalidating them. ops_base.html names them through the static tag now: under the manifest
storage the image builds with (collectstatic, CompressedManifestStaticFilesStorage), every console page names the four
fonts by their content-hashed names, and those answer with WhiteNoise's ten-year immutable caching. Under the plain
storage the other console tests read with, the addresses stay as they were (tests/test_admin_console.py LookTests).
Synthetic data only.
"""
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from tests.support import operator as ops
from tests.support import rounds as r

CONSOLE_FONTS = ('Manrope-Regular.ttf', 'Manrope-SemiBold.ttf', 'IBMPlexMono-Regular.ttf', 'IBMPlexMono-Medium.ttf')
# Pages of the console that extend ops_base.html and need no document: the front page, people, workspaces, spending,
# activity and sign-ins
CONSOLE_PAGES = ('/ops/', '/ops/people', '/ops/workspaces', '/ops/spending', '/ops/activity', '/ops/activity/sign-ins')


class ConsoleFontsByHashedNameTests(TestCase):
    """Under the manifest storage, after collectstatic into a temporary STATIC_ROOT, as the image is built."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._static_root = tempfile.TemporaryDirectory()
        cls._static = override_settings(STATIC_ROOT=Path(cls._static_root.name) / 'static')
        cls._static.enable()
        call_command('collectstatic', interactive=False, verbosity=0)

    @classmethod
    def tearDownClass(cls):
        cls._static.disable()
        cls._static_root.cleanup()
        super().tearDownClass()

    def setUp(self):
        self.console = ops.admin_client(r.f.user('platform-operator'))

    def named_fonts(self, url):
        response = self.console.get(url)
        self.assertEqual(response.status_code, 200, url)
        return re.findall(r'url\("([^"]+)"\)', response.content.decode())

    def test_the_storage_is_the_manifest_the_image_builds_with(self):
        self.assertEqual(settings.STORAGES['staticfiles']['BACKEND'],
                         'whitenoise.storage.CompressedManifestStaticFilesStorage')

    def test_every_console_page_names_the_four_fonts_by_their_hashed_names(self):
        expected = [staticfiles_storage.url(f'studio/fonts/{name}') for name in CONSOLE_FONTS]
        for name, address in zip(CONSOLE_FONTS, expected):
            stem, suffix = name.rsplit('.', 1)
            self.assertRegex(address, rf'^/static/studio/fonts/{re.escape(stem)}\.[0-9a-f]{{12}}\.{suffix}$')
        for url in CONSOLE_PAGES:
            with self.subTest(url=url):
                self.assertEqual(self.named_fonts(url), expected)

    def test_the_hashed_fonts_answer_immutable_for_ten_years_and_are_the_vendored_files(self):
        for name, address in zip(CONSOLE_FONTS, self.named_fonts('/ops/')):
            with self.subTest(name=name):
                response = Client(HTTP_HOST=settings.ADMIN_HOST).get(address)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response['Cache-Control'], 'max-age=315360000, public, immutable')
                served = b''.join(response.streaming_content) if response.streaming else response.content
                self.assertEqual(served, (Path(settings.BASE_DIR) / 'studio/static/studio/fonts' / name).read_bytes())
