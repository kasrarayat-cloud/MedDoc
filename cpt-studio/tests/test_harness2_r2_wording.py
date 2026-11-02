"""Refutation round 2, R2-WORDING (HARNESS.md 7, 11.1, 11.4, I9): how the page and the reports name proposers, phases and
participant text, so that every sentence is true of the record.

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

from tests import test_harness2_pipeline as hp
from tests.test_harness2_pipeline import BIOPSY, SNARE, TWO_EXTENTS
from tests.test_pipeline_api import drain

APP = Path(settings.BASE_DIR) / 'studio' / 'static' / 'studio' / 'app.js'
# What node evaluates an expression over: app.js's exports, the payload, and the page's visible text and parts.
PRELUDE = r"""
const app = require(process.argv[1]);
const data = JSON.parse(process.argv[2]);
const visible = html => html
  .replace(/<(br|\/p|\/li|\/div|\/h[1-6]|\/summary|\/small|\/strong|\/article|\/section|\/ul|\/details|\/dd|\/dt)\b[^>]*>/gi, '\n')
  .replace(/<[^>]+>/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
  .replace(/&#x60;/g, '`').replace(/&amp;/g, '&').split('\n').map(line => line.replace(/\s+/g, ' ').trim()).filter(Boolean).join('\n');
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
    app.js itself, so a screen is checked as it renders."""
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the screen checks need it')
    script = f'{PRELUDE}\nprocess.stdout.write(JSON.stringify({expression}));'
    done = subprocess.run([node, '-e', script, str(APP), json.dumps(data)], capture_output=True, text=True, timeout=60,
                          check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return json.loads(done.stdout)


class R2WordingCase(hp.ColonCase):
    """The colonoscopy chain of tests.test_harness2_pipeline.ColonCase: Corti selects 45385 and 45380, Astra's first
    reading proposes both, Fable's 45385; Astra's peer review answers the extent and Fable's adds 45378 after peer
    review; both codes are held on the extent."""

    def detail(self, encounter_id):
        response = self.client.get(f'/api/encounters/{encounter_id}')
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

class CortiRelationTests(R2WordingCase):
    """truth-6 (HARNESS.md 11.4): a participant's own proposal's card read "Corti did not propose this code" whenever
    Corti was not among its proposers - also beside Corti's own excluded selection of the code, which the card's own
    rationale and the Excluded candidates list named. The API serves Corti's relation to the code (corti_relation) and
    the page words it as the engine's rationale does; "did not propose" is said only when Corti has no entry at all."""

    def proposer_line(self, detail, proposal):
        return browser(f'statusLine(cardOf(page(), {json.dumps(proposal["id"])}), "Proposed by")', detail)

    def test_a_code_corti_selected_with_no_exact_passage_is_never_called_unproposed_by_corti(self):
        def inexact(answer, _text):
            for item in answer['codes']:
                if item['code'] == '45385':
                    item['evidences'] = [{'contextIndex': 0, 'start': 0, 'end': 9, 'text': 'Not text.'}]
        with self.corti_answer(inexact):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        detail = self.detail(encounter_id)
        [own] = self.proposals(detail, '45385', bucket='selected')
        [corti] = self.proposals(detail, '45385', bucket='excluded')
        self.assertEqual((self.origin(own), own['proposed_by'], corti['exclusion_reason']),
                         ('participant', ['astra', 'fable'], 'No exact source evidence'))
        self.assertEqual(self.proposer_line(detail, own),
                         'Astra (independent reading), Fable (independent reading); Corti also selected this code, '
                         'with no exact passage; it is listed apart, excluded.')
        self.assertEqual((own['corti_relation'], corti['corti_relation']),
                         ('selected_without_exact_passage', 'proposer'))
        # control: Fable's code after peer review, which Corti never named, still says so
        [added] = self.proposals(detail, '45378')
        self.assertEqual((added['corti_relation'], self.proposer_line(detail, added)),
                         ('none', 'Fable (after peer review); Corti did not propose this code.'))

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
        [own] = self.proposals(detail, '45380', bucket='selected')
        [listed] = self.proposals(detail, '45380', bucket='alternative')
        self.assertEqual((self.origin(own), self.origin(listed)), ('participant', 'primary'))
        self.assertEqual(self.proposer_line(detail, own), 'Astra (independent reading); Corti listed this code only as '
                                                          'a candidate, not selected; see Alternatives.')
        self.assertEqual((own['corti_relation'], listed['corti_relation']), ('candidate', 'proposer'))

    def test_every_proposal_carries_the_relation_and_corti_s_own_are_corti_s(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        detail = self.detail(encounter_id)
        relations = {(p['key'], p['code']): p['corti_relation'] for p in detail['assessment']['proposals']}
        self.assertEqual(relations, {('sel:0', '45385'): 'proposer', ('sel:1', '45380'): 'proposer',
                                     ('sel:2', '45378'): 'none'})
        line = self.proposer_line(detail, next(p for p in detail['assessment']['proposals'] if p['code'] == '45385'))
        self.assertEqual(line, 'Corti, Astra (independent reading), Fable (independent reading)')

    def test_a_payload_that_serves_no_relation_says_nothing_of_corti(self):
        # a proposal served without corti_relation (before it existed): who proposed it, and nothing about Corti that
        # the record would have to support
        lines = browser("['', 'none', 'unheard-of'].map(relation => visible(app.codeStatusLines({ proposed_by: ['fable'], "
                        "reference_check: { state: 'passed' }, ...(relation ? { corti_relation: relation } : {}) })))",
                        {})
        self.assertEqual([text.split('\n')[0] for text in lines],
                         ['Proposed by: Fable', 'Proposed by: Fable; Corti did not propose this code.',
                          'Proposed by: Fable'])
