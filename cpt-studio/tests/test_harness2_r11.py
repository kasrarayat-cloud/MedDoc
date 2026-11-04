"""Refutation round 11, the narrow pass over round 10's repair commit (2413020ff..2153571ec): the findings it reproduced
(refute-harness-r11, each verified in verify-harness-r11), on their own inputs.

- wording-1 (a regression in round 10's wording-2 repair): where no quote named a reading, the reason said only that the
  documented-service reading reads no performed service of the participant's kind - beside a quote the reading itself
  files under another family, as performed: a transnasal esophagoscopy report's title, a POEM or an esophagoscopy
  procedure line, a PEG line, each quoted as another GI service. The reason now also says what the reading reads as
  done in the quoted words, by that family's own label, and the participants.services check says it too. A not-done
  reading of the participant's own kind is still named first.
- wording-2 (from round 6's negation-5 repair): an instrument read as not done was named by its family's kind - "the
  upper endoscopy as negated" beside the inventory's negated esophagoscopy, its cancelled POEM or its cancelled PEG. An
  instrument names no kind of its own, so it is never named; the reason falls back.
- page-1 to page-4: round 10's piece titles were right, and mutants that undo them passed every pin. Each shape is pinned
  here through the pipeline, Corti alone, and in the `// refutation round 11` block of tests/frontend/app.test.cjs: a
  documented service's passage and an unchecked support's passage in one piece only, a split highlight after astral
  characters, a passage that ends exactly where the next piece begins, and two codes that each hold only a passage that
  does not show their act.

With no participant configured the engine's result is unchanged (I1). Synthetic data only; nothing is sent.
"""
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio import models, review
from studio.gi import context as gi_context
from studio.gi import detect
from studio.types import NormalizedResponse
from studio.validation.engine import assess
from tests import test_harness2_pipeline as hp
from tests import test_harness2_r6_meaning as r6m
from tests import test_harness2_r7 as r7
from tests import test_harness2_r8 as r8
from tests import test_harness2_r9 as r9

he = r9.he
ACK = review.ACKNOWLEDGEMENTS['human']
UPPER = 'a performed service under Upper GI endoscopy (EGD, esophagoscopy, POEM)'
TOPX = hp.HEAD + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
TITLE = 'Transnasal esophagoscopy report (fictional)'
EXAM = 'The esophagus was examined to the gastroesophageal junction and was normal.'
TNE = TOPX + TITLE + '\n' + EXAM + '\n'
CORPUS = Path(__file__).resolve().parent / 'corpus' / 'services' / 'documents'
# (the committed corpus document, its date of service, the procedure line quoted, Corti's code and its passage)
PROCEDURE_LINES = (
    ('svc-17-poem.txt', date(2026, 10, 22), 'PROCEDURE: Peroral endoscopic myotomy (POEM), anterior approach.', '43497',
     '4. Myotomy: Selective circular muscle myotomy from 33 cm to 2.5 cm below the gastroesophageal junction, 9.5 cm '
     'total.'),
    ('svc-14-esophagoscopy-stricture-not-traversed.txt', date(2026, 10, 21),
     'PROCEDURE PERFORMED: Flexible transoral esophagoscopy with biopsy.', '43202',
     'Eight cold forceps samples were taken from the mass at 33 to 35 cm and placed in a single jar.'),
)
UPPER_DONE = 'An upper endoscopy was performed to the second portion of the duodenum.'
MANOMETRY_NOT = 'Esophageal manometry was not performed.'
# (the line negating the service, the instrument line quoted) - wording-2's three variants
INSTRUMENT_LINES = (
    ('No transnasal esophagoscopy was performed today.', 'The ultrathin gastroscope was not inserted.'),
    ('The peroral endoscopic myotomy was cancelled.', 'Insertion of the gastroscope was cancelled.'),
    ('The PEG placement was cancelled.', 'Insertion of the gastroscope was cancelled.'),
)


def entry(result):
    (item,) = result.completeness['participant_services']
    return item


def services_check(result):
    return next(c for c in result.encounter_checks if c.id == 'participants.services')


def on_its_day(text, day, codes, participants):
    """tests.test_harness_engine.run with the document's own date of service."""
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                  normalized=NormalizedResponse('corti', 'test@1', tuple(codes)), reference=he.REFERENCE,
                  service_date=day, provider_status='succeeded', participants=tuple(participants))


def filed(label, status, quote, read_in, participant='Astra'):
    """The reason where the reading reads a service in the quoted words as done, under another family."""
    return (f'{participant} reads {status} {label} {r7.NOT_READ}, and reads in the quoted words {read_in} '
            f'(“{quote}”)')


def filed_check(label, quote, read_in):
    return (f'Astra reads a performed {label} (“{quote}”), where the documented-service reading reads in the quoted '
            f'words {read_in}. The documented-service reading reads no performed service of that kind, so coding '
            'completeness is incomplete.')


class FiledUnderAnotherFamilyTests(SimpleTestCase):
    """wording-1: a quote the reading itself files under another family, as done, is said to be read so."""

    def assert_filed(self, result, quote, label='other GI service', read_in=UPPER):
        item = entry(result)
        self.assertEqual((item['read_as'], item['read_in'], item['quote']), ('', read_in, quote))
        self.assertEqual(item['reason'], filed(label, 'a performed', quote, read_in))
        self.assertEqual(services_check(result).detail, filed_check(label, quote, read_in))
        self.assertEqual(result.completeness['state'], 'incomplete')  # the safety net stays
        return item

    def test_wording_1_a_transnasal_esophagoscopy_report_s_title(self):
        result = he.run(TNE, he.corti(('43197', he.span(TNE, EXAM))),
                        [he.read('astra', [he.code(TNE, '43197', EXAM)], services=[he.service(TNE, 'other_gi', TITLE)])])
        self.assertEqual([(s['family'], s['kind'], s['status']) for s in result.services['services']],
                         [('gi.egd', 'esophagoscopy', 'performed')])
        self.assert_filed(result, TITLE)

    def test_wording_1_the_corpus_poem_and_esophagoscopy_procedure_lines(self):
        for name, day, quote, value, anchor in PROCEDURE_LINES:
            with self.subTest(name):
                text = (CORPUS / name).read_text(encoding='utf-8')
                result = on_its_day(text, day, he.corti((value, he.span(text, anchor))),
                                    [he.read('astra', [he.code(text, value, anchor)],
                                             services=[he.service(text, 'other_gi', quote)])])
                self.assertIn('gi.egd', {s['family'] for s in result.services['services']
                                         if s['status'] == 'performed'})
                self.assert_filed(result, quote)

    def test_wording_1_a_peg_procedure_note(self):
        """r9's PEG note (moved there by this round): the PEG line is a service mention read as performed."""
        result = r9.engine(r9.PEG_NOTE, r8.PEG_PLACED, head_code='43246', anchor=r6m.D2, head_family='egd',
                           corti_code=[('43246', r6m.D2)])
        self.assert_filed(result, r8.PEG_PLACED)

    def test_wording_1_a_service_the_inventory_reads_as_incomplete(self):
        """A colonoscopy stopped short: the inventory reads the service as incomplete and the quoted reach as a
        performed mention. Moved by refutation round 12 (wording-1): the status named is the mention's own, never the
        whole service's, and the two differ here, so nothing is named and only what makes the service missing is said
        (it was "and reads in the quoted words an incomplete service under Colonoscopy", the incompleteness read in
        the stop sentence, another passage)."""
        reach = 'The colonoscope was advanced to the transverse colon.'
        text = (r6m.HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory '
                'surgery center\nProcedure: Colonoscopy\n' + reach + '\nThe examination was incomplete due to poor '
                'preparation.\n')
        result = he.run(text, he.corti(('45378', he.span(text, reach))),
                        [he.read('astra', [he.code(text, '45378', reach)], services=[he.service(text, 'eus', reach)])])
        self.assertEqual([(s['family'], s['status']) for s in result.services['services']],
                         [('gi.colonoscopy', 'incomplete')])
        item = entry(result)
        self.assertEqual((item['read_as'], item['read_in']), ('', ''))
        self.assertEqual(item['reason'], f'Astra reads a performed endoscopic ultrasound {r7.NOT_READ} (“{reach}”)')

    def test_a_not_done_reading_of_the_participant_s_own_kind_is_named_first(self):
        """Another GI service quoting a performed upper endoscopy and a manometry not performed: the manometry's own
        not-done reading is named, beside its line, in either order - never the upper endoscopy's."""
        text = r6m.doc(r6m.COLON, UPPER_DONE, MANOMETRY_NOT)
        for quotes in ((UPPER_DONE, MANOMETRY_NOT), (MANOMETRY_NOT, UPPER_DONE)):
            with self.subTest(first=quotes[0]):
                result = he.run(text, he.corti(('45378', he.span(text, r6m.CECUM))),
                                [he.read('astra', [he.code(text, '45378', r6m.CECUM)],
                                         services=[he.service(text, 'colonoscopy', r6m.CECUM),
                                                   he.service(text, 'other_gi', *quotes)])])
                item = entry(result)
                self.assertEqual((item['read_as'], item['read_in'], item['quote']),
                                 ('the manometry as negated', '', MANOMETRY_NOT))

    def test_a_quote_naming_no_service_keeps_the_fallback_alone(self):
        """The control: an act's words name no service, so only what makes the service missing is said."""
        text = r6m.doc(r6m.COLON, r7.BANDED)
        item = entry(r9.engine(text, r7.BANDED))
        self.assertEqual((item['read_as'], item['read_in']), ('', ''))
        self.assertEqual(item['reason'], f'Astra reads a performed other GI service {r7.NOT_READ} (“{r7.BANDED}”)')

    def test_a_service_named_in_the_quote_as_historical_is_never_said_to_be_done(self):
        """A quoted line that names another family's service as done before today: the reading reads that mention as
        historical, so nothing is said to be done in it, whatever the inventory reads elsewhere."""
        earlier = 'An upper endoscopy was performed in 2019.'
        text = r6m.doc(r6m.COLON, UPPER_DONE, earlier)
        item = entry(r9.engine(text, earlier, family='eus'))
        self.assertEqual((item['read_as'], item['read_in']), ('', ''))
        self.assertNotIn('Upper GI endoscopy', item['reason'])


class InstrumentIsNeverNamedTests(SimpleTestCase):
    """wording-2: an instrument names no kind of its own, so its not-done reading is never named."""

    def test_wording_2_an_instrument_beside_an_esophagoscopy_a_poem_or_a_peg_not_done(self):
        for line, instrument in INSTRUMENT_LINES:
            with self.subTest(line):
                text = r6m.doc(r6m.COLON, line, instrument)
                result = he.run(text, he.corti(('45378', he.span(text, r6m.CECUM))),
                                [he.read('astra', [he.code(text, '45378', r6m.CECUM)],
                                         services=[he.service(text, 'colonoscopy', r6m.CECUM),
                                                   he.service(text, 'egd', instrument)])])
                item = entry(result)
                self.assertEqual((item['read_as'], item['read_in']), ('', ''))
                self.assertEqual(item['reason'], f'Astra reads a performed upper endoscopy {r7.NOT_READ} '
                                                 f'(“{instrument}”)')
                self.assertNotIn('the upper endoscopy as', services_check(result).detail)

    def test_the_service_s_own_name_is_still_named_by_its_own_kind(self):
        """The control: quoting the esophagoscopy line itself names it."""
        line, instrument = INSTRUMENT_LINES[0]
        text = r6m.doc(r6m.COLON, line, instrument)
        result = he.run(text, he.corti(('45378', he.span(text, r6m.CECUM))),
                        [he.read('astra', [he.code(text, '45378', r6m.CECUM)],
                                 services=[he.service(text, 'colonoscopy', r6m.CECUM), he.service(text, 'egd', line)])])
        self.assertEqual(entry(result)['read_as'], 'the esophagoscopy as negated')


class FiledUnderAnotherFamilyPipelineTests(r6m.MeaningCase):
    def setUp(self):
        super().setUp()
        pfs = models.ReferenceSource.objects.get(key=hp.PFS_KEY)
        mue = models.ReferenceSource.objects.get(key=hp.MUE_KEY)
        models.ReferenceCodeFact.objects.create(source=pfs, code='43197', facts=r6m.BASE)
        models.ReferenceCodeFact.objects.create(source=mue, code='43197', facts=hp.MUE_ROW)

    def test_wording_1_on_the_reviewed_report(self):
        """wording-1 (a), on the reviewed report a reviewer signs, beside the approved 43197 whose source passage is
        that very title."""
        services = [('u1', 'other_gi', 'performed', TITLE)]
        encounter_id = self.scenario(TNE, [('43197', EXAM)], astra=hp.reading(codes=[('43197', EXAM)],
                                                                               services=services))
        detail = self.detail(encounter_id)
        said = filed('other GI service', 'a performed', TITLE, UPPER)
        self.assertIn(said, detail['coding']['statement'])
        (item,) = [p for p in r6m.proposals(detail) if p['code'] == '43197']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        self.assertTrue(self.detail(encounter_id)['readiness']['reviewed'])
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind):
                report = self.download(encounter_id, kind)
                self.assertIn(said, report)
                self.assertNotIn(f'{r7.NOT_READ} (“{TITLE}”)', report)

    def test_wording_2_on_the_reviewed_report(self):
        line, instrument = INSTRUMENT_LINES[0]
        text = r6m.doc(r6m.COLON, line, instrument)
        services = [r6m.colon_service(r6m.CECUM), ('u1', 'egd', 'performed', instrument)]
        encounter_id = self.scenario(text, [('45378', r6m.CECUM)],
                                     astra=hp.reading(codes=[('45378', r6m.CECUM)], services=services))
        (item,) = [p for p in r6m.proposals(self.detail(encounter_id)) if p['code'] == '45378']
        made = self.post(f'/api/encounters/{encounter_id}/decisions',
                         {'proposal_id': item['id'], 'action': 'approve', 'acknowledgement': ACK,
                          'note': 'Synthetic review.'})
        self.assertEqual(made.status_code, 201, made.content)
        report = self.download(encounter_id, 'reviewed')
        self.assertIn(f'Astra reads a performed upper endoscopy {r7.NOT_READ} (“{instrument}”)', report)
        self.assertNotIn('reads the upper endoscopy as negated', report)


# --- page-1 to page-4: what each piece of a highlight holds, Corti alone --------------------------------------------

SEEN, SNARED, BIOPSIES = r6m.SEEN, r7.SNARED, r9.BIOPSIES
TAIL = 'the examination was completed.'
NOT_THE_ACT = 'Passage the provider cited for {codes}, which does not show the coded act'
HOLDING = r9.HOLDING


class PieceHoldsTests(r6m.MeaningCase):
    def titles(self, detail):
        return {text: title for _, title, text in r6m.marks(detail)}

    def test_page_1_a_documented_service_s_passage_in_one_piece_only(self):
        """page-1 (b): C6 with a blank line after its cecum line. 45380's documented-service source passage is that
        line; 43251's passage runs across the blank line. The biopsy piece holds no documented-service passage."""
        # (P2 READ-HOLD, R8 D4: C6's unplaceable biopsy line is held now; its placed twin keeps the own-passage release
        # this title reads - tests/test_harness2_r6_meaning.py C6_PLACED)
        text = r6m.C6_PLACED.replace(f'{TAIL}\n', f'{TAIL}\n\n', 1)
        self.assertNotEqual(text, r6m.C6_PLACED)
        titles = self.titles(self.corti_alone(text, [('45380', r6m.PLACED_COL_BX),
                                                     ('43251', f'{TAIL}\n\n{r6m.PLACED_COL_BX}')]))
        self.assertEqual(titles[r6m.PLACED_COL_BX], 'Evidence for 43251, 45380')
        self.assertEqual(titles[TAIL], 'Evidence for 43251; Passage of the documented service for 45380')

    def test_page_1_an_unchecked_support_s_passage_in_one_piece_only(self):
        """page-1 (a): a blank line after the cecum line; 45380 quotes across it, and its support was not checked."""
        detail = self.corti_alone(r6m.COLON + '\n' + SEEN + '\n', [('45380', f'{TAIL}\n\n{SEEN}')])
        titles = self.titles(detail)
        self.assertEqual(titles[SEEN], 'Evidence for 45380')
        self.assertEqual(titles[TAIL], 'Evidence for 45380; Passage of the documented service for 45380, not checked '
                                       'against the coded act')

    def test_page_2_a_split_highlight_after_astral_characters(self):
        """page-2: round 10's own across shape, with three astral characters in the Procedure line, so a passage of
        the highlight begins in its second piece."""
        head = r6m.COLON.replace('Procedure: Colonoscopy\n', 'Procedure: Colonoscopy' + '\U0001F52C' * 3 + '\n', 1)
        self.assertNotEqual(head, r6m.COLON)
        detail = self.corti_alone(r6m.doc(head, SEEN, '', f'{SNARED} {BIOPSIES}'),
                                  [('45385', SEEN), ('45385', SNARED), ('45380', f'{SEEN}\n\n{SNARED} {BIOPSIES}')])
        self.assertEqual(self.titles(detail), {
            SEEN: f'Evidence for 45380; {NOT_THE_ACT.format(codes="45385")}',
            f'{SNARED} {BIOPSIES}': 'Evidence for 45380, 45385'})

    def test_page_3_a_passage_that_ends_where_the_next_piece_begins(self):
        """page-3: 45385 quotes the "was seen" line with its paragraph break, which no piece draws, and the passage
        through the snare line: the snare piece holds no character of the first."""
        detail = self.corti_alone(r6m.doc(r6m.COLON, SEEN, '', SNARED), [('45385', f'{SEEN}\n\n'),
                                                                         ('45385', f'{SEEN}\n\n{SNARED}')])
        self.assertEqual(self.titles(detail), {SEEN: HOLDING.format(code='45385'), SNARED: 'Evidence for 45385'})

    def test_page_4_two_codes_each_holding_only_a_passage_that_does_not_show_its_act(self):
        first = f'{SEEN} The mucosa was otherwise normal.'
        detail = self.corti_alone(r6m.doc(r6m.COLON, first, SNARED, BIOPSIES),
                                  [('45385', SEEN), ('45385', SNARED), ('45380', first), ('45380', BIOPSIES)])
        self.assertEqual(self.titles(detail)[first], NOT_THE_ACT.format(codes='45385, 45380'))


class ReadInGateTests(SimpleTestCase):
    """_Harness._read_in's gates on a recorded reading: a mention read as done, inside the quote's place, of a family
    whose service the inventory reads as done too - named by the inventory's status of that service."""

    def read_in(self, located, inventory_status, families=('gi.capsule',), span=(0, 30)):
        from types import SimpleNamespace
        from studio.validation.engine import _Harness
        harness = SimpleNamespace(located=tuple(located))
        inventory = SimpleNamespace(services=[SimpleNamespace(family='gi.egd', status=inventory_status)])
        return _Harness._read_in(harness, (SimpleNamespace(start=span[0], end=span[1]),), families, inventory)

    def test_the_inventory_s_own_status_of_the_family_s_service(self):
        """Moved by refutation round 12 (wording-1): a mention is named only with its own status, where the inventory
        gives the family's service the same one (a performed mention of a service read as incomplete had been named
        "an incomplete service")."""
        mention = ('service', 'gi.egd', 'egd', 'performed', 10, 20)
        self.assertEqual(self.read_in([mention], 'performed'), UPPER)
        for status in ('incomplete', 'negated', 'cancelled', 'planned', 'historical', 'uncertain'):
            with self.subTest(status):
                self.assertEqual(self.read_in([mention], status), '')
        incomplete = ('service', 'gi.egd', 'egd', 'incomplete', 10, 20)
        self.assertEqual(self.read_in([incomplete], 'incomplete'),
                         'an incomplete service under Upper GI endoscopy (EGD, esophagoscopy, POEM)')
        self.assertEqual(self.read_in([incomplete], 'performed'), '')

    def test_only_a_mention_read_as_done_inside_the_place(self):
        for mention in (('service', 'gi.egd', 'egd', 'historical', 10, 20),
                        ('service', 'gi.egd', 'egd', 'uncertain', 10, 20),
                        ('service', 'gi.egd', 'egd', 'performed', 25, 35),
                        ('instrument', 'gi.egd', 'egd', 'performed', 31, 40)):
            with self.subTest(mention):
                self.assertEqual(self.read_in([mention], 'performed'), '')
        # an instrument is a mention like a name here: it is named by its family's label, never a kind
        self.assertEqual(self.read_in([('instrument', 'gi.egd', 'egd', 'performed', 10, 20)], 'performed'), UPPER)
        # each family once
        self.assertEqual(self.read_in([('service', 'gi.egd', 'esophagoscopy', 'performed', 2, 8),
                                       ('instrument', 'gi.egd', 'egd', 'performed', 10, 20)], 'performed'), UPPER)
