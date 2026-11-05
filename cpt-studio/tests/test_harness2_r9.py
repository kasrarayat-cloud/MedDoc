"""Refutation round 9, the narrow pass over round 8's repair commit (cd914621a..b58c7bede): the findings it reproduced
(refute-harness-r9, each verified in verify-harness-r9), on their own inputs.

- retrieval-1, retrieval-2, page-1: round 8 traced the codes of every proposal that is not an alternative, so a code
  excluded with no reinstatement - outside CPT-only results, or with no exact source evidence - was traced and
  counted: reference validation read "Done 1 code checked" where no proposal could be decided on and the code's own
  reference check says none ran, and a READY 45378 was paired in a CMS endoscopy-family rule with an excluded 45380,
  in the reviewed report. Only a code a reviewer can decide is traced now (review.decidable: selected, or excluded and
  reinstatable), and the API reads only such a trace.
- wording-1, wording-2, wording-3: a service only a participant reads is worded with an act read as performed only
  where the act's own mention lies inside the quote (its whole clause had only to touch the quote's edge); a PEG
  mention is named by its act label and an act's service by its family's own label (never "the peg"); and every place
  the quote is found verbatim is read, not only the first.
- wording-4: participants.summary's closing sentence names a response CPT Studio used.
- page-2, page-3: a highlight holding both kinds of passage for one code says it holds them, never that they overlap,
  and the pins cover a highlight of two codes.

retrieval-3 was not reproduced: no installed system holds a trace an earlier build recorded (the harness adds
Assessment.retrieval, migration 0007, and no harness build has been installed). The page's branches are pinned in the
`// refutation round 9` block of tests/frontend/app.test.cjs. With no participant configured the engine's result is
unchanged (I1): tests/test_harness_engine_parity.py and CortiOnlyParityTests pin it. Synthetic data only; nothing is
sent: Corti is the suite's in-process fake read by the real normaliser, and Astra and Fable are the real replay
adapters on the real tool loop (tests.test_harness2_pipeline).
"""
import json

from django.test import SimpleTestCase, override_settings

from studio import review
from tests import test_harness2_pipeline as hp
from tests import test_harness2_r6_meaning as r6m
from tests import test_harness2_r7 as r7
from tests import test_harness2_r8 as r8
from tests import test_harness_engine as he
from tests.test_harness2_r2_wording import browser

ACK = review.ACKNOWLEDGEMENTS['human']
OFF = dict(ASTRA_MODE='disabled', FABLE_MODE='disabled')
NORMAL = 'The colon was normal.'
NO_POLYPECTOMY = 'No polypectomy was performed.'


def kind(p):
    return p['key'].split(':')[0]


def endoscopy_family(item):
    return [entry['label'] for entry in item['retrieval'] if 'endoscopy' in (entry['label'] or '')]


# --- retrieval-1, retrieval-2, page-1: a code no reviewer can decide is never traced -------------------------------

class UndecidableExclusionRetrievalTests(r6m.MeaningCase):
    def assert_nothing_checked(self, encounter_id, detail):
        """retrieval-1, page-1: the only code is Corti's, excluded with no reinstatement - no action reaches it and its
        own reference check says no CMS check ran - so reference validation is not run, never "Done 1 code checked"."""
        (item,) = r6m.proposals(detail)
        self.assertEqual((item['bucket'], item['reinstatable'], item['allowed_actions'], item['retrieval']),
                         ('excluded', False, [], []))
        self.assertEqual(r8.traced(encounter_id), [])
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked'], block['passages']), ('not_run', 0, 0))
        row = browser('rowOf(page(), "data-participant", "reference_validation")', detail)
        self.assertIn(r8.NOT_CHECKED, row)
        self.assertNotIn('checked against the CMS reference files', row)

    def test_retrieval_1_no_exact_passage_corti_alone(self):
        text = r6m.doc(r6m.COLON, r6m.SEEN)
        with r7.inexact(0, '45378'), override_settings(**OFF):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM)])
            detail = self.detail(encounter_id)
            self.assertEqual(detail['harness']['phase'], 0)
            self.assert_nothing_checked(encounter_id, detail)

    def test_retrieval_1_no_exact_passage_with_participants(self):
        text = r6m.doc(r6m.COLON, r6m.SEEN)
        with r7.inexact(0, '45378'):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM)])
        detail = self.detail(encounter_id)
        self.assertEqual(detail['harness']['phase'], 2)
        self.assert_nothing_checked(encounter_id, detail)

    def test_page_1_outside_cpt_only_results(self):
        """page-1 (b): Corti's only code is G0121, outside CPT-only results - "Done 1 code checked; 0 passages"."""
        with override_settings(**OFF):
            encounter_id = self.scenario(r6m.earlier(r6m.LAST_LABEL), [('G0121', r6m.LAST_LABEL)])
            self.assert_nothing_checked(encounter_id, self.detail(encounter_id))

    def test_page_1_beside_a_decidable_code_only_that_code_is_counted(self):
        """page-1 (c): beside the excluded 45378, Corti's 45385 on the snare sentence is selected - one code checked,
        never two."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r7.SNARED)
        with r7.inexact(0, '45378'), override_settings(**OFF):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM), ('45385', r7.SNARED)])
            detail = self.detail(encounter_id)
        self.assertEqual(sorted((p['code'], p['bucket']) for p in r6m.proposals(detail)),
                         [('45378', 'excluded'), ('45385', 'selected')])
        self.assertEqual(r8.traced(encounter_id), ['45385'])
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked']), ('done', 1))

    def test_a_reinstatable_exclusion_is_still_traced(self):
        """Control: Corti's 45385 on "No polypectomy was performed." is excluded by a documentation check and can be
        reinstated - a reviewer decides it - so it is traced and counted, beside the selected 45378."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, NO_POLYPECTOMY)
        with override_settings(**OFF):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM), ('45385', NO_POLYPECTOMY)])
            detail = self.detail(encounter_id)
        rows = {p['code']: p for p in r6m.proposals(detail)}
        self.assertEqual((rows['45385']['bucket'], rows['45385']['reinstatable']), ('excluded', True))
        self.assertTrue(rows['45385']['retrieval'])
        self.assertEqual(r8.traced(encounter_id), ['45378', '45385'])
        block = detail['harness']['reference_validation']
        self.assertEqual((block['state'], block['codes_checked']), ('done', 2))

    def test_an_undecidable_card_is_never_served_another_proposal_s_trace_of_its_code(self):
        """Corti's primary 45385 has no exact passage and is excluded with no reinstatement; the bounded second review
        then adds 45385 on the snare sentence. The added proposal is traced and its card lists the trace; the
        excluded card of the same code lists none of it."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r7.SNARED)
        with override_settings(**OFF):
            with r7.inexact(1, '45385'):
                encounter_id = self.scenario(text, [('45378', r6m.CECUM), ('45385', r6m.SEEN)])
            self.assertTrue(self.detail(encounter_id)['second_review']['available'])
            self.corti.selections = [('45385', r7.SNARED)]
            reply = self.client.post(f'/api/encounters/{encounter_id}/second-review')
            self.assertEqual(reply.status_code, 201, reply.content)
            r8.drain()
            detail = self.detail(encounter_id)
        rows = sorted((kind(p), p['bucket'], p['reinstatable'], bool(p['retrieval']))
                      for p in r6m.proposals(detail) if p['code'] == '45385')
        self.assertEqual(rows, [('exc', 'excluded', False, False), ('sel', 'selected', False, True)])
        self.assertEqual(r8.traced(encounter_id), ['45378', '45385'])

    def assert_no_pairing(self, encounter_id, detail):
        """retrieval-2: Corti's READY 45378 beside its 45380 excluded with no reinstatement: only 45378 is traced, and
        neither its card nor the reviewed report a reviewer signs pairs it with 45380 in a CMS endoscopy-family rule."""
        rows = {p['code']: p for p in r6m.proposals(detail)}
        self.assertEqual((rows['45378']['bucket'], rows['45378']['status'], rows['45380']['bucket'],
                          rows['45380']['reinstatable']), ('selected', 'ready', 'excluded', False))
        self.assertEqual(r8.traced(encounter_id), ['45378'])
        self.assertEqual(endoscopy_family(rows['45378']), [])
        self.assertEqual(rows['45380']['retrieval'], [])
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': rows['45378']['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        detail = self.detail(encounter_id)
        self.assertTrue(detail['readiness']['reviewed'], detail['readiness'])
        card = browser(f'visible(cardOf(page(), {json.dumps(rows["45378"]["id"])}))', detail)
        self.assertNotIn('ncci.endoscopy', card)
        report = self.download(encounter_id, 'reviewed')
        self.assertNotIn('is the endoscopic base of 45380', report)
        self.assertNotIn('45378, 45380 are one endoscopic family', report)
        self.assertEqual(detail['harness']['reference_validation']['codes_checked'], 1)

    def test_retrieval_2_corti_alone(self):
        text = r6m.doc(r6m.COLON, NORMAL)
        with r7.inexact(1, '45380'), override_settings(**OFF):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM), ('45380', NORMAL)])
            self.assert_no_pairing(encounter_id, self.detail(encounter_id))

    def test_retrieval_2_with_participants(self):
        text = r6m.doc(r6m.COLON, NORMAL)
        with r7.inexact(1, '45380'):
            encounter_id = self.scenario(text, [('45378', r6m.CECUM), ('45380', NORMAL)])
        self.assert_no_pairing(encounter_id, self.detail(encounter_id))


# --- wording-1, wording-2, wording-3: what a participant's quote of a service is said to be read as -----------------

SNARE_TAIL = 'a 6 mm rectal polyp was removed with a cold snare'
# (the line appended, the participant's status, its quote, whether the band ligation is named)
EDGE = (
    (f'Banding of the internal hemorrhoids was attempted but failed after {SNARE_TAIL}.', 'attempted_incomplete',
     'Banding of the internal hemorrhoids was attempted but failed', False),
    (f'Two internal hemorrhoids were banded after {SNARE_TAIL}.', 'performed', 'Two internal hemorrhoids were banded',
     True),
    (f'Anoscopy was performed after {SNARE_TAIL}.', 'performed', 'Anoscopy was performed', False),
    ('A 6 mm rectal polyp was removed with a cold snare Two internal hemorrhoids were banded.', 'performed',
     'Two internal hemorrhoids were banded.', True),
)
PEG_NOTE = (hp.HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
            'Procedure: Percutaneous endoscopic gastrostomy\nThe endoscope was advanced to the second part of the '
            'duodenum.\nA PEG tube was placed in the stomach.\n')
PEG_CANCELLED = 'The PEG tube placement was cancelled.'
EARLIER_BANDING = 'At the last visit (2025-03-02): Two internal hemorrhoids were banded.'
TODAY_BANDING = 'Today: Two internal hemorrhoids were banded.'
BANDED = 'Two internal hemorrhoids were banded.'
REFERRAL = 'Referral for upper endoscopy.'
UPPER = 'upper endoscopy'


def engine(text, quote, family='other_gi', status='performed', head_code='45378', anchor=r6m.CECUM,
           head_family='colonoscopy', corti_code=None):
    codes = he.corti(*((value, he.span(text, q)) for value, q in (corti_code or [(head_code, anchor)])))
    return he.run(text, codes,
                  [he.read('astra', [he.code(text, head_code, anchor)],
                           services=[he.service(text, head_family, anchor),
                                     he.service(text, family, quote, status=status)])])


class MissingServiceReadingTests(SimpleTestCase):
    def entry(self, result):
        (item,) = result.completeness['participant_services']
        return item

    def test_wording_1_an_act_is_named_only_by_its_own_mention_in_the_quote(self):
        """wording-1: the snare act's clause reaches the quote's edge ("... failed", "... performed") but its own words
        lie outside it: never "the snare removal ... as performed" beside it. Moved by refutation round 10 (wording-2 to
        wording-5): no act is named at all - the band ligation the quote holds included - and the reason says only what
        makes the service missing."""
        for line, status, quote, _ in EDGE:
            with self.subTest(quote):
                text = r6m.doc(r6m.COLON, line)
                item = self.entry(engine(text, quote, status=status, corti_code=[('45378', r6m.CECUM)]))
                self.assertNotIn('snare removal', item['reason'])
                self.assertEqual(item['read_as'], '')
                self.assertIn(r7.NOT_READ, item['reason'])

    def test_wording_2_a_peg_procedure_note(self):
        """wording-2 (a): the upper-endoscopy service takes its kind from its first mention, the PEG title, and its act
        had been named "in the peg". Moved by refutation round 10: no act is named, so neither label is printed."""
        result = engine(PEG_NOTE, r8.PEG_PLACED, head_code='43246', anchor=r6m.D2, head_family='egd',
                        corti_code=[('43246', r6m.D2)])
        item = self.entry(result)
        self.assertEqual(item['read_as'], '')
        self.assertIn(r7.NOT_READ, item['reason'])
        self.assertNotIn('the peg', item['reason'])

    def test_wording_2_a_cancelled_peg_line(self):
        """wording-2 (b): a quoted PEG line's own kind has no service label: it is named by its act label, beside
        services.inventory's "upper endoscopy (cancelled)" - never "the peg as cancelled"."""
        text = r6m.doc(r6m.COLON, r7.IN_QUOTE[2][1], PEG_CANCELLED)
        item = self.entry(engine(text, PEG_CANCELLED, family='egd'))
        self.assertEqual(item['read_as'], 'the gastrostomy (PEG) placement as cancelled')
        self.assertNotIn('the peg', item['reason'])

    def test_wording_3_every_place_of_the_quote_is_read(self):
        """wording-3: the quoted words are found twice. Moved by refutation round 10 (the act arm removed, so a repeat
        banding names nothing; it was "the band ligation in the colonoscopy as performed"): "upper endoscopy" is read
        as planned at its first place, a status the inventory's cancelled upper endoscopy did not adopt, and as
        cancelled at its second - so the reason names the second place's reading, and the entry's passage is that
        place."""
        text = r6m.doc(r6m.COLON, REFERRAL, r7.IN_QUOTE[2][1])
        item = self.entry(engine(text, UPPER, family='egd'))
        self.assertEqual(item['read_as'], 'the upper endoscopy as cancelled')
        second = text.index(UPPER, text.index(UPPER) + 1)
        self.assertEqual((item['start'], item['end']), (second, second + len(UPPER)))
        # and the repeat banding: no act is named; only what makes the service missing
        text = r6m.doc(r6m.COLON, EARLIER_BANDING, TODAY_BANDING)
        item = self.entry(engine(text, BANDED))
        self.assertEqual(item['read_as'], '')
        self.assertIn(r7.NOT_READ, item['reason'])


class MissingServiceReadingPipelineTests(r6m.MeaningCase):
    def test_wording_1_an_attempt_that_failed_is_never_printed_beside_as_performed(self):
        """wording-1 (a), on the reviewed report a reviewer signs."""
        line, status, quote, _ = EDGE[0]
        text = r6m.doc(r6m.COLON, line)
        services = [r6m.colon_service(r6m.CECUM), ('u1', 'other_gi', status, quote)]
        encounter_id = self.scenario(text, [('45385', SNARE_TAIL)],
                                     astra=hp.reading(codes=[('45378', r6m.CECUM)], services=services))
        detail = self.detail(encounter_id)
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '45385']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        self.assertTrue(self.detail(encounter_id)['readiness']['reviewed'])
        report = self.download(encounter_id, 'reviewed')
        self.assertIn(f'Astra reads an attempted, incomplete other GI service {r7.NOT_READ} (“{quote}”)', report)
        self.assertNotIn('snare removal (cold snare) at the rectum in the colonoscopy as performed (“Banding', report)


# --- wording-4: participants.summary's closing sentence beside a response refused whole ----------------------------

class SummarySentenceTests(r6m.MeaningCase):
    def test_beside_a_provider_response_refused_whole(self):
        """wording-4: Corti's stored response selects 45385, in scope and on an exact passage, and is refused whole. The
        sentence names a response CPT Studio used. HARNESS.md P-ADMIT (2026-11-05): Astra's first-reading 45385 on the
        snare sentence is admitted (D14 had listed it among the alternatives, as its sentence then said)."""
        text = r6m.doc(r6m.COLON, r6m.SEEN, r7.SNARED)
        with r8.refused_whole():
            encounter_id = self.scenario(text, [('45385', r7.SNARED)], astra=hp.reading(codes=[('45385', r7.SNARED)]))
        detail = self.detail(encounter_id)
        self.assertEqual([(kind(p), p['code']) for p in r6m.proposals(detail)], [('sel', '45385')])
        summary = self.summary(detail)
        self.assertTrue(summary.endswith(f' {r6m.NEVER_DECIDE}'), summary)
        self.assertIn('in a response CPT Studio used', summary)
        self.assertNotIn('one in a provider response CPT Studio did not use', summary)


# --- page-2, page-3: a highlight holding both kinds of passage for one code -------------------------------------

BIOPSIES = 'Biopsies of the rectum were taken with cold forceps.'
LINE = f'{r6m.SEEN} {r7.SNARED} {BIOPSIES}'
HOLDING = r8.OVERLAPPING


class TwoCodeHighlightTitleTests(r6m.MeaningCase):
    def titles(self, detail):
        return {text: title for _, title, text in r6m.marks(detail)}

    def both(self, corti):
        text = r6m.doc(r6m.COLON, LINE)
        return [self.corti_alone(text, corti), self.detail(self.scenario(text, corti))]

    def test_page_2_two_codes_in_one_highlight(self):
        """page-2: 45385 cites the "was seen" sentence and the passage holding it and the snare sentence; 45380 cites
        the snare and biopsy sentences; the layout joins all three. 45385's two kinds are said as held in the
        highlight, 45380's own evidence apart - never "Evidence for 45385, 45380; Passage the provider cited ..."."""
        corti = [('45385', r6m.SEEN), ('45385', f'{r6m.SEEN} {r7.SNARED}'), ('45380', f'{r7.SNARED} {BIOPSIES}')]
        for detail in self.both(corti):
            self.assertEqual(self.titles(detail), {LINE: f'Evidence for 45380; {HOLDING.format(code="45385")}'})

    def test_page_3_two_separate_passages_another_code_joins(self):
        """page-3: 45385's two passages are separate sentences; 45380's whole-line passage joins them into one
        highlight, which therefore holds both kinds for 45385 - and never says that they overlap."""
        corti = [('45385', r6m.SEEN), ('45385', r7.SNARED), ('45380', LINE)]
        for detail in self.both(corti):
            item = next(p for p in r6m.proposals(detail) if p['code'] == '45385')
            self.assertEqual((item['support']['supporting'], item['support']['unrelated']), ([1], [0]))
            titles = self.titles(detail)
            self.assertEqual(titles, {LINE: f'Evidence for 45380; {HOLDING.format(code="45385")}'})
            self.assertFalse(any('verlapping' in title for title in titles.values()), titles)
