"""GI round 3, fix round 1, owner "inventory" (session 7c8d38da): the independent refutation's inventory findings.

The refutation of the integrated candidate (543bae72a) found the documented-service inventory reading these shapes wrong
by the source. Each is fixed by its rule in studio/gi/services.py or studio/validation/reconcile.py ("gi3 fix round 1
(<finding>)"), and each test below holds the reviewer's own input (tests/fixtures/gi3/fix1_inventory, synthetic) to the
source-correct output, beside a control the fix must not change:

- INV-1: a table row of another occurrence - dated by any other day, month or year, labelled "Previous ...", or under a
  heading of another time or a review of records - states that occurrence's acts, never today's.
- INV-2: a table in a section routing's layout reads as a plan states planned acts, even inside a titled report.
- INV-3: a table answer naming its own instrument states that act and leaves the column's own act in doubt; a "Tissue
  sampled: Yes" beside tissue another act took leaves a forceps biopsy in doubt; a table act's technique follows its
  own kind.
- INV-4: a site the mention before an act takes as its object is that mention's; an act records its own segment's
  sites; "forceps biopsies" is one mention.
- INV-5: a stent placement or removal naming its duct is part of an exchange whose own words put it in that duct
  system; the instrument after the place a stent came out of is the removal's.
- INV-6: a denial or cancellation of another act, of which this act is only the time ("after the polypectomy"), never
  denies this act.
- INV-7: a labelled line naming the endoscopist, or denying the separate billing, attributes nothing.
- INV-8: a lesion named right after an act as its object is that act's.
- INV-9: a measure "at" introduces is a position, never a lesion's size.
- INV-10: a span's dates are found by bisection (the header-table loop reads each row in constant work).
- STATE-4: a tattoo or a submucosal injection never takes a snare's or forceps' technique; an act a procedure line or a
  summary table's row restates is the act the body states, listed once.
- EXT-2 (the inventory's half): a negation inside a relative clause is about its head noun, never the act.

Every document is synthetic. No network, no database.
"""
import bisect
import random
import time
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation import reconcile
from studio.validation.engine import assess

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3' / 'fix1_inventory'
CORPUS = Path(__file__).resolve().parent / 'corpus' / 'gi3_inventory' / 'texts'
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
NOT_READY = ('needs_clarification', 'excluded')


def fixture(name: str) -> str:
    return (FIXTURES / f'{name}.txt').read_text(encoding='utf-8')


def corpus(name: str) -> str:
    return (CORPUS / f'{name}.txt').read_text(encoding='utf-8')


def day_of(text: str):
    fact = gi_context.extract_context(text)['service_date']
    return date.fromisoformat(fact.value) if fact.value and fact.origin in ('document', 'user') else None


def read(text: str):
    """The inventory as the assess stage reads it: the context's service date, routing, then the inventory."""
    day = day_of(text)
    return services.build(text, service_date=day, routing=detect.route(text, day),
                          context_facts=gi_context.extract_context(text))


def acts(inv, family, kind=None, statuses=None):
    return [a for s in inv.services if s.family == family for a in s.acts
            if (kind is None or a.kind == kind) and (statuses is None or a.status in statuses)]


def described(inv, family):
    return [reconcile.describe_act(s, a) for s in inv.services if s.family == family for a in s.acts
            if a.status == 'performed']


def unresolved_kinds(inv, codes):
    unresolved, bundled, _ = reconcile.reconcile(inv, codes, procedure_day=True)
    return [(u.family, u.act) for u in unresolved], [b.act for b in bundled]


def assess_picks(text: str, picks):
    """The engine's result for provider-selected (code, quote) picks against an empty reference."""
    codes = []
    for index, (code, quote) in enumerate(picks):
        start = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(quote), quote, True),), index=index))
    day = day_of(text)
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def status(text: str, code: str, quote: str) -> str:
    return next(p for p in assess_picks(text, [(code, quote)]).proposals if p.code == code).status


def colonoscopy(findings: str, after: str = '') -> str:
    return (HEAD + 'Patient: Wren Fictional\nDate of service: 2026-10-16\nColonoscopy report\nFindings: The colonoscope '
            'was advanced to the cecum. ' + findings + '\n' + after)


class OtherOccurrenceRowTests(SimpleTestCase):
    """INV-1: a row of another occurrence states that occurrence's acts - read with its time, so no routing reading
    of a passage it holds stands in for an act the inventory does not read (engine._states_unread_act)."""

    CASES = (('f1b-results-month-row', 'gi.colonoscopy', 'snare', '45385',
              'Colonoscopy, this practice | November 2025 | Yes, two tubular adenomas'),
             ('f1b-previous-label-row', 'gi.egd', 'biopsy', '43239',
              'Previous upper endoscopy | LA grade C | Yes, distal esophagus'),
             ('f1b-prior-year-row', 'gi.colonoscopy', 'snare', '45385', 'Colonoscopy | 2021 | Yes, three tubular adenomas'))

    def test_a_row_of_another_occurrence_states_no_act_of_today(self):
        for name, family, kind, code, row in self.CASES:
            with self.subTest(name):
                text = fixture(name)
                inv = read(text)
                self.assertFalse(acts(inv, family, kind, ('performed', 'negated', 'cancelled')))
                self.assertEqual([a.status for a in acts(inv, family, kind)], ['historical'])
                header = text[:text.index(row)].rstrip('\n').rsplit('\n', 1)[1]
                for quote in (row, header.rsplit(' | ', 1)[1]):  # the row, and the column's own header word
                    self.assertIn(status(text, code, quote), NOT_READY, quote)

    def test_an_earlier_occurrences_denial_is_no_conflict(self):
        text = fixture('f1b-prior-row-denial')
        inv = read(text)
        self.assertEqual(inv.conflicts, ())
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'snare', ('negated',)))
        self.assertEqual(status(text, '45385', 'A 7 mm sessile polyp in the descending colon was removed with a cold '
                                               'snare.'), 'ready')

    def test_todays_row_and_a_neutral_table_still_bind(self):
        """Controls: a row dated the service date, and a table under a heading naming no other time, are today's."""
        for heading, row in (('Examination record', 'Colonoscopy | 2026-10-16 | Yes, two tubular adenomas'),
                             ('Examination record', 'Colonoscopy, this practice | today | Yes, two tubular adenomas')):
            text = fixture('f1b-results-month-row').replace('Results reviewed', heading).replace(
                'Colonoscopy, this practice | November 2025 | Yes, two tubular adenomas', row)
            with self.subTest(row):
                self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'snare')], ['performed'])

    def test_a_heading_of_records_reviewed_gives_its_rows_another_time(self):
        text = fixture('f1b-results-month-row').replace('November 2025', 'today')
        self.assertEqual([a.status for a in acts(read(text), 'gi.colonoscopy', 'snare')], ['historical'])


class PlanTableTests(SimpleTestCase):
    """INV-2: a table in a section routing's layout reads as a plan states planned acts, inside a titled report too."""

    def test_a_plan_table_states_planned_acts(self):
        for name, family, code, row in (
                ('f1a-plan-table-colonoscopy', 'gi.colonoscopy', '45385', 'Colonoscopy | Within 8 weeks | Yes, EMR | Yes'),
                ('f1a-plan-table-egd', 'gi.egd', '43239', 'Upper endoscopy | March 2027 | Yes, four-quadrant every 2 cm')):
            with self.subTest(name):
                text = fixture(name)
                inv = read(text)
                self.assertFalse(acts(inv, family, None, ('performed', 'negated', 'uncertain')))
                self.assertTrue(acts(inv, family, None, ('planned',)))
                self.assertIn(status(text, code, row), NOT_READY)
        unresolved, _ = unresolved_kinds(read(fixture('f1a-plan-table-colonoscopy')), [('45378', 'gi.colonoscopy')])
        self.assertEqual(unresolved, [])  # no tattoo the table plans is listed as undone work

    def test_the_same_table_in_the_findings_is_todays(self):
        """Control: the table under the report's own findings states today's acts."""
        text = fixture('f1a-plan-table-colonoscopy').replace('Impression\nAscending colon flat lesion, 15 mm.\nPlan\n',
                                                             '').replace('Within 8 weeks', 'Today')
        self.assertTrue(acts(read(text), 'gi.colonoscopy', 'tattoo', ('performed',)))


class CellInstrumentTests(SimpleTestCase):
    """INV-3: a table answer naming its own instrument states that act; the column's own act is then in doubt."""

    def test_a_cold_snare_answer_is_the_snare_removal(self):
        text = fixture('f2-tissue-sampled-cold-snare')
        inv = read(text)
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
        self.assertEqual(len(acts(inv, 'gi.colonoscopy', 'snare', ('performed',))), 1)  # the table restates it
        self.assertFalse([d for d in described(inv, 'gi.colonoscopy') if 'forceps biopsy' in d])
        self.assertIn(status(text, '45380', 'Yes, cold snare (one polyp)'), NOT_READY)
        self.assertEqual(status(text, '45385', 'removed with a cold snare'), 'ready')
        self.assertNotIn(('gi.colonoscopy', 'biopsy'), unresolved_kinds(inv, [('45385', 'gi.colonoscopy')])[0])

    def test_a_bare_yes_beside_tissue_a_snare_took_is_no_forceps_biopsy(self):
        text = fixture('f2-tissue-sampled-yes')
        self.assertFalse(acts(read(text), 'gi.colonoscopy', 'biopsy', ('performed',)))
        for quote in ('Colonoscopy | Adult colonoscope | Cecum | Yes', 'Tissue sampled'):
            self.assertIn(status(text, '45380', quote), NOT_READY, quote)

    def test_a_polyp_taken_with_cold_forceps_is_no_snare_removal(self):
        text = fixture('f2-polypectomy-cold-forceps')
        inv = read(text)
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'snare', ('performed',)))
        self.assertEqual([a.technique for a in acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',))], ['cold forceps'])
        self.assertFalse([a for a in acts(inv, 'gi.colonoscopy', 'snare') if 'forceps' in a.technique])
        self.assertIn(status(text, '45385', 'Polypectomy'), NOT_READY)
        self.assertEqual(status(text, '45380', '1 | Rectum | 2 mm | Yes, cold forceps'), 'ready')

    def test_an_answer_of_the_columns_own_act_still_states_it(self):
        """Controls: a biopsy column's "Yes, cold forceps", and a tissue column's "Yes" beside a documented biopsy."""
        text = colonoscopy('Two diminutive polyps were found.', 'Polyp | Location | Biopsy\n1 | Rectum | Yes, cold forceps\n')
        self.assertEqual([(a.status, a.technique) for a in acts(read(text), 'gi.colonoscopy', 'biopsy')],
                         [('performed', 'cold forceps')])
        text = colonoscopy('Biopsies of the ascending colon were taken with cold forceps.',
                           'Examination | Instrument | Tissue sampled\nColonoscopy | Adult colonoscope | Yes\n')
        self.assertTrue(acts(read(text), 'gi.colonoscopy', 'biopsy', ('performed',)))
        self.assertFalse(acts(read(text), 'gi.colonoscopy', 'biopsy', ('uncertain',)))


class SegmentSiteTests(SimpleTestCase):
    """INV-4: the site a mention takes as its object is that mention's; each act records its own segment's sites."""

    def test_each_service_takes_its_own_act_and_site(self):
        text = fixture('f3-procline-and')
        inv = read(text)
        self.assertEqual([a.anatomy for a in acts(inv, 'gi.egd', 'biopsy', ('performed',))], [('gastric antrum',)])
        self.assertEqual([a.anatomy for a in acts(inv, 'gi.colonoscopy', 'snare', ('performed',))], [('sigmoid colon',)])
        self.assertFalse(acts(inv, 'gi.egd', 'snare'))
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy'))
        result = assess_picks(text, [('43239', 'EGD with cold forceps biopsies of the gastric antrum'),
                                     ('45385', 'colonoscopy with cold snare polypectomy in the sigmoid colon'),
                                     ('45380', 'colonoscopy with cold snare polypectomy in the sigmoid colon')])
        self.assertEqual({p.code: p.status for p in result.proposals},
                         {'43239': 'ready', '45385': 'ready', '45380': 'needs_clarification'})

    def test_a_site_written_before_its_own_mention_stays_its_own(self):
        """Control: "antral biopsies" keeps its site, after another mention's object site in its clause."""
        text = colonoscopy('A 6 mm polyp in the sigmoid colon was removed with a cold snare and rectal biopsies were '
                           'taken.')
        self.assertEqual([a.anatomy for a in acts(read(text), 'gi.colonoscopy', 'biopsy', ('performed',))],
                         [('rectum',)])

    def test_a_word_that_ends_in_a_lesion_noun_is_no_lesion(self):
        """Control (live gi-08): "ring" inside "normal-appearing" or "during" is no lesion, so no point cuts the act's
        own segment short of its sites."""
        text = colonoscopy('Cold forceps biopsies were taken from the rectum and from the normal-appearing descending '
                           'colon at 40 cm during the examination, as listed below.')
        self.assertEqual([a.anatomy for a in acts(read(text), 'gi.colonoscopy', 'biopsy', ('performed',))],
                         [('rectum', 'descending colon')])
        self.assertEqual([m.group('noun') for m in services.LESION.finditer('appearing during a ring, monitoring')],
                         ['ring'])

    def test_forceps_biopsies_is_one_mention(self):
        text = HEAD + 'Biopsies were taken with cold forceps biopsies of the antrum.'
        self.assertEqual([k for k, _, _ in services._acts_in(text, 0, len(text))], ['biopsy', 'biopsy'])
        self.assertEqual(services._acts_in('cold forceps biopsies', 0, 21), [('biopsy', 5, 21)])


class ExchangePartTests(SimpleTestCase):
    """INV-5 and interpretation 46: a placement or removal naming its duct is part of the exchange its words place."""

    def test_a_placement_naming_its_duct_is_held_with_the_exchange(self):
        text = fixture('f5-exchange-placement-site')
        inv = read(text)
        m = reconcile.match('43274', inv, 'gi.ercp')
        self.assertEqual((m.state, m.reason), ('uncertain', reconcile.EXCHANGE_PART))
        self.assertIn('Biliary stent exchanged', m.question)
        result = assess_picks(text, [('43274', 'A new 10 French by 9 cm plastic stent was placed in the common bile '
                                               'duct across the stricture')])
        held = next(p for p in result.proposals if p.code == '43274')
        self.assertEqual(held.status, 'needs_clarification')
        self.assertFalse(held.reinstatable or held.exclusion_reason)

    def test_a_removal_naming_its_duct_is_part_of_the_exchange_and_its_snare_no_polypectomy(self):
        text = fixture('f5-exchange-removal-site')
        inv = read(text)
        self.assertFalse(acts(inv, 'gi.ercp', 'snare'))
        self.assertEqual(reconcile.match('43275', inv, 'gi.ercp').reason, reconcile.EXCHANGE_PART)
        self.assertEqual(unresolved_kinds(inv, [('43276', 'gi.ercp')])[0], [])
        result = assess_picks(text, [('43275', 'The existing plastic stent was removed from the common bile duct with a '
                                               'snare.'), ('43276', 'Biliary stent exchanged')])
        self.assertEqual({p.code: p.status for p in result.proposals},
                         {'43275': 'needs_clarification', '43276': 'ready'})

    def test_a_placement_in_another_duct_system_stays_its_own(self):
        """Controls: the pancreatic duct stent beside "Biliary stent exchanged" is a placement of its own; h2-10's
        placement, naming no site, is the exchange's (interpretation 46)."""
        inv = read(corpus('c6-ercp-exchange-plus-pancreatic'))
        m = reconcile.match('43274', inv, 'gi.ercp')
        self.assertEqual(m.state, 'performed')
        self.assertTrue(all('pancreatic duct' in a.anatomy for a in m.acts))
        self.assertEqual(reconcile.match('43274', read(corpus('h2-10-live')), 'gi.ercp').reason, reconcile.EXCHANGE_PART)

    def test_an_exchanges_place(self):
        exchange = services.Act(id='S1-A1', service='S1', kind='stent_exchange', status='performed', role='physician',
                                anatomy=(), region='', technique='', evidence=(services.Span(0, 23, 'Biliary stent '
                                                                                                    'exchanged'),))
        self.assertEqual(reconcile._exchange_places(exchange), frozenset(('biliary',)))
        self.assertEqual(reconcile._exchange_places(services.dataclasses.replace(
            exchange, evidence=(services.Span(0, 15, 'Stent exchanged'),))), frozenset())


class TemporalObjectTests(SimpleTestCase):
    """INV-6: an act named as the time of another act's denial ("after the polypectomy") is not what it denies."""

    def test_another_acts_denial_never_denies_the_act_it_follows(self):
        for name, denied in (('f4-hemostasis-after-polypectomy', 'bleeding_control'), ('f4-clips-not-needed', 'clip'),
                             ('f4-tattoo-not-needed', 'tattoo'), ('f4-did-not-take-after', 'biopsy')):
            with self.subTest(name):
                text = fixture(name)
                inv = read(text)
                self.assertEqual(inv.conflicts, ())
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'snare', ('negated', 'cancelled')))
                if name == 'f4-did-not-take-after':
                    # gi3 fix round 2 (INV2-10): "I did not take further biopsies" denies further biopsies - another
                    # occurrence its own words name (NEG_OTHER's class) - so R1's gate records no denied biopsy, as the
                    # installed revision read it; no biopsy is read done either
                    self.assertFalse(acts(inv, 'gi.colonoscopy', denied, ('performed', 'negated')))
                else:
                    self.assertTrue(acts(inv, 'gi.colonoscopy', denied, ('negated',)))
                self.assertEqual(status(text, '45385', 'removed with a cold snare'), 'ready')
        text = fixture('f4-biopsies-after-dilation')
        inv = read(text)
        self.assertEqual(inv.conflicts, ())
        self.assertTrue(acts(inv, 'gi.egd', 'biopsy', ('negated',)))
        self.assertEqual(status(text, '43249', 'Impression: Schatzki ring, dilated to 18 mm.'), 'ready')

    def test_the_act_a_denial_follows_is_never_excluded(self):
        text = fixture('f4-preexisting-exclusion-dilation')
        self.assertFalse(acts(read(text), 'gi.egd', 'dilation', ('negated', 'cancelled')))
        self.assertNotEqual(status(text, '43249', 'Biopsies were not taken after the balloon dilation to 18 mm.'),
                            'excluded')

    def test_an_act_noun_naming_a_place_is_no_act_denied(self):
        """INV-6's class: "the polypectomy defect" names the place the polypectomy left, so the clips' denial is no
        denial of it (ATTRIBUTIVE_ACT)."""
        inv = read(colonoscopy('A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare. Clips were not '
                               'needed to close the polypectomy defect.'))
        self.assertEqual(inv.conflicts, ())
        self.assertTrue(acts(inv, 'gi.colonoscopy', 'clip', ('negated',)))

    def test_a_cancellation_of_another_act_cancels_nothing_of_this_one(self):
        for sentence in ('Tattooing was deferred after the polypectomy.', 'After the polypectomy, tattooing was deferred.'):
            with self.subTest(sentence):
                inv = read(colonoscopy('A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare. '
                                       + sentence))
                self.assertEqual(inv.conflicts, ())
                self.assertTrue(acts(inv, 'gi.colonoscopy', 'tattoo', ('cancelled',)))

    def test_the_acts_own_denial_still_denies_it(self):
        """Controls: a denial whose subject is the act, or whose time is another act, still denies it."""
        for sentence in ('The polypectomy was not performed after the biopsy.', 'Biopsies were not taken.',
                         'No polypectomy was performed after the biopsies.'):
            with self.subTest(sentence):
                inv = read(colonoscopy('The mucosa was normal. ' + sentence))
                kind = 'biopsy' if sentence.startswith('Biopsies') else 'snare'
                self.assertTrue(acts(inv, 'gi.colonoscopy', kind, ('negated',)))
                self.assertFalse(acts(inv, 'gi.colonoscopy', kind, ('performed',)))


class AttributionTests(SimpleTestCase):
    """INV-7: a labelled line keeping the work with the endoscopist, or denying its separate billing, attributes
    nothing."""

    def test_the_endoscopists_own_work_is_no_other_providers(self):
        for name in ('f6-fluoro-will-not-be-billed', 'f6-fluoro-endoscopist-bills'):
            with self.subTest(name):
                text = fixture(name)
                self.assertNotIn('radiology', [a.role for a in read(text).attributions])
                result = assess_picks(text, [('74330', 'Fluoroscopy:'), ('43276', 'Biliary stent exchanged')])
                self.assertFalse([c for c in result.encounter_checks if c.id == 'services.attribution'])

    def test_a_line_denying_its_separate_billing_attributes_nothing(self):
        """A negation anywhere between the label's colon and its billing words says the opposite (no endoscopist named)."""
        for line in ('Fluoroscopy: interpreted in the room and will not be billed separately',
                     'Radiology: this is not to be reported separately', "Fluoroscopy: it won't be billed separately"):
            with self.subTest(line):
                text = colonoscopy('No polyps.', line + '\n')
                self.assertEqual([a.role for a in read(text).attributions if a.role in ('radiology', 'pathology')], [])

    def test_another_departments_line_still_attributes(self):
        """Controls: h2-10's radiology line, and the endoscopist named only past the line's semicolon."""
        self.assertIn('radiology', [a.role for a in read(corpus('h2-10-live')).attributions])
        text = colonoscopy('No polyps.', 'Pathology: reported separately; the endoscopist reviewed the slides\n')
        self.assertIn('pathology', [a.role for a in read(text).attributions])


class ObjectLesionTests(SimpleTestCase):
    """INV-8: a lesion named right after an act as its object is that act's own."""

    def test_each_act_takes_its_own_object(self):
        inv = read(fixture('f7-coordinated-lesions'))
        colon = reconcile.service_for(inv, 'gi.colonoscopy')
        lesion = {les.id: (les.size, les.noun) for les in colon.lesions}
        self.assertEqual([lesion[a.lesion] for a in acts(inv, 'gi.colonoscopy', 'snare', ('performed',))],
                         [('6 mm', 'polyp')])
        self.assertEqual([lesion[a.lesion] for a in acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',))],
                         [('25 mm', 'mass')])
        unresolved, bundled = unresolved_kinds(inv, [('45385', 'gi.colonoscopy')])
        self.assertIn(('gi.colonoscopy', 'biopsy'), unresolved)
        self.assertNotIn('biopsy', bundled)
        self.assertIn('snare removal (cold snare) of the 6 mm polyp in the rectum', described(inv, 'gi.colonoscopy'))

    def test_an_act_after_its_lesion_still_takes_it(self):
        """Control: "a polyp ... was removed with a cold snare and a 4 mm polyp ... was biopsied"."""
        inv = read(colonoscopy('A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare and a 4 mm polyp '
                               'in the rectum was biopsied.'))
        self.assertEqual(described(inv, 'gi.colonoscopy'),
                         ['snare removal (cold snare) of the 6 mm sessile polyp in the sigmoid colon',
                          'forceps biopsy of the 4 mm polyp in the rectum'])


class PositionTests(SimpleTestCase):
    """INV-9: a measure "at" introduces is a position, never a lesion's size."""

    def test_an_insertion_distance_is_no_size(self):
        inv = read(fixture('f9-distance-as-size'))
        self.assertFalse([les for s in inv.services for les in s.lesions if les.size == '32 cm'])
        self.assertIn('forceps biopsy (cold forceps) at the distal esophagus', described(inv, 'gi.egd'))

    def test_a_size_is_still_a_size(self):
        """Controls: a size a lead word, "of" or a decimal opens."""
        for findings, size in (('A 1.5 cm flat lesion in the ascending colon was biopsied with cold forceps.', '1.5 cm'),
                               ('Cold snare polypectomy of a 6 mm polyp at 25 cm in the sigmoid colon.', '6 mm')):
            with self.subTest(findings):
                inv = read(colonoscopy(findings))
                self.assertEqual([les.size for s in inv.services for les in s.lesions], [size])
        self.assertEqual(services.LESION.search('In the colon at 32 cm linear erosions').group('size'), None)
        self.assertEqual(services.LESION.search('In the colon at 2.5 cm linear erosions').group('size'), None)


class DatesInTests(SimpleTestCase):
    """INV-10 (cost-4): the dates of a span, found by bisection on both ends."""

    def test_the_same_dates_as_before(self):
        rng = random.Random(1030)
        for _ in range(300):
            starts = sorted(rng.sample(range(0, 2000), rng.randint(0, 40)))
            dates = tuple(gi_context.DateMention(s, s + 4, date(2026, 1, 1), 'year') for s in starts)
            a, b = sorted((rng.randint(-5, 2005), rng.randint(-5, 2005)))
            lo = bisect.bisect_left([d.start for d in dates], a)
            expected = [d for d in dates[lo:] if d.start < b]
            self.assertEqual(list(services._dates_in(dates, a, b)), expected)

    def test_each_call_reads_no_more_than_its_own_dates(self):
        """20,000 calls over 20,000 dates: a list of every start (or every later date) built per call was 400 million
        element copies; two bisections take well under a second."""
        dates = tuple(gi_context.DateMention(i * 10, i * 10 + 4, date(2025, 1, 1), 'year') for i in range(20000))
        started = time.process_time()
        for i in range(20000):
            services._dates_in(dates, i * 10, i * 10 + 5)
        self.assertLess(time.process_time() - started, 1.0)


    def test_a_tables_rows_read_their_dates_in_constant_work(self):
        """_heading_time, read once per table row for its label (_row_time): its dates by bisection on both ends, never
        a slice from the label to the document's last date (30,000 labels between the service date and 30,000 later dates:
        900 million copies, seconds; two bisections each, a fraction of one)."""
        own = 'Date of service: 2026-10-16\n'
        text = HEAD + own + 'Colonoscopy | x | y\n' * 30000 + 'Recall years: ' + '2026 ' * 30000 + '\n'
        dates = gi_context.find_dates(text)
        starts = [d.start for d in dates]
        self.assertGreater(len(dates), 30000)
        started = time.process_time()
        at = len(HEAD) + len(own)
        for _ in range(30000):
            self.assertEqual(services._heading_time(text, at, at + 11, date(2026, 10, 16), dates, starts), '')
            at += 20
        self.assertLess(time.process_time() - started, 1.5)


class SummaryTests(SimpleTestCase):
    """STATE-4: a summary's act restating a body act is that act; a tattoo or an injection takes no other instrument."""

    def test_ho_01s_procedure_line_adds_no_act(self):
        text = (Path(__file__).resolve().parent / 'fixtures' / 'gi3' / 'ho-01__30d3f32d__2026-10-29.txt').read_text(
            encoding='utf-8')
        inv = read(text)
        self.assertFalse([a for s in inv.services for a in s.acts if a.kind in ('tattoo', 'injection') and a.technique])
        self.assertEqual(len(acts(inv, 'gi.colonoscopy', 'snare', ('performed',))), 1)
        self.assertEqual(len(acts(inv, 'gi.colonoscopy', 'tattoo', ('performed',))), 1)
        self.assertEqual(described(inv, 'gi.egd'), ['forceps biopsy at the gastric antrum and body',
                                                    'forceps biopsy at the duodenal bulb'])
        line = text.index('Procedures: Esophagogastroduodenoscopy')
        snare = acts(inv, 'gi.colonoscopy', 'snare', ('performed',))[0]
        self.assertTrue(any(ev.start >= line and ev.end <= text.index('\n', line) for ev in snare.evidence))

    def test_a_summarys_site_is_kept_where_the_body_names_none(self):
        """Control (live ho-08): the procedure line's "esophageal manometry" joins the body's "manometry" with its site."""
        text = (HEAD + 'Date of service: 2026-10-16\nEsophageal manometry report\nProcedure: High-resolution esophageal '
                'manometry.\nFindings: Manometry was performed with a solid-state catheter. Peristalsis was normal.\n')
        inv = read(text)
        self.assertEqual([a.anatomy for s in inv.services for a in s.acts if a.kind == 'manometry'], [('esophagus',)])

    def test_a_summary_the_body_does_not_restate_stays_an_act(self):
        """Control: a procedure line's act the body never states stays an act of its own, performed."""
        text = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nProcedure: Colonoscopy with cold snare '
                'polypectomy.\nFindings: The colonoscope was advanced to the cecum.\n')
        self.assertEqual(len(acts(read(text), 'gi.colonoscopy', 'snare', ('performed',))), 1)

    def test_a_body_statement_the_summary_restates_is_never_hidden(self):
        """Control: "Random biopsies were taken" states its own act (merged with the procedure line's), which never
        joins the polyp's biopsy - bundled as a biopsy of a removed lesion, it would leave the random biopsies
        unlisted beside 45385."""
        text = colonoscopy('Random biopsies were taken. A 5 mm polyp in the sigmoid colon was biopsied and then removed '
                           'with a cold snare.').replace('Colonoscopy report\n', 'Colonoscopy report\nProcedure: '
                                                                                'Colonoscopy with biopsies.\n')
        unresolved, _ = unresolved_kinds(read(text), [('45385', 'gi.colonoscopy')])
        self.assertIn(('gi.colonoscopy', 'biopsy'), unresolved)

    def test_a_summary_still_pairs_with_a_denial_of_its_site(self):
        """Control (gi2 conflicts, PR1): the summary joins the body's act only once conflicts are read."""
        text = (HEAD + 'Date of service: 2026-10-16\nUpper endoscopy report\nProcedure: EGD with biopsies.\nFindings: The '
                'gastroscope was advanced to the second portion of the duodenum. Biopsies were taken from the antrum. '
                'No gastric biopsies were taken.\n')
        inv = read(text)
        self.assertTrue([c for c in inv.conflicts if c.subject == 'biopsy'])
        self.assertEqual(len(acts(inv, 'gi.egd', 'biopsy', ('performed',))), 1)


class RelativeClauseTests(SimpleTestCase):
    """EXT-2 (the inventory's half): a negation inside a relative clause is about its head noun."""

    def test_a_relative_clauses_denial_is_its_head_nouns(self):
        for name in ('rel-r1', 'rel-r2', 'rel-r3'):
            with self.subTest(name):
                text = fixture(name)
                inv = read(text)
                self.assertTrue(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('negated', 'cancelled')))
                quote = next(line for line in text.split('. ') if 'that was not removed' in line).strip()
                self.assertNotEqual(status(text, '45380', quote.rstrip('.').split('\n')[-1]), 'excluded')

    def test_the_acts_own_denial_still_denies_it(self):
        """Controls: a demonstrative "that", and the act's own negation beside a relative clause."""
        for sentence in ('Biopsies of that polyp were not taken.',
                         'Biopsies were not taken from the polyp that was removed.'):
            with self.subTest(sentence):
                inv = read(colonoscopy('A 15 mm sessile polyp in the ascending colon was seen. ' + sentence))
                self.assertTrue(acts(inv, 'gi.colonoscopy', 'biopsy', ('negated',)))
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
