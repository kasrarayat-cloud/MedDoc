"""Format @4 checks of ops/verify_downloads.py against the layout studio/reports.py writes ('cpt-studio-report@4').

Hand-made reports built with test_verify_downloads' helpers. A source passage CPT Studio selected is printed as
'       + source passage selected by CPT Studio: "<passage>" [chars s–e]' and, like every passage in the TXT, a line
break inside it continues at nine spaces (reports._item_block / _indent); the closing bracket is on its last line.

    cd cpt-studio && .venv/bin/python -m unittest discover -s ops -p 'test_format4_*.py' -v
"""
import unittest

import test_verify_downloads as h

vd = h.vd

WRAPPED = 'a separate rectal lesion was biopsied with cold forceps\nand left in place for a later resection.'
TEXT = h.TEXT + 'Findings: ' + WRAPPED + '\n'
OPENER = '       + source passage selected by CPT Studio: '


def doc():
    item = h.proposal('p-biopsy', '45380', 'selected', 'ready', h.BIOPSY)
    item['evidence'] = [h.span_in(TEXT, h.BIOPSY)]
    source = h.span_in(TEXT, WRAPPED)
    source.pop('page')
    item['support'] = {'origin': 'primary', 'service': 'S1', 'status': 'warn', 'source': [source]}
    data = h.doc_with(TEXT, [item])
    data['coding'] = {'state': 'pending_review'}
    data['assessment']['services'] = {'conflicts': []}
    data['assessment']['completeness'] = {'unresolved_items': []}
    return data, source


def report(source, closing=None, first=None):
    """The draft TXT with the @4 sections and the item's source passage, as the renderer lays them out."""
    head, tail = WRAPPED.split('\n')
    opener = OPENER + (first if first is not None else f'"{head}')
    close = closing if closing is not None else f'         {tail}" [chars {source["start"]}–{source["end"]}]'

    def mutate(lines):
        lines = [line.replace('format cpt-studio-report@1', 'format cpt-studio-report@4') for line in lines]
        at = lines.index('ENCOUNTER, SOURCE AND REVISION') - 1
        lines = lines[:at] + ['', 'CODING COMPLETENESS', '  State: pending_review',
                              '  Every documented service has a proposal; each still needs a reviewer\'s decision.',
                              '', 'UNRESOLVED DOCUMENTED SERVICES — NO SUPPORTED PROPOSAL',
                              '  - none: every documented act the catalogue reconciles has a selected proposal or is '
                              'not separately reported', '', 'CONFLICTS IN THE RECORD', '  - none'] + lines[at:]
        at = next(i for i, line in enumerate(lines) if line.startswith('       - "' + h.BIOPSY)) + 1
        return lines[:at] + ['     Evidence support: warn — The provider passage does not show forceps biopsy.',
                             opener, close] + lines[at:]
    return h.txt_report('draft', doc()[0]['assessment']['proposals'], mutate_lines=mutate)


def status(text, api):
    return [r.status for r in vd.check_txt('d', 'r.txt', text, 'draft', api) if r.check == 'txt.source_passages']


class SourcePassageOverSeveralLinesTests(unittest.TestCase):
    def test_a_genuine_wrapped_source_passage_passes(self):
        api, source = doc()
        self.assertEqual(status(report(source), api), ['pass'])

    def test_a_wrapped_source_passage_with_altered_text_fails(self):
        api, source = doc()
        altered = f'         and removed with a hot snare." [chars {source["start"]}–{source["end"]}]'
        self.assertEqual(status(report(source, closing=altered), api), ['fail'])

    def test_a_wrapped_source_passage_with_wrong_offsets_fails(self):
        api, source = doc()
        shifted = f'         and left in place for a later resection." [chars {source["start"]}–{source["end"] + 7}]'
        self.assertEqual(status(report(source, closing=shifted), api), ['fail'])

    def test_a_source_line_without_its_closing_citation_fails(self):
        api, source = doc()
        self.assertEqual(status(report(source, closing='         and left in place for a later resection."'), api),
                         ['fail'])

    def test_control_a_single_line_source_passage_with_altered_text_fails(self):
        api, source = doc()
        line = f'"{h.SNARE}" [chars {source["start"]}–{source["end"]}]'
        self.assertEqual(status(report(source, first=line, closing='     Rationale: synthetic'), api), ['fail'])



# --- a member date conflict's hold (session interpretation 19; gi2 ops) -------------------------------------------------
#
# studio/jobs.py MEMBER_DATE_CONFLICT_MESSAGE, written out here; the PROVIDER USAGE lines are those reports._provider_section
# wrote for a real hold and the one request a context save then sent (offline walk, 2026-10-28).
HOLD_MESSAGE = ('Nothing was sent: the service date entered as encounter metadata differs from the documented one. '
                'Correct or clear the metadata (or add an addendum), and the request is made for the agreed date.')
SENT_SHA, ANSWER_SHA = '8' * 64, '3' * 64
HOLD_HEAD = ('  - corti · live · not_sent · revision 1 · recorded 2026-10-28T22:21:54Z · nothing was sent: the service '
             'date entered as encounter metadata conflicts with the document')
USAGE = ['', 'PROVIDER USAGE', HOLD_HEAD, '    Usage: none reported', '    Request sha256: none · Response sha256: none',
         '  - corti · live · succeeded · HTTP 200 · revision 1 · requested 2026-10-28T22:21:57Z · used by this assessment',
         '    Usage: {"creditsConsumed": 0.02} (provider_reported_credits_not_usd)',
         f'    Request sha256: {SENT_SHA} · Response sha256: {ANSWER_SHA}']


def run(run_id, **fields):
    return {'id': run_id, 'provider': 'corti', 'mode': 'live', 'state': 'succeeded', 'http_status': 200,
            'usage': {'creditsConsumed': 0.02}, 'usage_basis': 'provider_reported_credits_not_usd',
            'request_sha256': SENT_SHA, 'response_sha256': ANSWER_SHA, 'reused_from': None, 'error': '',
            'reconciled': False, 'purpose': 'primary', 'scope_items': [], **fields}


HOLD = run('run-hold', state='not_sent', http_status=None, usage={}, usage_basis='', request_sha256='', response_sha256='',
           error=HOLD_MESSAGE)


def held(runs=None, edit=None):
    """The encounter JSON with a hold and the request sent after it, and the draft TXT listing them."""
    api, source = doc()
    api['provider_runs'] = [dict(HOLD), run('run-sent')] if runs is None else runs
    lines = report(source).split('\n')
    at = lines.index('NOT VERIFIED') - 1
    usage = edit(list(USAGE)) if edit else list(USAGE)
    return '\n'.join(lines[:at] + usage + lines[at:]), api


def hold_statuses(text, api):
    return {r.check: r.status for r in vd.check_txt('d', 'r.txt', text, 'draft', api) if r.check.startswith('txt.member_date_hold')}


class MemberDateHoldTests(unittest.TestCase):
    def test_a_genuine_hold_and_its_request_pass(self):
        self.assertEqual(hold_statuses(*held()), {'txt.member_date_hold.listed': 'pass',
                                                  'txt.member_date_hold.provider_usage': 'pass'})

    def test_a_hold_worded_as_requested_and_used_fails(self):
        worded = HOLD_HEAD.split(' · recorded ')[0] + ' · requested 2026-10-28T22:21:54Z · used by this assessment'
        statuses = hold_statuses(*held(edit=lambda lines: [worded if line == HOLD_HEAD else line for line in lines]))
        self.assertEqual(statuses['txt.member_date_hold.listed'], 'fail')

    def test_a_hold_said_to_be_requested_though_nothing_was_sent_fails(self):
        requested = HOLD_HEAD.replace(' · recorded ', ' · requested ')
        statuses = hold_statuses(*held(edit=lambda lines: [requested if line == HOLD_HEAD else line for line in lines]))
        self.assertEqual(statuses['txt.member_date_hold.listed'], 'fail')

    def test_a_hold_left_out_fails(self):
        statuses = hold_statuses(*held(edit=lambda lines: lines[:2] + lines[5:]))
        self.assertEqual(statuses, {'txt.member_date_hold.listed': 'fail', 'txt.member_date_hold.provider_usage': 'fail'})

    def test_a_hold_listed_with_usage_fails(self):
        statuses = hold_statuses(*held(edit=lambda lines: lines[:3] + ['    Usage: {"creditsConsumed": 0.02}'] + lines[4:]))
        self.assertEqual(statuses, {'txt.member_date_hold.listed': 'fail', 'txt.member_date_hold.provider_usage': 'fail'})

    def test_the_request_after_it_misstated_fails(self):
        other = 'c' * 64
        statuses = hold_statuses(*held(edit=lambda lines: [line.replace(SENT_SHA, other) for line in lines]))
        self.assertEqual(statuses, {'txt.member_date_hold.listed': 'pass', 'txt.member_date_hold.provider_usage': 'fail'})

    def test_control_no_hold_no_check(self):
        # every other report is read exactly as before: a not-sent run for another reason is not a hold
        for runs in ([run('run-sent')], [run('run-x', state='not_sent', usage={}, request_sha256='', response_sha256='',
                                             error='No recorded response for this request.')]):
            with self.subTest(runs=[r['id'] for r in runs]):
                self.assertEqual(hold_statuses(*held(runs=runs)), {})


if __name__ == '__main__':
    unittest.main()
