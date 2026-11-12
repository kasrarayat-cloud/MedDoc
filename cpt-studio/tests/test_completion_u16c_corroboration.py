"""Design round 2, cycle 2 (2026-11-08), U16 / u16c2: a food-bolus removal two statements of today's report corroborate.

Walk finding 4 stayed OPEN: a bolus "captured ... and brought out through the mouth", which the report's own Impression
states "cleared with a Roth net", read no removal (services.py: neither statement is one the installed readers read).
Cycle 1 (u16c) read the removal where the two statements agree; its lenses refuted the act it built (site and family
from the summary sentence, the summary line as evidence), the exits it read and the doubts it missed. Cycle 2
(services._corroborated_removal) reads the same two statements, narrower - an explicit exit that ENDS its sentence, a
food subject, a net, an Impression of the same part after it, one site - and adds the act the installed reader reads
from the input's FULL TWIN: statement (1)'s sentence replaced by "An impacted <food> bolus was found <site>. The bolus
was removed with <device>." The twin has an installed act, so on this tree it reads exactly as on the installed release:
the parity pins below compare a document with its own twin on the same tree.
The documents are synthetic paraphrases of the shapes, never the walk sets' own text. The walk round's pins
(tests/test_walk_round.BolusRemovalTests) are unchanged: none of their texts has a summary statement."""
from django.test import SimpleTestCase

from studio.gi import detect
from studio.gi import services as gi_services
from studio.types import ProviderCode
from tests.test_completion_structure import HEAD
from tests.test_harness_engine import DAY, corti, proposal, run, span

QUIET = ('pass', 'not_applicable', 'not_verified', 'info')
PROC = 'Procedure: Upper endoscopy\nDescription of procedure:\n'
REACH = 'The gastroscope was passed into the esophagus and advanced to the second portion of the duodenum. '
FOUND = 'An impacted meat bolus was found in the distal esophagus at 34 cm. '
FOUND_MEAT = 'A large piece of partly chewed meat was impacted in the distal esophagus at 34 cm. '
NET = 'A retrieval net was passed through the working channel. '
OUT = 'The bolus was captured with the net and brought out through the mouth.'
CITE = 'The bolus was captured with the net'
SUMMARY = '1. Meat impaction in the distal esophagus, cleared with a Roth net.'
IMP = '\nImpression:\n' + SUMMARY + '\n2. Normal stomach and duodenum.\n'
TWIN = 'An impacted meat bolus was found in the distal esophagus. The bolus was removed with a Roth net.'
TWIN_CITE = 'The bolus was removed with a Roth net'
SPLIT = ('We opened the retrieval net beside the steak and caught the food in three pieces, and each piece was pulled up '
         'into the overtube and brought out through the mouth with the scope.')


def flags(p):
    return sorted(c.id for c in p.checks if c.status not in QUIET and c.id != 'pfs.presence')


def document(narrative, impression=IMP):
    return HEAD + PROC + narrative + '\n' + impression


def acts(text):
    inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY), context_facts=None, pages=())
    return [(svc.family, a.status, a.anatomy, a.region, a.cues, a.technique, a.detail, tuple(e.text for e in a.evidence))
            for svc in inventory.services for a in svc.acts if a.kind == 'foreign_body']


def reading(text, quote=CITE, code='43247'):
    result = run(text, corti((code, span(text, quote))))
    found = proposal(result, code)
    return found.status, flags(found)


def held(text):
    return acts(text) == [] and reading(text, 'The gastroscope was passed') == ('needs_clarification', ['service.status'])


class CorroboratedRemovalTests(SimpleTestCase):
    def test_both_statements_read_the_removal(self):
        text = document(REACH + FOUND + NET + OUT)
        self.assertEqual(acts(text), [('gi.egd', 'performed', ('distal esophagus',), 'esophagus',
                                       ('performed: an act predicate',), '', '', (OUT,))])
        self.assertEqual(reading(text), ('ready', []))
        # REG-5: the summary line is no evidence of the act - a code citing only it is read as beside the twin's act
        self.assertEqual(reading(text, 'Meat impaction in the distal esophagus, cleared with a Roth net'),
                         ('ready', ['evidence.support']))

    def test_the_act_is_the_full_twins(self):
        # parity by construction: the act, and every code, read as the installed reader reads the full twin
        for narrative, sentence, quote in (
                (REACH + FOUND + NET + OUT, OUT, CITE),
                (REACH + FOUND + NET + 'The meat was captured with the net and brought out through the mouth.',
                 'The meat was captured with the net and brought out through the mouth.', 'The meat was captured'),
                (REACH + FOUND_MEAT + SPLIT, SPLIT, 'each piece was pulled up into the overtube'),
                (REACH + FOUND + NET + 'The bolus was grasped with the net and withdrawn out through the overtube.',
                 'The bolus was grasped with the net and withdrawn out through the overtube.', 'The bolus was grasped'),
                (REACH + FOUND + NET + OUT + ' Cold forceps biopsies were taken from the distal esophagus.', OUT, CITE)):
            with self.subTest(sentence):
                text = document(narrative)
                twin = text.replace(sentence, TWIN)
                self.assertEqual(text.count(sentence), 1)
                mine, theirs = acts(text), acts(twin)
                self.assertEqual(len(mine), 1)
                self.assertEqual([a[:7] for a in mine], [a[:7] for a in theirs])
                for code in ('43247', '43235', '43239', '43215', '43194'):
                    self.assertEqual(reading(text, quote, code), reading(twin, TWIN_CITE, code), code)

    def test_a_piece_of_the_food_its_own_sentence_split(self):
        self.assertEqual(reading(document(REACH + FOUND_MEAT + SPLIT), 'each piece was pulled up into the overtube'),
                         ('ready', []))
        for sentence in (SPLIT.replace('each piece was', 'one piece was'),
                         SPLIT.replace(' and brought out through the mouth with the scope', ' with the scope'),
                         SPLIT.replace('the food in three pieces', 'the polyp in three pieces')):
            with self.subTest(sentence):
                self.assertEqual(acts(document(REACH + FOUND_MEAT + sentence)), [])

    def test_the_narrative_alone_stays_held(self):
        text = document(REACH + FOUND + NET + OUT, '\nImpression:\n1. Food impaction in the distal esophagus.\n')
        self.assertTrue(held(text))

    def test_the_summary_alone_stays_held(self):
        self.assertTrue(held(document(REACH + FOUND + NET + 'The bolus was captured with the net.')))

    def test_the_exit_ends_its_sentence(self):
        # cycle-1 RELEASE 0: the exit is the food's last predicate, and an explicit exit from the body
        for sentence in ('The bolus was pulled up into the overtube with the net and then slipped distally.',
                         'The bolus was pulled up into the overtube with the net and then fell back.',
                         'The bolus was pulled up into the overtube with the net.',
                         'The bolus was captured with the net and brought out through the mouth, and then fell back.',
                         'The bolus was captured with the net and brought out through the mouth but slipped distally.',
                         'The bolus was captured with the net and brought out of the stomach.',
                         'The bolus was captured with the net and brought out through the mouth in two pieces.',
                         'The bolus was captured and brought out through the mouth.',
                         'The bolus was nearly brought out through the mouth with the net.'):
            with self.subTest(sentence):
                self.assertTrue(held(document(REACH + FOUND + NET + sentence)))

    def test_a_negated_exit_or_removal_holds(self):
        # cycle-1 RELEASE 1: anywhere in today's text, the Impression's other lines too
        for later in ('The bolus was not brought out.', 'The meat did not come out.', 'The bolus never came out.',
                      'The meat was not extracted.', 'The bolus could not be pulled out.'):
            with self.subTest(later):
                self.assertTrue(held(document(REACH + FOUND + NET + OUT + ' ' + later)))
        self.assertTrue(held(document(REACH + FOUND + NET + OUT, IMP + '3. The bolus was not brought out.\n')))

    def test_a_push_after_the_exit_holds(self):
        # cycle-1 RELEASE 2 (owner question Q1): a push, or the food moved by a course verb, after the exit
        for later in ('The bolus was then gently pushed with the scope tip.', 'The bolus was then pushed distally.',
                      'The bolus had to be pushed distally.', 'The meat was then advanced distally with the scope.',
                      'The remainder was advanced into the stomach.', 'It was then passed into the stomach.',
                      'The bolus had to be advanced into the stomach.', 'The meat then passed into the stomach.',
                      'Withdrawal was not possible, and the meat could only be advanced into the stomach.'):
            with self.subTest(later):
                self.assertTrue(held(document(REACH + FOUND + NET + OUT + ' ' + later)))
        self.assertTrue(held(document(REACH + FOUND + NET + OUT, IMP + '3. The meat was pushed through the junction.\n')))
        # an instrument's own course is no push
        text = document(REACH + FOUND + NET + OUT + ' The scope was then advanced into the stomach, which was normal.')
        self.assertEqual(len(acts(text)), 1)

    def test_a_later_removal_of_a_bolus_phrase_holds(self):
        # the twin's anchored finding would bind a later bolus phrase the input leaves unbound, and read an act there
        meat = 'The meat was captured with the net and brought out through the mouth.'
        for later in ('The bolus was then retrieved yesterday.', 'The bolus was removed by the ENT team.',
                      'The impaction was extracted at a later date.'):
            with self.subTest(later):
                self.assertEqual(acts(document(REACH + FOUND_MEAT + NET + meat + ' ' + later)), [])
        text = document(REACH + FOUND_MEAT + NET + meat + ' The overtube was removed with the scope at the end.')
        self.assertEqual(len(acts(text)), 1)

    def test_a_combined_report_without_a_single_family_reads_no_act(self):
        # cycle-1 REGRESS 0 (binding) and 1-3 (scope): no family's text holds statement (1), so there is no act
        colon = 'The colonoscope was then advanced to the cecum. The colon was normal. '
        text = (HEAD + 'Procedures: Upper endoscopy and colonoscopy\nFindings:\n' + REACH + FOUND + NET + OUT + ' ' + colon
                + '\n\nImpression:\nMeat impaction cleared with a Roth net, and a normal colon.\n')
        self.assertEqual(acts(text), [])
        self.assertEqual(reading(text, OUT, '45379'), ('needs_clarification', ['service.status']))
        self.assertEqual(reading(text, 'The colonoscope was then advanced to the cecum.', '45378'), ('ready', []))
        polyp = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        head = (HEAD + 'Procedures: Upper endoscopy and colonoscopy\nFindings:\n' + REACH
                + 'Cold forceps biopsies were obtained from the gastric antrum. \n')
        bolus = FOUND + NET + OUT + ' \n'
        f1 = (head + 'The colonoscope was then advanced to the cecum. ' + polyp + ' The cecum was presumably reached.\n'
              + bolus + IMP)
        f2 = (head + 'The colonoscope was then advanced to the cecum. Retroflexion in the rectum was possibly performed. '
              + polyp + '\n' + bolus + IMP)
        for text, code, quotes, expected in (
                (f1, '45385', (polyp, 'The cecum was presumably reached.'), ('needs_clarification', ['service.status'])),
                (f2, '43239', ('Cold forceps biopsies were obtained', 'Retroflexion in the rectum was possibly performed.'),
                 ('ready', ['service.status']))):
            with self.subTest(code):
                self.assertEqual(acts(text), [])
                result = run(text, [ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                                 tuple(span(text, q) for q in quotes))])
                found = proposal(result, code)
                self.assertEqual((found.status, flags(found)), expected)

    def test_the_site_is_the_impactions_own(self):
        for narrative, impression in (
                (REACH + FOUND + NET + OUT, '\nImpression:\n1. Meat impaction in the proximal esophagus, cleared with a '
                                            'Roth net.\n'),
                (REACH + 'Food residue was seen in the stomach. ' + FOUND + NET + OUT, IMP),
                (REACH + 'An impacted meat bolus was found in the esophagus. ' + NET + OUT, IMP),
                (REACH + 'An impacted meat bolus was found. ' + NET + OUT, '\nImpression:\n1. Meat impaction, cleared '
                                                                          'with a Roth net.\n')):
            with self.subTest(narrative[-120:] + impression):
                self.assertEqual(acts(document(narrative, impression)), [])
        # the narrative names no site: the summary phrase's own place; a distance only where no site is named
        found = acts(document(REACH + 'An impacted meat bolus was found. ' + NET + OUT))
        self.assertEqual([a[2] for a in found], [('distal esophagus',)])
        found = acts(document(REACH + 'An impacted meat bolus was found at 34 cm from the incisors. ' + NET + OUT))
        self.assertEqual([a[2] for a in found], [('distal esophagus',)])

    def test_only_a_net_and_only_food(self):
        for impression in ('\nImpression:\n1. Meat impaction in the distal esophagus, cleared with a snare.\n',
                           '\nImpression:\n1. Meat impaction in the distal esophagus, cleared with a basket.\n'):
            with self.subTest(impression):
                self.assertTrue(held(document(REACH + FOUND + NET + OUT, impression)))
        coin = document(REACH + 'A coin was found in the distal esophagus. ' + NET
                        + 'The coin was captured with the net and brought out through the mouth.',
                        '\nImpression:\n1. Coin in the distal esophagus, removed with a Roth net.\n')
        self.assertEqual(acts(coin), [])
        for sentence in ('Fragments of the meat were captured with the net and brought out through the mouth.',
                         'The polyp was captured with the net and brought out through the mouth.'):
            with self.subTest(sentence):
                self.assertEqual(acts(document(REACH + FOUND + NET + sentence)), [])

    def test_a_doubted_summary_holds(self):
        for summary in ('Meat impaction in the distal esophagus, possibly cleared with a Roth net.',
                        'Prior meat impaction in the distal esophagus, cleared with a Roth net.',
                        'Meat impaction in the distal esophagus, cleared with a Roth net by ENT.',
                        'Meat impaction in the distal esophagus, cleared with a Roth net on 2026-10-12.',
                        'Meat impaction in the distal esophagus, cleared with a Roth net into the stomach.'):
            with self.subTest(summary):
                self.assertEqual(acts(document(REACH + FOUND + NET + OUT, '\nImpression:\n1. ' + summary + '\n')), [])
        impression_first = HEAD + PROC.split('\n')[0] + '\nImpression:\n' + SUMMARY + '\n\nDescription of procedure:\n' \
            + REACH + FOUND + NET + OUT + '\n'
        self.assertEqual(acts(impression_first), [])

    def test_a_plan_that_still_schedules_a_removal_holds(self):
        text = document(REACH + FOUND + NET + OUT, IMP + 'Plan:\n- Repeat EGD tomorrow to remove the remaining bolus.\n')
        self.assertEqual(acts(text), [])
        text = document(REACH + FOUND + NET + OUT, IMP + 'Plan:\n- Return if a food impaction recurs.\n')
        self.assertEqual(len(acts(text)), 1)

    def test_tissue_is_never_the_material(self):
        for narrative in ('Cold forceps biopsies were taken. The biopsy fragments were captured with the net and brought '
                          'out through the mouth.',
                          'EMR was performed in three pieces. The resected pieces were captured with the net and '
                          'brought out through the mouth.'):
            with self.subTest(narrative):
                self.assertEqual(acts(document(REACH + FOUND + NET + narrative)), [])

    def test_an_installed_reading_of_a_foreign_body_stands(self):
        text = document(REACH + FOUND + NET + OUT, '\nImpression:\n1. Food impaction in the distal esophagus, removed '
                                                  'with a Roth net.\n')
        installed = acts(text)
        self.assertEqual(len(installed), 1)  # the installed act, and no second one
        self.assertNotIn(OUT, installed[0][7])

    def test_statement_one_carries_no_other_reading(self):
        # what the installed readers would read in statement (1)'s own sentence or line, the twin's sentences lack
        for narrative in (REACH + FOUND + NET + 'The bolus was captured with the net and brought out through the mouth '
                                                'with the endoscope.',
                          REACH + FOUND + NET + 'The bolus was captured with the forceps and the net and brought out '
                                                'through the mouth.',
                          REACH + FOUND + NET + 'The bolus was captured in the esophagus with the net and brought out '
                                                'through the mouth.',
                          REACH + FOUND + NET + '\nRemoval: ' + OUT):
            with self.subTest(narrative[-100:]):
                self.assertEqual(acts(document(narrative)), [])

    def test_the_account_before_it_is_read_too(self):
        for narrative in ('Her first endoscopy showed the following. ' + FOUND + NET + OUT + ' ' + REACH,
                          'She had an emergency endoscopy for that impaction. ' + FOUND + NET + OUT + ' ' + REACH,
                          REACH + FOUND + NET + 'We called otolaryngology, and the bolus was captured with the net and '
                                                'brought out through the mouth.',
                          REACH + FOUND + NET + 'It was reported that the bolus was brought out through the mouth with '
                                                'the net.',
                          REACH + FOUND + NET + "The bolus was captured with the net and brought out through the mouth "
                                                "with ENT's scope.",
                          REACH + FOUND + NET + 'The bolus was captured with the net and brought out through the mouth '
                                                'with a rigid esophagoscope.'):
            with self.subTest(narrative):
                self.assertEqual(acts(document(narrative)), [])

    def test_recorded_installed_classes_read_as_the_twin(self):
        # parity-bounded (recorded, not this design's): a statement before or after the removal that reassigns or undoes
        # it is read by no installed reader - the design reads each of these exactly as the installed reader reads its
        # full twin
        before, after, imp2, section = REACH + FOUND, NET + OUT, IMP, ''
        for prior, later, impression, extra in (
                (before + 'The surgeon took over. ', after, imp2, section),
                (before + 'That was during her first admission. ', after, imp2, section),
                (before, after + ' The bolus then fell back.', imp2, section),
                (before, after + ' All of the above took place yesterday in the emergency department.', imp2, section),
                (before, after, '\nImpression:\n' + SUMMARY + '\n2. This was done in the emergency department before my '
                                                               'arrival.\n', section),
                (before, after, imp2, '\nComplications:\nDuring withdrawal the bolus slipped out of the net and was '
                                      'swallowed by the patient.\n')):
            with self.subTest((prior + later + impression + extra)[-90:]):
                text = document(prior + later, impression + extra)
                twin = text.replace(OUT, TWIN)
                self.assertEqual(len(acts(text)), 1)
                for code in ('43247', '43235'):
                    self.assertEqual(reading(text, CITE, code), reading(twin, TWIN_CITE, code), code)


class TodaysAccountTests(SimpleTestCase):
    """Integration (2026-11-08; u16c2's release lens, finding 0): the account statement (1) closes is today's only where
    the sentence that first names the food states no more than the full twin's finding (a plain or locative lead, only
    locative prepositional phrases, no occasion word or date) and no sentence of the narrative before statement (1) tells
    another time. A follow-up report's account of an earlier emergency removal reads no removal (the installed hold), as
    the installed anchoring holds the same account told of "the bolus"."""

    MEAT = 'The meat was captured with the net and brought out through the mouth.'

    def test_an_account_of_another_occasion_reads_no_removal(self):
        for opener in ('Two days before, an', 'Last night, an', 'At the first endoscopy, an', 'Over the weekend, an',
                       'On 11/7, an'):
            text = document(REACH + opener + ' impacted meat bolus was found in the distal esophagus at 34 cm. ' + NET
                            + self.MEAT)
            with self.subTest(opener):
                self.assertEqual(acts(text), [])
                self.assertNotEqual(reading(text, 'The meat was captured')[0], 'ready')
        for tail in (' two days before.', ' at the first endoscopy.', ' over the weekend.'):
            text = document(REACH + 'An impacted meat bolus was found in the distal esophagus at 34 cm' + tail + ' ' + NET
                            + self.MEAT)
            with self.subTest(tail):
                self.assertEqual(acts(text), [])

    def test_a_plain_or_locative_introduction_reads_as_the_twin(self):
        self.assertEqual(len(acts(document(REACH + FOUND + NET + self.MEAT))), 1)
        found = 'At 33 cm from the incisors a large piece of meat filled the lumen and blocked it completely. '
        self.assertEqual(reading(document(REACH + found + SPLIT), 'each piece was pulled up into the overtube'),
                         ('ready', []))

    def test_a_sentence_needing_more_reads_than_are_read_holds(self):
        # cost bound (u16c2's lenses): past _DOUBT_READS structural subject reads in one sentence, the removal is held
        for n, expected in ((gi_services._DOUBT_READS, 1), (gi_services._DOUBT_READS + 1, 0)):
            later = ' The meat was seen and the scope passed' + ' passed' * (n - 1) + '.'
            with self.subTest(n):
                self.assertEqual(len(acts(document(REACH + FOUND + NET + self.MEAT + later))), expected)
