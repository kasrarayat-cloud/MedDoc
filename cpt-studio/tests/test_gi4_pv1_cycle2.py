"""GI round 4, Wave 1 repair cycle 2, package PV1 (tests/fixtures/gi4/declarations/pv1.json, amendment_20261101_cycle2,
declared and committed before this code). Every case is synthetic.

- The DROP of C1 and C2. The second refutation of the two releasing families found three blocking false READYs
  (PV1C2-01, -02 and -03). On the refutation's own inputs, each code now reads exactly as installed 80df1831d168 reads
  it; every expected tuple below was measured there.
- PV1C2-08, a pure text fix. A C4 cue resting on a line longer than _PV1_LINE_QUOTE quotes the layout's sentence holding
  its words when that sentence fits, so the quote keeps its subject. Its killing mutant is pv1-line-quote-sentence.
- The known limits the cycle records. C4 and C4-time are kept unchanged, and each finding against them is pinned as it
  reads now, named as the false hold it is, so a later change to it is seen.
"""
import datetime as dt
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio import jobs
from studio.gi import cues, detect

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = dt.date(2026, 10, 26)
EXAM = 'Physical exam\nAbdomen soft, nontender.\n'
CC = 'Chief complaint\nHeartburn.\n'
AP = 'Assessment and plan\nGERD, improved. Continue omeprazole.\n'
LOW, MOD, HIGH = ('Complexity of decision making: low.', 'Complexity of decision making: moderate.',
                  'Complexity of decision making: high.')
MDM = 'Medical decision making: moderate.'
INSTALLED_BASIS = ('selected', 'needs_clarification', ('em_basis',))  # installed's reading of a code citing a label


def head(title='Office visit note'):
    """The refutation's note head: a title, the date of service, an office place of service, an established patient."""
    return B + f'{title}\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\nEstablished patient\n'


def visit(cc='Heartburn.', plan='GERD. Continue omeprazole.', tail=''):
    """The refutation's in-person office visit: a physical exam with vital signs, its own MDM, an assessment and plan."""
    return (head() + 'Chief complaint\n' + cc + '\nPhysical exam\nBP 124/78, HR 70. Abdomen soft, nontender.\n' + MDM + '\n'
            'Assessment and plan\n' + plan + '\n' + tail)


def em(text, day=DAY):
    jobs.release_routing_caches()
    return next((f for f in detect.route(text, day).findings if f.family == 'gi.office_em'), None)


def facts(finding):
    return {f.name: f.value for f in (finding.facts if finding else ())}


def outcome(text, code, quote):
    """``code`` citing ``quote`` through the stages the H4 battery runs: (bucket, status, sorted clarification facts)."""
    m = battery.modules()
    document_facts, day, _ = m.jobs._analyze_child(text, {}, 1000)
    merged = m.jobs._merged_facts(document_facts, {})
    context = m.jobs.context_facts(SimpleNamespace(facts=merged))
    _, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context,
                                     battery.response(m, text, [(code, quote, 'MAY')]), m.Lookup([], {}), 'succeeded',
                                     'ok', ())
    m.jobs.release_routing_caches()
    p = next(p for p in result.proposals if p.code == code and p.bucket != 'alternative')
    return p.bucket, p.status, tuple(sorted(c.fact for c in p.clarifications))


def quote_of(finding):
    """The line quote of the C4 cue the finding's first mention carries."""
    cue = finding.mentions[0].cues[0]
    assert cue.startswith(detect.EM_NOT_IN_PERSON + ": '"), cue
    return cue[len(detect.EM_NOT_IN_PERSON) + 3:-1]


class DropTests(SimpleTestCase):
    """C1 and C2 are dropped: their false READYs read exactly as installed reads them."""

    def test_c2s_label_pattern_is_installeds(self):
        self.assertEqual(list(cues.MDM_LEVEL.finditer('Complexity of decision making: moderate.')), [])
        self.assertNotIn('of\\s+decision', cues.MDM_LEVEL.pattern)
        self.assertEqual([m.group('level') for m in cues.MDM_LEVEL.finditer('Medical decision making: moderate.')],
                         ['moderate'])  # installed's own reading, unchanged

    def test_pv1c2_01_telephone_visits_read_as_installed(self):
        # READY on fbc59ee53 (the history clause without "today", the plan clause with a planned cue)
        a1 = (head('GI Clinic Note') + 'History of present illness\nThis visit was conducted by telephone at her request. '
              'Heartburn is better on omeprazole.\n' + EXAM + AP + LOW + '\n')
        a10 = (head('GI Clinic Note') + 'History of present illness\nThis visit was conducted by telephone. Heartburn is '
               'better.\nVitals: weight 70 kg (patient\'s scale)\n' + AP + LOW + '\n')
        a13 = (head('GI Clinic Note') + CC + EXAM + 'Assessment and plan\nTelephone visit today, will continue omeprazole '
               'and recheck in 3 months.\n' + LOW + '\n')
        for text in (a1, a10, a13):
            self.assertEqual(outcome(text, '99213', LOW), INSTALLED_BASIS, text)
        # the release did not depend on the quote: A1 citing its HPI line reads as installed too
        self.assertEqual(outcome(a1, '99213', 'This visit was conducted by telephone at her request.'), INSTALLED_BASIS)
        # C1's form: installed EXCLUDES it ('planned: orders'), fbc59ee53 read it READY
        a6 = (head('GI Clinic Note') + 'History of present illness\nThis visit was conducted by telephone at her request. '
              'Heartburn is better on omeprazole.\n' + EXAM + AP + 'Total time: 25 minutes, including the orders and '
              'documentation.\n')
        self.assertEqual(outcome(a6, '99213', 'Total time: 25 minutes, including the orders and documentation.'),
                         ('excluded', 'excluded', ()))

    def test_pv1c2_02_notes_with_no_physician_visit_read_as_installed(self):
        vitals = 'Vital signs\nBP 128/76, HR 72, weight 70 kg.\n'
        b1 = (head('GI Clinic Note') + 'Chief complaint\nBiopsy results.\nVital signs\nBP 128/76, HR 72, weight 70 kg (last '
              'filed 09/14/2026).\nAssessment and plan\nH. pylori gastritis. Patient not present; the results and plan '
              'were sent to her by letter. Quadruple therapy sent to her pharmacy.\n' + MOD + '\n')
        c1 = (head() + CC + vitals + 'Assessment and plan\nThe patient left before being seen by the physician; she will '
              'be contacted to rebook.\n' + LOW + '\n')
        self.assertEqual(outcome(b1, '99214', MOD), INSTALLED_BASIS)
        self.assertEqual(outcome(c1, '99213', LOW), INSTALLED_BASIS)

    def test_pv1c2_03_another_notes_level_reads_as_installed(self):
        for intro in ('Previous note copied below.', 'Note from her visit on 09/14/2026 follows.',
                      'Hepatology note reviewed:', 'Previous note copied below:'):  # the last, a control on both trees
            text = head() + CC + EXAM + AP + intro + '\n' + HIGH + '\n'
            self.assertEqual(outcome(text, '99215', HIGH), INSTALLED_BASIS, intro)
            self.assertNotIn('mdm_level', facts(em(text)), intro)


K08_LINE = 'GERD. Continue omeprazole. Her CT result came back after the visit and was reviewed with the patient by phone.'


class QuoteSentenceTests(SimpleTestCase):
    """PV1C2-08: a long line's C4 quote is the sentence holding the words when it fits (text only: the hold is C4's,
    decided before the quote is read)."""

    def test_k08_keeps_its_sentences_subject(self):  # kills pv1-line-quote-sentence
        finding = em(visit(plan=K08_LINE))
        self.assertEqual(quote_of(finding),
                         '…Her CT result came back after the visit and was reviewed with the patient by phone.')
        self.assertEqual(finding.status, 'uncertain')  # the hold itself is C4's, unchanged (PV1C2-04, a known limit)

    def test_independent_variants_keep_their_subjects(self):
        for plan, cc, quoted in (
                ('GERD. Continue omeprazole. Labs drawn in clinic returned this afternoon and were discussed with the '
                 'patient by phone.', 'Heartburn.',
                 '…Labs drawn in clinic returned this afternoon and were discussed with the patient by phone.'),
                ('GERD. Continue omeprazole.', 'Heartburn, three weeks, worse at night and after meals. The patient was '
                 'contacted by phone today, as Dr. Lee advised.',
                 '…The patient was contacted by phone today, as Dr. Lee advised.'),  # "Dr." ends no sentence
                ('GERD. Continue omeprazole.', 'Heartburn, e.g. after spicy food, for three weeks; the antacids help a '
                 'little. She was reached by phone today about it.', '…She was reached by phone today about it.')):
            self.assertEqual(quote_of(em(visit(cc=cc, plan=plan))), quoted, quoted)

    def test_a_sentence_longer_than_the_quote_is_still_cut_around_its_words(self):
        cc = ('The patient was reached by telephone today and she reported that the heartburn is worse at night after '
              'large meals and better with antacids and sleeping propped up on pillows.')
        quoted = quote_of(em(visit(cc=cc)))
        self.assertEqual(quoted, 'The patient was reached by telephone today and she reported that the heartburn…')
        self.assertLessEqual(len(quoted), detect._PV1_LINE_QUOTE + 2)

    def test_a_short_line_is_quoted_whole(self):
        self.assertEqual(quote_of(em(visit(cc='Heartburn. She was reached by telephone today.'))),
                         'Heartburn. She was reached by telephone today.')


class KnownLimitTests(SimpleTestCase):
    """The cycle's recorded known limits (pv1.json amendment_20261101_cycle2, known_limits): false holds of C4 and
    C4-time, kept unchanged because the cycle's work order keeps those hold-only rules. Each test pins today's reading
    and says it is wrong. Installed reads every one of these codes READY."""

    HELD = ('selected', 'needs_clarification', ('performed_status',))

    def test_known_limit_pv1c2_04_a_same_day_triage_call_holds_an_in_person_visit(self):
        text = visit(cc='Heartburn. The patient was triaged by phone this morning and given a same-day appointment.')
        self.assertEqual(outcome(text, '99214', MDM), self.HELD)

    def test_known_limit_pv1c2_05_the_patients_daughter_reads_as_the_patient(self):
        text = visit(plan="GERD. Continue omeprazole. Spoke by phone with the patient's daughter about her medications.")
        self.assertEqual(outcome(text, '99214', MDM), self.HELD)
        control = visit(plan='GERD. Continue omeprazole. Spoke by phone with her daughter about her medications.')
        self.assertEqual(outcome(control, '99214', MDM), ('selected', 'ready', ()))

    def test_known_limit_pv1c2_06_a_denied_telephone_visit_holds(self):
        text = (head() + 'Visit type: in-person, not by telephone.\nChief complaint\nHeartburn.\nPhysical exam\nBP 124/78, '
                'HR 70. Abdomen soft, nontender.\n' + MDM + '\nAssessment and plan\nGERD. Continue omeprazole.\n')
        self.assertEqual(outcome(text, '99214', MDM), self.HELD)
        self.assertEqual(quote_of(em(text)), 'Visit type: in-person, not by telephone.')  # the false text

    def test_known_limit_cts2_3_a_pre_visit_call_holds(self):
        text = (head('GI Clinic Note') + 'History of present illness\nTwo days of dysphagia to solids.\nPhysical exam\n'
                'Vital signs: BP 118/72, pulse 76.\nAbdomen soft, nontender.\nAssessment and plan\nDysphagia; upper '
                'endoscopy to be scheduled.\nThe patient called (phone) earlier today; seen in clinic this afternoon.\n'
                'Total time: 32 minutes.\n')
        self.assertEqual(outcome(text, '99214', 'Total time: 32 minutes.'), self.HELD)

    def test_known_limit_pv1c2_07_another_visit_in_the_time_statement_holds_it_and_asks_the_basis(self):
        # C4-time, not reached by the drop: the hold also asks for a basis the note states (CTS-2 counts only C4's)
        for line in ('Total time: 30 minutes, including 10 minutes reviewing the colonoscopy done at her previous visit.',
                     'Total time: 30 minutes (her last visit was in August).'):
            text = (head() + CC + 'Physical exam\nBP 124/78, HR 70. Abdomen soft, nontender.\nAssessment and plan\nGERD. '
                    'Continue omeprazole.\n' + line + '\n')
            self.assertEqual(outcome(text, '99214', 'Total time: 30 minutes'),
                             ('selected', 'needs_clarification', ('em_basis', 'performed_status')), line)
            self.assertNotIn('time_minutes', facts(em(text)), line)
