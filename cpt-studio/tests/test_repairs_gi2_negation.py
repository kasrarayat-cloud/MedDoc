"""Repair round gi2 (session 7c8d38da, 2026-10-28), agent "negation": a negation that governs a STATUS word ("not
aborted", "never cancelled", "without being aborted", "wasn't postponed") denies that status, never the service.

At 2b82889f the reference reader let the bare status word "aborted" stand in for the procedure and read the negation
before it with the service-name grammar ("but not the colonoscopy"), so "Examination complete, not aborted." read as
"the colonoscopy was not done" and held a complete colonoscopy for clarification (held-out document ho-02); the
clause-cue reader read "Colonoscopy was not cancelled." as a cancellation and "The examination wasn't discontinued." as
a discontinued examination; and a cited "aborted" read as the service's denial. A bare negated status sentence is
released only when the family's own text establishes the procedure today and today's report holds no procedure-level
denial or doubt routing cannot read; anything more holds it as a doubt that keeps the status word's rank.

The expected answers live in these tests, outside the reader, and the truth of every constructed case is fixed by its
construction, never by a reader. Synthetic text only: every document opens with the synthetic banner.
"""
import json
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.ingest.extract import extract_document
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess
from tests.support import docgen

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
DAY = date(2026, 10, 19)
VARIANTS = Path(__file__).resolve().parent / 'corpus' / 'negated_status' / 'variants.json'
# what ho-02 did not do today: hot biopsy forceps or snare removal, EMR, biopsy, directed submucosal injection (tattoo)
NOT_DONE_TODAY = ('45384', '45385', '45390', '45380', '45381')


def read(text, family='gi.colonoscopy'):
    """(routing status of ``family``, its documented service in the inventory or None)."""
    routing = detect.route(text, DAY)
    inv = services.build(text, service_date=DAY, routing=routing, context_facts=gi_context.extract_context(text))
    finding = routing.finding(family)
    service = next((s for s in inv.services if s.family == family), None)
    return (finding.status if finding else None), service


def report(ext, desc='The colonoscope was inserted and advanced to the cecum. The appendiceal orifice was identified.',
           find='The colon mucosa was normal.'):
    return (BANNER + '\nColonoscopy Report\nDate of procedure: 2026-10-19\nProcedure: Colonoscopy.\n\nDescription\n'
            + desc + '\n\nFindings\n' + find + '\n\nExtent and completeness\n' + ext + '\n\nImpression\nSee findings.\n')


# The shape of held-out document ho-02: a complete diagnostic colonoscopy to the cecum, a large lesion left in place for
# a later EMR by another endoscopist, no biopsy, no tattoo, and "Examination complete, not aborted."
HO02_LINES = (
    BANNER,
    'Colonoscopy Report',
    'Date of procedure: 10/19/2026',
    'Procedure: Diagnostic colonoscopy.',
    '',
    'Indication',
    'Intermittent dark red blood mixed into the stool.',
    '',
    'Description',
    'After informed consent, the colonoscope was inserted and advanced without difficulty to',
    'the cecum. The terminal ileum was not entered.',
    '',
    'Findings',
    'Ascending colon: a 35 mm laterally spreading tumor. Because of its size it was not removed',
    'today and will be resected at a dedicated endoscopic mucosal resection',
    '(EMR) session. No biopsies were taken. No tattoo was placed.',
    '',
    'Extent and completeness',
    'Extent of examination: cecum. Examination complete, not aborted.',
    '',
    'Impression',
    '1. Laterally spreading tumor, left in place for a planned EMR.',
)
HO02_TEXT = '\n'.join(HO02_LINES) + '\n'


def ho02_pdf():
    """The same report as a digital PDF whose line wrap puts "(EMR) session." at the head of a line, as the uploaded
    ho-02 PDF does, read back by the real extraction."""
    assert all(len(line) <= docgen.PDF_LINE_CHARS for line in HO02_LINES)
    result = extract_document(docgen.make_pdf(['\n'.join(HO02_LINES)]), 'synthetic.pdf', 'application/pdf')
    assert result.status == 'ok', result.messages
    return result.text, result.pages


def assessed(text, codes, pages=()):
    """The engine's assessment of ``text`` with the provider selecting ``codes`` [(code, (quoted passages))]."""
    facts = gi_context.extract_context(text)
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    selected = []
    for code, quotes in codes:
        spans = []
        for quote in quotes:
            at = text.index(quote)
            spans.append(EvidenceSpan(0, at, at + len(quote), quote, True))
        selected.append(ProviderCode('selected', 'cpt', code, 'synthetic', tuple(spans)))
    return assess(text=text, pages=tuple(pages), context=facts, routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'synthetic@1', tuple(selected)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


class Ho02ShapeTests(SimpleTestCase):
    """The live failure: each negation and the later-plan clause govern their own act, never the colonoscopy."""

    def check(self, text):
        status, service = read(text)
        self.assertEqual(status, 'performed')
        self.assertEqual((service.status, service.completion), ('performed', 'complete'))
        self.assertIn('cecum', service.extent)
        self.assertEqual(service.intent, 'diagnostic')
        acts = {(a.kind, a.status) for a in service.acts}
        self.assertIn(('emr', 'planned'), acts)
        self.assertIn(('biopsy', 'negated'), acts)
        self.assertIn(('tattoo', 'negated'), acts)
        # the lesion "was not removed today": no removal, sampling or marking act is read as done
        self.assertEqual([a for a in service.acts if a.status == 'performed'], [])

    def test_text_reads_a_complete_colonoscopy_and_each_act_in_its_own_time(self):
        self.check(HO02_TEXT)

    def test_pdf_with_the_wrapped_emr_line_reads_the_same(self):
        self.check(ho02_pdf()[0])

    def test_engine_proposes_the_colonoscopy_without_a_question_or_a_reduced_service_consideration(self):
        for (text, pages), cited in ((
                (HO02_TEXT, ()), 'Examination complete, not aborted.'), ((HO02_TEXT, ()), 'aborted'),
                (ho02_pdf(), 'Examination complete, not aborted.')):
            with self.subTest(pdf=bool(pages), cited=cited):
                result = assessed(text, [('45378', ('Procedure: Diagnostic colonoscopy.', cited))], pages)
                proposal = next(p for p in result.proposals if p.code == '45378')
                self.assertEqual(proposal.status, 'ready')
                self.assertEqual([c.id for c in proposal.checks if c.status in ('warn', 'fail')], [])
                self.assertEqual(proposal.clarifications, ())
                self.assertEqual(proposal.modifier_considerations, ())
                self.assertEqual(result.clarifications, ())
                self.assertEqual(result.completeness['state'], 'complete_pending_review')
                self.assertFalse(any(p.code in NOT_DONE_TODAY for p in result.proposals))
                self.assertEqual([(s['family'], s['status'], s['completion']) for s in result.services['services']],
                                 [('gi.colonoscopy', 'performed', 'complete')])


class ReleasedBareStatementTests(SimpleTestCase):
    """A bare negated status sentence in a report that establishes the procedure today denies nothing."""
    BARE = ('Examination complete, not aborted.', 'Examination complete; not aborted.', 'The procedure was not aborted.',
            'The procedure was never aborted.', "The procedure wasn't aborted.", 'Not aborted.', '- Not aborted.',
            'The examination was completed without being aborted.', 'The procedure was neither aborted nor cancelled.',
            'The procedure was not aborted or interrupted.', 'The procedure was not terminated early.',
            "The exam wasn't cancelled or postponed.", 'Extent of examination: cecum. Examination complete, not\naborted.',
            'The procedure was not aborted at all.', 'The procedure wasn’t aborted.',
            'The examination was never stopped at any point.')

    def test_bare_forms_release(self):
        for sentence in self.BARE:
            with self.subTest(sentence=sentence):
                status, service = read(report(sentence))
                self.assertEqual(status, 'performed')
                self.assertEqual((service.status, service.completion), ('performed', 'complete'))

    def test_an_unresected_lesion_does_not_hold(self):  # owner, 2026-10-27
        status, service = read(report('Examination complete, not aborted.', find=(
            'A 30 mm lesion in the ascending colon. It was not removed today and will be resected at a later EMR session.')))
        self.assertEqual((status, service.status, service.completion), ('performed', 'performed', 'complete'))

    def test_a_cited_bare_sentence_reads_as_its_family_reads(self):
        # whatever part of it the provider cites: the negation before "aborted" is the status word's own, never the
        # service-name grammar's "but not the colonoscopy" (the third reader of the same misreading)
        text = report('Examination complete, not aborted.')
        for cited in ('Examination complete, not aborted.', 'not aborted', 'aborted', 'aborted.'):
            with self.subTest(cited=cited):
                at = text.index(cited)
                self.assertEqual(detect.status_for_span(text, at, at + len(cited), DAY)[0], 'performed')
                self.assertEqual(detect.own_status_for_span(text, at, at + len(cited), DAY)[0], 'performed')


class HeldTests(SimpleTestCase):
    """Never performed where the text denies, calls off, cuts short or hedges the procedure, or establishes nothing; and
    a negated status word is never itself the service's denial, cancellation or incompleteness."""
    MORE = ('The procedure was not aborted until the scope reached the hepatic flexure.',
            'The procedure was not aborted but was incomplete because of poor preparation.',
            'The procedure was possibly not aborted.', 'Was the procedure not aborted?',
            'The polypectomy was not aborted.', 'The procedure was not aborted on 2026-10-19.',
            'The procedure was not aborted and will be repeated in 3 years.',
            'The procedure was not aborted at any point before the cecum.')
    UNREAD = ('It was not performed.', 'It was cancelled before sedation.',
              'It is unclear whether the procedure was completed.', 'This was postponed.', 'It was not started.',
              'The procedure was limited by poor preparation.', 'The procedure may have been incomplete.',
              'The patient left before the procedure began.')

    def test_more_in_the_sentence_holds_and_never_denies(self):
        for sentence in self.MORE:
            with self.subTest(sentence=sentence):
                status, service = read(report(sentence))
                self.assertNotIn(status, ('performed', 'negated', 'cancelled'))
                self.assertNotEqual(service.status, 'performed')

    def test_a_cited_negated_status_word_is_never_the_services_denial(self):
        sentence = 'The procedure was not aborted until the scope reached the hepatic flexure.'
        text = report(sentence)
        for cited in (sentence, 'not aborted', 'aborted'):
            with self.subTest(cited=cited):
                at = text.index(cited)
                self.assertEqual(detect.status_for_span(text, at, at + len(cited), DAY)[0], 'uncertain')
                self.assertEqual(detect.own_status_for_span(text, at, at + len(cited), DAY)[0], 'uncertain')

    def test_an_unread_denial_or_doubt_in_todays_report_holds(self):
        for extra in self.UNREAD:
            with self.subTest(extra=extra):
                status, service = read(report('Examination complete, not aborted. ' + extra))
                self.assertNotEqual(status, 'performed')
                self.assertNotEqual(service.status, 'performed')

    def test_nothing_else_establishing_the_procedure_holds(self):
        for desc in ('Bowel preparation was adequate.', 'The colonoscope was inserted.'):
            with self.subTest(desc=desc):
                status, service = read(report('Examination complete, not aborted.', desc=desc))
                self.assertNotIn(status, ('performed', 'negated', 'cancelled', 'incomplete'))
                self.assertNotEqual(service.status, 'performed')

    def test_a_negated_cancellation_beside_the_name_is_never_a_cancellation(self):
        for sentence in ('Colonoscopy was not cancelled.', 'The colonoscopy was never cancelled.',
                         'The colonoscopy was not postponed.', 'The colonoscopy was not called off.',
                         'The colonoscopy was not deferred.', "The colonoscopy wasn't aborted."):
            with self.subTest(sentence=sentence):
                status, _ = read(report(sentence))
                self.assertNotIn(status, ('cancelled', 'negated', 'incomplete'))

    def test_a_held_negated_status_keeps_its_rank_over_a_plan_cue(self):
        # the hold stands for the status word, so the plan cue of its clause never makes the family planned, and a
        # denial beside it still decides
        status, _ = read(report('The colonoscopy was not cancelled and was then repeated next week.'))
        self.assertNotIn(status, ('planned', 'cancelled', 'negated'))
        status, service = read(report('The colonoscopy was not cancelled and was then repeated next week. '
                                      'It was not performed.'))
        self.assertNotEqual(status, 'performed')
        self.assertNotEqual(service.status, 'performed')


class ContractedNegationTests(SimpleTestCase):
    """A contracted negation, with either apostrophe, and a negative-polarity intensifier after the status word ("at any
    point", "at all") leave a statement bare. Round r1_n's flexible sigmoidoscopy: 2b82889f's routing read "wasn't
    discontinued" as a discontinued examination while the documented-service reader read it performed; a hold there
    would have turned that correct reading uncertain."""
    SIG = (BANNER + '\nProcedure date: 10/14/2026\nPROCEDURE NOTE: Flexible sigmoidoscopy\nIndication: Rectal bleeding.\n'
           'Technique: The sigmoidoscope was advanced to the descending colon.\nFindings:\n{x}\nImpression: See findings.\n')

    def test_routing_and_the_inventory_read_the_examination_performed(self):
        for line in ("The examination wasn't discontinued at any point.", 'The examination wasn’t discontinued at any '
                     'point.', 'The examination was complete and wasn’t discontinued.',
                     "The examination was complete and wasn't discontinued.", 'The examination was not discontinued at all.'):
            with self.subTest(line=line):
                text = self.SIG.format(x=line)
                routing = detect.route(text, date(2026, 10, 14))
                inv = services.build(text, service_date=date(2026, 10, 14), routing=routing,
                                     context_facts=gi_context.extract_context(text))
                self.assertEqual(routing.finding('gi.flex_sig').status, 'performed')
                self.assertEqual([s.status for s in inv.services if s.family == 'gi.flex_sig'], ['performed'])

    def test_a_contracted_negation_with_more_in_its_sentence_holds_and_never_denies(self):
        status = detect.route(self.SIG.format(x='The examination wasn’t discontinued until the sigmoid colon.'),
                              date(2026, 10, 14)).finding('gi.flex_sig').status
        self.assertNotIn(status, ('performed', 'incomplete', 'negated', 'cancelled'))


class GenuineStatusUnchangedTests(SimpleTestCase):
    CASES = (('The colonoscopy was not performed.', ('negated',)), ('The procedure was aborted.', ('incomplete',)),
             ('Colonoscopy cancelled.', ('cancelled',)), ('Unable to complete the examination.', ('incomplete',)),
             ('The colonoscopy was deferred.', ('cancelled',)),
             ('The procedure was aborted, not completed.', ('incomplete',)),
             ('Examination aborted. The cecum was not reached.', ('incomplete',)))

    def test_denials_aborts_and_cancellations_keep_their_reading(self):
        for sentence, allowed in self.CASES:
            with self.subTest(sentence=sentence):
                status, service = read(report(sentence))
                self.assertIn(status, allowed)
                self.assertNotEqual(service.status, 'performed')

    def test_a_hedged_service_stays_held(self):
        status, _ = read(report('Colonoscopy possibly performed.', desc='Bowel preparation was adequate.'))
        self.assertEqual(status, 'uncertain')

    def test_the_undenied_stop_word_release_is_unchanged(self):  # _Undenied and interpretation 14
        status, service = read(report('The examination was complete and was not discontinued.'))
        self.assertEqual((status, service.status, service.completion), ('performed', 'performed', 'complete'))


class OtherOccasionTests(SimpleTestCase):
    def test_a_historical_reference_does_not_touch_todays_service(self):  # owner, 2026-10-27
        text = (BANNER + '\nUpper Endoscopy Report\nDate of procedure: 2026-10-19\nIndication\nPrior colonoscopy in '
                '2019 was not aborted.\n\nProcedure: EGD.\n\nFindings\nThe endoscope was advanced to the second portion '
                'of the duodenum. Normal esophagus.\n')
        self.assertEqual(read(text, 'gi.egd')[0], 'performed')
        self.assertEqual(read(text)[0], 'historical')

    def test_a_negated_status_told_of_another_day_reads_as_its_positive_twin(self):
        # a statement about another occasion never holds today's service, and its negation holds no more than it does
        # (2b82889f read the negated form "negated" only through the service-name grammar's "not")
        for negated, twin in (('The procedure was not aborted on 2026-09-01.', 'The procedure was aborted on 2026-09-01.'),
                              ('The procedure was not cancelled on 2026-09-01.',
                               'The procedure was cancelled on 2026-09-01.')):
            with self.subTest(negated=negated):
                status = read(report(negated))[0]
                self.assertEqual(status, read(report(twin))[0])
                self.assertNotIn(status, ('negated', 'cancelled', 'incomplete'))

    def test_a_plan_keeps_its_time(self):
        text = (BANNER + '\nGastroenterology Office Note\nDate of procedure: 2026-10-19\nProcedure: Office visit for '
                'anemia.\n\nPlan\nColonoscopy next month. The procedure will not be cancelled.\n')
        self.assertEqual(read(text)[0], 'planned')


def variant_text(spec, case):
    """A constructed case's text: the frame filled with its description and its extent section (the negated status
    sentence followed by the extra sentence), or, ``counterfactual``, the same document without the negated status
    sentence."""
    lead, status, trail = spec['leads'][case['lead']], spec['statuses'][case['status']], spec['trails'][case['trail']]
    extra = spec['extras'][case['extra']]
    sentence = f"{lead['text']} {status}{trail['text']}."
    ext = (sentence + extra['text']) if not case.get('counterfactual') else (extra['text'].strip() or 'See above.')
    return spec['frame'].format(desc=spec['descriptions'][case['desc']]['text'], find=spec['findings'], ext=ext)


class NegatedStatusVariantCorpusTests(SimpleTestCase):
    """A sample of the constructed variant corpus (tests/corpus/negated_status/variants.json), so the class stays
    measured in both directions on every change: each case's truth is fixed by its construction; the readings that
    differ from it are exactly those recorded, with their reason, in the file; and no negated status sentence ever
    makes performed a document that reads otherwise without it (the counterfactual invariant)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.spec = json.loads(VARIANTS.read_text(encoding='utf-8'))
        cls.readings = {}
        for case in cls.spec['cases']:
            status, service = read(variant_text(cls.spec, case))
            cls.readings[case['id']] = (status, service.status if service else None)

    def outcome(self, case):
        """'performed', 'denied' (negated, cancelled or incomplete) or 'held' (anything else): routing or the
        inventory reading performed is a performed reading."""
        status, inventory = self.readings[case['id']]
        if 'performed' in (status, inventory):
            return 'performed'
        return 'denied' if status in ('negated', 'cancelled', 'incomplete') else 'held'

    def test_every_case_reads_as_recorded(self):
        spec = self.spec
        self.assertTrue(spec['frame'].startswith('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT'))
        self.assertGreaterEqual(len(spec['cases']), 500)
        recorded = {row['id']: row for row in spec['known_differences']}
        for case in spec['cases']:
            with self.subTest(case=case['id']):
                got = self.outcome(case)
                allowed = case['expected']
                if got in allowed:
                    self.assertNotIn(case['id'], recorded, 'a recorded difference disappeared: remove it')
                else:
                    self.assertIn(case['id'], recorded, f'read {got}, expected one of {allowed}: a new difference')
                    self.assertEqual(recorded[case['id']]['reads'], got)

    def test_every_recorded_difference_has_its_reason(self):
        for row in self.spec['known_differences']:
            self.assertIn(row['reason'], self.spec['reasons'], row['id'])

    def test_a_negated_status_word_never_denies_the_service(self):
        for case in self.spec['cases']:
            if not self.spec['extras'][case['extra']]['genuine'] and not self.spec['trails'][case['trail']]['genuine']:
                with self.subTest(case=case['id']):
                    self.assertNotEqual(self.outcome(case), 'denied')

    def test_counterfactual_invariant(self):
        """Every case that reads performed also reads performed without its negated status sentence: the negated
        sentence only ever withdraws a false denial, it never adds performance."""
        memo = {}
        for case in self.spec['cases']:
            if self.outcome(case) != 'performed':
                continue
            text = variant_text(self.spec, dict(case, counterfactual=True))
            if text not in memo:
                status, service = read(text)
                memo[text] = 'performed' in (status, service.status if service else None)
            with self.subTest(case=case['id']):
                self.assertTrue(memo[text])
