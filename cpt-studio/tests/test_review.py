"""Decisions, carry/invalidation, readiness and derived state (ARCHITECTURE 5.7). Synthetic data only."""
from dataclasses import replace

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from studio import models, review
from studio.types import ExtractionResult, Fact, sha256_json
from tests.support import factories as f
from tests.support import pipeline_factories as pf


class ReviewCase(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.first = pf.assess(self.s.encounter, pf.standard_result())

    def encounter(self):
        self.s.encounter.refresh_from_db()
        return self.s.encounter

    def current(self, assessment=None):
        assessment = assessment or self.encounter().current_assessment
        return {assessment.proposals.get(pk=pid).key: d for pid, d in review.current_decisions(assessment).items()}

    def actions(self, key, user=None, assessment=None):
        assessment = assessment or self.encounter().current_assessment
        return review.allowed_actions(assessment.proposals.get(key=key), assessment,
                                      self.s.membership(user or self.s.reviewer))

    def new_context(self, **user_values):
        """A member changes encounter metadata: a new current context of the same revision."""
        overrides = {name: Fact(name=name, value=value, origin='user') for name, value in user_values.items()}
        return pf.context(self.s.encounter, self.s.revision, fact_values=pf.facts(**overrides),
                          user_values=user_values)

    def reassess(self, assessment_result, **user_values):
        ctx = self.new_context(**user_values)
        return pf.assess(self.s.encounter, assessment_result, ctx=ctx)


class PersistAssessmentTests(ReviewCase):
    def test_rows_are_recorded_in_order_and_become_current(self):
        result = pf.standard_result()
        enc = self.encounter()
        self.assertEqual(enc.current_assessment_id, self.first.pk)
        self.assertEqual(self.first.sha256, sha256_json(result))
        rows = list(self.first.proposals.order_by('position'))
        self.assertEqual([(p.key, p.position, p.bucket, p.status) for p in rows],
                         [('sel:0', 0, 'selected', 'ready'), ('sel:1', 1, 'selected', 'ready'),
                          ('exc:0', 2, 'excluded', 'excluded'), ('alt:0', 3, 'alternative', 'informational')])
        self.assertEqual(rows[0].evidence[0]['text'], pf.EGD_PASSAGE)
        self.assertEqual(rows[1].modifier_considerations, ['Consider whether modifier 59 applies.'])
        self.assertEqual(self.first.summary, {'selected': 2, 'alternatives': 1, 'excluded': 1})
        event = models.AuditEvent.objects.get(event='assessment.created')
        self.assertEqual(event.data['proposals'], 4)
        self.assertEqual(event.data['selected'], 2)

    def test_proposal_and_encounter_clarifications_are_linked_by_scope(self):
        result = pf.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification',
                        clarifications=[pf.clarification('extent', family='gi.egd')]),
            clarifications=[pf.clarification('service_date', scope='encounter')])
        assessment = self.reassess(result, setting='office')
        linked = assessment.clarifications.get(fact='extent')
        self.assertEqual(linked.proposal, assessment.proposals.get(key='sel:0'))
        self.assertEqual(linked.scope, 'proposal')
        unlinked = assessment.clarifications.get(fact='service_date')
        self.assertIsNone(unlinked.proposal_id)
        self.assertEqual(unlinked.scope, 'encounter')

    def test_identical_result_on_identical_inputs_returns_the_current_assessment(self):
        enc = self.encounter()
        again = review.persist_assessment(encounter=enc, revision=self.first.revision, context=self.first.context,
                                          routing_run=self.first.routing, provider_run=self.first.provider_run,
                                          result=pf.standard_result())
        self.assertEqual(again.pk, self.first.pk)
        self.assertEqual(models.Assessment.objects.count(), 1)

    def test_refuses_a_revision_that_is_no_longer_current(self):
        old_context, old_revision = self.s.context, self.s.revision
        pf.addendum(self.s.encounter, self.s.reviewer, 'Setting confirmed.')
        with self.assertRaisesRegex(ValueError, 'no longer the current revision'):
            review.persist_assessment(encounter=self.s.encounter, revision=old_revision, context=old_context,
                                      routing_run=pf.routing(old_revision), provider_run=None,
                                      result=pf.standard_result())
        self.assertEqual(models.Assessment.objects.count(), 1)

    def test_refuses_a_context_that_was_replaced(self):
        stale = self.s.context
        self.new_context(setting='office')
        with self.assertRaisesRegex(ValueError, 'context changed'):
            review.persist_assessment(encounter=self.s.encounter, revision=self.s.revision, context=stale,
                                      routing_run=pf.routing(self.s.revision), provider_run=None,
                                      result=pf.standard_result())

    def test_refuses_a_provider_run_of_another_revision(self):
        old_run = self.first.provider_run
        rev = pf.addendum(self.s.encounter, self.s.reviewer, 'Setting confirmed.')
        ctx = pf.context(self.s.encounter, rev)
        with self.assertRaisesRegex(ValueError, 'another revision'):
            pf.assess(self.s.encounter, pf.standard_result(text=rev.text), ctx=ctx, run=old_run)

    def test_refuses_a_selected_proposal_without_exact_evidence(self):
        span = pf.evidence(pf.GI_NOTE, pf.EGD_PASSAGE)
        for bad in (replace(span, text='Hot forceps biopsies were taken from the gastric antrum.'),
                    replace(span, exact=False), replace(span, context_index=1),
                    replace(span, start=span.start + 1, end=span.end + 1), replace(span, start=-1)):
            with self.subTest(span=bad), self.assertRaisesRegex(ValueError, 'no exact evidence'):
                self.reassess(pf.result(pf.proposal('sel:0', '43239', spans=[bad])), setting='office')
        self.assertEqual(models.Assessment.objects.count(), 1)

    def test_refuses_inconsistent_lists_keys_and_codes(self):
        cases = {
            'list/status': pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='informational')),
            'alternative ready': pf.result(pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative',
                                                       status='ready')),
            'unique': pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                                pf.proposal('sel:0', '45385', [pf.SNARE_PASSAGE])),
            'truncated': pf.result(pf.proposal('exc:0', '4538512345678', [], bucket='excluded')),
            'fingerprint': pf.result(pf.with_fingerprint(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]), '')),
        }
        for name, result in cases.items():
            with self.subTest(name), self.assertRaises(ValueError):
                self.reassess(result, setting='office')
        self.assertEqual(models.Assessment.objects.count(), 1)

    def test_clarification_scope_must_match_its_owner(self):
        nested_encounter = pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification',
                                                 clarifications=[pf.clarification('service_date', scope='encounter')]))
        orphan = pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                           clarifications=[pf.clarification('extent', scope='proposal')])
        unknown_owner = pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                                  clarifications=[pf.clarification('extent', proposal_key='sel:9')])
        for result in (nested_encounter, orphan, unknown_owner):
            with self.assertRaises(ValueError):
                self.reassess(result, setting='office')

    def test_withdraws_open_clarifications_that_are_not_raised_again(self):
        asked = pf.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification',
                        clarifications=[pf.clarification('extent', family='gi.egd')]),
            pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE], status='needs_clarification',
                        clarifications=[pf.clarification('prep_quality', family='gi.colonoscopy')]),
            clarifications=[pf.clarification('service_date', scope='encounter')])
        second = self.reassess(asked, setting='office')
        answered = second.clarifications.get(fact='prep_quality')
        answered.state = models.Clarification.ANSWERED
        answered.save(update_fields=['state'])
        again = pf.result(
            pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification',
                        clarifications=[pf.clarification('extent', family='gi.egd')]),
            pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE]))
        third = self.reassess(again, setting='asc')
        states = {c.fact: c.state for c in second.clarifications.all()}
        self.assertEqual(states, {'extent': 'open', 'prep_quality': 'answered', 'service_date': 'withdrawn'})
        self.assertEqual([c.fact for c in third.clarifications.filter(state='open')], ['extent'])
        self.assertEqual(models.AuditEvent.objects.filter(event='assessment.created').last().data['withdrawn'], 1)


class DecisionTests(ReviewCase):
    def test_approve_requires_an_acknowledgement(self):
        for acknowledgement in ('', '   '):
            with self.assertRaisesRegex(ValidationError, 'acknowledgement'):
                self.s.decide('sel:0', 'approve', acknowledgement=acknowledgement)
        self.assertFalse(models.Decision.objects.exists())

    def test_approval_records_identity_time_and_binding(self):
        decision = self.s.decide('sel:0', 'approve', note=' Matches the biopsy passage. ')
        proposal = self.s.proposal('sel:0')
        self.assertEqual((decision.reviewer, decision.reviewer_kind), (self.s.reviewer, 'human'))
        self.assertEqual((decision.assessment, decision.revision), (self.first, self.s.revision))
        self.assertEqual(decision.profile_version, 'gi.egd@1')
        self.assertEqual(decision.proposal_fingerprint, proposal.fingerprint)
        self.assertEqual(decision.note, 'Matches the biopsy passage.')
        self.assertIsNotNone(decision.created_at)
        event = models.AuditEvent.objects.get(event='decision.recorded')
        self.assertEqual((event.actor, event.data['action'], event.data['code']), (self.s.reviewer, 'approve', '43239'))
        self.assertNotIn('biopsy passage', str(event.data))
        self.assertNotIn('Reviewed the source', str(event.data))

    def test_agent_decisions_are_recorded_as_agent(self):
        decision = self.s.decide('sel:0', 'approve', self.s.agent)
        self.assertEqual(decision.reviewer_kind, 'agent')
        self.assertIn('automated agent', decision.reviewer.label())

    def test_needs_clarification_can_be_rejected_but_never_approved(self):
        result = pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification',
                                       clarifications=[pf.clarification('extent', family='gi.egd')]))
        self.reassess(result, setting='office')
        self.assertEqual(self.actions('sel:0'), ['reject'])
        with self.assertRaisesRegex(ValidationError, 'not available'):
            self.s.decide('sel:0', 'approve')
        self.assertEqual(self.s.decide('sel:0', 'reject').action, 'reject')

    def test_viewer_has_no_actions_and_is_refused(self):
        self.assertEqual(self.actions('sel:0', self.s.viewer), [])
        with self.assertRaises(PermissionDenied):
            self.s.decide('sel:0', 'approve', self.s.viewer)
        self.assertFalse(models.Decision.objects.exists())

    def test_inactive_or_foreign_membership_is_refused(self):
        membership = self.s.membership(self.s.agent)
        membership.active = False
        membership.save(update_fields=['active'])
        self.assertEqual(self.actions('sel:0', self.s.agent), [])
        with self.assertRaises(PermissionDenied):
            self.s.decide('sel:0', 'approve', self.s.agent)
        other = pf.scenario(workspace_name='Other synthetic workspace')
        outsider = models.Membership.objects.get(user=other.reviewer)
        proposal = self.s.proposal('sel:0')
        self.assertEqual(review.allowed_actions(proposal, self.first, outsider), [])
        with self.assertRaises(PermissionDenied):
            review.record_decision(encounter=self.s.encounter, proposal=proposal, action='reject',
                                   user=other.reviewer, membership=outsider)
        with self.assertRaises(PermissionDenied):
            review.record_decision(encounter=self.s.encounter, proposal=proposal, action='reject',
                                   user=self.s.agent, membership=self.s.membership(self.s.reviewer))

    def test_a_superseded_assessment_cannot_be_decided(self):
        self.reassess(pf.standard_result(), setting='office')
        stale = self.first.proposals.get(key='sel:0')
        self.assertEqual(review.allowed_actions(stale, self.first, self.s.membership(self.s.reviewer)), [])
        with self.assertRaisesRegex(ValidationError, 'not part of the current review'):
            review.record_decision(encounter=self.s.encounter, proposal=stale, action='approve', user=self.s.reviewer,
                                   membership=self.s.membership(self.s.reviewer), acknowledgement='Checked.')

    def test_nothing_can_be_decided_while_a_new_revision_awaits_assessment(self):
        pf.addendum(self.s.encounter, self.s.reviewer, 'Setting confirmed.')
        self.assertEqual(self.actions('sel:0', assessment=self.first), [])
        with self.assertRaisesRegex(ValidationError, 'not part of the current review'):
            self.s.decide('sel:0', 'reject', assessment=self.first)

    def test_alternatives_can_never_be_decided(self):
        self.assertEqual(self.actions('alt:0'), [])
        for action in ('approve', 'reject', 'reinstate', 'revoke'):
            with self.subTest(action), self.assertRaises(ValidationError):
                self.s.decide('alt:0', action)

    def test_unknown_action_is_refused(self):
        with self.assertRaisesRegex(ValidationError, 'Unknown review action'):
            self.s.decide('sel:0', 'approve-all')

    def test_a_decided_proposal_only_allows_revoke(self):
        self.assertEqual(self.actions('sel:0'), ['approve', 'reject'])
        self.s.decide('sel:0', 'approve')
        self.assertEqual(self.actions('sel:0'), ['revoke'])
        for action in ('approve', 'reject', 'reinstate'):
            with self.subTest(action), self.assertRaises(ValidationError):
                self.s.decide('sel:0', action)

    def test_revoke_clears_the_current_decision(self):
        with self.assertRaisesRegex(ValidationError, 'not available'):
            self.s.decide('sel:0', 'revoke')
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:0', 'revoke', note='Approved the wrong card.')
        self.assertEqual(self.current(), {})
        self.assertEqual(self.actions('sel:0'), ['approve', 'reject'])
        self.assertEqual(list(models.Decision.objects.values_list('action', flat=True)), ['approve', 'revoke'])

    def test_reinstate_then_approve_records_both(self):
        self.assertEqual(self.actions('exc:0'), ['reinstate', 'confirm'])
        with self.assertRaises(ValidationError):
            self.s.decide('exc:0', 'approve')
        self.s.decide('exc:0', 'reinstate', note='The colonoscopy was performed today.')
        self.assertEqual(self.current()['exc:0'].action, 'reinstate')
        self.assertEqual(self.actions('exc:0'), ['approve', 'reject', 'revoke'])
        with self.assertRaisesRegex(ValidationError, 'acknowledgement'):
            self.s.decide('exc:0', 'approve', acknowledgement='')
        self.s.decide('exc:0', 'approve')
        self.assertEqual(self.current()['exc:0'].action, 'approve')
        self.assertEqual(list(models.Decision.objects.values_list('action', flat=True)), ['reinstate', 'approve'])
        self.s.decide('exc:0', 'revoke')
        self.assertNotIn('exc:0', self.current())
        self.assertEqual(self.actions('exc:0'), ['reinstate', 'confirm'])

    def test_reinstate_needs_a_reinstatable_exclusion_with_exact_evidence(self):
        span = pf.evidence(pf.GI_NOTE, pf.PLAN_PASSAGE)
        result = pf.result(
            pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=False),
            pf.proposal('exc:1', '45378', bucket='excluded', reinstatable=True, spans=[replace(span, exact=False)]),
            pf.proposal('exc:2', '3017F', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=True, code_kind='cpt2'))
        self.reassess(result, setting='office')
        self.assertEqual(self.actions('exc:0'), [])
        self.assertEqual(self.actions('exc:1'), ['confirm'])  # confirming an exclusion needs no exact evidence
        self.assertEqual(self.actions('exc:2'), ['reinstate', 'confirm'])
        with self.assertRaises(ValidationError):
            self.s.decide('exc:0', 'reinstate')

    def test_an_invalidated_latest_decision_never_resurrects_an_earlier_one(self):
        self.s.decide('exc:0', 'reinstate')
        self.s.decide('exc:0', 'approve')
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:0', 'revoke')
        self.s.decide('sel:0', 'reject')
        rev = pf.addendum(self.s.encounter, self.s.reviewer, 'Setting confirmed.')
        self.assertEqual(review.invalidate_for_new_revision(self.s.encounter, rev), 2)
        self.assertEqual(review.current_decisions(self.first), {})


class CarryAndInvalidateTests(ReviewCase):
    def setUp(self):
        super().setUp()
        self.approved = self.s.decide('sel:0', 'approve', note='EGD biopsy documented.')
        self.rejected = self.s.decide('sel:1', 'reject', self.s.agent, note='Not separately reportable here.')

    def test_context_change_with_identical_proposals_carries_decisions(self):
        self.confirmed = self.s.decide('exc:0', 'confirm', note='Planned; not performed on this date.')
        second = self.reassess(pf.standard_result(), setting='office')
        carried = self.current(second)
        self.assertEqual(set(carried), {'sel:0', 'sel:1', 'exc:0'})
        for key, old in (('sel:0', self.approved), ('sel:1', self.rejected), ('exc:0', self.confirmed)):
            new = carried[key]
            self.assertEqual(new.carried_from, old)
            self.assertEqual((new.action, new.reviewer, new.reviewer_kind, new.note, new.acknowledgement),
                             (old.action, old.reviewer, old.reviewer_kind, old.note, old.acknowledgement))
            self.assertEqual((new.assessment, new.revision), (second, self.s.revision))
            self.assertEqual(new.proposal, second.proposals.get(key=key))
        self.assertFalse(models.DecisionInvalidation.objects.exists())
        self.assertTrue(review.readiness(self.encounter())['reviewed'])

    def test_changed_fingerprint_invalidates_with_the_changed_field_named(self):
        changed = pf.standard_result().proposals
        result = pf.result(pf.with_fingerprint(changed[0], 'f' * 64), *changed[1:])
        second = self.reassess(result, service_date='2026-10-22')
        invalidation = models.DecisionInvalidation.objects.get(decision=self.approved)
        self.assertEqual(invalidation.by_context, second.context)
        self.assertIsNone(invalidation.by_revision)
        self.assertIn('service date: 2026-10-21 → 2026-10-22 [member-supplied]', invalidation.reason)
        # round 7 bypass:0: neither the evidence nor a check result differs, so neither is named
        self.assertIn('the decision on 43239 depends on a context value that changed', invalidation.reason)
        self.assertNotIn('evidence', invalidation.reason)
        self.assertEqual(set(self.current(second)), {'sel:1'})
        self.assertEqual(self.current(second)['sel:1'].carried_from, self.rejected)

    def test_same_fingerprint_with_a_changed_status_is_not_carried(self):
        items = pf.standard_result().proposals
        result = pf.result(replace(items[0], status='needs_clarification',
                                   clarifications=(pf.clarification('extent', family='gi.egd'),)), *items[1:])
        self.reassess(result, setting='office')
        reason = models.DecisionInvalidation.objects.get(decision=self.approved).reason
        self.assertIn('setting: hospital_outpatient → office [member-supplied]', reason)
        self.assertIn('the status of 43239 changed from Ready for review to Needs clarification', reason)

    def test_a_code_no_longer_proposed_is_invalidated(self):
        items = pf.standard_result().proposals
        self.reassess(pf.result(*items[1:]), setting='office')
        reason = models.DecisionInvalidation.objects.get(decision=self.approved).reason
        self.assertIn('43239 is no longer proposed', reason)

    def test_a_new_provider_result_is_named_even_without_a_context_change(self):
        items = pf.standard_result().proposals
        run = pf.provider_run(self.s.encounter, self.s.revision, response=b'{"codes": ["changed"]}')
        pf.assess(self.s.encounter, pf.result(*items[1:]), run=run)
        reason = models.DecisionInvalidation.objects.get(decision=self.approved).reason
        self.assertEqual(reason, 'Re-assessed after changes (provider result): 43239 is no longer proposed.')

    def test_a_new_revision_invalidates_every_current_decision_when_assessed(self):
        rev = pf.addendum(self.s.encounter, self.s.reviewer, 'Setting confirmed as hospital outpatient.')
        ctx = pf.context(self.s.encounter, rev)
        second = pf.assess(self.s.encounter, pf.standard_result(text=rev.text), ctx=ctx)
        for decision in (self.approved, self.rejected):
            invalidation = models.DecisionInvalidation.objects.get(decision=decision)
            self.assertEqual(invalidation.reason, 'Source revised to revision 2')
            self.assertEqual(invalidation.by_revision, rev)
        self.assertEqual(self.current(second), {})
        self.assertFalse(models.Decision.objects.filter(assessment=second).exists())

    def test_invalidate_for_new_revision_before_assessment(self):
        rev = pf.addendum(self.s.encounter, self.s.reviewer, 'Setting confirmed.')
        self.assertEqual(review.invalidate_for_new_revision(self.s.encounter, rev), 2)
        self.assertEqual(review.invalidate_for_new_revision(self.s.encounter, rev), 0)
        reasons = set(models.DecisionInvalidation.objects.values_list('reason', flat=True))
        self.assertEqual(reasons, {'Source revised to revision 2'})
        self.assertEqual(review.current_decisions(self.first), {})
        ready = review.readiness(self.encounter())
        self.assertEqual((ready['draft'], ready['reviewed']), (False, False))
        event = models.AuditEvent.objects.get(event='decisions.invalidated')
        self.assertEqual((event.data['number'], event.data['decisions']), (2, 2))
        ctx = pf.context(self.s.encounter, rev)
        pf.assess(self.s.encounter, pf.standard_result(text=rev.text), ctx=ctx)
        self.assertEqual(models.DecisionInvalidation.objects.count(), 2)

    def test_invalidate_for_new_revision_refuses_a_foreign_revision(self):
        other = pf.scenario(workspace_name='Other synthetic workspace')
        with self.assertRaises(ValueError):
            review.invalidate_for_new_revision(self.s.encounter, other.revision)

    def test_a_carried_decision_can_be_revoked(self):
        second = self.reassess(pf.standard_result(), setting='office')
        self.assertEqual(self.actions('sel:0', assessment=second), ['revoke'])
        self.s.decide('sel:0', 'revoke')
        self.assertEqual(set(self.current(second)), {'sel:1'})


class ReadinessTests(ReviewCase):
    def ready(self):
        return review.readiness(self.encounter())

    def test_undecided_codes_are_named(self):
        self.assertEqual(self.ready(), {'draft': True, 'reviewed': False,
                                        'blockers': ['43239 has no decision', '45385 has no decision', '45378 was excluded by a documentation check: confirm the exclusion or reinstate it']})

    def test_every_selected_code_decided_is_reviewed(self):
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:1', 'reject')
        self.assertEqual(self.ready(), {'draft': True, 'reviewed': False, 'blockers': ['45378 was excluded by a documentation check: confirm the exclusion or reinstate it']})
        self.s.decide('exc:0', 'confirm')
        self.assertEqual(self.ready(), {'draft': True, 'reviewed': True, 'blockers': []})

    def test_open_encounter_clarification_blocks(self):
        self.reassess(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                                clarifications=[pf.clarification('service_date', scope='encounter')]),
                      setting='office')
        self.s.decide('sel:0', 'approve')
        self.assertEqual(self.ready()['blockers'], ['Open clarification: service date'])

    def test_a_clarification_needing_proposal_blocks_until_rejected(self):
        self.reassess(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification',
                                            clarifications=[pf.clarification('extent', family='gi.egd')])),
                      setting='office')
        self.assertEqual(self.ready()['blockers'], ['43239 has an open clarification'])
        self.s.decide('sel:0', 'reject')
        self.assertTrue(self.ready()['reviewed'])

    def test_a_proposal_held_only_by_the_encounter_question_needs_clarification(self):
        self.reassess(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE], status='needs_clarification'),
                                clarifications=[pf.clarification('service_date', scope='encounter')]),
                      setting='office')
        self.assertEqual(self.ready()['blockers'], ['Open clarification: service date', '43239 needs clarification'])

    def test_a_reinstated_exclusion_needs_its_own_decision(self):
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:1', 'approve')
        self.s.decide('exc:0', 'reinstate')
        self.assertEqual(self.ready()['blockers'], ['45378 was reinstated and has no decision'])
        self.s.decide('exc:0', 'reject')
        self.assertTrue(self.ready()['reviewed'])

    def test_no_proposed_code_is_never_reviewed(self):
        # An alternative was proposed and cannot be decided: the blocker says so, never that no code was proposed
        # (refutation p2, reports2:3); a response with no code keeps "No CPT code was proposed".
        self.reassess(pf.result(pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative')),
                      setting='office')
        self.assertEqual(self.ready(), {'draft': True, 'reviewed': False, 'blockers': [
            'No code is selected for approval: the provider proposed only codes that were excluded or offered as '
            'alternatives']})
        self.reassess(pf.result(), setting='asc')
        self.assertEqual(self.ready(), {'draft': True, 'reviewed': False, 'blockers': ['No CPT code was proposed']})

    def test_unsettled_provider_results_block(self):
        for state, blocker in (('failed', 'The provider request failed'), ('not_sent', 'The provider request failed'),
                               ('unknown', 'The provider outcome is unknown')):
            with self.subTest(state):
                run = pf.provider_run(self.s.encounter, self.s.revision, state=state)
                ctx = self.new_context(setting=f'office-{state}')
                pf.assess(self.s.encounter, pf.result(), ctx=ctx, run=run)
                self.assertEqual(self.ready()['blockers'], [blocker])
        ctx = self.new_context(setting='asc')
        pf.assess(self.s.encounter, pf.result(), ctx=ctx, no_provider=True)
        self.assertEqual(self.ready()['blockers'], ['The provider was not run'])

    def test_pending_processing_and_replaced_context_block(self):
        pf.job(self.s.encounter, self.s.revision, 'assess', 'queued')
        self.assertIn('Processing has not finished', self.ready()['blockers'])
        models.Job.objects.update(state='succeeded')
        self.new_context(setting='office')
        self.assertIn('The encounter context changed; re-assessment has not finished', self.ready()['blockers'])

    def test_no_assessment_means_no_report(self):
        other = pf.scenario(workspace_name='Other synthetic workspace')
        self.assertEqual(review.readiness(other.encounter),
                         {'draft': False, 'reviewed': False, 'blockers': ['Revision 1 has not been assessed yet']})


class StateTests(ReviewCase):
    def state(self, enc=None):
        enc = enc or self.encounter()
        return review.refresh_state(enc)

    def fresh(self, text=pf.GI_NOTE, *, extract=True):
        enc = f.encounter(self.s.workspace, self.s.reviewer, title='Another synthetic note')
        rev = f.pasted_revision(enc, self.s.reviewer, text, extract=extract)
        return enc, rev

    def test_processing_while_any_stage_is_active(self):
        for job_state in ('queued', 'running'):
            with self.subTest(job_state):
                job = pf.job(self.s.encounter, self.s.revision, 'assess', job_state)
                self.assertEqual(self.state(), 'processing')
                job.state = 'succeeded'
                job.save(update_fields=['state'])

    def test_stopped_when_the_latest_stage_was_cancelled(self):
        pf.job(self.s.encounter, self.s.revision, 'predict', 'cancelled')
        self.assertEqual(self.state(), 'stopped')

    def test_extraction_failed(self):
        enc, rev = self.fresh(extract=False)
        self.assertEqual(self.state(enc), 'processing')
        f.record(rev, ExtractionResult(status='failed', method='pdf-text', text='',
                                       messages=('No text layer and OCR unavailable.',)))
        self.assertEqual(self.state(enc), 'extraction_failed')
        self.assertEqual(review.readiness(enc)['blockers'], ['No text was extracted'])

    def test_extraction_failed_when_the_extract_stage_died_before_recording(self):
        enc, rev = self.fresh(extract=False)
        pf.job(enc, rev, 'extract', 'failed', error='The stage expired before it could start.')
        self.assertEqual(self.state(enc), 'extraction_failed')

    def test_provider_states_of_the_current_assessment(self):
        for run_state, expected in (('failed', 'provider_failed'), ('not_sent', 'provider_failed'),
                                    ('cancelled', 'provider_failed'), ('unknown', 'provider_unknown'),
                                    ('sending', 'provider_unknown')):
            with self.subTest(run_state):
                run = pf.provider_run(self.s.encounter, self.s.revision, state=run_state)
                pf.assess(self.s.encounter, pf.result(), ctx=self.new_context(setting=run_state), run=run)
                self.assertEqual(self.state(), expected)
        pf.assess(self.s.encounter, pf.result(), ctx=self.new_context(setting='asc'), no_provider=True)
        self.assertEqual(self.state(), 'provider_not_run')

    def test_failed_predict_stage(self):
        job = pf.job(self.s.encounter, self.s.revision, 'predict', 'failed', error='Live calls are not authorized.')
        self.assertEqual(self.state(), 'provider_not_run')
        run = pf.provider_run(self.s.encounter, self.s.revision, state='sending')
        self.assertEqual(self.state(), 'provider_unknown')
        run.state = 'failed'
        run.save(update_fields=['state'])
        self.assertEqual(self.state(), 'provider_failed')
        job.state = 'unknown'
        job.save(update_fields=['state'])
        self.assertEqual(self.state(), 'provider_unknown')

    def test_failed_analyze_or_assess_stage_is_processing_failed(self):
        for kind in ('analyze', 'assess'):
            with self.subTest(kind):
                pf.job(self.s.encounter, self.s.revision, kind, 'failed')
                self.assertEqual(self.state(), 'processing_failed')

    def test_blocked_prediction_behind_an_unknown_outcome(self):
        unknown = pf.provider_run(self.s.encounter, self.s.revision, state='unknown')
        self.new_context(service_date='2026-10-22')
        pf.job(self.s.encounter, self.s.revision, 'predict', 'succeeded')
        self.assertEqual(self.state(), 'provider_unknown')
        unknown.reconciled_at = unknown.created_at
        unknown.save(update_fields=['reconciled_at'])
        self.assertEqual(self.state(), 'processing')

    def test_review_states(self):
        self.assertEqual(self.state(), 'ready_for_review')
        self.s.decide('sel:0', 'approve')
        self.assertEqual(self.encounter().state, 'ready_for_review')
        self.s.decide('sel:1', 'reject')
        self.assertEqual(self.encounter().state, 'ready_for_review')  # the exclusion still needs a decision
        self.s.decide('exc:0', 'confirm')
        self.assertEqual(self.encounter().state, 'reviewed')
        self.s.decide('sel:1', 'revoke')
        self.assertEqual(self.encounter().state, 'ready_for_review')

    def test_needs_clarification(self):
        self.reassess(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                                clarifications=[pf.clarification('service_date', scope='encounter')]),
                      setting='office')
        self.assertEqual(self.state(), 'needs_clarification')
        self.reassess(pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                                pf.proposal('sel:1', '45385', [pf.SNARE_PASSAGE], status='needs_clarification',
                                            clarifications=[pf.clarification('prep_quality')])),
                      setting='asc')
        self.assertEqual(self.state(), 'needs_clarification')
        self.s.decide('sel:1', 'reject')
        self.assertEqual(self.encounter().state, 'ready_for_review')

    def test_no_codes(self):
        self.reassess(pf.result(pf.proposal('alt:0', '45380', [pf.CECUM_PASSAGE], bucket='alternative'),
                                pf.proposal('exc:0', '3017F', [pf.PLAN_PASSAGE], bucket='excluded',
                                            code_kind='cpt2', exclusion_reason='CPT Category II code.')),
                      setting='office')
        self.assertEqual(self.state(), 'no_codes')

    def test_refresh_writes_only_on_change(self):
        self.assertEqual(self.state(), 'ready_for_review')
        stamp = self.encounter().updated_at
        self.assertEqual(self.state(), 'ready_for_review')
        self.assertEqual(self.encounter().updated_at, stamp)

    def test_every_api_state_and_status_has_a_label(self):
        states = ('processing', 'stopped', 'extraction_failed', 'provider_not_run', 'provider_failed',
                  'provider_unknown', 'needs_clarification', 'ready_for_review', 'reviewed', 'no_codes',
                  'processing_failed')
        for state in states:
            self.assertNotEqual(review.state_label(state), 'Unknown state', state)
        self.assertEqual(review.state_label('ready_for_review'), 'Ready for review')
        self.assertEqual(review.state_label('<b>'), 'Unknown state')
        self.assertEqual([review.status_label(s) for s in ('ready', 'needs_clarification', 'excluded',
                                                            'informational', 'other')],
                         ['Ready for review', 'Needs clarification', 'Excluded', 'Not selected', 'Unknown status'])
