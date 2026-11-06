"""Completion repair (owner directive 2026-11-06; HARNESS.md "Completion repair (2026-11-06)"), builder R2: an
examination's own outcome against a sub-act's, the instrument's own course, one extent fact.

- U3: a clause's incompleteness is the examination's own only when its grammatical subject is the examination (the
  service or its anaphor, the scope, the reach or entry, a landmark or an obstruction); a sub-act's or an accessory's
  failure ("the polypectomy was unsuccessful", "The snare could not be passed around the polyp") never makes the
  examination incomplete, never rewrites its extent and never lists the failed act's intervention as done. The subject
  is read by the shared primitive studio.gi.clauses (subject, subject_head, failure_of).
- U4: the instrument's own course in a positive section is a mention of its family (detect._instrument_mentions),
  performed by its own predicate and the section, under the conditions I1-I8; every other shape keeps the base reading.
- U12: routing reads the reach statements the documented-service reader reads (services.COMPLETE_POS), so one extent
  serves routing, the documented-service reader and the admission; a required extent no reader found is worded as the
  readers' finding ("CPT Studio could not find how far the examination reached"), never as a document fact.

Real readers and engine, no provider or database calls, synthetic documents only."""
import re
import time

from django.test import SimpleTestCase

from studio.gi import clauses, detect, sections
from studio.gi import context as gi_context
from studio.gi import services as gi_services
from studio.validation import checks
from tests.test_harness_engine import DAY, corti, run, span

QUIET = ('pass', 'not_applicable', 'not_verified', 'info')
HEAD = 'Date of service: 2026-10-14\nEndoscopist: Test Endoscopist, MD\nSedation: monitored anesthesia care\n'
COLD = 'A 6 mm polyp in the ascending colon was removed with a cold snare and retrieved.'
BIOPSIES = 'Cold forceps biopsies were obtained from the gastric antrum.'


def colon(*lines, title='Colonoscopy Report', procedure='Procedure: Colonoscopy. The colonoscope was advanced to the '
          'cecum.'):
    return f'{title}\n{HEAD}Indication: Chronic diarrhea.\n{procedure} ' + ' '.join(lines) + '\n'


def egd(*lines, title='EGD Report'):
    return (f'{title}\n{HEAD}Indication: Dysphagia.\nProcedure: EGD. The gastroscope was advanced to the second portion '
            f'of the duodenum. {BIOPSIES} ' + ' '.join(lines) + '\n')


def finding(text, family):
    return detect.route(text, DAY).finding(family)


def facts(text, family):
    found = finding(text, family)
    return {f.name: f.value for f in found.facts} if found else {}


def proposal(text, value, quote):
    result = run(text, corti((value, span(text, quote))))
    return next(p for p in result.proposals if p.code == value)


def instrument_mentions(text, family):
    found = finding(text, family)
    return [m for m in (found.mentions if found else ()) if m.cues[:1] == (detect.INSTRUMENT_COURSE,)]


def dated_today(text):
    """Whether the context reader reads the test's day as the document's date of service (an aside such as "(prior)"
    or "(planned)" moves the date channel, which the engine harness then refuses)."""
    return str(gi_context.extract_context(text)['service_date'].value) == DAY.isoformat()


def flagged(p):
    return sorted(c.id for c in p.checks if c.status not in QUIET)


def classify(sentence, predicate):
    """failure_of for the predicate matched by ``predicate`` in ``sentence``, its antecedent the clause before it."""
    m = re.search(predicate, sentence)
    lay = sections.layout(sentence)
    clause = next(c for c in lay.clauses if c[0] <= m.start() < c[1])
    prior = [c for c in lay.clauses if c[1] <= clause[0]]
    start = clauses.predicate_start(sentence, clause[0], m.start())
    found = clauses.subject(sentence, clause[0], start, prior[-1] if prior else None)
    return clauses.failure_of(sentence, found), found


SUB_ACT_FAILURES = (
    ('Hot snare polypectomy of a 14 mm polyp in the sigmoid colon was attempted, but the polypectomy was unsuccessful '
     'because of poor positioning; the polyp was left in place.', r'was unsuccessful'),
    ('Biopsy attempts were unsuccessful.', r'were unsuccessful'),
    ('Clip placement was unsuccessful.', r'was unsuccessful'),
    ('The snare could not be passed around the polyp.', r'could not'),
    ('Balloon dilation of a distal esophageal stricture was attempted, but the dilation was unsuccessful because of '
     'poor positioning.', r'was unsuccessful'),
    ('Argon plasma coagulation was unsuccessful.', r'was unsuccessful'),
    ('The polypectomy was attempted but it was unsuccessful.', r'was unsuccessful'),
    ('The polypectomy, which was attempted twice, was unsuccessful.', r'was unsuccessful'),
    ('The snare that was used could not be passed around the polyp.', r'could not'),
    ('During the colonoscopy, the polypectomy was unsuccessful.', r'was unsuccessful'),
    ('Polypectomy was attempted; the attempt was unsuccessful.', r'was unsuccessful'),
    ('Passage of the snare around the polyp was unsuccessful.', r'was unsuccessful'),
    ('Two of the clips could not be passed.', r'could not'),
    ('Repeated biopsy attempts were unsuccessful.', r'were unsuccessful'),
    ('The polypectomy was terminated because of bleeding.', r'terminated'),
    ('Polypectomy was aborted because of bleeding.', r'aborted'),
)
EXAMINATION_FAILURES = (
    ('Cecal intubation was unsuccessful.', r'was unsuccessful'),
    ('The cecum could not be reached because of poor preparation.', r'could not'),
    ('The scope could not be advanced beyond the stricture.', r'could not'),
    ('Attempts at cecal intubation were unsuccessful.', r'were unsuccessful'),
    ('Cannulation was unsuccessful.', r'was unsuccessful'),
    ('The procedure was unsuccessful.', r'was unsuccessful'),
    ('The colonoscope was advanced to the hepatic flexure but it could not be advanced further.', r'could not'),
    ('The colonoscope was advanced to the transverse colon and could not be advanced further.', r'could not'),
    ('The colonoscopy was unsuccessful.', r'was unsuccessful'),
    ('The stricture could not be traversed.', r'could not'),
    ('Passage of the colonoscope through the stricture was unsuccessful.', r'was unsuccessful'),
    ('Biliary cannulation was unsuccessful.', r'was unsuccessful'),
    ('The papilla could not be cannulated.', r'could not'),
    ('The procedure was terminated because of patient discomfort.', r'terminated'),
)
# Whose failure cannot be told: the base reading (incomplete) stands.
UNREAD = (
    ('We could not pass the snare around the polyp.', r'could not'),  # a person: the object failed, not read
    ('Colonoscopy with polypectomy, which was unsuccessful, was stopped.', r'was unsuccessful'),  # ambiguous attachment
    ('The attempt was unsuccessful.', r'was unsuccessful'),  # no antecedent in its sentence
    ('Multiple attempts were unsuccessful.', r'were unsuccessful'),
    ('The sigmoid polyp could not be reached.', r'could not'),  # a lesion: neither class
    ('In the sigmoid colon polypectomy was unsuccessful.', r'was unsuccessful'),  # a fronted phrase holds the subject
    ('The endoscopist was unable to advance the colonoscope.', r'unable'),
)


class SubjectPrimitiveTests(SimpleTestCase):
    """studio.gi.clauses: the subject of a predicate, read structurally, and whose failure it states."""

    def test_sub_act_and_accessory_failures(self):
        for sentence, predicate in SUB_ACT_FAILURES:
            with self.subTest(sentence):
                self.assertEqual(classify(sentence, predicate)[0], clauses.SUB_ACT)

    def test_examination_failures(self):
        for sentence, predicate in EXAMINATION_FAILURES:
            with self.subTest(sentence):
                self.assertEqual(classify(sentence, predicate)[0], clauses.EXAMINATION)

    def test_an_unread_subject_is_no_answer(self):
        for sentence, predicate in UNREAD:
            with self.subTest(sentence):
                self.assertIsNone(classify(sentence, predicate)[0])

    def test_partitive_and_attempt_heads_resolve_to_their_complement(self):
        for text, predicate, head, resolved in (
                ('Fragments of the bolus were removed with a net.', r'were removed', 'fragments', 'bolus'),
                ('Attempts at cecal intubation were unsuccessful.', r'were unsuccessful', 'attempts', 'intubation'),
                ('Biopsy attempts were unsuccessful.', r'were unsuccessful', 'attempts', 'biopsy'),
                ('Two of the clips could not be passed.', r'could not', 'two', 'clips'),
                ('Hot snare polypectomy of a 14 mm polyp in the sigmoid colon was attempted.', r'was attempted',
                 'polypectomy', 'polypectomy')):
            with self.subTest(text):
                pos = re.search(predicate, text).start()
                found = clauses.subject(text, 0, pos)
                self.assertEqual((found.head.word, found.resolved.word), (head, resolved))
                self.assertEqual(clauses.subject_head(text, 0, pos)[2], resolved)
                start, end, word = clauses.subject_head(text, 0, pos)
                self.assertEqual(text[start:end].lower(), word)

    def test_a_pronoun_resolves_only_through_its_antecedent_clause(self):
        text = 'The polypectomy was attempted but it was unsuccessful.'
        pos = text.index('was unsuccessful')
        clause = text.index('but')
        self.assertTrue(clauses.subject(text, clause, pos).pronoun)
        self.assertEqual(clauses.subject_head(text, clause, pos, (0, clause))[2], 'polypectomy')
        # a person as the antecedent never resolves it
        text = 'We attempted it but it was unsuccessful.'
        clause = text.index('but')
        self.assertTrue(clauses.subject(text, clause, text.index('was'), (0, clause)) is None
                        or clauses.subject(text, clause, text.index('was'), (0, clause)).pronoun)

    def test_the_subject_window_is_bounded(self):
        # a subject reaching past SUBJECT_REACH is not read (fail-closed), and the work per predicate is bounded
        text = 'The ' + 'very ' * 200 + 'snare could not be passed.'
        self.assertIsNone(clauses.subject(text, 0, text.index('could')))
        start = time.perf_counter()
        long_clause = ('polyp ' * 100000) + 'was unsuccessful'
        clauses.subject(long_clause, 0, long_clause.index('was unsuccessful'))
        self.assertLess(time.perf_counter() - start, 0.5)


class SubActFailureRoutingTests(SimpleTestCase):
    """U3: a sub-act's failure is that act's own; the examination keeps its own reading."""

    def test_a_failed_sub_act_leaves_a_complete_colonoscopy_performed(self):
        for line in ('Hot snare polypectomy of a 14 mm polyp in the sigmoid colon was attempted, but the polypectomy was '
                     'unsuccessful because of poor positioning; the polyp was left in place.',
                     'Biopsy attempts were unsuccessful.', 'Clip placement was unsuccessful.',
                     'The snare could not be passed around the polyp.', 'Argon plasma coagulation was unsuccessful.',
                     'The polypectomy was attempted but it was unsuccessful.'):
            for title, procedure in (('Colonoscopy Report', 'Procedure: Colonoscopy. The colonoscope was advanced to '
                                      'the cecum.'),
                                     ('Endoscopy Report', 'Procedure: Colonoscopy. The colonoscope was advanced to the '
                                      'cecum.'),
                                     ('Colonoscopy Report', 'Procedure: The colonoscope was advanced to the cecum.')):
                text = colon(COLD, line, title=title, procedure=procedure)
                with self.subTest(line=line, title=title, procedure=procedure):
                    found = finding(text, 'gi.colonoscopy')
                    self.assertEqual(found.status, 'performed')
                    self.assertEqual(facts(text, 'gi.colonoscopy')['extent'], 'cecum')
                    self.assertFalse([m for m in found.mentions if m.status == 'incomplete'])
                    p = proposal(text, '45385', COLD)
                    self.assertEqual((p.bucket, p.status), ('selected', 'ready'))
                    self.assertNotIn('service.incomplete', flagged(p))
                    self.assertFalse(p.modifier_considerations)

    def test_the_same_failure_on_its_own_line_and_in_a_findings_paragraph(self):
        failure = 'Hot snare polypectomy was attempted, but the polypectomy was unsuccessful.'
        for text in (colon(COLD) + failure + '\n',
                     colon(COLD, procedure='Procedure: Colonoscopy.\nFindings: The colonoscope was advanced to the '
                           'cecum.') + 'Findings: ' + failure + '\n'):
            with self.subTest(text=text):
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')
                self.assertEqual(facts(text, 'gi.colonoscopy')['extent'], 'cecum')

    def test_a_named_mentions_clause_takes_no_sub_acts_failure(self):
        # clause cues: "During the colonoscopy, the polypectomy was unsuccessful." was the named mention's own
        text = colon(COLD, 'During the colonoscopy, the polypectomy was unsuccessful.')
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')
        # but the examination's own failure in its clause is still its own
        text = colon(COLD, 'The colonoscopy was unsuccessful beyond the hepatic flexure.')
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')

    def test_a_failed_dilation_never_rewrites_an_egds_extent(self):
        line = ('Balloon dilation of a distal esophageal stricture was attempted, but the dilation was unsuccessful '
                'because of poor positioning.')
        for text in (egd(line), egd(line, title='Endoscopy Report')):
            with self.subTest(text=text[:40]):
                self.assertEqual(finding(text, 'gi.egd').status, 'performed')
                self.assertEqual(facts(text, 'gi.egd')['extent'], 'second part of duodenum')
                p = proposal(text, '43239', BIOPSIES)
                self.assertEqual((p.bucket, p.status), ('selected', 'ready'))
                self.assertNotIn('service.incomplete', flagged(p))

    def test_the_failed_acts_intervention_is_not_listed(self):
        text = colon(COLD, 'Hot snare polypectomy of a 14 mm pedunculated polyp in the sigmoid colon was attempted, but '
                     'the polypectomy was unsuccessful because of poor positioning; the polyp was left in place.')
        self.assertEqual(facts(text, 'gi.colonoscopy')['interventions'], 'cold snare')
        # a hot snare done today elsewhere is still listed
        text = colon(COLD, 'Hot snare polypectomy of the 14 mm polyp was attempted, but the polypectomy was '
                     'unsuccessful.', 'A 9 mm polyp in the cecum was removed with a hot snare.')
        self.assertEqual(facts(text, 'gi.colonoscopy')['interventions'], 'cold snare; hot snare')

    def test_a_cited_failed_attempt_keeps_its_own_reading(self):
        # the failed act's own passage is not made performed: routing reads it as its clause states it, and where it is
        # the only snare act its code is held (on the Procedure line it is the services reader's promotion, U6, which
        # builder A repairs: D|RT-f1, D|ARCH-D3a)
        failure = 'Hot snare polypectomy was attempted, but the polypectomy was unsuccessful.'
        text = colon() + failure + '\n'
        status, cues = detect.status_for_span(text, text.index(failure), text.index(failure) + len(failure), DAY)
        self.assertEqual(status, 'incomplete', cues)
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')
        p = proposal(text, '45385', failure)
        self.assertNotEqual(p.status, 'ready')
        # beside a snare act done today, a 45385 citing the failed attempt is supported by that act (e888f9ce's shape)
        text = colon(COLD) + failure + '\n'
        self.assertEqual(proposal(text, '45385', failure).status, 'ready')


class ExaminationFailureRoutingTests(SimpleTestCase):
    """The examination's own failure keeps the family incomplete, its warning and its 52/53 consideration."""

    def test_an_examinations_own_failure_stays_incomplete(self):
        for line in ('The cecum could not be reached because of poor preparation.',
                     'The scope could not be advanced beyond the hepatic flexure.',
                     'Cecal intubation was unsuccessful.', 'Attempts at cecal intubation were unsuccessful.',
                     'The procedure was unsuccessful.'):
            text = colon(COLD, line, procedure='Procedure: Colonoscopy. The colonoscope was advanced to the hepatic '
                         'flexure.')
            with self.subTest(line):
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')
                p = proposal(text, '45385', COLD)
                self.assertEqual((p.bucket, p.status), ('selected', 'ready'))
                self.assertIn('service.incomplete', flagged(p))
                self.assertTrue(any('modifier 52 or 53' in c for c in p.modifier_considerations))

    def test_the_pronoun_pair(self):
        sub_act = colon(COLD, 'The polypectomy was attempted but it was unsuccessful.')
        exam = colon(COLD, procedure='Procedure: Colonoscopy. The colonoscope was advanced to the hepatic flexure but '
                     'it could not be advanced further.')
        self.assertEqual(finding(sub_act, 'gi.colonoscopy').status, 'performed')
        self.assertEqual(finding(exam, 'gi.colonoscopy').status, 'incomplete')

    def test_an_unread_subject_keeps_the_base_reading(self):
        text = colon(COLD, 'We could not pass the snare around the 14 mm polyp.')
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')

    def test_an_ercp_cannulation_failure_stays_the_examinations(self):
        text = ('ERCP Report\n' + HEAD + 'Procedure: ERCP. The duodenoscope was advanced to the second portion of the '
                'duodenum. Biliary cannulation was unsuccessful.\n')
        self.assertEqual(finding(text, 'gi.ercp').status, 'incomplete')


class InstrumentMentionTests(SimpleTestCase):
    """U4: the instrument's own course in a positive section is a mention of its family (I1-I8)."""

    NARRATIVE = 'Procedure: The colonoscope was advanced to the cecum. ' + COLD + '\n'

    def doc(self, title, narrative=None, head=HEAD):
        return f'{title}\n{head}{narrative or self.NARRATIVE}'

    def test_a_silent_or_aside_title_over_a_procedure_narrative(self):
        for title in ('Colonoscopy', 'COLONOSCOPY', 'Colonoscopy Report (fictional)', 'Colonoscopy Report (Final)',
                      'Colonoscopy Report - Final', 'Colonoscopy (synthetic)'):
            text = self.doc(title)
            with self.subTest(title):
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')
                self.assertEqual(proposal(text, '45385', COLD).status, 'ready')

    def test_an_instrument_only_narrative_under_procedure_findings_or_technique(self):
        for heading in ('Procedure:', 'Findings:', 'Technique:', 'Description of procedure:'):
            text = ('Date of service: 2026-10-14\nIndications: Dysphagia.\n' + heading + ' The gastroscope was '
                    'advanced to the second portion of the duodenum. Biopsies were obtained from the distal '
                    'esophagus.\n')
            with self.subTest(heading):
                found = finding(text, 'gi.egd')
                self.assertEqual(found.status, 'performed')
                self.assertEqual(facts(text, 'gi.egd')['extent'], 'second part of duodenum')
                p = proposal(text, '43239', 'Biopsies were obtained from the distal esophagus.')
                self.assertEqual((p.bucket, p.status), ('selected', 'ready'))

    def test_the_instrument_mention_agrees_with_status_for_span(self):
        text = self.doc('Colonoscopy')
        mention = next(m for m in finding(text, 'gi.colonoscopy').mentions if m.span.text == 'colonoscope')
        self.assertEqual(detect.status_for_span(text, mention.span.start, mention.span.end, DAY),
                         (mention.status, mention.cues))
        self.assertEqual(mention.cues[0], detect.INSTRUMENT_COURSE)

    def test_an_aside_outside_the_closed_class_keeps_the_base_reading(self):
        # L5-3's asides, here over a Procedure heading (the corpus pins them with the narrative in the head)
        for aside in ('Void', 'Preop', 'Preoperative', 'Orders', 'Possibly', 'Probably', 'Photocopy', 'Duplicate',
                      'Another Facility', 'External', 'Entered in Error', 'Two Years Ago', 'October Twelfth',
                      'Tomorrow', 'Unsigned', 'Addendum', 'Consult', 'Request', 'Copia', 'Previa', 'amended', 'draft',
                      'outside', 'planned', 'prior'):
            for title in (f'Colonoscopy Report ({aside})', f'Endoscopy Report ({aside})', f'Colonoscopy - {aside}'):
                text = self.doc(title)
                with self.subTest(title):
                    found = finding(text, 'gi.colonoscopy')
                    self.assertTrue(found is None or found.status != 'performed', found)
                    self.assertFalse(instrument_mentions(text, 'gi.colonoscopy'))
                    if dated_today(text):
                        self.assertNotEqual(proposal(text, '45385', COLD).status, 'ready')

    def test_a_head_narrative_with_no_heading_keeps_the_base_reading(self):
        text = ('Colonoscopy Report (fictional)\n' + HEAD + 'The colonoscope was advanced to the cecum and the '
                'examination was completed.\n' + COLD + '\n')
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'uncertain')

    def test_an_attached_outside_or_other_day_report_keeps_the_base_reading(self):
        today = ('Upper Endoscopy Report\n' + HEAD + 'Procedure: Upper endoscopy. The gastroscope was passed to the '
                 'second portion of the duodenum.\n')
        # (an attached report with a plain "Colonoscopy Report" title reads its colonoscopy performed on the base by that
        # title's own section: not this rule's, and not changed by it)
        for attached in ('Outside report:\nColonoscopy Report (Final)\nProcedure: The colonoscope was advanced to the '
                         'cecum. ' + COLD + '\n',
                         'Outside report:\nProcedure: The colonoscope was advanced to the cecum. ' + COLD + '\n',
                         'Prior report:\nReceived by fax.\nProcedure: The colonoscope was advanced to the cecum. '
                         + COLD + '\n',
                         'History:\nProcedure: The colonoscope was advanced to the cecum. ' + COLD + '\n',
                         'Attached prior report:\nDate of service: 2023-03-01\nProcedure: The colonoscope was advanced '
                         'to the cecum. ' + COLD + '\n',
                         'Attached prior report:\nProcedure: The colonoscope was advanced to the cecum on 2023-03-01. '
                         + COLD + '\n'):
            text = today + attached
            with self.subTest(attached[:30]):
                found = finding(text, 'gi.colonoscopy')
                self.assertTrue(found is None or found.status != 'performed', found)
                self.assertFalse(instrument_mentions(text, 'gi.colonoscopy'))

    def test_another_familys_report_or_instrument_keeps_the_base_reading(self):
        for text in ('Flexible Sigmoidoscopy Report\n' + HEAD + 'Procedure: The colonoscope was advanced to the '
                     'descending colon. ' + COLD + '\n',
                     'EUS Report\n' + HEAD + 'Procedure: The gastroscope was advanced to the second portion of the '
                     'duodenum, then the echoendoscope was advanced.\n'):
            with self.subTest(text[:30]):
                instruments = [m for f in detect.route(text, DAY).findings for m in f.mentions
                               if m.cues[:1] == (detect.INSTRUMENT_COURSE,)]
                self.assertFalse([m for m in instruments if m.family in ('gi.colonoscopy', 'gi.egd')])

    def test_the_instrument_must_be_its_courses_subject(self):
        for narrative in ('Procedure: The snare was passed through the colonoscope. ' + COLD + '\n',
                          'Procedure: No colonoscope was advanced. ' + COLD + '\n',
                          'Procedure: The colonoscope was not advanced beyond the rectum. ' + COLD + '\n',
                          'Procedure: The colonoscope will be advanced to the cecum. ' + COLD + '\n',
                          'Procedure: Possibly the colonoscope was advanced to the cecum. ' + COLD + '\n'):
            text = self.doc('Colonoscopy', narrative)
            with self.subTest(narrative):
                self.assertNotEqual(finding(text, 'gi.colonoscopy').status, 'performed')

    def test_a_date_dates_the_narrative_unless_its_clause_names_another_service(self):
        # another family's dated service in the block does not date today's colonoscopy narrative
        other = self.doc('Colonoscopy Report (fictional)', 'History: Per outside report, an upper endoscopy was '
                         'performed at the referring facility in 2025.\n' + self.NARRATIVE)
        self.assertEqual(finding(other, 'gi.colonoscopy').status, 'performed')
        # the family's own dated mention, or an unnamed dated line, keeps the base reading
        for line in ('History: Colonoscopy in 2019 with polypectomy.\n', 'Note: the report below is from 2025.\n',
                     'History: The colonoscopy above was performed in 2025 and is copied for reference.\n'):
            text = self.doc('Colonoscopy Report (fictional)', line + self.NARRATIVE) if 'below' in line or 'History: C' in line \
                else self.doc('Colonoscopy Report (fictional)', self.NARRATIVE + line)
            with self.subTest(line):
                self.assertNotEqual(finding(text, 'gi.colonoscopy').status, 'performed')

    def test_a_planned_or_held_name_in_the_head_or_a_positive_section(self):
        for title in ('Colonoscopy tomorrow', 'Possible colonoscopy', 'Colonoscopy?'):
            text = self.doc(title)
            with self.subTest(title):
                self.assertNotEqual(finding(text, 'gi.colonoscopy').status, 'performed')
        # a plan or a negation of earlier encounters says nothing of today's narrative
        for extra in ('Plan: Repeat colonoscopy in 3 months.\n', 'Indication: No prior colonoscopy.\n'):
            text = self.doc('Colonoscopy', self.NARRATIVE + extra)
            with self.subTest(extra):
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')

    def test_a_cancellation_or_denial_still_contradicts(self):
        for line in ('The procedure was cancelled after the time-out.', 'No colonoscopy was performed today.'):
            text = self.doc('Colonoscopy', 'Procedure: The colonoscope was advanced to the cecum. ' + line + '\n')
            with self.subTest(line):
                self.assertNotEqual(finding(text, 'gi.colonoscopy').status, 'performed')

    def test_the_instrument_mentions_are_bounded(self):
        text = self.doc('Colonoscopy', 'Procedure:\n' + 'The colonoscope was advanced to the cecum.\n' * 5000)
        start = time.perf_counter()
        found = finding(text, 'gi.colonoscopy')
        self.assertLess(time.perf_counter() - start, 30)
        self.assertLessEqual(len([m for m in found.mentions if m.cues[:1] == (detect.INSTRUMENT_COURSE,)]),
                             detect.INSTRUMENT_MENTIONS)
        # the analyze stage's bound counts service names only, as before
        self.assertEqual(detect.service_mention_count(text), 1)


class InstrumentGuardTests(SimpleTestCase):
    """The refuter shapes that opened the instrument rule before I4's second half, I9 and I10 (each READY on the rule's
    first form, held on the base), and the controls that still release."""

    HEAD = 'Date of service: 2026-10-14\nEndoscopist: Jane Synthetic, MD\n'
    COLD = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'

    def doc(self, body, title='Colonoscopy', heading='Procedure: '):
        return (title + '\n' if title else '') + self.HEAD + heading + body + ' ' + self.COLD + '\n'

    def assert_base(self, text):
        self.assertFalse(instrument_mentions(text, 'gi.colonoscopy'), text)
        found = finding(text, 'gi.colonoscopy')
        self.assertTrue(found is None or found.status != 'performed', found)
        if dated_today(text):
            self.assertNotEqual(proposal(text, '45385', self.COLD).status, 'ready')

    def test_the_documented_service_readers_own_holds_hold_the_instrument(self):
        # I4: services.statement_hold and services.in_condition, the functions read_clause reads them with
        for body in ('It is unknown whether the colonoscope was advanced to the cecum.',
                     'At a community hospital, the colonoscope was advanced to the cecum.',
                     'Reportedly the colonoscope was advanced to the cecum.',
                     'The colonoscope was advanced to the cecum by Dr. Other Person.',
                     'According to the patient, the colonoscope was advanced to the cecum.',
                     'The colonoscope was advanced to the cecum (outside report).',
                     'The colonoscope was possibly advanced to the cecum.'):
            for title in ('Colonoscopy', ''):
                with self.subTest(body=body, title=title):
                    self.assert_base(self.doc(body, title))
        # the report's own physician named as the agent is no other source
        text = self.doc('The colonoscope was advanced to the cecum by Dr. Synthetic.')
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')

    def test_another_kind_of_document_is_no_procedure_report(self):
        # I9: an office visit, a discharge summary, a consult, a letter or a nursing note recounting the course
        for title, heading in (('Office Visit Note', 'HPI: Follow-up.\nFindings: '), ('Discharge Summary', 'Procedures: '),
                               ('GI Consult', 'Findings: '), ('Dear Dr. Smith,', 'Findings: '), ('Nursing Note', 'Procedure: '),
                               ('Nursing Record', 'Procedure: '), ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', 'Findings: ')):
            text = self.doc('The colonoscope was advanced to the cecum.', title, heading)
            with self.subTest(title):
                self.assert_base(text)
        # a procedure report's own head: a procedure title, a generic procedure report title, a strong head, or fields
        # and headings only
        for title, head in (('Colonoscopy', self.HEAD), ('Endoscopy Report', self.HEAD), ('Procedure Note', self.HEAD),
                            ('', 'Date of service: 2026-10-14\nEndoscopist: Jane Synthetic, MD\nSedation: MAC\n'),
                            ('', 'Date of service: 2026-10-14\nIndications: Screening.\n')):
            text = (title + '\n' if title else '') + head + 'Procedure: The colonoscope was advanced to the cecum. ' \
                + self.COLD + '\n'
            with self.subTest(title=title, head=head):
                self.assertTrue(instrument_mentions(text, 'gi.colonoscopy'))
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')

    def test_a_narrative_its_section_calls_a_copy_or_another_report(self):
        # I10
        for line in ('This narrative is copied from the prior report.', 'Text carried forward from the 2024 note.',
                     'Findings are from the previous colonoscopy.'):
            with self.subTest(line):
                self.assert_base(self.doc('The colonoscope was advanced to the cecum. ' + line))


class ExtentFactTests(SimpleTestCase):
    """U12: one extent fact - routing reads the completion reader's reach statements; truthful wording otherwise."""

    def test_routing_reads_the_completion_readers_reach_statements(self):
        for line in ('Cecal intubation was achieved.', 'Cecal intubation was confirmed.', 'The cecum was reached.',
                     'The appendiceal orifice and ileocecal valve were photographed.'):
            text = 'Date of service: 2026-10-14\nProcedure: Colonoscopy.\n' + line + ' A 6 mm sigmoid polyp was removed ' \
                   'with a cold snare.\n'
            with self.subTest(line):
                self.assertEqual(facts(text, 'gi.colonoscopy').get('extent'), 'cecum')
                p = proposal(text, '45385', 'A 6 mm sigmoid polyp was removed with a cold snare.')
                self.assertEqual((p.bucket, p.status), ('selected', 'ready'))

    def test_a_denied_or_doubted_reach_reads_no_extent(self):
        for line in ('Cecal intubation was not achieved.', 'Cecal intubation was achieved?', 'If cecal intubation '
                     'was achieved, the cecum was not photographed.'):
            text = 'Date of service: 2026-10-14\nProcedure: Colonoscopy.\n' + line + ' A 6 mm sigmoid polyp was removed ' \
                   'with a cold snare.\n'
            with self.subTest(line):
                self.assertNotEqual(facts(text, 'gi.colonoscopy').get('extent'), 'cecum')

    def test_a_missing_extent_is_worded_as_the_readers_finding(self):
        text = ('Date of service: 2026-10-14\nProcedure: Colonoscopy.\nA 6 mm sigmoid polyp was removed with a cold '
                'snare.\n')
        p = proposal(text, '45385', 'A 6 mm sigmoid polyp was removed with a cold snare.')
        required = next(c for c in p.checks if c.id == 'facts.required')
        self.assertEqual(required.status, 'warn')
        self.assertIn(checks.EXTENT_NOT_FOUND, required.detail)
        self.assertNotIn('Not documented: extent reached', required.detail)
        extent = next(c for c in p.clarifications if c.fact == 'extent')
        self.assertTrue(extent.reason.startswith(checks.EXTENT_NOT_FOUND), extent.reason)

    def test_the_incompleteness_evidence_is_what_states_it(self):
        text = colon(COLD, 'The procedure was terminated because of patient discomfort.')
        inventory = gi_services.build(text, service_date=DAY, routing=detect.route(text, DAY))
        service = next(s for s in inventory.services if s.family == 'gi.colonoscopy')
        self.assertEqual(service.status, 'incomplete')
        self.assertNotIn('The colonoscope was advanced to the cecum.', [e.text for e in service.completion_evidence])
        self.assertIn('The procedure was terminated because of patient discomfort.',
                      [e.text for e in service.completion_evidence])

    def test_the_documented_service_readers_own_completion_reads_the_same_subject(self):
        text = colon(COLD, 'The snare could not be passed around the 14 mm polyp.')
        alone = gi_services.build(text, service_date=DAY, routing=None)
        self.assertEqual(next(s for s in alone.services if s.family == 'gi.colonoscopy').completion, 'complete')
        text = colon(COLD, 'The scope could not be advanced beyond the hepatic flexure.',
                     procedure='Procedure: Colonoscopy. The colonoscope was advanced to the hepatic flexure.')
        alone = gi_services.build(text, service_date=DAY, routing=None)
        self.assertEqual(next(s for s in alone.services if s.family == 'gi.colonoscopy').completion, 'incomplete')


class CostTests(SimpleTestCase):
    def test_a_long_sentence_of_failures_and_interventions_stays_linear(self):
        sentence = ', '.join(['hot snare polypectomy was unsuccessful'] * 3000)
        text = colon(COLD, sentence + '.')
        start = time.perf_counter()
        detect.route(text, DAY)
        self.assertLess(time.perf_counter() - start, 30)
