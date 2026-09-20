from pathlib import Path
import ctypes
from io import StringIO
import os
import tempfile
import unittest
from dotenv import dotenv_values
from ops.email_activation import KEYS, ORIGIN, RUNNING_RELEASE, updated_environment, replace_environment, _line


SYNTHETIC_QUOTING_CASES = (
    "Example's Mail <no-reply@example.com>",
    r'Synthetic\gate\only5298!',
    'Synthetic "quoted" mail',
    r'Synthetic\n\t literal escapes',
    'Synthetic $bare-dollar `backtick` #hash',
    '  Synthetic leading and trailing whitespace  ',
    'Synthetic José mail',
)


class EmailActivationTests(unittest.TestCase):
    def values(self):
        result = dict.fromkeys(KEYS, 'synthetic-value')
        result.update(QUILLMD_RELEASE_SHA='a' * 40, QUILLMD_EMAIL_MODE='resend',
                      QUILLMD_APP_BASE_URL=ORIGIN, QUILLMD_TRUST_PROXY='1')
        return result

    def original(self):
        return ('# Preserve this comment\nSTRIPE_SECRET_KEY=synthetic-unchanged\n'
                'QUILLMD_RELEASE_SHA=' + RUNNING_RELEASE + '\nQUILLMD_AI_MODEL="unchanged"\n').encode()

    def test_unrelated_bytes_and_quoted_sender_are_preserved(self):
        values = self.values()
        values['QUILLMD_EMAIL_FROM'] = "Example's Mail <no-reply@example.com>"
        out = updated_environment(self.original(), values)
        self.assertIn(b'# Preserve this comment\nSTRIPE_SECRET_KEY=synthetic-unchanged\n', out)
        self.assertIn(b'QUILLMD_AI_MODEL="unchanged"\n', out)

    def test_dotenv_preserves_synthetic_special_characters(self):
        for value in SYNTHETIC_QUOTING_CASES:
            with self.subTest(synthetic_value=value):
                values = self.values()
                values['QUILLMD_EMAIL_FROM'] = value
                actual = dotenv_values(stream=StringIO(updated_environment(self.original(), values).decode()), interpolate=False)
                self.assertEqual(actual['QUILLMD_EMAIL_FROM'], value)

    def test_duplicate_export_or_changed_release_refuses(self):
        for extra in [b'export QUILLMD_RELEASE_SHA=' + RUNNING_RELEASE.encode() + b'\n',
                      b'QUILLMD_RELEASE_SHA=' + b'b' * 40 + b'\n']:
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                updated_environment(self.original() + extra, self.values())

    def test_unapproved_keys_origins_and_interpolation_refuse(self):
        for key, value in [('UNDECLARED_KEY', 'x'), ('QUILLMD_APP_BASE_URL', 'https://example.com'),
                           ('RESEND_API_KEY', '${SECRET}'), ('RESEND_API_KEY', 'value\nINJECT=1')]:
            values = self.values(); values[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                updated_environment(self.original(), values)

    def test_atomic_replacement_preserves_protection_and_refuses_stale_baseline(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'; path.write_bytes(self.original()); path.chmod(0o600)
            updated = updated_environment(self.original(), self.values())
            with self.assertRaises(ValueError):
                replace_environment(path, b'wrong', updated)
            self.assertEqual(path.read_bytes(), self.original())
            replace_environment(path, self.original(), updated)
            self.assertEqual(path.read_bytes(), updated)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_link_and_public_permissions_refuse(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'; path.write_bytes(self.original()); path.chmod(0o644)
            updated = updated_environment(self.original(), self.values())
            with self.assertRaises(ValueError): replace_environment(path, self.original(), updated)
            path.chmod(0o600); link = Path(folder) / 'link'; link.symlink_to(path)
            with self.assertRaises(ValueError): replace_environment(link, self.original(), updated)


class NativeSystemdEnvironmentTests(unittest.TestCase):
    """Use the installed systemd parser, with only synthetic temporary input.

    A CI image without its shared parser can run the portable tests above but
    must label this native parser evidence skipped; an installed broken parser
    fails rather than being represented as a successful compatibility check.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        libraries = sorted({path.resolve() for root in (Path('/usr/lib'), Path('/lib'))
                            for pattern in ('*/systemd/libsystemd-shared-*.so', 'systemd/libsystemd-shared-*.so')
                            for path in root.glob(pattern)})
        if not libraries:
            raise unittest.SkipTest('Native systemd shared parser absent; dotenv tests are separate evidence.')
        cls.native = ctypes.CDLL(str(libraries[-1]))
        if not hasattr(cls.native, 'load_env_file') or not hasattr(cls.native, 'strv_free'):
            raise unittest.SkipTest('Installed systemd library lacks the native environment parser entry points.')
        cls.vector_type = ctypes.POINTER(ctypes.c_char_p)
        cls.native.load_env_file.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(cls.vector_type)]
        cls.native.load_env_file.restype = ctypes.c_int
        cls.native.strv_free.argtypes = [cls.vector_type]
        cls.native.strv_free.restype = ctypes.c_void_p

    def parse(self, data):
        with tempfile.NamedTemporaryFile(prefix='quillmd-synthetic-env-') as synthetic:
            synthetic.write(data)
            synthetic.flush()
            result = self.vector_type()
            status = self.native.load_env_file(None, os.fsencode(synthetic.name), ctypes.byref(result))
            try:
                self.assertEqual(status, 0)
                parsed = {}
                if result:
                    index = 0
                    while result[index]:
                        key, value = result[index].decode().split('=', 1)
                        parsed[key] = value
                        index += 1
                return parsed
            finally:
                if result:
                    self.native.strv_free(result)

    def test_actual_systemd_and_dotenv_preserve_the_same_values(self):
        for value in SYNTHETIC_QUOTING_CASES:
            with self.subTest(synthetic_value=value):
                serialized = _line('SYNTHETIC_EXAMPLE', value)
                self.assertEqual(self.parse(serialized), {'SYNTHETIC_EXAMPLE': value})
                self.assertEqual(dict(dotenv_values(stream=StringIO(serialized.decode()), interpolate=False)),
                                 {'SYNTHETIC_EXAMPLE': value})

    def test_native_parser_exposes_the_historical_single_quote_false_positive(self):
        for value in SYNTHETIC_QUOTING_CASES[:2]:
            with self.subTest(synthetic_value=value):
                old_quoted = value.replace('\\', '\\\\').replace("'", "\\'")
                old_serialized = ("SYNTHETIC_EXAMPLE='" + old_quoted + "'\n").encode()
                self.assertEqual(dotenv_values(stream=StringIO(old_serialized.decode()), interpolate=False)['SYNTHETIC_EXAMPLE'], value)
                self.assertNotEqual(self.parse(old_serialized).get('SYNTHETIC_EXAMPLE'), value)
