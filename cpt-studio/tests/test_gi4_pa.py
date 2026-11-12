"""GI round 4, package PA: the agreement gate (studio/validation/engine.py). An exclusion needs both readers - the
routing-era reading and the documented-service reader - to read the code's own deciding passage with the same not-done
status. When both take that status only from the section the passage stands in, and that section reaches the passage
only across a heading-like line the layout does not read (sections.beyond_heading_reach; fail-closed past 200 lines or
20,000 characters), the two readings share one cause, the layout: the code is held, never excluded. A section whose own
heading stands above the passage is the document's own statement and still agrees. Declared movement (tests/fixtures/
gi4/declarations/pa.json): EXCLUDED -> held only.

Wave 1 repair cycle 1 (pa.json amendment_20261101_r2, declared before its code; refutations F6, CTS-3 and CTS-4 of
b840ae756): only a REAL unread heading makes the section's reading one cause (engine._pa_unread_heading) - never a list
entry, a provider, facility or page line, a bare procedure name, the section's first line, or a line that itself names
another occurrence (which governs: the agreement stands) - and on the act path the one-cause hold says why
(engine._pa_one_cause_hold) instead of the inventory's act_missing words, which are false of h4-05. The R2_ROWS below
are the amendment's rows, their texts pinned there by sha256, each code's outcome declared as [installed 80df1831d168,
b840ae756, cycle 1].

Every document here is synthetic; the provider answers are synthetic and read offline through the analyze and assess
children (no database, nothing sent). Truths are PROVISIONAL author readings; no qualified GI coder has reviewed them.
"""
import dataclasses
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery, boot
from studio.gi import detect, sections
from studio.gi import services as gi_services
from studio.types import Span
from studio.validation import checks, engine, reconcile

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
        # Wave 1 repair cycle 1 (pa.json amendment_20261101_r2): the words quote the real unread heading line
        self.assertIn('Both readers read the endoscopic ultrasound as historical only by the section it stands in: one '
                      'cause, not two readings; its section “Prior Studies” reaches the passage only past the line '
                      '“Scope Passage and Views”, written as a heading, which the layout does not read as one.', detail)
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
        self.assertEqual(near, 'its section “Prior Studies” reaches it only past the line “Scope Passage and Views”, '
                               'written as a heading, which the layout does not read as one')
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


# --- Wave 1 repair cycle 1 (pa.json amendment_20261101_r2; refutations F6, CTS-3 and CTS-4 of b840ae756) ---------------
R2 = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations' / 'pa.json').read_text(
    encoding='utf-8'))['amendment_20261101_r2']
R2_DECLARED = R2['expected']['rows']['rows']
COLON = 'Colonoscopy Report\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol by CRNA\n\n'
CECUM = 'The colonoscope was advanced to the cecum.'


def _f6(sub):
    """F6's colonoscopy report: an earlier EUS under Prior Studies, below the sub-heading ``sub``."""
    return (B + COLON + 'Prior Studies\nCT abdomen 2026-09-01: 19 mm pancreatic cyst.\n\n' + sub + '\n' + N1
            + ' The pancreas was examined from the head to the tail; the cyst measured 19 mm.\n\nProcedure\n' + CECUM
            + ' No polyps were found.\n')


OFFICE = ('Office visit note\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\nEstablished patient\n'
          'Chief complaint\nHeartburn.\n')
OFFICE_END = ('Physical exam\nAbdomen soft, nontender.\nMedical decision making: moderate.\nAssessment and plan\nGERD. '
              'Continue omeprazole.\n')
MDM = 'Medical decision making: moderate.'


def _psh(*lines):
    """CTS-3's office note, its Past Surgical History holding ``lines``."""
    return B + OFFICE + 'Past Surgical History\n' + ''.join(line + '\n' for line in lines) + OFFICE_END


STENT = 'The biliary stent was exchanged.'
SPHINCTEROTOMY = 'a biliary sphincterotomy was performed'


def _ercp(prior):
    """An ERCP report whose Prior Procedures section holds ``prior`` and then the stent exchange line."""
    return B + ERCP + 'Prior Procedures\n' + prior + STENT + '\n\n' + ERCP_TODAY


def _ercp_after(between):
    """The same, with a first content line (an earlier procedure) and a blank line before ``between``."""
    return _ercp('Cholecystectomy in 2014.\n\n' + between)


ERCP_CODES = (('43276', STENT, 'not_done'), ('43262', SPHINCTEROTOMY, 'done'))
EGD_CODES = (('99214', MDM, 'done'), ('43249', 'Upper endoscopy with dilation', 'not_done'))
# (text, ((code, quote, provisional truth), ...)): the amendment's rows, byte for byte as declared
R2_ROWS = {
    # F6: a sub-heading that names an earlier occurrence itself governs the passage: the agreement stands
    'F6 earlier echoendoscope sub-heading': (_f6('What the Earlier Echoendoscope Showed'),
                                             (('45378', CECUM, 'done'), ('43259', N1, 'not_done'))),
    'F6 control, earlier EUS report excerpt sub-heading': (_f6('Earlier EUS Report Excerpt'),
                                                           (('45378', CECUM, 'done'), ('43259', N1, 'not_done'))),
    # CTS-3: list entries, name and page lines, procedure-name lines in a history section are no headings
    'CTS-3 PA-06 surgical history entries in title case': (
        _psh('Colonoscopy With Biopsy', 'Upper Endoscopy With Dilation', 'Laparoscopic Cholecystectomy'),
        (('99214', MDM, 'done'), ('43249', 'Upper Endoscopy With Dilation', 'not_done'))),
    'CTS-3 PA-07 control, lower-case entries': (
        _psh('Colonoscopy with biopsy', 'Upper endoscopy with dilation', 'Laparoscopic cholecystectomy'), EGD_CODES),
    'CTS-3 PA-08 provider name line': (_psh('Colonoscopy with biopsy', 'Alan Synthetic MD', 'Upper endoscopy with dilation'),
                                      EGD_CODES),
    'CTS-3 PA-09 page header line': (_psh('Colonoscopy with biopsy', 'Page 2 of 3', 'Upper endoscopy with dilation'),
                                    EGD_CODES),
    'CTS-3 PA-10 control, the cited entry first': (_psh('Upper endoscopy with dilation', 'Colonoscopy with biopsy'),
                                                  EGD_CODES),
    'CTS-3 PA3-00 control, the cited line under its heading': (_ercp(''), ERCP_CODES),
    'CTS-3 PA3-01 procedure-name line': (_ercp('Endoscopic Retrograde Cholangiopancreatography\n'), ERCP_CODES),
    'CTS-3 PA3-02 facility line': (_ercp('Synthetic Regional Medical Center\n'), ERCP_CODES),
    'CTS-3 PA3-03 page header line': (_ercp('Page 2 of 3\n'), ERCP_CODES),
    # one row per guard of the real-heading rule (an ERCP report; the stent exchange is the not-done code)
    'G-pa control, a real unread heading': (_ercp_after('Stent Management\n'), ERCP_CODES),
    'G-pa first line under the heading, after a blank line': (_ercp('\nStent Management\n'), ERCP_CODES),
    'G-pa an entry followed by another entry': (_ercp_after('Stent Management\nPlastic Stent\n'), ERCP_CODES),
    'G-pa an entry under another entry': (_ercp_after('Gallbladder Removal\nStent Management\n'), ERCP_CODES),
    'G-pa a line continuing a sentence': (_ercp('Cholecystectomy in 2014 and later the stent was placed by the\n'
                                                'Stent Management Team\n'), ERCP_CODES),
    'G-pa control, a heading under a field line': (_ercp('Cholecystectomy: 2014\nStent Management\n'), ERCP_CODES),
    'G-pa a facility line': (_ercp_after('Synthetic Regional Medical Center\n'), ERCP_CODES),
    'G-pa a provider line with a credential': (_ercp_after('Alan Synthetic MD\n'), ERCP_CODES),
    'G-pa a provider line with a title': (_ercp_after('Dr. Alan Synthetic\n'), ERCP_CODES),
    'G-pa a provider line with an aside': (_ercp_after('Alan Synthetic MD (Gastroenterology)\n'), ERCP_CODES),
    'G-pa a page line': (_ercp_after('Page 2 of 3\n'), ERCP_CODES),
    'G-pa a bare procedure name': (_ercp_after('Endoscopic Retrograde Cholangiopancreatography\n'), ERCP_CODES),
    'G-pa a second entry of a procedure history': (
        _ercp('Endoscopic Retrograde Cholangiopancreatography\nThe bile duct was cleared of stones.\nEndoscopic '
              'Ultrasound\n'), ERCP_CODES),
    'G-pa control, a service heading that says more': (_ercp_after('Biliary ERCP Findings Today\n'), ERCP_CODES),
    'G-pa control, an act-word heading naming no service': (_ercp_after('Stent Exchange\n'), ERCP_CODES),
    'G-pa a line naming another occurrence': (_ercp_after('Previous Stent Management\n'), ERCP_CODES),
    # recorded limits: two headings in a row read as entries (the installed exclusion), and a title-case entry standing
    # alone between paragraphs reads as a heading (the one-cause hold stays, and now names the line)
    'L-pa two headings in a row': (_ercp_after('Today Stent Work\nStent Management\n'), ERCP_CODES),
    'L-pa a title-case entry standing as a heading': (
        _psh('Appendectomy in 1999.', '', 'Gallbladder Removal', 'Upper endoscopy with dilation was uncomplicated.'),
        (('99214', MDM, 'done'), ('43249', 'Upper endoscopy with dilation was uncomplicated.', 'not_done'))),
}


class CycleOneRowTests(SimpleTestCase):
    """The amendment's rows read through the stages: each code's outcome is the declared cycle-1 one (index 2 of
    [installed, b840ae756, cycle 1]); the texts and codes are the declared ones (sha256)."""

    def check(self, name):
        text, codes = R2_ROWS[name]
        row = R2_DECLARED[name]
        self.assertEqual(boot.sha256_text(text), row['text_sha256'], name)
        self.assertEqual([list(c) for c in codes], row['codes'], name)
        props = assess(text, [(code, [quote]) for code, quote, _ in codes])
        self.assertEqual({code: '/'.join(outcome(props[code])) for code, _, _ in codes},
                         {code: outcomes[2] for code, outcomes in row['outcomes'].items()}, name)

    def test_the_rows_are_the_declared_ones(self):
        self.assertEqual(sorted(R2_ROWS), sorted(R2_DECLARED))

    def test_f6_a_sub_heading_naming_an_earlier_occurrence_governs(self):  # kills pa-occurrence-governs
        self.check('F6 earlier echoendoscope sub-heading')
        self.check('F6 control, earlier EUS report excerpt sub-heading')

    def test_cts3_title_case_entries_of_a_surgical_history(self):  # 43249 excluded again, 99214 READY again
        self.check('CTS-3 PA-06 surgical history entries in title case')
        self.check('CTS-3 PA-07 control, lower-case entries')

    def test_cts3_provider_and_page_lines_in_a_surgical_history(self):
        self.check('CTS-3 PA-08 provider name line')
        self.check('CTS-3 PA-09 page header line')
        self.check('CTS-3 PA-10 control, the cited entry first')

    def test_cts3_procedure_name_facility_and_page_lines_opening_a_prior_procedure(self):
        self.check('CTS-3 PA3-00 control, the cited line under its heading')
        self.check('CTS-3 PA3-01 procedure-name line')
        self.check('CTS-3 PA3-02 facility line')
        self.check('CTS-3 PA3-03 page header line')

    def test_a_real_unread_heading_still_holds(self):  # kills pa-real-content-sentence
        self.check('G-pa control, a real unread heading')

    def test_the_sections_first_line_is_its_own_content(self):  # kills pa-real-first-line
        self.check('G-pa first line under the heading, after a blank line')

    def test_an_entry_followed_by_another_entry(self):  # kills pa-real-content
        self.check('G-pa an entry followed by another entry')

    def test_an_entry_under_another_entry_or_a_sentence_it_continues(self):  # kills pa-real-bounded-above
        self.check('G-pa an entry under another entry')
        self.check('G-pa a line continuing a sentence')

    def test_a_heading_under_a_field_line_stands(self):  # kills pa-real-bounded-field
        self.check('G-pa control, a heading under a field line')

    def test_facility_provider_and_page_lines(self):  # kill pa-name-facility, -credential, -title, -aside, -page
        for name in ('G-pa a facility line', 'G-pa a provider line with a credential', 'G-pa a provider line with a title',
                     'G-pa a provider line with an aside', 'G-pa a page line'):
            with self.subTest(name):
                self.check(name)

    def test_bare_procedure_names(self):  # kills pa-real-procedure-name
        self.check('G-pa a bare procedure name')
        self.check('G-pa a second entry of a procedure history')

    def test_headings_that_say_more_than_a_procedure_name(self):  # kill pa-procedure-only-words, pa-procedure-named
        self.check('G-pa control, a service heading that says more')
        self.check('G-pa control, an act-word heading naming no service')

    def test_a_line_naming_another_occurrence(self):  # kills pa-occurrence-governs
        self.check('G-pa a line naming another occurrence')

    def test_the_recorded_limits(self):
        self.check('L-pa two headings in a row')
        self.check('L-pa a title-case entry standing as a heading')
        text, codes = R2_ROWS['L-pa a title-case entry standing as a heading']
        p = assess(text, [(code, [quote]) for code, quote, _ in codes])['43249']
        self.assertIn('only past the line “Gallbladder Removal”', status_detail(p))  # the hold names its cause


class CycleOneWordsTests(SimpleTestCase):
    """CTS-4: the act path's one-cause hold says why, which is true of the document, in place of the inventory's
    act_missing words ("no endosonographic examination is documented as done in it"), false of h4-05."""

    def test_the_h4_05_counterfactual_says_why_it_is_held(self):  # kills pa-one-cause-hold-words
        text, codes = battery.CASES['S3h h4-05 counterfactual, EUS code citing the narrative']
        p = assess(text, [(code, [quote]) for code, quote, _ in codes])['43259']
        declared = R2['expected']['cts4']
        self.assertEqual('/'.join(outcome(p)), declared['outcome'])
        self.assertEqual(p.support['reason'], declared['support_reason'][1])
        asked = next(c for c in p.clarifications if c.fact == 'performed_status')
        self.assertEqual(asked.question, declared['question'][1])
        detail = status_detail(p)
        self.assertEqual(' '.join(asked.reason.split()), detail)
        straight = detail.replace('“', '"').replace('”', '"')
        for want in declared['detail_contains']:
            self.assertIn(want, straight)
        for unwanted in declared['detail_excludes']:
            self.assertNotIn(unwanted, straight)
        self.assertTrue(detail.startswith('The routing-era reading of the passage it cites reads it as historical only '
                                          'by its section: “A linear echoendoscope was introduced by mouth.”'))

    def read(self, text, quote):
        day = dt.date(2026, 10, 15)
        routing = detect.route(text, day)
        inventory = gi_services.build(text, service_date=day, routing=routing, context_facts={})
        found = reconcile.match('43259', inventory, 'gi.eus')
        pos = text.index(quote)
        old = checks.StatusOutcome('not_performed', checks.Reading(
            'historical', ('section: history (Prior Studies)',), 'evidence', quote, pos, pos + len(quote)))
        return found, old, day

    def tearDown(self):
        __import__('studio.jobs', fromlist=['x']).release_routing_caches()

    def test_the_hold_replaces_the_act_missing_words_only_for_one_cause(self):  # kills pa-one-cause-hold-only
        found, old, day = self.read(H405, N1)
        self.assertEqual(found.reason, 'act_missing')
        held = engine._pa_one_cause_hold(found, old, '43259', H405, day)
        self.assertEqual((held.state, held.reason), ('uncertain', 'readings_disagree'))
        self.assertEqual(held.question, 'Confirm whether 43259 was performed on the date of service.')
        self.assertIn(engine._PA_ONE_CAUSE, held.detail)
        self.assertIn('only past the line “Scope Passage and Views”', held.detail)
        # under the section's own heading the readers agree: nothing here to say, the match is returned as it is
        found, old, day = self.read(HEADED_405, N1)
        self.assertEqual(engine._second_reading(old, HEADED_405, day), '')
        self.assertIs(engine._pa_one_cause_hold(found, old, '43259', HEADED_405, day), found)

    def test_a_hold_decided_by_a_documented_act_keeps_its_words(self):  # kills pa-one-cause-hold-acts-here
        found, old, day = self.read(H405, N1)
        kinds = reconcile.catalogue.code_profile('43259').covers
        act = gi_services.Act(id='a-synthetic', service=found.service.id, kind=kinds[0], status='historical',
                              role='physician', evidence=(Span(old.decisive.start, old.decisive.end, N1),),
                              cues=('historical: in a history section',))
        with_act = dataclasses.replace(found, service=dataclasses.replace(found.service,
                                                                          acts=found.service.acts + (act,)))
        self.assertEqual(engine._acts_in_passage('43259', old.decisive, with_act.service), [act])
        self.assertTrue(engine._second_reading(old, H405, day).startswith(engine._PA_ONE_CAUSE))
        self.assertIs(engine._pa_one_cause_hold(with_act, old, '43259', H405, day), with_act)


class RealHeadingTests(SimpleTestCase):
    """The real-heading rule's predicates, read directly (F6, CTS-3)."""

    def test_name_and_page_lines(self):  # kill pa-name-page, -credential, -title, -facility, -aside
        for line in ('Page 2 of 3', 'Page 12', 'Alan Synthetic MD', 'Alan Synthetic, MD', 'Junia Haverkamp-Ode, DO',
                     'Alan Synthetic, PA-C', 'Dr. Alan Synthetic', 'Dr Alan Synthetic',
                     'Alan Synthetic MD (Gastroenterology)', 'Synthetic Regional Medical Center',
                     'Mercy Endoscopy Center', 'Northside Clinic', 'Synthetic Health System'):
            self.assertTrue(engine._pa_name_line(line), line)
        for line in ('Scope Passage and Views', 'Stent Management', 'Question to Answer', 'Earlier EUS Report Excerpt',
                     'Endosonographic Conclusion', 'Pages of Notes', 'Stent Exchange', 'Gallbladder Removal'):
            self.assertFalse(engine._pa_name_line(line), line)

    def test_bare_procedure_names(self):  # kill pa-real-procedure-name, pa-procedure-only-words, pa-procedure-named
        for line in ('Endoscopic Retrograde Cholangiopancreatography', 'Colonoscopy With Biopsy',
                     'Upper Endoscopy With Dilation', 'Endoscopic Ultrasound', 'Flexible Sigmoidoscopy'):
            self.assertTrue(engine._pa_procedure_name_line(line), line)
        for line in ('Biliary ERCP Findings Today', 'Colonoscopy Findings Today', 'Stent Exchange', 'Stent Management',
                     'Endosonographic Conclusion', 'Laparoscopic Cholecystectomy', 'Gallbladder Removal'):
            self.assertFalse(engine._pa_procedure_name_line(line), line)

    def test_bounded_above(self):  # kills pa-real-bounded-field
        for line in ('', 'Cholecystectomy in 2014.', 'Cholecystectomy: 2014', 'Is it tissue or mucin?'):
            self.assertTrue(engine._pa_bounded_above(line), line)
        for line in ('Gallbladder Removal', 'Cholecystectomy in 2014 and later the stent was placed by the',
                     'Prior Procedures', 'Prior Procedures:'):
            self.assertFalse(engine._pa_bounded_above(line), line)

    def test_content(self):  # kills pa-real-content-sentence
        for line in ('The biliary stent was exchanged.', 'Is it tissue or mucin?', 'Cholecystectomy: 2014',
                     '1. Stent exchanged', '* plastic stent', 'x' * 61):
            self.assertTrue(engine._pa_content(line), line)
        for line in ('Plastic Stent', 'Upper endoscopy with dilation', 'x' * 60):
            self.assertFalse(engine._pa_content(line), line)

    def test_the_unread_heading_found(self):
        unread = engine._pa_unread_heading
        self.assertEqual(unread(H405, H405.index(N1)), 'Scope Passage and Views')
        self.assertEqual(unread(HEADED_405, HEADED_405.index(N1)), '')
        for sub in ('What the Earlier Echoendoscope Showed', 'Earlier EUS Report Excerpt'):  # the occurrence governs
            text = _f6(sub)
            self.assertEqual(unread(text, text.index(N1)), '', sub)
        real = _ercp_after('Stent Management\n')
        self.assertEqual(unread(real, real.index(STENT)), 'Stent Management')
        first = _ercp('\nStent Management\n')
        self.assertEqual(unread(first, first.index(STENT)), '')
        self.assertEqual(unread(H405, H405.index('Pancreatic Endosonography')), '')  # before the first heading
        self.assertEqual(unread(H405, H405.index('Earlier EUS (this service)')), '')  # the heading's own first line

    def test_beyond_the_reach_read_it_fails_closed(self):  # kill pa-unread-far-lines, -far-chars, -far-floor
        unread = engine._pa_unread_heading
        lines = DOCS['note far']
        self.assertEqual(unread(lines, lines.index(EUS)), engine._PA_FAR)  # more than 200 lines back
        for prefix in ('', 'p' * 499):  # 45 lines of 500 characters: more than 20,000 characters back
            text = (B + ERCP + 'Prior Procedures\n' + ''.join('Earlier result ' + 'x' * 484 + '\n' for _ in range(45))
                    + prefix + STENT + '\n')
            pos = text.index(STENT)
            self.assertEqual(text[pos - sections.HEADING_REACH_CHARS] == '\n', bool(prefix))  # both alignments
            self.assertEqual(unread(text, pos), engine._PA_FAR, len(prefix))
        near = _ercp_after('Stent Management\n')  # the control: the heading within the reach
        self.assertNotEqual(unread(near, near.index(STENT)), engine._PA_FAR)
