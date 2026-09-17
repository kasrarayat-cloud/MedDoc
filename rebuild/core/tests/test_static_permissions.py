"""New compiled public assets must remain readable after later deployments."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase
from django.utils.module_loading import import_string


class StaticPermissionTests(SimpleTestCase):
    def test_new_public_assets_are_readable_without_broadening_private_uploads(self):
        definition = settings.STORAGES['staticfiles']
        backend = import_string(definition['BACKEND'])
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = backend(location=root / 'public', base_url='/static/', **definition.get('OPTIONS', {}))
            private = FileSystemStorage(location=root / 'private')
            previous = os.umask(0o077)
            try:
                public.save('nested/app.css', ContentFile(b'body { color: black; }'))
                private.save('originals/synthetic.docx', ContentFile(b'synthetic private object'))
            finally:
                os.umask(previous)
            for name in ('public', 'public/nested'):
                self.assertEqual((root / name).stat().st_mode & 0o777, 0o755)
            self.assertEqual((root / 'public/nested/app.css').stat().st_mode & 0o777, 0o644)
            self.assertEqual((root / 'private/originals').stat().st_mode & 0o777, 0o700)
            self.assertEqual((root / 'private/originals/synthetic.docx').stat().st_mode & 0o777, 0o600)
