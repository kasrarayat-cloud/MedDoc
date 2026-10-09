"""Model-free logging filter: Django loads this before the app registry."""
import logging


class AccountCSRFLogFilter(logging.Filter):
    def filter(self, record):
        if getattr(getattr(record, 'request', None), 'quillmd_account_origin', False):
            # Default CSRF warnings include a capability-bearing request.path.
            # Keep the warning while omitting the reason, URL and header data.
            record.msg = 'Forbidden (account CSRF validation failed).'
            record.args = ()
            record.request = None
            record.exc_info = record.exc_text = record.stack_info = None
        return True


PreviewCSRFLogFilter = AccountCSRFLogFilter
