"""Regressions for the refutation pass over GI routing (round 1).

Each class reproduces one confirmed finding (status:N in the triage) from its
exact input, then adds the wordings the finding lists and positive controls
that must still read performed. Synthetic text only; pure routing plus the real
validation engine with an empty in-memory reference.
"""
import unittest
from datetime import date

from studio.gi.detect import route, status_for_span
from studio.gi.sections import layout
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode
from studio.validation.engine import assess
from studio.gi.context import extract_context

HEADER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
DOS = date(2026, 10, 21)
NOT_PERFORMED = ('planned', 'historical', 'cancelled', 'negated', 'uncertain')
SILENT = 'uncertain: no performance evidence'


def span(text, phrase, occurrence=0):
    start = -1
    for _ in range(occurrence + 1):
        start = text.index(phrase, start + 1)
    return start, start + len(phrase)


def read(text, phrase, occurrence=0):
    return status_for_span(text, *span(text, phrase, occurrence))


def family(text, slug):
    finding = route(text).finding(slug)
    return finding.status if finding else None


def fact_value(text, slug, name):
    finding = route(text).finding(slug)
    for item in (finding.facts if finding else ()):
        if item.name == name:
            return item.value
    return None


def run_engine(text, picks):
    """picks: (code, evidence phrase[, occurrence]). The proposals by code."""
    codes = []
    for index, pick in enumerate(picks):
        code, phrase = pick[0], pick[1]
        start, end = span(text, phrase, pick[2] if len(pick) > 2 else 0)
        codes.append(ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED',
                                  evidence=(EvidenceSpan(0, start, end, text[start:end], True),), index=index))
    result = assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=extract_context(text), routing=route(text),
                    normalized=NormalizedResponse('replay', 'test', codes=tuple(codes)),
                    reference=InMemoryReferenceLookup((), {}), service_date=DOS, provider_status='succeeded',
                    extraction_status='ok')
    return {p.code: p for p in result.proposals}, result


class Status0InSpanNegationTests(unittest.TestCase):
    """status:0 — a negation inside an evidence span that names no service governs the span."""

    TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\nProcedure: Colonoscopy\n'
            'Findings: The colonoscope was advanced to the cecum. The colonic mucosa was normal. No biopsies were '
            'taken. No polypectomy was performed.\n')

    def test_the_claimed_spans_read_negated(self):
        self.assertEqual(span(self.TEXT, 'No biopsies were taken.'), (179, 202))
        self.assertEqual(span(self.TEXT, 'No polypectomy was performed.'), (203, 232))
        for phrase in ('No biopsies were taken.', 'No polypectomy was performed.'):
            self.assertEqual(read(self.TEXT, phrase)[0], 'negated', phrase)

    def test_the_claimed_codes_are_excluded_not_ready(self):
        proposals, _ = run_engine(self.TEXT, [('45380', 'No biopsies were taken.'),
                                              ('45385', 'No polypectomy was performed.')])
        for code in ('45380', '45385'):
            self.assertEqual((proposals[code].bucket, proposals[code].reinstatable), ('excluded', True), code)
            self.assertNotEqual(proposals[code].status, 'ready')

    def test_the_listed_wordings_never_read_performed(self):
        base = HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. '
        for sentence in ('Biopsies were not obtained.', 'Polypectomy was not performed.', 'No dilation was required.',
                         'The stricture was not dilated.', 'No biopsies were taken.', 'No polypectomy was performed.',
                         'No polyps were removed.', 'No clips were placed.', 'Biopsies: none.',
                         'No cold snare polypectomy was performed.', 'No random biopsies were obtained.'):
            with self.subTest(sentence=sentence):
                status, cues = read(base + sentence + '\n', sentence)
                self.assertEqual(status, 'negated', cues)

    def test_performed_wordings_still_read_performed(self):
        base = HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. '
        for sentence in ('Biopsies were taken from the ascending colon.', 'Two polyps were removed with a cold snare.',
                         'The stricture was dilated with a balloon.', 'Two clips were placed.',
                         'A polyp was removed with a cold snare without difficulty.',
                         'Biopsies were obtained and no bleeding was seen.'):
            with self.subTest(sentence=sentence):
                status, cues = read(base + sentence + '\n', sentence)
                self.assertEqual(status, 'performed', cues)
        status, _ = read(self.TEXT, 'The colonoscope was advanced to the cecum.')
        self.assertEqual(status, 'performed')


class Status1CoordinatedNegationTests(unittest.TestCase):
    """status:1 — "neither ... nor", elliptical "X was not" and "but not the X" negate X."""

    NEITHER = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
               'Indication: EUS for evaluation of a pancreatic cyst.\n'
               'Neither EUS nor ERCP was performed today because the patient had eaten breakfast.\nPlan: Reschedule.\n')
    ELLIPSIS = (HEADER + 'Indication: Dysphagia and a pancreatic cyst.\nProcedure: EGD was performed; EUS was not.\n'
                'Findings: The scope was advanced to the second part of the duodenum. Normal mucosa.\n')

    def test_neither_nor_negates_both_services(self):
        self.assertEqual(span(self.NEITHER, 'Neither EUS nor ERCP was performed today'), (125, 165))
        result = route(self.NEITHER)
        self.assertEqual(result.finding('gi.eus').status, 'negated')
        self.assertEqual(result.finding('gi.ercp').status, 'negated')
        self.assertEqual(read(self.NEITHER, 'Neither EUS nor ERCP was performed today')[0], 'negated')

    def test_neither_nor_code_is_excluded_and_no_missed_ercp_is_reported(self):
        proposals, result = run_engine(self.NEITHER, [('43259', 'Neither EUS nor ERCP was performed today')])
        self.assertEqual(proposals['43259'].bucket, 'excluded')
        unproposed = [c for c in result.encounter_checks if c.id == 'services.unproposed']
        self.assertTrue(all('ERCP' not in c.detail for c in unproposed), [c.detail for c in unproposed])

    def test_elliptical_was_not(self):
        result = route(self.ELLIPSIS)
        self.assertEqual(result.finding('gi.eus').status, 'negated')
        self.assertEqual(result.finding('gi.egd').status, 'performed')
        self.assertEqual(read(self.ELLIPSIS, 'EUS was not.')[0], 'negated')
        proposals, _ = run_engine(self.ELLIPSIS, [('43259', 'EUS was not.')])
        self.assertEqual(proposals['43259'].bucket, 'excluded')

    def test_the_listed_variants(self):
        for section in ('', 'Procedure: ', 'Findings: ', 'Technique: '):
            for body, egd in (('EGD was performed, colonoscopy was not.', 'performed'),
                              ('EGD was performed but not the colonoscopy.', 'performed'),
                              ('EGD was performed; colonoscopy was not.', 'performed'),
                              ('EGD, not colonoscopy, was performed.', None),
                              ('Neither EGD nor colonoscopy was performed.', 'negated'),
                              ('EGD was performed. Colonoscopy wasn\'t.', 'performed')):
                text = HEADER + section + body + '\n'
                with self.subTest(section=section, body=body):
                    self.assertNotIn(family(text, 'gi.colonoscopy'), ('performed', 'incomplete'))
                    self.assertEqual(family(text, 'gi.colonoscopy'), 'negated')
                    if egd:
                        self.assertEqual(family(text, 'gi.egd'), egd)

    def test_a_negation_of_another_service_does_not_touch_this_one(self):
        text = HEADER + 'EGD was performed today, no colonoscopy was performed today.\n'
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        text = HEADER + 'Procedure: Flexible sigmoidoscopy instead of colonoscopy.\n'
        self.assertEqual(family(text, 'gi.flex_sig'), 'performed')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'negated')


class Status2CuelessNegationTests(unittest.TestCase):
    """status:2 — a positive section's default never makes a negated, declined, replaced or pending service performed."""

    LINES = (('Colonoscopy - not performed.', 'gi.colonoscopy'), ('Colonoscopy: not performed.', 'gi.colonoscopy'),
             ('Colonoscopy: patient declined.', 'gi.colonoscopy'), ('Colonoscopy: declined.', 'gi.colonoscopy'),
             ('EGD and colonoscopy (not performed).', 'gi.colonoscopy'), ('ERCP not indicated.', 'gi.ercp'),
             ('ERCP pending insurance approval.', 'gi.ercp'), ('Colonoscopy: N/A', 'gi.colonoscopy'),
             ('Colonoscopy: no', 'gi.colonoscopy'), ('Colonoscopy: none.', 'gi.colonoscopy'),
             ('Flexible sigmoidoscopy instead of colonoscopy.', 'gi.colonoscopy'), ('EGD in lieu of EUS.', 'gi.eus'),
             ('An EGD was performed rather than EUS.', 'gi.eus'), ('Colonoscopy was not performed.', 'gi.colonoscopy'),
             ('The patient declined colonoscopy.', 'gi.colonoscopy'), ('No colonoscopy was performed.', 'gi.colonoscopy'),
             ('Colonoscopy: not done.', 'gi.colonoscopy'), ('Colonoscopy (not performed)', 'gi.colonoscopy'))

    def test_the_survey_under_every_positive_heading(self):
        for heading in ('Procedures performed:', 'Findings:', 'Procedure:', 'Technique:'):
            for line, slug in self.LINES:
                text = HEADER + heading + '\n' + line + '\n'
                with self.subTest(heading=heading, line=line):
                    self.assertIn(family(text, slug), NOT_PERFORMED)
                    status, cues = read(text, line)
                    self.assertIn(status, NOT_PERFORMED, cues)
                    self.assertFalse(all(c.startswith(SILENT) for c in cues), cues)  # a hedged, not silent, reading

    def test_case_a_declined_eus(self):
        text = (HEADER + 'Indication: EUS for evaluation of a pancreatic cyst.\nProcedures performed:\n'
                'EUS: not performed (patient declined).\n')
        self.assertEqual(span(text, 'EUS: not performed (patient declined).'), (147, 185))
        self.assertEqual(family(text, 'gi.eus'), 'negated')
        proposals, result = run_engine(text, [('43259', 'EUS: not performed (patient declined).')])
        self.assertEqual(proposals['43259'].bucket, 'excluded')
        proposals, _ = run_engine(text, [('43259', 'EUS')])  # evidence is only the indication's mention
        self.assertNotEqual(proposals['43259'].status, 'ready')

    def test_case_b_ercp_interventions_not_done(self):
        text = (HEADER + 'Indication: Choledocholithiasis suspected on imaging.\nProcedure: ERCP\n'
                'Description of procedure: The duodenoscope was advanced to the second part of the duodenum. '
                'Deep biliary cannulation was successful. The cholangiogram was normal. '
                'Sphincterotomy: not performed. Stent: none.\nImpression: Normal cholangiogram.\n')
        self.assertEqual(family(text, 'gi.ercp'), 'performed')
        self.assertIsNone(fact_value(text, 'gi.ercp', 'interventions'))
        proposals, _ = run_engine(text, [('43260', 'Deep biliary cannulation was successful.'),
                                         ('43262', 'Sphincterotomy: not performed.'), ('43274', 'Stent: none.')])
        self.assertEqual(proposals['43260'].bucket, 'selected')
        for code in ('43262', '43274'):
            self.assertEqual(proposals[code].bucket, 'excluded', code)

    def test_case_c_eus_replaced_by_egd(self):
        text = (HEADER + 'Indication: Pancreatic cyst; EUS requested.\n'
                'Procedure: Because the echoendoscope was unavailable, an EGD was performed rather than EUS.\n'
                'Findings: The esophagus, stomach and duodenum were normal.\n')
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        self.assertIn(family(text, 'gi.eus'), NOT_PERFORMED)
        proposals, _ = run_engine(text, [('43259', 'EUS', 1)])
        self.assertEqual(proposals['43259'].bucket, 'excluded')

    def test_controls_named_under_positive_headings_stay_performed(self):
        for heading in ('Procedures performed:', 'Procedure:'):
            for line, slug in (('Colonoscopy.', 'gi.colonoscopy'), ('EGD with cold forceps biopsy.', 'gi.egd'),
                               ('Colonoscopy, no sedation.', 'gi.colonoscopy'),
                               ('Colonoscopy without complications.', 'gi.colonoscopy'),
                               ('EGD with biopsy; no dilation.', 'gi.egd')):
                text = HEADER + heading + '\n' + line + '\n'
                with self.subTest(heading=heading, line=line):
                    self.assertEqual(read(text, line.split(' ')[0].rstrip('.,'))[0], 'performed')


class Status3UnrecognisedHeadingTests(unittest.TestCase):
    """status:3 — text under a heading the code does not know never inherits a positive section."""

    @staticmethod
    def colon_report(heading):
        return (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. '
                'The colon was normal.\n' + heading + '\n1. Normal colon.\n'
                '2. EUS for evaluation of the pancreatic cyst seen on CT.\n')

    @staticmethod
    def egd_report(heading):
        return (HEADER + 'Procedure: EGD\nFindings: The endoscope was advanced to the second part of the duodenum. '
                'Normal EGD.\n' + heading + '\nColonoscopy: the colonoscope was advanced to the cecum and a 10 mm '
                'polyp was removed with cold snare.\n')

    def test_case_a_recommendations_are_planned(self):
        for heading in ('Impression and Recommendations:', 'IMPRESSION AND RECOMMENDATIONS:',
                        'Impression/Recommendations:', 'Impression & Recommendations:',
                        'Assessment and Recommendations:', 'Post-procedure plan:', 'Impression and Recommendations'):
            text = self.colon_report(heading)
            with self.subTest(heading=heading):
                self.assertEqual(family(text, 'gi.eus'), 'planned')
                proposals, _ = run_engine(text, [('45378', 'The colonoscope was advanced to the cecum.'),
                                                 ('43259', 'EUS for evaluation of the pancreatic cyst seen on CT.')])
                self.assertEqual(proposals['43259'].bucket, 'excluded')
                self.assertEqual(proposals['45378'].bucket, 'selected')

    def test_case_b_previous_procedures_are_historical(self):
        for heading in ('Previous procedures:', 'Past procedures:', 'Procedural history:', 'Prior colonoscopies:',
                        'Previous colonoscopies:', 'Prior endoscopies:', 'Previous procedures'):
            text = self.egd_report(heading)
            with self.subTest(heading=heading):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'historical')
                self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'extent'))
                proposals, _ = run_engine(text, [('45385', 'a 10 mm polyp was removed with cold snare.')])
                self.assertEqual(proposals['45385'].bucket, 'excluded')
                self.assertEqual(family(text, 'gi.egd'), 'performed')

    def test_an_unknown_label_line_opens_a_section_with_no_positive_default(self):
        for heading, kind in (('Comments:', 'other'), ('Next procedures:', 'plan'), ('Earlier endoscopic work-up:', 'history'),
                              ('Recommended follow-up:', 'plan'), ('Surgical and endoscopic history:', 'history')):
            text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\n'
                    + heading + '\nEUS of the pancreatic cyst.\n')
            with self.subTest(heading=heading):
                start = text.index('EUS of')
                self.assertEqual(layout(text).section_at(start).kind, kind)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')

    def test_key_value_lines_stay_content(self):
        text = HEADER + 'Procedure: Colonoscopy\nExtent: cecum\nFindings: The colonoscope was advanced to the cecum.\n'
        self.assertEqual([s.kind for s in layout(text).sections], ['other', 'procedure', 'findings'])
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')


class Status7NegatedAdvancementTests(unittest.TestCase):
    """status:7 — "was not advanced to the cecum" never yields the cecum as the extent."""

    TEXT = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the splenic flexure only; it '
            'was not advanced to the cecum because of poor preparation.\n')

    def test_the_claimed_input_is_incomplete_at_the_splenic_flexure(self):
        result = route(self.TEXT)
        colon = result.finding('gi.colonoscopy')
        self.assertEqual(colon.status, 'incomplete')
        extent = next(f for f in colon.facts if f.name == 'extent')
        self.assertEqual(extent.value, 'incomplete: splenic flexure')
        # the denied advancement is read as the landmark not reached, and kept as evidence
        self.assertIn('it was not advanced to the cecum because of poor preparation.', [e.text for e in extent.evidence])
        proposals, _ = run_engine(self.TEXT, [('45378', 'The colonoscope was advanced to the splenic flexure only')])
        proposal = proposals['45378']
        self.assertEqual(proposal.bucket, 'selected')
        self.assertIn('service.incomplete', [c.id for c in proposal.checks])
        self.assertTrue(proposal.modifier_considerations)

    def test_negated_advancement_wordings(self):
        for body, slug, landmark in (
                ('The colonoscope was not advanced to the cecum.', 'gi.colonoscopy', 'cecum'),
                ('The colonoscope was never advanced to the cecum.', 'gi.colonoscopy', 'cecum'),
                ('The colonoscope was not able to be advanced to the cecum because of looping.', 'gi.colonoscopy', 'cecum'),
                ('Despite abdominal pressure, the colonoscope was not advanced to the cecum.', 'gi.colonoscopy', 'cecum'),
                ('The colonoscope was advanced to the hepatic flexure; it was never advanced to the cecum.',
                 'gi.colonoscopy', 'cecum'),
                ('The colonoscope did not reach the cecum.', 'gi.colonoscopy', 'cecum'),
                ('The endoscope was not advanced to the duodenum.', 'gi.egd', 'duodenum')):
            procedure = 'Colonoscopy' if slug == 'gi.colonoscopy' else 'EGD'
            text = HEADER + f'Procedure: {procedure}\nFindings: ' + body + '\n'
            with self.subTest(body=body):
                self.assertNotEqual(fact_value(text, slug, 'extent'), landmark)
                self.assertNotEqual(family(text, slug), 'performed')

    def test_reached_landmarks_still_count(self):
        for body, value in (('The colonoscope was advanced to the cecum without difficulty.', 'cecum'),
                            ('Without difficulty, the colonoscope was advanced to the cecum.', 'cecum'),
                            ('The colonoscope was advanced to the cecum and no polyps were seen.', 'cecum'),
                            ('The colonoscope could not be advanced beyond the splenic flexure.',
                             'incomplete: splenic flexure')):
            text = HEADER + 'Procedure: Colonoscopy\nFindings: ' + body + '\n'
            with self.subTest(body=body):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), value)


class Status8AbortedTests(unittest.TestCase):
    """status:8 — a started procedure that was aborted is incomplete and kept for review, never excluded."""

    def text(self, procedure, body):
        return HEADER + f'Procedure: {procedure}\nFindings: ' + body + '\n'

    def test_the_claimed_egd_is_incomplete_and_kept(self):
        body = 'EGD was aborted after the scope reached the gastric antrum because of oxygen desaturation.'
        text = self.text('EGD', body)
        self.assertEqual(family(text, 'gi.egd'), 'incomplete')
        self.assertEqual(read(text, body)[0], 'incomplete')
        proposals, _ = run_engine(text, [('43235', body)])
        self.assertEqual(proposals['43235'].bucket, 'selected')
        self.assertIn('service.incomplete', [c.id for c in proposals['43235'].checks])

    def test_started_aborts_are_incomplete(self):
        for procedure, slug, body in (
                ('Colonoscopy', 'gi.colonoscopy', 'Colonoscopy was aborted at the splenic flexure due to poor bowel preparation.'),
                ('Colonoscopy', 'gi.colonoscopy', 'The colonoscopy was aborted at 40 cm because of patient discomfort.'),
                ('Colonoscopy', 'gi.colonoscopy', 'The procedure was aborted at the splenic flexure due to poor bowel preparation.'),
                ('Colonoscopy', 'gi.colonoscopy', 'Colonoscopy was aborted because the scope could not be advanced beyond '
                                                  'the splenic flexure.'),
                ('Colonoscopy', 'gi.colonoscopy', 'Colonoscopy aborted at the hepatic flexure due to looping.'),
                ('EGD', 'gi.egd', 'EGD aborted in the esophagus due to patient agitation.'),
                ('Colonoscopy', 'gi.colonoscopy', 'Colonoscopy was aborted after the scope was advanced to the sigmoid colon.')):
            text = self.text(procedure, body)
            with self.subTest(body=body):
                self.assertEqual(family(text, slug), 'incomplete')
                self.assertEqual(read(text, body)[0], 'incomplete')

    def test_an_abort_after_documented_advancement_in_the_previous_sentence(self):
        text = (HEADER + 'Procedure: Colonoscopy\nTechnique: The colonoscope was advanced to the splenic flexure. '
                'The colonoscopy was aborted because of poor bowel preparation.\n')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')
        proposals, _ = run_engine(text, [('45378', 'The colonoscopy was aborted because of poor bowel preparation.')])
        self.assertEqual(proposals['45378'].bucket, 'selected')

    def test_an_abort_with_no_start_information_is_held_never_excluded(self):
        body = 'The colonoscopy was aborted.'
        text = self.text('Colonoscopy', body)
        self.assertNotIn(family(text, 'gi.colonoscopy'), ('performed', 'cancelled'))
        status, cues = read(text, body)
        self.assertIn(status, ('uncertain', 'incomplete'))
        proposals, _ = run_engine(text, [('45378', body)])
        self.assertEqual(proposals['45378'].bucket, 'selected')
        self.assertNotEqual(proposals['45378'].status, 'ready')

    def test_an_abort_before_the_start_stays_cancelled(self):
        for body in ('Colonoscopy was aborted before sedation because of hypertension.',
                     'The colonoscopy was aborted before insertion of the colonoscope.'):
            with self.subTest(body=body):
                self.assertEqual(family(self.text('Colonoscopy', body), 'gi.colonoscopy'), 'cancelled')


class Status9UpperExtentTests(unittest.TestCase):
    """status:9 — an EGD whose documented extent stops short of the duodenum is incomplete."""

    def text(self, body, procedure='EGD'):
        return HEADER + f'Procedure: {procedure}\nFindings: ' + body + '\n'

    def test_the_claimed_esophageal_stop(self):
        text = self.text('The endoscope was advanced to the distal esophagus, where a tight malignant-appearing '
                         'stricture prevented further passage of the endoscope. Biopsies were taken from the stricture.')
        self.assertEqual(family(text, 'gi.egd'), 'incomplete')
        self.assertEqual(fact_value(text, 'gi.egd', 'extent'), 'incomplete: esophagus')
        proposals, _ = run_engine(text, [('43239', 'Biopsies were taken from the stricture.')])
        self.assertEqual(proposals['43239'].bucket, 'selected')
        self.assertIn('service.incomplete', [c.id for c in proposals['43239'].checks])

    def test_stops_short_of_the_duodenum(self):
        for body, value in (
                ('The endoscope was advanced to the stomach; the duodenum was not entered because of a pyloric '
                 'stricture.', 'incomplete: stomach'),
                ('The endoscope was advanced to the stomach. The duodenum could not be examined because of gastric '
                 'outlet obstruction.', 'incomplete: stomach'),
                ('The endoscope was advanced to the antrum. Pyloric stenosis prevented entry into the duodenum.',
                 'incomplete: stomach'),
                ('The endoscope was advanced to the mid esophagus. The examination was limited to the esophagus '
                 'because of an impassable stricture.', 'incomplete: esophagus')):
            text = self.text(body + ' Biopsies were taken.')
            with self.subTest(body=body):
                self.assertEqual(family(text, 'gi.egd'), 'incomplete')
                self.assertEqual(fact_value(text, 'gi.egd', 'extent'), value)

    def test_prevented_passage_is_incomplete_where_no_extent_says_so(self):
        text = (HEADER + 'Procedure: ERCP\nFindings: A duodenal stricture prevented passage of the duodenoscope to the '
                'papilla.\n')
        self.assertEqual(family(text, 'gi.ercp'), 'incomplete')

    def test_complete_egd_and_esophagoscopy_controls(self):
        text = self.text('The endoscope was advanced to the second part of the duodenum. Biopsies were taken from '
                         'the gastric antrum.')
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        self.assertEqual(fact_value(text, 'gi.egd', 'extent'), 'second part of duodenum')
        text = self.text('The endoscope was advanced to the duodenal bulb. Biopsies were taken.')
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        text = self.text('The endoscope was advanced to the distal esophagus. Biopsies were taken.',
                         procedure='Esophagoscopy')
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        self.assertEqual(fact_value(text, 'gi.egd', 'extent'), 'esophagus')


class Status11SeparateEmTests(unittest.TestCase):
    """status:11 — only an explicit, affirmative, non-negated, non-interrogative statement counts."""

    BASE = (HEADER + 'Place of service: 11\nEstablished patient office visit for intermittent rectal bleeding.\n'
            'Medical decision making: moderate.\nTotal time spent: 30 minutes.\nProcedure: Flexible sigmoidoscopy.\n'
            'The sigmoidoscope was advanced to 35 cm.\nA cold forceps biopsy of the rectum was taken.\n')

    def separate_em(self, extra):
        result = route(self.BASE + extra + '\n')
        return next((f for f in result.finding('gi.office_em').facts if f.name == 'separate_em'), None)

    def test_negated_after_and_interrogative_statements_are_not_documented(self):
        for extra in ('Attestation: A significant, separately identifiable E/M service was not provided.',
                      'Attestation: A significant, separately identifiable E/M service was not performed.',
                      'A significant, separately identifiable E/M service was not provided on this date.',
                      'Q: Was a significant, separately identifiable evaluation and management service performed on the '
                      'date of service, beyond the usual pre-procedure assessment? A: No.',
                      '\nADDENDUM (revision 2, added 2026-10-22 09:00 UTC)\nA significant, separately identifiable E/M '
                      'service was not performed on the date of service.',
                      'Significant, separately identifiable E/M service performed: No',
                      'Separately identifiable E/M: none.',
                      'Separately identifiable E/M service - not applicable.',
                      'Is a significant, separately identifiable E/M documented? No.',
                      'Modifier 25 not appended because the E/M was not significant and separately identifiable.',
                      'No significant, separately identifiable E/M service was performed.',
                      'A significant, separately identifiable E/M service may have been provided.'):
            with self.subTest(extra=extra):
                self.assertIsNone(self.separate_em(extra))

    def test_the_e_m_stays_held_for_the_negated_statements(self):
        for extra in ('Attestation: A significant, separately identifiable E/M service was not provided.',
                      'Q: Was a significant, separately identifiable evaluation and management service performed on the '
                      'date of service, beyond the usual pre-procedure assessment? A: No.'):
            text = self.BASE + extra + '\n'
            with self.subTest(extra=extra):
                proposals, _ = run_engine(text, [('99214', 'Established patient office visit for intermittent rectal '
                                                            'bleeding.'),
                                                 ('45331', 'A cold forceps biopsy of the rectum was taken.')])
                self.assertEqual(proposals['99214'].status, 'needs_clarification')
                self.assertIn('separate_em', [c.fact for c in proposals['99214'].clarifications])

    def test_an_affirmative_statement_is_documented_with_its_whole_sentence(self):
        statement = 'Attestation: A significant, separately identifiable E/M service was performed.'
        fact = self.separate_em(statement)
        self.assertIsNotNone(fact)
        self.assertEqual(fact.value, 'documented')
        self.assertIn('separately identifiable E/M service was performed.', fact.evidence[0].text)


class Status12ComplicationNegationTests(unittest.TestCase):
    """status:12 — "No <service> complications" negates the complications, not the service."""

    TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
            'Place of service: office (POS 11)\nEstablished patient office visit.\nProcedure: Flexible sigmoidoscopy\n'
            'Findings: The sigmoidoscope was advanced to 40 cm. A biopsy was taken from the rectum.\n'
            'Complications: No flexible sigmoidoscopy complications.\nMedical decision making: moderate.\n'
            'Total time: 30 minutes.\n')

    def test_the_claimed_input(self):
        self.assertEqual(span(self.TEXT, 'Established patient office visit.'), (106, 139))
        self.assertEqual(family(self.TEXT, 'gi.flex_sig'), 'performed')
        proposals, _ = run_engine(self.TEXT, [('99214', 'Established patient office visit.'),
                                              ('45331', 'A biopsy was taken from the rectum.')])
        self.assertEqual(proposals['45331'].status, 'ready')
        self.assertEqual(proposals['99214'].status, 'needs_clarification')
        self.assertIn('em.same_day_procedure', [c.id for c in proposals['99214'].checks])

    def test_complication_wordings_keep_the_service_performed(self):
        for procedure, slug, evidence, line in (
                ('Colonoscopy', 'gi.colonoscopy', 'The colonoscope was advanced to the cecum.', 'No colonoscopy complications.'),
                ('EGD', 'gi.egd', 'The gastroscope was advanced to the second part of the duodenum.',
                 'No EGD-related complications.'),
                ('Colonoscopy', 'gi.colonoscopy', 'The colonoscope was advanced to the cecum.',
                 'There were no immediate colonoscopy-related complications.'),
                ('EGD', 'gi.egd', 'The gastroscope was advanced to the second part of the duodenum.',
                 'No complications of the EGD.')):
            text = (HEADER + f'Procedure: {procedure}\nFindings: {evidence}\nComplications: {line}\n')
            with self.subTest(line=line):
                self.assertEqual(family(text, slug), 'performed')
                self.assertEqual(read(text, evidence)[0], 'performed')

    def test_a_real_negation_of_the_service_still_negates(self):
        text = HEADER + 'Procedure: Colonoscopy\nNo colonoscopy was performed; the patient left before sedation.\n'
        self.assertEqual(family(text, 'gi.colonoscopy'), 'negated')


class Status14FactsFromNegatedTextTests(unittest.TestCase):
    """status:14 — facts come only from clauses read as performed for this encounter."""

    def test_case_a_colonoscopy_facts(self):
        text = (HEADER + 'Indication: Hematochezia.\nProcedure: Colonoscopy\nFindings: The colonoscope was advanced to the '
                'cecum. No polyps were found in this patient with a history of polyps.\nBiopsies: none.\nTattoo: no.\n'
                'Clips: none.\nPlan: Screening colonoscopy in 10 years.\n')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'interventions'))
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'polyp_count'))
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'intent'))
        proposals, _ = run_engine(text, [('45378', 'The colonoscope was advanced to the cecum.')])
        self.assertNotIn('biopsy', proposals['45378'].rationale)
        self.assertNotIn('screening', proposals['45378'].rationale)

    def test_case_b_eus_target_and_sampling_from_today_only(self):
        text = (HEADER + 'Indication: Prior EUS of a pancreatic cyst in 2023. Now jaundice.\nProcedure: EUS\n'
                'Findings: The echoendoscope was advanced to the duodenum. The common bile duct was dilated to 12 mm. '
                'FNA: not performed.\n')
        self.assertIsNone(fact_value(text, 'gi.eus', 'target'))
        self.assertNotIn(fact_value(text, 'gi.eus', 'tissue_sampling'), ('FNA', 'FNB'))
        control = (HEADER + 'Indication: EUS for evaluation of a pancreatic cyst.\nProcedure: EUS\n'
                   'Findings: The echoendoscope was advanced to the duodenum.\n')
        self.assertEqual(fact_value(control, 'gi.eus', 'target'), 'pancreatic cyst')

    def test_case_c_negated_interventions(self):
        text = (HEADER + 'Indication: Dyspepsia.\nProcedure: EGD\nFindings: The gastroscope was advanced to the second '
                'part of the duodenum. The mucosa was normal. No gastric biopsies were taken.\n')
        self.assertIsNone(fact_value(text, 'gi.egd', 'interventions'))
        self.assertIsNone(fact_value(text, 'gi.egd', 'location'))
        text = (HEADER + 'Indication: Choledocholithiasis.\nProcedure: ERCP\nFindings: The duodenoscope was advanced to '
                'the papilla. Deep biliary cannulation was achieved. No plastic stent was placed.\n')
        self.assertIsNone(fact_value(text, 'gi.ercp', 'interventions'))

    def test_negated_intent_and_polyp_count(self):
        text = (HEADER + 'Indication: Hematochezia. This is not a screening colonoscopy.\nProcedure: Colonoscopy\n'
                'Findings: The colonoscope was advanced to the cecum. There was not a single polyp.\n')
        self.assertNotEqual(fact_value(text, 'gi.colonoscopy', 'intent'), 'screening')
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'polyp_count'))
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_performed_facts_still_read(self):
        text = (HEADER + 'Indication: Screening colonoscopy, average risk.\nProcedure: Colonoscopy\nFindings: The '
                'colonoscope was advanced to the cecum. Two polyps were removed with a cold snare. Biopsies were taken '
                'from the rectum.\nPlan: Surveillance colonoscopy in 5 years.\n')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'intent'), 'screening')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'polyp_count'), '2')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'interventions'), 'biopsy; cold snare')


class StructuralFailClosedTests(unittest.TestCase):
    """The rules behind the repairs, pinned on wordings no vocabulary above lists: a section
    default needs a procedure description after the service name, a bare service line is
    qualified by the next line, and an unresolved negation word withholds "performed"."""

    def status(self, heading, body, slug):
        return family(HEADER + heading + '\n' + body + '\n', slug)

    def test_a_section_default_needs_a_procedure_description(self):
        for line in ('Colonoscopy - TBD.', 'Colonoscopy omitted.', 'Colonoscopy requested.', 'Colonoscopy on hold.',
                     'Colonoscopy deemed unnecessary.', 'Colonoscopy contraindicated.', 'Colonoscopy to follow.',
                     'Colonoscopy, however, was not.', 'Colonoscopy was felt to be unnecessary.'):
            with self.subTest(line=line):
                self.assertIn(self.status('Procedure:', line, 'gi.colonoscopy'), NOT_PERFORMED)
                text = HEADER + 'Procedure:\n' + line + '\n'
                status, cues = read(text, 'Colonoscopy')
                self.assertEqual(status, 'uncertain')
                self.assertFalse(cues[0].startswith(SILENT), cues)

    def test_procedure_descriptions_and_findings_lines_still_read_performed(self):
        for heading, line, slug in (
                ('Procedure:', 'Colonoscopy with cold snare polypectomy and cold forceps biopsy.', 'gi.colonoscopy'),
                ('Procedure:', 'Esophagogastroduodenoscopy (EGD) with cold forceps biopsy.', 'gi.egd'),
                ('Procedure:', 'Upper endoscopic ultrasound (EUS) with EUS-guided fine-needle biopsy (FNB) of a '
                               'pancreatic head mass.', 'gi.eus'),
                ('Procedure:', 'Diagnostic colonoscopy to the terminal ileum with random cold forceps biopsies.',
                 'gi.colonoscopy'),
                ('Procedure:', 'Colonoscopy performed.', 'gi.colonoscopy'),
                ('Procedure:', 'Colonoscopy procedure report', 'gi.colonoscopy'),
                ('Findings:', 'Colonoscopy - two diminutive polyps, cold snare; otherwise normal.', 'gi.colonoscopy'),
                ('Findings:', 'EGD - normal esophagus; gastric erythema, biopsied.', 'gi.egd'),
                ('Findings:', 'The EGD showed no esophagitis and no ulcers.', 'gi.egd'),
                ('Findings:', 'The EGD was normal.', 'gi.egd')):
            with self.subTest(line=line):
                self.assertEqual(self.status(heading, line, slug), 'performed')

    def test_the_next_line_speaks_for_a_bare_service_line(self):
        for lines in ('Colonoscopy\nNot performed.', 'Colonoscopy\nStatus: cancelled', 'Colonoscopy\nDeclined.'):
            with self.subTest(lines=lines):
                self.assertIn(self.status('Procedures performed:', lines, 'gi.colonoscopy'), NOT_PERFORMED)
        for lines in ('Colonoscopy\nNo polyps were found.', 'Colonoscopy\nThe colonoscope was advanced to the cecum.'):
            with self.subTest(lines=lines):
                self.assertEqual(self.status('Procedure:', lines, 'gi.colonoscopy'), 'performed')

    def test_a_next_sentence_that_refers_back_can_deny_the_service(self):
        for lines in ('Colonoscopy with biopsy.\nThis was later cancelled.', 'Colonoscopy with biopsy.\nIt was not performed.',
                      'Colonoscopy\nIt was not performed.', 'Colonoscopy with biopsy.\nThe procedure was not done.'):
            with self.subTest(lines=lines):
                self.assertIn(self.status('Procedure:', lines, 'gi.colonoscopy'), NOT_PERFORMED)
        for lines, expected in (('Colonoscopy with biopsy.\nIt was uneventful.', 'performed'),
                                ('Colonoscopy with biopsy.\nIt will be repeated in 5 years.', 'performed'),
                                ('Colonoscopy with biopsy.\nIt was performed without complication.', 'performed'),
                                ('Colonoscopy with biopsy.\nIt was not difficult.', 'performed'),
                                ('Colonoscopy with biopsy.\nIt was aborted at the splenic flexure.', 'incomplete')):
            with self.subTest(lines=lines):
                self.assertEqual(self.status('Procedure:', lines, 'gi.colonoscopy'), expected)

    def test_an_unresolved_negation_withholds_performed(self):
        self.assertIn(self.status('Procedure:', 'Colonoscopy, not today.', 'gi.colonoscopy'), NOT_PERFORMED)
        self.assertIn(self.status('Findings:', 'Colonoscopy was performed by the fellow, not today.', 'gi.colonoscopy'),
                      NOT_PERFORMED)
        text = HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. No polyps were seen.\n'
        status, cues = read(text, 'No polyps were seen.')  # quoted alone, the denial is what the passage says
        self.assertEqual(status, 'uncertain')
        self.assertTrue(cues[0].startswith('uncertain: unresolved negation'), cues)
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')

    def test_a_denied_finding_or_other_act_is_incidental(self):
        for heading, line in (('Procedure:', 'Colonoscopy, no sedation.'), ('Procedure:', 'Colonoscopy, no polypectomy.'),
                              ('Procedure:', 'Colonoscopy without retroflexion.'),
                              ('Procedure:', 'Colonoscopy was performed and no sedation was given.'),
                              ('Procedure:', 'Colonoscopy was performed after the patient declined sedation.'),
                              ('Procedure:', 'Colonoscopy was not difficult.'),
                              ('Findings:', 'During the EGD, no bleeding was seen.')):
            slug = 'gi.egd' if 'EGD' in line else 'gi.colonoscopy'
            with self.subTest(line=line):
                self.assertEqual(self.status(heading, line, slug), 'performed')
        text = HEADER + 'Procedure: Colonoscopy\nFindings: Biopsies were taken from the rectum, where no ulcers were seen.\n'
        self.assertEqual(read(text, 'Biopsies were taken from the rectum, where no ulcers were seen.')[0], 'performed')

    def test_not_completed_is_incomplete_not_negated(self):
        for line in ('Colonoscopy not completed.', 'Colonoscopy was not completed.', 'Colonoscopy: not completed.'):
            with self.subTest(line=line):
                self.assertEqual(self.status('Procedure: Colonoscopy\nFindings:', line, 'gi.colonoscopy'), 'incomplete')


class SilentCueContractTests(unittest.TestCase):
    """Validation tells a silent span from a hedged one by its cues: every cue of a silent
    reading starts with SILENT, and no reading that saw a negation, plan, history, hedge or
    question token carries that prefix."""

    def test_the_silent_default_is_unchanged(self):
        text = HEADER + 'Assessment\nColonoscopy.\n'
        self.assertEqual(read(text, 'Colonoscopy'), ('uncertain', ('uncertain: no performance evidence in its sentence '
                                                                  'or section',)))

    def test_no_hedged_reading_uses_the_silent_prefix(self):
        for heading, line, phrase in (('Procedure:', 'Colonoscopy - TBD.', 'Colonoscopy'),
                                      ('Findings:', 'No polyps were seen.', 'No polyps were seen.'),
                                      ('Findings:', 'Colonoscopy was aborted.', 'Colonoscopy was aborted.'),
                                      ('Procedure:', 'ERCP pending insurance approval.', 'ERCP'),
                                      ('Assessment', 'Colonoscopy?', 'Colonoscopy'),
                                      ('Procedures performed:', 'Colonoscopy\nNot performed.', 'Colonoscopy')):
            text = HEADER + heading + '\n' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, phrase)
                self.assertNotEqual(status, 'performed')
                self.assertFalse(any(c.startswith(SILENT) for c in cues), cues)


if __name__ == '__main__':
    unittest.main()
