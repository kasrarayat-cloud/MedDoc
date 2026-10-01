"""Declared administrator changes: a second administrator, and an administrator's authenticator reset.

Inventory 7A, F2. Neither had an audited door: the console refuses to change another administrator (and resets
only clinical accounts' authenticators), and `bootstrap_first_admin` elevates exactly one account on an otherwise
empty database. These two operations — `manage.py elevate_additional_admin` and `manage.py reset_admin_mfa` — are
the only doors now, and each one:

  (a) runs only through the ruled-mutation door (scripts/run-ruled-mutation.sh) opened for a declaration that is
      TRACKED, COMMITTED and UNMODIFIED in this checkout's docs/foundation/mutations/. The checks are the standing
      runner's own — provider_campaign.committed_file and standing_qa.require_door — not a second implementation;
  (b) names a DISTINCT APPROVER in that declaration: an existing, active, verified administrator with a confirmed
      authenticator, who is not the target. The declaration's commit is the approval record. The approver's live
      code is not also demanded: the door runs the command with standard input detached, so none could be typed;
  (c) invalidates every session of the target (session_version), in the same transaction as the change;
  (d) writes one audit record naming the operation, the approver, the declaration, its commit and its sha256;
  (e) prints no secret. A reset removes the target's authenticators and creates none: the new key is generated
      only when the administrator signs in again ON THE ADMINISTRATION SURFACE within ADMIN_REENROLMENT_WINDOW and
      enrols on /mfa/ — shown to them there, never printed by the command.

A declaration is used once: its sha256 is recorded with the audit row, and a second run of the same declaration is
refused before anything changes. Every refusal happens before the first write, inside one transaction.

The declaration (one line each, each exactly once):

    operation: elevate_additional_admin | reset_admin_mfa
    target_account: <account id>
    target_email: <account email>
    approver_account: <account id>
    approver_email: <account email>
    reason: <why, and for a reset how the holder's identity was checked — at least 12 characters>
"""
import hashlib
import os
import re
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
#: How long after a declared reset the administrator may sign in with the password alone to enrol a new
#: authenticator, on the administration surface only. An owner value (report: owner questions).
ADMIN_REENROLMENT_WINDOW = timedelta(hours=24)


def refused():
    """The refusal type: provider_campaign.Refused, which committed_file and require_door raise. Imported when a
    command runs, so the web processes (which only call reenrolment_open) never load the QA runner modules."""
    from ops.provider_campaign import Refused
    return Refused


def require(condition, message):
    if not condition:
        raise refused()(message)


def declaration_fields(data):
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise refused()('The declaration is not UTF-8 text.') from None
    require('<FILL' not in text, 'The declaration still carries template placeholders (<FILL …>).')
    fields = {}
    for name in FIELDS:
        found = re.findall(rf'^{name}:[ \t]*(\S(?:[^\n]*\S)?)[ \t]*$', text, re.M)
        require(len(found) == 1, f'The declaration must state exactly one `{name}:` line (found {len(found)}).')
        fields[name] = found[0]
    require(fields['operation'] in ACTIONS, 'The declaration names no administrator operation this command performs.')
    for name in ('target_account', 'approver_account'):
        try:
            fields[name] = uuid.UUID(fields[name])
        except ValueError:
            raise refused()(f'The declaration\'s `{name}:` is not an account id.') from None
    require(len(fields['reason']) >= 12, 'The declaration\'s `reason:` must say why, in at least 12 characters.')
    return fields


def declared(operation, declaration, target, *, repository=None, environ=None):
    """The committed, unmodified declaration for `operation` on `target`, opened through the ruled-mutation door.
    Returns (fields, provenance). Refuses before anything is read from the database."""
    from ops import provider_campaign as pc
    from ops import standing_qa
    root = Path(REPOSITORY if repository is None else repository).resolve()
    given = Path(declaration)
    path = Path(os.path.abspath(str(given if given.is_absolute() else root / given)))
    require(path.parent == root / 'docs' / 'foundation' / 'mutations' and NAME.fullmatch(path.name),
            'The declaration must be docs/foundation/mutations/<YYYYMMDD>-quillmd-admin-<name>.md in this checkout.')
    data, commit, commit_time, relative = pc.committed_file(path, root, 'declaration')
    door = standing_qa.require_door(SimpleNamespace(repository=str(root), path=str(path), commit=commit),
                                    os.environ if environ is None else environ)
    fields = declaration_fields(data)
    require(fields['operation'] == operation,
            f'The declaration is for {fields["operation"]}, not {operation}: a declaration authorizes one operation.')
    try:
        target = uuid.UUID(str(target))
    except ValueError:
        raise refused()('--target is not an account id.') from None
    require(fields['target_account'] == target, 'The declaration names another target account than --target.')
    require(fields['approver_account'] != fields['target_account'] and
            fields['approver_email'].lower() != fields['target_email'].lower(),
            'The approver and the target are the same account: an administrator change needs a second administrator.')
    provenance = {'declaration': relative, 'declaration_commit': commit, 'declaration_committed_at': commit_time,
                  'declaration_sha256': hashlib.sha256(data).hexdigest(), 'door_commit': door['commit']}
    return fields, provenance


def _account(pk, email, role):
    account = User.objects.select_for_update().filter(pk=pk).first()
    require(account is not None and account.email == email,
            f'The declared {role} account does not exist (no account has that id and email).')
    return account


def _confirmed_mfa(account):
    return TOTPDevice.objects.select_for_update().filter(user=account, confirmed=True).exists()


def perform(operation, declaration, target, *, repository=None, environ=None):
    """Perform `operation` under its declaration. Returns a dict with no secret in it."""
    fields, provenance = declared(operation, declaration, target, repository=repository, environ=environ)
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
        require(_confirmed_mfa(approver), 'The approver has no confirmed authenticator: only an MFA-enrolled '
                                          'administrator approves an administrator change.')
        require(not AuditEvent.objects.filter(action__in=ACTIONS.values(),
                                              details__declaration_sha256=provenance['declaration_sha256']).exists(),
                'This declaration has already been used; a declaration authorizes one change.')
        if operation == ELEVATE:
            require(account.is_active and not account.is_staff and not account.is_superuser and account.verified_at
                    and account.has_usable_password(), 'The target is not an active, verified, non-administrator account.')
            require(_confirmed_mfa(account), 'The target has no confirmed authenticator; it enrols one before elevation.')
            account.is_staff = True
            account.session_version += 1   # an existing clinical session cannot become an administrator session
            account.save(update_fields=['is_staff', 'session_version'])
            result = {'elevated': True, 'superuser': False}
        else:
            require(account.is_staff and account.is_active, 'The target is not an active administrator; a clinical '
                                                            'account\'s authenticator is reset from the console.')
            removed, _ = TOTPDevice.objects.filter(user=account).delete()
            account.session_version += 1
            account.save(update_fields=['session_version'])
            result = {'devices_removed': removed, 'enrolment_required_at_next_sign_in': True,
                      'enrolment_window_hours': int(ADMIN_REENROLMENT_WINDOW.total_seconds() // 3600)}
        counts = {'devices_removed': result['devices_removed']} if operation == RESET else {}
        audit(approver, ACTIONS[operation], account.pk, operation=operation, approver=str(approver.pk),
              reason=fields['reason'].replace('\x00', ''), sessions_invalidated=True, operator_uid=os.getuid(),
              **counts, **provenance)
    return {'operation': operation, 'target': str(account.pk), 'approver': str(approver.pk),
            'sessions_invalidated': True, **result, **provenance}


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
