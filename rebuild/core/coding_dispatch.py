"""Select the coding engine independently of clinical generation configuration."""
from django.conf import settings
from django.core.exceptions import ValidationError


def provider():
    value = getattr(settings, 'CODING_PROVIDER', 'existing')
    if value not in ('existing', 'corti'):
        raise ValidationError('Unknown configured coding provider.')
    return value


def contract():
    if provider() == 'corti':
        from .corti_coding import CONTRACT
    else:
        from .coding_engine import CONTRACT
    return CONTRACT


def configuration(actor, encounter):
    if provider() == 'corti':
        from .corti_prediction import configuration as configure
    else:
        from .coding_provider import configuration as configure
    return configure(actor, encounter)


def generate(run):
    if run.config.get('provider') == 'corti':
        from .corti_coding import generate as execute
    else:
        from .coding_engine import generate as execute
    return execute(run)


def validate_selection(run, selections):
    if run.config.get('provider') == 'corti':
        from .corti_coding import validate_selection as validate
    else:
        from .coding_engine import validate_selection as validate
    return validate(run, selections)
