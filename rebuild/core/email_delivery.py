"""Account email outcomes, safe audit metadata, and private failure recovery."""

from dataclasses import dataclass
from django.conf import settings
from django.core.mail import EmailMessage
from .email_backend import PrivateFileEmailBackend, application_origin, private_access_instructions
from .security import audit


@dataclass(frozen=True)
class Delivery:
    status: str  # outbox, accepted, failed
    recovery_staged: bool = False


#: The link route each purpose points at.
ROUTES = {
    'verification': 'verify',
    'invitation': 'invite',
    'recovery': 'recovery/confirm',
    'owner_invitation': 'invite/clinic',
}

#: Every account email QuillMD sends: (subject, body) per data mode and purpose. The ONLY substitution
#: field any of them may carry is {link}, which holds the configured origin, the route and the token.
#: Nothing from a patient, an encounter, a department, an organization or the recipient's own record can
#: be interpolated, and `core.tests.test_v1_email_copy` fails if a field other than {link} is
#: ever added. Real mode drops the "test account" and "synthetic" wording and changes nothing else.
COPY = {
    'synthetic': {
        'verification': ('Verify your QuillMD test account', 'Open {link} to verify your synthetic test account.'),
        'invitation': ('QuillMD department invitation', 'Accept your QuillMD department invitation at {link}'),
        'recovery': ('Recover your QuillMD test account', 'Recover your QuillMD test account at {link}. This link expires in 30 minutes. Administrators also need their enrolled authenticator.'),
        'owner_invitation': ('QuillMD clinic invitation', 'Set up your clinic on QuillMD at {link}. This invitation link works once and expires in 7 days.'),
    },
    'real': {
        'verification': ('Verify your QuillMD account', 'Open {link} to verify your QuillMD account.'),
        'invitation': ('QuillMD department invitation', 'Accept your QuillMD department invitation at {link}'),
        'recovery': ('Recover your QuillMD account', 'Recover your QuillMD account at {link}. This link expires in 30 minutes. If you use an authenticator, you will still need it to sign in.'),
        'owner_invitation': ('QuillMD clinic invitation', 'Set up your clinic on QuillMD at {link}. This invitation link works once and expires in 7 days.'),
    },
}


def account_copy(purpose):
    return COPY['synthetic' if settings.SYNTHETIC_ONLY else 'real'][purpose]


def deliver_account_email(actor, target, recipient, purpose, raw_token, department=None):
    """Return an honest outcome. Account creation survives transport failures."""
    route = ROUTES[purpose]
    subject, template = account_copy(purpose)
    recovery_body = f"Delivery configuration requires repair. Private recovery route: /{route}/{raw_token}/"
    try:
        link = f"{application_origin()}/{route}/{raw_token}/"
        body = template.format(link=link)
        recovery_body = body
        body += private_access_instructions(recipient, purpose)
        message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [recipient])
        if message.send(fail_silently=False) != 1:
            raise RuntimeError("Email transport did not acknowledge the message")
        status = "accepted" if settings.QUILLMD_EMAIL_MODE == "resend" else "outbox"
        audit(actor, f"email.{status}", target, department=department, purpose=purpose,
              provider_message_id=getattr(message, "provider_message_id", ""))
        return Delivery(status)
    except Exception as exc:
        # Store no recipient, body, raw token, error text, or provider response in audit.
        staged = False
        try:
            # Keep the original token recoverable, but never stage private gate
            # credentials locally, even when a Resend request failed after assembly.
            recovery_message = EmailMessage(subject, recovery_body, settings.DEFAULT_FROM_EMAIL, [recipient])
            staged = PrivateFileEmailBackend(fail_silently=False).send_messages([recovery_message]) == 1
        except Exception:
            pass
        audit(actor, "email.failed", target, department=department, purpose=purpose,
              error_class=type(exc).__name__, recovery_staged=staged)
        return Delivery("failed", staged)
