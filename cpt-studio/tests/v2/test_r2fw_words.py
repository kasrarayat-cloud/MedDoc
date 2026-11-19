"""r2f (DECISIONS D309, round r2f lane W: the member words' repairs RFEW-1..5 and e-words' Q1). SYNTHETIC only: tests/v2's
own FactSet builders over test_assess's synthetic letters (r2w_world: the renderer's child, persist, read time, the
customer payload, the details door and the AGAIN recompute); nothing is sent anywhere.

Each rule the round builds, with an input it must change and a boundary it must leave alone:

- RFEW-1 (D301 RBWX-2, D309): an examination is "the examination of this procedure" only when it is the examination of
  one of the code's OWN ESTABLISHED sessions - with none established (an E/M visit told with its own session unresolved
  or silent) another session's examination is another act, by its kind, asked the same question; and an examination act
  is in one of the code's sessions only when that session may hold an examination: a session holding an established
  E/M visit holds none (facts.family_kinds), whatever its kind fact says;
- RFEW-2: a session id the FactSet does not hold is unknown - possibly any session, as engine/classes reads it - never
  another session: the examination whose slot names one is named on every code of its session as the code that binds
  it names it;
- RFEW-3 (D297 W2R-3, D303 I2): a service fact's row is one per SESSION whenever codes of two sessions of one family ask
  it - one "Not documented" excludes one session's code;
- RFEW-5: a code a member's answer excluded says why by the state of that answer - never "until that answer is
  withdrawn" once it was withdrawn;
- e-words' Q1 (D303 I1 strictly): NOT_DOCUMENTED and UNLISTED_EVIDENCE ask performed_question(code), so they sit on the
  row that asks exactly that question - the SUPPORTED form's;
- RFEW-4's corpus control: over the RFEW scenes and every one-fact perturbation, every item's recorded form is the one an
  INDEPENDENT reading of its message, slots and the FactSet gives (the rulings' terms, written here: never the product's
  naming rule)."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio import answers, customer_api, jobs, models
from studio.interpretation import wording
from studio.interpretation.contract import types as ct
from studio.interpretation.contract.types import Attribute, FactState, Kind, Result, SessionKind
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine.requirements_table import FAMILY_KINDS
from studio.interpretation.engine.types import Id, IdFamily
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_evaluate as TE
from tests.v2 import test_overlay as TO
from tests.v2 import test_questions as TQ
from tests.v2.r2w_world import R2WWorld

ND = models.MemberAnswer.NOT_DOCUMENTED
# test_assess's synthetic letters with a space every seventh character, so a code's own passages have words to show
TEXT = ''.join(' ' if index % 7 == 6 else TA.TEXT[index] for index in range(len(TA.TEXT)))
THIS_PROCEDURE = 'the examination of this procedure'
DONE_IN_PART = 'documented as performed, in full or in part, on the date of service'
# the rows' words, as the design words them (FINAL-V2 4.8; D281 B6, D297, D303) - by value, so the module imports on the
# reference tree
OTHER_TIME = 'Was the examination done at this encounter, on the date of service?'
OTHER_TIME_MISSING = 'whether the examination was done at this encounter'
OTHER_DOUBT = f'Is the examination {DONE_IN_PART}?'
OTHER_DOUBT_MISSING = 'that the examination was performed, in full or in part, on the date of service'
OWN_DOUBT = f'Is {THIS_PROCEDURE} {DONE_IN_PART}?'
SUPPORTED_PROMPT = 'Is this code supported by what was done on the date of service?'
SUPPORTED_MISSING = 'that this code is supported by what was done on the date of service'
STATUS_KEY_PROMPT = 'Was this procedure performed on the date of service, as documented?'
STANDING_WORDS = ('A detail this code needs was answered as not documented or not confirmable, so it is excluded until '
                  'that answer is withdrawn.')
WITHDRAWN_WORDS = ('A detail this code needs was answered as not documented or not confirmable; that answer was '
                   'withdrawn, and the update that applies the withdrawal has not run yet.')


def offsets(row):
    return [(passage['start'], passage['end']) for passage in row['passages']]


def statement(missing):
    return f'From the document, CPT Studio could not confirm {missing}.'


def qualification(missing):
    return f'CPT Studio could not confirm from the document {missing}.'


# --- the scenes -------------------------------------------------------------------------------------------------------

def late_visit(visit_session=None):
    """test_overlay.office_and_undated_colonoscopy (an office visit X1 and 99213's visit E1; a colonoscopy X2 to the cecum
    whose examination E2 and cold snare E3 are undated) with the visit told after the colonoscopy (unit 9) and, when
    given, the visit's own session replaced by ``visit_session``; X2 stays established as E2's session (RFEW-1's P1)."""
    doc = TO.office_and_undated_colonoscopy()
    over = dict(basis=EF.sup(ct.EmBasis.MEDICAL_DECISION_MAKING), anchor=(EF.unit(9),))
    if visit_session is not None:
        over['session'] = visit_session
    doc.act(1, ct.Kind.EM_VISIT, **over)
    return doc


def visit_kind_unplaced(exam_session, x1_kind=None):
    """An office session X1 whose kind is ``x1_kind`` (unresolved office E/M by default) holding the established visit E1
    (unit 9); a colonoscopy X2 to the cecum whose examination E2 has session ``exam_session`` and no date relation, and a
    cold snare E3 in X2, undated (RFEW-1's P1b; RFEW-4's B)."""
    doc = EF.Doc()
    doc.session(1, x1_kind or EF.unres(ct.SessionKind.OFFICE_EM), encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, ct.Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.MEDICAL_DECISION_MAKING), anchor=(EF.unit(9),))
    doc.session(2, ct.SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
    doc.exam(2, session=exam_session, date=None)
    doc.lesion(1, lesion_places=[EF.sup(ct.Landmark.SIGMOID_COLON)])
    doc.act(3, ct.Kind.SNARE, session=EF.X(2), places=[EF.sup(ct.Landmark.SIGMOID_COLON)], lesion=EF.sup(EF.L(1)),
            device=EF.sup(ct.Device.COLD_SNARE), date=None)
    return doc


def exam_status(session_fact, kind=None):
    """EF.colonoscopy (X1 to the cecum: examination E1, the cold snare E2 of L1) with E1's status unresolved and its session
    slot ``session_fact``; ``kind``, when given, X1's kind fact (RFEW-2's P3; RFEW-4's C)."""
    doc = EF.colonoscopy()
    if kind is not None:
        doc.session(1, kind, reached=[EF.sup(ct.Extent.CECUM)])
    doc.exam(1, session=session_fact, status=EF.unres(ct.Status.PERFORMED))
    return doc


EXAM_CODES = (('45385', 2), ('45378', 1))


class Built:
    """A FactSet already built, read as a builder (``.build()``)."""

    def __init__(self, R):
        self.R = R

    def build(self):
        return self.R


def dre_unknown_session(session_fact):
    """test_questions.dre_shape: a colonoscopy X1 whose claimed digital examination E1 (device manual unresolved, status
    unresolved) has session slot ``session_fact``, beside the snare E2 (45385), the colonoscope's examination E3 and a
    biopsy: 45385's DIGITAL_SCOPE item names the held session's examination (D280.3)."""
    return Built(TQ.dre_shape({'device': EF.unres(ct.Device.MANUAL), 'status': EF.unres(ct.Status.PERFORMED),
                               'session': session_fact}))


def colonoscopies(sessions=2):
    """``sessions`` colonoscopies on the date of service, each reach unresolved: X1 (examination E1, a forceps biopsy E2 of
    L1 in the transverse colon: 45380) and, for two, X2 (examination E3, a cold snare E4 of L2 in the sigmoid colon:
    45385); for one, both acts in X1 (L7-08's one colonoscopy) (RFEW-3's P2 and its boundary)."""
    doc = EF.Doc()
    for number in range(1, sessions + 1):
        doc.session(number, ct.SessionKind.COLONOSCOPY, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER),
                    reached=[EF.unres(ct.Extent.CECUM)])
    doc.exam(1, session=EF.X(1))
    if sessions == 2:
        doc.exam(3, session=EF.X(2))
    for act, lesion, place, kind, device, session in (
            (2, 1, ct.Landmark.TRANSVERSE_COLON, ct.Kind.BIOPSY, ct.Device.FORCEPS, 1),
            (4, 2, ct.Landmark.SIGMOID_COLON, ct.Kind.SNARE, ct.Device.COLD_SNARE, sessions)):
        doc.lesion(lesion, lesion_places=[EF.sup(place)])
        doc.act(act, kind, session=EF.X(session), places=[EF.sup(place)], lesion=EF.sup(EF.L(lesion)),
                device=EF.sup(device))
    return doc


SERVICE_CODES = (('45380', 2), ('45385', 4))


def exchange():
    """test_evaluate's 3.2.6 exchange: an ERCP X1 whose placement E2 is filed and pass 2's unlisted removal act kept in its
    unit: 43274 on unit 2 is held by rule 2's UNLISTED_EVIDENCE."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.ERCP)
    doc.exam(1)
    doc.act(2, ct.Kind.STENT, duct=EF.sup(ct.Duct.BILIARY))
    doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.STENT_REMOVAL, EF.X(1), EF.unit(2)))
    return doc


def snare_status():
    """EF.colonoscopy with the snare E2's own status unresolved: 45385's STATUS about its own act (the status key row)."""
    doc = EF.colonoscopy()
    doc.act(2, ct.Kind.SNARE, session=EF.X(1), places=[EF.sup(ct.Landmark.SIGMOID_COLON)], lesion=EF.sup(EF.L(1)),
            device=EF.sup(ct.Device.COLD_SNARE), status=EF.unres(ct.Status.PERFORMED))
    return doc


# --- RFEW-1: no established session of the code's own makes no examination its own ---------------------------------

class R2FWCodeSessionNotEstablished(R2WWorld):
    """RFEW-1's P1: 99213's visit E1 told late with its own session unresolved (X1 claimed) or silent, held by the same-day
    rule's date question about E2, the colonoscopy X2's examination (X2 established). The visit's session is not
    established, so E2 is another act - "the examination" - asked its date, on the row, its statement, the code's
    qualification, through the door and after the AGAIN."""

    def walk(self, visit_session):
        scene = self.scene(late_visit(visit_session).build(), (('99213', 9),), text=TEXT)
        stored = self.proposal(scene, '99213')
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '99213')
        self.assertEqual(row['prompt'], OTHER_TIME)  # behaviour first (red: "the examination of this procedure")
        self.assertEqual((row['missing'], row['statement']), (OTHER_TIME_MISSING, statement(OTHER_TIME_MISSING)))
        self.assertEqual((stored.support['item']['form'], stored.support['item']['act_ref'].get('act')),
                         ('act_time', 'examination'))
        quals = self.code_row(payload, '99213')['why']['qualifications']
        self.assertIn(qualification(OTHER_TIME_MISSING), quals)
        self.assertFalse(any(THIS_PROCEDURE in sentence for sentence in quals))
        self.assertIn((200, 260), offsets(row))  # E2's own words
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])
        self.assertEqual(self.views(scene)['99213'].status, 'excluded')
        self.again(scene)
        [row] = self.rows_of(self.payload(scene), '99213')
        self.assertEqual((row['prompt'], row['saved']['value']), (OTHER_TIME, ND))

    def test_rfw_the_visits_session_unresolved(self):
        self.walk(EF.unres(EF.X(1)))

    def test_rfw_the_visits_session_silent(self):
        self.walk(EF.SILENT)

    def test_boundary_the_visits_session_established(self):
        """RBWX-2's own row (both trees): the visit's session established, the same-day item's examination another act."""
        scene = self.scene(late_visit(None).build(), (('99213', 9),), text=TEXT)
        [row] = self.rows_of(self.payload(scene), '99213')
        self.assertEqual(row['prompt'], OTHER_TIME)

    def test_boundary_the_codes_own_sessions_examination(self):
        """45385's STATUS about its own colonoscopy's examination E1 (established in X1, 45385's session): the examination
        of this procedure (both trees)."""
        scene = self.scene(exam_status(EF.X(1)).build(), EXAM_CODES, text=TEXT)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual(row['prompt'], OWN_DOUBT)


class R2FWVisitSessionHoldsNoExamination(R2WWorld):
    """RFEW-1's P1b: 99213's visit E1 established in X1, X1's kind not established (unresolved office E/M, or silent),
    beside the colonoscopy X2's examination E2 whose session slot is not established (silent, or unresolved claiming
    X1). X1 holds an established E/M visit, so no family it may be of holds an examination: E2 is another act - asked row
    7's done (DONE_IN_PART), its name "the examination"."""

    def walk(self, exam_session, x1_kind=None):
        scene = self.scene(visit_kind_unplaced(exam_session, x1_kind).build(), (('99213', 9),), text=TEXT)
        stored = self.proposal(scene, '99213')
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '99213')
        self.assertEqual(row['prompt'], OTHER_DOUBT)  # behaviour first (red: "the examination of this procedure")
        self.assertEqual(row['statement'], statement(OTHER_DOUBT_MISSING))
        self.assertEqual((stored.support['item']['form'], stored.support['item']['act_ref'].get('act')),
                         ('act_doubt', 'examination'))
        self.assertIn(qualification(OTHER_DOUBT_MISSING), self.code_row(payload, '99213')['why']['qualifications'])
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])

    def test_rfw_kind_unresolved_examination_silent(self):
        self.walk(EF.SILENT)

    def test_rfw_kind_silent_examination_claiming_the_office(self):
        self.walk(EF.unres(EF.X(1)), EF.SILENT)

    def test_boundary_a_procedure_session_of_unresolved_kind(self):
        """45385's snare established in X1, X1's kind unresolved (colonoscopy claimed), the examination E1's slot silent: an
        established snare leaves families that hold an examination, so E1 is the examination of this procedure (both
        trees)."""
        scene = self.scene(exam_status(EF.SILENT, EF.unres(ct.SessionKind.COLONOSCOPY)).build(), EXAM_CODES, text=TEXT)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual(row['prompt'], OWN_DOUBT)


# --- RFEW-2: an id the FactSet does not hold is unknown, never another session --------------------------------------

class R2FWUnknownSessionId(R2WWorld):
    """RFEW-2's P3: the colonoscopy's examination E1, its status unresolved, its session slot naming X9 - a session the
    FactSet does not hold (unresolved or supported). 4.11: an unknown id is possibly any session, never another one, so
    45385 (the snare, in X1) names E1 as 45378 (which binds E1) does: the examination of this procedure."""

    def walk(self, session_fact):
        scene = self.scene(exam_status(session_fact).build(), EXAM_CODES, text=TEXT)
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '45385')
        [own] = self.rows_of(payload, '45378')
        self.assertEqual(row['prompt'], OWN_DOUBT)  # behaviour first (red: "the examination", another act)
        self.assertEqual((row['prompt'], row['statement']), (own['prompt'], own['statement']))
        stored = self.proposal(scene, '45385')
        self.assertEqual(stored.support['item']['form'], 'session_status')
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])

    def test_rfw_unresolved_naming_an_unknown_session(self):
        self.walk(EF.unres(EF.X(9)))

    def test_rfw_supported_unknown_session(self):
        self.walk(EF.sup(EF.X(9)))

    def test_rfw_digital_scope_whose_claimed_examination_names_an_unknown_session(self):
        """The held-session arm (D280.3): the claimed digital examination's session supported as X9, which the FactSet
        does not hold - unknown, so the held session is not another session: 45385's DIGITAL_SCOPE row names the
        examination of this procedure (the held session engine/questions names is read as unknown)."""
        scene = self.scene(dre_unknown_session(EF.sup(EF.X(9))).build(), (('45385', 2),), text=TEXT)
        stored = self.proposal(scene, '45385')
        self.assertEqual(stored.support['item']['message'], 'digital_scope')
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual(row['prompt'], OWN_DOUBT)  # behaviour first (red: "the examination", another act)
        self.assertEqual(stored.support['item']['form'], 'digital_scope')

    def test_boundary_unresolved_naming_the_codes_session(self):
        """WX3-1's own shape (both trees): E1's slot unresolved claiming X1, 45385's session - the examination of this
        procedure."""
        scene = self.scene(exam_status(EF.unres(EF.X(1))).build(), EXAM_CODES, text=TEXT)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual(row['prompt'], OWN_DOUBT)


class R2FWUnknownSessionSubject(SimpleTestCase):
    """RFEW-2 on the session-subject arm: an item whose held subject is a session id the FactSet does not hold (X9) reads
    it as unknown - possibly any session, so possibly 45385's own colonoscopy X1 (which may hold an examination) - never
    as another session; a subject that IS another established session stays another act."""

    @staticmethod
    def item(session):
        from studio.interpretation.engine.types import HeldFact, ItemKind
        held = HeldFact(fact='performed_status', attribute=None, subject=Id(IdFamily.SESSION, session), result=None,
                        kind=ItemKind.QUESTION, cause='reading_unknown', reason=None, spans=(), rank=4)
        return Q.Item(held=held, message=Q.MessageId.DOUBT,
                      fill=Q.Fill(act=Kind.EXAMINATION, family=SessionKind.COLONOSCOPY, words=(ct.Span(100, 160),)))

    def shown(self, session, doc):
        from studio.interpretation import overlay
        R = TA.dated(doc.build())
        snare = Id(IdFamily.EVENT, 2)  # 45385's act, established in X1
        return overlay.item_shown(self.item(session), (snare,), R)[0]

    def test_rfw_an_unknown_session_subject(self):
        self.assertEqual(self.shown(9, EF.colonoscopy()), 'session_doubt')  # red: act_doubt (another session)

    def test_boundary_another_established_session(self):
        doc = EF.colonoscopy()
        doc.session(2, ct.SessionKind.COLONOSCOPY, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
        self.assertEqual(self.shown(2, doc), 'act_doubt')


# --- RFEW-3: one service row per session --------------------------------------------------------------------------------

class R2FWServiceRowPerSession(R2WWorld):
    """RFEW-3's P2: two colonoscopies, each reach unresolved; 45380 (X1) and 45385 (X2) are each held by EXTENT about
    their own session. Two sessions' reaches are two questions: a row each, with its own code and passages; one "Not
    documented" excludes that session's code only, and its withdrawal withdraws that answer only."""

    def test_rfw_two_sessions_two_rows(self):
        scene = self.scene(colonoscopies(2).build(), SERVICE_CODES, text=TEXT)
        payload = self.payload(scene)
        rows = [row for row in payload['details_needed'] if row['fact'] == 'extent']
        self.assertEqual(sorted(row['affects'] for row in rows), [['45380'], ['45385']])  # behaviour first (red: one)
        self.assertEqual(len({row['id'] for row in rows}), 2)
        [first] = [row for row in rows if row['affects'] == ['45380']]
        [second] = [row for row in rows if row['affects'] == ['45385']]
        self.assertTrue(set(offsets(first)).isdisjoint(offsets(second)))
        self.assertEqual(first['prompt'], answers.PROMPTS['extent'])
        saved = self.save(scene, first, ND)
        self.assertEqual([answer.code for answer in saved], ['45380'])
        views = self.views(scene)
        self.assertEqual((views['45380'].status, views['45385'].status), ('excluded', 'needs_clarification'))
        with self.reads(scene):
            answers.revoke_answer(self.fresh(scene), self.user, saved[0].pk)
        self.assertEqual(models.MemberAnswer.objects.filter(revision=scene.revision, revocation__isnull=True).count(), 0)
        rows = [row for row in self.payload(scene)['details_needed'] if row['fact'] == 'extent']
        self.assertEqual(sorted(row['affects'] for row in rows), [['45380'], ['45385']])

    def test_boundary_one_colonoscopy_one_row(self):
        """L7-08 (both trees): the biopsy and the snare in ONE colonoscopy ask its one reach - one row for both codes, its
        id the service row's."""
        scene = self.scene(colonoscopies(1).build(), SERVICE_CODES, text=TEXT)
        [row] = [row for row in self.payload(scene)['details_needed'] if row['fact'] == 'extent']
        self.assertEqual(sorted(row['affects']), ['45380', '45385'])
        self.assertEqual(row['id'], answers.detail_id('extent', self.proposal(scene, '45380').family, ''))


# --- RFEW-5: the excluded-by-an-answer sentence by the answer's state -------------------------------------------------

class R2FWWithdrawnAnswerSentence(R2WWorld):
    """RFEW-5: 45378's row (its examination's status unresolved) answered "Not documented", the AGAIN run (the engine reads
    the answer and excludes 45378), then the answer withdrawn before the update that applies the withdrawal: the code's
    sentence says the answer was withdrawn, never "until that answer is withdrawn"."""

    def answered(self):
        scene = self.scene(exam_status(EF.X(1)).build(), (('45378', 1),), text=TEXT)
        [row] = self.rows_of(self.payload(scene), '45378')
        [answer] = self.save(scene, row, ND)
        self.again(scene)
        return scene, answer

    def test_rfw_a_withdrawn_answer_before_its_update(self):
        scene, answer = self.answered()
        with self.reads(scene):
            answers.revoke_answer(self.fresh(scene), self.user, answer.pk)
        self.assertEqual(self.views(scene)['45378'].reason, 'detail_unavailable')  # the W1 rule: in effect until run
        quals = self.code_row(self.payload(scene), '45378')['why']['qualifications']
        self.assertNotIn(STANDING_WORDS, quals)  # behaviour first (red: "until that answer is withdrawn")
        self.assertIn(WITHDRAWN_WORDS, quals)

    def test_boundary_a_standing_answer(self):
        scene, _ = self.answered()
        quals = self.code_row(self.payload(scene), '45378')['why']['qualifications']
        self.assertIn(STANDING_WORDS, quals)


# --- e-words' Q1: NOT_DOCUMENTED and UNLISTED_EVIDENCE on the row that asks their question ----------------------------

class R2FWSupportedRow(R2WWorld):
    """NOT_DOCUMENTED (45380 proposed beside a colonoscopy with no biopsy) and UNLISTED_EVIDENCE (43274 on the exchange's
    unlisted removal) ask performed_question(code): their row asks whether the code is supported by what was done on the
    date of service (the SUPPORTED form's row), with its statement and the code's qualification; the door binds the
    item's fingerprint from it."""

    def walk(self, R, codes, code, message):
        scene = self.scene(R, codes, text=TEXT)
        stored = self.proposal(scene, code)
        self.assertEqual(stored.support['item']['message'], message)
        payload = self.payload(scene)
        [row] = [row for row in self.rows_of(payload, code) if row['fact'] == 'performed_status']
        self.assertEqual(row['prompt'], SUPPORTED_PROMPT)  # behaviour first (red: the status row)
        self.assertEqual((row['missing'], row['statement']), (SUPPORTED_MISSING, statement(SUPPORTED_MISSING)))
        self.assertEqual(row['id'], answers.detail_id('performed_status', stored.family, code, 'supported'))
        quals = self.code_row(payload, code)['why']['qualifications']
        self.assertIn(qualification(SUPPORTED_MISSING), quals)
        self.assertNotIn('CPT Studio could not confirm from the document that this was done on the date of service.', quals)
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])
        self.again(scene)
        [row] = [row for row in self.rows_of(self.payload(scene), code) if row['fact'] == 'performed_status']
        self.assertEqual((row['prompt'], row['saved']['value']), (SUPPORTED_PROMPT, ND))

    def test_rfw_not_documented(self):
        self.walk(EF.colonoscopy().build(), (('45380', 2), ('45378', 1)), '45380', 'not_documented')

    def test_rfw_unlisted_evidence(self):
        self.walk(exchange().build(), (('43274', 2),), '43274', 'unlisted_evidence')

    def test_boundary_a_status_of_the_codes_own_act(self):
        """45385's STATUS about its own snare keeps the status key row (both trees)."""
        scene = self.scene(snare_status().build(), (('45385', 2),), text=TEXT)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual(row['prompt'], STATUS_KEY_PROMPT)


# --- RFEW-4's corpus control: an INDEPENDENT reading of every item's row ------------------------------------------------
# The rulings' terms, written here (never the product's naming rule: overlay.own_session_examination, _holds_examination,
# wording.item_record or member_form): RBWX-2/D309 - only the examination of one of the code's OWN ESTABLISHED sessions is
# "the examination of this procedure"; WX3-1 - an examination whose slot is not established is the code's session's when
# it may be in it; 4.11/D227 - an id the FactSet does not hold is possibly any session; FAMILY_KINDS - a session may hold
# an examination only if a family it may be of (its kind fact, narrowed by its established acts' kinds) holds one; D280.3
# - DIGITAL_SCOPE names the engine's held session (an input); D281 B6 - the held session's DOUBT and STATUS ask row 7's
# done; D309 - NOT_DOCUMENTED and UNLISTED_EVIDENCE ask the SUPPORTED form's question.

def _held(R, value):
    return isinstance(value, Id) and value.family is IdFamily.SESSION and value in R.sessions


def _established(R, event):
    if getattr(event, 'family', None) is not IdFamily.EVENT:
        return None
    found = F.fact(R, event, Attribute.SESSION)
    return found.value if found.result is Result.SUPPORTED and _held(R, found.value) else None


def _may_be_in(R, event):
    found = F.fact(R, event, Attribute.SESSION)
    sessions = set(R.sessions)
    if found.result is Result.NEGATED:
        return sessions - {found.value}
    values = (found.value,) if found.result is Result.SUPPORTED else (found.value, *found.options)
    if any(isinstance(v, Id) and v.family is IdFamily.SESSION and v not in R.sessions for v in values):
        return sessions
    if found.result is Result.SUPPORTED:
        return {found.value} & sessions
    if found.state is None or found.state is FactState.NEGATED or F.overfilled(found):
        return sessions
    return {v for v in values if v in sessions}


ADMITTED = frozenset(kind for kinds in FAMILY_KINDS.values() for kind in kinds)


def _may_hold_examination(R, session):
    found = F.fact(R, session, Attribute.KIND)
    if found.result is Result.SUPPORTED and isinstance(found.value, SessionKind):
        families = {found.value}
    elif found.result is Result.NEGATED:
        families = set(SessionKind) - {found.value}
    elif found.state is None or found.state is FactState.NEGATED or F.overfilled(found):
        families = set(SessionKind)
    else:
        families = {v for v in (found.value, *found.options) if isinstance(v, SessionKind)}
    for event in R.events:
        if _established(R, event) == session:
            kind = F.fact(R, event, Attribute.KIND)
            if kind.result is Result.SUPPORTED and isinstance(kind.value, Kind) and kind.value in ADMITTED:
                families = {f for f in families if kind.value in FAMILY_KINDS.get(f, frozenset())}
    return any(Kind.EXAMINATION in FAMILY_KINDS.get(f, frozenset()) for f in families)


def independent_naming(item, own, R):
    """'own' when the held session's examination the item names is the examination of one of the code's own established
    sessions, else 'other'."""
    subject = item.held.subject
    if subject is None or subject in own:
        return 'own'
    mine = {s for s in (_established(R, act) for act in own) if s is not None}
    if not mine or getattr(subject, 'family', None) not in (IdFamily.SESSION, IdFamily.EVENT):
        return 'other'
    if subject.family is IdFamily.SESSION:
        if subject not in R.sessions:  # 4.11: an unknown id is possibly any session, never another one
            return 'own' if any(_may_hold_examination(R, s) for s in mine) else 'other'
        return 'own' if subject in mine else 'other'
    if item.message is Q.MessageId.DIGITAL_SCOPE:
        rest = Q._digital_rest(item.held, R)
        held = Q._held_session(R, rest, (), tuple(own)) if rest is not None else None  # the engine's held session
        if _held(R, held):
            return 'own' if held in mine else 'other'
    named = _established(R, subject)
    if named is not None:
        return 'own' if named in mine and _may_hold_examination(R, named) else 'other'
    possible = _may_be_in(R, subject)
    return 'own' if any(s in possible and _may_hold_examination(R, s) for s in mine) else 'other'


ROW7 = {Q.MessageId.DOUBT: 'doubt', Q.MessageId.STATUS: 'status', Q.MessageId.ENTRY: 'entry',
        Q.MessageId.TIME: 'time', Q.MessageId.TIME_BESIDE_VISIT: 'time', Q.MessageId.PERFORMER: 'performer'}
OWN_FORMS = {'doubt': 'session_doubt', 'status': 'session_status', 'entry': 'session_entry', 'time': 'session_time',
             'performer': 'session_performer', 'digital': 'digital_scope', 'unlisted': 'unlisted_scope'}
OTHER_FORMS = {'doubt': 'act_doubt', 'status': 'act_doubt', 'entry': 'act_entry', 'time': 'act_time',
               'performer': 'act_performer', 'digital': 'act_digital', 'unlisted': 'act_unlisted'}


def independent_form(found, R):
    """(form, the act a renamed form names) of ``found``'s item read independently - None outside the messages read here."""
    item = found.item
    message = item.message
    if message in (Q.MessageId.NOT_DOCUMENTED, Q.MessageId.UNLISTED_EVIDENCE):
        return 'supported', ''
    if message in (Q.MessageId.DIGITAL_SCOPE, Q.MessageId.UNLISTED_SCOPE):
        ask = 'digital' if message is Q.MessageId.DIGITAL_SCOPE else 'unlisted'
    elif message in ROW7 and item.fill.act is Kind.EXAMINATION and item.fill.family is not None:
        ask = ROW7[message]
    else:
        return None
    own = tuple(dict.fromkeys((*found.evaluation.bindings.values(), *found.evaluation.supporting)))
    if independent_naming(item, own, R) == 'own':
        return OWN_FORMS[ask], ''
    return OTHER_FORMS[ask], 'examination'


ENUMERATION = (
    ('P1 visit unresolved', lambda: late_visit(EF.unres(EF.X(1))), (('99213', 9),)),
    ('P1 visit silent', lambda: late_visit(EF.SILENT), (('99213', 9),)),
    ('P1b kind unresolved, examination silent', lambda: visit_kind_unplaced(EF.SILENT), (('99213', 9),)),
    ('B kind silent, examination claiming X1', lambda: visit_kind_unplaced(EF.unres(EF.X(1)), EF.SILENT),
     (('99213', 9),)),
    ('P3 unresolved X9', lambda: exam_status(EF.unres(EF.X(9))), EXAM_CODES),
    ('P3 supported X9', lambda: exam_status(EF.sup(EF.X(9))), EXAM_CODES),
    ('colonoscopy of unresolved kind', lambda: exam_status(EF.SILENT, EF.unres(ct.SessionKind.COLONOSCOPY)), EXAM_CODES),
    ('DIGITAL_SCOPE, the claimed examination in X9', lambda: dre_unknown_session(EF.sup(EF.X(9))), (('45385', 2),)),
    ('no biopsy beside 45380', EF.colonoscopy, (('45380', 2), ('45378', 1))),
    ('the exchange', exchange, (('43274', 2),)),
)


def rendered(found, result, R):
    return jobs._render_code(found, combination=result.combination, R=TA.dated(R), text=TA.TEXT, pages=(),
                             context_values={}, refs={}, sources=(), day=TA.DAY, active={}, provider='')


class R2FWIndependentEnumeration(SimpleTestCase):
    """Over the RFEW scenes and every one-fact perturbation of each: every item of the held session's examination (the
    row-7 keys, DIGITAL_SCOPE, UNLISTED_SCOPE) and every NOT_DOCUMENTED / UNLISTED_EVIDENCE item is recorded (the
    renderer's support['item']) with the form the independent reading above gives - the act a renamed form names the
    examination."""

    def test_rfw_every_items_row_is_the_independent_readings(self):
        seen = {'own': 0, 'renamed': 0, 'supported': 0}
        for name, build, codes in ENUMERATION:
            base = build().build()
            for label, R in [('base', base)] + [(f'{s}:{a.value}:{i}', R) for _, s, a, i, R in TA.perturbations(base)]:
                result = TA.run(R, *codes)
                for found in result.codes:
                    if found.item is None or found.evaluation is None or found.bucket is not AS.Bucket.SELECTED:
                        continue
                    expected = independent_form(found, TA.dated(R))
                    if expected is None:
                        continue
                    record = rendered(found, result, R).support['item']
                    with self.subTest(scene=name, perturbation=label, code=found.code,
                                      message=found.item.message.value):
                        self.assertEqual(record.get('form') or '', expected[0])
                        if expected[1]:
                            self.assertEqual((record.get('act_ref') or {}).get('act'), expected[1])
                    seen['supported' if expected[0] == 'supported' else 'renamed' if expected[1] else 'own'] += 1
        self.assertGreater(seen['own'], 20)
        self.assertGreater(seen['renamed'], 20)
        self.assertGreater(seen['supported'], 5)
