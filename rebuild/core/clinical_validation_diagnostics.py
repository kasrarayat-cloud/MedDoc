"""Bounded internal graph diagnostics, separate from source-bearing errors."""
import re

from django.core.exceptions import ValidationError


_CODE = re.compile(r'[a-z][a-z0-9_]{0,79}\Z')
_NAMESPACE = 'source_assertion_graph'


def _valid_code(code):
    return type(code) is str and _CODE.fullmatch(code) is not None


class SourceAssertionValidationError(ValidationError):
    """An internal graph predicate failed; its code contains no source data."""

    def __init__(self, code):
        if not _valid_code(code):
            raise ValueError('Invalid internal validation diagnostic code.')
        super().__init__('Source assertion graph: ' + code, code=code)


def safe_validation_diagnostic(exc):
    """Return only a trusted single predicate code, never messages or params."""
    if type(exc) is not SourceAssertionValidationError:
        return None
    values = vars(exc)
    errors = values.get('error_list')
    code = values.get('code')
    if ('error_dict' in values or type(errors) is not list or len(errors) != 1
            or errors[0] is not exc or not _valid_code(code)):
        return None
    return {'namespace': _NAMESPACE, 'code': code}
