"""Refutation round 3 of the core repair (2026-11-04): the acceptance tools - the walk (ops/verify_browser.cjs) and the
download check (ops/verify_downloads.py), the install's acceptance evidence - pass a genuine consistent site and fail a
misstatement (B-02, B-03, B-04).

- B-04: a quotation's continued lines are read in the grammar studio/reports.py writes. reports._join prints a part of
  a value that already starts seven spaces deep as it is and continues any other part seven spaces deep, so a printed
  line seven to thirteen spaces deep reads two ways, and stripping a fixed seven spaces read a passage line the document
  indents eight spaces back with one: a genuine draft failed items.evidence.support and a genuine approved export
  items.evidence.exact. The check now prints the passage as the writer prints it and compares the two (txt_printed),
  so the genuine export passes at every indent and the same file re-indented by one space fails.
- B-02 and B-03: the walk and the download check re-derived the overlay's status and actions and disagreed with the
  server for reinstated codes: a reinstated 45378 whose needed detail a member answered "Not documented" (the server:
  Excluded, revoke only) failed the genuine page and drafts as "expected ready", while a page and drafts forged to say
  "Ready for review" and to offer Approve (which the server refuses with 409) passed; a reinstated 45378 still waiting
  on that detail (needs a detail; the server accepts reject and revoke) failed the genuine page as "the server accepts
  revoke". The operator view now carries what the server decides for each code on the customer page
  (serializers.customer_codes: customer_api.code_rows over the review overlay - number, status, its label and sub
  label, and the actions a member who may review is allowed - and the overlay's own reason), and both tools judge
  against it; where the view carries none they cannot verify, and never pass.

DB-backed (CPT_STUDIO_TEST_DB_SUFFIX) except WrittenGrammarTests; synthetic data only; nothing is sent. The walk tests
need node (as the CI job has).
"""
import copy
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio import reports, review
from studio.gi import context as gi_context
from studio.types import to_jsonable
from tests.support import pipeline_factories as pf
from tests.test_cux_r2_reports import ExportCase, changed, post, signed_in, vd, walk_judged
from tests.test_cux_review import BIOPSY, HEAD, SNARE, assess, retrieval_for

SAMPLES = Path(reports.__file__).resolve().parents[1] / 'ops' / 'verification' / 'samples'
B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
VISIT = 'Established patient seen in the office today for follow-up of reflux.'
NO_COLONOSCOPY = 'A colonoscopy was not performed today.'
OFFICE_DENIED = (B + 'Office visit note (fictional)\nDate of service: 2026-11-03\nPlace of service: Office\n'
                 f'{VISIT}\n{NO_COLONOSCOPY}\n')
OFFICE_READY_DENIED = (B + 'Office visit note (fictional)\nDate of service: 2026-11-03\nPlace of service: Office\n'
                       f'{VISIT}\nTotal time spent on the date of the encounter was 25 minutes.\nMedical decision '
                       f'making: low complexity.\n{NO_COLONOSCOPY}\n')
OFFICE_CODES = [('99213', VISIT), ('45378', NO_COLONOSCOPY)]
UNAVAILABLE = 'A needed detail is not documented'
REINSTATED = 'Reinstated in review'


def persist_text(text, codes):
    """tests.test_cux_review.persist with the text and the Corti answer given (the same calls in the same order): an
    encounter whose current, final assessment is the engine's own result for them."""
    s = pf.scenario(text=text)
    facts = {name: to_jsonable(fact) for name, fact in gi_context.extract_context(text).items()}
    ctx = pf.context(s.encounter, s.revision, fact_values=facts)
    result = assess(text, codes)
    s.assessment = review.persist_assessment(
        encounter=s.encounter, revision=s.revision, context=ctx, routing_run=pf.routing(s.revision),
        provider_run=pf.provider_run(s.encounter, s.revision), result=result,
        retrieval=retrieval_for(result, [c for c, _ in codes]))
    s.encounter.refresh_from_db()
    return s


def indented(indent):
    """The finding's document: two findings lines the document indents ``indent`` spaces, and a Corti answer citing the
    biopsy line for 45380 and both lines together - the biopsy line, its line break and the indented snare line - for
    45385, an exact slice the support reading takes as supporting."""
    pad = ' ' * indent
    text = HEAD + 'Findings:\n' + pad + BIOPSY + '\n' + pad + SNARE + '\n'
    two = BIOPSY + '\n' + pad + SNARE
    assert text.count(two) == 1 and text.count(BIOPSY) == 1 and text.count(SNARE) == 1
    return text, [('45380', BIOPSY), ('45385', two)], two


def stripped_of_statements(view):
    """The operator view as served before it carried the server's statement of the customer page (serializers
    customer_codes): no 'customer' on any proposal."""
    view = copy.deepcopy(view)
    for proposal in view['assessment']['proposals']:
        proposal.pop('customer', None)
    return view


class WrittenGrammarTests(SimpleTestCase):
    """B-04, DB-free: the download check prints a passage as reports._join prints it inside a quotation, and reads a
    rendered quotation back exactly as printed."""

    # every way a passage can continue: no break; a part at each depth around the writer's seven (0, 1, 6, 7, 8, 13, 14,
    # 20); a blank part; a break first or last; trailing spaces; every break str.splitlines splits on (\r\n one
    # break); controls (escaped) at the start of a part and inside it; a tab before the indent
    PASSAGES = (['one line', 'a\nb', 'a\n\nb', 'a\n', '\na', 'a   \nb', 'a\r\nb', 'a\rb', 'a\n\rb', 'a\x0bb', 'a\x0cb',
                 'a\x1cb', 'a\x1db', 'a\x1eb', 'a\x85b', 'a\u2028b', 'a\u2029b', 'a\x01b', 'a\n\x01      b',
                 'a\n\t       b', 'a\n' + ' ' * 7 + '\n' + ' ' * 8, 'a\n' + ' ' * 7, 'a\x7fb\n        c\x9f']
                + [f'a\n{" " * n}b' for n in (1, 6, 7, 8, 13, 14, 20)]
                + [f'{BIOPSY}\n{" " * n}{SNARE}' for n in (0, 6, 7, 8, 13, 14)])

    def test_the_checker_prints_a_passage_as_the_writer_prints_it_in_a_quotation(self):
        for passage in self.PASSAGES:
            with self.subTest(passage=passage):
                printed = reports._join([f'   Quote: "{passage}" (page 1)'])
                self.assertTrue(printed.startswith('   Quote: "') and printed.endswith('" (page 1)'), printed)
                self.assertEqual(vd.txt_printed(passage), printed[len('   Quote: "'):-len('" (page 1)')])

    def test_a_rendered_quotation_is_read_back_exactly_and_the_same_line_re_indented_is_not_the_passage(self):
        snapshots = json.loads((SAMPLES / 'customer-report-snapshots.json').read_text(encoding='utf-8'))
        for kind in ('draft', 'approved'):
            for passage in self.PASSAGES:
                with self.subTest(kind=kind, passage=passage):
                    snap = copy.deepcopy(snapshots[kind])
                    snap['items'][0]['quotes'][0]['text'] = passage
                    text = reports.render_customer_txt(snap, snapshots['generated']).decode('utf-8')
                    (quote, *_) = vd.parse_customer_txt(text)['items'][0].quotes
                    self.assertTrue(quote['parsed'], quote)
                    self.assertEqual(quote['printed'], vd.txt_printed(passage))
                    self.assertTrue(vd._quote_matches(quote, passage))
                    # each continued line one space deeper, and (where it is deeper than seven) one space shallower:
                    # no longer what the writer prints for this passage
                    lines = text.split('\n')
                    at = next(n for n, line in enumerate(lines) if line.startswith('   Quote: "'))
                    continued = [n for n in range(at + 1, len(lines)) if lines[n].startswith(reports.CONTINUATION)]
                    continued = continued[:next((i for i, n in enumerate(continued) if n != at + 1 + i), len(continued))]
                    for n in continued:
                        for edit in (' ' + lines[n],) + ((lines[n][1:],) if lines[n].startswith(reports.CONTINUATION + ' ')
                                                         else ()):
                            other = lines[:n] + [edit] + lines[n + 1:]
                            (moved, *_) = vd.parse_customer_txt('\n'.join(other))['items'][0].quotes
                            self.assertFalse(vd._quote_matches(moved, passage), (n, edit))

    def test_the_checker_s_copies_of_the_writer_s_constants_are_the_writer_s(self):
        self.assertEqual(vd.CUSTOMER_QUOTE_CONTINUATION, reports.CONTINUATION)
        self.assertEqual(vd.CONTINUATION, reports.CONTINUATION)
        self.assertEqual(vd.CONTROL.pattern, reports.CONTROL.pattern)


class IndentedQuotationExportTests(ExportCase):
    """B-04 through the real pipeline: the genuine exports of a document whose quoted passage continues onto an indented
    line pass every check against ops-agent's operator view, at every indent; the same file re-indented fails."""

    def genuine(self, indent):
        text, codes, two = indented(indent)
        s = persist_text(text, codes)
        quotes = {code['code']: [(q['start'], q['end']) for q in code['why']['quotes']]
                  for code in self.payload(s, s.agent)['codes']}
        start = text.index(two)
        self.assertIn((start, start + len(two)), quotes['45385'])  # the page quotes the two-line passage
        self.decide(s, s.agent, '45380', 'approve')
        self.decide(s, s.agent, '45385', 'approve')
        files = self.exports(s, s.agent)
        view, trace = self.operator_view(s)
        return s, files, view, trace, (start, start + len(two))

    def test_every_genuine_export_passes_at_every_indent(self):
        for indent in (0, 6, 7, 8, 13, 14):
            with self.subTest(indent=indent):
                s, files, view, trace, (start, end) = self.genuine(indent)
                self.assert_all_pass(files, view, trace, s.agent.label())
                approved = files[('approved', 'txt')][1].decode('utf-8')
                self.assertIn(f'characters {start}–{end}', approved)
                continued = [line for line in approved.split('\n') if line.endswith(SNARE + f'" (page 1, characters {start}–{end})')]
                self.assertEqual(len(continued), 1)
                self.assertEqual(len(continued[0]) - len(continued[0].lstrip(' ')), indent if indent >= 7 else indent + 7)

    def test_the_genuine_export_re_indented_by_one_space_fails(self):
        s, files, view, trace, (start, end) = self.genuine(8)
        by = s.agent.label()
        approved = files[('approved', 'txt')][1].decode('utf-8')
        draft = files[('draft', 'txt')][1].decode('utf-8')
        line = ' ' * 8 + SNARE + f'" (page 1, characters {start}–{end})'
        for edit in (' ' + line, line[1:]):
            with self.subTest(edit=edit[:12]):
                self.assertIn('items.evidence.exact', self.failing('approved', 'txt', changed(approved, f'\n{line}\n', f'\n{edit}\n'),
                                                                   view, trace, by))
        draft_line = ' ' * 8 + SNARE + '" (page 1)'
        for edit in (' ' + draft_line, draft_line[1:]):
            with self.subTest(edit=edit[:12]):
                self.assertIn('items.evidence.support', self.failing('draft', 'txt', changed(draft, f'\n{draft_line}\n', f'\n{edit}\n'),
                                                                     view, trace, by))


class ServerStatementCase(ExportCase):
    def answered(self, s, fact='extent', code='45378', value='not_documented'):
        """The member answers ``value`` on the details row that asks ``fact`` of ``code``, in one save."""
        cust = self.payload(s, s.reviewer)
        (row,) = [r for r in cust['details_needed'] if r['fact'] == fact and code in r['affects']]
        response = post(signed_in(s.reviewer), f'/api/encounters/{s.encounter.pk}/details',
                        {'answers': [{'id': row['id'], 'fact': fact, 'value': value}]})
        self.assertEqual(response.status_code, 201, response.content)

    def attempt(self, s, code, action):
        """POST /decisions as the reviewer; the response."""
        doc = self.payload(s, s.reviewer)
        body = {'proposal_id': next(c['id'] for c in doc['codes'] if c['code'] == code), 'action': action,
                'note': 'Synthetic: refutation round 3 (B-02, B-03).'}
        if action == 'approve':
            body.update(acknowledgement=review.ACKNOWLEDGEMENTS[s.reviewer.actor_kind], modifiers=[])
        return post(signed_in(s.reviewer), f'/api/encounters/{s.encounter.pk}/decisions', body)

    def assert_statement_is_the_page(self, s, view):
        """The operator view's 'customer' on each code is what GET /api/encounters/<id> serves a reviewing member for it
        (its number, status, labels and actions), and nothing on a code the page does not list."""
        cust = self.payload(s, s.reviewer)
        listed = {code['id']: code for code in cust['codes']}
        for proposal in view['assessment']['proposals']:
            statement = proposal['customer']
            code = listed.get(proposal['id'])
            if code is None:
                self.assertIsNone(statement, proposal['code'])
                continue
            self.assertEqual(statement, {'number': code['number'], 'status': code['status'],
                                         'status_label': code['status_label'], 'sub_label': code['sub_label'],
                                         'reviewer_actions': code['allowed_actions']}, proposal['code'])
        self.assertEqual(set(listed), {p['id'] for p in view['assessment']['proposals'] if p['customer'] is not None})
        # a member who may not review is offered nothing; the statement stays what a reviewing member is allowed
        viewer = {code['id']: code['allowed_actions'] for code in self.payload(s, s.viewer)['codes']}
        self.assertEqual(set(viewer), set(listed))
        self.assertTrue(all(actions == [] for actions in viewer.values()))
        return cust


class AnsweredReinstatementTests(ServerStatementCase):
    """B-02: a reinstated 45378 whose 'How far was the instrument advanced?' detail the member answered "Not
    documented": the server shows it Excluded ("A needed detail is not documented") and accepts only revoke."""

    def setUp(self):
        super().setUp()
        self.s = persist_text(OFFICE_DENIED, OFFICE_CODES)
        self.decide(self.s, self.s.reviewer, '45378', 'reinstate')
        self.answered(self.s)
        self.view, self.trace = self.operator_view(self.s)

    def test_the_operator_view_carries_what_the_page_shows(self):
        cust = self.assert_statement_is_the_page(self.s, self.view)
        p78 = next(p for p in self.view['assessment']['proposals'] if p['code'] == '45378')
        self.assertEqual((p78['bucket'], p78['status'], p78['decision']['action'], p78['overlay_reason']),
                         ('excluded', 'excluded', 'reinstate', review.DETAIL_UNAVAILABLE))
        self.assertEqual(p78['customer'], {'number': 2, 'status': 'excluded', 'status_label': 'Excluded',
                                           'sub_label': UNAVAILABLE, 'reviewer_actions': ['revoke']})
        self.assertEqual(p78['allowed_actions'], [])  # the operator's own: none (no membership)
        # the statement is the server's own rule for a reviewing member, the rule record_decision enforces
        assessment = self.s.encounter.current_assessment
        proposal = assessment.proposals.get(code='45378')
        self.assertEqual(review.allowed_actions(proposal, assessment, self.s.membership(self.s.reviewer)), ['revoke'])
        self.assertEqual(self.attempt(self.s, '45378', 'approve').status_code, 409)
        self.assertEqual(self.attempt(self.s, '45378', 'reject').status_code, 409)
        self.assertEqual(next(c for c in cust['codes'] if c['code'] == '45378')['allowed_actions'], ['revoke'])

    def test_the_walk_passes_the_genuine_page_and_fails_a_page_that_misstates_it(self):
        cust = self.payload(self.s, self.s.reviewer)
        judged = walk_judged(cust, self.view)
        self.assertEqual([(k, v) for k, v in judged.items() if v[0] != 'pass'], [])
        forged = copy.deepcopy(cust)
        code = next(c for c in forged['codes'] if c['code'] == '45378')
        code.update(status='ready', status_label='Ready for review', sub_label=REINSTATED,
                    allowed_actions=['approve', 'reject', 'revoke'])
        judged = walk_judged(forged, self.view)
        self.assertEqual(sorted(k for k, v in judged.items() if v[0] != 'pass'), ['customer.codes.actions', 'customer.codes.status'])
        self.assertIn('45378 offers approve, reject (the server accepts revoke from this member)', judged['customer.codes.actions'][1])
        offer = copy.deepcopy(cust)  # the right status, and Approve offered
        next(c for c in offer['codes'] if c['code'] == '45378')['allowed_actions'] = ['approve', 'revoke']
        self.assertEqual(sorted(k for k, v in walk_judged(offer, self.view).items() if v[0] != 'pass'), ['customer.codes.actions'])
        relabelled = copy.deepcopy(cust)  # the right status and actions, another reason
        next(c for c in relabelled['codes'] if c['code'] == '45378')['sub_label'] = 'Excluded by a documentation check'
        self.assertEqual(sorted(k for k, v in walk_judged(relabelled, self.view).items() if v[0] != 'pass'), ['customer.codes.status'])

    def test_the_download_check_passes_the_genuine_drafts_and_fails_drafts_that_misstate_it(self):
        files = self.exports(self.s, self.s.reviewer, kinds=(('draft', 'txt'), ('draft', 'csv')))
        by = self.s.reviewer.label()
        for key, bad in self.judged(files, self.view, self.trace, by).items():
            self.assertEqual(bad, [], key)
        txt = files[('draft', 'txt')][1].decode('utf-8')
        csv = files[('draft', 'csv')][1].decode('utf-8')
        forged_txt = changed(changed(txt, '45378 — Excluded —', '45378 — Ready for review —'), f'   {UNAVAILABLE}\n',
                             f'   {REINSTATED}\n')
        forged_csv = changed(csv, '"45378","1","","excluded"', '"45378","1","","ready"')
        self.assertIn('items.status', self.failing('draft', 'txt', forged_txt, self.view, self.trace, by))
        self.assertIn('csv.items.status', self.failing('draft', 'csv', forged_csv, self.view, self.trace, by))


class AwaitingReinstatementTests(ServerStatementCase):
    """B-03: a reinstated 45378 waiting on its 'How far was the instrument advanced?' detail: the server shows it
    "Needs a detail" ("Reinstated in review") and accepts reject and revoke."""

    def test_the_walk_passes_the_genuine_page_and_the_server_accepts_what_the_statement_says(self):
        for text in (OFFICE_DENIED, OFFICE_READY_DENIED):
            with self.subTest(text=text[-80:]):
                s = persist_text(text, OFFICE_CODES)
                self.decide(s, s.reviewer, '45378', 'reinstate')
                view, _ = self.operator_view(s)
                cust = self.assert_statement_is_the_page(s, view)
                p78 = next(p for p in view['assessment']['proposals'] if p['code'] == '45378')
                self.assertEqual((p78['status'], p78['overlay_reason'], p78['approve_withheld_by']),
                                 ('needs_clarification', '', 'review.reinstatement'))
                self.assertEqual(p78['customer'], {'number': 2, 'status': 'needs_detail', 'status_label': 'Needs a detail',
                                                   'sub_label': REINSTATED, 'reviewer_actions': ['reject', 'revoke']})
                judged = walk_judged(cust, view)
                self.assertEqual([(k, v) for k, v in judged.items() if v[0] != 'pass'], [])
                forged = copy.deepcopy(cust)
                next(c for c in forged['codes'] if c['code'] == '45378')['allowed_actions'] = ['approve', 'reject', 'revoke']
                judged = walk_judged(forged, view)
                self.assertEqual(judged['customer.codes.actions'][0], 'fail')
                self.assertIn('45378 offers approve (the server accepts reject, revoke from this member)',
                              judged['customer.codes.actions'][1])
                self.assertEqual(self.attempt(s, '45378', 'approve').status_code, 409)
                self.assertEqual(self.attempt(s, '45378', 'reject').status_code, 201)


class WithoutTheStatementTests(ServerStatementCase):
    """Fail closed: an operator view that does not carry the server's statement of the customer page cannot verify a
    status or an action - the walk fails those checks as "cannot verify" and the download check reports them
    incomplete - and never passes the page or a draft."""

    def test_nothing_is_judged_against_a_statement_the_view_does_not_carry(self):
        s = persist_text(OFFICE_DENIED, OFFICE_CODES)
        self.decide(s, s.reviewer, '45378', 'reinstate')
        self.answered(s)
        view, trace = self.operator_view(s)
        bare = stripped_of_statements(view)
        cust = self.payload(s, s.reviewer)
        judged = walk_judged(cust, bare)
        self.assertEqual(sorted(k for k, v in judged.items() if v[0] != 'pass'), ['customer.codes.actions', 'customer.codes.status'])
        for check in ('customer.codes.actions', 'customer.codes.status'):
            self.assertIn('cannot verify', judged[check][1])
        files = self.exports(s, s.reviewer, kinds=(('draft', 'txt'), ('draft', 'csv')))
        for (kind, fmt), bad in self.judged(files, bare, trace, s.reviewer.label()).items():
            self.assertEqual([(check, status) for check, status, _ in bad],
                             [('items.status' if fmt == 'txt' else 'csv.items.status', 'incomplete')], (kind, fmt, bad))
            results = (vd.check_customer_txt('r3', 'draft.txt', files[(kind, fmt)][1].decode('utf-8'), kind, bare, trace,
                                             s.reviewer.label()) if fmt == 'txt'
                       else vd.check_customer_csv('r3', 'draft.csv', files[(kind, fmt)][1].decode('utf-8'), kind, bare, trace))
            self.assertEqual(vd.exit_status(results), 2)
        self.assertEqual([t['status'] for t in vd.customer_truth(bare, 'draft')], [vd.UNKNOWN, vd.UNKNOWN])
        self.assertEqual([t['status'] for t in vd.customer_truth(view, 'draft')], [c['status'] for c in cust['codes']])
        self.assertEqual([c['status'] for c in cust['codes']], ['needs_detail', 'excluded'])  # 99213 waits on its E/M basis

    def test_a_statement_that_cannot_be_made_is_left_out_and_never_fails_the_operator_s_page(self):
        s = persist_text(OFFICE_DENIED, OFFICE_CODES)
        cust = self.payload(s, s.reviewer)
        with mock.patch('studio.customer_api.code_rows', side_effect=RuntimeError('synthetic defect')), \
                self.assertLogs('studio.serializers', level='ERROR'):
            view, _ = self.operator_view(s)
        self.assertEqual([(p['code'], p['customer']) for p in view['assessment']['proposals']], [('99213', None), ('45378', None)])
        self.assertNotIn('synthetic defect', json.dumps(view))
        judged = walk_judged(cust, view)  # the tools cannot verify the page: never a pass
        self.assertEqual(sorted(k for k, v in judged.items() if v[0] != 'pass'), ['customer.codes.actions', 'customer.codes.status'])

    def test_the_statement_is_absent_only_where_the_page_lists_no_code(self):
        s = persist_text(OFFICE_DENIED, OFFICE_CODES)
        view, _ = self.operator_view(s)
        self.assert_statement_is_the_page(s, view)
        self.assertEqual([(p['code'], (p['customer'] or {}).get('number')) for p in view['assessment']['proposals']],
                         [('99213', 1), ('45378', 2)])
        # an addendum makes the assessment another revision's: the page lists no code, and the statement names none
        pf.addendum(s.encounter, s.reviewer, 'Synthetic addendum: no change to the findings.')
        s.encounter.refresh_from_db()
        self.assertEqual(self.payload(s, s.reviewer)['codes'], [])
        view, _ = self.operator_view(s)
        self.assertEqual([(p['code'], p['customer']) for p in view['assessment']['proposals']],
                         [('99213', None), ('45378', None)])
