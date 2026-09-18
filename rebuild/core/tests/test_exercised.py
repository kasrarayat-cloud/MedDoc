"""The missing-coverage guard itself, which nothing else would catch if it silently passed."""
import unittest

from exercised import MissingCoverage, requires_distinct, requires_input


class AGuardThatCannotFailIsNotAGuard(unittest.TestCase):
    def test_a_present_input_passes_and_returns_true(self):
        self.assertTrue(requires_input(True, 'an input that is present'))
        self.assertTrue(requires_distinct([None, {'release': 'x'}], 'two shapes'))

    def test_an_absent_input_raises_rather_than_passing(self):
        with self.assertRaises(MissingCoverage) as caught:
            requires_input(False, 'a finalized encounter, or the guard is never reached')
        self.assertIn('MISSING COVERAGE', str(caught.exception))
        self.assertIn('finalized encounter', str(caught.exception))

    def test_uniform_inputs_are_reported_as_undiscriminating(self):
        with self.assertRaises(MissingCoverage) as caught:
            requires_distinct([None, None], 'both surfaces up and both down')
        self.assertIn('DISCRIMINATE', str(caught.exception))

    def test_it_is_an_assertion_error_so_a_runner_reports_it_as_a_failure(self):
        self.assertTrue(issubclass(MissingCoverage, AssertionError))

    def test_the_module_imports_without_django(self):
        """It must work in the plain-unittest ops suite as well as the Django suite."""
        import exercised
        self.assertEqual([name for name in dir(exercised) if name.startswith('__im')], [])
        source = open(exercised.__file__).read()
        self.assertNotIn('import django', source)
        self.assertNotIn('import unittest', source)
