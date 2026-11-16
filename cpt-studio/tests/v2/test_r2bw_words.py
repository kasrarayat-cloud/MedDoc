"""r2b (DECISIONS D297: repair round r2b's words items W2R-1, W2R-2, W2R-3, W2R-4 and words Q2, Q5). SYNTHETIC only:
tests/v2's own FactSet builders over test_assess's synthetic letters (r2w_world: the renderer's child, persist, read time,
the customer payload, the details door and the AGAIN recompute); nothing is sent anywhere.

- W2R-1: an answer bound to an item whose hold read time's recount releases under the current decisions no longer
  excludes at read time - whether it was given before or after the decision and whether or not the AGAIN has run: the
  code is read with its live holds, as the selected code it was (every reader of its bucket reads it so), and the answer
  is listed no longer asked.
- W2R-2: an item whose act is not the code's own act - the held session's examination on another code's row, a
  counterpart act such as SAME_DUCT's - is worded naming that act, with that act's own passages, chosen by the item's
  slots; never "this act" over the code's own passage. One test enumerates every message whose item names another act.
- W2R-3: codes share a service row only when their items ask the service's one question; any other message keyed by a
  service fact is its code's own row, its id naming its form, and the door binds each item's fingerprint only from it.
- W2R-4: an item of a non-empty member form driven through every branch that carries one.
- Q2: every explanation whose key row's statement is untrue of the established failing fact has its own form.
- Q5: conflict:em_prolonged worded as the items word it.
Each rule: an input it must change and a boundary it must leave alone."""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import answers, customer_api, jobs, models, reports, review
from studio.interpretation import overlay, wording
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine.types import IdFamily
from studio.validation import questions as VQ
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_overlay as TO
from tests.v2.r2w_world import R2WWorld
from tests.v2.test_evaluate import stent_placement
from tests.v2.test_r2w_member_words import CITED, ercp_cited

ND, CC = models.MemberAnswer.NOT_DOCUMENTED, models.MemberAnswer.CANNOT_CONFIRM
STATUS_ROW = answers.PROMPTS['performed_status']
# test_assess's synthetic letters with a space every seventh character, so a code's own passages have words to show
TEXT = ''.join(' ' if index % 7 == 6 else TA.TEXT[index] for index in range(len(TA.TEXT)))


def offsets(row):
    return [(passage['start'], passage['end']) for passage in row['passages']]


def unit(n):
    span = EF.unit(n)
    return (span.start, span.end)


# --- W2R-1: an answer whose item's hold read time's recount releases ---------------------------------------------------

class R2BWReleasedAnswer(R2WWorld):
    """The F2 scene of r2 (ercp_cited): 43273 held by its ADDON row (43264 EXCLUDED by its cited denial, reinstatable)
    and, with ``held``, by the ERCP's cannulation. The member's "Not documented" to the ADDON row is the engine's own
    answer once the AGAIN has run (its fingerprint): a reviewer's reinstatement of 43264, a counted primary, releases
    that hold, so the answer excludes nothing, whichever came first."""

    def addon_answer(self, scene):
        [row] = self.rows_of(self.payload(scene), '43273')
        self.assertIn('primary codes', row['prompt'])
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, self.proposal(scene, '43273').support['question'])
        return answer

    def assert_read_with_its_live_holds(self, scene, answer, held, frozen=True):
        view = self.views(scene)['43273']
        self.assertNotEqual(view.status, 'excluded')  # behaviour first (red on the reference)
        self.assertEqual((view.status, view.reason), ('needs_clarification' if held else 'ready', ''))
        # the engine's own record of the answer (its marker) once the AGAIN has read it
        self.assertEqual(getattr(view, 'released_answer', ''), 'performed_status' if frozen else '')
        self.assertEqual([q['fact'] for q in view.questions], ['cannulation'] if held else [])
        payload = self.payload(scene)
        code = self.code_row(payload, '43273')
        self.assertEqual(code['status'], 'needs_detail' if held else 'ready')
        self.assertEqual(code['why']['qualifications'], [customer_api.QUESTION_WORDS['cannulation']] if held else [])
        self.assertEqual([row['fact'] for row in self.rows_of(payload, '43273')], ['cannulation'] if held else [])
        with self.reads(scene):
            earlier = answers.earlier_answers(self.fresh(scene), self.fresh(scene).current_assessment)
            applied, _, listed = review.answer_states(self.fresh(scene).current_assessment)
        [found] = [item for item in earlier if item['answer_id'] == str(answer.pk)]
        self.assertEqual(found['why'], VQ.NO_LONGER_ASKED)
        self.assertNotIn(answer.pk, [item.pk for item in applied])
        self.assertIn(answer.pk, [item.pk for item, _ in listed])
        blockers = self.blockers(scene)
        self.assertFalse([text for text in blockers if text.startswith('43273 was excluded by a documentation check')])
        self.assertIn('43273 has an open clarification' if held else '43273 has no decision', blockers)
        proposal = self.proposal(scene, '43273')
        with self.reads(scene):
            actions = review.allowed_actions(proposal, self.fresh(scene).current_assessment, self.membership)
        self.assertEqual(actions, [review.REJECT] if held else [review.APPROVE, review.REJECT])
        return view

    def test_rbw_answer_then_decision_then_again(self):
        scene = self.scene(ercp_cited(True), CITED)
        answer = self.addon_answer(scene)
        self.decide(scene, '43264', review.REINSTATE)
        before = self.assert_read_with_its_live_holds(scene, answer, True, frozen=False)
        self.again(scene)
        stored = self.proposal(scene, '43273')
        self.assertEqual((stored.bucket, stored.support['answered']['fact']), (models.Proposal.EXCLUDED,
                                                                              'performed_status'))
        after = self.assert_read_with_its_live_holds(scene, answer, True)
        self.assertEqual((after.status, after.questions), (before.status, before.questions))  # one view (D283)

    def test_rbw_answer_then_again_then_decision(self):
        scene = self.scene(ercp_cited(True), CITED)
        answer = self.addon_answer(scene)
        self.again(scene)
        self.assertEqual(self.views(scene)['43273'].status, 'excluded')
        self.decide(scene, '43264', review.REINSTATE)
        self.assert_read_with_its_live_holds(scene, answer, True)

    def test_rbw_a_released_addon_alone_is_ready_and_approved(self):
        """ADDON alone (cannulation achieved): read READY whatever the order; approvable as the selected code it was,
        approved, listed approved in the report and in the approved codes - never as a reinstatement."""
        scene = self.scene(ercp_cited(False), CITED)
        answer = self.addon_answer(scene)
        self.again(scene)
        self.decide(scene, '43264', review.REINSTATE)
        self.assert_read_with_its_live_holds(scene, answer, False)
        with self.reads(scene):
            draft = reports.snapshot(self.fresh(scene), reports.DRAFT)
        [item] = [item for item in draft['proposals'] if item['code'] == '43273']
        self.assertEqual(item['list'], 'undecided')  # never "excluded": the selected code it was, to decide
        with self.reads(scene):
            review.record_decision(encounter=self.fresh(scene), proposal=self.proposal(scene, '43273'),
                                   action=review.APPROVE, user=self.user, membership=self.membership,
                                   note='r2bw synthetic approval',
                                   acknowledgement=review.ACKNOWLEDGEMENTS[self.user.actor_kind])
            approved = review.approved_items(self.fresh(scene).current_assessment)
            draft = reports.snapshot(self.fresh(scene), reports.DRAFT)
        self.assertEqual(self.code_row(self.payload(scene), '43273')['status'], 'approved')
        [found] = [item for item in approved if item['code'] == '43273']
        self.assertFalse(found['reinstated'])
        [item] = [item for item in draft['proposals'] if item['code'] == '43273']
        self.assertFalse(item['reinstated'])  # approved as the selected code it was, never as a reinstatement
        self.assertFalse([text for text in self.blockers(scene) if '43273' in text])

    def test_boundary_with_no_decision_the_answer_excludes(self):
        """No decision releases the ADDON hold: the engine's answer stands before and after the AGAIN (applied)."""
        scene = self.scene(ercp_cited(True), CITED)
        answer = self.addon_answer(scene)
        for again in (False, True):
            if again:
                self.again(scene)
            with self.subTest(again=again):
                view = self.views(scene)['43273']
                self.assertEqual((view.status, view.reason, getattr(view, 'released_answer', '')),
                                 ('excluded', review.DETAIL_UNAVAILABLE, ''))
                self.assertEqual(self.code_row(self.payload(scene), '43273')['status'], 'excluded')
                with self.reads(scene):
                    earlier = answers.earlier_answers(self.fresh(scene), self.fresh(scene).current_assessment)
                self.assertNotIn(str(answer.pk), [item['answer_id'] for item in earlier])


class R2BWReleasedOverlayAnswer(R2WWorld):
    """W2R-1's other half, as the overlay already read it (no change, pinned on both trees): an overlay-bound answer -
    the earlier form, recorded with no fingerprint, which read time and engine/assess bind by its key alone - binds the
    item its code presents in each pass, so once the reinstatement of 43264 releases 43273's ADDON hold, the answer to
    that row excludes nothing, before and after the AGAIN."""

    def test_boundary_an_overlay_bound_answer_whose_hold_is_released(self):
        scene = self.scene(ercp_cited(True), CITED)
        stored = self.proposal(scene, '43273')
        answer = models.MemberAnswer.objects.create(
            encounter=scene.encounter, revision=scene.revision, assessment=scene.assessment, fact='performed_status',
            family=stored.family, code='43273', value=ND, answered_by=self.user, question='')
        self.assertEqual(self.views(scene)['43273'].status, 'excluded')
        self.decide(scene, '43264', review.REINSTATE)
        for again in (False, True):
            if again:
                self.again(scene)
            with self.subTest(again=again):
                view = self.views(scene)['43273']
                self.assertEqual((view.status, view.reason), ('needs_clarification', ''))
                self.assertEqual([q['fact'] for q in view.questions], ['cannulation'])
                with self.reads(scene):
                    earlier = answers.earlier_answers(self.fresh(scene), self.fresh(scene).current_assessment)
                self.assertIn(str(answer.pk), [item['answer_id'] for item in earlier])


class R2BWRecountReleased(SimpleTestCase):
    """overlay.recount's ``released`` (W2R-1): a code the engine excluded by a member's answer whose answer read time no
    longer applies is the selected code it was on the reviewer's side - back in its competition and counted by the ADDON
    row - while the engine's own side reproduces the stored record, its exclusion included."""

    @staticmethod
    def frozen(build, codes, code):
        plain = TA.by_code(TA.run(build().build(), *codes))[code]
        case = TO.Case(build().build(), *codes, answers=(TA.answer(plain),))
        key = next(p.key for p in case.rows if p.code == code)
        assert overlay.answered_by_engine(next(p for p in case.rows if p.key == key))[0]
        return case, key

    def test_rbw_a_released_code_competes_again(self):
        case, key = self.frozen(TO.unknown_dilation, (('43249', 2), ('43248', 2)), '43249')
        rival = next(p.key for p in case.rows if p.code == '43248')
        out = case.recount(out_of_competition=())
        self.assertNotIn(overlay.combination.COMPETING_CAUSE, [held.cause for held in out.live[rival].held])
        back = case.recount(released={key})
        self.assertIn(overlay.combination.COMPETING_CAUSE, [held.cause for held in back.live[rival].held])
        self.assertEqual(back.stored_joined.held, out.stored_joined.held)  # the engine's own side: as stored

    def test_rbw_a_released_primary_a_statement_may_exclude_still_holds_the_addon(self):
        # DECISIONS D304: words2's W2R-1 expectation (a released primary counts) is amended to D294 RD-2's reading -
        # the visit's own status is unresolved, so a statement may still exclude 99215 and assess holds 99417 on ADDON
        # with no answer at all; releasing the answer does not count a primary assess would not count
        def build():
            doc = TA.office_prolonged()
            doc.act(1, ct.Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.TOTAL_TIME), status=EF.unres(ct.Status.PERFORMED))
            return doc
        case, key = self.frozen(build, (('99215', 1), ('99417', 2)), '99215')
        addon = next(p.key for p in case.rows if p.code == '99417')
        causes = [held.cause for held in case.recount().live[addon].held]
        self.assertIn(overlay.ADDON_CAUSE, causes)
        causes = [held.cause for held in case.recount(released={key}).live[addon].held]
        self.assertIn(overlay.ADDON_CAUSE, causes)


class R2BWReleasedAnswerOverlay(SimpleTestCase):
    """The release is read over the answers read time binds (never the binding reading alone): refute-consistency C7's
    scene - A1, "Cannot confirm" on 99215's separate_em (the overlay's), leaves 99215 out of the ADDON count, so 99417
    presents the ADDON item, which A2 (the engine's) answers - with A1 standing nothing releases A2's hold (99417 stays
    excluded by it); with A1 withdrawn the recount counts 99215 and A2 excludes nothing."""

    def views(self, given):
        from tests.v2.test_r2w_member_words import R2WAssessedAnswers
        helper = R2WAssessedAnswers()
        a1, a2 = helper.answers_(True)
        case = TO.Case(R2WAssessedAnswers.c7().build(), *R2WAssessedAnswers.CODES, answers=(a1, a2))
        by = {view.code: view for view in case.views({}, answers=[{'code': a.code, 'family': a.family,
                                                                     'fact': a.fact, 'value': a.value,
                                                                     'question': a.question, 'answer_id': a.answer_id}
                                                                    for a in given(a1, a2)]).values()}
        return by['99417']

    def test_rbw_the_primarys_answer_withdrawn_releases_the_add_ons(self):
        view = self.views(lambda a1, a2: ())  # A1 withdrawn (A2 is the stored record's own)
        self.assertNotEqual(view.status, 'excluded')  # behaviour first (red on the reference)
        self.assertEqual((view.reason, getattr(view, 'released_answer', '')), ('', 'performed_status'))

    def test_boundary_the_primarys_answer_standing_keeps_the_add_ons(self):
        view = self.views(lambda a1, a2: (a1,))
        self.assertEqual((view.status, view.reason, getattr(view, 'released_answer', '')),
                         ('excluded', review.DETAIL_UNAVAILABLE, ''))


# --- W2R-2: an item whose act is not the code's own act -----------------------------------------------------------------

def exam_scene(**over):
    """EF.colonoscopy with the examination E1 changed by ``over`` (the snare E2, 45385's own act, established)."""
    doc = EF.colonoscopy()
    doc.exam(1, **over)
    return doc.build()


# (name, the examination's change, the key, the form its row takes: wording.FORM_SESSION_*) - the forms by value, so the
# module imports on the reference tree, whose failures are then behavioural
ROW7 = (('entry', dict(entry=EF.unres(ct.Owner.DOCUMENTING_CLINICIAN)), 'event_entry', 'session_entry'),
        ('date', dict(date=EF.unres(ct.DateRelation.ON_DATE_OF_SERVICE)), 'event_time', 'session_time'),
        ('performer', dict(performer=EF.unres(ct.Performer.DOCUMENTING_TEAM)), 'event_performer', 'session_performer'),
        ('status', dict(status=EF.unres(ct.Status.PERFORMED)), 'performed_status', 'session_status'))


class R2BWSessionExaminationRows(R2WWorld):
    """45385's row 7 item about the colonoscopy's examination E1 (its entry, date, performer or status not established):
    the row asks about the examination of this procedure and shows E1's passage, never the snare's; the door binds the
    item's fingerprint from that row; the answered row and the AGAIN keep it."""

    def test_rbw_every_row7_key_names_the_examination(self):
        for name, over, key, form in ROW7:
            with self.subTest(key=name):
                scene = self.scene(exam_scene(**over), (('45385', 2),), text=TEXT)
                stored = self.proposal(scene, '45385')
                payload = self.payload(scene)
                [row] = self.rows_of(payload, '45385')
                self.assertEqual(offsets(row), [unit(1)])  # behaviour first: E1's passage, never E2's
                self.assertEqual((row['fact'], row['prompt']), (key, answers.FORM_PROMPTS[form]))
                self.assertIn('the examination of this procedure', row['prompt'])
                self.assertNotIn('this act', row['prompt'])
                self.assertEqual(row['statement'], answers.STATEMENT.format(missing=answers.FORM_MISSING[form]))
                self.assertEqual(row['id'], answers.detail_id(key, stored.family, '45385', form))
                self.assertEqual(self.code_row(payload, '45385')['why']['qualifications'],
                                 [customer_api.FORM_WORDS[form]])
                [answer] = self.save(scene, row, CC)
                self.assertEqual(answer.question, stored.support['question'])
                view = self.views(scene)['45385']
                self.assertEqual((view.status, view.answered_form), ('excluded', form))
                self.again(scene)
                [row] = self.rows_of(self.payload(scene), '45385')
                self.assertEqual((row['prompt'], offsets(row), row['saved']['value']),
                                 (answers.FORM_PROMPTS[form], [unit(1)], CC))

    def test_rbw_a_conflict_about_the_examination_shows_its_passage(self):
        scene = self.scene(exam_scene(status=EF.contra(ct.Status.PERFORMED, ct.Status.PLANNED)), (('45385', 2),),
                           text=TEXT)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual(offsets(row), [unit(1)])
        self.assertEqual((row['fact'], row['prompt']), ('conflict:examination', answers.row_prompt(
            'conflict:examination')))

    def test_boundary_the_snares_own_keys_keep_their_rows(self):
        """The same keys on the code's own act (the snare's entry, date, performer, status): the key's row and the
        code's own passage, as before."""
        for name, over, key, _ in ROW7:
            with self.subTest(key=name):
                scene = self.scene(EF.colonoscopy(**over).build(), (('45385', 2),), text=TEXT)
                stored = self.proposal(scene, '45385')
                self.assertNotIn('act_ref', stored.support['item'])
                [row] = self.rows_of(self.payload(scene), '45385')
                self.assertEqual((row['prompt'], row['id']),
                                 (answers.PROMPTS[key], answers.detail_id(key, stored.family, '45385')))
                self.assertEqual(offsets(row), [unit(2)])


class R2BWSameDuctRows(R2WWorld):
    """XCHG's two-act duct question on the placement code 43274 (the removal E5's duct not established): the row names
    the removal and the placement by their kinds and shows both acts' passages; the qualification names the act whose
    duct CPT Studio could not confirm; the door binds the SAME_DUCT item's fingerprint from that row."""

    def test_rbw_the_placement_code_names_both_acts(self):
        scene = self.scene(stent_placement({}).build(), (('43274', 2),), text=TEXT)
        stored = self.proposal(scene, '43274')
        self.assertEqual(stored.support['item']['message'], wording.Message.SAME_DUCT.value)
        payload = self.payload(scene)
        [row] = [row for row in self.rows_of(payload, '43274') if row['fact'] == 'act_target']
        self.assertEqual(row['prompt'], 'Were the stent removal and the stent placement done in the same duct?')
        self.assertEqual(row['statement'],
                         'From the document, CPT Studio could not confirm in which duct the stent removal was done.')
        self.assertEqual(sorted(offsets(row)), [unit(2), unit(5)])
        self.assertEqual(row['id'], answers.detail_id('act_target', stored.family, '43274', wording.FORM_SAME_DUCT))
        self.assertIn('CPT Studio could not confirm from the document in which duct the stent removal was done.',
                      self.code_row(payload, '43274')['why']['qualifications'])
        [answer] = self.save(scene, row, ND)
        self.assertEqual(answer.question, stored.support['question'])
        self.again(scene)
        [row] = [row for row in self.rows_of(self.payload(scene), '43274') if row['fact'] == 'act_target']
        self.assertEqual((row['prompt'], row['saved']['value']),
                         ('Were the stent removal and the stent placement done in the same duct?', ND))
        with self.reads(scene):
            earlier = answers.earlier_answers(self.fresh(scene), self.fresh(scene).current_assessment)
        self.assertFalse([item for item in earlier if item['answer_id'] == str(answer.pk)])

    def test_boundary_the_removal_in_the_same_duct_asks_nothing(self):
        """The removal's duct established biliary, as the placement's: no duct question, no act_target row."""
        scene = self.scene(stent_placement(dict(duct=EF.sup(ct.Duct.BILIARY))).build(), (('43274', 2),), text=TEXT)
        self.assertNotEqual(self.proposal(scene, '43274').support['item'], None)
        self.assertFalse([row for row in self.rows_of(self.payload(scene), '43274') if row['fact'] == 'act_target'])


class R2BWOtherActEnumeration(SimpleTestCase):
    """Every message whose item names an act the code does not bind - over test_assess's fixtures and every one-fact
    perturbation of them (test_assess.perturbations) - is recorded with that act's spans (its slots' words and
    counterpart's) and gets a row that never says "this act" (nor the status row) about an act of another kind than the
    code's own: the session's examination by its forms, a counterpart by SAME_DUCT's, a conflict by its key's label."""

    FIXTURES = (('two sessions', TA.two_sessions, TA.TWO),
                ('ercp', lambda: TA.ercp(stone=True), (('43264', 5), ('43273', 3), ('43262', 4))),
                ('xchg', lambda: stent_placement({}), (('43274', 2), ('43275', 5))),
                ('office prolonged', TA.office_prolonged, (('99215', 1), ('99417', 2))))

    def test_rbw_every_message_naming_another_act(self):
        seen = {}
        for name, build, codes in self.FIXTURES:
            base = build().build()
            for label, R in [('base', base)] + [(f'{s}:{a.value}:{i}', R) for _, s, a, i, R in TA.perturbations(base)]:
                result = TA.run(R, *codes)
                for found in result.codes:
                    item = found.item
                    if item is None or found.evaluation is None:
                        continue
                    own = tuple(dict.fromkeys((*found.evaluation.bindings.values(), *found.evaluation.supporting)))
                    subject = item.held.subject
                    if subject is None or subject.family is not IdFamily.EVENT or subject in own:
                        continue
                    record = jobs._render_code(found, combination=result.combination, R=TA.dated(R), text=TA.TEXT,
                                               pages=(), context_values={}, refs={}, sources=(), day=TA.DAY,
                                               active={}, provider='').support['item']
                    key = (item.message.value, item.held.fact)
                    with self.subTest(message=key, fixture=name, perturbation=label, code=found.code):
                        self.assertIn('act_ref', record)  # behaviour first (red on the reference: nothing recorded)
                        act = wording.recorded_act(record['act_ref'])
                        spans = [(span.start, span.end) for span in (*item.fill.words, *item.fill.whole_words)]
                        self.assertEqual(list(act[0]), list(dict.fromkeys(spans)))
                        # the act the row names is the code's own act's kind only where the item's slots name it so
                        own_kinds = {Q.act_kind(R, event, ()) for event in own}
                        prompt = answers.row_prompt(item.held.fact, record['form'], act[1], act[2])
                        if item.fill.act not in own_kinds:
                            self.assertNotIn('this act', prompt)
                            self.assertNotEqual(prompt, STATUS_ROW)
                    seen.setdefault(key, record['form'])
        # the messages the class reaches (each pinned to the form its row reads)
        self.assertEqual(seen.get(('entry', 'event_entry')), wording.FORM_SESSION_ENTRY)
        self.assertEqual(seen.get(('time', 'event_time')), wording.FORM_SESSION_TIME)
        self.assertEqual(seen.get(('performer', 'event_performer')), wording.FORM_SESSION_PERFORMER)
        self.assertEqual(seen.get(('status', 'performed_status')), wording.FORM_SESSION_STATUS)
        self.assertEqual(seen.get(('same_duct', 'act_target')), wording.FORM_SAME_DUCT)
        self.assertEqual(seen.get(('conflict_attribute', 'conflict:examination')), '')
        self.assertIn(('conflict_fact', 'conflict:snare'), seen)
        self.assertIn(('cannulation', 'cannulation'), seen)
        self.assertIn(('em_basis', 'em_basis'), seen)


class R2BWOtherActForms(SimpleTestCase):
    """The class arm the corpus does not reach (its enumeration finds row 7's four keys about another act only for the
    session's examination): an entry, date, performer or status item about an act the code does not bind whose slots do
    not name the session's examination names that act by its kind (an act no kind names as "another act"), with its
    passages - never "this act" nor the status row; the same item about the code's own act keeps its key's row."""

    @staticmethod
    def item(message, fact, kind, subject):
        from studio.interpretation.engine.types import HeldFact, Id, ItemKind
        held = HeldFact(fact=fact, attribute=None, subject=Id(IdFamily.EVENT, subject), result=None,
                        kind=ItemKind.QUESTION, cause='reading_unknown', reason=None, spans=(), rank=4)
        fill = Q.Fill(act=kind, family=ct.SessionKind.ERCP, words=(ct.Span(500, 560),))
        return Q.Item(held=held, message=message, fill=fill)

    def test_rbw_another_acts_keys_name_it_by_its_kind(self):
        from studio.interpretation.engine.types import Id
        own = (Id(IdFamily.EVENT, 2),)
        for message, fact, words in ((Q.MessageId.STATUS, 'performed_status',
                                      'Was the stent placement performed on the date of service, as documented?'),
                                     (Q.MessageId.ENTRY, 'event_entry', 'In whose entry is the stent placement documented?'),
                                     (Q.MessageId.TIME, 'event_time',
                                      'Was the stent placement done at this encounter, on the date of service?'),
                                     (Q.MessageId.PERFORMER, 'event_performer', 'Who performed the stent placement?')):
            with self.subTest(message=message.value):
                found = self.item(message, fact, ct.Kind.STENT, 5)
                form, record = wording.item_record(wording.Message(message.value), found.fill, found.held.subject, own)
                act = wording.recorded_act(record)
                self.assertEqual(answers.row_prompt(fact, form, act[1], act[2]), words)
                self.assertEqual(act[0], ((500, 560),))
                own_form, own_record = wording.item_record(wording.Message(message.value), found.fill,
                                                           Id(IdFamily.EVENT, 2), own)
                self.assertEqual((own_form, own_record), ('', {}))  # the code's own act: its key's row
        found = self.item(Q.MessageId.STATUS, 'performed_status', ct.Kind.OTHER, 5)
        form, record = wording.item_record(wording.Message.STATUS, found.fill, found.held.subject, own)
        self.assertEqual(answers.row_prompt('performed_status', form, *wording.recorded_act(record)[1:]),
                         'Was another act performed on the date of service, as documented?')


# --- W2R-3: a service fact's row is shared only by the service's own question ---------------------------------------------

def eus(drain, fna):
    """An EUS session X1 (upper tract, to the duodenum, this encounter) with its examination E1, a transmural drainage
    E2 (``drain``) and, unless ``fna`` is None, an FNA E3 (``fna``)."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.EUS, tract=EF.sup(ct.Tract.UPPER), reached=[EF.sup(ct.Extent.DUODENUM)],
                encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.exam(1)
    doc.act(2, ct.Kind.DRAINAGE, route=EF.sup(ct.Route.EUS_TRANSMURAL), **drain)
    if fna is not None:
        doc.act(3, ct.Kind.FNA, **fna)
    return doc.build()


GALLBLADDER = dict(structure=EF.sup(ct.Structure.GALLBLADDER), places=[EF.sup(ct.Landmark.GALLBLADDER)])
EUS_CODES = (('43240', 2), ('43238', 3), ('43242', 3))


# each service fact's one question, by value (wording.SERVICE_MESSAGES)
SERVICE_QUESTIONS = {'target': 'target', 'extent': 'extent', 'cannulation': 'cannulation', 'em_basis': 'em_basis',
                     'setting': 'setting', 'patient_status': 'patient_status'}


class R2BWServiceMessages(SimpleTestCase):
    def test_rbw_every_message_of_a_service_fact_is_its_question_or_has_a_form(self):
        self.assertEqual(set(SERVICE_QUESTIONS), set(answers.SERVICE_FACTS))
        for message, spec in wording.MESSAGES.items():
            if spec.fact not in answers.SERVICE_FACTS:
                continue
            with self.subTest(message=message.value):
                if message.value == SERVICE_QUESTIONS[spec.fact]:
                    self.assertEqual(wording.member_form(message), '')
                else:  # every other message keyed by a service fact is its code's own row (W2R-3)
                    self.assertIn(wording.member_form(message), wording.FORMS)
        self.assertEqual({fact: message.value for fact, message in wording.SERVICE_MESSAGES.items()},
                         SERVICE_QUESTIONS)


class R2BWServiceRows(R2WWorld):
    """43240's STRUCT:pfc items beside R6's TARGET of 43238/43242 (one EUS): the target row is the FNA's alone; 43240's
    is its own, and a member's "Not documented" about the FNA's target never binds, nor excludes, 43240."""

    def walk(self, drain, form):
        scene = self.scene(eus(drain, {}), EUS_CODES)
        stored = self.proposal(scene, '43240')
        payload = self.payload(scene)
        target = [row for row in payload['details_needed'] if row['fact'] == 'target' and '43238' in row['affects']]
        [shared] = target
        self.assertNotIn('43240', shared['affects'])  # behaviour first (red on the reference: one row for all three)
        self.assertEqual(stored.support['item']['form'], form)
        self.assertEqual(sorted(shared['affects']), ['43238', '43242'])
        [own] = self.rows_of(payload, '43240')
        self.assertEqual((own['id'], own['prompt']), (answers.detail_id('target', stored.family, '43240', form),
                                                      answers.FORM_PROMPTS[form]))
        self.assertEqual(self.code_row(payload, '43240')['why']['qualifications'], [customer_api.FORM_WORDS[form]])
        saved = self.save(scene, shared, ND)
        self.assertEqual(sorted(answer.code for answer in saved), ['43238', '43242'])
        for again in (False, True):
            if again:
                self.again(scene)
            views = self.views(scene)
            self.assertEqual(views['43240'].status, 'needs_clarification')
            self.assertEqual({views['43238'].status, views['43242'].status}, {'excluded'})

    def test_rbw_another_structure_is_its_codes_own_row(self):
        self.walk(GALLBLADDER, 'described')

    def test_rbw_the_structure_question_is_its_codes_own_row(self):
        self.walk(dict(structure=EF.sup(ct.Structure.OTHER)), 'structure')

    def test_boundary_the_same_message_shares_the_service_row(self):
        """43240 asked R6's TARGET too (its structure unresolved, the FNA's too): one service row, as L7-08 rules."""
        scene = self.scene(eus(dict(structure=EF.unres(ct.Structure.PANCREATIC_FLUID_COLLECTION)),
                               dict(structure=EF.unres(ct.Structure.LYMPH_NODE))), EUS_CODES)
        self.assertEqual(self.proposal(scene, '43240').support['item']['message'], wording.Message.TARGET.value)
        [row] = [row for row in self.payload(scene)['details_needed'] if row['fact'] == 'target']
        self.assertEqual(sorted(row['affects']), ['43238', '43240', '43242'])


# --- Q2: an explanation whose key row's statement is untrue of the failing fact -------------------------------------------

Q2_FORMS = {wording.Message.WALL_INJECTION: 'described', wording.Message.ANOTHER_STRUCTURE: 'described',
            wording.Message.STRUCTURE_PLACE: 'described', wording.Message.NOTHING_RETRIEVED: 'described',
            wording.Message.SEPARATE_EM_DENIED: 'visit_denied', wording.Message.ATTEMPTED: 'attempted',
            wording.Message.UNPROFILED: 'supported', wording.Message.NOT_LINKED: 'supported',
            wording.Message.RECOGNISED_ONLY: 'supported', wording.Message.UNRECONCILED: 'supported'}


class R2BWExplanationForms(SimpleTestCase):
    def test_rbw_each_listed_explanation_has_its_form(self):
        for message, form in Q2_FORMS.items():
            with self.subTest(message=message.value):
                self.assertEqual(wording.member_form(message), form)
                key = wording.MESSAGES[message].fact
                statement = answers.FORM_STATEMENTS.get(form) or answers.STATEMENT.format(
                    missing=answers.FORM_MISSING[form])
                keys_statement = answers.STATEMENT.format(missing=wording.MISSING.get(key) or VQ.missing(key))
                self.assertNotEqual(statement, keys_statement)

    def test_boundary_the_questions_of_those_keys_keep_their_rows(self):
        for message in (wording.Message.YIELD, wording.Message.SEPARATE_EM, wording.Message.TECHNIQUE,
                        wording.Message.TARGET, wording.Message.STATUS):
            with self.subTest(message=message.value):
                self.assertEqual(wording.member_form(message), '')


class R2BWExplanationRows(R2WWorld):
    def walk(self, R, codes, code, form):
        scene = self.scene(R, codes)
        stored = self.proposal(scene, code)
        payload = self.payload(scene)
        [row] = self.rows_of(payload, code)
        self.assertNotEqual(row['id'], answers.detail_id(row['fact'], stored.family, code))  # behaviour first
        self.assertEqual(row['prompt'], answers.FORM_PROMPTS[form])
        self.assertEqual(row['statement'], answers.FORM_STATEMENTS.get(form) or answers.STATEMENT.format(
            missing=answers.FORM_MISSING[form]))
        self.assertEqual(row['id'], answers.detail_id(row['fact'], stored.family, code, form))
        self.assertEqual(self.code_row(payload, code)['why']['qualifications'], [customer_api.FORM_WORDS[form]])
        [answer] = self.save(scene, row, CC)
        self.assertEqual(answer.question, stored.support['question'])
        view = self.views(scene)[code]
        self.assertEqual((view.status, view.answered_form), ('excluded', form))
        self.again(scene)
        [row] = self.rows_of(self.payload(scene), code)
        self.assertEqual((row['prompt'], row['saved']['value']), (answers.FORM_PROMPTS[form], CC))
        self.assertEqual(self.views(scene)[code].status, 'excluded')
        return scene

    def test_rbw_nothing_retrieved(self):
        doc = TA.ercp(stone=True)
        doc.act(5, ct.Kind.STONE_EXTRACTION, duct=EF.sup(ct.Duct.BILIARY), yield_=EF.neg(ct.Material.ANYTHING))
        self.walk(doc.build(), (('43264', 5),), '43264', 'described')

    def test_rbw_the_drainage_placed_elsewhere(self):
        self.walk(eus(dict(structure=EF.sup(ct.Structure.PANCREATIC_FLUID_COLLECTION),
                           places=[EF.sup(ct.Landmark.BILE_DUCT)]), None), (('43240', 2),), '43240', 'described')

    def test_rbw_an_attempted_act(self):
        self.walk(EF.colonoscopy(status=EF.sup(ct.Status.ATTEMPTED_NOT_COMPLETED)).build(), (('45385', 2),), '45385',
                  'attempted')

    def test_rbw_a_visit_denied(self):
        doc = TA.office_and_sigmoidoscopy()
        doc.act(1, ct.Kind.EM_VISIT, basis=EF.sup(ct.EmBasis.TOTAL_TIME), separate=EF.neg(ct.Separate.STATED))
        self.walk(doc.build(), (('99213', 1), ('45330', 2)), '99213', 'visit_denied')

    def test_boundary_the_visits_question_keeps_its_row(self):
        scene = self.scene(TA.office_and_sigmoidoscopy().build(), (('99213', 1), ('45330', 2)))
        [row] = self.rows_of(self.payload(scene), '99213')
        self.assertEqual(row['prompt'], answers.PROMPTS['separate_em'])
        self.assertEqual(row['id'], answers.detail_id('separate_em', self.proposal(scene, '99213').family, '99213'))


# --- Q5: conflict:em_prolonged worded as the items word it --------------------------------------------------------------

class R2BWConflictWords(R2WWorld):
    def test_rbw_the_prolonged_visit_time(self):
        doc = TA.office_prolonged()
        doc.act(2, ct.Kind.EM_PROLONGED, status=EF.contra(ct.Status.PERFORMED, ct.Status.PLANNED))
        scene = self.scene(doc.build(), (('99215', 1), ('99417', 2)))
        [row] = self.rows_of(self.payload(scene), '99417')
        self.assertEqual(row['fact'], 'conflict:em_prolonged')
        self.assertEqual(row['prompt'], 'The record has conflicting statements about the prolonged visit time. '
                                        'Which is right for this date?')
        self.assertEqual(row['missing'], 'which statement about the prolonged visit time is right for this date')
        self.assertIn('the prolonged visit time', row['statement'])
        for words in (row['prompt'], row['missing'], row['statement']):
            self.assertNotIn('em prolonged', words)
        self.assertIn('the prolonged visit time', customer_api.held_fact_words('conflict:em_prolonged'))
        [answer] = self.save(scene, row, ND)  # the door and the recompute keep the row's words
        self.assertEqual(self.views(scene)['99417'].status, 'excluded')
        self.again(scene)
        [row] = self.rows_of(self.payload(scene), '99417')
        self.assertEqual((row['prompt'], row['saved']['value']),
                         ('The record has conflicting statements about the prolonged visit time. Which is right for '
                          'this date?', ND))

    def test_boundary_a_kind_whose_label_is_its_words_keeps_it(self):
        for kind in (ct.Kind.SNARE, ct.Kind.EXAMINATION, ct.Kind.EM_VISIT):
            with self.subTest(kind=kind.value):
                self.assertEqual(answers.conflict_act(kind.value), f'the {answers.act_label(kind.value)}')
        self.assertEqual(answers.conflict_act(ct.Kind.OTHER.value), wording.NO_KIND_LABEL)
        self.assertEqual(answers.conflict_act('polypectomy'), 'the polypectomy')  # a v1 kind: its act label


# --- W2R-4: an item of a non-empty member form through every branch that carries one ----------------------------------

class R2BWFormBranches(R2WWorld):
    """No input is known where read time's recount releases a hold and gives way to an item read time cannot word whose
    member form is not '' (r2's refuter, W2R-4; this round's search, NOTES): the ERCP's cannulation is the one item 43273's
    released ADDON row gives way to. So its form is made non-empty for this test (the classifier patched to give
    CANNULATION the DESCRIBED form), and the scene is driven end to end: the overlay's unworded arm, the member's row, the
    code's qualification, the door, the answered row and the AGAIN each carry the form."""

    def setUp(self):
        super().setUp()
        forms = dict(wording._MESSAGE_FORMS)
        forms[wording.Message.CANNULATION] = wording.FORM_DESCRIBED
        patcher = mock.patch.object(wording, '_MESSAGE_FORMS', forms)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_rbw_the_unworded_live_item_of_a_form(self):
        scene = self.scene(ercp_cited(True), CITED)
        stored = self.proposal(scene, '43273')
        self.decide(scene, '43264', review.REINSTATE)
        view = self.views(scene)['43273']
        [live] = view.questions
        self.assertEqual((live['id'], live['fact'], live['message'], live['form']),
                         ('', 'cannulation', 'cannulation', wording.FORM_DESCRIBED))
        self.assertEqual(live['question'], customer_api.FORM_WORDS[wording.FORM_DESCRIBED])
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '43273')
        self.assertEqual((row['fact'], row['prompt']), ('cannulation', answers.FORM_PROMPTS[wording.FORM_DESCRIBED]))
        self.assertEqual(row['id'], answers.detail_id('cannulation', stored.family, '43273', wording.FORM_DESCRIBED))
        self.assertEqual(self.code_row(payload, '43273')['why']['qualifications'],
                         [customer_api.FORM_WORDS[wording.FORM_DESCRIBED]])
        [answer] = self.save(scene, row, ND)
        self.assertNotEqual(answer.question, stored.support['question'])
        view = self.views(scene)['43273']
        self.assertEqual((view.status, view.answered, view.answered_form),
                         ('excluded', 'cannulation', wording.FORM_DESCRIBED))
        [row] = self.rows_of(self.payload(scene), '43273')
        self.assertEqual((row['prompt'], row['saved']['value']), (answers.FORM_PROMPTS[wording.FORM_DESCRIBED], ND))
        self.again(scene)
        view = self.views(scene)['43273']
        self.assertEqual((view.status, view.reason), ('excluded', review.DETAIL_UNAVAILABLE))
        [row] = self.rows_of(self.payload(scene), '43273')
        self.assertEqual(row['prompt'], answers.FORM_PROMPTS[wording.FORM_DESCRIBED])

    def test_rbw_the_unworded_question_carries_its_form_and_act(self):
        """The overlay's unworded arm, unit by unit: its dict carries the item's message, form and act record, its words
        are the form's sentence, an answer binds its fact (_answerable) and the bound form is the live one."""
        case = TO.Case(ercp_cited(True), *CITED)
        key = next(p.key for p in case.rows if p.code == '43264')
        found = case.recount(counted=[*case.engine_keys, key])
        live = next(item for code_key, item in found.live.items() if item.member.code == '43273')
        p = next(p for p in case.rows if p.code == '43273')
        question = overlay._unworded_question(p, live, overlay._own_acts(found, p.key))
        self.assertEqual((question['message'], question['form']), ('cannulation', wording.FORM_DESCRIBED))
        self.assertTrue(question['act_ref']['spans'])  # the cannulation, an act 43273 does not bind
        self.assertEqual(question['question'], customer_api.FORM_WORDS[wording.FORM_DESCRIBED])
        self.assertEqual(overlay._answerable(live, []), ['cannulation'])
        self.assertEqual(overlay._bound_form(p, live, True, 'cannulation'), wording.FORM_DESCRIBED)
        self.assertEqual(wording.asked_form(question, p.support), wording.FORM_DESCRIBED)
        self.assertEqual(wording.asked_act(question, p.support)[0], tuple(tuple(pair) for pair in
                                                                           question['act_ref']['spans']))
