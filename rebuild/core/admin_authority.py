"""Declared administrator changes: a second administrator, and an administrator's authenticator reset.

Inventory 7A, F2. Neither had an audited door: the console refuses to change another administrator (and resets
only clinical accounts' authenticators), and `bootstrap_first_admin` elevates exactly one account on an otherwise
empty database. These two operations — `manage.py elevate_additional_admin` and `manage.py reset_admin_mfa` — are
the only doors now, and each one:

  (a) runs only under a declaration, through one of two doors:
      PRODUCTION (QUILLMD_DEPLOYMENT_PROFILE=production): the operator door `bootstrap_first_admin` uses —
        ops.production_operator.authority through bootstrap_first_admin.production_context: a JSON declaration with
        `operation: administrators` and exactly one action (this operation), bound to the installed release, profile
        and RDS target, unexpired, run as root through the ruled-mutation environment, with the application's own
        production profile and TLS connection checked. An installed release is `rebuild/` alone (no git, no docs, no
        scripts), so this is the only door there (refutation R5);
      REPOSITORY (any other profile — the private beta and QA, which run from a git checkout): a declaration TRACKED,
        COMMITTED and UNMODIFIED in docs/foundation/mutations/, opened through scripts/run-ruled-mutation.sh — the
        standing runner's own checks, provider_campaign.committed_file and standing_qa.require_door. Both read the
        door from environment variables: that is the shared ruled-mutation design (refutation R8, recorded);
  (b) requires a DISTINCT APPROVER named in that declaration — an existing, active, verified administrator with a
      confirmed authenticator, who is not the target — to be PRESENT: a current code from the approver's own
      confirmed authenticator, read from a 0600 file passed by path (the door runs the command with standard input
      detached; the file is reached with no symbolic link in its path and judged on its open descriptor), verified
      against that device and consumed (the device records it, so the same code is refused a second time)
      (refutation R7). A code that does not verify is RECORDED in a transaction of its own — the device's throttle
      counts it and an audit row names the operator, the approver and the command — and a throttled device is not
      tried at all, while the act itself rolls back whole (round 2, R7-a/R7-b);
  (c) invalidates every session of the target (session_version), in the same transaction as the change;
  (d) writes one audit record. Its actor is the approver ONLY because the code proved the approver's presence; the
      record also names the operating account (uid), the door, the declaration, its commit, its committer and author
      (repository door) and its sha256;
  (e) prints no secret. A reset removes the target's authenticators and creates none: the new key is generated
      only when the administrator signs in again ON THE ADMINISTRATION SURFACE within ADMIN_REENROLMENT_WINDOW and
      enrols on /mfa/ — shown there to that session only, never printed by the command.

A declaration is used once: the act it authorizes (operation, target, approver, reason — act_identity) is recorded
with the audit row, and any declaration for the same act, however serialized, is refused before anything changes
(round 2, R5-a). Every refusal happens before the first write, inside one transaction; only the record of an
approver's code that failed is written, on its own, after the act has rolled back.

The repository declaration (markdown; one line each, each exactly once):

    operation: elevate_additional_admin | reset_admin_mfa
    target_account: <account id>
    target_email: <account email>
    approver_account: <account id>
    approver_email: <account email>
    reason: <why, and for a reset how the holder's identity was checked — at least 12 characters>

The production declaration (JSON): the production_operator fields (format 1, release_sha, profile_sha256,
expires_at, database_arn, database_resource_id, kms_key_arn) with `operation: "administrators"`,
`actions: ["<one operation>"]`, `target: {id, email}`, `approver: {id, email}` and `reason`.
"""
import hashlib
import json
import os
import re
import stat
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import AuditEvent, User
from .security import audit

REBUILD = Path(__file__).resolve().parents[1]
REPOSITORY = REBUILD.parent
NAME = re.compile(r'20[0-9]{6}-quillmd-admin-[a-z0-9]+(?:-[a-z0-9]+)*\.md')
FIELDS = ('operation', 'target_account', 'target_email', 'approver_account', 'approver_email', 'reason')
ELEVATE = 'elevate_additional_admin'
RESET = 'reset_admin_mfa'
ACTIONS = {ELEVATE: 'account.admin_elevated', RESET: 'account.admin_mfa_reset'}
#: The production_operator `operation` of an administrator-change declaration.
PRODUCTION_OPERATION = 'administrators'
#: How long after a declared reset the administrator may sign in with the password alone to enrol a new
#: authenticator, on the administration surface only. An owner value (report: owner questions).
ADMIN_REENROLMENT_WINDOW = timedelta(hours=24)
CODE = re.compile(rb'[0-9]{6}\n?')


class Refused(Exception):
    """An administrator change refused before anything was written. The text names rules, never secrets."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def production():
    return os.environ.get('QUILLMD_DEPLOYMENT_PROFILE') == 'production'


def bind(fields, operation, target):
    """The checks both doors share: one operation, the --target it names, an approver who is not the target."""
    require(fields['operation'] == operation,
            f'The declaration is for {fields["operation"]}, not {operation}: a declaration authorizes one operation.')
    try:
        target = uuid.UUID(str(target))
    except ValueError:
        raise Refused('--target is not an account id.') from None
    require(fields['target_account'] == target, 'The declaration names another target account than --target.')
    require(fields['approver_account'] != fields['target_account'] and
            fields['approver_email'].lower() != fields['target_email'].lower(),
            'The approver and the target are the same account: an administrator change needs a second administrator.')
    require(len(fields['reason']) >= 12, 'The declaration\'s reason must say why, in at least 12 characters.')
    return fields


def account_id(value, name):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        raise Refused(f'The declaration\'s {name} is not an account id.') from None


def declaration_fields(data):
    """The fields of a repository (markdown) declaration."""
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise Refused('The declaration is not UTF-8 text.') from None
    require('<FILL' not in text, 'The declaration still carries template placeholders (<FILL …>).')
    fields = {}
    for name in FIELDS:
        found = re.findall(rf'^{name}:[ \t]*(\S(?:[^\n]*\S)?)[ \t]*$', text, re.M)
        require(len(found) == 1, f'The declaration must state exactly one `{name}:` line (found {len(found)}).')
        fields[name] = found[0]
    require(fields['operation'] in ACTIONS, 'The declaration names no administrator operation this command performs.')
    for name in ('target_account', 'approver_account'):
        fields[name] = account_id(fields[name], f'`{name}:`')
    return fields


def repository_declared(operation, declaration, target, *, repository=None, environ=None):
    """The committed, unmodified repository declaration for `operation` on `target`, opened through the ruled-mutation
    door. Returns (fields, provenance). Refuses before anything is read from the database."""
    from ops import provider_campaign as pc
    from ops import standing_qa
    root = Path(REPOSITORY if repository is None else repository).resolve()
    given = Path(declaration)
    path = Path(os.path.abspath(str(given if given.is_absolute() else root / given)))
    require(path.parent == root / 'docs' / 'foundation' / 'mutations' and NAME.fullmatch(path.name),
            'The declaration must be docs/foundation/mutations/<YYYYMMDD>-quillmd-admin-<name>.md in this checkout.')
    try:
        data, commit, commit_time, relative = pc.committed_file(path, root, 'declaration')
        door = standing_qa.require_door(SimpleNamespace(repository=str(root), path=str(path), commit=commit),
                                        os.environ if environ is None else environ)
        people = pc._git(root, 'log', '-1', '--format=%an <%ae>%x00%cn <%ce>', commit, '--', relative).stdout
    except pc.Refused as exc:
        raise Refused(str(exc)) from None
    author, _, committer = people.decode('utf-8', 'replace').strip().partition('\x00')
    fields = bind(declaration_fields(data), operation, target)
    provenance = {'door': 'repository', 'declaration': relative, 'declaration_commit': commit,
                  'declaration_committed_at': commit_time, 'declaration_author': author,
                  'declaration_committer': committer, 'declaration_sha256': hashlib.sha256(data).hexdigest(),
                  'door_commit': door['commit']}
    return fields, provenance


def production_declared(operation, declaration, target):
    """The production operator door (bootstrap_first_admin.production_context): the JSON declaration the door names,
    for `administrators` with exactly this one action. Returns (fields, provenance)."""
    from core.management.commands.bootstrap_first_admin import production_context
    from ops import deployment_profile
    from ops.production_operator import OperatorError
    try:
        profile, authority = production_context(PRODUCTION_OPERATION, operation)
    except (OperatorError, deployment_profile.ProfileError) as exc:
        raise Refused('production door: ' + str(exc)) from None
    except (ValueError, KeyError, TypeError, OSError) as exc:
        # An unreadable or malformed declaration (its values are never echoed).
        raise Refused('production door: ' + type(exc).__name__) from None
    named = os.environ.get('RULED_MUTATION_DECLARATION', '')
    require(declaration and Path(os.path.abspath(declaration)).resolve() == Path(named).resolve(),
            '--declaration names another file than the ruled-mutation door opened.')
    data = Path(named).read_bytes()
    require(json.loads(data) == authority, 'The declaration changed while it was being read.')
    require(authority.get('actions') == [operation], 'A production administrator declaration names exactly one action.')
    parties = {}
    for role in ('target', 'approver'):
        party = authority.get(role)
        require(isinstance(party, dict) and set(party) == {'id', 'email'} and isinstance(party['email'], str),
                f'The declaration\'s {role} must be {{"id", "email"}}.')
        parties[role] = party
    require(isinstance(authority.get('reason'), str), 'The declaration states no reason.')
    fields = bind({'operation': operation, 'target_account': account_id(parties['target']['id'], 'target id'),
                   'target_email': parties['target']['email'],
                   'approver_account': account_id(parties['approver']['id'], 'approver id'),
                   'approver_email': parties['approver']['email'], 'reason': authority['reason'].strip()},
                  operation, target)
    provenance = {'door': 'production', 'declaration': Path(named).name,
                  'declaration_commit': os.environ.get('RULED_MUTATION_DECL_COMMIT', ''),
                  'declaration_sha256': hashlib.sha256(data).hexdigest(), 'release_sha': authority['release_sha'],
                  'profile_sha256': profile.sha256}
    return fields, provenance


def _open_without_links(path):
    """A read descriptor for absolute `path`, opened one component at a time from / with O_NOFOLLOW, so a symbolic
    link ANYWHERE in the path refuses (lstat and O_NOFOLLOW on the full path see only its last component), and with
    O_NONBLOCK, so a FIFO or device answers at once instead of blocking the command (refutation R7-b)."""
    common = os.O_CLOEXEC | os.O_NOFOLLOW
    parts = path.parts
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | common, dir_fd=directory)
            os.close(directory)
            directory = child
        return os.open(parts[-1], os.O_RDONLY | os.O_NONBLOCK | common, dir_fd=directory)
    finally:
        os.close(directory)


def approver_code(path):
    """The approver's current authenticator code, from a file only this process's account can read: reached with no
    symbolic link anywhere in its path, and judged on the OPEN descriptor (fstat) — a regular file owned by the
    effective user, mode 0600 or stricter, holding six digits — so nothing swapped in between a check and the open is
    ever read (refutation R7-b)."""
    require(path and str(path).strip(), 'The approver\'s presence is required: pass --approver-code-file, a 0600 '
                                        'file holding the approver\'s current six-digit authenticator code.')
    try:
        descriptor = _open_without_links(Path(os.path.abspath(path)))
    except OSError:
        raise Refused('The approver code file cannot be read: it must exist and be reached with no symbolic link in '
                      'its path.') from None
    try:
        info = os.fstat(descriptor)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid()
                and not info.st_mode & 0o077 and info.st_size <= 8,
                'The approver code file must be a regular file of this account, mode 0600, holding six digits.')
        data = os.read(descriptor, 16)
    finally:
        os.close(descriptor)
    require(CODE.fullmatch(data), 'The approver code file must hold the six-digit code and nothing else.')
    return data[:6].decode()


def _account(pk, email, role):
    account = User.objects.select_for_update().filter(pk=pk).first()
    require(account is not None and account.email == email,
            f'The declared {role} account does not exist (no account has that id and email).')
    return account


def _confirmed(account):
    return list(TOTPDevice.objects.select_for_update().filter(user=account, confirmed=True).order_by('pk'))


class _Absent(Exception):
    """The approver's code did not prove presence. Raised inside the act's transaction so the act rolls back whole;
    recorded afterwards, in a transaction of its own (record_absence)."""

    def __init__(self, approver, devices, reason):
        super().__init__(reason)
        self.approver, self.devices, self.reason = approver, devices, reason


def record_absence(operation, fields, provenance, absent):
    """Refutation R7-a: a code that does not prove the approver's presence is counted and kept, not rolled back with
    the act — otherwise codes could be guessed with no backoff and no trace. In its own committed transaction: each of
    the approver's devices the code was tried against counts one failure (django_otp's own throttle, which the next
    attempt and the approver's sign-in both honour), and one audit row names the operating account, the approver, the
    command and the change it was for. Never the code."""
    with transaction.atomic():
        for device in TOTPDevice.objects.select_for_update().filter(pk__in=absent.devices, user_id=absent.approver,
                                                                    confirmed=True):
            device.throttle_increment(commit=False)
            device.save(update_fields=['throttling_failure_count', 'throttling_failure_timestamp'])
        audit(None, 'account.admin_change_refused', absent.approver, command=operation, reason=absent.reason,
              approver=str(absent.approver), change_target=str(fields['target_account']),
              operator_uid=os.getuid(), operator_euid=os.geteuid(), **provenance)


def act_identity(fields):
    """The act a declaration authorizes, canonically: operation, target, approver and reason as sorted, compact JSON.
    A declaration is single-use by THIS, not by its bytes (refutation R5-a), so a re-serialized, re-formatted or
    re-issued copy of a used declaration is the same act and is refused."""
    canonical = {'operation': fields['operation'], 'reason': ' '.join(fields['reason'].split()),
                 'target': [str(fields['target_account']), fields['target_email'].lower()],
                 'approver': [str(fields['approver_account']), fields['approver_email'].lower()]}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def perform(operation, declaration, target, approver_code_file=None, *, repository=None, environ=None):
    """Perform `operation` under its declaration, with the approver present. Returns a dict with no secret in it."""
    if production():
        fields, provenance = production_declared(operation, declaration, target)
    else:
        fields, provenance = repository_declared(operation, declaration, target, repository=repository,
                                                 environ=environ)
    provenance['declaration_identity'] = act_identity(fields)
    code = approver_code(approver_code_file)
    try:
        return _act(operation, fields, provenance, code)
    except _Absent as absent:
        record_absence(operation, fields, provenance, absent)
        raise Refused('The approver\'s authenticator code did not verify ('
                      + ('the approver\'s authenticator is throttled after failed codes; wait, then present a new code'
                         if absent.reason == 'approver_throttled' else 'wrong, expired or already used')
                      + '). The attempt is recorded; nothing was changed.') from None


def _act(operation, fields, provenance, code):
    with transaction.atomic():
        # Both rows, locked in a fixed order: two declared changes on the same pair serialize, never deadlock.
        first, second = sorted([(fields['target_account'], 'target'), (fields['approver_account'], 'approver')],
                               key=lambda row: str(row[0]))
        accounts = {}
        for pk, role in (first, second):
            accounts[role] = _account(pk, fields[f'{role}_email'], role)
        account, approver = accounts['target'], accounts['approver']
        require(approver.is_staff and approver.is_active and approver.verified_at and approver.has_usable_password(),
                'The approver is not an active, verified administrator.')
        devices = _confirmed(approver)
        require(devices, 'The approver has no confirmed authenticator: only an MFA-enrolled administrator approves an '
                         'administrator change.')
        require(not AuditEvent.objects.filter(action__in=ACTIONS.values(),
                                              details__declaration_identity=provenance['declaration_identity']).exists(),
                'This declaration has already been used; a declaration authorizes one change.')
        if operation == ELEVATE:
            require(account.is_active and not account.is_staff and not account.is_superuser and account.verified_at
                    and account.has_usable_password(), 'The target is not an active, verified, non-administrator account.')
            require(_confirmed(account), 'The target has no confirmed authenticator; it enrols one before elevation.')
        else:
            require(account.is_staff and account.is_active, 'The target is not an active administrator; a clinical '
                                                            'account\'s authenticator is reset from the console.')
        # Presence, last. The device's own throttle is honoured: inside its backoff no code is tried at all. A code
        # that verifies is recorded on the device (consumed — refused if presented again); one that does not raises
        # _Absent, which rolls this whole transaction back and is then recorded on its own (record_absence).
        allowed = [device for device in devices if device.verify_is_allowed()[0]]
        if not allowed:
            raise _Absent(approver.pk, [], 'approver_throttled')
        present = next((device for device in allowed if device.verify_token(code)), None)
        if present is None:
            raise _Absent(approver.pk, [device.pk for device in allowed], 'approver_code_not_verified')
        if operation == ELEVATE:
            account.is_staff = True
            account.session_version += 1   # an existing clinical session cannot become an administrator session
            account.save(update_fields=['is_staff', 'session_version'])
            result = {'elevated': True, 'superuser': False}
        else:
            removed, _ = TOTPDevice.objects.filter(user=account).delete()
            account.session_version += 1
            account.save(update_fields=['session_version'])
            result = {'devices_removed': removed, 'enrolment_required_at_next_sign_in': True,
                      'enrolment_window_hours': int(ADMIN_REENROLMENT_WINDOW.total_seconds() // 3600)}
        counts = {'devices_removed': result['devices_removed']} if operation == RESET else {}
        # The actor is the approver because the code above proved the approver was present; the operating account
        # (who typed the command) is recorded beside it.
        audit(approver, ACTIONS[operation], account.pk, operation=operation, approver=str(approver.pk),
              approver_presence='authenticator code verified', approver_device=present.persistent_id,
              reason=fields['reason'].replace('\x00', ''), sessions_invalidated=True, operator_uid=os.getuid(),
              operator_euid=os.geteuid(), **counts, **provenance)
    return {'operation': operation, 'target': str(account.pk), 'approver': str(approver.pk),
            'approver_presence': 'verified', 'sessions_invalidated': True, **result, **provenance}


def reenrolment_open(user, now=None):
    """Whether `user`, an administrator with no confirmed authenticator, may sign in with the password alone to enrol
    one: only on the administration surface, only within ADMIN_REENROLMENT_WINDOW of a declared reset, and only until
    an authenticator is verified after that reset."""
    if not settings.ADMIN_SITE or not user.is_staff:
        return False
    now = now or timezone.now()
    reset = (AuditEvent.objects.filter(action=ACTIONS[RESET], target=str(user.pk))
             .order_by('-created_at').values_list('created_at', flat=True).first())
    if reset is None or reset < now - ADMIN_REENROLMENT_WINDOW:
        return False
    return not AuditEvent.objects.filter(actor=user, action='auth.mfa_verified', created_at__gt=reset).exists()
