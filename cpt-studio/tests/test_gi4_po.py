"""GI round 4, package PO: the second-review offer (validation/engine.py: _routing_agrees and its _po_ helpers).

An unresolved item the installed rule does not offer is offered - the flag only: a member still asks, once per revision
and date, and no stage sends anything (tests/test_gi4_po_state.py) - when routing does not contradict the
documented-service reading and the document's own head makes it today's procedure report: PO-1, routing reads the item's
family only silently (h4-02); PO-2, routing's not-today reading of the item's own passage comes only from a section that
reaches it across a heading-like line the layout does not read (h4-05). Every expectation here was declared before the
code (tests/fixtures/gi4/declarations/po.json): the regression replay's offers per member state, the H4 rows read with
their own and with an empty provider answer, and the guard rows, whose texts the declaration pins by sha256.

Each PO_MUTANTS entry removes one guard and is killed by a test below (H6, run against sealed copies by the harness's
mutant machinery; its anchors are checked here against this tree, so the registry cannot rot). Offline: nothing is sent
and no database is read. Every document is synthetic.
"""
import dataclasses
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery, boot, mutants, regression, replay
from studio.gi import detect, sections
from studio.gi import services as gi_services
from studio.types import Span
from studio.validation import engine, reconcile

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi4'
DECLARED = json.loads((FIXTURES / 'declarations' / 'po.json').read_text(encoding='utf-8'))
PIN = json.loads((FIXTURES / 'pins' / 'replay.json').read_text(encoding='utf-8'))
DOCS = regression.load_fixtures()
H402, H405 = DOCS['h4-02']['text'], DOCS['h4-05']['text']
B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
FILL = ''.join(f'Line {i} of the outside summary lists medications and allergies in detail.\n' for i in range(8))
COPIED = ('Colonoscopy at Mercy GI.\nCecum: normal.\nTerminal ileum: normal.\nThe entire colon was examined. A 10 mm polyp '
          'was removed with a hot snare.\n\nAssessment\nAdenoma history.\n')
CONCL = '\nEndosonographic Conclusion\n'
FILLER = ''.join(f'Filler sentence {i} repeats that the gland was seen well.\n' for i in range(210))
# (text, codes): the guard rows the declaration pins (codes: (code, quote); none = an empty provider answer)
ROWS = {
    'G-head clinic note, copied colonoscopy': (B + 'Hepatology Clinic Note\nDate of service: 10/20/2026\n\nSummary of '
                                               'outside records\nThe patient brought copies from Mercy GI.\n' + FILL
                                               + COPIED, ()),
    'G-around booking with head fields': (B + 'Endoscopy Booking\nDate of service: 10/20/2026\nEndoscopist: Synthetic '
                                          'Endoscopist, MD (fictional)\nSedation: propofol by CRNA, planned\n\nSummary of '
                                          'outside records\nThe patient brought copies from Mercy GI.\n' + FILL + COPIED,
                                          ()),
    'G-reach h4-05, 210 filler lines': (H405.replace(CONCL, '\n' + FILLER + CONCL), ()),
    'G-occurrence h4-05, previous summary line': (H405.replace(CONCL, '\nPrevious Endosonography Summary' + CONCL), ()),
    'G-contradiction h4-05, repeat EUS not done': (H405.replace('Repeat MRI with MRCP in 12 months.',
                                                                'Repeat MRI with MRCP in 12 months. A repeat EUS was not '
                                                                'performed.'), ()),
    'G-unread h4-05, directly headed HPI line': (H405.replace('\nPrior Studies\n', '\nHPI\nEndosonography of the '
                                                              'pancreas.\n\nPrior Studies\n', 1), ()),
    'G-evidence h4-02, repeat biopsies planned': (H402.replace(
        '2. Rectosigmoid inflammation of the same pattern; biopsied.',
        '2. Rectosigmoid inflammation of the same pattern; biopsied, and repeat biopsies are planned in six weeks.'),
        (('45330', 'Flexible sigmoidoscope'),)),
    'G-atleast P00160 runaway history, title only': (
        B + 'Surveillance Colonoscopy\nHensley Narrows Surgery Center (fictional)\nFacility category: ambulatory '
        'surgical center, POS 24\nProcedure date: October 13, 2026\nPatient: Petronella Szymanski-Abara (fictional), 64 '
        'years\nGastroenterologist: Lazare Sobczak-Muir, DO (fictional)\nSedation: propofol by Wynona Tarkington-Ezeh, '
        'CRNA (fictional)\nPrior Studies\nEarlier colonoscopy (this service): October 13, 2024 - two small polyps, '
        'removed by cold snare.\nWhy It Was Done\nSix kilograms of unintended weight loss over five months.\nObservations '
        'by Segment\nThe colonoscope was advanced to the cecum. Cold forceps biopsies were taken from the ascending '
        'colon.\nAt a Glance\n1. Biopsies taken; results to follow.\nPlan\nRepeat colonoscopy booked for November 4, '
        '2026.\nReport authenticated: Lazare Sobczak-Muir, DO (fictional), October 13, 2026 11:52\n', ()),
    'P-h4-02': (H402, ()),
    'P-h4-05': (H405, ()),
}
ENGINE = 'studio/validation/engine.py'
UNIT = 'unit:tests.test_gi4_po'
PO_MUTANTS = (
    mutants.Mutant('po-document-head', "PO: the document's head carries a procedure report's own fields", ENGINE,
                   '    return gi_sections.procedure_report_head(text) and not gi_sections.around_procedure_title(text)',
                   '    return not gi_sections.around_procedure_title(text)', UNIT),
    mutants.Mutant('po-document-around', 'PO: no head line is the title of a note written around a procedure', ENGINE,
                   '    return gi_sections.procedure_report_head(text) and not gi_sections.around_procedure_title(text)',
                   '    return gi_sections.procedure_report_head(text)', UNIT),
    mutants.Mutant('po-family-read', "PO: routing reads the item's family (never a vacuous reading)", ENGINE,
                   '    if not mentions or not _po_todays_procedure_report(text):',
                   '    if not _po_todays_procedure_report(text):', UNIT),
    mutants.Mutant('po-unreadable-passage', 'PO: a passage outside the text never reads as saying nothing', ENGINE,
                   '            return False\n        readings.append(', '            continue\n        readings.append(',
                   UNIT),
    mutants.Mutant('po1-family-silent', 'PO-1: every mention of the family is silent', ENGINE,
                   '    if all(_po_silent(m.status, m.cues) for m in mentions):  # PO-1', '    if True:  # PO-1', UNIT),
    mutants.Mutant('po1-evidence-says-nothing', "PO-1: no passage of the item reads as not today or doubted", ENGINE,
                   '        return all(_po_says_nothing(status, cues) for _, status, cues in readings)',
                   '        return True', UNIT),
    mutants.Mutant('po2-family-contradicts', 'PO-2: no mention of the family contradicts', ENGINE,
                   '        return False\n    runaway = [', '        continue\n    runaway = [', UNIT),
    mutants.Mutant('po2-at-least-one', "PO-2: at least one passage of the item is a runaway section's", ENGINE,
                   '    return any(runaway) and all(', '    return all(', UNIT),
    mutants.Mutant('po-says-nothing-worded', 'PO: a worded doubt says something', ENGINE,
                   '    return status == \'uncertain\' and bool(cues) and all(\n'
                   '        c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX, checks.SILENT_CUE_PREFIX))\n'
                   '        or c == UNESTABLISHED for c in cues)',
                   "    return status == 'uncertain'", UNIT),
    mutants.Mutant('po2-another-occasion-clean', "PO-2: another occasion's mention carries no doubt or denial", ENGINE,
                   '    return any(c.startswith(_PO_OWN_TIME) for c in cues) and all(\n'
                   '        c.startswith(_PO_OWN_TIME + (checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in '
                   'cues)',
                   '    return any(c.startswith(_PO_OWN_TIME) for c in cues)', UNIT),
    mutants.Mutant('po-runaway-section-only', 'PO-2: the not-today reading takes its time only from its section', ENGINE,
                   '            or not all(c.startswith((checks.SECTION_CUE_PREFIX, checks.PERFORMED_CUE_PREFIX)) for c in '
                   'cues) \\\n            or not any(c.startswith(checks.SECTION_CUE_PREFIX) for c in cues):',
                   '            or False:', UNIT),
    mutants.Mutant('po-runaway-within-reach', "PO-2: the section's heading lies within the helper's reach", ENGINE,
                   "    if lo < 0 or lo >= pos or pos - lo > gi_sections.HEADING_REACH_CHARS \\\n"
                   "            or text.count('\\n', lo, pos) > gi_sections.HEADING_REACH_LINES:",
                   '    if lo < 0 or lo >= pos:', UNIT),
    mutants.Mutant('po-runaway-unread-heading', 'PO-2: an unread heading-like line stands between heading and passage',
                   ENGINE,
                   '    return gi_sections.beyond_heading_reach(text, lay, pos) and not '
                   'gi_sections.under_another_occurrence(text, pos)',
                   '    return not gi_sections.under_another_occurrence(text, pos)', UNIT),
    mutants.Mutant('po-runaway-occurrence', 'PO-2: the nearest heading-like line names no other occurrence', ENGINE,
                   '    return gi_sections.beyond_heading_reach(text, lay, pos) and not '
                   'gi_sections.under_another_occurrence(text, pos)',
                   '    return gi_sections.beyond_heading_reach(text, lay, pos)', UNIT),
)


def offers_of(text, codes=(), user_values=None):
    """[family, act, reason, offered] per unresolved item, as the stages read the text (analyze child, the member's
    answer merged, assess child) with a synthetic provider answer: ``codes`` = ((code, exact quote), ...)."""
    m = battery.modules()
    user_values = user_values or {}
    document_facts, day, _ = m.jobs._analyze_child(text, user_values, 1000)
    facts = m.jobs._merged_facts(document_facts, user_values)
    context = m.jobs.context_facts(SimpleNamespace(facts=facts))
    response = battery.response(m, text, [(code, quote, '') for code, quote in codes])
    _, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context, response, m.Lookup([], {}),
                                     'succeeded', 'ok', ())
    m.jobs.release_routing_caches()
    return [[u['family'], u['act'] or '', u['reason'], bool(u['second_review'])]
            for u in result.completeness['unresolved_items']]


def declared(offers):
    return [[family, act, reason, po] for family, act, reason, _, po in offers]


class MutantRegistryTests(SimpleTestCase):
    def test_every_po_mutant_applies_exactly_once_and_names_its_guard(self):
        source = (boot.HARNESS_TREE / ENGINE).read_text(encoding='utf-8')
        for m in PO_MUTANTS:
            self.assertEqual(source.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
            self.assertTrue(m.guard and m.detector == UNIT, m.name)
        self.assertEqual(len({m.name for m in PO_MUTANTS}), len(PO_MUTANTS))
        self.assertFalse({m.name for m in PO_MUTANTS} & set(mutants.BY_NAME))


class RegressionOfferTests(SimpleTestCase):
    """H1's offers: h4-02 (PO-1) and h4-05 (PO-2) move as declared in every member state; no other document's do."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = replay.replay(DOCS)

    def offers(self, doc_id, label):
        return sorted([o['family'], o['reason'], bool(o['second_review'])]
                      for o in self.result['documents'][doc_id]['states'][label]['offers'])

    def test_the_declared_documents_offer_in_every_member_state(self):
        for doc_id in ('h4-02', 'h4-05'):
            want = DECLARED['replay'][doc_id]
            self.assertEqual(sorted(self.result['documents'][doc_id]['states']), sorted(want['states']), doc_id)
            for label in want['states']:
                self.assertEqual(self.offers(doc_id, label), sorted([f, r, po] for f, r, _, po in want['offers']),
                                 (doc_id, label))

    def test_no_other_document_moves(self):
        for doc_id in DECLARED['replay']['unchanged']:
            for label, state in PIN['documents'][doc_id]['states'].items():
                self.assertEqual(self.offers(doc_id, label), state['offers'], (doc_id, label))

    def test_the_offer_is_only_a_flag(self):
        """Nothing but the flag moves on the declared documents: the same items, questions and completeness."""
        for doc_id in ('h4-02', 'h4-05'):
            for label, state in PIN['documents'][doc_id]['states'].items():
                now = self.result['documents'][doc_id]['states'][label]
                self.assertEqual(sorted([o['family'], o['reason']] for o in now['offers']),
                                 sorted(o[:2] for o in state['offers']), (doc_id, label))
                self.assertEqual([now['completeness']['state'], now['completeness']['unresolved']],
                                 state['completeness'], (doc_id, label))
                self.assertEqual(sorted([q[0], q[1], q[2]] for q in now['clarifications']), state['questions'])


class OfferBatteryTests(SimpleTestCase):
    """The H4 rows read with their own and with an empty provider answer: only S3h's EUS moves (PO-2)."""

    def test_every_row_offers_as_declared(self):
        rows = DECLARED['offer_battery']['rows']
        self.assertEqual(sorted(rows), sorted(battery.CASES))
        for name, (text, codes) in battery.CASES.items():
            own = offers_of(text, [(code, quote) for code, quote, _ in codes])
            self.assertEqual(own, declared(rows[name]['own']), (name, 'own'))
            self.assertEqual(offers_of(text), declared(rows[name]['empty']), (name, 'empty'))


class GuardRowTests(SimpleTestCase):
    """Each guard's killing row offers nothing; the positive controls offer (the texts are pinned by the declaration)."""

    def check(self, name):
        text, codes = ROWS[name]
        row = DECLARED['guard_rows']['rows'][name]
        self.assertEqual(boot.sha256_text(text), row['text_sha256'], name)
        self.assertEqual([list(c) for c in codes], row['codes'], name)
        self.assertEqual(offers_of(text, codes), declared(row['offers']), name)

    def test_the_rows_are_the_declared_ones(self):
        self.assertEqual(sorted(ROWS), sorted(DECLARED['guard_rows']['rows']))

    def test_a_copied_procedure_in_a_note_without_a_procedure_head(self):  # kills po-document-head
        self.check('G-head clinic note, copied colonoscopy')

    def test_a_booking_note_whose_head_names_the_endoscopist(self):  # kills po-document-around
        self.check('G-around booking with head fields')

    def test_a_heading_beyond_the_reach_is_never_a_found_line(self):  # kills po-runaway-within-reach
        self.check('G-reach h4-05, 210 filler lines')

    def test_an_unread_line_naming_another_occurrence(self):  # kills po-runaway-occurrence
        self.check('G-occurrence h4-05, previous summary line')

    def test_a_denied_mention_of_the_family(self):  # kills po2-family-contradicts
        self.check('G-contradiction h4-05, repeat EUS not done')

    def test_a_directly_headed_not_today_mention(self):  # kills po-runaway-unread-heading
        self.check('G-unread h4-05, directly headed HPI line')

    def test_an_item_passage_read_as_planned(self):  # kills po1-evidence-says-nothing
        self.check('G-evidence h4-02, repeat biopsies planned')

    def test_evidence_only_silent_beside_another_occasions_mentions(self):  # kills po2-at-least-one, po1-family-silent
        self.check('G-atleast P00160 runaway history, title only')

    def test_the_positive_controls(self):
        self.check('P-h4-02')
        self.check('P-h4-05')


class RoutingAgreesUnitTests(SimpleTestCase):
    """_routing_agrees on real readings of a real text, with the item or routing's reading varied by hand."""

    def read(self, text, day):
        routing = detect.route(text, day)
        inventory = gi_services.build(text, service_date=day, routing=routing, context_facts={})
        unresolved, _, _ = reconcile.reconcile(inventory, [])
        return routing, inventory, unresolved

    def tearDown(self):
        __import__('studio.jobs', fromlist=['x']).release_routing_caches()

    def item(self, unresolved, family, act=''):
        return next(u for u in unresolved if u.family == family and u.act == act)

    def span(self, text, needle):
        start = text.index(needle)
        return Span(start, start + len(needle), needle)

    def test_a_family_routing_never_names_is_no_silent_reading(self):  # kills po-family-read
        routing, inventory, unresolved = self.read(H402, None)
        u = self.item(unresolved, 'gi.egd')  # no passage of its own: only the family reading can decide
        self.assertTrue(engine._routing_agrees(u, inventory, routing, H402, None))
        unnamed = dataclasses.replace(routing, findings=tuple(f for f in routing.findings if f.family != 'gi.egd'))
        self.assertFalse(engine._routing_agrees(u, inventory, unnamed, H402, None))

    def test_h405_offers_under_po2(self):
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        self.assertTrue(engine._routing_agrees(self.item(unresolved, 'gi.eus'), inventory, routing, H405, day))

    def test_an_item_passage_with_its_own_time_word_is_no_runaway_reading(self):  # kills po-runaway-section-only
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        u = self.item(unresolved, 'gi.eus')
        title, own = self.span(H405, 'Pancreatic Endosonography'), self.span(H405, 'earlier EUS')
        self.assertEqual(detect.status_for_span(H405, own.start, own.end, day), ('historical', ('historical: earlier',)))
        self.assertTrue(sections.beyond_heading_reach(H405, sections.layout(H405), own.start))
        self.assertFalse(engine._routing_agrees(dataclasses.replace(u, evidence=(title, own)), inventory, routing, H405,
                                                day))
        heading = self.span(H405, 'Endosonographic Conclusion')
        self.assertTrue(engine._routing_agrees(dataclasses.replace(u, evidence=(title, heading)), inventory, routing,
                                               H405, day))

    def test_a_passage_outside_the_text_never_reads_as_saying_nothing(self):  # kills po-unreadable-passage
        routing, inventory, unresolved = self.read(H402, None)
        u = self.item(unresolved, 'gi.egd')
        self.assertEqual(u.evidence, ())
        self.assertTrue(engine._routing_agrees(u, inventory, routing, H402, None))  # PO-1: family silent, no passage
        outside = Span(len(H402) + 5, len(H402) + 9, 'gone')
        self.assertFalse(engine._routing_agrees(dataclasses.replace(u, evidence=(outside,)), inventory, routing, H402,
                                                None))

    def test_a_doubted_mention_of_the_family_contradicts(self):
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        u = self.item(unresolved, 'gi.eus')

        def doubted(f):
            if f.family != 'gi.eus':
                return f
            first = dataclasses.replace(f.mentions[1], status='uncertain', cues=(detect.DOUBT_PREFIX + " 'not' in its "
                                                                                 'clause',))
            return dataclasses.replace(f, mentions=(f.mentions[0], first) + f.mentions[2:])
        changed = dataclasses.replace(routing, findings=tuple(doubted(f) for f in routing.findings))
        self.assertFalse(engine._routing_agrees(u, inventory, changed, H405, day))

    def test_another_occasions_mention_with_a_doubt_riding_along_contradicts(self):  # kills po2-another-occasion-clean
        day = dt.date(2026, 10, 15)
        routing, inventory, unresolved = self.read(H405, day)
        u = self.item(unresolved, 'gi.eus')
        eus = routing.finding('gi.eus')
        self.assertEqual(eus.mentions[3].cues, ('historical: earlier',))

        def with_cues(cues):
            mention = dataclasses.replace(eus.mentions[3], cues=cues)
            finding = dataclasses.replace(eus, mentions=eus.mentions[:3] + (mention,) + eus.mentions[4:])
            return dataclasses.replace(routing, findings=tuple(finding if f.family == 'gi.eus' else f
                                                               for f in routing.findings))
        self.assertTrue(engine._routing_agrees(u, inventory, with_cues(('historical: earlier',)), H405, day))
        self.assertFalse(engine._routing_agrees(u, inventory, with_cues(
            ('historical: earlier', detect.DOUBT_PREFIX + " 'not' in its clause")), H405, day))

    def test_the_installed_reasons_still_bound_the_offer(self):
        routing, inventory, unresolved = self.read(H402, None)
        u = self.item(unresolved, 'gi.egd')
        for reason in ('unsupported', 'coverage_unknown'):
            self.assertFalse(engine._routing_agrees(dataclasses.replace(u, reason=reason), inventory, routing, H402,
                                                    None))
        self.assertFalse(engine._routing_agrees(u, inventory, None, H402, None))


class HelperTests(SimpleTestCase):
    def test_another_occasion(self):
        self.assertTrue(engine._po_another_occasion(('historical: 2025-04-09 is before the service date',
                                                     'historical: Earlier')))
        self.assertTrue(engine._po_another_occasion(('planned: booked', 'section: plan (Plan)')))
        self.assertFalse(engine._po_another_occasion(('section: history (Prior Studies)',)))
        self.assertFalse(engine._po_another_occasion(('historical: earlier', 'negated: was not performed')))
        self.assertFalse(engine._po_another_occasion(()))

    def test_says_nothing(self):  # kills po-says-nothing-worded
        says = engine._po_says_nothing
        self.assertTrue(says('uncertain', (detect.SILENT,)))
        self.assertTrue(says('uncertain', ('performed: was advanced', 'section: indication (Indication)')))
        self.assertTrue(says('uncertain', ('section: procedure (Procedure)', detect.UNESTABLISHED)))
        self.assertFalse(says('uncertain', ("uncertain: unresolved negation 'defer' in its clause",)))
        self.assertFalse(says('uncertain', ('section: findings (Findings)', 'uncertain: the document denies this '
                                                                           'service (negated: No)')))
        self.assertFalse(says('uncertain', ('uncertain: versus',)))
        self.assertFalse(says('uncertain', ()))
        for status in ('historical', 'planned', 'negated', 'cancelled'):
            self.assertFalse(says(status, ('section: history (Prior Studies)',)), status)

    def test_silent_needs_a_cue(self):
        self.assertTrue(engine._po_silent('uncertain', (detect.SILENT,)))
        self.assertFalse(engine._po_silent('uncertain', ()))
        self.assertFalse(engine._po_silent('historical', (detect.SILENT,)))

    def test_section_only_across_an_unread_heading(self):
        runaway = engine._po_section_only_across_unread_heading
        section_only = ('section: history (Prior Studies)',)
        pos = H405.index('Endosonographic Conclusion')
        self.assertTrue(runaway(H405, pos, 'historical', section_only))
        self.assertTrue(runaway(H405, pos, 'historical', ('performed: was introduced',) + section_only))
        self.assertFalse(runaway(H405, pos, 'historical', ('historical: earlier',) + section_only))
        self.assertFalse(runaway(H405, pos, 'historical', ('performed: was introduced',)))
        self.assertFalse(runaway(H405, pos, 'negated', section_only))
        self.assertFalse(runaway(H405, pos, 'uncertain', section_only))
        self.assertFalse(runaway(H405, pos, 'historical', ()))
        direct = H405.index('Earlier EUS (this service)')  # right under "Prior Studies": no unread line between
        self.assertFalse(runaway(H405, direct, 'historical', section_only))
        title = H405.index('Pancreatic Endosonography')  # before the first heading
        self.assertFalse(runaway(H405, title, 'historical', section_only))

    def test_the_document_guard(self):
        self.assertTrue(engine._po_todays_procedure_report(H402))
        self.assertTrue(engine._po_todays_procedure_report(H405))
        self.assertFalse(engine._po_todays_procedure_report(ROWS['G-head clinic note, copied colonoscopy'][0]))
        self.assertFalse(engine._po_todays_procedure_report(ROWS['G-around booking with head fields'][0]))
