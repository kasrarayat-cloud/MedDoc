"""GI round 4, package PE: routing extent vocabulary (synthesis E2; the declaration is
tests/fixtures/gi4/declarations/pe.json, committed before this code).

cues.REACHED_BEFORE_ROUTING is installed cues.REACHED_BEFORE with "steered" and "navigated" added to its reach verbs, and
it is read only by detect._landmarks, through detect._pe_reached_before. These tests pin:
- the constant: exactly installed plus the two verbs with the same flags; cues.REACHED_BEFORE unchanged; neither
  context.py nor sections.py (the request side) reads the new one;
- the release: h4-04's EGD extent reads the second part of the duodenum (installed: "incomplete: stomach") in every
  member state, with 43251's bucket, status and fingerprint unchanged by PE (in the integrated Wave 1 tree its
  fingerprint moves by package PI's recorded movement only); and plain shapes read the endpoint they state;
- the plan's must-holds and every guard: each shape in INSTALLED reads exactly what installed 06e6d204e (cpt-studio
  identical to 80df1831d168) reads, measured on a sealed export before this file was written - "The pylorus could not
  be passed" stays "incomplete: stomach", a 30 cm stricture never reads complete, and a denied, hedged, planned,
  conditioned, generalised or falling-short steer, an accessory's, a shallow one, a letter's or another record's
  gives back the installed reading;
- the behaviour every PE mutant must break: this module is the detector of tests/test_gi4_pe_mutants.PE_MUTANTS, and
  holds no registry test of its own (a mutant removes its own anchor, so a registry check here would kill every
  mutant whatever the behaviour tests saw).
Offline: SimpleTestCase, no database, nothing sent.
"""
import datetime as dt
import inspect
import json
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import freeze, regression, replay
from studio import jobs
from studio.gi import context, cues, detect, sections, services

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
U = B + 'Upper Endoscopy Report\nDate of service: October 19, 2026\nFindings: '
L = B + 'Colonoscopy Report\nDate of service: 10/19/2026\nFindings: '
DAY = dt.date(2026, 10, 19)
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi4'
H404 = (FIXTURES / 'regression' / 'h4-04.txt').read_text(encoding='utf-8')
EGD, COLON, SIG = 'gi.egd', 'gi.colonoscopy', 'gi.flex_sig'
D2 = 'second part of duodenum'

# Shapes PE reads (the installed reading in the comment): a routing-only verb that states the family's endpoint.
RELEASES = {
    'h4-04': (H404, {EGD: ('uncertain', D2), COLON: ('negated', None)}),  # installed: 'incomplete: stomach'
    'steered into D2': (U + 'The gastroscope was steered into the second part of the duodenum. Normal mucosa.\n',
                        {EGD: ('performed', D2)}),  # installed: no extent
    'navigated to the cecum': (L + 'The colonoscope was navigated to the cecum. No polyps.\n',
                               {COLON: ('performed', 'cecum')}),
    'navigated through the sigmoid to the cecum': (L + 'The colonoscope was navigated through the sigmoid colon to the '
                                                       'cecum.\n', {COLON: ('performed', 'cecum')}),
    'navigated to the terminal ileum': (L + 'The colonoscope was navigated to the terminal ileum.\n',
                                        {COLON: ('performed', 'terminal ileum')}),
    'active: we steered the gastroscope': (U + 'We steered the gastroscope into the second part of the duodenum.\n',
                                           {EGD: ('performed', D2)}),
    'with some difficulty': (U + 'The gastroscope was navigated, with some difficulty, into the second part of the '
                                 'duodenum.\n', {EGD: ('performed', D2)}),
    'past the pylorus': (U + 'The gastroscope was steered past the pylorus into the duodenum.\n',
                         {EGD: ('performed', 'duodenum')}),  # installed: 'past the pylorus' alone read no extent
    'over a wire placed first': (U + 'A guidewire was placed and the gastroscope was steered over it into the second '
                                     'part of the duodenum.\n', {EGD: ('performed', D2)}),
    'the bulb, D2 not reached': (U + 'The gastroscope was steered into the duodenal bulb, but the second part of the '
                                     'duodenum could not be reached.\n',
                                 {EGD: ('incomplete', 'incomplete: duodenal bulb')}),  # installed: no extent
}

# Shapes that read exactly as on installed 06e6d204e (each value measured there): the must-holds, then each guard.
INSTALLED = {
    # --- the plan's must-holds (battery rows and their steered variants) ---
    'the pylorus could not be passed': (U + 'The gastroscope was introduced by mouth and steered through the stomach, but '
                                            'the pylorus could not be passed into the duodenum.\n',
                                        {EGD: ('incomplete', 'incomplete: stomach')}),
    'stricture at 30 cm': (L + 'The colonoscope could not be advanced past a tight stricture at 30 cm. Biopsies of the '
                               'stricture were taken.\n', {COLON: ('incomplete', None)}),
    'steered, then a stricture at 30 cm': (L + 'The colonoscope was steered through the rectum and could not be advanced '
                                               'past a tight stricture at 30 cm in the sigmoid colon.\n',
                                           {COLON: ('incomplete', None)}),
    # --- denials (also held by the status reading's own doubt) ---
    'could not be steered': (U + 'The gastroscope was introduced into the esophagus and the stomach was examined. The '
                                 'gastroscope could not be steered into the duodenum.\n',
                             {EGD: ('incomplete', 'incomplete: stomach')}),
    'was not steered': (U + 'The stomach was examined. The gastroscope was not steered into the duodenum because of a '
                            'tight pyloric channel.\n', {EGD: ('incomplete', 'incomplete: stomach')}),
    "couldn't be navigated": (L + "The colonoscope reached the hepatic flexure but couldn't be navigated to the cecum.\n",
                              {COLON: ('incomplete', 'incomplete: hepatic flexure')}),
    'never navigated': (L + 'The sigmoid colon was examined. The colonoscope was never navigated to the cecum because of '
                            'poor preparation.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'unable to be steered': (U + 'The stomach was examined. The scope was unable to be steered into the duodenal bulb.\n',
                             {EGD: ('incomplete', 'incomplete: stomach')}),
    'not successfully navigated': (L + 'The descending colon was examined. The colonoscope was not successfully '
                                       'navigated to the cecum.\n', {COLON: ('incomplete', 'incomplete: descending colon')}),
    # --- guard: the family's endpoint or beyond (never a new incompleteness) ---
    'steered into the esophagus only': (U + 'The gastroscope was steered into the esophagus under direct vision. Normal '
                                            'examination to the second part of the duodenum.\n', {EGD: ('performed', None)}),
    'navigated into the rectum only': (L + 'The colonoscope was navigated into the rectum. A complete examination was '
                                           'performed and the appendiceal orifice photographed.\n',
                                       {COLON: ('performed', None)}),
    'steered into the stomach, duodenal mucosa': (U + 'The gastroscope was steered into the stomach and the pylorus was '
                                                      'traversed. Normal duodenal mucosa.\n', {EGD: ('performed', None)}),
    'hepatic flexure, then on to the cecum': (L + 'The colonoscope was navigated to the hepatic flexure, where a polyp was '
                                                  'removed with a cold snare, and then on to the cecum.\n',
                                              {COLON: ('performed', None)}),
    'enteroscope to D2 only': (B + 'Push Enteroscopy Report\nDate of service: 10/19/2026\nFindings: The enteroscope was '
                                   'steered into the second part of the duodenum.\n', {EGD: ('performed', None)}),
    'sigmoidoscope to the descending colon': (B + 'Flexible Sigmoidoscopy Report\nDate of service: 10/19/2026\nFindings: '
                                                  'The sigmoidoscope was navigated to the descending colon.\n',
                                              {SIG: ('performed', None)}),
    # --- guard: a negation, modal, infinitive, hedge or present tense governing the verb ---
    'usually navigated': (L + 'The colonoscope reached the sigmoid colon. The colonoscope is usually navigated to the '
                              'cecum.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'is then steered (template)': (U + 'The gastroscope is then steered into the second part of the duodenum.\n',
                                   {EGD: ('performed', None)}),
    'would be steered': (L + 'The colonoscope reached the sigmoid colon. We hoped the scope would be steered to the '
                             'cecum.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'to be navigated later': (L + 'The colonoscope reached the sigmoid colon. The colonoscope, to be navigated to the '
                                  'cecum later, was withdrawn.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    # --- guard: a falling-short adverb ---
    'partially steered': (U + 'The stomach was examined. The gastroscope was partially steered into the duodenal bulb.\n',
                          {EGD: ('incomplete', 'incomplete: stomach')}),
    'nearly navigated': (L + 'The transverse colon was reached. The colonoscope was nearly navigated to the cecum.\n',
                         {COLON: ('incomplete', 'incomplete: transverse colon')}),
    'unsuccessfully steered': (U + 'The stomach was examined. The gastroscope was unsuccessfully steered into the '
                                   'duodenum.\n', {EGD: ('incomplete', 'incomplete: stomach')}),
    # --- guard: a wish, a plan, an attempt or a condition before the verb ---
    'hoped that': (L + 'The colonoscope reached the sigmoid colon. We hoped that the colonoscope was navigated to the '
                       'cecum.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'if clause': (L + 'The colonoscope reached the sigmoid colon. If the colonoscope was navigated to the cecum, its '
                      'landmarks were photographed.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    # --- guard: a negation, hedge or attempt between the verb and the landmark ---
    'steered, presumably, into': (U + 'The stomach was examined. The gastroscope was steered, presumably, into the '
                                      'duodenum.\n', {EGD: ('incomplete', 'incomplete: stomach')}),
    'steered toward but not into': (U + 'The stomach was examined. The scope was steered toward but not into the '
                                        'duodenum.\n', {EGD: ('incomplete', 'incomplete: stomach')}),
    'an attempt made to pass': (L + 'The transverse colon was reached. The colonoscope was navigated and an attempt made '
                                    'to pass to the cecum.\n', {COLON: ('incomplete', 'incomplete: transverse colon')}),
    # --- guard: another time or a condition after the landmark ---
    'later': (L + 'The colonoscope reached the sigmoid colon. The colonoscope was navigated to the cecum later.\n',
              {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'at the next procedure': (L + 'The colonoscope reached the sigmoid colon. The colonoscope was navigated to the cecum '
                                  'at the next procedure.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'if the preparation allowed': (L + 'The colonoscope reached the sigmoid colon. The colonoscope was navigated to the '
                                       'cecum if the preparation allowed.\n',
                                   {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    # --- guard: the endoscope moved, never an accessory, and a scope word to say so ---
    'a guidewire navigated': (U + 'The gastroscope could not be passed beyond the pylorus. A guidewire was navigated '
                                  'through the pylorus into the duodenum and the pylorus was dilated.\n',
                              {EGD: ('incomplete', 'incomplete: stomach')}),
    'a balloon steered': (U + 'The scope was held in the antrum. A dilating balloon was steered into the duodenal bulb '
                              'and inflated.\n', {EGD: ('performed', None)}),
    'a catheter navigated': (L + 'The colonoscope stopped at the splenic flexure. A catheter was navigated to the cecum '
                                 'for contrast.\n', {COLON: ('incomplete', None)}),
    'a wire after the scope': (U + 'The gastroscope was held in the antrum and a guidewire was steered through the pylorus '
                                   'into the second part of the duodenum.\n', {EGD: ('performed', None)}),
    'a pronoun subject': (U + 'The gastroscope was introduced by mouth. It was steered into the second part of the '
                              'duodenum.\n', {EGD: ('performed', None)}),
    # --- guard: a note written around a procedure ---
    'a referral letter': (B + 'Referral Letter\nDate of service: 10/19/2026\nColonoscopy Report\nThe colonoscope was '
                              'navigated to the cecum.\n', {COLON: ('performed', None)}),
    # (Wave 1 repair, amendment_20261101_cycle1_b: the referral letter's head names no family, so the head rule holds it
    # too; this note's title names the colonoscopy and its 'Findings' passage passes every copy guard, so the
    # around-procedure guard alone holds it - measured on installed 80df1831d168: performed, no extent)
    'a telephone note naming the colonoscopy': (B + 'Colonoscopy Telephone Note\nDate of service: 10/19/2026\nFindings\n'
                                                    'The colonoscope was navigated to the cecum.\n',
                                                {COLON: ('performed', None)}),
    # --- guard: under a line naming another occurrence's record ---
    'outside records': (B + 'Colonoscopy Report\nDate of service: 10/19/2026\nFindings\nThe colonoscope could not be '
                            'advanced beyond the sigmoid colon because of a stricture.\nOutside Records\nAt Mercy GI the '
                            'colonoscope was steered to the cecum.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    # --- another occasion (the per-hit status and _about_another_procedure, as installed) ---
    'dated 2024': (L + 'The colonoscope reached the sigmoid colon. On 03/02/2024 the colonoscope was navigated to the '
                       'cecum.\n', {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'a question': (L + 'The colonoscope reached the sigmoid colon. Was the colonoscope steered to the cecum?\n',
                   {COLON: ('incomplete', 'incomplete: sigmoid colon')}),
    'planned in an office note': (B + 'Office visit\nDate of service: 10/19/2026\nPlan: colonoscopy next month; the '
                                      'colonoscope will be navigated to the cecum.\n', {COLON: ('planned', None)}),
}


def reading(text, day=DAY):
    """{family: (status, extent or None)} for the endoscopy families routing reads in ``text``."""
    out = {}
    for f in detect.route(text, day).findings:
        if f.family in (EGD, COLON, SIG):
            extent = next((x for x in f.facts if x.name == 'extent'), None)
            out[f.family] = (f.status, None if extent is None else extent.value)
    jobs.release_routing_caches()
    return out


class RoutingVocabularyTests(SimpleTestCase):
    def test_the_routing_constant_is_installed_plus_two_reach_verbs(self):
        installed, routing = cues.REACHED_BEFORE, cues.REACHED_BEFORE_ROUTING
        self.assertEqual(installed.pattern.count('visualized)'), 1)
        self.assertEqual(routing.pattern, installed.pattern.replace('visualized)', 'visualized|steered|navigated)', 1))
        self.assertEqual(routing.flags, installed.flags)
        self.assertTrue(routing.search('steered through the stomach and pylorus\ninto the '))
        self.assertIsNone(installed.search('steered through the stomach and pylorus\ninto the '))

    def test_the_request_side_never_reads_it_and_reads_the_installed_constant_unchanged(self):
        for module in (context, sections):
            self.assertNotIn('REACHED_BEFORE_ROUTING', inspect.getsource(module), module.__name__)
        now = freeze.cue_inventory()
        self.assertNotIn('cues.REACHED_BEFORE_ROUTING', now)
        pinned = json.loads((FIXTURES / 'pins' / 'cues.json').read_text())['cues']
        self.assertEqual(now['cues.REACHED_BEFORE'], pinned['cues.REACHED_BEFORE'])

    def test_landmarks_reads_a_reach_only_through_the_pe_predicate(self):
        source = inspect.getsource(detect._landmarks)
        self.assertEqual(source.count('_pe_reached_before(an, pre, depth, table, m.start(), post)'), 2)
        self.assertNotIn('cues.REACHED_BEFORE.search', source)
        self.assertIn('cues.REACHED_BEFORE_ROUTING', inspect.getsource(detect._pe_reached_before))


class RoutingReleaseTests(SimpleTestCase):
    def test_each_release(self):
        for name, (text, want) in RELEASES.items():
            with self.subTest(name):
                self.assertEqual(reading(text), want)

    def test_h4_04_without_a_member_date_too(self):
        self.assertEqual(reading(H404, None), {EGD: ('uncertain', D2), COLON: ('negated', None)})

    def test_h4_04_inventory_takes_the_extent_and_keeps_its_completion(self):
        routing = detect.route(H404, DAY)
        inventory = services.build(H404, service_date=DAY, routing=routing, context_facts=context.extract_context(H404))
        jobs.release_routing_caches()
        egd = [s for s in inventory.services if s.family == EGD]
        self.assertEqual([(s.status, s.completion, s.extent) for s in egd], [('performed', 'complete', D2)])

    def test_h4_04_replay_moves_only_the_extent_and_pe_moves_no_fingerprint(self):
        """The declaration: in every member state gi.egd reads the second part of the duodenum; 43251 stays selected
        with its status, and PE moves no fingerprint (92e16310 in the walk state under PE alone: facts.required stays
        'pass'). In the integrated Wave 1 tree 43251's walk fingerprint is 9d6bff8e: package PI's movement, recorded
        in pi.json after_measurement (45378 now held beside 43251 adds pfs.endoscopic_base; the one live approval is
        invalidated at its next assessment, an install fact) - exactly PI's own value, so PE adds nothing to it."""
        pinned = json.loads((FIXTURES / 'pins' / 'replay.json').read_text())['documents']['h4-04']
        result = replay.replay({'h4-04': regression.load_fixtures()['h4-04']})['documents']['h4-04']
        self.assertEqual(sorted(result['states']), sorted(pinned['states']))
        for label, state in result['states'].items():
            with self.subTest(label):
                egd = state['routing'][EGD]
                self.assertEqual((egd['status'], egd['facts']), ('uncertain', [['extent', D2, 'document']]))
                self.assertEqual(state['inventory'][0]['extent'], D2)
                now = sorted([p['code'], p['bucket'], p['status'], p['fingerprint'][:12]] for p in state['proposals']
                             if p['bucket'] != 'alternative')
                self.assertEqual(now, pinned['states'][label]['proposals'])
        walk = {p['code']: p for p in result['states']['walk']['proposals']}
        self.assertEqual((walk['43251']['status'], walk['43251']['fingerprint'][:8]), ('ready', '9d6bff8e'))  # PI's


class InstalledReadingTests(SimpleTestCase):
    """Every must-hold and every guard: the shape reads exactly what installed reads."""

    def test_each_shape_reads_as_installed(self):
        for name, (text, want) in INSTALLED.items():
            with self.subTest(name):
                self.assertEqual(reading(text), want)


class GuardTests(SimpleTestCase):
    """The guards read directly (detect._pe_reach_doubted, detect._pe_endoscope_moved)."""

    def test_doubted(self):
        doubted = detect._pe_reach_doubted
        h404 = ('The gastroscope was introduced by mouth under visual guidance and ',
                'steered through the stomach and pylorus\ninto the ', '.')
        self.assertFalse(doubted(*h404))
        for before in ('The gastroscope could not be ', 'It was not ', "It couldn't be ", 'It was never ',
                       'The scope was unable to be ', 'It would be ', 'It may have been ', 'It will be ', 'It can be ',
                       'The scope, to be ', 'The scope is then ', 'It is usually ', 'It was probably ',
                       'It was partially ', 'It was nearly ', 'We hoped that the scope was ', 'If the scope was '):
            with self.subTest(before):
                self.assertTrue(doubted(before, 'steered into the ', '.'))
        for span in ('steered toward but not into the ', 'steered, presumably, into the ',
                     'navigated and an attempt made to pass to the '):
            with self.subTest(span):
                self.assertTrue(doubted('The scope was ', span, '.'))
        for post in (' later.', ' at the next procedure.', ' if the preparation allowed.', ' next time.'):
            with self.subTest(post):
                self.assertTrue(doubted('The scope was ', 'navigated to the ', post))
        self.assertFalse(doubted('No ulcers were seen and the gastroscope was ', 'steered into the ', '.'))

    def test_endoscope_moved(self):
        moved = detect._pe_endoscope_moved
        self.assertTrue(moved('The gastroscope was introduced by mouth and ', 'steered into the '))
        self.assertTrue(moved('We ', 'steered the gastroscope into the '))
        self.assertTrue(moved('A guidewire was placed and the gastroscope was ', 'steered over it into the '))
        self.assertFalse(moved('A guidewire was ', 'navigated through the pylorus into the '))
        self.assertFalse(moved('The gastroscope was held and a guidewire was ', 'steered into the '))
        self.assertFalse(moved('We ', 'steered the balloon into the '))
        self.assertFalse(moved('It was ', 'steered into the '))
        self.assertFalse(moved('', 'Steered into the '))


# --- GI round 4 Wave 1 repair, cycle 1: the shared copy guards (detect.todays_procedure_report and
# detect.in_todays_narrative; declared in pe.json and pi.json, amendment_20261101_cycle1). One implementation, read by
# PE's routing-only reach here and by PI's S1 and E1 (tests/test_gi4_pi.py). Each text below holds by exactly ONE guard,
# so the guard's mutant (ops/gi4/mutants.py, pe-today-*) is killed by its own behaviour. ---
FILL = ''.join(f'Line {i} of the outside summary lists medications and allergies in detail.\n' for i in range(8))
FIELDS = ('Date performed: October 19, 2026\nGastroenterologist: Synthetic Gastroenterologist, MD (fictional)\n'
          'Sedation and airway: propofol given by a CRNA (fictional)\n')
STRONG = B + 'Gastroscopy Then Colonoscopy in One Sitting\n' + FIELDS  # a head the layout reads no heading in
UPPER = 'Stomach and Duodenum\nThe gastroscope was advanced to the second part of the duodenum. The stomach was normal.\n'
REACH = 'The colonoscope reached the cecum.'


def narrative(text, needle=REACH, day=DAY):
    pos = text.index(needle)
    return detect.in_todays_narrative(text, pos, day, (pos, text.index('.', pos) + 1))


class TodaysProcedureReportTests(SimpleTestCase):
    """The strong head: an own-date field, a proceduralist field and a sedation field, each a labelled field; one own
    date; no title naming a later review or another record (refutation F2: 'Attending:', or 'sedation' in an
    allergy line, had passed sections.procedure_report_head)."""

    def test_the_regression_heads_are_strong(self):
        for doc_id in ('h4-03', 'h4-04', 'h4-06'):
            self.assertTrue(detect.todays_procedure_report(regression.load_fixtures()[doc_id]['text']), doc_id)
        self.assertTrue(detect.todays_procedure_report(STRONG))

    def test_an_own_date_field(self):
        self.assertFalse(detect.todays_procedure_report(STRONG.replace('Date performed: October 19, 2026\n', '')))

    def test_one_own_date_only(self):
        self.assertFalse(detect.todays_procedure_report(STRONG + 'Date of service: 10/20/2026\n'))

    def test_a_proceduralist_field_never_an_attending(self):
        self.assertFalse(detect.todays_procedure_report(STRONG.replace('Gastroenterologist:', 'Attending:')))

    def test_a_sedation_field_never_the_word_in_another_field(self):
        allergy = STRONG.replace('Sedation and airway: propofol given by a CRNA (fictional)',
                                 'Allergies: none; no reaction to sedation in the past.')
        self.assertFalse(detect.todays_procedure_report(allergy))

    def test_a_denied_sedation_is_no_sedation_field(self):
        self.assertFalse(detect.todays_procedure_report(
            STRONG.replace('Sedation and airway: propofol given by a CRNA (fictional)', 'Sedation: none')))

    def test_no_title_naming_a_later_review(self):
        self.assertFalse(detect.todays_procedure_report(
            STRONG.replace('Gastroscopy Then Colonoscopy in One Sitting', 'Colon Surveillance Pathology Review')))


class TodaysNarrativeTests(SimpleTestCase):
    """The copy guards of today's procedure narrative, each held alone (refutation F1 and F3: an attached outside report,
    unit statistics under a plan heading)."""

    def test_today_s_narrative_reads(self):
        self.assertTrue(narrative(STRONG + UPPER + 'Large Bowel\n' + REACH + ' No polyps were seen.\n'))
        for doc_id, needle in (('h4-04', 'The colonoscope reached the cecum'), ('h4-04', 'steered through'),
                               ('h4-03', 'The duodenal bulb and descending'), ('h4-06', 'Neoterminal ileum: normal')):
            text = regression.load_fixtures()[doc_id]['text']
            pos = text.index(needle)
            self.assertTrue(detect.in_todays_narrative(text, pos, None, (pos, pos + len(needle))), doc_id)

    def test_an_attachment_heading_opens_a_foreign_block(self):
        self.assertFalse(narrative(STRONG + UPPER + '\nAttached Report\n' + FILL + 'Large Bowel\n' + REACH + '\n'))

    def test_a_heading_dated_another_day_opens_a_foreign_block(self):
        self.assertFalse(narrative(STRONG + UPPER + '\nMercy GI, March 2023\n' + FILL + 'Large Bowel\n' + REACH + '\n'))

    def test_a_sign_off_opens_a_foreign_block(self):
        self.assertFalse(narrative(STRONG + UPPER + 'Signed electronically: Synthetic Gastroenterologist, MD (fictional)\n'
                                   'Large Bowel\n' + REACH + '\n'))

    def test_a_statement_that_a_copy_follows_opens_a_foreign_block(self):
        self.assertFalse(narrative(STRONG + UPPER.rstrip('\n') + ' Her earlier report is copied below.\n\nLarge Bowel\n'
                                   + REACH + '\n'))

    def test_the_governing_heading_names_no_other_occurrence_or_education(self):
        self.assertFalse(narrative(STRONG + UPPER + 'Index Examination\n' + FILL + REACH + '\n'))
        self.assertFalse(narrative(STRONG + UPPER + 'What Happens During a Colonoscopy\n' + FILL + REACH + '\n'))

    def test_the_governing_heading_names_no_facility(self):
        self.assertFalse(narrative(STRONG + UPPER + 'Mercy Endoscopy Center\n' + REACH + '\n'))

    def test_the_governing_heading_is_no_plan_heading(self):
        self.assertFalse(narrative(STRONG + UPPER + 'Next Steps\nBowel preparation: split dose the evening before.\n'
                                   + REACH + '\n'))

    def test_beyond_its_heading_s_reach_nothing_is_released(self):
        lines = ''.join(f'The mucosa of segment {i} was normal.\n' for i in range(210))
        self.assertFalse(narrative(STRONG + UPPER + 'Large Bowel\n' + lines + REACH + '\n'))

    def test_the_block_carries_no_other_date(self):
        self.assertFalse(narrative(STRONG + UPPER + 'Large Bowel\n' + REACH + ' A biopsy from the 09/28/2026 study was '
                                                                              'reviewed.\n'))

    def test_the_block_carries_no_sign_off(self):
        self.assertFalse(narrative(STRONG + UPPER + 'Large Bowel\n' + REACH + '\nReport signed by the Mercy GI '
                                                                              'endoscopist.\n'))

    def test_no_unit_statistics(self):
        text = STRONG + UPPER + 'Large Bowel\nIn our unit the colonoscope reached the cecum in 98 of 100 patients.\n'
        self.assertFalse(narrative(text, 'In our unit'))

    def test_never_under_another_occurrence(self):
        self.assertFalse(narrative(STRONG + UPPER + 'Large Bowel\nCopied: the colonoscope reached the cecum.\n',
                                   'the colonoscope reached'))

    def test_never_beyond_heading_reach(self):
        self.assertFalse(narrative(STRONG + 'Findings:\nThe stomach was normal.\nScope Passage and Views\n' + REACH + '\n'))


class AttachedReportReachTests(SimpleTestCase):
    """Refutation F3 (b840ae756): a routing-only verb read the cecum reached inside an attached outside colonoscopy
    report, and 45385 became READY. Routing reads such a reach as installed did again."""
    E = (B + 'Upper Endoscopy Report\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol by CRNA\n'
         '\nProcedure\nThe gastroscope was advanced to the second part of the duodenum. Cold forceps biopsies of the '
         'antrum were taken.\n\n')
    TAIL = ' A 10 mm sigmoid polyp was removed with a hot snare.\nReport signed by the Mercy GI endoscopist on 03/02/2024.\n'

    def shapes(self):
        lines = ''.join(f'Line {i} of the attached pages lists medications and allergies in detail.\n' for i in range(8))
        for verb in ('navigated', 'steered'):
            yield f'attached, {verb}', self.E + 'Attached Report\n' + lines + 'Procedure: Colonoscopy.\nThe colonoscope was ' \
                + verb + ' to the cecum.' + self.TAIL
            yield f'facility heading, {verb}', self.E + 'Mercy Endoscopy Center\nProcedure: Colonoscopy.\nThe colonoscope ' \
                'was ' + verb + ' to the cecum. A 10 mm sigmoid polyp was removed with a hot snare.\nSigned 03/02/2024.\n'

    def test_routing_reads_no_extent_there(self):
        for name, text in self.shapes():
            with self.subTest(name):
                colon = detect.route(text, dt.date(2026, 10, 20)).finding(COLON)
                jobs.release_routing_caches()
                self.assertNotIn('extent', [f.name for f in colon.facts])

    def test_45385_is_never_ready(self):
        from ops.gi4 import battery
        for name, text in self.shapes():
            with self.subTest(name):
                row = battery.run_row(battery.modules(), name, text, [
                    ('43239', 'Cold forceps biopsies of the antrum were taken.', 'done'),
                    ('45385', 'A 10 mm sigmoid polyp was removed with a hot snare.', 'not_done')])
                p = row['proposals']['45385']
                self.assertEqual((p['bucket'], p['status']), ('selected', 'needs_clarification'), name)
                self.assertIn('extent', p['clarifications'], name)


class HeadNamesFamilyTests(SimpleTestCase):
    """amendment_20261101_cycle1_b (pe.json): a routing-only reach counts only for a family the document's head NAMES, by
    routing's own service mentions in detect.head_procedure_spans (its title lines and its procedure fields, never past
    the body's first heading). The probes below leaked through cycle 1's copy guards: the pasted colonoscopy block of an
    EGD report under a heading no closed list names, or under none, made 45385 READY (installed: held on extent)."""
    NEUTRAL = ''.join(f'Line {i} of the pages lists medications and allergies in detail.\n' for i in range(8))
    BLOCK = ('Procedure: Colonoscopy.\nThe colonoscope was {verb} to the cecum. A 10 mm sigmoid polyp was removed with a '
             'hot snare.\n')

    def shapes(self):
        e = AttachedReportReachTests.E
        for verb in ('navigated', 'steered'):
            block = self.BLOCK.format(verb=verb)
            yield f'neutral heading, {verb}', e + 'Additional Pages\n' + self.NEUTRAL + block
            yield f'no heading, no filler, {verb}', e + block
            yield f'generic title, {verb}', e.replace('Upper Endoscopy Report', 'Procedure Note') + 'Additional Pages\n' \
                + self.NEUTRAL + block

    def test_routing_reads_no_extent_there(self):
        for name, text in self.shapes():
            with self.subTest(name):
                colon = detect.route(text, dt.date(2026, 10, 20)).finding(COLON)
                jobs.release_routing_caches()
                self.assertNotIn('extent', [f.name for f in colon.facts], name)

    def test_45385_is_never_ready(self):
        from ops.gi4 import battery
        for name, text in self.shapes():
            with self.subTest(name):
                row = battery.run_row(battery.modules(), name, text, [
                    ('43239', 'Cold forceps biopsies of the antrum were taken.', 'done'),
                    ('45385', 'A 10 mm sigmoid polyp was removed with a hot snare.', 'not_done')])
                p = row['proposals']['45385']
                self.assertEqual((p['bucket'], p['status']), ('selected', 'needs_clarification'), name)

    def test_the_head_spans_stop_at_the_body(self):
        e = AttachedReportReachTests.E + self.BLOCK.format(verb='navigated')
        spans = [e[s:t] for s, t in detect.head_procedure_spans(e)]
        self.assertIn('Upper Endoscopy Report', spans)
        self.assertNotIn('Procedure: Colonoscopy.', spans)  # the 8th non-empty line, but under the body's 'Procedure'
        field = B + 'Procedure Note\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nProcedure: Colonoscopy\n'
        self.assertIn('Procedure: Colonoscopy', [field[s:t] for s, t in detect.head_procedure_spans(field)])

    def test_the_head_rule_alone_decides_the_no_heading_shape(self):
        # the same text is read where the head names the colonoscopy, and only there: the head rule alone holds it
        text = AttachedReportReachTests.E + self.BLOCK.format(verb='navigated')
        extents = {}
        for title in ('Upper Endoscopy Report', 'Gastroscopy and Colonoscopy'):
            colon = detect.route(text.replace('Upper Endoscopy Report', title), dt.date(2026, 10, 20)).finding(COLON)
            jobs.release_routing_caches()
            extents[title] = [str(f.value) for f in colon.facts if f.name == 'extent']
        self.assertEqual(extents, {'Upper Endoscopy Report': [], 'Gastroscopy and Colonoscopy': ['cecum']})
