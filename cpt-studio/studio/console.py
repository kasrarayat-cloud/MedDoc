"""The operator console's controls (owner direction 2026-11-22, DECISIONS D395): people and roles, workspaces, spending
and the activity log, under /ops/ beside studio.operator's encounter pages and behind the same gate - anyone who is not
a platform operator gets exactly what an unknown URL gets, before the method, the body, the CSRF token or any record is
read (studio.operator.operator_view).

    GET  /ops/people                        everyone who can sign in to a workspace (a row per membership), the accounts
                                            that belong to no workspace, the operators (read-only) and the add form
    POST /ops/people/add                    a new person in one workspace with a role: answers the one-time password
    POST /ops/people/<user>/role            the role of one of the person's memberships: owner, reviewer or viewer
    POST /ops/people/<user>/password        a new password for the person: answered once
    POST /ops/people/<user>/access          the person's access off or on again (the account's is_active)
    GET  /ops/workspaces                    every workspace with its specialty, people and documents; the create form
    POST /ops/workspaces/new                a workspace for a specialty that exists
    GET  /ops/workspaces/<workspace>        one workspace's people, with the same acts, and the add form for it
    GET  /ops/spending                      the coding runs' estimated cost by day, workspace and document
    GET  /ops/activity                      every audit event of every workspace, newest first (workspace and kind filters)
    GET  /ops/activity/sign-ins             every sign-in attempt, newest first

What it never does:
- change an operator's account (an account holding a grant no revocation ended): such accounts are listed, and every act
  on one is refused - operator access is granted and ended on the server only (CORE-UX-DESIGN.md 5, studio.operator);
- delete a record: access off is the account's is_active, and its memberships, records and history stay. What it does
  delete is sign-in state: access off and a password reset end every stored session of the person at once, so an open
  session can never come back (refutation r1, gate-1);
- show, log, audit or redirect with a password: a password is generated here (secrets), checked against the site's
  password validators, stored only as its hash, and answered once, in the page that answers the POST that made it. A
  sign-in attempt's name is shown only when it is an account's username: a name that is none can be a password typed in
  the wrong box (refutation r1, data-3).

Every act is audited in the workspace it concerns, with ids, values and counts and never a password:
operator.member_added, operator.role_changed, operator.password_reset, operator.access_off, operator.access_on,
operator.workspace_created. Those rows name no encounter, so the customer's activity (studio.customer.activity_json, an
encounter's own events) never shows them. Adding a person and creating a workspace take provisioning's own lock
(studio/management/commands/provision.py PROVISION_LOCK), so a console act and a provisioning run never interleave, and a
new workspace's name is Latin letters, digits and a few marks, stored exactly as typed, follows provisioning's rules, and
reads alike no other workspace's.
"""
from __future__ import annotations

import importlib
import re
import secrets
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import ROUND_HALF_UP, Context, Decimal, InvalidOperation, Overflow, localcontext

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from . import audit, jobs, models, read_audit, security_events, spend
from .fable import pricing
from .management.commands import provision
from .operator import _methods as methods
from .operator import _see_other as see_other
from .operator import operator_view
# release 1, B2 step 5: the acts that change who can see what ask for the key again (studio.second_factor)
from .second_factor import requires_recent_second_factor
# end_sessions, the refusal it answers and the stores it can end live in studio.sessions (release 1, RELEASE-1-SPEC
# 3.3), so every lane can end sessions without the console; imported back, so console.end_sessions and console.Refused
# are those
from .sessions import NO_SESSION_STORE, SESSION_STORES, Refused, end_sessions  # noqa: F401 (re-exported)

User, Membership, Workspace, Category, Run = (models.User, models.Membership, models.Workspace, models.Category,
                                              models.ProviderRun)

ROLES = dict(Membership.ROLES)  # owner -> Owner, reviewer -> Reviewer, viewer -> Viewer, in that order
USERNAME_RE = re.compile(r'[a-z0-9][a-z0-9._-]{2,39}')
USERNAME_RULE = ('A username is 3 to 40 characters: lowercase letters, digits, dots, hyphens or underscores, starting '
                 'with a letter or a digit.')
NAME_CHARS = 120  # User.display_name and Workspace.name hold 120
# Characters a name may not hold: controls, format characters (zero-width spaces and joiners, direction marks),
# surrogates, private-use and unassigned code points, line and paragraph separators (refutation r1, data-4).
HIDDEN_CATEGORIES = {'Cc', 'Cf', 'Cs', 'Co', 'Cn', 'Zl', 'Zp'}
# and Unicode's Default_Ignorable_Code_Point characters in other categories - the Hangul fillers (letters that show nothing),
# the combining grapheme joiner, the variation selectors - with every range of the property (refutation r2, secure-3)
IGNORABLE_RANGES = (('\u00ad', '\u00ad'), ('\u034f', '\u034f'), ('\u061c', '\u061c'), ('\u115f', '\u1160'),
                    ('\u17b4', '\u17b5'), ('\u180b', '\u180f'), ('\u200b', '\u200f'), ('\u202a', '\u202e'),
                    ('\u2060', '\u206f'), ('\u3164', '\u3164'), ('\ufe00', '\ufe0f'), ('\ufeff', '\ufeff'),
                    ('\uffa0', '\uffa0'), ('\ufff0', '\ufff8'), ('\U0001bca0', '\U0001bca3'),
                    ('\U0001d173', '\U0001d17a'), ('\U000e0000', '\U000e0fff'))
# glyphs that draw nothing and are no white space (refutation r3, r3-6)
BLANK_GLYPHS = {'\u2800', '\U0001d159', '\ufffc'}
PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  # no 0/o, 1/l/i: it is read aloud or copied by hand
PASSWORD_GROUPS, PASSWORD_GROUP_CHARS = 4, 5  # 20 random characters (about 99 bits) in four groups
PAGE_SIZE = 100
SPENDING_DAYS = 30
TOP_DOCUMENTS = 50
OPERATOR_ACCOUNT = 'This is an operator account. Operator accounts are managed on the server, not here.'
NO_WORKSPACE = 'This account belongs to no workspace. It is managed on the server, not here.'
AGENT_OWNER = 'An automated agent can be a Reviewer or a Viewer, not an Owner.'
DONE = {
    'role': 'The role was changed.', 'same-role': 'The role was already that one: nothing changed.',
    'off': ('Access to this workspace was turned off. The person no longer reaches its documents, and if it was their '
            'only workspace every open session has ended.'),
    'on': 'Access to this workspace was turned on again.',
    'off-everywhere': 'Access was turned off everywhere. The person can no longer sign in, and every open session has ended.',
    'on-everywhere': ('Access was turned on again. The person signs in again with their password; no earlier session '
                      'comes back.'),
    'same-access': 'Access was already that way: nothing changed.',
    'created': 'The workspace was created. Add its people below.',
    'unlocked': 'The sign-in delay was cleared. The person can sign in again at once.',
}
# Release 1, C3 (ADM-14 (7)): every act that changes access asks who at the practice requested it - the practice's
# contact or a ticket reference, never patient details - and stores it on the act's audit row.
REQUESTED_BY_CHARS = 120
ACCESS_SCOPES = ('practice', 'everywhere')  # C4 item 4: the per-practice switch by default; "everywhere" apart
# The activity log's kinds (GET /ops/activity?kind=...): each a set of audit event names, or a prefix.
KINDS = {
    'documents': ('Documents added', ('encounter.created',)),
    # provider.counting (release 1, D4: Lane 4's record of a token count, before each send) belongs to the coding view
    'coding': ('Coding reviews', ('coding.round_queued', 'coding.round_done', 'coding.round_failed', 'pipeline.stopped',
                                  'pipeline.resumed', 'provider.counting', 'provider.sending', 'provider.finished',
                                  'provider.count_failed', 'provider.reconciled')),
    'decisions': ('Approvals and rejections', ('decision.recorded',)),
    'answers': ('Answers', ('answers.recorded',)),
    'downloads': ('Reports made', ('export.created',)),
    'operator': ('Operator acts', 'operator.'),
    'team': ("Owners' team changes", 'member.'),
}
EVENT_LABELS = {
    'encounter.created': 'Document added',
    'coding.round_queued': 'Coding review queued',
    'coding.round_done': 'Coding review finished',
    'coding.round_failed': 'Coding review could not finish',
    'pipeline.stopped': 'Stopped',
    'pipeline.resumed': 'Resumed',
    'provider.counting': 'Token count requested',
    'provider.sending': 'Coding request sent',
    'provider.finished': 'Coding request ended',
    'provider.count_failed': 'Token count failed',
    'provider.reconciled': 'Unknown run reconciled',
    'answers.recorded': 'Answers sent',
    'export.created': 'Report made',
    'operator.viewed': 'Record viewed by an operator',
    'operator.member_added': 'Person added',
    'operator.role_changed': 'Role changed',
    'operator.password_reset': 'Password reset',
    'operator.access_off': 'Access turned off',
    'operator.access_on': 'Access turned on',
    'operator.workspace_created': 'Workspace created',
    'operator.signin_cleared': 'Sign-in delay cleared',
    # release 1: the practice's own acts (C4) and a report asked for again (C5)
    'member.access_off': 'Access turned off by an owner',
    'member.access_on': 'Access turned on by an owner',
    'export.reused': 'Report asked for again (the stored copy)',
    'account.provisioned': 'Account set up on the server',
    # the earlier pipeline's events (ARCHITECTURE.md 5.11: its records stay and are shown as they are)
    'assessment.created': 'Review made (earlier version)',
    'assessment.recompute_queued': 'Review recompute queued (earlier version)',
    'assessment.refreshed': 'Review refreshed (earlier version)',
    'context.changed': 'Document details changed (earlier version)',
    'detail.answered': 'Question answered (earlier version)',
    'detail.revoked': 'Answer withdrawn (earlier version)',
    'provider.reused': 'Earlier answer reused (earlier version)',
    'provider.second_review_requested': 'Second review requested (earlier version)',
    'report.generated': 'Report made (earlier version)',
    'revision.addendum': 'Addendum added (earlier version)',
    'revision.extracted': 'Document text read (earlier version)',
}
DECISION_LABELS = {models.CodeDecision.APPROVE: 'Approved', models.CodeDecision.REJECT: 'Rejected',
                   models.CodeDecision.REVOKE: 'Decision undone'}
# The event data shown beside an event, in this order, by name (ids are kept for the operator's record elsewhere). No
# line and no code (release 1 repair round 1, bypass-0 and phileak-3): a decision's code and line - and an earlier
# version's answered detail's code - are the document's content, which its own page shows only with a content grant
# (studio.operator, C2), and this list is every practice's, read with no reason.
DETAIL_KEYS = ('number', 'kind', 'fmt', 'count', 'purpose', 'state', 'username', 'role', 'from', 'to', 'name', 'category',
               'view', 'scope', 'sessions_ended', 'requested_by', 'by')


# --- reading -------------------------------------------------------------------------------------------------------

def operator_ids() -> set:
    """The ids of every account holding a grant that no revocation ended (studio.operator.is_operator's own reading)."""
    return set(models.OperatorGrant.objects.filter(revocation__isnull=True).values_list('user_id', flat=True))


def membership_rows(queryset, operators) -> list:
    """One row per membership, with the roles its form offers: an automated agent is never offered Owner (unless it
    already is one), as set_role refuses it (refutation r1, data-7)."""
    rows = []
    for item in queryset.select_related('user', 'workspace', 'workspace__category').order_by(
            'workspace__name', 'workspace_id', 'user__username', 'pk'):
        rows.append({'membership': item, 'person': item.user, 'workspace': item.workspace,
                     'role_label': ROLES.get(item.role, item.role), 'operator': item.user_id in operators,
                     'roles': [(value, label) for value, label in Membership.ROLES
                               if not (item.user.actor_kind == User.AGENT and value == Membership.OWNER)
                               or item.role == value]})
    return rows


def _context(section, **values) -> dict:
    """Every console page's context: the release, the roles, the section the navigation marks, and the notice slots
    (named, so a page never looks a missing one up - refutation r1, data-6, restyle-3, restyle-4)."""
    return {'release': settings.RELEASE_SHA, 'roles': list(Membership.ROLES), 'section': section, 'error': None,
            'done': None, **values}


def _people_context(**extra) -> dict:
    operators = operator_ids()
    members = set(Membership.objects.values_list('user_id', flat=True))
    return _context(
        'people',
        rows=membership_rows(Membership.objects.all(), operators),
        unplaced=list(User.objects.exclude(pk__in=members).exclude(pk__in=operators).order_by('username')),
        operators=operator_rows(),
        # the add form's choice: open practices only (a closed one drops out of the routine lists, D1 step 1)
        workspaces=list(Workspace.objects.filter(closed_at__isnull=True).select_related('category').order_by('name', 'pk')),
        **extra)


def operator_rows(today=None) -> list:
    """The Operators card (release 1, C3 item 4; ADM-8): every grant no revocation ended, with the approval it rests on
    and its review date - flagged when the date has passed or none was recorded (a grant made before release 1), for
    the periodic access review - and an automated account flagged as holding no power (is_operator refuses it)."""
    today = today or timezone.localdate()
    rows = []
    for grant_row in (models.OperatorGrant.objects.filter(revocation__isnull=True).select_related('user')
                      .order_by('created_at', 'pk')):
        rows.append({'person': grant_row.user, 'since': grant_row.created_at, 'granted_by': grant_row.granted_by,
                     'authorization_ref': grant_row.authorization_ref, 'review_by': grant_row.review_by,
                     'overdue': grant_row.review_by is not None and grant_row.review_by < today,
                     'unreviewed': grant_row.review_by is None or not grant_row.authorization_ref,
                     'automated': grant_row.user.actor_kind != User.HUMAN})
    return rows


def _workspace_context(workspace, **extra) -> dict:
    return _context('workspaces', workspace=workspace, rows=membership_rows(workspace.memberships.all(), operator_ids()),
                    documents=workspace.encounters.filter(destroyed_at__isnull=True).count(), **extra)


def _workspace(workspace_id):
    try:
        return Workspace.objects.select_related('category').get(pk=workspace_id)
    except (Workspace.DoesNotExist, ValueError, TypeError, ValidationError):
        raise Http404()


def _person(user_id):
    try:
        return User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError, ValidationError):
        raise Http404()


# --- the acts' parts -------------------------------------------------------------------------------------------------

def hidden(ch) -> bool:
    """Whether ``ch`` cannot be seen or typed: a control, format, surrogate, private-use, unassigned or separator character,
    a default-ignorable one or a blank glyph (HIDDEN_CATEGORIES, IGNORABLE_RANGES, BLANK_GLYPHS)."""
    return (unicodedata.category(ch) in HIDDEN_CATEGORIES or ch in BLANK_GLYPHS
            or any(low <= ch <= high for low, high in IGNORABLE_RANGES))


def hidden_in(value: str) -> bool:
    """Whether ``value`` holds a character that cannot be seen or typed (tabs and line breaks aside: they are white space).
    Every default-ignorable character is refused, the variation selectors included: one between a letter and its accent
    would split a name that draws the same into two readings (refutation r4, r4-1, r4-3). A name with an emoji's
    presentation mark or an ideographic variant is written without it (a written limit)."""
    return any(hidden(ch) for ch in value if ch not in '\t\n\r')


def _field(request, name, *, limit=NAME_CHARS, required=False, label='This field', form='NFC') -> str:
    """A text field as stored, in Unicode NFC (a decomposed spelling and its composed one are one spelling; what the
    operator typed is otherwise kept: refutation r3, r3-7), runs of white space made one space, ends stripped; refused
    when it holds a character no one can see or type (hidden_in), when it is too long, when a required one is empty, or
    when it holds no letter or digit at all (refutation r1, data-4; r2, secure-3). A workspace name has further rules
    (plain_name_problem)."""
    value = request.POST.get(name, '')
    if not isinstance(value, str):
        value = ''
    if hidden_in(value):
        raise Refused(f'{label} contains a character that cannot be seen or typed (a control, format, filler or '
                      f'unassigned character).')
    value = ' '.join(unicodedata.normalize(form, value).split())
    if hidden_in(value):
        raise Refused(f'{label} contains a character that cannot be seen or typed (a control, format, filler or '
                      f'unassigned character).')
    if len(value) > limit:
        raise Refused(f'{label} can be at most {limit:,} characters.')
    if required and not value:
        raise Refused(f'{label} is required.')
    if value and not any(ch.isalnum() for ch in value):
        raise Refused(f'{label} needs at least one letter or digit.')
    return value


def _requested_by(request) -> str:
    """Who at the practice asked for an act that changes access (release 1, C3; ADM-14 (7)): the practice's contact or a
    ticket reference, required, as _field stores a name - never patient details, which the form says."""
    return _field(request, 'requested_by', limit=REQUESTED_BY_CHARS, required=True, label='Requested by')


def new_password(user) -> str:
    """A password for ``user`` from the secrets module, in four groups of five unambiguous characters, that the site's
    password validators accept for this account."""
    for _ in range(20):
        candidate = '-'.join(''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_GROUP_CHARS))
                             for _ in range(PASSWORD_GROUPS))
        try:
            validate_password(candidate, user)
        except ValidationError:
            continue
        return candidate
    raise RuntimeError('No generated password passed the password validators.')


def _lock():
    """Provisioning's own transaction-level advisory lock: a console act that adds an account or a workspace never
    interleaves with another such act or with a provisioning run (refutation r1, data-2)."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [provision.PROVISION_LOCK])


def _changeable(user, operators=None) -> list:
    """The memberships of ``user`` an act may touch, refused for an operator's account or one with no workspace."""
    operators = operator_ids() if operators is None else operators
    if user.pk in operators:
        raise Refused(OPERATOR_ACCOUNT, 409)
    memberships = list(user.memberships.select_related('workspace').order_by('created_at', 'pk'))
    if not memberships:
        raise Refused(NO_WORKSPACE, 409)
    return memberships


def _back(request, memberships=()):
    """Where an act's answer returns: the workspace page it came from (one the person belongs to), else People."""
    wanted = request.POST.get('back', '')
    for item in memberships:
        if wanted == str(item.workspace_id):
            return f'/ops/workspaces/{item.workspace_id}', item.workspace
    return '/ops/people', None


def _refused(request, exc, workspace=None):
    if workspace is not None:
        read_audit.record(request, view=read_audit.OPS_WORKSPACE, workspace_id=workspace.pk)  # C1, as workspace_page
        return render(request, 'studio/ops_workspace.html', _workspace_context(workspace, error=str(exc)),
                      status=exc.status)
    return render(request, 'studio/ops_people.html', _people_context(error=str(exc)), status=exc.status)


def _password_page(request, person, workspace, made, password):
    """The one answer that shows a password: the POST's own response (never a redirect or a URL), no-store like every
    console page (studio.access.SecurityHeadersMiddleware)."""
    return render(request, 'studio/ops_password.html',
                  _context('workspaces' if workspace is not None else 'people', person=person, workspace=workspace,
                           made=made, password=password,
                           change_hours=settings.STAFF_PASSWORD_UNUSED_SECONDS // 3600))  # release 1, B4 step 5


def _workspaces_of(memberships) -> list:
    """The distinct workspaces of ``memberships``, in their order: an act on a person is audited once in each."""
    return list({item.workspace_id: item.workspace for item in memberships}.values())


# --- people ------------------------------------------------------------------------------------------------------------

@operator_view
@methods('GET')
def people(request):
    return render(request, 'studio/ops_people.html', _people_context(done=DONE.get(request.GET.get('done', ''))))


@operator_view
@methods('POST')
@requires_recent_second_factor()
def add_person(request):
    """A new person: an account (human) in one workspace with a role, its password generated and answered once - to be
    replaced by the person at the first sign-in, within STAFF_PASSWORD_UNUSED_SECONDS (release 1, B4:
    password_change_required_at starts the clock). Who at the practice asked for it is required and recorded (C3)."""
    workspace, came_from = None, None
    try:
        try:
            workspace = Workspace.objects.select_related('category').get(pk=request.POST.get('workspace', ''))
        except (Workspace.DoesNotExist, ValueError, TypeError, ValidationError):
            raise Refused('Choose the workspace the person works in.')
        came_from = workspace if request.POST.get('back', '') == str(workspace.pk) else None
        requested_by = _requested_by(request)
        username = request.POST.get('username', '')
        username = username.strip() if isinstance(username, str) else ''
        if not username:
            raise Refused('The username is required.')
        if not USERNAME_RE.fullmatch(username):
            raise Refused(USERNAME_RULE)
        name = _field(request, 'name', label='The name')
        role = request.POST.get('role', '')
        if role not in ROLES:
            raise Refused('Choose a role: Owner, Reviewer or Viewer.')
        person = User(username=username, display_name=name, actor_kind=User.HUMAN,
                      password_change_required_at=timezone.now())
        password = new_password(person)
        person.set_password(password)
        try:
            with transaction.atomic():
                _lock()
                if User.objects.filter(username__iexact=username).exists():
                    raise Refused('That username is taken. Choose another.', 409)
                person.save()
                Membership.objects.create(user=person, workspace=workspace, role=role)
                audit.record(workspace, 'operator.member_added', actor=request.user, user=str(person.pk),
                             username=username, role=role, requested_by=requested_by)
        except IntegrityError:
            raise Refused('That username is taken. Choose another.', 409)
    except Refused as exc:
        return _refused(request, exc, came_from)
    return _password_page(request, person, came_from, 'added', password)


@operator_view
@methods('POST')
@requires_recent_second_factor()
def reset_password(request, user_id):
    """A new password for the person, generated and answered once, to be replaced at the first sign-in within
    STAFF_PASSWORD_UNUSED_SECONDS (release 1, B4: a reset starts a new clock); every stored session of theirs is ended.
    Who at the practice asked for it is required and recorded (C3)."""
    person = _person(user_id)
    memberships = []
    try:
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
            requested_by = _requested_by(request)
            password = new_password(person)
            person.set_password(password)
            person.password_change_required_at = timezone.now()
            person.save(update_fields=['password', 'password_change_required_at'])
            ended = end_sessions(person)
            for workspace in _workspaces_of(memberships):
                audit.record(workspace, 'operator.password_reset', actor=request.user, user=str(person.pk),
                             username=person.username, sessions_ended=ended, requested_by=requested_by)
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return _password_page(request, person, _back(request, memberships)[1], 'reset', password)


@operator_view
@methods('POST')
@requires_recent_second_factor()
def set_role(request, user_id):
    """The role of one of the person's memberships (owner, reviewer or viewer; an automated agent is never made an owner:
    provisioning keeps a workspace's owner a human - refutation r1, data-7). Who at the practice asked for it is required
    and recorded (C3)."""
    person = _person(user_id)
    memberships = []
    try:
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
            requested_by = _requested_by(request)
            target = next((item for item in memberships if str(item.pk) == request.POST.get('membership', '')), None)
            if target is None:
                raise Refused('That workspace membership is not this person\'s.', 404)
            role = request.POST.get('role', '')
            if role not in ROLES:
                raise Refused('Choose a role: Owner, Reviewer or Viewer.')
            if role == Membership.OWNER and person.actor_kind == User.AGENT and target.role != role:
                raise Refused(AGENT_OWNER)
            if target.role == role:
                done = 'same-role'
            else:
                previous = target.role
                Membership.objects.filter(pk=target.pk).update(role=role)
                audit.record(target.workspace, 'operator.role_changed', actor=request.user, user=str(person.pk),
                             username=person.username, requested_by=requested_by, **{'from': previous, 'to': role})
                done = 'role'
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return see_other(f'{_back(request, memberships)[0]}?done={done}')


@operator_view
@methods('POST')
@requires_recent_second_factor()
def set_access(request, user_id):
    """The person's access to one workspace off or on - by default, the membership's own switch (release 1, C4 item 4:
    this practice only; when the person then holds no other active membership, every stored session of theirs ends) -
    or, with scope everywhere, the account's (is_active: sign-in refused, and every stored session of theirs ended at
    once; on again, they sign in with their password). Who at the practice asked for it is required and recorded (C3).
    Nothing is deleted but sign-in state."""
    person = _person(user_id)
    memberships = []
    try:
        wanted = request.POST.get('access', '')
        if wanted not in ('off', 'on'):
            raise Refused('Choose whether access is turned off or on.')
        scope = request.POST.get('scope', '') or ACCESS_SCOPES[0]
        if scope not in ACCESS_SCOPES:
            raise Refused('Choose whether access changes in this workspace or everywhere.')
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
            requested_by = _requested_by(request)
            active = wanted == 'on'
            if scope == 'everywhere':
                done = _set_account_access(request, person, memberships, active, requested_by)
            else:
                target = next((item for item in memberships if str(item.pk) == request.POST.get('membership', '')), None)
                if target is None:
                    raise Refused('That workspace membership is not this person\'s.', 404)
                done = _set_membership_access(request, person, memberships, target, active, requested_by)
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return see_other(f'{_back(request, memberships)[0]}?done={done}')


def _set_membership_access(request, person, memberships, target, active, requested_by) -> str:
    """One membership's access (Membership.active), audited in its workspace; every session of the person ends when
    access goes off and no other active membership is left. The notice's key."""
    if target.active == active:
        return 'same-access'
    Membership.objects.filter(pk=target.pk).update(active=active)
    others = any(item.active and item.pk != target.pk for item in memberships)
    values = {'sessions_ended': end_sessions(person)} if not active and not others else {}
    wanted = 'on' if active else 'off'
    audit.record(target.workspace, f'operator.access_{wanted}', actor=request.user, user=str(person.pk),
                 username=person.username, scope='practice', membership=str(target.pk), requested_by=requested_by,
                 **values)
    return wanted


def _set_account_access(request, person, memberships, active, requested_by) -> str:
    """The account's own access (is_active), audited in each of its workspaces; every session ends both ways: off, so
    none goes on; on, so none made by a sign-in that raced the off act (it read the account active before the act
    committed) comes back (refutation r2, secure-1). The notice's key."""
    if person.is_active == active:
        return 'same-access'
    values = {'sessions_ended': end_sessions(person)}
    person.is_active = active
    person.save(update_fields=['is_active'])
    wanted = 'on' if active else 'off'
    for workspace in _workspaces_of(memberships):
        audit.record(workspace, f'operator.access_{wanted}', actor=request.user, user=str(person.pk),
                     username=person.username, scope='everywhere', requested_by=requested_by, **values)
    return f'{wanted}-everywhere'


# --- workspaces --------------------------------------------------------------------------------------------------------

def _workspaces_context(**extra) -> dict:
    """The practices, open ones first and the closed ones apart (release 1, D1 step 1: a closed practice drops out of
    the routine lists; its people keep reading until it confirms receipt), with their counts; a destroyed document's
    tombstone is not counted."""
    rows = list(Workspace.objects.select_related('category')
                .annotate(people=Count('memberships', distinct=True),
                          active_people=Count('memberships', distinct=True,
                                              filter=Q(memberships__active=True, memberships__user__is_active=True)),
                          documents=Count('encounters', distinct=True,
                                          filter=Q(encounters__destroyed_at__isnull=True)))
                .order_by('name', 'pk'))
    return _context('workspaces', workspaces=[row for row in rows if row.closed_at is None],
                    closed=[row for row in rows if row.closed_at is not None],
                    categories=list(Category.objects.order_by('name', 'pk')), **extra)


# Latin letters whose Unicode name gives no single base letter, read as the letters they stand for
LETTER_FOLDS = {'\u00e6': 'ae', '\u00f0': 'd', '\u00fe': 'th', '\u0153': 'oe'}


def base_letter(ch: str) -> str:
    """A Latin letter read as the base letter its Unicode name gives - 'LATIN SMALL LETTER D WITH STROKE' reads d,
    'LATIN SMALL LETTER DOTLESS I' reads i, 'LATIN LETTER SMALL CAPITAL K' reads k - or as the letters it stands for
    (LETTER_FOLDS); any other character as itself."""
    if ch in LETTER_FOLDS:
        return LETTER_FOLDS[ch]
    words = unicodedata.name(ch, '').split(' WITH ')[0].split()
    if len(words) > 2 and words[0] == 'LATIN' and len(words[-1]) == 1 and words[-1].isalpha():
        return words[-1].lower()
    return ch


def _without_marks(text: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text) if not unicodedata.category(ch).startswith('M'))


def name_reading(name: str) -> str:
    """How two workspace names are compared (refutations r2-r7): every mark dropped (NFKD) before case folding and after
    it, so no mark becomes a letter (r7-1: case folding turns COMBINING GREEK YPOGEGRAMMENI into an iota); then letters
    and digits only, a modifier letter (Unicode category Lm: an apostrophe, okina, prime or spacing accent written as a
    letter) set aside with the punctuation (r7-1); each Latin letter read as its base letter (base_letter). So
    'Caf\u00e9', 'CAFE' and 'Cafe\u0301' read alike, as do '\u00d8rsted' and 'O\u0338rsted', '\u00d0akovo' and
    '\u0110akovo', or "Hawai'i" and 'Hawai\u02bbi'. Look-alike letters of other scripts are not compared (a written limit,
    as provisioning's own)."""
    folded = _without_marks(_without_marks(name).casefold())
    return ''.join(base_letter(ch) for ch in folded
                   if unicodedata.category(ch)[0] in 'LN' and unicodedata.category(ch) != 'Lm')


# A workspace name's characters (refutations r2-r7): Latin letters - the basic ones, the accented letters of Latin-1
# (\u00c0 to \u00ff, the multiplication and division signs aside) and the other Western European ones (EXTRA_LETTERS:
# the French, Welsh and Windows-1252 letters Latin-1 lacks; r7-3), so the set holds each of its letters in both cases -
# digits, single spaces and a few marks, the typographic apostrophes among them. Every look-alike pair the rounds found
# (other scripts, styled letters, accents typed apart, letters of one script that draw alike, right-to-left order) lies
# outside this set; within it every letter reads as a plain one (name_reading), and a name is stored exactly as typed,
# the text provisioning finds a workspace by. Names in other scripts, and other Latin letters, are a written limit.
EXTRA_LETTERS = '\u0152\u0153\u0160\u0161\u017d\u017e\u0178\u0174\u0175\u0176\u0177'
NAME_PUNCTUATION = " .,'\u2018\u2019&-/()"
CHARACTERS_SENTENCE = ("A workspace name uses Latin letters, with the accents of Western European languages (such as "
                       "\u00e9, \u00fc, \u00f1 or \u00f8), digits, spaces and . , ' & - / ( ) only. Type them from the "
                       "keyboard: a look-alike pasted from elsewhere is refused.")
SPACING_SENTENCE = ('Type the workspace name with single spaces between words, no space at either end, and each accented '
                    'letter as one character.')


def name_character_allowed(ch: str) -> bool:
    return ((ch.isascii() and ch.isalnum()) or ch in NAME_PUNCTUATION or ch in EXTRA_LETTERS
            or ('\u00c0' <= ch <= '\u00ff' and ch not in '\u00d7\u00f7'))


def plain_name_problem(name: str, typed: str) -> str:
    """Why ``typed`` cannot name a workspace, or nothing. Its characters first (r7-2): each typed character must be one
    name_character_allowed accepts, white space, or an accent typed apart, and what NFC composes from them must be
    accepted characters or white space - else the characters sentence. Then it must be stored exactly as typed
    (``name`` is _field's stored form) - else the spacing sentence: a run of spaces, a space at an end, other white space
    or an accent typed apart from its letter."""
    if (any(not (name_character_allowed(ch) or ch.isspace() or unicodedata.category(ch).startswith('M')) for ch in typed)
            or not all(name_character_allowed(ch) or ch.isspace() for ch in unicodedata.normalize('NFC', typed))):
        return CHARACTERS_SENTENCE
    if typed != name:
        return SPACING_SENTENCE
    return ''


def workspace_name_problem(name: str, category) -> str:
    """Why a new workspace cannot take ``name`` (already through plain_name_problem), or nothing. Provisioning's rules,
    read the console's one way (name_reading: case, accents and modifier letters aside, letters and digits), which makes
    them stricter (refutation r3, r3-2, r3-8): it names no other specialty (provision.SPECIALTIES), and no workspace of
    ANY specialty reads alike - which covers provisioning's rule that no workspace of another specialty has it exactly -
    so no two workspaces are told apart only by case, accents, spacing or punctuation (refutation r1, data-2, data-4,
    data-5; r2, secure-2; r6; r7)."""
    reading = name_reading(name)
    if not reading:
        return 'A workspace name needs at least one letter or digit.'
    # another specialty's name, by either reading of the stored name, the console's and provisioning's (r4, r4-2; r5,
    # r5-3); the stored name is exactly what was typed (plain_name_problem)
    readings = {reading, provision._read(name)} - {''}
    for other, (other_name, _) in provision.SPECIALTIES.items():
        if other != category.slug and readings & {name_reading(other_name), provision._read(other_name)}:
            return f'{name!r} names the {other_name} specialty, and this workspace is {category.name}.'
    alike = sorted((each.name, each.category.name) for each in Workspace.objects.select_related('category')
                   if name_reading(each.name) == reading)
    if alike:
        return ('A workspace with that name exists: ' + ', '.join(f'{other!r} ({specialty})' for other, specialty in alike)
                + '. Choose another name.')
    return ''


@operator_view
@methods('GET')
def workspaces(request):
    return render(request, 'studio/ops_workspaces.html', _workspaces_context())


@operator_view
@methods('POST')
@requires_recent_second_factor()
def create_workspace(request):
    """A workspace for a specialty that exists (a Category row: what the page and the report show it as). Who asked for
    it is required and recorded (release 1, C3)."""
    try:
        requested_by = _requested_by(request)
        name = _field(request, 'name', required=True, label='The workspace name')
        typed = request.POST.get('name', '')
        plain = plain_name_problem(name, typed if isinstance(typed, str) else '')
        if plain:
            raise Refused(plain)
        try:
            category = Category.objects.get(pk=request.POST.get('category', ''))
        except (Category.DoesNotExist, ValueError, TypeError, ValidationError):
            raise Refused('Choose the specialty of the workspace.')
        with transaction.atomic():
            _lock()
            problem = workspace_name_problem(name, category)
            if problem:
                raise Refused(problem, 409)
            workspace = Workspace.objects.create(name=name, category=category)
            audit.record(workspace, 'operator.workspace_created', actor=request.user, name=name,
                         category=category.slug, requested_by=requested_by)
    except Refused as exc:
        return render(request, 'studio/ops_workspaces.html', _workspaces_context(error=str(exc)), status=exc.status)
    return see_other(f'/ops/workspaces/{workspace.pk}?done=created')


@operator_view
@methods('GET')
@read_audit.phi_read(read_audit.OPS_WORKSPACE)
def workspace_page(request, workspace_id):
    """One practice's page: its people, with the acts on them, and the add form - recorded as ops.workspace."""
    workspace = _workspace(workspace_id)
    read_audit.record(request, view=read_audit.OPS_WORKSPACE, workspace_id=workspace.pk)
    return render(request, 'studio/ops_workspace.html',
                  _workspace_context(workspace, done=DONE.get(request.GET.get('done', ''))))


# --- spending ----------------------------------------------------------------------------------------------------------

CENT = Decimal('0.01')
WIDE = Context(prec=60)
IN_FLIGHT = {Run.SENDING, Run.UNKNOWN}


def dollars(amount) -> str:
    """An estimate to the cent, for reading at a glance (the exact figures are on each document's page); never an error,
    whatever a stored figure holds (refutation r1, money-7; r2, figures-2)."""
    amount = Decimal(amount)
    if not amount.is_finite():
        return 'not known'
    try:
        return f'{amount.quantize(CENT, rounding=ROUND_HALF_UP, context=WIDE):,.2f}'
    except InvalidOperation:
        return f'{amount:.3E}'


def _bucket():
    return {'runs': 0, 'cost': Decimal(0), 'unpriced': 0, 'worst': Decimal(0)}


def _add(bucket, spent):
    cost, reserve = spent
    bucket['runs'] += 1
    if cost is None:
        bucket['unpriced'] += 1
        bucket['worst'] += reserve
    else:
        bucket['cost'] += cost


def _shown(bucket) -> dict:
    return {**bucket, 'cost_text': dollars(bucket['cost']), 'worst_text': dollars(bucket['worst'])}


def spending(now=None) -> dict:
    """Every coding run (the reader's and the checker's: jobs.PURPOSES) that was sent, is being sent or has an unknown
    outcome, its known cost or its worst case (studio.spend.run_spend, the reading every console page shares), summed by
    day (UTC, the day it was sent), workspace and document. A run whose cost is not known is counted apart, never as
    zero."""
    now = now or timezone.now()
    first_day = now.astimezone(dt_timezone.utc).date() - timedelta(days=SPENDING_DAYS - 1)
    runs = (Run.objects.filter(Q(sent=True) | Q(state__in=IN_FLIGHT), purpose__in=jobs.PURPOSES)
            .select_related('encounter', 'encounter__workspace', 'encounter__workspace__category')
            # the document by its id alone: no title is read (release 1, C2), the page names it by its reference
            .only('id', 'usage', 'scope', 'state', 'http_status', 'sent', 'endpoint', 'created_at', 'started_at', 'encounter',
                  'encounter__destroyed_at', 'encounter__workspace', 'encounter__workspace__name',
                  'encounter__workspace__category', 'encounter__workspace__category__name')
            .order_by('created_at', 'pk'))
    total, recent = _bucket(), _bucket()
    days, workspaces_seen, documents = {}, {}, {}
    # sums that never raise: an absurd stored figure becomes Infinity, which dollars() shows as not known (r2, figures-2)
    with localcontext(WIDE) as context:
        context.traps[Overflow] = False
        context.traps[InvalidOperation] = False
        for run in runs.iterator(chunk_size=500):
            spent = spend.run_spend(run)
            day = (run.started_at or run.created_at).astimezone(dt_timezone.utc).date()
            _add(total, spent)
            if day >= first_day:
                _add(recent, spent)
                _add(days.setdefault(day, _bucket()), spent)
            workspace = run.encounter.workspace
            entry = workspaces_seen.setdefault(workspace.pk, {'workspace': workspace, 'documents': set(), **_bucket()})
            entry['documents'].add(run.encounter_id)
            _add(entry, spent)
            if run.encounter.destroyed_at is None:  # a disposal's tombstone is never listed (D1)
                _add(documents.setdefault(run.encounter_id, {'encounter': run.encounter,
                                                              'reference': str(run.encounter_id)[:8], **_bucket()}), spent)
        # the most each document may have cost first: its known cost and the worst case of its runs with no known cost
        # (money-4; the page shows both parts on each row: r2, figures-3)
        by_document = sorted(documents.values(), key=lambda item: (-(item['cost'] + item['worst']), -item['unpriced'],
                                                                   str(item['encounter'].pk)))
        by_workspace = sorted(workspaces_seen.values(), key=lambda item: (-(item['cost'] + item['worst']),
                                                                          item['workspace'].name))
    other = Run.objects.filter(sent=True).exclude(purpose__in=jobs.PURPOSES).count()
    return {
        'total': _shown(total), 'recent': _shown(recent), 'days_window': SPENDING_DAYS,
        'days': [{'day': day, **_shown(days[day])} for day in sorted(days, reverse=True)],
        'workspaces': [{**_shown(entry), 'documents': len(entry['documents'])} for entry in by_workspace],
        'documents': [_shown(item) for item in by_document[:TOP_DOCUMENTS]], 'documents_total': len(by_document),
        'top_documents': TOP_DOCUMENTS, 'other_runs': other,
        'ceiling': dollars(jobs.ceiling_usd()), 'concurrent': settings.CONCURRENT_DOCUMENTS,
        'exact_total': pricing.usd(total['cost']),
    }


@operator_view
@methods('GET')
@read_audit.phi_read(read_audit.OPS_SPENDING)
def spending_page(request):
    """The coding runs' estimated cost by day, practice and document - recorded as ops.spending with the documents
    shown."""
    figures = spending()
    shown = [item['encounter'].pk for item in figures['documents']]
    read_audit.record(request, view=read_audit.OPS_SPENDING, encounter_ids=shown, count=len(shown))
    return render(request, 'studio/ops_spending.html', _context('spending', **figures))


# --- activity ----------------------------------------------------------------------------------------------------------
# Pages are read by position (keyset), not by number: "older" names the last row shown, and the next page holds the rows
# strictly older than it, so rows arriving meanwhile never repeat a row or skip one (refutation r1, money-6).

CURSOR_RE = re.compile(r'(\d{8}T\d{6}\.\d{6}Z)~([0-9a-f-]{1,36})')


def cursor_of(row) -> str:
    return f'{row.created_at.astimezone(dt_timezone.utc):%Y%m%dT%H%M%S.%fZ}~{row.pk}'


def _older_than(queryset, request, *, integer_pk=False):
    """(``queryset`` limited to the rows older than the request's ``before`` cursor, the cursor); the whole queryset
    with no cursor (the newest page); (None, '') when the cursor cannot be read."""
    raw = request.GET.get('before', '')
    if not raw:
        return queryset, ''
    match = CURSOR_RE.fullmatch(raw) if isinstance(raw, str) else None
    if not match:
        return None, ''
    try:
        moment = datetime.strptime(match.group(1), '%Y%m%dT%H%M%S.%fZ').replace(tzinfo=dt_timezone.utc)
        key = int(match.group(2)) if integer_pk else uuid.UUID(match.group(2))
    except (ValueError, TypeError):
        return None, ''
    # the bound on created_at alone lets an index start the scan at the cursor (refutation round 1, avail-3 and avail-5):
    # the same rows, read from the cursor rather than from the newest row down
    return (queryset.filter(created_at__lte=moment).filter(Q(created_at__lt=moment) | Q(created_at=moment, pk__lt=key)),
            raw)


def describe(event) -> dict:
    """An audit event in the log's words: what happened, and the event's own small values beside it (a value that is
    not a plain one is left out, never read as a key - refutation r1, money-8)."""
    data = event.data if isinstance(event.data, dict) else {}
    action = data.get('action')
    if event.event == 'decision.recorded':
        what = DECISION_LABELS.get(action, 'Decision recorded') if isinstance(action, str) else 'Decision recorded'
    else:
        what = EVENT_LABELS.get(event.event, event.event)
    details = []
    for key in DETAIL_KEYS:
        value = data.get(key)
        if value is None or value == '' or not isinstance(value, (str, int, float)):
            continue
        details.append(f'{key} {value}')
    # a document by its short reference, never its title (release 1, C2)
    return {'event': event, 'what': what, 'details': ' · '.join(details),
            'reference': str(event.encounter_id)[:8] if event.encounter_id else ''}


@operator_view
@methods('GET')
@read_audit.phi_read(read_audit.OPS_ACTIVITY)
def activity(request):
    """Every audit event of every practice, newest first, by practice and kind, in pages - recorded as ops.activity
    with the documents its rows name, its filters and its cursor."""
    events = models.AuditEvent.objects.select_related('workspace', 'actor')  # the document by its id alone (C2)
    chosen_workspace = None
    wanted = request.GET.get('workspace', '')
    if wanted:
        try:
            chosen_workspace = Workspace.objects.get(pk=wanted)
        except (Workspace.DoesNotExist, ValueError, TypeError, ValidationError):
            chosen_workspace = None
        else:
            events = events.filter(workspace=chosen_workspace)
    kind = request.GET.get('kind', '')
    if kind in KINDS:
        names = KINDS[kind][1]
        events = events.filter(event__startswith=names) if isinstance(names, str) else events.filter(event__in=names)
    else:
        kind = ''
    events, before = _older_than(events, request)
    window = list(events.order_by('-created_at', '-pk')[:PAGE_SIZE + 1]) if events is not None else []
    query = '&'.join(part for part in (f'workspace={chosen_workspace.pk}' if chosen_workspace else '',
                                       f'kind={kind}' if kind else '') if part)
    rows = window[:PAGE_SIZE]
    destroyed = set(models.Encounter.objects.filter(
        pk__in={row.encounter_id for row in rows if row.encounter_id}, destroyed_at__isnull=False).values_list(
        'pk', flat=True))
    read_audit.record(request, view=read_audit.OPS_ACTIVITY,
                      workspace_id=chosen_workspace.pk if chosen_workspace else None,
                      encounter_ids=list(dict.fromkeys(row.encounter_id for row in rows if row.encounter_id)),
                      count=len(rows), filters={'workspace': chosen_workspace.pk if chosen_workspace else None,
                                                'kind': kind or None, 'before': before or None})
    return render(request, 'studio/ops_activity.html', _context(
        'activity', rows=[{**describe(event), 'destroyed': event.encounter_id in destroyed} for event in rows],
        earlier=bool(before), unreadable=events is None,
        older=cursor_of(rows[-1]) if len(window) > PAGE_SIZE else '', query=query,
        kinds=[(key, label) for key, (label, _names) in KINDS.items()], kind=kind, chosen_workspace=chosen_workspace,
        workspaces=list(Workspace.objects.order_by('name', 'pk')), tab='actions'))


@operator_view
@methods('GET')
def sign_ins(request):
    attempts = models.LoginAttempt.objects.all()
    result = request.GET.get('result', '')
    if result == 'failed':
        attempts = attempts.filter(succeeded=False)
    elif result == 'succeeded':
        attempts = attempts.filter(succeeded=True)
    else:
        result = ''
    attempts, before = _older_than(attempts, request, integer_pk=True)
    window = list(attempts.order_by('-created_at', '-pk')[:PAGE_SIZE + 1]) if attempts is not None else []
    rows = window[:PAGE_SIZE]
    accounts = set(User.objects.filter(username__in={row.username for row in rows}).values_list('username', flat=True))
    # B1 step 5: the attempts the slowdown refused (they reach no password check, so they are counted, not listed), for
    # each account on this page (a name that is no account is never shown)
    refused = {name: throttle().refused_in(name) for name in sorted(accounts)}
    return render(request, 'studio/ops_activity.html', _context(
        'activity', attempts=[{'attempt': row, 'known': row.username in accounts,
                               'outcome': OUTCOME_LABELS.get(row.outcome or '', '')} for row in rows],
        earlier=bool(before), unreadable=attempts is None, older=cursor_of(rows[-1]) if len(window) > PAGE_SIZE else '',
        query=f'result={result}' if result else '', result=result, tab='sign-ins',
        refused=[(name, count) for name, count in refused.items() if count],
        delay_after=settings.SIGNIN_USER_DELAY_AFTER, delay_base=settings.SIGNIN_DELAY_BASE_SECONDS,
        delay_max_minutes=settings.SIGNIN_DELAY_MAX_SECONDS // 60, pair_limit=settings.SIGNIN_PAIR_LIMIT,
        client_limit=settings.SIGNIN_CLIENT_LIMIT, window_minutes=settings.SIGNIN_WINDOW_SECONDS // 60))


# B1 step 4's outcomes, as the page names them (an attempt an older release recorded has none: its result is shown)
OUTCOME_LABELS = {
    models.LoginAttempt.SIGNED_IN: 'Signed in',
    models.LoginAttempt.SECOND_FACTOR_PENDING: 'Password right, key not yet given',
    models.LoginAttempt.SECOND_FACTOR_FAILED: 'Key or recovery code refused',
    models.LoginAttempt.WRONG_PASSWORD: 'Wrong password',
    models.LoginAttempt.UNKNOWN_ACCOUNT: 'No such account',
    models.LoginAttempt.NO_ACCESS: 'Right password, no access at this door',
    models.LoginAttempt.PASSWORD_EXPIRED: 'A staff-set password not replaced in time',
}



# --- release 1's routes (RELEASE-1-SPEC 3.4): each a stub answering Django's 404 until its lane replaces it -------

# --- the reads (release 1, C1 item 9) ---------------------------------------------------------------------------------
# The activity review (ADM-5, ADM-11): every recorded read of PHI - by members and operators, served and refused - by
# account, practice, kind and day, newest first, in pages by position. Opening it is itself recorded (ops.reads).

READ_KINDS = {
    read_audit.MEMBER_LIST: 'Document list', read_audit.MEMBER_DETAIL: 'Document',
    read_audit.MEMBER_INLINE: 'Document viewed in the page', read_audit.MEMBER_DOWNLOAD: 'Document downloaded',
    read_audit.MEMBER_REPORT_DOWNLOAD: 'Report downloaded', read_audit.MEMBER_BUNDLE_DOWNLOAD: 'Bundle downloaded',
    read_audit.OPS_LIST: 'Console: every document', read_audit.OPS_WORKSPACE: 'Console: a practice',
    read_audit.OPS_SPENDING: 'Console: spending', read_audit.OPS_ACTIVITY: 'Console: activity',
    read_audit.OPS_DETAIL: "Console: a document's page", read_audit.OPS_CONTENT_OPEN: "Console: a document's content opened",
    read_audit.OPS_ORIGINAL: 'Console: an original downloaded', read_audit.OPS_READS: 'Console: these reads',
}
DATE_RE = re.compile(r'\d{4}-\d{2}-\d{2}')
DOCUMENTS_SHOWN = 8  # a row names at most this many documents by reference, and counts the rest


def _chosen(model, value):
    """The row of ``model`` a filter names by id, or None (no filter, or one that names nothing)."""
    if not value:
        return None
    try:
        return model.objects.filter(pk=uuid.UUID(str(value))).first()
    except (ValueError, TypeError, AttributeError):
        return None


@operator_view
@methods('GET')
@read_audit.phi_read(read_audit.OPS_READS)
def reads(request):
    rows = models.AccessRecord.objects.all()
    account = _chosen(User, request.GET.get('account', ''))
    workspace = _chosen(Workspace, request.GET.get('workspace', ''))
    kind = request.GET.get('kind', '')
    kind = kind if kind in READ_KINDS else ''
    day = request.GET.get('day', '')
    day = day if isinstance(day, str) and DATE_RE.fullmatch(day) else ''
    try:
        start = datetime.strptime(day, '%Y-%m-%d').replace(tzinfo=dt_timezone.utc) if day else None
    except ValueError:
        start, day = None, ''
    if account is not None:
        rows = rows.filter(actor_id=account.pk)
    if workspace is not None:
        rows = rows.filter(workspace_id=workspace.pk)
    if kind:
        rows = rows.filter(view=kind)
    if start is not None:
        rows = rows.filter(created_at__gte=start, created_at__lt=start + timedelta(days=1))
    rows, before = _older_than(rows, request)
    window = list(rows.order_by('-created_at', '-pk')[:PAGE_SIZE + 1]) if rows is not None else []
    shown = window[:PAGE_SIZE]
    filters = {'account': account.pk if account else None, 'workspace': workspace.pk if workspace else None,
               'kind': kind or None, 'day': day or None, 'before': before or None}
    read_audit.record(request, view=read_audit.OPS_READS, workspace_id=workspace.pk if workspace else None,
                      count=len(shown), filters=filters)
    people = {person.pk: person for person in User.objects.filter(pk__in={row.actor_id for row in shown})}
    # a member's list read again by the same session is counted on its record (refutation round 1, avail-3)
    repeats = {item.record_id: item for item in models.AccessRecordRepeat.objects.filter(
        record_id__in=[row.pk for row in shown if row.view == read_audit.MEMBER_LIST])}
    practices = dict(Workspace.objects.filter(pk__in={row.workspace_id for row in shown if row.workspace_id})
                     .values_list('pk', 'name'))
    query = '&'.join(f'{name}={value}' for name, value in (
        ('account', account.pk if account else ''), ('workspace', workspace.pk if workspace else ''), ('kind', kind),
        ('day', day)) if value)
    return render(request, 'studio/ops_activity_reads.html', _context(
        'activity', tab='reads', unreadable=rows is None, earlier=bool(before),
        older=cursor_of(shown[-1]) if len(window) > PAGE_SIZE else '', query=query,
        rows=[{'row': row, 'person': people.get(row.actor_id), 'practice': practices.get(row.workspace_id),
               'repeat': repeats.get(row.pk),
               'kind': READ_KINDS.get(row.view, row.view),
               'documents': [(str(item), str(item)[:8]) for item in row.encounter_ids[:DOCUMENTS_SHOWN]],
               'more': max(0, len(row.encounter_ids) - DOCUMENTS_SHOWN)} for row in shown],
        kinds=list(READ_KINDS.items()), kind=kind, day=day, chosen_account=account, chosen_workspace=workspace,
        accounts=list(User.objects.filter(pk__in=models.AccessRecord.objects.values('actor_id')).order_by('username')),
        workspaces=list(Workspace.objects.order_by('name', 'pk'))))


# --- clearing a sign-in delay (release 1, B1 step 8) ------------------------------------------------------------------
# Lane 2's studio.throttle owns the slowdown: clear_failures(username) clears a username's delay (its RateWindow
# counters; LoginAttempt rows are never deleted) and refused_in(username) is how many of its attempts the slowdown refused
# lately (B1 step 5). The console calls them by name, when used, so it imports on a tree without that module; the act
# writes the SecurityEvent signin.delay_cleared (the lead's contract of 2026-11-24).
THROTTLE_MODULE = 'studio.throttle'


def throttle():
    """Lane 2's studio.throttle (B1), imported when used."""
    return importlib.import_module(THROTTLE_MODULE)


@operator_view
@methods('POST')
@requires_recent_second_factor()
def unlock_sign_in(request, user_id):
    """Clear the person's sign-in delay (throttle.clear_failures), with a SecurityEvent signin.delay_cleared and an audit
    row in each of their workspaces carrying who at the practice asked for it (Requested by: clearing a delay changes who
    can sign in, so it is asked and recorded as every access act's is). Refused, as every act here, for an operator's
    account or one with no workspace (the server's clear-signin-failures clears those)."""
    person = _person(user_id)
    memberships = []
    try:
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
            requested_by = _requested_by(request)
            cleared = throttle().clear_failures(person.username)
            counted = {'cleared': cleared} if isinstance(cleared, int) and not isinstance(cleared, bool) else {}
            security_events.record('signin.delay_cleared', actor=request.user, subject=person, **counted)
            for workspace in _workspaces_of(memberships):
                audit.record(workspace, 'operator.signin_cleared', actor=request.user, user=str(person.pk),
                             username=person.username, requested_by=requested_by, **counted)
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return see_other(f'{_back(request, memberships)[0]}?done=unlocked')
