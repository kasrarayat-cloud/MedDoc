"""Select the coding engine independently of clinical generation configuration."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware


SOURCE_CONTEXT_CONTRACT = 'original-note-context-v1'


def prospectively_admitted(encounter):
    from .models import Encounter
    if not isinstance(encounter, Encounter) or encounter._state.adding:
        return False
    cutoff = parse_datetime(getattr(settings, 'CORTI_NEW_ENCOUNTERS_SINCE', '') or '')
    return bool(getattr(settings, 'SYNTHETIC_ONLY', False) and cutoff and is_aware(cutoff)
        and encounter.created_at and encounter.created_at >= cutoff
        and str(encounter.created_by_id) in getattr(settings, 'CORTI_NEW_ENCOUNTER_ACTORS', ()))


def source_context_enabled(encounter):
    from .models import CodingRun, Encounter
    if not isinstance(encounter, Encounter) or encounter._state.adding:
        return False
    first = CodingRun.objects.filter(encounter=encounter).order_by('created_at', 'pk').first()
    if first is not None:
        return first.config.get('source_context_contract') == SOURCE_CONTEXT_CONTRACT
    return prospectively_admitted(encounter)


def provider(encounter=None):
    """Pin existing encounters to their first engine; admit only new test work.

    A prospective actor/date admission cannot relabel historical runs or change
    their input digests. The default legacy provider remains independently set.
    """
    from .models import CodingRun, Encounter
    if isinstance(encounter, Encounter) and not encounter._state.adding:
        from .corti_coding import CONTRACT as CORTI_CONTRACT
        first = CodingRun.objects.filter(encounter=encounter).order_by('created_at', 'pk').first()
        if first is not None:
            return 'corti' if first.inputs.get('engine_contract') == CORTI_CONTRACT else 'existing'
        if prospectively_admitted(encounter):
            return 'corti'
    value = getattr(settings, 'CODING_PROVIDER', 'existing')
    if value not in ('existing', 'corti'):
        raise ValidationError('Unknown configured coding provider.')
    return value


def contract(encounter=None):
    if provider(encounter) == 'corti':
        from .corti_coding import CONTRACT
    else:
        from .coding_engine import CONTRACT
    return CONTRACT


def configuration(actor, encounter):
    if provider(encounter) == 'corti':
        from .corti_prediction import configuration as configure
    else:
        from .coding_provider import configuration as configure
    result = configure(actor, encounter)
    if result.get('provider') == 'corti' and source_context_enabled(encounter):
        result['source_context_contract'] = SOURCE_CONTEXT_CONTRACT
    return result


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
