"""Current saved-source identity is separate from a manual approval or old proof.

Pure retained-data boundaries: no provider, database or source record changes.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import coding_engine as engine, coding_service as service, coding_recovery as recovery, corti_prediction
from core.tests import test_coding_engine as identity_fixtures


@override_settings(SYNTHETIC_ONLY=True)
class CurrentCodingIdentityTests(SimpleTestCase):
    def case(self, *, missing=False):
        original, fields, definitions = identity_fixtures.CodingSemanticIdentityTests().case(missing=missing)
        answers = deepcopy(original.inputs['answers'])
        answer = answers['subjective']
        previous = deepcopy(answer)
        answer.update(status='edited', semantic_review_mode='manual',
            semantic_edit_history=[{'by':'11111111-1111-4111-8111-111111111111',
                'at':'2026-10-20T10:00:00+00:00', 'revision':1, 'decision':'edited', 'previous':previous}])
        version = N(fields=fields, semantic_definitions=definitions,
            template=N(sha256='a'*64), prepared_sha256='')
        encounter = N(pk='encounter', department_id='department', patient_id='patient',
            patient=N(pk='patient', display_name='Synthetic Avery Sen', reference='synthetic'),
            template_version_id='version', template_version=version, notes=original.inputs['notes'],
            revision=1, status='finalized', service_date=date(2026, 10, 20), answers=answers,
            template_review={'document_approval':{'approved_revision':1, 'actor':'synthetic-reviewer'}})
        return encounter, definitions

    def snapshot(self, encounter, definitions, *, current=True):
        with patch.object(service, 'context_data', return_value={}), \
             patch.object(service, 'release_snapshot', return_value=[]), \
             patch('core.semantic_preparation.validated_semantic_definitions', return_value=definitions):
            return service.input_snapshot(encounter,
                identity_policy=engine.CURRENT_IDENTITY_CONTRACT if current else None)

    def test_manual_answer_is_rechecked_against_current_source_and_historical_v1_stays_held(self):
        encounter, definitions = self.case()
        before = deepcopy((encounter.answers, encounter.template_review))
        old = self.snapshot(encounter, definitions, current=False)
        current = self.snapshot(encounter, definitions)
        self.assertEqual(old[0]['documented_patient_name_evidence']['contract'], engine.SEMANTIC_IDENTITY_CONTRACT)
        self.assertEqual(old[0]['documented_patient_name_evidence']['fields'][0]['finding']['verdict'], 'manual')
        checked = engine.checked_patient_name_evidence(current[0])
        self.assertEqual([n['name_evidence']['quote'] for row in checked for n in row['names']], ['Synthetic Avery Sen'])
        run = N(inputs=current[0], context={}, config={})
        self.assertEqual(engine.identity_blockers(run, {}), [])
        self.assertEqual(service.identity_policy_for(run), engine.CURRENT_IDENTITY_CONTRACT)
        self.assertNotEqual(old[3], current[3])
        self.assertEqual((encounter.answers, encounter.template_review), before)
        self.assertEqual(old, self.snapshot(encounter, definitions, current=False))

    def test_approval_and_matching_registry_cannot_supply_a_missing_source_name(self):
        encounter, definitions = self.case(missing=True)
        current = self.snapshot(encounter, definitions)
        run = N(inputs=current[0], context={'identity_review_reason':'Explicit synthetic review is not source identity.'}, config={})
        self.assertTrue(engine.identity_blockers(run, {}))
        self.assertEqual(engine.checked_patient_name_evidence(current[0])[0]['names'], [])

    def test_changed_source_answer_revision_or_review_invalidates_current_binding(self):
        encounter, definitions = self.case()
        current = self.snapshot(encounter, definitions)
        mutations = [lambda i:i.update(notes=i['notes']+' Another source sentence.'),
            lambda i:i['answers']['subjective'].update(text='A changed current saved answer'),
            lambda i:i.update(revision=2),
            lambda i:i['documented_patient_name_evidence']['review_state']['document_approval'].update(actor='other'),
            lambda i:i['documented_patient_name_evidence']['fields'][0]['names'][0]['name_evidence'].update(quote='Invented Name')]
        for change in mutations:
            changed = deepcopy(current[0]); change(changed)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                engine.checked_patient_name_evidence(changed)
        for change in (lambda e:e.answers['subjective'].update(text='Heartburn only', value='Heartburn only'),
                       lambda e:e.template_review['document_approval'].update(actor='other'),
                       lambda e:setattr(e, 'revision', 2)):
            changed = deepcopy(encounter); change(changed)
            self.assertNotEqual(current[3], self.snapshot(changed, definitions)[3])

    def test_complete_source_name_must_still_be_visible_as_a_complete_saved_value(self):
        encounter, definitions = self.case()
        for text in ('Heartburn only', 'Synthetic Avery Seneca reports heartburn'):
            changed = deepcopy(encounter)
            changed.answers['subjective'].update(text=text, value=text)
            current = self.snapshot(changed, definitions)
            self.assertEqual(engine.checked_patient_name_evidence(current[0])[0]['names'], [])
            self.assertTrue(engine.identity_blockers(N(inputs=current[0], context={}), {}))

    def test_source_identity_conflict_is_never_removed_by_document_approval(self):
        encounter, definitions = self.case()
        current = self.snapshot(encounter, definitions)
        current[0]['patient_identity']['display_name'] = 'Synthetic Different Patient'
        self.assertTrue(engine.identity_blockers(N(inputs=current[0], context={}), {}))

    def retained_pair(self):
        encounter, definitions = self.case()
        from core.corti_coding import CONTRACT as CORTI_CONTRACT
        with patch('core.coding_dispatch.contract', return_value=CORTI_CONTRACT):
            old = self.snapshot(encounter, definitions, current=False)
            current = self.snapshot(encounter, definitions)
        source = N(pk='original-run', encounter_id='encounter', user_id='actor',
            inputs=old[0], context=old[1], releases=old[2], input_digest=old[3],
            config={'provider':'corti', 'mode':'live', 'max_calls':1},
            state='needs_detail', actual_cost=None, result={'original':'retained failure'})
        payload = corti_prediction.payload(source)
        body = json.dumps({'codes':[], 'candidates':[{'system':'cpt', 'code':'99999'}]})
        source.requests = [{'stage':corti_prediction.STAGE, 'attempt':1, 'provider':'corti',
            'state':'succeeded', 'sent':True, 'simulated':False,
            'envelope':{'protocol':corti_prediction.PROTOCOL,
                'identity':corti_prediction.receipts._identity(source), 'payload':payload,
                'config':deepcopy(source.config)},
            'request_sha256':hashlib.sha256(corti_prediction.receipts.encode(payload)).hexdigest(),
            'raw_response':{'body':body, 'redacted':False},
            'response_sha256':hashlib.sha256(body.encode()).hexdigest()}]
        binding = {'contract':recovery.IDENTITY_REVIEW_CONTRACT, 'source_run_id':str(source.pk),
            'source_input_digest':source.input_digest, 'source_requests_digest':service.digest(source.requests),
            'source_result_digest':service.digest(source.result),
            'current_identity_binding_sha256':service.digest(current[0]['documented_patient_name_evidence']),
            'clinical_source_contract':engine.SHARED_SOURCE_CONTRACT,
            'cpt_time_source_contract':'source-bound-clinical-coding-v10'}
        derived = N(pk='local-only-run', encounter_id=source.encounter_id, user_id=source.user_id,
            inputs=current[0], context=current[1], releases=current[2], input_digest=current[3],
            config={**deepcopy(source.config), 'mode':recovery.MODE, 'max_calls':0, 'retained_prediction':binding,
                'clinical_source_contract':engine.SHARED_SOURCE_CONTRACT,
                'cpt_time_source_contract':'source-bound-clinical-coding-v10'},
            requests=[], actual_cost=Decimal('0'), state='needs_detail',
            result={'retained_prediction':binding, 'suggestions':[], 'candidates':{}})
        return source, derived

    def test_retained_identity_review_requires_exact_receipt_and_keeps_parent_unknown_cost(self):
        source, derived = self.retained_pair()
        before = deepcopy(source.__dict__)
        with patch.object(recovery.CodingRun.objects, 'get', return_value=source):
            self.assertIs(recovery.source_for(derived), source)
        self.assertEqual(source.__dict__, before)
        self.assertIsNone(source.actual_cost)
        self.assertEqual(derived.actual_cost, 0)
        self.assertEqual(derived.requests, [])

    def test_retained_identity_review_refuses_parent_or_receipt_tampering_and_unknown_outcomes(self):
        changes = [lambda source,run:source.result.update(original='changed'),
            lambda source,run:source.requests[0]['raw_response'].update(body='changed'),
            lambda source,run:source.requests[0].update(state='uncertain'),
            lambda source,run:source.requests[0]['envelope']['identity'].update(actor_id='different'),
            lambda source,run:setattr(source,'state','running'),
            lambda source,run:setattr(source,'state','uncertain'),
            lambda source,run:setattr(run,'input_digest','0'*64),
            lambda source,run:run.inputs['documented_patient_name_evidence']['review_state']['document_approval'].update(actor='changed'),
            lambda source,run:setattr(run,'context',{'different':'context'}),
            lambda source,run:run.inputs['answers']['subjective'].update(text='Different saved answer'),
            lambda source,run:run.inputs.update(revision=2)]
        for change in changes:
            source, derived = self.retained_pair(); change(source, derived)
            with self.subTest(change=change), patch.object(recovery.CodingRun.objects, 'get', return_value=source), \
                 self.assertRaises(ValidationError):
                recovery.source_for(derived)

    def test_new_scoped_generation_defers_only_automatic_corti_submission(self):
        from core.coding_hooks import after_saved_document
        from core.semantic_generation import CLINICAL_SEMANTICS_SCOPE_CONTRACT
        from core.source_assertion_graph import CONTRACT as GRAPH_SCOPE_CONTRACT
        encounter = N(pk='encounter', answers={'field':{'fact_scope_contract':CLINICAL_SEMANTICS_SCOPE_CONTRACT}})
        actor = N(pk='actor')
        with patch('core.coding_hooks.transaction.on_commit', side_effect=lambda callback:callback()), \
             patch('core.models.Encounter.objects.get', return_value=encounter), \
             patch('core.models.User.objects.get', return_value=actor), \
             patch('core.coding_dispatch.provider', return_value='corti'), \
             patch.object(service, 'ensure_run') as ensure:
            for scope in (CLINICAL_SEMANTICS_SCOPE_CONTRACT, GRAPH_SCOPE_CONTRACT):
                encounter.answers['field']['fact_scope_contract'] = scope
                after_saved_document(encounter.pk, actor.pk)
                ensure.assert_not_called()
            encounter.answers['field']['fact_scope_contract'] = 'positioned-labelled-components-v24'
            after_saved_document(encounter.pk, actor.pk)
            ensure.assert_called_once_with(encounter, actor, automatic=True)

    def test_local_identity_derivative_recomputes_selection_without_copying_unsupported_candidates(self):
        source, expected = self.retained_pair()
        before = deepcopy(source.__dict__)
        saved = []
        class LocalRun:
            objects = N(filter=lambda **_:N(order_by=lambda *_:[source]), get=lambda **_:source)
            DoesNotExist = LookupError
            def __init__(self, **values):
                self.__dict__.update(values)
                self.pk, self.user_id, self.encounter_id = 'new-local-run', self.user.pk, self.encounter.pk
            def save(self, **kwargs):
                saved.append(self)
        result = {'suggestions':[{'id':'supported', 'eligible':True}, {'id':'held', 'eligible':False}],
            'candidates':{'unsupported-alternative':[{'id':'not-a-selection', 'eligible':True}]},
            'global_blockers':[]}
        with patch.object(recovery, 'CodingRun', LocalRun), \
             patch.object(recovery.corti_coding, 'retained_result', return_value=deepcopy(result)), \
             patch.object(recovery, 'audit'), \
             patch.object(corti_prediction, 'execute', side_effect=AssertionError('No new provider submission')) as send:
            derived = recovery.reuse_for_identity_review(N(pk='encounter', department='department'),
                N(pk='actor'), expected.inputs, expected.context, expected.releases, expected.input_digest)
        self.assertEqual(saved, [derived])
        self.assertEqual(derived.selection, {'selected_ids':['supported'], 'overrides':{}})
        self.assertEqual(derived.requests, [])
        self.assertEqual(derived.actual_cost, 0)
        self.assertEqual(derived.config['max_calls'], 0)
        self.assertEqual(source.__dict__, before)
        self.assertIsNone(source.actual_cost)
        send.assert_not_called()

    def test_pending_identical_provider_payload_cannot_be_bypassed_by_context_or_policy_change(self):
        for state in ('queued', 'running', 'uncertain', 'reconciliation'):
            source, current = self.retained_pair()
            source.state = state
            source.context = {'different':'saved context'}
            queryset = N(order_by=lambda *_:[source])
            with self.subTest(state=state), \
                 patch.object(recovery.CodingRun.objects, 'filter', return_value=queryset), \
                 patch.object(corti_prediction, 'execute', side_effect=AssertionError('Duplicate provider request')), \
                 self.assertRaises(ValidationError):
                recovery.reuse_for_identity_review(N(pk='encounter'), N(pk='actor'), current.inputs,
                    current.context, current.releases, current.input_digest)

    def test_graph_or_changed_review_cannot_repeat_an_uncertain_exact_payload(self):
        source, current = self.retained_pair()
        graph_inputs = deepcopy(current.inputs)
        graph_inputs.pop('documented_patient_name_evidence')
        graph_inputs['source_interpretation'] = {'explicit_graph':'changed review metadata'}
        for state, receipts in (('uncertain', []), ('running', []), ('failed', [{'state':'unknown'}])):
            source.state, source.requests = state, receipts
            with self.subTest(state=state), self.assertRaises(ValidationError):
                recovery.assert_no_pending_prediction(N(pk='encounter'), graph_inputs, sources=[source])
        source.state, source.requests = 'succeeded', [{'state':'succeeded'}]
        recovery.assert_no_pending_prediction(N(pk='encounter'), graph_inputs, sources=[source])
