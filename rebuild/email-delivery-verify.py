#!/usr/bin/env python3
"""Controlled-recipient account email verification through the private doctor UI.

Run from the permanent reviewed release, as the operator:

  rebuild/.venv/bin/python rebuild/email-delivery-verify.py --release FULL_SHA \\
      --recipient ADDRESS --recipient-confirmation "I control this inbox" \\
      --department UUID --attempt LABEL --stage invitation --execute

Modes: --dry-run checks public sender DNS and configuration PRESENCE only (no
login, no provider request, nothing sent). --execute additionally drives the
real HTTP flow as the synthetic owner: an invitation to the recipient and/or a
password-recovery request for that address.

Stages: invitation | recovery, always separately. Protected operator evidence
must establish browser reachability and the intended account state before a send.
The recipient uses the original HTTPS link, with the private access credentials
supplied separately. This runner proves submission, never inbox receipt or link use.

Refuses unless the confirmation phrase is exact and the recipient is an
explicitly supplied, non-synthetic, non-placeholder address. Never prints or
stores credentials, API keys, tokens, links, message bodies, provider responses
or the unmasked recipient. Standard library plus httpx only.
"""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from uuid import UUID

import httpx

PERMANENT = Path('/opt/meddoc-pro/rebuild')
BASE = 'https://app.quillmd.com:9443'
CONFIRMATION = 'I control this inbox'
# Public DNS over HTTPS (Cloudflare JSON API). Chosen over dig/nslookup so the
# answer does not depend on the VPS resolver configuration or on parsing tool
# output; the response is JSON and the resolver is named in the report.
DOH = 'https://1.1.1.1/dns-query'
SYNTHETIC_DOMAIN = 'synthetic.quillmd.invalid'
RESERVED_TLDS = {'invalid', 'test', 'example', 'localhost', 'local', 'internal', 'onion', 'arpa'}
PLACEHOLDER_DOMAINS = {'example.com', 'example.org', 'example.net', 'quillmd.invalid'}
PLACEHOLDER_LOCALS = {'test', 'example', 'someone', 'user', 'recipient', 'address', 'email'}
SESSION_COOKIE = 'quillmd_doctor_session'
STAGES = ('invitation', 'recovery')
DNS_TYPES = {'TXT': 16, 'MX': 15}

# Runs inside the application's own environment so that key presence and the
# provider domain-status request are evaluated where the credential already
# lives. It prints booleans and the (public) sender domain only.
SETTINGS_PROBE = r'''
import json, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
import django
django.setup()
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
payload = json.loads(sys.stdin.read())
out = {'email_mode': str(settings.QUILLMD_EMAIL_MODE), 'resend_mode': settings.QUILLMD_EMAIL_MODE == 'resend',
       'configured': False, 'sender_domain': '',
       'app_base_url_matches_private_https': str(settings.QUILLMD_APP_BASE_URL) == payload.get('expected_origin'),
       'app_base_url_https': str(settings.QUILLMD_APP_BASE_URL).startswith('https://'),
       'provider_domain_status': {'attempted': False, 'readable': False, 'http_status': None,
                                  'domain_listed': None, 'status': None, 'region': None}}
try:
    from email.utils import parseaddr
    from core.email_backend import resend_configuration
    key, sender = resend_configuration()
    out['configured'] = True
    out['sender_domain'] = parseaddr(sender)[1].rsplit('@', 1)[-1].lower()
    if payload.get('probe_provider'):
        import httpx
        out['provider_domain_status']['attempted'] = True
        try:
            response = httpx.get('https://api.resend.com/domains', headers={'Authorization': 'Bearer ' + key},
                                 timeout=httpx.Timeout(15, connect=5), follow_redirects=False, trust_env=False)
            out['provider_domain_status']['http_status'] = response.status_code
            if response.status_code == 200:
                rows = response.json().get('data', [])
                match = [row for row in rows if isinstance(row, dict) and str(row.get('name', '')).lower() == out['sender_domain']]
                out['provider_domain_status'].update(readable=True, domain_listed=bool(match),
                    status=(str(match[0].get('status'))[:40] if match else None),
                    region=(str(match[0].get('region'))[:40] if match else None))
        except (httpx.HTTPError, ValueError) as exc:
            out['provider_domain_status']['error_class'] = type(exc).__name__
except ImproperlyConfigured:
    out['error_class'] = 'ImproperlyConfigured'
print(json.dumps(out))
'''


class Refusal(Exception):
    """Fixed, non-sensitive message; the run stops before any send."""


def refuse(message):
    raise Refusal(message)


class Page(HTMLParser):
    """Collect the few rendered elements the flow needs, without third-party parsers."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.csrf = ''
        self.selects = {}
        self.notices = []
        self.status = []
        self.buttons = []
        self.rows = []
        self._row = None
        self._select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('name') == 'csrfmiddlewaretoken':
            self.csrf = attrs.get('value', '')
        if tag == 'select':
            self._select = attrs.get('name', '')
            self.selects.setdefault(self._select, [])
        if tag == 'tr':
            self._row = []
        self.stack.append({'tag': tag, 'attrs': attrs, 'text': []})

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['text'].append(data)

    def handle_endtag(self, tag):
        while self.stack:
            element = self.stack.pop()
            text = ' '.join(''.join(element['text']).split())
            if self.stack:
                self.stack[-1]['text'].append(' ' + text + ' ')
            classes = element['attrs'].get('class', '').split()
            if element['tag'] == 'option' and self._select is not None:
                self.selects[self._select].append((element['attrs'].get('value', text), text))
            elif element['tag'] == 'select':
                self._select = None
            elif element['tag'] in ('td', 'th') and self._row is not None:
                self._row.append(text)
            elif element['tag'] == 'tr' and self._row is not None:
                self.rows.append(self._row)
                self._row = None
            elif 'notice' in classes:
                self.notices.append(text)
            elif element['attrs'].get('role') == 'status':
                self.status.append(text)
            elif element['tag'] == 'button':
                self.buttons.append(text)
            if element['tag'] == tag:
                break


def parse(text):
    page = Page()
    page.feed(text)
    page.close()
    return page


def mask(address):
    local, domain = address.rsplit('@', 1)
    return local[:2] + '***@' + domain


def validate_recipient(raw):
    address = raw.strip()
    if address != raw or not address:
        refuse('Pass the recipient address exactly, without surrounding whitespace.')
    if not re.fullmatch(r'[A-Za-z0-9._%+-]{1,64}@(?:[A-Za-z0-9-]{1,63}\.)+[A-Za-z]{2,24}', address):
        refuse('The recipient must be one plain mailbox address.')
    local, domain = address.rsplit('@', 1)
    domain = domain.lower()
    tld = domain.rsplit('.', 1)[-1]
    if domain == SYNTHETIC_DOMAIN or domain.endswith('.' + SYNTHETIC_DOMAIN):
        refuse('Synthetic addresses cannot receive mail; supply the controlled inbox you actually check.')
    if tld in RESERVED_TLDS or domain in PLACEHOLDER_DOMAINS:
        refuse('The recipient domain is reserved or a placeholder; supply the controlled inbox explicitly.')
    if local.lower() in PLACEHOLDER_LOCALS:
        refuse('The recipient looks like a placeholder, not a controlled inbox.')
    return local + '@' + domain


def private_read(path):
    path = Path(path)
    if path.resolve() != path:
        refuse('Private credential file must not be reached through a link.')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'r') as handle:
        info = os.fstat(handle.fileno())
        if not (stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                and (info.st_mode & 0o777) == 0o600 and info.st_size <= 2 * 1024 * 1024):
            refuse('Private credential file must be an owner-only 0600 regular file.')
        return json.load(handle)


def write_private(path, document):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(json.dumps(document, indent=2) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical_uuid(value, label):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        refuse(label + ' must be a canonical UUID.')
    return value


def recent_evidence(value, field):
    try:
        timestamp = datetime.fromisoformat(value)
        if timestamp.tzinfo is None:
            raise ValueError
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
        if not 0 <= age <= 86400:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        refuse(field + ' must be a timezone-qualified timestamp within the past 24 hours.')


def evidence_reference(value):
    # References identify an operator report, not a URL, credential or message.
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_. /:-]{3,240}', value) or '://' in value:
        refuse('Use a short nonsecret evidence reference, not an email link.')
    return value


def private_access(runtime):
    access = private_read(runtime / 'email-private-access.json')
    if not isinstance(access, dict) or access.get('origin') != BASE:
        refuse('Private access must name exactly the approved HTTPS origin.')
    username, password = access.get('username'), access.get('password')
    if (not isinstance(username, str) or not username or ':' in username
            or not isinstance(password, str) or not password
            or any(ord(c) < 32 or ord(c) > 126 for c in username + password)):
        refuse('Protected private access credentials are invalid.')
    return httpx.BasicAuth(username, password)


def execution_authorization(runtime, recipient, department, release, stage):
    browser = private_read(runtime / 'email-owner-browser-readiness.json')
    if (not isinstance(browser, dict) or browser.get('origin') != BASE
            or browser.get('reachable') is not True or browser.get('confirmed_by') != 'owner'):
        refuse('Owner browser reachability on the exact private HTTPS origin must be recorded first.')
    recent_evidence(browser.get('confirmed_at'), 'Browser confirmation time')
    browser_reference = evidence_reference(browser.get('evidence_reference'))
    authorization = private_read(runtime / 'email-flow-authorization.json')
    if (not isinstance(authorization, dict) or authorization.get('origin') != BASE
            or authorization.get('recipient') != recipient or authorization.get('department_id') != department
            or authorization.get('release') != release):
        refuse('Protected account evidence does not match this recipient, department, origin and release.')
    recent_evidence(authorization.get('checked_at'), 'Account evidence time')
    account_reference = evidence_reference(authorization.get('evidence_reference'))
    account = authorization.get(stage)
    if not isinstance(account, dict):
        refuse('Protected account evidence is missing this stage.')
    if stage == 'invitation':
        if account.get('recipient_absent') is not True:
            refuse('Invitation requires independent evidence that the recipient has no existing account.')
    else:
        canonical_uuid(account.get('account_id'), 'Verified invitee account ID')
        if (account.get('verified') is not True or account.get('is_staff') is not False
                or account.get('department_id') != department or account.get('role') != 'employee'
                or account.get('invitation_accepted') is not True):
            refuse('Recovery requires independent evidence of the accepted, verified Employee test account.')
    return {'owner_browser_reachability': {'confirmed': True, 'confirmed_at': browser['confirmed_at'],
                                         'evidence_reference': browser_reference},
            'account_state': {'checked_at': authorization['checked_at'], 'evidence_reference': account_reference,
                              'stage': stage, 'matched': True}}


def private_client(auth=None):
    # Fixed origin and relative application paths only; never follow a Location
    # header or disable certificate verification to get through a failed gate.
    return httpx.Client(base_url=BASE, auth=auth, timeout=httpx.Timeout(30, connect=5),
                        trust_env=False, follow_redirects=False, verify=True)


def private_https_health(auth, release):
    with private_client() as public:
        response = public.get('/health/')
        if response.status_code != 401 or not response.headers.get('www-authenticate', '').lower().startswith('basic '):
            refuse('The private HTTPS origin must challenge unauthenticated access with HTTP Basic Auth.')
    with private_client(auth) as client:
        health(client, release)


def doh(client, name, rtype):
    result = {'name': name, 'type': rtype, 'records': []}
    try:
        response = client.get(DOH, params={'name': name, 'type': rtype}, headers={'accept': 'application/dns-json'})
        result['http_status'] = response.status_code
        if response.status_code != 200:
            return result
        body = response.json()
        result['rcode'] = body.get('Status')
        for row in body.get('Answer') or []:
            if row.get('type') != DNS_TYPES[rtype]:
                continue
            data = str(row.get('data', ''))
            if rtype == 'TXT':
                data = ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', data)) or data
            result['records'].append(data[:512])
            if len(result['records']) >= 10:
                break
    except (httpx.HTTPError, ValueError) as exc:
        result['error_class'] = type(exc).__name__
    return result


def sender_dns(domain):
    with httpx.Client(timeout=httpx.Timeout(15, connect=5), trust_env=False, follow_redirects=False) as client:
        root_txt = doh(client, domain, 'TXT')
        send_txt = doh(client, 'send.' + domain, 'TXT')
        send_mx = doh(client, 'send.' + domain, 'MX')
        dkim = doh(client, 'resend._domainkey.' + domain, 'TXT')
        dmarc = doh(client, '_dmarc.' + domain, 'TXT')
    spf = lambda rows: [r for r in rows['records'] if r.lower().startswith('v=spf1')]
    return {
        'resolver': 'DNS over HTTPS, 1.1.1.1 JSON API', 'queried_at': now(), 'domain': domain,
        'spf_root': {**root_txt, 'spf_present': bool(spf(root_txt))},
        'spf_send_subdomain': {**send_txt, 'spf_present': bool(spf(send_txt)),
                               'references_amazonses': any('amazonses.com' in r for r in spf(send_txt))},
        'mx_send_subdomain': {**send_mx, 'present': bool(send_mx['records'])},
        'dkim_resend_selector': {**dkim, 'present': any('p=' in r for r in dkim['records'])},
        'dmarc': {**dmarc, 'present': any(r.lower().startswith('v=dmarc1') for r in dmarc['records'])},
        'note': 'Conventional Resend record names; the authoritative list is the one Resend shows for this domain.',
    }


def settings_probe(probe_provider):
    env = {'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'), 'HOME': os.environ.get('HOME', ''), 'LANG': 'C.UTF-8'}
    try:
        result = subprocess.run([str(PERMANENT / '.venv/bin/python'), '-c', SETTINGS_PROBE], cwd=PERMANENT, env=env,
                                input=json.dumps({'probe_provider': probe_provider, 'expected_origin': BASE}), capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'probe_failed': True, 'error_class': type(exc).__name__}
    if result.returncode != 0:
        return {'probe_failed': True, 'exit': result.returncode}
    try:
        return json.loads(result.stdout)
    except ValueError:
        return {'probe_failed': True, 'exit': 0, 'stdout_json': False}


def fetch(client, path_):
    response = client.get(path_)
    if response.status_code != 200:
        refuse('Unexpected response from ' + path_ + ': HTTP ' + str(response.status_code))
    return parse(response.text)


def health(client, release):
    response = client.get('/health/')
    if response.status_code != 200:
        refuse('Health endpoint unavailable.')
    body = response.json()
    if body.get('release') != release or body.get('data_mode') != 'synthetic-only' or body.get('surface') != 'doctor':
        refuse('The running service is not the exact synthetic-only doctor release named.')


def login(client, account):
    if not (isinstance(account, dict) and str(account.get('email', '')).endswith('@' + SYNTHETIC_DOMAIN)
            and isinstance(account.get('password'), str)):
        refuse('Synthetic owner credentials are not in the expected form.')
    page = fetch(client, '/login/')
    response = client.post('/login/', data={'csrfmiddlewaretoken': page.csrf, 'email': account['email'],
                                            'password': account['password'], 'otp': '', 'next': ''},
                           headers={'Referer': BASE + '/login/'})
    if response.status_code != 302 or response.headers.get('location', '') not in ('/', BASE + '/') or SESSION_COOKIE not in client.cookies:
        refuse('Synthetic owner sign-in was not accepted.')


def classify(notices):
    text = ' '.join(notices)
    if 'submitted to the email provider' in text:
        return 'accepted-by-provider'
    if 'private development outbox' in text:
        return 'private-outbox-only'
    if 'could not be confirmed' in text:
        return 'delivery-failed'
    return 'no-recognised-notice'


def invite(client, recipient, department):
    page = fetch(client, '/team/')
    departments = page.selects.get('department', [])
    if not departments:
        refuse('The synthetic owner has no department with invitation authority.')
    matches = [(v, label) for v, label in departments if v == department and label == 'X-ray']
    if len(matches) != 1:
        refuse('The exact approved X-ray department is not available to this synthetic owner.')
    chosen, chosen_label = matches[0]
    if 'employee' not in [v for v, _ in page.selects.get('role', [])]:
        refuse('The invitation form does not offer the employee role.')
    response = client.post('/team/', data={'csrfmiddlewaretoken': page.csrf, 'department': chosen,
                                           'email': recipient, 'role': 'employee'},
                           headers={'Referer': BASE + '/team/'})
    outcome = {'invitation_http_status': response.status_code, 'department': chosen_label, 'role': 'employee'}
    if response.status_code == 302:
        after = fetch(client, '/team/')
        outcome['invitation_outcome'] = classify(after.notices)
        outcome['application_notices'] = after.notices[:5]
        rows = [row for row in after.rows if row and row[0].lower() == recipient]
        outcome['invitation_rows_for_recipient'] = [row[3] for row in rows if len(row) >= 4][:10]
        outcome['csrf'] = after.csrf
    elif response.status_code == 429:
        outcome['invitation_outcome'] = 'rate-limited'
    else:
        outcome['invitation_outcome'] = 'rejected'
    return outcome


def recovery(recipient, auth):
    with private_client(auth) as client:
        page = fetch(client, '/recovery/')
        response = client.post('/recovery/', data={'csrfmiddlewaretoken': page.csrf, 'email': recipient},
                               headers={'Referer': BASE + '/recovery/'})
        outcome = {'recovery_http_status': response.status_code}
        if response.status_code == 200:
            after = parse(response.text)
            text = ' '.join(after.status)
            outcome['recovery_page_acknowledged'] = 'If this address is eligible' in text
            outcome['recovery_page_reports_live_delivery'] = 'Check your inbox' in response.text
            outcome['note'] = ('The page deliberately does not reveal whether a message was produced. A recovery '
                               'message exists only if the recipient already holds a verified account; a rate-limited '
                               'or unknown address receives the same page.')
        return outcome


def require_submission(stage, outcome):
    if stage == 'invitation':
        if outcome.get('invitation_http_status') != 302 or outcome.get('invitation_outcome') != 'accepted-by-provider':
            refuse('Invitation was not confirmed as accepted by the provider; preserve this attempt and inspect it before any retry.')
        return 'provider-accepted'
    if (outcome.get('recovery_http_status') != 200 or outcome.get('recovery_page_acknowledged') is not True
            or outcome.get('recovery_page_reports_live_delivery') is not True):
        refuse('The recovery request did not return the expected live-delivery acknowledgement.')
    return 'request-acknowledged-provider-outcome-not-proved'


def logout(client, csrf):
    if csrf:
        client.post('/logout/', data={'csrfmiddlewaretoken': csrf}, headers={'Referer': BASE + '/'})


def main():
    parser = argparse.ArgumentParser(description='Controlled-recipient email delivery verification.')
    parser.add_argument('--release', required=True)
    parser.add_argument('--recipient', required=True)
    parser.add_argument('--recipient-confirmation', required=True)
    parser.add_argument('--department', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--stage', required=True, choices=STAGES)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--execute', action='store_true')
    mode.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if args.recipient_confirmation != CONFIRMATION:
        refuse('The recipient confirmation phrase must be exactly: ' + CONFIRMATION)
    recipient = validate_recipient(args.recipient)
    department = canonical_uuid(args.department, '--department')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', args.attempt):
        refuse('--attempt must be a unique lowercase letter/digit/hyphen label of at most 64 characters.')
    if not re.fullmatch(r'[a-f0-9]{40}', args.release):
        refuse('--release must be the full 40-character commit SHA.')
    here = Path(__file__).resolve().parent
    # sys.prefix names the virtual environment; the binary itself is a symlink
    # shared with the system interpreter, so comparing it would prove nothing.
    if here != PERMANENT or Path(sys.prefix).resolve() != (PERMANENT / '.venv').resolve():
        refuse('Run from the reviewed permanent release with its own interpreter.')
    runtime = PERMANENT / '.runtime'
    info = runtime.lstat()
    if not (stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode) and info.st_uid == os.getuid() and (info.st_mode & 0o777) == 0o700):
        refuse('The private runtime directory must be an owner-only 0700 directory.')
    credentials = private_read(runtime / 'private-access.json')
    suffix = '-' + args.stage + '-' + args.attempt
    report_path = runtime / ('email-delivery-verification-' + args.release[:12] + suffix + ('' if args.execute else '-dry-run') + '.json')
    if report_path.exists() or report_path.is_symlink():
        refuse('Existing verification evidence requires inspection before another attempt.')
    if args.execute:
        # Reserve this attempt before any checks or potential send. A competing
        # process must not overwrite the first process's eventual outcome report.
        try:
            write_private(report_path.with_suffix('.execution-lock'), {'stage': args.stage, 'attempt': args.attempt, 'started_at': now()})
        except FileExistsError:
            refuse('This immutable attempt is already claimed; inspect its evidence before any retry.')

    report = {'passed': False, 'executed': False, 'mode': 'execute' if args.execute else 'dry-run', 'stage': args.stage,
              'release': args.release, 'synthetic_only': True, 'app_origin': BASE, 'started_at': now(), 'checks': [],
              'pass_scope': 'configuration-checks-only' if args.dry_run else 'submission-checks-only',
              'attempt': args.attempt, 'department_id': department, 'role': 'employee',
              'recipient': mask(recipient), 'recipient_confirmation_phrase_matched': True,
              'sender_domain_dns': None, 'provider_domain_status': None, 'app_email_configuration': None,
              'invitation_http_status': None, 'invitation_outcome': None,
              'recovery_http_status': None, 'recovery_outcome': None,
              'provider_message_ids_recorded': False,
              'tokens_exposed': False, 'links_stored': False,
              'inbox_receipt_confirmed': False, 'inbox_receipt_confirmed_by': None, 'inbox_receipt_confirmed_at': None,
              'provider_delivery_confirmed': False, 'application_flow_completed': False,
              'submission_status': 'not-attempted', 'execution_authorization': None,
              'next_steps': []}
    active = 'configuration presence'

    def check(name):
        nonlocal active
        active = name
        report['checks'].append({'name': name, 'passed': True})
        print('PASS ' + name)

    try:
        probe = settings_probe(probe_provider=args.execute)
        report['app_email_configuration'] = {k: v for k, v in probe.items() if k != 'provider_domain_status'}
        report['provider_domain_status'] = probe.get('provider_domain_status')
        if probe.get('probe_failed'):
            refuse('The application settings probe failed; no delivery attempted.')
        check('Application email configuration read as booleans only')
        domain = probe.get('sender_domain') or ''
        if domain:
            report['sender_domain_dns'] = sender_dns(domain)
            check('Public DNS evidence for the configured sender domain recorded')
        else:
            report['sender_domain_dns'] = {'domain': None, 'note': 'No configured Resend sender; DNS not queried.'}
        if not args.execute:
            report['next_steps'] = ['Establish protected HTTPS access and verify the existing sender before live account email.',
                                    'Record owner browser reachability and independent account-state evidence in the protected runtime files.',
                                    'Use one separately authorized invitation or recovery stage; this dry run made no login or provider request.']
            report['passed'] = True
            return report, report_path
        if not (probe.get('resend_mode') and probe.get('configured')):
            refuse('Resend delivery is not explicitly enabled and configured in the running application environment.')
        if probe.get('app_base_url_matches_private_https') is not True:
            refuse('QUILLMD_APP_BASE_URL must exactly match the approved private HTTPS origin.')
        status = report['provider_domain_status'] or {}
        if status.get('readable') and (not status.get('domain_listed') or str(status.get('status')).lower() != 'verified'):
            refuse('The provider reports the sender domain as not verified.')
        check('Resend mode, sender assertion and exact HTTPS link origin are configured; unreadable provider status is not proof of verification')
        report['execution_authorization'] = execution_authorization(runtime, recipient, department, args.release, args.stage)
        check('Protected owner browser confirmation and independent account evidence match this stage')
        auth = private_access(runtime)
        private_https_health(auth, args.release)
        check('TLS-verified HTTPS rejects unauthenticated access and serves the exact synthetic-only doctor release with private authentication')
        with private_client(auth) as client:
            health(client, args.release)
            check('Running service is the exact synthetic-only doctor release')
            csrf = ''
            if args.stage == 'invitation':
                login(client, credentials.get('doctor'))
                check('Synthetic owner signed in through the real login form')
                report['executed'] = True
                report['submission_status'] = 'attempted-outcome-unknown'
                outcome = invite(client, recipient, department)
                csrf = outcome.pop('csrf', '')
                report['invitation_http_status'] = outcome.get('invitation_http_status')
                report['invitation_outcome'] = dict(outcome)
                logout(client, csrf)
                report['submission_status'] = require_submission('invitation', outcome)
                check('Invitation submission accepted by provider; delivery, inbox receipt and acceptance remain unproved')
            else:
                report['executed'] = True
                report['submission_status'] = 'attempted-outcome-unknown'
                outcome = recovery(recipient, auth)
                report['recovery_http_status'] = outcome.get('recovery_http_status')
                report['recovery_outcome'] = dict(outcome)
                report['submission_status'] = require_submission('recovery', outcome)
                check('Recovery request acknowledged; provider outcome, delivery, inbox receipt and reset remain unproved')
        report['next_steps'] = [
            'Recipient: confirm inbox receipt and open the original HTTPS email link unchanged using the private access already verified. Do not paste or forward the link.',
            'Recipient: complete this invitation or recovery with synthetic account details and confirm the result; never send passwords in chat.',
            'Operator: preserve this report unchanged. Add separate timestamped evidence for provider acceptance/delivery, owner inbox receipt and completed application actions.',
            'Operator: after verified invitation acceptance, update independent account-state evidence before requesting the one recovery email.',
            'Operator: capture provider IDs from email.accepted audit metadata and verify scope, welcome credit, session invalidation and token reuse separately.',
        ]
        report['passed'] = True
        return report, report_path
    except Refusal as exc:
        report['refusal'] = str(exc)
        report['active_check'] = active
        raise
    except Exception as exc:
        report['error_class'] = type(exc).__name__
        report['active_check'] = active
        raise
    finally:
        report['finished_at'] = now()
        try:
            write_private(report_path, report)
            print('Evidence: ' + str(report_path))
        except OSError:
            print('Evidence could not be written; inspect the runtime directory.', file=sys.stderr)


if __name__ == '__main__':
    try:
        main()
    except Refusal as exc:
        print('REFUSED: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
    except SystemExit:
        raise
    except Exception:
        raise SystemExit('Email delivery verification stopped; details are suppressed. No retry was attempted.')
