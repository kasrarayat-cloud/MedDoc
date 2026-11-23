"""Offline tests of release 2 of the admin.quillmd.com move (ops/install.py; ops/INSTALL.md, ingress, ingress-rollback,
the coupling invariant): the quillmd vhost's two pinned states and their derivation, the coupling invariant, the
two-file write as the ingress and ingress-rollback phases drive it - the REAL phases, publish_vhost, vhost_state,
recorded_vhosts and the REAL root helper body (H_VHOST, executed in-process on temporary directories) - the cert phase
for a served site, preflight's and verify's new checks, the own-host checks (routing, check-cotenants' skip, the
revision-aware admin answers through the public path and on the loopback port).

No Docker, sudo, nginx, network or live port: the host guard of test_install refuses every one of them.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v
"""
import base64
import hashlib
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import (EARLIER_REVISION, TemporaryDirectoryTest, coupled, guard_host, pre_admin,  # noqa: E402
                          release_host, rendered, run_body)
from test_install_bluegreen import BlueGreenWorld, run_app, switch_back_args  # noqa: E402

REVISION = 'a' * 40   # the revision being installed (release 2)
SERVING = 'c' * 40    # the web the ingress finds serving (release 1)
OLD = 'b' * 40        # a revision before release 1
ADMIN, CPT = install.ADMIN_HOST, install.DOMAIN
QUILLMD_NAMES = ['admin.quillmd.com', 'app.quillmd.com', 'pro.quillmd.com', 'quillmd.com', 'www.quillmd.com']
POLICY = {'strict-transport-security': ['max-age=31536000'], 'x-content-type-options': ['nosniff'],
          'referrer-policy': ['same-origin'], 'x-robots-tag': ['noindex, nofollow']}


def setUpModule():
    guard_host()


def tearDownModule():
    release_host()


def sha(data) -> str:
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def synthetic_quillmd():
    """(before, after): a quillmd vhost of thirty lines with admin named on line 13 (its :80 block) and line 26 (its
    :443 block), and the after state built here line by line - independently of quillmd_bytes."""
    lines = [f'# synthetic quillmd vhost, line {number}' for number in range(1, 31)]
    lines[12] = '    server_name quillmd.com www.quillmd.com app.quillmd.com admin.quillmd.com pro.quillmd.com;'
    lines[25] = install.QUILLMD_ADMIN_LINE.decode()
    before = '\n'.join(lines) + '\n'
    lines[25] = install.QUILLMD_FREED_LINE.decode()
    return before.encode(), ('\n'.join(lines) + '\n').encode()


def health(revision):
    return {'status': 'ok', 'service': 'cpt-studio', 'data_mode': 'synthetic-only', 'database': 'ok',
            'release': revision}


# --- the quillmd vhost's two states ---------------------------------------------------------------------------------

class QuillmdVhostTests(unittest.TestCase):
    def setUp(self):
        self.before, self.after = synthetic_quillmd()
        patcher = mock.patch.multiple(install, QUILLMD_VHOST_BEFORE=sha(self.before), QUILLMD_VHOST_AFTER=sha(self.after))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_after_state_is_line_26_replaced_whole_and_the_way_back_its_inverse(self):
        self.assertEqual(install.quillmd_bytes(self.before, 'after'), self.after)
        self.assertEqual(install.quillmd_bytes(self.after, 'before'), self.before)
        self.assertIs(install.quillmd_bytes(self.before, 'before'), self.before)  # already there: unchanged
        self.assertIs(install.quillmd_bytes(self.after, 'after'), self.after)
        before, after = self.before.split(b'\n'), self.after.split(b'\n')
        self.assertEqual([index + 1 for index, (a, b) in enumerate(zip(before, after)) if a != b], [26])
        self.assertIn(b'admin.quillmd.com', after[install.QUILLMD_ACME_LINE_NUMBER - 1])  # the :80 route stays

    def test_any_other_shape_is_refused_before_anything_is_written(self):
        lines = self.before.split(b'\n')
        twice = list(lines)
        twice[27] = install.QUILLMD_ADMIN_LINE  # the full line a second time
        moved = list(lines)
        moved[24], moved[25] = moved[25], moved[24]  # the line, but at 25
        trailing = list(lines)
        trailing[25] = install.QUILLMD_ADMIN_LINE + b'  # a comment'  # the substring, not the full line
        acme = list(lines)
        acme[12] = acme[12].replace(b' admin.quillmd.com', b'')  # a file whose :80 line differs is another file
        cases = {'the line twice': b'\n'.join(twice), 'the line elsewhere': b'\n'.join(moved),
                 'the line with a comment': b'\n'.join(trailing), 'line 13 edited': b'\n'.join(acme)}
        for label, raw in cases.items():
            with self.subTest(label):
                with self.assertRaises(install.InstallError):  # in neither pinned state
                    install.quillmd_bytes(raw, 'after')
                with mock.patch.object(install, 'QUILLMD_VHOST_BEFORE', sha(raw)), \
                        self.assertRaisesRegex(install.InstallError, 'nothing was written'):
                    install.quillmd_bytes(raw, 'after')  # even pinned as the before state, the edit is refused
        with mock.patch.object(install, 'QUILLMD_VHOST_AFTER', '0' * 64), \
                self.assertRaisesRegex(install.InstallError, 'pinned after sha256'):
            install.quillmd_bytes(self.before, 'after')  # the result must be exactly the pinned after state
        # line 26 itself, not only the pins: a file whose line moved is refused even were both pins derived from it
        edited = list(moved)
        edited[24] = install.QUILLMD_FREED_LINE
        with mock.patch.multiple(install, QUILLMD_VHOST_BEFORE=sha(b'\n'.join(moved)),
                                 QUILLMD_VHOST_AFTER=sha(b'\n'.join(edited))), \
                self.assertRaisesRegex(install.InstallError, 'not once at line 26'):
            install.quillmd_bytes(b'\n'.join(moved), 'after')



class QuillmdPinTests(unittest.TestCase):
    """The pins as committed (no stand-in)."""

    def test_the_constants_are_the_designs(self):
        self.assertEqual(install.QUILLMD_ADMIN_LINE, b'    server_name quillmd.com www.quillmd.com admin.quillmd.com;')
        self.assertEqual(install.QUILLMD_FREED_LINE, b'    server_name quillmd.com www.quillmd.com;')
        self.assertEqual((install.QUILLMD_ADMIN_LINE_NUMBER, install.QUILLMD_ACME_LINE_NUMBER), (26, 13))
        self.assertEqual(install.QUILLMD_VHOST_BEFORE,
                         'e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638')  # the earlier single pin
        self.assertEqual(install.QUILLMD_VHOST_AFTER,
                         'b3ab66023547790e861c3d12b39d8b268de8748ba6453f830194a4df6e4a3dbb')

    @unittest.skipUnless((install.NGINX_AVAILABLE / 'quillmd').is_file(), 'not the QuillMD host')
    def test_the_pinned_after_state_is_the_live_file_with_line_26_replaced(self):
        # the derivation the constants' comment states, from the live file, read only
        raw = (install.NGINX_AVAILABLE / 'quillmd').read_bytes()
        if sha(raw) not in (install.QUILLMD_VHOST_BEFORE, install.QUILLMD_VHOST_AFTER):
            self.skipTest('the live quillmd vhost is in neither pinned state')
        before = install.quillmd_bytes(raw, 'before')
        after = install.quillmd_bytes(before, 'after')
        self.assertEqual((sha(before), sha(after)), (install.QUILLMD_VHOST_BEFORE, install.QUILLMD_VHOST_AFTER))
        self.assertEqual(install.quillmd_bytes(after, 'before'), before)


# --- the coupling invariant ------------------------------------------------------------------------------------------

class CouplingTests(TemporaryDirectoryTest):
    def test_the_coupling_table(self):
        before, after = install.QUILLMD_VHOST_BEFORE, install.QUILLMD_VHOST_AFTER
        table = {(before, False): 'before', (after, True): 'after', (before, True): 'both',
                 (after, False): 'uncoupled', ('0' * 64, False): 'uncoupled', ('0' * 64, True): 'uncoupled',
                 (before, None): 'uncoupled', (after, None): 'uncoupled', (None, False): 'uncoupled'}
        for (quillmd, admin), expected in table.items():
            with self.subTest(quillmd=str(quillmd)[:8], admin=admin):
                self.assertEqual(install.coupling(quillmd, admin), expected)

    def test_read_coupling_reads_the_quillmd_vhost_and_quillmd_cpt_on_the_host(self):
        available, enabled = self.tmp / 'available', self.tmp / 'enabled'
        available.mkdir()
        enabled.mkdir()
        before, after = synthetic_quillmd()
        (available / 'quillmd').write_bytes(before)
        with mock.patch.multiple(install, NGINX_AVAILABLE=available, NGINX_ENABLED=enabled,
                                 QUILLMD_VHOST_BEFORE=sha(before), QUILLMD_VHOST_AFTER=sha(after)):
            self.assertEqual(install.read_coupling()['coupling'], 'before')  # no quillmd-cpt names nothing
            (available / install.VHOST_NAME).write_text(pre_admin(rendered(9151)['https']))
            (enabled / install.VHOST_NAME).symlink_to(install.VHOST_LINK_TARGET)  # as the installer links it
            self.assertEqual(install.read_coupling()['coupling'], 'before')
            (available / install.VHOST_NAME).write_text(rendered(9151)['https'])
            self.assertEqual(install.read_coupling()['coupling'], 'both')
            (available / 'quillmd').write_bytes(after)
            self.assertEqual(install.read_coupling(),
                             {'quillmd_sha256': sha(after), 'names_admin': True, 'coupling': 'after'})
            # quillmd-cpt claims the admin host only as nginx loads it (check, round R2-1): without its sites-enabled
            # link nothing claims admin's :443, and behind a link that is not the installer's it cannot be told
            (enabled / install.VHOST_NAME).unlink()
            self.assertEqual(install.read_coupling(),
                             {'quillmd_sha256': sha(after), 'names_admin': False, 'coupling': 'uncoupled'})
            (enabled / install.VHOST_NAME).symlink_to(available / 'quillmd')
            self.assertEqual(install.read_coupling(),
                             {'quillmd_sha256': sha(after), 'names_admin': None, 'coupling': 'uncoupled'})
            (enabled / install.VHOST_NAME).unlink()
            (enabled / install.VHOST_NAME).write_text(rendered(9151)['https'])  # a file, not the installer's link
            self.assertEqual(install.read_coupling()['coupling'], 'uncoupled')
            (enabled / install.VHOST_NAME).unlink()
            (enabled / install.VHOST_NAME).symlink_to(install.VHOST_LINK_TARGET)
            self.assertEqual(install.read_coupling()['coupling'], 'after')
            (available / install.VHOST_NAME).unlink()
            (available / install.VHOST_NAME).symlink_to(available / 'quillmd')  # not a regular file: cannot be told
            self.assertEqual(install.read_coupling()['names_admin'], None)
            self.assertEqual(install.read_coupling()['coupling'], 'uncoupled')
            (available / install.VHOST_NAME).unlink()
            self.assertEqual(install.read_coupling()['coupling'], 'uncoupled')  # after, with nothing claiming admin
            (available / 'quillmd').unlink()
            self.assertEqual(install.read_coupling()['coupling'], 'uncoupled')

    def test_coupling_problem_names_the_state_and_the_way_on(self):
        self.assertEqual(install.coupling_problem(coupled('before')), '')
        self.assertEqual(install.coupling_problem(coupled('after')), '')
        self.assertIn('half way', install.coupling_problem(coupled('both')))
        self.assertIn('ingress-rollback', install.coupling_problem(coupled('after'), expected=('before',),
                                                                   remedy=install.AFTER_STATE_REMEDY))
        found = {'quillmd_sha256': '0' * 64, 'names_admin': None, 'coupling': 'uncoupled'}
        self.assertIn('cannot be read', install.coupling_problem(found))


# --- routing and the co-tenant script ------------------------------------------------------------------------------

class OwnRoutesTests(unittest.TestCase):
    def test_routing_diff_leaves_out_admins_443_alone(self):
        before = {f'https://{ADMIN}:443@127.0.0.1': {'status': 503, 'cert_sha256': 'quillmd'},
                  f'https://{ADMIN}:443@::1': {'status': 503, 'cert_sha256': 'quillmd'},
                  f'http://{ADMIN}:80@127.0.0.1': {'status': 301},
                  f'https://{CPT}:443@127.0.0.1': {'status': 302},
                  'https://app.quillmd.com:443@127.0.0.1': {'status': 302, 'cert_sha256': 'quillmd'}}
        moved = {key: value for key, value in before.items() if ':443@' not in key or ADMIN not in key}
        moved[f'https://{CPT}:443@127.0.0.1'] = {'status': 200}
        self.assertEqual(install.routing_diff(before, moved), [])  # admin's :443 left the quillmd vhost: its own
        changed = dict(moved, **{f'http://{ADMIN}:80@127.0.0.1': {'status': 200}})
        self.assertEqual(install.routing_diff(before, changed), [f'http://{ADMIN}:80@127.0.0.1'])  # QuillMD's :80
        for key in (f'https://x{ADMIN}:443@127.0.0.1', f'https://{ADMIN}.example:443@127.0.0.1',
                    f'https://{ADMIN}:9443@127.0.0.1', 'https://app.quillmd.com:443@127.0.0.1'):
            with self.subTest(key=key):
                self.assertEqual(install.routing_diff({**before, key: {'status': 1}}, {**before, key: {'status': 2}}),
                                 [key])

    def check(self, stdout, environ=None):
        completed = SimpleNamespace(returncode=0, stdout=stdout.encode(), stderr=b'')
        with mock.patch.object(install.subprocess, 'run', return_value=completed) as runner, \
                mock.patch.dict(os.environ, environ or {}):
            found = install.cotenant_check()
        return found, runner.call_args

    def test_check_cotenants_is_told_the_installers_own_host_and_never_the_operators_variable(self):
        found, call = self.check('', {'CPT_INSTALLER_SKIP_HOSTS': 'quillmd.com app.quillmd.com'})
        env = call.kwargs['env']
        self.assertEqual(env['CPT_INSTALLER_SKIP_HOSTS'], 'admin.quillmd.com')  # exactly the constant
        self.assertEqual(set(env), set(install.COMMAND_ENV) | {'CPT_INSTALLER_SKIP_HOSTS'})
        self.assertNotIn('CPT_INSTALLER_SKIP_HOSTS', install.COMMAND_ENV)  # nothing else is handed it
        self.assertEqual(call.args[0][-1], str(install.ROOT / 'scripts' / 'check-cotenants.sh'))
        self.assertEqual((found['skipped'], found['judged_skipped']), (['admin.quillmd.com'], []))

    def test_a_script_that_judged_the_skipped_host_is_seen(self):
        judged = ('HOST                   EXPECTED  OBSERVED\n'
                  '  🟢 quillmd.com          200       200\n'
                  '  🔴 admin.quillmd.com    503       302\n')
        found, _ = self.check(judged)
        self.assertEqual((found['observed'], found['judged_skipped']),
                         ({'quillmd.com': '200', 'admin.quillmd.com': '302'}, ['admin.quillmd.com']))
        skipped = ('HOST                   EXPECTED  OBSERVED\n'
                   '  🟢 quillmd.com          200       200\n'
                   '  ⚪ admin.quillmd.com    skipped (CPT_INSTALLER_SKIP_HOSTS)\n')
        self.assertEqual(self.check(skipped)[0]['judged_skipped'], [])

    def test_run_adds_a_callers_variables_to_the_fixed_environment_alone(self):
        completed = SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        before = dict(install.COMMAND_ENV)
        with mock.patch.object(install.subprocess, 'run', return_value=completed) as runner, \
                mock.patch.dict(os.environ, {'LEAK': 'operator'}):
            install.run(['true'], env={'ONE': '1'})
            install.run(['true'])
        self.assertEqual(runner.call_args_list[0].kwargs['env'], {**before, 'ONE': '1'})
        self.assertEqual(runner.call_args_list[1].kwargs['env'], before)
        self.assertEqual(install.COMMAND_ENV, before)


# --- which revisions serve the admin host ---------------------------------------------------------------------------

class CotenantScriptContractTests(TemporaryDirectoryTest):
    """The REAL scripts/check-cotenants.sh (QuillMD's), run by the REAL cotenant_check with curl stood in on the fixed
    PATH: the contract the installer relies on - the skipped host is printed without two codes (never judged), the
    floor is counted from the rows judged - and the two deliberate states the script accepts for admin across the move
    (QuillMD's notice; the console's sign-in on its own host), nothing else."""

    BASE = ('quillmd.com 200', 'www.quillmd.com 200', 'app.quillmd.com 302 https://app.quillmd.com/login/?next=/',
            'pro.quillmd.com 410')

    def setUp(self):
        super().setUp()
        self.bin = self.tmp / 'bin'
        self.bin.mkdir()
        curl = self.bin / 'curl'
        curl.write_text('#!/bin/bash\n'
                        'url="${*: -1}"; host="${url#https://}"\n'
                        'line="$(grep -m1 "^$host " "$STUB_SCENARIO")" || { printf "000 "; exit 7; }\n'
                        'read -r _h code target <<< "$line"\n'
                        'printf "%s %s" "$code" "${target:-}"\n')
        curl.chmod(0o755)

    def run_script(self, admin, *, skip=True, base=BASE):
        scenario = self.tmp / 'scenario'
        scenario.write_text('\n'.join((*base, f'{ADMIN} {admin}')) + '\n')
        env = {'PATH': f'{self.bin}:{install.COMMAND_ENV["PATH"]}', 'STUB_SCENARIO': str(scenario)}
        if skip:
            with mock.patch.dict(install.COMMAND_ENV, env):
                return install.cotenant_check()
        completed = subprocess.run(['bash', str(install.ROOT / 'scripts' / 'check-cotenants.sh')], capture_output=True,
                                   env={**install.COMMAND_ENV, **env}, timeout=60)
        return {'returncode': completed.returncode, 'stdout': completed.stdout.decode()}

    def test_the_installers_skip_is_honoured_and_never_judged(self):
        for admin in ('503', f'302 https://{ADMIN}/login/', '502', '200'):  # admin is the installer's to judge
            with self.subTest(admin=admin):
                found = self.run_script(admin)
                self.assertEqual((found['returncode'], found['judged_skipped']), (0, []))
                self.assertEqual(found['observed'], {'quillmd.com': '200', 'www.quillmd.com': '200',
                                                     'app.quillmd.com': '302', 'pro.quillmd.com': '410'})
        found = self.run_script('503', base=(*self.BASE[:3], 'pro.quillmd.com 200'))  # a co-tenant diverged
        self.assertEqual(found['returncode'], 1)

    def test_without_the_skip_admin_has_two_deliberate_states_and_nothing_else(self):
        for admin, code in (('503', 0), (f'302 https://{ADMIN}/login/', 0),
                            ('302 https://app.quillmd.com/login/?next=/', 1), (f'302 https://{ADMIN}/ops/', 1),
                            ('502', 1), ('404', 1), ('200', 1)):
            with self.subTest(admin=admin):
                self.assertEqual(self.run_script(admin, skip=False)['returncode'], code)


class ServesAdminHostTests(unittest.TestCase):
    def test_release_1_and_later_serve_it_and_an_earlier_revision_does_not(self):
        head = subprocess.run(['git', '-C', str(install.ROOT), 'rev-parse', 'HEAD'], capture_output=True,
                              check=True).stdout.decode().strip()
        self.assertTrue(install.serves_admin_host(head))  # this tree holds the admin urlconf and middleware
        # a value that is not a revision, or one this checkout cannot read, is refused - never taken for an older
        # revision, which would leave the admin answers unjudged (check, round R2-3)
        for value in ('HEAD', head[:12], '--help', '', None, 'f' * 40):
            with self.subTest(value=value), self.assertRaises(install.InstallError):
                install.serves_admin_host(value)
        found = subprocess.run(['git', '-C', str(install.ROOT), 'cat-file', '-e', f'{EARLIER_REVISION}^{{commit}}'],
                               capture_output=True)
        if found.returncode:
            self.skipTest(f'the earlier revision {EARLIER_REVISION[:12]} is not in this clone')
        self.assertFalse(install.serves_admin_host(EARLIER_REVISION))  # the pipeline before the admin host


# --- the cert phase for a served site --------------------------------------------------------------------------------

class CertTests(TemporaryDirectoryTest):
    EARLIER = pre_admin(rendered(9151)['https'])  # the stage the running web is served through before the ingress
    LE_BEFORE = {'accounts': ['acct'], 'dirs': {},
                 'live': {CPT: {'fullchain.pem': True, 'privkey.pem': True}, 'quillmd.com': {'fullchain.pem': True}},
                 'renewal': {f'{CPT}.conf': 'cpt-1', 'quillmd.com.conf': 'q-1'}}

    def ctx(self):
        return install.Context(SimpleNamespace(phase='cert', revision=REVISION, receipts=str(self.tmp)), self.tmp)

    def receipt(self, phase, details, revision=REVISION):
        install.write_receipt(self.tmp, phase, {'phase': phase, 'ok': True, 'revision': revision, 'details': details})

    def run_cert(self, *, live=None, web_port=9151, dns=None, le_after=None, acme_fails=(), helper=None):
        live = live or self.EARLIER
        events, calls = [], []
        le_after = le_after or {**self.LE_BEFORE,
                                'live': {**self.LE_BEFORE['live'],
                                         install.CERT_NAME: {'fullchain.pem': True, 'privkey.pem': True}},
                                'renewal': {**self.LE_BEFORE['renewal'], f'{install.CERT_NAME}.conf': 'studio-1',
                                            f'{CPT}.conf': 'cpt-2'}}  # DOMAIN's own lineage renewed meanwhile
        states = iter([self.LE_BEFORE, le_after])
        dns = dns or {}

        def getaddrinfo(host, port, type=0):
            events.append(('dns', host))
            return dns.get(host, [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (install.PUBLIC_IPV4, port))])

        def acme(ctx, label, host=CPT):
            events.append(('acme', host))
            return {'passed': host not in acme_fails, 'probe_removed': True, 'host': host}

        def run_helper(body, params, **kwargs):
            events.append(('certbot',))
            calls.append((body, params, kwargs))
            return helper or {'returncode': 0, 'output': 'ok'}
        web = {'Id': 'w', 'State': {'Running': True},
               'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'web', install.REVISION_LABEL: SERVING}},
               'HostConfig': {'PortBindings': {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(web_port)}]}}}
        with mock.patch.object(install, 'rendered_vhosts', side_effect=lambda revision, port=9150: rendered(port)), \
                mock.patch.object(install, 'vhost_state', return_value={'file_sha256': sha(live)}), \
                mock.patch.object(install, 'live_vhost_bytes', return_value=live.encode()), \
                mock.patch.object(install, 'inspect', side_effect=lambda kind, name: web), \
                mock.patch.object(install.socket, 'getaddrinfo', side_effect=getaddrinfo), \
                mock.patch.object(install, 'le_state', side_effect=lambda: next(states)), \
                mock.patch.object(install, 'acme_probe', side_effect=acme), \
                mock.patch.object(install, 'run_helper', side_effect=run_helper):
            return install.phase_cert(self.ctx()), events, calls

    def test_a_served_site_orders_both_names_under_cpt_studio_after_proving_both_routes(self):
        # no http-vhost receipt of this revision: the stage the running web is served through, recorded here
        self.receipt('app', {'switch': {'vhost_sha_after': sha(self.EARLIER)}}, revision=SERVING)
        details, events, calls = self.run_cert()
        self.assertEqual(details['stage'], {'site': 'served', 'vhost_sha256': sha(self.EARLIER), 'kind': 'https',
                                            'port': 9151, 'recorded_by': SERVING})
        self.assertEqual(events, [('dns', CPT), ('dns', ADMIN), ('acme', CPT), ('acme', ADMIN), ('certbot',)])
        (body, params, kwargs), = calls
        self.assertIs(body, install.H_CERTBOT)
        self.assertEqual((params['domains'], params['cert_name'], params['account']),
                         ([CPT, ADMIN], 'cpt-studio', 'acct'))
        self.assertEqual(kwargs['network'], 'host')
        self.assertEqual((details['cert_name'], details['renewal_conf']), ('cpt-studio', 'cpt-studio.conf'))
        self.assertIn('cpt-studio', details['summary'])

    def test_it_refuses_before_certbot_runs(self):
        self.receipt('app', {'switch': {'vhost_sha_after': sha(self.EARLIER)}}, revision=SERVING)
        aaaa = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (install.PUBLIC_IPV4, 80)),
                (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:db8::1', 80, 0, 0))]
        cases = {'admin has an AAAA record': (dict(dns={ADMIN: aaaa}), f'{ADMIN} no longer resolves'),
                 "admin's HTTP-01 route does not serve": (dict(acme_fails=(ADMIN,)), f'path of {ADMIN}'),
                 'the running web publishes the other port': (dict(web_port=9150), 'does not publish'),
                 'an unrecorded stage': (dict(live=self.EARLIER + '#\n'), 'not a stage this installer wrote')}
        for label, (kwargs, expected) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(install.InstallError, expected):
                self.run_cert(**kwargs)

    def test_with_no_receipt_recording_a_stage_it_refuses_before_reading_the_host(self):
        with mock.patch.object(install, 'vhost_state', side_effect=AssertionError('read the host')), \
                self.assertRaisesRegex(install.InstallError, 'receipt'):
            install.phase_cert(self.ctx())

    def test_the_new_lineage_and_domains_own_are_this_installers_another_lineage_is_not(self):
        self.receipt('app', {'switch': {'vhost_sha_after': sha(self.EARLIER)}}, revision=SERVING)
        changed = {**self.LE_BEFORE, 'live': {**self.LE_BEFORE['live'], install.CERT_NAME: {
            'fullchain.pem': True, 'privkey.pem': True}},
                   'renewal': {**self.LE_BEFORE['renewal'], f'{install.CERT_NAME}.conf': 's', 'quillmd.com.conf': 'q-2'}}
        with self.assertRaisesRegex(install.InstallError, 'another lineage changed'):
            self.run_cert(le_after=changed)
        missing = {**self.LE_BEFORE}
        with self.assertRaisesRegex(install.InstallError, 'cpt-studio lineage paths'):
            self.run_cert(le_after=missing)
        self.assertEqual(install.other_lineages({'renewal': {'cpt.quillmd.com.conf': 1, 'cpt-studio.conf': 2,
                                                             'quillmd.com.conf': 3},
                                                 'live': {'cpt.quillmd.com': {}, 'cpt-studio': {}, 'quillmd.com': {}}}),
                         ({'quillmd.com.conf': 3}, {'quillmd.com'}))

    def test_the_certbot_helper_orders_every_name_by_the_one_webroot_under_one_cert_name(self):
        seen = []

        class FakeOs:
            def __getattr__(self, name):
                return getattr(os, name)

            def chroot(self, path):
                seen.append(('chroot', path))

            def chdir(self, path):
                seen.append(('chdir', path))
        fake = SimpleNamespace(run=lambda cmd, **kwargs: seen.append(cmd) or SimpleNamespace(
            returncode=0, stdout=b'done', stderr=b''))
        lines, namespace = [], {}
        exec(compile(install.HELPER_PRELUDE, '<prelude>', 'exec'), namespace)
        namespace.update(os=FakeOs(), subprocess=fake, P={'domains': [CPT, ADMIN], 'cert_name': 'cpt-studio',
                                                          'account': 'acct', 'timeout': 240},
                         print=lambda *args, **kwargs: lines.append(' '.join(map(str, args))))
        exec(compile(install.H_CERTBOT, '<certbot>', 'exec'), namespace)
        self.assertEqual(seen[:2], [('chroot', '/host'), ('chdir', '/')])
        self.assertEqual(seen[2], ['/usr/bin/certbot', 'certonly', '--webroot', '-w', '/var/www/certbot', '-d', CPT,
                                   '-d', ADMIN, '--cert-name', 'cpt-studio', '--non-interactive',
                                   '--keep-until-expiring', '--account', 'acct'])
        self.assertEqual(json.loads(lines[-1])['returncode'], 0)


# --- the edge through the public path ------------------------------------------------------------------------------

class Edge:
    """The public path as https_checks reads it, modelled: nginx picks the server block by Host and presents a
    certificate by SNI (the cpt-studio lineage's for either CPT name once admin is on quillmd-cpt, QuillMD's otherwise),
    the quillmd-cpt block's guards, and the web behind it - the admin urlconf, or (misrouted) the full one."""

    def __init__(self, *, guard=421, admin_on='cpt', urlconf='admin', revision=REVISION, admin_head=302,
                 static=True, cross=True):
        self.guard, self.admin_on, self.urlconf, self.revision = guard, admin_on, urlconf, revision
        self.admin_head, self.static, self.cross = admin_head, static, cross
        self.seen = []

    def app(self, asked, path, method):
        """What the web answers, by the host Django sees."""
        if asked == ADMIN and self.urlconf == 'old':
            return {'status': 400, 'body_sha256': 'bad-request'}
        admin = asked == ADMIN and self.urlconf == 'admin'
        if path == '/health/':
            return {'status': 200, 'json': health(self.revision)}
        if path == '/api/session':
            return {'status': 404 if admin else 401}
        if path == '/':
            status = self.admin_head if (admin and method == 'HEAD') else 302
            return {'status': status, 'headers': {'location': ['/login/' if admin else '/login/?next=/']}}
        if path == '/login/':
            page = (b'<link rel="icon" href="/static/studio/favicon.0a1b2c.svg">' if self.static else b'<p>sign in</p>')
            return {'status': 200, 'headers': {'content-type': ['text/html; charset=utf-8']}, 'body': page}
        if path.startswith('/static/'):
            return {'status': 200}
        raise AssertionError(path)

    def probe(self, scheme, host, path='/', *, port=None, connect_ip=None, verify=True, method='GET', headers=None,
              timeout=5.0, keep_body=False):
        asked = (headers or {}).get('Host', host)
        self.seen.append((host, asked, path, method))
        assert scheme == 'https' and connect_ip is None and port is None, 'the public path only'
        cpt_cert = host in (CPT, ADMIN) and not (host == ADMIN and self.admin_on == 'quillmd')
        result = {'cert_sha256': 'cpt-studio' if cpt_cert else 'quillmd.com',
                  'cert_names': install.ADMIN_CERT_NAMES if cpt_cert else QUILLMD_NAMES}
        if asked == ADMIN and self.admin_on == 'quillmd':  # the quillmd vhost's block: Caddy's notice
            return {**result, 'status': 503, 'body_sha256': 'caddy-notice'}
        if asked in (CPT, ADMIN):  # quillmd-cpt's block
            if host not in (CPT, ADMIN) or (not self.cross and host != asked):
                return {**result, 'status': 421} if self.guard == 421 else {'error': 'RemoteDisconnected'}
            answer = self.app(asked, path, method)
            answer = {**answer, 'headers': {**POLICY, **answer.get('headers', {})}}
            if not keep_body:
                answer.pop('body', None)
            return {**result, **answer}
        return {**result, 'status': 200, 'json': {'status': 'ok'}}  # app.quillmd.com, QuillMD's own


class HttpsChecksTests(unittest.TestCase):
    def checks(self, edge, *, serving=True, revision=REVISION):
        ctx = SimpleNamespace(revision=REVISION)
        with mock.patch.object(install, 'probe', edge.probe), \
                mock.patch.object(install, 'serves_admin_host', return_value=serving), \
                mock.patch.object(install.time, 'sleep'):
            return install.https_checks(ctx, revision)

    def test_both_hosts_of_a_correct_edge_pass_and_every_answer_is_recorded(self):
        problems, evidence = self.checks(Edge())
        self.assertEqual(problems, [])
        self.assertEqual(evidence['sni_mismatch'], {CPT: {'status': 421, 'error': None},
                                                    ADMIN: {'status': 421, 'error': None}})
        self.assertEqual(evidence['cross_name'], {f'{ADMIN} > {CPT}': {'status': 200, 'error': None},
                                                  f'{CPT} > {ADMIN}': {'status': 200, 'error': None}})
        answers = evidence['admin']['answers']
        self.assertEqual((answers['api_session'], answers['get_root'], answers['head_root']),
                         (404, {'status': 302, 'location': ['/login/']}, {'status': 302, 'location': ['/login/']}))
        self.assertEqual(answers['login']['assets'], {'/static/studio/favicon.0a1b2c.svg': 200})
        self.assertEqual(evidence['admin']['edge']['cert_names'], install.ADMIN_CERT_NAMES)

    def test_each_way_the_edge_or_the_routing_can_be_wrong_is_a_problem(self):
        cases = {
            'a misdirected request closed (the old 444) instead of 421': (Edge(guard=444), 'not 421 Misdirected'),
            'the admin host routed to the full urlconf': (Edge(urlconf='full'), '/api/session answered 401'),
            'the full urlconf\'s redirect': (Edge(urlconf='full'), 'not 302 to exactly /login/'),
            'the admin host still on the quillmd vhost': (Edge(admin_on='quillmd'), 'not served with the cpt-studio'),
            'a HEAD of / refused by a method guard': (Edge(admin_head=405), 'anonymous HEAD'),
            'a sign-in naming no static file': (Edge(static=False), 'names no static file'),
            'a connection for one host not serving the other': (Edge(cross=False), 'on a connection opened for'),
            'another revision answering': (Edge(revision=OLD), 'did not serve revision'),
        }
        for label, (edge, expected) in cases.items():
            with self.subTest(label):
                problems, _ = self.checks(edge)
                self.assertTrue(any(expected in problem for problem in problems), problems)

    def test_an_older_webs_400_on_the_admin_host_is_recorded_and_never_a_problem(self):
        problems, evidence = self.checks(Edge(urlconf='old'), serving=False)
        self.assertEqual(problems, [])
        self.assertEqual(evidence['admin']['answers']['judged'], False)
        self.assertEqual(evidence['admin']['answers']['status'], 400)
        self.assertEqual(evidence['cross_name'][f'{CPT} > {ADMIN}']['status'], 400)
        # the edge is the vhost's, whatever web answers: its certificate is still judged
        problems, _ = self.checks(Edge(urlconf='old', admin_on='quillmd'), serving=False)
        self.assertTrue(any('not served with the cpt-studio' in problem for problem in problems), problems)


# --- the incoming web's admin answers on its loopback port ---------------------------------------------------------

class _TwoHostHandler(http.server.BaseHTTPRequestHandler):
    urlconf = 'admin'
    seen = []

    def log_message(self, *args):
        pass

    def answer(self, body):
        host = self.headers.get('Host')
        type(self).seen.append((self.command, self.path, host))
        admin = host == ADMIN and type(self).urlconf == 'admin'
        if self.path in ('/login/',):
            status, kind, page = 200, 'text/html; charset=utf-8', b'<link href="/static/studio/a.0a1b.css">'
        elif self.path.startswith('/static/'):
            status, kind, page = 200, 'text/css', b'x'
        elif self.path == '/api/session':
            status, kind, page = (404 if admin else 401), 'text/plain', b''
        elif self.path == '/':
            self.send_response(302)
            self.send_header('Location', '/login/' if admin else '/login/?next=/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        else:
            status, kind, page = 404, 'text/plain', b''
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(page)))
        self.end_headers()
        if body:
            self.wfile.write(page)

    def do_GET(self):
        self.answer(True)

    def do_HEAD(self):
        self.answer(False)


class SmokeAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _TwoHostHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _TwoHostHandler.urlconf, _TwoHostHandler.seen = 'admin', []

    def test_a_web_that_serves_the_admin_host_is_asked_its_own_answers_before_a_switch(self):
        record = install.smoke_web(self.port, admin=True)
        self.assertEqual(record['admin']['api_session'], 404)
        self.assertEqual(record['admin']['head_root'], {'status': 302, 'location': ['/login/']})
        self.assertIn(('HEAD', '/', ADMIN), _TwoHostHandler.seen)
        self.assertIn(('GET', '/static/studio/a.0a1b.css', ADMIN), _TwoHostHandler.seen)

    def test_a_web_routing_the_admin_host_to_the_full_urlconf_is_refused_before_a_switch(self):
        _TwoHostHandler.urlconf = 'full'
        with self.assertRaisesRegex(install.InstallError, r'/api/session answered 401.*/login/\?next=/'):
            install.smoke_web(self.port, admin=True)

    def test_a_web_that_does_not_serve_it_is_never_asked(self):
        _TwoHostHandler.urlconf = 'full'
        record = install.smoke_web(self.port)
        self.assertIn('not judged', record['admin'])
        self.assertFalse([seen for seen in _TwoHostHandler.seen if seen[2] == ADMIN])


class SwitchSmokeTests(TemporaryDirectoryTest):
    """The admin arm is asked of the incoming web exactly when its revision serves the admin host."""

    def test_the_app_and_switch_back_smoke_follow_the_incoming_webs_revision(self):
        for serving, expected in ((True, True), (False, False)):
            world = BlueGreenWorld(self.tmp)
            with self.subTest(serving=serving), \
                    mock.patch.object(install, 'serves_admin_host', side_effect=lambda revision: serving):
                details, error = run_app(world)
                self.assertIsNone(error)
                self.assertEqual(world.smoked_admin, [(9151, expected)])
            for path in self.tmp.iterdir():
                path.unlink()
        world = BlueGreenWorld(self.tmp, live=9151, serving=(REVISION, 'sha256:' + 'c' * 64))
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'replaced': {'web': {'id': 'web-old', 'image': 'sha256:' + 'd' * 64, 'revision': OLD},
                         'worker': {'id': 'worker-old', 'image': 'sha256:' + 'd' * 64, 'revision': OLD}}}})
        patches = world.patches() + [mock.patch.object(install, 'serves_admin_host',
                                                       side_effect=lambda revision: revision == REVISION)]
        for patcher in patches:
            patcher.start()
        try:
            details = install.phase_switch_back(install.Context(switch_back_args(self.tmp), self.tmp))
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        self.assertEqual(world.smoked_admin, [(9150, False)])  # a revision before release 1: not asked
        self.assertIn(f"{ADMIN} answers {OLD[:12]}'s 400", details['summary'])
        self.assertIn('ingress-rollback', details['admin_host'])


# --- ingress and ingress-rollback, end to end on temporary files with the real root helper --------------------------

class IngressWorld:
    """sites-available and sites-enabled as temporary directories holding a synthetic quillmd vhost (pinned for the
    test) and quillmd-cpt; the REAL phases, publish_vhost, vhost_state, live_vhost_bytes, live_web_port,
    recorded_vhosts and quillmd_bytes run against them, and the REAL H_VHOST body runs in-process for every root-helper
    call (logging its renames). Faked: nginx (test and reload), the web container, the probes of the public path
    (answering from the files: which block claims each host), the checks of other test modules."""

    def __init__(self, tmp, *, live, web=(SERVING, 9151), quillmd='before', serving=(SERVING, REVISION)):
        self.tmp, self.receipts = tmp, tmp / 'receipts'
        self.receipts.mkdir(mode=0o700)
        self.available, self.enabled = tmp / 'available', tmp / 'enabled'
        self.available.mkdir()
        self.enabled.mkdir()
        self.before, self.after = synthetic_quillmd()
        (self.available / 'quillmd').write_bytes(self.before if quillmd == 'before' else self.after)
        (self.available / install.VHOST_NAME).write_text(live)
        os.symlink(install.VHOST_LINK_TARGET, self.enabled / install.VHOST_NAME)
        self.web_revision, self.web_port = web
        self.serving = set(serving)  # the revisions whose web serves the admin host
        self.ops, self.renamed, self.nginx_t, self.reloads = [], [], [], 0
        self.warnings_after = []     # a warning nginx -t gives once the files changed
        self.https_problems = []     # what https_checks finds after the change
        self.caddy = {'status': 503, 'body_sha256': 'caddy-notice'}
        self.loopback = ([], {'api_session': 404})
        self.lineage = True
        self.drift = []
        self.receipt('preflight', {'routing': {}, 'app_health': {'status': 200}})
        self.receipt('cert', {})

    def receipt(self, phase, details, revision=REVISION):
        return install.write_receipt(self.receipts, phase, {'phase': phase, 'ok': True, 'revision': revision,
                                                            'details': details})

    def files(self):
        cpt = self.available / install.VHOST_NAME
        return ((self.available / 'quillmd').read_bytes(), cpt.read_text() if cpt.exists() else None)

    def cpt_text(self):
        path = self.available / install.VHOST_NAME
        return path.read_text() if path.is_file() else ''

    # -- fakes
    def run_helper(self, body, params, **kwargs):
        assert body is install.H_VHOST, 'only the vhost helper'
        log = RenameLogOs()
        result = run_body(body, params, {"'/available'": repr(str(self.available)),
                                         "'/enabled'": repr(str(self.enabled))}, fake_os=log)
        self.ops.append(params['op'])
        self.renamed.append(log.renamed)
        if result.get('error'):
            raise install.InstallError(f'Root helper refused: {result["error"]}', details=result)
        return result

    def nginx_test(self):
        changed = self.files() != getattr(self, 'baseline_files', self.files())
        self.nginx_t.append('test')
        return {'ok': True, 'warnings': ['w1'] + (self.warnings_after if changed else []), 'output': 'ok'}

    def nginx_reload(self):
        self.reloads += 1

    def inspect(self, kind, name):
        if name != install.SERVICES['web']:
            return None
        return {'Id': 'web-1', 'Image': 'sha256:' + 'e' * 64, 'State': {'Running': True},
                'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'web',
                                      install.REVISION_LABEL: self.web_revision}},
                'HostConfig': {'PortBindings': {'8000/tcp': [{'HostIp': '127.0.0.1',
                                                             'HostPort': str(self.web_port)}]}}}

    def probe(self, scheme, host, path='/', *, port=None, connect_ip=None, verify=True, method='GET', headers=None,
              timeout=5.0, keep_body=False):
        asked = (headers or {}).get('Host', host)
        if port == install.CADDY_ADDRESS[1]:  # QuillMD's Caddy, directly
            return dict(self.caddy)
        if scheme == 'http' and asked == CPT and path == '/':
            return {'status': 301, 'headers': {'location': [f'https://{CPT}/']}}
        quillmd_claims_admin = sha((self.available / 'quillmd').read_bytes()) == sha(self.before)
        text = self.cpt_text()
        if asked == ADMIN:
            if quillmd_claims_admin:
                return {'status': 503, 'body_sha256': 'caddy-notice', 'cert_names': QUILLMD_NAMES}
            if install.names_host_on(text, ADMIN):
                return {'status': 200, 'json': health(self.web_revision), 'cert_names': install.ADMIN_CERT_NAMES}
            return {'error': 'SSLCertVerificationError'}  # a co-tenant's default server and certificate
        if asked == CPT and install.names_host_on(text, CPT):
            return {'status': 200, 'json': health(self.web_revision), 'cert_sha256': 'cpt'}
        return {'status': 404, 'cert_sha256': 'unmatched'}  # CPT's :443 claimed by nothing, or the unmatched host

    def nginx_file_state(self):
        return {'available': {path.name: sha(path.read_bytes()) for path in sorted(self.available.iterdir())}}

    def patches(self):
        return [mock.patch.multiple(
            install, NGINX_AVAILABLE=self.available, NGINX_ENABLED=self.enabled,
            QUILLMD_VHOST_BEFORE=sha(self.before), QUILLMD_VHOST_AFTER=sha(self.after),
            run_helper=self.run_helper, nginx_test=self.nginx_test, nginx_reload=self.nginx_reload,
            inspect=self.inspect, probe=self.probe, nginx_file_state=self.nginx_file_state,
            rendered_vhosts=lambda revision, port=install.WEB_PORT: rendered(port),
            le_state=lambda: {'live': {install.CERT_NAME: {'fullchain.pem': True, 'privkey.pem': True}}
                              if self.lineage else {}},
            serves_admin_host=lambda revision: revision in self.serving,
            loopback_admin_answers=lambda port: self.loopback,
            https_checks=lambda ctx, revision=None: (list(self.https_problems), {'revision': revision}),
            acme_probe=lambda ctx, label, host=CPT: {'passed': True, 'probe_removed': True, 'host': host},
            ingress_checks=lambda ctx, preflight: list(self.drift)),
            mock.patch.object(install.time, 'sleep')]

    def run(self, phase):
        """The REAL phase; its receipt written as main writes it. (details or None, the InstallError or None)."""
        ctx = install.Context(SimpleNamespace(phase=phase, revision=REVISION, receipts=str(self.receipts)),
                              self.receipts)
        self.baseline_files = self.files()
        function = {'ingress': install.phase_ingress, 'ingress-rollback': install.phase_ingress_rollback,
                    'http-vhost': install.phase_http_vhost, 'rollback-vhost': install.phase_rollback_vhost}[phase]
        patches = self.patches()
        for patcher in patches:
            patcher.start()
        try:
            details = function(ctx)
        except install.InstallError as error:
            install.write_receipt(self.receipts, phase, {'phase': phase, 'ok': False, 'revision': REVISION,
                                                         'error': str(error)})
            return None, error
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        install.write_receipt(self.receipts, phase, {'phase': phase, 'ok': True, 'revision': REVISION,
                                                     'details': details})
        return details, None


class RenameLogOs:
    """os for the helper body: ownership recorded instead of changed (test_install.FakeOwnership) and every rename
    logged by target name."""

    def __init__(self):
        from test_install import FakeOwnership
        self._os, self.renamed = FakeOwnership(), []

    def __getattr__(self, name):
        return getattr(self._os, name)

    def replace(self, source, target):
        self._os.replace(source, target)
        self.renamed.append(os.path.basename(target))


class IngressTests(TemporaryDirectoryTest):
    EARLIER = pre_admin(rendered(9151)['https'])  # release 1's stage for 9151: names cpt alone

    def served_world(self, **kwargs):
        world = IngressWorld(self.tmp, live=self.EARLIER, **kwargs)
        world.receipt('app', {'switch': {'vhost_sha_after': sha(self.EARLIER)}}, revision=SERVING)
        return world

    def test_ingress_moves_admin_onto_quillmd_cpt_in_one_act_and_ingress_rollback_gives_it_back(self):
        world = self.served_world()
        details, error = world.run('ingress')
        self.assertIsNone(error)
        self.assertEqual(world.files(), (world.after, rendered(9151)['https']))
        self.assertEqual((world.ops, world.renamed), (['couple'], [[install.VHOST_NAME, 'quillmd']]))
        self.assertEqual((world.nginx_t, world.reloads), (['test', 'test'], 1))  # validated together, reloaded once
        self.assertEqual((details['moved'], details['vhost_sha256'], details['upstream_port']),
                         (True, sha(rendered(9151)['https']), 9151))
        self.assertEqual({key: details['from'][key] for key in ('sha256', 'kind', 'port', 'recorded_by')},
                         {'sha256': sha(self.EARLIER), 'kind': 'https', 'port': 9151, 'recorded_by': SERVING})
        self.assertEqual(base64.b64decode(details['from']['b64']).decode(), self.EARLIER)  # byte for byte
        self.assertEqual(details['quillmd'], {'before': sha(world.before), 'after': sha(world.after), 'line': 26})
        self.assertEqual(details['web']['revision'], SERVING)
        # recorded_vhosts reads the ingress's stage (refutation INSTALLER-11)
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION, receipts=str(world.receipts)),
                              world.receipts)
        self.assertEqual(install.recorded_vhosts(ctx)[sha(rendered(9151)['https'])], (REVISION, 'https'))

        details, error = world.run('ingress-rollback')
        self.assertIsNone(error)
        self.assertEqual(world.files(), (world.before, self.EARLIER))
        self.assertEqual((world.ops[1:], world.renamed[1:]), (['decouple'], [['quillmd', install.VHOST_NAME]]))
        self.assertEqual((details['vhost_sha256'], details['vhost_kind'], details['caddy']['status']),
                         (sha(self.EARLIER), 'https', 503))
        self.assertEqual(install.recorded_vhosts(ctx)[sha(self.EARLIER)], (SERVING, 'https'))  # the app receipt's
        # run again in the state it left: verified, nothing written
        details, error = world.run('ingress-rollback')
        self.assertIsNone(error)
        self.assertEqual((details['already_rolled_back'], world.ops[2:]), (True, []))

    def test_a_failed_verification_writes_both_files_back_the_quillmd_vhost_first(self):
        world = self.served_world()
        world.https_problems = ['https://admin.quillmd.com/api/session answered 401']
        details, error = world.run('ingress')
        self.assertIn('answered 401', str(error))
        self.assertEqual(world.files(), (world.before, self.EARLIER))
        self.assertEqual((world.ops, world.renamed), (['couple', 'decouple'], [[install.VHOST_NAME, 'quillmd'],
                                                                                ['quillmd', install.VHOST_NAME]]))
        self.assertEqual(world.reloads, 2)  # the change, then the restored files

    def test_a_new_nginx_warning_writes_both_back_with_no_reload(self):
        world = self.served_world()
        world.warnings_after = ['conflicting server name "admin.quillmd.com" on 0.0.0.0:443, ignored']
        details, error = world.run('ingress')
        self.assertIn('added warnings', str(error))
        self.assertEqual((world.files(), world.ops, world.reloads), ((world.before, self.EARLIER),
                                                                      ['couple', 'decouple'], 0))

    def test_ingress_refuses_before_anything_is_written(self):
        cases = {
            'the running web does not serve the admin host': (
                lambda world: world.serving.discard(SERVING), 'does not answer the admin host'),
            'its loopback answers are not the admin urlconf\'s': (
                lambda world: setattr(world, 'loopback', (['/api/session answered 401'], {})), 'yet'),
            'the cpt-studio lineage is absent': (lambda world: setattr(world, 'lineage', False), 'lineage'),
            'co-tenant routing drifted since preflight': (
                lambda world: setattr(world, 'drift', ['co-tenant routing changed: x']), 'routing changed'),
            'the quillmd vhost is already the after state': (
                lambda world: (world.available / 'quillmd').write_bytes(world.after), 'not coupled'),
            'quillmd-cpt names admin while the quillmd vhost does too': (
                lambda world: (world.available / install.VHOST_NAME).write_text(rendered(9151)['https']),
                'half way'),
            'the running web publishes the other port': (lambda world: setattr(world, 'web_port', 9150),
                                                         'does not publish'),
            'a stage nobody recorded': (
                lambda world: (world.available / install.VHOST_NAME).write_text(self.EARLIER + '#\n'),
                'did not write'),
        }
        for label, (change, expected) in cases.items():
            with self.subTest(label):
                for path in list(self.tmp.iterdir()):
                    if path.is_dir():
                        for inner in path.iterdir():
                            inner.unlink()
                        path.rmdir()
                world = self.served_world()
                change(world)
                before = world.files()
                details, error = world.run('ingress')
                self.assertIsNotNone(error, label)
                self.assertRegex(str(error), expected)
                self.assertEqual((world.files(), world.ops, world.reloads), (before, [], 0))

    def test_run_again_on_the_after_state_it_verifies_and_writes_nothing(self):
        world = self.served_world()
        world.run('ingress')
        details, error = world.run('ingress')
        self.assertIsNone(error)
        self.assertEqual((details['moved'], details['already_installed'], world.ops), (False, True, ['couple']))

    def test_ingress_rollback_refuses_unless_the_web_the_ingress_found_serves_again_on_the_saved_port(self):
        world = self.served_world()
        world.run('ingress')
        # app: this revision's web on 9150, the stage switched to its 9150 rendering (blue/green)
        (world.available / install.VHOST_NAME).write_text(rendered(9150)['https'])
        world.web_revision, world.web_port = REVISION, 9150
        details, error = world.run('ingress-rollback')
        self.assertRegex(str(error), 'switch-back')
        self.assertIn(SERVING[:12], str(error))
        # a switch-back landing that revision on the other port is not enough either
        world.web_revision = SERVING
        details, error = world.run('ingress-rollback')
        self.assertRegex(str(error), 'on 9151, the port the saved stage proxies to')
        self.assertEqual((world.ops, world.files()[0]), (['couple'], world.after))
        # back on 9151 (switch-back to it), it rolls back
        (world.available / install.VHOST_NAME).write_text(rendered(9151)['https'])
        world.web_port = 9151
        details, error = world.run('ingress-rollback')
        self.assertIsNone(error)
        self.assertEqual(world.files(), (world.before, self.EARLIER))

    def test_ingress_rollback_reads_caddys_notice_before_it_writes_anything(self):
        world = self.served_world()
        world.run('ingress')
        world.caddy = {'error': 'SSLError'}  # Caddy lost its certificate: admin would answer a raw 502
        details, error = world.run('ingress-rollback')
        self.assertRegex(str(error), "Caddy did not complete a handshake")
        self.assertEqual((world.ops, world.files()[0]), (['couple'], world.after))

    def test_a_failed_rollback_verification_writes_both_forward_again(self):
        world = self.served_world()
        world.run('ingress')
        world.caddy = {'status': 503, 'body_sha256': 'another-notice'}  # admin will not answer this one
        details, error = world.run('ingress-rollback')
        self.assertRegex(str(error), "did not answer QuillMD's Caddy notice")
        self.assertEqual(world.files(), (world.after, rendered(9151)['https']))
        self.assertEqual((world.ops, world.renamed[1:]), (['couple', 'decouple', 'couple'],
                                                          [['quillmd', install.VHOST_NAME],
                                                           [install.VHOST_NAME, 'quillmd']]))

    def test_with_no_ingress_receipt_there_is_nothing_to_roll_back(self):
        world = self.served_world()
        details, error = world.run('ingress-rollback')
        self.assertRegex(str(error), 'No successful --phase ingress receipt')

    def test_a_move_made_by_another_revision_is_refused_and_its_way_back_named(self):
        """check, round R2-2: a later revision's ingress-rollback, with admin moved by an earlier revision's ingress,
        refuses and names that revision's switch-back and ingress-rollback - never 'nothing to roll back'"""
        world = self.served_world()
        details, error = world.run('ingress')
        self.assertIsNone(error)
        for path in world.receipts.glob('ingress-*.json'):  # the move was another revision's
            record = json.loads(path.read_text())
            record['revision'] = SERVING
            path.write_text(json.dumps(record))
        details, error = world.run('ingress-rollback')
        self.assertRegex(str(error), f'moved by revision {SERVING[:12]}')
        self.assertIn('--phase switch-back', str(error))
        self.assertNotIn('nothing to roll back', str(error))
        self.assertEqual((world.ops, world.files()[0]), (['couple'], world.after))  # nothing written

    def test_a_fresh_host_moves_from_this_revisions_http_stage_and_rolls_back_to_it(self):
        world = IngressWorld(self.tmp, live=rendered()['http'], web=(REVISION, 9150), serving=(REVISION,))
        world.receipt('http-vhost', {'vhost_sha256': sha(rendered()['http'])})
        details, error = world.run('ingress')
        self.assertIsNone(error)
        self.assertEqual(world.files(), (world.after, rendered(9150)['https']))
        self.assertEqual({key: details['from'][key] for key in ('kind', 'port')}, {'kind': 'http', 'port': None})
        details, error = world.run('ingress-rollback')
        self.assertIsNone(error)
        self.assertEqual(world.files(), (world.before, rendered()['http']))
        self.assertEqual(details['vhost_kind'], 'http')

    def test_rollback_vhost_and_http_vhost_refuse_while_admin_is_on_quillmd_cpt(self):
        world = self.served_world()
        world.run('ingress')
        for phase in ('rollback-vhost', 'http-vhost'):
            with self.subTest(phase):
                details, error = world.run(phase)
                self.assertIn('run --phase ingress-rollback first', str(error))
                self.assertEqual((world.ops, world.files()[0]), (['couple'], world.after))
        # with quillmd-cpt gone too (by hand), the after state names nothing: http-vhost still refuses to write
        os.unlink(world.enabled / install.VHOST_NAME)
        (world.available / install.VHOST_NAME).unlink()
        details, error = world.run('http-vhost')
        self.assertRegex(str(error), 'not coupled')
        self.assertEqual(world.ops, ['couple'])


# --- preflight's new checks ---------------------------------------------------------------------------------------------

class PreflightTests(TemporaryDirectoryTest):
    """phase_preflight with the host stood in: the coupling invariant (either state, never another), admin.quillmd.com's
    DNS and HTTP-01 route, and a check-cotenants that honours the installer's skip."""

    def run_preflight(self, *, quillmd=None, live=None, dns=None, admin_acme=True, judged=(), link=True):
        quillmd = quillmd or install.QUILLMD_VHOST_AFTER
        live = rendered(9151)['https'] if live is None else live
        dns = dns or {}

        def getaddrinfo(host, port, type=0):
            return dns.get(host, [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (install.PUBLIC_IPV4, port))])

        def helper_stat(paths):
            return {path: ({'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}
                           if path == install.PROVIDER_SOURCES else {'exists': False}) for path in paths}

        def run_helper(body, params, **kwargs):
            return {'written': True} if body == install.H_ACME_WRITE else {'removed': True}
        target = {True: install.VHOST_LINK_TARGET, False: None}.get(link, link)  # link: True, False or a target
        vhost = {'file_exists': bool(live), 'file_sha256': sha(live) if live else None,
                 'link_exists': bool(live) and link is not False, 'link_target': target if live else None}
        ctx = install.Context(SimpleNamespace(phase='preflight', revision=REVISION, receipts=str(self.tmp)), self.tmp)
        with mock.patch.multiple(
                install, docker_positive_control=lambda: '27.0.0',
                nginx_file_state=lambda: {'available': {'quillmd': quillmd}, 'enabled': {}, 'nginx_conf_sha256': 'x',
                                          'conf_d': []},
                vhost_state=lambda: vhost, live_vhost_bytes=lambda: live.encode() if live else None,
                nginx_test=lambda: {'ok': True, 'warnings': [], 'output': 'ok'},
                enabled_config_texts=lambda: [], routing_snapshot=lambda targets: {}, cpt_probes=lambda: {},
                app_health=lambda: {'status': 200, 'json': {'status': 'ok'}, 'error': None},
                cotenant_check=lambda: {'returncode': 0, 'observed': {}, 'skipped': [ADMIN],
                                        'judged_skipped': list(judged)},
                containers=lambda: {}, volumes=lambda: [], networks=lambda: [],
                web_port_layout=lambda: {'active': 9151, 'idle': 9150, 'problems': []},
                port_problem=lambda port, owner: '', foreign_uid_tasks=lambda uid, ids: 0, own_service_ids=lambda: [],
                inspect=lambda kind, name: {'Id': name}, helper_stat=helper_stat,
                le_state=lambda: {'dirs': {'/etc/letsencrypt': True}, 'accounts': ['acct'], 'live': {}, 'renewal': {}},
                run_helper=run_helper,
                acme_probe=lambda ctx, label, host=CPT: {'passed': admin_acme or host != ADMIN, 'probe_removed': True,
                                                         'host': host, 'label': label}), \
                mock.patch.object(install.socket, 'getaddrinfo', side_effect=getaddrinfo), \
                mock.patch.object(install.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 2 ** 30)):
            try:
                return install.phase_preflight(ctx), []
            except install.InstallError as error:
                return error.details, error.details['problems']

    def test_either_state_of_the_coupling_invariant_is_a_baseline(self):
        details, problems = self.run_preflight()  # after the ingress: the act's second preflight
        self.assertEqual((problems, details['coupling']['coupling']), ([], 'after'))
        details, problems = self.run_preflight(quillmd=install.QUILLMD_VHOST_BEFORE,
                                               live=pre_admin(rendered(9151)['https']))  # before it
        self.assertEqual((problems, details['coupling']['coupling']), ([], 'before'))
        self.assertEqual(details['dns'], {host: {'a': [install.PUBLIC_IPV4], 'aaaa': []} for host in (CPT, ADMIN)})
        self.assertEqual(details['admin_acme']['host'], ADMIN)

    def test_any_other_state_is_a_problem(self):
        cases = {'both name admin': (install.QUILLMD_VHOST_BEFORE, rendered(9151)['https'], 'half way'),
                 'nothing claims admin': (install.QUILLMD_VHOST_AFTER, pre_admin(rendered(9151)['https']),
                                          'not coupled'),
                 'the after state with no quillmd-cpt': (install.QUILLMD_VHOST_AFTER, '', 'not coupled'),
                 'a quillmd vhost in neither state': ('0' * 64, rendered()['http'], 'not coupled')}
        for label, (quillmd, live, expected) in cases.items():
            with self.subTest(label):
                details, problems = self.run_preflight(quillmd=quillmd, live=live)
                self.assertTrue(any(expected in problem for problem in problems), problems)

    def test_the_after_state_is_judged_as_nginx_loads_quillmd_cpt(self):
        """check, round R2-1: quillmd-cpt claims admin's :443 only through the installer's sites-enabled link"""
        for label, link in (('no sites-enabled link', False),
                            ('a link to another file', '/etc/nginx/sites-available/quillmd')):
            with self.subTest(label):
                details, problems = self.run_preflight(link=link)
                self.assertEqual(details['coupling']['coupling'], 'uncoupled')
                self.assertTrue(any('not coupled' in problem for problem in problems), problems)

    def test_admins_dns_route_and_the_skip_are_checked(self):
        aaaa = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (install.PUBLIC_IPV4, 443)),
                (socket.AF_INET6, socket.SOCK_STREAM, 6, '', ('2001:db8::1', 443, 0, 0))]
        _, problems = self.run_preflight(dns={ADMIN: aaaa})
        self.assertIn(f'{ADMIN} must resolve to A {install.PUBLIC_IPV4} only', problems)
        _, problems = self.run_preflight(admin_acme=False)
        self.assertTrue(any(f'path of {ADMIN}' in problem for problem in problems), problems)
        _, problems = self.run_preflight(judged=[ADMIN])
        self.assertTrue(any('does not honour the skip' in problem for problem in problems), problems)
