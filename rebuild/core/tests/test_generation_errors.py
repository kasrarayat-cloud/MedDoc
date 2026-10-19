"""Pure exception contracts; no worker, database, provider, or media runtime."""
import ast
import os
from pathlib import Path
import pickle
import subprocess
import sys
from types import ModuleType
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from core.generation_errors import NoProviderRequest, PlatformFailure


ERROR_TYPES = (NoProviderRequest, PlatformFailure)
REBUILD_ROOT = Path(__file__).resolve().parents[2]


def jobs_error_exports():
    """Execute only jobs' real exception imports, not its Linux-only runtime.

    This checks the backwards-compatible import surface without claiming that
    the whole worker can run on a platform that does not provide resource.
    """
    tree = ast.parse((REBUILD_ROOT / 'core' / 'jobs.py').read_text(encoding='utf-8'))
    names = {error_type.__name__ for error_type in ERROR_TYPES}
    declarations = [node for node in tree.body
                    if (isinstance(node, ast.ImportFrom) and node.module == 'generation_errors')
                    or (isinstance(node, ast.ClassDef) and node.name in names)]
    module = ModuleType('core.jobs')
    module.__package__ = 'core'
    module.ValidationError = ValidationError
    exec(compile(ast.Module(body=declarations, type_ignores=[]), 'core/jobs.py', 'exec'), module.__dict__)
    return module


class GenerationErrorContracts(TestCase):
    def test_import_needs_no_django_setup_or_worker_dependencies(self):
        env = dict(os.environ)
        env.pop('DJANGO_SETTINGS_MODULE', None)
        result = subprocess.run([sys.executable, '-c',
            'import sys; from django.conf import settings; '
            'from core.generation_errors import NoProviderRequest, PlatformFailure; '
            'assert not settings.configured; '
            'assert not ({"core.jobs", "core.media", "core.models", "resource"} & sys.modules.keys())'],
            cwd=REBUILD_ROOT, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scalar_validation_error_behavior_is_preserved(self):
        for error_type in ERROR_TYPES:
            with self.subTest(error_type=error_type.__name__):
                error = error_type('Review %(field)s.', code='needs_review', params={'field': 'source'})
                self.assertIsInstance(error, ValidationError)
                self.assertEqual(error.messages, ['Review source.'])
                self.assertEqual(error.code, 'needs_review')
                self.assertEqual(error.params, {'field': 'source'})
                self.assertEqual(type(error).__name__, error_type.__name__)

    def test_structured_errors_and_pickle_round_trips_preserve_classification(self):
        for error_type in ERROR_TYPES:
            for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
                with self.subTest(error_type=error_type.__name__, protocol=protocol):
                    error = error_type({'source': [ValidationError(
                        'Review %(field)s.', code='needs_review', params={'field': 'source'})]})
                    restored = pickle.loads(pickle.dumps(error, protocol=protocol))
                    self.assertIs(type(restored), error_type)
                    self.assertEqual(restored.message_dict, {'source': ['Review source.']})
                    self.assertEqual(restored.error_dict['source'][0].code, 'needs_review')
                    self.assertEqual(restored.error_dict['source'][0].params, {'field': 'source'})

    def test_existing_jobs_exports_are_the_same_exception_classes(self):
        exports = jobs_error_exports()
        for error_type in ERROR_TYPES:
            self.assertIs(getattr(exports, error_type.__name__), error_type)

    def test_legacy_pickle_module_references_resolve_through_jobs_exports(self):
        exports = jobs_error_exports()
        for error_type in ERROR_TYPES:
            with self.subTest(error_type=error_type.__name__):
                current = pickle.dumps(error_type('Review required.'), protocol=0)
                old_reference = ('ccore.generation_errors\n' + error_type.__name__ + '\n').encode()
                legacy_reference = ('ccore.jobs\n' + error_type.__name__ + '\n').encode()
                self.assertEqual(current.count(old_reference), 1)
                legacy = current.replace(old_reference, legacy_reference)
                with patch.dict(sys.modules, {'core.jobs': exports}):
                    restored = pickle.loads(legacy)
                self.assertIs(type(restored), error_type)
                self.assertEqual(restored.messages, ['Review required.'])
