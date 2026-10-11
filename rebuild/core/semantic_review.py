"""One prospective semantic proof reader for display, review and export."""
from copy import deepcopy
import hashlib
from django.core.exceptions import ValidationError
from django.utils import timezone
from .security import membership


def definitions_for(version):
    from .semantic_preparation import validated_semantic_definitions
    return validated_semantic_definitions(version)


def validate_answer(encounter,field,answer,definitions=None):
    from .semantic_generation import validate_stored_answer
    definitions=definitions if definitions is not None else definitions_for(encounter.template_version)
    return validate_stored_answer(encounter.notes,field,definitions[field['key']],answer)


def displayed_answer(encounter,field,answer,definitions):
    if encounter.status=='finalized':return answer
    try:return validate_answer(encounter,field,answer,definitions)
    except (ValidationError,KeyError,TypeError,ValueError):
        return {**answer,'text':'','status':'conflict','candidate_text':answer.get('text',''),
            'review_reasons':['The retained semantic proof could not be verified. Review its original evidence and enter your decision; it cannot be finalized unchanged.']}


def save_answer(encounter,field,previous,value,actor,reviewed,blank,revision,definitions,withdraw_blank=False):
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
    answer=deepcopy(previous)
    if manual:
        from documents.engine import answer_constraint_error
        error=answer_constraint_error(field,value)
        if error:raise ValidationError(error)
        typed=validate_value(definitions[field['key']],value,field)
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
    answer.update(reviewed=reviewed or new_blank,reviewed_by=str(actor.pk) if reviewed or new_blank else None,
                  review_revision=revision if reviewed or new_blank else None)
    return answer
