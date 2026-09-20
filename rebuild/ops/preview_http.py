"""Operator HTTP access through the same preview form used by a browser.

No Basic credentials, capability URLs, or session cookies enter logs. This is
preview access only; individual application authentication remains separate.
"""
from html.parser import HTMLParser
from urllib.parse import urlsplit, parse_qs
import re

ORIGIN = 'https://app.quillmd.com:9443'
COOKIE = '__Host-quillmd_preview'


class PreviewAccessError(RuntimeError):
    pass


class Inputs(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'input' and values.get('name') in {'csrfmiddlewaretoken', 'flow'}:
            self.values.setdefault(values['name'], set()).add(values.get('value', ''))


def require(value, message):
    if not value:
        raise PreviewAccessError(message)


def sign_in_path(response):
    """Accept only the fixed sign-in route and a bounded opaque flow handle."""
    require(response.status_code == 302, 'Preview must redirect to its sign-in page.')
    path = response.headers.get('location', '')
    parsed = urlsplit(path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    require(not parsed.scheme and not parsed.netloc and not parsed.fragment
            and parsed.path == '/preview/sign-in/' and set(query) == {'flow'}
            and len(query['flow']) == 1
            and re.fullmatch(r'[a-f0-9]{32,128}', query['flow'][0]) is not None,
            'Preview returned an unexpected sign-in destination.')
    require('www-authenticate' not in response.headers,
            'Browser-native authentication must not be active on the preview.')
    return path, query['flow'][0]


def authenticate(client, credentials):
    require(str(client.base_url).rstrip('/') == ORIGIN, 'Preview origin differs from the approved HTTPS address.')
    require(isinstance(credentials, dict) and set(credentials) == {'username', 'password'}
            and all(isinstance(value, str) and value for value in credentials.values()),
            'Protected preview credentials are unavailable.')
    path, flow = sign_in_path(client.get('/health/'))
    response = client.get(path)
    require(response.status_code == 200 and 'www-authenticate' not in response.headers,
            'The preview sign-in page is unavailable.')
    fields = Inputs()
    fields.feed(response.text)
    require(fields.values.get('flow') == {flow} and len(fields.values.get('csrfmiddlewaretoken', set())) == 1,
            'The preview sign-in form did not preserve its destination.')
    csrf = next(iter(fields.values['csrfmiddlewaretoken']))
    require(re.fullmatch(r'[A-Za-z0-9]{64}', csrf) is not None, 'Preview CSRF token is unavailable.')
    response = client.post('/preview/sign-in/', data={**credentials, 'flow': flow, 'csrfmiddlewaretoken': csrf},
                           headers={'Origin': ORIGIN, 'Referer': ORIGIN + path})
    require(response.status_code == 302 and response.headers.get('location') == '/health/',
            'Preview sign-in was not accepted or lost its destination.')
    cookies = [cookie for cookie in client.cookies.jar if cookie.name == COOKIE]
    require(len(cookies) == 1 and cookies[0].secure and cookies[0].path == '/' and not cookies[0].domain_specified,
            'Preview session cookie lacks required host-only HTTPS scope.')
    rest = {key.lower(): value for key, value in cookies[0]._rest.items()}
    require('httponly' in rest and str(rest.get('samesite', '')).lower() == 'lax',
            'Preview session cookie protections are incomplete.')


def sign_out(client):
    """End only this preview session, preserving any application session."""
    token = client.cookies.get('quillmd_doctor_csrf')
    require(token and re.fullmatch(r'[A-Za-z0-9]{32,64}', token), 'Preview logout requires the current CSRF cookie.')
    response = client.post('/preview/sign-out/', data={'csrfmiddlewaretoken': token},
                           headers={'Origin': ORIGIN, 'Referer': ORIGIN + '/preview/sign-in/'})
    require(response.status_code == 302 and response.headers.get('location') == '/preview/sign-in/',
            'Preview session logout was not acknowledged.')
    sign_in_path(client.get('/health/'))
