"""Environment-file isolation must not fall back to reading operator secrets."""
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


SETTINGS = Path(__file__).resolve().parents[1] / 'quillmd/settings.py'


class ServiceConfigurationTests(unittest.TestCase):
    def test_managed_environment_never_opens_operator_dotenv(self):
        values = {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_SECRET_KEY': 'synthetic-only',
                  'QUILLMD_DB_PASSWORD': 'synthetic-only',
                  'QUILLMD_STATE_DIR': '/var/lib/quillmd', 'QUILLMD_ADMIN_SITE': '1'}
        with patch.dict(os.environ, values, clear=True), \
                patch('dotenv.load_dotenv', side_effect=AssertionError('Secret file opened')):
            settings = runpy.run_path(str(SETTINGS))
        self.assertEqual(settings['MEDIA_ROOT'], Path('/var/lib/quillmd/files'))
        self.assertEqual(settings['EMAIL_FILE_PATH'], Path('/var/lib/quillmd/mail'))
        self.assertTrue(settings['ADMIN_SITE'])
        self.assertTrue(settings['SYNTHETIC_ONLY'])

    def test_operator_cli_keeps_explicit_local_configuration(self):
        values = {'QUILLMD_SECRET_KEY': 'synthetic-only', 'QUILLMD_DB_PASSWORD': 'synthetic-only'}
        with patch.dict(os.environ, values, clear=True), patch('dotenv.load_dotenv') as loader:
            settings = runpy.run_path(str(SETTINGS))
        loader.assert_called_once_with(SETTINGS.parents[1] / '.env')
        self.assertEqual(settings['MEDIA_ROOT'], SETTINGS.parents[1] / '.runtime/files')

    def test_relative_state_path_refuses(self):
        values = {'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_STATE_DIR': '../other-project'}
        with patch.dict(os.environ, values, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'must be absolute'):
                runpy.run_path(str(SETTINGS))
