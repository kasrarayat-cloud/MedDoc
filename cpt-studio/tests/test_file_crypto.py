"""studio.file_crypto (release 1, F1; RELEASE-1-SPEC 3.3 and 3.7): AES-256-GCM sealing of stored files with a practice's
own data key, wrapped by a key-encryption key that never enters the database. Round trips; a flipped byte, another
practice or a changed AAD is refused; the key's sources and the system check. Synthetic keys and bytes only: every key
here is made by the test and lives in its temporary folder or its patched environment."""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from unittest import mock

from django.core import checks
from django.test import TestCase, override_settings
from django.utils import timezone

from studio import file_crypto, models
from tests.support import coding as f

DATA = b'%PDF-1.7\n% a synthetic original, sealed and opened by the file_crypto tests\n%%EOF\n'
AAD = 'original:synthetic-storage-name.pdf'


def kek_text():
    return base64.b64encode(os.urandom(32)).decode('ascii')


class KeyCase(TestCase):
    def setUp(self):
        self.ws, self.other_ws = f.workspace(), f.workspace('Another synthetic practice')
        self.kek = kek_text()
        patcher = mock.patch.dict(os.environ, {file_crypto.KEK_NAME: self.kek})
        patcher.start()
        self.addCleanup(patcher.stop)


class RoundTripTests(KeyCase):
    def test_a_sealed_file_opens_to_its_bytes_and_shows_none_of_them(self):
        sealed = file_crypto.seal(self.ws.pk, DATA, AAD)
        self.assertTrue(sealed.startswith(b'CPTF1'))
        self.assertTrue(file_crypto.is_sealed(sealed))
        self.assertEqual(len(sealed), file_crypto.HEADER_BYTES + len(DATA) + file_crypto.TAG_BYTES)
        self.assertNotIn(b'synthetic original', sealed)
        self.assertEqual(file_crypto.open_sealed(self.ws.pk, sealed, AAD), DATA)
        self.assertEqual(file_crypto.open_sealed(str(self.ws.pk), memoryview(sealed), AAD.encode()), DATA)
        self.assertNotEqual(file_crypto.seal(self.ws, DATA, AAD), sealed)  # a fresh nonce every time
        for data in (b'', os.urandom(1024 * 1024)):
            with self.subTest(size=len(data)):
                self.assertEqual(file_crypto.open_sealed(self.ws.pk, file_crypto.seal(self.ws.pk, data, AAD), AAD), data)

    def test_a_flipped_byte_anywhere_is_refused(self):
        sealed = file_crypto.seal(self.ws.pk, b'synthetic', AAD)
        for position in range(len(sealed)):
            changed = bytearray(sealed)
            changed[position] ^= 0x01
            with self.subTest(position=position), self.assertRaises(file_crypto.NotAuthentic):
                file_crypto.open_sealed(self.ws.pk, bytes(changed), AAD)
        for cut in (sealed[:-1], sealed[:file_crypto.HEADER_BYTES + file_crypto.TAG_BYTES - 1], sealed + b'\x00'):
            with self.subTest(length=len(cut)), self.assertRaises(file_crypto.NotAuthentic):
                file_crypto.open_sealed(self.ws.pk, cut, AAD)

    def test_a_changed_aad_is_refused(self):
        sealed = file_crypto.seal(self.ws.pk, DATA, AAD)
        for other in ('original:synthetic-storage-name.pdg', 'view:synthetic-storage-name.pdf', AAD + ' ', AAD[:-1],
                      'export:00000000-0000-4000-8000-000000000001'):
            with self.subTest(aad=other), self.assertRaises(file_crypto.NotAuthentic):
                file_crypto.open_sealed(self.ws.pk, sealed, other)
        self.assertEqual(file_crypto.open_sealed(self.ws.pk, sealed, AAD), DATA)  # the control

    def test_a_blob_moved_to_another_practice_is_refused(self):
        sealed = file_crypto.seal(self.ws.pk, DATA, AAD)
        with self.assertRaises(file_crypto.KeyUnavailable):  # the other practice has sealed nothing: it has no key
            file_crypto.open_sealed(self.other_ws.pk, sealed, AAD)
        file_crypto.seal(self.other_ws.pk, b'its own', AAD)
        with self.assertRaises(file_crypto.NotAuthentic):  # with its own key: still not its blob
            file_crypto.open_sealed(self.other_ws.pk, sealed, AAD)

    def test_plain_data_is_not_a_sealed_file(self):
        for blob in (DATA, b'', b'CPTF1', b'CPTF1' + b'\x00' * 31, None, 'CPTF1' + 'x' * 40):
            with self.subTest(blob=blob[:8] if blob else blob):
                self.assertFalse(file_crypto.is_sealed(blob))
        with self.assertRaises(file_crypto.NotAuthentic):
            file_crypto.open_sealed(self.ws.pk, DATA, AAD)

    def test_arguments_outside_the_contract(self):
        for arguments in ((self.ws.pk, 'text, not bytes', AAD), (self.ws.pk, DATA, ''), (self.ws.pk, DATA, b''),
                          (self.ws.pk, DATA, None), ('not-a-practice', DATA, AAD)):
            with self.subTest(arguments=arguments[1:]), self.assertRaises(ValueError):
                file_crypto.seal(*arguments)


class KeyHandlingTests(KeyCase):
    def test_one_wrapped_key_per_practice_and_neither_key_is_stored(self):
        file_crypto.seal(self.ws.pk, DATA, AAD)
        file_crypto.seal(self.ws.pk, DATA, AAD)
        self.assertEqual(models.FileKey.objects.count(), 1)
        row = models.FileKey.objects.get(workspace_id=self.ws.pk)
        version, data_key = file_crypto._data_key(self.ws.pk, create=False)
        self.assertEqual((version, row.key_version, len(data_key)), (1, 1, 32))
        stored = bytes(row.wrapped_key)
        self.assertEqual(len(stored), file_crypto.NONCE_BYTES + 32 + file_crypto.TAG_BYTES)
        self.assertNotIn(data_key, stored)
        self.assertNotIn(base64.b64decode(self.kek), stored)
        file_crypto.seal(self.other_ws.pk, DATA, AAD)
        self.assertNotEqual(file_crypto._data_key(self.other_ws.pk, create=False)[1], data_key)

    def test_another_key_encryption_key_opens_nothing(self):
        sealed = file_crypto.seal(self.ws.pk, DATA, AAD)
        with mock.patch.dict(os.environ, {file_crypto.KEK_NAME: kek_text()}):
            with self.assertRaises(file_crypto.KeyUnavailable):
                file_crypto.open_sealed(self.ws.pk, sealed, AAD)
            with self.assertRaises(file_crypto.KeyUnavailable):
                file_crypto.seal(self.ws.pk, DATA, AAD)

    def test_a_destroyed_key_seals_and_opens_nothing(self):
        sealed = file_crypto.seal(self.ws.pk, DATA, AAD)
        models.FileKey.objects.filter(workspace_id=self.ws.pk).update(wrapped_key=b'\x00' * 60,
                                                                     destroyed_at=timezone.now())
        for act in (lambda: file_crypto.open_sealed(self.ws.pk, sealed, AAD),
                    lambda: file_crypto.seal(self.ws.pk, DATA, AAD)):
            with self.assertRaisesMessage(file_crypto.KeyUnavailable, 'destroyed'):
                act()

    def test_a_data_key_is_bound_to_its_practice(self):
        file_crypto.seal(self.ws.pk, DATA, AAD)
        row = models.FileKey.objects.get(workspace_id=self.ws.pk)
        models.FileKey.objects.create(workspace_id=self.other_ws.pk, key_version=1, wrapped_key=bytes(row.wrapped_key))
        with self.assertRaises(file_crypto.KeyUnavailable):  # a wrapped key copied onto another practice opens nothing
            file_crypto.seal(self.other_ws.pk, DATA, AAD)


class KeySourceTests(TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix='lane1_kek_')
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop(file_crypto.KEK_NAME, None)

    def env_file(self, text):
        path = self.tmp / 'files-kek.env'
        path.write_text(text, encoding='utf-8')
        path.chmod(0o600)
        return str(path)

    def test_the_key_comes_from_the_named_file_or_else_the_environment(self):
        value = kek_text()
        named = self.env_file(f'# the protected environment file\nCPT_STUDIO_SECRET_KEY=synthetic\n'
                              f'{file_crypto.KEK_NAME}={value}\n\n')
        with self.settings(FILES_KEK_FILE=named):
            self.assertEqual(file_crypto.key_encryption_key(), base64.b64decode(value))
        os.environ[file_crypto.KEK_NAME] = value
        self.assertEqual(file_crypto.key_encryption_key(), base64.b64decode(value))

    def test_every_unusable_source_is_refused_and_no_message_holds_the_key(self):
        value = kek_text()
        cases = {
            'nothing configured': ('', None),
            'both sources': (self.env_file(f'{file_crypto.KEK_NAME}={value}\n'), value),
            'no such file': (str(self.tmp / 'missing.env'), None),
            'two key lines': (self.env_file(f'{file_crypto.KEK_NAME}={value}\n{file_crypto.KEK_NAME}={value}\n'), None),
            'no key line': (self.env_file('CPT_STUDIO_SECRET_KEY=synthetic\n'), None),
            'a line that is not NAME=value': (self.env_file(f'{file_crypto.KEK_NAME}={value}\nexport\n'), None),
            'not base64': (self.env_file(f'{file_crypto.KEK_NAME}={value[:-2]}!!\n'), None),
            'sixteen bytes': (self.env_file(f'{file_crypto.KEK_NAME}={base64.b64encode(os.urandom(16)).decode()}\n'),
                              None),
            'an environment value of the wrong length': ('', base64.b64encode(os.urandom(31)).decode()),
        }
        for label, (path, environment) in cases.items():
            with self.subTest(label):
                os.environ.pop(file_crypto.KEK_NAME, None)
                if environment is not None:
                    os.environ[file_crypto.KEK_NAME] = environment
                with self.settings(FILES_KEK_FILE=path), self.assertRaises(file_crypto.KeyUnavailable) as refused:
                    file_crypto.key_encryption_key()
                self.assertNotIn(value, str(refused.exception))
                if environment:
                    self.assertNotIn(environment, str(refused.exception))


class SystemCheckTests(TestCase):
    def test_off_needs_no_key_and_on_needs_a_usable_one(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(file_crypto.KEK_NAME, None)
            self.assertEqual(file_crypto.check_files_key(), [])  # today: off
            with override_settings(FILES_ENCRYPTION='on'):
                found = file_crypto.check_files_key()
                self.assertEqual([error.id for error in found], ['studio.E101'])
                self.assertTrue(found[0].is_serious())
                # registered: the security checks Django runs at `manage.py check` and the worker's start report it
                self.assertIn('studio.E101', [error.id for error in checks.run_checks(tags=[checks.Tags.security])])
                os.environ[file_crypto.KEK_NAME] = kek_text()
                self.assertEqual(file_crypto.check_files_key(), [])
