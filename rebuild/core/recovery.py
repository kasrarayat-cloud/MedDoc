"""Django token-based recovery; mailbox proof never replaces administrator MFA."""
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetConfirmView, INTERNAL_RESET_SESSION_TOKEN
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.http import require_http_methods
from django_otp.plugins.otp_totp.models import TOTPDevice

from .email_delivery import deliver_account_email
from .models import User, Verification
from .security import audit, digest, rate_limit, token


class RecoveryRequestForm(PasswordResetForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'autocomplete': 'email'}))

    def get_users(self, email):
        return (user for user in super().get_users(email) if user.verified_at)


class RecoveryPasswordForm(SetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        if user and user.is_staff:
            self.fields['otp'] = forms.CharField(
                label='Current authenticator code', min_length=6, max_length=6,
                widget=forms.TextInput(attrs={'autocomplete': 'one-time-code', 'inputmode': 'numeric'}),
                help_text='Administrator recovery still requires your enrolled authenticator.')


@require_http_methods(['GET', 'POST'])
def recovery_request(request):
    form = RecoveryRequestForm(request.POST or None)
    sent = False
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        allowed_ip = rate_limit('recovery-ip:' + request.META.get('REMOTE_ADDR', ''), limit=20)
        allowed_email = rate_limit('recovery-email:' + email, limit=3)
        if allowed_ip and allowed_email:
            for user in form.get_users(email):
                raw = f'{urlsafe_base64_encode(force_bytes(user.pk))}/{default_token_generator.make_token(user)}'
                deliver_account_email(user, user.pk, user.email, 'recovery', raw)
                audit(user, 'auth.recovery_requested')
        # Same response for inactive, unknown, unverified and rate-limited accounts.
        sent = True
    return render(request, 'recovery.html', {'form': form, 'sent': sent, 'mode': 'request', 'email_live': settings.QUILLMD_EMAIL_MODE == 'resend'})


class RecoveryConfirmView(PasswordResetConfirmView):
    form_class = RecoveryPasswordForm
    template_name = 'recovery.html'
    success_url = reverse_lazy('recovery_complete')
    extra_context = {'mode': 'confirm'}
    post_reset_login = False

    def get_user(self, uidb64):
        user = super().get_user(uidb64)
        return user if user and user.is_active and user.verified_at else None

    def form_valid(self, form):
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=self.user.pk)
            raw = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN)
            if not user.is_active or not user.verified_at or not self.token_generator.check_token(user, raw):
                form.add_error(None, 'This recovery link expired or has already been used. Request a new link.')
                return self.form_invalid(form)
            if user.is_staff:
                allowed = rate_limit('recovery-mfa:' + str(user.pk), limit=8)
                device = TOTPDevice.objects.select_for_update().filter(user=user, confirmed=True).first()
                if not allowed or not device or not device.verify_token(form.cleaned_data.get('otp', '')):
                    audit(user, 'auth.recovery_mfa_failed')
                    form.add_error('otp' if 'otp' in form.fields else None, 'Invalid or already used authenticator code.')
                    return self.form_invalid(form)
            form.user = user
            response = super().form_valid(form)
            audit(user, 'auth.password_recovered', sessions_invalidated=True, mfa_required=user.is_staff)
            return response


def recovery_complete(request):
    return render(request, 'recovery.html', {'mode': 'complete'})


@require_http_methods(['GET', 'POST'])
def verification_resend(request):
    if settings.ADMIN_SITE:
        raise Http404
    form = RecoveryRequestForm(request.POST or None)
    sent = False
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        allowed_ip = rate_limit('verification-resend-ip:' + request.META.get('REMOTE_ADDR', ''), limit=20)
        allowed_email = rate_limit('verification-resend-email:' + email, limit=3)
        if allowed_ip and allowed_email:
            with transaction.atomic():
                user = User.objects.select_for_update().filter(email__iexact=email, is_active=True, verified_at__isnull=True).first()
                if user:
                    raw = token()
                    Verification.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
                    verification = Verification.objects.create(user=user, token_hash=digest(raw), expires_at=timezone.now() + timedelta(hours=24))
            if user:
                deliver_account_email(user, verification.pk, user.email, 'verification', raw)
                audit(user, 'account.verification_reissued', verification.pk)
        sent = True
    return render(request, 'recovery.html', {'form': form, 'sent': sent, 'mode': 'verification', 'email_live': settings.QUILLMD_EMAIL_MODE == 'resend'})
