"""Decision/export boundary tests. Clinical routing has separate pure regressions."""
from copy import deepcopy
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from core import coding_source_review as source, coding_service as service, coding_views
from core.models import CodingContext, CodingDecision, CodingRun, CodingSourceDecision, Encounter, User
from core.tests import test_coding_export as export_tests
from core.tests.test_coding_export import texts


@override_settings(ADMIN_SITE=False, SYNTHETIC_ONLY=True, CODING_PROVIDER='existing')
class SourceDecisionBoundaryTests(TestCase):
    save_decision = export_tests.CodingWordExport.save_decision
    download = export_tests.CodingWordExport.download

    def setUp(self):
        export_tests.CodingWordExport.setUp(self)
        self.saved = {'run': CodingRun.objects.values().get(pk=self.run.pk),
            'decision': CodingDecision.objects.values().get(pk=self.decision.pk),
            'encounter': Encounter.objects.values().get(pk=self.encounter.pk)}
        self.evaluation = {
            'inventory': [
                {'id': 'source-condition:covered', 'condition_text': 'Saved approved condition',
                 'evidence': [{'quote': self.encounter.notes, 'start': 0, 'end': len(self.encounter.notes)}],
                 'approved_codes': ['Z00.00']},
                {'id': 'source-condition:omitted', 'condition_text': 'Omitted synthetic condition',
                 'evidence': [{'quote': self.encounter.notes, 'start': 0, 'end': len(self.encounter.notes)}],
                 'approved_codes': []}],
            'suggestions': [{'id': 'source:candidate', 'condition_id': 'source-condition:omitted',
                'code': 'Z00.01', 'description': 'Synthetic source suggestion', 'eligible': True,
                'route': 'Synthetic > specified', 'evidence': [{'text': self.encounter.notes,
                    'start': 0, 'end': len(self.encounter.notes)}]}],
            'blockers': [], 'coverage': {'limit': 'Explicit fixture boundary'}}
        def assess(e, run):
            service.assert_current(run, e)
            base = CodingDecision.objects.filter(run=run).first()
            return {'contract': source.CONTRACT, 'input_digest': run.input_digest,
                'evaluation': deepcopy(self.evaluation)}, base
        # Test only the persistence/selection boundary here; it cannot make
        # clinical routing pass. The pure and PostgreSQL projection suites do so.
        p = patch.object(source, 'assess', side_effect=assess)
        self.assessment = p.start(); self.addCleanup(p.stop)
        p = patch('core.coding_service.ensure_run', side_effect=AssertionError('No predictions from source review'))
        p.start(); self.addCleanup(p.stop)
        p = patch('core.corti_prediction.execute', side_effect=AssertionError('No provider call'))
        p.start(); self.addCleanup(p.stop)

    def choose(self, action='accept', reason='', candidate='source:candidate', view=None):
        view = view or source.view(self.encounter, self.run, self.user)
        return source.decide(self.encounter, self.user, view['display_token'], view['review_digest'],
            view['prior_revision'], {'source-condition:omitted': {
                'action': action, 'suggestion_id': candidate, 'reason': reason}})

    def bytes(self, query=''):
        response = self.download(query=query)
        self.assertEqual(response.status_code, 200)
        result = b''.join(response.streaming_content)
        response.file_to_stream.close()
        return result

    def assert_originals(self):
        self.assertEqual(self.saved['run'], CodingRun.objects.values().get(pk=self.run.pk))
        self.assertEqual(self.saved['decision'], CodingDecision.objects.values().get(pk=self.decision.pk))
        self.assertEqual(self.saved['encounter'], Encounter.objects.values().get(pk=self.encounter.pk))
        self.assertEqual(self.original, self.path.read_bytes())

    def post_source_review(self, view, *, ajax=True, **overrides):
        data = {'source_review_token': view['display_token'], 'review_digest': view['review_digest'],
            'prior_revision': view['prior_revision'], 'action:source-condition:omitted': 'accept',
            'suggestion:source-condition:omitted': 'source:candidate', **overrides}
        kwargs = {'content_type': 'application/json'} if ajax else {}
        request = RequestFactory().post('/synthetic/coding/source-review/', data, **kwargs)
        request.user = self.user
        return coding_views.source_review(request, self.encounter.pk)

    def test_successful_json_post_assesses_once_and_later_display_and_export_reassess(self):
        import json
        view = source.view(self.encounter, self.run, self.user)
        self.assessment.reset_mock()
        response = self.post_source_review(view)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(body['error'], '')
        self.assertIn('All conditions in this source review have approved ICD codes', body['html'])
        self.assertEqual(self.assessment.call_count, 1)
        decision = CodingSourceDecision.objects.get()
        self.assertEqual(decision.user_id, self.user.pk)
        self.assertEqual(decision.choices['source-condition:omitted']['action'], 'accept')
        self.assertTrue(decision.approved_at)
        self.assertTrue(service.snapshot(self.encounter, self.user)['source_review']['all_coded'])
        self.assertEqual(self.assessment.call_count, 2)
        self.assertIn('Z00.01 — Synthetic source suggestion', texts(self.bytes()))
        self.assertEqual(self.assessment.call_count, 3)
        self.assert_originals()

    def test_plain_source_approval_redirect_does_not_repeat_assessment(self):
        view = source.view(self.encounter, self.run, self.user)
        self.assessment.reset_mock()
        response = self.post_source_review(view, ajax=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/encounters/' + str(self.encounter.pk) + '/?tab=coding')
        self.assertEqual(self.assessment.call_count, 1)
        self.assertEqual(CodingSourceDecision.objects.count(), 1)
        self.assert_originals()

    def test_negotiated_receipt_saves_once_without_rendering_another_panel(self):
        import json
        from django.core import signing
        view = source.view(self.encounter, self.run, self.user)
        request = RequestFactory().post('/synthetic/coding/source-review/', {
            'source_review_token': view['display_token'], 'review_digest': view['review_digest'],
            'prior_revision': '', 'action:source-condition:omitted': 'accept',
            'suggestion:source-condition:omitted': 'source:candidate'},
            content_type='application/json', HTTP_ACCEPT='application/json',
            HTTP_X_QUILLMD_CODING_RESPONSE=coding_views.MUTATION_RESPONSE)
        request.user = self.user
        self.assessment.reset_mock()
        with patch.object(service, 'snapshot', side_effect=AssertionError('No panel projection in save receipt')):
            response = coding_views.source_review(request, self.encounter.pk)
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertTrue(body['saved'])
        self.assertEqual(body['action'], 'source-review')
        self.assertEqual(body['status_url'], f'/encounters/{self.encounter.pk}/coding/status/')
        self.assertNotIn('html', body)
        saved = CodingSourceDecision.objects.get()
        binding = signing.loads(body['receipt'], salt=coding_views.MUTATION_RESPONSE)
        self.assertEqual(binding, {'contract': coding_views.MUTATION_RESPONSE,
            'actor': str(self.user.pk), 'encounter': str(self.encounter.pk),
            'action': 'source-review', 'saved_model': 'core.codingsourcedecision',
            'saved_id': str(saved.pk)})
        self.assertEqual(self.assessment.call_count, 1)
        self.assertTrue(source.view(self.encounter, self.run, self.user)['all_coded'])
        self.assertEqual(self.assessment.call_count, 2)
        self.assert_originals()

    def test_receipt_protocol_cannot_bypass_source_choice_or_display_binding(self):
        import json
        view = source.view(self.encounter, self.run, self.user)
        for changes in ({'source_review_token': 'forged'},
                        {'suggestion:source-condition:omitted': 'source:ineligible'}):
            data = {'source_review_token': view['display_token'], 'review_digest': view['review_digest'],
                'prior_revision': '', 'action:source-condition:omitted': 'accept',
                'suggestion:source-condition:omitted': 'source:candidate', **changes}
            request = RequestFactory().post('/synthetic/coding/source-review/', data,
                content_type='application/json', HTTP_ACCEPT='application/json',
                HTTP_X_QUILLMD_CODING_RESPONSE=coding_views.MUTATION_RESPONSE)
            request.user = self.user
            response = coding_views.source_review(request, self.encounter.pk)
            self.assertEqual(response.status_code, 409)
            self.assertFalse(json.loads(response.content).get('saved', False))
            self.assertFalse(CodingSourceDecision.objects.exists())
        self.assert_originals()

    def test_post_rejects_forged_stale_and_unexpected_response_proofs(self):
        view = source.view(self.encounter, self.run, self.user)
        for values in ({'source_review_token': 'forged'}, {'review_digest': '0' * 64},
                       {'prior_revision': 'other'}, {'source_decision_response': '{}'}):
            with self.subTest(values=values):
                response = self.post_source_review(view, **values)
                self.assertEqual(response.status_code, 409)
                self.assertFalse(CodingSourceDecision.objects.exists())
        self.evaluation['suggestions'][0]['eligible'] = False
        self.assertEqual(self.post_source_review(view).status_code, 409)
        self.assertFalse(CodingSourceDecision.objects.exists())
        self.assert_originals()

    def test_success_response_proof_is_single_use_and_expires_after_callback(self):
        view = source.view(self.encounter, self.run, self.user)
        captured = []
        def respond(proof):
            captured.append(proof)
            first = source.view(self.encounter, self.run, self.user, decision_response=proof)
            self.assertTrue(first['all_coded'])
            self.assertFalse(source.view(self.encounter, self.run, self.user,
                                        decision_response=proof)['available'])
            return first
        self.assessment.reset_mock()
        result = source.decide(self.encounter, self.user, view['display_token'], view['review_digest'], '',
            {'source-condition:omitted': {'action': 'accept', 'suggestion_id': 'source:candidate', 'reason': ''}},
            respond=respond)
        self.assertTrue(result['all_coded'])
        self.assertFalse(source.view(self.encounter, self.run, self.user,
                                    decision_response=captured[0])['available'])
        self.assertEqual(self.assessment.call_count, 1)
        self.assertTrue(source.view(self.encounter, self.run, self.user)['all_coded'])
        self.assertEqual(self.assessment.call_count, 2)

    def test_response_rejects_changed_actor_run_proof_source_and_reference(self):
        view = source.view(self.encounter, self.run, self.user)
        for change in ('actor', 'encounter', 'inputs', 'context', 'config', 'result', 'requests',
                       'selection', 'releases', 'notes', 'reference'):
            with self.subTest(change=change), transaction.atomic():
                def respond(proof):
                    e, run, user = deepcopy(self.encounter), deepcopy(self.run), deepcopy(self.user)
                    if change == 'actor': user.pk = self.department.pk
                    elif change == 'encounter': e.pk = self.department.pk
                    elif change == 'inputs': run.inputs['notes'] = 'Changed input'
                    elif change == 'context': run.context['setting'] = 'unknown'
                    elif change == 'config': run.config['provider'] = 'changed'
                    elif change == 'result': run.result['global_blockers'] = ['Changed proof']
                    elif change == 'requests': run.requests = [{'changed': True}]
                    elif change == 'selection': run.selection['selected_ids'] = []
                    elif change == 'releases': run.releases = []
                    elif change == 'notes': e.notes += ' Changed source.'
                    elif change == 'reference':
                        # Model-copy return exercises rebinding without disabling
                        # append-only database guards on the actual reference.
                        with patch.object(service, 'release_snapshot', return_value=[]):
                            return source.view(e, run, user, decision_response=proof)
                    return source.view(e, run, user, decision_response=proof)
                result = source.decide(self.encounter, self.user, view['display_token'], view['review_digest'], '',
                    {'source-condition:omitted': {'action': 'accept', 'suggestion_id': 'source:candidate', 'reason': ''}},
                    respond=respond)
                self.assertFalse(result['available'])
                transaction.set_rollback(True)
        self.assertFalse(CodingSourceDecision.objects.exists())
        self.assert_originals()

    def test_failed_response_rolls_back_decision_and_expires_unused_proof(self):
        view = source.view(self.encounter, self.run, self.user)
        captured = []
        def respond(proof):
            captured.append(proof)
            raise RuntimeError('Synthetic render failure')
        with self.assertRaisesMessage(RuntimeError, 'Synthetic render failure'):
            source.decide(self.encounter, self.user, view['display_token'], view['review_digest'], '',
                {'source-condition:omitted': {'action': 'accept', 'suggestion_id': 'source:candidate', 'reason': ''}},
                respond=respond)
        self.assertFalse(CodingSourceDecision.objects.exists())
        self.assertFalse(source.view(self.encounter, self.run, self.user,
                                    decision_response=captured[0])['available'])
        self.assert_originals()

    def test_read_does_not_select_or_approve_and_explicit_selection_preserves_original_export(self):
        old = self.bytes()
        view = source.view(self.encounter, self.run, self.user)
        self.assertFalse(view['complete'])
        self.assertEqual(view['counts']['needs_review'], 1)
        self.assertFalse(CodingSourceDecision.objects.exists())
        self.choose(view=view)
        after = source.view(self.encounter, self.run, self.user)
        self.assertTrue(after['complete']); self.assertTrue(after['all_coded'])
        new = self.bytes()
        self.assertNotEqual(old, new)
        self.assertEqual(old, self.bytes('?source_review=provider'))
        self.assertEqual(new, self.bytes())
        self.assertIn('Z00.01 — Synthetic source suggestion', texts(new))
        self.assertEqual(texts(new)[:len(texts(self.original))], texts(self.original))
        self.assert_originals()

    def test_provider_approval_state_and_source_completeness_remain_distinct(self):
        view = service.snapshot(self.encounter, self.user)
        self.assertEqual(view['state_label'], 'Selections approved')
        self.assertEqual(view['completeness_state_label'], 'Partial ICD coding — source review remains')
        self.assertEqual(view['decision'].pk, self.decision.pk)
        self.assertFalse(CodingSourceDecision.objects.exists())
        self.choose()
        after = service.snapshot(self.encounter, self.user)
        self.assertEqual(after['state_label'], 'Selections approved')
        self.assertEqual(after['completeness_state_label'],
                         'All conditions in this source review have approved ICD codes')
        self.assertEqual(after['decision'].pk, self.decision.pk)
        self.assert_originals()

    def test_unknown_held_wrong_condition_and_missing_candidate_refuse(self):
        for candidate in ('', 'selected:0', 'source:other'):
            with self.subTest(candidate=candidate), self.assertRaises(ValidationError):
                self.choose(candidate=candidate)
        self.evaluation['suggestions'][0]['eligible'] = False
        with self.assertRaises(ValidationError): self.choose()
        self.evaluation['suggestions'][0]['eligible'] = True
        self.evaluation['suggestions'][0]['condition_id'] = 'source-condition:covered'
        with self.assertRaises(ValidationError): self.choose()
        self.assertFalse(CodingSourceDecision.objects.exists())
        self.assert_originals()

    def test_no_code_is_explicit_final_outcome_and_never_all_coded(self):
        for reason, candidate in [('', ''), ('A reason', 'source:candidate')]:
            with self.assertRaises(ValidationError): self.choose('no_code', reason, candidate)
        self.choose('no_code', 'Explicit synthetic review outcome.', '')
        view = source.view(self.encounter, self.run, self.user)
        self.assertTrue(view['complete']); self.assertFalse(view['all_coded'])
        exported = texts(self.bytes())
        self.assertTrue(any('explicit no-code outcomes' in text for text in exported))
        self.assertNotIn('Z00.01 — Synthetic source suggestion', exported)
        with self.assertRaises(ValidationError): self.choose()
        self.assert_originals()

    def test_clarification_stays_partial_and_later_explicit_selection_appends(self):
        first = self.choose('needs_clarification', 'Needs source clarification.', '')
        view = source.view(self.encounter, self.run, self.user)
        self.assertFalse(view['complete'])
        self.assertEqual(view['counts']['needs_clarification'], 1)
        self.assertTrue(any('Partial ICD coding' in text for text in texts(self.bytes())))
        second = self.choose()
        self.assertEqual(second.previous_id, first.pk)
        self.assertEqual(CodingSourceDecision.objects.count(), 2)
        self.assertEqual(CodingSourceDecision.objects.get(pk=first.pk).choices,
                         first.choices)
        self.assert_originals()

    def test_stale_replayed_foreign_actor_and_changed_reference_tokens_refuse(self):
        view = source.view(self.encounter, self.run, self.user)
        self.evaluation['suggestions'][0]['description'] = 'Changed reference'
        with self.assertRaises(ValidationError): self.choose(view=view)
        self.evaluation['suggestions'][0]['description'] = 'Synthetic source suggestion'
        outsider = User.objects.create_user(username='source-outsider', email='source-outsider@synthetic.invalid',
                                            verified_at=timezone.now())
        with self.assertRaises(PermissionDenied):
            source.decide(self.encounter, outsider, view['display_token'], view['review_digest'], '', {})
        self.choose(view=view)
        with self.assertRaises(ValidationError): self.choose(view=view)
        self.assertEqual(CodingSourceDecision.objects.count(), 1)

    def test_append_only_database_guard_and_changed_proof_fail_closed_on_export(self):
        decision = self.choose()
        with self.assertRaises(DatabaseError), transaction.atomic():
            CodingSourceDecision.objects.filter(pk=decision.pk).update(choices={})
        with self.assertRaises(DatabaseError), transaction.atomic():
            CodingSourceDecision.objects.filter(pk=decision.pk).delete()
        self.evaluation['suggestions'][0]['eligible'] = False
        self.assertEqual(self.download().status_code, 409)
        self.assertEqual(self.download(query='?source_review=provider').status_code, 200)
        self.assert_originals()

    def unapproved_copy(self, result, selection):
        import uuid
        context = service.context_data(self.encounter)
        self.encounter.pk = uuid.uuid4()
        self.encounter._state.adding = True
        self.encounter.save(force_insert=True)
        CodingContext.objects.create(encounter=self.encounter, updated_by=self.user, data=context)
        inputs, context, releases, key = service.input_snapshot(self.encounter)
        self.run = CodingRun.objects.create(encounter=self.encounter, user=self.user, input_digest=key,
            inputs=inputs, context=context, releases=releases, state='succeeded',
            result=result, selection=selection)

    def test_provider_review_must_freeze_selections_before_source_approval(self):
        self.unapproved_copy(deepcopy(self.run.result), deepcopy(self.run.selection))
        before = CodingRun.objects.values().get(pk=self.run.pk)
        view = source.view(self.encounter, self.run, self.user)
        self.assertTrue(view['available'])
        self.assertFalse(view['can_review'])
        self.assertIn('provider selections first', view['approval_pending_reason'])
        self.assertTrue(view['rows'][1]['suggestions'])
        with self.assertRaisesMessage(ValidationError, 'provider selections first'):
            self.choose(view=view)
        self.assertFalse(CodingSourceDecision.objects.filter(run=self.run).exists())
        self.assertEqual(before, CodingRun.objects.values().get(pk=self.run.pk))
        with patch('core.coding_dispatch.validate_selection', side_effect=lambda _, selections: selections):
            base = service.approve(self.run, self.user, self.run.input_digest, service.selection_digest(self.run))
        decision = self.choose()
        self.assertEqual(decision.base_decision_id, base.pk)
        # Repeating an existing provider approval is still idempotent.
        with patch('core.coding_dispatch.validate_selection', side_effect=lambda _, selections: selections):
            self.assertEqual(service.approve(self.run, self.user, self.run.input_digest,
                             service.selection_digest(self.run)).pk, base.pk)
        self.assertTrue(source.view(self.encounter, self.run, self.user)['all_coded'])

    def test_source_only_approval_can_export_when_provider_omits_every_condition(self):
        self.unapproved_copy({'suggestions': [], 'global_blockers': []},
                             {'selected_ids': [], 'overrides': {}})
        self.evaluation['inventory'] = self.evaluation['inventory'][1:]
        self.assertEqual(self.download().status_code, 409)
        self.choose()
        self.assertTrue(source.view(self.encounter, self.run, self.user)['all_coded'])
        self.assertIn('Z00.01 — Synthetic source suggestion', texts(self.bytes()))
        self.assertFalse(CodingDecision.objects.filter(run=self.run).exists())
        self.assertEqual(self.download(query='?source_review=provider').status_code, 409)
        before = CodingRun.objects.values().get(pk=self.run.pk)
        with self.assertRaisesMessage(ValidationError, 'source review has already been approved'):
            service.update_selection(self.run, self.user, self.run.selection, self.run.selection_revision)
        with patch('core.coding_dispatch.validate_selection', side_effect=lambda _, selections: selections), \
                self.assertRaisesMessage(ValidationError, 'source-only review has already been approved'):
            service.approve(self.run, self.user, self.run.input_digest, service.selection_digest(self.run))
        self.assertEqual(before, CodingRun.objects.values().get(pk=self.run.pk))
        self.assertTrue(source.view(self.encounter, self.run, self.user)['all_coded'])
        self.assertIn('Z00.01 — Synthetic source suggestion', texts(self.bytes()))
