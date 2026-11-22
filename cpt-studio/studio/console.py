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
- delete anything: access off is the account's is_active, and its memberships, records and history stay;
- show, log, audit or redirect with a password: a password is generated here (secrets), checked against the site's
  password validators, stored only as its hash, and answered once, in the page that answers the POST that made it.

Every act is audited in the workspace it concerns, with ids and values and never a password: operator.member_added,
operator.role_changed, operator.password_reset, operator.access_off, operator.access_on, operator.workspace_created.
Those rows name no encounter, so the customer's activity (studio.customer.activity_json, an encounter's own events) never
shows them.
"""
from __future__ import annotations

import re
import secrets
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from . import audit, jobs, models
from .fable import pricing
from .operator import _methods as methods
from .operator import _see_other as see_other
from .operator import operator_view

User, Membership, Workspace, Category = models.User, models.Membership, models.Workspace, models.Category

ROLES = dict(Membership.ROLES)  # owner -> Owner, reviewer -> Reviewer, viewer -> Viewer, in that order
USERNAME_RE = re.compile(r'[a-z0-9][a-z0-9._-]{2,39}')
USERNAME_RULE = ('A username is 3 to 40 characters: lowercase letters, digits, dots, hyphens or underscores, starting '
                 'with a letter or a digit.')
NAME_CHARS = 120  # User.display_name and Workspace.name hold 120
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')
PASSWORD_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  # no 0/o, 1/l/i: it is read aloud or copied by hand
PASSWORD_GROUPS, PASSWORD_GROUP_CHARS = 4, 5  # 20 random characters (about 99 bits) in four groups
PAGE_SIZE = 100
SPENDING_DAYS = 30
TOP_DOCUMENTS = 50
OPERATOR_ACCOUNT = 'This is an operator account. Operator accounts are managed on the server, not here.'
NO_WORKSPACE = 'This account belongs to no workspace. It is managed on the server, not here.'
DONE = {
    'role': 'The role was changed.', 'same-role': 'The role was already that one: nothing changed.',
    'off': 'Access was turned off. The person can no longer sign in, and any open session ends.',
    'on': 'Access was turned on again.', 'same-access': 'Access was already that way: nothing changed.',
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
}
DECISION_LABELS = {models.CodeDecision.APPROVE: 'Approved', models.CodeDecision.REJECT: 'Rejected',
                   models.CodeDecision.REVOKE: 'Decision undone'}
# The event data shown beside an event, in this order, by name (ids are kept for the operator's record elsewhere).
DETAIL_KEYS = ('number', 'line', 'code', 'kind', 'fmt', 'count', 'purpose', 'state', 'username', 'role', 'from', 'to',
               'name', 'category', 'view')


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
    rows = []
    for item in queryset.select_related('user', 'workspace', 'workspace__category').order_by(
            'workspace__name', 'workspace_id', 'user__username', 'pk'):
        rows.append({'membership': item, 'person': item.user, 'workspace': item.workspace,
                     'role_label': ROLES.get(item.role, item.role), 'operator': item.user_id in operators})
    return rows


def _context(**values) -> dict:
    return {'release': settings.RELEASE_SHA, 'roles': list(Membership.ROLES), **values}


def _people_context(**extra) -> dict:
    operators = operator_ids()
    members = set(Membership.objects.values_list('user_id', flat=True))
    return _context(
        rows=membership_rows(Membership.objects.all(), operators),
        unplaced=list(User.objects.exclude(pk__in=members).exclude(pk__in=operators).order_by('username')),
        operators=[{'person': grant_row.user, 'since': grant_row.created_at}
                   for grant_row in models.OperatorGrant.objects.filter(revocation__isnull=True)
                   .select_related('user').order_by('created_at', 'pk')],
        workspaces=list(Workspace.objects.select_related('category').order_by('name', 'pk')),
        **extra)


def _workspace_context(workspace, **extra) -> dict:
    return _context(workspace=workspace, rows=membership_rows(workspace.memberships.all(), operator_ids()),
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

def _field(request, name, *, limit=NAME_CHARS, required=False, label='This field') -> str:
    value = request.POST.get(name, '')
    if not isinstance(value, str):
        value = ''
    value = value.strip()
    if UNSTORABLE.search(value):
        raise Refused(f'{label} contains a NUL character or an invalid Unicode code point.')
    if len(value) > limit:
        raise Refused(f'{label} can be at most {limit:,} characters.')
    if required and not value:
        raise Refused(f'{label} is required.')
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
    return render(request, 'studio/ops_password.html', _context(person=person, workspace=workspace, made=made,
                                                                 password=password))


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
        username = _field(request, 'username', limit=40, required=True, label='The username')
        if not USERNAME_RE.fullmatch(username):
            raise Refused(USERNAME_RULE)
        name = _field(request, 'name', label='The name')
        role = request.POST.get('role', '')
        if role not in ROLES:
            raise Refused('Choose a role: Owner, Reviewer or Viewer.')
        if User.objects.filter(username__iexact=username).exists():
            raise Refused('That username is taken. Choose another.', 409)
        person = User(username=username, display_name=name, actor_kind=User.HUMAN)
        password = new_password(person)
        person.set_password(password)
        try:
            with transaction.atomic():
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
    """A new password for the person, generated and answered once; every open session of theirs ends (Django's session
    check reads the password hash)."""
    person = _person(user_id)
    memberships = []
    try:
        with transaction.atomic():
            person = User.objects.select_for_update().get(pk=person.pk)
            memberships = _changeable(person)
            password = new_password(person)
            person.set_password(password)
            person.save(update_fields=['password'])
            for workspace in _workspaces_of(memberships):
                audit.record(workspace, 'operator.password_reset', actor=request.user, user=str(person.pk),
                             username=person.username)
    except Refused as exc:
        return _refused(request, exc, _back(request, memberships)[1])
    return _password_page(request, person, _back(request, memberships)[1], 'reset', password)


@operator_view
@methods('POST')
def set_role(request, user_id):
    """The role of one of the person's memberships (owner, reviewer or viewer)."""
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
    """The person's access off (the account's is_active: sign-in refused, open sessions end at their next request) or on
    again. Nothing is deleted."""
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
                person.is_active = active
                person.save(update_fields=['is_active'])
                for workspace in _workspaces_of(memberships):
                    audit.record(workspace, f'operator.access_{wanted}', actor=request.user, user=str(person.pk),
                                 username=person.username)
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
    return _context(workspaces=list(rows), categories=list(Category.objects.order_by('name', 'pk')), **extra)


@operator_view
@methods('GET')
def workspaces(request):
    return render(request, 'studio/ops_workspaces.html', _workspaces_context())


@operator_view
@methods('POST')
def create_workspace(request):
    """A workspace for a specialty that exists (a Category row: what the coding review reads it as)."""
    try:
        name = _field(request, 'name', required=True, label='The workspace name')
        try:
            category = Category.objects.get(pk=request.POST.get('category', ''))
        except (Category.DoesNotExist, ValueError, TypeError, ValidationError):
            raise Refused('Choose the specialty of the workspace.')
        with transaction.atomic():
            if Workspace.objects.select_for_update().filter(name__iexact=name).exists():
                raise Refused('A workspace with that name exists. Choose another name.', 409)
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


def dollars(amount) -> str:
    """An estimate to the cent, for reading at a glance (the exact figures are on each document's page)."""
    return f'{Decimal(amount).quantize(CENT, rounding=ROUND_HALF_UP):,.2f}'


def _worst(run) -> Decimal:
    try:
        value = Decimal(str((run.scope or {})['worst_usd']))
    except (KeyError, TypeError, InvalidOperation):
        return Decimal(0)
    return value if value.is_finite() and value >= 0 else Decimal(0)


def _bucket():
    return {'runs': 0, 'cost': Decimal(0), 'unpriced': 0, 'worst': Decimal(0)}


def _add(bucket, cost, run):
    bucket['runs'] += 1
    if cost is None:
        bucket['unpriced'] += 1
        bucket['worst'] += _worst(run)
    else:
        bucket['cost'] += cost


def _shown(bucket) -> dict:
    return {**bucket, 'cost_text': dollars(bucket['cost']), 'worst_text': dollars(bucket['worst'])}


def spending(now=None) -> dict:
    """Every coding run that was sent (the reader's and the checker's: jobs.PURPOSES), priced from its recorded usage by
    jobs.run_cost - the console's own figures - and summed by day (UTC, the day it was sent), workspace and document. A
    run that cannot be priced is counted apart, with the worst case it was reserved at, never as zero."""
    now = now or timezone.now()
    first_day = now.date() - timedelta(days=SPENDING_DAYS - 1)
    runs = (models.ProviderRun.objects.filter(purpose__in=jobs.PURPOSES, sent=True)
            .select_related('encounter', 'encounter__workspace', 'encounter__workspace__category')
            .only('id', 'usage', 'scope', 'created_at', 'started_at', 'encounter', 'encounter__title',
                  'encounter__workspace', 'encounter__workspace__name', 'encounter__workspace__category',
                  'encounter__workspace__category__name')
            .order_by('created_at', 'pk'))
    total, recent = _bucket(), _bucket()
    days, workspaces_seen, documents = {}, {}, {}
    for run in runs.iterator(chunk_size=500):
        cost = jobs.run_cost(run)
        day = (run.started_at or run.created_at).date()
        _add(total, cost, run)
        if day >= first_day:
            _add(recent, cost, run)
            _add(days.setdefault(day, _bucket()), cost, run)
        workspace = run.encounter.workspace
        entry = workspaces_seen.setdefault(workspace.pk, {'workspace': workspace, 'documents': set(), **_bucket()})
        entry['documents'].add(run.encounter_id)
        _add(entry, cost, run)
        _add(documents.setdefault(run.encounter_id, {'encounter': run.encounter, **_bucket()}), cost, run)
    other = models.ProviderRun.objects.filter(sent=True).exclude(purpose__in=jobs.PURPOSES).count()
    by_document = sorted(documents.values(), key=lambda item: (-item['cost'], -item['unpriced'], str(item['encounter'].pk)))
    return {
        'total': _shown(total), 'recent': _shown(recent), 'days_window': SPENDING_DAYS,
        'days': [{'day': day, **_shown(days[day])} for day in sorted(days, reverse=True)],
        'workspaces': [{**_shown(entry), 'documents': len(entry['documents'])}
                       for entry in sorted(workspaces_seen.values(), key=lambda item: (-item['cost'],
                                                                                       item['workspace'].name))],
        'documents': [_shown(item) for item in by_document[:TOP_DOCUMENTS]], 'documents_total': len(by_document),
        'top_documents': TOP_DOCUMENTS, 'other_runs': other,
        'ceiling': dollars(Decimal(settings.DOCUMENT_CEILING_USD)), 'concurrent': settings.CONCURRENT_DOCUMENTS,
        'exact_total': pricing.usd(total['cost']),
    }


@operator_view
@methods('GET')
def spending_page(request):
    return render(request, 'studio/ops_spending.html', _context(**spending()))


# --- activity ----------------------------------------------------------------------------------------------------------

def _page_number(request) -> int:
    raw = request.GET.get('page', '1')
    return int(raw) if isinstance(raw, str) and raw.isascii() and raw.isdigit() and 0 < int(raw) <= 100_000 else 1


def describe(event) -> dict:
    """An audit event in the log's words: what happened, and the event's own small values beside it."""
    data = event.data if isinstance(event.data, dict) else {}
    if event.event == 'decision.recorded':
        what = DECISION_LABELS.get(data.get('action'), 'Decision recorded')
    else:
        what = EVENT_LABELS.get(event.event, event.event)
    details = []
    for key in DETAIL_KEYS:
        value = data.get(key)
        if value is None or value == '' or isinstance(value, (dict, list)):
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
    page = _page_number(request)
    window = list(events.order_by('-created_at', '-pk')[(page - 1) * PAGE_SIZE:page * PAGE_SIZE + 1])
    query = '&'.join(part for part in (f'workspace={chosen_workspace.pk}' if chosen_workspace else '',
                                       f'kind={kind}' if kind else '') if part)
    return render(request, 'studio/ops_activity.html', _context(
        rows=[describe(event) for event in window[:PAGE_SIZE]], page=page, newer=page > 1,
        older=len(window) > PAGE_SIZE, query=query, kinds=[(key, label) for key, (label, _names) in KINDS.items()],
        kind=kind, chosen_workspace=chosen_workspace,
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
    page = _page_number(request)
    window = list(attempts.order_by('-created_at', '-pk')[(page - 1) * PAGE_SIZE:page * PAGE_SIZE + 1])
    return render(request, 'studio/ops_activity.html', _context(
        attempts=window[:PAGE_SIZE], page=page, newer=page > 1, older=len(window) > PAGE_SIZE,
        query=f'result={result}' if result else '', result=result, tab='sign-ins',
        throttle_attempts=settings.LOGIN_THROTTLE_ATTEMPTS,
        throttle_minutes=settings.LOGIN_THROTTLE_WINDOW_SECONDS // 60))
