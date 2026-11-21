"""Line identity (FIX-SPEC section 1; findings INT-1, INT-2, INT-3, FG-B): every code row is its own line, every review
names the line it reviews, and decisions, the encounter state and the exports key by line - so two rows with one code
are decided apart, a review the code cannot place only ever sends lines to a human, and a decision is refused when the
page that sent it shows another round. Synthetic data only; nothing reaches the network."""
import json
import re

from django.test import SimpleTestCase, TestCase

from studio import decisions, models, state
from studio.fable import result
from tests.support import coding as f
from tests.support import rounds as r

Decision = models.CodeDecision
CHANGED = 'This coding review has changed. Reload to see the latest.'  # FIX-SPEC 1, the 409 a stale page reads
# Each line a PDF report lists, as report_text reads its codes table: (its line, the first word of its modifiers)
LISTED = re.compile(r'Line (\w+) · Modifiers: (\S+)')


def code_row(text, index, code):
    """Row ``index`` (01, 02 ...) of a PDF report's codes table, which must be ``code``'s: its text as report_text reads
    it, from the row's number and code up to its evidence reference - so a check on it is scoped to that one line (every
    row these tests make has quotes; a row without fails here, never reads another row)."""
    start = text.find(f'{index:02d} {code} ')
    end = text.find(f'Evidence {index:02d}', start) if start != -1 else -1
    if end == -1:
        raise AssertionError(f'the report has no code row {index:02d} {code}: {text}')
    return text[start:end]


def bilateral(status_lt='ready', question=None):
    return [f.code('20610', 'ready', modifiers=['RT'], reason='Right knee injection documented.'),
            f.code('20610', status_lt, modifiers=['LT'], question=question,
                   reason='Left knee injection is planned, not performed.')]


class CombineByLineTests(SimpleTestCase):
    """INT-2: a review belongs to the line it names (and that line's code), never to every row with its code."""

    def combine(self, codes, reviews, missed=()):
        return result.combine(f.reader_result(codes), f.checker_result(reviews, missed=missed))['codes']

    def test_two_lines_with_one_code_each_keep_their_own_review(self):
        rows = self.combine(
            [f.code('64483', modifiers=['RT']), f.code('64483', modifiers=['LT'])],
            [r.review('L1', '64483', 'agree', reason='The right-sided injection is documented.'),
             r.review('L2', '64483', 'disagree', reason='No left-sided injection documented.')])
        self.assertEqual([(row.get('line'), row['status'], row['second_check']['agrees'], row['second_check']['reason'])
                          for row in rows],
                         [('L1', 'ready', True, 'The right-sided injection is documented.'),
                          ('L2', 'needs_review', False, 'No left-sided injection documented.')])

    def test_a_review_the_code_cannot_place_sends_every_line_of_its_code_to_a_human(self):
        rows = self.combine(
            [f.code('64483', modifiers=['RT']), f.code('64483', modifiers=['LT'])],
            [f.review('64483', 'agree'),
             f.review('64483-LT', 'disagree', reason='No left-sided injection documented.')])
        self.assertEqual([(row.get('line'), row['status']) for row in rows],
                         [('L1', 'needs_review'), ('L2', 'needs_review')])

    def test_one_agreement_never_reaches_two_lines(self):
        rows = self.combine([f.code('64483', modifiers=['RT']), f.code('64483', modifiers=['LT'])],
                            [r.review('L1', '64483', 'agree')])
        self.assertEqual([(row['status'], row['second_check']['agrees']) for row in rows],
                         [('ready', True), ('needs_review', None)])

    def test_a_review_naming_a_line_with_another_code_belongs_to_no_line(self):
        rows = self.combine([f.code('45385'), f.code('45380')],
                            [r.review('L1', '45380', 'agree'), r.review('L2', '45380', 'agree')])
        # L1 is named by a review of 45380: it cannot be told whether it reviewed L1, so L1 and the 45380 line wait
        self.assertEqual([(row.get('line'), row['status']) for row in rows],
                         [('L1', 'needs_review'), ('L2', 'needs_review')])

    def test_lines_are_labelled_in_order_and_missed_codes_are_m_lines(self):
        rows = self.combine([f.code('45385'), f.code('45380')], [r.review('L1', '45385'), r.review('L2', '45380')],
                            missed=[r.missed('45378'), r.missed('45385', modifiers=['XS'])])
        self.assertEqual([(row.get('line'), row['code'], row['status'], row['listed_by']) for row in rows],
                         [('L1', '45385', 'ready', 'reader'), ('L2', '45380', 'ready', 'reader'),
                          ('M1', '45378', 'needs_review', 'checker'), ('M2', '45385', 'needs_review', 'checker')])

    def test_the_checker_is_given_each_line_with_its_label(self):
        listed = result.listing(f.reader_result([f.code('20610', modifiers=['RT']), f.code('20610', 'needs_answer',
                                                                                         question='Which knee?')]))
        # each line with the ids of the questions it names (D370) and, in today's shape, the question it wrote
        self.assertEqual(listed, {'lines': [
            {'line': 'L1', 'code': '20610', 'units': 1, 'modifiers': ['RT'], 'status': 'ready', 'question_ids': []},
            {'line': 'L2', 'code': '20610', 'units': 1, 'modifiers': [], 'status': 'needs_answer', 'question_ids': [],
             'question': 'Which knee?'}], 'questions': []})


class LineCase(r.CustomerCase, TestCase):
    def payload(self, enc, user=None):
        return self.client_for(user or self.reviewer).get(f'/api/encounters/{enc.pk}').json()

    def rows(self, enc):
        return [(code.get('line'), code['code'], code['modifiers'], code['status'],
                 (code['decision'] or {}).get('action'), code['allowed_actions'])
                for code in self.payload(enc)['codes']]


class DecisionByLineTests(LineCase):
    """INT-1 and FG-B: one decision is one line's."""

    def test_a_checker_added_line_with_a_listed_code_is_decided_apart(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('20610', modifiers=['RT'])]),
                        checker=f.checker_result([r.review('L1', '20610')], missed=[
                            r.missed('20610', modifiers=['LT'], reason='The left knee was also injected.')]))
        self.assertEqual(self.decide(enc, 'L1', '20610', 'approve').status_code, 201)
        self.assertEqual(self.rows(enc), [('L1', '20610', ['RT'], 'ready', 'approve', ['revoke']),
                                          ('M1', '20610', ['LT'], 'needs_review', None, ['approve', 'reject'])])
        self.assertEqual(self.payload(enc)['state'], 'needs_review')
        text = self.report_text(enc, 'approved')
        self.assertEqual(LISTED.findall(text), [('L1', 'RT')])  # the one line listed
        self.assertIn('Line L1 · Modifiers: RT UNITS 1', code_row(text, 1, '20610'))
        self.assertNotRegex(text, r'\bLT\b')  # the M1 line's modifier (the identity strip's SPECIALTY is no LT)
        self.assertEqual(self.decide(enc, 'M1', '20610', 'reject').status_code, 201)
        self.assertEqual(self.payload(enc)['state'], 'reviewed')
        self.assertEqual(list(Decision.objects.order_by('sequence').values_list('line', 'code', 'action')),
                         [('L1', '20610', 'approve'), ('M1', '20610', 'reject')])

    def test_a_needs_answer_twin_is_never_approved_by_its_ready_twins_approval(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result(bilateral('needs_answer', 'Was the left knee injected too?')),
                        checker=f.checker_result([r.review('L1', '20610'), r.review('L2', '20610')]))
        self.assertEqual(self.decide(enc, 'L1', '20610', 'approve').status_code, 201)
        self.assertEqual(self.rows(enc), [('L1', '20610', ['RT'], 'ready', 'approve', ['revoke']),
                                          ('L2', '20610', ['LT'], 'needs_answer', None, [])])
        # the approved report lists the ready twin alone (it prints no coding status: the page above says L1 is ready)
        text = self.report_text(enc, 'approved')
        self.assertEqual(LISTED.findall(text), [('L1', 'RT')])
        self.assertIn('Line L1 · Modifiers: RT', code_row(text, 1, '20610'))
        self.assertNotRegex(text, r'\bLT\b')

    def test_the_ready_twin_listed_second_can_be_approved(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result(list(reversed(bilateral('needs_answer', 'Which knee?')))),
                        checker=f.checker_result([r.review('L1', '20610'), r.review('L2', '20610')]))
        response = self.decide(enc, 'L2', '20610', 'approve')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['line'], 'L2')

    def test_a_not_supported_line_is_never_exported_as_approved(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45385'), f.code('45380', 'not_supported',
                                                                              reason='No biopsy is documented.')]),
                        checker=f.checker_result([r.review('L1', '45385'), r.review('L2', '45380', 'disagree')],
                                                 missed=[r.missed('45380', modifiers=['XS'])]))
        self.assertEqual(self.decide(enc, 'M1', '45380', 'approve').status_code, 201)
        self.assertEqual(self.rows(enc), [('L1', '45385', [], 'ready', None, ['approve', 'reject']),
                                          ('L2', '45380', [], 'needs_review', None, ['approve', 'reject']),
                                          ('M1', '45380', ['XS'], 'needs_review', 'approve', ['revoke'])])
        text = self.report_text(enc, 'approved')
        self.assertEqual(LISTED.findall(text), [('M1', 'XS')])  # the one line listed
        self.assertIn('Line M1 · Modifiers: XS UNITS 1', code_row(text, 1, '45380'))
        self.assertNotIn('No biopsy is documented.', text)

    def test_an_approved_export_lists_only_approved_lines_that_are_ready_or_need_review(self):
        enc = self.encounter()
        round_ = r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'needs_answer', question='Q?'),
                                           r.row('43251', 'not_supported')])
        fields = {field.name for field in Decision._meta.get_fields()}
        for line, code in (('L1', '45385'), ('L2', '45380'), ('L3', '43251')):  # rows a page could never have made
            Decision.objects.create(encounter=enc, round=round_, code=code, action=Decision.APPROVE,
                                    reviewer=self.reviewer, reviewer_kind='human', acknowledgement='x',
                                    **({'line': line} if 'line' in fields else {}))
        text = self.report_text(enc, 'approved')
        self.assertEqual(LISTED.findall(text), [('L1', 'none')])
        self.assertIn('Line L1', code_row(text, 1, '45385'))  # row 01 is 45385, its own line L1
        self.assertNotIn('45380', text)
        self.assertNotIn('43251', text)


class StaleRoundTests(LineCase):
    """INT-3: a decision names the round the page showed; another round, or a line of another code, is refused."""

    def test_a_page_left_on_round_one_cannot_approve_round_twos_line(self):
        enc = self.started()
        reader1 = f.reader_result([f.code('99214'), f.code('20610', 'needs_answer', question='Which knee?')],
                                  questions=[{'question': 'Which knee?', 'affects': ['20610']}])
        self.code_round(enc, reader=reader1, checker=f.checker_result([r.review('L1', '99214'),
                                                                       r.review('L2', '20610')]))
        member_b = r.f.member(self.ws)
        page_a = self.payload(enc)
        question = self.payload(enc, member_b)['questions'][0]['id']
        answered = self.client_for(member_b).post(f'/api/encounters/{enc.pk}/answers', data=json.dumps(
            {'answers': [{'question_id': question, 'text': 'The right knee.'}]}), content_type='application/json')
        self.assertEqual(answered.status_code, 201, answered.content)
        reader2 = f.reader_result([f.code('99214', modifiers=['25']), f.code('20610', modifiers=['RT'])])
        self.code_round(enc, reader=reader2, checker=f.checker_result([r.review('L1', '99214'),
                                                                       r.review('L2', '20610')]))
        response = self.decide(enc, 'L1', '99214', 'approve', round_number=page_a['round']['number'])
        self.assertEqual((response.status_code, response.json().get('error')), (409, CHANGED))
        self.assertEqual(Decision.objects.count(), 0)
        self.assertEqual(decisions.ROUND_CHANGED, CHANGED)
        self.assertEqual(self.decide(enc, 'L1', '99214', 'approve').status_code, 201)  # the page shows round 2 now
        self.assertEqual(Decision.objects.get().round.number, 2)

    def test_a_line_whose_code_differs_from_the_code_sent_is_refused(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready'), r.row('45380', 'ready')])
        for line, code in (('L2', '45385'), ('L3', '45385'), ('M1', '45385')):
            with self.subTest(line=line):
                response = self.decide(enc, line, code, 'approve')
                self.assertEqual((response.status_code, response.json().get('error')),
                                 (409, 'That code is not part of this coding review. Reload to see the latest.'))
        self.assertEqual(Decision.objects.count(), 0)

    def test_a_decision_while_the_next_round_runs_is_refused_as_changed(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        r.write_round(enc, state_=models.CodingRound.RUNNING)
        for number in (1, 2):
            with self.subTest(round=number):
                response = self.decide(enc, 'L1', '45385', 'approve', round_number=number)
                self.assertEqual((response.status_code, response.json().get('error')), (409, CHANGED))

    def test_the_round_and_the_line_must_be_named(self):
        enc = self.encounter()
        r.write_round(enc, codes=[r.row('45385', 'ready')])
        client = self.client_for(self.reviewer)
        for body, message in (({'line': 'L1'}, decisions.ROUND_REQUIRED), ({'round': True, 'line': 'L1'},
                                                                             decisions.ROUND_REQUIRED),
                              ({'round': 1}, decisions.LINE_REQUIRED), ({'round': 1, 'line': 3},
                                                                       decisions.LINE_REQUIRED)):
            with self.subTest(body=body):
                response = client.post(f'/api/encounters/{enc.pk}/decisions', data=json.dumps(
                    {'code': '45385', 'action': 'reject', **body}), content_type='application/json')
                self.assertEqual((response.status_code, response.json()['error']), (400, message))
        self.assertEqual(state.latest_round(enc).decisions.count(), 0)
