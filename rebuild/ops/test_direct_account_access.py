"""Focused owner-decision and exact gate-retirement controls; no host actions."""
from pathlib import Path
from contextlib import contextmanager
import hashlib
import io
import json
import tempfile
from email.message import Message
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ops import direct_account_access as act
from ops import email_activation, owner_normal_origin, preview_activation, word_milestone_delivery
from ops import preview_browser_tls

PRIOR = 'a' * 40
TARGET = 'b' * 40
ENV = (b'# preserved operator comment\nQUILLMD_RELEASE_SHA="' + PRIOR.encode() + b'"\n'
    b'QUILLMD_APP_BASE_URL="https://app.quillmd.com:9443"\n'
    b'QUILLMD_TRUST_PROXY="1"\nQUILLMD_PREVIEW_AUTH_ENABLED="1"\n'
    b'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="1"\n'
    b'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME="synthetic-obsolete"\n'
    b'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD="synthetic-obsolete-secret-only"\n'
    b'QUILLMD_DB_PASSWORD="synthetic-unchanged-not-real"\n'
    b'QUILLMD_AI_MODEL="synthetic-label-unchanged"\n')
OLD_NORMAL = b'fictional old normal suffix\n'
OLD_LEGACY = b'fictional old legacy file\n'
PREFIX = b'fictional preserved unrelated ingress prefix\n'
ROOT = Path(__file__).resolve().parents[1]
NEW_NORMAL = (ROOT / 'deploy/owner-normal-https.conf').read_bytes()
NEW_LEGACY = (ROOT / 'deploy/email-private-https.conf').read_bytes()


@contextmanager
def native_fixture_identity(uid=1000):
    """Qualify only fictional metadata; CI's runner may have a different UID."""
    original_fstat, original_lstat = act.os.fstat, Path.lstat
    def identity(row):
        names=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
        return SimpleNamespace(**{name:getattr(row,name) for name in names},st_uid=uid,st_gid=uid)
    with patch.object(act.os,'fstat',side_effect=lambda fd:identity(original_fstat(fd))), \
         patch.object(Path,'lstat',lambda path:identity(original_lstat(path))):
        yield


class DirectAccountEnvironmentTests(unittest.TestCase):
    def test_exact_seven_keys_change_and_unrelated_bytes_are_preserved(self):
        out = act.environment(ENV, PRIOR, TARGET)
        parsed = act.values(out)
        self.assertEqual(parsed[act.MARKER], '1')
        self.assertEqual(parsed['QUILLMD_RELEASE_SHA'], TARGET)
        self.assertEqual(parsed['QUILLMD_PREVIEW_AUTH_ENABLED'], '0')
        self.assertEqual(parsed['QUILLMD_APP_BASE_URL'], act.ORIGIN)
        self.assertEqual(parsed['QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'], '1')
        self.assertNotIn('QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME', parsed)
        self.assertNotIn('QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD', parsed)
        for unchanged in (b'# preserved operator comment\n',
                          b'QUILLMD_DB_PASSWORD="synthetic-unchanged-not-real"\n',
                          b'QUILLMD_AI_MODEL="synthetic-label-unchanged"\n'):
            self.assertIn(unchanged, out)
        self.assertNotIn(b'synthetic-obsolete', out)

    def test_duplicate_controlled_key_stale_release_live_mode_or_untrusted_transport_refuse(self):
        cases = (ENV + b'QUILLMD_APP_BASE_URL="https://app.quillmd.com"\n',
                 ENV.replace(PRIOR.encode(), TARGET.encode()),
                 ENV + b'QUILLMD_DATA_MODE="live"\n',
                 ENV.replace(b'QUILLMD_TRUST_PROXY="1"', b'QUILLMD_TRUST_PROXY="0"'),
                 ENV.replace(b'https://app.quillmd.com:9443', b'https://outside.invalid'),
                 ENV + b'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED="unexpected"\n',
                 ENV.rstrip(b'\n'))
        for raw in cases:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                act.environment(raw, PRIOR, TARGET)
        for previous, target in ((PRIOR[:12], TARGET), (PRIOR, TARGET.upper()), (None, TARGET)):
            with self.assertRaises(ValueError):
                act.environment(ENV, previous, target)

    def test_historical_gate_renderers_refuse_installed_direct_account_policy(self):
        installed = act.environment(ENV, PRIOR, TARGET)
        controls = (
            lambda: preview_activation.environment(installed, TARGET, PRIOR, True),
            lambda: email_activation.updated_environment(installed, {}),
            lambda: owner_normal_origin.controlled_environment(installed, TARGET, PRIOR, enabled=True),
            lambda: word_milestone_delivery.render_environment(installed, TARGET),
        )
        for control in controls:
            with self.subTest(control=control), self.assertRaisesRegex(Exception,
                    'owner_direct_account_decision_supersedes_shared_preview_gate'):
                control()

    def test_missing_marker_keeps_only_historical_uninstalled_fixture_compatible(self):
        self.assertIsNone(act.reject_legacy_environment(ENV))
        with self.assertRaisesRegex(ValueError, 'supersedes_shared_preview_gate'):
            act.reject_legacy_environment(act.environment(ENV, PRIOR, TARGET))

    def test_leading_whitespace_controls_rewrite_once_but_quoted_and_multiline_bindings_refuse(self):
        whitespace = ENV.replace(b'QUILLMD_RELEASE_SHA=', b' \texport QUILLMD_RELEASE_SHA=')
        out = act.environment(whitespace, PRIOR, TARGET)
        self.assertEqual(out.count(b'QUILLMD_RELEASE_SHA='), 1)
        self.assertEqual(act.values(out)['QUILLMD_RELEASE_SHA'], TARGET)
        for raw in (ENV+b"'QUILLMD_RELEASE_SHA'='"+PRIOR.encode()+b"'\n",
                    ENV+b"'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED'='1'\n",
                    ENV+b'QUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED="1"\nQUILLMD_DIRECT_ACCOUNT_ACCESS_ENABLED="0"\n',
                    ENV.replace(b'QUILLMD_APP_BASE_URL="https://app.quillmd.com:9443"',
                        b'QUILLMD_APP_BASE_URL="https://app.quillmd.com:9443\n"')):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                act.environment(raw, PRIOR, TARGET)


class DirectAccountIngressTests(unittest.TestCase):
    def render(self, **changes):
        values = dict(original=PREFIX+OLD_NORMAL, legacy=OLD_LEGACY,
            old_normal=OLD_NORMAL, old_legacy=OLD_LEGACY,
            new_normal=NEW_NORMAL, new_legacy=NEW_LEGACY)
        values.update(changes)
        return act.render_ingress(**values)

    def test_only_declared_suffix_and_retired_port_change(self):
        out = self.render()
        self.assertEqual(set(out), set(act.INGRESS_PATHS))
        self.assertEqual(out[act.INGRESS_PATHS[0]], PREFIX+NEW_NORMAL)
        self.assertEqual(out[act.INGRESS_PATHS[1]], NEW_LEGACY)
        self.assertNotIn(b'auth_basic', NEW_NORMAL)
        self.assertNotIn(b'__Host-quillmd_preview', NEW_NORMAL)
        self.assertIn(b'proxy_set_header X-QuillMD-Account "1";', NEW_NORMAL)
        self.assertIn(b'return 303 https://app.quillmd.com/login/;', NEW_LEGACY)
        self.assertNotIn(b'proxy_pass', NEW_LEGACY)
        self.assertNotIn(b'$request_uri', NEW_LEGACY)
        self.assertNotIn(b'$args', NEW_LEGACY)

    def test_missing_duplicate_stale_or_changed_originals_are_refused(self):
        for changes in ({'original': PREFIX}, {'original': OLD_NORMAL+PREFIX+OLD_NORMAL},
                        {'legacy': OLD_LEGACY+b'extra'}, {'original': PREFIX+OLD_NORMAL+b'extra'}):
            with self.subTest(changes=sorted(changes)), self.assertRaises(ValueError):
                self.render(**changes)

    def test_gate_cookie_header_basic_auth_query_replay_and_wrong_upstream_refuse(self):
        cases = (
            {'new_normal': NEW_NORMAL+b'auth_basic "retired";\n'},
            {'new_normal': NEW_NORMAL+b'# __Host-quillmd_preview\n'},
            {'new_normal': NEW_NORMAL.replace(b'X-QuillMD-Account "1"', b'X-QuillMD-Preview "1"')},
            {'new_normal': NEW_NORMAL.replace(b'http://127.0.0.1:9130;', b'http://127.0.0.1:9141;')},
            {'new_legacy': NEW_LEGACY+b'proxy_pass http://127.0.0.1:9130;\n'},
            {'new_legacy': NEW_LEGACY.replace(b'/login/;', b'/login/?next=$request_uri;')},
        )
        for changes in cases:
            with self.subTest(changes=sorted(changes)), self.assertRaises(ValueError):
                self.render(**changes)

    def test_helper_refuses_unknown_path_metadata_hash_or_multi_file_scope(self):
        original = {act.INGRESS_PATHS[0]: PREFIX+OLD_NORMAL, act.INGRESS_PATHS[1]: OLD_LEGACY}
        candidate = self.render()
        metadata = {path: {'uid':0,'gid':0,'mode':0o644,'device':1,'inode':index+10,
            'sha256':hashlib.sha256(raw).hexdigest()} for index,(path,raw) in enumerate(original.items())}
        code = act.ingress_helper_code(original, candidate, metadata, 'a'*16)
        self.assertIn("{'quillmd','quillmd-email-preview'}", code)
        self.assertIn("['/usr/sbin/nginx','-t']", code)
        self.assertNotIn('restart', code)
        wrong = {**metadata, '/etc/nginx/sites-available/unrelated': dict(next(iter(metadata.values())))}
        with self.assertRaises(ValueError):
            act.ingress_helper_code(original, candidate, wrong, 'a'*16)
        metadata[act.INGRESS_PATHS[0]]['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            act.ingress_helper_code(original, candidate, metadata, 'a'*16)


class OwnerDecisionTests(unittest.TestCase):
    def fixture(self, directory):
        path = Path(directory)/'decision.json'
        raw = json.dumps({'base_installed_revision':'0042cf7f7f0b437b3baeaf1c40dab66912294fef',
            'provider_calls_allowed':0,'password_reset_allowed':False,'public_signup_allowed':False,
            'other_projects_changes_allowed':False},sort_keys=True).encode()
        path.write_bytes(raw); path.chmod(0o600)
        return path, raw

    def test_exact_scope_hash_and_protected_identity_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path, raw = self.fixture(directory)
            with patch.object(act, 'DECISION', path), patch.object(act, 'DECISION_SHA256', act.sha(raw)), \
                 native_fixture_identity():
                self.assertEqual(act.owner_decision()['sha256'], act.sha(raw))
                path.chmod(0o644)
                with self.assertRaisesRegex(ValueError, 'protected_evidence_identity'):
                    act.owner_decision()
                path.chmod(0o600); path.write_bytes(raw+b' ')
                with self.assertRaisesRegex(ValueError, 'exact_owner_decision'):
                    act.owner_decision()
                path.unlink()
                with self.assertRaises(FileNotFoundError):
                    act.owner_decision()

    def test_matching_hash_cannot_authorize_expanded_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            path, raw = self.fixture(directory)
            decision=json.loads(raw); decision['public_signup_allowed']=True
            expanded=json.dumps(decision).encode(); path.write_bytes(expanded)
            with patch.object(act,'DECISION',path), patch.object(act,'DECISION_SHA256',act.sha(expanded)), \
                 native_fixture_identity():
                with self.assertRaisesRegex(ValueError,'owner_decision_scope'):
                    act.owner_decision()

    def test_wrong_owner_hardlink_symlink_and_oversized_evidence_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path,raw=self.fixture(directory)
            with native_fixture_identity(uid=1001), self.assertRaisesRegex(ValueError,'protected_evidence_identity'):
                act.protected(path,16384)
            with native_fixture_identity(), self.assertRaisesRegex(ValueError,'protected_evidence_race'):
                act.protected(path,1)
            link=Path(directory)/'alias.json';link.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'canonical_evidence_path'):
                act.protected(link,16384)
            link.unlink();act.os.link(path,link)
            with native_fixture_identity(), self.assertRaisesRegex(ValueError,'protected_evidence_identity'):
                act.protected(path,16384)

    def test_existing_marker_refuses_legacy_executor_even_when_decision_missing_or_corrupt(self):
        installed=act.environment(ENV,PRIOR,TARGET)
        for exception in (FileNotFoundError('synthetic missing'), ValueError('synthetic corrupt')):
            with patch.object(act,'protected',return_value=installed), \
                 patch.object(act,'owner_decision',side_effect=exception) as decision:
                with self.assertRaises(type(exception)):
                    act.refuse_legacy_operation()
                decision.assert_called_once_with()
        with patch.object(act,'protected',return_value=installed), \
             patch.object(act,'owner_decision',return_value={'synthetic':'scope verified'}):
            with self.assertRaisesRegex(ValueError,'supersedes_shared_preview_gate'):
                act.refuse_legacy_operation()


class IsolatedAccountTLSProxyTests(unittest.TestCase):
    def fixture(self, host=preview_browser_tls.ORIGIN_HOST, path='/login/'):
        headers=Message()
        for key,value in {'Host':host,'Content-Length':'0','Authorization':'synthetic-spoof',
             'Proxy-Authorization':'synthetic-spoof','X-QuillMD-Preview':'1',
             'X-QuillMD-Account':'attacker','X-Forwarded-Proto':'http',
             'X-Forwarded-For':'203.0.113.7','X-Real-IP':'203.0.113.7','Connection':'keep-alive'}.items():
            headers[key]=value
        return SimpleNamespace(headers=headers,path=path,command='GET',rfile=io.BytesIO(),
            wfile=io.BytesIO(),send_response=unittest.mock.MagicMock(),
            send_header=unittest.mock.MagicMock(),end_headers=unittest.mock.MagicMock(),
            send_error=unittest.mock.MagicMock())

    def test_harness_overwrites_exact_transport_and_strips_spoofed_headers(self):
        request=self.fixture()
        with patch.object(preview_browser_tls.http.client,'HTTPConnection') as connection:
            response=connection.return_value.getresponse.return_value
            response.status=200;response.read.return_value=b'synthetic account page';response.getheaders.return_value=[]
            preview_browser_tls.Proxy.handle_request(request)
            connection.assert_called_once_with('127.0.0.1',19430,timeout=30)
            sent=connection.return_value.request.call_args.kwargs['headers']
            self.assertEqual(sent['Host'],'app.quillmd.com')
            self.assertEqual(sent['X-QuillMD-Account'],'1')
            self.assertEqual(sent['X-Forwarded-Proto'],'https')
            self.assertEqual(sent['X-Real-IP'],'127.0.0.1')
            for key in ('authorization','proxy-authorization','x-quillmd-preview','x-forwarded-for'):
                self.assertNotIn(key,{name.lower() for name in sent})
            connection.return_value.close.assert_called_once_with()
        request.send_error.assert_not_called()

    def test_wrong_host_and_double_slash_refuse_before_upstream(self):
        for host,path in (('app.quillmd.com','/login/'),
                          ('outside.invalid:19443','/login/'),
                          (preview_browser_tls.ORIGIN_HOST,'//outside.invalid/')):
            request=self.fixture(host,path)
            with patch.object(preview_browser_tls.http.client,'HTTPConnection') as connection:
                preview_browser_tls.Proxy.handle_request(request)
                request.send_error.assert_called_once_with(400)
                connection.assert_not_called()
