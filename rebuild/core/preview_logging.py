"""Model-free logging filter: Django loads this before the app registry."""
import logging


class PreviewCSRFLogFilter(logging.Filter):
    def filter(self, record):
        if getattr(getattr(record, 'request', None), 'quillmd_preview', False):
            # Default CSRF warnings include a capability-bearing request.path.
            # Keep the warning while omitting the reason, URL and header data.
            record.msg = 'Forbidden (private preview CSRF validation failed).'
            record.args = ()
            record.request = None
            record.exc_info = record.exc_text = record.stack_info = None
        return True
