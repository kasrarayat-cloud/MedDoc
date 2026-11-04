"""Unit tests for the customer-report path of ops/verify_downloads.py (cpt-studio-customer-report@1).

Over the committed samples - studio/reports.py's own bytes of the sample snapshots, which tests/test_cux_r2_reports.py
pins (refutation round 2, L3-1: the samples were once written in a grammar the server never wrote, so every genuine
export failed the checks the samples passed) - and the operator view the walk's operator account reads
(operator-encounter.json: a grant and no membership): each check passes on the samples and fails on the defect it exists
for. The comparison source is the OPERATOR view of the encounter, never the customer API the walk's browser read.
Offline; no server.

    cd cpt-studio && python3 -B -m unittest discover -s ops -p 'test_customer_verify_downloads.py' -v
"""
import copy
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('cpt_customer_verify_downloads', HERE / 'verify_downloads.py')
vd = importlib.util.module_from_spec(_spec)
sys.modules['cpt_customer_verify_downloads'] = vd  # dataclasses resolve their module while the class is built
_spec.loader.exec_module(vd)

SAMPLES = HERE / 'verification' / 'samples'
AGENT = 'CPT Studio review agent (automated agent)'
LABEL = 'Agent-executed synthetic review — not clinical approval'
HUMAN = 'Reviewer Four'
APPROVER_80 = f'   Approved by {AGENT} (agent) at 2026-11-03T22:05:00+00:00'
APPROVER_85 = f'   Approved by {AGENT} (agent) at 2026-11-03T22:05:30+00:00'
QUOTE_80 = '   Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." (page 1, characters 256–329)'
BANNER_ROW = '"' + '","'.join(['SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS'] + [''] * 16) + '"'


def sample(name: str) -> str:
    return (SAMPLES / name).read_bytes().decode('utf-8')  # as downloaded: a CSV keeps its CR LF


def operator() -> dict:
    return json.loads(sample('operator-encounter.json'))


def trace() -> dict:
    return json.loads(sample('operator-trace.json'))


def failed(results) -> list:
    return sorted({r.check for r in results if r.status == 'fail'})


def statuses(results) -> dict:
    return {r.check: r.status for r in results}


def changed(text: str, old: str, new: str, count: int = 1) -> str:
    """``text`` with ``old`` replaced once: it must occur exactly ``count`` times, and the edit must apply."""
    assert text.count(old) == count, f'expected {count} / measured {text.count(old)} of {old!r}'
    out = text.replace(old, new, 1)
    assert out != text, f'the edit of {old!r} did not apply'
    return out


def txt(kind: str, text: str | None = None, api: dict | None = None):
    return vd.check_customer_txt('d', f'{kind}.txt', sample(f'customer-report-{kind}.txt') if text is None else text, kind,
                                 operator() if api is None else api, trace(), AGENT)


def csv(kind: str, text: str | None = None, api: dict | None = None):
    return vd.check_customer_csv('d', f'{kind}.csv', sample(f'customer-report-{kind}.csv') if text is None else text, kind,
                                 operator() if api is None else api, trace())


def proposal(api: dict, code: str) -> dict:
    return next(p for p in api['assessment']['proposals'] if p['code'] == code)


def without_modifiers(api: dict) -> dict:
    """The operator view as served before serializers._decision_json carried 'modifiers' (refutation round 2, L3-3)."""
    api = copy.deepcopy(api)
    for p in api['assessment']['proposals']:
        if p.get('decision'):
            p['decision'].pop('modifiers', None)
    return api


def stated(p: dict, status: str, sub_label: str, actions: list) -> dict:
    """``p`` with the operator view's statement of what the customer page shows for it (serializers.customer_codes: its
    number kept, the status and its label, the sub label and the actions a member who may review is allowed) - what a
    test that changes the persisted state must change with it, as the server would."""
    p['customer'] = {'number': (p.get('customer') or {}).get('number'), 'status': status,
                     'status_label': vd.CUSTOMER_STATUS_LABELS[status], 'sub_label': sub_label, 'reviewer_actions': actions}
    return p


def reinstated_by_agent_approved_by_human(api: dict, code: str = '45385') -> dict:
    """``code`` as an excluded code an agent reinstated and a human then approved (the 'denied' shape of L3-6)."""
    api = copy.deepcopy(api)
    p = proposal(api, code)
    p.update(bucket='excluded', status='excluded', reinstatable=True,
             reinstated_by={'reviewer': AGENT, 'reviewer_kind': 'agent', 'decided_at': '2026-11-03T22:04:00+00:00'})
    p['decision'].update(reviewer=HUMAN, reviewer_kind='human')
    stated(p, 'approved', '', ['revoke'])  # a person's approval: no agent label
    return api


class SampleTests(unittest.TestCase):
    def test_each_sample_report_passes_every_check_against_the_operator_view(self):
        for kind in ('approved', 'draft'):
            for check, results in (('txt', txt(kind)), ('csv', csv(kind))):
                with self.subTest(kind=kind, fmt=check):
                    self.assertEqual([(r.check, r.status, r.detail) for r in results if r.status != 'pass'], [])
                    names = {r.check for r in results}
                    for owed in ('format', 'scan.file'):
                        self.assertIn(owed, names)
        self.assertIn('items.approver', {r.check for r in txt('approved')})
        self.assertIn('csv.items.approver', {r.check for r in csv('approved')})
        self.assertIn('items.status', {r.check for r in txt('draft')})
        for results in (txt('approved'), txt('draft')):
            self.assertIn('header.agent_label', {r.check for r in results})
        for kind in ('approved', 'draft'):
            self.assertIn('items.agent_label', {r.check for r in txt(kind)})
            self.assertIn('csv.items.agent_label', {r.check for r in csv(kind)})

    def test_the_samples_are_in_the_grammar_the_server_writes(self):
        # the banner opens and closes each file; items at column 0 with their details at three spaces (TXT); the
        # header row, then the banner row, the rows and the banner row again (CSV); review_label last
        text = sample('customer-report-approved.txt').splitlines()
        self.assertEqual(text[:3], ['SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS', 'CPT STUDIO — APPROVED CODES', LABEL])
        self.assertIn('Generated: 2026-11-03T22:10:00Z by CPT Studio review agent (automated agent)', text)
        self.assertIn('1. 45380 — units 1 — modifiers: none', text)
        self.assertIn(APPROVER_80, text)
        rows = vd.scanner().csv_rows(sample('customer-report-approved.csv'))
        rows = [row for row in rows if any(cell for cell in row)]
        self.assertEqual(tuple(rows[0]), vd.CUSTOMER_CSV_COLUMNS)
        self.assertEqual(rows[0][-1], 'review_label')
        self.assertTrue(vd._banner_row(rows[1]) and vd._banner_row(rows[-1]))

    def test_the_truth_is_the_operator_view_s_approved_items_in_the_contract_s_order(self):
        truth = vd.customer_truth(operator(), 'approved')
        self.assertEqual([(t['number'], t['code'], t['units'], t['modifiers'], t['approver_kind'], t['agent']) for t in truth],
                         [(1, '45380', '1', (), 'agent', True), (2, '45385', '1', ('XS',), 'agent', True)])
        self.assertEqual([t['code'] for t in vd.customer_truth(operator(), 'draft')], ['45380', '45385'])
        undecided = operator()
        undecided['assessment']['proposals'][0]['decision'] = None
        stated(undecided['assessment']['proposals'][0], 'ready', '', ['approve', 'reject'])
        self.assertEqual([t['code'] for t in vd.customer_truth(undecided, 'approved')], ['45385'])
        first = vd.customer_truth(undecided, 'draft')[0]
        self.assertEqual((first['status'], first['modifiers'], first['agent']), ('ready', (), False))


class ApprovedTxtTests(unittest.TestCase):
    def assert_fails(self, mutate, wanted, kind='approved', api=None):
        text = sample(f'customer-report-{kind}.txt')
        mutated = mutate(text)
        self.assertNotEqual(mutated, text, 'the mutation did not apply')
        got = failed(txt(kind, mutated, api))
        for check in wanted:
            self.assertIn(check, got, f'{check} not failed; failed {got}')
        return got

    def test_an_item_that_is_not_an_approved_code_fails(self):
        line = f'3. 45378 — units 1 — modifiers: none\n{APPROVER_80}\n'
        self.assert_fails(lambda t: changed(t, '\nLimitations', f'{line}\nLimitations'), ['items.items'])

    def test_a_missing_approved_code_fails(self):
        self.assert_fails(lambda t: t[:t.index('2. 45385')] + t[t.index('\nLimitations'):], ['items.items'])

    def test_units_and_modifiers_are_the_persisted_ones(self):
        self.assert_fails(lambda t: changed(t, '1. 45380 — units 1', '1. 45380 — units 2'), ['items.units'])
        self.assert_fails(lambda t: changed(t, 'modifiers: XS', 'modifiers: none'), ['items.modifiers'])
        self.assert_fails(lambda t: changed(t, 'modifiers: XS', 'modifiers: 59, XS'), ['items.modifiers'])
        self.assert_fails(lambda t: changed(t, '1. 45380 — units 1 — modifiers: none', '1. 45380 — units 1 — modifiers: 59'),
                          ['items.modifiers'])

    def test_a_modifier_the_operator_view_does_not_record_is_never_read_as_none(self):
        # refutation round 2, L3-3: a view whose decisions name no modifiers made the reviewer's XS a failure and a
        # report without it a pass; the comparison could not run, and says so (fail closed, exit status 2)
        bare = without_modifiers(operator())
        dropped = changed(sample('customer-report-approved.txt'), 'modifiers: XS', 'modifiers: none')
        for text in (sample('customer-report-approved.txt'), dropped):
            results = txt('approved', text, bare)
            self.assertEqual(statuses(results)['items.modifiers'], 'incomplete')
            self.assertEqual(failed(results), [])
            self.assertEqual(vd.exit_status(results), 2)
        self.assertEqual([t['modifiers'] for t in vd.customer_truth(bare, 'approved')], [vd.UNKNOWN, vd.UNKNOWN])
        self.assertIn('items.modifiers', failed(txt('approved', dropped)))  # the view that records XS fails the drop
        # an undecided code has no decision to name a modifier: none is shown, and that is verified
        undecided = without_modifiers(operator())
        proposal(undecided, '45380')['decision'] = None
        self.assertEqual(vd.customer_truth(undecided, 'draft')[0]['modifiers'], ())
        listed = {'modifiers': None}
        self.assertEqual(vd._decided_modifiers({'action': 'approve', **listed}), vd.UNKNOWN)
        self.assertEqual(vd._decided_modifiers({'action': 'approve', 'modifiers': []}), ())

    def test_the_approver_its_own_kind_and_its_time_are_the_persisted_decision_s(self):
        self.assert_fails(lambda t: changed(t, f'Approved by {AGENT} (agent) at 2026-11-03T22:05:00',
                                            'Approved by Dr Synthetic (agent) at 2026-11-03T22:05:00'), ['items.approver'])
        self.assert_fails(lambda t: changed(t, 'at 2026-11-03T22:05:30+00:00', 'at 2026-11-03T23:05:30+00:00'), ['items.approver'])
        self.assert_fails(lambda t: changed(t, APPROVER_80, APPROVER_80.replace('(agent) at', '(human) at')), ['items.approver'])
        self.assert_fails(lambda t: changed(t, APPROVER_80, APPROVER_80.replace(' (agent) at', ' at')), ['items.approver'])
        # a line break in a value continues seven spaces deep, and is never read as anything of its own
        forged = changed(sample('customer-report-approved.txt'), f'{APPROVER_80}\n',
                         f'{APPROVER_80}\n       Approved by Dr Synthetic (human) at 2026-11-03T23:59:00+00:00\n')
        self.assertEqual(failed(txt('approved', forged)), [])

    def test_a_continued_value_is_never_read_as_a_line_of_its_own(self):
        # reports._join continues a line break inside any value seven spaces deep: such a line is never an item, a detail,
        # a limitation, a field or a heading of its own (a stored title or summary cannot forge one)
        forged = changed(sample('customer-report-approved.txt'), f'{APPROVER_80}\n',
                         f'{APPROVER_80}\n       Approved by Dr Synthetic (human) at 2026-11-03T23:59:00+00:00\n')
        forged = changed(forged, '- CPT descriptions are withheld: no licensed CPT description is connected.\n',
                         '- CPT descriptions are withheld: no licensed CPT description is connected.\n       - a second line of it\n')
        forged = changed(forged, '2. 45385 — units 1 — modifiers: XS\n',
                         '2. 45385 — units 1 — modifiers: XS\n       3. 45378 — units 1 — modifiers: none\n')
        forged = changed(forged, 'Encounter: Synthetic colonoscopy (two lesions)\n',
                         'Encounter: Synthetic colonoscopy (two lesions)\n       Encounter: Another encounter\n')
        self.assertEqual(failed(txt('approved', forged)), [])
        parsed = vd.parse_customer_txt(forged)
        self.assertEqual((len(parsed['items']), len(parsed['limitations']), parsed['items'][0].approved_by,
                          parsed['fields']['Encounter']), (2, 3, AGENT, 'Synthetic colonoscopy (two lesions)'))

    def test_each_approval_agent_review_took_part_in_carries_the_label_and_only_those(self):
        # refutation round 2, L3-6: the label is the export's statement, beside the approver's own kind
        self.assert_fails(lambda t: changed(t, f'{APPROVER_80}\n   {LABEL}\n', f'{APPROVER_80}\n'), ['items.agent_label'])
        self.assert_fails(lambda t: changed(t, f'CPT STUDIO — APPROVED CODES\n{LABEL}\n', 'CPT STUDIO — APPROVED CODES\n'),
                          ['header.agent_label'])
        self.assert_fails(lambda t: changed(t, f'\n   {LABEL}\n', '\n   Agent-executed synthetic review\n', 2), ['items.agent_label'])
        # a human's own approval carries no label: the same report of a human's approvals fails where it says so
        human = operator()
        for p in human['assessment']['proposals']:
            if p.get('decision'):
                p['decision'].update(reviewer=HUMAN, reviewer_kind='human')
        text = sample('customer-report-approved.txt').replace(f'{AGENT} (agent)', f'{HUMAN} (human)')
        self.assertEqual(text.count(f'{HUMAN} (human)'), 2)
        got = failed(txt('approved', text, human))
        self.assertEqual(got, ['header.agent_label', 'items.agent_label'])
        bare = text.replace(f'\n{LABEL}\n', '\n', 1).replace(f'\n   {LABEL}\n', '\n')
        self.assertEqual(failed(txt('approved', bare, human)), [])

    def test_a_human_s_approval_of_an_agent_s_reinstatement_is_labelled_with_the_human_kind(self):
        # one rule everywhere (customer_api.agent_approval, refutation round 2 L3-6): a person's approval is the
        # person's - the human kind and no agent label - even of a code an agent reinstated
        api = reinstated_by_agent_approved_by_human(operator())
        self.assertFalse(vd.agent_reviewed(proposal(api, '45385')))
        text = changed(sample('customer-report-approved.txt'), f'{AGENT} (agent) at 2026-11-03T22:05:30', f'{HUMAN} (human) at 2026-11-03T22:05:30')
        unlabelled = changed(text, f'{HUMAN} (human) at 2026-11-03T22:05:30+00:00\n   {LABEL}\n', f'{HUMAN} (human) at 2026-11-03T22:05:30+00:00\n')
        self.assertEqual(failed(txt('approved', unlabelled, api)), [])
        self.assertIn('items.agent_label', failed(txt('approved', text, api)))  # the person's approval labelled an agent's
        self.assertIn('items.approver', failed(txt('approved', changed(unlabelled, f'{HUMAN} (human)', f'{HUMAN} (agent)'), api)))

    def test_every_quotation_is_exact_on_its_page_and_a_passage_held_as_support(self):
        self.assert_fails(lambda t: changed(t, 'characters 256–329', 'characters 257–330'), ['items.evidence.exact', 'items.evidence.support'])
        self.assert_fails(lambda t: changed(t, '(page 1, characters 256–329)', '(page 2, characters 256–329)'), ['items.evidence.exact'])
        cecum = operator()['routing']['families'][0]['mentions'][0]['span']
        self.assert_fails(lambda t: changed(t, QUOTE_80, f'   Quote: "{cecum["text"]}" (page 1, characters {cecum["start"]}–{cecum["end"]})'),
                          ['items.evidence.support'])
        self.assert_fails(lambda t: changed(t, '(page 1, characters 256–329)', '(page 1)'), ['items.evidence.exact'])
        got = self.assert_fails(lambda t: changed(t, f'{QUOTE_80}\n', ''), ['items.quoted'])
        self.assertNotIn('items.evidence.exact', got)

    def test_the_passages_a_code_may_quote_are_the_server_s_one_rule(self):
        # refutation round 2, L3-7 and L3-10: never every exact passage where no support reading exists, never the
        # service's own passages of a 'not_applicable' reading; CPT Studio's located passages only where the reading
        # says they show the act ('warn')
        text = operator()['revision']['text']
        cecum = 'The colonoscope was advanced to the cecum.'
        start = text.index(cecum)
        located = {'start': start, 'end': start + len(cecum), 'text': cecum}
        with_cecum = changed(sample('customer-report-approved.txt'), f'{QUOTE_80}\n',
                             f'   Quote: "{cecum}" (page 1, characters {located["start"]}–{located["end"]})\n')
        unread = operator()
        proposal(unread, '45380')['support'] = {}
        self.assertEqual(vd.allowed_passages(proposal(unread, '45380'), text)[0], [])
        self.assertIn('items.evidence.support', failed(txt('approved', api=unread)))  # the provider's passage is not held
        quoteless = changed(sample('customer-report-approved.txt'), f'{QUOTE_80}\n', '')
        self.assertEqual(failed(txt('approved', quoteless, unread)), [])  # nothing to quote: none owed
        for reading, outcome in (('not_applicable', ['items.evidence.support']), ('fail', ['items.evidence.support']), ('warn', [])):
            with self.subTest(reading=reading):
                api = operator()
                proposal(api, '45380')['support'].update(status=reading, supporting=[], unrelated=[0], source=[located])
                self.assertEqual(failed(txt('approved', with_cecum, api)), outcome)
        warn = operator()
        proposal(warn, '45380')['support'].update(status='warn', supporting=[], unrelated=[0], source=[located])
        self.assertIn('items.quoted', failed(txt('approved', quoteless, warn)))  # a located passage is owed
        self.assertEqual(vd.allowed_passages(proposal(operator(), '45380'), text, {}, 'excluded'), ([], []))

    def test_the_evidence_cpt_studio_recorded_for_the_matched_act_is_support_while_it_is_performed_or_incomplete(self):
        # the wiring report's item 1 (2026-11-04): customer reports quote CPT Studio's own evidence for the matched act
        # first (customer_api._quotes); only for an act the code's support names, stored performed or incomplete
        api = operator()
        text = api['revision']['text']
        passage = 'Procedure: Colonoscopy with polyp removal.'
        start = text.index(passage)
        span = {'text': passage, 'start': start, 'end': start + len(passage)}
        api['assessment']['services'] = {'services': [{'id': 'S1', 'family': 'colonoscopy', 'acts': [
            {'id': 'act-1', 'kind': 'removal', 'status': 'performed', 'evidence': [span]}]}]}
        report = changed(sample('customer-report-approved.txt'), f'{QUOTE_80}\n',
                         f'   Quote: "{passage}" (page 1, characters {span["start"]}–{span["end"]})\n{QUOTE_80}\n')
        self.assertEqual(failed(txt('approved', report, api=api)), [])
        self.assertEqual([s['start'] for s in vd.allowed_passages(proposal(api, '45380'), text, vd.act_index(api))[0]],
                         [start, 256])  # the act's own evidence, then the supporting passage
        for status, outcome in (('incomplete', []), ('not_performed', ['items.evidence.support']),
                                ('planned', ['items.evidence.support']), (None, ['items.evidence.support'])):
            with self.subTest(status=status):
                other = json.loads(json.dumps(api))
                other['assessment']['services']['services'][0]['acts'][0]['status'] = status
                self.assertEqual(failed(txt('approved', report, api=other)), outcome)
        self.assertEqual(failed(txt('approved', report)), ['items.evidence.support'])  # no recorded reading
        other = json.loads(json.dumps(api))
        other['assessment']['services']['services'][0]['acts'][0]['id'] = 'act-2'  # an act the support does not name
        self.assertEqual(failed(txt('approved', report, api=other)), ['items.evidence.support'])

    def test_a_quotation_found_unrelated_is_never_one(self):
        api = operator()
        support = api['assessment']['proposals'][0]['support']
        support.update(unrelated=[0], supporting=[], source=[])
        got = failed(txt('approved', api=api))
        self.assertIn('items.evidence.support', got)
        detail = next(r.detail for r in txt('approved', api=api) if r.check == 'items.evidence.support')
        self.assertIn('a passage CPT Studio found unrelated', detail)

    def test_banner_format_headline_and_header_fields(self):
        self.assert_fails(lambda t: t.rstrip('\n').rsplit('\n', 1)[0] + '\n', ['marker.synthetic'])
        self.assert_fails(lambda t: t.split('\n', 1)[1], ['marker.synthetic'])
        self.assert_fails(lambda t: changed(t, 'cpt-studio-customer-report@1', 'cpt-studio-report@4'), ['format'])
        self.assert_fails(lambda t: changed(t, 'CPT STUDIO — APPROVED CODES', 'CPT STUDIO — SUGGESTED CODES — NOT APPROVED'), ['headline'])
        self.assert_fails(lambda t: changed(t, 'Encounter: Synthetic colonoscopy (two lesions)', 'Encounter: Another encounter'), ['header.encounter'])
        self.assert_fails(lambda t: changed(t, 'Date of service: 2026-11-03', 'Date of service: 2026-11-02'), ['header.date_of_service'])
        self.assert_fails(lambda t: changed(t, f'Generated: 2026-11-03T22:10:00Z by {AGENT}\n', ''), ['header.generated'])
        self.assertEqual(statuses(txt('approved', changed(sample('customer-report-approved.txt'), 'Generated: 2026-11-03T22:10:00Z by',
                                                          'Generated: today by')))['header.generated_iso'], 'warn')
        self.assert_fails(lambda t: changed(t, 'Encounter:', '7. 45378 — units 1 — modifiers: none\nEncounter:'), ['items.outside_section'])
        self.assert_fails(lambda t: changed(t, '\nLimitations\n', '\nLimitations\n3. 45378 — units 1 — modifiers: none\n'),
                          ['items.outside_section'])

    def test_another_layout_of_the_same_content_reads_the_same_and_its_defects_still_fail(self):
        # the format fixes what a report says, not how each line is laid out: items indented, ")" numbering, "1 unit",
        # "Modifiers:" in another case, details deeper, "Approved by:" with a space-separated UTC time, bullet quotations
        # with "(p. N, chars S-E)", "Generated at:" and "Generated by:" on lines of their own, capital headings, bullets
        text = sample('customer-report-approved.txt')
        for old, new in (('\nApproved codes\n', '\nAPPROVED CODES\n'), ('1. 45380 — units 1 — modifiers: none', '  1) 45380 · 1 unit · Modifiers: none'),
                         ('2. 45385 — units 1 — modifiers: XS', '  2) 45385 · Units: 1 · Modifier: XS'),
                         (APPROVER_80, f'     Approved by: {AGENT} (agent) on 2026-11-03 22:05:00 UTC'),
                         (QUOTE_80, '     - "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps." (p. 1, chars 256-329)'),
                         (f'Generated: 2026-11-03T22:10:00Z by {AGENT}', f'Generated at: 2026-11-03T22:10:00Z\nGenerated by: {AGENT}'),
                         ('\nLimitations\n', '\nLIMITATIONS\n'), ('- CPT descriptions', '  • CPT descriptions')):
            text = changed(text, old, new)
        self.assertEqual([(r.check, r.detail) for r in txt('approved', text) if r.status not in ('pass',)], [])
        parsed = vd.parse_customer_txt(text)
        self.assertEqual([(i.code, i.units, i.modifiers, i.approver_kind, i.agent_label) for i in parsed['items']],
                         [('45380', '1', (), 'agent', True), ('45385', '1', ('XS',), 'agent', True)])
        self.assertEqual(len(parsed['limitations']), 3)
        self.assertIn('items.units', failed(txt('approved', changed(text, '  1) 45380 · 1 unit', '  1) 45380 · 2 units'))))
        self.assertIn('items.modifiers', failed(txt('approved', changed(text, 'Modifier: XS', 'Modifier: 59'))))
        self.assertIn('items.evidence.exact', failed(txt('approved', changed(text, 'chars 256-329', 'chars 256-330'))))
        self.assertIn('items.approver', failed(txt('approved', changed(text, 'on 2026-11-03 22:05:00 UTC', 'on 2026-11-03 22:06:00 UTC'))))
        # numbering and order: an approved export in another order is a warning, a gap in its numbering a failure
        first, second, end = text.index('  1) 45380'), text.index('  2) 45385'), text.index('\nLIMITATIONS')
        swapped = text[:first] + text[second:end] + '\n' + text[first:second].rstrip('\n') + text[end:]
        swapped = swapped.replace('  2) 45385', '  1) 45385', 1).replace('  1) 45380', '  2) 45380', 1)
        result = statuses(txt('approved', swapped))
        self.assertEqual((result['items.items'], result['items.order']), ('pass', 'warn'))
        self.assertIn('items.items', failed(txt('approved', changed(text, '  2) 45385', '  3) 45385'))))
        # a status, units or a modifier stated only on a detail line is never read as the item's
        moved = changed(sample('customer-report-approved.txt'), '2. 45385 — units 1 — modifiers: XS', '2. 45385 — units 1')
        moved = changed(moved, APPROVER_85, f'{APPROVER_85}\n   modifiers: XS')
        self.assertIn('items.modifiers', failed(txt('approved', moved)))

    def test_the_negative_scan_reads_every_line(self):
        api = operator()
        for line in ('Read by Astra (OpenAI, gpt-6-astra).', f'Request sha256: {api["provider_runs"][0]["request_sha256"]}',
                     'Tokens: 2,100 in, 420 out', 'Rule evidence.exact passed', f'Run {api["provider_runs"][1]["id"]}'):
            with self.subTest(line=line):
                self.assert_fails(lambda t, line=line: changed(t, '\nLimitations', f'\n{line}\n\nLimitations'), ['scan.file'])

    def test_a_passage_that_spans_lines_is_read_whole(self):
        api = operator()
        passage = 'COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps.\nCOL-2: a 9 mm sigmoid colon polyp was removed with a cold snare.'
        start = api['revision']['text'].index(passage)
        api['assessment']['proposals'][0]['evidence'] = [{'context_index': 0, 'start': start, 'end': start + len(passage), 'text': passage, 'exact': True, 'page': 1}]
        text = changed(sample('customer-report-approved.txt'), QUOTE_80,
                       '   Quote: "COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps.\n'
                       '       COL-2: a 9 mm sigmoid colon polyp was removed with a cold snare." '
                       f'(page 1, characters {start}–{start + len(passage)})')
        results = txt('approved', text, api)
        self.assertEqual(failed(results), [])
        quote = vd.parse_customer_txt(text)['items'][0].quotes[0]
        self.assertEqual((quote['text'], quote['start'], quote['end'], quote['page']), (passage, start, start + len(passage), 1))

    def test_a_passage_continued_onto_a_line_the_document_indents_is_read_as_the_writer_prints_it(self):
        # refutation round 3, B-04: reports._join continues a part of a value seven spaces deep unless it already starts
        # seven spaces deep, when it prints it as it is - so the document's own indent of seven or more is printed
        # unchanged, and the check compares the passage printed as the writer prints it (txt_printed); stripping seven
        # spaces read an eight-space line back with one and failed the genuine export
        for indent in (0, 6, 7, 8, 13, 14, 20):
            with self.subTest(indent=indent):
                api = operator()
                pad = ' ' * indent
                text = api['revision']['text'] + f'Findings (fictional):\n{pad}A 4 mm polyp was removed.\n{pad}A 9 mm polyp was removed.\n'
                passage = f'A 4 mm polyp was removed.\n{pad}A 9 mm polyp was removed.'
                start = text.index(passage)
                api['revision'].update(text=text, pages=[{'page': 1, 'start': 0, 'end': len(text)}])
                api['assessment']['proposals'][0]['evidence'] = [{'context_index': 0, 'start': start, 'end': start + len(passage),
                                                                  'text': passage, 'exact': True, 'page': 1}]
                printed = pad if indent >= 7 else '       ' + pad  # as reports._join prints the second part
                self.assertEqual(vd.txt_printed(passage), f'A 4 mm polyp was removed.\n{printed}A 9 mm polyp was removed.')
                where = f'(page 1, characters {start}–{start + len(passage)})'
                report = changed(sample('customer-report-approved.txt'), QUOTE_80,
                                 f'   Quote: "A 4 mm polyp was removed.\n{printed}A 9 mm polyp was removed." {where}')
                self.assertEqual(failed(txt('approved', report, api)), [])
                quote = vd.parse_customer_txt(report)['items'][0].quotes[0]
                self.assertEqual((quote['printed'], quote['start']), (vd.txt_printed(passage), start))
                # the same line one space deeper, or (where it is deeper than seven) one space shallower: not the passage
                # at those offsets (a quotation with offsets is support by its offsets, so only its exactness fails)
                for other in [' ' + printed] + ([printed[1:]] if len(printed) > 7 else []):
                    moved = changed(report, f'\n{printed}A 9 mm', f'\n{other}A 9 mm')
                    self.assertEqual(failed(txt('approved', moved, api)), ['items.evidence.exact'], len(other))

    def test_a_code_not_approved_named_outside_the_items_is_a_warning(self):
        api = operator()
        api['assessment']['proposals'][0]['decision'] = None
        text = sample('customer-report-approved.txt')
        text = text[:text.index('1. 45380')] + '1. 45385' + text[text.index('2. 45385') + len('2. 45385'):]
        text = changed(text, '\nLimitations\n', '\nLimitations\n- Note: 45380 is not approved.\n')
        results = txt('approved', text, api)
        self.assertEqual(statuses(results)['approved.only'], 'warn')
        self.assertEqual(failed(results), [])


class DraftTxtTests(unittest.TestCase):
    def test_the_draft_lists_every_suggested_code_with_its_status_and_only_decided_modifiers(self):
        api = operator()
        api['assessment']['proposals'][1]['decision'] = None  # 45385 undecided: Ready for review, no modifier, no label
        stated(api['assessment']['proposals'][1], 'ready', '', ['approve', 'reject'])
        text = changed(sample('customer-report-draft.txt'), f'2. 45385 — Approved — units 1 — modifiers: XS\n   {LABEL}\n',
                       '2. 45385 — Ready for review — units 1 — modifiers: none\n')
        self.assertEqual(failed(txt('draft', text, api)), [])
        self.assertIn('items.modifiers', failed(txt('draft', changed(text, '45385 — Ready for review — units 1 — modifiers: none',
                                                                      '45385 — Ready for review — units 1 — modifiers: XS'), api)))
        self.assertIn('items.status', failed(txt('draft', changed(text, '45385 — Ready for review', '45385 — Approved'), api)))
        self.assertIn('items.items', failed(txt('draft', text[:text.index('2. 45385')] + text[text.index('\nLimitations'):], api)))
        labelled = changed(text, '2. 45385 — Ready for review — units 1 — modifiers: none\n',
                           f'2. 45385 — Ready for review — units 1 — modifiers: none\n   {LABEL}\n')
        self.assertIn('items.agent_label', failed(txt('draft', labelled, api)))  # an undecided code is no approval

    def test_a_draft_labels_each_agent_approval_and_the_header_says_so(self):
        # refutation round 2, L3-6: the draft says agent review wherever the page does
        self.assertEqual(failed(txt('draft')), [])
        got = failed(txt('draft', changed(sample('customer-report-draft.txt'), f'modifiers: none\n   {LABEL}\n', 'modifiers: none\n')))
        self.assertEqual(got, ['items.agent_label'])
        got = failed(txt('draft', changed(sample('customer-report-draft.txt'), f'NOT APPROVED\n{LABEL}\n', 'NOT APPROVED\n')))
        self.assertEqual(got, ['header.agent_label'])

    def test_a_draft_never_reads_as_the_approved_export(self):
        text = sample('customer-report-draft.txt')
        self.assertIn('headline', failed(txt('draft', changed(text, 'CPT STUDIO — SUGGESTED CODES — NOT APPROVED', 'CPT STUDIO — APPROVED CODES'))))
        self.assertIn('codes.section', failed(txt('draft', changed(text, '\nSuggested codes — not approved\n', '\nApproved codes\n'))))
        self.assertIn('items.evidence.support', failed(txt('draft', changed(text, 'Quote: "COL-1: a 4 mm', 'Quote: "COL-1: a 5 mm'))))

    def test_an_excluded_code_quotes_nothing(self):
        api = operator()
        p = proposal(api, '45385')
        p['decision'].update(action='reject', modifiers=[])
        stated(p, 'excluded', 'Rejected in review', ['revoke'])
        text = changed(sample('customer-report-draft.txt'), f'2. 45385 — Approved — units 1 — modifiers: XS\n   {LABEL}\n',
                       '2. 45385 — Excluded — units 1 — modifiers: none\n   Rejected in review\n')
        self.assertEqual(failed(txt('draft', text, api)), ['items.evidence.support'])  # its quotation stands
        quote = '   Quote: "COL-2: a 9 mm sigmoid colon polyp was removed with a cold snare." (page 1)\n'
        self.assertEqual(failed(txt('draft', changed(text, quote, ''), api)), [])


class ServerStatementTests(unittest.TestCase):
    """Refutation round 3, B-02: a draft's statuses are the server's statement of the customer page - the operator view's
    'customer' on each code (serializers.customer_codes: customer_api.code_rows' rows) - never re-derived from the
    overlay's facts; a view that states none cannot verify them."""

    def answered(self):
        """45385 as a reinstated code whose needed detail a member answered "Not documented": the server shows it Excluded,
        "A needed detail is not documented", and accepts revoke only - beside facts (an exclusion, a reinstate decision,
        nothing withholding approve) a re-derivation read as Ready for review - and its genuine draft, TXT and CSV."""
        api = operator()
        p = proposal(api, '45385')
        p.update(bucket='excluded', status='excluded', reinstatable=True, overlay_reason='detail_unavailable', approve_withheld_by=None)
        p['decision'].update(action='reinstate', modifiers=[], note='Synthetic reinstatement.')
        stated(p, 'excluded', 'A needed detail is not documented', ['revoke'])
        report = changed(sample('customer-report-draft.txt'), f'2. 45385 — Approved — units 1 — modifiers: XS\n   {LABEL}\n',
                         '2. 45385 — Excluded — units 1 — modifiers: none\n   A needed detail is not documented\n')
        report = changed(report, '   Quote: "COL-2: a 9 mm sigmoid colon polyp was removed with a cold snare." (page 1)\n', '')
        table = changed(sample('customer-report-draft.csv'), '"2","45385","1","XS","approved"', '"2","45385","1","","excluded"')
        table = changed(table, f'"COL-2: a 9 mm sigmoid colon polyp was removed with a cold snare.","1","330","394","{LABEL}"', '"","","","",""')
        return api, report, table

    def test_the_server_s_status_is_the_one_a_draft_is_held_to(self):
        api, report, table = self.answered()
        self.assertEqual([t['status'] for t in vd.customer_truth(api, 'draft')], ['approved', 'excluded'])
        self.assertEqual(failed(txt('draft', report, api)), [])
        self.assertEqual(failed(csv('draft', table, api)), [])
        forged = changed(changed(report, '45385 — Excluded —', '45385 — Ready for review —'),
                         '   A needed detail is not documented\n', '   Reinstated in review\n')
        self.assertEqual(failed(txt('draft', forged, api)), ['items.status'])
        self.assertEqual(failed(csv('draft', changed(table, '"2","45385","1","","excluded"', '"2","45385","1","","ready"'), api)),
                         ['csv.items.status'])
        detail = next(r.detail for r in txt('draft', forged, api) if r.check == 'items.status')
        self.assertEqual(detail, '45385 Ready for review (expected Excluded)')

    def test_a_view_that_states_no_status_cannot_verify_a_draft(self):
        bare = operator()
        for p in bare['assessment']['proposals']:
            p.pop('customer', None)
        self.assertEqual([t['status'] for t in vd.customer_truth(bare, 'draft')], [vd.UNKNOWN, vd.UNKNOWN])
        for kind, fmt, results, check in (('draft', 'txt', txt('draft', api=bare), 'items.status'),
                                          ('draft', 'csv', csv('draft', api=bare), 'csv.items.status')):
            with self.subTest(fmt=fmt):
                self.assertEqual((failed(results), statuses(results)[check]), ([], 'incomplete'))
                self.assertIn('cannot verify', next(r.detail for r in results if r.check == check))
                self.assertEqual(vd.exit_status(results), 2)
        # a draft that misstates a status still cannot pass against such a view: it cannot be verified either way
        wrong = changed(sample('customer-report-draft.txt'), '45385 — Approved —', '45385 — Ready for review —')
        self.assertEqual(statuses(txt('draft', wrong, bare))['items.status'], 'incomplete')
        # the approved export lists approvals only, which the persisted decisions name: no status is read there
        for results in (txt('approved', api=bare), csv('approved', api=bare)):
            self.assertEqual([(r.check, r.status) for r in results if r.status != 'pass'], [])

    def test_the_status_is_read_from_the_statement_alone(self):
        row = {'number': 1, 'status': 'needs_detail', 'status_label': 'Needs a detail', 'sub_label': 'Reinstated in review',
               'reviewer_actions': ['reject', 'revoke']}
        facts = {'bucket': 'excluded', 'status': 'needs_clarification', 'decision': {'action': 'reinstate'}}
        self.assertEqual(vd.customer_status({**facts, 'customer': row}), 'needs_detail')
        for customer in (None, {}, 'needs_detail', {**row, 'status': 'Needs a detail'}, {**row, 'status': 'needs_clarification'},
                         {**row, 'status': None}):
            with self.subTest(customer=customer):
                self.assertIs(vd.customer_status({**facts, 'customer': customer}), vd.UNKNOWN)
        self.assertIs(vd.customer_status(facts), vd.UNKNOWN)


class CsvTests(unittest.TestCase):
    def test_columns_format_constants_and_neutralised_cells(self):
        text = sample('customer-report-approved.csv')
        self.assertIn('csv.columns', failed(csv('approved', changed(text, '"evidence_start"', '"evidence_begin"'))))
        self.assertIn('csv.columns', failed(csv('approved', changed(text, ',"review_label"', ''))))
        self.assertIn('format', failed(csv('approved', changed(text, '"cpt-studio-customer-report@1","Synthetic', '"cpt-studio-report@4","Synthetic', 2))))
        self.assertIn('csv.constants', failed(csv('approved', changed(text, '"2026-11-03","1","45380"', '"2026-11-02","1","45380"'))))
        self.assertIn('csv.neutralised', failed(csv('approved', changed(text, '"The colonoscopy documents removal of the 4 mm',
                                                                          '"=1+1 The colonoscopy documents removal of the 4 mm'))))
        self.assertEqual(statuses(csv('approved', text.replace(BANNER_ROW + '\r\n', '')))['csv.synthetic_marker'], 'fail')
        self.assertEqual(statuses(csv('approved', changed(text, BANNER_ROW + '\r\n', '', 2)))['csv.synthetic_marker'], 'fail')
        # a SYNTHETIC line before the header row is not this renderer's file: its columns are not the header
        self.assertIn('csv.columns', failed(csv('approved', 'SYNTHETIC DATA — NOT FOR BILLING OR CLAIMS\r\n' + text)))

    def test_the_rows_are_the_approved_items_with_their_units_modifiers_approver_and_evidence(self):
        text = sample('customer-report-approved.csv')
        rows = text.split('\r\n')
        self.assertTrue(rows[2].startswith('"cpt-studio-customer-report@1"') and '"45380"' in rows[2])
        extra = rows[2].replace('"1","45380",', '"3","45378",')
        self.assertIn('csv.items.items', failed(csv('approved', changed(text, rows[2], rows[2] + '\r\n' + extra))))
        self.assertIn('csv.items.units', failed(csv('approved', changed(text, '"1","45380","1",', '"1","45380","2",'))))
        self.assertIn('csv.items.modifiers', failed(csv('approved', changed(text, '"2","45385","1","XS",', '"2","45385","1","59;XS",'))))
        self.assertIn('csv.items.approver', failed(csv('approved', changed(text, '"agent","2026-11-03T22:05:00+00:00"', '"human","2026-11-03T22:05:00+00:00"'))))
        self.assertIn('csv.items.evidence.exact', failed(csv('approved', changed(text, '"1","256","329"', '"1","256","330"'))))
        self.assertIn('csv.groups', failed(csv('approved', changed(text, rows[2], rows[2] + '\r\n' + rows[2].replace('"1","45380","1",', '"1","45380","2",')))))
        self.assertIn('csv.items.quoted', failed(csv('approved', changed(
            text, '"COL-1: a 4 mm ascending colon polyp was removed with cold biopsy forceps.","1","256","329"', '"","","",""'))))

    def test_each_row_of_an_approval_agent_review_took_part_in_carries_the_label_with_the_approver_s_own_kind(self):
        # refutation round 2, L3-6: no CSV carried the label, and a human's approval of an agent's reinstatement read
        # approver_kind 'human' with no agent label anywhere
        for kind in ('approved', 'draft'):
            text = sample(f'customer-report-{kind}.csv')
            self.assertIn('csv.items.agent_label', failed(csv(kind, changed(text, f'"{LABEL}"', '""', 2))))
            self.assertIn('csv.items.agent_label', failed(csv(kind, changed(text, f'"{LABEL}"', '"Rejected in review"', 2))))
        # a person's approval carries no agent label, even of a code an agent reinstated (customer_api.agent_approval)
        api = reinstated_by_agent_approved_by_human(operator())
        text = changed(sample('customer-report-approved.csv'), f'"{AGENT}","agent","2026-11-03T22:05:30+00:00"',
                       f'"{HUMAN}","human","2026-11-03T22:05:30+00:00"')
        unlabelled = text.replace(f'"{LABEL}"\r\n"SYNTHETIC', '""\r\n"SYNTHETIC')
        self.assertNotEqual(unlabelled, text)
        self.assertEqual(failed(csv('approved', unlabelled, api)), [])
        self.assertIn('csv.items.agent_label', failed(csv('approved', text, api)))
        self.assertIn('csv.items.approver', failed(csv('approved', changed(unlabelled, f'"{HUMAN}","human"', f'"{HUMAN}","agent"'), api)))

    def test_a_modifier_the_operator_view_does_not_record_is_never_read_as_none(self):
        text = sample('customer-report-approved.csv')
        dropped = changed(text, '"2","45385","1","XS",', '"2","45385","1","",')
        for body in (text, dropped):
            results = csv('approved', body, without_modifiers(operator()))
            self.assertEqual((statuses(results)['csv.items.modifiers'], failed(results)), ('incomplete', []))
        self.assertIn('csv.items.modifiers', failed(csv('approved', dropped)))

    def test_a_draft_has_no_approval_cell_and_statuses_as_the_view_implies(self):
        text = sample('customer-report-draft.csv')
        self.assertEqual(failed(csv('draft', text)), [])
        self.assertIn('csv.approval_cells', failed(csv('draft', changed(text, '"approved","","",""', f'"approved","{AGENT}","agent","2026-11-03T22:05:00+00:00"', 2))))
        self.assertIn('csv.items.status', failed(csv('draft', changed(text, '"1","45380","1","","approved"', '"1","45380","1","","needs_detail"'))))
        self.assertEqual(failed(csv('draft', text.replace('"approved","","",""', '"Approved","","",""'))), [], 'a status label reads as its key')


class DownloadTests(unittest.TestCase):
    def download(self, kind, fmt, data: bytes, **extra) -> dict:
        digest = hashlib.sha256(data).hexdigest()
        return {'kind': kind, 'fmt': fmt, 'audience': 'customer', 'path': f'cux/{kind}-{fmt}.{fmt}', 'size': len(data),
                'report_id': f'r-{kind}-{fmt}', 'sha256': digest, 'refetch_sha256': digest, 'header_sha256': None,
                'operator_sha256': digest, 'operator_audience': 'customer', 'operator_download_sha256': digest,
                'operator_header_sha256': digest, **extra}

    def test_the_bytes_are_the_customer_re_fetch_s_and_the_operator_s_and_carry_no_hash_header(self):
        data = sample('customer-report-approved.txt').encode('utf-8')
        ok = self.download('approved', 'txt', data)
        self.assertEqual(failed(vd.check_customer_hashes('d', 'approved.txt', data, ok)), [])
        for change, check in (({'header_sha256': 'a' * 64}, 'header.no_hash'), ({'operator_sha256': None}, 'sha256.operator_sha256'),
                              ({'refetch_sha256': 'b' * 64}, 'sha256.refetch_sha256'), ({'operator_audience': 'operator'}, 'audience'),
                              ({'operator_download_sha256': 'c' * 64}, 'sha256.operator_download_sha256'), ({'size': 3}, 'size')):
            with self.subTest(change=change):
                self.assertIn(check, failed(vd.check_customer_hashes('d', 'approved.txt', data, {**ok, **change})))

    def write_evidence(self, root: Path, snapshots: dict, downloads=None) -> Path:
        (root / 'cux').mkdir()
        for name in ('operator-encounter.json', 'operator-trace.json', 'customer-encounter.json'):
            (root / 'cux' / name).write_text(sample(name), encoding='utf-8')
        records = []
        for kind in ('draft', 'approved'):
            for fmt in ('txt', 'csv'):
                data = sample(f'customer-report-{kind}.{fmt}').encode('utf-8')
                (root / 'cux' / f'{kind}-{fmt}.{fmt}').write_bytes(data)
                records.append(self.download(kind, fmt, data))
        doc = {'id': 'cux-01', 'encounter_id': operator()['id'], 'decisions': [], 'downloads': records if downloads is None else downloads, **snapshots}
        evidence = {'schema': 'cpt-studio-browser-evidence@2', 'session': {'user': {'label': AGENT}}, 'documents': [doc]}
        path = root / 'evidence.json'
        path.write_text(json.dumps(evidence), encoding='utf-8')
        return path

    def test_main_checks_every_customer_download_against_the_operator_snapshot_the_evidence_names(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = self.write_evidence(root, {'operator_snapshots': {'final': 'cux/operator-encounter.json', 'trace': 'cux/operator-trace.json'},
                                                  'customer_snapshots': {'final': 'cux/customer-encounter.json'}})
            out = io.StringIO()
            with redirect_stdout(out):
                code = vd.main(['--evidence', str(evidence), '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text())
            self.assertEqual([r for r in results if r['status'] != 'pass'], [])
            self.assertEqual(code, 0, out.getvalue()[-2000:])
            snapshot = next(r for r in results if r['check'] == 'api.snapshot')
            self.assertTrue(snapshot['detail'].endswith('cux/operator-encounter.json'))
            self.assertEqual(len({(r['report'], r['check']) for r in results if r['check'] == 'scan.file'}), 4)

    def test_main_exits_2_when_the_operator_view_does_not_record_the_modifiers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = self.write_evidence(root, {'operator_snapshots': {'final': 'cux/operator-encounter.json'}})
            (root / 'cux' / 'operator-encounter.json').write_text(json.dumps(without_modifiers(operator())), encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                code = vd.main(['--evidence', str(evidence), '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text())
            self.assertEqual(code, 2)
            self.assertEqual(sorted({(r['report'], r['check']) for r in results if r['status'] != 'pass'}),
                             sorted({(f'{kind}.{fmt}', f'{"items" if fmt == "txt" else "csv.items"}.modifiers')
                                     for kind in ('draft', 'approved') for fmt in ('txt', 'csv')}))

    def test_the_customer_snapshot_is_never_the_source_of_truth_and_api_dir_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            evidence = self.write_evidence(root, {'customer_snapshots': {'final': 'cux/customer-encounter.json'}})
            out = io.StringIO()
            with redirect_stdout(out):
                code = vd.main(['--evidence', str(evidence), '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text())
            self.assertEqual(code, 2, 'no operator view: the content checks could not run')
            self.assertEqual(next(r['status'] for r in results if r['check'] == 'api.snapshot'), 'incomplete')
            self.assertTrue(all(r['status'] == 'incomplete' for r in results if r['check'] == 'content.vs.operator'))
            api_dir = root / 'api'
            api_dir.mkdir()
            (api_dir / f'{operator()["id"]}.json').write_text(sample('operator-encounter.json'), encoding='utf-8')
            (root / 'downloads.json').unlink()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(vd.main(['--evidence', str(evidence), '--api-dir', str(api_dir), '--json-out', str(root / 'downloads.json')]), 0)

    def test_a_customer_report_recorded_as_an_operator_download_or_of_an_unknown_kind_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = sample('customer-report-approved.txt').encode('utf-8')
            records = [{**self.download('approved', 'txt', data), 'audience': None}, {**self.download('reviewed', 'txt', data)}]
            evidence = self.write_evidence(root, {'operator_snapshots': {'final': 'cux/operator-encounter.json'}}, downloads=records)
            for record, name in zip(records, ('approved-txt.txt', 'approved-txt.txt')):
                record['path'] = f'cux/{name}'
            payload = json.loads(evidence.read_text())
            payload['documents'][0]['downloads'] = records
            evidence.write_text(json.dumps(payload))
            with redirect_stdout(io.StringIO()):
                vd.main(['--evidence', str(evidence), '--json-out', str(root / 'downloads.json')])
            results = json.loads((root / 'downloads.json').read_text())
            fails = {(r['report'], r['check']) for r in results if r['status'] == 'fail'}
            self.assertIn(('approved.txt', 'audience.recorded'), fails)
            self.assertIn(('reviewed.txt', 'format'), fails)


if __name__ == '__main__':
    unittest.main()
