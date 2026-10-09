"""Optional transactional Resend transport; private file outbox is the default.

No provider calls happen while importing this module or reading configuration.
The application sends verification/invitation links only, never clinical content.
"""

from email.utils import parseaddr
import hashlib
import json
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.filebased import EmailBackend as FileEmailBackend
from django.core.validators import validate_email
from dotenv import dotenv_values
import httpx


class EmailDeliveryError(RuntimeError):
    """Safe error: never includes a credential, recipient, link or provider body."""


class PrivateFileEmailBackend(FileEmailBackend):
    """Django's file backend with private permissions before any token is written."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        os.chmod(self.file_path, 0o700)

    def open(self):
        if self.stream is not None:
            return False
        descriptor = os.open(self._get_filename(), os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        os.fchmod(descriptor, 0o600)
        self.stream = os.fdopen(descriptor, "ab")
        return True


def application_origin():
    """Fixed configured origin: never use an untrusted request Host header."""
    origin = settings.QUILLMD_APP_BASE_URL.rstrip("/")
    try:
        parsed = urlsplit(origin)
        parsed.port  # Reject malformed or out-of-range ports before generating a link.
    except ValueError:
        raise ImproperlyConfigured("Configure a valid QuillMD application origin for email links.") from None
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"} or any(character.isspace() for character in origin)):
        raise ImproperlyConfigured("Configure a valid QuillMD application origin for email links.")
    if parsed.hostname == 'app.quillmd.com' and origin != 'https://app.quillmd.com':
        raise ImproperlyConfigured("QuillMD account links require the normal HTTPS origin without a special port.")
    if settings.QUILLMD_EMAIL_MODE == "resend":
        if parsed.scheme != "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            raise ImproperlyConfigured("Resend email requires an HTTPS application origin reachable by recipients.")
        if parsed.hostname not in settings.ALLOWED_HOSTS:
            raise ImproperlyConfigured("Email application origin must be an allowed application host.")
    return origin


def validate_resend_recipient(recipient):
    """Restrict controlled sends at the transport boundary, before any HTTP call."""
    validate_email(recipient)
    configured = settings.QUILLMD_EMAIL_ALLOWED_RECIPIENTS
    allowed = []
    if configured:
        for address in configured.split(","):
            address = address.strip()
            try:
                validate_email(address)
            except ValidationError:
                raise ImproperlyConfigured("Configure a valid controlled email recipient allowlist.") from None
            allowed.append(address.casefold())
        if recipient.casefold() not in allowed:
            raise EmailDeliveryError("The account email recipient is outside the controlled allowlist.")


def account_access_instructions(recipient, purpose):
    """Account instructions contain no shared credentials or preview prerequisite."""
    if settings.QUILLMD_EMAIL_MODE != "resend":
        return ""
    validate_resend_recipient(recipient)
    if purpose not in {"invitation", "recovery"}:
        return ""
    origin = application_origin()
    return (f"\n\nSign in to your individual QuillMD account at {origin}/login/."
            " Use your account email and password. Access is by invitation."
            " Use only synthetic information.")


# Retained callers cannot recover or send a retired shared credential.
private_access_instructions = account_access_instructions


def resend_configuration():
    if settings.QUILLMD_EMAIL_MODE != "resend":
        raise ImproperlyConfigured("Resend delivery is not explicitly enabled.")
    application_origin()
    key = settings.RESEND_API_KEY
    sender = settings.QUILLMD_EMAIL_FROM
    path = settings.QUILLMD_RESEND_ENV_FILE
    if path and (not key or not sender):
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor, "r") as credentials:
                meta = os.fstat(credentials.fileno())
                if not stat.S_ISREG(meta.st_mode) or meta.st_mode & 0o077:
                    raise ImproperlyConfigured("The optional email credential file must be a private regular file (0600).")
                values = dotenv_values(stream=credentials, interpolate=False)
                # Reuse only provider credentials/sender. Never import old app settings.
                key = key or values.get("RESEND_API_KEY", "")
                sender = sender or values.get("RESEND_FROM", "")
        except OSError:
            raise ImproperlyConfigured("The optional email credential file is unavailable.") from None
    if not key or not sender or "\r" in sender or "\n" in sender:
        raise ImproperlyConfigured("Configure the Resend API key and explicit sender.")
    address = parseaddr(sender)[1]
    try:
        validate_email(address)
    except ValidationError:
        raise ImproperlyConfigured("Configure a valid Resend sender address.") from None
    verified_domain = settings.QUILLMD_EMAIL_VERIFIED_DOMAIN.strip().lower()
    if not verified_domain or address.rsplit("@", 1)[-1].lower() != verified_domain:
        raise ImproperlyConfigured("Confirm the sender's verified domain using QUILLMD_EMAIL_VERIFIED_DOMAIN.")
    return key, sender


class ResendEmailBackend(BaseEmailBackend):
    """Resend's documented HTTPS Send Email API through maintained HTTPX."""

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
                sent += 1
            except (EmailDeliveryError, ImproperlyConfigured, ValidationError):
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        key, sender = resend_configuration()
        if (len(message.to) != 1 or message.cc or message.bcc or message.reply_to
                or message.attachments or getattr(message, "alternatives", None)
                or message.content_subtype != "plain"):
            raise EmailDeliveryError("Only single-recipient plain-text account emails are supported.")
        validate_resend_recipient(message.to[0])
        if "\r" in message.subject or "\n" in message.subject:
            raise EmailDeliveryError("Email subject contains an invalid header character.")
        if len(message.body.encode("utf-8")) > 64 * 1024:
            raise EmailDeliveryError("Account email exceeds its explicit size limit.")
        payload = {"from": sender, "to": message.to, "subject": message.subject, "text": message.body}
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        try:
            response = httpx.post(
                "https://api.resend.com/emails", json=payload,
                headers={"Authorization": f"Bearer {key}", "Idempotency-Key": f"quillmd-account/{fingerprint}"},
                timeout=httpx.Timeout(15, connect=5), follow_redirects=False,
            )
        except httpx.HTTPError:
            raise EmailDeliveryError("The email provider outcome is uncertain; no automatic retry was made.") from None
        if not 200 <= response.status_code < 300:
            raise EmailDeliveryError("The email provider did not accept the request.")
        try:
            provider_id = response.json()["id"]
            if not isinstance(provider_id, str) or not provider_id or len(provider_id) > 200:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise EmailDeliveryError("The email provider returned an unconfirmed result.") from None
        message.provider_message_id = provider_id
