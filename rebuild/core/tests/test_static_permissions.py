"""New compiled public assets must remain readable after later deployments."""
import os
import gzip
import stat
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import SimpleTestCase
from django.utils.module_loading import import_string
from whitenoise.compress import Compressor


class StaticPermissionTests(SimpleTestCase):
    def test_source_swap_after_validation_cannot_publish_private_bytes(self):
        from quillmd.static_storage import PublicAssetCompressor
        with TemporaryDirectory() as temporary:
            root = Path(temporary); public = root / 'public'; public.mkdir(mode=0o755)
            source = public / 'app.css'; source.write_bytes(b'body { color: black; }\n' * 100)
            private = root / 'private'; private_bytes = b'SYNTHETIC PRIVATE MUST NOT PUBLISH\n' * 100
            private.write_bytes(private_bytes); private.chmod(0o600)
            compressor = PublicAssetCompressor(public, use_brotli=False, quiet=True)
            check = compressor._check
            swapped = False
            def replace_after_file_check(info, *, directory=False):
                nonlocal swapped
                check(info, directory=directory)
                if not directory and stat.S_ISREG(info.st_mode) and not swapped:
                    swapped = True
                    source.rename(public / 'saved-public.css')
                    source.symlink_to(private)
            with patch.object(compressor, '_check', side_effect=replace_after_file_check), self.assertRaises(RuntimeError):
                compressor.compress(str(source))
            self.assertTrue(swapped)
            self.assertFalse((public / 'app.css.gz').exists())
            self.assertEqual(private.read_bytes(), private_bytes)
            self.assertEqual(private.stat().st_mode & 0o777, 0o600)

    def test_actual_compression_is_public_under_both_operator_umasks(self):
        definition = settings.STORAGES['staticfiles']
        backend = import_string(definition['BACKEND'])
        source = b'body { color: black; background: white; }\n' * 300
        for mask in (0o002, 0o077):
            with self.subTest(umask=oct(mask)), TemporaryDirectory() as temporary:
                root = Path(temporary)
                public = backend(location=root / 'public', base_url='/static/', **definition.get('OPTIONS', {}))
                private = FileSystemStorage(location=root / 'private')
                previous = os.umask(mask)
                try:
                    public.save('nested/app.css', ContentFile(source))
                    results = list(public.post_process({'nested/app.css': (public, 'nested/app.css')}))
                    private.save('originals/synthetic.docx', ContentFile(b'synthetic private object'))
                finally:
                    os.umask(previous)
                self.assertFalse(any(isinstance(processed, Exception) for _, _, processed in results))
                compressed = list((root / 'public').rglob('*.gz'))
                self.assertEqual(len(compressed), 2, 'Both original and manifest-hashed CSS must actually compress.')
                for path in compressed:
                    self.assertEqual(gzip.decompress(path.read_bytes()), source)
                    self.assertEqual(path.read_bytes(), Compressor.compress_gzip(source))
                for path in (root / 'public').rglob('*'):
                    self.assertEqual(path.stat().st_mode & 0o777, 0o755 if path.is_dir() else 0o644, path.name)
                self.assertEqual((root / 'private/originals').stat().st_mode & 0o777, 0o700)
                self.assertEqual((root / 'private/originals/synthetic.docx').stat().st_mode & 0o777, 0o600)

    def test_compressed_output_links_cannot_truncate_or_broaden_private_file(self):
        from quillmd.static_storage import PublicAssetCompressor
        with TemporaryDirectory() as temporary:
            root = Path(temporary); public = root / 'public'; public.mkdir(mode=0o755)
            source = public / 'app.css'; source.write_bytes(b'body { color: black; }\n' * 100)
            private = root / 'private'; private.write_bytes(b'SYNTHETIC PRIVATE CANARY'); private.chmod(0o600)
            output = public / 'app.css.gz'
            compressor = PublicAssetCompressor(public, use_brotli=False, quiet=True)
            for kind in ('symlink', 'hardlink'):
                with self.subTest(kind=kind):
                    if kind == 'symlink':output.symlink_to(private)
                    else:os.link(private, output)
                    try:
                        with self.assertRaises((OSError, RuntimeError)):
                            compressor.compress(str(source))
                        self.assertEqual(private.read_bytes(), b'SYNTHETIC PRIVATE CANARY')
                        self.assertEqual(private.stat().st_mode & 0o777, 0o600)
                    finally:
                        output.unlink()

    def test_compressor_refuses_outside_paths_linked_parents_and_foreign_owner(self):
        from quillmd.static_storage import PublicAssetCompressor
        with TemporaryDirectory() as temporary:
            root = Path(temporary); public = root / 'public'; public.mkdir(mode=0o755)
            source = root / 'private'; source.write_bytes(b'SYNTHETIC PRIVATE CANARY'); source.chmod(0o600)
            compressor = PublicAssetCompressor(public, use_brotli=False, quiet=True)
            with self.assertRaises(RuntimeError):compressor.compress(str(source))
            with self.assertRaises(RuntimeError):compressor.compress(str(public / '..' / 'private'))
            (public / 'linked').symlink_to(root, target_is_directory=True)
            with self.assertRaises(OSError):compressor.compress(str(public / 'linked' / 'private'))
            with self.assertRaises(RuntimeError):
                PublicAssetCompressor(public / 'linked', quiet=True).compress(str(public / 'linked' / 'private'))
            linked_source = public / 'source.css'; os.link(source, linked_source)
            with self.assertRaises(RuntimeError):compressor.compress(str(linked_source))
            linked_source.unlink(); linked_source.write_bytes(b'body { color: black; }\n' * 100)
            with patch('quillmd.static_storage.os.geteuid', return_value=os.geteuid()+1), self.assertRaises(RuntimeError):
                compressor.compress(str(linked_source))
            self.assertEqual(source.read_bytes(), b'SYNTHETIC PRIVATE CANARY')
            self.assertFalse(list(public.rglob('*.gz')))

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
