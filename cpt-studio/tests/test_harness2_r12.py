"""Refutation round 12, the narrow pass over round 11's repair commit (2153571ec..09ae39ae5): the findings it reproduced
(refute-harness-r12, verified in verify-harness-r12), on their own inputs.

- wording-1: round 11's clause named the inventory's status of the whole service as what the quoted words hold: "and
  reads in the quoted words an incomplete service under ERCP" beside a quoted duodenoscope reach the reading reads as
  performed, the ERCP's failure read in other passages. The clause now names a mention only with its own status, where
  the inventory gives the family's service the same one; otherwise only what makes the service missing is said.
- wording-4 (a false green): no pin held the clause's two stated rules - the first quote whose places name a reading is
  the entry's, and its passage the first of those places - so mutants that read only the first quote, or pointed the
  entry at the quote's first place, passed the whole suite.

wording-2 and wording-3 were not reproduced: the clause truly states the reading's own reading of the quoted mention (a
bare "endoscope" filed under its report part's family; a hedged, another physician's or plan line read as performed),
as services.inventory does, and those readings are the readers' recorded residuals, for the shared-reader repair. With no
participant configured the engine's result is unchanged (I1). Synthetic data only; nothing is sent.
"""
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect
from studio.gi import services as gi_services
from tests import test_harness2_pipeline as hp
from tests import test_harness2_r6_meaning as r6m
from tests import test_harness2_r7 as r7
from tests import test_harness2_r11 as r11
from tests.legacy_chain import applied

he = r11.he
ACK = r11.ACK
SVC34 = Path(__file__).resolve().parent / 'corpus' / 'services' / 'documents' / 'svc-34-ercp-failed-cannulation.txt'
SVC34_DAY = date(2026, 10, 24)
REACH = 'The duodenoscope reached the second portion of the duodenum without difficulty.'
CANNULATION = 'Biliary cannulation was attempted for about 25 minutes using a sphincterotome with a guidewire'
COLON_TOP = (r6m.HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory '
             'surgery center\nProcedure: Colonoscopy\n')
SIGMOID = 'The colonoscope was advanced to the sigmoid colon.'
STOPPED = COLON_TOP + SIGMOID + '\nThe procedure was terminated early because of patient discomfort.\n'
COMPLETED = COLON_TOP + r6m.CECUM + '\nImpression: Incomplete examination due to poor preparation.\n'
ALSO = 'An upper endoscopy was also performed.'
TOP = (r6m.HEAD + 'Procedure report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
       'center\n')
TWO_PLACES = TOP + 'History:\n' + ALSO + '\n\nProcedure: Colonoscopy and EGD\n' + r6m.CECUM + '\n' + ALSO + '\n'


def entry(result):
    (item,) = result.completeness['participant_services']
    return item


def located_in(text, day, start, end):
    rows = []
    gi_services.build(text, service_date=day, routing=detect.route(text, day),
                      context_facts=gi_context.extract_context(text), pages=(), located=rows)
    return [row for row in rows if start <= row[4] and row[5] <= end]


class MentionOwnStatusTests(SimpleTestCase):
    """wording-1: a mention read as performed, of a service the inventory reads as incomplete from other passages, is
    never said to be an incomplete service in the quoted words."""

    def assert_fallback(self, result, label, quote):
        item = entry(result)
        self.assertEqual((item['read_as'], item['read_in']), ('', ''))
        self.assertEqual(item['reason'], f'Astra reads a performed {label} {r7.NOT_READ} (“{quote}”)')
        self.assertNotIn('incomplete service', next(c for c in result.encounter_checks
                                                    if c.id == 'participants.services').detail)

    def test_wording_1_a_failed_ercp_s_reach(self):
        text = SVC34.read_text(encoding='utf-8')
        start = text.index(REACH)
        self.assertEqual([(row[0], row[1], row[3]) for row in located_in(text, SVC34_DAY, start, start + len(REACH))],
                         [('instrument', 'gi.ercp', 'performed')])
        result = r11.on_its_day(text, SVC34_DAY, he.corti(('43260', he.span(text, CANNULATION))),
                                [he.read('astra', [he.code(text, '43260', CANNULATION)],
                                         services=[he.service(text, 'egd', REACH)])])
        self.assertIn(('gi.ercp', 'incomplete'), [(s['family'], s['status']) for s in result.services['services']])
        self.assert_fallback(result, 'upper endoscopy', REACH)

    def test_wording_1_a_stopped_colonoscopy_s_procedure_line_and_a_completed_line(self):
        for text, corti, quote in ((STOPPED, SIGMOID, 'Procedure: Colonoscopy'), (COMPLETED, r6m.CECUM, r6m.CECUM)):
            with self.subTest(quote):
                result = he.run(text, he.corti(('45378', he.span(text, corti))),
                                [he.read('astra', [he.code(text, '45378', corti)],
                                         services=[he.service(text, 'flexible_sigmoidoscopy', quote)])])
                self.assertEqual([(s['family'], s['status']) for s in result.services['services']],
                                 [('gi.colonoscopy', 'incomplete')])
                self.assert_fallback(result, 'flexible sigmoidoscopy', quote)


class InArmRulesTests(SimpleTestCase):
    """wording-4: the clause's first quote, and its passage the first place, that names a reading."""

    def test_wording_4_every_quote_is_read_in_turn(self):
        """A banding line, which names no service, then the transnasal esophagoscopy report's title."""
        text = r11.TNE + r7.BANDED + '\n'
        result = he.run(text, he.corti(('43197', he.span(text, r11.EXAM))),
                        [he.read('astra', [he.code(text, '43197', r11.EXAM)],
                                 services=[he.service(text, 'other_gi', r7.BANDED, r11.TITLE)])])
        item = entry(result)
        self.assertEqual((item['quote'], item['read_in']), (r11.TITLE, r11.UPPER))
        self.assertEqual((item['start'], item['end']), (text.index(r11.TITLE), text.index(r11.TITLE) + len(r11.TITLE)))

    def test_wording_4_the_place_whose_reading_is_named(self):
        """One quote found twice: under History, read as historical, and in today's narrative, read as performed. The
        entry's passage is the later place, whose reading the reason names."""
        first, last = TWO_PLACES.index(ALSO), TWO_PLACES.rindex(ALSO)
        self.assertNotEqual(first, last)
        self.assertEqual([row[3] for row in located_in(TWO_PLACES, he.DAY, first, first + len(ALSO))], ['historical'])
        self.assertEqual([row[3] for row in located_in(TWO_PLACES, he.DAY, last, last + len(ALSO))], ['performed'])
        result = he.run(TWO_PLACES, he.corti(('45378', he.span(TWO_PLACES, r6m.CECUM))),
                        [he.read('astra', [he.code(TWO_PLACES, '45378', r6m.CECUM)],
                                 services=[he.service(TWO_PLACES, 'eus', ALSO)])])
        item = entry(result)
        self.assertEqual(item['read_in'], r11.UPPER)
        self.assertEqual((item['start'], item['end']), (last, last + len(ALSO)))


@applied
class MentionOwnStatusPipelineTests(r6m.MeaningCase):
    def test_wording_1_on_the_reviewed_report(self):
        """svc-34, on the reviewed report a reviewer signs, beside the approved 43260."""
        text = SVC34.read_text(encoding='utf-8')
        services = [('u1', 'egd', 'performed', REACH)]
        encounter_id = self.scenario(text, [('43260', CANNULATION)],
                                     astra=hp.reading(codes=[('43260', CANNULATION)], services=services))
        detail = self.detail(encounter_id)
        said = f'Astra reads a performed upper endoscopy {r7.NOT_READ} (“{REACH}”)'
        self.assertIn(said, detail['coding']['statement'])
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '43260']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        self.assertTrue(self.detail(encounter_id)['readiness']['reviewed'])
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind):
                report = self.download(encounter_id, kind)
                self.assertIn(said, report)
                self.assertNotIn('an incomplete service under ERCP', report)
