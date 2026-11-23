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
new workspace's name follows provisioning's rules plus one: no two workspaces read alike.
"""
from __future__ import annotations

import re
import secrets
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import ROUND_HALF_UP, Context, Decimal, InvalidOperation, Overflow, localcontext
from importlib import import_module

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from . import audit, jobs, models, spend
from .fable import pricing
from .management.commands import provision
from .operator import _methods as methods
from .operator import _see_other as see_other
from .operator import operator_view

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
# the session stores whose sessions this console can list and end (refutation r2, secure-4)
SESSION_STORES = ('django.contrib.sessions.backends.db',)  # cached_db can hold a session the table no longer has (r3-3)
PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  # no 0/o, 1/l/i: it is read aloud or copied by hand
PASSWORD_GROUPS, PASSWORD_GROUP_CHARS = 4, 5  # 20 random characters (about 99 bits) in four groups
PAGE_SIZE = 100
SPENDING_DAYS = 30
TOP_DOCUMENTS = 50
OPERATOR_ACCOUNT = 'This is an operator account. Operator accounts are managed on the server, not here.'
NO_WORKSPACE = 'This account belongs to no workspace. It is managed on the server, not here.'
AGENT_OWNER = 'An automated agent can be a Reviewer or a Viewer, not an Owner.'
NO_SESSION_STORE = ('This site keeps sessions where the console cannot end them, so access cannot be changed or a '
                    'password reset here.')
DONE = {
    'role': 'The role was changed.', 'same-role': 'The role was already that one: nothing changed.',
    'off': 'Access was turned off. The person can no longer sign in, and every open session has ended.',
    'on': 'Access was turned on again. The person signs in again with their password; no earlier session comes back.',
    'same-access': 'Access was already that way: nothing changed.',
    'created': 'The workspace was created. Add its people below.',
}
# The activity log's kinds (GET /ops/activity?kind=...): each a set of audit event names, or a prefix.
KINDS = {
    'documents': ('Documents added', ('encounter.created',)),
    'coding': ('Coding reviews', ('coding.round_queued', 'coding.round_done', 'coding.round_failed', 'pipeline.stopped',
                                  'pipeline.resumed', 'provider.sending', 'provider.finished', 'provider.count_failed',
                                  'provider.reconciled')),
    'decisions': ('Approvals and rejections', ('decision.recorded',)),
    'answers': ('Answers', ('answers.recorded',)),
    'downloads': ('Reports made', ('export.created',)),
    'operator': ('Operator acts', 'operator.'),
}
EVENT_LABELS = {
    'encounter.created': 'Document added',
    'coding.round_queued': 'Coding review queued',
    'coding.round_done': 'Coding review finished',
    'coding.round_failed': 'Coding review could not finish',
    'pipeline.stopped': 'Stopped',
    'pipeline.resumed': 'Resumed',
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
# The event data shown beside an event, in this order, by name (ids are kept for the operator's record elsewhere).
DETAIL_KEYS = ('number', 'line', 'code', 'kind', 'fmt', 'count', 'purpose', 'state', 'username', 'role', 'from', 'to',
               'name', 'category', 'view', 'sessions_ended')


class Refused(Exception):
    """An act the console declines, with the sentence the operator reads and the status it answers."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


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
        operators=[{'person': grant_row.user, 'since': grant_row.created_at}
                   for grant_row in models.OperatorGrant.objects.filter(revocation__isnull=True)
                   .select_related('user').order_by('created_at', 'pk')],
        workspaces=list(Workspace.objects.select_related('category').order_by('name', 'pk')),
        **extra)


def _workspace_context(workspace, **extra) -> dict:
    return _context('workspaces', workspace=workspace, rows=membership_rows(workspace.memberships.all(), operator_ids()),
                    documents=workspace.encounters.count(), **extra)


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


def end_sessions(user) -> int:
    """End every live session signed in as ``user``: an open session ends at once and can never come back, whatever
    happens to the account later (refutation r1, gate-1). The sessions are read from the database table (the db store
    only, SESSION_STORES; any other store is refused - r2, secure-4; r3, r3-3), live ones only (an expired session signs
    nobody in - r2, secure-5), and each is deleted through its store. Sessions are sign-in state, not records. The
    number ended."""
    if settings.SESSION_ENGINE not in SESSION_STORES:
        raise Refused(NO_SESSION_STORE, 409)
    store = import_module(settings.SESSION_ENGINE).SessionStore
    ended = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator(chunk_size=200):
        try:
            data = session.get_decoded()
        except Exception:  # noqa: BLE001 - a session that cannot be read signs nobody in
            continue
        if isinstance(data, dict) and str(data.get('_auth_user_id', '')) == str(user.pk):
            store(session_key=session.session_key).delete()
            ended += 1
    return ended


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
        return render(request, 'studio/ops_workspace.html', _workspace_context(workspace, error=str(exc)),
                      status=exc.status)
    return render(request, 'studio/ops_people.html', _people_context(error=str(exc)), status=exc.status)


def _password_page(request, person, workspace, made, password):
    """The one answer that shows a password: the POST's own response (never a redirect or a URL), no-store like every
    console page (studio.access.SecurityHeadersMiddleware)."""
    return render(request, 'studio/ops_password.html',
                  _context('workspaces' if workspace is not None else 'people', person=person, workspace=workspace,
                           made=made, password=password))


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
def add_person(request):
    """A new person: an account (human) in one workspace with a role, its password generated and answered once."""
    workspace, came_from = None, None
    try:
        try:
            workspace = Workspace.objects.select_related('category').get(pk=request.POST.get('workspace', ''))
        except (Workspace.DoesNotExist, ValueError, TypeError, ValidationError):
            raise Refused('Choose the workspace the person works in.')
        came_from = workspace if request.POST.get('back', '') == str(workspace.pk) else None
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
        person = User(username=username, display_name=name, actor_kind=User.HUMAN)
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
                             username=username, role=role)
        except IntegrityError:
            raise Refused('That username is taken. Choose another.', 409)
    except Refused as exc:
        return _refused(request, exc, came_from)
    return _password_page(request, person, came_from, 'added', password)


@operator_view
@methods('POST')
def reset_password(request, user_id):
    """A new password for the person, generated and answered once; every stored session of theirs is ended."""
    person = _person(user_id)
    memberships = []
    try:
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
            password = new_password(person)
            person.set_password(password)
            person.save(update_fields=['password'])
            ended = end_sessions(person)
            for workspace in _workspaces_of(memberships):
                audit.record(workspace, 'operator.password_reset', actor=request.user, user=str(person.pk),
                             username=person.username, sessions_ended=ended)
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return _password_page(request, person, _back(request, memberships)[1], 'reset', password)


@operator_view
@methods('POST')
def set_role(request, user_id):
    """The role of one of the person's memberships (owner, reviewer or viewer; an automated agent is never made an owner:
    provisioning keeps a workspace's owner a human - refutation r1, data-7)."""
    person = _person(user_id)
    memberships = []
    try:
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
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
                             username=person.username, **{'from': previous, 'to': role})
                done = 'role'
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return see_other(f'{_back(request, memberships)[0]}?done={done}')


@operator_view
@methods('POST')
def set_access(request, user_id):
    """The person's access off (the account's is_active: sign-in refused, and every stored session of theirs ended at
    once) or on again (they sign in again with their password). Nothing is deleted but sign-in state."""
    person = _person(user_id)
    memberships = []
    try:
        wanted = request.POST.get('access', '')
        if wanted not in ('off', 'on'):
            raise Refused('Choose whether access is turned off or on.')
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
            active = wanted == 'on'
            if person.is_active == active:
                done = 'same-access'
            else:
                # every session ends both ways: off, so none goes on; on, so none made by a sign-in that raced the
                # off act (it read the account active before the act committed) comes back (refutation r2, secure-1)
                values = {'sessions_ended': end_sessions(person)}
                person.is_active = active
                person.save(update_fields=['is_active'])
                for workspace in _workspaces_of(memberships):
                    audit.record(workspace, f'operator.access_{wanted}', actor=request.user, user=str(person.pk),
                                 username=person.username, **values)
                done = wanted
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return see_other(f'{_back(request, memberships)[0]}?done={done}')


# --- workspaces --------------------------------------------------------------------------------------------------------

def _workspaces_context(**extra) -> dict:
    rows = (Workspace.objects.select_related('category')
            .annotate(people=Count('memberships', distinct=True),
                      active_people=Count('memberships', distinct=True,
                                          filter=Q(memberships__active=True, memberships__user__is_active=True)),
                      documents=Count('encounters', distinct=True))
            .order_by('name', 'pk'))
    return _context('workspaces', workspaces=list(rows), categories=list(Category.objects.order_by('name', 'pk')),
                    **extra)


def name_reading(name: str) -> str:
    """A name as it reads: Unicode NFKC caseless (normalised, case folded, normalised again), then provisioning's letters
    and digits (provision._read), so full-width, mathematical and decomposed spellings read as the plain one (refutation
    r2, secure-2). No other specialty's name may read so (provision._new_name_problem's rule, read the same way)."""
    folded = unicodedata.normalize('NFKC', unicodedata.normalize('NFKC', name).casefold())
    return provision._read(folded)


# Scripts whose letters come precomposed with their accents: an accent typed apart after one of them is refused in a
# workspace name (refutation r5, r5-1), as is a mark after a dotless i or j, or a mark with no letter before it.
PRECOMPOSED_SCRIPTS = ('LATIN', 'GREEK', 'CYRILLIC')


def plain_name_problem(name: str) -> str:
    """Why ``name`` (as _field stores it, NFC) cannot name a workspace, or nothing. A workspace name is stored exactly
    as typed and read exactly so by provisioning, which finds a workspace by its exact text (refutation r4, r4-4; r5,
    r5-2): so it may hold no compatibility character - its NFKC form must be itself (no full-width or mathematical
    letter, ligature, superscript or trade mark sign) - and no accent typed apart from a Latin, Greek or Cyrillic letter,
    which would draw like the precomposed letter and read otherwise, nor one after anything that is no letter (r5-1). Look-alike letters of different scripts are
    not compared (a written limit, as provisioning's own)."""
    if unicodedata.normalize('NFKC', name) != name:
        return ('The workspace name holds a compatibility character (a full-width or styled letter, a ligature, a '
                'superscript or a sign such as the trade mark sign). Type it with plain characters.')
    base = ''
    for ch in name:
        if unicodedata.category(ch).startswith('M'):
            script = unicodedata.name(base, '').split(' ')[0] if base else ''
            if (not base or not unicodedata.category(base).startswith('L') or script in PRECOMPOSED_SCRIPTS
                    or base in '\u0131\u0237'):
                return ('The workspace name has an accent typed as a separate character. Type the accented letter '
                        'itself.')
        else:
            base = ch
    return ''


def workspace_name_problem(name: str, category) -> str:
    """Why a new workspace cannot take ``name``, or nothing. Provisioning's rules, read the console's one way
    (name_reading: NFKC caseless, letters and digits), which makes them stricter (refutation r3, r3-2, r3-8): it names no
    other specialty (provision.SPECIALTIES), and no workspace of ANY specialty reads alike - which covers provisioning's
    rule that no workspace of another specialty has it exactly - so no two workspaces are told apart only by case,
    spacing, punctuation or a compatibility spelling (refutation r1, data-2, data-4, data-5; r2, secure-2)."""
    reading = name_reading(name)
    if not reading:
        return 'A workspace name needs at least one letter or digit.'
    # another specialty's name, by either reading of the stored name: the console's and provisioning's (r4, r4-2; r5,
    # r5-3 - the stored name is what was typed, plain_name_problem having refused anything NFKC would change)
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
def create_workspace(request):
    """A workspace for a specialty that exists (a Category row: what the page and the report show it as)."""
    try:
        name = _field(request, 'name', required=True, label='The workspace name')
        plain = plain_name_problem(name)
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
                         category=category.slug)
    except Refused as exc:
        return render(request, 'studio/ops_workspaces.html', _workspaces_context(error=str(exc)), status=exc.status)
    return see_other(f'/ops/workspaces/{workspace.pk}?done=created')


@operator_view
@methods('GET')
def workspace_page(request, workspace_id):
    workspace = _workspace(workspace_id)
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
            .only('id', 'usage', 'scope', 'state', 'http_status', 'sent', 'endpoint', 'created_at', 'started_at', 'encounter',
                  'encounter__title', 'encounter__workspace', 'encounter__workspace__name',
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
            _add(documents.setdefault(run.encounter_id, {'encounter': run.encounter, **_bucket()}), spent)
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
def spending_page(request):
    return render(request, 'studio/ops_spending.html', _context('spending', **spending()))


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
    return queryset.filter(Q(created_at__lt=moment) | Q(created_at=moment, pk__lt=key)), raw


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
    return {'event': event, 'what': what, 'details': ' · '.join(details)}


@operator_view
@methods('GET')
def activity(request):
    events = models.AuditEvent.objects.select_related('workspace', 'encounter', 'actor')
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
    return render(request, 'studio/ops_activity.html', _context(
        'activity', rows=[describe(event) for event in rows], earlier=bool(before), unreadable=events is None,
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
    return render(request, 'studio/ops_activity.html', _context(
        'activity', attempts=[{'attempt': row, 'known': row.username in accounts} for row in rows],
        earlier=bool(before), unreadable=attempts is None, older=cursor_of(rows[-1]) if len(window) > PAGE_SIZE else '',
        query=f'result={result}' if result else '', result=result, tab='sign-ins',
        throttle_attempts=settings.LOGIN_THROTTLE_ATTEMPTS,
        throttle_minutes=settings.LOGIN_THROTTLE_WINDOW_SECONDS // 60))
