"""GI round 4, package PA: the agreement gate (studio/validation/engine.py). An exclusion needs both readers - the
routing-era reading and the documented-service reader - to read the code's own deciding passage with the same not-done
status. When both take that status only from the section the passage stands in, and that section reaches the passage
only across a heading-like line the layout does not read (sections.beyond_heading_reach; fail-closed past 200 lines or
20,000 characters), the two readings share one cause, the layout: the code is held, never excluded. A section whose own
heading stands above the passage is the document's own statement and still agrees. Declared movement (tests/fixtures/
gi4/declarations/pa.json): EXCLUDED -> held only.

Every document here is synthetic; the provider answers are synthetic and read offline through the analyze and assess
children (no database, nothing sent). Truths are PROVISIONAL author readings; no qualified GI coder has reviewed them.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio.gi import sections
from studio.validation import checks, engine

B = battery.B
H405 = battery.H405
N1 = 'A linear echoendoscope was introduced by mouth.'
N2 = ('Echoendoscopic views were obtained from the duodenal bulb, the descending duodenum and the stomach, covering the '
      'gland from the uncinate process to the tail.')
UNREAD = ('Cholecystectomy: 2014.\n\nQuestion to Answer\nIs the possible nodule on MRI tissue or mucin?\n\nScope Passage and '
          'Views\n')
# h4-05 with its two unread heading-like lines taken out: the narrative now stands under the Prior Studies heading itself
HEADED_405 = H405.replace(UNREAD, 'Cholecystectomy: 2014.\n\n')
EUS = 'Endoscopic ultrasound was performed with a linear echoendoscope introduced by mouth.'
NOTE = 'Pancreas Procedure Note\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol by CRNA\n\n'
CLINIC = 'Pancreas Clinic Note\nDate of service: 10/20/2026\n\n'
ERCP = 'ERCP Report\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol by CRNA\n\n'
ERCP_TODAY = ('Procedure\nThe duodenoscope was advanced to the second part of the duodenum. The bile duct was cannulated '
              'and a biliary sphincterotomy was performed.\n')
EXAMINED = 'A linear echoendoscope was introduced by mouth and the pancreatic cyst was examined.'
PLAN = '\n\nAssessment and plan\nBranch-duct IPMN. Repeat MRI in 12 months.\n'
CONCLUSION = '\n\nConclusion\nBranch-duct IPMN of the pancreatic body.\n'
DOCS = {
    # no documented EUS service (engine._held_unless_agreed): routing alone names it, by its section
    'clinic runaway': B + CLINIC + 'Prior Studies\nMRI 2026-09-22: 21 mm cyst in the pancreatic body.\n\nScope Passage and '
                      'Views\n' + EXAMINED + PLAN,
    'clinic headed': B + CLINIC + 'Prior Studies\n' + EXAMINED + PLAN,
    # a documented EUS service read historical (service_negative: engine._not_the_same_not_done)
    'note runaway': B + NOTE + 'Prior Studies\nMRI 2026-09-22: 21 mm cyst in the pancreatic body.\n\nScope Passage and '
                    'Views\n' + EUS + CONCLUSION,
    'note headed': B + NOTE + 'Prior Studies\n' + EUS + CONCLUSION,
    'note far': B + NOTE + 'Prior Studies\n' + ''.join(f'Prior line {i} lists an earlier result in detail.\n'
                                                       for i in range(210)) + EUS + CONCLUSION,
    # the service's status cue is an earlier line's own word ("historical: earlier"): independent of the layout
    'clinic earlier line': B + CLINIC + 'Prior Studies\nAn earlier EUS showed a 19 mm cyst.\n\nScope Passage and Views\n'
                           + EUS + PLAN,
    # the act path with a stent exchange (no such act in the inventory's vocabulary): runaway and headed
    'ercp runaway': B + ERCP + 'Prior Procedures\nCholecystectomy in 2014.\n\nStent Management\nThe biliary stent was '
                    'exchanged.\n\n' + ERCP_TODAY,
    'ercp headed': B + ERCP + 'Prior Procedures\nThe biliary stent was exchanged.\n\n' + ERCP_TODAY,
}
HELD = ('selected', 'needs_clarification')
EXCLUDED = ('excluded', 'excluded')


def assess(text: str, codes) -> dict:
    """{code: proposal} for synthetic provider codes [(code, [quote, ...])], read as the stages read them (the analyze
    child, the merged facts, the assess child with an in-memory answer and no reference rows)."""
    m = battery.modules()
    document_facts, day, _routing = m.jobs._analyze_child(text, {}, 1000)
    facts = m.jobs._merged_facts(document_facts, {})
    found = []
    for i, (code, quotes) in enumerate(codes):
        spans = tuple(m.EvidenceSpan(0, text.index(q), text.index(q) + len(q), q, True, 1) for q in quotes)
        found.append(m.ProviderCode(role='selected', system='cpt', code=code, display='SYNTHETIC', index=i, evidence=spans))
    response = m.NormalizedResponse(provider='corti', adapter_version='corti-coding-v2@cptstudio-1', codes=tuple(found))
    try:
        _, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),),
                                         m.jobs.context_facts(SimpleNamespace(facts=facts)), response, m.Lookup([], {}),
                                         'succeeded', 'ok', ())
    finally:
        m.jobs.release_routing_caches()
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}


def outcome(p) -> tuple:
    return p.bucket, p.status


def status_detail(p) -> str:
    return ' '.join(next(c.detail for c in p.checks if c.id == 'service.status').split())


class OneCauseIsHeldTests(SimpleTestCase):
    """Both readings only by a section that reaches the passage across an unread heading-like line: held."""

    def test_the_h4_05_counterfactual_is_held(self):
        # the judge's F1: an EUS code citing h4-05's narrative under the runaway "Prior Studies" section had been
        # EXCLUDED as historical, both readers taking the time from that one section
        for code in ('43259', '43237'):
            for quotes in ([N1], [N2], [N1, N2]):
                with self.subTest(code=code, quotes=len(quotes), first=quotes[0][:20]):
                    self.assertEqual(outcome(assess(H405, [(code, quotes)])[code]), HELD)

    def test_citing_only_the_title_stays_held(self):
        p = assess(H405, [('43259', ['Pancreatic Endosonography'])])['43259']
        self.assertEqual(outcome(p), HELD)

    def test_an_attributive_time_word_leaves_both_readings_section_only(self):
        text = H405.replace(N1, 'A linear echoendoscope was introduced by mouth for a remote cyst.')
        p = assess(text, [('43259', ['A linear echoendoscope was introduced by mouth for a remote cyst.'])])['43259']
        self.assertEqual(outcome(p), HELD)

    def test_with_no_documented_service_routing_alone_is_held_and_says_why(self):
        p = assess(DOCS['clinic runaway'], [('43259', [EXAMINED])])['43259']
        self.assertEqual(outcome(p), HELD)
        self.assertIn('reads it the same only by its section: one cause, not two readings', status_detail(p))

    def test_a_service_read_historical_only_by_its_section_is_held_and_says_why(self):
        p = assess(DOCS['note runaway'], [('43259', [EUS])])['43259']
        self.assertEqual(outcome(p), HELD)
        detail = status_detail(p)
        self.assertIn('The routing-era reading of the passages it cites reads it the same way:', detail)
        self.assertNotIn('reads it otherwise', detail)
        self.assertIn('Both readers read the endoscopic ultrasound as historical only by the section it stands in: one '
                      'cause, not two readings; its section “Prior Studies” reaches the passage only past a line '
                      'written as a heading that the layout does not read as one.', detail)
        self.assertIn('Held for the reviewer, not excluded.', detail)

    def test_a_heading_beyond_the_reach_read_fails_closed_and_says_so(self):
        p = assess(DOCS['note far'], [('43259', [EUS])])['43259']
        self.assertEqual(outcome(p), HELD)
        self.assertIn('its section “Prior Studies” reaches the passage from more than 200 lines or 20,000 '
                      'characters below its heading, further than a heading is read', status_detail(p))

    def test_a_runaway_stent_exchange_is_held(self):
        p = assess(DOCS['ercp runaway'], [('43276', ['The biliary stent was exchanged.'])])['43276']
        self.assertEqual(outcome(p), HELD)


class HeadedSectionsStillExcludeTests(SimpleTestCase):
    """The same readings under the section's own heading: the document's own statement, so the readers agree."""

    def test_the_h4_05_narrative_under_its_heading_stays_excluded(self):
        self.assertNotEqual(HEADED_405, H405)
        self.assertEqual(outcome(assess(HEADED_405, [('43259', [N1])])['43259']), EXCLUDED)

    def test_with_no_documented_service_stays_excluded(self):
        self.assertEqual(outcome(assess(DOCS['clinic headed'], [('43259', [EXAMINED])])['43259']), EXCLUDED)

    def test_a_service_read_historical_under_its_heading_stays_excluded(self):
        p = assess(DOCS['note headed'], [('43259', [EUS])])['43259']
        self.assertEqual(outcome(p), EXCLUDED)
        self.assertIn('The routing-era reading agrees:', status_detail(p))

    def test_a_headed_prior_stent_exchange_stays_excluded(self):
        self.assertEqual(outcome(assess(DOCS['ercp headed'], [('43276', ['The biliary stent was exchanged.'])])['43276']),
                         EXCLUDED)


class AReadingOfItsOwnStillAgreesTests(SimpleTestCase):
    """A time word, a date or a denial a reader reads itself is not the layout's: the agreement stands."""

    def test_the_documented_service_reader_reads_a_time_word_of_its_own(self):
        text = H405.replace(N1, 'A linear echoendoscope had been introduced by mouth.')
        p = assess(text, [('43259', ['A linear echoendoscope had been introduced by mouth.'])])['43259']
        self.assertEqual(outcome(p), EXCLUDED)

    def test_the_service_status_cue_is_another_lines_own_word(self):
        # the literal rule's boundary: the service is historical by "An earlier EUS ..." (its own word), so its reading
        # is not the section's alone, whatever routing's reading of the cited line
        self.assertEqual(outcome(assess(DOCS['clinic earlier line'], [('43259', [EUS])])['43259']), EXCLUDED)

    def test_two_different_not_done_statuses_still_read_otherwise(self):
        text, codes = battery.CASES['colonoscope reaches cecum in a plan']
        p = assess(text, [(c, [q]) for c, q, _ in codes])['45378']
        self.assertEqual(outcome(p), HELD)
        detail = status_detail(p)
        self.assertIn('The routing-era reading of the passages it cites reads it otherwise:', detail)
        self.assertIn('not the same reading.', detail)


class PredicateTests(SimpleTestCase):
    """The gate's two predicates and its words, read directly."""

    def test_a_documented_service_reading_only_by_its_section(self):
        yes = (('historical: in a history section',), ('planned: in a plan section',),
               ('historical: in a history section', 'uncertain: routing reads the family as historical'))
        no = ((), ('historical: had been',), ('historical: earlier',), ('uncertain: no performance statement',),
              ('historical: in a history section', 'historical: 2023 is before the service date'),
              ('negated: "not" on its predicate', 'historical: in a history section'),
              ('historical: in a history section', 'cancelled: aborted'))
        for cues in yes:
            self.assertTrue(engine._section_only_service_reading(cues), cues)
        for cues in no:
            self.assertFalse(engine._section_only_service_reading(cues), cues)

    def reading(self, text, quote, *cues, start=True):
        pos = text.index(quote)
        return checks.Reading('historical', cues, 'evidence', quote, pos if start else None, pos + len(quote))

    def test_routing_reading_only_by_a_section_beyond_its_heading(self):
        section = 'section: history (Prior Studies)'
        self.assertTrue(engine._section_only_routing_reading(self.reading(H405, N1, section), H405))
        self.assertTrue(engine._section_only_routing_reading(self.reading(H405, N1, 'performed: was introduced', section),
                                                             H405))
        # a time cue of its own is routing's own reading, whatever its section
        self.assertFalse(engine._section_only_routing_reading(
            self.reading(H405, N1, 'historical: 2025-04-09 is before the service date', section), H405))
        self.assertFalse(engine._section_only_routing_reading(self.reading(H405, N1, 'negated: never had a', section),
                                                              H405))
        # no section cue: not its section's reading
        self.assertFalse(engine._section_only_routing_reading(self.reading(H405, N1, 'performed: was introduced'), H405))
        # no passage of its own (a reading of the whole family)
        self.assertFalse(engine._section_only_routing_reading(self.reading(H405, N1, section, start=False), H405))
        # under the section's own heading
        self.assertFalse(engine._section_only_routing_reading(self.reading(HEADED_405, N1, section), HEADED_405))
        # and on another text than the passage's (no heading reaches it)
        self.assertFalse(engine._section_only_routing_reading(self.reading(H405, N1, section), ''))

    def test_every_not_done_status_a_reader_states_itself_is_its_own_reading(self):
        # a plan word or a cancellation is a reading of its own as much as a time word or a denial, on either side of
        # the gate: every status checks.NEGATIVE knows is one (a status added there and not here fails this pin)
        for status in checks.NEGATIVE:
            self.assertTrue(engine._pa_own_time(f'{status}: a word of its own'), status)
        for cue in ('performed: was introduced', 'section: history (Prior Studies)', 'uncertain: no performance '
                    'statement', 'incomplete: could not be advanced'):
            self.assertFalse(engine._pa_own_time(cue), cue)
        self.assertFalse(engine._section_only_service_reading(('planned: in a plan section', 'planned: in one year')))
        self.assertFalse(engine._section_only_service_reading(('planned: in a plan section', 'cancelled: aborted')))
        section = 'section: history (Prior Studies)'
        self.assertTrue(engine._section_only_routing_reading(self.reading(H405, N1, section), H405))  # the control
        for own in ('planned: in one year', 'cancelled: aborted', 'historical: earlier', 'negated: No further'):
            self.assertFalse(engine._section_only_routing_reading(self.reading(H405, N1, own, section), H405), own)

    def test_the_words_for_how_the_section_reaches_the_passage(self):
        near = engine._pa_reach(H405, H405.index(N1))
        self.assertEqual(near, 'its section “Prior Studies” reaches it only past a line written as a heading '
                               'that the layout does not read as one')
        far_text = DOCS['note far']
        self.assertTrue(sections.beyond_heading_reach(far_text, sections.layout(far_text), far_text.index(EUS)))
        far = engine._pa_reach(far_text, far_text.index(EUS), 'the passage')
        self.assertEqual(far, 'its section “Prior Studies” reaches the passage from more than 200 lines or '
                              '20,000 characters below its heading, further than a heading is read')

    def test_the_same_not_done_status(self):
        service = SimpleNamespace(status='historical')
        same = SimpleNamespace(reason='service_negative', service=service)
        old = checks.StatusOutcome('not_performed', checks.Reading('historical', (), 'evidence', '', 0, 1))
        self.assertTrue(engine._pa_same_not_done(same, old))
        self.assertFalse(engine._pa_same_not_done(same, checks.StatusOutcome(
            'not_performed', checks.Reading('planned', (), 'evidence', '', 0, 1))))
        self.assertFalse(engine._pa_same_not_done(SimpleNamespace(reason='act_denied', service=service), old))
        self.assertFalse(engine._pa_same_not_done(same, checks.StatusOutcome('not_performed', None)))
