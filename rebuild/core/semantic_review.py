"""One prospective semantic proof reader for display, review and export."""
from copy import deepcopy
import hashlib
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone
from .security import membership


def definitions_for(version):
    from .semantic_preparation import validated_semantic_definitions
    return validated_semantic_definitions(version)


def _typed_value(definition, value, field):
    from .semantic_generation import _string, validate_value
    if definition.get('version') == 4 and definition['value_type'] == 'text':
        # Version 4 checks complete component meaning independently; individual
        # words cannot classify a manual text value as an unrelated source clause.
        _string(value, 'answer', 50000, empty=True)
        return value if value.strip() else None
    return validate_value(definition, value, field)


def validate_answer(encounter,field,answer,definitions=None):
    from .semantic_generation import validate_stored_answer
    definitions=definitions if definitions is not None else definitions_for(encounter.template_version)
    from .source_assertion_graph import SCOPE_CONTRACT
    if definitions[field['key']].get('version') == 4 or answer.get('fact_scope_contract') == SCOPE_CONTRACT:
        if definitions[field['key']].get('version') != 4 or answer.get('fact_scope_contract') != SCOPE_CONTRACT:
            raise ValidationError('The answer does not retain its approved interpretation contract and lineage.')
        from .source_interpretation_store import load_for_answer
        from .source_assertion_generation import validate_stored_answer as validate_graph_answer
        interpretation = load_for_answer(encounter, field, definitions[field['key']], answer)
        if answer.get('semantic_review_mode') == 'manual':
            return _validate_graph_manual(encounter, field, definitions[field['key']], answer, interpretation)
        return validate_graph_answer(encounter.notes, field, definitions[field['key']], answer, interpretation)
    return validate_stored_answer(encounter.notes,field,definitions[field['key']],answer)


MANUAL_PROOF = 'source-graph-manual-decision-v1'


def _manual_payload(field, answer):
    from .semantic_generation import digest
    return {'contract': MANUAL_PROOF, 'field_key': field['key'],
        'source_interpretation': answer.get('source_interpretation'),
        'source_sha256': answer.get('source_sha256'), 'definition_sha256': answer.get('definition_sha256'),
        'history_sha256': digest(answer.get('semantic_edit_history')),
        'answer_sha256': digest({key: value for key, value in answer.items()
            if key not in {'semantic_edit_history', 'semantic_manual_proof'}})}


def _manual_signature(field, answer):
    # Persisted decision proofs do not expire. Standard SECRET_KEY_FALLBACKS
    # preserve verification during an operator-managed signing-key rotation.
    return signing.dumps(_manual_payload(field, answer), salt=MANUAL_PROOF, compress=True)


def _validate_graph_manual(encounter, field, definition, answer, interpretation):
    """Existing explicit clinician edits retain graph lineage and dated history.

    The immutable source graph remains evidence, not permission to claim that a
    manual edit was produced or independently checked by the generation stages.
    """
    from datetime import datetime
    from uuid import UUID
    from .semantic_generation import definition_digest
    from documents.engine import answer_constraint_error
    from .source_assertion_generation import validate_stored_answer as validate_generated
    history = answer.get('semantic_edit_history')
    if answer.get('status') not in ('edited', 'left_blank') or not isinstance(history, list) or not history:
        raise ValidationError('A manual answer requires its recorded clinician decision.')
    try:
        retained = signing.loads(answer.get('semantic_manual_proof', ''), salt=MANUAL_PROOF)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ValidationError('The manual decision or its retained history could not be verified.') from exc
    if retained != _manual_payload(field, answer):
        raise ValidationError('The manual decision changed its retained answer or review history.')
    prior_revision = -1
    for entry in history:
        if (not isinstance(entry, dict) or set(entry) != {'by', 'at', 'revision', 'decision', 'previous'}
                or entry['decision'] not in ('edited', 'left_blank') or type(entry['revision']) is not int
                or entry['revision'] <= prior_revision or not isinstance(entry['previous'], dict)):
            raise ValidationError('The complete manual decision history is inconsistent.')
        prior_revision = entry['revision']
        try:
            if str(UUID(entry['by'])) != entry['by'] or datetime.fromisoformat(entry['at']).tzinfo is None:
                raise ValueError()
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ValidationError('Every manual decision needs its attributed, dated history.') from exc
    validate_generated(encounter.notes, field, definition, history[0]['previous'], interpretation)
    if type(answer.get('reviewed', False)) is not bool:
        raise ValidationError('The manual review attribution is malformed.')
    if answer.get('reviewed', False):
        try:
            if str(UUID(answer['reviewed_by'])) != answer['reviewed_by']:
                raise ValueError()
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ValidationError('The manual review actor is malformed.') from exc
        if type(answer.get('review_revision')) is not int or answer['review_revision'] < 0:
            raise ValidationError('The manual review revision is malformed.')
    elif answer.get('reviewed_by') is not None or answer.get('review_revision') is not None:
        raise ValidationError('An unreviewed manual answer cannot claim a review actor or revision.')
    last = history[-1]
    if (not isinstance(last, dict) or last.get('decision') not in ('edited', 'left_blank')
            or type(last.get('revision')) is not int or last['revision'] < 0
            or not isinstance(last.get('previous'), dict)):
        raise ValidationError('The manual answer decision history is incomplete.')
    try:
        UUID(last['by'])
        if datetime.fromisoformat(last['at']).tzinfo is None:
            raise ValueError()
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValidationError('The manual answer needs an attributed, dated clinician decision.') from exc
    if (answer.get('source_sha256') != hashlib.sha256(encounter.notes.encode()).hexdigest()
            or answer.get('definition_sha256') != definition_digest(definition)):
        raise ValidationError('The manual answer source or approved definition changed.')
    if answer.get('source_interpretation') != last['previous'].get('source_interpretation'):
        raise ValidationError('The manual decision changed its original interpretation lineage.')
    error = answer_constraint_error(field, answer.get('text', ''))
    if error:
        raise ValidationError(error)
    typed = _typed_value(definition, answer.get('text', ''), field)
    if type(typed) is not type(answer.get('value')) or typed != answer.get('value'):
        raise ValidationError('The manual typed value differs from its displayed answer.')
    if (answer['status'] == 'left_blank') != (last['decision'] == 'left_blank'):
        raise ValidationError('The manual blank decision differs from its retained history.')
    if answer['status'] == 'left_blank':
        decision = answer.get('blank_decision') or {}
        if (answer.get('text') or typed is not None or decision.get('by') != last['by']
                or decision.get('revision') != last['revision']):
            raise ValidationError('An explicit blank must retain the clinician’s matching decision.')
    return answer


def displayed_answer(encounter,field,answer,definitions):
    if encounter.status=='finalized':return answer
    try:return validate_answer(encounter,field,answer,definitions)
    except (ValidationError,KeyError,TypeError,ValueError):
        return {**answer,'text':'','status':'conflict','candidate_text':answer.get('text',''),
            'review_reasons':['The retained semantic proof could not be verified. Review its original evidence and enter your decision; it cannot be finalized unchanged.']}


def save_answer(encounter,field,previous,value,actor,reviewed,blank,revision,definitions,withdraw_blank=False,document_level=False):
    from .semantic_generation import CONTRACT,definition_digest,validate_value,protected
    from .generation import is_empty
    if len(value)>20000:raise ValidationError('Answer too long; nothing was truncated or saved.')
    if not value.strip() or is_empty(value):value=''
    if blank and (value or protected(field)):
        raise ValidationError('An explicit blank decision requires an empty, unprotected answer area.')
    prior_blank=previous.get('status')=='left_blank'
    new_blank=blank and not prior_blank
    withdraw=prior_blank and not blank and (bool(value) or withdraw_blank)
    if withdraw and not value:raise ValidationError('Enter the replacement answer to withdraw a reviewed blank decision, or keep the explicit blank decision.')
    changed=value!=previous.get('text','')
    if changed and not value and not blank and not protected(field):
        raise ValidationError('Choose the explicit clinician blank decision to clear this answer. Reviewing an empty displayed field cannot clear its retained evidence.')
    manual=changed or new_blank or withdraw
    if reviewed or manual:membership(actor,encounter.department,roles=['owner','clinician'])
    graph_manual = definitions[field['key']].get('version') == 4
    if graph_manual and manual:
        validate_answer(encounter, field, previous, definitions)
    answer=deepcopy(previous)
    if manual:
        from documents.engine import answer_constraint_error
        error=answer_constraint_error(field,value)
        if error:raise ValidationError(error)
        typed=_typed_value(definitions[field['key']],value,field)
        history=list(previous.get('semantic_edit_history') or [])
        snapshot={k:deepcopy(v) for k,v in previous.items() if k!='semantic_edit_history'}
        history.append({'by':str(actor.pk),'at':timezone.now().isoformat(),'revision':revision,
                        'decision':'left_blank' if new_blank else 'edited','previous':snapshot})
        status='left_blank' if new_blank else 'edited'
        answer.update(text=value,value=typed,status=status,
            evidence_contract=CONTRACT,semantic_review_mode='manual',semantic_edit_history=history,
            source_sha256=hashlib.sha256(encounter.notes.encode()).hexdigest(),
            definition_sha256=definition_digest(definitions[field['key']]))
        if new_blank:answer['blank_decision']={'by':str(actor.pk),'at':timezone.now().isoformat(),'revision':revision,'from_status':previous.get('status','missing')}
        elif answer.get('blank_decision'):answer.pop('blank_decision')
    else:
        # Ticking review alone never turns conflict/ambiguity into a usable answer.
        validate_answer(encounter,field,answer,definitions)
    if document_level:
        if manual:
            for key in ('reviewed', 'reviewed_by', 'review_revision'):
                answer.pop(key, None)
        if graph_manual and answer.get('semantic_review_mode') == 'manual':
            answer['semantic_manual_proof'] = _manual_signature(field, answer)
        return answer
    answer.update(reviewed=reviewed or new_blank,reviewed_by=str(actor.pk) if reviewed or new_blank else None,
                  review_revision=revision if reviewed or new_blank else None)
    if graph_manual and answer.get('semantic_review_mode') == 'manual':
        answer['semantic_manual_proof'] = _manual_signature(field, answer)
    return answer
