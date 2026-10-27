"""Unit tests for ops/install.py. No Docker, sudo, nginx or network beyond loopback.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Helper bodies (the code that runs as root inside the pinned helper image) are
executed in-process against temporary directories: their absolute container
paths are rewritten (each rewrite asserted to apply) and ownership changes are
recorded by a shim instead of needing root.
"""
import base64
import hashlib
import http.server
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402

DEPLOY = Path(__file__).resolve().parents[1] / 'deploy'
REVISION = 'a' * 40
OTHER = 'b' * 40


def template(kind):
    return (DEPLOY / 'nginx' / f'cpt-quillmd-{kind}.conf').read_text(encoding='utf-8')


def rendered():
    return {'http': install.render(template('http'), {'DOMAIN': install.DOMAIN}),
            'https': install.render(template('https'), {'DOMAIN': install.DOMAIN, 'UPSTREAM': install.UPSTREAM})}


def statements(conf):
    """Every directive as a word list, in order, with its enclosing block names."""
    out, stack, words = [], [], []
    for kind, value in install.nginx_tokens(conf):
        if kind == 'punct' and value == '{':
            stack.append(words[0] if words else '')
            words = []
        elif kind == 'punct' and value == '}':
            stack.pop()
            words = []
        elif kind == 'punct':
            out.append((tuple(stack), words))
            words = []
        else:
            words.append(value)
    return out


class FakeOwnership:
    """os, but chown/fchown are recorded and reported back by lstat/stat (no root needed)."""

    def __init__(self):
        self.owners, self.fds = {}, {}

    def __getattr__(self, name):
        return getattr(os, name)

    def open(self, path, flags, mode=0o777, **kwargs):
        fd = os.open(path, flags, mode, **kwargs)
        self.fds[fd] = os.path.abspath(path)
        return fd

    def fchown(self, fd, uid, gid):
        self.owners[self.fds[fd]] = (uid, gid)

    def chown(self, path, uid, gid):
        self.owners[os.path.abspath(path)] = (uid, gid)

    def link(self, source, target):
        os.link(source, target)
        if os.path.abspath(source) in self.owners:
            self.owners[os.path.abspath(target)] = self.owners[os.path.abspath(source)]

    def replace(self, source, target):
        os.replace(source, target)
        if os.path.abspath(source) in self.owners:
            self.owners[os.path.abspath(target)] = self.owners.pop(os.path.abspath(source))

    def _owned(self, path, result):
        uid, gid = self.owners.get(os.path.abspath(path), (result.st_uid, result.st_gid))
        values = list(result)[:10]
        values[4], values[5] = uid, gid
        return os.stat_result(values)

    def lstat(self, path):
        return self._owned(path, os.lstat(path))

    def stat(self, path):
        return self._owned(path, os.stat(path))


def run_body(body, params, paths, fake_os=None):
    """Execute a helper body with container paths mapped onto temp paths; return its JSON."""
    source = body
    for old, new in paths.items():
        count = source.count(old)
        assert count >= 1, f'path {old!r} does not occur in the helper body'
        source = source.replace(old, new)
    lines, namespace = [], {}
    exec(compile(install.HELPER_PRELUDE, '<helper-prelude>', 'exec'), namespace)
    namespace.update(os=fake_os or FakeOwnership(), subprocess=None, P=params,
                     print=lambda *args, **kwargs: lines.append(' '.join(str(a) for a in args)))
    exec(compile(source, '<helper-under-test>', 'exec'), namespace)
    return json.loads(lines[-1])


class TemporaryDirectoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        os.chmod(self.tmp, 0o700)

    def tearDown(self):
        self._tmp.cleanup()


# --- templates -----------------------------------------------------------------------

class TemplateRenderingTests(unittest.TestCase):
    def test_templates_render_completely_and_share_the_http_stage(self):
        confs = rendered()
        for conf in confs.values():
            self.assertNotIn('@@', conf)
            self.assertIn(f'server_name {install.DOMAIN};', conf)
        self.assertTrue(confs['https'].startswith(confs['http']))
        self.assertIn(f'proxy_pass http://{install.UPSTREAM};', confs['https'])

    def test_rendered_vhosts_reads_templates_at_the_revision(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            kind = 'http' if argv[-1].endswith('-http.conf') else 'https'
            return SimpleNamespace(stdout=template(kind).encode(), returncode=0)
        with mock.patch.object(install, 'run', fake_run):
            confs = install.rendered_vhosts(REVISION)
        self.assertEqual(confs, rendered())
        self.assertEqual(sorted(argv[-1] for argv in calls),
                         sorted(f'{REVISION}:{path}' for path in install.TEMPLATES.values()))

    def test_rendered_vhosts_refuses_an_https_stage_that_drifted_from_http(self):
        drifted = template('https').replace('access_log off;', 'access_log on;', 1)

        def fake_run(argv, **kwargs):
            return SimpleNamespace(stdout=(template('http') if argv[-1].endswith('-http.conf') else drifted).encode())
        with mock.patch.object(install, 'run', fake_run), self.assertRaises(install.InstallError):
            install.rendered_vhosts(REVISION)

    def test_default_server_is_refused_by_directive_not_by_comment(self):
        claimed = template('https').replace('    listen 443 ssl http2;', '    listen 443 ssl http2 default_server;', 1)
        self.assertNotEqual(claimed, template('https'))

        def fake_run(argv, **kwargs):
            return SimpleNamespace(stdout=(template('http') if argv[-1].endswith('-http.conf') else claimed).encode())
        with mock.patch.object(install, 'run', fake_run), self.assertRaises(install.InstallError) as caught:
            install.rendered_vhosts(REVISION)
        self.assertIn('default_server', str(caught.exception))
        self.assertIn('NO default_server', template('http'))  # the comment alone is accepted

    def test_render_refuses_mismatched_or_unsafe_values(self):
        good = 'server_name @@DOMAIN@@; proxy_pass http://@@UPSTREAM@@;'
        cases = [
            (good, {'DOMAIN': install.DOMAIN}),  # placeholder without a value
            ('server_name @@DOMAIN@@;', {'DOMAIN': install.DOMAIN, 'UPSTREAM': install.UPSTREAM}),  # unused value
            ('@@DOMAIN@@ @@OTHER@@', {'DOMAIN': install.DOMAIN}),  # unknown placeholder
            (good, {'DOMAIN': 'cpt.quillmd.com; include /etc/passwd', 'UPSTREAM': install.UPSTREAM}),
            (good, {'DOMAIN': 'CPT.quillmd.com', 'UPSTREAM': install.UPSTREAM}),
            (good, {'DOMAIN': 'localhost', 'UPSTREAM': install.UPSTREAM}),
            (good, {'DOMAIN': install.DOMAIN, 'UPSTREAM': '0.0.0.0:9150'}),
            (good, {'DOMAIN': install.DOMAIN, 'UPSTREAM': '127.0.0.1:9150; return 200'}),
        ]
        for text, values in cases:
            with self.subTest(values=values), self.assertRaises(install.InstallError):
                install.render(text, values)

    def test_https_vhost_hardening(self):
        conf = rendered()['https']
        found = statements(conf)
        listens = [words[1:] for blocks, words in found if words[0] == 'listen']
        self.assertEqual(listens, [['80'], ['[::]:80'], ['443', 'ssl', 'http2'], ['[::]:443', 'ssl']])
        names = [words[1:] for blocks, words in found if words[0] == 'server_name']
        self.assertEqual(names, [[install.DOMAIN], [install.DOMAIN]])
        self.assertFalse([args for args in listens if {'default_server', 'default'} & set(args)])
        self.assertNotIn('$proxy_add_x_forwarded_for', conf)
        returns = [words for blocks, words in found if words[0] == 'return' and words[1] == '444']
        self.assertEqual(len(returns), 3)  # one Host check on :80, Host and SNI checks on :443
        server = [words for blocks, words in found if blocks == ('server',)]
        directives = {words[0]: words[1:] for words in server}
        self.assertEqual(directives['ssl_certificate'], [f'/etc/letsencrypt/live/{install.DOMAIN}/fullchain.pem'])
        self.assertEqual(directives['ssl_certificate_key'], [f'/etc/letsencrypt/live/{install.DOMAIN}/privkey.pem'])
        self.assertEqual(directives['client_max_body_size'], ['20m'])
        headers = {words[1]: words[2:] for words in server if words[0] == 'add_header'}
        self.assertEqual(headers, {'Strict-Transport-Security': ['max-age=31536000', 'always'],
                                   'X-Content-Type-Options': ['nosniff', 'always'],
                                   'Referrer-Policy': ['same-origin', 'always'],
                                   'X-Robots-Tag': ['noindex, nofollow', 'always']})
        proxy = [words for blocks, words in found if blocks == ('server', 'location') and words[0].startswith('proxy')]
        set_headers = {words[1]: words[2:] for words in proxy if words[0] == 'proxy_set_header'}
        self.assertEqual(set_headers['X-Forwarded-For'], ['$remote_addr'])
        self.assertEqual(set_headers['Authorization'], [''])
        self.assertEqual(set_headers['Host'], [install.DOMAIN])
        for name in ('proxy_read_timeout', 'proxy_send_timeout'):
            value = next(words[1] for words in proxy if words[0] == name)
            self.assertGreaterEqual(int(value.rstrip('s')), 150, name)
        hidden = {words[1] for words in proxy if words[0] == 'proxy_hide_header'}
        self.assertEqual(hidden, set(headers))

    def test_csrf_cookie_stays_readable_by_the_page_script(self):
        cookie_flags = [words[1:] for blocks, words in statements(rendered()['https'])
                        if words[0] == 'proxy_cookie_flags']
        self.assertEqual(cookie_flags[0], ['cptstudio_session', 'secure', 'httponly', 'samesite=strict'])
        self.assertEqual(cookie_flags[1], ['~', 'secure', 'samesite=strict'])  # catch-all: no httponly
        self.assertEqual(len(cookie_flags), 2)

    def test_http_stage_never_proxies_the_application(self):
        conf = rendered()['http']
        self.assertNotIn('proxy_pass', conf)
        self.assertIn('location /.well-known/acme-challenge/ {\n        root /var/www/certbot;', conf)
        self.assertIn(f'return 301 https://{install.DOMAIN}$request_uri;', conf)


# --- nginx parsing -------------------------------------------------------------------

SAMPLE_VHOSTS = '''
# server { listen 9999; server_name commented.example; }
map $http_upgrade $connection_upgrade { default upgrade; '' close; }
upstream pool { server 127.0.0.1:8080; }
server {
    listen 80;  # trailing comment with ; and {
    listen [::]:80;
    server_name one.example www.one.example _;
    location / { return 200 "body with ; and { braces }"; }
}
server {
    listen 443 ssl http2;
    listen [::]:443 ssl;
    server_name two.example ~^regex\\.example$ *.wild.example 5.6.7.8;
    if ($host != two.example) { return 444; }
    location /x { proxy_pass http://pool; }
}
server { listen unix:/run/x.sock; server_name socket.example; }
'''


class NginxParsingTests(unittest.TestCase):
    def test_server_blocks_ignore_comments_quotes_and_nested_blocks(self):
        blocks = install.parse_server_blocks(SAMPLE_VHOSTS)
        self.assertEqual(len(blocks), 3)
        self.assertEqual(blocks[0], {'listen': [['80'], ['[::]:80']],
                                     'server_names': ['one.example', 'www.one.example', '_']})
        self.assertEqual(blocks[1]['listen'], [['443', 'ssl', 'http2'], ['[::]:443', 'ssl']])

    def test_unbalanced_braces_are_refused(self):
        for text in ('server { listen 80;', 'listen 80; }'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                install.parse_server_blocks(text)

    def test_listen_forms(self):
        self.assertEqual(install.parse_listen(['80']), {'port': 80, 'ssl': False, 'connect': '127.0.0.1'})
        self.assertEqual(install.parse_listen(['[::]:443', 'ssl']), {'port': 443, 'ssl': True, 'connect': '::1'})
        self.assertEqual(install.parse_listen(['0.0.0.0:443', 'ssl', 'http2'])['connect'], '127.0.0.1')
        self.assertEqual(install.parse_listen(['*:8080'])['port'], 8080)
        self.assertEqual(install.parse_listen(['10.1.2.3:80'])['connect'], '10.1.2.3')
        self.assertIsNone(install.parse_listen(['unix:/run/x.sock']))
        self.assertIsNone(install.parse_listen([]))

    def test_routing_targets_skip_catch_all_regex_wildcards_and_sockets(self):
        targets = install.routing_targets([SAMPLE_VHOSTS])
        names = {target[0] for target in targets}
        self.assertEqual(names, {'one.example', 'www.one.example', 'two.example', '5.6.7.8', install.UNMATCHED_HOST})
        self.assertIn(('two.example', 443, True, '::1'), targets)
        self.assertIn((install.UNMATCHED_HOST, 443, True, '127.0.0.1'), targets)
        self.assertEqual(len(targets), len(set(targets)))

    @unittest.skipUnless((install.NGINX_ENABLED / 'quillmd').exists(), 'not the QuillMD host (CI runners ship nginx)')
    def test_live_enabled_vhosts_parse_and_include_the_quillmd_app(self):
        targets = install.routing_targets(install.enabled_config_texts())
        self.assertIn(('app.quillmd.com', 443, True, '127.0.0.1'), targets)
        self.assertFalse(any(target[0] == install.DOMAIN for target in targets))

    def test_new_warnings_and_routing_differences(self):
        output = ('nginx: [warn] protocol options redefined for 0.0.0.0:443 in /a:7\n'
                  'nginx: the configuration file /etc/nginx/nginx.conf syntax is ok\n')
        self.assertEqual(install.nginx_warnings(output), ['protocol options redefined for 0.0.0.0:443 in /a:7'])
        # This host's Ubuntu nginx logs to stderr and prints only the timestamped form (the 2026-10-26 preflight
        # log). The same warning one second later is the same warning; a new one is new.
        ubuntu = ('2026/10/26 20:42:50 [warn] 1204878#1204878: protocol options redefined for 0.0.0.0:443 in /a:7\n'
                  'nginx: the configuration file /etc/nginx/nginx.conf syntax is ok\n'
                  'nginx: configuration file /etc/nginx/nginx.conf test is successful\n')
        later = ubuntu.replace('20:42:50', '20:42:51').replace('1204878#1204878', '1204990#1204990')
        added = later + '2026/10/26 20:42:51 [warn] 1204990#1204990: conflicting server name "x" on 0.0.0.0:80, ignored\n'
        self.assertEqual(install.nginx_warnings(ubuntu), install.nginx_warnings(output))
        self.assertEqual(install.nginx_warnings(later), install.nginx_warnings(ubuntu))
        self.assertEqual(sorted(set(install.nginx_warnings(added)) - set(install.nginx_warnings(ubuntu))),
                         ['conflicting server name "x" on 0.0.0.0:80, ignored'])
        before = {'http://a.example:80@127.0.0.1': {'status': 200},
                  f'https://{install.DOMAIN}:443@127.0.0.1': {'status': 200}}
        after = {'http://a.example:80@127.0.0.1': {'status': 502},
                 f'https://{install.DOMAIN}:443@127.0.0.1': {'status': 301},
                 'http://b.example:80@127.0.0.1': {'status': 200}}
        self.assertEqual(install.routing_diff(before, after),
                         ['http://a.example:80@127.0.0.1', 'http://b.example:80@127.0.0.1'])
        self.assertEqual(install.routing_diff(before, dict(before)), [])


# --- receipts and arguments ---------------------------------------------------------

class ReceiptTests(TemporaryDirectoryTest):
    def test_receipts_directory_is_created_private(self):
        path = install.prepare_receipts(str(self.tmp / 'receipts'))
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
        self.assertEqual(install.prepare_receipts(str(path)), path)

    def test_receipts_directory_refusals(self):
        (self.tmp / 'open').mkdir(mode=0o755)
        os.chmod(self.tmp / 'open', 0o755)
        (self.tmp / 'file').write_text('x')
        (self.tmp / 'real').mkdir(mode=0o700)
        (self.tmp / 'alias').symlink_to(self.tmp / 'real')
        for text in ('relative/receipts', str(self.tmp / 'x' / '..' / 'y'), str(install.ROOT / 'receipts'),
                     str(self.tmp / 'open'), str(self.tmp / 'file'), str(self.tmp / 'alias')):
            with self.subTest(text=text), self.assertRaises(install.InstallError):
                install.prepare_receipts(text)
        self.assertFalse((install.ROOT / 'receipts').exists())

    def test_receipts_are_private_exclusive_json(self):
        path = install.write_receipt(self.tmp, 'preflight', {'phase': 'preflight', 'ok': True})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(json.loads(path.read_text()), {'phase': 'preflight', 'ok': True})
        with self.assertRaises(FileExistsError):
            install.write_private(self.tmp, path.name, b'{}')

    def test_latest_receipt_is_the_newest_success_for_the_revision(self):
        def put(name, **record):
            (self.tmp / name).write_text(json.dumps(record))
        put('http-vhost-20261023T010000000000Z.json', phase='http-vhost', ok=True, revision=REVISION, n=1)
        put('http-vhost-20261023T020000000000Z.json', phase='http-vhost', ok=True, revision=REVISION, n=2)
        put('http-vhost-20261023T030000000000Z.json', phase='http-vhost', ok=False, revision=REVISION, n=3)
        put('http-vhost-20261023T040000000000Z.json', phase='http-vhost', ok=True, revision=OTHER, n=4)
        put('https-vhost-20261023T050000000000Z.json', phase='https-vhost', ok=True, revision=REVISION, n=5)
        self.assertEqual(install.latest_receipt(self.tmp, 'http-vhost', REVISION)['n'], 2)
        self.assertEqual(install.latest_receipt(self.tmp, 'https-vhost', REVISION)['n'], 5)
        self.assertIsNone(install.latest_receipt(self.tmp, 'cert', REVISION))


class ArgumentTests(unittest.TestCase):
    BASE = ['--revision', REVISION, '--receipts', '/tmp/receipts']

    def parse(self, *extra):
        with mock.patch('sys.stderr', io.StringIO()):
            return install.parse_args([*self.BASE, *extra])

    def refused(self, *extra):
        with self.assertRaises(SystemExit) as caught, mock.patch('sys.stderr', io.StringIO()):
            install.parse_args([*extra] if extra and extra[0] == '--revision' else [*self.BASE, *extra])
        self.assertEqual(caught.exception.code, 2)

    def test_valid_invocations(self):
        self.assertEqual(self.parse('--phase', 'preflight').phase, 'preflight')
        args = self.parse('--phase', 'app', '--provider-mode', 'live', '--authorization-ref',
                          'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
        self.assertEqual(args.provider_mode, 'live')
        args = self.parse('--phase', 'provision', '--owner-username', 'owner')
        self.assertEqual((args.agent_username, args.workspace_name), ('review-agent', 'Gastroenterology'))
        self.assertEqual(self.parse('--phase', 'reference', '--pfs-zip', '/x/a.zip', '--mue-zip', '/x/b.zip',
                                    '--pfs-retrieved-at', '2026-10-23T20:59:00Z',
                                    '--mue-retrieved-at', '2026-10-23T21:01:44+00:00').phase, 'reference')

    def test_refusals(self):
        self.refused('--revision', 'abc123', '--receipts', '/tmp/r', '--phase', 'preflight')
        self.refused('--revision', 'A' * 40, '--receipts', '/tmp/r', '--phase', 'preflight')
        self.refused('--phase', 'install-everything')
        self.refused('--phase', 'preflight', '--provider-mode', 'live')
        self.refused('--phase', 'app', '--pfs-zip', '/x/a.zip', '--provider-mode', 'disabled')
        self.refused('--phase', 'reference', '--pfs-zip', '/x/a.zip')
        zips = ('--pfs-zip', '/x/a.zip', '--mue-zip', '/x/b.zip', '--pfs-retrieved-at', '2026-10-23T20:59:00Z')
        self.refused('--phase', 'reference', *zips)
        for moment in ('2026-10-23T20:59:00', 'yesterday', '2999-01-01T00:00:00Z'):
            self.refused('--phase', 'reference', *zips, '--mue-retrieved-at', moment)
        self.refused('--phase', 'app')
        self.refused('--phase', 'app', '--provider-mode', 'live')
        self.refused('--phase', 'app', '--provider-mode', 'disabled', '--authorization-ref', 'docs/x.md')
        for reference in ('../outside.md', '/etc/passwd', 'docs/../../x', 'docs/x.md; rm -rf /', 'a' * 201):
            self.refused('--phase', 'app', '--provider-mode', 'live', '--authorization-ref', reference)
        self.refused('--phase', 'provision')
        self.refused('--phase', 'provision', '--owner-username', 'Owner')
        self.refused('--phase', 'provision', '--owner-username', 'ab')
        self.refused('--phase', 'provision', '--owner-username', 'agent', '--agent-username', 'agent')
        self.refused('--phase', 'provision', '--owner-username', 'owner', '--owner-display-name', 'x"; DROP')
        self.refused('--phase', 'verify', '--reset-passwords')


# --- door and tree ------------------------------------------------------------------

class DoorTests(TemporaryDirectoryTest):
    """The door binds a phase to a COMMITTED declaration (refutation finding installer:0), on a real git repo."""

    NAME = 'docs/declaration.md'

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / 'repo'
        (self.repo / 'docs').mkdir(parents=True)
        self.git('init', '-q')
        patcher = mock.patch.object(install, 'ROOT', self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=Synthetic', '-c',
                               'user.email=synthetic@example.invalid', '-c', 'commit.gpgsign=false', *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, name, text):
        (self.repo / name).write_text(text)
        self.git('add', name)
        self.git('commit', '-q', '--no-verify', '-m', f'synthetic {name}')
        return self.git('rev-parse', 'HEAD')

    def door(self, declaration, commit):
        return install.check_door({'RULED_MUTATION_DECLARATION': str(declaration),
                                   'RULED_MUTATION_DECL_COMMIT': commit}, REVISION)

    def refuses(self, declaration, commit, message):
        with self.assertRaisesRegex(install.InstallError, message):
            self.door(declaration, commit)

    def test_door_requires_both_variables(self):
        for environ in ({}, {'RULED_MUTATION_DECLARATION': 'x'}, {'RULED_MUTATION_DECL_COMMIT': OTHER}):
            with self.subTest(environ=environ), self.assertRaisesRegex(install.InstallError, 'run-ruled-mutation'):
                install.check_door(environ, REVISION)

    def test_a_committed_declaration_naming_the_revision_is_accepted(self):
        commit = self.commit(self.NAME, f'Revision installed: {REVISION}\n')
        self.assertEqual(self.door(self.NAME, commit)['declaration_commit'], commit)
        self.assertEqual(self.door(self.repo / self.NAME, commit)['declaration_commit'], commit)

    def test_content_refusals(self):
        commit = self.commit(self.NAME, f'Revision installed: {REVISION} and <REVISION>\n')
        self.refuses(self.NAME, commit, 'placeholder')
        commit = self.commit(self.NAME, f'Revision installed: {OTHER}\n')
        self.refuses(self.NAME, commit, 'does not name the revision')
        self.refuses('docs/missing.md', commit, 'cannot be read')
        self.refuses(self.NAME, 'abc', 'full commit sha')

    def test_a_symbolic_link_to_the_committed_declaration_is_refused(self):
        commit = self.commit(self.NAME, f'Revision installed: {REVISION}\n')
        (self.repo / 'docs' / 'alias.md').symlink_to('declaration.md')
        self.refuses('docs/alias.md', commit, 'symbolic link')
        (self.repo / 'linked').symlink_to('docs', target_is_directory=True)
        self.refuses('linked/declaration.md', commit, 'symbolic link')
        outside = self.tmp / 'outside.md'
        outside.symlink_to(self.repo / self.NAME)
        self.refuses(outside, commit, 'inside this repository')
        # A directory link followed by '..' (round 3, installer3:2): the OS opens a byte-identical copy OUTSIDE the
        # tree (link first, then '..'), while a lexical collapse names the committed file the git checks run on.
        far = self.tmp / 'elsewhere' / 'a' / 'b'
        far.mkdir(parents=True)
        copy = self.tmp / 'elsewhere' / 'a' / 'declaration.md'
        copy.write_bytes((self.repo / self.NAME).read_bytes())
        (self.repo / 'docs' / 'linkdir').symlink_to(far, target_is_directory=True)
        for named in ('docs/linkdir/../declaration.md', str(self.repo / 'docs' / 'linkdir' / '..' / 'declaration.md'),
                      'docs/../docs/declaration.md'):
            with self.subTest(named=named):
                self.refuses(named, commit, r"contains '\.\.'")
        with self.assertRaisesRegex(install.InstallError, r"contains '\.\.'"):
            install.committed_declaration(self.repo / 'docs' / 'linkdir' / '..' / 'declaration.md', commit,
                                          copy.read_bytes())
        # The receipt names the repository path actually checked, whatever form the variable took.
        for named in (self.NAME, f'./{self.NAME}', str(self.repo / self.NAME)):
            self.assertEqual(self.door(named, commit)['declaration'], self.NAME, named)

    def test_an_uncommitted_or_foreign_declaration_is_refused(self):
        ancestor = self.commit('docs/other.md', 'unrelated\n')
        outside = self.tmp / 'forged.md'
        outside.write_text(f'Revision installed: {REVISION}\n')
        self.refuses(outside, ancestor, 'inside this repository')
        (self.repo / self.NAME).write_text(f'Revision installed: {REVISION}\n')
        self.refuses(self.NAME, ancestor, 'not tracked')
        commit = self.commit(self.NAME, f'Revision installed: {REVISION}\n')
        self.refuses(self.NAME, ancestor, 'not the commit that last touched')
        (self.repo / self.NAME).write_text(f'Revision installed: {REVISION}, edited after the commit\n')
        self.refuses(self.NAME, commit, 'differs from its committed copy')


class TreeTests(unittest.TestCase):
    def check(self, *, resolved=REVISION, dirty='', head=REVISION, ancestors=(REVISION, OTHER), changed=''):
        def fake_git(*args, check=True):
            if args[0] == 'rev-parse' and args[1] == '--verify':
                return resolved
            if args[0] == 'status':
                return dirty
            if args == ('rev-parse', 'HEAD'):
                return head
            if args[0] == 'diff':
                return changed
            raise AssertionError(args)

        def fake_run(argv, **kwargs):
            return SimpleNamespace(returncode=0 if argv[-2] in ancestors else 1)
        with mock.patch.object(install, 'git', fake_git), mock.patch.object(install, 'run', fake_run):
            return install.check_tree(REVISION, OTHER)

    def test_exact_and_docs_only_descendant(self):
        self.assertEqual(self.check()['mode'], 'exact')
        self.assertEqual(self.check(head='c' * 40)['mode'], 'descendant-without-runtime-change')

    def test_refusals(self):
        cases = {'unknown revision': {'resolved': ''}, 'dirty tree': {'dirty': ' M cpt-studio/ops/install.py'},
                 'revision not an ancestor': {'head': 'c' * 40, 'ancestors': (OTHER,)},
                 'declaration not an ancestor': {'ancestors': (REVISION,)},
                 'runtime changed since revision': {'head': 'c' * 40, 'changed': 'cpt-studio/studio/api.py'}}
        for label, kwargs in cases.items():
            with self.subTest(label), self.assertRaises(install.InstallError):
                self.check(**kwargs)


# --- secrets handling ---------------------------------------------------------------

class SecretHandlingTests(unittest.TestCase):
    VALUE = 'x' * 40

    def test_env_validation(self):
        keys = install.APP_ENV_KEYS
        install.validate_env_text(f'CPT_STUDIO_SECRET_KEY={self.VALUE}\nCPT_STUDIO_DB_PASSWORD={self.VALUE}\n', keys)
        bad = {'missing': f'CPT_STUDIO_SECRET_KEY={self.VALUE}\n',
               'duplicate': f'CPT_STUDIO_SECRET_KEY={self.VALUE}\nCPT_STUDIO_SECRET_KEY={self.VALUE}\n'
                            f'CPT_STUDIO_DB_PASSWORD={self.VALUE}\n',
               'extra': f'CPT_STUDIO_SECRET_KEY={self.VALUE}\nCPT_STUDIO_DB_PASSWORD={self.VALUE}\n'
                        f'OTHER={self.VALUE}\n',
               'short': f'CPT_STUDIO_SECRET_KEY=short\nCPT_STUDIO_DB_PASSWORD={self.VALUE}\n',
               'quoted': f'CPT_STUDIO_SECRET_KEY="{self.VALUE}"\nCPT_STUDIO_DB_PASSWORD={self.VALUE}\n'}
        for label, text in bad.items():
            with self.subTest(label), self.assertRaises(install.InstallError):
                install.validate_env_text(text, keys)

    def test_env_validation_errors_never_echo_values(self):
        secret = 'TOPSECRETVALUE' * 3
        for text in (secret, f'{secret}={secret}', f'CPT_STUDIO_SECRET_KEY={secret} trailing'):
            with self.assertRaises(install.InstallError) as caught:
                install.validate_env_text(text, install.APP_ENV_KEYS)
            self.assertNotIn('TOPSECRET', str(caught.exception))

    def test_secret_leaks_in_output_are_refused(self):
        install.assert_no_secret([b'created human account owner (owner)'], ['s3cret-value-123'])
        with self.assertRaises(install.InstallError) as caught:
            install.assert_no_secret([b'ok', b'password is s3cret-value-123'], ['s3cret-value-123'])
        self.assertNotIn('s3cret', str(caught.exception))

    def test_provision_outcome(self):
        expected = {'owner': ('human', 'owner'), 'review-agent': ('agent', 'reviewer')}
        stdout = 'created human account owner (owner)\nkept agent account review-agent (reviewer)\nworkspace x\n'
        self.assertEqual(install.provision_outcome(stdout, expected), {'owner': 'created', 'review-agent': 'kept'})
        for wrong in ('created agent account owner (owner)\ncreated agent account review-agent (reviewer)',
                      'created human account owner (reviewer)\ncreated agent account review-agent (reviewer)',
                      'created human account owner (owner)'):
            with self.subTest(wrong=wrong), self.assertRaises(install.InstallError):
                install.provision_outcome(wrong, expected)


# --- docker arguments -----------------------------------------------------------------

class DockerArgumentTests(unittest.TestCase):
    IMAGE = 'sha256:' + 'c' * 64

    def flags(self, argv, flag):
        return [argv[i + 1] for i, part in enumerate(argv) if part == flag]

    def test_web_is_locked_down_and_loopback_only(self):
        argv = install.service_args('web', self.IMAGE, REVISION, 'live', 'docs/x.md')
        self.assertEqual(argv[-2:], [self.IMAGE, 'web'])
        for flag in ('--read-only', '--pull=never'):
            self.assertIn(flag, argv)
        self.assertEqual(self.flags(argv, '--cap-drop'), ['ALL'])
        self.assertEqual(self.flags(argv, '--security-opt'), ['no-new-privileges'])
        self.assertEqual(self.flags(argv, '--user'), [f'{install.APP_UID}:{install.APP_UID}'])
        self.assertEqual(self.flags(argv, '--memory'), self.flags(argv, '--memory-swap'))
        self.assertEqual(self.flags(argv, '-p'), ['127.0.0.1:9150:8000'])
        self.assertEqual(self.flags(argv, '--restart'), ['unless-stopped'])
        self.assertEqual(self.flags(argv, '--env-file'), ['/dev/stdin'])
        self.assertEqual(self.flags(argv, '--ulimit'), ['core=0'])
        self.assertTrue(self.flags(argv, '--tmpfs')[0].startswith('/tmp:rw,noexec,nosuid,nodev'))
        # Live: the web names the worker's credentials path (a context change builds the request it would send,
        # which opens nothing) but never mounts the file; only the worker holds it.
        self.assertIn(f'CPT_STUDIO_CORTI_CREDENTIALS_FILE={install.CREDENTIALS_IN_CONTAINER}', self.flags(argv, '-e'))
        self.assertEqual(self.flags(argv, '--mount'), [f'type=volume,src={install.FILES_VOLUME},dst={install.STATE_DIR}'])
        disabled = install.service_args('web', self.IMAGE, REVISION, 'disabled', '')
        self.assertNotIn('corti', ' '.join(disabled).lower())

    def test_worker_gets_credentials_only_when_live(self):
        live = install.service_args('worker', self.IMAGE, REVISION, 'live', 'docs/x.md')
        mounts = self.flags(live, '--mount')
        self.assertIn(f'type=bind,src={install.CORTI_TARGET},dst={install.CREDENTIALS_IN_CONTAINER},readonly', mounts)
        self.assertIn(f'CPT_STUDIO_CORTI_CREDENTIALS_FILE={install.CREDENTIALS_IN_CONTAINER}', self.flags(live, '-e'))
        self.assertIn('--no-healthcheck', live)
        self.assertEqual(self.flags(live, '--stop-timeout'), ['150'])
        self.assertEqual(self.flags(live, '-p'), [])
        disabled = install.service_args('worker', self.IMAGE, REVISION, 'disabled', '')
        self.assertNotIn('corti', ' '.join(disabled).lower())
        self.assertIn('CPT_STUDIO_PROVIDER_MODE=disabled', self.flags(disabled, '-e'))

    def test_no_secret_names_carry_values_in_argv(self):
        for argv in (install.service_args('web', self.IMAGE, REVISION, 'live', 'docs/x.md'),
                     install.service_args('worker', self.IMAGE, REVISION, 'live', 'docs/x.md'), install.db_args()):
            joined = ' '.join(argv)
            for name in ('SECRET_KEY', 'DB_PASSWORD', 'POSTGRES_PASSWORD', 'CLIENT_SECRET'):
                self.assertNotIn(name, joined)

    def test_installer_and_dockerfile_agree_on_the_application_uid(self):
        dockerfile = (DEPLOY / 'Dockerfile').read_text()
        uid = install.APP_UID
        self.assertIn(f'USER {uid}:{uid}', dockerfile)
        self.assertIn(f'--uid {uid} --gid {uid}', dockerfile)
        self.assertIn(f'install -d -o {uid} -g {uid} -m 0700 /var/lib/cpt-studio', dockerfile)
        self.assertNotEqual(uid, 10001)

    def test_image_makes_all_of_app_readable_after_copying_the_context(self):
        # COPY keeps the context's modes; the first install's 0700 directories reached the image this way.
        dockerfile = (DEPLOY / 'Dockerfile').read_text()
        after_copy = dockerfile[dockerfile.index('COPY . .'):dockerfile.index('USER ')]
        self.assertIn('chmod -R u=rwX,go=rX /app', after_copy)

    def test_database_readiness_is_probed_over_tcp(self):
        # The image's first-start init server listens on the unix socket only; the application connects over TCP.
        calls = []
        with mock.patch.object(install, 'docker', side_effect=lambda *argv, **kw: calls.append(argv)
                               or SimpleNamespace(returncode=0)):
            install.wait_db_ready(attempts=1)
        self.assertEqual(calls, [('exec', install.DB_CONTAINER, 'pg_isready', '-q', '-h', '127.0.0.1', '-p', '5432',
                                  '-U', install.DB_USER, '-d', install.DB_NAME)])

    def test_database_container(self):
        argv = install.db_args()
        self.assertEqual(argv[-1], install.POSTGRES_IMAGE)
        self.assertEqual(self.flags(argv, '--user'), ['70:70'])
        self.assertEqual(self.flags(argv, '--cap-drop'), ['ALL'])
        self.assertEqual(self.flags(argv, '-p'), ['127.0.0.1:55451:5432'])
        self.assertEqual(self.flags(argv, '--env-file'), ['/dev/stdin'])
        self.assertIn('@sha256:', install.POSTGRES_IMAGE)

    def test_reference_import_command_carries_pinned_provenance(self):
        command = install.reference_command('cms-mue-practitioner', '/var/lib/cpt-studio/reference/x.zip',
                                            '2026-10-23T21:01:44Z')
        values = dict(zip(command[2::2], command[3::2]))
        self.assertEqual(command[:2], ['manage', 'import_reference'])
        self.assertEqual(values, {
            '--kind': 'cms-mue-practitioner', '--zip': '/var/lib/cpt-studio/reference/x.zip',
            '--expected-sha256': install.REFERENCE_FILES['cms-mue-practitioner']['sha256'], '--release': '2026-Q4',
            '--url': 'https://www.cms.gov/files/zip/medicare-ncci-2026-q4-practitioner-services-mue-table.zip',
            '--effective-start': '2026-10-01', '--effective-end': '2026-12-31',
            '--retrieved-at': '2026-10-23T21:01:44Z'})
        for pinned in install.REFERENCE_FILES.values():
            self.assertTrue(pinned['url'].startswith('https://www.cms.gov/'))
            self.assertRegex(pinned['sha256'], '^[0-9a-f]{64}$')

    def test_oneshot_runs_with_provider_disabled_and_removes_leftovers(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        with mock.patch.object(install, 'run', fake_run), mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot(self.IMAGE, ['migrate'], b'ENV=1\n')
        argv, kwargs = calls[0]
        self.assertEqual(argv[-2:], [self.IMAGE, 'migrate'])
        self.assertIn('CPT_STUDIO_PROVIDER_MODE=disabled', argv)
        self.assertIn('--rm', argv)
        self.assertEqual(kwargs['input'], b'ENV=1\n')

    def test_credentials_check_runs_offline_with_the_worker_mount(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout=b'corti-credentials-parse-ok\n', stderr=b'')
        with mock.patch.object(install, 'run', fake_run), mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot(self.IMAGE, ['manage', 'shell', '-c', install.CREDENTIALS_CHECK], b'', network='none',
                            credentials=True)
            install.oneshot(self.IMAGE, ['migrate'], b'')
        checked, plain = calls
        self.assertEqual(self.flags(checked, '--network'), ['none'])
        self.assertIn(f'type=bind,src={install.CORTI_TARGET},dst={install.CREDENTIALS_IN_CONTAINER},readonly',
                      self.flags(checked, '--mount'))
        self.assertIn(f'CPT_STUDIO_CORTI_CREDENTIALS_FILE={install.CREDENTIALS_IN_CONTAINER}',
                      self.flags(checked, '-e'))
        self.assertIn('CPT_STUDIO_PROVIDER_MODE=disabled', self.flags(checked, '-e'))
        self.assertEqual(self.flags(plain, '--network'), [install.NETWORK])
        self.assertNotIn('corti', ' '.join(plain).lower())
        compile(install.CREDENTIALS_CHECK, 'credentials-check', 'exec')

    def test_helper_argv_and_source(self):
        argv = install.helper_argv('cpt-studio-helper-t', 't', ['type=bind,src=/x,dst=/y'], 'none', 1e10)
        for part in ('--rm', '-i', '--pull=never', '--log-driver=none'):
            self.assertIn(part, argv)
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        self.assertEqual(argv[argv.index(install.HELPER_IMAGE) + 1:argv.index(install.HELPER_IMAGE) + 4],
                         ['python', '-I', '-B'])
        compile(argv[-1], 'bootstrap', 'exec')
        source = install.helper_source('', {'a': [1, 'two'], 'quote': "'); import os #"})
        self.assertNotIn('import os #', source)  # parameters travel encoded, never as code
        namespace = {}
        exec(source, namespace)
        self.assertEqual(namespace['P'], {'a': [1, 'two'], 'quote': "'); import os #"})
        for name in [n for n in dir(install) if n.startswith('H_')]:
            compile(install.helper_source(getattr(install, name), {}), name, 'exec')

    def test_certbot_helper_cannot_register_or_touch_other_lineages(self):
        body = install.H_CERTBOT
        for required in ("'certonly'", "'--webroot'", "'--keep-until-expiring'", "'--account'", "'--non-interactive'",
                         "'--cert-name'"):
            self.assertIn(required, body)
        for forbidden in ('--agree-tos', '--expand', '--nginx', '--email', "'-m'", 'register', '--force-renewal',
                          'privkey'):
            self.assertNotIn(forbidden, body)


class CommandTests(unittest.TestCase):
    def test_command_labels_skip_option_values(self):
        self.assertEqual(install.command_label(['git', '-C', '/repo', 'status', '--porcelain']), 'git status')
        self.assertEqual(install.command_label(['/usr/bin/docker', 'run', '--rm', '-i', 'x']), 'docker run x')
        self.assertEqual(install.command_label(['sudo', '-n', '/usr/sbin/nginx', '-t']), 'sudo /usr/sbin/nginx')

    def test_foreign_tasks_on_the_application_uid_are_counted(self):
        proc = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, proc)
        own = 'a' * 64
        for pid, uid, threads, cgroup in (('10', 10150, 4, f'0::/system.slice/docker-{own}.scope'),
                                          ('11', 10150, 7, f'0::/system.slice/docker-{"b" * 64}.scope'),
                                          ('12', 1000, 9, '0::/user.slice'), ('13', 10150, 2, '0::/user.slice')):
            (proc / pid).mkdir()
            (proc / pid / 'status').write_text(
                f'Name:\tpython\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nThreads:\t{threads}\n')
            (proc / pid / 'cgroup').write_text(cgroup + '\n')
        (proc / 'self').mkdir()
        (proc / '14').mkdir()  # vanished mid-scan: no status file
        self.assertEqual(install.foreign_uid_tasks(10150, [own], proc), 9)
        self.assertEqual(install.foreign_uid_tasks(10150, [], proc), 13)
        self.assertEqual(install.foreign_uid_tasks(4242, [], proc), 0)

    def test_listening_ports(self):
        tcp = ('  sl  local_address rem_address   st\n'
               '   0: 0100007F:23C6 00000000:0000 0A\n'
               '   1: 0100007F:D8EB 00000000:0000 0A\n'
               '   2: 0100007F:1F90 0100007F:9C40 01\n')
        self.assertEqual(install.listening_ports([tcp]), {0x23C6, 0xD8EB})

    def test_health_requires_every_field(self):
        good = {'status': 'ok', 'service': 'cpt-studio', 'data_mode': 'synthetic-only', 'database': 'ok',
                'release': REVISION}
        self.assertTrue(install.health_ok(good, REVISION))
        self.assertFalse(install.health_ok(good, OTHER))
        for key, value in (('status', 'degraded'), ('database', 'error'), ('data_mode', 'real'), ('service', 'x')):
            self.assertFalse(install.health_ok({**good, key: value}, REVISION), key)
        self.assertFalse(install.health_ok(None, REVISION))


class ArchiveTests(TemporaryDirectoryTest):
    def archive(self, members):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as tar:
            for name, kind in members:
                info = tarfile.TarInfo(name)
                if kind == 'file':
                    info.size = 2
                    tar.addfile(info, io.BytesIO(b'ok'))
                elif kind == 'dir':
                    info.type = tarfile.DIRTYPE
                    tar.addfile(info)
                else:
                    info.type, info.linkname = tarfile.SYMTYPE, '/etc/passwd'
                    tar.addfile(info)
        return buffer.getvalue()

    def test_safe_archive_extracts(self):
        install.extract_archive(self.archive([('cpt-studio', 'dir'), ('cpt-studio/a.py', 'file')]), self.tmp)
        self.assertEqual((self.tmp / 'cpt-studio' / 'a.py').read_bytes(), b'ok')

    def test_directories_are_0755_under_the_installers_umask(self):
        # main() runs under umask 077, and the 'data' filter leaves directory modes to it: every directory
        # came out 0700 and the image user could not enter /app. The implicit parent is the case git archive
        # never lists explicitly in a test, so it is covered too.
        previous = os.umask(0o077)
        try:
            install.extract_archive(self.archive([('cpt-studio', 'dir'), ('cpt-studio/pkg/a.py', 'file')]), self.tmp)
        finally:
            os.umask(previous)
        for relative in ('cpt-studio', 'cpt-studio/pkg'):
            self.assertEqual(stat.S_IMODE((self.tmp / relative).stat().st_mode), 0o755, relative)
        self.assertEqual(stat.S_IMODE((self.tmp / 'cpt-studio' / 'pkg' / 'a.py').stat().st_mode), 0o644)

    def test_unsafe_archives_are_refused(self):
        for members in ([('cpt-studio/../x', 'file')], [('/abs/x', 'file')], [('other/x', 'file')],
                        [('cpt-studio/link', 'link')]):
            with self.subTest(members=members), self.assertRaises(install.InstallError):
                install.extract_archive(self.archive(members), self.tmp)


# --- helper bodies, executed against temporary directories --------------------------

class VhostHelperTests(TemporaryDirectoryTest):
    def setUp(self):
        super().setUp()
        self.available, self.enabled = self.tmp / 'available', self.tmp / 'enabled'
        self.available.mkdir()
        self.enabled.mkdir()
        self.quillmd = b'server { server_name app.quillmd.com; }\n'
        (self.available / 'quillmd').write_bytes(self.quillmd)
        self.confs = rendered()

    def op(self, op, **params):
        params = {'op': op, 'name': install.VHOST_NAME, 'link_target': install.VHOST_LINK_TARGET,
                  'quillmd_sha256': hashlib.sha256(self.quillmd).hexdigest(), **params}
        return run_body(install.H_VHOST, params, {"'/available'": repr(str(self.available)),
                                                  "'/enabled'": repr(str(self.enabled))})

    def content(self, kind):
        return base64.b64encode(self.confs[kind].encode()).decode()

    def sha(self, kind):
        return hashlib.sha256(self.confs[kind].encode()).hexdigest()

    def test_install_replace_remove_cycle(self):
        result = self.op('install', content=self.content('http'))
        self.assertEqual(result['done'], 'installed')
        self.assertEqual(result['state']['file_sha256'], self.sha('http'))
        self.assertEqual(os.readlink(self.enabled / install.VHOST_NAME), install.VHOST_LINK_TARGET)
        self.assertIn('error', self.op('install', content=self.content('http')))
        self.assertIn('error', self.op('replace', expected_sha256=self.sha('https'), content=self.content('https')))
        self.assertEqual(self.op('replace', expected_sha256=self.sha('http'), content=self.content('https'))['done'],
                         'replaced')
        self.assertEqual((self.available / install.VHOST_NAME).read_text(), self.confs['https'])
        self.assertEqual(self.op('remove', allowed_sha256=[self.sha('http'), self.sha('https')])['done'], 'removed')
        self.assertFalse(os.path.lexists(self.available / install.VHOST_NAME))
        self.assertFalse(os.path.lexists(self.enabled / install.VHOST_NAME))
        self.assertEqual((self.available / 'quillmd').read_bytes(), self.quillmd)

    def test_refuses_when_the_quillmd_vhost_is_not_the_pinned_one(self):
        (self.available / 'quillmd').write_bytes(self.quillmd + b'# edited\n')
        result = self.op('install', content=self.content('http'))
        self.assertIn('error', result)
        self.assertFalse(os.path.lexists(self.available / install.VHOST_NAME))

    def test_never_removes_a_vhost_it_did_not_write(self):
        (self.available / install.VHOST_NAME).write_text('server { listen 80; server_name cpt.quillmd.com; }\n')
        os.symlink(install.VHOST_LINK_TARGET, self.enabled / install.VHOST_NAME)
        self.assertIn('error', self.op('remove', allowed_sha256=[self.sha('http')]))
        self.assertTrue((self.available / install.VHOST_NAME).exists())
        (self.available / install.VHOST_NAME).write_text(self.confs['http'])
        os.unlink(self.enabled / install.VHOST_NAME)
        os.symlink('/etc/nginx/sites-available/quillmd', self.enabled / install.VHOST_NAME)
        self.assertIn('error', self.op('remove', allowed_sha256=[self.sha('http')]))
        self.assertTrue(os.path.islink(self.enabled / install.VHOST_NAME))


class SecretsHelperTests(TemporaryDirectoryTest):
    CORTI = (b'# synthetic test credentials\nCORTI_CLIENT_ID=client\nexport CORTI_CLIENT_SECRET=not-a-real-secret\n'
             b'CORTI_ENVIRONMENT=eu\nCORTI_TENANT_NAME=tenant\n')

    def setUp(self):
        super().setUp()
        self.target = self.tmp / 'target'
        self.target.mkdir(mode=0o700)
        self.source = self.tmp / 'credentials.env'
        self.source.write_bytes(self.CORTI)
        self.fake = FakeOwnership()

    def run_secrets(self):
        params = {'uid': install.APP_UID, 'corti_keys': list(install.CORTI_KEYS),
                  'app_keys': list(install.APP_ENV_KEYS), 'db_keys': list(install.DB_ENV_KEYS)}
        return run_body(install.H_SECRETS, params, {"'/target'": repr(str(self.target)),
                                                    "'/source/credentials.env'": repr(str(self.source))}, self.fake)

    def test_creates_secrets_once_then_reports_present(self):
        created = self.run_secrets()
        self.assertEqual(created['state'], 'created')
        self.assertEqual(created['files']['corti-credentials.env'],
                         {'regular': True, 'uid': install.APP_UID, 'gid': install.APP_UID, 'mode': '0o400'})
        app_env = (self.target / 'app.env').read_text()
        install.validate_env_text(app_env, install.APP_ENV_KEYS)
        password = app_env.split('CPT_STUDIO_DB_PASSWORD=')[1].strip()
        self.assertEqual((self.target / 'db.env').read_text(), f'POSTGRES_PASSWORD={password}\n')
        self.assertEqual((self.target / 'corti-credentials.env').read_bytes(), self.CORTI)
        self.assertNotIn(password, json.dumps(created))
        self.assertNotIn('not-a-real-secret', json.dumps(created))
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ['app.env', 'corti-credentials.env', 'db.env'])
        again = self.run_secrets()
        self.assertEqual(again['state'], 'present')
        self.assertEqual((self.target / 'app.env').read_text(), app_env)

    def test_refuses_missing_corti_names_without_writing(self):
        self.source.write_bytes(b'CORTI_CLIENT_ID=x\nCORTI_CLIENT_SECRET=y\n')
        result = self.run_secrets()
        self.assertIn('CORTI_ENVIRONMENT', result['error'])
        self.assertNotIn('=x', result['error'])
        self.assertEqual(list(self.target.iterdir()), [])

    def test_refuses_partial_state_and_changed_sources(self):
        (self.target / 'app.env').write_text('CPT_STUDIO_SECRET_KEY=' + 'k' * 40 + '\n')
        self.assertIn('partial', self.run_secrets()['error'])
        (self.target / 'app.env').unlink()
        self.run_secrets()
        self.source.write_bytes(self.CORTI + b'# rotated\n')
        self.assertIn('differs', self.run_secrets()['error'])


class RootFileHelperTests(TemporaryDirectoryTest):
    def op(self, op, **params):
        params = {'op': op, 'final': install.INITIAL_CREDENTIALS, 'staged': f'.{install.INITIAL_CREDENTIALS}.new',
                  'replace': False, **params}
        return run_body(install.H_ROOT_FILE, params, {"'/target'": repr(str(self.tmp))})

    def test_stage_commit_discard(self):
        content = base64.b64encode(b'{"accounts": []}').decode()
        self.assertEqual(self.op('state'), {'final_exists': False, 'staged_exists': False})
        self.op('stage', content=content)
        self.assertEqual(self.op('commit')['committed'], True)
        self.assertEqual((self.tmp / install.INITIAL_CREDENTIALS).read_bytes(), b'{"accounts": []}')
        self.op('stage', content=content)
        self.assertIn('error', self.op('commit'))
        wrong = self.op('discard', sha256='0' * 64)
        self.assertEqual(wrong, {'discarded': False})
        right = self.op('discard', sha256=hashlib.sha256(b'{"accounts": []}').hexdigest())
        self.assertEqual(right, {'discarded': True})
        self.op('stage', content=base64.b64encode(b'{"rotated": true}').decode())
        self.assertTrue(self.op('commit', replace=True)['committed'])
        self.assertEqual((self.tmp / install.INITIAL_CREDENTIALS).read_bytes(), b'{"rotated": true}')


class LetsEncryptHelperTests(TemporaryDirectoryTest):
    def test_reports_paths_without_opening_key_material(self):
        host = self.tmp / 'host'
        le = host / 'etc' / 'letsencrypt'
        live = le / 'live' / 'quillmd.com'
        live.mkdir(parents=True)
        for name in ('cert.pem', 'chain.pem', 'fullchain.pem'):
            (live / name).write_text('public')
        key = live / 'privkey.pem'
        key.write_text('never read')
        key.chmod(0o000)
        (le / 'live' / 'README').write_text('not a lineage')
        (le / 'renewal').mkdir()
        (le / 'renewal' / 'quillmd.com.conf').write_text('account = abc\n')
        (le / install.LE_ACCOUNTS / 'abc123').mkdir(parents=True)
        result = run_body(install.H_LE_STATE, {'dirs': ['/etc/letsencrypt', '/var/log/letsencrypt'],
                                               'accounts': install.LE_ACCOUNTS},
                          {"'/host/etc/letsencrypt'": repr(str(le)), "'/host' + d": repr(str(host)) + ' + d'})
        self.assertEqual(result['live'], {'quillmd.com': {'cert.pem': True, 'chain.pem': True, 'fullchain.pem': True,
                                                          'privkey.pem': True}})
        self.assertEqual(result['accounts'], ['abc123'])
        self.assertEqual(result['dirs'], {'/etc/letsencrypt': True, '/var/log/letsencrypt': False})
        self.assertEqual(result['renewal'], {'quillmd.com.conf': hashlib.sha256(b'account = abc\n').hexdigest()})


class AcmeAndVolumeHelperTests(TemporaryDirectoryTest):
    def test_acme_probe_write_and_remove(self):
        mapping = {"'/acme'": repr(str(self.tmp))}
        params = {'name': 'token', 'content': 'abc'}
        run_body(install.H_ACME_WRITE, params, mapping)
        self.assertEqual(stat.S_IMODE((self.tmp / 'token').stat().st_mode), 0o644)
        (self.tmp / 'token').write_text('changed by someone else')
        self.assertIn('error', run_body(install.H_ACME_REMOVE, params, mapping))
        self.assertTrue((self.tmp / 'token').exists())
        (self.tmp / 'token').write_text('abc')
        self.assertEqual(run_body(install.H_ACME_REMOVE, params, mapping), {'removed': True})

    def test_reference_copy_into_the_files_volume(self):
        files, source = self.tmp / 'files', self.tmp / 'source.zip'
        files.mkdir()
        source.write_bytes(b'PK synthetic zip bytes')
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        mapping = {"'/files'": repr(str(files)), "'/in/source.zip'": repr(str(source))}
        fake = FakeOwnership()
        self.assertEqual(run_body(install.H_FILES_VOLUME, {'uid': install.APP_UID, 'sha256': digest}, mapping, fake),
                         {'copied': True})
        copy = files / 'reference' / f'{digest}.zip'
        self.assertEqual(copy.read_bytes(), source.read_bytes())
        self.assertEqual(fake.owners[str(copy)], (install.APP_UID, install.APP_UID))
        self.assertEqual(fake.owners[str(files)], (install.APP_UID, install.APP_UID))
        self.assertEqual(run_body(install.H_FILES_VOLUME, {'uid': install.APP_UID, 'sha256': digest}, mapping, fake),
                         {'copied': False})
        self.assertIn('error', run_body(install.H_FILES_VOLUME, {'uid': install.APP_UID, 'sha256': '0' * 64},
                                        mapping, fake))


# --- helper runner, probes and phase refusals ----------------------------------------

class HelperRunnerTests(unittest.TestCase):
    def fake_docker(self, removed=True, label=None):
        def docker(*args, **kwargs):
            if args[:2] == ('container', 'inspect'):
                if removed:
                    return SimpleNamespace(returncode=1, stdout=b'', stderr=b'No such container')
                return SimpleNamespace(returncode=0, stdout=f'{"d" * 64}|{label}'.encode(), stderr=b'')
            if args[:2] == ('container', 'ls'):
                return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
            raise AssertionError(args)
        return docker

    def test_returns_the_final_json_line_after_cleanup(self):
        completed = SimpleNamespace(returncode=0, stdout=b'noise\n{"ok": 1}\n', stderr=b'')
        with mock.patch.object(install.subprocess, 'run', return_value=completed) as runner, \
                mock.patch.object(install, 'docker', self.fake_docker()):
            self.assertEqual(install.run_helper('print(1)', {}, mounts=[]), {'ok': 1})
        argv = runner.call_args.args[0]
        self.assertEqual(argv[argv.index('--network') + 1], 'none')
        self.assertIn(b'P=json.loads(base64.b64decode(', runner.call_args.kwargs['input'])

    def test_failures_keep_stderr_unless_sensitive(self):
        failed = SimpleNamespace(returncode=1, stdout=b'', stderr=b'Traceback: detail')
        for sensitive, expected in ((False, b'Traceback: detail'), (True, b'')):
            with mock.patch.object(install.subprocess, 'run', return_value=failed), \
                    mock.patch.object(install, 'docker', self.fake_docker()), \
                    self.assertRaises(install.InstallError) as caught:
                install.run_helper('x', {}, mounts=[], sensitive=sensitive)
            self.assertEqual(caught.exception.output, expected)
        refused = SimpleNamespace(returncode=0, stdout=b'{"error": "nope"}\n', stderr=b'')
        with mock.patch.object(install.subprocess, 'run', return_value=refused), \
                mock.patch.object(install, 'docker', self.fake_docker()), self.assertRaises(install.InstallError):
            install.run_helper('x', {}, mounts=[])

    def test_timeouts_still_remove_the_container(self):
        with mock.patch.object(install.subprocess, 'run', side_effect=subprocess.TimeoutExpired('docker', 1)), \
                mock.patch.object(install, 'remove_helper') as remover, self.assertRaises(install.InstallError):
            install.run_helper('x', {}, mounts=[], timeout=1)
        remover.assert_called_once()

    def test_cleanup_never_touches_a_foreign_container(self):
        with mock.patch.object(install, 'docker', self.fake_docker(removed=False, label='someone-else')), \
                self.assertRaises(install.InstallError):
            install.remove_helper('cpt-studio-helper-x', 'mine')


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/health/':
            body = json.dumps({'status': 'ok', 'release': REVISION, 'host': self.headers['Host']}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/close':
            self.close_connection = True
            self.connection.shutdown(2)
        else:
            self.send_response(301)
            self.send_header('Location', 'https://cpt.quillmd.com/')
            self.send_header('Content-Length', '0')
            self.end_headers()


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # the /close route breaks its own connection on purpose


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _QuietServer(('127.0.0.1', 0), _Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_json_redirect_and_closed_connection(self):
        health = install.probe('http', install.DOMAIN, '/health/', port=self.port, connect_ip='127.0.0.1')
        self.assertEqual((health['status'], health['json']['host']), (200, install.DOMAIN))
        redirect = install.probe('http', install.DOMAIN, '/', port=self.port, connect_ip='127.0.0.1')
        self.assertEqual((redirect['status'], redirect['headers']['location']), (301, ['https://cpt.quillmd.com/']))
        closed = install.probe('http', install.DOMAIN, '/close', port=self.port, connect_ip='127.0.0.1')
        self.assertIn('error', closed)
        refused = install.probe('http', install.DOMAIN, '/', port=1, connect_ip='127.0.0.1', timeout=1)
        self.assertEqual(refused, {'error': 'ConnectionRefusedError'})

    def test_poll_stops_at_the_first_pass_and_is_bounded(self):
        results = iter([(False, {'n': 0}), (True, {'n': 1}), (True, {'n': 2})])
        with mock.patch.object(install.time, 'sleep'):
            self.assertEqual(install.poll(lambda: next(results), attempts=5, interval=0)[0], True)
            passed, observations = install.poll(lambda: (False, {}), attempts=3, interval=0)
        self.assertEqual((passed, len(observations)), (False, 3))


class PhaseRefusalTests(TemporaryDirectoryTest):
    def ctx(self, phase='http-vhost', **arguments):
        args = SimpleNamespace(phase=phase, revision=REVISION, receipts=str(self.tmp), **arguments)
        return install.Context(args, self.tmp)

    def receipt(self, phase, details=None):
        install.write_receipt(self.tmp, phase, {'phase': phase, 'ok': True, 'revision': REVISION,
                                                'details': details or {}})

    def test_http_vhost_refuses_a_foreign_existing_vhost(self):
        self.receipt('preflight')
        state = {'file_exists': True, 'file_sha256': '0' * 64, 'link_exists': True,
                 'link_target': install.VHOST_LINK_TARGET}
        with mock.patch.object(install, 'rendered_vhosts', return_value=rendered()), \
                mock.patch.object(install, 'vhost_state', return_value=state), \
                mock.patch.object(install, 'run_helper') as helper, self.assertRaises(install.InstallError):
            install.phase_http_vhost(self.ctx())
        helper.assert_not_called()

    def test_phases_refuse_without_their_prerequisite_receipts(self):
        for phase, function in (('http-vhost', install.phase_http_vhost), ('cert', install.phase_cert),
                                ('https-vhost', install.phase_https_vhost), ('verify', install.phase_verify)):
            with self.subTest(phase), self.assertRaises(install.InstallError) as caught:
                function(self.ctx(phase))
            self.assertIn('receipt', str(caught.exception))

    def test_cert_requires_exactly_one_existing_account(self):
        self.receipt('http-vhost')
        state = {'file_sha256': hashlib.sha256(rendered()['http'].encode()).hexdigest()}
        dns = [(2, 1, 6, '', (install.PUBLIC_IPV4, 80))]
        for accounts in ([], ['one', 'two']):
            le = {'accounts': accounts, 'live': {}, 'renewal': {}, 'dirs': {}}
            with self.subTest(accounts=accounts), \
                    mock.patch.object(install, 'rendered_vhosts', return_value=rendered()), \
                    mock.patch.object(install, 'vhost_state', return_value=state), \
                    mock.patch.object(install.socket, 'getaddrinfo', return_value=dns), \
                    mock.patch.object(install, 'le_state', return_value=le), \
                    mock.patch.object(install, 'run_helper') as helper, self.assertRaises(install.InstallError):
                install.phase_cert(self.ctx('cert'))
            helper.assert_not_called()

    def test_cert_refuses_when_dns_moved(self):
        self.receipt('http-vhost')
        state = {'file_sha256': hashlib.sha256(rendered()['http'].encode()).hexdigest()}
        moved = [(2, 1, 6, '', (install.PUBLIC_IPV4, 80)), (10, 1, 6, '', ('2001:db8::1', 80, 0, 0))]
        with mock.patch.object(install, 'rendered_vhosts', return_value=rendered()), \
                mock.patch.object(install, 'vhost_state', return_value=state), \
                mock.patch.object(install.socket, 'getaddrinfo', return_value=moved), \
                mock.patch.object(install, 'le_state') as le, self.assertRaises(install.InstallError):
            install.phase_cert(self.ctx('cert'))
        le.assert_not_called()

    def test_https_vhost_refuses_when_the_http_stage_is_not_ours(self):
        self.receipt('preflight')
        self.receipt('cert')
        state = {'file_exists': True, 'file_sha256': '0' * 64, 'link_exists': True,
                 'link_target': install.VHOST_LINK_TARGET}
        with mock.patch.object(install, 'rendered_vhosts', return_value=rendered()), \
                mock.patch.object(install, 'vhost_state', return_value=state), \
                mock.patch.object(install, 'run_helper') as helper, self.assertRaises(install.InstallError):
            install.phase_https_vhost(self.ctx('https-vhost'))
        helper.assert_not_called()

    def test_publish_restores_on_failed_verification_or_new_warnings(self):
        ok = {'ok': True, 'warnings': ['w1'], 'output': 'test is successful'}
        louder = {'ok': True, 'warnings': ['w1', 'w2'], 'output': 'test is successful'}
        for after, reloads in ((ok, 2), (louder, 0)):
            calls = []
            tests = iter([ok, after, ok])

            def verify():
                raise install.InstallError('probe failed')
            with self.subTest(after=after['warnings']), \
                    mock.patch.object(install, 'nginx_test', lambda: next(tests)), \
                    mock.patch.object(install, 'nginx_reload', lambda: calls.append('reload')), \
                    self.assertRaises(install.InstallError):
                install.publish_vhost(self.ctx(), lambda: calls.append('apply'), lambda: calls.append('undo'), verify)
            self.assertEqual(calls.count('undo'), 1)
            self.assertEqual(calls.count('reload'), reloads)

    def test_a_failed_restore_names_both_failures(self):
        ok = {'ok': True, 'warnings': [], 'output': 'test is successful'}

        def verify():
            raise install.InstallError('probe failed')

        def undo():
            raise install.InstallError('helper refused')
        with mock.patch.object(install, 'nginx_test', return_value=ok), \
                mock.patch.object(install, 'nginx_reload'), self.assertRaises(install.InstallError) as caught:
            install.publish_vhost(self.ctx(), lambda: None, undo, verify)
        self.assertIn('probe failed', str(caught.exception))
        self.assertIn('helper refused', str(caught.exception))

    def test_an_installed_http_stage_is_reverified_without_touching_nginx(self):
        self.receipt('preflight', {'routing': {}, 'app_health': {'status': 200}})
        state = {'file_exists': True, 'file_sha256': hashlib.sha256(rendered()['http'].encode()).hexdigest(),
                 'link_exists': True, 'link_target': install.VHOST_LINK_TARGET}
        acme = {'passed': True, 'probe_removed': True}
        redirect = {'status': 301, 'headers': {'location': [f'https://{install.DOMAIN}/']}}
        with mock.patch.object(install, 'rendered_vhosts', return_value=rendered()), \
                mock.patch.object(install, 'vhost_state', return_value=state), \
                mock.patch.object(install, 'acme_probe', return_value=acme), \
                mock.patch.object(install, 'probe', return_value=redirect), \
                mock.patch.object(install, 'ingress_checks', return_value=[]), \
                mock.patch.object(install, 'publish_vhost') as publish, \
                mock.patch.object(install, 'nginx_reload') as reload:
            result = install.phase_http_vhost(self.ctx())
        publish.assert_not_called()
        reload.assert_not_called()
        self.assertTrue(result['already_installed'])

    def test_publish_refuses_when_nginx_is_already_broken(self):
        with mock.patch.object(install, 'nginx_test', return_value={'ok': False, 'warnings': [], 'output': ''}), \
                self.assertRaises(install.InstallError):
            install.publish_vhost(self.ctx(), mock.Mock(side_effect=AssertionError('applied')), mock.Mock(),
                                  mock.Mock())

    def republish_case(self, *, recorded=True, reproducible=True):
        """Live: the OLD revision's HTTPS stage. Running: the NEW revision, whose HTTPS template changed."""
        old = rendered()
        new = {'http': old['http'], 'https': old['https'].replace('client_max_body_size 20m;', 'client_max_body_size 25m;')}
        self.assertNotEqual(old['https'], new['https'])
        old_sha = hashlib.sha256(old['https'].encode()).hexdigest()
        self.receipt('preflight', {'routing': {}, 'app_health': {'status': 200}})
        if recorded:
            install.write_receipt(self.tmp, 'https-vhost', {'phase': 'https-vhost', 'ok': True, 'revision': OTHER,
                                                            'details': {'vhost_sha256': old_sha}})
        by_revision = {REVISION: new, OTHER: old if reproducible else new}
        live = {'file_exists': True, 'file_sha256': old_sha, 'link_exists': True,
                'link_target': install.VHOST_LINK_TARGET}
        return by_revision, live, old

    def test_rollback_vhost_removes_a_stage_an_earlier_receipt_recorded_and_restores_its_exact_bytes(self):
        # reproducible=False: re-rendering the OLD revision with this installer's parameters no longer yields the
        # live bytes (the round-2 case: a changed WEB_PORT or placeholder set). The live bytes are restored.
        by_revision, live, old = self.republish_case(reproducible=False)
        operations = []
        states = iter([live, {'file_exists': False, 'link_exists': False, 'file_sha256': None, 'link_target': None}])

        def publish(ctx, apply, undo, verify):
            apply()
            undo()  # as on a failed verification: the removal is put back exactly
            return {}
        with mock.patch.object(install, 'rendered_vhosts', side_effect=lambda revision: by_revision[revision]), \
                mock.patch.object(install, 'vhost_state', side_effect=lambda: next(states)), \
                mock.patch.object(install, 'live_vhost_bytes', return_value=old['https'].encode()), \
                mock.patch.object(install, 'vhost_operation', side_effect=lambda op, **kw: operations.append((op, kw))), \
                mock.patch.object(install, 'publish_vhost', side_effect=publish):
            install.phase_rollback_vhost(self.ctx('rollback-vhost'))
        old_sha = hashlib.sha256(old['https'].encode()).hexdigest()
        self.assertEqual(operations[0][0], 'remove')
        self.assertIn(old_sha, operations[0][1]['allowed_sha256'])
        self.assertEqual(operations[1], ('install', {'content': base64.b64encode(old['https'].encode()).decode()}))

    def test_live_vhost_bytes_reads_only_a_regular_file(self):
        # Round 3, evidence:2: the repair's central reader was mocked in every test.
        available = self.tmp / 'sites-available'
        available.mkdir()
        with mock.patch.object(install, 'NGINX_AVAILABLE', available):
            self.assertIsNone(install.live_vhost_bytes())  # absent
            (available / install.VHOST_NAME).write_bytes(b'server { listen 80; }\n')
            self.assertEqual(install.live_vhost_bytes(), b'server { listen 80; }\n')
            (available / install.VHOST_NAME).unlink()
            (available / 'elsewhere').write_bytes(b'server { listen 80; }\n')
            (available / install.VHOST_NAME).symlink_to(available / 'elsewhere')
            self.assertIsNone(install.live_vhost_bytes())  # a link is never read as the stage

    def test_rollback_vhost_restores_the_live_bytes_from_real_files(self):
        """The round-2 republish case end to end on real files: only the root helper (emulated on the temp dirs),
        publish_vhost and rendering are replaced; live_vhost_bytes and vhost_state run for real."""
        available, enabled = self.tmp / 'sites-available', self.tmp / 'sites-enabled'
        available.mkdir()
        enabled.mkdir()
        old = rendered()
        new = {'http': old['http'], 'https': old['https'].replace('client_max_body_size 20m;', 'client_max_body_size 25m;')}
        self.assertNotEqual(old['https'], new['https'])
        live_file = available / install.VHOST_NAME
        live_file.write_bytes(old['https'].encode())
        (enabled / install.VHOST_NAME).symlink_to(live_file)
        self.receipt('preflight', {'routing': {}, 'app_health': {'status': 200}})
        install.write_receipt(self.tmp, 'https-vhost', {'phase': 'https-vhost', 'ok': True, 'revision': OTHER,
                                                        'details': {'vhost_sha256': hashlib.sha256(
                                                            old['https'].encode()).hexdigest()}})
        operations = []

        def helper(op, **params):
            operations.append(op)
            if op == 'remove':
                (enabled / install.VHOST_NAME).unlink()
                live_file.unlink()
            elif op == 'install':
                live_file.write_bytes(base64.b64decode(params['content']))
                (enabled / install.VHOST_NAME).symlink_to(live_file)
            return {}

        def publish(ctx, apply, undo, verify):
            apply()
            undo()  # as on a failed verification: the removal is put back exactly
            return {}
        with mock.patch.object(install, 'NGINX_AVAILABLE', available), \
                mock.patch.object(install, 'NGINX_ENABLED', enabled), \
                mock.patch.object(install, 'rendered_vhosts', side_effect=lambda revision: new), \
                mock.patch.object(install, 'vhost_operation', side_effect=helper), \
                mock.patch.object(install, 'publish_vhost', side_effect=publish):
            install.phase_rollback_vhost(self.ctx('rollback-vhost'))
        self.assertEqual(operations, ['remove', 'install'])
        self.assertEqual(live_file.read_bytes(), old['https'].encode())
        self.assertTrue((enabled / install.VHOST_NAME).is_symlink())

    def test_rollback_vhost_refuses_an_unrecorded_stage_or_one_that_changed_while_read(self):
        for recorded, live_bytes, message in ((False, None, 'did not write'), (True, b'changed meanwhile', 'changed while')):
            with self.subTest(recorded=recorded):
                for path in self.tmp.glob('*.json'):
                    path.unlink()
                by_revision, live, old = self.republish_case(recorded=recorded)
                with mock.patch.object(install, 'rendered_vhosts', side_effect=lambda revision: by_revision[revision]), \
                        mock.patch.object(install, 'vhost_state', return_value=live), \
                        mock.patch.object(install, 'live_vhost_bytes', return_value=live_bytes or old['https'].encode()), \
                        mock.patch.object(install, 'vhost_operation') as operation, \
                        mock.patch.object(install, 'publish_vhost') as publish, \
                        self.assertRaisesRegex(install.InstallError, message):
                    install.phase_rollback_vhost(self.ctx('rollback-vhost'))
                operation.assert_not_called()
                publish.assert_not_called()

    def test_verify_compares_other_lineages_without_this_domains_own_on_both_sides(self):
        own = f'{install.DOMAIN}.conf'
        baseline = {'renewal': {own: 'a', 'app.quillmd.com.conf': 'b'}, 'live': {install.DOMAIN: {}, 'app.quillmd.com': {}}}
        now = {'renewal': {own: 'c', 'app.quillmd.com.conf': 'b'}, 'live': {install.DOMAIN: {}, 'app.quillmd.com': {}}}
        self.assertEqual(install.other_lineages(now), install.other_lineages(baseline))
        changed = {'renewal': {own: 'c', 'app.quillmd.com.conf': 'X'}, 'live': {install.DOMAIN: {}, 'app.quillmd.com': {}}}
        self.assertNotEqual(install.other_lineages(changed), install.other_lineages(baseline))

    def run_verify(self, le_now):
        own = f'{install.DOMAIN}.conf'
        https_sha = hashlib.sha256(rendered()['https'].encode()).hexdigest()
        files = {'available': {'quillmd': install.QUILLMD_VHOST_SHA256, install.VHOST_NAME: '1' * 64},
                 'enabled': {'quillmd': 'quillmd', install.VHOST_NAME: install.VHOST_LINK_TARGET},
                 'nginx_conf_sha256': '2' * 64, 'conf_d': {}}
        # A reinstall: the preflight baseline already holds this domain's vhost and its lineage.
        self.receipt('preflight', {'nginx_files': files, 'routing': {}, 'app_health': {'status': 200},
                                   'cotenants': {'ok': True}, 'containers': {}, 'volumes': ['v'],
                                   'letsencrypt': {'renewal': {own: 'a', 'app.quillmd.com.conf': 'b'},
                                                   'live': {install.DOMAIN: {}, 'app.quillmd.com': {}}}})
        current = {**files, 'available': {**files['available'], install.VHOST_NAME: https_sha}}
        running = {'State': {'Running': True}, 'Id': 'x'}
        with mock.patch.object(install, 'installed_image', return_value='sha256:' + 'c' * 64), \
                mock.patch.object(install, 'nginx_file_state', return_value=current), \
                mock.patch.object(install, 'rendered_vhosts', return_value=rendered()), \
                mock.patch.object(install, 'ingress_checks', return_value=[]), \
                mock.patch.object(install, 'cotenant_check', return_value={'ok': True}), \
                mock.patch.object(install, 'containers', return_value={}), \
                mock.patch.object(install, 'volumes', return_value=['v']), \
                mock.patch.object(install, 'le_state', return_value=le_now), \
                mock.patch.object(install, 'inspect', return_value=running), \
                mock.patch.object(install, 'db_container_problems', return_value=[]), \
                mock.patch.object(install, 'service_problems', return_value=[]), \
                mock.patch.object(install, 'https_checks', return_value=([], {})), \
                mock.patch.object(install, 'foreign_uid_tasks', return_value=0), \
                mock.patch.object(install, 'own_service_ids', return_value=[]):
            return install.phase_verify(self.ctx('verify'))

    def test_verify_after_a_reinstall_accepts_this_domains_own_renewed_lineage(self):
        own = f'{install.DOMAIN}.conf'
        renewed = {'renewal': {own: 'c', 'app.quillmd.com.conf': 'b'}, 'live': {install.DOMAIN: {}, 'app.quillmd.com': {}}}
        self.assertIn('verified', self.run_verify(renewed)['summary'])
        changed = {'renewal': {own: 'c', 'app.quillmd.com.conf': 'X'}, 'live': {install.DOMAIN: {}, 'app.quillmd.com': {}}}
        with self.assertRaisesRegex(install.InstallError, 'another Let.s Encrypt lineage changed'):
            self.run_verify(changed)

    def test_reference_refuses_a_file_that_is_not_the_pinned_one(self):
        fake = self.tmp / 'rvu.zip'
        fake.write_bytes(b'not the CMS file')
        ctx = self.ctx('reference', pfs_zip=str(fake), mue_zip=str(fake), pfs_retrieved_at='2026-10-23T20:59:00Z',
                       mue_retrieved_at='2026-10-23T21:01:44Z')
        with mock.patch.object(install, 'installed_image', return_value='sha256:' + 'c' * 64), \
                mock.patch.object(install, 'require_db'), \
                mock.patch.object(install, 'read_protected_env', return_value=b''), \
                mock.patch.object(install, 'run_helper') as helper, self.assertRaises(install.InstallError) as caught:
            install.phase_reference(ctx)
        helper.assert_not_called()
        self.assertIn('pinned', str(caught.exception))

    def test_provision_refuses_existing_credentials_without_reset(self):
        ctx = self.ctx('provision', reset_passwords=None, owner_username='owner', agent_username='review-agent',
                       owner_display_name='', agent_display_name='CPT Studio review agent',
                       workspace_name='Gastroenterology')
        with mock.patch.object(install, 'installed_image', return_value='sha256:' + 'c' * 64), \
                mock.patch.object(install, 'require_db'), \
                mock.patch.object(install, 'read_protected_env', return_value=b''), \
                mock.patch.object(install, 'root_file', return_value={'final_exists': True, 'staged_exists': False}), \
                mock.patch.object(install, 'oneshot') as oneshot, self.assertRaises(install.InstallError):
            install.phase_provision(ctx)
        oneshot.assert_not_called()

    def test_live_app_stops_before_migrating_when_credentials_do_not_load(self):
        ctx = self.ctx('app', provider_mode='live',
                       authorization_ref='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
        corti = {'exists': True, 'kind': 'file', 'uid': install.APP_UID, 'gid': install.APP_UID, 'mode': '0o400'}
        # credentials, then migrate, then the read of the queue for stages this revision cannot run (refutation r1)
        for loads, expected_commands in ((False, 1), (True, 3)):
            commands = []

            def fake_oneshot(image_id, command, env, **kwargs):
                commands.append(command)
                if command[:2] == ['manage', 'shell'] and install.UNRUNNABLE_STAGES in command[-1]:
                    answer = install.APP_SCRIPT_ANSWER + json.dumps({'known': [], 'stuck': 0, 'kinds': []})
                    return SimpleNamespace(returncode=0, stderr=b'', stdout=answer.encode() + b'\n')
                parsed = loads or command[:2] != ['manage', 'shell']
                return SimpleNamespace(returncode=0 if parsed else 1, stderr=b'CredentialsError: refused',
                                       stdout=b'corti-credentials-parse-ok\n' if parsed else b'')
            with self.subTest(loads=loads), \
                    mock.patch.object(install, 'run', return_value=SimpleNamespace(returncode=0)), \
                    mock.patch.object(install, 'installed_image', return_value='sha256:' + 'c' * 64), \
                    mock.patch.object(install, 'require_db'), \
                    mock.patch.object(install, 'helper_stat', return_value={install.CORTI_TARGET: corti}), \
                    mock.patch.object(install, 'read_protected_env', return_value=b''), \
                    mock.patch.object(install, 'oneshot', fake_oneshot), \
                    mock.patch.object(install, 'replace_services', return_value={}) as replace:
                if loads:
                    install.phase_app(ctx)
                else:
                    with self.assertRaises(install.InstallError):
                        install.phase_app(ctx)
            self.assertEqual(len(commands), expected_commands)
            self.assertEqual(commands[0][:2], ['manage', 'shell'])
            self.assertIn(install.CREDENTIALS_CHECK, commands[0][-1])
            self.assertEqual(replace.called, loads)

    def test_installed_image_must_carry_this_revision(self):
        self.receipt('image', {'image_id': 'sha256:' + 'c' * 64})
        image = {'Id': 'sha256:' + 'c' * 64, 'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'app-image',
                                                                   install.REVISION_LABEL: OTHER}}}
        with mock.patch.object(install, 'inspect', return_value=image), self.assertRaises(install.InstallError):
            install.installed_image(self.ctx('app'))


class ServiceReplacementTests(TemporaryDirectoryTest):
    """A failed replacement removes what it started and restores exactly the parked pair (after closing the stages
    the new pair left open: tests/test_repairs_r1_m.py)."""

    def test_failed_worker_restores_previous_pair(self):
        names = {'cpt-studio-web': 'web', 'cpt-studio-worker': 'worker'}
        live = {name: {'Id': f'old-{role}', 'Image': 'old', 'State': {'Running': True},
                       'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role}}}
                for name, role in names.items()}
        calls = []

        def fake_inspect(kind, name):
            return live.get(name)

        def fake_docker(*args, **kwargs):
            calls.append(args[:3])
            if args[0] == 'rename':
                live[args[2]] = live.pop(args[1])
            elif args[0] == 'run':
                role = args[args.index('--name') + 1]
                live[role] = {'Id': f'new-{names[role]}', 'Image': 'new', 'State': {'Running': True},
                              'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: names[role]}}}
            elif args[0] == 'rm':
                for name, container in list(live.items()):
                    if container['Id'] == args[2]:
                        del live[name]
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def fake_wait(role, revision, image_id):
            if role == 'worker':
                raise install.InstallError('worker crashed')
            return {'id': f'new-{role}'}
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        with mock.patch.object(install, 'inspect', fake_inspect), mock.patch.object(install, 'docker', fake_docker), \
                mock.patch.object(install, 'wait_service', fake_wait), \
                mock.patch.object(install, 'close_undone_stages', return_value={'closed': 0}), \
                self.assertRaises(install.InstallError):
            install.replace_services(ctx, 'new', b'', 'disabled', '')
        self.assertEqual({name: container['Id'] for name, container in live.items()},
                         {'cpt-studio-web': 'old-web', 'cpt-studio-worker': 'old-worker'})
        self.assertIn(('start', 'cpt-studio-web'), calls)
        self.assertIn(('start', 'cpt-studio-worker'), calls)


class MainTests(TemporaryDirectoryTest):
    def test_outside_the_door_writes_a_failure_receipt_and_one_line(self):
        receipts = self.tmp / 'receipts'
        output = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch('sys.stdout', output):
            os.environ.pop('RULED_MUTATION_DECLARATION', None)
            os.environ.pop('RULED_MUTATION_DECL_COMMIT', None)
            code = install.main(['--phase', 'preflight', '--revision', REVISION, '--receipts', str(receipts)])
        self.assertEqual(code, 1)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        summary = json.loads(lines[0])
        self.assertFalse(summary['ok'])
        record = json.loads(Path(summary['receipt']).read_text())
        self.assertIn('run-ruled-mutation', record['error'])
        self.assertEqual(stat.S_IMODE(Path(summary['receipt']).stat().st_mode), 0o600)

    def test_one_phase_at_a_time_per_receipts_directory(self):
        import fcntl
        receipts = install.prepare_receipts(str(self.tmp / 'receipts'))
        holder = os.open(receipts / '.lock', os.O_WRONLY | os.O_CREAT, 0o600)
        fcntl.flock(holder, fcntl.LOCK_EX)
        output = io.StringIO()
        try:
            with mock.patch.object(install, 'check_door') as door, mock.patch('sys.stdout', output):
                code = install.main(['--phase', 'preflight', '--revision', REVISION, '--receipts', str(receipts)])
        finally:
            os.close(holder)
        self.assertEqual(code, 1)
        door.assert_not_called()
        self.assertIn('another phase', json.loads(output.getvalue())['error'])
        self.assertEqual(list(receipts.glob('*.json')), [])

    def test_an_unusable_receipts_path_is_one_json_line_not_a_traceback(self):
        for path in (self.tmp / 'missing-parent' / 'receipts', 'relative/receipts'):
            output = io.StringIO()
            with mock.patch('sys.stdout', output):
                code = install.main(['--phase', 'preflight', '--revision', REVISION, '--receipts', str(path)])
            self.assertEqual(code, 1)
            line = json.loads(output.getvalue())
            self.assertFalse(line['ok'])
            self.assertIn('--receipts unusable', line['error'])

    def test_unexpected_errors_are_recorded_not_raised(self):
        receipts = self.tmp / 'receipts'
        output = io.StringIO()
        with mock.patch.object(install, 'check_door', return_value={'declaration_commit': OTHER}), \
                mock.patch.object(install, 'check_tree', return_value={'mode': 'exact'}), \
                mock.patch.dict(install.PHASES, {'preflight': mock.Mock(side_effect=KeyError('boom'))}), \
                mock.patch('sys.stdout', output):
            code = install.main(['--phase', 'preflight', '--revision', REVISION, '--receipts', str(receipts)])
        self.assertEqual(code, 1)
        record = json.loads(Path(json.loads(output.getvalue())['receipt']).read_text())
        self.assertEqual(record['error'], 'unexpected KeyError; see failure log')
        self.assertTrue(Path(record['failure_log']).exists())


if __name__ == '__main__':
    unittest.main()
