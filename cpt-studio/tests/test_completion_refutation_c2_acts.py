"""Refutation of the integrated completion diff, cycle 2 (2026-11-06), lens "acts" (A1-A8) and admission D3: act frames
in the documented-service reader, by closed forms (builder K; HARNESS.md "Completion repair (2026-11-06)").

The owner's rule (2026-11-06): a cycle-1 patch that cycle 2 refuted is abandoned, never patched a third time with more
words, and the approach changes - to the base reading, or to a closed positive form under which an unlisted phrasing
can only cost a false hold. Each test names its finding; every document is synthetic. A pin reads the engine as the
website reads it (tests.test_harness_engine.run: real routing, the real documented-service inventory, and the
participants' readings where a lens used them).

- A1: statement_hold's base reading (the first hedge holds): "Colonoscopy for attempted polypectomy" is held.
- A2: a coordinated second conjunct shares the first conjunct's subject only as a plain done statement (closed form);
  the removal's status is read in its predicate's own clause too.
- A3: an anaphor binds only to an antecedent whose own clause is a plain finding of today (closed form); cycle 1's
  occasion reader is dropped.
- A4: a nominal removal adds a done act only where the rest of its sentence is recognized whole (closed form).
- A5: a later failure doubts the only done act of its kind with no lesion too (a widened hold).
- A6: the future-purpose release applies to the marking kinds only; routing's mirror reads the same rule.
- A7, D3: a listed removal is withheld where the service records lesions and none is stated removed today.
- A8 (rule 6b): an act noun modifying a head of a closed class states no act (it stays a denial, a plan or a history).
"""
from __future__ import annotations

import re

from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi import services as gi_services
from tests.test_harness_engine import DAY, code, corti, read, run, span

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
COLON_HEAD = BANNER + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
UPPER_HEAD = BANNER + 'EGD report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
ADVANCED = 'The colonoscope was advanced to the cecum and the examination was completed.\n'
UPPER_ADV = 'The gastroscope was advanced to the second portion of the duodenum.\n'
LISTED = 'Procedure: Colonoscopy with hot snare polypectomy\n'
LISTING = 'Colonoscopy with hot snare polypectomy'
BOLUS_FOUND = 'Findings: An impacted meat bolus was found in the distal esophagus.\n'


def colon(body, procedure='Procedure: Colonoscopy\n'):
    return COLON_HEAD + procedure + ADVANCED + body


def upper(body, procedure='Procedure: Upper endoscopy\n'):
    return UPPER_HEAD + procedure + UPPER_ADV + body


def outcome(text, picks, astra=()):
    """{code: (bucket, status)} of the selected and excluded proposals (alternatives left out)."""
    readings = [read('astra', [code(text, c, q) for c, q in astra])] if astra else []
    result = run(text, corti(*[(c, span(text, q)) for c, q in picks]), readings)
    return {p.code: (p.bucket, p.status) for p in result.proposals if p.bucket != 'alternative'}


def ready(text, picks, astra=()):
    return {c for c, value in outcome(text, picks, astra).items() if value == ('selected', 'ready')}


def acts(text, family, kind):
    inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY))
    service = next(s for s in inventory.services if s.family == family)
    return [(a.status, a.cues) for a in service.acts if a.kind == kind]


def shared_subject(sentence, verb='removed'):
    """What the participle ``verb`` of ``sentence`` is said of (services._predicate_subject in its own clause), or None."""
    cls = gi_services.clauses(sentence, 0, len(sentence))
    m = re.search(r'\b' + verb + r'\b', sentence)
    clause = gi_services._clause_for(cls, m.start())
    found = gi_services._predicate_subject(sentence, clause[0], m.start(), m.end(), len(sentence))
    return None if found is None else sentence[found[0]:found[1]]


def plain(sentence, head):
    """Whether ``sentence`` is a plain finding of the bolus-class head ``head`` (services._plain_finding)."""
    m = re.search(r'\b' + head + r'\b', sentence)
    return gi_services._plain_finding(sentence, (0, len(sentence)), m.start(), m.end())


class ReasonLeadTests(SimpleTestCase):
    """A1: the cycle-1 skip of a hedge after a reason's lead is dropped; statement_hold returns the first hedge."""

    def test_an_attempted_act_after_a_reason_lead_is_held(self):
        """Cycle 2, acts A1: "Colonoscopy for attempted polypectomy" (both bodies), and the EGD twin by Corti or Astra."""
        line = 'Procedure: Colonoscopy for attempted polypectomy\n'
        for body in ('A 30 mm sessile polyp was found in the ascending colon. The polyp did not lift with saline '
                     'injection; surgical referral was made.\n', 'No polyps were found.\n'):
            with self.subTest(body):
                text = colon(body, line)
                self.assertNotIn('45385', ready(text, [('45385', 'Colonoscopy for attempted polypectomy')]))
                self.assertNotIn('performed', [s for s, _ in acts(text, 'gi.colonoscopy', 'snare')])
        text = upper('A swallowed coin was found in the gastric body. It could not be grasped and was left in place '
                     'for surgical retrieval.\n', 'Procedure: Upper endoscopy for attempted foreign body removal\n')
        listing = 'Upper endoscopy for attempted foreign body removal'
        self.assertNotIn('43247', ready(text, [('43247', listing)]))
        self.assertNotIn('43247', ready(text, [('43235', UPPER_ADV.strip())], [('43247', listing)]))

    def test_a_hedged_reason_on_the_procedure_line_is_held_again(self):
        """Cycle 2, acts A1: the cycle-1 F5 shape ("biopsies for suspected celiac disease") is a recorded false hold
        again (held, never excluded), as the base read it."""
        line = 'Upper endoscopy with duodenal biopsies for suspected celiac disease'
        text = upper('The duodenal mucosa appeared normal.\n', 'Procedure: ' + line + '\n')
        self.assertEqual(outcome(text, [('43239', line)])['43239'], ('selected', 'needs_clarification'))


class SharedSubjectTests(SimpleTestCase):
    """A2: a second conjunct shares the first conjunct's subject only when it is a plain done statement."""

    MODAL = (', and could be removed if it does not pass.', ', and would be removed only if it failed to pass.',
             ', and can be removed at surgery.')

    def test_a_modal_or_conditional_conjunct_shares_no_subject(self):
        """Cycle 2, acts A2: the main input and its variants, the coin input, and Astra proposing 43247."""
        for tail in self.MODAL:
            with self.subTest(tail):
                sentence = 'An impacted meat bolus was found at 32 cm' + tail
                text = upper('Findings: ' + sentence + '\n')
                self.assertNotIn('43247', ready(text, [('43247', 'An impacted meat bolus was found at 32 cm')]))
                self.assertIsNone(shared_subject(sentence))
        coin = 'A swallowed coin was seen in the gastric body, and would be removed by the surgeon if it did not pass.'
        text = upper('Findings: ' + coin + '\n')
        self.assertNotIn('43247', ready(text, [('43247', 'A swallowed coin was seen in the gastric body')]))
        text = upper('Findings: An impacted meat bolus was found at 32 cm' + self.MODAL[0] + '\n')
        self.assertNotIn('43247', ready(text, [('43235', UPPER_ADV.strip())],
                                        [('43247', 'An impacted meat bolus was found at 32 cm, and could be removed '
                                                   'if it does not pass')]))

    def test_a_condition_negation_failure_or_time_in_a_done_conjunct(self):
        """Cycle 2, acts A2: a condition or a negation anywhere in the conjunct shares no subject; a failure or another
        time after the participle is read in the removal predicate's own clause."""
        for tail in (' and was removed if it did not pass.', ' and was not removed.', ' and was removed unsuccessfully.',
                     ' and was removed two years ago.'):
            with self.subTest(tail):
                sentence = 'An impacted meat bolus was found at 32 cm' + tail
                text = upper(sentence + '\n')
                self.assertNotIn('43247', ready(text, [('43247', sentence[:-1])]))

    def test_a_plain_done_conjunct_shares_the_subject(self):
        """Cycle 2, acts A2 controls: "... and was removed piecemeal" (the listed polypectomy READY), "... and was
        removed with a Roth net" (43247 READY by Corti or Astra), and an adverb before the participle."""
        sentence = 'An impacted meat bolus was found at 32 cm and was removed with a Roth net.'
        text = upper(sentence + '\n')
        self.assertEqual(ready(text, [('43247', sentence)]), {'43247'})
        self.assertIn('43247', ready(text, [('43235', UPPER_ADV.strip())], [('43247', sentence)]))
        self.assertEqual(shared_subject(sentence), 'bolus')
        coin = 'A swallowed coin was seen in the gastric body and was then removed with a Roth net.'
        self.assertEqual(ready(upper(coin + '\n'), [('43247', coin)]), {'43247'})
        polyp = 'A 25 mm polyp was found in the cecum and was removed piecemeal.'
        self.assertEqual(ready(colon(polyp + '\n', LISTED), [('45385', LISTING)]), {'45385'})
        self.assertEqual(shared_subject(polyp), 'polyp')
        self.assertIsNone(shared_subject('A 25 mm polyp was found in the cecum, and could be removed at surgery.'))


class BolusAntecedentTests(SimpleTestCase):
    """A3: an anaphor binds only to an antecedent whose own clause is a plain finding of today, recognized whole."""

    RING = ('Indication: Intermittent solid-food dysphagia.\nProcedure: Upper endoscopy with dilation\n' + UPPER_ADV
            + 'Findings: A Schatzki ring was found at 38 cm from the incisors. ')
    DILATED = ' The ring was dilated with a 54 Fr Savary dilator over a guidewire.\n'

    def test_another_occasions_impaction_binds_no_anaphor(self):
        """Cycle 2, acts A3: the main input and its variants (previously, history of, prior, last year, in March), the
        cycle-1 pinned shape, another person's coin or bolus, an outside hospital and a condition."""
        for middle, quote in (
                ('This ring was the site of a steak impaction two years ago. The impaction was removed endoscopically.',
                 'The impaction was removed endoscopically'),
                ('She previously had a steak impaction at this ring; the impaction was removed endoscopically.',
                 'the impaction was removed endoscopically'),
                ('She has a history of steak impaction at this ring; the impaction was removed endoscopically.',
                 'the impaction was removed endoscopically'),
                ('She had a prior steak impaction at this ring; the impaction was removed endoscopically.',
                 'the impaction was removed endoscopically'),
                ('She had a steak impaction at this ring last year; the impaction was removed endoscopically.',
                 'the impaction was removed endoscopically'),
                ('She had a steak impaction at this ring in March; the impaction was removed endoscopically.',
                 'the impaction was removed endoscopically'),
                ('This ring was the site of her steak impaction in 2023; the impaction was removed endoscopically at '
                 'that time.', 'the impaction was removed endoscopically at that time')):
            with self.subTest(middle):
                text = UPPER_HEAD + self.RING + middle + self.DILATED
                self.assertNotIn('43247', ready(text, [('43247', quote)]))
        for body, quote in (
                ('Findings: Normal esophagus, stomach and duodenum. The family reports that her twin brother swallowed a '
                 'coin last month; the coin was removed endoscopically.\n', 'the coin was removed endoscopically'),
                ('Her brother had a meat bolus impaction last month. The bolus was removed with a Roth net.\n',
                 'The bolus was removed with a Roth net.'),
                ('She presented to an outside hospital last week with a steak impaction. The impaction was removed with '
                 'a Roth net there.\n', 'The impaction was removed with a Roth net there.'),
                ('If a meat bolus recurs, the bolus is removed with a Roth net.\n', 'the bolus is removed with a Roth net')):
            with self.subTest(body):
                self.assertNotIn('43247', ready(upper(body), [('43247', quote)]))

    def test_a_plain_finding_of_today_binds_it(self):
        """Cycle 2, acts A3 controls: sister A ("elsewhere" in another clause) and sister B (a clock time), the shapes
        of corpus text 137 and of the retained walk documents, a coin, a chain of anaphors and one sentence."""
        sister = 'Findings: An impacted meat bolus was found in the distal esophagus; the mucosa elsewhere was normal.\n'
        for removal in ('The bolus was removed with a Roth net.', 'The bolus was removed with a Roth net at 1942.'):
            with self.subTest(removal):
                text = upper(sister + removal + '\n')
                self.assertEqual(ready(text, [('43247', removal)]), {'43247'})
                self.assertIn('43247', ready(text, [('43235', UPPER_ADV.strip())], [('43247', removal)]))
        for body, quote in (
                ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus. A large '
                 'impacted meat bolus was found at 34 cm.\nA retrieval net was passed through the working channel and '
                 'the bolus was removed through the mouth.\n', 'the bolus was removed through the mouth'),
                ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus. An '
                 'impacted\nmeat bolus was found in the distal esophagus at 36 cm. A retrieval net was passed through '
                 'the working channel\nand the bolus was removed through the mouth in one piece.\n',
                 'the bolus was removed through the mouth in one piece'),
                ('Upper endoscopy: The gastroscope was advanced under direct visualization into the esophagus. A large\n'
                 'impacted meat bolus was encountered at 35 cm from the incisors, obstructing passage of the '
                 'instrument. A\nretrieval net was passed through the working channel and the bolus was removed through '
                 'the mouth in two\npieces.\n', 'the bolus was removed through the mouth in two'),
                ('A swallowed coin was found in the gastric body.\nThe coin was removed with a Roth net.\n',
                 'The coin was removed with a Roth net.'),
                ('An impacted meat bolus was found at 32 cm. The bolus was grasped with a Roth net. The bolus was then '
                 'removed.\n', 'The bolus was then removed.'),
                ('An impacted meat bolus was found at 32 cm, and the bolus was removed with a Roth net.\n',
                 'the bolus was removed with a Roth net')):
            with self.subTest(body):
                self.assertEqual(ready(upper(body), [('43247', quote)]), {'43247'})

    def test_the_plain_finding_grammar(self):
        """Cycle 2, acts A3: the closed form, positive and negative, and its failure on the safe side."""
        for sentence, head in (('An impacted meat bolus was found at 32 cm.', 'bolus'),
                               ('Findings: An impacted meat bolus was found in the distal esophagus', 'bolus'),
                               ('A large impacted meat bolus was encountered at 35 cm from the incisors.', 'bolus'),
                               ('A meat bolus was impacted at 34 cm.', 'bolus'),
                               ('A swallowed coin was seen in the gastric body.', 'coin'),
                               ('A foreign body (a swallowed coin) was seen in the transverse colon.', 'foreign body'),
                               ('A bolus of steak was found at 30 cm from the incisors.', 'bolus')):
            with self.subTest(sentence):
                self.assertTrue(plain(sentence, head))
        for sentence, head in (('This ring was the site of a steak impaction two years ago.', 'impaction'),
                               ('She previously had a steak impaction at this ring', 'impaction'),
                               ('A prior meat bolus was found at 32 cm.', 'bolus'),
                               ('A meat bolus was found in the past.', 'bolus'),
                               ('A meat bolus was found in the emergency department.', 'bolus'),
                               ('A meat bolus was found at 32 cm in 2023.', 'bolus'),
                               ('An impacted meat bolus was found at 32 cm at 2015 hours.', 'bolus'),
                               ('Her brother\'s meat bolus was found at 32 cm.', 'bolus'),
                               ('Possibly a meat bolus was found at 32 cm.', 'bolus'),
                               ('An impacted meat bolus was found at 32 cm and was removed with a Roth net.', 'bolus')):
            with self.subTest(sentence):
                self.assertFalse(plain(sentence, head))


class NominalRemovalTests(SimpleTestCase):
    """A4: "Removal of the bolus" or "Bolus removal" adds a done act only where the rest of its sentence is recognized
    whole: instrument phrases, was/were, closed adverbs, one done word, instrument phrases, the end."""

    def test_anything_after_the_done_word_adds_no_removal(self):
        """Cycle 2, acts A4: the main input and its variants, by Corti and by Astra, and cycle 1's "impossible"."""
        coin = 'Findings: A swallowed coin was found in the gastric body.\n'
        for body, quote in (
                (BOLUS_FOUND + 'Bolus removal was performed but was unsuccessful, and the bolus was advanced into the '
                 'stomach.\n', 'Bolus removal was performed but was unsuccessful'),
                (coin + 'Removal of the coin was performed but failed.\n', 'Removal of the coin was performed but failed.'),
                (BOLUS_FOUND + 'Removal of the bolus was performed unsuccessfully; it was pushed into the stomach.\n',
                 'Removal of the bolus was performed unsuccessfully'),
                (BOLUS_FOUND + 'Removal of the bolus was carried out unsuccessfully.\n',
                 'Removal of the bolus was carried out unsuccessfully.'),
                (BOLUS_FOUND + 'Removal of the bolus was undertaken but failed.\n',
                 'Removal of the bolus was undertaken but failed.'),
                (BOLUS_FOUND + 'Removal of the bolus was performed with a Roth net but failed.\n',
                 'Removal of the bolus was performed with a Roth net but failed.'),
                (BOLUS_FOUND + 'Removal of the bolus was impossible, so it was pushed into the stomach.\n',
                 'Removal of the bolus was impossible')):
            with self.subTest(quote):
                text = upper(body)
                self.assertNotIn('43247', ready(text, [('43247', quote)]))
                self.assertNotIn('43247', ready(text, [('43235', UPPER_ADV.strip())], [('43247', quote)]))

    def test_the_done_forms_are_read(self):
        """Cycle 2, acts A4 controls: two adverbs before the done word, "technically successful" after an instrument,
        a compound with an instrument, and "using" a device."""
        for body, quote in (
                (BOLUS_FOUND, 'Removal of the bolus was then successfully performed with a Roth net.'),
                (BOLUS_FOUND, 'Removal of the bolus with a Roth net was technically successful.'),
                (BOLUS_FOUND, 'Bolus removal was performed with a Roth net.'),
                ('Findings: A swallowed coin was found in the gastric body.\n',
                 'Removal of the coin was performed using a Roth net.')):
            with self.subTest(quote):
                self.assertEqual(ready(upper(body + quote + '\n'), [('43247', quote)]), {'43247'})

    def test_the_nominal_grammar(self):
        """Cycle 2, acts A4: services._nominal_removal_done reads the rest of the sentence whole (bounded)."""
        def done(rest):
            return gi_services._nominal_removal_done(rest, 0, len(rest))
        for rest in (' was performed.', ' was then successfully performed with a Roth net.',
                     ' with a Roth net was technically successful.', ' were completed using a 25 mm retrieval net.'):
            with self.subTest(rest):
                self.assertTrue(done(rest))
        for rest in (' was performed but was unsuccessful.', ' was performed but failed.', ' was performed unsuccessfully.',
                     ' was performed with a Roth net but failed.', ' was impossible.', ' was not performed.',
                     ' was performed, and the bolus was pushed into the stomach.', ' was attempted.',
                     ' was performed' + ' with a net' * 30 + '.'):
            with self.subTest(rest):
                self.assertFalse(done(rest))


class SameActLaterFailureTests(SimpleTestCase):
    """A5: a later failure of the only done act of its kind doubts it, lesion-bound or not, unless their sites conflict."""

    def test_the_only_done_act_without_a_lesion_is_doubted_by_its_abort(self):
        """Cycle 2, acts A5: the duodenal biopsies then aborted (Corti, Astra) and the colon twin."""
        aborted = 'The biopsy was aborted due to bleeding and no tissue was obtained.\n'
        quote = 'Cold forceps biopsies were obtained from the second portion of the duodenum'
        text = upper(quote + '.\n' + aborted)
        self.assertNotIn('43239', ready(text, [('43239', quote)]))
        self.assertNotIn('43239', ready(text, [('43235', UPPER_ADV.strip())], [('43239', quote)]))
        quote = 'Cold forceps biopsies were obtained from the transverse colon'
        self.assertNotIn('45380', ready(colon(quote + '.\n' + aborted), [('45380', quote)]))

    def test_another_site_another_act_or_an_earlier_failure_keeps_it(self):
        """Cycle 2, acts A5 controls: a failure at a site of its own, of an act calling itself another, or before."""
        quote = 'Cold forceps biopsies were obtained from the gastric antrum'
        for body in (quote + '.\nA biopsy of the duodenal bulb was aborted due to bleeding.\n',
                     quote + '.\nA second biopsy was aborted due to bleeding.\n',
                     'A biopsy attempt failed due to bleeding.\nCold forceps biopsies were then obtained from the gastric '
                     'antrum.\n'):
            with self.subTest(body):
                q = quote if quote in body else 'Cold forceps biopsies were then obtained from the gastric antrum'
                self.assertEqual(ready(upper(body), [('43239', q)]), {'43239'})


class PresupposingHeadTests(SimpleTestCase):
    """A8, rule 6b: an act noun modifying a head of a closed class names what or where an act left: no act is read."""

    DONE = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare'

    def test_an_act_word_modifying_a_closed_head_states_no_act(self):
        """Cycle 2, acts A8: "Clip closure of the polypectomy defect failed." (Corti, Astra beside Corti's 45378), "the
        polypectomy specimen", the EGD twin "the biopsy site" and an EMR defect."""
        for tail in ('Clip closure of the polypectomy defect failed.', 'Retrieval of the polypectomy specimen was '
                     'unsuccessful.'):
            with self.subTest(tail):
                text = colon(self.DONE + '.\n' + tail + '\n')
                self.assertEqual(ready(text, [('45385', self.DONE)]), {'45385'})
                self.assertIn('45385', ready(text, [('45378', ADVANCED.strip())], [('45385', self.DONE)]))
        quote = 'Cold forceps biopsies were obtained from the gastric antrum'
        self.assertEqual(ready(upper(quote + '.\nClip closure of the biopsy site failed.\n'), [('43239', quote)]),
                         {'43239'})
        quote = 'A 25 mm flat lesion in the ascending colon was removed by endoscopic mucosal resection'
        self.assertEqual(ready(colon(quote + '.\nClosure of the EMR defect was unsuccessful.\n'), [('45390', quote)]),
                         {'45390'})

    def test_a_denial_or_a_plan_on_it_is_kept(self):
        """Cycle 2, rule 6b: a reading that the act is not today's stays the act's ("No biopsy specimens were
        obtained." against a listed biopsy; "EMR margin marking ... for future resection")."""
        listing = 'Upper endoscopy with biopsy'
        text = upper('No biopsy specimens were obtained.\n', 'Procedure: ' + listing + '\n')
        self.assertNotIn('43239', ready(text, [('43239', listing)]))
        self.assertIn('negated', [s for s, _ in acts(text, 'gi.egd', 'biopsy')])

    def test_the_held_shapes(self):
        """Cycle 2, acts A8: recorded readings on the safe side. "Specimen retrieval after the polypectomy failed." stays
        held - the act word is the object of "after", not a modifier of a closed head, so rule 6b does not reach it (a
        recorded false hold the spec asked READY); another polyp's failed snare and a failed first pass stay held, and
        "Biopsy specimens were obtained" reads no biopsy act (the rule's own cost)."""
        for tail in ('Specimen retrieval after the polypectomy failed.',
                     'Hot snare polypectomy of a large pedunculated polyp failed.'):
            with self.subTest(tail):
                text = colon(self.DONE + '.\n' + tail + '\n')
                self.assertEqual(outcome(text, [('45385', self.DONE)])['45385'], ('selected', 'needs_clarification'))
        quote = 'A 5 mm polyp in the ascending colon was biopsied with cold forceps.'
        text = colon(quote + '\nThe first biopsy pass was unsuccessful, but tissue was obtained on the next pass.\n')
        self.assertEqual(outcome(text, [('45380', quote)])['45380'], ('selected', 'needs_clarification'))
        quote = 'Biopsy specimens were obtained from the gastric antrum'
        self.assertEqual(outcome(upper(quote + '.\n'), [('43239', quote)])['43239'], ('selected', 'needs_clarification'))

    def test_the_closed_head(self):
        """Cycle 2, rule 6b: services._presupposed - a noun before a closed head; never a verb form or another head."""
        for text, word in (('the polypectomy defect', 'polypectomy'), ('the biopsy sites', 'biopsy'),
                           ('the EMR margin', 'EMR'), ('the snare defect', 'snare'), ('biopsy tissue', 'biopsy')):
            with self.subTest(text):
                m = re.search(word, text)
                self.assertTrue(gi_services._presupposed(text, m.start(), m.end()))
        for text, word in (('we biopsied tissue', 'biopsied'), ('the polypectomy was', 'polypectomy'),
                           ('the biopsy forceps', 'biopsy'), ('the polypectomy, defect', 'polypectomy')):
            with self.subTest(text):
                m = re.search(word, text)
                self.assertFalse(gi_services._presupposed(text, m.start(), m.end()))


class PurposeReleaseTests(SimpleTestCase):
    """A6: the future-purpose release frees a marking (a tattoo or an injection) whatever its subject's head, and never
    another act's word, which keeps the purpose's future; routing's mirror reads the same rule."""

    LESION = 'A 30 mm flat lesion was found in the ascending colon.\n'

    def test_another_acts_word_keeps_the_purposes_future(self):
        """Cycle 2, acts A6: the main input and its variants (45390), the EGD twins (43254) and cycle 1's EMR referral."""
        for sentence in ('EMR margin marking was performed around the lesion for future resection',
                         'An EMR tattoo was placed distal to the lesion for future resection',
                         'EMR lift solution was injected into the lesion for future resection'):
            with self.subTest(sentence):
                self.assertNotIn('45390', ready(colon(self.LESION + sentence + '.\n'), [('45390', sentence)]))
                text = upper('A 20 mm flat lesion was found in the gastric body.\n' + sentence + '.\n')
                self.assertNotIn('43254', ready(text, [('43254', sentence)]))
        text = colon('Findings: A 30 mm flat lesion was found in the ascending colon.\nImpression: 30 mm flat lesion in '
                     'the ascending colon. EMR referral placed for future resection.\n')
        self.assertNotIn('45390', ready(text, [('45390', 'EMR referral placed')]))

    def test_a_marking_is_released_whatever_its_head(self):
        """Cycle 2, acts A6 controls: "tattoo placement", "A tattoo mark", "India ink", "Tattoo ink", a tattoo an EMR
        word modifies (45381), the EGD twin (43236) and a snare and a tattoo in one sentence (45385, 45381)."""
        for sentence in ('Submucosal tattoo placement was performed distal to the lesion for future localization',
                         'A tattoo mark was placed distal to the lesion for future localization',
                         'India ink was injected distal to the lesion for future localization',
                         'Tattoo ink was injected distal to the lesion for future localization',
                         'An EMR tattoo was placed distal to the lesion for future resection'):
            with self.subTest(sentence):
                self.assertEqual(ready(colon(self.LESION + sentence + '.\n'), [('45381', sentence)]), {'45381'})
        sentence = 'India ink was injected distal to the lesion for future localization'
        text = upper('A 20 mm flat lesion was found in the gastric body.\n' + sentence + '.\n')
        self.assertEqual(ready(text, [('43236', sentence)]), {'43236'})
        sentence = ('The 15 mm polyp in the sigmoid colon was removed with a hot snare and the site was tattooed for '
                    'future localization.')
        text = colon(sentence + '\n')
        for value in ('45385', '45381'):
            with self.subTest(value):
                self.assertEqual(ready(text, [(value, sentence)]), {value})

    def test_routing_reads_the_same(self):
        """Cycle 2, acts A6: detect._purpose_is_not_the_targets - another act's word is planned, a marking is not, and a
        passage keeps the reading of the act words the services reader reads in it."""
        text = colon(self.LESION + 'EMR margin marking was performed around the lesion for future resection.\n')
        emr = text.index('EMR margin')
        self.assertEqual(detect.status_for_span(text, emr, emr + 3, DAY)[0], 'planned')
        text = colon(self.LESION + 'Submucosal tattoo placement was performed distal to the lesion for future '
                     'localization.\n')
        tattoo = text.index('tattoo placement')
        self.assertNotEqual(detect.status_for_span(text, tattoo, tattoo + 6, DAY)[0], 'planned')
        sentence = ('The 15 mm polyp in the sigmoid colon was removed with a hot snare and the site was tattooed for '
                    'future localization.')
        text = colon(sentence + '\n')
        start = text.index(sentence)
        self.assertNotEqual(detect.status_for_span(text, start, start + len(sentence), DAY)[0], 'planned')

    def test_a_biopsy_keeps_the_purposes_future(self):
        """Cycle 2, acts A6: a biopsy's word is never released (the base reading): held or excluded, never READY."""
        sentence = 'Random cold forceps biopsies were obtained from the transverse colon for future comparison.'
        self.assertNotIn('45380', ready(colon(sentence + '\n'), [('45380', sentence)]))
        self.assertIn('planned', [s for s, _ in acts(colon(sentence + '\n'), 'gi.colonoscopy', 'biopsy')])


class ListingTechniqueTests(SimpleTestCase):
    """A7, D3: the procedure line supplies a technique, never a performance - a listed removal with no performed act
    of its kind is withheld where the service records lesions and none of them is stated removed today."""

    def test_no_lesion_stated_removed_withholds_the_listing(self):
        """Cycle 2, acts A7 and admission D3: a field label, a reduced coordination, a pronoun, a tattoo, a post-modifier
        and a negative quantifier; Corti on the listing, a participant on the passage; the heading and EGD twins."""
        found = 'A 10 mm polyp was found in the sigmoid colon'
        for body in ('Findings: ' + found + ' and was left in place for surgical resection.\n',
                     'Findings:\n' + found + ' and was left in place for surgical resection.\n',
                     found + ' and left in place for surgical resection.\n',
                     found + '. It was left in place for surgical resection.\n',
                     found + ' and was tattooed for later surgical resection.\n',
                     'A 10 mm polyp in the sigmoid colon was left in place for surgical resection.\n',
                     'A 9 mm pedunculated polyp in the sigmoid colon was seen.\nNo polyps were removed.\n'):
            with self.subTest(body):
                text = colon(body, LISTED)
                self.assertNotIn('45385', ready(text, [('45385', LISTING)]))
                passage = body.split('\n')[0] if not body.startswith('Findings:\n') else body.split('\n')[1]
                self.assertNotIn('45385', ready(text, [('45378', ADVANCED.strip())], [('45385', passage)]))
        text = colon('Findings: ' + found + ' and was left in place for surgical resection.\n', LISTED)
        self.assertIn(gi_services.LISTED_CONTRADICTED_CUE, [c for _, cues in acts(text, 'gi.colonoscopy', 'snare')
                                                            for c in cues])
        line = 'Upper endoscopy with snare polypectomy'
        text = upper('A 10 mm sessile polyp in the gastric body was seen.\n', 'Procedure: ' + line + '\n')
        self.assertNotIn('43251', ready(text, [('43251', line)]))

    def test_a_lesion_stated_removed_keeps_the_listing(self):
        """Cycle 2, acts A7 controls: a lesion stated removed (plainly, by a shared subject beside a residual, with a
        snare), the EGD twin, and a listed EMR whose lesion a performed hot-snare act removed."""
        for body in ('A 6 mm polyp in the sigmoid colon was removed.\n',
                     'A 25 mm sessile polyp was found in the cecum and was removed piecemeal. The residual polyp was left '
                     'in place.\n', 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.\n'):
            with self.subTest(body):
                self.assertEqual(ready(colon(body, LISTED), [('45385', LISTING)]), {'45385'})
        line = 'Upper endoscopy with snare polypectomy'
        text = upper('A 10 mm sessile polyp in the gastric body was removed.\n', 'Procedure: ' + line + '\n')
        self.assertEqual(ready(text, [('43251', line)]), {'43251'})
        line = 'Colonoscopy with endoscopic mucosal resection'
        text = colon('A 25 mm flat lesion in the ascending colon was resected with a hot snare after a saline lift.\n',
                     'Procedure: ' + line + '\n')
        self.assertEqual(ready(text, [('45390', line)]), {'45390'})
