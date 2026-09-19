"""Static guards of the billing-policy resume script, proved against the repository."""
import ast
import importlib.util
from pathlib import Path
import unittest

try:
    from . import source_module
except ImportError:
    import source_module

ROOT = Path(__file__).resolve().parents[2]


def load(relative):
    return source_module.load(Path(relative).stem.replace('-', '_'), ROOT / relative)


class ResumeGuards(unittest.TestCase):
    def setUp(self):
        self.resume = load('scripts/resume-billing-policy.py')
        self.activator = load('scripts/activate-billing-policy.py')

    def test_bookkeeping_rows_are_exactly_the_two_new_models(self):
        source = (ROOT / self.activator.MIGRATION_PATH).read_text()
        names = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and getattr(node.func, 'attr', '') == 'CreateModel':
                names.append(ast.literal_eval({k.arg: k.value for k in node.keywords}['name']).lower())
        self.assertEqual(tuple(names), self.resume.BOOKKEEPING_MODELS)
        self.assertEqual(len(self.resume.BOOKKEEPING_PERMISSIONS), 8)
        for model in names:
            for action in ('add', 'change', 'delete', 'view'):
                self.assertIn(f'{action}_{model}', self.resume.BOOKKEEPING_PERMISSIONS)
                self.assertIn(model, self.resume.BOOKKEEPING_TABLES['django_content_type'])
                self.assertIn(model, self.resume.BOOKKEEPING_TABLES['auth_permission'])

    def test_resume_targets_the_recorded_partial_activation(self):
        self.assertEqual(self.resume.TARGET, 'd2e45b533396390c36d1ffa681c188126be556ce')
        self.assertEqual(self.resume.BASELINE, self.activator.BASELINE)
        self.assertEqual(self.resume.FAILED_RESULT.name, 'billing-policy-activation-20260918.json')
        self.assertEqual(len(self.resume.FAILED_RESULT_SHA), 64)
        self.assertEqual(len(self.resume.OLD_LOCK_SHA), 64)
        self.assertEqual(self.resume.ALLOWED_CHANGES, {'scripts/resume-billing-policy.py', 'rebuild/ops/test_billing_resume.py', self.resume.DECLARATION})
        self.assertTrue((ROOT / self.resume.DECLARATION).is_file())

    def test_resume_never_migrates_or_reinstalls(self):
        source = (ROOT / 'scripts/resume-billing-policy.py').read_text()
        for forbidden in ("'migrate'", 'with_db_role', 'install_artifact', 'activate-billing-policy.py --execute', 'git reset', 'git checkout'):
            self.assertNotIn(forbidden, source)
        self.assertIn("run(['git', 'merge', '--ff-only', args.resume_target])", source)
        self.assertIn("word.systemd('start', helper)", source)

    def test_require_raises(self):
        with self.assertRaises(RuntimeError):
            self.resume.require(False, 'refused')


if __name__ == '__main__':
    unittest.main()
