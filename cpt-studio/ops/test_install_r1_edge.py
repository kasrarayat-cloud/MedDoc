"""Release 1's front door (RELEASE-1-SPEC A1-A4, B6): the HTTPS template's limits, its access log without query strings,
nothing spooled to disk, the TLS policy and both session cookie names; and gunicorn's access line (A2). No nginx is
needed: both templates are rendered with install.render() and read with install.nginx_statements() (and, where a
directive's block matters, test_install's block-aware reader), as the installer itself reads them.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_edge -v
"""
import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import guard_host, release_host, rendered, statements  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
UUID = '0f8fad5b-d9cb-469f-a165-70867728950e'
SIZES = {'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3}
# A1's starting numbers (owner decision D5): zone -> (key variable, zone size, rate, burst)
ZONES = {'cpt_all': ('$cpt_all_key', '10m', '30r/s', '120'), 'cpt_signin': ('$cpt_signin_key', '5m', '20r/m', '10'),
         'cpt_write': ('$cpt_write_key', '5m', '5r/s', '30'), 'cpt_upload': ('$cpt_upload_key', '5m', '10r/m', '10'),
         'cpt_export': ('$cpt_export_key', '5m', '6r/m', '6')}
CIPHERS = ('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:'
           'ECDHE-RSA-AES128-GCM-SHA256')
QUERY_VARIABLES = ('$request_uri', '$args', '$query_string', '$arg_', '$http_referer', '$is_args')


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def size(text):
    """An nginx size ('20m', '256k', '512') in bytes."""
    match = re.fullmatch(r'(\d+)([kmg]?)', text.lower())
    assert match, text
    return int(match[1]) * SIZES.get(match[2], 1)


def https_part(port=install.WEB_PORT):
    """The HTTPS stage beyond the HTTP stage it begins with: what release 1 adds and the 443 block."""
    confs = rendered(port)
    assert confs['https'].startswith(confs['http'])
    return confs['https'][len(confs['http']):]


def blocks_of(conf, *path):
    """Every directive (word list) whose enclosing blocks are exactly ``path``."""
    return [words for blocks, words in statements(conf) if blocks == path]


def directive(conf, name, *path):
    found = [words[1:] for words in blocks_of(conf, *path) if words[0] == name]
    assert len(found) == 1, (name, path, found)
    return found[0]


def maps(conf):
    """{variable: {'source', 'exact', 'regex', 'default'}} of every map block, read in order as nginx reads them (a
    block's own line - 'map <source> <variable>' - is the words before its opening brace)."""
    words_before, found, stack = [], {}, []
    for kind, value in install.nginx_tokens(conf):
        if kind == 'punct' and value == '{':
            if words_before[:1] == ['map']:
                variable = words_before[2]
                found[variable] = {'source': words_before[1], 'exact': {}, 'regex': [], 'default': None}
                stack.append(variable)
            else:
                stack.append(None)
            words_before = []
        elif kind == 'punct' and value == '}':
            stack.pop()
            words_before = []
        elif kind == 'punct':
            if stack and stack[-1] is not None and len(words_before) == 2:
                entry = found[stack[-1]]
                key, result = words_before
                if key == 'default':
                    entry['default'] = result
                elif key.startswith('~'):
                    entry['regex'].append((key[1:], result))
                else:
                    entry['exact'][key] = result
            words_before = []
        else:
            words_before.append(value)
    return found


def mapped(entry, value):
    """What nginx's map gives for ``value``: an exact key first, then each regular expression in order, else default."""
    if value in entry['exact']:
        return entry['exact'][value]
    for pattern, result in entry['regex']:
        if re.search(pattern, value):
            return result
    return entry['default']


def python_constant(path, name):
    """A module-level literal ``name`` of the application file ``path`` (read with ast; nothing is imported), the
    simple arithmetic of a size constant included."""
    for node in ast.parse((APP_ROOT / path).read_text(encoding='utf-8')).body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(getattr(target, 'id', None) == name for target in targets):
            return eval(compile(ast.Expression(node.value), path, 'eval'), {'__builtins__': {}})  # noqa: S307
    raise LookupError(f'{name} is not a module-level constant of {path}')


class FrontDoorLimitTests(unittest.TestCase):
    """A1: floods, slow connections and password guessing are refused at the edge."""

    def test_the_two_installer_rules_hold_one_proxy_pass_and_the_http_stage_first(self):
        for port in install.WEB_PORTS:
            confs = rendered(port)
            self.assertTrue(confs['https'].startswith(confs['http']), port)
            passes = [words for words in install.nginx_statements(confs['https']) if words[0] == 'proxy_pass']
            self.assertEqual(passes, [['proxy_pass', f'http://127.0.0.1:{port}']])
            self.assertEqual(install.proxied_port(confs['https']), port)
            for conf in confs.values():
                self.assertFalse([block for block in install.parse_server_blocks(conf) for args in block['listen']
                                  if {'default_server', 'default'} & set(args)])

    def test_every_limit_is_in_the_one_proxied_location(self):
        conf = rendered()['https']
        location = blocks_of(conf, 'server', 'location')
        limits = sorted(words[1:] for words in location if words[0] == 'limit_req')
        self.assertEqual(limits, sorted([f'zone={zone}', f'burst={burst}', 'nodelay']
                                        for zone, (_, _, _, burst) in ZONES.items()))
        self.assertEqual(sorted(words[1:] for words in location if words[0] == 'limit_conn'),
                         [['cpt_bytes_conn', '6'], ['cpt_conn', '40']])
        self.assertEqual(directive(conf, 'limit_req_status', 'server', 'location'), ['429'])
        self.assertEqual(directive(conf, 'limit_conn_status', 'server', 'location'), ['429'])
        pages = [words[1:] for words in location if words[0] == 'error_page']
        self.assertIn(['429', '=', '@cpt_too_many'], pages)
        # the 429 sentence comes from a named location, which is not a second upstream
        too_many = install.nginx_statements(conf[conf.index('location @cpt_too_many'):])
        self.assertEqual(too_many[:2], [['location', '@cpt_too_many'], ['default_type', 'text/plain']])
        self.assertEqual(too_many[2], ['return', '429', 'Too many requests. Wait a minute and try again.\\n'])
        self.assertNotIn('proxy_pass', [words[0] for words in too_many])

    def test_the_zones_and_their_starting_numbers(self):
        conf = rendered()['https']
        top = blocks_of(conf)
        zones = {words[2].split('=', 1)[1].split(':')[0]: words[1:] for words in top if words[0] == 'limit_req_zone'}
        self.assertEqual(sorted(zones), sorted(ZONES))
        for zone, (key, memory, rate, _) in ZONES.items():
            self.assertEqual(zones[zone], [key, f'zone={zone}:{memory}', f'rate={rate}'], zone)
        connections = sorted(words[1:] for words in top if words[0] == 'limit_conn_zone')
        self.assertEqual(connections, [['$binary_remote_addr', 'zone=cpt_conn:10m'],
                                       ['$cpt_bytes_key', 'zone=cpt_bytes_conn:5m']])
        # about 40 MB of shared memory on the shared nginx (the spec's figure), and no more
        total = sum(size(words[2].split(':')[1]) for words in top if words[0] in ('limit_req_zone', 'limit_conn_zone'))
        self.assertLessEqual(total, 45 * 2 ** 20)

    def test_the_host_itself_is_exempt_and_every_key_is_an_address_or_empty(self):
        conf = rendered()['https']
        geo = install.nginx_statements(conf[conf.index('geo $cpt_exempt'):conf.index('}', conf.index('geo $cpt_exempt'))])
        self.assertEqual(geo[0], ['geo', '$cpt_exempt'])
        self.assertEqual(sorted(words for words in geo[1:]),
                         sorted([['default', '0'], ['127.0.0.1', '1'], ['::1', '1'], [install.PUBLIC_IPV4, '1']]))
        found = maps(conf)
        self.assertEqual(sorted(found), sorted(['$cpt_all_key', '$cpt_signin_key', '$cpt_write_key', '$cpt_upload_key',
                                                '$cpt_export_key', '$cpt_bytes_key']))
        for variable, entry in found.items():
            self.assertEqual(entry['source'], '$cpt_exempt:$request_method $uri', variable)
            self.assertEqual(entry['default'], '', variable)
            values = set(entry['exact'].values()) | {result for _, result in entry['regex']}
            self.assertEqual(values, {'$binary_remote_addr'}, variable)

    def test_each_key_counts_exactly_its_requests(self):
        found = maps(rendered()['https'])
        counted = {
            '$cpt_all_key': ['0:GET /', '0:POST /login/', '0:GET /static/studio/app.js', '0:HEAD /health/'],
            '$cpt_signin_key': ['0:POST /login/'],
            '$cpt_write_key': ['0:POST /api/encounters', f'0:POST /api/encounters/{UUID}/decisions', '0:POST /ops/people/add',
                               f'0:POST /ops/encounters/{UUID}/content'],
            '$cpt_upload_key': ['0:POST /api/encounters'],
            '$cpt_export_key': [f'0:POST /api/encounters/{UUID}/reports'],
            '$cpt_bytes_key': [f'0:GET /api/encounters/{UUID}/original', f'0:HEAD /api/encounters/{UUID}/original',
                               f'0:GET /api/reports/{UUID}/download', f'0:GET /api/encounters/{UUID}/bundle',
                               f'0:GET /ops/encounters/{UUID}/original'],
        }
        not_counted = {
            '$cpt_all_key': ['1:GET /', '1:POST /login/'],
            '$cpt_signin_key': ['1:POST /login/', '0:GET /login/', '0:POST /login/second-factor', '0:POST /api/session'],
            '$cpt_write_key': ['1:POST /api/encounters', '0:GET /api/encounters', '0:POST /login/', '0:POST /apix/'],
            '$cpt_upload_key': ['1:POST /api/encounters', '0:GET /api/encounters', f'0:POST /api/encounters/{UUID}/answers',
                                '0:POST /api/encounters/'],
            '$cpt_export_key': [f'1:POST /api/encounters/{UUID}/reports', f'0:GET /api/encounters/{UUID}/reports',
                                f'0:POST /api/encounters/{UUID}/reports/x', '0:POST /api/encounters/x y/reports'],
            '$cpt_bytes_key': [f'1:GET /api/encounters/{UUID}/original', f'0:GET /api/encounters/{UUID}',
                               f'0:GET /api/encounters/{UUID}/original/x', '0:GET /api/encounters/ZZ;x/original',
                               f'0:GET /ops/encounters/{UUID}/content'],
        }
        for variable, values in counted.items():
            for value in values:
                with self.subTest(variable=variable, value=value):
                    self.assertEqual(mapped(found[variable], value), '$binary_remote_addr')
        for variable, values in not_counted.items():
            for value in values:
                with self.subTest(variable=variable, value=value, counted=False):
                    self.assertEqual(mapped(found[variable], value), '')

    def test_slow_clients_and_slow_upstreams_are_cut_off(self):
        conf = rendered()['https']
        for name, value in (('client_header_timeout', '15s'), ('client_body_timeout', '15s'), ('send_timeout', '60s'),
                            ('reset_timedout_connection', 'on')):
            self.assertEqual(directive(conf, name, 'server'), [value], name)
        for name in ('proxy_read_timeout', 'proxy_send_timeout'):
            self.assertEqual(directive(conf, name, 'server', 'location'), ['60s'], name)
        self.assertEqual(directive(conf, 'proxy_connect_timeout', 'server', 'location'), ['10s'])
        # gunicorn's own request timeout is unchanged: the drain after a switch is sized against it
        self.assertIn('timeout = 120\n', (APP_ROOT / 'deploy' / 'gunicorn.conf.py').read_text())
        self.assertGreater(install.DRAIN_MIN_SECONDS, 120)

    def test_every_name_this_file_defines_is_cpt_prefixed(self):
        conf = rendered()['https']
        top = blocks_of(conf)
        defined = []
        for words in top:
            if words[0] in ('geo', 'map'):
                defined.append(words[-1].lstrip('$'))
            elif words[0] in ('limit_req_zone', 'limit_conn_zone'):
                defined.append(next(word for word in words if word.startswith('zone='))[5:].split(':')[0])
            elif words[0] == 'log_format':
                defined.append(words[1])
        # a block's own line (geo, map) is not a statement of the reader: those names are read from the text
        defined += re.findall(r'^(?:geo|map) [^\n{]*?\$(\w+) \{$', conf, re.M)
        defined += re.findall(r'location @(\w+)', conf)
        self.assertGreaterEqual(len(defined), 6 + 7 + 1 + 2)
        for name in defined:
            self.assertTrue(name.startswith('cpt_'), name)
        variables = set(re.findall(r'\$(cpt\w*)', conf))
        self.assertEqual(variables, {'cpt_exempt', 'cpt_all_key', 'cpt_signin_key', 'cpt_write_key', 'cpt_upload_key',
                                     'cpt_export_key', 'cpt_bytes_key'})


class EdgeLogTests(unittest.TestCase):
    """A2: an access log at the edge, and gunicorn's, without query strings; the request id and the session reference."""

    def test_the_log_format_has_the_path_but_never_its_query_string(self):
        conf = rendered()['https']
        formats = [words for words in blocks_of(conf) if words[0] == 'log_format']
        self.assertEqual(len(formats), 1)
        name, *parts = formats[0][1:]
        self.assertEqual(name, 'cpt_studio')
        text = ' '.join(parts)
        for variable in QUERY_VARIABLES:
            self.assertNotIn(variable, text)
        for needed in ('$uri', '$request_id', '$upstream_http_x_cpt_actor', '$status', '$remote_addr',
                       '$ssl_server_name', '$host', '$limit_req_status'):
            self.assertIn(needed, text)

    def test_no_query_string_reaches_a_key_a_map_or_a_log_line(self):
        # the HTTP stage's redirect alone keeps $request_uri: it is the byte-identical stage every renewal reads
        for port in install.WEB_PORTS:
            text = ' '.join(' '.join(words) for words in install.nginx_statements(https_part(port)))
            for variable in QUERY_VARIABLES:
                self.assertNotIn(variable, text, (port, variable))
        self.assertIn('$request_uri', rendered()['http'])

    def test_the_443_block_logs_to_its_own_files_and_the_80_block_stays_off(self):
        server_logs = [words[1:] for blocks, words in statements(https_part()) if blocks == ('server',)
                       and words[0] in ('access_log', 'error_log')]
        self.assertEqual(server_logs, [['/var/log/nginx/cpt-studio-access.log', 'cpt_studio'],
                                       ['/var/log/nginx/cpt-studio-error.log', 'warn']])
        http_logs = [words[1:] for blocks, words in statements(rendered()['http']) if words[0] == 'access_log']
        self.assertEqual(http_logs, [['off']])

    def test_the_request_id_goes_upstream_and_the_actor_never_reaches_the_browser(self):
        conf = rendered()['https']
        location = blocks_of(conf, 'server', 'location')
        set_headers = {words[1]: words[2:] for words in location if words[0] == 'proxy_set_header'}
        self.assertEqual(set_headers['X-Request-ID'], ['$request_id'])
        hidden = [words[1] for words in location if words[0] == 'proxy_hide_header']
        self.assertIn('X-CPT-Actor', hidden)

    def test_gunicorn_logs_the_path_the_request_id_and_the_actor_and_no_query_field(self):
        namespace = {}
        exec(compile((APP_ROOT / 'deploy' / 'gunicorn.conf.py').read_text(), 'gunicorn.conf.py', 'exec'), namespace)  # noqa: S102
        line = namespace['access_log_format']
        for needed in ('%(U)s', '%({x-request-id}i)s', '%({x-cpt-actor}o)s', '%({x-forwarded-for}i)s'):
            self.assertIn(needed, line)
        # %(r)s is the request line with its query string, %(q)s the query string, %(f)s and {referer}i the Referer
        for refused in ('%(r)s', '%(q)s', '%(f)s', '{referer}i', '{referrer}i'):
            self.assertNotIn(refused, line)
        self.assertEqual(namespace['accesslog'], '-')


class NothingOnDiskTests(unittest.TestCase):
    """A3: no request body and no response is written to nginx's temporary directories."""

    def test_a_request_body_stays_in_memory_up_to_the_largest_one_accepted(self):
        conf = rendered()['https']
        body = size(directive(conf, 'client_body_buffer_size', 'server')[0])
        largest = size(directive(conf, 'client_max_body_size', 'server')[0])
        self.assertEqual(body, largest)
        self.assertEqual(largest, 20 * 2 ** 20)

    def test_a_response_stays_in_memory_and_a_larger_one_is_relayed_without_a_file(self):
        conf = rendered()['https']
        self.assertEqual(directive(conf, 'proxy_buffering', 'server', 'location'), ['on'])
        self.assertEqual(directive(conf, 'proxy_max_temp_file_size', 'server', 'location'), ['0'])
        count, each = directive(conf, 'proxy_buffers', 'server', 'location')
        held = int(count) * size(each)
        self.assertGreaterEqual(held, 24 * 2 ** 20)
        busy = size(directive(conf, 'proxy_busy_buffers_size', 'server', 'location')[0])
        self.assertLess(busy, held - size(each))  # nginx -t refuses a busy size that is not below the rest
        self.assertGreaterEqual(busy, size(each))
        # the largest file the application serves fits in memory: an original (MAX_UPLOAD_BYTES) and a bundle
        # (BUNDLE_MAX_BYTES) as settings.py gives them, and a converted PDF (MAX_PDF_BYTES) as the conversion code does
        self.assertLessEqual(python_constant('cptstudio/settings.py', 'MAX_UPLOAD_BYTES'), held)
        self.assertLessEqual(python_constant('cptstudio/settings.py', 'BUNDLE_MAX_BYTES'), held)
        pdf = [path for path in ('studio/fable/document.py', 'studio/fable/docx_package.py')
               if (APP_ROOT / path).exists() and 'MAX_PDF_BYTES = ' in (APP_ROOT / path).read_text()]
        self.assertTrue(pdf)
        self.assertLessEqual(python_constant(pdf[0], 'MAX_PDF_BYTES'), held)


class TlsPolicyTemplateTests(unittest.TestCase):
    """A4: the cipher list and a hidden server version, on CPT's 443 block."""

    def test_aes_gcm_suites_only_and_no_server_version(self):
        conf = rendered()['https']
        self.assertEqual(directive(conf, 'ssl_protocols', 'server'), ['TLSv1.2', 'TLSv1.3'])
        self.assertEqual(directive(conf, 'ssl_ciphers', 'server'), [CIPHERS])
        for suite in CIPHERS.split(':'):
            self.assertRegex(suite, r'^ECDHE-(ECDSA|RSA)-AES(128|256)-GCM-SHA(256|384)$')
        self.assertEqual(directive(conf, 'ssl_conf_command', 'server'),
                         ['Ciphersuites', 'TLS_AES_256_GCM_SHA384:TLS_AES_128_GCM_SHA256'])
        self.assertEqual(directive(conf, 'ssl_prefer_server_ciphers', 'server'), ['on'])
        self.assertEqual(directive(conf, 'ssl_session_tickets', 'server'), ['off'])
        self.assertEqual(directive(conf, 'server_tokens', 'server'), ['off'])
        offered = ' '.join(directive(conf, 'ssl_ciphers', 'server') + directive(conf, 'ssl_conf_command', 'server'))
        self.assertNotRegex(offered, r'(?i)chacha|camellia|aria|cbc|sha1\b|rsa-aes\d+-sha\b|!|\+|@seclevel')


class CookieNameTests(unittest.TestCase):
    """B6: the vhost is published before the switch, so it gives both session cookie names their flags."""

    def test_both_session_cookie_names_are_http_only_and_the_csrf_cookie_stays_readable(self):
        flags = [words[1:] for words in blocks_of(rendered()['https'], 'server', 'location')
                 if words[0] == 'proxy_cookie_flags']
        self.assertEqual(flags, [['cptstudio_session', 'secure', 'httponly', 'samesite=strict'],
                                 ['__Host-cptstudio_session', 'secure', 'httponly', 'samesite=strict'],
                                 ['~', 'secure', 'samesite=strict']])  # the catch-all last: nginx applies the first match


if __name__ == '__main__':
    unittest.main()
