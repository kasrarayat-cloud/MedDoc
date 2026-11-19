"""r2e (DECISIONS D303, D304: round r2e's words item - the member surface's ONE structural invariant). SYNTHETIC only:
tests/v2's own FactSet builders over test_assess's synthetic letters (r2w_world: the renderer's child, persist, read time,
the customer payload, the details door and the AGAIN recompute); nothing is sent anywhere.

The invariant (D303): (I1) every item a row binds asks exactly the question the row shows - its prompt, statement,
missing and the code's qualification derived from the item's own message and slots; renaming an act changes its name
only, never what is asked; (I2) items whose questions differ never share a row; (I3) the door records an answer only
against items whose question equals the row's shown question, and read time binds it only to items the current reading
still asks (by fingerprint); (I4) every row's passages are the passages its items' questions quote; (I5) an add-on counted
at read time - selected, reinstated or reopened - is read over the counted set, and (D304's twin) a released primary
nothing may exclude counts for its add-on. Checked by code over the corpus in the round's seam harness; here, the rules
the round builds, each with an input it must change and a boundary it must leave alone:

- WX3-1: the held session's examination is another session's only when it is established as one - a session DOUBT or
  STATUS about an examination whose session slot is not established keeps row 7's done (DONE_IN_PART) on every code's
  row, and the door binds its fingerprint from that row;
- WX3-1/WX3-2, the rename: an examination of another session is named as another act in the question its own form asks -
  DONE_IN_PART for the session's DOUBT and STATUS (ACT_DOUBT), DIGITAL_SCOPE's own question (ACT_DIGITAL), UNLISTED_SCOPE's
  (ACT_UNLISTED) - never a date, entry, performer or status question chosen by its fact key;
- a DOUBT about another act that is not the session's examination asks STATUS's question of that act (ACT_STATUS), and
  PROCEDURE about another act asks that act's procedure (ACT_PROCEDURE) - never "this procedure" / "this act";
- WX3-3: a reinstated add-on is read over the counted set whatever its supporting acts: no counted primary holds it
  (coding_rule:ADDON, withheld ADDON_CHECK, never approvable alone), its row the ADDON row;
- D304's twin: a primary whose engine-read answer read time releases, which nothing may exclude, counts for its add-on;
- the corpus enumeration: every engine item of the scenes below (each base and every one-fact perturbation) is recorded
  with the row its own question has, by an independent reading of its message and slots."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio import answers, customer_api, jobs, models, review
from studio.interpretation import overlay, wording
from studio.interpretation.contract import types as ct
from studio.interpretation.contract.types import Attribute, Result
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import classes as CL
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine.types import Id, IdFamily
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_overlay as TO
from tests.v2 import test_questions as TQ
from tests.v2.r2w_world import R2WWorld

ND = models.MemberAnswer.NOT_DOCUMENTED
# test_assess's synthetic letters with a space every seventh character, so a code's own passages have words to show
TEXT = ''.join(' ' if index % 7 == 6 else TA.TEXT[index] for index in range(len(TA.TEXT)))
EXAMINATION_WORDS = 'the examination of this procedure'
DONE_IN_PART = 'documented as performed, in full or in part, on the date of service'
# the rename (by value, so the module imports on the reference tree)
ACT_DOUBT, ACT_DIGITAL, ACT_UNLISTED = 'act_doubt', 'act_digital', 'act_unlisted'
RENAMED = {'session_doubt': ACT_DOUBT, 'session_status': ACT_DOUBT, 'session_entry': 'act_entry',
           'session_time': 'act_time', 'session_performer': 'act_performer', 'digital_scope': ACT_DIGITAL,
           'unlisted_scope': ACT_UNLISTED}


def offsets(row):
    return [(passage['start'], passage['end']) for passage in row['passages']]


def unit(n):
    span = EF.unit(n)
    return (span.start, span.end)


def canonical(text):
    """``text`` with the act's name taken out: what is asked, whatever the act is called."""
    for name in (EXAMINATION_WORDS, 'the examination', 'this procedure', 'this act', 'the act', '{act}'):
        text = text.replace(name, '<act>')
    return text


# --- WX3-1: an examination whose session slot is not established is the held session's ----------------------------

def doubted_exam_unplaced():
    """EF.colonoscopy (X1 to the cecum, examination E1, the cold snare E2 of L1, done today) with E1's session unresolved
    (X1 claimed) and its status in doubt: 45385 and 45378 are both held by the DOUBT about E1 (refute-words3's P1)."""
    doc = EF.colonoscopy()
    doc.exam(1, session=EF.unres(EF.X(1)), status=EF.doubted(ct.Status.PERFORMED))
    return doc


def status_exam_unplaced():
    """The same with E1's status unresolved (STATUS about E1)."""
    doc = EF.colonoscopy()
    doc.exam(1, session=EF.unres(EF.X(1)), status=EF.unres(ct.Status.PERFORMED))
    return doc


UNPLACED_CODES = (('45385', 2), ('45378', 1))


class R2EWUnplacedExamination(R2WWorld):
    """WX3-1: the DOUBT (or STATUS) about the colonoscopy's examination E1, whose session slot is not established, held
    for 45385 (which does not bind E1) and 45378 (which does): the engine's item names E1 as the held session's
    examination ("the colonoscopy") for both, so both rows ask row 7's done (DONE_IN_PART) - one question - and the
    door binds the item's fingerprint from the row that asks it; read time and the AGAIN read it alike."""

    def walk(self, build, form):
        scene = self.scene(build().build(), UNPLACED_CODES, text=TEXT)
        stored = self.proposal(scene, '45385')
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '45385')
        self.assertEqual(row['prompt'], answers.DONE_IN_PART_PROMPT)  # behaviour first (red: the status row)
        self.assertEqual(stored.support['item']['form'], form)
        self.assertEqual(row['statement'], answers.STATEMENT.format(missing=wording.FORM_MISSING[form]))
        self.assertEqual(row['id'], answers.detail_id('performed_status', stored.family, '45385', form))
        quals = self.code_row(payload, '45385')['why']['qualifications']
        self.assertIn(customer_api.FORM_WORDS[form], quals)
        self.assertNotIn(customer_api.QUESTION_WORDS['performed_status'], quals)
        [own] = self.rows_of(payload, '45378')  # the code that binds E1: the same question
        self.assertEqual((own['prompt'], own['statement']), (row['prompt'], row['statement']))
        self.assertIn(unit(1), offsets(row))  # E1's own words
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])
        view = self.views(scene)['45385']
        self.assertEqual((view.status, view.answered_form), ('excluded', form))
        self.again(scene)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual((row['prompt'], row['saved']['value']), (answers.DONE_IN_PART_PROMPT, ND))

    def test_rew_a_doubt_about_the_unplaced_examination(self):
        self.walk(doubted_exam_unplaced, wording.FORM_SESSION_DOUBT)

    def test_rew_a_status_of_the_unplaced_examination(self):
        self.walk(status_exam_unplaced, wording.FORM_SESSION_STATUS)

    def test_boundary_another_sessions_examination_is_another_act(self):
        """RBWX-2 kept: the office visit's same-day item about the colonoscopy X2's undated examination (its session
        established, X2) names it as another act, with its question (the date) unchanged (both trees)."""
        scene = self.scene(TO.office_and_undated_colonoscopy().build(), (('99213', 1),), text=TEXT)
        stored = self.proposal(scene, '99213')
        self.assertEqual(stored.support['item']['form'], wording.FORM_ACT_TIME)
        [row] = self.rows_of(self.payload(scene), '99213')
        self.assertEqual(row['prompt'], 'Was the examination done at this encounter, on the date of service?')


# --- WX3-2: DIGITAL_SCOPE of another session keeps its question, the act renamed -------------------------------------

def claimed_dre_beside_a_visit():
    """An office visit X1 (99213's visit E1) and a colonoscopy X2 whose claimed digital examination E2 (device manual
    unresolved) and colonoscope's examination E3 have no date relation (refute-words3's P1b)."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.OFFICE_EM, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, ct.Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
    doc.session(2, ct.SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
    doc.exam(2, session=EF.X(2), device=EF.unres(ct.Device.MANUAL), date=None)
    doc.exam(3, session=EF.X(2), date=None)
    return doc


class R2EWDigitalScopeOfAnotherSession(R2WWorld):
    """WX3-2: the visit's DIGITAL_SCOPE item names X2's examination (another session's): its row asks DIGITAL_SCOPE's own
    question - whether that examination is documented as performed, in full or in part - with the examination named as
    another act, never the claimed examination's date; its qualification says DIGITAL_SCOPE's sentence renamed."""

    PROMPT = f'Is the examination {DONE_IN_PART}?'
    MISSING = 'the technique of an examination the document states, which may be the examination'

    def test_rew_the_visits_digital_scope_asks_its_own_question(self):
        scene = self.scene(claimed_dre_beside_a_visit().build(), (('99213', 1),), text=TEXT)
        stored = self.proposal(scene, '99213')
        self.assertEqual(stored.support['item']['message'], wording.Message.DIGITAL_SCOPE.value)
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '99213')
        self.assertEqual(row['prompt'], self.PROMPT)  # behaviour first (red: "Was the examination done at this ...")
        self.assertNotIn('at this encounter', row['prompt'])
        self.assertEqual(stored.support['item']['form'], ACT_DIGITAL)
        self.assertEqual(row['statement'], answers.STATEMENT.format(missing=self.MISSING))
        quals = self.code_row(payload, '99213')['why']['qualifications']
        self.assertIn(f'CPT Studio could not confirm from the document {self.MISSING}.', quals)
        self.assertEqual(offsets(row)[0], (300, 360))  # the held session's examination E3 first
        self.assertIn((200, 260), offsets(row))  # the claimed examination's statement its question quotes
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])
        self.assertEqual(self.views(scene)['99213'].answered_form, ACT_DIGITAL)
        self.again(scene)
        [row] = self.rows_of(self.payload(scene), '99213')
        self.assertEqual((row['prompt'], row['saved']['value']), (self.PROMPT, ND))

    def test_boundary_the_codes_own_digital_scope(self):
        """45385 beside a claimed DRE of its own colonoscopy: its own session's examination (both trees)."""
        R = TQ.dre_shape({'device': EF.unres(ct.Device.MANUAL), 'status': EF.unres(ct.Status.PERFORMED)})
        scene = self.scene(R, (('45385', 2),), text=TEXT)
        stored = self.proposal(scene, '45385')
        self.assertEqual(stored.support['item']['form'], wording.FORM_DIGITAL_SCOPE)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual(row['prompt'], answers.DONE_IN_PART_PROMPT)


# --- the rename itself: one question, the act renamed --------------------------------------------------------------

def _item(message, fact, family=ct.SessionKind.COLONOSCOPY, act=ct.Kind.EXAMINATION):
    from studio.interpretation.engine.types import HeldFact, ItemKind
    held = HeldFact(fact=fact, attribute=None, subject=Id(IdFamily.EVENT, 2), result=None, kind=ItemKind.QUESTION,
                    cause='reading_unknown', reason=None, spans=(), rank=4)
    return Q.Item(held=held, message=message, fill=Q.Fill(act=act, family=family, words=(ct.Span(200, 260),)))


class R2EWRename(SimpleTestCase):
    """wording.item_record over an item about an examination of another session (``own_session`` False): the form is the
    item's own form renamed - its prompt, missing and qualification equal to its examination form's but for the act's
    name - whatever its fact key; the act recorded is the examination."""

    CASES = ((Q.MessageId.DOUBT, 'performed_status', 'session_doubt'),
             (Q.MessageId.STATUS, 'performed_status', 'session_status'),
             (Q.MessageId.ENTRY, 'event_entry', 'session_entry'), (Q.MessageId.TIME, 'event_time', 'session_time'),
             (Q.MessageId.PERFORMER, 'event_performer', 'session_performer'),
             (Q.MessageId.DIGITAL_SCOPE, 'event_time', 'digital_scope'),
             (Q.MessageId.DIGITAL_SCOPE, 'event_entry', 'digital_scope'),
             (Q.MessageId.DIGITAL_SCOPE, 'conflict:examination', 'digital_scope'),
             (Q.MessageId.UNLISTED_SCOPE, 'performed_status', 'unlisted_scope'))

    def test_rew_renaming_changes_the_name_only(self):
        own = (Id(IdFamily.EVENT, 1),)
        for message, fact, session_form in self.CASES:
            with self.subTest(message=message.value, fact=fact):
                found = _item(message, fact)
                form, record = wording.item_record(wording.Message(message.value), found.fill, found.held.subject,
                                                   own, own_session=False, fact=fact)
                self.assertEqual(form, RENAMED[session_form])  # red: by its fact key (act_status, act_time, '')
                self.assertEqual(wording.recorded_act(record), (((200, 260),), 'examination', ''))
                renamed = answers.row_prompt(fact, form, 'examination')
                self.assertNotIn(EXAMINATION_WORDS, renamed)
                self.assertEqual(canonical(renamed), canonical(answers.row_prompt(fact, session_form)))
                self.assertEqual(canonical(wording.form_text(wording.FORM_MISSING[form], 'examination')),
                                 canonical(wording.FORM_MISSING[session_form]))
                self.assertEqual(canonical(wording.form_text(customer_api.FORM_WORDS[form], 'examination')),
                                 canonical(customer_api.FORM_WORDS[session_form]))

    def test_rew_the_renamed_act_is_the_examination(self):
        """Every renamed form names the held session's examination, whatever kind its Fill's act slot carries (a
        DIGITAL_SCOPE item's is its held conflict's kind: D280.3)."""
        own = (Id(IdFamily.EVENT, 1),)
        for message, fact in ((Q.MessageId.DIGITAL_SCOPE, 'conflict:other'), (Q.MessageId.UNLISTED_SCOPE,
                                                                                'performed_status')):
            with self.subTest(message=message.value):
                found = _item(message, fact, act=ct.Kind.OTHER)
                form, record = wording.item_record(wording.Message(message.value), found.fill, found.held.subject,
                                                   own, own_session=False, fact=fact)
                self.assertEqual(wording.recorded_act(record)[1], 'examination')  # red: the key row or 'other'
                self.assertIn('the examination', answers.row_prompt(fact, form, wording.recorded_act(record)[1]))

    def test_rew_time_beside_visit_asks_times_question(self):
        """TIME_BESIDE_VISIT asks TIME's question (its reason adds the visit): the held session's examination's date on
        the code's own session (SESSION_TIME), another session's or another act's by its kind (ACT_TIME)."""
        own = (Id(IdFamily.EVENT, 1),)
        found = _item(Q.MessageId.TIME_BESIDE_VISIT, 'event_time')
        cases = ((True, found, wording.FORM_SESSION_TIME), (False, found, wording.FORM_ACT_TIME),
                 (True, _item(Q.MessageId.TIME_BESIDE_VISIT, 'event_time', act=ct.Kind.SNARE), wording.FORM_ACT_TIME))
        for own_session, item, form in cases:
            with self.subTest(own_session=own_session, act=item.fill.act.value):
                self.assertEqual(wording.item_record(wording.Message.TIME_BESIDE_VISIT, item.fill, item.held.subject,
                                                     own, own_session=own_session, fact='event_time')[0], form)

    def test_boundary_the_codes_own_session_keeps_its_form(self):
        own = (Id(IdFamily.EVENT, 1),)
        for message, fact, session_form in self.CASES:
            with self.subTest(message=message.value, fact=fact):
                found = _item(message, fact)
                self.assertEqual(wording.item_record(wording.Message(message.value), found.fill, found.held.subject,
                                                     own, own_session=True, fact=fact)[0], session_form)


class R2EWOtherActDoubt(SimpleTestCase):
    """A DOUBT about an act the code does not bind that is not the held session's examination asks whether that act was
    done on the date of service (STATUS's question): its row names that act (ACT_STATUS), never "this procedure"."""

    def test_rew_a_doubt_about_another_act(self):
        found = _item(Q.MessageId.DOUBT, 'performed_status', act=ct.Kind.SNARE)
        form, record = wording.item_record(wording.Message.DOUBT, found.fill, found.held.subject,
                                           (Id(IdFamily.EVENT, 1),), own_session=True, fact='performed_status')
        self.assertEqual(form, wording.FORM_ACT_STATUS)  # red: '' (the status row, "this procedure")
        self.assertEqual(wording.recorded_act(record), (((200, 260),), 'snare', ''))
        self.assertEqual(answers.row_prompt('performed_status', form, 'snare'),
                         'Was the snare removal performed on the date of service, as documented?')

    def test_rew_a_procedure_about_another_act(self):
        """XCHG's counterpart (the placement 43276 does not bind) whose session is not established: its row names it."""
        found = _item(Q.MessageId.PROCEDURE, 'procedure', act=ct.Kind.STENT)
        form, record = wording.item_record(wording.Message.PROCEDURE, found.fill, found.held.subject,
                                           (Id(IdFamily.EVENT, 1),), own_session=True, fact='procedure')
        self.assertEqual(form, 'act_procedure')  # red: '' (the key row, "this act")
        self.assertEqual(wording.recorded_act(record), (((200, 260),), 'stent', ''))
        self.assertEqual(answers.row_prompt('procedure', form, 'stent'), 'In which procedure was the stent placement done?')
        self.assertEqual(canonical(answers.row_prompt('procedure', form, 'stent').replace('the stent placement', '{act}')),
                         canonical(answers.row_prompt('procedure')))

    def test_boundary_a_procedure_about_the_codes_own_act(self):
        found = _item(Q.MessageId.PROCEDURE, 'procedure', act=ct.Kind.STENT)
        self.assertEqual(wording.item_record(wording.Message.PROCEDURE, found.fill, found.held.subject,
                                             (Id(IdFamily.EVENT, 2),), own_session=True, fact='procedure')[0], '')

    def test_boundary_a_doubt_about_the_codes_own_act(self):
        found = _item(Q.MessageId.DOUBT, 'performed_status', act=ct.Kind.SNARE)
        form, record = wording.item_record(wording.Message.DOUBT, found.fill, found.held.subject,
                                           (Id(IdFamily.EVENT, 2),), own_session=True, fact='performed_status')
        self.assertEqual((form, record), ('', {}))


# --- WX3-3: a reinstated add-on is read over the counted set ---------------------------------------------------------

DENIED = TA.EvidenceSpan(0, 200, 260, TA.TEXT[200:260], True)


def denied_prolonged():
    """test_assess.office_prolonged with the prolonged time E2 denied (all of its kind): 99417, citing that denial, is
    EXCLUDED by citation and reinstatable (refute-words3's P3)."""
    doc = TA.office_prolonged()
    doc.act(2, ct.Kind.EM_PROLONGED, status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.ALL_OF_KIND),
            kind_words=EF.Span(200, 230), status_words=EF.Span(230, 260))
    return doc.build()


class R2EWReinstatedAddon(R2WWorld):
    """WX3-3 (D268, D284): 99417 reinstated with no primary counted - proposed alone, or 99215 rejected - is held by its
    ADDON row at read time (withheld ADDON_CHECK, never approvable alone), its row the ADDON row; with 99215 counted it is
    not (approvable)."""

    def reinstated(self, codes, reject):
        scene = self.scene(denied_prolonged(), codes)
        self.assertEqual(self.proposal(scene, '99417').bucket, models.Proposal.EXCLUDED)
        if reject:
            self.decide(scene, '99215', review.REJECT)
        self.decide(scene, '99417', review.REINSTATE)
        view = self.views(scene)['99417']
        with self.reads(scene):
            assessment = models.Assessment.objects.get(pk=scene.assessment.pk)
            actions = review.allowed_actions(self.proposal(scene, '99417'), assessment, self.membership)
        return scene, view, actions

    def walk(self, codes, reject):
        scene, view, actions = self.reinstated(codes, reject)
        self.assertEqual(view.withheld_by, overlay.ADDON_CHECK)  # behaviour first (red: '' - approvable alone)
        self.assertNotIn(review.APPROVE, actions)
        self.assertEqual(view.status, models.Proposal.NEEDS_CLARIFICATION)
        payload = self.payload(scene)
        self.assertIn(customer_api.WITHHELD_WORDS[overlay.ADDON_CHECK],
                      self.code_row(payload, '99417')['why']['qualifications'])
        [row] = self.rows_of(payload, '99417')
        self.assertEqual(row['prompt'], answers.FORM_PROMPTS[wording.FORM_ADDON])
        self.assertEqual(row['statement'], answers.ADDON_STATEMENT)

    def test_rew_reinstated_alone(self):
        self.walk((('99417', DENIED),), reject=False)

    def test_rew_reinstated_with_its_primary_rejected(self):
        self.walk((('99215', 1), ('99417', DENIED)), reject=True)

    def test_boundary_reinstated_beside_its_counted_primary(self):
        scene, view, actions = self.reinstated((('99215', 1), ('99417', DENIED)), reject=False)
        self.assertEqual(view.withheld_by, '')
        self.assertIn(review.APPROVE, actions)
        self.assertEqual(self.rows_of(self.payload(scene), '99417'), [])


# --- D304's twin: a released primary nothing may exclude counts for its add-on ------------------------------------------

class R2EWReleasedPrimary(SimpleTestCase):
    """overlay.recount's ``released`` (W2R-1) read with D294 RD-2 (D304): a primary the engine excluded by a member's
    answer whose answer read time releases counts for its add-on's ADDON row exactly when no statement may exclude it -
    the twin of test_r2bw_words' RD-2 fixture, where one may."""

    @staticmethod
    def frozen(build):
        codes = (('99215', 1), ('99417', 2))
        plain = TA.by_code(TA.run(build().build(), *codes))['99215']
        case = TO.Case(build().build(), *codes, answers=(TA.answer(plain),))
        key = next(p.key for p in case.rows if p.code == '99215')
        assert overlay.answered_by_engine(next(p for p in case.rows if p.key == key))[0]
        addon = next(p.key for p in case.rows if p.code == '99417')
        return case, key, addon

    def test_rew_a_released_primary_nothing_may_exclude_counts(self):
        def build():  # the visit's basis not established (99215 asks it), its status supported: nothing may exclude it
            doc = TA.office_prolonged()
            doc.act(1, ct.Kind.EM_VISIT, basis=EF.unres(ct.EmBasis.TOTAL_TIME))
            return doc
        case, key, addon = self.frozen(build)
        rows = {p.key: p for p in case.rows}
        self.assertFalse(AS.addon_uncounted('99215', overlay.read_record(rows[key]).kept, case.R))
        self.assertIn(overlay.ADDON_CAUSE, [held.cause for held in case.recount().live[addon].held])
        released = case.recount(released={key})
        self.assertNotIn(overlay.ADDON_CAUSE, [held.cause for held in released.live[addon].held])

    def test_boundary_a_released_primary_a_statement_may_exclude(self):
        def build():  # D304's fixture: the visit's own status unresolved - a statement may still exclude 99215
            doc = TA.office_prolonged()
            doc.act(1, ct.Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.TOTAL_TIME), status=EF.unres(ct.Status.PERFORMED))
            return doc
        case, key, addon = self.frozen(build)
        self.assertIn(overlay.ADDON_CAUSE, [held.cause for held in case.recount(released={key}).live[addon].held])


# --- the corpus enumeration: every item's recorded row is the row its own question has --------------------------------

def _session(R, subject):
    """The session ``subject`` is, or is established in; r2f (DECISIONS D309, RFEW-2): an id the FactSet does not hold
    establishes none."""
    if subject is None:
        return None
    if subject.family is IdFamily.SESSION:
        return subject
    found = F.fact(R, subject, Attribute.SESSION)
    value = found.value
    return value if found.result is Result.SUPPORTED and isinstance(value, Id) and value in R.sessions else None


def _holds_examination(R, session):
    """Whether an examination act may be in ``session``: a family it may be of holds one - r2f (DECISIONS D309, RFEW-1):
    its kind fact's families (classes._open), narrowed by the established kinds of the acts established in it (an
    established E/M visit's family holds none)."""
    families = CL._open(F.fact(R, session, Attribute.KIND), ct.SessionKind)
    held = frozenset(kind for family in ct.SessionKind for kind in F.family_kinds(family))
    for event in R.events:
        if _session(R, event) != session:
            continue
        kind = F.fact(R, event, Attribute.KIND)
        if kind.result is Result.SUPPORTED and isinstance(kind.value, ct.Kind) and kind.value in held:
            families = frozenset(found for found in families if kind.value in F.family_kinds(found))
    return any(ct.Kind.EXAMINATION in F.family_kinds(found) for found in families)


def expected_form(found, R):
    """The row of ``found``'s item read independently of wording.item_record (D303 I1): what its own question asks
    (row 7's done for the held session's examination named by its service - D281 B6; STATUS's question for any other
    DOUBT) and which act it names (the code's own; the examination of its own session, or of a session it may be -
    WX3-1; another act) - None for an item outside the row-7 keys and the scope messages."""
    item = found.item
    message, fill = item.message, item.fill
    own = tuple(dict.fromkeys((*found.evaluation.bindings.values(), *found.evaluation.supporting)))
    asks = {Q.MessageId.DOUBT: 'performed', Q.MessageId.STATUS: 'performed', Q.MessageId.ENTRY: 'entry',
            Q.MessageId.TIME: 'time', Q.MessageId.PERFORMER: 'performer', Q.MessageId.DIGITAL_SCOPE: 'digital',
            Q.MessageId.UNLISTED_SCOPE: 'unlisted', Q.MessageId.PROCEDURE: 'procedure'}
    if message not in asks:
        return None
    subject = item.held.subject
    session_named = (fill.act is ct.Kind.EXAMINATION and fill.family is not None
                     and message is not Q.MessageId.PROCEDURE)  # PROCEDURE asks the session itself: no session naming
    ask = asks[message]
    if message in (Q.MessageId.DOUBT, Q.MessageId.STATUS) and session_named:
        ask = 'done_in_part'
    sessions = {_session(R, act) for act in own} - {None}
    if subject is None or subject in own:
        naming = 'own'
    elif session_named or message in (Q.MessageId.DIGITAL_SCOPE, Q.MessageId.UNLISTED_SCOPE):
        named = _session(R, subject)
        if message is Q.MessageId.DIGITAL_SCOPE and subject.family is IdFamily.EVENT:  # the held session it names
            rest = Q._digital_rest(item.held, R)
            held = Q._held_session(R, rest, (), own) if rest is not None else None
            named = held if held is not None and held in R.sessions else named
        slot = F.fact(R, subject, Attribute.SESSION) if subject.family is IdFamily.EVENT else None
        may = named is None and slot is not None and any(CL._may_name(slot, session, R) and _holds_examination(R, session)
                                                         for session in sessions)
        held_named = (message is Q.MessageId.DIGITAL_SCOPE or subject.family is IdFamily.SESSION)
        if named is not None:
            own_session = named in sessions and (held_named or _holds_examination(R, named))
        else:
            own_session = may
        # r2f (DECISIONS D309, RFEW-1): with no established session of the code's own, no examination is its own
        naming = 'own' if sessions and own_session else 'other'
    else:
        naming = 'other' if subject.family is IdFamily.EVENT else 'own'
    exam = session_named or message in (Q.MessageId.DIGITAL_SCOPE, Q.MessageId.UNLISTED_SCOPE)
    if naming == 'own':
        if exam:
            return {'done_in_part': 'session_doubt' if message is Q.MessageId.DOUBT else 'session_status',
                    'entry': 'session_entry', 'time': 'session_time', 'performer': 'session_performer',
                    'digital': 'digital_scope', 'unlisted': 'unlisted_scope'}[ask]
        return ''
    return {'done_in_part': ACT_DOUBT, 'performed': 'act_status', 'entry': 'act_entry', 'time': 'act_time',
            'performer': 'act_performer', 'digital': ACT_DIGITAL, 'unlisted': ACT_UNLISTED,
            'procedure': 'act_procedure'}[ask]


def rendered(found, result, R):
    return jobs._render_code(found, combination=result.combination, R=TA.dated(R), text=TA.TEXT, pages=(),
                             context_values={}, refs={}, sources=(), day=TA.DAY, active={}, provider='')


def sigmoidoscopy_undated():
    """test_assess.office_and_sigmoidoscopy with the sigmoidoscopy's examination E2's date relation unresolved."""
    doc = TA.office_and_sigmoidoscopy()
    doc.exam(2, session=EF.X(2), date=EF.unres(ct.DateRelation.ON_DATE_OF_SERVICE))
    return doc


SCENES = (
    ('doubted exam unplaced', doubted_exam_unplaced, UNPLACED_CODES),
    # the visit alone beside another session's undated examination: its session slot perturbed, the visit's session holds
    # no examination, so the examination stays another act (WX3-1's possibility reading, RBWX-2 kept)
    ('office undated colonoscopy, the visit alone', TO.office_and_undated_colonoscopy, (('99213', 1),)),
    ('office undated sigmoidoscopy, the visit alone', sigmoidoscopy_undated, (('99213', 1),)),
    # XCHG: 43276 binds the removal; its counterpart placement's session or status not established (R3's PROCEDURE)
    ('exchange, the placement unplaced', lambda: TA.r2da_exchange(placement=dict(session=EF.unres(EF.X(1)))),
     TA.R2DA_EXCHANGE_CODES),
    ('exchange, the placement doubted', lambda: TA.r2da_exchange(placement=dict(status=EF.doubted(ct.Status.PERFORMED))),
     TA.R2DA_EXCHANGE_CODES),
    ('status exam unplaced', status_exam_unplaced, UNPLACED_CODES),
    ('claimed dre beside a visit', claimed_dre_beside_a_visit, (('99213', 1),)),
    ('office undated colonoscopy', TO.office_and_undated_colonoscopy, (('99213', 1), ('45385', 3), ('45378', 2))),
    ('colonoscopy', EF.colonoscopy, UNPLACED_CODES),
)


class R2EWInvariantEnumeration(SimpleTestCase):
    """Over the scenes above, each base and every one-fact perturbation: every engine item of the row-7 keys and the scope
    messages is recorded (the renderer's support['item']) with the row its own question has - the form an independent
    reading of its message and slots gives (``expected_form``) - so its row, statement and qualification ask what it
    asks; the act a renamed form names is the examination."""

    def test_rew_every_items_row_asks_its_own_question(self):
        seen = {'own': 0, 'renamed': 0, 'held session': 0}
        for name, build, codes in SCENES:
            base = build().build()
            for label, R in [('base', base)] + [(f'{s}:{a.value}:{i}', R) for _, s, a, i, R in TA.perturbations(base)]:
                result = TA.run(R, *codes)
                for found in result.codes:
                    if found.item is None or found.evaluation is None or found.bucket is not AS.Bucket.SELECTED:
                        continue
                    expected = expected_form(found, TA.dated(R))
                    if expected is None:
                        continue
                    record = rendered(found, result, R).support['item']
                    with self.subTest(scene=name, perturbation=label, code=found.code,
                                      message=found.item.message.value):
                        self.assertEqual(record.get('form') or '', expected)
                        if expected in (ACT_DOUBT, ACT_DIGITAL, ACT_UNLISTED):
                            self.assertEqual(record['act_ref'].get('act'), 'examination')
                    seen['renamed' if expected.startswith('act_') else 'held session' if expected else 'own'] += 1
        self.assertGreater(seen['held session'], 50)
        self.assertGreater(seen['renamed'], 0)
