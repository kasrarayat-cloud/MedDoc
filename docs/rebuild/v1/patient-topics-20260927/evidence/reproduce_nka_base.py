import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings', QUILLMD_DB_PORT='1')
import django
django.setup()
from core.tests import test_v3_ordinary_notes as cases
path = Path(__file__).with_name('base-generation.py')
spec = importlib.util.spec_from_file_location('core.baseline_generation', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
cases.g = module
with patch('socket.socket.connect', side_effect=AssertionError('Network denied')):
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([
        cases.ScopeInOrdinarySentences('test_a_complete_statement_needs_a_listed_verb')]))
sys.exit(not result.wasSuccessful())
