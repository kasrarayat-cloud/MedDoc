"""Prospective signing identity controls; no providers or database connections."""
import dataclasses
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from ops import provider_campaign as pc, standing_qa as st, standing_qa_signing as sk
from .test_standing_qa import Base, RESTRICTED_SAMPLE, RUNNER_COMMIT, SYNTHETIC_KEY, fixture_text, parse, rights_ledger, scratch

_network = None


def setUpModule():
    global _network
    _network = patch.object(socket.socket, 'connect', side_effect=AssertionError('No database or network in signing tests'))
    _network.start()


def tearDownModule():
    _network.stop()


class QASigningKeyTests(Base):
    def own_campaign(self, persistent=True):
        root = scratch(self) / 'campaign'
        root.mkdir(mode=0o700)
        for name in ('access', 'runs', 'preflight', 'qa-state', 'tmp'):
            (root / name).mkdir(mode=0o700)
        rights, digest = rights_ledger(self, RESTRICTED_SAMPLE)
        declaration = dataclasses.replace(parse(self), root=str(root),
            restricted_inputs_ledger=rights, restricted_inputs_ledger_sha256=digest,
            qa_signing_key_file=str(root / 'access' / sk.KEY_NAME) if persistent else None)
        campaign = st.StandingCampaign(declaration)
        campaign.ledger.acquire()
        self.addCleanup(campaign.ledger.release)
        return campaign

    def prepare(self):
        campaign = self.own_campaign()
        key, record = st.signing_identity(campaign, create=True)
        return campaign, key, record

    def replace_key_and_sidecar(self, campaign):
        path = Path(campaign.declaration.qa_signing_key_file)
        path.write_bytes(b'S' * 64)
        record = json.loads((path.parent / sk.RECORD_NAME).read_text())
        record['sha256'] = hashlib.sha256(b'S' * 64).hexdigest()
        (path.parent / sk.RECORD_NAME).write_text(json.dumps(record))

    def test_optional_declaration_is_exact_and_cannot_read_another_route(self):
        text = fixture_text()
        root = '/nonexistent/standing-qa-test-root'
        line = f'qa_signing_key_file: {root}/access/{sk.KEY_NAME}\n'
        self.assertIsNone(parse(self).qa_signing_key_file)
        self.assertEqual(parse(self, text + line).qa_signing_key_file, f'{root}/access/{sk.KEY_NAME}')
        for suffix in [line + line, '- ' + line, line.upper(),
                       line.replace('/access/', '/credential/'), line.replace(root, '/other'),
                       line.replace(sk.KEY_NAME, '.env'), line.replace('/access/', '/access/../access/')]:
            with self.subTest(suffix=suffix[:80]), self.assertRaises(pc.Refused):
                parse(self, text + suffix)

    def test_absence_keeps_random_process_keys_and_adds_no_historical_fields(self):
        campaign = self.own_campaign(False)
        with patch.object(sk, '_access', side_effect=AssertionError('No signing file read for old declarations')):
            self.assertEqual(st.signing_identity(campaign), (None, None))
            self.open_model_check_run(campaign)
            attempt = self.model_check_attempt(campaign)
            campaign.ledger.write_attempt(attempt)
            self.assertNotIn(sk.FIELD, campaign.ledger.rows()[0][0])
            self.assertNotIn(sk.FIELD, campaign.runs.current())
            environments = [st.request_environment(SYNTHETIC_KEY, campaign.declaration, campaign.root, 'synthetic-password',
                {'command': 'run'}, st.STAGE_FLAGS['model_check'], {'declaration': 'synthetic', 'commit': RUNNER_COMMIT})
                for _ in range(2)]
            self.assertTrue(environments[0]['QUILLMD_SECRET_KEY'] != environments[1]['QUILLMD_SECRET_KEY'])
        self.assertEqual(list((campaign.root / 'access').iterdir()), [])

    def test_prepare_is_locked_once_and_reused_without_secret_evidence(self):
        campaign = self.own_campaign()
        campaign.ledger.release()
        with self.assertRaisesRegex(pc.Refused, 'lock'):
            st.signing_identity(campaign, create=True)
        campaign.ledger.acquire()
        key, record = st.signing_identity(campaign, create=True)
        path = Path(campaign.declaration.qa_signing_key_file)
        before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in path.parent.iterdir()}
        other, reused = st.signing_identity(campaign, create=True)
        self.assertTrue(other == key)
        self.assertEqual(record, reused)
        self.assertTrue(before == {p.name: (p.stat().st_ino, p.read_bytes()) for p in path.parent.iterdir()})
        self.assertTrue(key not in json.dumps(record))
        self.assertEqual((path.stat().st_mode & 0o777, path.stat().st_nlink), (0o600, 1))
        self.assertEqual(record['sha256'], hashlib.sha256(key.encode()).hexdigest())

    def test_current_transcript_confirmation_survives_same_key_and_rejects_another_key(self):
        campaign, key, _ = self.prepare()
        environment = st.request_environment(SYNTHETIC_KEY, campaign.declaration, campaign.root, 'synthetic-password',
            {'command': 'run'}, st.STAGE_FLAGS['model_check'], {'declaration': 'synthetic', 'commit': RUNNER_COMMIT})
        self.assertTrue(environment['QUILLMD_SECRET_KEY'] == key)
        source = '''import json,sys
from types import SimpleNamespace
from django.conf import settings
from django.test.utils import override_settings
from core import transcript_context as c
key=json.loads(sys.stdin.read())
settings.configure(SECRET_KEY=key,SECRET_KEY_FALLBACKS=[])
notes="Examination mild swelling over the left lateral ankle."
d=c.digest(notes)
review=SimpleNamespace(pk="review",job_id="job",reviewed_by_id="actor",source_revision=1,
source_sha256=d,raw_sha256=d,result_sha256=d,reviewed_sha256=d,span_start=0,span_end=len(notes))
token=c.token_for(review)
same=c.verified(notes,token) is not None
with override_settings(SECRET_KEY="distinct-synthetic-test-key"):
 other=c.verified(notes,token) is not None
print(json.dumps({"same":same,"other":other}))
'''
        result = subprocess.run([sys.executable, '-B', '-c', source], cwd=st.REBUILD,
            input=json.dumps(environment['QUILLMD_SECRET_KEY']), capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'same': True, 'other': False})
        self.assertTrue(key not in result.stdout + result.stderr)

    def test_existing_random_attempt_or_activity_cannot_be_resigned(self):
        campaign = self.own_campaign(False)
        self.open_model_check_run(campaign)
        campaign.ledger.write_attempt(self.model_check_attempt(campaign))
        campaign.declaration = dataclasses.replace(campaign.declaration,
            qa_signing_key_file=str(campaign.root / 'access' / sk.KEY_NAME))
        with self.assertRaisesRegex(pc.Refused, 'before this campaign has any activity'):
            st.signing_identity(campaign, create=True)
        self.assertFalse((campaign.root / 'access' / sk.KEY_NAME).exists())
        for directory in ('preflight', 'qa-state'):
            own = self.own_campaign()
            (own.root / directory / 'old-evidence').write_bytes(b'SYNTHETIC')
            with self.subTest(directory=directory), self.assertRaises(pc.Refused):
                st.signing_identity(own, create=True)

    def test_first_run_and_attempt_pin_refuses_both_key_and_sidecar_replacement(self):
        campaign, _, record = self.prepare()
        self.open_model_check_run(campaign)
        attempt = self.model_check_attempt(campaign)
        campaign.ledger.write_attempt(attempt)
        self.completed(campaign, attempt['number'])
        self.assertEqual(campaign.runs.current()[sk.FIELD], record)
        self.assertEqual(campaign.ledger.rows()[0][0][sk.FIELD], record)
        self.replace_key_and_sidecar(campaign)
        for operation in [lambda: st.signing_identity(campaign), lambda: campaign.stage_open('mapping'),
                          lambda: st.request_environment(SYNTHETIC_KEY, campaign.declaration, campaign.root, 'unused',
                            {}, {}, {'declaration': 'synthetic', 'commit': RUNNER_COMMIT})]:
            with self.assertRaisesRegex(pc.Refused, 'earlier preflight, run or attempt'):
                operation()
        self.assertEqual(len(campaign.ledger.rows()), 1)

    def test_last_attempt_door_refuses_forged_identity_and_dropping_opt_in(self):
        campaign, _, record = self.prepare()
        self.open_model_check_run(campaign)
        forged = self.model_check_attempt(campaign, **{sk.FIELD: {**record, 'sha256': '0'*64}})
        with self.assertRaisesRegex(pc.Refused, 'another QA signing identity'):
            campaign.ledger.write_attempt(forged)
        campaign.declaration = dataclasses.replace(campaign.declaration, qa_signing_key_file=None)
        with self.assertRaisesRegex(pc.Refused, 'earlier preflight, run or attempt'):
            campaign.ledger.write_attempt(self.model_check_attempt(campaign))
        self.assertEqual(campaign.ledger.rows(), [])

    def test_request_process_cannot_pin_changed_file_while_using_previous_key(self):
        campaign, key, _ = self.prepare()
        self.replace_key_and_sidecar(campaign)
        with patch.dict(os.environ, {st.CONTEXT_VARIABLE: '{}', 'QUILLMD_SECRET_KEY': key}):
            with self.assertRaisesRegex(pc.Refused, 'request process does not carry'):
                self.open_model_check_run(campaign)
        self.assertEqual(campaign.runs.listing(), [])

    def test_interrupted_preflight_pin_precedes_network_and_cannot_be_replaced(self):
        campaign, _, record = self.prepare()
        folder = campaign.root / 'preflight' / '001'
        folder.mkdir(mode=0o700)
        pc.write_new(folder / 'qa-signing-key.json', record)
        self.assertEqual(st.signing_identity(campaign)[1], record)
        self.replace_key_and_sidecar(campaign)
        with self.assertRaisesRegex(pc.Refused, 'earlier preflight, run or attempt'):
            st.run_preflight(campaign, secret=SYNTHETIC_KEY, transport=object())
        self.assertFalse((campaign.root / 'preflight' / '002').exists())

    def test_real_preflight_guard_records_binding_before_simulated_transport(self):
        import httpx
        campaign, key, record = self.prepare()
        called = []

        def receive(request):
            called.append(request.method)
            self.assertEqual(pc.read_json(campaign.root / 'preflight' / '001' / 'qa-signing-key.json'), record)
            self.assertTrue(key not in request.content.decode())
            return httpx.Response(200, request=request, json={'id': campaign.declaration.model, 'type': 'model'})

        result = st.run_preflight(campaign, secret=SYNTHETIC_KEY, transport=httpx.MockTransport(receive))
        self.assertEqual(called, ['GET'])
        self.assertEqual(result[sk.FIELD], record)
        self.assertTrue(result['matches_declared'])
        self.assertTrue(key not in json.dumps(result))
        self.assertEqual(st.signing_identity(campaign)[1], record)

    def test_key_file_symlink_hardlink_mode_and_parent_alias_are_refused(self):
        for attack in ('symlink', 'hardlink', 'mode', 'parent-alias', 'access-mode', 'campaign-parent-mode'):
            campaign, _, _ = self.prepare()
            path = Path(campaign.declaration.qa_signing_key_file)
            if attack == 'symlink':
                target = path.with_name('kept-original'); path.rename(target); path.symlink_to(target)
            elif attack == 'hardlink':
                os.link(path, path.with_name('second-name'))
            elif attack == 'mode':
                path.chmod(0o644)
            elif attack == 'access-mode':
                path.parent.chmod(0o750)
            elif attack == 'campaign-parent-mode':
                campaign.root.parent.chmod(0o750)
            else:
                alias = campaign.root.with_name('campaign-alias'); alias.symlink_to(campaign.root, target_is_directory=True)
                campaign.root = alias
                campaign.declaration = dataclasses.replace(campaign.declaration, root=str(alias),
                    qa_signing_key_file=str(alias / 'access' / sk.KEY_NAME))
            with self.subTest(attack=attack), self.assertRaises(pc.Refused):
                st.signing_identity(campaign)

    def test_wrong_campaign_binding_and_incomplete_key_preparation_refuse(self):
        campaign, _, record = self.prepare()
        sidecar = campaign.root / 'access' / sk.RECORD_NAME
        sidecar.write_text(json.dumps({**record, 'campaign': 'another-campaign'}))
        with self.assertRaisesRegex(pc.Refused, 'campaign identity has changed'):
            st.signing_identity(campaign)
        own = self.own_campaign()
        key = own.root / 'access' / sk.KEY_NAME
        key.write_bytes(b'S' * 64); key.chmod(0o600)
        self.assertIsNotNone(st.signing_identity(own, create=True)[1])
        sidecar = key.parent / sk.RECORD_NAME
        sidecar.write_bytes(b'{')
        with self.assertRaisesRegex(pc.Refused, 'cannot be read'):
            st.signing_identity(own, create=True)
