"""Generation failure classifications without worker or media dependencies."""

from django.core.exceptions import ValidationError


class PlatformFailure(ValidationError):
    """A post-settlement failure QuillMD absorbs. Its message is a fixed, non-clinical string that is safe to display."""


class NoProviderRequest(ValidationError):
    """Raised before any provider request is made: nothing billable happened, so the held funds are released."""
