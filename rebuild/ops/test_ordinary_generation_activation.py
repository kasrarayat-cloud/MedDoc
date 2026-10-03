"""Meaningful source-bound preparation controls; no installed environment or provider access."""
import copy
import hashlib
from io import StringIO
import unittest

from dotenv import dotenv_values
from ops import ordinary_generation_activation as activation


class OrdinaryGenerationConfiguration(unittest.TestCase):
    def setUp(self):
        self.original = (b'# retained baseline\nQUILLMD_RELEASE_SHA=' + b'a' * 40 + b'\n'
                         b'QUILLMD_DATA_MODE=synthetic\nQUILLMD_AI_MODE=live\nQUILLMD_AI_PROVIDER=anthropic\n'
                         b'QUILLMD_AI_MODEL=claude-sonnet-4-6\nQUILLMD_AI_INPUT_RATE=3\n'
                         b'QUILLMD_AI_OUTPUT_RATE=15\nQUILLMD_AI_CACHED_RATE=.30\n'
                         b'QUILLMD_V3_FIELD_RELATIONS=0\nQUILLMD_STRIPE_MODE=test\n'
                         b'QUILLMD_PREVIEW_AUTH_ENABLED=1\nANTHROPIC_API_KEY="synthetic-test-only"\n'
                         b'UNRELATED="literal $value\\\\path"\n')
        self.sources = {path: ('synthetic source for ' + path).encode() for path in activation.SOURCE_PATHS}
        self.identity = {'release': 'b' * 40, 'model': activation.MODEL,
                         'ordinary_field_contract': activation.CONTRACT, 'request_profile': activation.PROFILE,
                         'sources': {path: hashlib.sha256(data).hexdigest() for path, data in self.sources.items()}}

    def prepare(self, **changes):
        return activation.environment(changes.get('original', self.original), changes.get('expected', 'a' * 40),
                                      changes.get('target', 'b' * 40),
                                      source_identity=changes.get('identity', self.identity),
                                      source_bytes=changes.get('sources', self.sources))

    def test_explicit_ordinary_profile_delta_preserves_mode_protection_payments_and_other_bytes(self):
        result = self.prepare()
        actual = dotenv_values(stream=StringIO(result.decode()), interpolate=False)
        self.assertEqual({name: actual[name] for name in activation.VALUES}, activation.VALUES)
        self.assertEqual(actual['QUILLMD_RELEASE_SHA'], 'b' * 40)
        self.assertEqual(actual['QUILLMD_AI_MODE'], 'live')
        for line in self.original.splitlines(keepends=True):
            if not any(line.startswith((name + '=').encode()) for name in activation.KEYS):
                self.assertIn(line, result)

    def test_fixture_mode_stays_fixture_and_no_provider_mode_is_enabled_by_preparation(self):
        result = self.prepare(original=self.original.replace(b'QUILLMD_AI_MODE=live', b'QUILLMD_AI_MODE=fixture'))
        self.assertIn(b'QUILLMD_AI_MODE=fixture\n', result)
        self.assertNotIn(b'QUILLMD_AI_MODE=live', result)

    def test_changed_source_or_release_or_contract_cannot_render_the_delta(self):
        sources = {**self.sources, next(iter(self.sources)): b'changed source'}
        with self.assertRaises(ValueError):
            self.prepare(sources=sources)
        for key, value in (('release', 'c' * 40), ('model', 'claude-sonnet-5'),
                           ('ordinary_field_contract', 'ordinary-field-relations-v3'),
                           ('request_profile', 'claude-sonnet-5-5-v1')):
            identity = copy.deepcopy(self.identity); identity[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.prepare(identity=identity)
        with self.assertRaises(ValueError):
            self.prepare(expected='c' * 40)
        with self.assertRaises(ValueError):
            self.prepare(target='b' * 8)

    def test_duplicate_controlled_settings_and_real_mode_and_other_contracts_refuse(self):
        for name in activation.KEYS:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.prepare(original=self.original + (name + '=duplicate\n' + name + '=duplicate\n').encode())
        with self.assertRaises(ValueError):
            self.prepare(original=self.original.replace(b'QUILLMD_DATA_MODE=synthetic', b'QUILLMD_DATA_MODE=real'))
        for name in ('QUILLMD_WM_NARRATIVE', 'QUILLMD_V3_HISTORY_CONTEXT', 'QUILLMD_V3_GENERATION_BATCHES'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.prepare(original=self.original + (name + '=1\n').encode())


if __name__ == '__main__':
    unittest.main()
