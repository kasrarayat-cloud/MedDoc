"""Refutation r1 repairs, cluster N: clause structure and negation in the documented-service reader
(studio/gi/services.py: NOT_VERB, the negation part of read_clause, _CLAUSE_CUT and clauses()).

Each text is a fresh synthetic paraphrase written for the case under test (fictional patients only); the expected
readings are written here, outside the reader. None of them is a sentence the reader matches by its exact wording.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = date(2026, 10, 14)
COLONOSCOPY = HEAD + ('Procedure date: 10/14/2026\n\nPROCEDURE NOTE: Colonoscopy\nIndication: Screening colonoscopy, average '
                      'risk.\nTechnique: The colonoscope was advanced to the cecum, identified by the appendiceal orifice and '
                      'ileocecal valve.\nFindings:\nThe preparation was good. {x}\nImpression: See findings.\n')
EGD = HEAD + ('Procedure date: 10/14/2026\n\nPROCEDURE NOTE: EGD\nIndication: Dyspepsia.\nTechnique: The upper endoscope was '
              'advanced to the second portion of the duodenum.\nFindings:\nThe esophagus was normal. {x}\nImpression: See '
              'findings.\n')
SIGMOIDOSCOPY = HEAD + ('Procedure date: 10/14/2026\n\nPROCEDURE NOTE: Flexible sigmoidoscopy\nIndication: Rectal bleeding.\n'
                        'Technique: The sigmoidoscope was advanced to the descending colon.\nFindings:\n{x}\nImpression: '
                        'See findings.\n')
COLON_BASE = ('45378', 'The colonoscope was advanced to the cecum')
EGD_BASE = ('43235', 'The upper endoscope was advanced to the second portion of the duodenum')


def inventory(text, day=DAY):
    return services.build(text, service_date=day, routing=detect.route(text, day),
                          context_facts=gi_context.extract_context(text))


def statuses(text, kind, day=DAY):
    """The statuses the inventory reads for every act of ``kind``, in any service."""
    return sorted({a.status for s in inventory(text, day).services for a in s.acts if a.kind == kind})


def assessed(text, picks, day=DAY):
    """The engine's result for provider-selected (code, quote) picks against an empty reference."""
    codes = []
    for code, quote in picks:
        start = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(quote), quote, True),)))
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def proposal(result, code):
    return next(p for p in result.proposals if p.code == code)


def unresolved(result):
    return [(u.get('act'), u.get('reason')) for u in (result.completeness or {}).get('unresolved_items', [])]


def sent_for_review(result):
    """The unresolved items a paid second review would ask about (both readers read them as done today)."""
    return [(u.get('act'), u.get('reason')) for u in (result.completeness or {}).get('unresolved_items', [])
            if u.get('second_review') is True]


class ContractionNegationTests(SimpleTestCase):
    """negtime-1: an auxiliary's contraction is the same negation as its "not", in either apostrophe."""

    def test_a_contracted_auxiliary_denies_its_act(self):
        for template, line, kind in (
                (EGD, 'Biopsies weren’t taken because the patient takes apixaban.', 'biopsy'),
                (COLONOSCOPY, 'A 6 mm polyp was seen in the sigmoid colon. Polypectomy wasn’t performed because the '
                              'patient takes apixaban.', 'snare'),
                (EGD, "Biopsies haven't been obtained.", 'biopsy'),
                (EGD, 'A biopsy hasn’t been taken from the antrum.', 'biopsy'),
                (EGD, "Cold forceps biopsies hadn't been obtained by the end of the examination.", 'biopsy'),
                (EGD, 'Biopsies couldn’t be obtained because of oozing.', 'biopsy'),
                (COLONOSCOPY, 'The 7 mm descending colon polyp wasn’t removed with a snare.', 'snare')):
            with self.subTest(line=line):
                self.assertEqual(statuses(template.format(x=line), kind), ['negated'])

    def test_controls_the_uncontracted_and_ascii_forms_read_as_before(self):
        for line in ('Biopsies were not taken because the patient takes apixaban.',
                     "Biopsies weren't taken because the patient takes apixaban."):
            with self.subTest(line=line):
                self.assertEqual(statuses(EGD.format(x=line), 'biopsy'), ['negated'])
        self.assertEqual(statuses(EGD.format(x='Biopsies were taken from the antrum with cold forceps.'), 'biopsy'),
                         ['performed'])

    def test_a_contraction_on_another_predicate_leaves_the_act_done(self):
        # the coordinated subject with its own contracted predicate is its own clause; the subordinate clause's
        # contracted "not" is its own predicate's
        self.assertEqual(statuses(EGD.format(x='Biopsies were obtained and dilation wasn’t performed.'), 'biopsy'),
                         ['performed'])
        self.assertEqual(statuses(COLONOSCOPY.format(x='Cold snare polypectomy of a 6 mm sigmoid polyp was performed '
                                                       'because the polyp didn’t appear invasive.'), 'snare'),
                         ['performed'])

    def test_a_contracted_completion_denial_is_no_discontinuation(self):
        for line in ('The examination was complete and wasn’t discontinued.',
                     "The examination wasn't discontinued at any point."):
            with self.subTest(line=line):
                sig = [s for s in inventory(SIGMOIDOSCOPY.format(x=line)).services if s.family == 'gi.flex_sig']
                self.assertEqual([(s.status, s.completion) for s in sig], [('performed', 'unknown')])
        sig = [s for s in inventory(SIGMOIDOSCOPY.format(x='The examination was discontinued because of discomfort.'))
               .services if s.family == 'gi.flex_sig']
        self.assertEqual([s.status for s in sig], ['incomplete'])

    def test_the_base_code_is_not_held_and_nothing_is_sent_for_a_denied_act(self):
        text = EGD.format(x='Biopsies weren’t taken because the patient takes apixaban.')
        result = assessed(text, [EGD_BASE])
        self.assertEqual(proposal(result, '43235').status, 'ready')
        self.assertEqual(unresolved(result), [])
        result = assessed(text, [('43239', 'Biopsies weren’t taken')])
        self.assertNotEqual(proposal(result, '43239').status, 'ready')


class ReplacementCueTests(SimpleTestCase):
    """negtime-3: a replacement cue ("instead of", "rather than") governs its own object only - one noun phrase right
    after it - never the act that replaced it."""

    def test_the_act_that_replaced_another_reads_done(self):
        for template, line, done, replaced in (
                (EGD, 'Instead of a hot snare, a cold snare was used to remove the 8 mm gastric polyp.', 'snare', 'snare'),
                (COLONOSCOPY, 'Rather than a snare, cold forceps were used to remove the 3 mm rectal polyp.', 'biopsy',
                 'snare'),
                (COLONOSCOPY, 'Rather than cold forceps, a cold snare was used for the 4 mm sigmoid polyp.', 'snare',
                 'biopsy'),
                (COLONOSCOPY, 'In place of the hot snare, cold snare polypectomy was performed on the 6 mm sigmoid '
                              'polyp.', 'snare', 'snare')):
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertIn('performed', statuses(text, done))
                self.assertIn('negated', statuses(text, replaced))

    def test_what_is_named_as_replaced_is_still_negated(self):
        for template, line, kind, other in (
                (COLONOSCOPY, 'Cold forceps were used instead of a snare for the 3 mm rectal polyp.', 'snare', 'biopsy'),
                (COLONOSCOPY, 'The 3 mm polyp was removed with cold forceps rather than a cold snare.', 'snare', 'biopsy'),
                (COLONOSCOPY, 'A cold snare was used instead of cold forceps biopsy for the 5 mm polyp.', 'biopsy',
                 'snare'),
                (COLONOSCOPY, 'The 25 mm polyp was tattooed instead of removing it with a hot snare.', 'snare', 'tattoo')):
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['negated'])
                self.assertEqual(statuses(text, other), ['performed'])
        self.assertEqual(statuses(COLONOSCOPY.format(x='A 6 mm sessile polyp was seen in the sigmoid colon. The polyp '
                                                       'was photographed instead of being removed by cold snare.'),
                                  'snare'), ['negated'])
        text = HEAD + ('Procedure date: 10/14/2026\n\nPROCEDURE NOTE: EGD\nTechnique: Because the echoendoscope was '
                       'unavailable, an EGD was performed rather than EUS. The upper endoscope was advanced to the second '
                       'portion of the duodenum.\nImpression: Normal.\n')
        self.assertEqual([s.status for s in inventory(text).services if s.family == 'gi.eus'], ['negated'])

    def test_the_replacing_act_is_never_excluded_nor_sent_for_review(self):
        text = EGD.format(x='Instead of a hot snare, a cold snare was used to remove the 8 mm gastric polyp.')
        result = assessed(text, [('43251', 'a cold snare was used to remove the 8 mm gastric polyp')])
        self.assertNotEqual(proposal(result, '43251').bucket, 'excluded')
        self.assertEqual(sent_for_review(result), [])
        text = COLONOSCOPY.format(x='Rather than a snare, cold forceps were used to remove the 3 mm rectal polyp.')
        result = assessed(text, [('45380', 'cold forceps were used to remove the 3 mm rectal polyp')])
        self.assertNotEqual(proposal(result, '45380').bucket, 'excluded')
        self.assertEqual(sent_for_review(result), [])
