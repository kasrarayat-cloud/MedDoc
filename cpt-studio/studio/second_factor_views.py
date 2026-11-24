"""The operator's second factor at the admin door (release 1, B2; RELEASE-1-SPEC 3.4 and 4, B2): the sign-in's second
step, setup with a code issued on the server, recovery codes and the keys page, around studio.second_factor's
ceremony. The browser side is static/studio/ops_second_factor.js (navigator.credentials, base64url, no inline script).

    GET, POST /login/second-factor            the key: after a checked password (the session's pending sign-in), or a
                                              signed-in operator's step-up (?next=<the page to go back to>)
    POST      /login/second-factor/options    the signed challenge's options, as JSON
    GET, POST /login/enrol                    setup: the setup code and a new password, then the first key; the
                                              recovery codes are shown once
    POST      /login/enrol/options            the new key's options, as JSON
    GET, POST /login/recovery                 a recovery code in place of a key, for the sign-in or the step-up
    GET, POST /ops/security                   the operator's keys: list, add, remove (behind operator_view, a satisfied
                                              second factor, and the step-up for every change)

Every view keeps Django's CSRF check; every refusal is a fixed sentence. Nothing here logs or records a code, a key or a
password: the security events hold ids and counts.
"""
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from . import rate, request_meta, second_factor as factor, security_events, sessions, throttle
from .models import LoginAttempt, OneTimeToken, User
from .operator import _methods as methods
from .operator import operator_view

SIGN_IN_PAGE = '/login/'
ENROL_PAGE = '/login/enrol'
KEYS_PAGE = '/ops/security'
NO_KEYS = ('No security key is set up for this account yet. Set one up with the setup code you were given, or use a '
           'recovery code.')
SETUP_CODE_REFUSED = 'This setup code cannot be used. Check it, or ask for a new one: a code works once, for 30 minutes.'
RECOVERY_REFUSED = 'That recovery code cannot be used: it is not one of yours, or it was used before.'
SETUP_EXPIRED = 'This setup has expired. Start again with your setup code.'
DONE = {'added': 'The key was added.', 'removed': 'The key was removed.'}


def _see_other(url):
    response = HttpResponseRedirect(url)
    response.status_code = 303
    return response


def _who(request):
    """(the account, the pending state or None, the purpose) of a request that may present a second factor: a pending
    sign-in (SIGN_IN), or a signed-in operator at the admin door (STEP_UP); else (None, None, None)."""
    if request.user.is_authenticated:
        if factor.satisfied(request) and factor.is_human_operator(request.user):
            return request.user, None, factor.STEP_UP
        return None, None, None
    user, state = factor.pending(request)
    if user is None:
        return None, None, None
    return user, state, factor.SIGN_IN


def _next_of(request, state):
    """Where a finished second factor goes: the pending sign-in's own next, or the step-up's ?next=, as safe_next keeps
    it - a path of this host alone naming a console page or the account page (refutation r2, finding 5)."""
    host = request.get_host()
    if state is not None:
        return factor.safe_next(state.get('next'), host)
    return factor.safe_next(request.POST.get('next') or request.GET.get('next'), host)


def _page(request, template, context, error=''):
    context = {**context, 'error': error}
    return render(request, template, context, status=200 if not error else 400)


@ensure_csrf_cookie
def second_factor(request):
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    user, state, purpose = _who(request)
    if user is None:
        return redirect(SIGN_IN_PAGE)  # nothing here waits for a key: the password comes first
    next_url = _next_of(request, state)
    error = ''
    if request.method == 'POST':
        error = factor.too_many(user)
        if not error:
            try:
                factor.verify_key(request, user, request.POST.get('credential', ''), purpose)
            except factor.Refused as refused:
                error = str(refused)
                if factor.note_failure(request, user, state):
                    return redirect(f'{SIGN_IN_PAGE}?reason=key')  # the pending sign-in was dropped
            else:
                if purpose == factor.SIGN_IN:
                    if not factor.complete_sign_in(request, user, state):
                        return redirect(f'{SIGN_IN_PAGE}?reason=key')  # its attempt was settled meanwhile
                else:
                    factor.refresh(request)
                return redirect(next_url)
    keys = factor.active_keys(user).exists()
    return _page(request, 'studio/ops_second_factor.html', {
        'mode': 'key', 'next': next_url, 'step_up': purpose == factor.STEP_UP, 'has_keys': keys,
        'no_keys': '' if keys else NO_KEYS, 'codes_left': factor.recovery_codes_left(user),
        'attempts_left': factor.attempts_left(user, state)}, error)


def second_factor_options(request):
    """POST: the options of a signed challenge for the account's own keys (JSON)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    user, state, purpose = _who(request)
    if user is None:
        return JsonResponse({'error': factor.NO_CHALLENGE}, status=403)
    refused = factor.too_many(user)
    if refused:
        return JsonResponse({'error': refused}, status=429)
    if not factor.active_keys(user).exists():
        return JsonResponse({'error': NO_KEYS}, status=409)
    return JsonResponse(factor.authentication_options(request, user, purpose))


@ensure_csrf_cookie
def recovery(request):
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    user, state, purpose = _who(request)
    if user is None:
        return redirect(SIGN_IN_PAGE)
    next_url = _next_of(request, state)
    error = ''
    if request.method == 'POST':
        error = factor.too_many(user)
        if not error:
            if factor.use_recovery_code(user, request.POST.get('code', '')):
                left = factor.recovery_codes_left(user)
                security_events.record('second_factor.recovery_used', actor=user, subject=user, request=request,
                                       stage=purpose, codes_left=left)
                if purpose == factor.SIGN_IN:
                    if not factor.complete_sign_in(request, user, state):
                        return redirect(f'{SIGN_IN_PAGE}?reason=key')  # its attempt was settled meanwhile
                else:
                    factor.refresh(request)
                return redirect(next_url)
            error = RECOVERY_REFUSED
            if factor.note_failure(request, user, state, kind='recovery'):
                return redirect(f'{SIGN_IN_PAGE}?reason=key')
    return _page(request, 'studio/ops_second_factor.html', {
        'mode': 'recovery', 'next': next_url, 'codes_left': factor.recovery_codes_left(user),
        'step_up': purpose == factor.STEP_UP, 'attempts_left': factor.attempts_left(user, state)}, error)


# --- setup with a code issued on the server ---------------------------------------------------------------------------

def _enrolment(request):
    """(the account, the live setup claim) of the setup this session claimed with its code, or (None, None)."""
    state = request.session.get(factor.ENROLMENT)
    if not isinstance(state, dict):
        return None, None
    try:
        user = User.objects.get(pk=state.get('user'), is_active=True)
    except (User.DoesNotExist, ValueError, TypeError, ValidationError):
        request.session.pop(factor.ENROLMENT, None)
        return None, None
    claim = factor.live_claim(state.get('claim'), user)
    if claim is None or not factor.is_human_operator(user):
        request.session.pop(factor.ENROLMENT, None)
        return None, None
    return user, claim


def _code_refused(request):
    """The refusal when this address has used up its wrong setup codes for the window (5, SECOND_FACTOR_ATTEMPTS), else ''."""
    window = settings.SIGNIN_WINDOW_SECONDS
    used = rate.count(factor.SETUP_CODE_SCOPE, request_meta.client_key(request), since=rate.window_start(window))
    if used < settings.SECOND_FACTOR_ATTEMPTS:
        return ''
    return factor.TOO_MANY.format(wait=throttle.wait_words(window))


def _start_enrolment(request):
    """The first step: the setup code and the new password. The refusal sentence, or '' once the password is set. The
    code is used up here, in the transaction that sets the password (factor.claim_setup_code): a second browser with
    the same code - at the same moment or later - is refused like a used code, and only this session, in a fresh session
    key, holds the claim that finishes the setup (refutation r2, finding 6)."""
    refused = _code_refused(request)
    if refused:
        return refused
    token = factor.setup_token(request.POST.get('code', ''))
    if token is not None:
        user = token.user
        new, again = request.POST.get('new_password', ''), request.POST.get('new_password_again', '')
        if new != again:
            return 'The two new passwords are not the same.'
        try:
            validate_password(new, user)
        except ValidationError as exc:
            return ' '.join(exc.messages)
        with transaction.atomic():
            claim = factor.claim_setup_code(token)
            if claim is not None:
                user.set_password(new)
                user.password_changed_at = timezone.now()
                user.password_change_required_at = None
                user.save(update_fields=['password', 'password_changed_at', 'password_change_required_at'])
        if claim is not None:
            ended = sessions.end_sessions(user)
            security_events.record('password.changed', actor=user, subject=user, request=request,
                                   door=request_meta.ADMIN, stage='setup', sessions_ended=ended, token=token.pk)
            request.session.flush()  # the claim lives in a session of its own, under a new key
            request.session[factor.ENROLMENT] = {'claim': str(claim.pk), 'token': str(token.pk), 'user': str(user.pk)}
            return ''
    rate.hit(factor.SETUP_CODE_SCOPE, request_meta.client_key(request), window_seconds=settings.SIGNIN_WINDOW_SECONDS)
    return SETUP_CODE_REFUSED


def _finish_enrolment(request, user, claim):
    """The second step: the first key. The page that shows the recovery codes once, or Refused. The key is checked
    first, which uses its challenge up outside any transaction (a refused answer has used it too); the setup's claim is
    then locked and used up while the key is stored, so two answers sent at once cannot both finish it."""
    checked = factor.checked_registration(request, user, request.POST.get('credential', ''),
                                          request.POST.get('label', ''), factor.ENROL)
    with transaction.atomic():
        try:
            claim = OneTimeToken.objects.select_for_update().get(
                pk=claim.pk, user=user, purpose=factor.SETUP_CLAIM_PURPOSE, used_at__isnull=True,
                revoked_at__isnull=True, expires_at__gt=timezone.now())
        except OneTimeToken.DoesNotExist:
            raise factor.Refused(SETUP_EXPIRED) from None
        key = factor.store_key(user, checked)
        claim.used_at = timezone.now()
        claim.save(update_fields=['used_at'])
        codes = factor.new_recovery_codes(user)
    token = request.session.pop(factor.ENROLMENT, {}).get('token')
    security_events.record('second_factor.enrolled', actor=user, subject=user, request=request, key=key.pk,
                           token=token, claim=claim.pk, recovery_codes=len(codes))
    door = throttle.Door(request, request_meta.ADMIN, user.get_username())
    door.record(LoginAttempt.SIGNED_IN)  # setup ends signed in, with the key just made as the second factor
    sessions.prepare_sign_in(request, door=request_meta.ADMIN, sign_in_ref=door.sign_in_ref)
    login(request, user)
    request.session[request_meta.SESSION_SECOND_FACTOR_AT] = request_meta.epoch_seconds()
    return render(request, 'studio/ops_enrol.html', {'step': 'codes', 'codes': codes, 'label': key.label})


@ensure_csrf_cookie
def enrol(request):
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    if request.user.is_authenticated:
        return redirect(KEYS_PAGE)  # a signed-in operator adds keys on the keys page
    user, claim = _enrolment(request)
    error = ''
    if request.method == 'POST':
        step = request.POST.get('step')
        if step == 'key':
            if user is None:
                error = SETUP_EXPIRED
            else:
                try:
                    return _finish_enrolment(request, user, claim)
                except factor.Refused as refused:
                    error = str(refused)
        else:
            error = _start_enrolment(request)
            if not error:
                return _see_other(ENROL_PAGE)
            user, claim = None, None
    context = {'step': 'key' if user is not None else 'code', 'min_length': settings.PASSWORD_MIN_LENGTH,
               'expires_at': claim.expires_at if claim is not None else None}
    return _page(request, 'studio/ops_enrol.html', context, error)


def enrol_options(request):
    """POST: the options of the first key, for the session that presented a setup code (JSON)."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if request.user.is_authenticated:
        return JsonResponse({'error': SETUP_EXPIRED}, status=403)
    user, _token = _enrolment(request)
    if user is None:
        return JsonResponse({'error': SETUP_EXPIRED}, status=403)
    return JsonResponse(factor.registration_options(request, user, factor.ENROL))


# --- the operator's keys (/ops/security) ------------------------------------------------------------------------------

def _keys_page(request, error=''):
    user = request.user
    keys = list(factor.active_keys(user))
    return render(request, 'studio/ops_security.html', {
        'section': 'security', 'release': settings.RELEASE_SHA, 'keys': keys, 'last_key': len(keys) == 1,
        'codes_left': factor.recovery_codes_left(user), 'recent': factor.recent(request),
        'step_up': factor.step_up_location(KEYS_PAGE), 'error': error,
        'done': DONE.get(request.GET.get('done', ''), '') if not error else ''}, status=200 if not error else 400)


@operator_view
@methods('GET', 'POST')
def keys(request):
    # the console's gate (operator_view; Lane 3 makes it ask for the admin host and the second factor too) and, here,
    # a satisfied second factor: a password-only session, or one opened at cpt.quillmd.com, never sees this page
    if not factor.satisfied(request) or not factor.is_human_operator(request.user):
        raise Http404()
    if request.method == 'GET':
        return _keys_page(request)
    action = request.POST.get('action', '')
    if not factor.recent(request):  # every change asks for the key again (B2, item 6)
        if action == 'options':
            return JsonResponse({'error': 'step_up', 'location': factor.step_up_location(KEYS_PAGE)}, status=403)
        return _see_other(factor.step_up_location(KEYS_PAGE))
    user = request.user
    try:
        if action == 'options':
            return JsonResponse(factor.registration_options(request, user, factor.ADD))
        if action == 'add':
            key = factor.verify_registration(request, user, request.POST.get('credential', ''),
                                             request.POST.get('label', ''), factor.ADD)
            security_events.record('second_factor.key_added', actor=user, subject=user, request=request, key=key.pk,
                                   keys=factor.active_keys(user).count())
            return _see_other(f'{KEYS_PAGE}?done=added')
        if action == 'remove':
            key = factor.remove_key(user, request.POST.get('key', ''))
            security_events.record('second_factor.key_removed', actor=user, subject=user, request=request, key=key.pk,
                                   keys=factor.active_keys(user).count())
            return _see_other(f'{KEYS_PAGE}?done=removed')
    except factor.Refused as refused:
        if action == 'options':
            return JsonResponse({'error': str(refused)}, status=400)
        return _keys_page(request, str(refused))
    return _keys_page(request, 'Choose what to do with your keys.')
