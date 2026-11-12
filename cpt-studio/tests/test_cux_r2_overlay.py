"""Round-2 refutation repairs of the core repair and customer interface (2026-11-04), repair owner "overlay-and-customer":
the review overlay (studio/validation/review_view.py), the customer contract (studio/customer_api.py), the approved
export's evidence (studio/review.py, approved_items), the operator view's decision (studio/serializers.py). The operator
gate's own repairs (L4-2, L4-3) are in tests/test_operator.py, beside the matrix they extend.

- L7-01 (session decision (e): member answers never release a code): a member's "Not documented" or "Cannot confirm"
  excludes the code it answers and nothing else. A code it excluded still holds every code its presence held - the
  diagnostic-base rule, two E/M levels that hold each other, a reinstated same-day procedure beside an office visit - so
  no member answer lifts a hold, drops another code's question or makes another code approvable; only a recorded
  decision does, by the engine's own rule, as before.
- L3-8 (clear status): a reinstated code whose approval waits on the documentation its stored review.reinstatement
  check names says "Needs a detail", with the details row that asks it, never "Ready for review".
- L3-6: one approval carries one kind and one label everywhere: the agent label exactly when the approver is an agent.
- L3-7, L3-10: "Why this code?" and the approved export's evidence are the same passages by one rule
  (review.evidence_spans): none unless the support reading records the act as shown.
- L3-3: the operator view's decision carries the reviewer's chosen modifier.
- L4-4: a modifier review's source is shown by its title or not at all, never by its key.

DB-free classes read the overlay through tests/test_cux_review's Shape; DB-backed ones go through the customer API.
Synthetic data only; nothing is sent.
"""
import json
from dataclasses import replace

from django.test import Client, SimpleTestCase, TestCase

from studio import customer_api, models, reports, review, serializers
from studio.types import to_jsonable
from studio.validation import review_view
from tests.support import factories as f
from tests.support import operator as ops
from tests.support import pipeline_factories as pf
from tests.test_cux_review import (B, CECUM, HEAD, SHAPES, Shape, actions, assess, decide, persist, retrieval_for)

HEDGED = 'A 9 mm sessile polyp in the sigmoid colon was possibly removed with a cold snare.'
HEDGED_TEXT = HEAD + HEDGED + '\n'
HEDGED_CODES = [('45378', CECUM), ('45385', HEDGED)]
VISIT = 'Established patient seen in the office today for follow-up of reflux.'
NO_COLONOSCOPY = 'A colonoscopy was not performed today.'
OFFICE_DENIED = (B + 'Office visit note (fictional)\nDate of service: 2026-11-03\nPlace of service: Office\n'
                 f'{VISIT}\n{NO_COLONOSCOPY}\n')
OFFICE_CODES = [('99213', VISIT), ('45378', NO_COLONOSCOPY)]
# the same visit with its level documented (99213 ready): reinstating the colonoscopy holds it on the same-day E/M gate
OFFICE_READY_DENIED = (B + 'Office visit note (fictional)\nDate of service: 2026-11-03\nPlace of service: Office\n'
                       f'{VISIT}\nTotal time spent on the date of the encounter was 25 minutes.\nMedical decision '
                       f'making: low complexity.\n{NO_COLONOSCOPY}\n')
ANOSCOPY_LINE = 'Anoscopy was performed and showed grade 2 internal hemorrhoids.'
ANOSCOPY = (B + 'Anoscopy note (fictional)\nDate of service: 2026-11-03\nPlace of service: Office\nProcedure: Anoscopy\n'
            f'{ANOSCOPY_LINE}\n')
COLON, EM = 'gi.colonoscopy', 'gi.office_em'
EXTENT_Q = 'Colonoscopy: confirm the furthest extent reached.'
UNAVAILABLE = ('not_documented', 'cannot_confirm')
# every input the overlay tests read: the suite's shapes, the hedged snare, the office visits beside a denied colonoscopy
INPUTS = {**SHAPES, 'hedged': (HEDGED_TEXT, HEDGED_CODES), 'office_denied': (OFFICE_DENIED, OFFICE_CODES),
          'office_ready_denied': (OFFICE_READY_DENIED, OFFICE_CODES),
          'anoscopy': (ANOSCOPY, [('46600', ANOSCOPY_LINE)])}


def shape_of(name):
    text, codes = INPUTS[name]
    return Shape(name, text=text, codes=codes)


def answer(code, family, fact, value='not_documented'):
    return {'code': code, 'family': family, 'fact': fact, 'value': value}


def check_of(view_or_stored, check_id):
    return next((c for c in view_or_stored.checks if c['id'] == check_id), None)


# --- L7-01: a member answer never releases another code ----------------------------------------------------------------

class MemberAnswerNeverReleasesTests(SimpleTestCase):
    """Session decision (e) of 2026-11-03: "Member answers never release a code." The answered code alone is excluded;
    it still counts wherever its presence held another code, and only a reviewer's or agent's recorded decision lifts
    such a hold."""

    def test_cannot_confirm_on_the_hedged_snare_keeps_the_base_held_on_its_own_question(self):
        shape = shape_of('hedged')
        before = shape.view()
        self.assertEqual([before[c].status for c in ('45378', '45385')], ['needs_clarification'] * 2)
        base_q = 'Is 45378 reported separately from 45385 for this examination?'
        self.assertEqual([q['question'] for q in before['45378'].questions], [base_q])
        answers = [answer('45385', COLON, 'performed_status', 'cannot_confirm')]
        after = shape.view(answers=answers)
        self.assertEqual((after['45385'].status, after['45385'].reason, after['45385'].answer),
                         ('excluded', 'detail_unavailable', 'cannot_confirm'))
        base = after['45378']
        self.assertEqual((base.status, base.released, base.reason, base.withheld_by), ('needs_clarification', (), '', ''))
        self.assertEqual(check_of(base, 'services.base_included'), check_of(shape.by_code['45378'],
                                                                             'services.base_included'))  # word for word
        self.assertEqual(check_of(base, 'services.base_included')['status'], 'warn')
        # only a reading that holds nothing moves: the endoscopic-family note reads the codes still in review
        self.assertTrue(set(base.recomputed) <= {'pfs.endoscopic_base'}, base.recomputed)
        self.assertEqual([q['question'] for q in base.questions], [base_q])
        self.assertNotIn('approve', actions(shape, '45378', after))
        # a recorded decision still releases it by the engine's own rule (the reviewer's rejection of the snare code)
        rejected = shape.view({'45385': 'reject'}, answers=answers)
        self.assertEqual((rejected['45378'].status, rejected['45378'].released), ('ready', ('base_included',)))
        self.assertEqual(actions(shape, '45378', rejected), ['approve', 'reject'])

    def test_not_documented_on_one_em_level_never_picks_the_other(self):
        shape = shape_of('em_pair')
        for answered, other in (('99213', '99214'), ('99214', '99213')):
            with self.subTest(answered=answered):
                for value in UNAVAILABLE:
                    views = shape.view(answers=[answer(answered, EM, 'base_included', value)])
                    self.assertEqual(views[answered].reason, 'detail_unavailable')
                    held = views[other]
                    self.assertEqual((held.status, held.released, held.reason), ('needs_clarification', (), ''))
                    self.assertEqual([q['fact'] for q in held.questions], ['base_included'])
                    self.assertNotIn('approve', actions(shape, other, views))
        both = shape.view(answers=[answer('99213', EM, 'base_included'), answer('99214', EM, 'base_included')])
        self.assertEqual([both[c].reason for c in ('99213', '99214')], ['detail_unavailable'] * 2)
        self.assertEqual([actions(shape, c, both) for c in ('99213', '99214')], [[], []])
        # the reviewer's rejection of one level is a recorded decision: it releases the other, as before
        rejected = shape.view({'99213': 'reject'})
        self.assertEqual((rejected['99214'].status, rejected['99214'].released), ('ready', ('base_included',)))

    def test_no_member_answer_changes_another_codes_status_questions_or_actions(self):
        """Every open proposal-scoped question of every input - stored, or asked by the overlay (a reinstated code's
        waits, a base question a reinstatement raises) - answered either way, under no decision and under each single
        decision a reviewer can record: the answered code is excluded (the answer applied), and every other code keeps
        exactly the status, the open questions, the same-day hold and the actions it had without the answer."""
        compared, applied = 0, set()
        for name in INPUTS:
            shape = shape_of(name)
            decidable = [s for s in shape.stored if s.bucket != 'alternative']
            decision_sets = [{}] + [{s.code: action} for s in decidable for action in
                                    (('reject',) if s.bucket == 'selected' else ('reinstate',))]
            for decisions in decision_sets:
                plain = shape.view(decisions)
                for asked in decidable:
                    for question in plain[asked.code].questions:
                        if question.get('scope') != 'proposal':
                            continue
                        for value in UNAVAILABLE:
                            answered = shape.view(decisions, answers=[answer(asked.code, question['family'],
                                                                             question['fact'], value)])
                            where = (name, asked.code, question['fact'], value, decisions)
                            self.assertEqual(answered[asked.code].reason, 'detail_unavailable', where)
                            applied.add((name, asked.code, question['fact']))
                            for other in decidable:
                                if other.code == asked.code:
                                    continue
                                here = where + (other.code,)
                                mine, base = answered[other.code], plain[other.code]
                                self.assertEqual((mine.status, mine.questions, mine.same_day_held, mine.withheld_by),
                                                 (base.status, base.questions, base.same_day_held, base.withheld_by),
                                                 here)
                                self.assertEqual(actions(shape, other.code, answered, decisions),
                                                 actions(shape, other.code, plain, decisions), here)
                                compared += 1
        self.assertGreaterEqual(compared, 60)
        # the overlay's own questions are part of it: a reinstated code's waits and the base question D14 raises
        self.assertIn(('office_denied', '45378', 'extent'), applied)
        self.assertIn(('office_ready_denied', '45378', 'extent'), applied)
        self.assertIn(('denied', '45378', 'base_included'), applied)

    def test_a_reinstated_procedure_answered_away_still_holds_the_same_day_visit(self):
        shape = shape_of('office_ready_denied')
        self.assertEqual(actions(shape, '99213', shape.view()), ['approve', 'reject'])
        reinstated = shape.view({'45378': 'reinstate'})
        self.assertTrue(reinstated['99213'].same_day_held)
        self.assertNotIn('approve', actions(shape, '99213', reinstated))
        answered = shape.view({'45378': 'reinstate'}, answers=[answer('45378', COLON, 'extent')])
        self.assertEqual(answered['45378'].reason, 'detail_unavailable')
        self.assertTrue(answered['99213'].same_day_held)
        self.assertNotIn('approve', actions(shape, '99213', answered))
        approved = shape.view({'45378': 'reinstate', '99213': 'approve'}, answers=[answer('45378', COLON, 'extent')])
        self.assertTrue(approved['99213'].same_day_held)  # an approval made earlier stays out of the approved export


# --- L3-8: a reinstated code that cannot be approved yet says what it needs, with the row that asks it -------------

class ReinstatedCodeWaitsTests(SimpleTestCase):
    """A reinstated exclusion is held to the gates a selected code meets (checks.reinstatement_check): while its stored
    review.reinstatement check names what approval waits for, the overlay asks exactly that of it - the same questions
    a selected code of its family is asked - and reads it as needing clarification, never as ready."""

    def test_the_reinstated_colonoscopy_asks_the_extent_its_check_names(self):
        shape = shape_of('office_denied')
        stored = shape.by_code['45378']
        gate = next(c for c in stored.checks if c['id'] == 'review.reinstatement')
        self.assertEqual(gate['status'], 'warn')
        self.assertIn(EXTENT_Q, gate['detail'])
        self.assertEqual(shape.view()['45378'].questions, ())  # not reinstated: nothing is asked of an exclusion
        view = shape.view({'45378': 'reinstate'})['45378']
        self.assertEqual((view.status, view.withheld_by, view.reinstatement_clear),
                         ('needs_clarification', 'review.reinstatement', False))
        self.assertEqual([(q['id'], q['scope'], q['family'], q['fact'], q['question']) for q in view.questions],
                         [('', 'proposal', COLON, 'extent', EXTENT_Q)])
        self.assertEqual(actions(shape, '45378', shape.view({'45378': 'reinstate'}), {'45378': 'reinstate'}),
                         ['reject', 'revoke'])

    def test_a_member_answer_to_that_question_excludes_the_reinstated_code_only(self):
        shape = shape_of('office_denied')
        for value in UNAVAILABLE:
            views = shape.view({'45378': 'reinstate'}, answers=[answer('45378', COLON, 'extent', value)])
            self.assertEqual((views['45378'].status, views['45378'].reason, views['45378'].answer),
                             ('excluded', 'detail_unavailable', value))
            self.assertEqual(actions(shape, '45378', views, {'45378': 'reinstate'}), ['revoke'])
            self.assertEqual(views['99213'].status, shape.view({'45378': 'reinstate'})['99213'].status)
        # an answer to a question the reinstated code is not asked changes nothing
        views = shape.view({'45378': 'reinstate'}, answers=[answer('45378', COLON, 'target')])
        self.assertEqual((views['45378'].status, views['45378'].reason), ('needs_clarification', ''))

    def test_a_reinstated_base_the_base_rule_holds_reads_as_needing_clarification(self):
        from tests.test_cux_review import ReinstatedBaseTests
        shape = ReinstatedBaseTests.excluded_base_shape()
        view = shape.view({'45378': 'reinstate'})['45378']
        self.assertEqual((view.status, view.withheld_by), ('needs_clarification', 'services.base_included'))
        self.assertEqual([q['fact'] for q in view.questions], ['base_included'])

    def test_a_reinstated_code_its_check_clears_stays_as_stored(self):
        shape = shape_of('denied')
        view = shape.view({'45385': 'reinstate'})['45385']
        self.assertEqual((view.status, view.questions, view.withheld_by, view.reinstatement_clear),
                         ('excluded', (), '', True))
        self.assertEqual(actions(shape, '45385', shape.view({'45385': 'reinstate'}), {'45385': 'reinstate'}),
                         ['approve', 'reject', 'revoke'])

    def test_every_profile_s_waits_are_recognised_from_the_gate_s_own_wording(self):
        """For every family profile, the gate checks.reinstatement_check builds from its required facts (missing or in
        conflict, with and without an unknown date, and with the separate E/M an E/M family waits on) names exactly the
        facts the overlay asks - so no wait is dropped and none is invented."""
        from studio.gi.profiles import PROFILES
        from studio.types import Fact
        from studio.validation import checks
        families = 0
        for slug, profile in PROFILES.items():
            for problem in ('missing', 'conflict'):
                for date_unknown in (False, True):
                    states = [checks.FactState(name, None if problem == 'missing' else Fact(name, None, 'conflict'),
                                               problem) for name in profile.required_facts]
                    holds = list(checks.fact_clarifications(states, profile, slug, 'exc:0'))
                    if slug in checks.EM_FAMILIES:
                        holds.append(checks.separate_em_clarification(('Colonoscopy',), slug, 'exc:0'))
                    gate = to_jsonable(checks.reinstatement_check(holds, date_unknown=date_unknown))
                    stored = review_view.Stored(key='exc:0', code='00000', family=slug, bucket='excluded',
                                                status='excluded', reinstatable=True, checks=(gate,))
                    waits = review_view._reinstatement_waits(stored)
                    where = (slug, problem, date_unknown)
                    if holds:
                        self.assertEqual([w['fact'] for w in waits], [h.fact for h in holds], where)
                        self.assertEqual([w['question'] for w in waits], [h.question for h in holds], where)
                    elif date_unknown:
                        self.assertEqual(waits, (), where)  # the encounter's own date question asks it
                    else:
                        self.assertEqual(gate['status'], 'pass', where)
                        self.assertEqual(waits, (), where)
            families += bool(profile.required_facts)
        self.assertGreater(families, 3)

    def test_every_wait_the_check_can_name_is_asked_and_an_unrecognised_one_still_holds(self):
        shape = shape_of('office_denied')
        stored = shape.by_code['45378']
        lead = ('If a reviewer reinstates this code, it can only be rejected until the documentation is completed (add it '
                'as an addendum): ')
        from studio.validation import checks
        for waits, facts in (([EXTENT_Q, checks.SEPARATE_EM_QUESTION], ['extent', 'separate_em']),
                             (['the date of service is not established for this encounter.'], []),
                             (['Something an earlier release worded differently.'], ['documentation'])):
            with self.subTest(waits=waits):
                gate = {'id': 'review.reinstatement', 'label': 'Approval after reinstatement', 'status': 'warn',
                        'detail': lead + ' '.join(waits), 'source': 'cpt-studio:review-gate'}
                changed = replace(stored, checks=tuple(gate if c['id'] == 'review.reinstatement' else c
                                                       for c in stored.checks))
                rows = [changed if s.key == stored.key else s for s in shape.stored]
                views = review_view.review_view(rows, {stored.key: 'reinstate'}, services=to_jsonable(
                    shape.result.services), retrieval=shape.retrieval,
                    reference_sources=to_jsonable(shape.result.reference_sources))
                view = views[stored.key]
                self.assertEqual([q['fact'] for q in view.questions], facts)
                self.assertEqual(view.status, 'needs_clarification')


# --- L4-4: never a source key ---------------------------------------------------------------------------------------

class ModifierSourceTests(SimpleTestCase):
    def test_a_source_this_release_does_not_bundle_is_shown_by_no_key(self):
        shape = Shape('pair')
        bundled = shape.view()['45380'].modifier_review['sources'][0]
        self.assertTrue(bundled['title'].startswith('Medicare Claims Processing Manual (Pub. 100-04), Chapter 12'))
        newer = 'Rev. 14100; Issued: 01-05-27'
        retrieval = json.loads(json.dumps(shape.retrieval).replace('Rev. 13753; Issued: 05-07-26', newer))
        self.assertIn(newer, json.dumps(retrieval))
        views = Shape('pair', retrieval=retrieval).view()
        for code in ('45380', '45385'):
            with self.subTest(code):
                source = views[code].modifier_review['sources'][0]
                self.assertEqual((source['key'], source['release'], source['title']),
                                 ('cms-claims-manual-100-04-ch12', newer, ''))
                shown = customer_api.modifier_review_of(views[code])
                self.assertEqual(shown['sources'], [])  # the title, or nothing - never the key
                self.assertNotIn('cms-claims-manual', json.dumps(shown))
                self.assertEqual(shown['options'], ['59', 'XS'])
        control = customer_api.modifier_review_of(shape.view()['45380'])
        self.assertEqual(len(control['sources']), 1)
        self.assertTrue(control['sources'][0].startswith('Medicare Claims Processing Manual (Pub. 100-04)'))

    def test_a_source_word_that_is_its_key_is_refused(self):
        for source in ({'key': 'cms-x', 'title': 'cms-x', 'release': 'R1', 'page': '2'},
                       {'key': 'cms-x', 'title': '', 'release': 'R1', 'page': '2'}, {'title': ''}):
            with self.subTest(source):
                self.assertEqual(customer_api._source_words(source), '')
        self.assertEqual(customer_api._source_words({'key': 'cms-x', 'title': 'A CMS manual', 'release': 'R1',
                                                     'effective_start': '2026-01-01', 'page': '2'}),
                         'A CMS manual (R1; in effect from 2026-01-01), page 2')


# --- DB-backed: through the customer API ------------------------------------------------------------------------------

def persist_input(name):
    """An encounter whose live assessment is the engine's own result for INPUTS[name] (tests/test_cux_review.persist,
    for any input here)."""
    if name in SHAPES:
        return persist(name)
    from studio.gi import context as gi_context
    text, codes = INPUTS[name]
    s = pf.scenario(text=text)
    facts = {fact_name: to_jsonable(fact) for fact_name, fact in gi_context.extract_context(text).items()}
    ctx = pf.context(s.encounter, s.revision, fact_values=facts)
    result = assess(text, codes)
    s.assessment = review.persist_assessment(
        encounter=s.encounter, revision=s.revision, context=ctx, routing_run=pf.routing(s.revision),
        provider_run=pf.provider_run(s.encounter, s.revision), result=result,
        retrieval=retrieval_for(result, [c for c, _ in codes]))
    s.encounter.refresh_from_db()
    s.result = result
    return s


class ApiCase(TestCase):
    def client_for(self, user):
        client = Client(enforce_csrf_checks=False)
        client.force_login(user)
        return client

    def payload(self, s, user=None):
        response = self.client_for(user or s.reviewer).get(f'/api/encounters/{s.encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def post(self, s, path, body, user=None):
        return self.client_for(user or s.reviewer).post(path, data=json.dumps(body), content_type='application/json')

    def codes(self, doc):
        return {code['code']: code for code in doc['codes']}

    def row(self, doc, code, fact):
        (row,) = [item for item in doc['details_needed'] if item['affects'] == [code] and item['fact'] == fact]
        return row

    def save(self, s, row, value):
        response = self.post(s, f'/api/encounters/{s.encounter.pk}/details',
                             {'answers': [{'id': row['id'], 'fact': row['fact'], 'value': value}]})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def approve(self, s, code, user=None):
        user = user or s.reviewer
        proposal = s.encounter.current_assessment.proposals.get(code=code)
        return self.post(s, f'/api/encounters/{s.encounter.pk}/decisions',
                         {'proposal_id': str(proposal.pk), 'action': 'approve',
                          'acknowledgement': review.ACKNOWLEDGEMENTS[user.actor_kind]}, user)

    def export(self, s, kind='approved', fmt='txt'):
        made = self.post(s, f'/api/encounters/{s.encounter.pk}/reports', {'kind': kind, 'fmt': fmt})
        self.assertEqual(made.status_code, 201, made.content)
        return self.client_for(s.reviewer).get(made.json()['download_url']).content.decode('utf-8')

    def ready_means_approvable(self, doc):
        for code in doc['codes']:
            if code['status'] == 'ready':
                self.assertIn('approve', code['allowed_actions'], code['code'])


class MemberAnswerApiTests(ApiCase):
    """L7-01 through the details endpoint and the customer payload: the answered code alone leaves the review."""

    def test_cannot_confirm_on_the_snare_leaves_the_base_waiting_on_its_own_question(self):
        s = persist_input('hedged')
        doc = self.payload(s)
        self.assertEqual({c['code']: c['status'] for c in doc['codes']}, {'45378': 'needs_detail',
                                                                          '45385': 'needs_detail'})
        base_row = self.row(doc, '45378', 'base_included')
        self.save(s, self.row(doc, '45385', 'performed_status'), 'cannot_confirm')
        doc = self.payload(s)
        codes = self.codes(doc)
        self.assertEqual((codes['45385']['status'], codes['45385']['sub_label']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABELS['cannot_confirm']))
        self.assertEqual((codes['45378']['status'], codes['45378']['detail_ids']), ('needs_detail', [base_row['id']]))
        self.assertNotIn('approve', codes['45378']['allowed_actions'])
        self.assertEqual(self.row(doc, '45378', 'base_included')['saved'], None)  # still asked, never answered for it
        self.assertEqual(doc['state'], 'awaiting_detail')
        self.assertFalse(doc['readiness']['approved'])
        self.ready_means_approvable(doc)
        self.assertEqual(self.approve(s, '45378').status_code, 409)
        self.assertFalse(models.Decision.objects.filter(encounter=s.encounter).exists())

    def test_an_answer_on_a_reinstated_procedure_never_releases_the_same_day_visit(self):
        s = persist_input('office_ready_denied')
        decide(s, '99213', 'approve')
        decide(s, '45378', 'reinstate', note='Synthetic: the reviewer reinstates the colonoscopy.')
        same_day = '99213 needs a separately identifiable E/M: 45378 was reinstated as a same-day procedure'
        self.assertIn(same_day, review.readiness(s.encounter)['blockers'])
        self.save(s, self.row(self.payload(s), '45378', 'extent'), 'not_documented')
        doc = self.payload(s)
        self.assertEqual(self.codes(doc)['45378']['status'], 'excluded')
        self.assertIn(same_day, review.readiness(s.encounter)['blockers'])  # the answer lifts no hold
        self.assertFalse(doc['readiness']['approved'])
        self.assertEqual(review.approved_items(s.encounter.current_assessment), [])

    def test_not_documented_on_one_em_level_leaves_the_other_waiting(self):
        s = persist('em_pair')
        doc = self.payload(s)
        self.save(s, self.row(doc, '99213', 'base_included'), 'not_documented')
        codes = self.codes(self.payload(s))
        self.assertEqual((codes['99213']['status'], codes['99214']['status']), ('excluded', 'needs_detail'))
        self.assertNotIn('approve', codes['99214']['allowed_actions'])
        self.assertEqual(self.approve(s, '99214').status_code, 409)
        self.assertEqual(review.approved_items(s.encounter.current_assessment), [])


class ReinstatedCodeApiTests(ApiCase):
    """L3-8: a reinstated code its stored check holds says "Needs a detail", with the row that asks it."""

    def test_the_reinstated_colonoscopy_needs_a_detail_with_its_row_and_is_never_ready(self):
        s = persist_input('office_denied')
        decide(s, '45378', 'reinstate', note='Synthetic: the reviewer reinstates the colonoscopy.')
        doc = self.payload(s)
        code = self.codes(doc)['45378']
        self.assertEqual((code['status'], code['status_label'], code['sub_label']),
                         ('needs_detail', 'Needs a detail', customer_api.REINSTATED_SUB_LABEL))
        self.assertEqual(code['allowed_actions'], ['reject', 'revoke'])
        row = self.row(doc, '45378', 'extent')
        self.assertEqual((row['control'], row['allow'], row['saved'], row['addendum_allowed']),
                         ('confirm', ['not_documented', 'cannot_confirm'], None, True))
        self.assertEqual(code['detail_ids'], [row['id']])
        # completion repair (2026-11-06, U9): CPT Studio's reading, never a statement that the document leaves it out
        self.assertIn('CPT Studio could not confirm how far the examination reached.', code['why']['qualifications'])
        self.ready_means_approvable(doc)
        self.assertEqual(self.approve(s, '45378').status_code, 409)
        # the operator view reads the same status (the walk maps it to the customer's)
        full = ops.client(f.user('platform-operator')).get(f'/ops/api/encounters/{s.encounter.pk}').json()
        self.assertEqual({p['code']: p['status'] for p in full['assessment']['proposals']}['45378'],
                         'needs_clarification')
        # answered "not documented": excluded, nothing left to decide but undoing the reinstatement
        self.save(s, row, 'not_documented')
        doc = self.payload(s)
        code = self.codes(doc)['45378']
        self.assertEqual((code['status'], code['sub_label'], code['allowed_actions']),
                         ('excluded', customer_api.UNAVAILABLE_SUB_LABEL, ['revoke']))
        self.assertNotIn('45378 was reinstated and has no decision yet.', doc['readiness']['blockers'])
        self.assertEqual(self.row(doc, '45378', 'extent')['saved']['value'], 'not_documented')


class OneApprovalOneLabelTests(ApiCase):
    """L3-6: the kind an approval is shown with and its agent label agree on every surface: the label is the agent's
    exactly when the approver is an agent (CORE-UX-DESIGN.md 5 and 7: "when the approver is an agent")."""

    def surfaces(self, s, code):
        doc = self.payload(s)
        row = self.codes(doc)[code]
        assessment = s.encounter.current_assessment
        current = review.current_decisions(assessment)
        item = next(i for i in customer_api.approved_export_items(assessment, current, customer_api.views_of(
            assessment, current)) if i['code'] == code)
        return row, item

    def test_every_mix_of_reinstater_and_approver_carries_one_kind_and_one_label(self):
        for reinstater in ('human', 'agent'):
            for approver in ('human', 'agent'):
                with self.subTest(reinstater=reinstater, approver=approver):
                    s = persist('denied')
                    who = {'human': s.reviewer, 'agent': s.agent}
                    decide(s, '45385', 'reinstate', user=who[reinstater], note='Synthetic: the snare is read as done.')
                    decide(s, '45378', 'reject', user=who[approver], note='Synthetic: included in the snare removal.')
                    decide(s, '45385', 'approve', user=who[approver])
                    row, item = self.surfaces(s, '45385')
                    agent = approver == 'agent'
                    self.assertEqual((row['status'], row['decision']['by_kind'], row['sub_label']),
                                     ('approved', approver, customer_api.AGENT_SUB_LABEL if agent else ''))
                    self.assertEqual((item['approver_kind'], item['agent']), (approver, agent))
                    text = self.export(s)
                    self.assertEqual(reports.AGENT_LINE in text, agent)
                    self.assertIn(f'({approver})', text)

    def test_an_agent_approval_is_labelled_on_the_page_the_draft_and_the_approved_export(self):
        s = persist('pair')
        decide(s, '45380', 'approve', user=s.agent)
        row, item = self.surfaces(s, '45380')
        self.assertEqual((row['sub_label'], row['decision']['by_kind'], item['agent']),
                         (customer_api.AGENT_SUB_LABEL, 'agent', True))
        self.assertIn(f'   {customer_api.AGENT_SUB_LABEL}', self.export(s, kind='draft'))


class OnePassageRuleTests(ApiCase):
    """L3-7, L3-10: "Why this code?" and the approved export's evidence are the same passages, by one rule."""

    def quotes(self, doc, code):
        return [(q['text'], q['start'], q['end'], q['page']) for q in self.codes(doc)[code]['why']['quotes']]

    def evidence(self, s, code):
        item = next(i for i in review.approved_items(s.encounter.current_assessment) if i['code'] == code)
        return [(e['text'], e['start'], e['end'], e['page']) for e in item['evidence']]

    def test_a_reinstated_code_whose_act_is_not_established_quotes_no_passage_anywhere(self):
        s = persist('denied')
        decide(s, '45385', 'reinstate', user=s.agent, note='Synthetic: the agent reads the snare as done.')
        self.assertEqual(self.quotes(self.payload(s), '45385'), [])
        decide(s, '45378', 'reject', note='Synthetic: included in the snare removal.')
        decide(s, '45385', 'approve', user=s.agent)
        self.assertEqual((self.quotes(self.payload(s), '45385'), self.evidence(s, '45385')), ([], []))
        self.assertNotIn('Quote:', self.export(s))

    def test_a_code_in_doubt_quotes_no_passage_of_the_service(self):
        s = persist_input('hedged')
        self.assertEqual(self.quotes(self.payload(s), '45385'), [])
        self.assertEqual(len(self.quotes(self.payload(s), '45378')), 1)

    def test_a_code_with_no_support_reading_quotes_nothing_on_the_page_or_in_the_export(self):
        s = persist_input('anoscopy')
        self.assertEqual(s.encounter.current_assessment.proposals.get(code='46600').support, {})
        self.assertEqual(self.quotes(self.payload(s), '46600'), [])
        self.assertEqual(self.approve(s, '46600', s.agent).status_code, 201)
        self.assertEqual((self.quotes(self.payload(s), '46600'), self.evidence(s, '46600')), ([], []))
        self.assertNotIn(ANOSCOPY_LINE, self.export(s).split('Limitations')[0].split('46600', 1)[1])

    def test_the_page_and_the_export_agree_on_every_approved_code(self):
        compared = 0
        for name in ('pair', 'selected', 'siblings', 'egd'):
            with self.subTest(name):
                s = persist(name)
                doc = self.payload(s)
                for code in doc['codes']:
                    if 'approve' in code['allowed_actions']:
                        decide(s, code['code'], 'approve', user=s.agent)
                doc = self.payload(s)
                for item in review.approved_items(s.encounter.current_assessment):
                    self.assertEqual(self.evidence(s, item['code']), self.quotes(doc, item['code']), item['code'])
                    self.assertTrue(self.evidence(s, item['code']))
                    compared += 1
        self.assertGreater(compared, 4)


class OperatorDecisionModifiersTests(TestCase):
    """L3-3: the operator view's decision carries the modifier the reviewer chose (Decision.modifiers), so the download
    check and the walk compare a chosen modifier against the record."""

    def test_the_operator_decision_and_its_history_carry_the_chosen_modifier(self):
        s = persist('pair')
        decide(s, '45385', 'approve', modifiers=['XS'], note='Synthetic: separate lesion.')
        decide(s, '45380', 'approve', user=s.agent)
        full = ops.client(f.user('platform-operator')).get(f'/ops/api/encounters/{s.encounter.pk}').json()
        decisions = {p['code']: p['decision'] for p in full['assessment']['proposals'] if p['decision']}
        self.assertEqual({code: d['modifiers'] for code, d in decisions.items()}, {'45380': [], '45385': ['XS']})
        history = full['decisions']['history']
        self.assertEqual(sorted((d['code'], d['modifiers']) for d in history), [('45380', []), ('45385', ['XS'])])
        persisted = {d.proposal.code: d.modifiers for d in models.Decision.objects.filter(encounter=s.encounter)}
        self.assertEqual(persisted, {'45380': [], '45385': ['XS']})
        decision = models.Decision.objects.get(encounter=s.encounter, proposal__code='45385')
        self.assertEqual(serializers._decision_json(decision)['modifiers'], ['XS'])
