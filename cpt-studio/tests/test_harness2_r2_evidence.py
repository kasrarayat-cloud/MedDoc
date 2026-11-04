"""Refutation round 2, R2-EV: the evidence checks of the candidates and the confirmations (HARNESS.md 11.3, 12.5).

- EV2-1 (the plan's D1): a status is checked on the act the question asks about. A status candidate, and every status
  confirmation the engine reads, is verified only where CPT Studio's readers - the documented-service inventory the
  final assessment recorded - read the passage's whole sentence as stating exactly that status for the act the
  proposal's code accounts for (or its service) in the documented service its hold was decided on: one function,
  reconcile.status_stated, decides it for both. The four scenarios of the verifier's probe run end to end - a pasted
  document through POST /api/encounters, the real pipeline, the served candidates, the confirmation endpoint - and each
  ends with its snare or biopsy code NOT ready; a status confirmation stored before the repair is listed as not read,
  with why, and never applied; and a passage that truly states the act is still confirmed (the check is not vacuous).
- EV2-2, truth-1 and EV2-3 (the plan's D2): every fact's passage gets the section rule, an extent or a structure the
  readers find not reached, not seen or qualified never verifies, and a date of birth or a history date is never
  offered as the date of service - each through the same pipeline and endpoint, ending with nothing confirmed.
- truth-10 (the plan's D3): an assessment of an earlier context is offered no candidate and takes no confirmation; the
  endpoint refuses first, saying why, and so does the re-assessment.
- truth-7 (the shared wording): the first sentence of a participant's own proposal never says Corti did not propose a
  code Corti listed only as a candidate, or selected with no exact passage.
- FG2-1 (tests only): a confirmation is bound to its proposal's identity, context included - a member's new service
  date makes the next chain list it as moved.
- FG2-2 (tests only): a new revision's assessments read no confirmation of an earlier one, and its page and draft
  report list none.
- FG2-4 (tests only): an agent reviewer's confirmation is served, reported and shown as an agent's.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake; Astra and Fable are the real
replay adapters on the real tool loop (tests.test_harness2_pipeline), and CPT Studio's real CMS tool executor answers
their tool calls over a synthetic reference store.
"""
import json
from datetime import date
from unittest import mock

from django.test import Client, SimpleTestCase, override_settings

from studio import jobs, models, review
from studio.gi import context as gi_context
from studio.gi import detect
from studio.gi import services as gi_services
from studio.types import ConfirmedFinding, EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation import engine, reconcile
from studio.validation.engine import assess
from tests.test_harness2_pipeline import (EMPTY_PEER, HEAD, TWO_EXTENTS, ColonCase, Harness2Case, answered,
                                          open_questions, peer_answer, reading)
from tests.test_harness_engine_confirmations import CONFIGURED, REFERENCE, REVIEWER, binding, encounter_check, proposal
from tests.test_participants_support import code as code_item, empty_reading, service as service_item
from tests.test_pipeline_api import drain

DAY = date(2026, 10, 14)
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
NORMAL = 'The mucosa appeared normal throughout. No polyps were seen.'
HEDGE_BX = 'It is unclear whether biopsies of the ascending colon lesion were taken.'
HEDGE_SN = 'It is unclear whether the sigmoid polyp was removed with a hot snare.'
SLICE_BX = 'biopsies of the ascending colon lesion were taken'
SLICE_SN = 'the sigmoid polyp was removed with a hot snare'
JAR_1 = 'Specimen log: jar 1, sigmoid polyp, hot snare.'
JAR_2 = 'Specimen log: jar 2, ascending colon lesion, cold forceps.'
DONE_BX = 'Cold forceps biopsies of the ascending colon lesion were taken.'
TOP = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
       'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n')
# (A) a diagnostic colonoscopy: no polyp, no snare
DIAGNOSTIC = TOP + CECUM + '\n' + NORMAL + '\n'
# (B) each act doubted by its own sentence, each with a specimen line (the suite's DOUBTS)
DOUBTS = TOP + CECUM + '\n' + HEDGE_BX + '\n' + HEDGE_SN + '\n' + JAR_1 + '\n' + JAR_2 + '\n'
# (C), (D) each act doubted, nothing documents either as done
UNSETTLED = TOP + CECUM + '\n' + HEDGE_BX + '\n' + HEDGE_SN + '\n'
# The positive control: the biopsy is stated done, but 45380 cites the hedge, so the two readers disagree and it is
# held on its status - a passage that truly states the act answers that question.
DISAGREE = TOP + CECUM + '\n' + HEDGE_BX + '\n' + DONE_BX + '\n'
NOT_VERIFIED = 'That candidate is not verified, so it cannot be confirmed: '


def say(*parts):
    print('R2EV', *parts, flush=True)


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class EvidenceCase(Harness2Case):
    """The pipeline suite's case: Corti's fake and the replay participants on the real loop, the real API and the real
    confirmation endpoint."""
    corti_codes = ()

    def first(self, astra, fable=None, astra_peer=EMPTY_PEER):
        self.adapters['astra'].first = [answered('astra', astra)]
        self.adapters['fable'].first = [answered('fable', fable if fable is not None else reading())]
        self.adapters['astra'].peer = [astra_peer if callable(astra_peer) else answered('astra', astra_peer, number=2)]
        self.adapters['fable'].peer = [answered('fable', EMPTY_PEER, number=2)]

    def final(self, encounter_id):
        assessment = self.encounter(encounter_id).current_assessment
        self.assertEqual((jobs.assessment_phase(assessment), review.is_final(assessment)), (2, True))
        return assessment

    def status_question(self, assessment, code_value):
        return assessment.clarifications.get(proposal__code=code_value, fact='performed_status',
                                             state=models.Clarification.OPEN)

    def served(self, encounter_id, question):
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        return next(c for c in detail['clarifications'] if c['id'] == str(question.pk))['candidates']

    def served_proposal(self, encounter_id, code_value):
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        return next(p for p in detail['assessment']['proposals']
                    if p['code'] == code_value and p['bucket'] == 'selected')

    def candidate_on(self, encounter_id, question, passage, value='performed'):
        offered = self.served(encounter_id, question)
        say(question.proposal.code if question.proposal_id else question.fact,
            [(c['value'], c['verified'], [s['text'] for s in c['spans']], c['why']) for c in offered])
        return next(c for c in offered if c['value'] == value and [s['text'] for s in c['spans']] == [passage])

    def confirm(self, encounter_id, question, candidate):
        """POST the confirmation endpoint with the candidate's id and the attestation a verified candidate carries (an
        unverified one is served with none: the sentence it would need is sent, so the refusal is the candidate's)."""
        attestation = candidate['attestation'] or ('I read this passage in the source document; it documents '
                                                   f'{candidate["value"]} for this encounter.')
        return self.post(f'/api/encounters/{encounter_id}/clarifications/{question.pk}/confirm',
                         {'candidate_id': candidate['id'], 'attestation': attestation})

    def assertRefusedNotReady(self, encounter_id, question, candidate, why, code_value):
        """``candidate`` is served unverified with ``why``; confirming it is refused and records nothing; its code stays
        held, with nothing but Reject to offer."""
        self.assertEqual((candidate['verified'], candidate['why'], candidate['attestation']), (False, why, ''))
        response = self.confirm(encounter_id, question, candidate)
        self.assertEqual(response.status_code, 409, response.content)
        # moved by the customer interface change (CORE-UX-DESIGN.md 5): a member is told the refusal's fixed head; the
        # candidate's reason, composed from stored readings, stays on the operator payload (candidate['why'])
        self.assertEqual(response.json()['error'], NOT_VERIFIED.rstrip(': ') + '.')
        self.assertFalse(models.FindingConfirmation.objects.exists())
        drain()
        served = self.served_proposal(encounter_id, code_value)
        self.assertEqual((served['status'], served['confirmed'], served['allowed_actions']),
                         ('needs_clarification', [], ['reject']))

    def stored(self, encounter_id, question, passage, value='performed'):
        """A status confirmation of ``question`` as the round-1 endpoint stored one (refutation round 2, EV2-1: a
        stored or forged one), then the re-assessment that reads it."""
        revision = self.encounter(encounter_id).current_revision
        start = revision.text.index(passage)
        row = models.FindingConfirmation.objects.create(
            encounter_id=encounter_id, revision=revision, clarification=question, scope='proposal',
            fact='performed_status', family='gi.colonoscopy', proposal_key=question.proposal.key, value=value,
            spans=[{'start': start, 'end': start + len(passage), 'text': passage, 'page': None}],
            located_by=['astra'], runs=[], confirmed_by=self.reviewer,
            attestation=f'I read this passage in the source document; it documents {value} for this encounter.')
        jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        drain()
        return row

    def assertNotRead(self, encounter_id, row, code_value, why):
        again = self.encounter(encounter_id).current_assessment
        item = again.proposals.get(code=code_value, bucket='selected')
        self.assertEqual(item.status, 'needs_clarification')
        self.assertNotIn('confirmed', item.support)
        self.assertNotIn('confirmed from', json.dumps(item.checks))
        self.assertEqual(again.completeness['confirmations'], {'applied': [], 'ignored': [{'id': str(row.pk),
                                                                                           'why': why}]})
        ignored = next(c for c in again.encounter_checks if c['id'] == 'confirmations.ignored')
        self.assertIn(f'the confirmation of whether it was performed for proposal {item.key} ({code_value}): {why}',
                      ignored['detail'])
        served = self.served_proposal(encounter_id, code_value)
        self.assertEqual((served['status'], served['allowed_actions']), ('needs_clarification', ['reject']))


# --- EV2-1: the four scenarios of the verifier's probe, end to end ---------------------------------------------------

class DiagnosticExaminationTests(EvidenceCase):
    """(A) A diagnostic colonoscopy ("No polyps were seen"): Corti selects 45378 and 45385 on the cecum sentence;
    Astra reads 45378 and a colonoscopy performed, quoting it. 45385 is held - no snare removal is documented - and the
    cecum sentence names no snare removal, so it never answers that question."""
    corti_codes = (('45378', CECUM), ('45385', CECUM))

    def setUp(self):
        super().setUp()
        self.first(reading(codes=[('45378', CECUM)], services=[('c1', 'colonoscopy', 'performed', CECUM)]))

    def test_the_examination_sentence_never_verifies_a_snare_removal(self):
        encounter_id = self.create(DIAGNOSTIC)
        drain()
        question = self.status_question(self.final(encounter_id), '45385')
        self.assertIn('shows no snare removal', question.question)
        candidate = self.candidate_on(encounter_id, question, CECUM)
        self.assertRefusedNotReady(encounter_id, question, candidate, 'The passage does not name the snare removal.',
                                   '45385')

    def test_a_status_confirmation_stored_on_it_is_not_read(self):
        encounter_id = self.create(DIAGNOSTIC)
        drain()
        question = self.status_question(self.final(encounter_id), '45385')
        row = self.stored(encounter_id, question, CECUM)
        self.assertNotRead(encounter_id, row, '45385', 'the passage does not name the snare removal')


def doubts_reading():
    return empty_reading(
        services=[service_item(1, id='c1', family='colonoscopy', status='performed', evidence=[JAR_1, JAR_2])],
        codes=[code_item('45385', service_ids=[], evidence=['hot snare polypectomy of the sigmoid polyp']),
               code_item('45380', service_ids=[], evidence=[SLICE_BX])])


class SpecimenLineTests(EvidenceCase):
    """(B) The suite's DOUBTS document: each act is left in doubt, and Astra's colonoscopy service quotes both specimen
    lines - which the readers read as no snare removal and no biopsy at all. Round 1's EV-1 wrong output (45385 ready on
    the cold-forceps jar) is unreachable through the endpoint."""
    # moved by refutation round 6 (R6-MEANING, the session's D14): Corti selects the codes the held questions are
    # about - the participants' own proposals of them were the holds, and a participant's code is never a proposal
    # now; read on the same passages, the holds are the ones those proposals had (I2)
    corti_codes = (('45385', SLICE_SN), ('45380', SLICE_BX))

    def setUp(self):
        super().setUp()
        self.first(doubts_reading(), astra_peer=peer_answer(codes=[('45385', SLICE_SN)]))

    def test_neither_specimen_line_verifies_the_snare_removal(self):
        encounter_id = self.create(DOUBTS)
        drain()
        question = self.status_question(self.final(encounter_id), '45385')
        for jar in (JAR_1, JAR_2):
            candidate = self.candidate_on(encounter_id, question, jar)
            self.assertEqual((candidate['verified'], candidate['why']),
                             (False, 'The passage does not name the snare removal.'))
        self.assertRefusedNotReady(encounter_id, question, self.candidate_on(encounter_id, question, JAR_2),
                                   'The passage does not name the snare removal.', '45385')

    def test_the_cold_forceps_jar_stored_for_the_snare_is_not_read(self):
        encounter_id = self.create(DOUBTS)
        drain()
        question = self.status_question(self.final(encounter_id), '45385')
        row = self.stored(encounter_id, question, JAR_2)
        self.assertNotRead(encounter_id, row, '45385', 'the passage does not name the snare removal')


class UnsettledTests(EvidenceCase):
    """(C) Nothing documents either act as done; Astra reads the colonoscopy as performed, quoting the cecum sentence.
    Neither 45380 nor 45385 becomes ready on it."""
    # moved by refutation round 6 (R6-MEANING, the session's D14): Corti selects the codes the held questions are
    # about - the participants' own proposals of them were the holds, and a participant's code is never a proposal
    # now; read on the same passages, the holds are the ones those proposals had (I2)
    corti_codes = (('45385', SLICE_SN), ('45380', SLICE_BX))

    def setUp(self):
        super().setUp()
        self.first(reading(codes=[('45385', SLICE_SN), ('45380', SLICE_BX)],
                           services=[('c1', 'colonoscopy', 'performed', CECUM)]))

    def test_the_cecum_sentence_verifies_neither_act(self):
        encounter_id = self.create(UNSETTLED)
        drain()
        final = self.final(encounter_id)
        for code_value, act in (('45380', 'forceps biopsy'), ('45385', 'snare removal')):
            question = self.status_question(final, code_value)
            self.assertIn('in doubt', question.question)
            candidate = self.candidate_on(encounter_id, question, CECUM)
            self.assertRefusedNotReady(encounter_id, question, candidate, f'The passage does not name the {act}.',
                                       code_value)


def answers_with_slice(name, number=2):
    """A peer review answering 45380's open performed-status question 'performed', quoting an exact slice of the hedge
    (without its "It is unclear whether")."""
    def answer(body):
        questions = open_questions(name, body)
        return answered(name, peer_answer(answers=[(q['question_id'], True, 'performed', SLICE_BX) for q in questions
                                                   if q['fact'] == 'performed_status'
                                                   and 'biops' in q['question'].lower()]), number)
    return answer


class HedgeSliceTests(EvidenceCase):
    """(D) Astra's peer review answers 45380's question 'performed', quoting a slice of the hedge sentence. The readers
    read the whole sentence, which leaves the biopsy in doubt; the page shows the slice with that whole sentence."""
    # moved by refutation round 6 (R6-MEANING, the session's D14): Corti selects the codes the held questions are
    # about - the participants' own proposals of them were the holds, and a participant's code is never a proposal
    # now; read on the same passages, the holds are the ones those proposals had (I2)
    corti_codes = (('45385', SLICE_SN), ('45380', SLICE_BX))

    def setUp(self):
        super().setUp()
        self.first(reading(codes=[('45385', SLICE_SN), ('45380', SLICE_BX)]), astra_peer=answers_with_slice('astra'))

    def test_a_slice_of_the_hedge_never_verifies_the_biopsy(self):
        encounter_id = self.create(UNSETTLED)
        drain()
        question = self.status_question(self.final(encounter_id), '45380')
        candidate = self.candidate_on(encounter_id, question, SLICE_BX)
        self.assertEqual(candidate['phase'], 'peer_review')
        self.assertRefusedNotReady(encounter_id, question, candidate,
                                   'The passage leaves the forceps biopsy in doubt.', '45380')
        # the page is served the slice's whole sentence, which it shows with the slice (HARNESS.md 12.5)
        start = UNSETTLED.index(HEDGE_BX)
        self.assertEqual(candidate['sentences'], [{'start': start, 'end': start + len(HEDGE_BX), 'text': HEDGE_BX}])

    def test_the_slice_stored_as_a_confirmation_is_not_read(self):
        encounter_id = self.create(UNSETTLED)
        drain()
        question = self.status_question(self.final(encounter_id), '45380')
        row = self.stored(encounter_id, question, SLICE_BX)
        self.assertNotRead(encounter_id, row, '45380', 'the passage leaves the forceps biopsy in doubt')


class ActStatedTests(EvidenceCase):
    """The control: a passage that truly states the act answers its question. 45380 cites the hedge while another
    sentence states the biopsy done, so the readers disagree and hold it on its status; the done sentence is verified,
    the confirmation is recorded, and the re-assessment makes 45380 ready - never the hedge."""
    corti_codes = (('45380', SLICE_BX),)

    def setUp(self):
        super().setUp()
        self.first(reading(codes=[('45380', SLICE_BX)], services=[('c1', 'colonoscopy', 'performed', DONE_BX)]))

    def test_the_sentence_that_states_the_biopsy_done_is_confirmed(self):
        encounter_id = self.create(DISAGREE)
        drain()
        question = self.status_question(self.final(encounter_id), '45380')
        self.assertEqual(question.proposal.support['reason'], 'readings_disagree')
        candidate = self.candidate_on(encounter_id, question, DONE_BX)
        self.assertEqual((candidate['verified'], candidate['why']), (True, ''))
        response = self.confirm(encounter_id, question, candidate)
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        served = self.served_proposal(encounter_id, '45380')
        row = models.FindingConfirmation.objects.get()
        self.assertEqual((served['status'], served['confirmed'], served['allowed_actions']),
                         ('ready', [str(row.pk)], ['approve', 'reject']))


# --- EV2-1: the one function, read by the engine as by the candidates ------------------------------------------------

def span(text, phrase):
    start = text.index(phrase)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def engine_run(text, codes, confirmed=()):
    selected = tuple(ProviderCode('selected', 'cpt', value, 'UNVERIFIED PROVIDER WORDING', (span(text, quote),))
                     for value, quote in codes)
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, DAY),
                  normalized=NormalizedResponse('corti', 'test@1', selected), reference=REFERENCE, service_date=DAY,
                  provider_status='succeeded', participants=CONFIGURED, confirmed=confirmed)


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class OneCheckTests(SimpleTestCase):
    """reconcile.status_stated is the one check: every status candidate passes it, and engine._Confirmations applies it
    to every status confirmation it is given, however it was made."""

    def status(self, text, code_value, value, passage):
        inventory = gi_services.build(text, service_date=DAY)
        service = inventory.for_family('gi.colonoscopy')[0]
        at = span(text, passage)
        return reconcile.status_stated(inventory, service.id, code_value, 'gi.colonoscopy', value, at.start, at.end,
                                       text)

    def test_what_the_readers_read_decides_and_the_whole_sentence_is_read(self):
        text = (TOP + CECUM + '\n' + HEDGE_BX + '\n' + HEDGE_SN + '\n' + JAR_1 + '\n'
                + 'No biopsies were obtained from the ascending colon lesion.\n'
                + 'A 6 mm polyp in the ascending colon was removed with a cold snare.\n')
        cases = [
            ('45385', 'performed', CECUM, 'the passage does not name the snare removal'),
            ('45385', 'performed', JAR_1, 'the passage does not name the snare removal'),
            ('45385', 'performed', HEDGE_BX, 'the passage does not name the snare removal'),  # another act's hedge
            ('45385', 'performed', SLICE_SN, 'the passage leaves the snare removal in doubt'),
            ('45380', 'performed', 'No biopsies were obtained from the ascending colon lesion.',
             'the passage states the forceps biopsy as not performed, not as performed'),
            ('45380', 'not performed', 'No biopsies were obtained from the ascending colon lesion.', ''),
            ('45385', 'not performed', JAR_1, 'the passage does not name the snare removal'),
            ('45385', 'not performed', 'A 6 mm polyp in the ascending colon was removed with a cold snare.',
             'the passage states the snare removal as performed, not as not performed'),
            ('45385', 'performed', 'A 6 mm polyp in the ascending colon was removed with a cold snare.', ''),
            ('45378', 'performed', CECUM, ''),  # a base code asks about its service
            ('45378', 'performed', HEDGE_BX,
             "CPT Studio's readers read no statement of the colonoscopy in the passage"),
        ]
        for code_value, value, passage, why in cases:
            with self.subTest(code=code_value, value=value, passage=passage):
                self.assertEqual(self.status(text, code_value, value, passage), why)

    def test_no_subject_the_readers_can_check_never_verifies(self):
        text = DISAGREE
        inventory = gi_services.build(text, service_date=DAY)
        at = span(text, DONE_BX)
        for given, service_id in ((None, 'S1'), (inventory, ''), (inventory, 'S9')):
            self.assertEqual(reconcile.status_stated(given, service_id, '45380', 'gi.colonoscopy', 'performed',
                                                     at.start, at.end, text), reconcile.NO_SUBJECT)
        self.assertEqual(reconcile.status_stated(inventory, 'S1', '45380', 'gi.egd', 'performed', at.start, at.end,
                                                 text), reconcile.NO_SUBJECT)  # a service of another family
        self.assertEqual(reconcile.status_stated(inventory, 'S1', '45380', 'gi.colonoscopy', 'performed', at.start,
                                                 at.end, text), '')

    def confirmation(self, text, result, key, passage, value='performed'):
        return ConfirmedFinding('proposal', 'performed_status', 'gi.colonoscopy', key, value, (span(text, passage),),
                                ('astra',), REVIEWER, 'conf-1', **binding(proposal(result, key)))

    def test_the_engine_never_reads_a_status_confirmation_its_readers_do_not_read_on_its_passage(self):
        codes = (('45380', SLICE_BX),)
        before = engine_run(DISAGREE, codes)
        held = proposal(before, 'sel:0')
        self.assertEqual((held.code, held.status, held.support['reason']),
                         ('45380', 'needs_clarification', 'readings_disagree'))
        for passage, why in ((SLICE_BX, 'the passage leaves the forceps biopsy in doubt'),
                             (HEDGE_BX, 'the passage leaves the forceps biopsy in doubt'),
                             (CECUM, 'the passage does not name the forceps biopsy')):
            with self.subTest(passage):
                after = engine_run(DISAGREE, codes, [self.confirmation(DISAGREE, before, 'sel:0', passage)])
                self.assertEqual(proposal(after, 'sel:0').status, 'needs_clarification')
                self.assertNotIn('confirmed', proposal(after, 'sel:0').support)
                self.assertEqual(after.completeness['confirmations'],
                                 {'applied': [], 'ignored': [{'id': 'conf-1', 'why': why}]})
                self.assertIn(why, encounter_check(after, 'confirmations.ignored').detail)
        read_ = engine_run(DISAGREE, codes, [self.confirmation(DISAGREE, before, 'sel:0', DONE_BX)])
        self.assertEqual((proposal(read_, 'sel:0').status, proposal(read_, 'sel:0').support['confirmed']),
                         ('ready', ['conf-1']))


# --- EV2-2 and truth-1 (the plan's D2): an extent, a structure or a basis on a passage about another occasion, or on
# one that denies what it names, is never verified --------------------------------------------------------------------

EARLIER = 'Indication: surveillance; the colonoscopy in 2019 reached the cecum.'
DENIED = 'The cecum was not reached because of poor preparation.'
CUT_SHORT = 'The cecum could not be reached because of a poor preparation.'
POLYP = 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'
FLAT = 'A separate 12 mm flat lesion in the ascending colon was biopsied with cold forceps.'
COLON_HEAD = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
              'Place of service: Ambulatory surgery center\n')
NO_EXTENT = COLON_HEAD + EARLIER + '\nProcedure: Colonoscopy\n' + POLYP + '\n' + FLAT + '\n'
DENIAL = COLON_HEAD + 'Procedure: Colonoscopy\n' + DENIED + '\n' + POLYP + '\n' + FLAT + '\n'
CUT = COLON_HEAD + 'Procedure: Colonoscopy\n' + POLYP + '\n' + FLAT + '\n' + CUT_SHORT + '\n'
SNARE_QUOTE, BIOPSY_QUOTE = 'was removed with a hot snare', 'was biopsied with cold forceps'


def extent_reading(quote, extent='cecum'):
    return empty_reading(codes=[code_item('45385', service_ids=[], evidence=[SNARE_QUOTE]),
                                code_item('45380', service_ids=[], evidence=[BIOPSY_QUOTE])],
                         services=[service_item(1, id='c1', family='colonoscopy', extent=extent, evidence=[quote])])


def answers_extent_with(quote, value='cecum', number=2):
    """A peer review answering 45385's open extent question with ``value``, quoting ``quote``."""
    def answer(body):
        questions = open_questions('astra', body)
        return answered('astra', peer_answer(answers=[(q['question_id'], True, value, quote) for q in questions
                                                      if q['fact'] == 'extent' and q['proposal_key'] == 'sel:0']),
                        number)
    return answer


class ExtentEvidenceTests(EvidenceCase):
    corti_codes = (('45385', SNARE_QUOTE), ('45380', BIOPSY_QUOTE))

    def extent_question(self, encounter_id):
        return self.final(encounter_id).clarifications.get(proposal__code='45385', fact='extent',
                                                           state=models.Clarification.OPEN)

    def test_an_earlier_procedure_s_indication_line_never_verifies_today_s_extent(self):
        """EV2-2 (a): no extent is documented today; Astra's extent 'cecum' quotes the indication's 2019 colonoscopy."""
        self.first(extent_reading(EARLIER))
        encounter_id = self.create(NO_EXTENT)
        drain()
        question = self.extent_question(encounter_id)
        candidate = self.candidate_on(encounter_id, question, EARLIER, value='cecum')
        self.assertRefusedNotReady(encounter_id, question, candidate, 'The passage is in an indication section, which '
                                   'never documents a service at this encounter.', '45385')

    def test_a_passage_that_denies_the_landmark_never_verifies_it(self):
        """EV2-2 (b): the note says the cecum was not reached; Astra's extent 'cecum' quotes that denial."""
        self.first(extent_reading(DENIED))
        encounter_id = self.create(DENIAL)
        drain()
        question = self.extent_question(encounter_id)
        candidate = self.candidate_on(encounter_id, question, DENIED, value='cecum')
        self.assertRefusedNotReady(encounter_id, question, candidate,
                                   'The passage states the cecum as not reached or not seen.', '45385')

    def test_a_peer_answer_quoting_a_slice_of_the_denial_never_verifies_it(self):
        """truth-1 (s6): Astra's peer review answers the extent 'cecum', quoting "The cecum could not be reached"."""
        self.first(reading(codes=[('45385', SNARE_QUOTE)], services=[('c1', 'colonoscopy', 'performed', POLYP)]),
                   astra_peer=answers_extent_with('The cecum could not be reached'))
        encounter_id = self.create(CUT)
        drain()
        question = self.extent_question(encounter_id)
        candidate = self.candidate_on(encounter_id, question, 'The cecum could not be reached', value='cecum')
        self.assertRefusedNotReady(encounter_id, question, candidate,
                                   'The passage states the cecum as not reached or not seen.', '45385')
        start = CUT.index(CUT_SHORT)
        self.assertEqual(candidate['sentences'], [{'start': start, 'end': start + len(CUT_SHORT), 'text': CUT_SHORT}])


PRIOR = 'At the visit on 2026-03-02, total time was 45 minutes.'
VISIT = 'Established patient office visit for follow-up of reflux.'
NO_BASIS = (HEAD + 'Office visit note (fictional)\nDate of service: 2026-10-20\nPlace of service: Office\n' + VISIT
            + '\nHistory: ' + PRIOR + '\nAssessment: reflux, stable on current therapy.\nPlan: continue omeprazole.\n')


class BasisEvidenceTests(EvidenceCase):
    """EV2-2 (c): no time and no MDM are documented for today; Astra's office visit quotes an earlier visit's time."""
    corti_codes = (('99214', VISIT),)

    def setUp(self):
        super().setUp()
        self.first(empty_reading(codes=[code_item('99214', service_ids=[], evidence=[VISIT])],
                                 services=[service_item(1, id='v1', family='office_em', evidence=[PRIOR])]))

    def test_an_earlier_visit_s_time_never_verifies_today_s_basis(self):
        encounter_id = self.create(NO_BASIS)
        drain()
        question = self.final(encounter_id).clarifications.get(fact='em_basis', state=models.Clarification.OPEN)
        candidate = self.candidate_on(encounter_id, question, PRIOR, value='time')
        self.assertRefusedNotReady(encounter_id, question, candidate, 'The passage is in a history section, which '
                                   'never documents a service at this encounter.', '99214')


# --- EV2-3 (the plan's D2): a date of birth, or a history date, is never offered as the date of service ---------------

DOB = 'Date of birth: 1960-01-05'
PRIOR_DATE = 'History: Prior colonoscopy on 2025-03-14 showed two adenomas.'


def undated(line):
    return (HEAD + 'Colonoscopy report (fictional)\nPatient: Synthetic Person\n' + line + '\n'
            'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n' + CECUM + '\n' + POLYP + '\n')


class DateEvidenceTests(EvidenceCase):
    corti_codes = (('45385', SNARE_QUOTE),)

    def date_case(self, line, value, quote, why):
        self.first(reading(codes=[('45385', SNARE_QUOTE)], services=[('c1', 'colonoscopy', 'performed', POLYP)],
                           date_value=value, date_evidence=[quote]))
        encounter_id = self.create(undated(line))
        drain()
        question = self.final(encounter_id).clarifications.get(scope='encounter', fact='service_date',
                                                               state=models.Clarification.OPEN)
        self.assertEqual(question.question, 'Confirm the date of service for this encounter.')
        sent = len(self.corti.requests)
        candidate = self.candidate_on(encounter_id, question, quote, value=value)
        self.assertEqual((candidate['verified'], candidate['why'], candidate['attestation']), (False, why, ''))
        response = self.confirm(encounter_id, question, candidate)
        self.assertEqual(response.status_code, 409, response.content)
        # moved by the customer interface change (CORE-UX-DESIGN.md 5): a member is told the refusal's fixed head; the
        # candidate's reason, composed from stored readings, stays on the operator payload (candidate['why'])
        self.assertEqual(response.json()['error'], NOT_VERIFIED.rstrip(': ') + '.')
        drain()
        encounter = self.encounter(encounter_id)
        # nothing entered the context and nothing more was sent: the date of service is still asked
        self.assertEqual((encounter.user_values, len(self.corti.requests)), ({}, sent))
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'missing')
        self.assertFalse(models.FindingConfirmation.objects.exists())

    def test_a_date_of_birth_is_never_the_date_of_service(self):
        self.date_case(DOB, '1960-01-05', DOB, 'The passage states 1960-01-05 as a date of birth, and a date of '
                                               'birth is never a date of service.')

    def test_a_history_date_is_never_the_date_of_service(self):
        self.date_case(PRIOR_DATE, '2025-03-14', 'Prior colonoscopy on 2025-03-14 showed two adenomas.',
                       'The passage is in a history section, which never documents a service at this encounter.')


# --- truth-10 (the plan's D3): no candidate, no control and no confirmation for an assessment of an earlier context ---

PAGE_NODE = r"""
const app = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const doc = JSON.parse(input);
  process.stdout.write(JSON.stringify({codes: app.reviewView(doc, app.documentLayout(doc), 'codes', true)}));
});
"""


def page(detail):
    """The Suggestions tab as the shipped app.js renders the served detail (node runs the file)."""
    import shutil
    import subprocess
    from django.conf import settings

    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the page checks need it')
    app = f'{settings.BASE_DIR}/studio/operator/ops.js'
    done = subprocess.run([node, '-e', PAGE_NODE, app], input=json.dumps(detail), capture_output=True, text=True,
                          timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-3000:])
    return json.loads(done.stdout)['codes']


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class ContextChangedTests(ColonCase):
    """truth-10 (s5): the colon chain to phase 2, then a member's context change, then Stop. The live assessment is the
    earlier context's, which no re-assessment would read: the page offers no candidate and no control, and the endpoint
    refuses at once, saying why."""

    def test_no_candidate_is_offered_and_the_confirmation_is_refused_with_why(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        final = self.encounter(encounter_id).current_assessment
        question = final.clarifications.get(proposal__key='sel:0', fact='extent', state=models.Clarification.OPEN)
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        served = next(c for c in detail['clarifications'] if c['id'] == str(question.pk))['candidates']
        candidate = next(c for c in served if c['verified'])  # the control: offered while the context is current
        self.assertIn('data-action="confirm-finding"', page(detail))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'billing_context': 'professional'}).status_code, 201)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        encounter = self.encounter(encounter_id)
        self.assertEqual((encounter.current_assessment, encounter.state), (final, 'stopped'))
        self.assertNotEqual(final.context_id, encounter.current_context_id)
        detail = self.client.get(f'/ops/api/encounters/{encounter_id}').json()
        self.assertEqual((detail['pipeline']['busy'], detail['permissions']['can_confirm']), (False, True))
        self.assertEqual([c['candidates'] for c in detail['clarifications']], [[] for _ in detail['clarifications']])
        self.assertNotIn('data-action="confirm-finding"', page(detail))
        self.assertEqual(review.assessment_candidates(final), {})
        response = self.post(f'/api/encounters/{encounter_id}/clarifications/{question.pk}/confirm',
                             {'candidate_id': candidate['id'], 'attestation': candidate['attestation']})
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error'], review.CONTEXT_CHANGED)
        self.assertEqual(review.CONTEXT_CHANGED, 'The encounter context changed after this assessment; resume '
                                                 'processing and confirm on its new assessment.')
        self.assertFalse(models.FindingConfirmation.objects.exists())
        self.assertFalse(models.AuditEvent.objects.filter(event='finding.confirmed').exists())
        # the re-assessment's own refusal says the same, never that there is no assessment
        with self.assertRaisesMessage(jobs.Refused, jobs.REASSESS_CONTEXT):
            jobs.reassess_after_confirmation(encounter, self.reviewer)
        self.assertNotEqual(jobs.REASSESS_CONTEXT, jobs.REASSESS_NONE)
        self.assertEqual(jobs.REASSESS_NONE, 'The current revision has no final assessment to make again.')


# --- truth-7 (the shared wording): the engine never says Corti did not propose a code Corti listed --------------------

def lead_run(text, corti, participants, **second):
    """``corti``: (role, code, quote) of the proposal provider's answer; ``participants``: participant inputs;
    ``second``: a bounded second review (second=, second_scope=), if any."""
    def located(quote):
        return (span(text, quote),) if quote in text else (EvidenceSpan(0, 0, len(quote), quote, False),)
    codes = tuple(ProviderCode(role, 'cpt', value, 'UNVERIFIED PROVIDER WORDING', located(quote))
                  for role, value, quote in corti)
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, DAY),
                  normalized=NormalizedResponse('corti', 'test@1', codes), reference=REFERENCE, service_date=DAY,
                  provider_status='succeeded', participants=participants, **second)


class CortiLeadTests(SimpleTestCase):
    """How a participant's code that Corti did not select is worded beside Corti's own entry of the code. Moved by
    refutation round 6 (R6-MEANING, the session's D14): it was a proposal of its own whose rationale's first sentence
    (_Harness._lead) said how Corti stood to the code - listed as a candidate, selected with no exact passage, listed by
    its second review, or "Corti did not propose this code." only where Corti had no entry. A participant's code is
    never a proposal now: it is listed as an alternative, with CPT Studio's own reason, and its sentences say nothing of
    Corti, so none can misstate Corti's entry; Corti's own entry is listed as before."""
    TEXT = COLON_HEAD + 'Procedure: Colonoscopy\n' + CECUM + '\n' + POLYP + '\n' + FLAT + '\n'

    def participant(self, value, quote):
        from tests.test_harness_engine import code as participant_code, read
        return [read('astra', [participant_code(self.TEXT, value, quote)])]

    def listed(self, corti, **second):
        result = lead_run(self.TEXT, corti, self.participant('45380', BIOPSY_QUOTE), **second)
        (theirs,) = [p for p in result.proposals if p.code == '45380' and p.support.get('origin') == 'participant']
        self.assertEqual((theirs.key, theirs.bucket, theirs.status), ('altp:0', 'alternative', 'informational'))
        self.assertEqual(theirs.exclusion_reason, 'Proposed by Astra (independent participant), but not added as a '
                                                  f'proposal: {engine.PARTICIPANT_NOT_ADDED}. Alternatives cannot be '
                                                  'approved.')
        for said in (theirs.exclusion_reason, theirs.rationale):
            self.assertNotIn('Corti', said)
        self.assertFalse(any(p.code == '45380' and p.bucket == 'selected' for p in result.proposals))
        return result

    def test_a_code_corti_listed_only_as_a_candidate_is_said_so(self):
        result = self.listed((('selected', '45385', SNARE_QUOTE), ('candidate', '45380', BIOPSY_QUOTE)))
        self.assertEqual([(p.key, p.code) for p in result.proposals if p.bucket == 'alternative'],
                         [('alt:0', '45380'), ('altp:0', '45380')])

    def test_a_code_corti_selected_with_no_exact_passage_is_said_so(self):
        result = self.listed((('selected', '45385', SNARE_QUOTE),
                              ('selected', '45380', 'a passage the document does not hold')))
        self.assertEqual([(p.key, p.bucket, p.exclusion_reason) for p in result.proposals if p.key == 'exc:0'],
                         [('exc:0', 'excluded', engine.NO_EVIDENCE)])

    def test_corti_did_not_propose_a_code_only_where_it_has_no_entry_for_it(self):
        result = self.listed((('selected', '45385', SNARE_QUOTE),))
        self.assertEqual([p.code for p in result.proposals], ['45385', '45380'])

    def test_a_code_only_corti_s_second_review_listed_is_said_so(self):
        # Corti's bounded second review lists 45380 only as a candidate (alt2:0) and Astra proposes it from the biopsy
        # passage: both are listed, each saying whose it is (R2-WORDING's NEEDS 2 on truth-7)
        text = self.TEXT
        second = NormalizedResponse('corti', 'test@1', (ProviderCode('candidate', 'cpt', '45380', '',
                                                                     (span(text, BIOPSY_QUOTE),)),))
        scope = {'start': text.index('Procedure: Colonoscopy'), 'end': len(text), 'items': ['the flat lesion biopsy']}
        result = self.listed((('selected', '45385', SNARE_QUOTE),), second=second, second_scope=scope)
        self.assertEqual([(p.key, p.code) for p in result.proposals if p.support.get('origin') == 'second_review'],
                         [('alt2:0', '45380')])


# --- FG2-1: a confirmation's identity binds its context too (HARNESS.md 12.5, 12.7) ----------------------------------

DATE_LINE = 'Date of service: 2026-10-14\n'


# The dormant confirmation path (HARNESS.md 12.10): this release offers no reviewer confirmation; these tests
# run that path with its setting on and keep their assertions.
@override_settings(STUDIO_OFFER_CONFIRMATIONS=True)
class ConfirmationAcrossChangesCase(ColonCase):
    """The pipeline suite's colon case: Corti selects 45385 and 45380, both held on the extent, and Astra's peer review
    answers 45385's with the landmark passage, which a reviewer confirms through the endpoint."""

    def detail(self, encounter_id):
        return self.client.get(f'/ops/api/encounters/{encounter_id}').json()

    def confirm_extent(self, encounter_id, user=None):
        detail = self.detail(encounter_id)
        snare = next(p['id'] for p in detail['assessment']['proposals'] if p['key'] == 'sel:0')
        question = next(c for c in detail['clarifications'] if c['proposal_id'] == snare and c['fact'] == 'extent')
        candidate = next(c for c in question['candidates'] if c['verified'])
        client = self.client
        if user is not None:
            client = Client()
            client.force_login(user)
        response = client.post(f'/api/encounters/{encounter_id}/clarifications/{question["id"]}/confirm',
                               data=json.dumps({'candidate_id': candidate['id'],
                                                'attestation': candidate['attestation']}),
                               content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return models.FindingConfirmation.objects.get(clarification_id=question['id']), response.json()

    def snare(self, assessment):
        return [(p.key, p.status, (p.support or {}).get('confirmed')) for p in
                assessment.proposals.filter(code='45385').order_by('position')]


class IdentityContextTests(ConfirmationAcrossChangesCase):
    def test_a_confirmation_made_under_one_member_date_is_not_read_under_another(self):
        """FG2-1 (a): the identity includes the service date (12.7), so the confirmation made under 2026-10-14 is not
        read once the member saves 2026-10-21, and each later assessment says why; 45385 is asked its extent again."""
        self.assertEqual(TWO_EXTENTS.count(DATE_LINE), 1)
        encounter_id = self.create(TWO_EXTENTS.replace(DATE_LINE, ''), service_date='2026-10-14')
        drain()
        confirmation, _ = self.confirm_extent(encounter_id)
        self.assertEqual(self.snare(self.encounter(encounter_id).current_assessment),
                         [('sel:0', 'ready', [str(confirmation.pk)])])
        before = len(self.assessments(encounter_id))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-21'}).status_code, 201)
        drain()
        later = self.assessments(encounter_id)[before:]
        self.assertEqual([jobs.assessment_phase(a) for a in later], [1, 2])
        for assessment in later:
            self.assertEqual(assessment.context.user_values.get('service_date'), '2026-10-21')
            self.assertEqual(self.snare(assessment), [('sel:0', 'needs_clarification', None)])
            self.assertEqual(assessment.completeness['confirmations'],
                             {'applied': [], 'ignored': [{'id': str(confirmation.pk), 'why': engine.MOVED}]})
            # each raises 45385's extent question again (assess #1's is withdrawn once assess #2 asks it)
            self.assertTrue(assessment.clarifications.filter(proposal__key='sel:0', fact='extent').exists())
        self.assertTrue(later[-1].clarifications.filter(proposal__key='sel:0', fact='extent',
                                                        state=models.Clarification.OPEN).exists())


# --- FG2-2: a new revision reads and lists no confirmation of an earlier one (HARNESS.md 11.3, 12.5) ------------------

ADDENDUM = 'Addendum (synthetic): the patient tolerated the procedure well.'
CONTRADICTING = ('Addendum (synthetic): correction - the cecum was not reached; the examination ended in the '
                 'transverse colon because of poor preparation.')


class NewRevisionTests(ConfirmationAcrossChangesCase):
    def to_revision_two(self, addendum):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        confirmation, _ = self.confirm_extent(encounter_id)
        self.assertEqual(self.snare(self.encounter(encounter_id).current_assessment),
                         [('sel:0', 'ready', [str(confirmation.pk)])])
        before = len(self.assessments(encounter_id))
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': addendum, 'clarification_id': None, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        revision = self.encounter(encounter_id).current_revision
        first = models.SourceRevision.objects.get(encounter_id=encounter_id, number=1)
        self.assertEqual(revision.number, 2)
        self.assertTrue(revision.text.startswith(first.text))  # revision 1's spans are still exact slices of it
        return encounter_id, revision, self.assessments(encounter_id)[before:]

    def txt_section(self, encounter_id, title):
        from studio import reports
        lines = reports.render_txt(reports.snapshot(self.encounter(encounter_id), 'draft')).decode('utf-8').split('\n')
        start = lines.index(title) + 1
        return lines[start:lines.index('', start)]

    def test_the_assessments_of_a_new_revision_read_no_earlier_confirmation(self):
        """FG2-2 (a): jobs.confirmed_findings filters by revision, so both of revision 2's assessments hold 45385 on its
        extent again - also against an addendum that contradicts the confirmed extent."""
        for addendum in (ADDENDUM, CONTRADICTING):
            with self.subTest(addendum=addendum[:40]):
                encounter_id, revision, later = self.to_revision_two(addendum)
                self.assertEqual(jobs.confirmed_findings(revision), ())
                self.assertEqual([jobs.assessment_phase(a) for a in later], [1, 2])
                for assessment in later:
                    self.assertEqual(assessment.revision_id, revision.pk)
                    self.assertEqual(self.snare(assessment), [('sel:0', 'needs_clarification', None)])
                    self.assertNotIn('confirmations', assessment.completeness)
                    self.assertNotIn('confirmations.applied', [c['id'] for c in assessment.encounter_checks])

    def test_the_page_and_the_report_list_no_earlier_revision_s_confirmation(self):
        """FG2-2 (b): review.revision_confirmations filters by revision: the new revision's detail lists none, and the
        draft report's CONFIRMED FINDINGS says so."""
        encounter_id, revision, _ = self.to_revision_two(ADDENDUM)
        detail = self.detail(encounter_id)
        self.assertEqual(detail['confirmations'], [])
        self.assertEqual([c['confirmation'] for c in detail['clarifications']], [None] * len(detail['clarifications']))
        self.assertEqual(review.revision_confirmations(revision), [])
        self.assertEqual(self.txt_section(encounter_id, 'CONFIRMED FINDINGS'),
                         ['  None: no reviewer has confirmed a finding for this revision.'])


# --- FG2-4: an agent's confirmation is served and reported as an agent's ----------------------------------------------

class AgentConfirmationTests(ConfirmationAcrossChangesCase):
    def test_an_agent_reviewer_s_confirmation_is_labelled_an_agent_s_everywhere(self):
        import csv
        import io

        from studio import reports
        from tests.support import factories as f

        agent = f.member(self.ws, f.user('agent2r', actor_kind=models.User.AGENT))
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        with mock.patch('studio.jobs.reassess_after_confirmation'):  # the question stays shown with its confirmation
            confirmation, made = self.confirm_extent(encounter_id, user=agent)
        label = agent.label()
        self.assertTrue(label.endswith('(automated agent)'), label)
        self.assertEqual((made['confirmed_by'], made['confirmed_by_kind']), (label, 'agent'))
        detail = self.detail(encounter_id)
        self.assertEqual([(c['confirmed_by'], c['confirmed_by_kind']) for c in detail['confirmations']],
                         [(label, 'agent')])
        snap = reports.snapshot(self.encounter(encounter_id), 'draft')
        lines = reports.render_txt(snap).decode('utf-8').split('\n')
        start = lines.index('CONFIRMED FINDINGS') + 1
        line = next(text for text in lines[start:lines.index('', start)] if 'confirmed by' in text)
        self.assertIn(f'confirmed by {label} at ', line)
        self.assertNotIn('(human)', line)
        rows = list(csv.reader(io.StringIO(reports.render_csv(snap).decode('utf-8'), newline='')))
        header = rows[0]
        named = [dict(zip(header, row)) for row in rows[1:] if len(row) == len(header) and label in row]
        self.assertTrue(named)
        self.assertEqual({row['reviewer_kind'] for row in named}, {'agent'})
        # the page, rendering the served payload, tags it as an agent's synthetic review, never clinical approval
        self.assertIn('agent-executed synthetic review — not clinical approval', page(detail))
