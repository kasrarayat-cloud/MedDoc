"""Participant credentials (HARNESS.md 8; I9): the OpenAI and Anthropic files parsed strictly as data, refused for
anything but a protected regular file with exactly the keys each may hold, and never echoed in a repr or an error.
Offline and synthetic: every key is fake (test_participants_support)."""
from __future__ import annotations

import os

from studio.participants.credentials import (AnthropicCredentials, OpenAICredentials, load_anthropic_credentials,
                                             load_openai_credentials)
from studio.providers.base import ProviderUnavailable
from studio.providers.credentials import CredentialsError

from tests.test_participants_support import (ANTHROPIC_KEY, ANTHROPIC_WORKSPACE, OPENAI_KEY, OPENAI_PROJECT, SECRETS,
                                             OfflineTestCase, anthropic_env, openai_env, write_file)

VENDORS = (('OpenAI', load_openai_credentials, openai_env, 'OPENAI_API_KEY', 'OPENAI_PROJECT', OPENAI_PROJECT),
           ('Anthropic', load_anthropic_credentials, anthropic_env, 'ANTHROPIC_API_KEY', 'ANTHROPIC_WORKSPACE_ID',
            ANTHROPIC_WORKSPACE))


class CredentialsTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.files = 0

    def write(self, content, mode=0o600):
        self.files += 1
        return write_file(self.tmp / f'credentials-{self.files}.env', content, mode)

    def assertRefused(self, load, path, expect=''):
        with self.assertRaises(CredentialsError) as caught:
            load(path)
        error = caught.exception
        self.assertIsInstance(error, ProviderUnavailable)
        self.assertIsNone(error.__cause__)
        self.assertTrue(error.__suppress_context__ or error.__context__ is None)
        for text in (str(error), repr(error)):
            for secret in SECRETS + (OPENAI_PROJECT, ANTHROPIC_WORKSPACE):
                self.assertNotIn(secret, text)
            if path:
                self.assertNotIn(str(path), text)
        self.assertIn(expect, str(error))
        return str(error)

    def test_the_required_key_alone(self):
        credentials = load_openai_credentials(self.write(openai_env()))
        self.assertEqual((credentials.api_key, credentials.project), (OPENAI_KEY, None))
        credentials = load_anthropic_credentials(self.write(anthropic_env()))
        self.assertEqual((credentials.api_key, credentials.workspace_id), (ANTHROPIC_KEY, None))

    def test_the_optional_key_and_the_dotenv_forms_the_corti_file_accepts(self):
        content = ('# Synthetic OpenAI credentials for tests\n'
                   f"export OPENAI_API_KEY='{OPENAI_KEY}'\r\n"
                   '\n'
                   f'OPENAI_PROJECT = "{OPENAI_PROJECT}"  # the project\n')
        self.assertEqual(load_openai_credentials(self.write(content)), OpenAICredentials(OPENAI_KEY, OPENAI_PROJECT))
        content = f'ANTHROPIC_API_KEY={ANTHROPIC_KEY} # inline comment\nANTHROPIC_WORKSPACE_ID={ANTHROPIC_WORKSPACE}\n'
        self.assertEqual(load_anthropic_credentials(self.write(content)),
                         AnthropicCredentials(ANTHROPIC_KEY, ANTHROPIC_WORKSPACE))

    def test_repr_and_str_redact_every_value(self):
        for credentials in (OpenAICredentials(OPENAI_KEY, OPENAI_PROJECT), OpenAICredentials(OPENAI_KEY),
                            AnthropicCredentials(ANTHROPIC_KEY, ANTHROPIC_WORKSPACE),
                            AnthropicCredentials(ANTHROPIC_KEY)):
            for text in (repr(credentials), str(credentials), f'{credentials}', repr([credentials])):
                with self.subTest(text=text):
                    for value in SECRETS + (OPENAI_PROJECT, ANTHROPIC_WORKSPACE):
                        self.assertNotIn(value, text)
                    self.assertIn('api_key=<redacted>', text)
        self.assertIn('project=<configured>', repr(OpenAICredentials(OPENAI_KEY, OPENAI_PROJECT)))
        self.assertIn('workspace_id=<not configured>', repr(AnthropicCredentials(ANTHROPIC_KEY)))

    def test_a_missing_required_key(self):
        for vendor, load, env, required, optional, value in VENDORS:
            with self.subTest(vendor=vendor):
                self.assertRefused(load, self.write(f'{optional}={value}\n'),
                                   f'{required} is missing from the {vendor} credentials file')

    def test_unknown_lowercase_or_other_vendors_keys_are_refused(self):
        for vendor, load, env, required, optional, value in VENDORS:
            other = 'ANTHROPIC_API_KEY=x-synthetic' if vendor == 'OpenAI' else 'OPENAI_API_KEY=x-synthetic'
            for extra in ('OPENAI_ORGANIZATION=org-synthetic', other, required.lower() + '=x-synthetic',
                          'CORTI_CLIENT_ID=synthetic'):
                with self.subTest(vendor=vendor, extra=extra):
                    message = self.assertRefused(load, self.write(env() + extra + '\n'), 'Line 2')
                    self.assertIn(f'sets a key other than {required} or {optional}', message)

    def test_a_repeated_key_is_refused(self):
        for vendor, load, env, required, optional, value in VENDORS:
            with self.subTest(vendor=vendor):
                self.assertRefused(load, self.write(env() + f'{required}=second-synthetic-key\n'),
                                   f'{required} is set more than once')
                self.assertRefused(load, self.write(env(**{optional: value}) + f'{optional}={value}\n'),
                                   f'{optional} is set more than once')

    def test_a_key_that_cannot_be_a_header_value_is_refused_before_any_send(self):
        for vendor, load, env, required, optional, value in VENDORS:
            for bad in ('', "''", '"two words"', '"key\twith-tab"', 'kéy-not-ascii', '"\x7fdel"'):
                with self.subTest(vendor=vendor, value=repr(bad)):
                    self.assertRefused(load, self.write(env(**{required: bad})),
                                       'empty or contains a space, a control character')

    def test_the_optional_identifiers_must_be_well_formed(self):
        for value in ('', 'project_synthetic', 'proj_', 'proj_has space', 'proj_x.y', 'proj_' + 'a' * 129, 'proj_é'):
            with self.subTest(project=value):
                self.assertRefused(load_openai_credentials, self.write(openai_env(OPENAI_PROJECT=value)),
                                   'OPENAI_PROJECT is not an OpenAI project id')
        self.assertEqual(load_openai_credentials(self.write(openai_env(OPENAI_PROJECT='proj_' + 'a' * 128))).project,
                         'proj_' + 'a' * 128)
        for value in ('', '-leading', 'has space', 'w' * 129, 'wrkspc/x', 'wrkspc_é'):
            with self.subTest(workspace=value):
                self.assertRefused(load_anthropic_credentials,
                                   self.write(anthropic_env(ANTHROPIC_WORKSPACE_ID=value)),
                                   'ANTHROPIC_WORKSPACE_ID is not a workspace id')

    def test_a_bare_secret_line_is_refused_without_echoing_it(self):
        for vendor, load, env, *_ in VENDORS:
            with self.subTest(vendor=vendor):
                message = self.assertRefused(load, self.write(env() + f'{OPENAI_KEY}\n'), 'Line 2')
                self.assertIn('not a KEY=VALUE assignment', message)

    def test_quoting_errors(self):
        for vendor, load, env, required, *_ in VENDORS:
            for line, expect in ((f'{required}="{OPENAI_KEY}', 'unterminated or malformed'),
                                 (f'{required}="{OPENAI_KEY}"tail"', 'unterminated or malformed'),
                                 (f'{required}="{OPENAI_KEY}\\n"', 'escapes are not supported')):
                with self.subTest(vendor=vendor, line=line):
                    self.assertRefused(load, self.write(line + '\n'), expect)

    def test_the_size_limit_is_32000_bytes(self):
        for vendor, load, env, *_ in VENDORS:
            with self.subTest(vendor=vendor):
                base = env()
                exact = base + '#' * (32_000 - len(base) - 1) + '\n'
                self.assertEqual(len(exact.encode()), 32_000)
                load(self.write(exact))
                self.assertRefused(load, self.write(exact + '#'), 'larger than 32,000 bytes')

    def test_permissions_must_be_owner_only(self):
        for vendor, load, env, *_ in VENDORS:
            for mode in (0o640, 0o604, 0o620, 0o602, 0o660, 0o644):
                with self.subTest(vendor=vendor, mode=oct(mode)):
                    self.assertRefused(load, self.write(env(), mode=mode), 'accessible to group or other users')
            self.assertTrue(load(self.write(env(), mode=0o400)).api_key)

    def test_symlinks_directories_fifos_missing_and_unconfigured_paths(self):
        for vendor, load, env, *_ in VENDORS:
            with self.subTest(vendor=vendor):
                target = self.write(env())
                link = self.tmp / f'link-{vendor}.env'
                link.symlink_to(target)
                self.assertRefused(load, link, 'symbolic link')
                directory = self.tmp / f'dir-{vendor}.env'
                directory.mkdir(mode=0o700)
                self.assertRefused(load, directory, 'not a regular file')
                fifo = self.tmp / f'fifo-{vendor}.env'
                os.mkfifo(fifo, 0o600)
                self.assertRefused(load, fifo, 'not a regular file')  # O_NONBLOCK: no hang waiting for a writer
                self.assertRefused(load, self.tmp / 'absent.env', 'does not exist')
                for unset in ('', None):
                    self.assertRefused(load, unset, f'No {vendor} credentials file is configured')

    def test_non_utf8_content(self):
        for vendor, load, env, *_ in VENDORS:
            with self.subTest(vendor=vendor):
                self.assertRefused(load, self.write(env().encode() + b'\xff\xfe'), 'not valid UTF-8')
