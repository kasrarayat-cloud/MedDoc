"""Unit tests for the differential check of "what changed" (ops/verification/what_changed.py; AMENDMENT-1.md 11.3 over its
6.2 and 5.4; step 6b). Each rule of 6.2 is a synthetic row set and the result 6.2's text gives for it, written here from
the amendment (never from customer_api.what_changed); then the comparison, which fails on every difference and on every
part it could not judge. No Django, no database, no network: synthetic rows only.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops/verification -p 'test_*.py' -v
"""
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_what_changed', HERE / 'what_changed.py')
wc = importlib.util.module_from_spec(_spec)
sys.modules.setdefault('cpt_what_changed', wc)
_spec.loader.exec_module(wc)

WORDS = wc.product_words()  # the current tree's answers.py
T0, T1, T2, T3 = '2026-11-12T09:00:00+00:00', '2026-11-12T10:00:00+00:00', '2026-11-12T11:00:00+00:00', '2026-11-12T12:00:00+00:00'


def fact(value, origin='document'):
    return {'value': value, 'origin': origin if value is not None or origin == 'conflict' else 'missing'}


class Rows:
    """A row set as the operator API serves what_changed_rows: by default a legacy E on context C1 (revision 1), and the
    update's final N, a v2 assessment on context C2 that records E as its earlier assessment."""

    def __init__(self, *, e_engine='cpt-studio-validation@10', n_engine='cpt-studio-events@2', n_revision='r1'):
        self.data = {'schema': wc.ROWS_SCHEMA, 'fresh': True, 'current_assessment': 'N', 'current_context': 'C2',
                     'assessments': {}, 'contexts': {}, 'revisions': {'r1': {'number': 1}, 'r2': {'number': 2},
                                                                       'r3': {'number': 3}},
                     'decisions': [], 'invalidations': [], 'member_answers': []}
        self.context('C1', 'r1', T0, version='gi-context@5', facts={'service_date': fact('2026-11-10')})
        self.context('C2', n_revision, T2, version='gemini-context@2', facts={'service_date': fact('2026-11-10')},
                     earlier='E')
        self.assessment('E', 'C1', T1, 'r1', e_engine)
        self.assessment('N', 'C2', T3, n_revision, n_engine)
        self.sequence = 0

    def context(self, pk, revision, created, *, version, facts, earlier=None):
        self.data['contexts'][pk] = {'created_at': created, 'revision': revision, 'version': version, 'facts': facts,
                                     'earlier_assessment': earlier}

    def assessment(self, pk, context, created, revision, engine):
        self.data['assessments'][pk] = {'created_at': created, 'revision': revision, 'context': context,
                                        'engine_version': engine, 'proposals': [], 'clarifications': []}

    def proposal(self, assessment, pk, code, *, bucket='selected', status='ready', units=1, position=0,
                 reinstatable=False, answered=(), family='gi.colonoscopy', other_reason=None):
        self.data['assessments'][assessment]['proposals'].append(
            {'id': pk, 'code': code, 'bucket': bucket, 'status': status, 'units': units, 'position': position,
             'reinstatable': reinstatable, 'answered_away': bool(answered), 'answers': list(answered),
             'family': family, 'other_reason': other_reason})

    def clarification(self, assessment, pk, fact_key, created, *, proposal=None, scope='proposal',
                      family='gi.colonoscopy', answer=None):
        self.data['assessments'][assessment]['clarifications'].append(
            {'id': pk, 'created_at': created, 'proposal': proposal, 'scope': scope, 'family': family,
             'fact': fact_key, 'answer': answer})

    def decision(self, pk, assessment, proposal, code, action='approve', carried_from=None):
        self.sequence += 1
        self.data['decisions'].append({'id': pk, 'assessment': assessment, 'proposal': proposal, 'code': code,
                                       'action': action, 'carried_from': carried_from, 'sequence': self.sequence})

    def invalidate(self, decision, *, by_context=None, by_revision=None):
        self.data['invalidations'].append({'decision': decision, 'by_context': by_context, 'by_revision': by_revision})

    def answer(self, pk, revision, answered_at, *, standing=True):
        self.data['member_answers'].append({'id': pk, 'revision': revision, 'answered_at': answered_at,
                                            'standing': standing})

    def result(self):
        assert wc.rows_problem(self.data) == '', wc.rows_problem(self.data)
        return wc.compute(copy.deepcopy(self.data), WORDS)

    def changed(self):
        found = self.result()
        self.unjudged = found['unjudged']
        return found['what_changed']


class WhenTests(unittest.TestCase):
    def test_null_unless_fresh_with_an_earlier_assessment_and_compared_with_e(self):
        rows = Rows()
        self.assertEqual(rows.changed()['compared_with'], {'made_at': T1, 'revision': 1})
        rows.data['fresh'] = False
        self.assertIsNone(rows.changed())
        rows = Rows()
        rows.data['contexts']['C2']['earlier_assessment'] = None
        self.assertIsNone(rows.changed())
        rows = Rows()
        rows.data['current_assessment'] = None
        self.assertIsNone(rows.changed())


class DetailsTests(unittest.TestCase):
    def test_each_field_in_the_members_words_and_the_documentation_and_reading_lines(self):
        rows = Rows()
        rows.data['contexts']['C1']['facts'] = {'service_date': fact('2026-11-10'), 'setting': fact('office', 'user'),
                                                'billing_context': fact(None), 'patient_status': fact('new', 'user')}
        rows.data['contexts']['C2']['facts'] = {'service_date': fact('2026-11-05', 'user'), 'setting': fact('asc', 'user'),
                                                'billing_context': fact('facility', 'user'),
                                                'patient_status': fact('new', 'user')}
        self.assertEqual(rows.changed()['details'], [
            'Date of service: 10 November 2026 → 5 November 2026',
            'Place of service: Office → Ambulatory surgery center',
            'Claim: not documented → Facility claim',
            'The document was read again with the current reading.'])  # a legacy E: the engine families differ
        self.assertEqual(rows.unjudged, [])

    def test_a_date_conflict_and_an_addendum(self):
        rows = Rows(e_engine='cpt-studio-events@2', n_revision='r2')
        rows.data['contexts']['C2']['facts'] = {'service_date': fact(None, 'conflict')}
        self.assertEqual(rows.changed()['details'], ['Date of service: 10 November 2026 → two dates to choose from',
                                                     'Documentation added (revision 2)'])

    def test_a_conflict_of_a_choice_has_no_words_in_6_2_and_is_not_judged(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.data['contexts']['C2']['facts'] = {'service_date': fact('2026-11-10'), 'setting': fact(None, 'conflict')}
        self.assertEqual(rows.changed()['details'], [])
        self.assertEqual(len(rows.unjudged), 1)
        self.assertIn('setting', rows.unjudged[0])


class CodesTests(unittest.TestCase):
    def test_added_removed_status_units_detail_and_unchanged_paired_by_code_and_position(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('E', 'e1', '45380', position=0)
        rows.proposal('E', 'e2', '45380', position=1)  # a second row of one code: paired by stored position
        rows.proposal('E', 'e3', '45385', status='needs_clarification', position=2)
        rows.proposal('E', 'e4', '45378', status='needs_clarification', position=3)
        rows.proposal('E', 'e5', '99213', position=4)
        rows.proposal('E', 'e6', '43239', units=1, position=5)
        rows.clarification('E', 'q1', 'extent', T1, proposal='e4')
        rows.proposal('N', 'n1', '45380', position=0)
        rows.proposal('N', 'n3', '45385', position=1)  # needs a detail -> ready: the outcome changed
        rows.proposal('N', 'n4', '45378', status='needs_clarification', position=2)
        rows.clarification('N', 'q2', 'completion', T3, proposal='n4')  # another fact: the item changed
        rows.proposal('N', 'n6', '43239', units=2, position=3)
        rows.proposal('N', 'n7', '43235', status='needs_clarification', position=4)  # new
        rows.proposal('N', 'n8', '99213', bucket='alternative', position=5)  # listed as an alternative only
        found = rows.changed()
        self.assertEqual(found['codes'], [
            {'code': '43235', 'change': 'added', 'text': '43235 is now suggested (Needs a detail)'},
            {'code': '43239', 'change': 'units', 'text': '43239: 1 → 2 units'},
            {'code': '45378', 'change': 'detail', 'text': '45378: the detail needed changed: '
                                                          '"How far was the instrument advanced?" → '
                                                          '"Was the examination completed as intended?"'},
            {'code': '45380', 'change': 'removed', 'text': '45380 is no longer suggested'},
            {'code': '45385', 'change': 'status', 'text': '45385: Needs a detail → Ready for review'},
            {'code': '99213', 'change': 'removed',
             'text': '99213 is no longer suggested. Listed as an alternative only; not suggested for approval.'},
        ])
        self.assertEqual(found['unchanged'], 1)  # 45380's first row
        self.assertEqual(rows.unjudged, [])

    def test_which_rows_are_listed_and_their_statuses(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('N', 'n1', '45385', bucket='excluded', status='excluded', reinstatable=True)
        rows.proposal('N', 'n2', '45384', bucket='excluded', status='excluded', answered=['a1'], position=1)
        rows.proposal('N', 'n3', '45390', bucket='excluded', status='excluded', position=2)  # nobody can decide it
        rows.proposal('N', 'n4', '45391', bucket='alternative', position=3)
        self.assertEqual([item['text'] for item in rows.changed()['codes']], [
            '45384 is now suggested (Excluded: a needed detail is not documented)',
            '45385 is now suggested (Excluded by a documentation check)'])

    def test_the_detail_falls_back_to_the_services_question_and_a_removed_codes_served_reason(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('E', 'e1', '45378', status='needs_clarification', family='gi.colonoscopy')
        rows.clarification('E', 'q0', 'units', T0, scope='service', family='gi.egd')  # another family's
        rows.clarification('E', 'q1', 'extent', T1, scope='service', family='gi.colonoscopy')
        rows.proposal('N', 'n1', '45378', status='needs_clarification', family='gi.colonoscopy')
        rows.clarification('N', 'q2', 'event_entry', T3, proposal='n1')  # design v2's new fact, worded by PROMPTS
        rows.proposal('E', 'e2', '45380', position=1)
        rows.proposal('N', 'n2', '45380', bucket='excluded', status='excluded', position=1,
                      other_reason='Not suggested: the documented act is a biopsy.')
        self.assertEqual([item['text'] for item in rows.changed()['codes']], [
            '45378: the detail needed changed: "How far was the instrument advanced?" → '
            '"In whose entry is this act documented?"',
            '45380 is no longer suggested. Not suggested: the documented act is a biopsy.'])

    def test_a_status_or_reason_6_2_does_not_word_is_not_judged(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('N', 'n1', '45385', status='informational')
        rows.proposal('E', 'e2', '45380', position=1)
        rows.proposal('N', 'n2', '45380', bucket='excluded', status='excluded', position=1)  # its reason not served
        found = rows.changed()
        self.assertEqual(found['codes'], [])
        self.assertEqual(len(rows.unjudged), 2)


    def test_a_pair_that_changed_in_two_ways_is_not_judged_until_6_2_says_how_it_is_listed(self):
        # refutation 6b-r1 P6: status and units both changed, and units and the detail both changed - 6.2 step 3 does
        # not say whether such a pair is listed once or once per change, so neither reading is passed or failed
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('E', 'p1', '43239', status='needs_clarification', units=1, position=0)
        rows.clarification('E', 'c1', 'extent', T1, proposal='p1')
        rows.proposal('N', 'q1', '43239', status='ready', units=2, position=0)
        rows.proposal('E', 'p2', '45380', status='needs_clarification', units=1, position=1)
        rows.clarification('E', 'c2', 'extent', T1, proposal='p2')
        rows.proposal('N', 'q2', '45380', status='needs_clarification', units=2, position=1)
        rows.clarification('N', 'c3', 'completion', T3, proposal='q2')
        rows.proposal('E', 'p3', '45385', status='needs_clarification', units=1, position=2)  # one change: judged
        rows.proposal('N', 'q3', '45385', status='ready', units=1, position=2)
        found = rows.changed()
        self.assertEqual(found['codes'], [{'code': '45385', 'change': 'status',
                                           'text': '45385: Needs a detail → Ready for review'}])
        self.assertEqual(rows.unjudged, [
            'codes: 43239 changed in more than one way (status, units): 6.2 step 3 does not say whether such a pair '
            'is listed once or once for each change',
            'codes: 45380 changed in more than one way (units, detail): 6.2 step 3 does not say whether such a pair '
            'is listed once or once for each change'])
        # and the check fails on a page that lists either reading
        mine = wc.compute(rows.data, WORDS)
        for page_codes in ([{'code': '43239', 'change': 'status', 'text': '43239: Needs a detail → Ready for review'}],
                           [{'code': '43239', 'change': 'status', 'text': '43239: Needs a detail → Ready for review'},
                            {'code': '43239', 'change': 'units', 'text': '43239: 1 → 2 units'}]):
            page = {**mine['what_changed'], 'codes': page_codes}
            self.assertTrue(any('not judged' in item for item in wc.compare(page, mine)))


class DecisionsTests(unittest.TestCase):
    def rows(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('E', 'e1', '45380')
        rows.proposal('E', 'e2', '45385', position=1)
        rows.proposal('N', 'n1', '45380')
        rows.proposal('N', 'n2', '45385', position=1)
        return rows

    def test_kept_and_cleared_with_5_4s_words_and_a_decision_revoked_before_the_change_not_listed(self):
        rows = self.rows()
        rows.proposal('E', 'e3', '43239', position=2)
        rows.decision('d1', 'E', 'e1', '45380')
        rows.decision('d2', 'N', 'n1', '45380', carried_from='d1')  # carried by the update's final
        rows.decision('d3', 'E', 'e2', '45385', action='reinstate')
        rows.invalidate('d3', by_context='C2')  # cleared when the details changed
        rows.decision('d4', 'E', 'e3', '43239')
        rows.decision('d5', 'E', 'e3', '43239', action='revoke')  # revoked before the change: nothing carried it
        self.assertEqual(rows.changed()['decisions'], [
            {'code': '45380', 'action': 'approve', 'outcome': 'kept', 'text': 'Approval of 45380 kept: the code is unchanged.'},
            {'code': '45385', 'action': 'reinstate', 'outcome': 'cleared',
             'text': 'Cleared when the details changed: the code it was made on changed.'}])

    def test_kept_then_cleared_by_a_same_details_final_and_kept_then_changed_by_a_reviewer(self):
        rows = self.rows()
        rows.assessment('N2', 'C2', '2026-11-12T13:00:00+00:00', 'r1', 'cpt-studio-events@2')  # an answer's recompute
        rows.proposal('N2', 'm1', '45380')
        rows.proposal('N2', 'm2', '45385', position=1)
        rows.data['current_assessment'] = 'N2'
        rows.decision('d1', 'E', 'e1', '45380')
        rows.decision('d2', 'N', 'n1', '45380', carried_from='d1')
        rows.invalidate('d2', by_context='C2')  # the recompute's final cleared it, with the same details
        rows.decision('d3', 'E', 'e2', '45385', action='confirm')
        rows.decision('d4', 'N', 'n2', '45385', action='confirm', carried_from='d3')
        rows.decision('d5', 'N2', 'm2', '45385', action='confirm', carried_from='d4')  # carried again onto N2
        rows.decision('d6', 'N2', 'm2', '45385', action='revoke')  # then the reviewer revoked it there
        self.assertEqual(rows.changed()['decisions'], [
            {'code': '45380', 'action': 'approve', 'outcome': 'kept_then_cleared',
             'text': 'Approval of 45380 was kept by the update, then cleared when the codes were checked again with '
                     'the same details.'},
            {'code': '45385', 'action': 'confirm', 'outcome': 'kept_then_changed',
             'text': 'Confirmed exclusion of 45385 was kept by the update, then changed by a reviewer.'}])
        rows.decision('d7', 'N2', 'm2', '45385', action='confirm')  # revoked and decided again: still changed
        self.assertEqual(rows.changed()['decisions'][1]['outcome'], 'kept_then_changed')

    def test_a_legacy_es_decisions_across_engines_and_the_two_addenda_of_case_c(self):
        rows = Rows()  # legacy E
        rows.proposal('E', 'e1', '45380')
        rows.decision('d1', 'E', 'e1', '45380', action='reject')
        rows.invalidate('d1', by_context='C2')
        self.assertEqual(rows.changed()['decisions'][0]['text'], wc.CLEARED_ACROSS_ENGINES)
        # R3T-3: two addenda before the update's final; the first cleared E's approval (revision 2), the second found none
        rows = Rows(e_engine='cpt-studio-events@2', n_revision='r3')
        rows.proposal('E', 'e1', '45380')
        rows.decision('d1', 'E', 'e1', '45380')
        rows.invalidate('d1', by_revision='r2')
        rows.decision('d0', 'E', 'e1', '45380', action='revoke')  # (never listed: not current, nothing acted on it)
        self.assertEqual(rows.changed()['decisions'], [
            {'code': '45380', 'action': 'approve', 'outcome': 'cleared',
             'text': 'Cleared when documentation was added (revision 2).'}])
        # within one revision a by_revision clearing is not this update's
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('E', 'e1', '45380')
        rows.decision('d1', 'E', 'e1', '45380')
        rows.invalidate('d1', by_revision='r2')
        self.assertEqual(rows.changed()['decisions'], [])

    def test_the_same_details_sentence_and_a_decision_made_after_ns_context_is_not_listed(self):
        rows = self.rows()
        rows.decision('d1', 'E', 'e1', '45380')
        rows.invalidate('d1', by_context='C1')  # cleared by a final made with E's own details
        rows.decision('d2', 'E', 'e2', '45385')
        rows.decision('d3', 'N', 'n2', '45385', carried_from='d2')
        self.assertEqual([entry['outcome'] for entry in rows.changed()['decisions']], ['kept'])  # d1: neither acted
        rows.data['invalidations'][0]['by_context'] = 'C2'
        rows.data['contexts']['C2']['created_at'] = T2
        found = wc._cleared(wc._Rows(rows.data), rows.data['decisions'][0], {'decision': 'd1', 'by_context': 'C1',
                                                                                'by_revision': None}, 'Approval')
        self.assertEqual(found['text'], wc.CLEARED_SAME_DETAILS)
        later = self.rows()
        later.decision('d9', 'N', 'n1', '45380')  # made on N, after its context: not the update's act
        self.assertEqual(later.changed()['decisions'], [])


class AnswersTests(unittest.TestCase):
    def test_an_earlier_answer_n_does_not_read_draws_the_line_and_nothing_else_does(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.answer('a1', 'r1', T1)
        self.assertEqual(rows.changed()['answers'], wc.ANSWERS_LINE)
        read = copy.deepcopy(rows)
        read.clarification('N', 'q1', 'extent', T3, answer='a1')
        self.assertIsNone(read.changed()['answers'])
        away = copy.deepcopy(rows)
        away.proposal('N', 'n1', '45385', bucket='excluded', status='excluded', answered=['a1'])
        self.assertIsNone(away.changed()['answers'])
        after = Rows(e_engine='cpt-studio-events@2')
        after.answer('a2', 'r1', T3)  # given after the update to a question N asks
        self.assertIsNone(after.changed()['answers'])
        withdrawn = Rows(e_engine='cpt-studio-events@2')
        withdrawn.answer('a3', 'r1', T1, standing=False)
        self.assertIsNone(withdrawn.changed()['answers'])
        addendum = Rows(e_engine='cpt-studio-events@2', n_revision='r2')
        addendum.answer('a4', 'r2', T1)
        self.assertIsNone(addendum.changed()['answers'])  # only while the revision is E's


class CompareTests(unittest.TestCase):
    def mine(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('N', 'n1', '45385', status='needs_clarification')
        rows.proposal('E', 'e1', '45380')
        rows.proposal('N', 'n2', '45380')
        rows.decision('d1', 'E', 'e1', '45380')
        rows.decision('d2', 'N', 'n2', '45380', carried_from='d1')
        rows.data['contexts']['C2']['facts'] = {'service_date': fact('2026-11-05', 'user')}
        return rows.result()

    def test_agreement_is_no_difference_whatever_the_instant_format_detail_order_or_action_form(self):
        mine = self.mine()
        page = copy.deepcopy(mine['what_changed'])
        self.assertEqual(wc.compare(page, mine), [])
        page['compared_with']['made_at'] = '2026-11-12T10:00:00Z'  # the same instant
        page['decisions'][0]['action'] = 'Approval'  # 6.2's noun for the same action
        self.assertEqual(wc.compare(page, mine), [])
        self.assertEqual(wc.compare(None, {'what_changed': None, 'unjudged': []}), [])

    def test_every_field_that_differs_is_named(self):
        mine = self.mine()
        cases = {
            'compared_with': lambda page: page['compared_with'].update(revision=2),
            'details': lambda page: page['details'].append('Patient: not documented → New patient'),
            'codes[0]': lambda page: page['codes'][0].update(text='45385 is now suggested (Ready for review)'),
            'codes[1]': lambda page: page['codes'].append({'code': '99999', 'change': 'added', 'text': 'x'}),
            'unchanged': lambda page: page.update(unchanged=0),
            'decisions[0]': lambda page: page['decisions'][0].update(outcome='cleared'),
            'answers': lambda page: page.update(answers=wc.ANSWERS_LINE),
            'keys 6.2 does not have': lambda page: page.update(changed_by='synthetic'),
        }
        for want, mutate in cases.items():
            with self.subTest(want=want):
                page = copy.deepcopy(mine['what_changed'])
                mutate(page)
                found = wc.compare(page, mine)
                self.assertTrue(found and any(want in item for item in found), found)
        self.assertEqual(wc.compare(None, mine), ['what_changed: the page serves none, the independent check one'])
        self.assertEqual(wc.compare(mine['what_changed'], {'what_changed': None, 'unjudged': []}),
                         ['what_changed: the page serves one, the independent check none'])

    def test_a_part_left_unjudged_fails_the_check(self):
        mine = self.mine()
        mine['unjudged'] = ['details: setting has no words in 6.2']
        self.assertEqual(wc.compare(copy.deepcopy(mine['what_changed']), mine),
                         ['not judged: details: setting has no words in 6.2'])


class InputTests(unittest.TestCase):
    def test_the_product_words_are_read_from_the_source_every_prompt_resolved(self):
        self.assertEqual(WORDS['unresolved'], [])
        # a key named by an imported constant (answers.COMPETING_FACT, from validation.engine) is resolved too
        self.assertTrue(WORDS['prompts']['competing_codes'].startswith('More than one code is proposed for the same '
                                                                      'documented act.'))
        self.assertEqual(WORDS['prompts']['event_entry'], 'In whose entry is this act documented?')
        self.assertEqual(WORDS['default_prompt'], 'CPT Studio could not confirm a detail this code depends on.')
        self.assertEqual(WORDS['choice_labels']['setting']['hospital_outpatient'], 'Hospital outpatient department')

    def test_the_rows_must_be_served_in_their_shape(self):
        with self.assertRaises(wc.Unusable) as missing:
            wc.rows_from_operator_view({'id': 'enc'})
        self.assertIn('requested of the integration owner', str(missing.exception))
        rows = Rows().data
        self.assertEqual(wc.rows_from_operator_view({'what_changed_rows': rows}), rows)
        for broken in ({**rows, 'schema': 'other@1'}, {**rows, 'fresh': 'yes'}, {**rows, 'decisions': [{'id': 'd'}]},
                       {**rows, 'member_answers': [{'id': 'a', 'revision': 'r1', 'answered_at': T0}]}):
            with self.subTest(broken=sorted(broken)), self.assertRaises(wc.Unusable):
                wc.rows_from_operator_view({'what_changed_rows': broken})

    def test_the_command_exits_0_when_they_agree_1_when_they_differ_and_2_when_unusable(self):
        rows = Rows(e_engine='cpt-studio-events@2')
        rows.proposal('N', 'n1', '45385')
        mine = rows.result()['what_changed']
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'op.json').write_text(json.dumps({'id': 'enc-1', 'what_changed_rows': rows.data}), encoding='utf-8')
            for page, code in ((mine, 0), ({**mine, 'unchanged': 9}, 1)):
                (folder / 'cust.json').write_text(json.dumps({'what_changed': page}), encoding='utf-8')
                out = io.StringIO()
                with redirect_stdout(out):
                    self.assertEqual(wc.main(['--operator', str(folder / 'op.json'), '--customer',
                                              str(folder / 'cust.json')]), code)
                self.assertEqual(json.loads(out.getvalue())['result'], 'pass' if code == 0 else 'fail')
            (folder / 'op.json').write_text(json.dumps({'id': 'enc-1'}), encoding='utf-8')
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(wc.main(['--operator', str(folder / 'op.json'), '--customer', str(folder / 'cust.json')]), 2)
            self.assertEqual(json.loads(out.getvalue())['result'], 'unusable')


if __name__ == '__main__':
    unittest.main()
