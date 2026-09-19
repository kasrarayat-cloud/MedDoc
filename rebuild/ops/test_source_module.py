"""That the loader cannot serve a stale compiled copy — proved against a real one."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

try:
    from . import source_module
except ImportError:
    import source_module


class NeverServesACachedCopy(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'activate_something.py'
        # ⚠️ ORDER-DEPENDENCE, AND IT IS THE REASON THE HAZARD IS INTERMITTENT RATHER THAN CONSTANT. Every
        # `activate-*.py` sets `sys.dont_write_bytecode = True` at module scope, so the first activator any
        # test loads turns caching off for the WHOLE process — after which nothing new is cached and the
        # control below silently stops reproducing anything. It says nothing about caches written by
        # EARLIER processes, which is where the stale copy that cost this session an hour came from. Pin it
        # so this test measures the loader and not whichever test ran before it.
        self.addCleanup(setattr, sys, 'dont_write_bytecode', sys.dont_write_bytecode)
        sys.dont_write_bytecode = False

    def mutate_leaving_size_and_mtime_alone(self):
        """Exactly what a mutation proof does: same length, restored within the same second."""
        stat = self.path.stat()
        self.path.write_text("VALUE = 'MUTATED-'\n")
        os.utime(self.path, (stat.st_atime, stat.st_mtime))

    def test_the_standard_loader_really_does_serve_a_stale_copy(self):
        """The positive control. If this ever stops failing, the hazard is gone and so is the reason
        for this module — but it must be DEMONSTRATED gone, not assumed."""
        self.path.write_text("VALUE = 'ORIGINAL'\n")
        spec = importlib.util.spec_from_file_location('activate_something', self.path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.VALUE, 'ORIGINAL')
        self.mutate_leaving_size_and_mtime_alone()
        spec = importlib.util.spec_from_file_location('activate_something', self.path)
        stale = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stale)
        self.assertEqual(stale.VALUE, 'ORIGINAL', 'the cache no longer goes stale; re-read this module')

    def test_this_loader_reads_the_file_that_is_there(self):
        self.path.write_text("VALUE = 'ORIGINAL'\n")
        spec = importlib.util.spec_from_file_location('activate_something', self.path)
        primed = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(primed)          # prime __pycache__ the way a previous test run would
        self.mutate_leaving_size_and_mtime_alone()
        self.assertEqual(source_module.load('activate_something', self.path).VALUE, 'MUTATED-')

    def test_it_writes_no_cache_of_its_own(self):
        self.path.write_text("VALUE = 'ORIGINAL'\n")
        source_module.load('activate_something', self.path)
        self.assertFalse((self.path.parent / '__pycache__').exists())


if __name__ == '__main__':
    unittest.main()
