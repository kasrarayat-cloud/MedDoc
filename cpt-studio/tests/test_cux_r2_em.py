"""Round-2 repair reader-em (2026-11-04): the round-2 refutation's findings on the office E/M reading, declared before
code in tests/fixtures/gi4/declarations/cux-r2-em.json.

- L2/F07: P1 rule 8 read a sentence as the explicit statement that no separate office E/M service is documented when it
  was not one: a location hedge ("The office visit is not documented here; it is documented in the clinic note of
  today.") or a negator governing another noun ("No medication changes at today's office visit were documented."). The
  E/M questions vanished and a proposed visit code was excluded. Rule R8b-1: the statement is the whole of its sentence.
- L2/F08: a same-day evaluation stated in any wording other than an E/M visit phrase never contradicted the absence
  statement. Rule R8b-2: an evaluation of the patient, a history, an examination or a visit stated anywhere else holds
  it, as an E/M statement read performed already did.
- L7/L7-06: a member's saved new or established status was ignored by the office E/M service's uncertainty, so the
  question came back after the one re-assessment (or moved to a service row). Rule E7: the context's status closes it,
  as the context's setting already did.
- L2/F09 was judged BY_DESIGN: its reading is pinned here as it is.

Every document is synthetic and opens "SYNTHETIC TEST DOCUMENT - FICTIONAL". Nothing is sent: the provider answers are
synthetic (ops.gi4.battery.response) or the project's in-process FakeProvider.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings

from ops.gi4 import battery
from studio import answers, jobs, models
from studio.gi import context as gi_context
from studio.gi import cues, detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import PageSpan
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.test_cux_bind import EM_QUESTIONS, READY, day_of, em_questions, inventory, outcomes, run, service
from tests.test_pipeline_api import FakeProvider, drain

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
# the body of tests/fixtures/cux/reader/r8-*.txt (the findings' BODY, verbatim)
BODY = (B + 'Upper Endoscopy Report\nDate of service: 2026-10-26\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
        'Sedation: propofol by a CRNA (fictional)\nProcedure: EGD\nThe gastroscope was advanced to the second part of the '
        'duodenum. Cold forceps biopsies were taken from the gastric antrum.\n')
BIOPSY = ('43239', 'Cold forceps biopsies were taken from the gastric antrum.')
# Mara's sentence (tests/fixtures/cux/mara/rev1.txt), the owner's worked example of an explicit absence statement
MARA = 'No separate office evaluation and management encounter or office-visit time is documented on this date.'
OFFICE_EM = 'gi.office_em'


def routing_em(text):
    finding = detect.route(text, day_of(text)).finding(OFFICE_EM)
    jobs.release_routing_caches()
    return finding


def mention_cues(finding):
    return [c for m in finding.mentions for c in m.cues] if finding is not None else []


def held_with_code(test, text, code, quote):
    """The proposed E/M ``code`` beside the biopsy: held with a question, never excluded or ready; 43239 stays READY."""
    result = run(text, [BIOPSY, (code, quote)])
    found = outcomes(result)
    test.assertEqual(found[code][:2], ('selected', 'needs_clarification'), found)
    test.assertEqual(found['43239'], READY)
    return found


class AbsenceIsTheWholeSentenceTests(SimpleTestCase):
    """F07 (R8b-1): rule 8 negates the visit only where the sentence is the absence statement and nothing else."""

    FINDING = {
        # the finding's two inputs, and the verifier's isolating variants
        'S1 hedged here, documented in the clinic note':
            ('The office visit is not documented here; it is documented in the clinic note of today.',
             'The office visit is not documented here'),
        "S2 no medication changes at today's visit":
            ("No medication changes at today's office visit were documented.",
             "No medication changes at today's office visit were documented"),
        "no complications at today's visit":
            ("No complications at today's office visit were documented.",
             "No complications at today's office visit were documented"),
        'hedged here, alone': ('The office visit is not documented here.', 'The office visit is not documented here'),
        # the verifier's side note: billing wordings that presuppose a visit
        'no charge for an office visit': ('No charge for an office visit was billed.',
                                          'No charge for an office visit was billed'),
        'no fee for the office E/M service': (
            'No fee for the office evaluation and management service was billed separately.',
            'No fee for the office evaluation and management service was billed separately'),
    }
    # Mara's own shape (an "office" between the negator and the mention, so no generic negation cue reads it and only
    # rule 8 could), with something else in the sentence
    HEDGED = (
        'No separate office evaluation and management encounter is documented here.',
        'No separate office evaluation and management encounter is documented in this report.',
        'No separate office evaluation and management encounter is documented elsewhere.',
        'No separate office evaluation and management encounter is documented in this note; see the clinic note.',
        'No separate office evaluation and management encounter was provided by the endoscopist.',
        'No separate office evaluation and management encounter is documented, and the visit is in the clinic note.',
        'Evaluation and management was not documented in this procedure note.',
        'Evaluation and management is not documented here; it is documented in the clinic note of today.',
        'The office visit was not documented.',
        # a condition or a question: a hedge cue reads these first (as at c47d71a3); rule 8 never reads them either
        'If needed, no separate office evaluation and management encounter was provided.',
        'Is no separate office evaluation and management encounter documented?',
    )
    # Outside rule 8: "no separate <visit mention>" is the installed generic negation (cues.NEGATED_PRE, "no" with only
    # fillers before the mention), which reads these as installed 41e03656df61 did, whatever follows; the absence
    # pattern does not match them, so rule 8 is never the reason (a recorded limit of this repair, cux-r2-em.json).
    GENERIC = (
        'No separate office visit is documented elsewhere.',
        'No separate office visit is documented in this note; see the clinic note.',
        'No separate office visit was provided by the endoscopist.',
    )

    def assert_asks(self, line):
        text = BODY + line + '\n'
        self.assertIsNone(cues.EM_ABSENCE.search(line), line)
        finding = routing_em(text)
        self.assertNotEqual(finding.status, 'negated', line)
        self.assertNotIn(detect.EM_ABSENT_CUE, mention_cues(finding), line)
        self.assertNotEqual(service(inventory(text), OFFICE_EM).status, 'negated', line)
        result = run(text, [BIOPSY])
        asked = em_questions(result)
        self.assertTrue(asked and asked <= EM_QUESTIONS, (line, asked))
        self.assertEqual(outcomes(result)['43239'], READY)

    def test_the_finding_s_sentences_ask_as_installed(self):
        for label, (line, quote) in self.FINDING.items():
            with self.subTest(label):
                self.assert_asks(line)
                held_with_code(self, BODY + line + '\n', '99203', quote)

    def test_the_finding_s_first_input_asks_what_the_installed_release_asks(self):
        line, quote = self.FINDING['S1 hedged here, documented in the clinic note']
        text = BODY + line + '\n'
        self.assertEqual(routing_em(text).status, 'uncertain')
        self.assertEqual(em_questions(run(text, [BIOPSY])), {'em_basis', 'patient_status'})

    def test_a_hedge_another_clause_a_condition_or_a_question_keeps_the_questions(self):
        for line in self.HEDGED:
            with self.subTest(line):
                self.assert_asks(line)

    def test_outside_rule_8_the_generic_negation_reads_as_installed(self):
        for line in self.GENERIC:
            with self.subTest(line):
                self.assertIsNone(cues.EM_ABSENCE.search(line))
                self.assertNotIn(detect.EM_ABSENT_CUE, mention_cues(routing_em(BODY + line + '\n')))

    def test_the_class_sentences_still_release(self):
        for line in (MARA,
                     'No separately identifiable office visit or outpatient evaluation and management service was '
                     'provided on this date.',
                     'Separate evaluation and management was not provided today.',
                     'No separate office evaluation and management service is documented.',
                     'Evaluation and management was not provided.',
                     'No record of a separate office visit is documented.',
                     'No documentation of a separate office visit was provided on this date.',
                     'No separate clinic visit occurred today.'):
            with self.subTest(line):
                match = cues.EM_ABSENCE.search(line)
                self.assertIsNotNone(match)
                self.assertEqual(match.group(0), line.rstrip('.'))  # the whole sentence, and nothing else
                text = BODY + line + '\n'
                finding = routing_em(text)
                self.assertEqual(finding.status, 'negated')
                em = service(inventory(text), OFFICE_EM)
                self.assertEqual(em.status, 'negated')
                if all(detect.EM_ABSENT_CUE in m.cues for m in finding.mentions):  # rule 8 read it, both readers say so
                    self.assertIn(services.EM_ABSENT_SERVICE_CUE, em.cues)
                else:  # "No separate clinic visit": the installed generic negation reads it first, as at c47d71a3
                    self.assertEqual(line, 'No separate clinic visit occurred today.')
                result = run(text, [BIOPSY])
                self.assertEqual(em_questions(result), set())
                self.assertEqual(outcomes(result)['43239'], READY)

    def test_the_statement_is_read_in_its_own_sentence_whatever_comes_before_or_after(self):
        # Mara's own placement: after "precautions." on the same line, and before the authentication line
        text = BODY + 'The patient received routine post-endoscopy\nprecautions. ' + MARA + '\nAuthenticated: (fictional)\n'
        finding = routing_em(text)
        self.assertEqual(finding.status, 'negated')
        self.assertEqual(em_questions(run(text, [BIOPSY])), set())
        # a statement read from its sentence's start only: never from inside another sentence
        self.assertIsNone(cues.EM_ABSENCE.search('Although the visit was brief, no separate office visit was provided.'))

    def test_a_day_may_open_the_statement_and_a_qualifier_never_lengthens_the_visit_mention(self):
        for line in ('Today, no separate office evaluation and management encounter was provided.',
                     'On this date, no separate office evaluation and management encounter is documented.',
                     'No separate office evaluation and management encounter on this date is documented.',
                     'Outpatient evaluation and management was not provided today.'):
            with self.subTest(line):
                self.assertEqual(cues.EM_ABSENCE.search(line).group(0), line.rstrip('.'))
                text = BODY + line + '\n'
                self.assertEqual(routing_em(text).status, 'negated')
                self.assertEqual(em_questions(run(text, [BIOPSY])), set())
        # "outpatient office visit" is one visit mention that starts before the noun rule 8 denies: P1's form never
        # covered it, so it is never read as the denial here either (it asks, as at c47d71a3)
        for line in ('Outpatient office visit was not provided today.', 'In-person clinic visit was not documented.'):
            with self.subTest(line):
                self.assertIsNone(cues.EM_ABSENCE.search(line))
                self.assertNotEqual(routing_em(BODY + line + '\n').status, 'negated')


class AbsenceBesideAnEvaluationTests(SimpleTestCase):
    """F08 (R8b-2): an evaluation of the patient, a history, an examination or a visit stated anywhere else in the note
    holds the absence statement; the note contradicts itself and still asks."""

    EVALUATIONS = (
        'She was also evaluated today for new-onset jaundice, a separate problem, with a history and examination.',
        'Separately, she was seen and examined today for new-onset jaundice; labs and an MRCP were ordered.',
        'She was also seen in clinic today for new-onset jaundice, a separate problem.',
        'A separate problem-focused history and examination was performed today for new-onset jaundice.',
        'I examined her today for new-onset jaundice, a separate problem.',
        'History of present illness: two weeks of new-onset jaundice.',
        'The jaundice visit is documented in the clinic note of today.',
        # a denial earlier in the sentence governs nothing past its clause
        'No complications occurred, and she was evaluated today for new-onset jaundice.',
        # a named patient seen for something; the patient who underwent an evaluation
        'Mara was seen for new-onset jaundice, a separate problem.',
        'She also underwent a separate evaluation for new-onset jaundice.',
    )

    def assert_held(self, text):
        finding = routing_em(text)
        self.assertEqual(finding.status, 'uncertain', text)
        found = mention_cues(finding)
        self.assertNotIn(detect.EM_ABSENT_CUE, [c for m in finding.mentions for c in m.cues[:1]])
        self.assertTrue(any(c.startswith(detect.EM_ABSENT_EVALUATION) for c in found), found)
        self.assertEqual(service(inventory(text), OFFICE_EM).status, 'uncertain')
        result = run(text, [BIOPSY])
        asked = em_questions(result)
        self.assertTrue(asked and asked <= EM_QUESTIONS, asked)
        self.assertEqual(outcomes(result)['43239'], READY)
        return asked

    def test_the_finding_s_inputs_ask_in_either_order(self):
        for line in self.EVALUATIONS:
            for label, text in (('evaluation first', BODY + line + '\n' + MARA + '\n'),
                                ('absence first', BODY + MARA + '\n' + line + '\n')):
                with self.subTest(f'{label}: {line}'):
                    self.assert_held(text)

    def test_the_finding_s_first_input_asks_what_the_installed_release_asks_and_holds_99213(self):
        line = self.EVALUATIONS[0]
        text = BODY + line + '\n' + MARA + '\n'
        self.assertEqual(self.assert_held(text), {'em_basis', 'patient_status', 'setting'})
        for quote in (line.rstrip('.'), 'She was also evaluated today for new-onset jaundice'):
            with self.subTest(quote):
                held_with_code(self, text, '99213', quote)

    def test_the_finding_s_second_input_holds_99213_whatever_the_quote(self):
        line = self.EVALUATIONS[1]
        text = BODY + line + '\n' + MARA + '\n'
        for quote in ('Separately', 'she was seen and examined today for new-onset jaundice', line.rstrip('.')):
            with self.subTest(quote):
                held_with_code(self, text, '99213', quote)

    def test_an_e_m_statement_read_performed_still_holds_it_as_before(self):
        text = BODY + 'An office visit was also completed today for her reflux symptoms.\n' + MARA + '\n'
        finding = routing_em(text)
        self.assertEqual(finding.status, 'uncertain')
        self.assertTrue(any(detect.EM_ABSENT_CONTRADICTED in m.cues for m in finding.mentions))

    def test_controls_what_states_no_evaluation_today_still_releases(self):
        for line in ('She will be seen in clinic in two weeks to review the pathology.',
                     'The history and examination were reviewed, informed consent was obtained, and a procedural '
                     'time-out was completed.',
                     'Non-bleeding grade I internal hemorrhoids were seen on rectal retroflexion.',
                     'The patient tolerated the procedure and was transferred to recovery in stable condition.'):
            with self.subTest(line):
                text = BODY + line + '\n' + MARA + '\n'
                self.assertIsNone(cues.EM_EVALUATION_STATED.search(line))
                self.assertEqual(routing_em(text).status, 'negated')
                self.assertEqual(em_questions(run(text, [BIOPSY])), set())

    def test_controls_an_evaluation_the_sentence_denies_still_releases(self):
        # the words are there, and the sentence opens by denying them: no evaluation is stated
        for line in ('No separate evaluation was performed today.', 'No physical examination was documented.',
                     'There was no HPI.'):
            with self.subTest(line):
                self.assertIsNotNone(cues.EM_EVALUATION_STATED.search(line))
                text = BODY + line + '\n' + MARA + '\n'
                self.assertEqual(routing_em(text).status, 'negated')
                self.assertEqual(em_questions(run(text, [BIOPSY])), set())

    def test_the_evaluation_words_inside_an_absence_statement_never_hold_it(self):
        # an absence statement whose own words are evaluation words ("consultation was provided") is not another
        # statement of an evaluation. "provided": a generic negation cue reads "No ... was performed" first, and rule 8
        # is then not asked. The second line reaches the words past the denying opener's four words and an "or", so
        # only the absence statement's own span keeps them out.
        for line in ('No separately identifiable office consultation was provided today.',
                     'No separately identifiable office or clinic consultation was provided today.'):
            self.assertIsNotNone(cues.EM_EVALUATION_STATED.search(line))
            self.assertIsNotNone(cues.EM_ABSENCE.search(line))
            for text in (BODY + line + '\n', BODY + MARA + '\n' + line + '\n'):
                with self.subTest(text[len(BODY):]):
                    finding = routing_em(text)
                    self.assertEqual(finding.status, 'negated')
                    self.assertTrue(all(detect.EM_ABSENT_CUE in m.cues for m in finding.mentions))
                    self.assertEqual(em_questions(run(text, [BIOPSY])), set())


class BilledSeparatelyKeptByDesignTests(SimpleTestCase):
    """F09 was judged BY_DESIGN: "No office evaluation and management service was billed separately." is a negator
    governing the visit through visit qualifiers only (arm A), and the installed release already read its twins without
    "office" as negated. It is kept as it is (an open owner question covers the wordings that state a visit happened)."""

    LINE = 'No office evaluation and management service was billed separately.'

    def test_it_reads_as_at_c47d71a3(self):
        text = BODY + self.LINE + '\n'
        self.assertEqual(routing_em(text).status, 'negated')
        self.assertEqual(service(inventory(text), OFFICE_EM).status, 'negated')
        self.assertEqual(em_questions(run(text, [BIOPSY])), set())
        found = outcomes(run(text, [BIOPSY, ('99213', self.LINE.rstrip('.'))]))
        self.assertEqual(found['99213'][:2], ('excluded', 'excluded'))
        # the billing wordings that state a visit happened keep the installed reading
        for line in ('Office visit not billed separately.', 'The office visit was not separately billable.'):
            with self.subTest(line):
                self.assertNotEqual(routing_em(BODY + line + '\n').status, 'negated')


# --- L7-06: a member's new or established status ---------------------------------------------------------------------

OFFICE_NOTE = B + """Lakeside Digestive Clinic (fictional)
Date of service: 2026-10-20
Place of service: Office, in-person outpatient visit

Chief complaint
Follow-up of chronic constipation.

Assessment and plan
Chronic idiopathic constipation, improved. Continue polyethylene glycol daily.

Medical decision making
Low: one stable chronic illness; prescription drug management.

Time
Total time on the date of the encounter was 24 minutes.
"""
TIME = 'Total time on the date of the encounter was 24 minutes.'


def assess_with(text, codes, user_values):
    """The analyze and assess children with a member's answers merged, as ops.gi4.battery.run_row reads a row."""
    m = battery.modules()
    document_facts, day, _routing = jobs._analyze_child(text, user_values, 1000)
    facts = jobs._merged_facts(document_facts, user_values)
    context = jobs.context_facts(SimpleNamespace(facts=facts))
    _, result = jobs._assess_child(text, day, (PageSpan(1, 0, len(text)),), context,
                                   battery.response(m, text, [(c, q, 'MAY') for c, q in codes]),
                                   InMemoryReferenceLookup([], {}), 'succeeded', 'ok', ())
    jobs.release_routing_caches()
    return result


def asked(result, fact):
    return sorted((c.scope, c.family, getattr(c, 'code', '') or '') for c in result.clarifications if c.fact == fact) + \
        sorted(('proposal', p.code) for p in result.proposals if p.bucket != 'alternative'
               for c in p.clarifications if c.fact == fact)


class MemberStatusClosesTheVisitQuestionTests(SimpleTestCase):
    """L7-06 (E7), at the reader: the office E/M service's uncertainty reads new or established status from the encounter
    context, as it reads the setting."""

    def uncertainty(self, text, user_values):
        day = day_of(text)
        facts = gi_context.merge_user_values(gi_context.extract_context(text), user_values)
        inv = services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)
        jobs.release_routing_caches()
        return service(inv, OFFICE_EM).uncertainty

    def test_a_member_status_closes_it_and_none_leaves_it_asked(self):
        self.assertIn('patient_status', self.uncertainty(OFFICE_NOTE, {}))
        for value in ('new', 'established'):
            with self.subTest(value):
                self.assertNotIn('patient_status', self.uncertainty(OFFICE_NOTE, {'patient_status': value}))

    def test_the_assessment_asks_it_once_and_not_after_the_answer(self):
        self.assertEqual(asked(assess_with(OFFICE_NOTE, [], {}), 'patient_status'),
                         [('service', OFFICE_EM, '')])
        self.assertEqual(asked(assess_with(OFFICE_NOTE, [], {'patient_status': 'new'}), 'patient_status'), [])
        # with 99213 proposed the question is the code's before the answer and nobody's after it
        self.assertEqual(asked(assess_with(OFFICE_NOTE, [('99213', TIME)], {}), 'patient_status'),
                         [('proposal', '99213')])
        after = assess_with(OFFICE_NOTE, [('99213', TIME)], {'patient_status': 'new'})
        self.assertEqual(asked(after, 'patient_status'), [])
        self.assertEqual(outcomes(after)['99213'], READY)

    def test_controls_the_basis_is_never_context_and_a_conflict_is_still_asked(self):
        bare = OFFICE_NOTE.replace('Medical decision making\nLow: one stable chronic illness; prescription drug '
                                   'management.\n\n', '').replace('Time\n' + TIME + '\n', '')
        self.assertIn('em_basis', self.uncertainty(bare, {'patient_status': 'new'}))
        documented = OFFICE_NOTE.replace('Chief complaint', 'Patient status: Established patient.\n\nChief complaint')
        self.assertNotIn('patient_status', self.uncertainty(documented, {}))
        result = assess_with(documented, [], {'patient_status': 'new'})
        reasons = [c.reason for c in result.clarifications if c.fact == 'patient_status']
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn('in conflict', reasons[0])


@applied
@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class MemberStatusEndToEndTests(TestCase):
    """L7-06, end to end through the customer API (the verifier's flow): the member answers the status row once; after
    the one re-assessment the row is gone, nothing is open, and nothing was sent again."""

    def setUp(self):
        self.ws = f.workspace()
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(f.member(self.ws, f.user('r2em-reviewer')))

    def create(self, provider):
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
            self.assertEqual(response.status_code, 201, response.content)
            drain()
        return response.json()['id']

    def save(self, url, items):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(url + '/details', data=json.dumps({'answers': items}),
                                        content_type='application/json')
        drain()
        return response

    def rows(self, eid, fact='patient_status'):
        return [r for r in self.client.get(f'/api/encounters/{eid}').json()['details_needed'] if r['fact'] == fact]

    def open_details(self, eid):
        rows = self.client.get('/api/encounters').json()['encounters']
        return next(r for r in rows if r['id'] == str(eid))['open_details']

    def answer_once(self, selections, value):
        provider = FakeProvider(selections=selections)
        eid = self.create(provider)
        url = f'/api/encounters/{eid}'
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            before = self.rows(eid)
            self.assertEqual(len(before), 1, before)
            sent = len(provider.sent)
            response = self.save(url, [{'id': before[0]['id'], 'fact': 'patient_status', 'value': value}])
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(self.rows(eid), [])
            self.assertEqual(self.open_details(eid), 0)
            self.assertEqual(len(provider.sent), sent)  # the re-assessment sends nothing
            encounter = models.Encounter.objects.get(pk=eid)
            self.assertEqual(encounter.user_values.get('patient_status'), value)
            self.assertFalse(models.MemberAnswer.objects.filter(encounter=encounter, fact='patient_status').exists())
        return eid

    def test_with_no_code_the_answered_status_is_not_asked_again(self):
        self.answer_once([], 'new')

    def test_with_99213_the_question_does_not_move_to_a_service_row(self):
        eid = self.answer_once([('99213', TIME)], 'established')
        page = self.client.get(f'/api/encounters/{eid}').json()
        self.assertNotIn(answers.detail_id('patient_status', OFFICE_EM, ''), [r['id'] for r in page['details_needed']])
        self.assertEqual({c['code']: c['status'] for c in page['codes']}.get('99213'), 'ready')


class EmRowsTests(SimpleTestCase):
    """The reader-em rows the lead added to the battery at integration (cux-r2-em.json's integration amendment): each of
    the four moved codes ends where the amendment records it, F09 and the two controls keep the visit code as the
    pre-repair head read it, and no row has a violation."""

    def test_the_rows(self):
        from tests.test_cux_r2_bind import row, state
        declaration = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'declarations'
                                  / 'cux-r2-em.json').read_text(encoding='utf-8'))
        moved = {(name, code): after for name, code, _, after in declaration['amendment_20261104_integration_rows']['battery']}
        names = [name for name in battery.CASES if name.startswith('R8 R2 EM ')]
        self.assertEqual(len(names), 7)
        self.assertEqual({name for name, _ in moved} <= set(names), True)
        for name in names:
            result = row(name)
            for code in result['proposals']:
                with self.subTest(name, code=code):
                    if (name, code) in moved:
                        self.assertEqual(state(result, code), moved[(name, code)])
                    self.assertEqual(result['proposals'][code]['violations'], [])
        unmoved = {'R8 R2 EM F09 billed separately, by design', 'R8 R2 EM rule 8 control, the absence statement alone',
                   'R8 R2 EM rule 8 control, a future clinic visit'}
        for name in unmoved:
            with self.subTest(name):
                self.assertEqual(state(row(name), '99213'), 'excluded/excluded')

