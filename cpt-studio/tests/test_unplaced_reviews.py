"""Reviews the code cannot place (FIX-SPEC-2 section 3; findings LINES-1, LINES-2, LINES-4, LINES-7, LINES-8 and the
INT-2 residue). A checker review that names no line, or a line that does not exist, sends the lines holding its code to
a human; when no line holds its code, EVERY line of the round goes to a human, because the code cannot tell which line it
is about - and in both cases the customer reads the review's reason as a note on the encounter. A review naming a line
but carrying another code holds that line even beside the line's own agreement. A verdict that is neither exactly
"agree" nor exactly "disagree" reads as no clear verdict, never as a disagreement. A checker-added line says the status
the checker gave it, and the operator console lists every review that belongs to no line in full. Synthetic answers
only; nothing reaches the network."""
from django.test import SimpleTestCase, TestCase

from studio import customer, physician_report
from studio.fable import result
from tests.support import coding as f
from tests.support import operator as ops
from tests.support import rounds as r

NOTE = 'The second check made a comment that could not be tied to one line'
UNCLEAR = 'The second check did not give a clear verdict.'
# LINES-1's input: the third review names line "2" (no such line) and a code no line holds
UNPLACED_REASON = 'The biopsy was of the polyp that was then snared; 45380 is not separately reported.'


def unplaced_review(line='2', code='45380-59', verdict='disagree', reason=UNPLACED_REASON):
    review = {**f.review(code, verdict, reason=reason), 'correct_status': 'not_supported'}
    return review if line is None else {**review, 'line': line}


def rows_of(codes, reviews, missed=()):
    return result.combine(f.reader_result(codes), f.checker_result(reviews, missed=missed))['codes']


def statuses(rows):
    return [(row['line'], row['status']) for row in rows]


class PlacementTests(SimpleTestCase):
    def test_a_review_whose_code_no_line_holds_sends_every_line_to_a_human(self):
        # LINES-1: the review counted only as "unplaced" and both lines stayed ready, the second check "agreeing"
        for line in ('2', 'L7', None, '', 2, 'Line 2', 'M3'):
            with self.subTest(line=line):
                rows = rows_of([f.code('45385'), f.code('45380')],
                               [r.review('L1', '45385'), r.review('L2', '45380'), unplaced_review(line)])
                self.assertEqual(statuses(rows), [('L1', 'needs_review'), ('L2', 'needs_review')])
                self.assertEqual([(row['second_check']['agrees'], row['second_check']['unplaced']) for row in rows],
                                 [(True, 1), (True, 1)])

    def test_an_agreeing_review_placed_nowhere_also_sends_every_line_to_a_human(self):
        rows = rows_of([f.code('45385'), f.code('45380')],
                       [r.review('L1', '45385'), r.review('L2', '45380'), r.review('L9', '99999', 'agree')])
        self.assertEqual(statuses(rows), [('L1', 'needs_review'), ('L2', 'needs_review')])

    def test_a_review_whose_code_a_line_holds_sends_only_those_lines_to_a_human(self):
        rows = rows_of([f.code('45385'), f.code('45380'), f.code('43239')],
                       [r.review('L1', '45385'), r.review('L2', '45380'), r.review('L3', '43239'),
                        unplaced_review('L7', '45380')])
        self.assertEqual(statuses(rows), [('L1', 'ready'), ('L2', 'needs_review'), ('L3', 'ready')])
        self.assertEqual([row['second_check']['unplaced'] for row in rows], [0, 0, 0])

    def test_a_review_naming_a_line_with_another_code_holds_that_line_beside_its_own_agreement(self):
        # LINES-2: the one case where the named-line guard decides the outcome - the line has its own agreeing review
        rows = rows_of([f.code('45385'), f.code('45380')],
                       [r.review('L1', '45385'), r.review('L2', '45380'),
                        r.review('L2', '45378', 'disagree', reason='No separate biopsy; the biopsied polyp was snared.')])
        self.assertEqual(statuses(rows), [('L1', 'ready'), ('L2', 'needs_review')])
        self.assertEqual([(row['second_check']['agrees'], row['second_check']['unmatched'],
                           row['second_check']['unplaced']) for row in rows], [(True, 0, 0), (True, 1, 0)])

    def test_the_lt_review_labelled_l1_by_mistake_holds_both_lines(self):
        # the INT-2 residue's R7: the left-knee disagreement was written as line L1 with the code "64483-LT"
        rows = rows_of([f.code('64483', modifiers=['RT']), f.code('64483', modifiers=['LT'])],
                       [r.review('L1', '64483', 'agree', reason='The right-sided injection is documented.'),
                        r.review('L1', '64483-LT', 'disagree', reason='No left-sided injection documented.')])
        self.assertEqual(statuses(rows), [('L1', 'needs_review'), ('L2', 'needs_review')])
        self.assertEqual(rows[0]['second_check']['unmatched'], 1)

    def test_a_disagreement_placed_nowhere_beside_two_named_agreements_holds_both_lines(self):
        # the INT-2 residue's P8: each line agreed by name, and the disagreement named no line and no line's code
        rows = rows_of([f.code('64483', modifiers=['RT']), f.code('64483', modifiers=['LT'])],
                       [r.review('L1', '64483', 'agree'), r.review('L2', '64483', 'agree'),
                        f.review('64483-LT', 'disagree', reason='No left-sided injection documented.')])
        self.assertEqual(statuses(rows), [('L1', 'needs_review'), ('L2', 'needs_review')])

    def test_the_unmatched_reviews_of_a_round_are_read_from_its_stored_rows_in_full(self):
        reader = f.reader_result([f.code('45385'), f.code('45380')])
        checker = f.checker_result([r.review('L2', '45380'), unplaced_review('2'),
                                    r.review('L7', '45385', 'disagree', reason='Same polyp.')])
        codes = result.combine(reader, checker)['codes']
        found = result.unmatched_reviews(codes, checker)
        self.assertEqual([(item['number'], item['reaches'], item['reason']) for item in found],
                         [(2, [], UNPLACED_REASON), (3, ['L1'], 'Same polyp.')])
        self.assertEqual(found[0]['review'], checker['reviews'][1])  # the review exactly as the checker wrote it
        self.assertEqual(result.unmatched_reviews(codes, None), [])


class VerdictWordsTests(SimpleTestCase):
    def check(self, verdict, reason='Supported as listed.'):
        item = {**r.review('L1', '45385'), 'verdict': verdict, 'reason': reason}
        (row,) = rows_of([f.code('45385')], [item])
        return row, customer.check_json(row)

    def test_a_verdict_neither_agree_nor_disagree_reads_as_no_clear_verdict(self):
        # LINES-4: the customer was told "disagrees" although the checker wrote "Agree" (or no verdict)
        for verdict in ('Agree', 'agrees', 'AGREE', 'agree ', None, True, 1):
            with self.subTest(verdict=verdict):
                row, check = self.check(verdict)
                self.assertEqual(row['status'], 'needs_review')
                self.assertEqual(check, {'agrees': None, 'reason': f'{UNCLEAR} Supported as listed.'})
                # the report's words for the line's second check (a line with no reason and no question of its own)
                self.assertEqual(physician_report._note({'reason': None, 'second_check': check, 'question': None},
                                                        physician_report.DRAFT),
                                 f'Second check: no verdict. {UNCLEAR} Supported as listed.')
        self.assertEqual(self.check(None, None)[1], {'agrees': None, 'reason': UNCLEAR})

    def test_an_exact_disagreement_still_reads_as_one_and_is_shown_before_an_unclear_verdict(self):
        self.assertEqual(self.check('disagree')[1], {'agrees': False, 'reason': 'Supported as listed.'})
        self.assertEqual(self.check('agree')[1], {'agrees': True, 'reason': 'Supported as listed.'})
        both = [{**r.review('L1', '45385'), 'verdict': 'Agree', 'reason': 'Looks fine.'},
                {**r.review('L1', '45385'), 'verdict': 'disagree', 'reason': 'No snare is documented.'}]
        (row,) = rows_of([f.code('45385')], both)
        self.assertEqual(customer.check_json(row), {'agrees': False, 'reason': 'No snare is documented.'})


class CustomerWordsTests(SimpleTestCase):
    def test_a_line_reached_by_a_review_placed_nowhere_says_so_never_that_a_review_names_it(self):
        rows = rows_of([f.code('45385'), f.code('45380')], [r.review('L1', '45385'), unplaced_review(None)])
        self.assertEqual(customer.check_json(rows[0]),
                         {'agrees': True, 'reason': 'Supported as listed. Another review by the second check names '
                                                    'none of these lines, so this code needs your review.'})
        self.assertEqual(customer.check_json(rows[1]), {'agrees': None, 'reason': customer.UNPLACED_CHECK})

    def test_a_checker_added_line_says_the_status_the_checker_gave_it(self):
        # LINES-7: every added line read "found this code", whatever the checker said of it
        rows = rows_of([f.code('45385')], [r.review('L1', '45385')],
                       missed=[r.missed('45380', 'needs_answer', question='Was a biopsy taken from a separate site?'),
                               r.missed('45378', 'ready')])
        self.assertEqual([customer.check_json(row) for row in rows[1:]], [
            {'agrees': None, 'reason': 'The second check found this code and listed it as needing an answer; it needs '
                                       'your review.'},
            {'agrees': None, 'reason': 'The second check found this code and listed it as ready for approval; it '
                                       'needs your review.'}])


class UnplacedPipelineTests(r.CustomerCase, TestCase):
    def payload(self, enc):
        return self.client_for(self.reviewer).get(f'/api/encounters/{enc.pk}').json()

    def test_a_review_the_code_cannot_place_holds_every_line_and_the_customer_reads_its_reason(self):
        # LINES-1 through the stage, the API, the draft report and an approval
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45385'), f.code('45380')]),
                        checker=f.checker_result([r.review('L1', '45385'), r.review('L2', '45380'), unplaced_review()]))
        payload = self.payload(enc)
        self.assertEqual((payload['state'], payload['state_label']), ('needs_review', 'Needs your review'))
        self.assertEqual([(code['line'], code['status']) for code in payload['codes']],
                         [('L1', 'needs_review'), ('L2', 'needs_review')])
        for code in payload['codes']:
            self.assertIn('names none of these lines', code['second_check']['reason'])
        self.assertEqual(payload['notes'], [f'{NOTE}: {UNPLACED_REASON}'])
        draft = self.report_text(enc, 'draft')
        self.assertIn(f'– {NOTE}: {UNPLACED_REASON}', draft.partition('DOCUMENTATION NOTES')[2])  # a listed note
        self.assertEqual(self.decide(enc, 'L2', '45380', 'approve').status_code, 201)  # a human decides it

    def test_every_unmatched_review_is_a_note_with_its_reason_or_without_one(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45385'), f.code('45380')], problems=['No signature.']),
                        checker=f.checker_result([
                            r.review('L1', '45385'), r.review('L2', '45380'),
                            r.review('L2', '45378', 'disagree', reason='No separate biopsy.'),
                            {**unplaced_review(None), 'reason': None}]))
        self.assertEqual(self.payload(enc)['notes'], ['No signature.', f'{NOTE}: No separate biopsy.', f'{NOTE}.'])

    def test_an_unclear_verdict_is_never_shown_or_exported_as_a_disagreement(self):
        # LINES-4 through the stage, the API and the draft report
        enc = self.started()
        item = {**r.review('L1', '45385'), 'verdict': 'Agree', 'reason': 'Supported as listed.'}
        self.code_round(enc, reader=f.reader_result([f.code('45385')]), checker=f.checker_result([item]))
        (code,) = self.payload(enc)['codes']
        self.assertEqual((code['status'], code['second_check']),
                         ('needs_review', {'agrees': None, 'reason': f'{UNCLEAR} Supported as listed.'}))
        draft = self.report_text(enc, 'draft')
        self.assertIn(f'Second check: no verdict. {UNCLEAR} Supported as listed.', draft.partition('01 45385 / ')[2])
        self.assertNotIn('disagrees', draft)

    def test_a_checker_added_line_shows_its_status_on_the_page_and_in_the_draft(self):
        # LINES-7 through the stage
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45385')]), checker=f.checker_result(
            [r.review('L1', '45385')],
            missed=[r.missed('45380', 'needs_answer', question='Was a biopsy taken from a separate site?')]))
        added = self.payload(enc)['codes'][1]
        self.assertEqual((added['line'], added['status'], added['second_check']['reason']),
                         ('M1', 'needs_review', 'The second check found this code and listed it as needing an '
                                                'answer; it needs your review.'))
        draft = self.report_text(enc, 'draft')
        self.assertIn('listed it as needing an answer', draft.partition('02 45380 / ')[2])  # the M1 line's reasons


class OperatorListTests(r.CustomerCase, TestCase):
    """LINES-8: the operator console listed no unmatched review and called a line one reached "not reviewed"."""

    def setUp(self):
        super().setUp()
        self.ops = ops.admin_client(r.f.user('platform-operator'))  # release 1, B3: the admin host, 2FA

    def test_the_console_lists_every_review_that_belongs_to_no_line_in_full(self):
        enc = self.started()
        self.code_round(enc, reader=f.reader_result([f.code('45385'), f.code('45380')]),
                        checker=f.checker_result([r.review('L2', '45380'),
                                                  unplaced_review('2', '45380-59', reason='Separately reported?'),
                                                  r.review('L7', '45385', 'disagree', reason='Same polyp.')]))
        self.ops.post(f'/ops/encounters/{enc.pk}/content', {'reason': 'support_request', 'reference': 'SR-1'})  # release 1, C2
        page = self.ops.get(f'/ops/encounters/{enc.pk}').content.decode('utf-8')
        start = page.index('Reviews that belong to no line')
        listed = page[start:page.index('Citations by line', start)]
        for fragment in ('Review 2', 'Review 3', '45380-59', 'Separately reported?', '&quot;L7&quot;', 'Same polyp.',
                         'reaches L1', 'every line'):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, listed)
        table = page[page.index('<h3>Final codes</h3>'):start]
        self.assertNotIn('not reviewed', table)
        self.assertIn('1 review(s) name this line or its code but not both', table)
        self.assertIn('tied to no line', table)
