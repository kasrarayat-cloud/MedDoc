"""Refutation round 2, R2-WORDING (HARNESS.md 7, 11.1, 11.4, I9): how the page and the reports name proposers, phases
and participant text, so that every sentence is true of the record.

Each class reproduces one finding of the round (refute-harness-r2/findings.json, verified in
verify-harness-r2/results.json) through the real pipeline - the real jobs, engine, readers, tool executor and tool loop,
the vendors' HTTP replaced by scripted bytes in their own envelopes (tests.test_harness2_pipeline) - the real API, and
the real app.js run by node, and asserts the wording that is true of the record beside a control that must not change.
Synthetic data only; nothing is sent.
"""
import dataclasses
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import override_settings

from studio import jobs
from studio.validation import engine
from tests import test_harness2_api as h2
from tests import test_harness2_pipeline as hp
from tests.legacy_chain import applied
from tests.test_harness2_pipeline import BIOPSY, SNARE, TWO_EXTENTS
from tests.test_pipeline_api import drain

APP = Path(settings.BASE_DIR) / 'studio' / 'operator' / 'ops.js'
# What node evaluates an expression over: app.js's exports, the payload, and the page's visible text and parts.
PRELUDE = r"""
const app = require(process.argv[1]);
const data = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const BREAKS = new RegExp('<(br|/p|/li|/div|/h[1-6]|/summary|/small|/strong|/article|/section|/ul|/details|/dd|/dt)'
  + '\\b[^>]*>', 'gi');
const visible = html => html.replace(BREAKS, '\n').replace(/<[^>]+>/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&#x60;/g, '`').replace(/&amp;/g, '&').split('\n')
  .map(line => line.replace(/\s+/g, ' ').trim()).filter(Boolean).join('\n');
const page = (tab = 'codes') => app.reviewView(data, app.documentLayout(data), tab, true);
const cards = html => [...html.matchAll(/<article class="code-card"[\s\S]*?<\/article>/g)].map(match => match[0]);
const cardOf = (html, id) => cards(html).find(card => card.includes(`id="card-${id}"`)) || '';
const statusLine = (card, name) => {
  const line = new RegExp(`<li><b>${name}:</b> ([^<]*)</li>`).exec(card);
  return line ? visible(line[1]) : null;
};
const rowOf = (html, attribute, key) => {
  const start = html.indexOf(`${attribute}="${key}"`);
  if (start < 0) return '';
  const from = html.lastIndexOf('<div class="check-item', start);
  const next = html.indexOf('<div class="check-item', start);
  return visible(html.slice(from, next > 0 ? next : html.length));
};
"""


def browser(expression, data):
    """The value of a JavaScript ``expression`` over PRELUDE's names, as the page computes it from ``data``: node runs
    app.js itself, so a screen is checked as it renders. The payload goes on standard input (an argument is bounded
    in size)."""
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the screen checks need it')
    script = f'{PRELUDE}\nprocess.stdout.write(JSON.stringify({expression}));'
    done = subprocess.run([node, '-e', script, str(APP)], input=json.dumps(data), capture_output=True, text=True,
                          timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return json.loads(done.stdout)


class R2WordingCase(hp.ColonCase):
    """The colonoscopy chain of tests.test_harness2_pipeline.ColonCase: Corti selects 45385 and 45380, Astra's first
    reading proposes both, Fable's 45385; Astra's peer review answers the extent and Fable's adds 45378 after peer
    review; both codes are held on the extent."""

    def detail(self, encounter_id):
        response = self.client.get(f'/ops/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def proposals(self, detail, code, **fields):
        return [p for p in detail['assessment']['proposals']
                if p['code'] == code and all(p.get(key) == value for key, value in fields.items())]

    def origin(self, proposal):
        return (proposal['support'] or {}).get('origin') or 'primary'

    def corti_answer(self, edit):
        """Corti's scripted answer, rewritten by ``edit`` (its parsed JSON body and the request's text) before it is
        stored and read, exactly as a vendor could have sent it."""
        real = self.corti.send

        def send(request, *, deadline_s):
            exchange = real(request, deadline_s=deadline_s)
            answer = json.loads(exchange.response_bytes)
            edit(answer, request.contexts[0])
            data = json.dumps(answer).encode()
            return dataclasses.replace(exchange, response_bytes=data, response_sha256=hashlib.sha256(data).hexdigest())
        return mock.patch.object(self.corti, 'send', side_effect=send)


# --- truth-6: "Corti did not propose this code" only when Corti has no entry for it ----------------------------------

@applied
class CortiRelationTests(R2WordingCase):
    """truth-6 (HARNESS.md 11.4): a participant's own proposal's card read "Corti did not propose this code" whenever
    Corti was not among its proposers - also beside Corti's own excluded selection of the code, which the card's own
    rationale and the Excluded candidates list named. The API serves Corti's relation to the code (corti_relation) and
    the page words it as the engine's rationale does; "did not propose" is said only when Corti has no entry at all.
    Moved by refutation round 6 (R6-MEANING, the session's D14) to alternatives with no card; restored by HARNESS.md
    P-ADMIT (owner directive 2026-11-05) for a code a participant's first reading proposes and CPT Studio's readers
    admit - it is a card again, worded as before D14 - while a code given only in peer review is still listed, with
    P-ADMIT's reason, which says nothing of Corti; the API serves the relation either way."""

    def proposer_line(self, detail, proposal):
        return browser(f'statusLine(cardOf(page(), {json.dumps(proposal["id"])}), "Proposed by")', detail)

    def assert_listed(self, detail, proposal):
        """``proposal`` is the participants' alternative: no card, nothing to decide, and a reason that says nothing
        of Corti; no card on the page says Corti did not propose a code."""
        from tests.test_harness2_r6_meaning import not_added_reason
        self.assertEqual((proposal['bucket'], proposal['status'], proposal['allowed_actions']),
                         ('alternative', 'informational', []))
        self.assertTrue(not_added_reason(proposal['exclusion_reason']), proposal['exclusion_reason'])
        self.assertNotIn('Corti', proposal['exclusion_reason'])
        page = browser('page()', detail)
        self.assertNotIn(f'id="card-{proposal["id"]}"', page)
        self.assertNotIn('Corti did not propose this code', page)

    def test_a_code_corti_selected_with_no_exact_passage_is_never_called_unproposed_by_corti(self):
        def inexact(answer, _text):
            for item in answer['codes']:
                if item['code'] == '45385':
                    item['evidences'] = [{'contextIndex': 0, 'start': 0, 'end': 9, 'text': 'Not text.'}]
        with self.corti_answer(inexact):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        detail = self.detail(encounter_id)
        # HARNESS.md P-ADMIT (2026-11-05): the participants' first-reading 45385 is admitted, a selected card worded
        # "Corti also selected this code, with no exact passage; ..." as before D14 (which listed it)
        [own] = self.proposals(detail, '45385', bucket='selected')
        [corti] = self.proposals(detail, '45385', bucket='excluded')
        self.assertEqual((self.origin(own), own['proposed_by'], corti['exclusion_reason']),
                         ('participant', ['astra', 'fable'], 'No exact source evidence'))
        self.assertEqual(self.proposer_line(detail, own),
                         'Astra (independent reading), Fable (independent reading); Corti also selected this code, '
                         'with no exact passage; it is listed apart, excluded.')
        self.assertEqual((own['corti_relation'], corti['corti_relation']),
                         ('selected_without_exact_passage', 'proposer'))
        # control: Fable's code given only after peer review, which Corti never named: never admitted, so listed, its
        # relation 'none' (before D14 it was a card worded "Fable (after peer review); Corti did not propose this code.")
        [added] = self.proposals(detail, '45378')
        self.assertEqual(added['corti_relation'], 'none')
        self.assert_listed(detail, added)

    def test_a_code_corti_listed_only_as_a_candidate_says_so(self):
        self.corti.selections = [('45385', SNARE)]

        def candidate(answer, text):
            start = text.index(BIOPSY)
            answer['candidates'] = [{'system': 'cpt', 'code': '45380', 'display': hp.CORTI_DISPLAY,
                                     'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(BIOPSY),
                                                    'text': BIOPSY}], 'alternatives': []}]
        with self.corti_answer(candidate):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        detail = self.detail(encounter_id)
        # HARNESS.md P-ADMIT (2026-11-05): Astra's first-reading 45380 is admitted beside Corti's candidate, a selected
        # card worded as before D14 (which listed it); the engine's record names no role a code was listed in, so the
        # sentence is true of a candidate and of an alternative (refutation round 3, R3-TRUTH truth-5)
        [own] = self.proposals(detail, '45380', bucket='selected')
        [listed] = self.proposals(detail, '45380', bucket='alternative')
        self.assertEqual((self.origin(own), self.origin(listed)), ('participant', 'primary'))
        self.assertEqual(self.proposer_line(detail, own), 'Astra (independent reading); Corti listed this code as a '
                                                          'candidate or an alternative, not selected; see '
                                                          'Alternatives.')
        self.assertEqual((own['corti_relation'], listed['corti_relation']), ('candidate', 'proposer'))

    def test_every_proposal_carries_the_relation_and_corti_s_own_are_corti_s(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        relations = {(p['key'], p['code']): p['corti_relation'] for p in detail['assessment']['proposals']}
        # moved by refutation round 6 (R6-MEANING, the session's D14): Fable's peer-review 45378 is its alternative (it
        # was sel:2)
        self.assertEqual(relations, {('sel:0', '45385'): 'proposer', ('sel:1', '45380'): 'proposer',
                                     ('altp:0', '45378'): 'none'})
        line = self.proposer_line(detail, next(p for p in detail['assessment']['proposals'] if p['code'] == '45385'))
        self.assertEqual(line, 'Corti, Astra (independent reading), Fable (independent reading)')

    def test_a_payload_that_serves_no_relation_says_nothing_of_corti(self):
        # a proposal served without corti_relation (before it existed): who proposed it, and nothing about Corti that
        # the record would have to support
        lines = browser("['', 'none', 'unheard-of'].map(relation => visible(app.codeStatusLines({ "
                        "proposed_by: ['fable'], reference_check: { state: 'passed' }, "
                        "...(relation ? { corti_relation: relation } : {}) })))", {})
        self.assertEqual([text.split('\n')[0] for text in lines],
                         ['Proposed by: Fable', 'Proposed by: Fable; Corti did not propose this code.',
                          'Proposed by: Fable'])


# --- truth-11: a participant row never says "It proposed no code" beside the codes it cannot list ---------------------

@applied
class UnlistedCodesTests(R2WordingCase):
    """truth-11 (HARNESS.md 7; the round-1 IND-1 repair's count sentence): a participant whose reading proposed only a
    code the engine cannot list read "It returned 1 code that cannot be listed ..." and then "It proposed no code." The
    row serves the count (unlisted_codes), and the page says what can be listed, never that it proposed nothing."""

    LONG = '45385-SYNTHETIC-LONG-VALUE'

    def fable_reads(self, *codes):
        self.adapters['fable'].first = [hp.answered('fable', hp.reading(
            codes=[(value, SNARE) for value in codes], services=[('c1', 'colonoscopy', 'performed', SNARE)]))]
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        return self.detail(encounter_id)

    def row_text(self, detail, name):
        return browser(f'rowOf(page(), "data-participant", {json.dumps(name)})', detail)

    def test_a_reading_that_proposed_only_a_code_it_cannot_list(self):
        detail = self.fable_reads(self.LONG)
        rows = {row['name']: row for row in detail['harness']['participants']}
        text = self.row_text(detail, 'fable')
        self.assertIn('It returned 1 code that cannot be listed', text)
        self.assertIn('It proposed no code that can be listed.', text)
        self.assertNotIn('It proposed no code.', text)
        self.assertNotIn(self.LONG, json.dumps(detail['harness']))  # never served (I9)
        self.assertEqual((rows['fable']['codes'], rows['fable']['unlisted_codes']), ([], 1))
        # control: a row whose every code can be listed reads as before
        self.assertEqual((rows['astra']['codes'], rows['astra']['unlisted_codes']), (['45385', '45380'], 0))
        self.assertIn('Codes it proposed: 45385, 45380.', self.row_text(detail, 'astra'))
        self.assertEqual(rows['corti']['unlisted_codes'], 0)

    def test_a_reading_with_codes_it_can_and_cannot_list_says_which_are_listed(self):
        detail = self.fable_reads('45385', self.LONG)
        text = self.row_text(detail, 'fable')
        self.assertIn('Codes it proposed that can be listed: 45385.', text)
        self.assertNotIn('Codes it proposed: 45385.', text)
        fable = next(row for row in detail['harness']['participants'] if row['name'] == 'fable')
        self.assertEqual((fable['codes'], fable['unlisted_codes']), (['45385'], 1))


# --- truth-9: a phase-1 final assessment's peer rows say why it read no peer review ----------------------------------

# Why a final assessment of phase 1 read no peer review, as the row says it (the reports' PEER REVIEW says the same).
HELD = ('Peer review: none is read by this assessment: the service date entered as encounter metadata conflicts with '
        'the document, and no peer review is sent while that question is open.')
NOT_RECORDED = 'No peer review is recorded for this revision'


@applied
class PhaseOneFinalTests(R2WordingCase):
    """truth-9 (HARNESS.md 7: each row says plainly whether its step ran): after phase 2, a member date conflict made
    a new assess #1 the final assessment with no peer entries. Both peer rows read "Not run - No peer review is recorded
    for this revision. Its peer-review stage: Done." and the final row "no peer review is recorded for this revision",
    while the same payload's provider runs listed both peer reviews as succeeded. The API now serves each row's peer
    state for such an assessment with why, and the page's own sentence says what is true: this assessment read none."""

    def test_a_member_date_conflict_after_phase_two(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        changed = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-20'})
        self.assertEqual(changed.status_code, 201, changed.content)
        drain()
        detail = self.detail(encounter_id)
        self.assertEqual((detail['harness']['phase'], detail['pipeline']['busy']), (1, False))
        self.assertEqual(sorted((run['provider'], run['state']) for run in detail['provider_runs']
                                if run['purpose'] == 'peer_review'), [('astra', 'succeeded'), ('fable', 'succeeded')])
        rows = browser('["astra", "fable"].map(name => rowOf(page(), "data-peer", name)).concat([rowOf(page(), '
                       '"data-participant", "final")])', detail)
        for row in rows:
            self.assertNotIn(NOT_RECORDED.lower(), row.lower())
        for row in rows[:2]:
            self.assertIn(HELD, row)
        self.assertIn('Assessed from the frozen first readings; no peer review was read by this assessment.', rows[2])
        served = {row['name']: row['peer'] for row in detail['harness']['participants']}
        for name in ('astra', 'fable'):
            self.assertEqual(served[name], {'state': 'not_sent', 'detail': HELD, 'run_id': None, 'codes_added': [],
                                            'unverified_quotes': 0}, name)
        self.assertEqual(served['corti'], {})


@override_settings(**h2.BOTH)
class PhaseOneFinalRowsTests(h2.Harness2Case):
    """truth-9's other cause: an assess #1 whose participants are no longer configured owes no peer stage, so it is the
    final assessment; its rows say why no peer review follows it. While its peer stages are owed it serves none, as
    before (the page then says only that this assessment read none)."""

    def peer(self):
        response = self.client_for(self.reviewer).get(f'/ops/api/encounters/{self.encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return {row['name']: row['peer'] for row in response.json()['harness']['participants']}, response.json()

    def test_no_participant_configured_now(self):
        self.persist([self.entry(name) for name in h2.ADAPTERS])  # an assess #1 that read both first readings
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'):
            served, detail = self.peer()
            self.assertTrue(jobs.owed_peer_stages(self.encounter.assessments.latest('created_at')) == [])
        self.assertEqual(detail['harness']['phase'], 1)
        for name, label in (('astra', 'Astra'), ('fable', 'Fable')):
            self.assertEqual(served[name], {'state': 'not_sent', 'run_id': None, 'codes_added': [],
                                            'unverified_quotes': 0,
                                            'detail': f'Peer review: none follows this assessment: {label} is not '
                                                      'configured on this installation now.'}, name)
        rows = browser('["astra", "fable"].map(name => rowOf(page(), "data-peer", name))', detail)
        self.assertIn('Peer review: none follows this assessment: Astra is not configured on this installation now.',
                      rows[0])

    def test_an_assess_one_whose_peer_stages_are_owed_serves_none(self):
        self.persist([self.entry(name) for name in h2.ADAPTERS])
        served, detail = self.peer()
        self.assertEqual((served['astra'], served['fable']), ({}, {}))
        rows = browser('["astra", "fable"].map(name => rowOf(page(), "data-peer", name))', detail)
        for row in rows:
            self.assertIn('No peer review was read by this assessment.', row)
            self.assertNotIn(NOT_RECORDED, row)


# --- truth-8: "proposed after peer review, never independent" only for a code first proposed there --------------------

REPEATED = 'It listed 45385 again in peer review; it first proposed it in its independent reading.'


@applied
class PeerRepeatedCodeTests(R2WordingCase):
    """truth-8 (HARNESS.md 11.1): Astra's peer review listed 45385 again - its own frozen first reading's code, located
    with the same quote - and the peer row read "Codes it proposed after peer review, never independent: 45385." beside
    the 45385 card's "Astra (independent reading)", while the engine recorded 45385's phase for Astra as independent.
    The TXT and the CSV said the same. A peer review's additional code is now called first proposed after peer review
    only where the engine records it so (serializers.peer_code_phases); a repeated one is said to be repeated."""

    def setUp(self):
        super().setUp()
        self.adapters['astra'].peer = [hp.answered('astra', hp.peer_answer(codes=[('45385', SNARE)]), number=2)]
        self.encounter_id = self.create(TWO_EXTENTS)
        drain()

    def test_the_peer_row_never_calls_a_repeated_code_never_independent(self):
        detail = self.detail(self.encounter_id)
        rows = browser('["astra", "fable"].map(name => rowOf(page(), "data-peer", name))', detail)
        self.assertNotIn('never independent: 45385', rows[0])
        self.assertIn(REPEATED, rows[0])
        self.assertIn('It first proposed no code in peer review that can be listed.', rows[0])
        # control: Fable's 45378, first proposed in its peer review, keeps the label
        self.assertIn('Codes it proposed after peer review, never independent: 45378.', rows[1])
        served = {row['name']: row['peer'] for row in detail['harness']['participants']}
        self.assertEqual((served['astra']['codes_added'], served['fable']['codes_added']), ([], ['45378']))
        self.assertTrue(served['astra']['detail'].endswith(REPEATED), served['astra']['detail'])
        [snare] = self.proposals(detail, '45385')
        self.assertEqual(snare['phases']['astra'], 'independent')  # the engine's record the row now follows

    def test_the_phase_of_each_additional_code_is_the_engine_s_record(self):
        from studio import review, serializers
        from studio.types import ParticipantCode

        assessment = self.encounter(self.encounter_id).current_assessment
        records = self.records(assessment)
        reviews = {name: review.recorded_peer_review(assessment, records[name]) for name in ('astra', 'fable')}
        # recorded by the engine: Astra's repeated 45385 (independent) and Fable's 45378 (after peer review) - moved by
        # refutation round 5 (R5-ACCOUNT, the session's D12): read from the review itself and its record, the located
        # entries alone, where the call named the assessment and the codes
        self.assertEqual(serializers.peer_code_phases(reviews['astra'], records['astra']), {'45385': 'independent'})
        self.assertEqual(serializers.peer_code_phases(reviews['fable'], records['fable']), {'45378': 'peer_review'})
        self.assertEqual(self.proposals(self.detail(self.encounter_id), '45385')[0]['phases']['astra'], 'independent')
        # a code no proposal records the participant on: its located entries decide, as the engine reads them - its
        # first reading's located quote, else its peer review's; a code no entry of either located is '' (listed in peer
        # review: the record's unlocated listing of 45399 made it 'independent', and 45398's unlocated entry
        # 'peer_review')
        located = reviews['astra'].additional_codes[0]
        listed = {**records['astra'], 'codes': [*records['astra']['codes'], {'code': '45399', 'quote': ''},
                                                {'code': '45397', 'quote': SNARE}]}
        # a code the review lists twice, one entry located and one not, in both orders (refutation round 6,
        # falsegreen-1: only 45396's order, unlocated then located, was pinned, so a rule letting the last entry of a
        # code decide passed; 45395 is the other order)
        more = dataclasses.replace(reviews['astra'], additional_codes=(
            located, ParticipantCode('45399'), ParticipantCode('45398'), ParticipantCode('45397'),
            ParticipantCode('45396'), dataclasses.replace(located, code='45396'),
            dataclasses.replace(located, code='45395'), ParticipantCode('45395')))
        self.assertEqual(serializers.peer_code_phases(more, listed), {
            '45385': 'independent', '45399': '', '45398': '', '45397': 'independent', '45396': 'peer_review',
            '45395': 'peer_review'})

    def test_the_reports_word_each_additional_code_by_its_phase(self):
        from studio import reports, review, serializers

        assessment = self.encounter(self.encounter_id).current_assessment
        records = self.records(assessment)
        snap = reports.snapshot(self.encounter(self.encounter_id), 'draft')
        for entry in snap['peer_review']['participants']:
            # moved by refutation round 5 (R5-ACCOUNT, the session's D12): the phases are read from the review as the
            # assessment read it and its record, where the call named the assessment and the codes
            record = records[entry['name']]
            phases = serializers.peer_code_phases(review.recorded_peer_review(assessment, record), record)
            for added in entry['additional_codes']:
                added.setdefault('phase', phases[added['code']])
        text = reports.render_txt(snap).decode('utf-8')
        self.assertIn('Additional code 45385 · units 1 — repeated in peer review; first proposed in its independent '
                      'reading', text)
        self.assertNotIn('Additional code 45385 · units 1 — proposed after peer review', text)
        self.assertIn('Additional code 45378 · units 1 — proposed after peer review, never independent', text)
        rows = [row for row in reports.render_csv(snap).decode('utf-8').splitlines() if '"peer_additional_code"' in row]
        self.assertEqual(len(rows), 2)
        self.assertIn('"repeated_in_peer_review"', next(row for row in rows if '"45385"' in row))
        self.assertIn('"proposed_after_peer_review"', next(row for row in rows if '"45378"' in row))


# --- IR2-4: participant text that reads like a descriptor is withheld; the document's own passage is shown ----------

PLURAL = 'Polyp(s) in the sigmoid colon were removed with a hot snare.'


@applied
class DocumentQuoteTests(R2WordingCase):
    """IR2-4 (b) (I9; app.js's own rule that the document's text is shown as it is): a participant's position quote is
    its first LOCATED quote - an exact slice of the revision (jobs._first_located, I7) - and the code card withheld it
    as "reads like a CPT descriptor" because the document itself wrote a plural mark, while the owner's trace showed
    the same passage verbatim. The card now shows it as the document's own text."""

    def test_a_located_quote_with_the_document_s_own_plural_mark_is_shown(self):
        text = TWO_EXTENTS.replace('A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.',
                                   PLURAL)
        self.assertIn(PLURAL, text)
        snare = 'were removed with a hot snare'
        self.corti.selections = [('45385', snare), ('45380', BIOPSY)]
        self.adapters['astra'].first = [hp.answered('astra', hp.reading(
            codes=[('45385', snare), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', snare)]))]
        self.adapters['fable'].first = [hp.answered('fable', hp.reading(
            codes=[('45385', PLURAL)], services=[('c1', 'colonoscopy', 'performed', PLURAL)]))]
        encounter_id = self.create(text)
        drain()
        detail = self.detail(encounter_id)
        [card] = self.proposals(detail, '45385', bucket='selected')
        self.assertEqual(card['participant_positions']['fable']['quote'], PLURAL)  # the document's own passage
        lines = browser(f'[...visible(cardOf(page(), {json.dumps(card["id"])})).split("\\n")]'
                        '.filter(line => line.startsWith("Fable proposed it"))', detail)
        # moved by refutation round 6 (R6-MEANING, negation-4, ownership-7): the 'proposed' detail is the engine's own
        # wording, "quoting the document verbatim", never "with evidence located in the document"
        self.assertEqual(lines, [f'Fable proposed it: Fable proposed this code, quoting the document verbatim. '
                                 f'— “{PLURAL}”'])
        self.assertNotIn('its quote is withheld', json.dumps(lines))


# --- FG2-5: every real code card states the PTP limit once -----------------------------------------------------------

@applied
class ReferenceLineTests(R2WordingCase):
    """FG2-5 (I4: PTP always "not verified"): the API's reference_check detail always ends with
    review.PTP_NOT_CONNECTED, and the page always appended its own "(NCCI procedure-to-procedure edits not verified:
    not connected)" too, so every real code card stated the PTP limit twice; only hand-written fixtures, whose details
    the API cannot produce, were tested. Each card the real API serves now states it exactly once."""

    def test_each_code_card_states_the_ptp_limit_once(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        cards = [p for p in detail['assessment']['proposals'] if p['bucket'] == 'selected']
        # moved by refutation round 6 (R6-MEANING, the session's D14): two cards, Corti's 45385 and 45380 - Fable's
        # peer-review 45378, the third, is its alternative now, with no card
        self.assertEqual(len(cards), 2)
        for proposal in cards:
            self.assertTrue(proposal['reference_check']['detail'].endswith(
                'NCCI procedure-to-procedure edits are not connected, so bundling with other codes is not verified.'))
        lines = browser('cards(page()).map(card => statusLine(card, "CMS reference checks"))', detail)
        self.assertEqual(len(lines), 2)
        for line in lines:
            self.assertEqual(line.count('procedure-to-procedure'), 1, line)
