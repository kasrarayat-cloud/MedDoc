"""Completion repair (owner directive 2026-11-06; HARNESS.md "Completion repair (2026-11-06)"), builder A: act frames
in the documented-service reader. Each rule is pinned by minimal positive and negative pairs, its refuter sentences,
and an equivalent wording in another layout or GI family. Real engine and readers, no provider or database calls.
Synthetic documents only (the retained cases appear through paraphrases of their structure, as the earlier repairs'
tests do).

- U6, placement never overwrites outcome: an act on a Procedure line is promoted to performed only where its own clause
  states no outcome (services._outcome_in_doubt).
- U13, coordinated anatomy: "the right and left colon" reads both sites (services._anatomy_in).
"""
from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi import services as gi_services
from tests.test_harness_engine import DAY, code, corti, proposal, read, run, span

COLON_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
              'Endoscopy Report\n'
              'Date of service: 2026-10-14\n'
              'Endoscopist: Test Endoscopist, MD\n'
              'Indication: Chronic diarrhea.\n')
FAILED_SNARE = ('Hot snare polypectomy of a 14 mm polyp in the sigmoid colon was attempted, but the polypectomy was '
                'unsuccessful because of poor positioning; the polyp was left in place.')
FAILED_DILATION = ('Balloon dilation of a distal esophageal stricture was attempted, but the dilation was unsuccessful '
                   'because of poor positioning.')


def inventory(text, day=DAY):
    return gi_services.build(text, service_date=day, routing=detect.route(text, day))


def acts_of(text, family, kind):
    svc = next(s for s in inventory(text).services if s.family == family)
    return [(a.status, a.cues) for a in svc.acts if a.kind == kind]


def outcome(text, value, quote, *primary):
    """(Corti's bucket/status, a participant's bucket/status) for ``value`` on ``quote``."""
    base = [(c, span(text, q)) for c, q in primary]
    by_corti = proposal(run(text, corti(*base, (value, span(text, quote)))), value)
    by_astra = proposal(run(text, corti(*base), [read('astra', [code(text, value, quote)])]), value)
    return (by_corti.bucket, by_corti.status), (by_astra.bucket, by_astra.status)


class PlacementNeverOverwritesOutcomeTests(SimpleTestCase):
    """U6 (D|RT-f1, D|RT-f3, D|ARCH-D3a): a failed attempt sharing the Procedure line had been promoted to a performed
    act ('performed: listed on the procedure line'), so a code citing it was READY. The listing places the act; the
    clause's own outcome decides it."""

    def test_a_failed_attempt_on_the_procedure_line_is_not_performed(self):
        text = (COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum. The appendiceal orifice '
                'was identified. ' + FAILED_SNARE + '\n')
        readings = acts_of(text, 'gi.colonoscopy', 'snare')
        self.assertTrue(readings)
        self.assertNotIn('performed', [status for status, _ in readings])
        self.assertTrue(all('performed: listed on the procedure line' not in cues for _, cues in readings))
        for label, (bucket, status) in zip(('corti', 'astra'), outcome(text, '45385', FAILED_SNARE)):
            with self.subTest(label):
                self.assertNotEqual(status, 'ready')

    def test_the_same_attempt_on_its_own_line_reads_the_same(self):
        on_line = (COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum. ' + FAILED_SNARE + '\n')
        own_line = (COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum.\n' + FAILED_SNARE
                    + '\n')
        self.assertEqual([status for status, _ in acts_of(on_line, 'gi.colonoscopy', 'snare')],
                         [status for status, _ in acts_of(own_line, 'gi.colonoscopy', 'snare')])
        self.assertEqual(outcome(on_line, '45385', FAILED_SNARE), outcome(own_line, '45385', FAILED_SNARE))

    def test_an_egd_dilation_attempt_on_the_procedure_line(self):
        text = (COLON_HEAD + 'Procedure: EGD. The gastroscope was advanced to the second portion of the duodenum. '
                + FAILED_DILATION + '\n')
        self.assertNotIn('performed', [status for status, _ in acts_of(text, 'gi.egd', 'dilation')])
        for label, (bucket, status) in zip(('corti', 'astra'), outcome(text, '43249', FAILED_DILATION)):
            with self.subTest(label):
                self.assertNotEqual(status, 'ready')

    def test_a_hedge_or_an_open_question_on_the_procedure_line_is_not_promoted(self):
        for sentence in ('Hot snare polypectomy of the sigmoid polyp was possibly performed.',
                         'It is unknown whether hot snare polypectomy of the sigmoid polyp was performed.'):
            with self.subTest(sentence):
                text = COLON_HEAD + 'Procedure: Colonoscopy. The colonoscope was advanced to the cecum. ' + sentence + '\n'
                self.assertNotIn('performed', [status for status, _ in acts_of(text, 'gi.colonoscopy', 'snare')])

    def test_a_labelled_procedures_line_with_its_attempt(self):
        line = 'Procedures performed: Colonoscopy; hot snare polypectomy attempted, unsuccessful.'
        text = COLON_HEAD + line + '\nThe colonoscope was advanced to the cecum.\n'
        self.assertNotIn('performed', [status for status, _ in acts_of(text, 'gi.colonoscopy', 'snare')])

    def test_a_bare_listing_is_still_placed_as_performed(self):
        # the control: a listing with no outcome of its own stands in for the performance statement, as before
        listing = 'Colonoscopy with cold snare polypectomy'
        text = (COLON_HEAD + 'Procedure: ' + listing + '\nThe colonoscope was advanced to the cecum. A 6 mm polyp was '
                'seen in the sigmoid colon.\n')
        self.assertIn('performed', [status for status, _ in acts_of(text, 'gi.colonoscopy', 'snare')])
        self.assertEqual(outcome(text, '45385', listing)[0], ('selected', 'ready'))

    def test_the_failure_is_one_shared_test(self):
        self.assertTrue(gi_services._outcome_in_doubt(('uncertain: attempted',)))
        self.assertTrue(gi_services._outcome_in_doubt(('uncertain: unsuccessful',)))
        self.assertTrue(gi_services._outcome_in_doubt((gi_services.CONDITION_CUE,)))
        self.assertFalse(gi_services._outcome_in_doubt(('uncertain: named without an act predicate',)))
        self.assertFalse(gi_services._outcome_in_doubt(('uncertain: no performance statement',)))


EGD_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nUpper endoscopy report\n'
            'Date of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nProcedure\n'
            'The gastroscope was passed to the second portion of the duodenum.\n')
COMBINED_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nEndoscopy Procedure Report\n'
                 'Date of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
                 'Procedure: Upper endoscopy and colonoscopy\n')
FOUND = 'A large meat bolus was found at 34 cm. '


def removal_acts(text, family='gi.egd'):
    svc = next((s for s in inventory(text).services if s.family == family), None)
    return [] if svc is None else [(a.status, a.anatomy) for a in svc.acts if a.kind == 'foreign_body']


def subject(sentence, verb='removed'):
    """The removal predicate's subject as _removal_subject reads it (the verb group's start, as pass 3 passes it)."""
    import re
    m = re.search(r'\b' + verb + r'\b', sentence)
    group = gi_services._VERB_GROUP.search(sentence, max(0, m.start() - 60), m.start())
    start = group.start() if group is not None and gi_services._GROUP_AUXILIARY.search(group.group(0)) else m.start()
    found = gi_services._removal_subject(sentence, 0, start)
    return None if found is None else (sentence[found[0]:found[1]], found[2])


class RemovalSubjectTests(SimpleTestCase):
    """U1's second half, the structural subject (services._removal_subject, the contract of R2's clauses.subject_head):
    the nearest preceding noun phrase of the clause that is no prepositional object and no verb's object inside a
    relative clause or a participial modifier; a comma aside and a parenthesis are passed over; a partitive resolves to
    its complement. Every F-ACTS refuter's removal is another noun's."""

    def test_the_refuters_removal_is_another_nouns(self):
        cases = {
            'Because the meat bolus passed spontaneously the scope was removed.': 'scope',
            'The meat bolus remained impacted yet the overtube was removed.': 'overtube',
            'The Roth net that missed the bolus was removed.': 'net',
            'The meat bolus remained impacted while the scope was removed.': 'scope',
            'The overtube placed over the bolus was removed.': 'overtube',
            'The overtube protecting the meat bolus was removed.': 'overtube',
            'The scope that had pushed the bolus into the stomach was then removed.': 'scope',
            'The scope that pushed the meat bolus was removed.': 'scope',
            'After the meat bolus passed into the stomach the scope was removed.': 'scope',
            'The steak impaction cleared as soon as the guidewire was removed.': 'guidewire',
            'After a 50 mg propofol bolus, the bite block was removed.': 'block',
            'A fentanyl bolus was given and the clip was then removed.': 'clip',
            'The scope having pushed the bolus was removed.': 'scope',
        }
        for sentence, head in cases.items():
            with self.subTest(sentence):
                self.assertEqual(subject(sentence), (head, head))

    def test_the_boluss_own_removal(self):
        cases = {
            'the bolus was removed through the mouth': ('bolus', 'bolus'),
            'The bolus in the distal esophagus was removed.': ('bolus', 'bolus'),
            'The bolus found in the esophagus was removed.': ('bolus', 'bolus'),
            'The meat bolus, which was large, was removed.': ('bolus', 'bolus'),
            'The meat bolus (3 cm) was removed.': ('bolus', 'bolus'),
            'Meat bolus removed with a Roth net.': ('bolus', 'bolus'),
            'The bolus could not be removed.': ('bolus', 'bolus'),
            'Fragments of the bolus were removed with a net.': ('bolus', 'fragments'),
            'The bolus fragments were removed.': ('bolus', 'fragments'),
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence):
                self.assertEqual(subject(sentence), expected)

    def test_an_unreadable_subject_is_none(self):
        # an intransitive verb before a new clause's subject, or a participle among bare modifiers: no subject is read
        for sentence in ('Once the steak impaction cleared the overtube was removed.',
                         'Overtube protecting meat bolus was removed.', 'Once dislodged the bolus was removed.'):
            with self.subTest(sentence):
                self.assertIsNone(subject(sentence))


class BolusAntecedentTests(SimpleTestCase):
    """U1 (d44a77b3, 39f0ac49): "An impacted meat bolus was found ... the bolus was removed through the mouth" read no
    act, so a participant's 43247 was listed "not documented as done". A bolus named by its food, or a definite anaphor
    whose documented antecedent is a food or a foreign body, is the foreign-body act when it is the removal predicate's
    subject or object - and takes its antecedent's site."""

    def test_the_anaphor_of_a_food_bolus_removed_today(self):
        for removal in ('The bolus was removed with a Roth net.', 'We removed the bolus with a Roth net.',
                        'The bolus was grasped with a Roth net and removed through the mouth.',
                        'Fragments of the bolus were removed with a Roth net.',
                        'Removal of the bolus with a Roth net was performed.'):
            with self.subTest(removal):
                text = EGD_HEAD + FOUND + removal + '\n'
                self.assertEqual([s for s, _ in removal_acts(text)], ['performed'])
                self.assertEqual(outcome(text, '43247', removal), (('selected', 'ready'), ('selected', 'ready')))

    def test_a_bolus_named_by_its_food_or_an_impaction(self):
        for text, quote in (
                (EGD_HEAD + 'The meat bolus was removed with a retrieval net.\n', 'The meat bolus was removed with a retrieval net.'),
                (EGD_HEAD + 'A steak impaction was found in the distal esophagus. The impaction was removed with a Roth net.\n',
                 'The impaction was removed with a Roth net.'),
                (EGD_HEAD + 'She could not swallow after a steak impaction at dinner. The bolus was removed with a Roth net.\n',
                 'The bolus was removed with a Roth net.'),
                (EGD_HEAD + 'A coin was seen in the stomach. The coin was removed with a Roth net.\n',
                 'The coin was removed with a Roth net.'),
                (EGD_HEAD + 'A swallowed object was seen in the stomach. The object was removed with a Roth net.\n',
                 'The object was removed with a Roth net.')):
            with self.subTest(quote):
                self.assertEqual([s for s, _ in removal_acts(text)], ['performed'])
                self.assertEqual(outcome(text, '43247', quote)[0], ('selected', 'ready'))

    def test_no_food_or_foreign_antecedent_is_no_act(self):
        for text in (EGD_HEAD + 'A 50 mg bolus of propofol was given. The bolus was removed.\n',
                     EGD_HEAD + 'A saline bolus was injected. The bolus was removed.\n',
                     EGD_HEAD + 'A bolus of retained secretions was seen. The bolus was removed with suction.\n',
                     EGD_HEAD + 'The bolus was removed with a Roth net.\n',
                     EGD_HEAD + 'No food impaction was seen. The impaction was removed.\n',
                     EGD_HEAD + 'An object resembling a pill was seen. The object was removed.\n'):
            with self.subTest(text.split('\n')[-2]):
                self.assertEqual(removal_acts(text), [])

    def test_the_f_acts_refuters_stay_non_removals(self):
        for sentence in ('Because the meat bolus passed spontaneously the scope was removed.',
                         'The meat bolus remained impacted yet the overtube was removed.',
                         'The Roth net that missed the bolus was removed.',
                         'The meat bolus remained impacted while the scope was removed.',
                         'The overtube placed over the bolus was removed.',
                         'The overtube protecting the meat bolus was removed.',
                         'The scope that had pushed the bolus into the stomach was then removed.',
                         'Once the steak impaction cleared the overtube was removed.',
                         'An impacted meat bolus was found.', 'No food impaction was seen.'):
            with self.subTest(sentence):
                text = EGD_HEAD + FOUND + sentence + '\n'
                self.assertNotIn('performed', [s for s, _ in removal_acts(text)])
                for path in outcome(text, '43247', sentence):
                    self.assertNotEqual(path[1], 'ready')

    def test_a_push_a_passage_or_another_time_or_source_is_never_ready(self):
        for sentence in ('The bolus was cleared into the stomach with gentle insufflation.',
                         'The bolus was dislodged distally into the stomach with the tip of the scope.',
                         'The bolus was cleared by peristalsis.', 'The bolus could not be removed.',
                         'At the referring hospital, the bolus was removed with a Roth net.',
                         'The bolus will be removed at a later date.'):
            with self.subTest(sentence):
                text = EGD_HEAD + FOUND + sentence + '\n'
                self.assertNotIn('performed', [s for s, _ in removal_acts(text)])
                for path in outcome(text, '43247', sentence):
                    self.assertNotEqual(path[1], 'ready')

    def test_the_antecedents_site_binds_it_where_two_families_are_present(self):
        removal = 'A retrieval net was passed through the working channel and the bolus was removed through the mouth.'
        colon = 'The colonoscope was advanced to the cecum. A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n'
        for antecedent, site in (('An impacted meat bolus was found in the distal esophagus.', ('distal esophagus',)),
                                 ('A large impacted meat bolus was encountered at 35 cm from the incisors.', ('esophagus',))):
            with self.subTest(antecedent):
                text = (COMBINED_HEAD + 'The gastroscope was advanced to the second portion of the duodenum. ' + antecedent
                        + ' ' + removal + '\n' + colon)
                self.assertEqual(removal_acts(text), [('performed', site)])
                quote = 'the bolus was removed through the mouth'
                self.assertEqual(outcome(text, '43247', quote), (('selected', 'ready'), ('selected', 'ready')))

    def test_a_colon_foreign_body_binds_to_the_colonoscopy(self):
        # C3-1-1's refuter: the site-less removal of a foreign body seen in the transverse colon is the colonoscopy's,
        # never the upper endoscopy's (43247 not READY; 45379 READY)
        text = (COMBINED_HEAD + 'The gastroscope was advanced to the second portion of the duodenum.\n'
                'The colonoscope was advanced to the cecum. A foreign body (a swallowed coin) was seen in the transverse '
                'colon. The foreign body was removed with a Roth net.\n')
        quote = 'The foreign body was removed with a Roth net.'
        self.assertEqual(removal_acts(text, 'gi.colonoscopy'), [('performed', ('transverse colon',))])
        self.assertEqual(removal_acts(text, 'gi.egd'), [])
        for path in outcome(text, '43247', quote):
            self.assertNotEqual(path[1], 'ready')
        self.assertEqual(outcome(text, '45379', quote)[0], ('selected', 'ready'))

    def test_no_stated_site_with_two_families_stays_unbound(self):
        # a recorded residual: "at 34 cm" names no site, so with two families present the act is not attributed
        text = (COMBINED_HEAD + 'The gastroscope was advanced to the second portion of the duodenum. ' + FOUND
                + 'The bolus was removed with a Roth net.\nThe colonoscope was advanced to the cecum.\n')
        self.assertEqual(removal_acts(text), [])


LISTED_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
               'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
               'Procedure: Colonoscopy with hot snare polypectomy\n'
               'The colonoscope was advanced to the cecum and the examination was completed.\n'
               'A 9 mm pedunculated polyp in the sigmoid colon was seen.\n')
LISTING = 'Colonoscopy with hot snare polypectomy'


def dispositions(text, family='gi.colonoscopy'):
    svc = next(s for s in inventory(text).services if s.family == family)
    return [lesion.disposition for lesion in svc.lesions]


class DispositionTests(SimpleTestCase):
    """U6's base false READY (H2|NEG3-5) and U13: "The polyp was left in place." under "Procedure: Colonoscopy with hot
    snare polypectomy" left the lesion's disposition unknown and the listed polypectomy READY. A recorded lesion's
    stated disposition is read from the predicate whose subject it is; a listed removal whose every lesion is stated
    not removed today is contradicted, so it is held."""

    def test_left_in_place_not_removed_or_scheduled(self):
        for sentence, disposition in (('The polyp was left in place.', 'untreated'),
                                      ('The polyp was left in situ.', 'untreated'),
                                      ('The polyp was not removed.', 'untreated'),
                                      ('The polyp could not be removed because of anticoagulation.', 'untreated'),
                                      ('The polyp will be removed at a later date.', 'scheduled')):
            with self.subTest(sentence):
                text = LISTED_HEAD + sentence + '\n'
                self.assertEqual(dispositions(text), [disposition])
                self.assertEqual(acts_of(text, 'gi.colonoscopy', 'snare')[0][0], 'uncertain')
                self.assertEqual(outcome(text, '45385', LISTING)[0], ('selected', 'needs_clarification'))

    def test_the_same_in_an_upper_endoscopy(self):
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nUpper endoscopy report (fictional)\n'
                'Date of service: 2026-10-14\nProcedure: Upper endoscopy with snare polypectomy\n'
                'The gastroscope was advanced to the second portion of the duodenum.\n'
                'A 10 mm sessile polyp in the gastric body was seen.\nThe polyp was left in place.\n')
        self.assertEqual(dispositions(text, 'gi.egd'), ['untreated'])
        self.assertEqual(outcome(text, '43251', 'Upper endoscopy with snare polypectomy')[0][1], 'needs_clarification')

    def test_a_negative_quantifier_another_time_or_another_lesion_contradicts_nothing(self):
        # "No polyps were removed." names no recorded lesion (the dropped kindless branch's shape, a recorded base
        # residual); a past statement is no disposition today; a second lesion with nothing stated keeps the listing
        for sentence in ('No polyps were removed.', 'Previously, the polyp was left in place.',
                         'The polyp was left in place. A 5 mm polyp in the cecum was seen.'):
            with self.subTest(sentence):
                text = LISTED_HEAD + sentence + '\n'
                self.assertNotIn('uncertain', [s for s, _ in acts_of(text, 'gi.colonoscopy', 'snare')])
                self.assertEqual(outcome(text, '45385', LISTING)[0], ('selected', 'ready'))

    def test_a_removal_done_beside_a_lesion_left_in_place(self):
        text = (LISTED_HEAD + 'The polyp was left in place.\n'
                'A 6 mm polyp in the cecum was removed with a hot snare.\n')
        self.assertEqual(dispositions(text), ['untreated', 'removed'])
        self.assertEqual(outcome(text, '45385', 'A 6 mm polyp in the cecum was removed with a hot snare.')[0],
                         ('selected', 'ready'))

    def test_the_failed_attempts_lesion(self):
        text = (COLON_HEAD + 'Procedure: The colonoscope was advanced to the terminal ileum.\n'
                'A 6 mm polyp in the descending colon was removed with a cold snare and retrieved.\n' + FAILED_SNARE + '\n')
        self.assertEqual(dispositions(text), ['removed', 'untreated'])


class CoordinatedAnatomyTests(SimpleTestCase):
    """U13: "from the right and left colon" had read the descending colon only (the left colon) - the coordinated
    modifier shares the site's head."""

    @staticmethod
    def sites(sentence):
        return [name for name, _, _, _ in gi_services._anatomy_in(sentence, 0, len(sentence))]

    def test_a_shared_head_reads_both_sites(self):
        cases = {
            'Random cold forceps biopsies were obtained from the right and left colon.': ['ascending colon',
                                                                                         'descending colon'],
            'Biopsies were obtained from the left and right colon.': ['descending colon', 'ascending colon'],
            'Biopsies were obtained from the proximal and distal esophagus.': ['proximal esophagus', 'distal esophagus'],
            'Biopsies were obtained from the mid and distal esophagus.': ['mid esophagus', 'distal esophagus'],
            'Biopsies were obtained from the upper or lower esophagus.': ['proximal esophagus', 'distal esophagus'],
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence):
                self.assertEqual(self.sites(sentence), expected)

    def test_a_coordination_of_whole_sites_adds_nothing(self):
        cases = {
            'Biopsies of the stomach and duodenal bulb.': ['stomach', 'duodenal bulb'],
            'Biopsies of the cecum and ascending colon.': ['cecum', 'ascending colon'],
            'Biopsies from the sigmoid and descending colon.': ['sigmoid colon', 'descending colon'],
            'Biopsies of the antrum and body.': ['gastric antrum and body'],
            'Biopsies from the left colon.': ['descending colon'],
        }
        for sentence, expected in cases.items():
            with self.subTest(sentence):
                self.assertEqual(self.sites(sentence), expected)

    def test_the_act_carries_both_sites(self):
        biopsy = 'Random cold forceps biopsies were obtained from the right and left colon to evaluate for microscopic colitis.'
        text = (COLON_HEAD + 'Procedure: The colonoscope was advanced to the terminal ileum.\n' + biopsy + '\n')
        svc = next(s for s in inventory(text).services if s.family == 'gi.colonoscopy')
        act = next(a for a in svc.acts if a.kind == 'biopsy')
        self.assertEqual(act.anatomy, ('ascending colon', 'descending colon'))
