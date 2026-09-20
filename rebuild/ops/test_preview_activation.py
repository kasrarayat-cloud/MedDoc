import unittest
from ops.preview_activation import environment


class ConfigurationTests(unittest.TestCase):
    def test_enable_then_basic_rollback_preserves_credentials_and_actual_revision(self):
        source = b'# existing\nQUILLMD_RELEASE_SHA="' + b'a' * 40 + b'"\nRESEND_API_KEY="synthetic-only"\nUNRELATED="a$z\\\\q"\n'
        enabled = environment(source, 'a' * 40, 'b' * 40, True)
        self.assertIn(b'QUILLMD_PREVIEW_AUTH_ENABLED="1"\n', enabled)
        self.assertIn(b'RESEND_API_KEY="synthetic-only"\nUNRELATED="a$z\\\\q"\n', enabled)
        rollback = environment(enabled, 'b' * 40, 'b' * 40, False)
        self.assertIn(b'QUILLMD_PREVIEW_AUTH_ENABLED="0"\n', rollback)
        self.assertIn(b'QUILLMD_RELEASE_SHA="' + b'b' * 40, rollback)
        self.assertNotIn(b'a' * 40, rollback)

    def test_duplicates_changed_release_and_ambiguous_mode_refused(self):
        baseline = b'QUILLMD_RELEASE_SHA="' + b'a' * 40 + b'"\n'
        cases = [(baseline * 2, 'a' * 40, 'b' * 40, True),
                 (baseline + b'QUILLMD_PREVIEW_AUTH_ENABLED=0\nQUILLMD_PREVIEW_AUTH_ENABLED=1\n', 'a' * 40, 'b' * 40, True),
                 (baseline, 'c' * 40, 'b' * 40, True),
                 (baseline, 'a' * 40, 'b' * 40, 'yes')]
        for arguments in cases:
            with self.subTest(arguments=arguments[1:]), self.assertRaises(ValueError):
                environment(*arguments)
