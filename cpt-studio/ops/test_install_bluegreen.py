"""Offline tests of the blue/green install (ops/install.py switch_services and phase_switch_back; ops/INSTALL.md app,
switch-back), the availability record, the drain, the port-aware vhost phases, and the operators and reassess phases.
No Docker, sudo, nginx, database (but the marked in-image script tests) or network: the host guard of test_install
refuses every one of them.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

The heart is BlueGreenWorld: the host as the installer sees it - containers by name, the vhost file, the port nginx
routes new requests to (moved only by a reload), the requests old nginx workers still hold on a port, the worker - with
every Docker, nginx and in-image call the installer makes replaced by a fake that acts on that model, and an invariant
checked after EVERY fake call: a running, healthy web publishes both the port nginx routes to and the port the file
names (so even a reload by someone else at that moment lands on a healthy web); at most one worker runs; no worker runs
when nginx's port moves; no web is stopped while requests are still in flight to it; the full recompute of the stored
list states never runs beside a container of another image. The success path, one test per row of the failure matrix,
and an interrupt at every single fake call of the success path all run the REAL phase_app / switch_services /
switch_upstream / publish_vhost / replacement_plan against it.
"""
import base64
import datetime as dt
import difflib
import hashlib
import http.server
import io
import json
import os
import stat
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import (TemporaryDirectoryTest, guard_host, release_host, rendered,  # noqa: E402
                          HOST_GUARD_ATTEMPTS)

APP_ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40            # the revision being installed
OLD = 'b' * 40                 # the revision serving before it
IMAGE = 'sha256:' + 'c' * 64
OLD_IMAGE = 'sha256:' + 'd' * 64
RULING = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
WEB, WORKER = install.SERVICES['web'], install.SERVICES['worker']
NEXT = install.INCOMING_WEB
KINDS_OLD = ['analyze', 'assess', 'astra', 'astra_peer', 'extract', 'fable', 'fable_peer', 'predict', 'review2']


def setUpModule():
    guard_host()


def tearDownModule():
    try:
        harness2 = sys.modules.get('test_install_harness2')
        if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
            connection = harness2._DATABASE.pop('connection')
            connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)
    finally:
        release_host()


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def flags(argv, flag):
    return [argv[i + 1] for i, part in enumerate(argv) if part == flag]


class Interrupted(Exception):
    pass


class BlueGreenWorld:
    """The host, for the blue/green paths (see the module docstring). ``fail`` maps a fault point to the exception it
    raises once; ``interrupt_at`` raises KeyboardInterrupt at that fake call (1-based), once."""

    def __init__(self, tmp, *, live=9150, serving=(OLD, OLD_IMAGE)):
        self.tmp = tmp
        self.live, self.idle = live, install.other_port(live)
        self.confs = {port: rendered(port) for port in install.WEB_PORTS}
        self.containers = {}
        self.events, self.calls, self.interrupt_at, self.fail = [], 0, None, {}
        self.unhealthy, self.closes, self.put_backs, self.recomputes = set(), [], [], []
        self.nginx_answers = []     # the next nginx -t answers, in order (then: ok, no warning)
        self.checking = True
        self.hazards_answer = {}
        self.close_answer = {'closed': 0, 'kinds': [], 'hazards': {}, 'relabel': []}
        self.vhost_text = self.confs[live]['https']
        self.nginx_port = live
        self.inflight = {}          # port -> requests old nginx workers still hold to it
        self.availability = None    # the recorder's model: every invariant point it saw, served or not
        self.next_id = 0
        revision, image = serving
        self.add(WEB, 'web', image, revision, port=live)
        self.add(WORKER, 'worker', image, revision)
        self.stage_kinds = {OLD_IMAGE: KINDS_OLD, IMAGE: KINDS_OLD + ['synthetic_new']}
        self.preflight_receipt()

    # -- the model ---------------------------------------------------------------------------------------------------
    def add(self, name, role, image, revision, *, port=None, running=True):
        self.next_id += 1
        self.containers[name] = {'Id': f'{role}-{self.next_id}', 'Image': image, 'role': role, 'port': port,
                                 'running': running, 'healthy': name not in self.unhealthy, 'revision': revision,
                                 'created': f'2026-11-03T10:{self.next_id:02d}:00.000000Z'}

    def by_id(self, container_id):
        return next((name for name, c in self.containers.items() if c['Id'] == container_id), None)

    def web_on(self, port):
        found = [c for c in self.containers.values() if c['role'] == 'web' and c['port'] == port and c['running']]
        return found[0] if len(found) == 1 else None

    def file_port(self):
        return install.proxied_port(self.vhost_text)

    def invariant(self):
        if not self.checking:  # a host that serves nothing through the vhost has no blue/green invariant
            return
        where = self.events[-1] if self.events else 'start'
        for which, port in (('nginx', self.nginx_port), ('file', self.file_port())):
            web = self.web_on(port)
            assert web is not None and web['healthy'], f'I-web: no healthy web on the {which} port {port} after {where}'
        workers = [name for name, c in self.containers.items() if c['role'] == 'worker' and c['running']]
        assert len(workers) <= 1, f'I-worker: {workers} run together after {where}'
        for port, requests in self.inflight.items():
            if requests:
                assert self.web_on(port) is not None, f'a web was stopped with {requests} request(s) in flight on {port}'
        if self.availability is not None:
            served = self.web_on(self.nginx_port)
            self.availability.append(200 if served is not None and served['healthy'] else 503)

    def act(self, *event):
        self.calls += 1
        if self.interrupt_at is not None and self.calls == self.interrupt_at:
            self.interrupt_at = None
            self.events.append(('interrupted', *event))
            raise KeyboardInterrupt()
        self.events.append(event)
        for key in list(self.fail):  # a fault raised by the call it names (an event prefix), before it acts
            if tuple(event[:len(key)]) == key:
                raise self.fail.pop(key)

    def done(self, value=None):
        self.invariant()
        return value

    # -- receipts ----------------------------------------------------------------------------------------------------
    def preflight_receipt(self, revision=REVISION):
        install.write_receipt(self.tmp, 'preflight', {'phase': 'preflight', 'ok': True, 'revision': revision,
                                                      'details': {'routing': {}, 'app_health': {'status': 200}}})

    # -- fakes ---------------------------------------------------------------------------------------------------------
    def inspect(self, kind, name):
        self.act('inspect', kind, name)
        if kind == 'image':
            labels = {IMAGE: REVISION, OLD_IMAGE: OLD}
            found = None if name not in labels else {
                'Id': name, 'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'app-image',
                                                  install.REVISION_LABEL: labels[name]}}}
            return self.done(found)
        c = self.containers.get(name)
        if c is None:
            return self.done(None)
        bindings = ({'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(c['port'])}]} if c['role'] == 'web' else {})
        return self.done({'Id': c['Id'], 'Image': c['Image'], 'Created': c['created'], 'RestartCount': 0,
                          'State': {'Running': c['running'], 'Restarting': False, 'ExitCode': 0},
                          'Config': {'User': f'{install.APP_UID}:{install.APP_UID}',
                                     'Labels': {install.LABEL: '1', install.ROLE_LABEL: c['role'],
                                                install.REVISION_LABEL: c['revision']}},
                          'HostConfig': {'PortBindings': bindings}})

    def docker(self, *args, **kwargs):
        verb = args[0]
        if verb == 'run':
            name = args[args.index('--name') + 1]
            role, image = args[-1], args[-2]
            port = int(flags(args, '-p')[0].split(':')[1]) if role == 'web' else None
            revision = next(value.split('=', 1)[1] for value in flags(args, '--label')
                            if value.startswith(install.REVISION_LABEL + '='))
            self.act('run', role, name, port, image)
            if name in self.containers:
                raise install.InstallError(f'docker run: the name {name} is in use')
            if role == 'worker':
                assert not [n for n, c in self.containers.items() if c['role'] == 'worker' and c['running']], \
                    'I-worker: a worker was started while another ran'
            self.add(name, role, image, revision, port=port)
        elif verb == 'stop':
            name, seconds = args[-1], args[args.index('--time') + 1]
            self.act('stop', name, seconds)
            if name in self.containers:
                self.containers[name]['running'] = False
        elif verb == 'rename':
            self.act('rename', args[1], args[2])
            if args[2] in self.containers or args[1] not in self.containers:
                raise install.InstallError(f'docker rename {args[1]} {args[2]} failed')
            self.containers[args[2]] = self.containers.pop(args[1])
        elif verb == 'rm':
            name = self.by_id(args[-1]) or args[-1]
            self.act('rm', name)
            self.containers.pop(name, None)
        elif verb == 'start':
            self.act('start', args[1])
            self.containers[args[1]]['running'] = True
        elif verb == 'logs':
            self.act('logs', args[-1])
        else:
            raise AssertionError(f'unexpected docker {args}')
        return self.done(SimpleNamespace(returncode=0, stdout=b'', stderr=b''))

    def wait_service(self, role, revision, image_id, *, name=None, port=install.WEB_PORT):
        name = name or install.SERVICES[role]
        self.act('wait', role, name, port if role == 'web' else None)
        c = self.containers.get(name)
        if c is None or not c['running'] or not c['healthy'] or c['revision'] != revision or c['Image'] != image_id \
                or (role == 'web' and c['port'] != port):
            raise install.InstallError(f'{name} did not become ready: readiness not observed.')
        return self.done({'id': c['Id'], 'observations': 2})

    def smoke_web(self, port):
        self.act('smoke', port)
        assert self.web_on(port) is not None
        return self.done({'login': {'status': 200, 'content_type': 'text/html; charset=utf-8'},
                          'assets': {'/static/studio/styles.0123456789ab.css': 200}})

    def vhost_state(self):
        self.act('vhost-state')
        return self.done({'file_exists': True, 'file_sha256': sha(self.vhost_text), 'link_exists': True,
                          'link_target': install.VHOST_LINK_TARGET})

    def live_vhost_bytes(self):
        self.act('vhost-read')
        return self.done(self.vhost_text.encode())

    def vhost_operation(self, op, **params):
        content = base64.b64decode(params.get('content', '')).decode()
        self.act('vhost', op, install.proxied_port(content))
        assert op == 'replace', op
        if params['expected_sha256'] != sha(self.vhost_text):
            raise install.InstallError('Root helper refused: quillmd-cpt is not in the expected state')
        self.vhost_text = content
        return self.done({'done': 'replaced'})

    def nginx_test(self):
        self.act('nginx-t')
        answer = self.nginx_answers.pop(0) if self.nginx_answers else {}
        return self.done({'ok': True, 'warnings': [], 'output': 'nginx: configuration file test is successful',
                          **answer})

    def nginx_reload(self):
        self.act('reload', self.file_port())
        moved = self.file_port() != self.nginx_port
        if moved:
            assert not [n for n, c in self.containers.items() if c['role'] == 'worker' and c['running']], \
                'a worker still ran when nginx moved its traffic'
            self.inflight[self.nginx_port] = self.inflight.get(self.nginx_port, 0) + 2  # old workers finish these
        self.nginx_port = self.file_port()
        return self.done()

    def https_checks(self, ctx, revision=None):
        expected = revision or ctx.revision
        self.act('https', self.nginx_port, expected)
        web = self.web_on(self.nginx_port)
        passed = web is not None and web['healthy'] and web['revision'] == expected
        return self.done(([] if passed else [f'https://cpt.quillmd.com/health/ did not serve revision {expected[:12]}'],
                          {'observations': [{'attempt': 0, 'status': 200 if passed else 503}],
                           'final': {'status': 200 if passed else 503}}))

    def ingress_checks(self, ctx, preflight):
        self.act('ingress')
        return self.done([])

    def drain_web(self, port):
        self.act('drain', port)
        assert port != self.nginx_port, f'drained {port} while nginx still routes to it'
        self.inflight[port] = 0  # the drain's samples saw them end (DrainTests pin how)
        return self.done({'port': port, 'seconds': 130.0, 'samples': 131, 'bounded_out': False, 'connections': 2,
                          'shutting_down': 1, 'unreadable': 0, 'nginx_unseen': 0})

    def host_listening_ports(self):
        self.act('ports')
        return self.done({c['port'] for c in self.containers.values() if c['role'] == 'web' and c['running']})

    def close(self, image_id, env_bytes, since, revision, reason, kinds):
        self.act('close', image_id, tuple(kinds))
        self.closes.append({'image': image_id, 'since': since, 'revision': revision, 'reason': reason,
                            'kinds': list(kinds)})
        return self.done(json.loads(json.dumps(self.close_answer)))

    def put_back(self, closed, older_image, image_id, env_bytes):
        self.act('put_back', older_image)
        self.put_backs.append(older_image)
        return self.done({'encounters': 0, 'changed': {}})

    def stage_kinds_of(self, image_id, env_bytes):
        self.act('kinds', image_id)
        return self.done(list(self.stage_kinds.get(image_id, install.COMMON_STAGE_KINDS)))

    def undo_hazards(self, image_id, env_bytes, revision):
        self.act('hazards', image_id)
        return self.done(dict(self.hazards_answer))

    def app_script(self, image_id, env_bytes, body, params, **kwargs):
        if body == install.RECOMPUTE_STATES:
            self.act('recompute', image_id, 'some' if params.get('encounters') is not None else 'all')
            if params.get('encounters') is None and self.checking:
                others = [n for n, c in self.containers.items() if c['running'] and c['Image'] != image_id]
                assert not others, f'I-state: the stored list states were recomputed while {others} ran'
                self.recomputes.append(image_id)
            return self.done({'encounters': 0, 'changed': {}})
        if body == install.UNRUNNABLE_STAGES:
            self.act('unrunnable', image_id)
            return self.done({'known': self.stage_kinds.get(image_id, KINDS_OLD), 'stuck': 0, 'kinds': []})
        raise AssertionError('unexpected in-image script')

    def oneshot(self, image_id, command, env_bytes, **kwargs):
        self.act('oneshot', tuple(command[:2]))
        return self.done(SimpleNamespace(returncode=0, stdout=b'corti-credentials-parse-ok\n', stderr=b''))

    def rendered_vhosts(self, revision, port=install.WEB_PORT):
        return self.confs[port]

    def recorder(self, world=None):
        world = self

        class Recorder:
            def start(self):
                world.act('recorder', 'start')
                world.availability = []
                return self

            def stop(self):
                world.act('recorder', 'stop')
                seen, world.availability = world.availability or [], None
                return {'samples': len(seen), 'statuses': {str(s): seen.count(s) for s in set(seen)},
                        'releases_seen': [], 'non_200': [], 'non_200_count': sum(1 for s in seen if s != 200)}
        return Recorder()

    def patches(self):
        return [mock.patch.multiple(
            install, inspect=self.inspect, docker=self.docker, wait_service=self.wait_service,
            smoke_web=self.smoke_web, vhost_state=self.vhost_state, live_vhost_bytes=self.live_vhost_bytes,
            vhost_operation=self.vhost_operation, nginx_test=self.nginx_test, nginx_reload=self.nginx_reload,
            https_checks=self.https_checks, ingress_checks=self.ingress_checks, drain_web=self.drain_web,
            host_listening_ports=self.host_listening_ports, close_undone_stages=self.close,
            put_back_states=self.put_back, stage_kinds_of=self.stage_kinds_of, undo_hazards=self.undo_hazards,
            app_script=self.app_script, oneshot=self.oneshot, rendered_vhosts=self.rendered_vhosts,
            AvailabilityRecorder=self.recorder, installed_image=mock.Mock(return_value=IMAGE),
            require_db=mock.Mock(), helper_stat=mock.Mock(return_value={}),
            read_protected_env=mock.Mock(return_value=b'CPT_STUDIO_SECRET_KEY=synthetic\n'),
            run=mock.Mock(return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')))]

    # -- what the tests read ---------------------------------------------------------------------------------------------
    def names(self):
        return {name: (c['Image'], c['port'], c['running']) for name, c in self.containers.items()}

    def acts(self, *kinds):
        return [event for event in self.events if event[0] in kinds]


def app_args(tmp, **extra):
    values = dict(phase='app', revision=REVISION, receipts=str(tmp), provider_mode='disabled', authorization_ref='',
                  astra_mode='disabled', fable_mode='disabled', access_check=None)
    values.update(extra)
    return SimpleNamespace(**values)


def run_app(world, args=None):
    """The REAL phase_app in ``world``; (details or None, the InstallError or None)."""
    patches = world.patches()
    for patcher in patches:
        patcher.start()
    try:
        return install.phase_app(install.Context(args or app_args(world.tmp), world.tmp)), None
    except install.InstallError as error:
        return None, error
    finally:
        for patcher in reversed(patches):
            patcher.stop()


# --- the guard itself -------------------------------------------------------------------------------------------------

class HostGuardTests(unittest.TestCase):
    def test_controls_the_guard_refuses_docker_sudo_and_live_ports_and_records_them(self):
        before = len(HOST_GUARD_ATTEMPTS)
        for argv in ([install.DOCKER, 'version'], ['sudo', '-n', '/usr/sbin/nginx', '-t'], ['/usr/sbin/nginx', '-t']):
            with self.subTest(argv=argv), self.assertRaisesRegex(AssertionError, 'a test tried to run'):
                install.run(argv, check=False)
        for address in (('127.0.0.1', 443), ('127.0.0.1', 9150), ('127.0.0.1', 9151), ('127.0.0.1', 55451),
                        ('147.189.172.8', 8443), ('cpt.quillmd.com', 443)):
            with self.subTest(address=address), self.assertRaisesRegex(AssertionError, 'a test tried to connect'):
                install.socket.create_connection(address, 1)
        self.assertEqual(len(HOST_GUARD_ATTEMPTS), before + 9)
        del HOST_GUARD_ATTEMPTS[before:]  # these were this test's own: the module's teardown must not fail on them
        self.assertEqual(install.run(['git', '--version']).returncode, 0)  # what tests may run still runs


# --- rendering and ports --------------------------------------------------------------------------------------------------

class RenderTests(unittest.TestCase):
    def test_each_port_s_https_stage_begins_with_the_http_stage_and_they_differ_in_one_line(self):
        confs = {port: rendered(port) for port in install.WEB_PORTS}
        for port, conf in confs.items():
            self.assertTrue(conf['https'].startswith(conf['http']), port)
            self.assertEqual(conf['http'], confs[install.WEB_PORT]['http'])
        changed = [line for line in difflib.unified_diff(confs[9150]['https'].splitlines(),
                                                         confs[9151]['https'].splitlines(), lineterm='', n=0)
                   if line[:1] in '+-' and not line.startswith(('+++', '---'))]
        self.assertEqual(changed, ['-        proxy_pass http://127.0.0.1:9150;', '+        proxy_pass http://127.0.0.1:9151;'])

    def test_proxied_port_reads_one_loopback_web_port_and_nothing_else(self):
        for port in install.WEB_PORTS:
            self.assertEqual(install.proxied_port(rendered(port)['https']), port)
        https = rendered()['https']
        line = '        proxy_pass http://127.0.0.1:9150;\n'
        self.assertEqual(https.count(line), 1)
        cases = {'the HTTP stage': rendered()['http'], 'nothing': '', 'None': None,
                 'doubled': https.replace(line, line + line),
                 'another host': https.replace(line, '        proxy_pass http://10.0.0.1:9150;\n'),
                 'another port': https.replace(line, '        proxy_pass http://127.0.0.1:9152;\n'),
                 'https upstream': https.replace(line, '        proxy_pass https://127.0.0.1:9150;\n'),
                 'a path': https.replace(line, '        proxy_pass http://127.0.0.1:9150/x;\n'),
                 'a variable': https.replace(line, '        proxy_pass $upstream;\n'),
                 'only in a comment': https.replace(line, '        # proxy_pass http://127.0.0.1:9150;\n')}
        for label, text in cases.items():
            with self.subTest(label):
                self.assertIsNone(install.proxied_port(text))

    def test_the_renderings_are_the_http_stage_once_and_the_https_stage_per_port(self):
        with mock.patch.object(install, 'rendered_vhosts', side_effect=lambda revision, port: rendered(port)):
            found = install.vhost_renderings(REVISION)
        # R7 said four; the HTTP stage names no upstream, so one rendering of it serves both ports: three contents
        self.assertEqual(len(found), 3)
        self.assertEqual(sorted((info['kind'], info['port']) for info in found.values()),
                         [('http', None), ('https', 9150), ('https', 9151)])
        for digest, info in found.items():
            self.assertEqual(digest, sha(info['text']))
        with self.assertRaisesRegex(install.InstallError, 'must be one of 9150, 9151'):
            install.upstream(9152)


class PortArgumentTests(unittest.TestCase):
    def test_the_incoming_web_differs_from_the_serving_one_in_its_name_and_port_alone(self):
        modes = {'astra': 'live', 'fable': 'disabled'}
        serving = install.service_args('web', IMAGE, REVISION, 'live', RULING, modes)
        incoming = install.service_args('web', IMAGE, REVISION, 'live', RULING, modes, name=NEXT, port=9151)
        self.assertEqual(flags(incoming, '--name'), [NEXT])
        self.assertEqual(flags(incoming, '-p'), ['127.0.0.1:9151:8000'])
        normalised = [WEB if part == NEXT else '127.0.0.1:9150:8000' if part == '127.0.0.1:9151:8000' else part
                      for part in incoming]
        self.assertEqual(normalised, serving)
        self.assertEqual(install.service_args('web', IMAGE, REVISION, 'live', RULING, modes, port=9150), serving)

    def test_the_worker_has_one_name_and_no_port(self):
        worker = install.service_args('worker', IMAGE, REVISION, 'disabled', '')
        self.assertEqual(install.service_args('worker', IMAGE, REVISION, 'disabled', '', port=9151), worker)
        self.assertEqual(flags(worker, '-p'), [])
        for name in (NEXT, WORKER + '-previous', 'cpt-studio-worker-2'):
            with self.subTest(name=name), self.assertRaises(install.InstallError):
                install.service_args('worker', IMAGE, REVISION, 'disabled', '', name=name)
        for name in (WEB + '-previous', 'cpt-studio-web-2', WORKER):
            with self.subTest(name=name), self.assertRaises(install.InstallError):
                install.service_args('web', IMAGE, REVISION, 'disabled', '', name=name)
        with self.assertRaises(install.InstallError):
            install.service_args('web', IMAGE, REVISION, 'disabled', '', port=9152)

    def test_published_port_and_the_other_port(self):
        def web(port, host_ip='127.0.0.1', extra=None):
            bindings = {'8000/tcp': [{'HostIp': host_ip, 'HostPort': str(port)}], **(extra or {})}
            return {'HostConfig': {'PortBindings': bindings}}
        self.assertEqual(install.published_port(web(9150)), 9150)
        self.assertEqual(install.published_port(web(9151)), 9151)
        for container in (web(9152), web(9150, '0.0.0.0'), web(9150, extra={'9000/tcp': []}), {}, None,
                          {'HostConfig': {'PortBindings': {'8000/tcp': []}}}):
            with self.subTest(container=container):
                self.assertIsNone(install.published_port(container))
        self.assertEqual((install.other_port(9150), install.other_port(9151)), (9151, 9150))


# --- the success path -------------------------------------------------------------------------------------------------

ACTS = ('recorder', 'run', 'wait', 'smoke', 'stop', 'rename', 'vhost', 'reload', 'https', 'drain', 'rm', 'start',
        'close', 'put_back', 'recompute')


class SuccessPathTests(TemporaryDirectoryTest):
    def test_the_exact_order_of_S1_to_S6_and_the_final_names(self):
        world = BlueGreenWorld(self.tmp)
        details, error = run_app(world)
        self.assertIsNone(error)
        self.assertEqual(world.acts(*ACTS), [
            ('recorder', 'start'),
            ('run', 'web', NEXT, 9151, IMAGE), ('wait', 'web', NEXT, 9151), ('smoke', 9151),          # S1
            ('stop', WORKER, '600'), ('rename', WORKER, WORKER + '-previous'),                           # S2
            ('vhost', 'replace', 9151), ('reload', 9151), ('https', 9151, REVISION),                     # S3
            ('run', 'worker', WORKER, None, IMAGE), ('wait', 'worker', WORKER, None),                    # S4
            ('drain', 9150), ('stop', WEB, '30'), ('rename', WEB, WEB + '-previous'), ('rename', NEXT, WEB),  # S5
            ('recorder', 'stop'),
            ('recompute', IMAGE, 'all'), ('rm', WORKER + '-previous'), ('rm', WEB + '-previous')])     # S6
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        migrate = world.events.index(('oneshot', ('migrate',)))
        self.assertLess(migrate, world.events.index(('run', 'web', NEXT, 9151, IMAGE)))  # migrations first
        self.assertEqual(world.closes, [])  # nothing is closed on success
        self.assertEqual(details['ports'], {'from': 9150, 'to': 9151})
        self.assertEqual(details['mode'], 'blue-green')
        self.assertEqual(details['replacement']['mode'], 'blue-green')
        switch = details['switch']
        self.assertEqual((switch['vhost_sha_before'], switch['vhost_sha_after']),
                         (sha(world.confs[9150]['https']), sha(world.confs[9151]['https'])))
        self.assertEqual(details['drain']['bounded_out'], False)
        self.assertEqual(details['availability']['non_200_count'], 0)
        self.assertGreater(details['availability']['samples'], 20)
        self.assertEqual(sorted(details['steps']), ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'done'])
        self.assertEqual(details['replaced']['web']['revision'], OLD)
        self.assertEqual(details['replaced']['worker']['image'], OLD_IMAGE)
        self.assertIn('switched blue/green 9150 -> 9151', details['summary'])
        self.assertIn('0 not 200', details['summary'])

    def test_a_second_install_flips_back_to_9150(self):
        world = BlueGreenWorld(self.tmp)
        self.assertIsNone(run_app(world)[1])
        # the next install's own receipt directory holds its preflight; the same revision installs again
        world.events.clear()
        details, error = run_app(world)
        self.assertIsNone(error)
        self.assertEqual(details['ports'], {'from': 9151, 'to': 9150})
        self.assertEqual(world.names(), {WEB: (IMAGE, 9150, True), WORKER: (IMAGE, None, True)})
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))

    def test_the_receipt_through_main(self):
        world = BlueGreenWorld(self.tmp)
        receipts = self.tmp / 'receipts'
        receipts.mkdir(mode=0o700)
        os.chmod(receipts, 0o700)
        install.write_receipt(receipts, 'preflight', {'phase': 'preflight', 'ok': True, 'revision': REVISION,
                                                      'details': {'routing': {}, 'app_health': {'status': 200}}})
        output = io.StringIO()
        patches = world.patches() + [
            mock.patch.object(install, 'check_door', return_value={'declaration_commit': OTHER_COMMIT}),
            mock.patch.object(install, 'check_tree', return_value={'mode': 'exact'}),
            mock.patch('sys.stdout', output)]
        for patcher in patches:
            patcher.start()
        try:
            code = install.main(['--phase', 'app', '--revision', REVISION, '--receipts', str(receipts),
                                 '--provider-mode', 'disabled'])
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        printed = json.loads(output.getvalue().strip().splitlines()[-1])
        self.assertEqual((code, printed['ok']), (0, True), printed)
        record = json.loads(Path(printed['receipt']).read_text())
        for key in ('ports', 'switch', 'drain', 'availability', 'steps', 'replacement', 'smoke'):
            self.assertIn(key, record['details'])
        self.assertEqual(set(record['details']['availability']),
                         {'samples', 'statuses', 'releases_seen', 'non_200', 'non_200_count'})

    def test_a_host_where_nothing_is_served_through_the_vhost_is_swapped_as_before(self):
        for case in ('no vhost', 'http stage', 'https stage, no running web'):
            world = BlueGreenWorld(self.tmp)
            world.checking = False
            if case == 'http stage':
                world.vhost_text = world.confs[9150]['http']
            elif case == 'https stage, no running web':
                world.containers[WEB]['running'] = False
            with self.subTest(case=case):
                patches = world.patches()
                if case == 'no vhost':
                    patches.append(mock.patch.object(install, 'vhost_state', return_value={
                        'file_exists': False, 'file_sha256': None, 'link_exists': False, 'link_target': None}))
                for patcher in patches:
                    patcher.start()
                try:
                    with mock.patch.object(install, 'swap_services',
                                           return_value={'started': {}, 'replaced': {}}) as swap, \
                            mock.patch.object(install, 'switch_services') as switch:
                        details = install.phase_app(install.Context(app_args(self.tmp), self.tmp))
                finally:
                    for patcher in reversed(patches):
                        patcher.stop()
                switch.assert_not_called()
                self.assertEqual(swap.call_args.kwargs, {'port': 9150})
                self.assertEqual(details['replacement']['mode'], 'fresh')


OTHER_COMMIT = 'e' * 40


# --- the failure matrix: one test per row -----------------------------------------------------------------------------

class FailureArmTests(TemporaryDirectoryTest):
    """Each arm runs the REAL undo; the world's invariant held after every call of it (or the test would have failed
    inside the fake), and each test asserts where it ended: which web serves, which worker runs or is held, the vhost
    bytes, and what was closed."""

    def failed(self, world):
        details, error = run_app(world)
        self.assertIsNone(details, 'the phase passed')
        self.assertIsInstance(error, install.InstallError)
        world.invariant()
        return str(error), error.details or {}

    def assert_old_pair_serves(self, world, *, worker_running=True):
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, worker_running)})
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        self.assertEqual(world.vhost_text, world.confs[9150]['https'])  # the exact bytes

    def test_s1_an_incoming_web_that_is_not_healthy_is_removed_and_nothing_else_changes(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(NEXT)
        message, details = self.failed(world)
        self.assert_old_pair_serves(world)
        self.assertIn('nothing else changed', message)
        self.assertEqual(details['failed_at'], 'S1')
        self.assertEqual(world.acts('stop', 'reload', 'close', 'vhost'), [('stop', NEXT, '30')])
        self.assertEqual(details['availability']['non_200_count'], 0)
        self.assertEqual(details['left']['vhost_port'], 9150)

    def test_s1_a_smoke_check_that_fails_removes_the_incoming_web(self):
        world = BlueGreenWorld(self.tmp)
        world.fail[('smoke',)] = install.InstallError('The incoming web did not serve its own pages: /login/ answered 500')
        message, details = self.failed(world)
        self.assert_old_pair_serves(world)
        self.assertIn('/login/ answered 500', message)
        self.assertNotIn(('stop', WORKER, '600'), world.events)

    def test_s2_a_worker_rename_that_fails_restarts_the_old_worker(self):
        world = BlueGreenWorld(self.tmp)
        world.fail[('rename', WORKER, WORKER + '-previous')] = install.InstallError('docker rename failed')
        message, details = self.failed(world)
        self.assert_old_pair_serves(world)
        self.assertEqual(details['failed_at'], 'S2')
        self.assertIn(('start', WORKER), world.events)  # park's own restart
        self.assertEqual(world.closes, [])
        self.assertNotIn(NEXT, world.containers)

    def test_s3_nginx_t_failing_after_the_change_restores_the_bytes_and_resumes_the_old_worker(self):
        for label, answers in (('nginx -t fails', [{}, {'ok': False}]),
                               ('a new warning', [{}, {'warnings': ['conflicting server name "x"']}])):
            with self.subTest(label):
                world = BlueGreenWorld(self.tmp)
                world.nginx_answers = answers
                message, details = self.failed(world)
                self.assert_old_pair_serves(world)
                self.assertEqual(world.acts('reload'), [])  # never reloaded with the change
                self.assertEqual([close['kinds'] for close in world.closes], [KINDS_OLD])  # the old worker's kinds
                self.assertEqual(world.closes[0]['image'], IMAGE)  # in the new image, as every undo's close
                self.assertNotIn(('drain', 9151), world.events)  # it took no traffic
                self.assertIn('the vhost was put back', message)

    def test_s3_a_failed_verification_after_the_reload_drains_the_incoming_web_before_removing_it(self):
        world = BlueGreenWorld(self.tmp)
        world.fail[('https', 9151)] = install.InstallError('https://cpt.quillmd.com/health/ did not serve it')
        message, details = self.failed(world)
        self.assert_old_pair_serves(world)
        self.assertEqual(world.acts('reload'), [('reload', 9151), ('reload', 9150)])
        drain, remove = world.events.index(('drain', 9151)), world.events.index(('stop', NEXT, '30'))
        self.assertLess(drain, remove)
        self.assertEqual(len(world.closes), 1)
        self.assertGreaterEqual(world.closes[0]['since'], dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
        self.assertEqual(world.put_backs, [OLD_IMAGE])  # the old pair's own derivation
        self.assertEqual(details['availability']['non_200_count'], 0)

    def test_s3_a_reload_that_fails_restores_the_file_without_reloading(self):
        world = BlueGreenWorld(self.tmp)
        world.fail[('reload',)] = install.InstallError('sudo systemctl reload nginx failed with exit 1.')
        message, details = self.failed(world)
        self.assert_old_pair_serves(world)
        self.assertEqual(world.acts('reload'), [('reload', 9151)])  # attempted, failed, not repeated

    def test_s3_acting_hazards_hold_the_old_worker_and_shown_ones_are_named_only(self):
        world = BlueGreenWorld(self.tmp)
        world.fail[('https', 9151)] = install.InstallError('it did not serve')
        world.close_answer = {'closed': 1, 'kinds': [], 'hazards': {'e1': ['unknown'], 'e2': ['participant']},
                              'relabel': []}
        message, details = self.failed(world)
        self.assert_old_pair_serves(world, worker_running=False)
        self.assertNotIn(('start', WORKER), world.events)
        self.assertIn('It is held - nothing can be sent', message)
        self.assertIn('unknown 1', message)
        self.assertIn('participant 1', message)

    def test_s4_an_unstable_new_worker_switches_back_without_interrupting_the_site(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        message, details = self.failed(world)
        self.assert_old_pair_serves(world)
        self.assertEqual(world.acts('reload'), [('reload', 9151), ('reload', 9150)])
        order = [world.events.index(event) for event in (
            ('stop', WORKER, '600'), ('close', IMAGE, tuple(KINDS_OLD)), ('put_back', OLD_IMAGE), ('reload', 9150),
            ('https', 9150, OLD), ('drain', 9151), ('stop', NEXT, '30'), ('rename', WORKER + '-previous', WORKER),
            ('start', WORKER))]
        self.assertEqual(order, sorted(order))
        self.assertIn('the vhost was switched back', message)
        self.assertEqual(details['failed_at'], 'S4')
        self.assertEqual(details['availability']['non_200_count'], 0)

    def test_s4_shown_hazards_keep_the_new_web_serving_with_nothing_processed(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = {'closed': 1, 'kinds': [], 'hazards': {'e1': ['participant']}, 'relabel': []}
        message, details = self.failed(world)
        self.assertEqual(world.names(), {NEXT: (IMAGE, 9151, True), WEB: (OLD_IMAGE, 9150, True),
                                         WORKER: (IMAGE, None, False), WORKER + '-previous': (OLD_IMAGE, None, False)})
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertEqual(world.acts('reload'), [('reload', 9151)])  # no switch back
        self.assertIn('the new web keeps serving on 9151', message)
        self.assertIn('participant 1', message)

    def test_s4_acting_hazards_switch_back_and_hold_the_old_worker(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = {'closed': 1, 'kinds': [], 'hazards': {'e1': ['outcome']}, 'relabel': []}
        message, details = self.failed(world)
        self.assert_old_pair_serves(world, worker_running=False)
        self.assertIn('It is held - nothing can be sent', message)

    def test_s4_a_close_that_fails_keeps_the_new_web_serving(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.fail[('close',)] = install.InstallError('Closing the stages failed (exit 1).')
        message, details = self.failed(world)
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertIn('could not be closed', message)
        self.assertFalse(world.containers[WORKER]['running'])

    def test_s4_a_switch_back_that_fails_leaves_the_new_web_serving(self):
        world = BlueGreenWorld(self.tmp)
        world.unhealthy.add(WORKER)
        world.fail[('https', 9150)] = install.InstallError('it did not serve the old revision')
        message, details = self.failed(world)
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertEqual(world.vhost_text, world.confs[9151]['https'])
        self.assertIn('the switch back to the old web failed', message)
        self.assertIn('rerun --phase app, which recomputes them', message)

    def test_s5_a_rename_that_fails_leaves_the_new_pair_serving_and_says_what_is_left(self):
        world = BlueGreenWorld(self.tmp)
        world.fail[('rename', NEXT, WEB)] = install.InstallError('docker rename failed')
        message, details = self.failed(world)
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertEqual(world.names(), {NEXT: (IMAGE, 9151, True), WEB + '-previous': (OLD_IMAGE, 9150, False),
                                         WORKER: (IMAGE, None, True), WORKER + '-previous': (OLD_IMAGE, None, False)})
        self.assertIn('the incoming pair serves', message)
        self.assertNotIn(('recompute', IMAGE, 'all'), world.events)  # S6 never ran
        self.assertEqual(details['left']['containers'][NEXT]['port'], 9151)

    def test_s6_a_recompute_that_fails_says_the_parked_pair_is_left(self):
        world = BlueGreenWorld(self.tmp)
        world.fail[('recompute', IMAGE, 'all')] = install.InstallError('Recomputing the stored list states failed')
        message, details = self.failed(world)
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertIn('the stored list states were not recomputed', message)
        self.assertIn('the previous pair is still parked', message)

    def test_a_plan_refusal_changes_nothing(self):
        cases = {
            'the idle port is held': lambda world: world.add('foreign-web', 'web', 'sha256:' + 'f' * 64, OLD,
                                                             port=9151),
            'an incoming web is left': lambda world: world.add(NEXT, 'web', IMAGE, REVISION, port=9152,
                                                               running=False),
            'a parked worker is left': lambda world: world.add(WORKER + '-previous', 'worker', OLD_IMAGE, OLD,
                                                               running=False),
            'the vhost names another port than the web': lambda world: world.containers[WEB].update(port=9151),
            'the vhost is not ours': lambda world: setattr(world, 'vhost_text', world.confs[9150]['https'] + '#\n'),
            'the web carries no revision label': lambda world: world.containers[WEB].update(revision=''),
        }
        for label, change in cases.items():
            world = BlueGreenWorld(self.tmp)
            world.checking = False
            change(world)
            with self.subTest(label):
                details, error = run_app(world)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn('nothing was started or stopped', str(error))
                self.assertEqual(world.acts('run', 'stop', 'rename', 'vhost', 'reload', 'rm'), [])

    def test_without_a_preflight_receipt_the_switch_is_refused_before_anything_starts(self):
        world = BlueGreenWorld(self.tmp)
        for path in self.tmp.glob('preflight-*.json'):
            path.unlink()
        details, error = run_app(world)
        self.assertIn('No successful --phase preflight receipt', str(error))
        self.assertEqual(world.acts('run', 'stop', 'rename', 'vhost', 'reload'), [])


# --- an interrupt at every fake call ------------------------------------------------------------------------------------

class InterruptAtEveryStepTests(TemporaryDirectoryTest):
    def test_ctrl_c_at_any_call_leaves_a_healthy_web_behind_the_vhost_and_says_what_is_left(self):
        clean = BlueGreenWorld(self.tmp)
        self.assertIsNone(run_app(clean)[1])
        total = clean.calls
        self.assertGreater(total, 40)
        outcomes = {'refused before acting': 0, 'undone or reported': 0, 'installed': 0}
        for k in range(1, total + 1):
            for path in self.tmp.glob('*.json'):
                path.unlink()
            for path in self.tmp.glob('*.log'):
                path.unlink()
            world = BlueGreenWorld(self.tmp)
            world.interrupt_at = k
            with self.subTest(call=k):
                try:
                    details, error = run_app(world)
                except KeyboardInterrupt:
                    # only before anything acted: the incoming web was never started
                    self.assertFalse([event for event in world.events if event[0] == 'run'], world.events[-3:])
                    outcomes['refused before acting'] += 1
                    world.invariant()
                    continue
                world.invariant()  # I-web, I-worker after the handling, whatever was left
                if error is None:
                    outcomes['installed'] += 1  # the interrupt landed in a call whose failure is recorded, not raised
                    continue
                outcomes['undone or reported'] += 1
                self.assertTrue(str(error))
                inside = error.details is not None and 'left' in error.details
                self.assertTrue(inside or 'web and worker running' in str(error), str(error))
        self.assertEqual(outcomes['installed'], 0)  # a Ctrl-C is never swallowed: the receipt says what is left
        self.assertGreater(outcomes['undone or reported'], 20)
        self.assertGreater(outcomes['refused before acting'], 5)


class StopTimeoutBlueGreenTests(TemporaryDirectoryTest):
    def test_no_path_stops_a_worker_with_less_than_600_seconds(self):
        worlds = []
        for fault in (None, 'S3', 'S4'):
            world = BlueGreenWorld(self.tmp)
            if fault == 'S3':
                world.fail[('https', 9151)] = install.InstallError('it did not serve')
            elif fault == 'S4':
                world.unhealthy.add(WORKER)
            run_app(world)
            worlds.append(world)
        for world in worlds:
            for event in world.acts('stop'):
                name, seconds = event[1], event[2]
                if name.startswith(WORKER):
                    self.assertEqual(seconds, '600', event)
                else:
                    self.assertEqual(seconds, '30', event)


# --- the drain ------------------------------------------------------------------------------------------------------------

class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class DrainTests(unittest.TestCase):
    def drain(self, connections=lambda t: 0, shutting=lambda t: 0, visible=lambda t: 5, **bounds):
        clock = FakeClock()
        start = clock.now
        result = install.drain_web(9150, clock=clock, sleep=clock.sleep,
                                   sample=lambda: connections(clock.now - start),
                                   nginx=lambda: {'visible': visible(clock.now - start),
                                                  'shutting_down': shutting(clock.now - start)}, **bounds)
        return result, clock.now - start

    def test_it_waits_at_least_the_minimum_even_when_quiet_from_the_start(self):
        result, waited = self.drain()
        self.assertEqual((result['bounded_out'], waited), (False, install.DRAIN_MIN_SECONDS))
        self.assertEqual(result['seconds'], install.DRAIN_MIN_SECONDS)
        self.assertGreater(install.DRAIN_MIN_SECONDS, 120)  # above gunicorn's request timeout
        gunicorn = (APP_ROOT / 'deploy' / 'gunicorn.conf.py').read_text()
        self.assertIn('timeout = 120\n', gunicorn)

    def test_it_needs_quiet_consecutive_samples_after_the_last_connection(self):
        result, waited = self.drain(connections=lambda t: 1 if t <= 200 else 0)
        self.assertFalse(result['bounded_out'])
        self.assertEqual(waited, 201 + install.DRAIN_QUIET_SECONDS - 1)  # 10 quiet samples, one second apart
        self.assertEqual(result['connections'], 1)
        # a single busy sample inside the quiet run starts it again
        result, waited = self.drain(connections=lambda t: 1 if t <= 200 or t == 205 else 0)
        self.assertEqual(waited, 206 + install.DRAIN_QUIET_SECONDS - 1)

    def test_an_nginx_worker_still_shutting_down_keeps_it_waiting(self):
        result, waited = self.drain(shutting=lambda t: 1 if t < 300 else 0)
        self.assertEqual(waited, 300 + install.DRAIN_QUIET_SECONDS - 1)
        self.assertEqual(result['shutting_down'], 1)

    def test_it_gives_up_at_the_maximum_and_says_so(self):
        result, waited = self.drain(connections=lambda t: 3)
        self.assertEqual((result['bounded_out'], waited), (True, install.DRAIN_MAX_SECONDS))
        self.assertEqual(result['last'], {'connections': 3, 'shutting_down': 0})

    def test_what_cannot_be_told_counts_as_busy(self):
        # no nginx process seen at all (another mount namespace, a hidden /proc): never read as none shutting down
        result, waited = self.drain(visible=lambda t: 0)
        self.assertTrue(result['bounded_out'])
        self.assertEqual(result['nginx_unseen'], result['samples'])

        def broken():
            raise OSError('unreadable')
        clock = FakeClock()
        result = install.drain_web(9150, clock=clock, sleep=clock.sleep, sample=broken,
                                   nginx=lambda: {'visible': 2, 'shutting_down': 0})
        self.assertTrue(result['bounded_out'])
        self.assertEqual(result['unreadable'], result['samples'])

    def test_the_tcp_parsing_is_shared_with_listening_ports(self):
        tcp = ('  sl  local_address rem_address   st tx_queue\n'
               '   0: 0100007F:23BE 00000000:0000 0A 00000000\n'      # 127.0.0.1:9150 listening (docker-proxy)
               '   1: 0100007F:23BE 0100007F:C350 01 00000000\n'      # docker-proxy's side of a proxied request
               '   2: 0100007F:C351 0100007F:23BE 01 00000000\n'      # nginx's side of it
               '   3: 0100007F:C352 0100007F:23BE 06 00000000\n'      # time-wait: finished
               '   4: 0100007F:C353 0100007F:23BF 02 00000000\n'      # opening to 9151
               '   5: 0100007F:C354 0100007F:23BE 08 00000000\n')     # close-wait: the request ended
        tcp6 = ('  sl  local_address                         remote_address                        st\n'
                '   0: 0000000000000000FFFF00000100007F:C355 0000000000000000FFFF00000100007F:23BE 03\n')
        self.assertEqual(install.listening_ports([tcp, tcp6]), {9150})
        self.assertEqual(install.active_connections(9150, [tcp, tcp6]), 3)
        self.assertEqual(install.active_connections(9151, [tcp, tcp6]), 1)
        self.assertEqual(install.active_connections(9146, [tcp, tcp6]), 0)
        self.assertEqual(sorted(install.tcp_entries([tcp]))[0], (0x23BE, 0, '0A'))
        with mock.patch.object(install, 'proc_net_texts', return_value=[tcp, tcp6]):
            self.assertEqual(install.established_to(9150), 3)
            self.assertEqual(install.host_listening_ports(), {9150})


class NginxProcessTests(TemporaryDirectoryTest):
    def process(self, pid, cmdline, parent):
        (self.tmp / str(pid)).mkdir()
        (self.tmp / str(pid) / 'cmdline').write_bytes(cmdline)
        (self.tmp / str(pid) / 'stat').write_text(f'{pid} (nginx) S {parent} {pid} {pid} 0 -1\n')

    def test_only_the_host_master_s_workers_count_and_shutting_down_is_read_from_their_titles(self):
        self.process(100, b'nginx: master process /usr/sbin/nginx -g daemon on; master_process on;', 1)
        self.process(101, b'nginx: worker process' + b' ' * 40, 100)
        self.process(102, b'nginx: worker process is shutting down' + b'\0' * 8, 100)
        self.process(200, b'nginx: worker process is shutting down', 199)   # a co-tenant's container nginx
        self.process(300, b'python3 -m something nginx: worker process is shutting down', 100)
        (self.tmp / 'self').mkdir()
        (self.tmp / '400').mkdir()  # ended mid-scan: no cmdline
        pid_file = self.tmp / 'nginx.pid'
        pid_file.write_text('100\n')
        self.assertEqual(install.nginx_processes(self.tmp, pid_file),
                         {'visible': 3, 'shutting_down': 1, 'master': 100})
        # no readable pid file: every nginx process counts, which can only lengthen a drain
        self.assertEqual(install.nginx_processes(self.tmp, self.tmp / 'missing.pid'),
                         {'visible': 4, 'shutting_down': 2, 'master': None})


# --- the availability record ------------------------------------------------------------------------------------------

class AvailabilityRecorderTests(unittest.TestCase):
    def test_each_sample_is_counted_by_status_with_the_releases_in_the_order_seen(self):
        answers = iter([{'status': 200, 'json': {'release': OLD}}, {'status': 200, 'json': {'release': OLD}},
                        {'status': 503}, {'error': 'ConnectionResetError'}, {'status': 200, 'json': {'release': REVISION}}])
        recorder = install.AvailabilityRecorder(check=lambda: next(answers))
        for _ in range(5):
            recorder.sample()

        def raises():
            raise RuntimeError('boom')
        recorder.check = raises
        recorder.sample()
        record = recorder.stop()
        self.assertEqual(record['samples'], 6)
        self.assertEqual(record['statuses'], {'200': 3, '503': 1, 'error': 2})
        self.assertEqual(record['releases_seen'], [OLD, REVISION])
        self.assertEqual(record['non_200_count'], 3)
        self.assertEqual([(entry['status'], entry['error']) for entry in record['non_200']],
                         [(503, None), (None, 'ConnectionResetError'), (None, 'RuntimeError')])
        self.assertTrue(all(entry['at'].endswith('Z') for entry in record['non_200']))

    def test_the_kept_samples_are_bounded_and_all_are_counted(self):
        recorder = install.AvailabilityRecorder(check=lambda: {'status': 502})
        for _ in range(install.AVAILABILITY_KEPT + 7):
            recorder.sample()
        record = recorder.stop()
        self.assertEqual((len(record['non_200']), record['non_200_count']),
                         (install.AVAILABILITY_KEPT, install.AVAILABILITY_KEPT + 7))

    def test_the_thread_samples_until_stopped_and_ends(self):
        seen = []
        recorder = install.AvailabilityRecorder(interval=0.01, check=lambda: seen.append(1) or {'status': 200})
        recorder.start()
        deadline = time.monotonic() + 5
        while len(seen) < 3 and time.monotonic() < deadline:
            time.sleep(0.01)
        record = recorder.stop()
        self.assertGreaterEqual(record['samples'], 3)
        self.assertFalse(recorder._thread.is_alive())
        self.assertEqual(record['interval_seconds'], 0.01)
        self.assertTrue(record['started_at'] and record['finished_at'])
        count = len(seen)
        time.sleep(0.05)
        self.assertEqual(len(seen), count)  # nothing after stop

    def test_the_default_check_is_the_public_health_path(self):
        with mock.patch.object(install, 'probe', return_value={'status': 200}) as probe:
            install.AvailabilityRecorder().sample()
        probe.assert_called_once_with('https', install.DOMAIN, '/health/', timeout=3)


# --- the incoming web's own pages ---------------------------------------------------------------------------------------

LOGIN_PAGE = (b'<!doctype html><html><head><link rel="icon" href="/static/studio/favicon.0a1b2c3d4e5f.svg" '
              b'type="image/svg+xml"><link rel="stylesheet" href="/static/studio/styles.9f8e7d6c5b4a.css">'
              b'</head><body><form method="post"></form></body></html>')


class _LoginHandler(http.server.BaseHTTPRequestHandler):
    statuses = {}
    page = LOGIN_PAGE
    seen = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        type(self).seen.append((self.path, self.headers.get('X-Forwarded-Proto'), self.headers.get('Host')))
        if self.path == '/login/':
            body, status, kind = type(self).page, 200, 'text/html; charset=utf-8'
        else:
            body, status, kind = b'asset', type(self).statuses.get(self.path, 200), 'text/css'
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SmokeWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), _LoginHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _LoginHandler.statuses, _LoginHandler.page, _LoginHandler.seen = {}, LOGIN_PAGE, []

    def test_the_sign_in_page_and_every_static_file_it_names_answer_200(self):
        record = install.smoke_web(self.port)
        self.assertEqual(record['login']['status'], 200)
        self.assertEqual(record['assets'], {'/static/studio/favicon.0a1b2c3d4e5f.svg': 200,
                                            '/static/studio/styles.9f8e7d6c5b4a.css': 200})
        self.assertEqual({(path, proto, host) for path, proto, host in _LoginHandler.seen},
                         {('/login/', 'https', install.DOMAIN),
                          ('/static/studio/favicon.0a1b2c3d4e5f.svg', 'https', install.DOMAIN),
                          ('/static/studio/styles.9f8e7d6c5b4a.css', 'https', install.DOMAIN)})

    def test_a_missing_static_file_or_a_page_naming_none_is_refused(self):
        _LoginHandler.statuses = {'/static/studio/styles.9f8e7d6c5b4a.css': 404}
        with self.assertRaisesRegex(install.InstallError, 'styles.9f8e7d6c5b4a.css answered 404'):
            install.smoke_web(self.port)
        _LoginHandler.statuses, _LoginHandler.page = {}, b'<html><body>no assets</body></html>'
        with self.assertRaisesRegex(install.InstallError, 'names no static file'):
            install.smoke_web(self.port)

    def test_the_committed_sign_in_template_names_static_files(self):
        template = (APP_ROOT / 'studio' / 'templates' / 'studio' / 'login.html').read_text(encoding='utf-8')
        self.assertIn("{% static '", template)


# --- preflight's ports, and the vhost phases on either port ---------------------------------------------------------------

def container_on(port, *, running=True, role='web'):
    return {'Id': f'{role}-x', 'Image': IMAGE, 'State': {'Running': running},
            'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role, install.REVISION_LABEL: REVISION}},
            'HostConfig': {'PortBindings': {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(port)}]}
                           if role == 'web' else {}}}


class PreflightPortTests(unittest.TestCase):
    def layout(self, *, web_port=9150, listening=(9150,), holders=None, leftover=False, vhost=None):
        containers = {WEB: container_on(web_port) if web_port else None, NEXT: container_on(9151) if leftover else None}
        holders = holders or {9150: [WEB], 9151: [WEB]}
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: containers.get(name)), \
                mock.patch.object(install, 'host_listening_ports', return_value=set(listening)), \
                mock.patch.object(install, 'published_by', side_effect=lambda port: holders.get(port, [])), \
                mock.patch.object(install, 'live_vhost_bytes', return_value=vhost):
            return install.web_port_layout()

    def test_the_active_port_held_by_the_web_and_the_idle_one_free_pass(self):
        for port in install.WEB_PORTS:
            with self.subTest(port=port):
                found = self.layout(web_port=port, listening=(port, 22))
                self.assertEqual(found, {'active': port, 'idle': install.other_port(port), 'problems': []})
        # a fresh host: no web, no vhost, nothing listening
        self.assertEqual(self.layout(web_port=None, listening=()), {'active': 9150, 'idle': 9151, 'problems': []})
        # no web container, but the live HTTPS stage names 9151: that is the active port
        self.assertEqual(self.layout(web_port=None, listening=(), vhost=rendered(9151)['https'].encode())['active'],
                         9151)

    def test_a_held_idle_port_or_a_leftover_incoming_web_refuses(self):
        held = self.layout(listening=(9150, 9151), holders={9150: [WEB], 9151: ['someone-else']})
        self.assertEqual(held['problems'], ["port 9151 is in use by ['someone-else'] (the incoming web's port must "
                                            "be free)"])
        foreign = self.layout(listening=(9150,), holders={9150: ['someone-else']})
        self.assertEqual(foreign['problems'], ["port 9150 is in use by ['someone-else']"])
        left = self.layout(leftover=True)
        self.assertEqual(left['problems'], [f'{NEXT} is left from an interrupted app (ops/INSTALL.md, Recovery notes)'])


class VerifyAndVhostPhaseTests(TemporaryDirectoryTest):
    def ctx(self, phase):
        return install.Context(SimpleNamespace(phase=phase, revision=REVISION, receipts=str(self.tmp)), self.tmp)

    def receipt(self, phase, details=None, revision=REVISION, ok=True):
        install.write_receipt(self.tmp, phase, {'phase': phase, 'ok': ok, 'revision': revision,
                                                'details': details or {}})

    def renderings(self):
        return mock.patch.object(install, 'rendered_vhosts', side_effect=lambda revision, port=9150: rendered(port))

    def state(self, text):
        return {'file_exists': True, 'file_sha256': sha(text), 'link_exists': True,
                'link_target': install.VHOST_LINK_TARGET}

    def verify(self, vhost_text, web_port=9151):
        files = {'available': {'quillmd': install.QUILLMD_VHOST_SHA256, install.VHOST_NAME: '1' * 64},
                 'enabled': {'quillmd': 'quillmd', install.VHOST_NAME: install.VHOST_LINK_TARGET},
                 'nginx_conf_sha256': '2' * 64, 'conf_d': {}}
        self.receipt('preflight', {'nginx_files': files, 'routing': {}, 'app_health': {'status': 200},
                                   'cotenants': {'ok': True}, 'containers': {}, 'volumes': ['v'],
                                   'letsencrypt': {'renewal': {}, 'live': {}}})
        current = {**files, 'available': {**files['available'], install.VHOST_NAME: sha(vhost_text)}}
        running = {WEB: container_on(web_port), WORKER: container_on(None, role='worker'),
                   install.DB_CONTAINER: {'State': {'Running': True}, 'Id': 'db'}}
        problems = {}
        with self.renderings(), \
                mock.patch.object(install, 'installed_image', return_value=IMAGE), \
                mock.patch.object(install, 'nginx_file_state', return_value=current), \
                mock.patch.object(install, 'live_vhost_bytes', return_value=vhost_text.encode()), \
                mock.patch.object(install, 'ingress_checks', return_value=[]), \
                mock.patch.object(install, 'cotenant_check', return_value={'ok': True}), \
                mock.patch.object(install, 'containers', return_value={}), \
                mock.patch.object(install, 'volumes', return_value=['v']), \
                mock.patch.object(install, 'le_state', return_value={'renewal': {}, 'live': {}}), \
                mock.patch.object(install, 'inspect', side_effect=lambda kind, name: running.get(name) or (
                    {} if kind == 'image' else None)), \
                mock.patch.object(install, 'db_container_problems', return_value=[]), \
                mock.patch.object(install, 'service_problems', side_effect=lambda c, role, image, port=None:
                                  (problems.setdefault(role, port), [])[1]), \
                mock.patch.object(install, 'https_checks', return_value=([], {})), \
                mock.patch.object(install, 'foreign_uid_tasks', return_value=0), \
                mock.patch.object(install, 'own_service_ids', return_value=[]):
            return install.phase_verify(self.ctx('verify')), problems

    def test_verify_accepts_the_9151_rendering_with_the_web_on_9151_and_checks_that_port(self):
        details, checked = self.verify(rendered(9151)['https'])
        self.assertIn('verified', details['summary'])
        self.assertEqual(details['web_port'], 9151)
        self.assertEqual(checked['web'], 9151)  # service_problems got the port the vhost names

    def test_verify_refuses_a_third_content_and_a_web_on_another_port(self):
        with self.assertRaisesRegex(install.InstallError, 'sites-available differs'):
            self.verify(rendered(9151)['https'] + '# edited\n')
        with self.assertRaisesRegex(install.InstallError, 'which the running cpt-studio-web does not publish'):
            self.verify(rendered(9151)['https'], web_port=9150)

    def test_cert_accepts_either_rendering_and_refuses_a_third(self):
        self.receipt('http-vhost')
        le = {'accounts': ['one', 'two'], 'live': {}, 'renewal': {}, 'dirs': {}}
        dns = [(2, 1, 6, '', (install.PUBLIC_IPV4, 80))]
        for text, expected in ((rendered(9151)['https'], 'Exactly one existing ACME account'),
                               (rendered(9150)['http'], 'Exactly one existing ACME account'),
                               (rendered(9151)['https'] + '#\n', 'not a stage this installer wrote')):
            with self.subTest(expected=expected), self.renderings(), \
                    mock.patch.object(install, 'vhost_state', return_value=self.state(text)), \
                    mock.patch.object(install.socket, 'getaddrinfo', return_value=dns), \
                    mock.patch.object(install, 'le_state', return_value=le), \
                    mock.patch.object(install, 'run_helper') as helper, \
                    self.assertRaisesRegex(install.InstallError, expected):
                install.phase_cert(self.ctx('cert'))
            helper.assert_not_called()

    def https_vhost(self, text, web_port):
        self.receipt('preflight', {'routing': {}, 'app_health': {'status': 200}})
        self.receipt('cert')
        operations = []

        def publish(ctx, apply, undo, verify):
            apply()
            return {}
        with self.renderings(), \
                mock.patch.object(install, 'vhost_state', return_value=self.state(text)), \
                mock.patch.object(install, 'le_state', return_value={'live': {install.DOMAIN: {
                    'fullchain.pem': True, 'privkey.pem': True}}}), \
                mock.patch.object(install, 'inspect', side_effect=lambda kind, name: container_on(web_port)
                                  if name == WEB else None), \
                mock.patch.object(install, 'publish_vhost', side_effect=publish), \
                mock.patch.object(install, 'https_checks', return_value=([], {})), \
                mock.patch.object(install, 'probe', return_value={'status': 301, 'headers': {
                    'location': [f'https://{install.DOMAIN}/']}}), \
                mock.patch.object(install, 'acme_probe', return_value={'passed': True, 'probe_removed': True}), \
                mock.patch.object(install, 'ingress_checks', return_value=[]), \
                mock.patch.object(install, 'vhost_operation', side_effect=lambda op, **kw: operations.append(
                    (op, kw))):
            return install.phase_https_vhost(self.ctx('https-vhost')), operations

    def test_https_vhost_renders_for_the_port_the_running_web_publishes(self):
        details, operations = self.https_vhost(rendered(9151)['http'], 9151)
        self.assertEqual(operations, [('replace', {'expected_sha256': sha(rendered(9151)['http']),
                                                   'content': base64.b64encode(
                                                       rendered(9151)['https'].encode()).decode()})])
        self.assertEqual((details['upstream_port'], details['vhost_sha256']), (9151, sha(rendered(9151)['https'])))
        details, operations = self.https_vhost(rendered(9151)['https'], 9151)
        self.assertEqual((details['already_installed'], operations), (True, []))
        with self.assertRaisesRegex(install.InstallError, 'for another port than 9151'):
            self.https_vhost(rendered(9150)['https'], 9151)

    def test_rollback_vhost_removes_either_rendering_and_refuses_a_third(self):
        self.receipt('preflight', {'routing': {}, 'app_health': {'status': 200}})
        for text, removed in ((rendered(9151)['https'], True), (rendered(9151)['https'] + '#\n', False)):
            operations = []
            with self.subTest(removed=removed), self.renderings(), \
                    mock.patch.object(install, 'vhost_state', return_value=self.state(text)), \
                    mock.patch.object(install, 'live_vhost_bytes', return_value=text.encode()), \
                    mock.patch.object(install, 'vhost_operation', side_effect=lambda op, **kw: operations.append(
                        (op, kw))), \
                    mock.patch.object(install, 'publish_vhost', side_effect=lambda ctx, apply, undo, verify:
                                      apply() or {}):
                if removed:
                    install.phase_rollback_vhost(self.ctx('rollback-vhost'))
                    self.assertEqual(operations[0][0], 'remove')
                    self.assertEqual(sorted(operations[0][1]['allowed_sha256']),
                                     sorted({sha(rendered(9150)['http']), sha(rendered(9150)['https']),
                                             sha(rendered(9151)['https'])}))
                else:
                    with self.assertRaisesRegex(install.InstallError, 'did not write'):
                        install.phase_rollback_vhost(self.ctx('rollback-vhost'))
                    self.assertEqual(operations, [])

    def test_recorded_vhosts_read_the_switch_an_app_or_switch_back_receipt_made(self):
        after = sha(rendered(9151)['https'])
        self.receipt('app', {'switch': {'vhost_sha_after': after}}, revision=OLD)
        self.receipt('switch-back', {'switch': {'vhost_sha_after': 'f' * 64}})
        self.receipt('app', {'switch': {'vhost_sha_after': '9' * 64}}, ok=False)  # a failed one records nothing
        self.receipt('https-vhost', {'vhost_sha256': sha(rendered(9150)['https'])})
        found = install.recorded_vhosts(self.ctx('rollback-vhost'))
        self.assertEqual(found, {after: (OLD, 'https'), 'f' * 64: (REVISION, 'https'),
                                 sha(rendered(9150)['https']): (REVISION, 'https')})


# --- switch-back: the rollback that never stops the serving web ----------------------------------------------------------

def switch_back_args(tmp, **extra):
    values = dict(phase='switch-back', revision=REVISION, receipts=str(tmp), provider_mode='disabled',
                  authorization_ref='', astra_mode='disabled', fable_mode='disabled')
    values.update(extra)
    return SimpleNamespace(**values)


class SwitchBackTests(TemporaryDirectoryTest):
    def world(self, *, replaced=(OLD_IMAGE, OLD)):
        world = BlueGreenWorld(self.tmp, live=9151, serving=(REVISION, IMAGE))
        if replaced is not None:
            install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
                'replaced': {'web': {'id': 'web-old', 'image': replaced[0], 'revision': replaced[1]},
                             'worker': {'id': 'worker-old', 'image': replaced[0], 'revision': replaced[1]}}}})
        return world

    def switch_back(self, world, args=None):
        patches = world.patches()
        for patcher in patches:
            patcher.start()
        try:
            return install.phase_switch_back(install.Context(args or switch_back_args(self.tmp), self.tmp)), None
        except install.InstallError as error:
            return None, error
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_the_switch_back_in_order_and_the_previous_pair_serving_after_it(self):
        world = self.world()
        details, error = self.switch_back(world)
        self.assertIsNone(error)
        self.assertEqual(world.acts(*ACTS), [
            ('recorder', 'start'),
            ('run', 'web', NEXT, 9150, OLD_IMAGE), ('wait', 'web', NEXT, 9150), ('smoke', 9150),        # B2
            ('stop', WORKER, '600'), ('rename', WORKER, WORKER + '-previous'),                            # B3
            ('close', IMAGE, tuple(KINDS_OLD)), ('put_back', OLD_IMAGE),                                  # B4
            ('vhost', 'replace', 9150), ('reload', 9150), ('https', 9150, OLD),                           # B5
            ('drain', 9151), ('stop', WEB, '30'), ('rename', WEB, WEB + '-previous'), ('rename', NEXT, WEB),  # B6
            ('close', IMAGE, tuple(KINDS_OLD)), ('put_back', OLD_IMAGE),                                  # B7
            ('run', 'worker', WORKER, None, OLD_IMAGE), ('wait', 'worker', WORKER, None),                 # B8
            ('rm', WORKER + '-previous'), ('rm', WEB + '-previous'),                                      # B9
            ('recorder', 'stop')])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        first, second = world.closes
        self.assertEqual(first['since'], dt.datetime(2026, 11, 3, 10, 1, tzinfo=dt.timezone.utc))  # the pair's start
        self.assertGreater(second['since'], first['since'])
        self.assertEqual(details['previous'], {'image': OLD_IMAGE, 'revision': OLD})
        self.assertEqual(details['availability']['non_200_count'], 0)
        self.assertIn('switched back to bbbbbbbbbbbb', details['summary'])
        self.assertEqual(world.acts('hazards'), [('hazards', IMAGE)])  # rollback-app's check, first

    def test_it_refuses_before_starting_anything(self):
        cases = {'a hazard': (dict(), 'hold records an older revision would act on'),
                 'no app receipt': (dict(replaced=None), 'No successful --phase app receipt'),
                 'the same revision': (dict(replaced=(IMAGE, REVISION)), 'this same revision'),
                 'no previous image': (dict(replaced=('sha256:' + '7' * 64, OLD)), 'is not present'),
                 'not served by this revision': ('old', 'not served by this revision')}
        for label, (change, expected) in cases.items():
            for path in self.tmp.glob('*.json'):
                path.unlink()
            if change == 'old':
                world = BlueGreenWorld(self.tmp, live=9151, serving=(OLD, OLD_IMAGE))
                install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
                    'replaced': {'web': {'image': OLD_IMAGE, 'revision': OLD}}}})
            else:
                world = self.world(**change)
            if label == 'a hazard':
                world.hazards_answer = {'e1': ['participant']}
            with self.subTest(label):
                details, error = self.switch_back(world)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn(expected, str(error))
                self.assertEqual(world.acts('run', 'stop', 'rename', 'vhost', 'reload', 'close'), [])

    def test_a_close_naming_a_record_before_the_switch_resumes_this_revision(self):
        world = self.world()
        world.close_answer = {'closed': 1, 'kinds': [], 'hazards': {'e1': ['unknown']}, 'relabel': []}
        details, error = self.switch_back(world)
        self.assertIn('nothing was switched', str(error))
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})
        self.assertEqual(world.acts('reload'), [])
        self.assertEqual(world.recomputes, [])  # nothing was put back, so nothing to recompute

    def test_a_switch_that_fails_resumes_this_revision_and_recomputes_its_states(self):
        world = self.world()
        world.fail[('https', 9150)] = install.InstallError('it did not serve the previous revision')
        details, error = self.switch_back(world)
        self.assertIn('nothing was switched', str(error))
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertEqual(world.recomputes, [IMAGE])  # the put-back states recomputed with this revision's derivation
        self.assertLess(world.events.index(('drain', 9150)), world.events.index(('stop', NEXT, '30')))

    def test_after_the_switch_a_record_holds_the_previous_worker_and_the_previous_web_serves(self):
        world = self.world()
        answers = iter([{'closed': 0, 'kinds': [], 'hazards': {}, 'relabel': []},
                        {'closed': 1, 'kinds': [], 'hazards': {'e1': ['unknown']}, 'relabel': []}])
        world.close = lambda *args: (world.act('close', args[0], tuple(args[5])), world.closes.append(args),
                                     world.done(next(answers)))[2]
        details, error = self.switch_back(world)
        self.assertIn("the previous revision's worker was not started", str(error))
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        self.assertEqual(world.names()[WEB], (OLD_IMAGE, 9150, True))
        self.assertFalse([name for name, c in world.containers.items() if c['role'] == 'worker' and c['running']])

    def test_a_previous_worker_that_does_not_become_ready_is_stopped(self):
        world = self.world()
        world.unhealthy.add(WORKER)
        details, error = self.switch_back(world)
        self.assertIn("the previous revision's worker did not become ready", str(error))
        self.assertEqual(world.names()[WEB], (OLD_IMAGE, 9150, True))
        self.assertFalse(world.containers[WORKER]['running'])


# --- the new phases' arguments -------------------------------------------------------------------------------------------

ENCOUNTER = '5f0c2a1e-8b9d-4c3e-a7f6-0123456789ab'
ENCOUNTER_2 = '6a1d3b2f-9cae-4d4f-b807-123456789abc'


class ArgumentTestCase(unittest.TestCase):
    BASE = ['--revision', REVISION, '--receipts', '/tmp/receipts']

    def parse(self, *extra):
        with mock.patch('sys.stderr', io.StringIO()):
            return install.parse_args([*self.BASE, *extra])

    def refused(self, *extra):
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as caught, mock.patch('sys.stderr', stderr):
            install.parse_args([*self.BASE, *extra])
        self.assertEqual(caught.exception.code, 2)
        return stderr.getvalue()


class SwitchBackArgumentTests(ArgumentTestCase):
    def test_the_phase_is_in_the_table(self):
        self.assertIs(install.PHASES['switch-back'], install.phase_switch_back)

    def test_switch_back_takes_the_previous_pair_s_modes_like_app_and_no_access_check(self):
        args = self.parse('--phase', 'switch-back', '--provider-mode', 'live', '--astra-mode', 'live',
                          '--authorization-ref', RULING)
        self.assertEqual((args.provider_mode, args.astra_mode, args.fable_mode), ('live', 'live', 'disabled'))
        self.assertIn('--phase switch-back needs an explicit --provider-mode', self.refused('--phase', 'switch-back'))
        self.assertIn('--provider-mode live needs --authorization-ref',
                      self.refused('--phase', 'switch-back', '--provider-mode', 'live'))
        self.refused('--phase', 'switch-back', '--provider-mode', 'disabled', '--access-check')


class OperatorsAndReassessArgumentTests(ArgumentTestCase):
    def test_the_phases_are_in_the_table(self):
        for phase, function in (('operators', install.phase_operators), ('reassess', install.phase_reassess)):
            self.assertIs(install.PHASES[phase], function)

    def test_operators_takes_only_reset_passwords(self):
        self.assertIsNone(self.parse('--phase', 'operators').reset_passwords)
        self.assertTrue(self.parse('--phase', 'operators', '--reset-passwords').reset_passwords)
        for extra in (('--owner-username', 'owner'), ('--provider-mode', 'disabled'), ('--encounter', ENCOUNTER)):
            with self.subTest(extra=extra):
                self.refused('--phase', 'operators', *extra)

    def test_reassess_takes_one_to_twenty_distinct_encounter_ids_and_dry_run(self):
        args = self.parse('--phase', 'reassess', '--encounter', ENCOUNTER, '--encounter', ENCOUNTER_2, '--dry-run')
        self.assertEqual((args.encounter, args.dry_run), ([ENCOUNTER, ENCOUNTER_2], True))
        self.assertIn('needs at least one --encounter', self.refused('--phase', 'reassess'))
        self.assertIn('must not repeat', self.refused('--phase', 'reassess', '--encounter', ENCOUNTER, '--encounter',
                                                      ENCOUNTER))
        for value in (ENCOUNTER.upper(), ENCOUNTER[:-1], 'effe4d0b b449', '../x', ENCOUNTER + ';'):
            with self.subTest(value=value):
                self.assertIn('is not a lowercase encounter id', self.refused('--phase', 'reassess', '--encounter',
                                                                             value))
        many = []
        for index in range(install.REASSESS_LIMIT + 1):
            many += ['--encounter', f'00000000-0000-4000-8000-{index:012d}']
        self.assertIn('at most 20', self.refused('--phase', 'reassess', *many))
        for phase in ('app', 'verify', 'operators'):
            with self.subTest(phase=phase):
                self.refused('--phase', phase, '--dry-run')
                self.refused('--phase', phase, '--encounter', ENCOUNTER)


# --- the operators phase ------------------------------------------------------------------------------------------------

class FakeRootFile:
    """root_file's helper (H_ROOT_FILE), on a directory standing in for /etc/cpt-studio."""

    def __init__(self, directory):
        self.directory, self.calls = directory, []

    def __call__(self, op, *, final=install.INITIAL_CREDENTIALS, staged=None, **params):
        staged = staged or f'.{final}.new'
        self.calls.append((op, final, staged))
        target, stage = self.directory / final, self.directory / staged
        if op == 'state':
            return {'final_exists': target.exists(), 'staged_exists': stage.exists()}
        if op == 'stage':
            install.write_private(self.directory, staged, base64.b64decode(params['content']))
            return {'staged': True}
        if op == 'commit':
            if target.exists() and not params.get('replace'):
                raise install.InstallError('Root helper refused: the credentials file already exists')
            os.replace(stage, target)
            return {'committed': True}
        if op == 'discard':
            if stage.exists() and sha(stage.read_text()) == params['sha256']:
                stage.unlink()
                return {'discarded': True}
            return {'discarded': False}
        raise AssertionError(op)


class OperatorsPhaseTests(TemporaryDirectoryTest):
    def setUp(self):
        super().setUp()
        self.etc, self.home = self.tmp / 'etc', self.tmp / 'home'
        self.etc.mkdir(mode=0o700)
        self.home.mkdir(mode=0o700)
        os.chmod(self.home, 0o700)
        self.agent_file = self.home / 'ops-agent-credentials.json'
        self.root = FakeRootFile(self.etc)
        self.scripts, self.oneshots, self.mounted = [], [], {}
        self.accounts_answer = None
        self.check_answer = None
        self.grant_exit = {}

    def app_script(self, image_id, env, body, params, *, what, mounts=(), user=None, **kwargs):
        self.scripts.append((body, params, list(mounts), user))
        if body == install.OPERATOR_ACCOUNTS:
            for mount in mounts:  # what the container would read: the RAM-only password files, still there
                source = mount.split('src=', 1)[1].split(',', 1)[0]
                self.mounted[Path(source).name] = Path(source).read_text()
            return self.accounts_answer or {'accounts': {spec['username']: 'reset' if params['reset'] else 'created'
                                                         for spec in params['accounts']}}
        if body == install.OPERATOR_CHECK:
            return self.check_answer or {'accounts': {
                'ops-agent': {'operator': True, 'memberships': 0, 'actor_kind': 'agent', 'active': True},
                'platform-operator': {'operator': True, 'memberships': 0, 'actor_kind': 'human', 'active': True}}}
        raise AssertionError('unexpected script')

    def oneshot(self, image_id, command, env, **kwargs):
        self.oneshots.append((command, kwargs))
        source = kwargs['mounts'][0].split('src=', 1)[1].split(',', 1)[0]
        self.mounted[Path(source).name] = Path(source).read_text()
        return SimpleNamespace(returncode=self.grant_exit.get(command[3], 0), stdout=b'granted\n', stderr=b'')

    def run_phase(self, reset=None):
        ctx = install.Context(SimpleNamespace(phase='operators', revision=REVISION, receipts=str(self.tmp),
                                              reset_passwords=reset), self.tmp)
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value=IMAGE), require_db=mock.Mock(),
                                 read_protected_env=mock.Mock(return_value=b''), root_file=self.root,
                                 app_script=self.app_script, oneshot=self.oneshot,
                                 OPS_AGENT_CREDENTIALS=self.agent_file), \
                mock.patch.dict(os.environ, {'RULED_MUTATION_DECLARATION': 'docs/foundation/mutations/x.md',
                                             'RULED_MUTATION_DECL_COMMIT': OTHER_COMMIT}):
            return install.phase_operators(ctx)

    def test_both_accounts_are_created_granted_and_read_back_with_their_logins_saved(self):
        details = self.run_phase()
        agent = json.loads(self.agent_file.read_text())
        human = json.loads((self.etc / install.OPERATOR_CREDENTIALS).read_text())
        self.assertEqual((agent['username'], agent['actor_kind']), ('ops-agent', 'agent'))
        self.assertEqual((human['username'], human['actor_kind']), ('platform-operator', 'human'))
        self.assertEqual(stat.S_IMODE(self.agent_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE((self.etc / install.OPERATOR_CREDENTIALS).stat().st_mode), 0o600)
        self.assertGreaterEqual(len(agent['password']), 32)
        self.assertNotEqual(agent['password'], human['password'])
        self.assertEqual(agent['operator_url'], 'https://cpt.quillmd.com/ops/')
        # the passwords reached the accounts script only as the mounted RAM-only files, never as parameters
        body, params, mounts, user = self.scripts[0]
        self.assertEqual(params['accounts'], [
            {'username': 'ops-agent', 'kind': 'agent', 'display_name': 'CPT Studio operations agent',
             'password_file': '/run/cpt-operators/ops-agent.pw'},
            {'username': 'platform-operator', 'kind': 'human', 'display_name': 'CPT Studio platform operator',
             'password_file': '/run/cpt-operators/platform-operator.pw'}])
        self.assertEqual((self.mounted['ops-agent.pw'], self.mounted['platform-operator.pw']),
                         (agent['password'], human['password']))
        self.assertTrue(all(mount.startswith('type=bind,src=/dev/shm/') and mount.endswith(',readonly')
                            for mount in mounts))
        self.assertEqual(user, f'{os.getuid()}:{os.getgid()}')
        # each account granted by the application's own command, by its contract
        self.assertEqual([command for command, _ in self.oneshots], [
            ['manage', 'grant_operator', '--username', 'ops-agent', '--reason-file',
             '/run/cpt-operators/ops-agent.reason'],
            ['manage', 'grant_operator', '--username', 'platform-operator', '--reason-file',
             '/run/cpt-operators/platform-operator.reason']])
        self.assertIn('owner directive 2026-11-03, section 2', self.mounted['ops-agent.reason'])
        self.assertIn(REVISION, self.mounted['platform-operator.reason'])
        self.assertEqual(self.scripts[1][0], install.OPERATOR_CHECK)
        self.assertEqual(self.scripts[1][1], {'usernames': ['ops-agent', 'platform-operator']})
        # nothing of either password in the receipt's details, and the RAM files are gone
        flat = json.dumps(details)
        self.assertNotIn(agent['password'], flat)
        self.assertNotIn(human['password'], flat)
        self.assertEqual(details['accounts'], {'ops-agent': 'created', 'platform-operator': 'created'})
        self.assertFalse(list(Path('/dev/shm').glob('cpt-studio-operators-*')))
        self.assertEqual([op for op, *_ in self.root.calls], ['state', 'stage', 'commit'])
        self.assertTrue(all(final == install.OPERATOR_CREDENTIALS for _, final, _ in self.root.calls))

    def test_existing_logins_are_kept_without_reset_and_rotated_with_it(self):
        self.run_phase()
        first = json.loads(self.agent_file.read_text())['password']
        with self.assertRaisesRegex(install.InstallError, 'use --reset-passwords'):
            self.run_phase()
        self.assertEqual(len(self.scripts), 2)  # the refusal ran nothing
        details = self.run_phase(reset=True)
        self.assertNotEqual(json.loads(self.agent_file.read_text())['password'], first)
        self.assertEqual(details['accounts'], {'ops-agent': 'reset', 'platform-operator': 'reset'})
        self.assertTrue(self.scripts[2][1]['reset'])

    def test_an_account_that_already_existed_saves_nothing_without_reset(self):
        self.accounts_answer = {'accounts': {'ops-agent': 'created', 'platform-operator': 'kept'}}
        with self.assertRaisesRegex(install.InstallError, 'already existed'):
            self.run_phase()
        self.assertFalse(self.agent_file.exists())
        self.assertFalse((self.etc / install.OPERATOR_CREDENTIALS).exists())
        self.assertFalse(list(self.etc.iterdir()))  # the staged root file was discarded
        self.assertEqual(self.oneshots, [])  # nothing granted

    def test_staged_leftovers_or_a_loose_directory_refuse_before_anything_runs(self):
        (self.etc / f'.{install.OPERATOR_CREDENTIALS}.new').write_text('{}')
        with self.assertRaisesRegex(install.InstallError, 'interrupted run'):
            self.run_phase()
        (self.etc / f'.{install.OPERATOR_CREDENTIALS}.new').unlink()
        os.chmod(self.home, 0o755)
        with self.assertRaisesRegex(install.InstallError, 'mode 0700'):
            self.run_phase()
        self.assertEqual((self.scripts, self.oneshots), ([], []))

    def test_a_grant_that_fails_or_an_account_that_does_not_read_back_fails_the_phase(self):
        self.grant_exit = {'platform-operator': 2}
        with self.assertRaisesRegex(install.InstallError, 'grant_operator failed for platform-operator') as caught:
            self.run_phase()
        self.assertIn('--reset-passwords', str(caught.exception))
        self.assertTrue(self.agent_file.exists())  # the logins match the accounts: they stay
        self.grant_exit = {}
        for answer in ({'operator': False, 'memberships': 0, 'actor_kind': 'agent', 'active': True},
                       {'operator': True, 'memberships': 1, 'actor_kind': 'agent', 'active': True},
                       {'operator': True, 'memberships': 0, 'actor_kind': 'human', 'active': True}):
            self.check_answer = {'accounts': {'ops-agent': answer, 'platform-operator': {
                'operator': True, 'memberships': 0, 'actor_kind': 'human', 'active': True}}}
            with self.subTest(answer=answer), self.assertRaisesRegex(install.InstallError, 'ops-agent did not read back'):
                self.run_phase(reset=True)

    def test_the_in_image_scripts_compile_and_never_print_a_password(self):
        for body in (install.OPERATOR_ACCOUNTS, install.OPERATOR_CHECK, install.REASSESS_JOBS):
            compile(install.APP_SCRIPT_PRELUDE.format(payload='e30=', answer=install.APP_SCRIPT_ANSWER) + body,
                    'script', 'exec')
        self.assertNotIn('print(password', install.OPERATOR_ACCOUNTS)
        self.assertIn('user.memberships.exists()', install.OPERATOR_ACCOUNTS)
        self.assertNotIn('Membership', install.OPERATOR_ACCOUNTS)  # it never creates one
        self.assertIn('from studio.operator import is_operator', install.OPERATOR_CHECK)


# --- the reassess phase -------------------------------------------------------------------------------------------------

class ReassessPhaseTests(TemporaryDirectoryTest):
    def setUp(self):
        super().setUp()
        self.commands, self.reads = [], []
        self.jobs = {ENCOUNTER: [['j1', 'assess', 'succeeded', 'k1']], ENCOUNTER_2: []}
        self.queues = {ENCOUNTER: [['j2', 'assess', 'queued', 'k1:c:tag']], ENCOUNTER_2: [['j3', 'assess', 'queued',
                                                                                         'k2:c:tag']]}
        self.exit = {}
        self.app_receipt({'astra': 'live', 'fable': 'live'})

    def app_receipt(self, participants):
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION,
                                                'details': {'participants': participants}})

    def app_script(self, image_id, env, body, params, **kwargs):
        self.assertEqual(body, install.REASSESS_JOBS)
        self.reads.append(list(params['encounters']))
        return {'encounters': {pk: None if pk not in self.jobs else {'state': 'ready_for_review',
                                                                    'jobs': list(self.jobs[pk])}
                               for pk in params['encounters']}}

    def oneshot(self, image_id, command, env, **kwargs):
        self.commands.append((command, kwargs))
        if command[:2] == ['manage', 'reassess_retained']:
            pk = command[3]
            if not self.exit.get(pk) and '--dry-run' not in command:
                self.jobs[pk] += self.queues[pk]
            return SimpleNamespace(returncode=self.exit.get(pk, 0), stdout=json.dumps({'queued': True}).encode(),
                                   stderr=b'')
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

    def run_phase(self, encounters, dry=None):
        ctx = install.Context(SimpleNamespace(phase='reassess', revision=REVISION, receipts=str(self.tmp),
                                              encounter=encounters, dry_run=dry), self.tmp)
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value=IMAGE), require_db=mock.Mock(),
                                 read_protected_env=mock.Mock(return_value=b''), app_script=self.app_script,
                                 oneshot=self.oneshot):
            return install.phase_reassess(ctx)

    def test_each_named_encounter_is_reassessed_by_the_contract_and_its_new_jobs_are_measured(self):
        details = self.run_phase([ENCOUNTER, ENCOUNTER_2])
        self.assertEqual([command for command, _ in self.commands], [
            ['manage', 'migrate', '--check'],
            ['manage', 'reassess_retained', '--encounter', ENCOUNTER, '--tag', REVISION, '--participants', 'astra,fable'],
            ['manage', 'reassess_retained', '--encounter', ENCOUNTER_2, '--tag', REVISION, '--participants',
             'astra,fable']])
        self.assertEqual(details['participants'], ['astra', 'fable'])
        self.assertEqual(self.reads, [[ENCOUNTER, ENCOUNTER_2]] * 2)  # before and after
        self.assertEqual(details['encounters'][ENCOUNTER]['jobs_appeared'], [['j2', 'assess', 'queued', 'k1:c:tag']])
        self.assertEqual(details['encounters'][ENCOUNTER_2]['jobs_appeared'], [['j3', 'assess', 'queued', 'k2:c:tag']])
        self.assertEqual(details['encounters'][ENCOUNTER]['receipt'], {'queued': True})
        self.assertTrue(Path(details['encounters'][ENCOUNTER]['log']).exists())
        self.assertEqual((details['tag'], details['dry_run']), (REVISION, False))
        self.assertIn('2 job(s) appeared', details['summary'])
        for command, kwargs in self.commands:
            self.assertNotIn('environment', kwargs)  # the one-shot's default: provider and participants disabled

    def test_a_dry_run_passes_the_flag_and_fails_when_a_job_appeared(self):
        details = self.run_phase([ENCOUNTER], dry=True)
        self.assertEqual(self.commands[1][0][-1], '--dry-run')
        self.assertEqual(details['encounters'][ENCOUNTER]['jobs_appeared'], [])
        self.jobs[ENCOUNTER].append(['j9', 'assess', 'queued', 'member'])  # someone else's, meanwhile
        original = self.app_script
        calls = []

        def script(*args, **kwargs):
            calls.append(1)
            answer = original(*args, **kwargs)
            if len(calls) == 1:
                answer['encounters'][ENCOUNTER]['jobs'].pop()
            return answer
        self.app_script = script
        with self.assertRaisesRegex(install.InstallError, 'A dry run was followed by 1 new job'):
            self.run_phase([ENCOUNTER], dry=True)

    def test_the_participants_are_the_app_receipt_s_and_none_without_a_receipt_runs_nothing(self):
        # the worker's modes, from this revision's app receipt: the one-shot itself runs with every participant
        # disabled, so the command is told whom the worker reads (a harness encounter was refused otherwise)
        self.app_receipt({'astra': 'live', 'fable': 'disabled'})
        self.run_phase([ENCOUNTER])
        self.assertEqual(self.commands[1][0][-2:], ['--participants', 'astra'])
        self.commands.clear()
        self.app_receipt({'astra': 'disabled', 'fable': 'disabled'})
        self.run_phase([ENCOUNTER_2])
        self.assertEqual(self.commands[1][0][-2:], ['--participants', 'none'])
        for receipt in self.tmp.glob('app-*'):
            receipt.unlink()
        self.commands.clear()
        with self.assertRaisesRegex(install.InstallError, 'No successful --phase app receipt'):
            self.run_phase([ENCOUNTER])
        self.assertEqual(self.commands, [])

    def test_an_unknown_encounter_refuses_before_any_command_and_a_failure_says_what_ran(self):
        with self.assertRaisesRegex(install.InstallError, 'do not exist'):
            self.run_phase(['00000000-0000-4000-8000-000000000000'])
        self.assertEqual([command[:2] for command, _ in self.commands], [['manage', 'migrate']])
        self.commands.clear()
        self.exit = {ENCOUNTER_2: 1}
        with self.assertRaisesRegex(install.InstallError, f'failed \\(exit 1\\).*It ran before for {ENCOUNTER}'):
            self.run_phase([ENCOUNTER, ENCOUNTER_2])

    def test_it_refuses_while_this_revision_s_migrations_are_not_applied(self):
        def pending(image_id, command, env, **kwargs):
            self.commands.append((command, kwargs))
            return SimpleNamespace(returncode=1, stdout=b'', stderr=b'')
        self.oneshot = pending
        with self.assertRaisesRegex(install.InstallError, 'run --phase app first'):
            self.run_phase([ENCOUNTER])
        self.assertEqual(self.reads, [])


# --- the in-image scripts on a real database (CI's disposable PostgreSQL; skipped, never passed, without one) -----------

from test_install_harness2 import DatabaseTest, run_in_image  # noqa: E402


class OperatorAccountsOnTheDatabaseTests(DatabaseTest):
    """OPERATOR_ACCOUNTS as `manage shell -c` runs it, on real rows: no membership, refusals change nothing."""

    def specs(self, folder, passwords):
        found = []
        for (username, kind, display), password in zip(install.OPERATOR_ACCOUNTS_SPEC, passwords):
            path = Path(folder) / f'{username}.pw'
            path.write_text(password + '\n')
            found.append({'username': username, 'kind': kind, 'display_name': display, 'password_file': str(path)})
        return found

    def setUp(self):
        super().setUp()
        import tempfile
        self._folder = tempfile.TemporaryDirectory()
        self.addCleanup(self._folder.cleanup)
        self.folder = self._folder.name

    def test_accounts_are_created_with_no_membership_then_kept_or_reset(self):
        from studio import models
        first = ['synthetic-operator-pass-0123456789-A', 'synthetic-operator-pass-0123456789-B']
        answer = run_in_image(install.OPERATOR_ACCOUNTS, {'accounts': self.specs(self.folder, first), 'reset': False})
        self.assertEqual(answer, {'accounts': {'ops-agent': 'created', 'platform-operator': 'created'}})
        for (username, kind, display), password in zip(install.OPERATOR_ACCOUNTS_SPEC, first):
            user = models.User.objects.get(username=username)
            self.assertEqual((user.actor_kind, user.display_name, user.memberships.count()), (kind, display, 0))
            self.assertTrue(user.check_password(password))
        second = ['synthetic-operator-pass-9876543210-C', 'synthetic-operator-pass-9876543210-D']
        kept = run_in_image(install.OPERATOR_ACCOUNTS, {'accounts': self.specs(self.folder, second), 'reset': False})
        self.assertEqual(kept, {'accounts': {'ops-agent': 'kept', 'platform-operator': 'kept'}})
        self.assertTrue(models.User.objects.get(username='ops-agent').check_password(first[0]))
        reset = run_in_image(install.OPERATOR_ACCOUNTS, {'accounts': self.specs(self.folder, second), 'reset': True})
        self.assertEqual(reset, {'accounts': {'ops-agent': 'reset', 'platform-operator': 'reset'}})
        self.assertTrue(models.User.objects.get(username='platform-operator').check_password(second[1]))
        self.assertFalse(models.Membership.objects.filter(user__username__in=['ops-agent', 'platform-operator'])
                         .exists())

    def test_a_member_account_or_another_kind_is_refused_and_nothing_changes(self):
        from studio import models
        category, _ = models.Category.objects.get_or_create(slug='synthetic-ops', defaults={
            'name': 'Synthetic', 'profiles_version': 'synthetic@1'})
        workspace = models.Workspace.objects.create(name='Synthetic ops', category=category)
        member = models.User.objects.create(username='platform-operator', actor_kind='human')
        models.Membership.objects.create(user=member, workspace=workspace, role=models.Membership.OWNER)
        passwords = ['synthetic-operator-pass-0123456789-E', 'synthetic-operator-pass-0123456789-F']
        with self.assertRaisesRegex(SystemExit, 'holds a workspace membership'):
            run_in_image(install.OPERATOR_ACCOUNTS, {'accounts': self.specs(self.folder, passwords), 'reset': True})
        self.assertFalse(models.User.objects.filter(username='ops-agent').exists())  # rolled back with it
        self.assertEqual(models.User.objects.get(pk=member.pk).password, member.password)  # its password untouched
        models.Membership.objects.filter(user=member).delete()
        member.actor_kind = 'agent'
        member.save()
        with self.assertRaisesRegex(SystemExit, 'another actor kind'):
            run_in_image(install.OPERATOR_ACCOUNTS, {'accounts': self.specs(self.folder, passwords), 'reset': True})


class ReassessJobsOnTheDatabaseTests(DatabaseTest):
    def test_the_jobs_of_each_named_encounter_in_order_and_none_for_an_unknown_one(self):
        from django.utils import timezone
        from studio import models
        encounter = self.encounter('reassess')
        for index, (kind, state) in enumerate((('extract', 'succeeded'), ('assess', 'queued'))):
            models.Job.objects.create(encounter=encounter, revision=encounter.current_revision, kind=kind, state=state,
                                      idempotency_key=f'synthetic-reassess-{index}',
                                      deadline_at=timezone.now() + dt.timedelta(minutes=30))
        missing = '00000000-0000-4000-8000-000000000000'
        answer = run_in_image(install.REASSESS_JOBS, {'encounters': [str(encounter.pk), missing]})
        found = answer['encounters'][str(encounter.pk)]
        self.assertEqual([job[1:] for job in found['jobs']], [['extract', 'succeeded', 'synthetic-reassess-0'],
                                                             ['assess', 'queued', 'synthetic-reassess-1']])
        self.assertEqual(found['state'], encounter.state)
        self.assertIsNone(answer['encounters'][missing])


# --- what INSTALL.md says ---------------------------------------------------------------------------------------------------

class InstallDocTests(unittest.TestCase):
    """INSTALL.md says what the code does, with the code's own numbers (the doc-test style of test_install_r5_sends)."""

    @classmethod
    def setUpClass(cls):
        cls.text = (APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8')
        cls.said = ' '.join(cls.text.split())

    def between(self, start, end):
        return self.said.split(start, 1)[1].split(end, 1)[0]

    def says(self, phrase, text):
        self.assertTrue(phrase in text, f'INSTALL.md does not say: {phrase}')

    def test_the_app_paragraph_names_the_incoming_web_the_idle_port_the_switch_and_the_drain(self):
        app = self.between('- **app** (live mode)', '- **reference**')
        for phrase in ('`cpt-studio-web-next` starts on the idle port', "**S3** the vhost's upstream is switched",
                       '**S5** the old web is drained', 'at least 130 s', '10 consecutive one-second samples',
                       'never longer than 600 s', 'every 0.5 s', '`availability`', 'never stops the serving web',
                       '`docker stop --time 600`', 'graceful, 30 s', 'the two differ in their `proxy_pass` line alone'):
            self.says(phrase, app)
        self.assertEqual((install.DRAIN_MIN_SECONDS, install.DRAIN_QUIET_SECONDS, install.DRAIN_MAX_SECONDS),
                         (130, 10, 600))
        self.assertEqual((install.AVAILABILITY_INTERVAL_SECONDS, install.STOP_SECONDS),
                         (0.5, {'web': 30, 'worker': 600}))
        for step in ('S1', 'S2', 'S3', 'S4', 'S5'):
            self.says(f'- {step} (', app)  # one row of the failure matrix each

    def test_the_tables_name_the_ports_and_the_new_phases(self):
        self.says('`127.0.0.1:9150` or `127.0.0.1:9151` → 8000', self.said)
        for row in ('| 9a | `operators` |', '| 9b | `reassess` |'):
            self.says(row, self.said)
        self.says('ops-agent-credentials.json` (0600, top-level `username` and `password`)', self.said)
        self.says('`operator-credentials.json` (root 0600', self.said)
        self.assertEqual(str(install.OPS_AGENT_CREDENTIALS), '/home/claude/.cpt-studio/ops-agent-credentials.json')
        self.assertEqual(install.OPERATOR_CREDENTIALS, 'operator-credentials.json')

    def test_switching_back_and_the_recovery_notes(self):
        switch = self.between('## Switching back', '## Reinstalling an older revision')
        for step in ('**B2**', '**B3**', '**B4**', '**B5**', '**B6**', '**B7**', '**B8**', '**B9**'):
            self.says(step, switch)
        recovery = self.between('## Recovery notes', '## Local build and tests')
        for phrase in ('A `cpt-studio-web-next` left by an interrupted blue/green `app`',
                       'An installer killed outright inside S3', 'the TLS renewal deploy hook'):
            self.says(phrase, recovery)

    def test_the_known_limits_state_every_residual_of_the_design(self):
        limits = self.said.split('## Known limits', 1)[1]
        for number, phrase in ((1, 'a large upload'), (2, 'hashed names'), (3, 'keeps running the old `app.js`'),
                               (4, 'Processing pauses'), (5, 'host-global'), (6, 'alternates with the port'),
                               (7, 'During the drain'), (8, 'over-closing is the safe side'),
                               (9, 'An installer older than this one knows only port 9150'), (10, 'cannot ride the switch')):
            self.says(f'{number}. ', limits)
            self.says(phrase, limits)
