"""U24, the structure round's cycle 2 (2026-11-08): "<quantity> <time unit>(s) back" read as its "ago" twin, hold-only.

"Some months back a 6 mm polyp in the sigmoid colon was removed with a cold snare" is "Some months ago ...". No
installed reader read the phrase, in any layout, while the same text with "ago" is held in every layout, so a report
narrating an earlier polypectomy read it as today's (45385 READY; in a labelled paragraph N1's future exemption released
it too).
cues.HISTORICAL_BACK reads the phrase as routing reads its twin (the cue 'ago', historical, the twin's span), and
detect._held_by_back holds a code's own cited evidence where the phrase dates it - only there, and only to hold.

The pins: the class held in every layout (labelled, headed, a service-name line, plain, the Impression, an addendum);
the ordinary senses of "back" read nothing; the request side and HISTORICAL_CLAUSE unchanged; routing, structure and
the services reader read every text as installed; and the release shapes the cycle-2 prototypes measured stay held
(design-r2/u24b): a delayed colonoscopy's own doubt, a site-less act beside another family, a box row's bundled base
code, a polypectomy the phrase dates (held, never excluded). A held reading is the twin's own, so a code citing today's
act and the earlier session's sentence reads READY as its ago twin does (integration, 2026-11-08).
The changed approach (2026-11-08, OutcomeHoldTests): the twin's reading is no longer the code's evidence reading. Lowered
there, it let a co-cited plan line decide ahead of a hedge that held the code ("Probable complete colonoscopy." beside
"Await pathology."), so 45385 read READY where the installed release and the ago twin hold it. The engine now reads the
code as installed and only holds a code that reading releases (engine._dated_hold). Synthetic documents only; nothing is
sent."""
from __future__ import annotations

import time

from django.test import SimpleTestCase

from studio.gi import cues, detect, structure
from tests.test_harness_engine import corti, run, span

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Gastroenterology Procedure Report\n'
        'Date of service: 2026-10-14\n'
        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
IND = 'Indications: Surveillance after a sigmoid adenoma.\n'
CO = 'The colonoscope was introduced through the anus and advanced to the cecum.'
EG = 'The gastroscope was advanced to the second portion of the duodenum.'
PREP = 'The bowel preparation was adequate (Boston scale total 7: 2-3-2).'
SNQ = 'a 6 mm polyp in the sigmoid colon was removed with a cold snare'
BXQ = 'cold forceps biopsies were obtained from the gastric antrum'
QUIET = ('pass', 'not_applicable', 'not_verified', 'info')


def back_pattern():
    return cues.HISTORICAL_BACK[0][1]  # read at call time, so the other pins also read on a tree without it


def statuses(text, picks):
    """code -> (bucket, status) of each cited code (the code's own proposal)."""
    result = run(text, corti(*[(c, span(text, q)) for c, q in picks]))
    return {p.code: (p.bucket, p.status) for p in result.proposals if p.bucket != 'alternative'}


def ready(text, picks) -> dict:
    return {c: s == ('selected', 'ready') for c, s in statuses(text, picks).items()}


def layouts(lead, plan=''):
    """The member sentence ``lead`` in every layout: (name, text)."""
    para = CO + ' ' + lead + ' ' + PREP + plan
    tail = 'Impression: Clean polypectomy scar; no polyps.\n'
    return (
        ('labelled', HEAD + IND + 'Colonoscopy: ' + para + '\n' + tail),
        ('headed', HEAD + IND + 'Procedure: Colonoscopy\nFindings: ' + para + '\n' + tail),
        ('service-line', HEAD + IND + 'Colonoscopy\n' + para + '\n' + tail),
        ('plain', HEAD + 'Colonoscopy was performed for surveillance after a sigmoid adenoma. ' + para + '\n'),
        ('impression', HEAD + IND + 'Procedure: Colonoscopy\nFindings: ' + CO + ' No polyps.\nImpression: ' + lead
         + plan + '\n'),
        ('addendum', HEAD + IND + 'Procedure: Colonoscopy\nFindings: ' + CO + ' No polyps.\nImpression: Normal.\n'
         'Addendum: ' + lead + plan + '\n'),
    )


class PhraseTests(SimpleTestCase):
    """The shared reader: the phrase, its twin's span, what it never reads."""

    def test_the_ago_cue_and_the_request_side_are_as_installed(self):
        self.assertEqual(cues.HISTORICAL_CLAUSE[0][1].pattern,
                         r'\b(?:\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|several|many|few)\s+'
                         r'(?:days?|weeks?|months?|years?)\s+ago\b|\bago\b')
        self.assertFalse(any(pattern is back_pattern() for _, pattern in cues.HISTORICAL_CLAUSE))
        from ops.gi4 import freeze
        inventory = freeze.cue_inventory()
        self.assertFalse([name for name in inventory
                          if name.startswith(('cues._BACK', 'cues._AGO', 'cues.HISTORICAL_BACK'))])

    def test_each_form_is_read_with_its_twins_span(self):
        for text in ('Some months back a 6 mm polyp', 'A few days back cold forceps biopsies were obtained',
                     'Weeks back cold forceps biopsies were obtained', 'removed 2 years back.', 'Two weeks back, she',
                     'a year back which showed', 'Several months back she had', 'a couple of weeks back the',
                     '6 wks back.', '1 yr back she', 'Months back cold snare polypectomy was performed',
                     'two weeks back (outside)', 'two weeks back - normal', 'two weeks back | yes',
                     'removed weeks back'):
            with self.subTest(text):
                back = [m.span() for m in back_pattern().finditer(text)]
                twin = text.replace(' back', ' ago', 1)
                ago = [m.span() for m in cues.HISTORICAL_CLAUSE[0][1].finditer(twin)]
                self.assertEqual(len(back), 1)
                self.assertEqual([s for s, _ in back], [s for s, _ in ago])  # the twin's own start

    def test_ordinary_senses_read_nothing(self):
        for text in ('She has chronic back pain.', 'The scope was advanced back to the cecum.',
                     'The scope was pulled back to the rectum.', 'The pathology came back benign.',
                     'The specimen was sent from the back table.', 'She reports two weeks back pain.',
                     'Her recovery was set back by a cold.', 'The scope was brought back to the splenic flexure.',
                     'She has been a week back home after her trip.', 'Two weeks back pain began.',
                     'Three months back pain and weight loss.', 'She returned two weeks back to work.',
                     'She is two weeks back from a trip abroad.', 'She has been a month back at work.',
                     'She is two days back on aspirin.', 'Two sessions were done back to back.',
                     'She has two weeks back-pain.', 'This is her first day back.', 'two weeks back\npain began'):
            with self.subTest(text):
                self.assertEqual([m.group(0) for m in back_pattern().finditer(text)], [])

    def test_recorded_limits_read_nothing(self):
        # past senses the phrase does not read (narrower than the twin, each recorded): a preposition, a determiner
        # inside the subject, an active verb, an unlisted unit, two spaces after an unlisted quantity
        for text in ('A polyp was removed two years back at an outside hospital.',
                     'A polyp was removed two weeks back with a cold snare.',
                     'Weeks back cold forceps biopsies of the antrum were obtained.',
                     'Two years back colonoscopy showed polyps.', 'a decade back.', 'an hour back.',
                     'some months  back.'):
            with self.subTest(text):
                self.assertEqual([m.group(0) for m in back_pattern().finditer(text)], [])

    def test_the_pattern_is_linear(self):
        for unit in ('She reports two weeks back pain and some months back home. ',
                     'weeks back weeks back cold forceps biopsy forceps biopsy forceps biopsy ',
                     'a a few some several many two weeks days months years ', '2 weeks  back 6 wks back 1 yr back '):
            text = unit * (200_000 // len(unit))
            with self.subTest(unit[:30]):
                t0 = time.monotonic()
                sum(1 for _ in back_pattern().finditer(text))
                self.assertLess(time.monotonic() - t0, 2.0)


class MemberTests(SimpleTestCase):
    """The class, held in every layout; the course of today's examination stays READY."""

    def test_the_integrators_member_is_held(self):
        body = ('The colonoscope was introduced through the anus and advanced to the cecum. Some months back a 6 mm '
                'polyp in the sigmoid colon was removed with a cold snare; the scar was seen today and was clean. The '
                'bowel preparation was adequate (Boston scale total 7: 2-3-2). Surveillance in 3 years.\n')
        text = HEAD + IND + 'Colonoscopy: ' + body + 'Impression: Clean polypectomy scar; no polyps.\n' \
            'Plan: Surveillance in 3 years.\n'
        self.assertEqual(ready(text, [('45385', SNQ)]), {'45385': False})
        self.assertEqual(ready(text.replace(' back', ' ago'), [('45385', SNQ)]), {'45385': False})

    def test_each_form_is_held_in_every_layout(self):
        for lead in ('Some months back ' + SNQ + '.', 'A few days back ' + SNQ + '.', 'Two weeks back, ' + SNQ + '.',
                     'Many years back ' + SNQ + '.', 'Months back ' + SNQ + '.',
                     'A 6 mm polyp in the sigmoid colon was removed with a cold snare some months back.'):
            for plan in ('', ' Surveillance in 3 years.'):
                for name, text in layouts(lead, plan):
                    quote = SNQ if SNQ in text else SNQ[0].upper() + SNQ[1:]
                    with self.subTest(lead=lead[:20], plan=plan, layout=name):
                        self.assertEqual(ready(text, [('45385', quote)]), {'45385': False})

    def test_the_egd_forms_are_held(self):
        for lead in ('Weeks back ' + BXQ + '.', 'A few days back ' + BXQ + '; the sites were seen today.'):
            for plan in ('', ' Repeat in 1 year.'):
                text = (HEAD + 'Indications: Dyspepsia.\nUpper endoscopy: ' + EG + ' ' + lead + plan
                        + '\nImpression: Gastric biopsy sites.\n')
                with self.subTest(lead=lead[:20], plan=plan):
                    self.assertEqual(ready(text, [('43239', BXQ)]), {'43239': False})

    def test_todays_course_beside_a_member_stays_ready(self):
        # Z9: a clean colonoscopy, then an upper endoscopy narrating biopsies from a few days back (the ago twin also
        # holds the colonoscopy, through the tract rule: a hold this repair does not copy)
        egd = 'Upper endoscopy: ' + EG + ' A few days back ' + BXQ + '; the sites were seen today. Repeat in 1 year.\n'
        text = (HEAD + IND + 'Colonoscopy: ' + CO + ' ' + PREP + ' No polyps.\n' + egd
                + 'Impression: Normal colon; gastric biopsy sites.\nPlan: Surveillance.\n')
        self.assertEqual(ready(text, [('43239', BXQ), ('45378', CO[:-1])]), {'43239': False, '45378': True})


class HoldOnlyTests(SimpleTestCase):
    """Routing, structure and the services reader read every text as installed; nothing the phrase reads is released."""

    def test_routing_and_structure_read_the_phrase_as_nothing(self):
        for name, text in layouts('Some months back ' + SNQ + '.', ' Surveillance in 3 years.'):
            plain = text.replace(' back', ' bxck')  # the same text with no phrase: routing and structure read it alike
            with self.subTest(name):
                self.assertEqual([(f.family, f.status) for f in detect.route(text).findings],
                                 [(f.family, f.status) for f in detect.route(plain).findings])
                self.assertEqual([w for _, w in structure.decisions(text)], [w for _, w in structure.decisions(plain)])

    def test_only_a_codes_own_evidence_reads_it(self):
        text = layouts('Some months back ' + SNQ + '.')[1][1]
        start = text.index(SNQ)
        self.assertEqual(detect.status_for_span(text, start, start + len(SNQ))[0], 'performed')
        status, held = detect.status_for_span(text, start, start + len(SNQ), back=True)
        self.assertEqual(status, 'uncertain')
        self.assertTrue(any('back' in cue for cue in held))
        twin = text.replace('Some months back', 'Some months ago')  # the twin's own reading, as installed
        at = twin.index(SNQ)
        self.assertEqual(status, detect.status_for_span(twin, at, at + len(SNQ))[0])

    def test_a_delayed_colonoscopy_keeps_its_own_doubt(self):
        # read at the family level, the phrase replaced the doubt this sentence carries and released 45385
        for lead in ('This colonoscopy had been pushed two weeks back.', 'Colonoscopy was delayed two weeks back.'):
            act = SNQ[0].upper() + SNQ[1:]
            text = (HEAD + IND + 'Procedure: Colonoscopy\nFindings: ' + lead + ' ' + CO + ' ' + act
                    + '.\nImpression: Polyp removed.\n')
            with self.subTest(lead):
                self.assertEqual(ready(text, [('45385', act)]), {'45385': False})

    def test_a_site_less_act_never_binds_to_the_other_family(self):
        # read by structure (N1), the phrase held the colonoscopy paragraph, and the Impression's biopsies bound to the
        # upper endoscopy, the one family left read performed (43239 READY)
        member = (' Some months back a 6 mm polyp was removed with a cold snare; the scar was seen today. '
                  'Surveillance in 3 years.')
        text = (HEAD + 'Indications: Dyspepsia; anemia.\nUpper endoscopy: ' + EG
                + ' The stomach and duodenum were normal.\nColonoscopy: ' + CO + ' The bowel preparation was adequate.'
                + member + '\nImpression: Cold forceps biopsies were obtained.\n')
        self.assertEqual(ready(text, [('43239', 'Cold forceps biopsies were obtained')]), {'43239': False})

    def test_a_box_rows_base_code_stays_bundled(self):
        # read by every caller of status_for_span, the services reader dropped the row's polypectomy and freed 45378
        for row in ('[x] Cold snare polypectomy of a 6 mm sigmoid polyp two weeks back.',
                    '☒ Cold snare polypectomy of a 6 mm sigmoid polyp some months back'):
            text = (HEAD + 'Indications: Surveillance.\nProcedure: Colonoscopy\nFindings: ' + CO + '\n' + row
                    + '\nImpression: Polyp.\n')
            with self.subTest(row[:3]):
                self.assertEqual(ready(text, [('45378', CO[:-1])]), {'45378': False})
                self.assertEqual(ready(text, [('45385', 'Cold snare polypectomy'), ('45378', CO[:-1])]),
                                 {'45385': False, '45378': False})

    def test_a_dated_polypectomy_is_held_never_excluded(self):
        text = (HEAD.replace('Gastroenterology Procedure Report', 'Colonoscopy report (fictional)')
                + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was '
                'completed.\nIn this case, a 6 mm polyp in the ascending colon was removed with a cold snare two years '
                'back.\n')
        quote = 'a 6 mm polyp in the ascending colon was removed with a cold snare'
        got = statuses(text, [('45378', 'The colonoscope was advanced to the cecum'), ('45385', quote)])
        self.assertEqual(got['45385'], ('selected', 'needs_clarification'))
        self.assertNotEqual(got['45378'], ('selected', 'ready'))

    def test_a_reading_that_is_not_performed_is_left_as_installed(self):
        text = (HEAD + IND + 'Procedure: Colonoscopy\nFindings: ' + CO + ' The planned polypectomy was cancelled two '
                'weeks back.\nImpression: Normal.\n')
        start = text.index('The planned polypectomy was cancelled')
        end = start + len('The planned polypectomy was cancelled')
        self.assertEqual(detect.status_for_span(text, start, end, back=True), detect.status_for_span(text, start, end))



class TwinReadingTests(SimpleTestCase):
    """A held reading is the ago twin's own (integration, 2026-11-08: u24b's regress lens, finding 0). Converted to
    'uncertain', the earlier session's sentence contested today's act cited beside it and held a code its twin reads
    READY; as the twin's 'historical' it is named in a warn beside today's passage."""

    def test_a_code_citing_today_and_the_earlier_session_reads_as_its_twin(self):
        from studio.types import ProviderCode
        quotes = ('Today 4 bands were applied to the esophageal varices', 'EVL was done',
                  'band ligation done today with 4 bands')
        for when in ('2 weeks back', '2 weeks ago'):
            text = (HEAD + 'Indications: Esophageal varices; secondary prophylaxis after variceal bleeding.\n'
                    'Procedure: Upper endoscopy with variceal band ligation\nFindings: ' + EG + ' Grade II esophageal '
                    'varices with post-banding scars were seen. EVL was done ' + when + '. Today 4 bands were applied '
                    'to the esophageal varices.\nImpression: Esophageal varices; band ligation done today with 4 '
                    'bands.\nPlan: Repeat EVL in 2 weeks.\n')
            entry = ProviderCode('selected', 'cpt', '43244', 'UNVERIFIED PROVIDER WORDING',
                                 tuple(span(text, q) for q in quotes))
            result = run(text, [entry])
            got = {p.code: (p.bucket, p.status) for p in result.proposals if p.bucket != 'alternative'}
            with self.subTest(when):
                self.assertEqual(got['43244'], ('selected', 'ready'))
                start = text.index('EVL was done')
                self.assertEqual(detect.status_for_span(text, start, start + len('EVL was done'), back=True)[0],
                                 'historical')

    def test_the_earlier_session_alone_is_held(self):
        text = (HEAD + 'Indications: Esophageal varices.\nProcedure: Upper endoscopy\nFindings: ' + EG
                + ' Small esophageal varices with post-banding scars were seen. EVL was done 2 weeks back.\n'
                'Impression: Small varices; no banding today.\n')
        self.assertEqual(ready(text, [('43244', 'EVL was done')]), {'43244': False})

class OrdinarySenseTests(SimpleTestCase):
    """Today's polypectomy stays READY beside the ordinary senses, and where the phrase dates another thing."""

    def test_ordinary_senses_beside_todays_act_read_as_installed(self):
        # read exactly as the same text with the word written "bxck" (no phrase): READY under a heading; in a labelled
        # paragraph N1's own reading of these sentences (reported speech, a temporal lead, a time unit) decides, as
        # installed
        for sentence in ('She reports two weeks back pain.', 'The scope was pulled back to the rectum.',
                         'She has been a week back home after her trip.', 'The pathology came back benign.',
                         'She returned two weeks back to work.', 'This is her first day back.'):
            for name, text in layouts(SNQ[0].upper() + SNQ[1:] + '. ' + sentence, ' Surveillance in 3 years.')[:2]:
                picks = [('45385', SNQ[0].upper() + SNQ[1:])]
                with self.subTest(sentence=sentence, layout=name):
                    self.assertEqual(ready(text, picks), ready(text.replace(' back', ' bxck'), picks))
                    if name == 'headed':
                        self.assertEqual(ready(text, picks), {'45385': True})

    def test_a_time_routing_gives_to_another_thing_holds_nothing(self):
        for sentence in ('A 6 mm polyp, first seen two years back, was removed with a cold snare today.',
                         'A 6 mm polyp was removed with a cold snare after a positive FIT two months back.'):
            text = HEAD + IND + 'Procedure: Colonoscopy\nFindings: ' + CO + ' ' + sentence + '\nImpression: Polyp.\n'
            quote = sentence[:sentence.index('cold snare') + len('cold snare')]
            with self.subTest(sentence[:30]):
                self.assertEqual(ready(text, [('45385', quote)]), {'45385': True})


class OutcomeHoldTests(SimpleTestCase):
    """The hold is made at the code's outcome, never at its evidence reading (the changed approach, 2026-11-08): a code
    reads as installed wherever the installed readings do not release it, whatever else it cites."""

    @staticmethod
    def member(hedge, plan):
        return (HEAD + IND + 'Procedure: Colonoscopy\nFindings: ' + CO + ' Some months back ' + SNQ + '. ' + PREP
                + '\nImpression: Clean polypectomy scar; no polyps. ' + hedge + '\nPlan: ' + plan + '.\n')

    @staticmethod
    def cited(text, quotes, *more):
        from studio.types import ProviderCode
        entries = [ProviderCode('selected', 'cpt', '45385', 'UNVERIFIED PROVIDER WORDING',
                                tuple(span(text, q) for q in quotes))]
        entries += [ProviderCode('selected', 'cpt', c, 'UNVERIFIED PROVIDER WORDING', (span(text, q),)) for c, q in more]
        return {p.code: (p.bucket, p.status) for p in run(text, entries).proposals if p.bucket != 'alternative'}

    def test_a_hedge_and_a_plan_cited_beside_the_dated_act_read_as_installed(self):
        # the integration's first form: the twin's 'uncertain' left 'Await pathology' (planned) deciding ahead of the
        # hedge, and 45385 read READY in every citation order (design-r2/corr/u24_resolve.py)
        import itertools
        for hedge, plan in (('Probable complete colonoscopy.', 'Await pathology'),
                            ('Complete colonoscopy?', 'Repeat colonoscopy in 3 years')):
            text = self.member(hedge, plan)
            parts = (hedge.rstrip('.'), SNQ, plan)
            for order in itertools.permutations(parts):
                with self.subTest(hedge=hedge, order=[q[:12] for q in order]):
                    got = self.cited(text, order)
                    self.assertEqual(got, self.cited(text.replace(' back', ' bxck'), order))
                    self.assertNotEqual(got['45385'], ('selected', 'ready'))

    def test_the_dated_act_alone_is_held_and_its_base_stays_bundled(self):
        text = self.member('Probable complete colonoscopy.', 'Await pathology')
        self.assertEqual(self.cited(text.replace(' back', ' bxck'), [SNQ])['45385'], ('selected', 'ready'))
        got = self.cited(text, [SNQ], ('45378', CO[:-1]))
        self.assertEqual(got['45385'], ('selected', 'needs_clarification'))
        self.assertNotEqual(got['45378'], ('selected', 'ready'))

    def test_the_code_s_evidence_reading_is_the_installed_one(self):
        from studio.types import EvidenceSpan
        from studio.validation import checks
        text = self.member('Probable complete colonoscopy.', 'Await pathology')
        at = text.index(SNQ)
        own = checks.evidence_readings(text, [EvidenceSpan(0, at, at + len(SNQ), SNQ, True)])
        self.assertEqual([r.status for r in own], ['performed'])
        dated, replaced = checks.dated_readings(text, own)
        self.assertEqual([r.status for r in replaced], [detect.status_for_span(text, at, at + len(SNQ), back=True)[0]])
        self.assertNotIn(replaced[0].status, ('performed', 'incomplete'))
        self.assertEqual(checks.dated_readings(text.replace(' back', ' bxck'), own), ((), ()))

    def test_todays_banding_beside_an_earlier_session_stays_ready(self):
        # the first form held today's act where the phrase dated another session inside its sentence
        for findings in ('Two internal hemorrhoid columns were banded today, after a first session 4 weeks back.',
                         'First banding was done 4 weeks back, today two internal hemorrhoid columns were banded.'):
            text = (HEAD + 'Indications: Bleeding internal hemorrhoids.\nProcedure: Anoscopy\nFindings: The anoscope was '
                    'inserted. ' + findings + '\nImpression: As above.\nPlan: Routine.\n')
            quote = 'Two internal hemorrhoid columns were banded today' if findings.startswith('Two') \
                else 'today two internal hemorrhoid columns were banded'
            with self.subTest(findings[:20]):
                self.assertEqual(ready(text, [('46221', quote)]), {'46221': True})
