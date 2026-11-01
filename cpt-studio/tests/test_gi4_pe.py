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
