"""Account email outcomes, safe audit metadata, and private failure recovery."""

from dataclasses import dataclass
from django.conf import settings
from django.core.mail import EmailMessage
from .email_backend import PrivateFileEmailBackend, application_origin
from .security import audit


@dataclass(frozen=True)
class Delivery:
    status: str  # outbox, accepted, failed
    recovery_staged: bool = False


def deliver_account_email(actor, target, recipient, purpose, raw_token, department=None):
    """Return an honest outcome. Account creation survives transport failures."""
    route = "verify" if purpose == "verification" else "invite"
    subject = "Verify your QuillMD test account" if purpose == "verification" else "QuillMD department invitation"
    message = None
    try:
        link = f"{application_origin()}/{route}/{raw_token}/"
        body = (f"Open {link} to verify your synthetic test account."
                if purpose == "verification" else f"Accept your QuillMD department invitation at {link}")
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
            if message is None:
                # Configuration may fail before the URL is usable. An administrator
                # can recover this one token from the protected local outbox.
                message = EmailMessage(subject, f"Delivery configuration requires repair. Private recovery route: /{route}/{raw_token}/", settings.DEFAULT_FROM_EMAIL, [recipient])
            staged = PrivateFileEmailBackend(fail_silently=False).send_messages([message]) == 1
        except Exception:
            pass
        audit(actor, "email.failed", target, department=department, purpose=purpose,
              error_class=type(exc).__name__, recovery_staged=staged)
        return Delivery("failed", staged)
