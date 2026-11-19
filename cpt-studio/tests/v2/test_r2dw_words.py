"""r2d (DECISIONS D301: round r2d's words items RBWX-1 .. RBWX-5, the refutation of r2b's words2). SYNTHETIC only:
tests/v2's own FactSet builders over test_assess's synthetic letters (r2w_world: the renderer's child, persist, read time,
the customer payload, the details door and the AGAIN recompute); nothing is sent anywhere.

- RBWX-1: a details row shows every passage its item's question quotes - the act's words, its counterpart's and the
  statements it quotes - beside the act's own passages (another act's recorded spans, else the code's own:
  questions.question_passages, which stays); an act record that holds no span never empties a row.
- RBWX-2: an item's examination is "the examination of this procedure" only when it is the examination of the session
  the code is matched to; any other session's examination - an E/M's same-day procedure included - is named as another
  act (its row, its statement and the code's qualification), with that act's own passages.
- RBWX-3: an answer saved on a row is recorded with the fingerprint of the question the row shows (the effective view,
  read with the standing answers) and read time binds it as the answer passes bind it - an answer the engine reads binds
  only the item whose fingerprint it carries; an answer is listed no longer asked only when no reading with the standing
  answers asks its question - so the door, read time before the AGAIN and the AGAIN's record read it alike.
- RBWX-4: every reader that decides whether a code was reinstated, or counts it as a reinstated, selected code, reads it
  through review.bucket_of over its effective view: a code read as the selected code it was is never a reinstatement,
  and a code its answer excludes again is never counted as one.
- RBWX-5: a row with an answer in effect shows the words and passages of the item the answer was bound to, live or
  stored, as its row showed them when asked.
Each rule: an input it must change and a boundary it must leave alone."""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import answers, customer_api, jobs, models, reports, review
from studio.interpretation import overlay, wording
from studio.interpretation.contract import types as ct
from studio.interpretation.contract.types import Attribute, Result
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine.types import Id, IdFamily
from studio.validation import questions as VQ
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_overlay as TO
from tests.v2.r2w_world import R2WWorld
from tests.v2.test_r2w_member_words import CITED, ercp_cited

ND, CC = models.MemberAnswer.NOT_DOCUMENTED, models.MemberAnswer.CANNOT_CONFIRM
# test_assess's synthetic letters with a space every seventh character, so a code's own passages have words to show
TEXT = ''.join(' ' if index % 7 == 6 else TA.TEXT[index] for index in range(len(TA.TEXT)))
# the forms that name "the examination of this procedure" (by value, so the module imports on the reference tree)
EXAMINATION_WORDS = 'the examination of this procedure'


def offsets(row):
    return [(passage['start'], passage['end']) for passage in row['passages']]


def unit(n):
    span = EF.unit(n)
    return (span.start, span.end)


def session_of(R, subject):
    """The session ``subject`` is (a session) or is supported in (an event), None when not established."""
    if subject is None:
        return None
    if subject.family is IdFamily.SESSION:
        return subject
    found = F.fact(R, subject, Attribute.SESSION)
    return found.value if found.result is Result.SUPPORTED and isinstance(found.value, Id) else None


def rendered(found, result, R):
    """The renderer's own record of ``found`` (jobs._render_code), as persisted."""
    return jobs._render_code(found, combination=result.combination, R=TA.dated(R), text=TA.TEXT, pages=(),
                             context_values={}, refs={}, sources=(), day=TA.DAY, active={}, provider='')


def corpus(scenes):
    """Every engine item of ``scenes`` ((name, builder, codes)), each base and every one-fact perturbation: (scene,
    perturbation, R, result, found)."""
    for name, build, codes in scenes:
        base = build().build()
        for label, R in [('base', base)] + [(f'{s}:{a.value}:{i}', R) for _, s, a, i, R in TA.perturbations(base)]:
            result = TA.run(R, *codes)
            for found in result.codes:
                if found.item is not None and found.evaluation is not None:
                    yield name, label, R, result, found


# --- RBWX-1: every passage an item's question quotes -----------------------------------------------------------------

DENIED_BIOPSY = (('99213', 1), ('99214', 1), ('45380', 2))
DENIED_STONE = (('43264', 5), ('43273', 3), ('43262', 4))


class R2DWQuotedPassages(R2WWorld):
    """An exclusion's statement_scope about a denial the code does not bind (its act record holds no span: the act it
    names is the code's own, "the act this code accounts for") shows the code's own passage and the denial it quotes,
    through the door and the AGAIN - never no passage at all (refute-words2 RBWX-1's 190 items)."""

    def walk(self, build, codes, code, own, statement):
        scene = self.scene(build().build(), codes, text=TEXT)
        stored = self.proposal(scene, code)
        self.assertEqual(stored.support['item']['fact'], 'statement_scope')
        [row] = self.rows_of(self.payload(scene), code)
        self.assertTrue(row['passages'])  # behaviour first (red on the reference: no passage at all)
        self.assertEqual(offsets(row), [own, statement])
        self.assertEqual([passage['text'] for passage in row['passages']], [TEXT[a:b] for a, b in (own, statement)])
        self.assertEqual(stored.support['item']['act_ref'], {'spans': []})  # the act record, unchanged: no span
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])
        self.assertEqual(self.views(scene)[code].status, 'excluded')
        for again in (False, True):
            if again:
                self.again(scene)
            with self.subTest(again=again):
                [row] = self.rows_of(self.payload(scene), code)
                self.assertEqual((offsets(row), row['saved']['value']), ([own, statement], ND))

    def test_rdw_a_denial_of_biopsies_beside_the_code_it_holds(self):
        self.walk(TO.office_with_denied_biopsy, DENIED_BIOPSY, '45380', unit(2), (300, 360))

    def test_rdw_a_denied_stone_extraction(self):
        self.walk(TO.denied_stone_ercp, DENIED_STONE, '43264', unit(5), (600, 660))

    def test_rdw_a_live_item_shows_what_it_quotes(self):
        """Read time's own item (a live question): reinstating 45380 makes the date a procedure day, so 99213 asks the
        separately identifiable visit live - its row shows the visit's passage the item quotes (the code's own cited
        fragment, a single word of the synthetic letters, shows nothing a member could read: questions.passages)."""
        scene = self.scene(TO.office_with_denied_biopsy().build(), TO.VISITS_AND_DENIAL)
        self.decide(scene, '45380', review.REINSTATE)
        [question] = self.views(scene)['99213'].questions
        self.assertEqual((question['id'], question['fact']), ('', 'separate_em'))
        [row] = self.rows_of(self.payload(scene), '99213')
        self.assertEqual(offsets(row), [unit(1)])  # behaviour (red on the reference: no passage)

    def test_boundary_an_item_that_quotes_nothing_keeps_its_codes_passages(self):
        """43273's ADDON row (an item from codes alone: it quotes no passage) shows the code's own passage, as before."""
        scene = self.scene(ercp_cited(False), CITED, text=TEXT)
        stored = self.proposal(scene, '43273')
        self.assertEqual(stored.support['item']['message'], wording.Message.ADDON.value)
        self.assertNotIn('quoted', stored.support['item'])
        [row] = self.rows_of(self.payload(scene), '43273')
        self.assertEqual(offsets(row), [unit(3)])


def row_passages(record, found, rendered_proposal, family):
    """The member row's passages of ``found``'s item as answers._passages_of shows them over a stand-in assessment whose
    revision is TEXT (the record's act and quoted passages as the row reads them; a tree whose rows read no quoted
    record is read as it is)."""
    act = wording.recorded_act(record.get('act_ref'))
    member = (found.item.held.fact, family, found.code)
    proposal = SimpleNamespace(evidence=[{'context_index': 0, 'start': span.start, 'end': span.end,
                                          'text': TEXT[span.start:span.end], 'exact': True}
                                         for span in found.evidence.kept], support=rendered_proposal.support)
    assessment = SimpleNamespace(revision=SimpleNamespace(text=TEXT, pages=()), services={})
    kwargs = {}
    if 'quoted_named' in inspect.signature(answers._passages_of).parameters:
        quoted = wording.recorded_quoted(record.get('quoted'))
        kwargs['quoted_named'] = {member: quoted} if quoted else {}
    shown = answers._passages_of(assessment, [member], {found.code: [proposal]}, {member: act} if act else {}, **kwargs)
    return [(passage['start'], passage['end']) for passage in shown]


def item_quotes(fill):
    """Every span ``fill``'s sentence quotes - its act's words, its counterpart's, each statement's - each once."""
    out = []
    for span in (*fill.words, *fill.whole_words, *(span for statement in fill.statements for span in statement)):
        if (span.start, span.end) not in out:
            out.append((span.start, span.end))
    return out


QUOTED_SCENES = (
    ('office denied biopsy', TO.office_with_denied_biopsy, DENIED_BIOPSY),
    ('denied stone ercp', TO.denied_stone_ercp, DENIED_STONE),
    ('denial beside a snare', TA.denial_beside_a_snare, (('45385', 2), ('45378', 1), ('45380', 3))),
    ('two sessions', TA.two_sessions, TA.TWO),
)


class R2DWQuotedEnumeration(SimpleTestCase):
    """Over the RBWX-1 scenes and two sessions, each base and every one-fact perturbation: every row shows every passage
    its item's question quotes (the row's cap aside, a passage overlapping a shown one counted shown), and a row whose
    act record holds no span shows the code's own passages - never none."""

    def test_rdw_every_row_shows_what_its_item_quotes(self):
        seen = {'items': 0, 'no span': 0}
        for name, label, R, result, found in corpus(QUOTED_SCENES):
            proposal = rendered(found, result, R)
            record = proposal.support['item']
            shown = row_passages(record, found, proposal, proposal.family)
            quotes = [(a, b) for a, b in item_quotes(found.item.fill) if 0 <= a < b <= len(TEXT)]
            seen['items'] += 1
            with self.subTest(scene=name, perturbation=label, code=found.code, message=found.item.message.value):
                if quotes or found.evidence.kept:
                    self.assertTrue(shown)  # never an empty row (red on the reference: 190 such items)
                if len(shown) < answers.MAX_ROW_PASSAGES:
                    for a, b in quotes:
                        self.assertTrue(any(start < b and a < end for start, end in shown), (a, b, shown))
                act = wording.recorded_act(record.get('act_ref'))
                if act is not None and not act[0]:
                    seen['no span'] += 1
                    own = [(span.start, span.end) for span in found.evidence.kept]
                    self.assertTrue(set(own) <= set(shown) or len(shown) == answers.MAX_ROW_PASSAGES, (own, shown))
        self.assertGreater(seen['no span'], 100)  # the class is reached (refute-words2: 190 over its corpus)


# --- RBWX-2: the examination of this procedure, only for the code's own session --------------------------------------

def claimed_dre_beside_a_visit():
    """An office visit X1 (99213's visit E1) and a colonoscopy X2 whose claimed digital examination E2 (device manual
    unresolved) and colonoscope's examination E3 have no date relation: the visit's same-day item rests on E2
    (DIGITAL_SCOPE), the held session X2's examination - not the visit's."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.OFFICE_EM, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, ct.Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
    doc.session(2, ct.SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
    doc.exam(2, session=EF.X(2), device=EF.unres(ct.Device.MANUAL), date=None)
    doc.exam(3, session=EF.X(2), date=None)
    return doc


def sigmoidoscopy_undated():
    """test_assess.office_and_sigmoidoscopy with the sigmoidoscopy's examination E2's date relation unresolved."""
    doc = TA.office_and_sigmoidoscopy()
    doc.exam(2, session=EF.X(2), date=EF.unres(ct.DateRelation.ON_DATE_OF_SERVICE))
    return doc


class R2DWAnotherSessionsExamination(R2WWorld):
    """An E/M code's same-day item about another session's examination is named as another act - its row, statement
    and the code's qualification - with that examination's passage; the door binds its fingerprint from that row and the
    AGAIN keeps it."""

    TIME_PROMPT = 'Was the examination done at this encounter, on the date of service?'
    TIME_QUALIFICATION = 'CPT Studio could not confirm from the document whether the examination was done at this encounter.'

    def walk(self, build, form, statement_words, prompt=TIME_PROMPT, qualification=TIME_QUALIFICATION):
        # r2e (DECISIONS D303, I1; WX3-2): the row asks the question its item's own form asks, the act renamed -
        # the date for TIME, DIGITAL_SCOPE's own question for DIGITAL_SCOPE (``prompt``, ``qualification``)
        scene = self.scene(build().build(), (('99213', 1),), text=TEXT)
        stored = self.proposal(scene, '99213')
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '99213')
        quals = self.code_row(payload, '99213')['why']['qualifications']
        for words in (row['prompt'], row['statement'], *quals):
            self.assertNotIn(EXAMINATION_WORDS, words)  # behaviour first (red on the reference)
        self.assertEqual(stored.support['item']['form'], form)
        self.assertEqual(row['prompt'], prompt)
        self.assertEqual(row['statement'], statement_words)
        self.assertEqual(row['id'], answers.detail_id('event_time', stored.family, '99213', form))
        self.assertIn(qualification, quals)
        self.assertIn(unit(2), offsets(row))  # the examination's own passage (E2)
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])
        view = self.views(scene)['99213']
        self.assertEqual((view.status, view.answered_form), ('excluded', form))
        self.again(scene)
        [row] = self.rows_of(self.payload(scene), '99213')
        self.assertEqual((row['prompt'], row['saved']['value']), (prompt, ND))
        return scene

    STATEMENT = 'From the document, CPT Studio could not confirm whether the examination was done at this encounter.'

    def test_rdw_an_undated_colonoscopy_beside_the_visit(self):
        self.walk(TO.office_and_undated_colonoscopy, 'act_time', self.STATEMENT)

    def test_rdw_an_undated_sigmoidoscopy_beside_the_visit(self):
        self.walk(sigmoidoscopy_undated, 'act_time', self.STATEMENT)

    def test_rdw_a_claimed_digital_examination_of_another_session(self):
        """DIGITAL_SCOPE names the held session's examination (X2's): for the visit it is another act - r2e (DECISIONS
        D303, I1; WX3-2): asked DIGITAL_SCOPE's own question, the act renamed (ACT_DIGITAL), never its key's date."""
        missing = 'the technique of an examination the document states, which may be the examination'
        scene = self.walk(claimed_dre_beside_a_visit, 'act_digital', f'From the document, CPT Studio could not confirm '
                          f'{missing}.', prompt='Is the examination documented as performed, in full or in part, on the '
                          'date of service?', qualification=f'CPT Studio could not confirm from the document {missing}.')
        self.assertEqual(self.proposal(scene, '99213').support['item']['message'],
                         wording.Message.DIGITAL_SCOPE.value)

    def test_boundary_the_codes_own_sessions_examination_keeps_its_words(self):
        """45385 (the snare of X2) and 45378 asked the same examination's date: X2 is their own session."""
        scene = self.scene(TO.office_and_undated_colonoscopy().build(), (('99213', 1), ('45385', 3), ('45378', 2)),
                           text=TEXT)
        for code in ('45385', '45378'):
            with self.subTest(code=code):
                stored = self.proposal(scene, code)
                self.assertEqual(stored.support['item']['form'], wording.FORM_SESSION_TIME)
                [row] = self.rows_of(self.payload(scene), code)
                self.assertEqual(row['prompt'], answers.FORM_PROMPTS[wording.FORM_SESSION_TIME])
                self.assertIn(EXAMINATION_WORDS, row['prompt'])
                self.assertEqual(offsets(row), [unit(2)])


def _holds_examination(R, session):
    """r2e (D303, WX3-1): whether a session's family holds an examination (an E/M visit's does not)."""
    kind = F.fact(R, session, Attribute.KIND)
    if kind.result is not Result.SUPPORTED or not isinstance(kind.value, ct.SessionKind):
        return True
    return ct.Kind.EXAMINATION in F.family_kinds(kind.value)


SESSION_SCENES = (
    ('office undated colonoscopy', TO.office_and_undated_colonoscopy, (('99213', 1),)),
    ('office undated colonoscopy + codes', TO.office_and_undated_colonoscopy, (('99213', 1), ('45385', 3),
                                                                               ('45378', 2))),
    ('office + undated sigmoidoscopy', sigmoidoscopy_undated, (('99213', 1),)),
    ('claimed dre beside a visit', claimed_dre_beside_a_visit, (('99213', 1),)),
    ('colonoscopy', EF.colonoscopy, (('45385', 2), ('45378', 1))),
)


class R2DWSessionEnumeration(SimpleTestCase):
    """Over the RBWX-2 scenes and EF.colonoscopy, each base and every one-fact perturbation: no member sentence of an item
    about the examination of a session that is not the code's own (its subject's established session not among the
    sessions of the acts the code binds) says "the examination of this procedure" - its row, its statement, its
    qualification - and every item whose row says it is about the code's own session."""

    def test_rdw_only_the_codes_own_session_is_this_procedure(self):
        seen = {'other': 0, 'own': 0}
        for name, label, R, result, found in corpus(SESSION_SCENES):
            record = rendered(found, result, R).support['item']
            form = record.get('form') or ''
            act = wording.recorded_act(record.get('act_ref'))
            kinds = (act[1], act[2]) if act is not None else ('', '')
            row = answers.row_prompt(found.item.held.fact, form, *kinds)
            sentences = [row]
            if form in answers.FORM_MISSING:
                sentences.append(wording.form_text(answers.FORM_MISSING[form], *kinds))
            if form in customer_api.FORM_WORDS:
                sentences.append(wording.form_text(customer_api.FORM_WORDS[form], *kinds))
            own = tuple(dict.fromkeys((*found.evaluation.bindings.values(), *found.evaluation.supporting)))
            sessions = {session_of(R, event) for event in own} - {None}
            subject = found.item.held.subject
            # r2e (DECISIONS D303, I1; WX3-1): never another session's merely because a session slot is not established -
            # an examination whose session is not established is the code's own session's when it may be one of them
            # (its session fact possibly one of the code's sessions whose family holds an examination), or when the
            # code's own session is not established
            slot = F.fact(R, subject, Attribute.SESSION) if subject is not None and subject.family is IdFamily.EVENT \
                else None
            may = (session_of(R, subject) is None and slot is not None
                   and any(F.possibly(slot, session) and _holds_examination(R, session) for session in sessions))
            mine = (subject is None or subject in own or session_of(R, subject) in sessions or may
                    or (not sessions and found.item.message is not Q.MessageId.DIGITAL_SCOPE))
            if subject is not None and subject.family is IdFamily.EVENT and found.item.message is Q.MessageId.DIGITAL_SCOPE \
                    and session_of(R, subject) is None:
                continue  # DIGITAL_SCOPE's held session falls back to the code's acts' (overlay: _held_session)
            says = any(EXAMINATION_WORDS in sentence for sentence in sentences)
            with self.subTest(scene=name, perturbation=label, code=found.code, message=found.item.message.value):
                if not mine:
                    seen['other'] += 1
                    self.assertFalse(says, sentences)  # red on the reference: 81 such items
                elif says:
                    seen['own'] += 1
        self.assertGreater(seen['other'], 50)
        self.assertGreater(seen['own'], 50)


class R2DWSessionForms(SimpleTestCase):
    """wording.item_record's examination rule, unit by unit: each form that names "the examination of this procedure"
    keeps it only for the code's own session (``own_session``) - else the form of its key naming the act by its kind."""

    @staticmethod
    def item(message, fact, family=ct.SessionKind.COLONOSCOPY):
        from studio.interpretation.engine.types import HeldFact, ItemKind
        held = HeldFact(fact=fact, attribute=None, subject=Id(IdFamily.EVENT, 2), result=None,
                        kind=ItemKind.QUESTION, cause='reading_unknown', reason=None, spans=(), rank=4)
        return Q.Item(held=held, message=message,
                      fill=Q.Fill(act=ct.Kind.EXAMINATION, family=family, words=(ct.Span(200, 260),)))

    def test_rdw_another_sessions_examination_is_another_act(self):
        own = (Id(IdFamily.EVENT, 1),)
        # r2e (DECISIONS D303, I1; WX3-1): renaming the act changes its name only - the session's DOUBT and STATUS keep
        # row 7's done (ACT_DOUBT), DIGITAL_SCOPE and UNLISTED_SCOPE their own questions (ACT_DIGITAL, ACT_UNLISTED),
        # whatever their key
        for message, fact, session_form, other_form in (
                (Q.MessageId.DOUBT, 'performed_status', 'session_doubt', 'act_doubt'),
                (Q.MessageId.ENTRY, 'event_entry', 'session_entry', 'act_entry'),
                (Q.MessageId.TIME, 'event_time', 'session_time', 'act_time'),
                (Q.MessageId.PERFORMER, 'event_performer', 'session_performer', 'act_performer'),
                (Q.MessageId.STATUS, 'performed_status', 'session_status', 'act_doubt')):
            with self.subTest(message=message.value):
                found = self.item(message, fact)
                for own_session, form in ((True, session_form), (False, other_form)):
                    got, record = wording.item_record(wording.Message(message.value), found.fill, found.held.subject,
                                                      own, own_session=own_session, fact=fact)
                    self.assertEqual(got, form)
                    if not own_session:
                        self.assertEqual(wording.recorded_act(record), (((200, 260),), 'examination', ''))
                        self.assertNotIn(EXAMINATION_WORDS, answers.row_prompt(fact, got, 'examination'))
        # DIGITAL_SCOPE and UNLISTED_SCOPE name the held session's examination: by their item's own question (r2e,
        # D303 I1: never by the item's key)
        for message, fact, other_form in ((Q.MessageId.DIGITAL_SCOPE, 'event_time', 'act_digital'),
                                          (Q.MessageId.UNLISTED_SCOPE, 'performed_status', 'act_unlisted'),
                                          (Q.MessageId.DIGITAL_SCOPE, 'conflict:examination', 'act_digital')):
            with self.subTest(message=message.value, fact=fact):
                found = self.item(message, fact)
                self.assertIn(wording.item_record(wording.Message(message.value), found.fill, found.held.subject, own,
                                                  own_session=True, fact=fact)[0], wording.EXAMINATION_FORMS)
                self.assertEqual(wording.item_record(wording.Message(message.value), found.fill, found.held.subject,
                                                     own, own_session=False, fact=fact)[0], other_form)


# --- RBWX-3: the door records the shown question's fingerprint; read time binds it as the passes do -------------------

class R2DWHeldSession(SimpleTestCase):
    """DIGITAL_SCOPE names the held session's examination (engine/questions._held_session): where its claimed
    examination's session is not established, the held session is the session of the code's own act - the code's own,
    so its form says "the examination of this procedure", as before (both trees)."""

    def test_boundary_an_unplaced_claimed_examination_names_the_codes_own_session(self):
        for session in (EF.unres(EF.X(2)), EF.doubted(EF.X(2))):
            doc = EF.Doc()
            doc.session(2, ct.SessionKind.COLONOSCOPY, reached=[EF.sup(ct.Extent.CECUM)])
            doc.exam(2, session=session, device=EF.unres(ct.Device.MANUAL), date=None)
            doc.exam(3, session=EF.X(2), date=None)
            R = doc.build()
            result = TA.run(R, ('45378', 3))
            [found] = result.codes
            with self.subTest(session=session.result.value):
                self.assertIs(found.item.message, Q.MessageId.DIGITAL_SCOPE)
                self.assertEqual(rendered(found, result, R).support['item']['form'], wording.FORM_DIGITAL_SCOPE)


class R2DWShownQuestion(R2WWorld):
    """refute-consistency C7's scene (99215, 99417, 45330): "Cannot confirm" on 99215's separate_em row moves 99417's item
    to its ADDON row (D283's passes), a question the reading with no answers does not ask. The member's "Not documented"
    on that row is recorded with the fingerprint of the question the row shows - the live ADDON item's, the one
    engine/assess stores for that item - and read time binds it as the passes bind it: 99417 is excluded by it before the
    AGAIN, and the AGAIN applies it (one view)."""

    def primary_answer(self, scene):
        [row] = [row for row in self.rows_of(self.payload(scene), '99215') if row['fact'] == 'separate_em']
        [answer] = self.save(scene, row, CC)
        return answer

    def addon_answer(self, scene):
        [row] = [row for row in self.rows_of(self.payload(scene), '99417') if row['fact'] == 'performed_status']
        self.assertIn('primary codes', row['prompt'])
        [answer] = self.save(scene, row, ND)
        self.assertTrue(answer.question)  # behaviour first (red on the reference: recorded with no fingerprint)
        return answer

    def assert_excluded_by(self, scene, answer, applied):
        view = self.views(scene)['99417']
        self.assertEqual((view.status, view.reason, view.answered, view.answered_form),
                         ('excluded', review.DETAIL_UNAVAILABLE, 'performed_status', wording.FORM_ADDON))
        with self.reads(scene):
            assessment = self.fresh(scene).current_assessment
            done, bound, earlier = review.answer_states(assessment)
            listed = answers.earlier_answers(self.fresh(scene), assessment)
        self.assertIn(answer.pk, [item.pk for item in (done if applied else bound)])
        self.assertNotIn(answer.pk, [item.pk for item, _ in earlier])
        self.assertNotIn(str(answer.pk), [item['answer_id'] for item in listed])
        [row] = [row for row in self.rows_of(self.payload(scene), '99417') if row['fact'] == 'performed_status']
        self.assertEqual(row['saved']['value'], ND)
        self.assertFalse([text for text in self.blockers(scene) if text.startswith('99417')])

    def test_rdw_answered_before_the_again(self):
        scene = self.scene(TO.c7_scene().build(), TO.C7_CODES)
        self.primary_answer(scene)
        self.assertEqual(self.proposal(scene, '99417').support['item']['fact'], 'separate_em')
        answer = self.addon_answer(scene)
        self.assert_excluded_by(scene, answer, applied=False)
        self.again(scene)
        stored = self.proposal(scene, '99417')
        self.assertEqual((stored.bucket, stored.support['answered']['answers']),
                         (models.Proposal.EXCLUDED, [str(answer.pk)]))
        self.assertEqual(stored.support['question'], answer.question)  # the engine's own fingerprint of that item
        self.assert_excluded_by(scene, answer, applied=True)

    def test_rdw_answered_after_the_again(self):
        scene = self.scene(TO.c7_scene().build(), TO.C7_CODES)
        self.primary_answer(scene)
        self.again(scene)
        stored = self.proposal(scene, '99417')
        self.assertEqual(stored.support['item']['message'], wording.Message.ADDON.value)
        answer = self.addon_answer(scene)
        self.assertEqual(answer.question, stored.support['question'])
        self.assert_excluded_by(scene, answer, applied=False)
        self.again(scene)
        self.assertEqual(self.proposal(scene, '99417').bucket, models.Proposal.EXCLUDED)
        self.assert_excluded_by(scene, answer, applied=True)

    def test_boundary_no_reading_with_the_standing_answers_asks_it(self):
        """The primary's answer withdrawn: no reading asks 99417's ADDON row - the answer is listed no longer asked and
        excludes nothing (99417 asks its separate_em again)."""
        scene = self.scene(TO.c7_scene().build(), TO.C7_CODES)
        first = self.primary_answer(scene)
        [row] = [row for row in self.rows_of(self.payload(scene), '99417') if row['fact'] == 'performed_status']
        [answer] = self.save(scene, row, ND)
        with self.reads(scene):
            answers.revoke_answer(self.fresh(scene), self.user, str(first.pk))
        view = self.views(scene)['99417']
        self.assertEqual((view.status, [q['fact'] for q in view.questions]), ('needs_clarification', ['separate_em']))
        with self.reads(scene):
            listed = answers.earlier_answers(self.fresh(scene), self.fresh(scene).current_assessment)
        [found] = [item for item in listed if item['answer_id'] == str(answer.pk)]
        self.assertEqual(found['why'], VQ.NO_LONGER_ASKED)


class R2DWDoorUnits(SimpleTestCase):
    def test_rdw_the_door_records_the_shown_question_where_the_binding_reading_asks_none(self):
        key = ('99417', 'gi.office_em', 'performed_status')
        row = SimpleNamespace(form='addon')
        shown = {'fingerprints': {key: 'L' * 64}}
        self.assertEqual(answers._bound_question(None, {}, row, key, {}, {}, dict(shown)), 'L' * 64)

    def test_boundary_the_binding_readings_question_of_the_rows_form(self):
        key = ('99417', 'gi.office_em', 'performed_status')
        row = SimpleNamespace(form='addon')
        shown = {'fingerprints': {key: 'L' * 64}}
        self.assertEqual(answers._bound_question(None, {}, row, key, {key: 'S' * 64}, {key: frozenset({'addon'})},
                                                 dict(shown)), 'S' * 64)


def held_status_addon():
    """test_assess.office_prolonged with the prolonged time's status unresolved: 99417's item is its STATUS question
    (performed_status), engine-read by its fingerprint."""
    doc = TA.office_prolonged()
    doc.act(2, ct.Kind.EM_PROLONGED, status=EF.unres(ct.Status.PERFORMED))
    return doc


class R2DWBindsByFingerprint(SimpleTestCase):
    """Read time binds an answer the engine reads as engine/assess's passes bind it: only to the item whose fingerprint
    it carries. An answer under 99417's performed_status key carrying another item's fingerprint excludes 99417 at
    neither half (assess records it asked differently); carrying its STATUS item's own, at both. The stored rows carry
    the fingerprint engine/assess stored for each item (support['question']), as the renderer records it."""

    CODES = (('99215', 1), ('99417', 2))

    def both(self, question):
        import dataclasses

        plain = TA.by_code(TA.run(held_status_addon().build(), *self.CODES))
        self.assertEqual(plain['99417'].item.message, Q.MessageId.STATUS)
        given = TA.answer(plain['99417'], question=question)
        engine = TA.by_code(TA.run(held_status_addon().build(), *self.CODES, answers=(given,)))['99417']
        case = TO.Case(held_status_addon().build(), *self.CODES)
        fingerprints = {p.key: p.question for p in case.assessment.codes}
        rows = [dataclasses.replace(row, support={**row.support, 'question': fingerprints[row.key]})
                for row in case.rows]
        key = next(p.key for p in rows if p.code == '99417')
        view = overlay.review_view(rows, {}, completeness=case.completeness, facts=case.R, member=case.member,
                                   answers=[{'code': given.code, 'family': given.family, 'fact': given.fact,
                                             'value': given.value, 'question': given.question}])[key]
        return plain['99417'], engine, view

    def test_rdw_another_items_fingerprint_binds_nothing(self):
        plain, engine, view = self.both('A' * 64)
        self.assertNotEqual(view.status, 'excluded')  # behaviour first (red on the reference: bound by its key)
        self.assertEqual(engine.status, AS.Outcome.NEEDS_CLARIFICATION)
        self.assertEqual(view.status, 'needs_clarification')

    def test_boundary_its_own_items_fingerprint_binds(self):
        plain, engine, view = self.both(None)
        self.assertEqual(engine.status, AS.Outcome.EXCLUDED)
        self.assertEqual((view.status, view.reason), ('excluded', review.DETAIL_UNAVAILABLE))


# --- RBWX-4: reinstated, read through bucket_of over the effective view ------------------------------------------------

class R2DWReinstatedReaders(R2WWorld):
    """W2R-1's scene (ercp_cited, ADDON alone): 43273's "Not documented" is the engine's after the AGAIN; reinstating 43264
    reopens 43273 (READY), which the reviewer approves as the selected code it was - never a reinstatement; revoking the
    reinstatement of 43264 excludes 43273 by its answer again - never counted as a reinstated, selected code."""

    def setUp(self):
        super().setUp()
        self.scene_ = self.scene(ercp_cited(False), CITED)
        [row] = self.rows_of(self.payload(self.scene_), '43273')
        self.save(self.scene_, row, ND)
        self.again(self.scene_)
        self.reinstatement = self.decide(self.scene_, '43264', review.REINSTATE)

    def readings(self):
        scene = self.scene_
        with self.reads(scene):
            assessment = self.fresh(scene).current_assessment
            codes = review.reinstated_codes(assessment)
            completeness = review.reviewed_completeness(assessment)
            draft = reports.snapshot(self.fresh(scene), reports.DRAFT)
            approved = review.approved_items(assessment)
        items = {item['code']: item for item in draft['proposals']}
        return [code for code, _ in codes], completeness.get('reinstated'), items, approved

    def test_rdw_a_reopened_code_is_no_reinstatement(self):
        scene = self.scene_
        self.assertEqual(self.views(scene)['43273'].status, 'ready')
        with self.reads(scene):
            review.record_decision(encounter=self.fresh(scene), proposal=self.proposal(scene, '43273'),
                                   action=review.APPROVE, user=self.user, membership=self.membership,
                                   note='r2dw synthetic approval',
                                   acknowledgement=review.ACKNOWLEDGEMENTS[self.user.actor_kind])
        codes, listed, items, approved = self.readings()
        self.assertEqual(codes, ['43264'])  # behaviour first (red on the reference: 43273 named reinstated)
        self.assertEqual(listed, ['43264'])
        self.assertFalse(items['43273']['reinstated'])
        self.assertFalse(next(item for item in approved if item['code'] == '43273')['reinstated'])
        with self.reads(scene):
            review.record_decision(encounter=self.fresh(scene), proposal=self.reinstatement.proposal,
                                   action=review.REVOKE, user=self.user, membership=self.membership,
                                   note='r2dw synthetic revoke')
        self.assertEqual(self.views(scene)['43273'].reason, review.DETAIL_UNAVAILABLE)  # its answer excludes it again
        codes, listed, items, approved = self.readings()
        self.assertEqual(codes, [])  # red on the reference: 43273 counted as a reinstated, selected code
        self.assertFalse(listed)
        self.assertEqual((items['43273']['list'], items['43273']['reinstated']), ('excluded', False))

    def test_rdw_the_date_row_reads_a_reopened_code_as_selected(self):
        """The date of service's row (shown here as for a member's date the document does not give: ``_date_in_use``)
        lists the codes that depend on it - the codes the review reads as selected, the reopened 43273 among them."""
        scene = self.scene_
        with mock.patch.object(answers, '_date_in_use', return_value=True):
            payload = self.payload(scene)
        [row] = [row for row in payload['details_needed'] if row['fact'] == answers.DATE_FACT]
        self.assertIn('43273', row['affects'])  # behaviour (red on the reference: the stored bucket, excluded)
        self.assertNotIn('43264', row['affects'])

    def test_boundary_a_reinstated_exclusion_is_one(self):
        codes, listed, items, _ = self.readings()
        self.assertEqual((codes, listed), (['43264'], ['43264']))
        self.assertTrue(items['43264']['reinstated'])
        self.assertFalse(items['43273']['reinstated'])


# --- RBWX-5: the answered row shows the item the answer was bound to --------------------------------------------------

class R2DWAnsweredRows(R2WWorld):
    """W2R-1's held scene (ercp_cited(True)): after the AGAIN and the reinstatement of 43264, 43273 is reopened and asks
    its live cannulation question about E2 (an act it does not bind), with E2's passage. The member's "Not documented"
    there is bound to that live item; the row that shows it in effect keeps that item's words and passage, before and
    after the AGAIN."""

    def test_rdw_an_answer_to_a_live_item_keeps_its_passage(self):
        scene = self.scene(ercp_cited(True), CITED)
        [row] = self.rows_of(self.payload(scene), '43273')
        self.save(scene, row, ND)
        self.again(scene)
        self.decide(scene, '43264', review.REINSTATE)
        [row] = self.rows_of(self.payload(scene), '43273')
        self.assertEqual((row['fact'], offsets(row)), ('cannulation', [unit(2)]))
        [answer] = self.save(scene, row, ND)
        for again in (False, True):
            if again:
                self.again(scene)
            with self.subTest(again=again):
                view = self.views(scene)['43273']
                self.assertEqual((view.status, view.answered), ('excluded', 'cannulation'))
                [row] = self.rows_of(self.payload(scene), '43273')
                self.assertEqual(row['saved']['value'], ND)
                self.assertEqual(offsets(row), [unit(2)])  # behaviour (red on the reference: no passage)
                self.assertEqual(row['prompt'], answers.PROMPTS['cannulation'])
                self.assertEqual(view.answered_question['message'], wording.Message.CANNULATION.value)
                self.assertEqual(wording.recorded_act(view.answered_question['act_ref'])[0], (unit(2),))

    def test_boundary_an_answer_to_the_stored_item_keeps_the_stored_items_row(self):
        """45385's row 7 item about the examination E1 answered: the row shows E1's passage, from the stored item."""
        doc = EF.colonoscopy()
        doc.exam(1, date=EF.unres(ct.DateRelation.ON_DATE_OF_SERVICE))
        scene = self.scene(doc.build(), (('45385', 2),), text=TEXT)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.save(scene, row, CC)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual((row['saved']['value'], offsets(row)), (CC, [unit(1)]))
