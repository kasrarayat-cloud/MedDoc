"""r2 (DECISIONS D294, member words: WORDS-F1, F3, F6 as one class, with WORDS-F2, F4, F5 and F7). SYNTHETIC only: tests/v2's
own FactSet builders over test_assess's synthetic letters (r2w_world: the renderer's child, persist, read time, the
customer payload, the details door and the AGAIN recompute); nothing is sent anywhere.

- The class (F1 DIGITAL_SCOPE, F6 D281's begun UNLISTED_SCOPE and the session's DOUBT, F3 ADDON): a held code's details
  row (prompt, statement, missing) and its qualification are worded from the held item's own message (its member form,
  wording.member_form) wherever its fact key's fixed row asks something else; items of different forms never share a row
  (the row and its id name the form); the door binds an answer to an item's fingerprint only for a row that asks that
  item's question (review.bound_fingerprints with the shown forms; answers._bound_question).
- F2: a hold read time's recount releases shows nothing resting on it - its stored question is not the open question,
  the customer's sentence and the member's row are the live item's, it is listed recomputed, never stale, and an answer
  binds only the question read time still asks (one view before and after the AGAIN).
- F4: questions._techniques reads what pass 1's claim STATES (AMENDMENT-2 4.3.3 b), never a claimed-value set.
- F5: conflict:other is "another act" on every member sentence (D254 rule 2).
- F7: overlay.assessed_answers names an answer assess read for the ADDON count whatever became of the add-on.
Each rule: an input it must change and a boundary it must leave alone."""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import answers, customer_api, interpretation, jobs, models, review
from studio.interpretation import overlay, wording
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine.types import Id, IdFamily
from studio.types import EvidenceSpan
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_facts as TF
from tests.v2 import test_questions as TQ
from tests.v2.r2w_world import R2WWorld
from tests.v2.test_update_customer import HARD

ND, CC = models.MemberAnswer.NOT_DOCUMENTED, models.MemberAnswer.CANNOT_CONFIRM
KEY_ROW = answers.PROMPTS['performed_status']  # "Was this procedure performed on the date of service, as documented?"


def row_words(row):
    return row['prompt'], row['statement']


def form_words(form):
    """(prompt, statement) of a member form's row."""
    return (answers.FORM_PROMPTS[form],
            answers.FORM_STATEMENTS.get(form) or answers.STATEMENT.format(missing=answers.FORM_MISSING[form]))


# --- the classifier (wording.member_form, asked_form) and the fixed sentences ------------------------------------------

class R2WMemberFormTests(SimpleTestCase):
    """The forms: every message whose question its fact key's fixed row does not ask has one; every other has none."""

    KEYS_OWN = (wording.Message.STATUS, wording.Message.NOT_DOCUMENTED, wording.Message.ENTRY, wording.Message.TIME,
                wording.Message.PERFORMER, wording.Message.PROCEDURE, wording.Message.CONFLICT, wording.Message.EXTENT,
                wording.Message.CANNULATION, wording.Message.BASE_INCLUDED, wording.Message.SEPARATE_EM)

    @staticmethod
    def named():
        return {wording.Message.DIGITAL_SCOPE: wording.FORM_DIGITAL_SCOPE,
                wording.Message.UNLISTED_SCOPE: wording.FORM_UNLISTED_SCOPE, wording.Message.ADDON: wording.FORM_ADDON,
                wording.Message.ENTEROSCOPY_ROUTE: wording.FORM_DESCRIBED,
                wording.Message.EXAMINATION_CLASS: wording.FORM_DESCRIBED,
                wording.Message.ANOTHER_ENTRY: wording.FORM_ANOTHER_ENTRY, wording.Message.BUNDLED: wording.FORM_SEPARATE,
                wording.Message.ANOTHER_TECHNIQUE: wording.FORM_ACCOUNTED,
                wording.Message.BUNDLING_TARGET: wording.FORM_PART}

    def test_the_named_messages_have_their_form_and_the_keys_own_have_none(self):
        for message, form in self.named().items():
            with self.subTest(message=message.value):
                self.assertEqual(wording.member_form(message), form)
                self.assertEqual(wording.member_form(message.value), form)  # by its recorded value too
        for message in self.KEYS_OWN:
            with self.subTest(message=message.value):
                self.assertEqual(wording.member_form(message), '')
        for message in wording.Message:
            self.assertIn(wording.member_form(message), wording.FORMS | {''})

    def test_the_sessions_doubt_is_chosen_by_its_slots(self):
        """D281 B6: DOUBT's question about the held session's examination says row 7's done; any other DOUBT asks what
        its key's row asks. The form reads the same predicate as the question (wording.session_examination)."""
        session = wording.Slots(act=ct.Kind.EXAMINATION, family=ct.SessionKind.COLONOSCOPY)
        for slots, form in ((session, wording.FORM_SESSION_DOUBT),
                            (wording.Slots(act=ct.Kind.SNARE, family=ct.SessionKind.COLONOSCOPY), ''),
                            (wording.Slots(act=ct.Kind.EXAMINATION), ''), (None, '')):
            with self.subTest(slots=slots):
                self.assertEqual(wording.member_form(wording.Message.DOUBT, slots), form)
        question = wording.build(wording.Message.DOUBT, session, TA.TEXT).question
        self.assertIn(wording.DONE_IN_PART, question)

    def test_every_form_has_its_row_and_its_qualification_and_they_say_one_thing(self):
        self.assertEqual(set(answers.FORM_PROMPTS), wording.FORMS)
        self.assertEqual(set(answers.FORM_MISSING), wording.FORMS)
        self.assertEqual(set(customer_api.FORM_WORDS), wording.FORMS)
        for form in wording.FORMS - {wording.FORM_ADDON}:
            with self.subTest(form=form):
                self.assertIn(answers.FORM_MISSING[form], customer_api.FORM_WORDS[form])
        self.assertEqual(customer_api.FORM_WORDS[wording.FORM_ADDON], customer_api.ADDON_WORDS)
        self.assertEqual(answers.FORM_STATEMENTS[wording.FORM_ADDON], customer_api.ADDON_WORDS)
        for form in (wording.FORM_DIGITAL_SCOPE, wording.FORM_UNLISTED_SCOPE, wording.FORM_SESSION_DOUBT):
            self.assertIn(wording.DONE_IN_PART, answers.FORM_PROMPTS[form])
        self.assertNotIn(KEY_ROW, answers.FORM_PROMPTS.values())

    def test_the_sentences_pass_the_customer_guard(self):
        texts = [*answers.FORM_PROMPTS.values(), *customer_api.FORM_WORDS.values(), answers.ADDON_STATEMENT,
                 *(answers.STATEMENT.format(missing=missing) for missing in answers.FORM_MISSING.values()),
                 answers.row_prompt('conflict:other'), answers.CONFLICT_STATEMENT.format(act=answers.conflict_act('other'))]
        for text in texts:
            with self.subTest(text=text):
                self.assertEqual(customer_api.plain(text), text)
                self.assertIsNone(customer_api.FORBIDDEN.search(text), text)
                self.assertEqual([pattern.pattern for pattern in HARD if pattern.search(text)], [], text)
                self.assertFalse([cause for cause in customer_api.HELD_FACT_CAUSES if cause in text], text)
                self.assertNotIn('“', text)

    def test_asked_form_reads_a_live_question_a_stored_one_and_a_record(self):
        item = {'message': 'addon', 'fact': 'performed_status', 'kind': 'question'}
        support = {'item': item}
        for question, support_, form in (
                ({'fact': 'performed_status', 'message': 'addon'}, {}, wording.FORM_ADDON),
                ({'fact': 'performed_status', 'message': 'doubt', 'form': 'session_doubt'}, {},
                 wording.FORM_SESSION_DOUBT),
                ({'fact': 'performed_status', 'message': 'status'}, support, ''),
                ({'id': 'c1', 'scope': 'proposal', 'fact': 'performed_status'}, support, wording.FORM_ADDON),
                ({'id': 'c1', 'scope': 'proposal', 'fact': 'performed_status'},
                 {'item': {**item, 'message': 'doubt', 'form': 'session_doubt'}}, wording.FORM_SESSION_DOUBT),
                ({'id': 'c1', 'scope': 'proposal', 'fact': 'event_entry'}, support, ''),  # an item of another fact
                ({'scope': 'proposal', 'fact': 'performed_status'}, support, ''),  # a wait: no row id
                ({'id': 'c1', 'scope': 'proposal', 'fact': 'performed_status'}, {'item': {**item, 'form': 'bogus'}}, '')):
            with self.subTest(question=question, support=support_):
                self.assertEqual(wording.asked_form(question, support_), form)

    def test_items_of_different_forms_never_share_a_row(self):
        """A service fact's question is asked once for its service (L7-08) - but an item of a member form is its code's
        own row, keyed and identified by its form, so it never shares a row (nor an id) with the key's own question."""
        family = 'gi.eus'
        self.assertEqual(answers._row_key('extent', family, '43237', ''), ('extent', family, '', ''))
        self.assertEqual(answers._row_key('extent', family, '43238', ''), ('extent', family, '', ''))
        described = answers._row_key('extent', family, '43237', wording.FORM_DESCRIBED)
        self.assertEqual(described, ('extent', family, '43237', wording.FORM_DESCRIBED))
        self.assertNotEqual(answers.detail_id('extent', family, '43237', wording.FORM_DESCRIBED),
                            answers.detail_id('extent', family, '43237'))
        self.assertEqual(answers.detail_id('extent', family, ''), answers.detail_id('extent', family, '', ''))

    def test_read_time_words_an_item_it_cannot_word_by_its_form(self):
        """WORDS-F2's fixed sentence for a live item read time cannot word (overlay._fact_sentence): an item of a member
        form says its form's words - never "in which procedure the act was done" of a route whose procedure is known
        (D267) -, any other its key's, and a conflict over no act kind names "another act"."""
        self.assertEqual(overlay._fact_sentence('procedure', wording.FORM_DESCRIBED),
                         customer_api.FORM_WORDS[wording.FORM_DESCRIBED])
        self.assertEqual(overlay._fact_sentence('procedure'), 'A detail is needed: in which procedure the act was done.')
        self.assertEqual(overlay._fact_sentence('cannulation'),
                         'A detail is needed: whether the intended duct was cannulated.')
        self.assertEqual(overlay._fact_sentence('conflict:other'),
                         'A detail is needed: which statement about another act is right for this date.')

    def test_the_renderer_records_the_form_with_the_item(self):
        """jobs._render_code records the form beside the message (support['item']['form']): a stored DOUBT about the
        held session's examination is told from one about another act, whose slots no record otherwise keeps."""
        doc = EF.Doc()
        doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.exam(1, status=EF.sup(ct.Status.ATTEMPTED_NOT_COMPLETED))
        doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, EF.X(1), EF.unit(9)))
        found = TA.by_code(TA.run(doc.build(), ('45378', 1)))['45378']
        self.assertIs(found.item.message, Q.MessageId.DOUBT)
        rendered = jobs._render_code(found, combination=None, R=TA.dated(doc.build()), text=TA.TEXT, pages=(),
                                     context_values={}, refs={}, sources=(), day=TA.DAY, active={}, provider='')
        self.assertEqual(rendered.support['item']['form'], wording.FORM_SESSION_DOUBT)


# --- WORDS-F1: DIGITAL_SCOPE -------------------------------------------------------------------------------------------

class R2WDigitalScopeRows(R2WWorld):
    """D280.3's DIGITAL_SCOPE item - a DRE filed as the colonoscopy's examination whose device CLAIMS manual - keeps the
    held fact's key (performed_status, conflict:examination, event_entry, event_performer, event_time). The member's row
    and the code's qualification ask what the item asks (the session's examination, in full or in part), the door
    binds the answer to the item's fingerprint from that row, and the row keeps the question once answered."""

    ROWS = [(name, over, key) for name, over, key in TQ.DRE_OWN if key is not None]

    def test_every_dre_row_asks_the_items_question(self):
        seen = set()
        for name, over, key in self.ROWS:
            if key in seen:
                continue
            seen.add(key)
            with self.subTest(row=name, key=key):
                scene = self.scene(TQ.dre_shape(dict(over, device=TQ.unres(ct.Device.MANUAL)), e3=True), TQ.DRE_CODES)
                [first] = self.rows_of(self.payload(scene), '45385')
                self.assertIn(wording.DONE_IN_PART, first['prompt'])  # behaviour first (red on the reference)
                prompt, statement = form_words(wording.FORM_DIGITAL_SCOPE)
                stored = self.proposal(scene, '45385')
                self.assertEqual((stored.support['item']['message'], stored.support['item']['fact']),
                                 (wording.Message.DIGITAL_SCOPE.value, key))
                payload = self.payload(scene)
                [row] = self.rows_of(payload, '45385')
                self.assertIn(wording.DONE_IN_PART, row['prompt'])  # the item's question: the session's examination
                self.assertEqual((row['fact'], row_words(row)), (key, (prompt, statement)))
                self.assertEqual(row['id'], answers.detail_id(key, stored.family, '45385', wording.FORM_DIGITAL_SCOPE))
                self.assertNotEqual(row['id'], answers.detail_id(key, stored.family, '45385'))
                quals = self.code_row(payload, '45385')['why']['qualifications']
                self.assertIn(customer_api.FORM_WORDS[wording.FORM_DIGITAL_SCOPE], quals)
                self.assertNotIn(customer_api.QUESTION_WORDS['performed_status'], quals)
                [answer] = self.save(scene, row, ND)
                self.assertEqual(answer.question, stored.support['question'])  # the item the row asks
                payload = self.payload(scene)
                [row] = self.rows_of(payload, '45385')
                self.assertEqual((row_words(row), row['saved']['value']), ((prompt, statement), ND))
                self.assertEqual(self.views(scene)['45385'].answered_form, wording.FORM_DIGITAL_SCOPE)
                self.again(scene)
                [row] = self.rows_of(self.payload(scene), '45385')
                self.assertEqual((row_words(row), row['saved']['value']), ((prompt, statement), ND))

    def test_boundary_the_snares_own_entry_keeps_its_keys_row(self):
        """The same key on the code's own act (the snare's entry not established): ENTRY, its key's own row."""
        scene = self.scene(TQ.dre_shape(None, e3=True), TQ.DRE_CODES)  # no DRE line: 45385 READY
        self.assertEqual(self.rows_of(self.payload(scene), '45385'), [])
        doc = EF.colonoscopy(entry=EF.unres(ct.Owner.DOCUMENTING_CLINICIAN))
        scene = self.scene(doc.build(), (('45385', 2),))
        stored = self.proposal(scene, '45385')
        self.assertEqual(stored.support['item']['message'], wording.Message.ENTRY.value)
        [row] = self.rows_of(self.payload(scene), '45385')
        self.assertEqual((row['fact'], row['prompt'], row['id']),
                         ('event_entry', answers.PROMPTS['event_entry'],
                          answers.detail_id('event_entry', stored.family, '45385')))


# --- WORDS-F6: D281's begun UNLISTED_SCOPE and the session's DOUBT ----------------------------------------------------

def begun(card):
    """refute-safety's begun_scope shape (tests/v2/test_questions.D281Begun): the colonoscopy's examination E1 begun
    beside a kept unlisted doubt of kind examination - with no card (UNLISTED_SCOPE) or carded to X1 (the session's
    DOUBT)."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.exam(1, status=EF.sup(ct.Status.ATTEMPTED_NOT_COMPLETED))
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, card, EF.unit(9)))
    return doc.build()


class R2WBegunScopeRows(R2WWorld):
    """D281 B6 (G3-27): a question about the held session's examination says row 7's done - on the member's row and the
    code's qualification too, so a truthful "Not documented" about a begun examination is never asked for."""

    def test_unlisted_scope_and_the_sessions_doubt(self):
        for card, message, form in ((None, wording.Message.UNLISTED_SCOPE, 'unlisted_scope'),
                                    (EF.X(1), wording.Message.DOUBT, 'session_doubt')):
            with self.subTest(form=form):
                scene = self.scene(begun(card), (('45378', 1),))
                stored = self.proposal(scene, '45378')
                self.assertEqual(stored.support['item']['message'], message.value)
                payload = self.payload(scene)
                [row] = self.rows_of(payload, '45378')
                self.assertIn(wording.DONE_IN_PART, row['prompt'])
                self.assertNotEqual(row['prompt'], KEY_ROW)
                self.assertEqual(row_words(row), form_words(form))
                quals = self.code_row(payload, '45378')['why']['qualifications']
                self.assertEqual(quals, [customer_api.FORM_WORDS[form]])
                [answer] = self.save(scene, row, CC)
                self.assertEqual(answer.question, stored.support['question'])

    def test_boundary_a_doubt_about_another_act_keeps_its_keys_row(self):
        scene = self.scene(EF.colonoscopy(status=EF.doubted(ct.Status.PERFORMED)).build(), (('45385', 2),))
        self.assertEqual(self.proposal(scene, '45385').support['item']['message'], wording.Message.DOUBT.value)
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '45385')
        self.assertEqual(row['prompt'], KEY_ROW)
        self.assertEqual(self.code_row(payload, '45385')['why']['qualifications'],
                         [customer_api.QUESTION_WORDS['performed_status']])


class R2WClassRows(R2WWorld):
    """The class beyond the three named messages: an explanation whose question its key's row does not ask - the
    colonoscope's examination told only in the nursing entry (ANOTHER_ENTRY, event_entry): the row asks whether it was
    performed in this procedure, never whose entry it is told in, which is established."""

    def test_another_entry(self):
        doc = EF.colonoscopy(snare=False)
        doc.exam(1, entry=EF.sup(ct.Owner.NURSING))
        scene = self.scene(doc.build(), (('45378', 1),))
        self.assertEqual(self.proposal(scene, '45378').support['item']['message'], wording.Message.ANOTHER_ENTRY.value)
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '45378')
        self.assertNotEqual(row['prompt'], answers.PROMPTS['event_entry'])  # behaviour first (red on the reference)
        self.assertEqual(row_words(row), form_words('another_entry'))
        self.assertEqual(self.code_row(payload, '45378')['why']['qualifications'],
                         [customer_api.FORM_WORDS['another_entry']])


# --- WORDS-F3: ADDON -----------------------------------------------------------------------------------------------------

class R2WAddonRows(R2WWorld):
    """D284's ADDON item: the member's row asks whether one of the add-on's primaries is documented - never the status
    row's "could not confirm that this procedure was performed", untrue of an established add-on act - stored and as
    read time words it live; the door binds the item the row asks."""

    def test_the_stored_addon_item(self):
        for name, doc, codes, code in (('43273 alone', TA.ercp(stone=False), (('43273', 3),), '43273'),
                                       ('99417 beside 99213', TA.office_prolonged(), (('99213', 1), ('99417', 2)),
                                        '99417')):
            with self.subTest(case=name):
                scene = self.scene(doc.build(), codes)
                stored = self.proposal(scene, code)
                payload = self.payload(scene)
                [row] = self.rows_of(payload, code)
                self.assertNotEqual(row['prompt'], KEY_ROW)  # behaviour first (red on the reference)
                self.assertIn('primary codes', row['prompt'])
                self.assertEqual(row_words(row), form_words('addon'))
                self.assertEqual(self.code_row(payload, code)['why']['qualifications'], [customer_api.ADDON_WORDS])
                [answer] = self.save(scene, row, CC)
                self.assertEqual(answer.question, stored.support['question'])

    def test_the_live_addon_item_and_its_earlier_answer(self):
        """99215 and 99417 READY; the reviewer rejects 99215: read time words ADDON live. The row asks it, the door binds
        the live question (no stored item), the excluded row keeps it; once the rejection is revoked the answer is an
        earlier one, listed with the question it was given to."""
        scene = self.scene(TA.office_prolonged().build(), (('99215', 1), ('99417', 2)))
        self.assertEqual(self.rows_of(self.payload(scene), '99417'), [])
        decision = self.decide(scene, '99215', review.REJECT)
        [row] = self.rows_of(self.payload(scene), '99417')
        self.assertNotEqual(row['prompt'], KEY_ROW)  # behaviour first (red on the reference)
        prompt, statement = form_words('addon')
        self.assertEqual(row_words(row), (prompt, statement))
        [answer] = self.save(scene, row, ND)
        self.assertTrue(answer.question)
        self.assertEqual(self.views(scene)['99417'].answered_form, 'addon')
        [row] = self.rows_of(self.payload(scene), '99417')
        self.assertEqual((row_words(row), row['saved']['value']), ((prompt, statement), ND))
        with self.reads(scene):
            review.record_decision(encounter=self.fresh(scene), proposal=decision.proposal, action=review.REVOKE,
                                   user=self.user, membership=self.membership, note='r2w synthetic revoke')
        payload = self.payload(scene)
        self.assertEqual(self.code_row(payload, '99417')['status'], 'ready')
        with self.reads(scene):
            earlier = answers.earlier_answers(self.fresh(scene), self.fresh(scene).current_assessment)
        [listed] = [item for item in earlier if item['answer_id'] == str(answer.pk)]
        self.assertEqual(listed['prompt'], prompt)

    def test_boundary_an_add_on_held_by_its_own_status_keeps_its_keys_row(self):
        doc = TA.office_prolonged()
        doc.act(2, ct.Kind.EM_PROLONGED, status=EF.unres(ct.Status.PERFORMED))
        scene = self.scene(doc.build(), (('99215', 1), ('99417', 2)))
        self.assertEqual(self.proposal(scene, '99417').support['item']['message'], wording.Message.STATUS.value)
        payload = self.payload(scene)
        [row] = self.rows_of(payload, '99417')
        self.assertEqual(row['prompt'], KEY_ROW)
        self.assertEqual(self.code_row(payload, '99417')['why']['qualifications'],
                         [customer_api.QUESTION_WORDS['performed_status']])


class R2WDoorTests(SimpleTestCase):
    """The door: an answer is bound to an item's fingerprint only from a row that asks that item's question."""

    @staticmethod
    def assessment(proposals):
        return SimpleNamespace(engine_version=interpretation.ENGINE_VERSION_V3, completeness={},
                               proposals=SimpleNamespace(all=lambda: list(proposals)))

    def test_bound_fingerprints_take_the_stored_item_only_for_its_form(self):
        stored = SimpleNamespace(code='99417', family='gi.office_em', bucket=models.Proposal.SELECTED, position=1,
                                 support={'question': 'S' * 64, 'item': {'message': 'addon', 'fact': 'performed_status',
                                                                          'kind': 'question', 'form': 'addon'}})
        key = ('99417', 'gi.office_em', 'performed_status')
        pairs = [(key, {'scope': 'proposal', 'family': 'gi.office_em', 'fact': 'performed_status', 'code': '99417',
                        'question': 'shown', 'reason': 'shown', 'passages': []})]
        own = review.bound_fingerprints(self.assessment([stored]), [stored], pairs, {key: frozenset({''})})[key]
        self.assertNotEqual(own, 'S' * 64)  # a row of another form: the shown question's own fingerprint
        for forms in ({key: frozenset({'addon'})}, None):
            self.assertEqual(review.bound_fingerprints(self.assessment([stored]), [stored], pairs, forms)[key],
                             'S' * 64)

    def test_the_door_never_binds_the_fingerprint_of_another_form(self):
        key = ('99417', 'gi.office_em', 'performed_status')
        row = SimpleNamespace(form='addon')
        shown = {'fingerprints': {key: 'L' * 64}}
        for forms, expected in (({key: frozenset({'addon'})}, 'S' * 64), ({key: frozenset({''})}, 'L' * 64),
                                ({}, 'S' * 64)):
            with self.subTest(forms=forms):
                self.assertEqual(answers._bound_question(None, {}, row, key, {key: 'S' * 64}, forms, dict(shown)),
                                 expected)


# --- WORDS-F2: a hold read time's recount releases ------------------------------------------------------------------

def ercp_cited(held):
    """test_assess.ercp(stone=False) beside AddonTests' cited denial (a stone extraction E6 denied for every stone,
    which excludes 43264, reinstatable); with ``held`` E2's access outcome unresolved, so R6's ERCP access row holds
    43273 (cannulation, rank 16) beside its ADDON row (rank 4)."""
    doc = TA.ercp(stone=False)
    if held:
        doc.act(2, ct.Kind.CANNULATION, access=EF.unres(ct.AccessOutcome.ACHIEVED), duct=EF.sup(ct.Duct.BILIARY))
    doc.act(6, ct.Kind.STONE_EXTRACTION, status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.ALL_OF_KIND),
            kind_words=EF.Span(600, 630), status_words=EF.Span(630, 660))
    return doc.build()


CITED = (('43264', EvidenceSpan(0, 600, 660, TA.TEXT[600:660], True)), ('43273', 3))


class R2WReleasedHold(R2WWorld):
    def test_a_released_addon_row_shows_nothing_resting_on_it(self):
        scene = self.scene(ercp_cited(True), CITED)
        stored = self.proposal(scene, '43273')
        self.assertEqual(stored.support['item']['message'], wording.Message.ADDON.value)
        self.decide(scene, '43264', review.REINSTATE)
        view = self.views(scene)['43273']
        self.assertEqual((view.status, [q['fact'] for q in view.questions], view.recomputed, view.stale),
                         ('needs_clarification', ['cannulation'], (overlay.ADDON_CHECK,), ()))
        self.assertFalse([q for q in view.questions if q.get('id')])  # the stored ADDON question is not open
        payload = self.payload(scene)
        quals = self.code_row(payload, '43273')['why']['qualifications']
        self.assertEqual(quals, [customer_api.QUESTION_WORDS['cannulation']])
        [row] = self.rows_of(payload, '43273')
        self.assertEqual((row['fact'], row['prompt']), ('cannulation', answers.PROMPTS['cannulation']))
        with self.reads(scene):
            from studio import reports
            draft = reports.snapshot(self.fresh(scene), reports.DRAFT)
        self.assertFalse([q for q in draft['clarifications'] if q.get('fact') == 'performed_status'])
        [answer] = self.save(scene, row, ND)
        self.assertNotEqual(answer.question, stored.support['question'])  # never the released item's
        before = self.views(scene)['43273']
        self.assertEqual((before.status, before.reason), ('excluded', review.DETAIL_UNAVAILABLE))
        self.again(scene)
        after = self.views(scene)['43273']
        self.assertEqual((after.status, after.reason), (before.status, before.reason))  # one view (D283)

    def test_boundary_an_addon_held_by_its_row_alone_is_released_to_ready(self):
        scene = self.scene(ercp_cited(False), CITED)
        self.decide(scene, '43264', review.REINSTATE)
        view = self.views(scene)['43273']
        self.assertEqual((view.status, view.questions, view.recomputed, view.stale),
                         ('ready', (), (overlay.ADDON_CHECK,), ()))


# --- WORDS-F5: conflict:other ------------------------------------------------------------------------------------------

class R2WConflictOther(R2WWorld):
    def test_conflict_other_rows_say_another_act(self):
        doc = TA.two_sessions()
        doc.act(2, EF.contra(ct.Kind.SNARE, ct.Kind.BIOPSY), places=[EF.sup(ct.Landmark.SIGMOID_COLON)],
                lesion=EF.sup(EF.L(1)))
        scene = self.scene(doc.build(), TA.TWO)
        payload = self.payload(scene)
        for code in ('45385', '45380'):
            with self.subTest(code=code):
                [row] = self.rows_of(payload, code)
                self.assertEqual(row['fact'], 'conflict:other')
                self.assertEqual(row['prompt'], 'The record has conflicting statements about another act. Which is '
                                                'right for this date?')
                self.assertEqual(row['statement'], 'The document states another act in more than one way, and CPT '
                                                   'Studio could not confirm which statement is right for this date.')
                self.assertEqual(row['missing'], 'which statement about another act is right for this date')
                for words in (row['prompt'], row['statement'], row['missing']):
                    self.assertNotIn('the other', words)
        [row] = self.rows_of(payload, '45385')
        stored = self.proposal(scene, '45385')
        answer = models.MemberAnswer.objects.create(  # an answer to the question asked differently: an earlier one
            encounter=scene.encounter, revision=scene.revision, assessment=scene.assessment, fact='conflict:other',
            family=stored.family, code='45385', value=ND, answered_by=self.user, question='0' * 64)
        with self.reads(scene):
            earlier = answers.earlier_answers(self.fresh(scene), self.fresh(scene).current_assessment)
        [listed] = [item for item in earlier if item['answer_id'] == str(answer.pk)]
        self.assertEqual(listed['prompt'], row['prompt'])

    def test_boundary_a_named_kinds_conflict_keeps_its_label(self):
        """A conflict over an act whose kind is established (the snare's status contradicted): conflict:snare, its
        label as before."""
        doc = TA.two_sessions()
        doc.act(2, ct.Kind.SNARE, places=[EF.sup(ct.Landmark.SIGMOID_COLON)], lesion=EF.sup(EF.L(1)),
                status=EF.contra(ct.Status.PERFORMED, ct.Status.PLANNED))
        scene = self.scene(doc.build(), TA.TWO)
        [row] = self.rows_of(self.payload(scene), '45385')
        label = answers.act_label('snare')
        self.assertEqual((row['fact'], row['prompt'], row['missing']),
                         ('conflict:snare',
                          f'The record has conflicting statements about the {label}. Which is right for this date?',
                          f'which statement about the {label} is right for this date'))


# --- WORDS-F7: assessed_answers ---------------------------------------------------------------------------------------

class R2WAssessedAnswers(SimpleTestCase):
    """refute-consistency C7's scene (an office visit with its prolonged time and a same-day flexible sigmoidoscopy):
    A1, "Cannot confirm" on 99215's separate_em (overlay-bound), leaves the primary out of the ADDON count, so 99417
    presents the ADDON item; A2, "Not documented" to that item (its fingerprint, engine-read), excludes 99417. assess read
    A1 for the ADDON count, so it is named, whatever became of the add-on: its withdrawal holds readiness."""

    @staticmethod
    def c7():
        doc = TA.office_and_sigmoidoscopy()
        doc.act(3, ct.Kind.EM_PROLONGED, session=EF.X(1))
        return doc

    CODES = (('99215', 1), ('99417', 3), ('45330', 2))

    def case(self, given):
        from tests.v2 import test_overlay as TO
        from tests.v2.test_review_binding import AssessedAnswersTests

        case = TO.Case(self.c7().build(), *self.CODES, answers=given)
        return case, lambda standing: AssessedAnswersTests.withdrawn(case, standing)

    def answers_(self, with_a2):
        plain = TA.by_code(TA.run(self.c7().build(), *self.CODES, member=TA.ENTERED))
        a1 = TA.answer(plain['99215'], value=CC, answer_id='a1')
        if not with_a2:
            return (a1,)
        after = TA.by_code(TA.run(self.c7().build(), *self.CODES, member=TA.ENTERED, answers=(a1,)))
        self.assertIs(after['99417'].item.message, Q.MessageId.ADDON)
        return a1, TA.answer(after['99417'], answer_id='a2')

    def test_an_answer_read_for_the_addon_count_is_named_when_the_add_on_is_excluded_by_its_own(self):
        case, withdrawn = self.case(self.answers_(True))
        by = {row.code: row for row in case.rows}
        self.assertTrue(overlay.answered_by_engine(by['99417'])[0])  # 99417 excluded by A2
        self.assertEqual(overlay.assessed_answers(case.completeness, case.rows), frozenset({'a1'}))
        self.assertTrue(withdrawn({'a2'}))  # A1 withdrawn: readiness held until the recompute
        self.assertFalse(withdrawn({'a1', 'a2'}))

    def test_boundary_an_add_on_assess_never_passed_names_nothing(self):
        """A "Cannot confirm" on 99215 where no add-on is assessed (99417 not proposed) binds no primary: not named."""
        plain = TA.by_code(TA.run(self.c7().build(), ('99215', 1), ('45330', 2), member=TA.ENTERED))
        from tests.v2 import test_overlay as TO
        case = TO.Case(self.c7().build(), ('99215', 1), ('45330', 2),
                       answers=(TA.answer(plain['99215'], value=CC, answer_id='a1'),))
        self.assertEqual(overlay.assessed_answers(case.completeness, case.rows), frozenset())


# --- WORDS-F4: what the document states of a device ---------------------------------------------------------------------

E2 = Id(IdFamily.EVENT, 2)
A = ct.Attribute


def device_view(doubt_readings, second='negated'):
    """The real FactSet builder (engine/facts over test_facts' stored view): E2's device slot overfilled [manual
    supported, endoscope ``second``], with a doubt naming E2 that reads ``doubt_readings``."""
    events = TF.planted(TF.view(TF.colonoscopy()), IdFamily.EVENT, 'E2', A.TECHNIQUE_DEVICE, [
        TF.written_fact('supported', 'manual', units=('S5',)), TF.written_fact(second, 'endoscope', units=('S6',))])
    if doubt_readings:
        events['doubts'] = list(events['doubts']) + [{'about': 'technique', 'objects': ['E2'], 'units': ['S6'],
                                                      'basis': 'unclear', 'readings': list(doubt_readings)}]
    return F.fact(F.factset(events), E2, A.TECHNIQUE_DEVICE)


class R2WTechniques(SimpleTestCase):
    """D280.3's "(the document states more than one technique for it)" says what the document STATES."""

    def reason(self, device):
        R = TQ.dre_shape(dict(status=TQ.unres(ct.Status.PERFORMED), device=device), e3=True)
        found = TA.by_code(TA.run(R, *TQ.DRE_CODES))['45385']
        self.assertIs(found.item.message, Q.MessageId.DIGITAL_SCOPE)
        return found.item.fill.techniques, jobs.word_item(found.item, found.key, TA.run(R, *TQ.DRE_CODES).combination,
                                                          TA.dated(R), TA.TEXT).reason

    def test_a_denied_device_a_doubt_only_offers_is_not_stated(self):
        view = device_view(('endoscope',))
        self.assertEqual(set(F.claimed_values(view)), {ct.Device.MANUAL, ct.Device.ENDOSCOPE})  # the claimed reader
        techniques, reason = self.reason(dataclasses.replace(view, spans=(), cited=()))
        self.assertFalse(techniques)
        self.assertNotIn(wording.DIGITAL_TECHNIQUES.strip(), reason)

    def test_boundary_pass_ones_own_contradiction_states_two(self):
        techniques, reason = self.reason(EF.contra(ct.Device.MANUAL, ct.Device.ENDOSCOPE))
        self.assertTrue(techniques)
        self.assertIn(wording.DIGITAL_TECHNIQUES.strip(), reason)

    def test_the_stated_reader(self):
        """Q._states_several: pass 1's own contradiction states its sides; a claim and a doubt's readings, one value; a
        merged view, nothing (the fail-closed reading of Q1R) - whatever it claims (facts.claimed_values)."""
        self.assertTrue(Q._states_several(EF.contra(ct.Device.MANUAL, ct.Device.ENDOSCOPE)))
        for name, found in (('claimed', EF.unres(ct.Device.MANUAL)),
                            ('doubted', EF.doubted(ct.Device.MANUAL, ct.Device.ENDOSCOPE)),
                            ('overfilled, a denied value a doubt offers', device_view(('endoscope',))),
                            ('overfilled, both written stated', device_view((), second='supported'))):
            with self.subTest(case=name):
                self.assertFalse(Q._states_several(found))
