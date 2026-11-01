"""The participant registry and replay (HARNESS.md 8): which adapter a mode builds and from which settings, which
reader reads a stored run, and replayed answers that send nothing, report no new usage and are read exactly as live
ones. Offline and synthetic (test_participants_support)."""
from __future__ import annotations

import copy
import hashlib
import os
import subprocess
import sys
from pathlib import Path

from django.test import override_settings

from studio.participants import (Participant, configured, get_participant, participant_mode, reader_for,
                                 registry)
from studio.participants.anthropic_fable import FableParticipant
from studio.participants.openai_astra import AstraParticipant
from studio.participants.replay import ReplayParticipant
from studio.providers.base import ProviderUnavailable

from tests.test_participants_support import (CLIENT_REQUEST_ID, NOTE, ORIGINAL, PAGES, PDF, OfflineTestCase,
                                             fixture_bytes, write_file)

ASTRA_VERSION = 'openai-responses@cptstudio-harness-1'
FABLE_VERSION = 'anthropic-messages@cptstudio-harness-1'


class RegistryTests(OfflineTestCase):
    def test_live_builds_each_adapter_from_settings_without_reading_its_credentials(self):
        openai_path, anthropic_path = str(self.tmp / 'openai-not-yet.env'), str(self.tmp / 'anthropic-not-yet.env')
        with override_settings(OPENAI_CREDENTIALS_FILE=openai_path, ANTHROPIC_CREDENTIALS_FILE=anthropic_path,
                               PARTICIPANT_CONNECT_TIMEOUT_SECONDS=7, PARTICIPANT_READ_TIMEOUT_SECONDS=99,
                               PARTICIPANT_MAX_REQUEST_BYTES=1234, PARTICIPANT_MAX_RESPONSE_BYTES=5678):
            astra, fable = registry.build('astra', 'live'), registry.build('fable', 'live')
        for adapter, kind, path in ((astra, AstraParticipant, openai_path), (fable, FableParticipant, anthropic_path)):
            with self.subTest(adapter=adapter.name):
                self.assertIsInstance(adapter, kind)
                self.assertIsInstance(adapter, Participant)
                self.assertEqual((adapter.credentials_path, adapter.connect_timeout, adapter.read_timeout,
                                  adapter.max_request_bytes, adapter.max_response_bytes), (path, 7, 99, 1234, 5678))
                self.assertFalse(Path(path).exists())

    def test_the_settings_defaults_are_the_contract(self):
        from django.conf import settings

        self.assertEqual((settings.PARTICIPANT_CONNECT_TIMEOUT_SECONDS, settings.PARTICIPANT_READ_TIMEOUT_SECONDS,
                          settings.PARTICIPANT_SEND_DEADLINE_SECONDS), (10, 300, 330))
        with override_settings(OPENAI_CREDENTIALS_FILE='/run/cpt-studio/openai.env'):
            adapter = registry.build('astra', 'live')
        self.assertEqual((adapter.connect_timeout, adapter.read_timeout, adapter.max_request_bytes,
                          adapter.max_response_bytes), (10, 300, 24 * 1024 * 1024, 4 * 1024 * 1024))

    def test_live_without_its_credentials_setting_is_unavailable(self):
        with override_settings(OPENAI_CREDENTIALS_FILE='', ANTHROPIC_CREDENTIALS_FILE=''):
            for name, setting in (('astra', 'CPT_STUDIO_OPENAI_CREDENTIALS_FILE'),
                                  ('fable', 'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE')):
                with self.subTest(name=name), self.assertRaises(ProviderUnavailable) as caught:
                    registry.build(name, 'live')
                self.assertIn(setting, str(caught.exception))

    def test_replay_needs_its_directory(self):
        with override_settings(PARTICIPANT_REPLAY_DIR=str(self.tmp)):
            adapter = registry.build('fable', 'replay')
        self.assertIsInstance(adapter, ReplayParticipant)
        self.assertEqual((adapter.name, adapter.mode, adapter.replay_dir), ('fable', 'replay', self.tmp))
        with override_settings(PARTICIPANT_REPLAY_DIR=''), self.assertRaises(ProviderUnavailable):
            registry.build('astra', 'replay')

    def test_unknown_participants_and_modes_are_programming_errors(self):
        for name, mode in (('corti', 'live'), ('Astra', 'live'), ('', 'replay'), ('astra', 'disabled'),
                           ('fable', 'LIVE'), ('astra', None)):
            with self.subTest(name=name, mode=mode), self.assertRaises(ValueError):
                registry.build(name, mode)

    def test_the_mode_settings_decide_what_runs(self):
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'):
            self.assertEqual(configured(), ())
            self.assertIsNone(get_participant('astra'))
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='live', ANTHROPIC_CREDENTIALS_FILE='/x.env'):
            self.assertEqual(configured(), ('fable',))
            self.assertEqual(participant_mode('fable'), 'live')
            self.assertIsInstance(get_participant('fable'), FableParticipant)
            self.assertIsNone(get_participant('astra'))
        with override_settings(ASTRA_MODE='replay', FABLE_MODE='live', PARTICIPANT_REPLAY_DIR=str(self.tmp),
                               ANTHROPIC_CREDENTIALS_FILE=''):
            self.assertEqual(configured(), ('astra', 'fable'))
            self.assertIsInstance(get_participant('astra'), ReplayParticipant)
            with self.assertRaises(ProviderUnavailable):  # a misconfigured participant raises; it is not skipped
                get_participant('fable')

    def test_a_stored_run_is_read_only_as_the_version_that_recorded_it(self):
        from studio.participants import anthropic_fable, openai_astra

        self.assertIs(registry.reader('astra', ASTRA_VERSION), openai_astra.read_response)
        self.assertIs(registry.reader('fable', FABLE_VERSION), anthropic_fable.read_response)
        self.assertIs(reader_for('astra', ASTRA_VERSION), openai_astra.read_response)
        for provider, version in (('astra', FABLE_VERSION), ('fable', ASTRA_VERSION), ('astra', ASTRA_VERSION + '0'),
                                  ('corti', 'corti-coding-v2@cptstudio-1'), ('replay', ASTRA_VERSION),
                                  ('Astra', ASTRA_VERSION), ('astra', None), (None, None), (['astra'], ASTRA_VERSION)):
            with self.subTest(provider=provider, version=version), self.assertRaises(ProviderUnavailable):
                registry.reader(provider, version)

    def test_importing_the_participants_never_reads_settings(self):
        script = ('import studio.participants.registry, studio.participants.replay, studio.participants.pricing\n'
                  'from django.conf import settings\n'
                  'assert not settings.configured, "importing the participants configured settings"\n')
        environment = {'PATH': os.environ.get('PATH', ''), 'PYTHONDONTWRITEBYTECODE': '1'}
        completed = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parent.parent,
                                   env=environment, capture_output=True, text=True, timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stderr)


class ReplayTests(OfflineTestCase):
    def setUp(self):
        super().setUp()
        self.astra = ReplayParticipant('astra', self.tmp)
        self.raw = fixture_bytes('astra-colonoscopy.response.json')

    def record(self, name, request, raw, mode=0o600):
        folder = self.tmp / name
        folder.mkdir(mode=0o700, exist_ok=True)
        return write_file(folder / f'{request.canonical_sha256}.json', raw, mode)

    def send(self, adapter, request, **options):
        options.setdefault('deadline_s', 5)
        options.setdefault('client_request_id', CLIENT_REQUEST_ID)
        options.setdefault('original_bytes', None)
        return adapter.send(request, **options)

    def test_a_recorded_answer_replays_without_new_usage_and_calls_nothing(self):
        request = self.astra.build_request(NOTE, PAGES, 'paste', None)
        self.record('astra', request, self.raw)
        exchange = self.send(self.astra, request)
        self.assertEqual((exchange.outcome, exchange.sent, exchange.http_status, exchange.latency_ms),
                         ('succeeded', False, None, None))
        self.assertEqual((exchange.response_bytes, exchange.response_sha256),
                         (self.raw, hashlib.sha256(self.raw).hexdigest()))
        self.assertEqual((exchange.usage, exchange.usage_basis), ({}, 'historical_replay_not_new_usage'))
        self.assertEqual((exchange.endpoint, exchange.provider_request_id, exchange.error), ('', '', ''))
        self.assertEqual((exchange.requested_model, exchange.returned_model, exchange.response_id),
                         ('gpt-6-astra', 'gpt-6-astra', 'resp_synthetic_fixture_0001'))
        self.assertIn(b'"input_tokens": 2412', exchange.response_bytes)  # history, never new usage

    def test_requests_and_readings_are_the_live_adapters_own(self):
        for name, live_class, fixture in (('astra', AstraParticipant, 'astra-colonoscopy.response.json'),
                                          ('fable', FableParticipant, 'fable-colonoscopy.response.json')):
            with self.subTest(name=name):
                replay, live = ReplayParticipant(name, self.tmp), live_class(self.tmp / 'never-read.env')
                self.assertIsInstance(replay, Participant)
                self.assertEqual((replay.adapter_version, replay.requested_model, replay.endpoint),
                                 (live.adapter_version, live.requested_model, ''))
                replayed, built = (replay.build_request(NOTE, PAGES, 'pdf', ORIGINAL),
                                   live.build_request(NOTE, PAGES, 'pdf', ORIGINAL))
                self.assertEqual((replayed.provider, replayed.body, replayed.canonical_sha256, replayed.contexts),
                                 (built.provider, built.body, built.canonical_sha256, built.contexts))
                raw = fixture_bytes(fixture)
                self.assertEqual(replay.read(replayed, raw), live.read(built, raw))

    def test_each_participant_replays_only_its_own_recordings(self):
        request = self.astra.build_request(NOTE, PAGES, 'paste', None)
        self.record('astra', request, self.raw)
        fable = ReplayParticipant('fable', self.tmp)
        (self.tmp / 'fable').mkdir()
        exchange = self.send(fable, fable.build_request(NOTE, PAGES, 'paste', None))
        self.assertEqual((exchange.outcome, exchange.error), ('not_sent', 'No recorded response for this request.'))

    def test_a_pdf_request_replays_only_with_its_verified_original(self):
        request = self.astra.build_request(NOTE, PAGES, 'pdf', ORIGINAL)
        self.record('astra', request, self.raw)
        self.assertEqual(self.send(self.astra, request, original_bytes=PDF).outcome, 'succeeded')
        for original_bytes, expect in ((None, 'none was given'), (PDF + b'x', 'does not match')):
            with self.subTest(expect=expect):
                exchange = self.send(self.astra, request, original_bytes=original_bytes)
                self.assertEqual((exchange.outcome, exchange.sent), ('not_sent', False))
                self.assertIn(expect, exchange.error)

    def test_missing_unavailable_symlinked_or_oversized_recordings_are_not_sent(self):
        request = self.astra.build_request(NOTE, PAGES, 'paste', None)
        exchange = self.send(ReplayParticipant('astra', self.tmp / 'absent'), request)
        self.assertEqual((exchange.outcome, exchange.error), ('not_sent', 'The replay directory is not available.'))
        exchange = self.send(self.astra, request)
        self.assertEqual((exchange.outcome, exchange.error), ('not_sent', 'The replay directory is not available.'))
        (self.tmp / 'astra').mkdir()
        self.assertEqual(self.send(self.astra, request).error, 'No recorded response for this request.')
        target = write_file(self.tmp / 'elsewhere.json', self.raw)
        (self.tmp / 'astra' / f'{request.canonical_sha256}.json').symlink_to(target)
        self.assertEqual(self.send(self.astra, request).error,
                         'The recorded response is a symbolic link; it was refused.')
        small_dir = self.tmp / 'small'
        small = ReplayParticipant('astra', small_dir, max_response_bytes=100)
        (small_dir / 'astra').mkdir(parents=True)
        write_file(small_dir / 'astra' / f'{request.canonical_sha256}.json', self.raw)
        self.assertEqual(self.send(small, request).error, 'The recorded response is larger than 100 bytes.')

    def test_altered_foreign_or_undated_requests_are_not_replayed(self):
        request = self.astra.build_request(NOTE, PAGES, 'paste', None)
        self.record('astra', request, self.raw)
        altered = copy.deepcopy(request)
        altered.body['input'][0]['content'][-1]['text'] += ' altered'
        foreign = ReplayParticipant('fable', self.tmp).build_request(NOTE, PAGES, 'paste', None)
        for candidate, deadline, expect in ((altered, 5, 'does not match its recorded hash'),
                                            (foreign, 5, 'different provider'), (request, 0, 'deadline')):
            with self.subTest(expect=expect):
                exchange = self.send(self.astra, candidate, deadline_s=deadline)
                self.assertEqual((exchange.outcome, exchange.sent), ('not_sent', False))
                self.assertIn(expect, exchange.error)

    def test_an_empty_directory_setting_never_means_the_working_directory(self):
        for empty in ('', None):
            with self.subTest(empty=empty), self.assertRaises(ValueError):
                ReplayParticipant('astra', empty)
        with self.assertRaises(ValueError):
            ReplayParticipant('corti', self.tmp)
