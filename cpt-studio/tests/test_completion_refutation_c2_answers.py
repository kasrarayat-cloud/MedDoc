"""Completion repair, refutation cycle 2, lens "answers" (W1-W6; builder W, 2026-11-06): stored answers and the
withdrawal window, back to one source of truth.

- W2, W4: an answer recorded in the earlier form (MemberAnswer.question '') was given to the installed release's fixed
  prompt for its (code, family, fact). It binds by that key, as the installed release bound it - through a
  re-assessment by this release and to a question only the review overlay asks - never by CPT Studio's question or
  reason text, which its member never saw and this release words anew.
- W1, W5, W6: the cycle-1 overlay reopen is removed. Every surface reads the stored assessment until the recompute an
  answer's withdrawal queued has run (the window that leaves is the recorded limitation, API.md); an answer that
  supersedes a value answers the question the stored assessment closed, and is never listed as no longer asked.
- W3: an assessment the engine re-made with a member's answer is this revision's write, so an undo holds the old worker
  for it (ops/install.py UNDO_HAZARDS' written_since and the pure undo functions, read in the test database; the
  installer is never run).

Synthetic data only; every provider is an in-process fake (nothing is sent anywhere).
"""
import json

from django.test import SimpleTestCase
from django.utils import timezone

from studio import customer_api, jobs, models, reports, review, serializers
from studio.validation import engine, questions
from tests.test_cux_r2_details import PipelineCase
from tests.test_cux_r2_overlay import ApiCase, persist_input
from tests.test_cux_review import decide
from tests.test_harness_engine import corti, run, span
from tests.test_pipeline_api import drain
from tests.test_reference import ArchiveMixin
from tests.test_repairs_r1_m import install, run_app_script

SYN = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
COLON = 'gi.colonoscopy'
COLON_HEAD = (SYN + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
              'center\nProcedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was '
              'completed.\n')
FORCEPS = 'A 4 mm polyp in the rectum was removed with cold forceps.'
HEDGED_SNARE = 'A 9 mm polyp in the sigmoid colon was possibly removed with a hot snare.'
HEDGED = COLON_HEAD + FORCEPS + '\n' + HEDGED_SNARE + '\n'
ADVANCED = 'The colonoscope was advanced to the cecum'
UNREACHED = (SYN + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
             'center\nProcedure: Colonoscopy\nThe colonoscope was advanced.\nA 9 mm pedunculated polyp in the sigmoid '
             'colon was removed with a hot snare.\n')
UNREACHED_SNARE = 'was removed with a hot snare'
UPPER_HEAD = (SYN + 'Upper endoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory '
              'surgery center\nProcedure: Upper endoscopy\n')
UPPER_SNARE = 'A 6 mm gastric polyp was possibly removed with a hot snare.'
UPPER_HEDGED = UPPER_HEAD + 'The endoscope was advanced to the second portion of the duodenum.\n' + UPPER_SNARE + '\n'
UPPER_BIOPSY = 'Biopsies of the gastric antrum were taken with cold forceps.'
UPPER_UNREACHED = UPPER_HEAD + 'The endoscope was advanced.\n' + UPPER_BIOPSY + '\n'
OFFICE_SNARE = 'A 9 mm polyp in the sigmoid colon was removed with a hot snare.'
OFFICE_COLON = (SYN + 'Office visit and colonoscopy (fictional)\nDate of service: 2026-10-14\nPlace of service: Office\n'
                'Established patient seen for reflux.\nProcedure: Colonoscopy\nThe colonoscope was advanced to the cecum '
                'and the examination was completed.\n' + OFFICE_SNARE + '\n')
# The installed release's own words for 45385's performed_status question on HEDGED (its engine, b452c6c4, measured by
# the lens): what an install finds on an assessment that release made. The member who answered was shown neither - only
# the fixed prompt "Was this procedure performed on the date of service, as documented?".
INSTALLED_QUESTION = ('The documented colonoscopy leaves the snare removal in doubt (“A 9 mm polyp in the sigmoid colon '
                      'was possibly removed with a hot snare.”). Was a snare removal performed on the date of service?')
INSTALLED_REASON = ('The colonoscopy is documented as performed, but the document does not establish the snare removal '
                    'as done: “A 9 mm polyp in the sigmoid colon was possibly removed with a hot snare.”. The '
                    'routing-era reading of the passages it cites also holds it: No documentation establishes that '
                    'Colonoscopy was performed on the date of service. Read as uncertain: “A 9 mm polyp in the sigmoid '
                    'colon was possibly removed with a hot snare.” (cue “uncertain: A 9 mm polyp in the sigmoid colon '
                    'was possibly removed”, linked passage). Routing reads it as performed elsewhere: “Colonoscopy” (cue '
                    '“section: procedure (Procedure)”, routing).')
# the base's wording of an act in doubt, which this release says as what CPT Studio could not confirm (U9)
INSTALLED_DOUBT, THIS_DOUBT = 'the document does not establish', 'CPT Studio could not confirm'
OTHER_WORDS = 'other words'
UNTRUE_QUALIFICATION = 'The document does not show this service as performed on the date of service.'


def legacy_answer(encounter, assessment, code, family, fact, user, value='not_documented'):
    """An answer as the installed release recorded it: no fingerprint (MemberAnswer.question '')."""
    return models.MemberAnswer.objects.create(encounter=encounter, revision=encounter.current_revision,
                                              assessment=assessment, fact=fact, family=family, code=code, value=value,
                                              answered_by=user)


def rows_of(doc):
    return {row['code']: row for row in doc['codes']}


def facts_asked(doc, fact):
    return [row for row in doc['details_needed'] if row['fact'] == fact]


# --- W2, W4: the binding rule itself -----------------------------------------------------------------------------------

STALE_WORDS = customer_api.BLOCKER_EXACT[review.STALE_ANSWER_BLOCKER]


class EarlierFormKeyBindingTests(SimpleTestCase):
    def test_an_earlier_form_answer_binds_by_its_key_and_a_fingerprinted_one_by_its_fingerprint(self):
        """Cycle 2, answers W2 and W4 (questions.bind): an answer recorded with no fingerprint binds wherever its (code,
        family, fact) is asked, whatever the question's fingerprint - the installed release's binding; one whose key is
        not asked is no longer asked. Controls: a fingerprinted answer binds by its fingerprint alone, and one to a
        question asked differently is listed, never applied."""
        key = ('45385', COLON, 'performed_status')

        def answer(**kw):
            return {'code': '45385', 'family': COLON, 'fact': 'performed_status', 'value': 'not_documented',
                    'question': '', **kw}
        for fingerprint in ('a' * 64, 'b' * 64):  # whatever this release's words make the question's fingerprint
            with self.subTest(fingerprint):
                bound, earlier = questions.bind([answer()], {key: fingerprint})
                self.assertEqual((len(bound), earlier), (1, []))
        bound, earlier = questions.bind([answer(code='45380')], {key: 'a' * 64})
        self.assertEqual((bound, [why for _, why in earlier]), ([], [questions.NO_LONGER_ASKED]))
        bound, earlier = questions.bind([answer(question='a' * 64)], {key: 'a' * 64})
        self.assertEqual((len(bound), earlier), (1, []))
        bound, earlier = questions.bind([answer(question='e' * 64)], {key: 'a' * 64})
        self.assertEqual((bound, [why for _, why in earlier]), ([], [questions.ASKED_DIFFERENTLY]))
        self.assertEqual(questions.bind([answer(value='performed')], {key: 'a' * 64}), ([], []))
        self.assertFalse(hasattr(questions, 'EARLIER_FORM'))  # no reason says a question is asked "in other words"

    def test_the_engine_leaves_an_earlier_form_answer_to_the_overlay_in_either_family(self):
        """Cycle 2, answers W2 had the engine read an earlier-form answer by its key. Refutation cycle 4 (answers 1-3):
        the review overlay reads it, at read time, by its key, as the installed release did (questions.bind, above) -
        the engine leaves every code and fingerprint as it was and records the answer as the overlay's, so no other
        code's stored checks depend on which form an answer took. Controls: a fingerprinted answer to a question asked
        differently is listed as such and changes nothing; an earlier-form answer to a key no longer asked changes
        nothing."""
        for text, value, quote, fact in ((HEDGED, '45385', HEDGED_SNARE, 'performed_status'),
                                         (UNREACHED, '45385', UNREACHED_SNARE, 'extent'),
                                         (UPPER_HEDGED, '43251', UPPER_SNARE, 'performed_status'),
                                         (UPPER_UNREACHED, '43239', UPPER_BIOPSY, 'extent')):
            with self.subTest(value=value, fact=fact):
                codes = corti((value, span(text, quote)))
                before = run(text, codes)
                (asked,) = [p for p in before.proposals if p.code == value]
                self.assertIn(fact, [spec.fact for spec in asked.clarifications])
                family = asked.family
                earlier_form = questions.MemberAnswerInput(value, family, fact, 'not_documented', '', 'a1')
                after = run(text, codes, member_answers=(earlier_form,))
                self.assertEqual([(p.bucket, p.fingerprint) for p in after.proposals],
                                 [(p.bucket, p.fingerprint) for p in before.proposals])
                record = after.completeness['member_answers']
                self.assertEqual((record['applied'], [(e['answer'], e['why']) for e in record['earlier']]),
                                 ([], [('a1', engine.OVERLAY_READ)]))
                other = questions.MemberAnswerInput(value, family, fact, 'not_documented', 'e' * 64, 'x1')
                unasked = questions.MemberAnswerInput(value, family, 'units', 'not_documented', '', 'x2')
                kept = run(text, codes, member_answers=(other, unasked))
                self.assertEqual([p.fingerprint for p in kept.proposals], [p.fingerprint for p in before.proposals])
                self.assertEqual([(e['answer'], e['why']) for e in kept.completeness['member_answers']['earlier']],
                                 [('x1', questions.ASKED_DIFFERENTLY), ('x2', questions.NO_LONGER_ASKED)])


# --- W1, W6 and their controls: the withdrawal window reads the stored assessment everywhere ------------------------

class WithdrawalWindowTests(ArchiveMixin, PipelineCase):
    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()
        self.provider.selections = [('45380', FORCEPS), ('45385', HEDGED_SNARE)]

    def readers(self, encounter_id):
        """Every reader of one encounter: the customer page's codes, readiness and details, the operator's readiness,
        draft report, coding completeness and queue, the customer draft, and the operator view's actions."""
        doc = self.doc(encounter_id)
        encounter = self.encounter(encounter_id)
        snapshot = reports.snapshot(encounter, reports.DRAFT)
        assessment = encounter.current_assessment
        views = review.effective_view(assessment)
        membership = models.Membership.objects.get(user=self.reviewer, workspace=self.ws)
        return {
            'codes': {code: (row['status'], row['sub_label'], row['allowed_actions'], row['why']['qualifications'])
                      for code, row in rows_of(doc).items()},
            'blockers': [item for item in doc['readiness']['blockers'] if item != 'Processing has not finished.'],
            'operator_blockers': [item for item in review.readiness(encounter)['blockers']
                                  if not item.startswith('Processing has not finished')],
            'draft': {item['code']: (item['list'], item['exclusion_reason']) for item in snapshot['proposals']},
            'coding': (snapshot['coding']['state'], snapshot['coding']['reasons']),
            'customer_draft': {item['code']: item['status']
                               for item in reports.customer_snapshot(encounter, reports.DRAFT)['items']},
            'views': {p.code: (views[p.key].reason, review.allowed_actions(p, assessment, membership, views))
                      for p in assessment.proposals.all() if p.bucket != 'alternative'},
            'earlier': doc['earlier_answers'], 'details': [(row['fact'], row['affects']) for row in doc['details_needed']],
            'doc': doc,
        }

    def answer_and_recompute(self, encounter_id, fact, value):
        (row,) = facts_asked(self.doc(encounter_id), fact)
        response = self.save(encounter_id, row, value)  # drains: the recompute runs
        self.assertEqual(response.status_code, 201, response.content)

    def test_a_withdrawn_engine_applied_answer_reads_as_stored_everywhere_until_its_recompute_runs(self):
        """Cycle 2, answers W1: "Not documented" on 45385 (the recompute excludes it by the answer), withdrawn, the
        recompute queued and then stopped. Every reader reads the stored assessment - the code excluded by the member's
        answer, as it was before the withdrawal - and none says "excluded by a documentation check", gives the untrue
        "not performed" qualification, names a blocker whose actions are not offered, or asks the question again beside
        it. After Resume the recompute runs: the question is asked again and 45385 needs a detail."""
        encounter_id = self.upload(HEDGED)
        self.answer_and_recompute(encounter_id, 'performed_status', 'not_documented')
        answered = self.readers(encounter_id)
        self.assertEqual(answered['codes']['45385'][:3], ('excluded', customer_api.UNAVAILABLE_SUB_LABEL, []))
        marker = self.encounter(encounter_id).current_assessment
        (answer,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id)
        revoked = self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke')
        self.assertEqual(revoked.status_code, 201, revoked.content)
        queued = self.readers(encounter_id)
        stopped = self.client.post(f'/api/encounters/{encounter_id}/stop')
        self.assertIn(stopped.status_code, (200, 201, 202), stopped.content)
        held = self.readers(encounter_id)
        self.assertEqual(held['doc']['state'], 'stopped')
        self.assertEqual(self.encounter(encounter_id).current_assessment_id, marker.pk)  # the recompute has not run
        for label, now in (('queued', queued), ('stopped', held)):
            with self.subTest(label):
                # one source of truth: every reader as it read the stored assessment before the withdrawal
                for name in ('codes', 'draft', 'coding', 'customer_draft', 'views'):
                    self.assertEqual(now[name], answered[name], name)
                # and readiness holds while the stored assessment reads an answer that no longer stands (integration of
                # cycle 2): an approval meanwhile could export without 45385 on the strength of the withdrawn answer
                self.assertEqual(now['blockers'], [STALE_WORDS] + answered['blockers'])
                self.assertEqual(now['operator_blockers'], [review.STALE_ANSWER_BLOCKER] + answered['operator_blockers'])
                status, sub_label, allowed, qualifications = now['codes']['45385']
                self.assertNotEqual(sub_label, customer_api.CHECK_EXCLUDED_SUB_LABEL)
                self.assertNotIn(UNTRUE_QUALIFICATION, qualifications)
                self.assertFalse([item for item in now['blockers'] + now['operator_blockers'] if '45385' in item])
                self.assertEqual(now['views']['45385'], (review.DETAIL_UNAVAILABLE, []))
                self.assertEqual(facts_asked(now['doc'], 'performed_status'), [])  # nothing re-asked beside it
                self.assertEqual(now['earlier'], [])
        self.assertNotIn('question', serializers.queue_reasons(self.encounter(encounter_id)))
        resumed = self.client.post(f'/api/encounters/{encounter_id}/resume')
        self.assertIn(resumed.status_code, (200, 201, 202), resumed.content)
        drain()
        after = self.readers(encounter_id)
        self.assertEqual(after['codes']['45385'][:3], ('needs_detail', '', ['reject']))
        (row,) = facts_asked(after['doc'], 'performed_status')
        self.assertIsNone(row['saved'])
        self.assertIn('45385 needs a detail.', after['blockers'])
        self.assertIn('question', serializers.queue_reasons(self.encounter(encounter_id)))
        self.assertEqual(after['draft']['45385'][0], 'undecided')

    def test_the_same_window_reads_alike_on_an_upper_endoscopy(self):
        """Cycle 2, answers W1, another GI family: "Not documented" on 43251's performed_status, withdrawn, the recompute
        stopped - 43251 reads as stored (excluded by the member's answer) on every reader, nothing asks again until
        Resume, and then it needs a detail."""
        self.provider.selections = [('43251', UPPER_SNARE)]
        encounter_id = self.upload(UPPER_HEDGED)
        self.answer_and_recompute(encounter_id, 'performed_status', 'not_documented')
        answered = self.readers(encounter_id)
        self.assertEqual(answered['codes']['43251'][:2], ('excluded', customer_api.UNAVAILABLE_SUB_LABEL))
        (answer,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id)
        self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke')
        self.client.post(f'/api/encounters/{encounter_id}/stop')
        held = self.readers(encounter_id)
        for name in ('codes', 'draft', 'coding', 'customer_draft', 'views'):
            self.assertEqual(held[name], answered[name], name)
        self.assertEqual(held['blockers'][0], STALE_WORDS)  # readiness holds while the withdrawn answer is read
        self.assertLessEqual(set(held['blockers'][1:]), set(answered['blockers']))
        self.assertEqual(facts_asked(held['doc'], 'performed_status'), [])
        self.client.post(f'/api/encounters/{encounter_id}/resume')
        drain()
        after = self.readers(encounter_id)
        self.assertEqual(after['codes']['43251'][0], 'needs_detail')
        self.assertEqual(len(facts_asked(after['doc'], 'performed_status')), 1)

    def test_a_superseding_value_keeps_the_exclusion_answers_its_question_and_marks_no_check_stale(self):
        """Cycle 2, answers W6, and the control "superseding a value keeps the exclusion": "Not documented" on 45385
        (recomputed), then "Cannot confirm" on the same row, the recompute stopped. 45385 stays excluded; 45380 is told
        nothing about review decisions (none was recorded and nothing moved); the new answer is shown on its row and is
        never listed as an earlier answer "no longer asked" (cycle 1's F5). After Resume the engine applies it."""
        encounter_id = self.upload(HEDGED)
        self.answer_and_recompute(encounter_id, 'performed_status', 'not_documented')
        (row,) = facts_asked(self.doc(encounter_id), 'performed_status')
        response = self.client.post(f'/api/encounters/{encounter_id}/details', content_type='application/json',
                                    data=json.dumps({'answers': [{'id': row['id'], 'fact': row['fact'],
                                                                  'value': 'cannot_confirm'}]}))
        self.assertEqual(response.status_code, 201, response.content)
        self.client.post(f'/api/encounters/{encounter_id}/stop')
        first, second = models.MemberAnswer.objects.filter(encounter_id=encounter_id).order_by('answered_at', 'pk')
        self.assertTrue(models.MemberAnswerRevocation.objects.filter(answer=first).exists())
        self.assertFalse(models.MemberAnswerRevocation.objects.filter(answer=second).exists())
        self.assertEqual(second.question, first.question)  # the closed question it answers
        held = self.readers(encounter_id)
        self.assertEqual(held['doc']['state'], 'stopped')
        self.assertEqual(held['codes']['45385'][0], 'excluded')
        self.assertNotIn(customer_api.STALE_WORDS, held['codes']['45380'][3])
        assessment = self.encounter(encounter_id).current_assessment
        views = review.effective_view(assessment)
        self.assertEqual({views[p.key].stale for p in assessment.proposals.all()}, {()})
        (row,) = facts_asked(held['doc'], 'performed_status')
        self.assertEqual((row['saved']['value'], row['saved']['answer_id']), ('cannot_confirm', str(second.pk)))
        self.assertEqual(held['earlier'], [])
        self.client.post(f'/api/encounters/{encounter_id}/resume')
        drain()
        after = self.readers(encounter_id)
        self.assertEqual(after['codes']['45385'][:2], ('excluded', customer_api.UNAVAILABLE_SUB_LABELS['cannot_confirm']))
        applied = self.encounter(encounter_id).current_assessment.completeness['member_answers']['applied']
        self.assertEqual([entry['answer'] for entry in applied], [str(second.pk)])
        self.assertEqual(after['earlier'], [])

    def test_re_answering_after_a_stopped_withdrawal_binds_through_the_recompute(self):
        """Cycle 2, control (answers lens): after a withdrawal whose recompute was stopped the stored reading stands and
        nothing is re-asked; once Resume has run the recompute the question is asked again, and an answer given then
        binds through its own recompute (the engine applies it)."""
        encounter_id = self.upload(HEDGED)
        self.answer_and_recompute(encounter_id, 'performed_status', 'not_documented')
        (answer,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id)
        self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke')
        self.client.post(f'/api/encounters/{encounter_id}/stop')
        self.assertEqual(facts_asked(self.doc(encounter_id), 'performed_status'), [])
        self.client.post(f'/api/encounters/{encounter_id}/resume')
        drain()
        self.answer_and_recompute(encounter_id, 'performed_status', 'cannot_confirm')
        doc = self.doc(encounter_id)
        self.assertEqual(rows_of(doc)['45385']['status'], 'excluded')
        (again,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id, revocation__isnull=True)
        applied = self.encounter(encounter_id).current_assessment.completeness['member_answers']['applied']
        self.assertEqual([entry['answer'] for entry in applied], [str(again.pk)])
        self.assertEqual(doc['earlier_answers'], [])

    def test_a_fingerprinted_answer_to_a_question_asked_differently_is_listed_never_applied(self):
        """Cycle 2, control (answers lens): an answer carrying another question's fingerprint for 45385's
        performed_status is listed as asked differently and never applied - 45385 still needs the detail."""
        encounter_id = self.upload(HEDGED)
        encounter = self.encounter(encounter_id)
        models.MemberAnswer.objects.create(encounter=encounter, revision=encounter.current_revision,
                                           assessment=encounter.current_assessment, fact='performed_status',
                                           family=COLON, code='45385', value='not_documented', question='e' * 64,
                                           answered_by=self.reviewer)
        doc = self.doc(encounter_id)
        self.assertEqual(rows_of(doc)['45385']['status'], 'needs_detail')
        (row,) = facts_asked(doc, 'performed_status')
        self.assertIsNone(row['saved'])
        (listed,) = doc['earlier_answers']
        self.assertEqual((listed['why'], listed['affects']), (questions.ASKED_DIFFERENTLY, ['45385']))
        self.assertNotIn(OTHER_WORDS, json.dumps(doc))


# --- W5: a documented service's engine-applied answer, withdrawn: the same window, read alike --------------------------

class ServiceAnswerWindowTests(ArchiveMixin, PipelineCase):
    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()
        self.provider.selections = [('45385', OFFICE_SNARE)]

    def readers(self, encounter_id):
        doc = self.doc(encounter_id)
        assessment = self.encounter(encounter_id).current_assessment
        return {'rows': facts_asked(doc, 'em_basis'), 'earlier': doc['earlier_answers'],
                'open': [(q['scope'], q['fact']) for q in review.open_questions_of(assessment)],
                'stored': [(row.state, row.answer_id) for row in assessment.clarifications.filter(fact='em_basis')]}

    def test_a_withdrawn_service_answer_reads_as_stored_until_its_recompute_runs(self):
        """Cycle 2, answers W5 (the recorded window, not hidden): "Not documented" on the visit's em_basis (the engine
        closes it with the answer), withdrawn, the recompute stopped. Every reader reads the stored assessment - the
        question closed, no row, no open question, no earlier answer - and none disagrees; after Resume the question is
        asked again."""
        encounter_id = self.upload(OFFICE_COLON)
        (row,) = facts_asked(self.doc(encounter_id), 'em_basis')
        self.assertIn('not_documented', row['allow'])
        self.assertEqual(self.save(encounter_id, row, 'not_documented').status_code, 201)
        (answer,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id)
        answered = self.readers(encounter_id)
        self.assertEqual(answered['stored'], [(models.Clarification.ANSWERED, answer.pk)])
        self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke')
        self.client.post(f'/api/encounters/{encounter_id}/stop')
        held = self.readers(encounter_id)
        self.assertEqual((held['rows'], held['earlier'], held['stored']), ([], [], answered['stored']))
        self.assertNotIn(('service', 'em_basis'), held['open'])
        self.client.post(f'/api/encounters/{encounter_id}/resume')
        drain()
        after = self.readers(encounter_id)
        (row,) = after['rows']
        self.assertIsNone(row['saved'])
        self.assertIn(('service', 'em_basis'), after['open'])


# --- W2: an earlier-form answer through a re-assessment by this release ----------------------------------------------

class EarlierFormThroughReassessmentTests(ArchiveMixin, PipelineCase):
    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()
        self.provider.selections = [('45380', FORCEPS), ('45385', HEDGED_SNARE)]

    def as_installed(self, encounter_id, value, fact, rewrite):
        """The live assessment's question rows of ``value``/``fact`` worded as the installed release worded them, and an
        earlier-form answer to that question on it - what an install finds."""
        encounter = self.encounter(encounter_id)
        assessment = encounter.current_assessment
        rows = list(assessment.clarifications.filter(proposal__code=value, fact=fact))
        self.assertEqual(len(rows), 1)
        question, reason = rewrite(rows[0])
        self.assertNotEqual((question, reason), (rows[0].question, rows[0].reason))
        changed = models.Clarification.objects.filter(pk=rows[0].pk).update(question=question, reason=reason)
        self.assertEqual(changed, 1)
        family = assessment.proposals.get(code=value).family
        return legacy_answer(encounter, assessment, value, family, fact, self.reviewer), assessment

    def assert_still_applied(self, encounter_id, answer, value, before):
        encounter = self.encounter(encounter_id)
        assessment = encounter.current_assessment
        self.assertNotEqual(assessment.pk, before.pk)  # re-made by this release's engine
        doc = self.doc(encounter_id)
        self.assertEqual(rows_of(doc)[value]['status'], 'excluded')
        self.assertEqual(rows_of(doc)[value]['sub_label'], customer_api.UNAVAILABLE_SUB_LABEL)
        # refutation cycle 4 (answers 1-3): read by the review overlay, by its key, at read time - the engine records it
        # as the overlay's and applies nothing itself
        self.assertIn((str(answer.pk), engine.OVERLAY_READ),
                      [(e['answer'], e['why']) for e in assessment.completeness['member_answers']['earlier']])
        self.assertNotIn(str(answer.pk), [e['answer'] for e in assessment.completeness['member_answers']['applied']])
        self.assertEqual(doc['earlier_answers'], [])
        self.assertNotIn(f'{value} needs a detail.', doc['readiness']['blockers'])
        self.assertNotIn(OTHER_WORDS, json.dumps(doc))
        return assessment

    def test_an_earlier_form_answer_stays_applied_after_the_installers_reassess_phase(self):
        """Cycle 2, answers W2 (a): an earlier-form answer to 45385's performed_status on the assessment the installed
        release made (its own question and reason), then jobs.reassess_retained - the installer's reassess phase,
        nothing sent. 45385 stays excluded by the answer, now applied by this release's engine, though this release
        words the question's reason anew; nothing says the question is asked in other words."""
        encounter_id = self.upload(HEDGED)
        answer, before = self.as_installed(encounter_id, '45385', 'performed_status',
                                           lambda row: (INSTALLED_QUESTION, INSTALLED_REASON))
        self.assertEqual(rows_of(self.doc(encounter_id))['45385']['status'], 'excluded')  # as the overlay binds it
        sent = len(self.provider.sent)
        outcome = jobs.reassess_retained(self.encounter(encounter_id), 'c2-w2-synthetic', user=self.reviewer)
        self.assertEqual(outcome['action'], 'queued')
        drain()
        self.assertEqual(len(self.provider.sent), sent)
        after = self.assert_still_applied(encounter_id, answer, '45385', before)
        (stored,) = after.clarifications.filter(proposal__code='45385', fact='performed_status')
        self.assertIsNone(stored.answer_id)  # the overlay answers it at read time (refutation cycle 4)
        self.assertNotEqual(stored.reason, INSTALLED_REASON)  # the words moved; the binding did not depend on them

    def test_an_earlier_form_answer_stays_applied_after_the_member_answers_another_question(self):
        """Cycle 2, answers W2 (b): the same earlier-form answer, then the member answers 45378's base_included ("Cannot
        confirm"): the recompute that answer queues re-makes the assessment with this release's engine, and 45385 stays
        excluded by the earlier answer beside 45378 excluded by the new one."""
        self.provider.selections = [('45378', ADVANCED), ('45380', FORCEPS), ('45385', HEDGED_SNARE)]
        encounter_id = self.upload(HEDGED)
        answer, before = self.as_installed(encounter_id, '45385', 'performed_status',
                                           lambda row: (INSTALLED_QUESTION, INSTALLED_REASON))
        (row,) = facts_asked(self.doc(encounter_id), 'base_included')
        self.assertEqual(row['affects'], ['45378'])
        self.assertEqual(self.save(encounter_id, row, 'cannot_confirm').status_code, 201)
        self.assert_still_applied(encounter_id, answer, '45385', before)
        self.assertEqual(rows_of(self.doc(encounter_id))['45378']['status'], 'excluded')

    def test_an_earlier_form_answer_on_an_upper_endoscopy_stays_applied_after_reassessment(self):
        """Cycle 2, answers W2, another GI family: 43251's performed_status as the installed release worded it ("the
        document does not establish ..." where this release says "CPT Studio could not confirm ..."), an earlier-form
        answer, then the reassess phase: 43251 stays excluded by it."""
        self.provider.selections = [('43251', UPPER_SNARE)]
        encounter_id = self.upload(UPPER_HEDGED)

        def installed(row):
            self.assertIn(THIS_DOUBT, row.reason)
            return row.question, row.reason.replace(THIS_DOUBT, INSTALLED_DOUBT)
        answer, before = self.as_installed(encounter_id, '43251', 'performed_status', installed)
        jobs.reassess_retained(self.encounter(encounter_id), 'c2-w2-synthetic-upper', user=self.reviewer)
        drain()
        self.assert_still_applied(encounter_id, answer, '43251', before)


# --- W4: an earlier-form answer to a question only the overlay asks --------------------------------------------------

class OverlayOnlyQuestionTests(ApiCase):
    def test_an_earlier_form_answer_to_a_question_only_the_overlay_asks_binds_by_its_key(self):
        """Cycle 2, answers W4: the reviewer reinstates 45378 for the same day, so the overlay asks 99213's separate_em -
        a question with no stored row. An earlier-form answer to (99213, office E/M, separate_em) binds by its key, as the
        installed release bound it: 99213 is excluded by it, its row shows the answer, nothing is listed as asked in
        other words, and readiness asks only for the reinstated colonoscopy's decision. The reinstated code's own wait
        (45378's extent, no stored row either) binds the same way."""
        s = persist_input('office_ready_denied')
        decide(s, '45378', 'reinstate', note='Synthetic: the reviewer reinstates the colonoscopy.')
        assessment = s.encounter.current_assessment
        self.assertFalse(assessment.clarifications.filter(proposal__code='99213').exists())  # the overlay's question
        self.assertIn('99213 needs a detail.', self.payload(s)['readiness']['blockers'])
        answer = legacy_answer(s.encounter, assessment, '99213', 'gi.office_em', 'separate_em', s.reviewer)
        doc = self.payload(s)
        row = rows_of(doc)['99213']
        self.assertEqual((row['status'], row['sub_label'], row['allowed_actions']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABEL, []))
        (asked,) = facts_asked(doc, 'separate_em')
        self.assertEqual((asked['saved']['value'], asked['saved']['answer_id']), ('not_documented', str(answer.pk)))
        self.assertEqual(doc['earlier_answers'], [])
        self.assertFalse([item for item in doc['readiness']['blockers'] if item.startswith('99213')])
        self.assertNotIn(OTHER_WORDS, json.dumps(doc))
        self.assertFalse(assessment.clarifications.filter(proposal__code='45378', fact='extent').exists())
        waits = legacy_answer(s.encounter, assessment, '45378', COLON, 'extent', s.reviewer)
        doc = self.payload(s)
        (asked,) = facts_asked(doc, 'extent')
        self.assertEqual(asked['saved']['answer_id'], str(waits.pk))
        self.assertEqual(doc['earlier_answers'], [])

    def test_an_earlier_form_answer_to_a_stored_question_asked_word_for_word_still_binds(self):
        """Cycle 2, control (answers lens): an earlier-form answer to a question the stored assessment asks word for
        word - 45385's performed_status on the hedged snare - binds and excludes 45385, as before."""
        s = persist_input('hedged')
        legacy_answer(s.encounter, s.encounter.current_assessment, '45385', COLON, 'performed_status', s.reviewer)
        doc = self.payload(s)
        self.assertEqual((rows_of(doc)['45385']['status'], rows_of(doc)['45385']['sub_label']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABEL))
        self.assertEqual(doc['earlier_answers'], [])


# --- W3: the undo times a marker assessment as this revision's write ---------------------------------------------------

def undo_reading(since):
    """(hazards, written_since) as CLOSE_STAGES reads them (UNDO_HAZARDS, run here on this database: the installer is
    never run), and the installer's split and hold of that answer for an undo to an older revision (same=False)."""
    body = install.UNDO_HAZARDS + (
        "import datetime\n"
        "hazards = undo_hazards()\n"
        "written = written_since(datetime.datetime.fromisoformat(P['since']), sorted(hazards))\n"
        "print(ANSWER + json.dumps({'hazards': hazards, 'written': written}))\n")
    answer = run_app_script(body, {'since': since.isoformat()})
    closed = {'hazards': answer['hazards'], 'written_since': answer['written']}
    shown = {pk: [reason for reason in reasons if reason in install.SHOWN_HAZARDS]
             for pk, reasons in answer['hazards'].items()}
    hold, notes = install.undo_hold([{'problems': [], 'closed': closed, 'acting': {}, 'shown': shown,
                                      'since': since}], same=False)
    return answer['hazards'], answer['written'], install.web_written_by_time(closed), hold, notes


class MarkerHazardTimingTests(ArchiveMixin, PipelineCase):
    def setUp(self):
        super().setUp()
        self.load_pfs()
        self.load_mue()
        self.provider.selections = [('45380', FORCEPS), ('45385', HEDGED_SNARE)]

    def assert_held(self, encounter_id, since):
        hazards, written, (split_since, before, unplaced), hold, notes = undo_reading(since)
        self.assertEqual(hazards, {encounter_id: ['member_answer']})
        self.assertEqual(written, {encounter_id: ['member_answer']})
        self.assertEqual((split_since, before, unplaced), ({encounter_id: ['member_answer']}, {}, {}))
        self.assertTrue(hold)
        self.assertTrue(any(install.WEB_WRITTEN_NOTE in note for note in notes), notes)
        self.assertFalse([note for note in notes if 'beside the old pair' in note], notes)

    def test_a_marker_with_no_standing_answer_is_this_revisions_write(self):
        """Cycle 2, answers W3: the member's answer, the recompute that made the marker assessment, the answer withdrawn
        and the recompute stopped. The undo names member_answer from the marker alone, counts it as written since the
        switch - only this revision's worker makes one - holds the old worker, and its receipt never says the record
        predates the new web: with the switch before the answer, and with it after the marker was made."""
        since = timezone.now()
        encounter_id = self.upload(HEDGED)
        (row,) = facts_asked(self.doc(encounter_id), 'performed_status')
        self.save(encounter_id, row, 'not_documented')
        marker = self.encounter(encounter_id).current_assessment
        self.assertTrue(questions.answered_away(marker.proposals.get(code='45385')))
        (answer,) = models.MemberAnswer.objects.filter(encounter_id=encounter_id)
        self.client.post(f'/api/encounters/{encounter_id}/details/{answer.pk}/revoke')
        self.client.post(f'/api/encounters/{encounter_id}/stop')
        self.assertEqual(self.encounter(encounter_id).current_assessment_id, marker.pk)
        self.assert_held(encounter_id, since)
        self.assert_held(encounter_id, timezone.now())  # a marker no standing answer explains: always this revision's

    def test_an_earlier_form_answer_given_before_the_switch_makes_no_marker(self):
        """Cycle 2, answers W3 (its second shape, which W2's binding made common): an earlier-form answer given before
        the switch, then this revision's reassess phase re-made the assessment with it - a marker made since the switch,
        for which the undo held the old worker. Refutation cycle 4 (answers 1-3): the review overlay reads an
        earlier-form answer, as the installed release read it, so the reassess phase applies nothing - no marker is made,
        the old worker reads the record exactly as this one does, and the undo has nothing written to hold for."""
        encounter_id = self.upload(HEDGED)
        encounter = self.encounter(encounter_id)
        legacy_answer(encounter, encounter.current_assessment, '45385', COLON, 'performed_status', self.reviewer)
        since = timezone.now()
        jobs.reassess_retained(self.encounter(encounter_id), 'c2-w3-synthetic', user=self.reviewer)
        drain()
        remade = self.encounter(encounter_id).current_assessment
        self.assertFalse(questions.answered_away(remade.proposals.get(code='45385')))
        self.assertGreaterEqual(remade.created_at, since)
        self.assertEqual(rows_of(self.doc(encounter_id))['45385']['status'], 'excluded')  # the overlay reads it
        hazards, written, (split_since, before, unplaced), hold, notes = undo_reading(since)
        self.assertEqual((written, split_since), ({}, {}), (hazards, notes))
        self.assertFalse(hold, notes)
