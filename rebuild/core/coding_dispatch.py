"""Select the coding engine independently of clinical generation configuration."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware


SOURCE_CONTEXT_CONTRACT = 'original-note-context-v1'
AUTHORIZED_SYNTHETIC_SCOPE = 'authorized_synthetic_clinicians'


def authorized_synthetic_actor(actor, department_id):
    """Reuse actual testing enrollment and clinical membership, never a patient list."""
    from . import testing_authority
    from .security import membership
    try:
        if not testing_authority.enabled():
            return False
        testing_authority.admit_actor(actor, department_id)
        membership(actor, department_id, roles=['owner', 'clinician'])
    except (ValidationError, PermissionDenied):
        return False
    return True


def prospectively_admitted(encounter):
    from .models import Encounter
    if not isinstance(encounter, Encounter) or encounter._state.adding:
        return False
    cutoff = parse_datetime(getattr(settings, 'CORTI_NEW_ENCOUNTERS_SINCE', '') or '')
    prospective = bool(getattr(settings, 'SYNTHETIC_ONLY', False) and cutoff and is_aware(cutoff)
        and encounter.created_at and encounter.created_at >= cutoff)
    if not prospective:
        return False
    scope = getattr(settings, 'CORTI_NEW_ENCOUNTER_SCOPE', '')
    if scope:
        if scope != AUTHORIZED_SYNTHETIC_SCOPE:
            raise ValidationError('Unknown prospective synthetic coding scope.')
        return authorized_synthetic_actor(encounter.created_by, encounter.department_id)
    return str(encounter.created_by_id) in getattr(settings, 'CORTI_NEW_ENCOUNTER_ACTORS', ())


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
    from . import source_assertion_coding as shared
    graph_generation = (any(type(d) is dict and d.get('version') == 4
        for d in getattr(getattr(encounter, 'template_version', None), 'semantic_definitions', {}).values())
        or any(type(a) is dict and a.get('fact_scope_contract') == shared.graph.CONTRACT
               for a in getattr(encounter, 'answers', {}).values()))
    selected_provider = provider(encounter)
    if graph_generation and selected_provider != 'corti':
        raise ValidationError('Coding for this newly reviewed form requires Corti. Ask your administrator to configure it; no prediction was sent.')
    if selected_provider == 'corti':
        from .corti_prediction import configuration as configure
    else:
        from .coding_provider import configuration as configure
    result = configure(actor, encounter)
    if result.get('provider') == 'corti' and (graph_generation or source_context_enabled(encounter)):
        result['source_context_contract'] = SOURCE_CONTEXT_CONTRACT
        if getattr(settings, 'CORTI_NEW_ENCOUNTER_SCOPE', '') == AUTHORIZED_SYNTHETIC_SCOPE:
            from .coding_recovery import CONTEXT_CONTRACT
            result['context_review_contract'] = CONTEXT_CONTRACT
        from .models import CodingRun
        from .coding_engine import QUALIFIED_SOURCE_CONTRACT, SHARED_SOURCE_CONTRACT, SOURCE_CONTRACTS
        first = CodingRun.objects.filter(encounter=encounter).order_by('created_at', 'pk').first()
        # Pin old encounters to the contract on their first immutable run.
        # Context-only derivatives already copy that run's configuration.
        contract = first.config.get('clinical_source_contract') if first is not None else QUALIFIED_SOURCE_CONTRACT
        if first is None:
            from .semantic_generation import CLINICAL_SEMANTICS_SCOPE_CONTRACTS
            if any(isinstance(answer, dict) and answer.get('fact_scope_contract') in CLINICAL_SEMANTICS_SCOPE_CONTRACTS
                   for answer in getattr(encounter, 'answers', {}).values()):
                contract = SHARED_SOURCE_CONTRACT
        if graph_generation:
            shared.snapshot(encounter)  # Explicit persisted generation, never a caller-supplied flag.
            contract = shared.CONTRACT
        from .corti_semantics import DOCUMENTED_TIME_CONTRACT, time_contract
        prior_time_contract = None
        if first is not None and not graph_generation and 'cpt_time_source_contract' in first.config:
            try:
                prior_time_contract = time_contract(first.config)
            except ValueError as exc:
                raise ValidationError('Unknown CPT time-source contract.') from exc
        if contract is not None:
            if contract not in SOURCE_CONTRACTS and contract != shared.CONTRACT:
                raise ValidationError('Unknown clinical coding source contract.')
            result['clinical_source_contract'] = contract
            if contract == SHARED_SOURCE_CONTRACT:
                from .corti_semantics import SHARED_TIME_CONTRACT
                result['cpt_time_source_contract'] = SHARED_TIME_CONTRACT
            if contract == QUALIFIED_SOURCE_CONTRACT:
                if first is None:
                    result['cpt_time_source_contract'] = DOCUMENTED_TIME_CONTRACT
                elif prior_time_contract is not None:
                    result['cpt_time_source_contract'] = prior_time_contract
            if contract == shared.CONTRACT:
                from .corti_coding import DIAGNOSTIC_CONTRACT
                result['coding_diagnostic_contract'] = DIAGNOSTIC_CONTRACT
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
