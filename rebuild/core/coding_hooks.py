"""Queue coding only after the saved clinical transaction has committed."""
import logging

from django.db import transaction


def after_saved_document(encounter_id, user_id):
    def enqueue():
        from .coding_service import ensure_run
        from .models import Encounter, User
        try:
            encounter = Encounter.objects.get(pk=encounter_id)
            user = User.objects.get(pk=user_id)
            from .semantic_generation import CLINICAL_SEMANTICS_SCOPE_CONTRACTS
            from .source_assertion_graph import CONTRACT as GRAPH_SCOPE_CONTRACT
            from .coding_dispatch import provider
            if (provider(encounter) == 'corti' and any(
                    isinstance(answer, dict) and answer.get('fact_scope_contract') in (
                        *CLINICAL_SEMANTICS_SCOPE_CONTRACTS, GRAPH_SCOPE_CONTRACT)
                    for answer in encounter.answers.values())):
                # Current reviewed-source coding is explicit. Generation cannot
                # send a prediction before the reviewed document is saved, then
                # spend again merely because that review changes its proof.
                return
            ensure_run(encounter, user, automatic=True)
        except Exception as exc:
            # Independent coding must never roll back a successfully saved
            # clinical document or misclassify its already settled request.
            logging.getLogger(__name__).error('Coding enqueue failed (%s).', type(exc).__name__)
            try:
                from .security import audit
                audit(user, 'coding.enqueue_failed', encounter.pk, department=encounter.department,
                      error_type=type(exc).__name__)
            except Exception:
                pass  # A database outage cannot be recorded in that database.
    transaction.on_commit(enqueue)
