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
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install  # noqa: E402
from test_install import guard_host, release_host, rendered, statements  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
UUID = '0f8fad5b-d9cb-469f-a165-70867728950e'
SIZES = {'k': 1024, 'm': 1024 ** 2, 'g': 1024 ** 3}
# A1's starting numbers (owner decision D5), the sign-in and the upload sized for an office behind one address
# (refutation, edge lens C-12, C-13): zone -> (key variable, zone size, rate, burst)
ZONES = {'cpt_all': ('$cpt_all_key', '10m', '30r/s', '120'), 'cpt_signin': ('$cpt_signin_key', '5m', '60r/m', '40'),
         'cpt_write': ('$cpt_write_key', '2m', '5r/s', '30'), 'cpt_upload': ('$cpt_upload_key', '2m', '60r/m', '60'),
         'cpt_export': ('$cpt_export_key', '2m', '6r/m', '6')}
# the connection limits: zone -> (key variable, zone size, at once)
CONNECTIONS = {'cpt_conn': ('$cpt_conn_key', '5m', '40'), 'cpt_bytes_conn': ('$cpt_bytes_key', '2m', '20'),
               'cpt_bytes_all': ('$cpt_bytes_all_key', '1m', '24'),
               'cpt_large_body': ('$cpt_large_body_key', '2m', '4'),
               'cpt_large_body_all': ('$cpt_large_body_all_key', '1m', '40'),
               'cpt_small_body': ('$cpt_small_body_key', '5m', '40')}
# Each location's body size (refutation, edge lens C-15's follow-up): the upload, a coding review's answers, the rest
BODY_SIZES = {('=', '/api/encounters'): '20m', ('~', '^/api/encounters/[0-9a-f-]+/answers$'): '1m', ('/',): '64k'}
REQUEST_KEYS = ('$cpt_all_key', '$cpt_signin_key', '$cpt_write_key', '$cpt_upload_key', '$cpt_export_key',
                '$cpt_bytes_key')
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


def locations(conf):
    """{the location's arguments (a tuple): its directives (word lists)} of the 443 block's locations, read in order -
    every location here holds plain directives only."""
    found, current, words = {}, None, []
    for kind, value in install.nginx_tokens(conf[conf.index('listen 443'):]):
        if kind == 'punct' and value == '{':
            if words[:1] == ['location']:
                current = tuple(words[1:])
                found[current] = []
            words = []
        elif kind == 'punct' and value == '}':
            current, words = None, []
        elif kind == 'punct':
            if current is not None and words:
                found[current].append(words)
            words = []
        else:
            words.append(value)
    return found


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


def chosen_location(found, uri):
    """The location nginx chooses for ``uri`` among ``found`` (locations()): an exact match, else the first regular
    expression that matches, in order, else the longest prefix (none here is ^~)."""
    exact = [where for where in found if where[0] == '=' and where[1] == uri]
    if exact:
        return exact[0]
    for where in found:
        if where[0] in ('~', '~*') and re.search(where[1], uri, re.I if where[0] == '~*' else 0):
            return where
    prefixes = [where for where in found if len(where) == 1 and not where[0].startswith('@') and uri.startswith(where[0])]
    return max(prefixes, key=lambda where: len(where[0]))


def class_constant(path, cls, name):
    """A class-level literal ``name`` of class ``cls`` in the application file ``path`` (read with ast)."""
    for node in ast.walk(ast.parse((APP_ROOT / path).read_text(encoding='utf-8'))):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.Assign) and any(getattr(t, 'id', None) == name for t in item.targets):
                    return ast.literal_eval(item.value)
    raise LookupError(f'{cls}.{name} is not a class-level constant of {path}')


def mapped(entry, value):
    """What nginx's map gives for ``value``: an exact key first, then each regular expression in order, else default -
    a regular expression's positional captures ($1 ...) put into its value, as nginx puts them."""
    if value in entry['exact']:
        return entry['exact'][value]
    for pattern, result in entry['regex']:
        match = re.search(pattern, value)
        if match:
            return re.sub(r'\$(\d)', lambda m: match.group(int(m.group(1))) or '', result)
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
        location = locations(conf)[('@cpt_proxy',)]
        limits = sorted(words[1:] for words in location if words[0] == 'limit_req')
        self.assertEqual(limits, sorted([f'zone={zone}', f'burst={burst}', 'nodelay']
                                        for zone, (_, _, _, burst) in ZONES.items()))
        self.assertEqual(sorted(words[1:] for words in location if words[0] == 'limit_conn'),
                         sorted([zone, at_once] for zone, (_, _, at_once) in CONNECTIONS.items()))
        self.assertEqual([words[1:] for words in location if words[0] == 'limit_req_status'], [['429']])
        self.assertEqual([words[1:] for words in location if words[0] == 'limit_conn_status'], [['429']])
        self.assertEqual([words for words in location if words[0] == 'proxy_pass'],
                         [['proxy_pass', f'http://127.0.0.1:{install.WEB_PORT}']])
        # and nowhere else: a path location only gives its body size and hands on to this one
        everywhere = [words for words in install.nginx_statements(conf) if words[0].startswith('limit_')
                      and words[0] not in ('limit_req_zone', 'limit_conn_zone')]
        self.assertEqual(len(everywhere), len([words for words in location if words[0].startswith('limit_')]))
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
        self.assertEqual(connections, sorted([key, f'zone={zone}:{memory}']
                                             for zone, (key, memory, _) in CONNECTIONS.items()))
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
        self.assertEqual(sorted(found), sorted([*REQUEST_KEYS, '$cpt_client', '$cpt_conn_key', '$cpt_body_size',
                                                '$cpt_large_body_key', '$cpt_small_body_key', '$cpt_large_body_all_key',
                                                '$cpt_bytes_all_key', '$cpt_unsized_body']))
        for variable in REQUEST_KEYS:
            entry = found[variable]
            self.assertEqual(entry['source'], '$cpt_exempt:$request_method $uri', variable)
            self.assertEqual(entry['default'], '', variable)
            values = set(entry['exact'].values()) | {result for _, result in entry['regex']}
            self.assertEqual(values, {'$cpt_client'}, variable)  # the client: its address, or its IPv6 /64
        # the connection keys: the client too, never counted for this host itself, and never empty when they count
        self.assertEqual((found['$cpt_conn_key']['source'], found['$cpt_conn_key']['exact'],
                          found['$cpt_conn_key']['default']), ('$cpt_exempt', {'0': '$cpt_client'}, ''))
        self.assertEqual((found['$cpt_client']['default'], mapped(found['$cpt_client'], '203.0.113.9')),
                         ('$remote_addr', '$remote_addr'))

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
                    self.assertEqual(mapped(found[variable], value), '$cpt_client')
        for variable, values in not_counted.items():
            for value in values:
                with self.subTest(variable=variable, value=value, counted=False):
                    self.assertEqual(mapped(found[variable], value), '')

    def test_an_ipv6_client_is_counted_by_its_64_and_an_ipv4_one_by_its_address(self):
        # refutation, edge lens C-15: limits keyed per IPv6 /128 left a /64 unbounded. Every RFC 5952 form nginx writes
        # ($remote_addr), with the :: run at each place it can fall, gives its first four groups.
        import ipaddress
        import random
        client = maps(rendered()['https'])['$cpt_client']
        rng, seen = random.Random(20261124), set()
        for _ in range(4000):
            groups = [rng.choice((0, 0, 0, rng.randrange(1, 0x10000))) for _ in range(8)]
            address = ipaddress.IPv6Address(':'.join(f'{group:x}' for group in groups))
            if address.ipv4_mapped is not None:
                continue
            text = address.compressed
            expected = ':'.join(f'{group:x}' for group in groups[:4])
            with self.subTest(address=text):
                self.assertEqual(mapped(client, text), expected)
            seen.add(text.count('::') and text.index('::'))
        self.assertGreater(len(seen), 6)  # the run fell at many places
        for text, expected in (('2001:db8::1', '2001:db8:0:0'), ('::1', '0:0:0:0'), ('::', '0:0:0:0'),
                               ('fe80::1:2:3:4:5', 'fe80:0:0:1'), ('::1:2:3:4:5:6', '0:0:1:2'),
                               ('2001:db8:85a3:8d3:1319:8a2e:370:7348', '2001:db8:85a3:8d3'),
                               ('2001:db8:1:2::', '2001:db8:1:2'), ('::ffff:192.0.2.7', '192.0.2.7'),
                               ('192.0.2.7', '$remote_addr')):
            with self.subTest(address=text):
                self.assertEqual(mapped(client, text), expected)
        # one /64 is one key, whatever its interface ids
        self.assertEqual({mapped(client, ipaddress.IPv6Address(f'2001:db8:1:2:{n:x}::{n:x}').compressed)
                          for n in range(1, 500)}, {'2001:db8:1:2'})

    def test_a_request_that_declares_a_body_is_bounded_per_client_and_large_ones_in_all(self):
        # refutation, edge lens C-15: a body buffer is reserved at the declared length (20 MiB for a slow sender); and
        # its follow-up: a body over the small locations' limit - which only the upload and the answers can declare -
        # takes the global cap, and every other body counts per client alone, so no trickle of uploads stops a sign-in
        conf = rendered()['https']
        found = maps(conf)
        body_size, large, small = found['$cpt_body_size'], found['$cpt_large_body_key'], found['$cpt_small_body_key']
        every = found['$cpt_large_body_all_key']
        self.assertEqual(body_size['source'], '$content_length')
        self.assertEqual((large['source'], small['source']), ('$cpt_exempt:$cpt_body_size',) * 2)
        limit = size(BODY_SIZES[('/',)])  # 64 KiB: the small locations' limit

        def counted(exempt, length):
            kind = mapped(body_size, length)
            return mapped(large, f'{exempt}:{kind}'), mapped(small, f'{exempt}:{kind}')
        import random
        draw = random.Random(20261124)
        lengths = sorted({*range(0, 12), *range(limit - 300, limit + 300), *range(65000, 100100, 7),
                          *range(99990, 100010), *(10 ** n + d for n in range(5, 10) for d in (-1, 0, 1)),
                          *(draw.randrange(1, 2 ** 31) for _ in range(300)), 20 * 2 ** 20, 2 ** 40})
        for length in lengths:
            # a declared length may carry leading zeros - nginx reads past them - so the class does too (follow-up)
            for written in (str(length), '0' + str(length), '000' + str(length)):
                want = ('$cpt_client', '') if length > limit else ('', '$cpt_client') if length else ('', '')
                self.assertEqual(counted('0', written), want, written)
                self.assertEqual(counted('1', written), ('', ''), written)  # the host itself is exempt
        self.assertEqual(counted('0', ''), ('', ''))  # no length declared: cut off at 64 KiB, and cpt_conn counts it
        self.assertEqual((mapped(every, '2001:db8:1:2'), mapped(every, '')), ('cpt', ''))
        self.assertNotIn('$cpt_small_body_all_key', found)  # no global cap on the small bodies
        location = locations(conf)[('@cpt_proxy',)]
        limits = {words[1]: int(words[2]) for words in location if words[0] == 'limit_conn'}
        largest = max(size(body) for body in BODY_SIZES.values())
        self.assertLessEqual(limits['cpt_large_body_all'] * largest, 800 * 2 ** 20)  # the bound the edge lens asked for
        self.assertEqual(limits['cpt_large_body'], 4)
        # a small body: never fewer at once per client than the sign-in burst lets through (C-13), and under 2.5 MiB a
        # client, with no global cap
        self.assertGreaterEqual(limits['cpt_small_body'], int(ZONES['cpt_signin'][3]))
        self.assertLessEqual(limits['cpt_small_body'] * limit, 2.5 * 2 ** 20)
        self.assertNotIn('cpt_small_body_all', limits)
        # a body with no declared length is cut off at the proxied location's limit - the server's, as it sets none -
        # and counts in cpt_conn: under 2.5 MiB a client too
        self.assertEqual(directive(conf, 'client_max_body_size', 'server'), ['64k'])
        self.assertNotIn('client_max_body_size', [words[0] for words in location])
        self.assertLessEqual(limits['cpt_conn'] * size(directive(conf, 'client_max_body_size', 'server')[0]),
                             2.5 * 2 ** 20)
        bytes_all = found['$cpt_bytes_all_key']
        self.assertEqual((mapped(bytes_all, '203.0.113.9'), mapped(bytes_all, '')), ('cpt', ''))
        buffers = [words[1:] for words in location if words[0] == 'proxy_buffers'][0]
        response = int(buffers[0]) * size(buffers[1])
        self.assertLessEqual(limits['cpt_bytes_all'] * response, 600 * 2 ** 20)
        self.assertEqual(limits['cpt_bytes_conn'], 20)
        self.assertEqual(directive(conf, 'client_body_timeout', 'server'), ['15s'])

    def test_a_body_of_unknown_length_is_refused_with_411(self):
        # refutation, edge lens C-16: chunked, or an HTTP/2 stream with no content-length, spooled past 20 MiB
        conf = rendered()['https']
        unsized = maps(conf)['$cpt_unsized_body']
        self.assertEqual(unsized['source'], '$request_method:$content_length:$http_transfer_encoding')
        for value, refused in (('POST::chunked', True), ('GET::chunked', True), ('POST:12:chunked', True),
                               ('POST::', True), ('PUT::', True), ('PATCH::', True), ('POST:0:', False),
                               ('POST:2048:', False), ('GET::', False), ('HEAD::', False), ('DELETE::', False)):
            with self.subTest(value=value):
                self.assertEqual(mapped(unsized, value), '1' if refused else '0')
        self.assertEqual(conf.count('if ($cpt_unsized_body) { return 411; }'), 1)
        # in the 443 block, before its one proxied location, so no body is read first
        start = conf.index('listen 443')
        self.assertLess(start, conf.index('if ($cpt_unsized_body) { return 411; }'))
        self.assertLess(conf.index('if ($cpt_unsized_body) { return 411; }'), conf.index('    location / {', start))

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
        self.assertEqual(variables, {'cpt_exempt', 'cpt_client', 'cpt_all_key', 'cpt_signin_key', 'cpt_write_key',
                                     'cpt_upload_key', 'cpt_export_key', 'cpt_bytes_key', 'cpt_conn_key',
                                     'cpt_body_size', 'cpt_large_body_key', 'cpt_small_body_key',
                                     'cpt_large_body_all_key', 'cpt_bytes_all_key', 'cpt_unsized_body'})


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
        found = locations(conf)
        sizes = [size(words[1]) for directives in found.values() for words in directives
                 if words[0] == 'client_max_body_size']
        largest = max([*sizes, size(directive(conf, 'client_max_body_size', 'server')[0])])
        self.assertEqual(body, largest)
        self.assertEqual(largest, 20 * 2 ** 20)
        # the one proxied location, where the body is read, keeps the server's buffer
        self.assertNotIn('client_body_buffer_size', [words[0] for words in found[('@cpt_proxy',)]])

    def test_each_location_takes_the_body_its_routes_need_and_hands_on_to_the_one_proxied_location(self):
        # refutation, edge lens C-15's follow-up: a sign-in declaring 20 MiB held a 20 MiB buffer; now every route but
        # the upload and the answers takes 64k, checked against the declared length as the location is chosen
        conf = rendered()['https']
        found = locations(conf)
        self.assertEqual(sorted(found), sorted([*BODY_SIZES, ('@cpt_proxy',), ('@cpt_unavailable',),
                                                ('@cpt_too_many',)]))
        for where, body in BODY_SIZES.items():
            with self.subTest(location=where):
                self.assertEqual(found[where], [['client_max_body_size', body], ['error_page', '418', '=', '@cpt_proxy'],
                                                ['return', '418']])
        self.assertEqual(directive(conf, 'client_max_body_size', 'server'), ['64k'])
        self.assertEqual(directive(conf, 'recursive_error_pages', 'server'), ['on'])  # @cpt_proxy's own error pages
        # the routes each location takes, as nginx chooses among the template's own locations
        for uri, body in (('/api/encounters', '20m'), (f'/api/encounters/{UUID}/answers', '1m'), ('/login/', '64k'),
                          ('/login/second-factor', '64k'), ('/login/enrol', '64k'), ('/account/', '64k'),
                          (f'/api/encounters/{UUID}/decisions', '64k'), (f'/api/members/{UUID}/access', '64k'),
                          ('/ops/people/add', '64k'), (f'/ops/encounters/{UUID}/reconcile', '64k'),
                          ('/session/activity', '64k'), ('/api/encounters/', '64k'), ('/API/encounters', '64k'),
                          (f'/api/encounters/{UUID}/answers/x', '64k'), (f'/api/encounters/{UUID.upper()}/answers', '64k')):
            with self.subTest(uri=uri):
                self.assertEqual(found[chosen_location(found, uri)][0], ['client_max_body_size', body])
        # only the upload and the answers can declare more than the small limit, so only they take the global cap
        body_size = maps(conf)['$cpt_body_size']
        for where, body in BODY_SIZES.items():
            self.assertEqual(mapped(body_size, str(size(body))), 'large' if size(body) > size('64k') else 'small')
        # the largest bodies the application accepts, as a browser writes them, fit with margin: 6 bytes a character
        # at most in JSON (a control character as \u00XX), 12 in a form (a 4-byte character percent-encoded)
        import json
        from urllib.parse import urlencode
        answer_chars = class_constant('studio/models.py', 'CodingAnswer', 'MAX_CHARS')
        answers = json.dumps({'answers': [{'question_id': UUID, 'text': '\x01' * answer_chars}
                                          for _ in range(python_constant('studio/decisions.py', 'MAX_ANSWERS'))]},
                             ensure_ascii=False).encode()
        self.assertLess(len(answers), size('1m'))
        self.assertLess(len(answers.replace(b'\\u0001', '\U0001f600'.encode())) * 2, size('1m'))  # 4-byte characters
        note_chars = python_constant('studio/decisions.py', 'MAX_NOTE_CHARS')
        decision = json.dumps({'round': 99, 'line': 'L12', 'code': '99999', 'action': 'approve',
                               'acknowledgement': '\x01' * note_chars, 'note': '\x01' * note_chars, 'decision': UUID},
                              ensure_ascii=False).encode()
        self.assertLess(len(decision) * 2, size('64k'))
        for name in ('MAX_NOTE_CHARS', 'MAX_REASON_CHARS'):
            form = urlencode({'csrfmiddlewaretoken': 'x' * 64, 'run': UUID,
                              'note': '\U0001f600' * python_constant('studio/operator.py', name)}).encode()
            self.assertLess(len(form) * 2, size('64k'), name)

    def test_install_md_says_what_still_waits_on_slow_senders_and_that_sign_ins_never_do(self):
        # the edge lens's C-15 follow-up: the known limit names what remains, and what no longer does
        text = ' '.join((APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8').split())
        for sentence in ('the upload 20 MiB, a coding review\'s answers 1 MiB, every other request 64 KiB',
                         'A larger declared length is refused with 413 before any of it is read.',
                         'at most 40 such bodies are read at once in all - under 800 MiB however many clients send',
                         'A body of 64 KiB or less counts per client only, 40 at once: under 2.5 MiB a client, with no '
                         'global cap.',
                         'is cut off at 64 KiB read',
                         'So uploads and answers can still be held up by slow trickles from ten or more clients',
                         'sign-ins cannot, nor can any other request: a body of 64 KiB or less never takes one of those '
                         '40.'):
            self.assertIn(sentence, text)
        self.assertNotIn('sign-ins and uploads then get 429', text)

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

    def test_the_template_and_install_md_say_what_holds_on_the_shared_listener(self):
        # refutation, edge lens C-17: on a non-default server ssl_protocols, the TLS 1.3 Ciphersuites and
        # ssl_prefer_server_ciphers take no effect after SNI - TLS 1.3 ChaCha20 is accepted - so "AES-GCM only" was untrue
        conf = rendered()['https']
        comment = ' '.join(line.lstrip('# ').strip() for line in conf[conf.index('# A4:'):].splitlines()[:9])
        self.assertNotIn('AES-GCM suites only', conf)
        for said in ('not this shared listener\'s default server', 'ssl_protocols, the TLS 1.3 Ciphersuites and '
                     'ssl_prefer_server_ciphers stay the default server\'s', 'TLS 1.3 ChaCha20 is accepted', 'D27'):
            self.assertIn(said, comment)
        limits = ' '.join((APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8').split())
        self.assertIn('so TLS 1.3 ChaCha20 is accepted', limits)
        self.assertIn('a suite outside the policy is a finding, never an undo (D27)', limits)


class CookieNameTests(unittest.TestCase):
    """B6: the vhost is published before the switch, so it gives both session cookie names their flags."""

    def test_both_session_cookie_names_are_http_only_and_the_csrf_cookie_stays_readable(self):
        flags = [words[1:] for words in blocks_of(rendered()['https'], 'server', 'location')
                 if words[0] == 'proxy_cookie_flags']
        self.assertEqual(flags, [['cptstudio_session', 'secure', 'httponly', 'samesite=strict'],
                                 ['__Host-cptstudio_session', 'secure', 'httponly', 'samesite=strict'],
                                 ['~', 'secure', 'samesite=strict']])  # the catch-all last: nginx applies the first match



# Recorded shapes of `openssl s_client` (OpenSSL 3.x) - synthetic transcripts, no host was probed.
ACCEPTED_12 = b"""CONNECTED(00000003)
---
Certificate chain
 0 s:CN = cpt.quillmd.com
---
New, TLSv1.2, Cipher is ECDHE-ECDSA-AES256-GCM-SHA384
Server public key is 256 bit
SSL-Session:
    Protocol  : TLSv1.2
    Cipher    : ECDHE-ECDSA-AES256-GCM-SHA384
---
DONE
"""
ACCEPTED_13 = b"""CONNECTED(00000003)
---
New, TLSv1.3, Cipher is TLS_AES_256_GCM_SHA384
Server public key is 256 bit
---
DONE
"""
ACCEPTED_CBC = b"""CONNECTED(00000003)
New, TLSv1.2, Cipher is ECDHE-ECDSA-AES128-SHA
    Cipher    : ECDHE-ECDSA-AES128-SHA
"""
REFUSED_CIPHER = b"""CONNECTED(00000003)
40A7C0B5A47F0000:error:0A000410:SSL routines:ssl3_read_bytes:sslv3 alert handshake failure:../ssl/record/rec_layer_s3.c:1584:SSL alert number 40
---
no peer certificate available
---
New, (NONE), Cipher is (NONE)
Secure Renegotiation IS NOT supported
"""
REFUSED_VERSION = b"""CONNECTED(00000003)
40A7C0B5A47F0000:error:0A00042E:SSL routines:ssl3_read_bytes:tlsv1 alert protocol version:../ssl/record/rec_layer_s3.c:1584:SSL alert number 70
New, (NONE), Cipher is (NONE)
"""
CLIENT_NO_CIPHERS = b"""CONNECTED(00000003)
40D7B1F6E37F0000:error:0A0000B5:SSL routines:ssl_cipher_list_to_bytes:no ciphers available:../ssl/statem/statem_clnt.c:3889:No ciphers enabled for max supported SSL/TLS version
---
New, (NONE), Cipher is (NONE)
"""
CLIENT_NO_PROTOCOLS = b"""CONNECTED(00000003)
40E7B1F6E37F0000:error:0A0000BF:SSL routines:tls_setup_handshake:no protocols available:../ssl/statem/statem_lib.c:104:
New, (NONE), Cipher is (NONE)
"""
REFUSED_BUT_CLIENT_SAID_NO_CIPHERS = REFUSED_CIPHER + b"40D7:error:0A0000B5:SSL routines::no ciphers available\n"


class TlsProbeTests(unittest.TestCase):
    """A4: the probe parser on recorded openssl outputs - a refusal counts only when the SERVER sent it."""

    def test_accepted_refused_and_client_side_shapes(self):
        verdict = install.tls_probe_verdict
        self.assertEqual(verdict(0, ACCEPTED_12), {'verdict': 'accepted', 'protocol': 'TLSv1.2',
                                                   'cipher': 'ECDHE-ECDSA-AES256-GCM-SHA384'})
        self.assertEqual(verdict(0, ACCEPTED_13)['cipher'], 'TLS_AES_256_GCM_SHA384')
        self.assertEqual(verdict(1, REFUSED_CIPHER)['verdict'], 'refused')
        self.assertEqual(verdict(1, REFUSED_VERSION)['verdict'], 'refused')
        self.assertEqual(verdict(1, b'connect:errno=111\n')['verdict'], 'unknown')
        self.assertEqual(verdict(1, b'')['verdict'], 'unknown')

    def test_a_client_that_could_not_offer_is_never_a_refusal(self):
        for label, output in (('no ciphers', CLIENT_NO_CIPHERS), ('no protocols', CLIENT_NO_PROTOCOLS),
                              ('both an alert and a client failure', REFUSED_BUT_CLIENT_SAID_NO_CIPHERS)):
            with self.subTest(label):
                self.assertEqual(install.tls_probe_verdict(1, output)['verdict'], 'client')

    def test_the_policy_needs_aes_gcm_by_default_and_every_family_refused_by_the_server(self):
        def probe_with(answers):
            def probe(host, options):
                return install.tls_probe_verdict(0, answers.get(tuple(options), REFUSED_CIPHER))
            return probe
        good = {(): ACCEPTED_12}
        findings, probes = install.tls_policy_problems(probe=probe_with(good))
        self.assertEqual(findings, [])
        self.assertEqual(sorted(probes), sorted([install.DOMAIN, install.ADMIN_HOST]))
        self.assertEqual(sorted(probes[install.DOMAIN]), sorted(['default', *[label for label, _ in
                                                                             install.TLS_REFUSED_PROBES]]))
        cbc = dict(install.TLS_REFUSED_PROBES)['TLSv1.2 AES-CBC-SHA']
        findings, _ = install.tls_policy_problems(probe=probe_with({**good, tuple(cbc): ACCEPTED_CBC}))
        self.assertEqual(len(findings), 2)  # one per host
        self.assertIn('TLSv1.2 AES-CBC-SHA negotiated ECDHE-ECDSA-AES128-SHA', findings[0])
        # a family the client could not offer is a finding, never a pass (TEC-18 (2))
        chacha = dict(install.TLS_REFUSED_PROBES)['TLSv1.3 ChaCha20']
        findings, _ = install.tls_policy_problems(probe=probe_with({**good, tuple(chacha): CLIENT_NO_CIPHERS}))
        self.assertTrue(findings and all('could not tell' in finding for finding in findings))
        # a default client that negotiates something else is a finding
        findings, _ = install.tls_policy_problems(probe=probe_with({(): ACCEPTED_CBC}))
        self.assertTrue(all('did not negotiate an AES-GCM suite' in finding for finding in findings))

    def test_each_refused_family_is_offered_alone_and_the_old_protocols_at_seclevel_0(self):
        families = dict(install.TLS_REFUSED_PROBES)
        self.assertEqual(sorted(families), sorted(['TLSv1.3 ChaCha20', 'TLSv1.2 ChaCha20', 'TLSv1.2 ARIA-GCM',
                                                   'TLSv1.2 Camellia', 'TLSv1.2 AES-CBC-SHA', 'TLSv1.1', 'TLSv1.0']))
        for label, options in install.TLS_REFUSED_PROBES:
            offered = ' '.join(options)
            self.assertIsNone(install.TLS_APPROVED_RE.search(offered), label)  # never a suite the policy allows
            if label in ('TLSv1.1', 'TLSv1.0'):
                self.assertIn('@SECLEVEL=0', offered)

    def test_a_probe_runs_the_hosts_openssl_against_the_local_listener_and_an_error_is_unknown(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(returncode=0, stdout=ACCEPTED_12, stderr=b'')
        with mock.patch.object(install, 'run', fake_run):
            self.assertEqual(install.tls_probe('cpt.quillmd.com', ('-tls1_2',))['verdict'], 'accepted')
        argv, kwargs = calls[0]
        self.assertEqual(argv, [install.OPENSSL, 's_client', '-connect', '127.0.0.1:443', '-servername',
                                'cpt.quillmd.com', '-tls1_2'])
        self.assertEqual((kwargs['input'], kwargs['check']), (b'', False))
        with mock.patch.object(install, 'run', side_effect=FileNotFoundError('openssl')):
            self.assertEqual(install.tls_probe('cpt.quillmd.com', ())['verdict'], 'unknown')
        # under the host guard a real probe is refused outright: no test reaches this host's listener
        self.assertIn('openssl', test_install.HOST_COMMANDS)

    def test_the_report_records_findings_and_never_raises(self):
        with mock.patch.object(install, 'tls_policy_problems', side_effect=RuntimeError('boom')):
            report = test_install.REAL_TLS_POLICY_REPORT()
        self.assertEqual(report, {'findings': ['the TLS probes did not run (RuntimeError)'], 'probes': {}})


if __name__ == '__main__':
    unittest.main()
