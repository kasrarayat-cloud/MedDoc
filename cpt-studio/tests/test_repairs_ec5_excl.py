"""Repair round ec5, cluster EXCL: a code for an act the document states done today is never EXCLUDED by a misreading
(must-fix class 4, owner decision 2026-10-27). An exclusion needs both readers to agree and the clause structure to
support the not-done reading for THIS act - its own predicate, its own time; a word that belongs to another predicate
or another noun never decides it.

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


class ReplacementCueConfirmationTests(SimpleTestCase):
    """negtime-3 (repaired by 81b39461b, "a replacement cue governs its own object only"), confirmed at this round's
    head on the finding's inputs and on the phrasings its verifier found beside them: the act that replaced another is
    never excluded."""

    def test_the_replacing_act_is_never_excluded(self):
        for template, line, code, quote in (
                (EGD, 'Instead of a hot snare, a cold snare was used to remove the 8 mm gastric polyp.', '43251',
                 'a cold snare was used to remove the 8 mm gastric polyp'),
                (COLONOSCOPY, 'Rather than a snare, cold forceps were used to remove the 3 mm rectal polyp.', '45380',
                 'cold forceps were used to remove the 3 mm rectal polyp'),
                (COLONOSCOPY, 'Rather than hot snare, cold snare polypectomy was performed on the 6 mm sigmoid polyp.',
                 '45385', 'cold snare polypectomy was performed on the 6 mm sigmoid polyp'),
                (COLONOSCOPY, 'Rather than cold forceps, a cold snare was used to remove the 5 mm polyp.', '45385',
                 'a cold snare was used to remove the 5 mm polyp'),
                (COLONOSCOPY, 'Instead of forceps, a cold snare was used to remove the 5 mm polyp.', '45385',
                 'a cold snare was used to remove the 5 mm polyp'),
                (COLONOSCOPY, 'A cold snare, rather than a hot snare, was used to remove the 5 mm polyp.', '45385',
                 'A cold snare, rather than a hot snare, was used'),
                (EGD, 'Rather than a balloon, a Savary dilator was used to dilate the distal esophageal stricture.',
                 '43248', 'a Savary dilator was used to dilate the distal esophageal stricture')):
            with self.subTest(line=line):
                result = assessed(template.format(x=line), [(code, quote)])
                self.assertNotEqual(proposal(result, code).bucket, 'excluded')


class CoordinatedPredicateTimeTests(SimpleTestCase):
    """negtime-4: a plan, future or cancel word on a coordinated second predicate ("and will be sent to pathology", "and
    dilation was deferred", "and repeat EGD is planned") is that predicate's own; it never dates the act the first
    predicate states done, so the act's code is never excluded on it."""

    CASES = (
        (EGD, 'Cold forceps biopsies were obtained from the antrum and will be sent to pathology.', 'biopsy', '43239',
         'Cold forceps biopsies were obtained from the antrum', EGD_BASE),
        (EGD, 'Biopsies of the distal esophageal stricture were obtained and dilation was deferred until pathology '
              'returns.', 'biopsy', '43239', 'Biopsies of the distal esophageal stricture were obtained', EGD_BASE),
        (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare and will be sent to pathology.', 'snare', '45385',
         'A 6 mm sigmoid polyp was removed with a cold snare', COLON_BASE),
        (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare, retrieved and will be submitted for histology.',
         'snare', '45385', 'A 6 mm sigmoid polyp was removed with a cold snare', COLON_BASE),
        (EGD, 'Biopsies were taken from the antrum and we will follow up on the results.', 'biopsy', '43239',
         'Biopsies were taken from the antrum', EGD_BASE),
        (EGD, 'Biopsies were taken from the antrum and repeat EGD is planned in 8 weeks.', 'biopsy', '43239',
         'Biopsies were taken from the antrum', EGD_BASE),
        (COLONOSCOPY, 'Cold snare polypectomy of a 6 mm sigmoid polyp was performed and the specimen will be sent to '
                      'pathology.', 'snare', '45385', 'Cold snare polypectomy of a 6 mm sigmoid polyp was performed',
         COLON_BASE),
    )

    def test_the_first_act_reads_by_its_own_predicate(self):
        for template, line, kind, _, _, _ in self.CASES:
            with self.subTest(line=line):
                self.assertEqual(statuses(template.format(x=line), kind), ['performed'])

    def test_its_code_is_never_excluded_and_the_act_is_not_hidden(self):
        for template, line, kind, code, quote, base in self.CASES:
            with self.subTest(line=line):
                text = template.format(x=line)
                for cited in (quote, line):
                    self.assertNotEqual(proposal(assessed(text, [(code, cited)]), code).bucket, 'excluded')
                # with the base code alone the act done today stays visible (it had been hidden as planned)
                self.assertIn((kind, 'not_covered'), unresolved(assessed(text, [base])))

    def test_controls_an_act_s_own_time_or_denial_still_decides(self):
        for template, line, kind, status in (
                # the first predicate's own words
                (EGD, 'Biopsies were not obtained and will be taken at the next EGD.', 'biopsy', 'negated'),
                (COLONOSCOPY, 'Polypectomy was deferred and will be scheduled at a later date.', 'snare', 'cancelled'),
                (EGD, 'Biopsies will be obtained and will be sent to pathology.', 'biopsy', 'planned'),
                (COLONOSCOPY, 'A 6 mm sigmoid polyp will be removed with a cold snare and sent to pathology.', 'snare',
                 'planned'),
                # no predicate of its own before the coordinated one: the clause keeps its one reading
                (COLONOSCOPY, 'Biopsy and polypectomy will be performed at the next colonoscopy.', 'snare', 'planned'),
                (COLONOSCOPY, 'Biopsy and polypectomy will be performed at the next colonoscopy.', 'biopsy', 'planned'),
                # the coordinated negated predicate (cut before this round) leaves the first act done
                (EGD, 'Biopsies were obtained and dilation was not performed.', 'biopsy', 'performed')):
            with self.subTest(line=line):
                self.assertEqual(statuses(template.format(x=line), kind), [status])
        # a true exclusion stands: the act's own predicate denies it, or dates it after today
        for line, quote in (('Biopsies were not obtained and will be taken at the next EGD.', 'Biopsies were not obtained'),
                            ('Biopsies will be obtained and will be sent to pathology.', 'Biopsies will be obtained')):
            with self.subTest(line=line):
                result = assessed(EGD.format(x=line), [('43239', quote)])
                self.assertEqual(proposal(result, '43239').bucket, 'excluded')


class DateOwnershipTests(SimpleTestCase):
    """negtime-7: a date dates an act only as the act's own time. A birth date or a clock time is no act's time; a date
    of another clause or event (a subordinate or relative clause with a predicate of its own, a finding "found on
    barium swallow on <date>", a drug "held on <date>") leaves the act's time in doubt: its code is held with a
    question, never excluded on that date."""

    def test_a_birth_date_or_a_clock_time_is_no_acts_time(self):
        for template, line, kind in (
                (COLONOSCOPY, 'Ms. Alex Synthetic (DOB 03/04/1961) underwent colonoscopy today with cold snare '
                              'polypectomy of a 6 mm sigmoid polyp.', 'snare'),
                (COLONOSCOPY, 'Ms. Alex Synthetic (DOB 03/04/1961) underwent colonoscopy on 10/14/2026 with cold snare '
                              'polypectomy of a 6 mm sigmoid polyp.', 'snare'),
                (EGD, 'Patient Alex Synthetic, born 04-Mar-1961, underwent EGD with biopsies of the antrum.', 'biopsy'),
                (EGD, 'Biopsies were obtained from the antrum (patient born 1961).', 'biopsy'),
                (EGD, 'A 1 cm duodenal bulb ulcer with a visible vessel was found. Hemostasis was achieved with two '
                      'hemoclips at 2015.', 'bleeding_control'),
                (EGD, 'Two hemoclips were placed on the visible vessel at 2015 with hemostasis.', 'clip'),
                (EGD, 'Two hemoclips were placed at 2040 with hemostasis.', 'clip'),
                (COLONOSCOPY, 'A 6 mm polyp was removed at 1955 with a cold snare.', 'snare')):
            with self.subTest(line=line):
                self.assertEqual(statuses(template.format(x=line), kind), ['performed'])
        text = EGD.format(x='Patient Alex Synthetic, born 04-Mar-1961, underwent EGD with biopsies of the antrum.')
        self.assertNotEqual(proposal(assessed(text, [('43239', 'underwent EGD with biopsies of the antrum')]),
                                     '43239').bucket, 'excluded')
        text = EGD.format(x='Hemostasis was achieved with two hemoclips at 2015.')
        self.assertNotEqual(proposal(assessed(text, [('43255', 'Hemostasis was achieved with two hemoclips at 2015.')]),
                                     '43255').bucket, 'excluded')

    def test_another_events_date_holds_the_act_never_excludes_it(self):
        for template, line, kind, code in (
                (EGD, 'Upper endoscopy with balloon dilation was performed for the stricture found on barium swallow on '
                      '09/22/2026.', 'dilation', '43249'),
                (EGD, 'The stricture found on barium swallow on 09/22/2026 was dilated with a 15 mm through-the-scope '
                      'balloon.', 'dilation', '43249'),
                (COLONOSCOPY, 'A polyp seen on CT on 09/22/2026 was removed with a cold snare.', 'snare', '45385'),
                (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare after apixaban was held on '
                              '10/12/2026.', 'snare', '45385'),
                (COLONOSCOPY, 'Biopsies were obtained from the ulcer noted on 09/30/2026 in the cecum.', 'biopsy',
                 '45380')):
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['uncertain'])
                held = proposal(assessed(text, [(code, line)]), code)
                self.assertEqual((held.bucket, held.status), ('selected', 'needs_clarification'))

    def test_controls_the_acts_own_date_still_dates_it(self):
        for line, kind, status in (
                ('A 6 mm sigmoid polyp was removed with a cold snare on 09/03/2026.', 'snare', 'historical'),
                ('On 09/03/2026 a 6 mm sigmoid polyp was removed with a cold snare.', 'snare', 'historical'),
                ('A 6 mm sigmoid polyp was removed with a cold snare in 2019.', 'snare', 'historical'),
                ('A 6 mm sigmoid polyp will be removed with a cold snare on 11/20/2026.', 'snare', 'planned'),
                # the date inside the relative clause is the snare's own; the biopsy outside it is held
                ('Biopsies were taken from the polyp, which was removed with a cold snare on 09/03/2026.', 'snare',
                 'historical'),
                ('Biopsies were taken from the polyp, which was removed with a cold snare on 09/03/2026.', 'biopsy',
                 'uncertain')):
            with self.subTest(line=line, kind=kind):
                self.assertEqual(statuses(COLONOSCOPY.format(x=line), kind), [status])
        text = COLONOSCOPY.format(x='A 6 mm sigmoid polyp was removed with a cold snare on 09/03/2026.')
        self.assertEqual(proposal(assessed(text, [('45385', 'A 6 mm sigmoid polyp was removed with a cold snare')]),
                                  '45385').bucket, 'excluded')


class AttributiveTimeWordTests(SimpleTestCase):
    """negtime-5: a history or plan word inside a noun phrase that names a site, a lesion or a finding ("the prior
    polypectomy site", "the previous EMR scar", "the previously tattooed polyp", "old blood", "the next polyp") is the
    time of what that phrase names, never of an act outside it: the act's time is left in doubt, so its code is held
    with a question, never excluded. A time word on an occasion ("at the prior colonoscopy") still dates the act."""

    def test_a_time_word_on_another_noun_holds_the_act_never_excludes_it(self):
        for template, line, kind, code in (
                (COLONOSCOPY, 'Biopsies were obtained from the prior polypectomy site in the ascending colon.', 'biopsy',
                 '45380'),
                (COLONOSCOPY, 'The previous EMR scar in the ascending colon was biopsied with cold forceps.', 'biopsy',
                 '45380'),
                (COLONOSCOPY, 'The previously tattooed polyp in the ascending colon was removed with a hot snare.',
                 'snare', '45385'),
                (EGD, 'The prior biopsy site in the antrum was oozing and hemostasis was achieved with one hemoclip.',
                 'bleeding_control', '43255'),
                (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare at the prior polypectomy site.',
                 'snare', '45385'),
                (EGD, 'An ulcer with old blood in its base was treated with two hemoclips.', 'clip', '43255'),
                (COLONOSCOPY, 'The next polyp, a 5 mm sessile polyp in the transverse colon, was removed with a cold '
                              'snare.', 'snare', '45385')):
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['uncertain'])
                held = proposal(assessed(text, [(code, line)]), code)
                self.assertEqual((held.bucket, held.status), ('selected', 'needs_clarification'))

    def test_controls_a_time_word_on_its_own_noun_or_an_occasion_still_dates(self):
        for template, line, kind, status in (
                # the phrase's own act keeps the time word
                (COLONOSCOPY, 'The previous EMR scar in the ascending colon was biopsied with cold forceps.', 'emr',
                 'historical'),
                (COLONOSCOPY, 'The previously tattooed polyp in the ascending colon was removed with a hot snare.',
                 'tattoo', 'historical'),
                (EGD, 'The prior biopsy site in the antrum was oozing and hemostasis was achieved with one hemoclip.',
                 'biopsy', 'historical'),
                # an occasion, an adverb on the act's own predicate, or no phrase at all
                (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare at the prior colonoscopy.', 'snare',
                 'historical'),
                (EGD, 'Biopsies were taken at the previous EGD.', 'biopsy', 'historical'),
                (COLONOSCOPY, 'A polyp was previously removed from the sigmoid colon with a cold snare.', 'snare',
                 'historical'),
                (COLONOSCOPY, 'Prior polyps were removed with a cold snare.', 'snare', 'historical')):
            with self.subTest(line=line, kind=kind):
                self.assertEqual(statuses(template.format(x=line), kind), [status])
        for template, line, code in (
                (COLONOSCOPY, 'A 6 mm sigmoid polyp was removed with a cold snare at the prior colonoscopy.', '45385'),
                (EGD, 'Biopsies were taken at the previous EGD.', '43239')):
            with self.subTest(line=line):
                self.assertEqual(proposal(assessed(template.format(x=line), [(code, line)]), code).bucket, 'excluded')


class NegationScopeTests(SimpleTestCase):
    """negtime-6: a negation covers what it lists up to its predicate; an act inside a clause opened after it by a
    subordinator ("after", "once", "because", ...) is outside the negated list and reads by its own predicate, so its
    code is never excluded on that negation. A negation of the act's own ("... because no biopsies were taken") still
    denies it."""

    def test_an_act_in_a_clause_opened_after_the_negation_is_outside_it(self):
        for template, line, kind, code in (
                (EGD, 'No bleeding occurred after the biopsies were obtained from the antrum.', 'biopsy', '43239'),
                (EGD, 'There were no complications after biopsies were taken from the antrum.', 'biopsy', '43239'),
                (EGD, 'No residual bleeding followed once two hemoclips were placed on the vessel.', 'clip', '43255'),
                (EGD, 'There was no oozing once two hemoclips were placed on the vessel.', 'clip', '43255'),
                (EGD, 'There was no bleeding after the antral biopsies were taken with cold forceps.', 'biopsy', '43239'),
                (EGD, 'Hemostasis was achieved without rebleeding once two hemoclips were placed on the vessel.', 'clip',
                 '43255')):
            with self.subTest(line=line):
                text = template.format(x=line)
                self.assertEqual(statuses(text, kind), ['performed'])
                self.assertNotEqual(proposal(assessed(text, [(code, line)]), code).bucket, 'excluded')

    def test_controls_the_negations_own_list_still_denies(self):
        for template, line, kind in (
                (EGD, 'No biopsies were taken after the dilation.', 'biopsy'),
                (EGD, 'There were no biopsies taken since the mucosa was normal.', 'biopsy'),
                (EGD, 'No biopsies were obtained because the patient takes apixaban.', 'biopsy'),
                (COLONOSCOPY, 'No biopsies, polypectomy or tattoo was performed.', 'snare'),
                (COLONOSCOPY, 'No polyps were seen, so no polypectomy was performed.', 'snare'),
                # the act's own negation after the subordinator
                (EGD, 'There was no bleeding because no biopsies were taken.', 'biopsy'),
                (EGD, 'The mucosa was normal after inspection, so no biopsies were obtained.', 'biopsy')):
            with self.subTest(line=line):
                self.assertEqual(statuses(template.format(x=line), kind), ['negated'])
        for line in ('No biopsies were taken after the dilation.', 'There were no biopsies taken since the mucosa was '
                                                                   'normal.'):
            with self.subTest(line=line):
                self.assertEqual(proposal(assessed(EGD.format(x=line), [('43239', line)]), '43239').bucket, 'excluded')


class BothReadersAgreeTests(SimpleTestCase):
    """The engine half of negtime-6's class: where the inventory reads no act of a code's kind, the routing-era reading
    of the code's own passage excluded the code alone, even when the inventory reads an act stated done today in that
    very passage ("No residual bleeding followed once two hemoclips were placed on the vessel": clips placed, 43255
    excluded as "negated"). The two readers then disagree about the passage, so the code is held, never excluded."""

    def test_an_act_done_in_the_passage_routing_denies_holds_the_code(self):
        for line in ('No residual bleeding followed once two hemoclips were placed on the vessel.',
                     'There was no oozing once two hemoclips were placed on the vessel.'):
            with self.subTest(line=line):
                held = proposal(assessed(EGD.format(x=line), [('43255', line)]), '43255')
                self.assertEqual((held.bucket, held.status), ('selected', 'needs_clarification'))

    def test_controls_an_agreed_or_unopposed_exclusion_stands(self):
        # the inventory reads the code's own act as not done (planned), and routing agrees
        line = 'The 6 mm polyp was removed with a cold snare and will be biopsied at the next EGD.'
        self.assertEqual(proposal(assessed(COLONOSCOPY.format(x=line), [('45380', line)]), '45380').bucket, 'excluded')
        # nothing in the passage is read as done today
        line = 'Hemostasis will be achieved with hemoclips at the next EGD if the ulcer bleeds.'
        self.assertEqual(proposal(assessed(EGD.format(x=line), [('43255', line)]), '43255').bucket, 'excluded')


class DocumentationStampTests(SimpleTestCase):
    """negtime-10: the date that stamps when text was written - the app's own addendum header ("ADDENDUM (revision 2,
    added <stamp>)"), a signature's or a dictation's date - is the document's time, never an act's: the act the addendum
    adds reads by its own words, and its code is never excluded on the stamp."""

    NOTES = (
        (HEAD + 'Procedure date: 10/14/2026\n\nPROCEDURE NOTE: EGD\nIndication: Dyspepsia.\nTechnique: The upper endoscope '
                'was advanced to the second portion of the duodenum.\nFindings: The esophagus was normal.\nImpression: '
                'Normal.\n', 'Cold forceps biopsies were also taken from the duodenum to exclude celiac disease.', 'biopsy',
         '43239'),
        (HEAD + 'Procedure date: 10/14/2026\n\nPROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the '
                'cecum.\nFindings: The colon was normal.\nImpression: Normal.\n',
         'A 5 mm sigmoid polyp was also removed with a cold snare.', 'snare', '45385'),
    )

    @staticmethod
    def _with_addendum(note, sentence):
        from datetime import datetime, timezone
        from studio.jobs import addendum_block_text
        block = addendum_block_text(2, datetime(2026, 10, 27, 8, 15, tzinfo=timezone.utc), sentence)
        return note + block, block.strip().splitlines()[0]

    def test_an_addendum_stamp_never_dates_the_act_it_adds(self):
        for note, sentence, kind, code in self.NOTES:
            text, header = self._with_addendum(note, sentence)
            with self.subTest(sentence=sentence):
                self.assertEqual(statuses(text, kind), ['performed'])
                for quote in (sentence, header + '\n' + sentence, header):
                    self.assertNotEqual(proposal(assessed(text, [(code, quote)]), code).bucket, 'excluded')

    def test_a_signature_or_dictation_date_is_no_acts_time(self):
        for line in ('A 6 mm sigmoid polyp was removed with a cold snare (dictated 10/16/2026).',
                     'A 6 mm sigmoid polyp was removed with a cold snare, electronically signed 10/16/2026.'):
            with self.subTest(line=line):
                self.assertEqual(statuses(COLONOSCOPY.format(x=line), 'snare'), ['performed'])

    def test_controls_an_addendum_s_own_time_still_dates_its_act(self):
        note, _, _, _ = self.NOTES[1]
        text, _ = self._with_addendum(note, 'Repeat colonoscopy with polypectomy is planned on 11/20/2026.')
        self.assertEqual(statuses(text, 'snare'), ['planned'])
        text, _ = self._with_addendum(note, 'The 5 mm sigmoid polyp had been removed with a cold snare on 09/03/2026.')
        self.assertEqual(statuses(text, 'snare'), ['historical'])


class NoDocumentedServiceTests(SimpleTestCase):
    """The same rule where the inventory documents no service of the code's family (a gi.other procedure such as
    hemorrhoid banding): the routing-era reading of the code's own passage excluded the code alone, on the misreadings
    above ("No bleeding occurred after two rubber bands were placed ...", "... and will be checked at the next visit",
    "(DOB ...)"). The documented-service reader reads that passage's own act: where it reads the act done today, the two
    readers disagree and the code is held; where it agrees (a plan line, an earlier date), the exclusion stands."""

    ANOSCOPY = HEAD + ('Procedure date: 10/14/2026\n\nPROCEDURE NOTE: Anoscopy with hemorrhoid banding\nIndication: Bleeding '
                       'internal hemorrhoids.\nFindings:\nGrade 2 internal hemorrhoids were seen. {x}\nImpression: See '
                       'findings.\n')

    def test_an_act_this_reader_reads_done_holds_the_code(self):
        for line in ('No bleeding occurred after two rubber bands were placed on the internal hemorrhoids.',
                     'Two rubber bands were placed on the internal hemorrhoids and will be checked at the next visit.',
                     'Two rubber bands were placed on the hemorrhoids at the prior banding site.',
                     'Patient (DOB 03/04/1961): two rubber bands were placed on the internal hemorrhoids today.'):
            with self.subTest(line=line):
                held = proposal(assessed(self.ANOSCOPY.format(x=line), [('46221', line)]), '46221')
                self.assertEqual((held.bucket, held.status), ('selected', 'needs_clarification'))
                self.assertTrue(any(c.fact == 'performed_status' for c in held.clarifications))

    def test_controls_an_agreed_exclusion_stands_and_a_done_act_stays_ready(self):
        for line in ('Two rubber bands were placed on the internal hemorrhoids on 09/03/2026.',
                     'Two rubber bands will be placed on the internal hemorrhoids at the next visit.',
                     'No rubber bands were placed on the internal hemorrhoids.'):
            with self.subTest(line=line):
                self.assertEqual(proposal(assessed(self.ANOSCOPY.format(x=line), [('46221', line)]), '46221').bucket,
                                 'excluded')
        line = 'Two rubber bands were placed on the internal hemorrhoids.'
        self.assertEqual(proposal(assessed(self.ANOSCOPY.format(x=line), [('46221', line)]), '46221').status, 'ready')
