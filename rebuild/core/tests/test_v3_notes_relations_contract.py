"""The field-relations v2 contract as the ordinary-notes contract for a live claude-sonnet-5 deployment (2026-09-30).

Provider decisions are simulated (the keyed v2 wire, or the exact retained provider text). What is asserted is what the
application does with them: the model's per-unit relations are the evidence that neighbouring statements are
independent; the application keeps the hard floors it can detect structurally, and those floors only ever HOLD.

Each first decision named in the 2026-09-30 reconciliation has its exact case here, and each new floor has the adverse
input it holds with every other unit called 'independent' (the model missing the problem), beside the control it must
leave useful.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from quillmd import application_profile as profile
from .test_v3_field_relations import offered, relation_wire
from .test_v3_ordinary_notes import LIVE, field, run

RELATIONS = dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True, V3_GENERATION_BATCHES=False)
DEFAULT = dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False, V3_GENERATION_BATCHES=False)
TITLE = 'Clinic visit record'


def v3(key, label, kind='text', context='', options=None):
    made = field(key, label, kind, options)
    made['context'] = context
    return made


def clinic_form(**contexts):
    """The r1-11 clinic form of the frozen ordinary-notes set (its inspected labels, kinds and contexts)."""
    fields = [v3('v3_1', 'Chief complaint', 'text', TITLE), v3('v3_2', 'History of present illness', 'long_text', TITLE),
              v3('v3_3', 'Past medical history', 'long_text', TITLE), v3('v3_4', 'Medications', 'long_text', TITLE),
              v3('v3_5', 'Allergies', 'text', TITLE), v3('v3_6', 'Smoker', 'choice', TITLE + ' > Smoker', ['Yes', 'No']),
              v3('v3_7', 'Examination', 'long_text', TITLE), v3('v3_8', 'Assessment', 'long_text', TITLE),
              v3('v3_9', 'Plan', 'long_text', TITLE), v3('v3_10', 'Consent obtained', 'checkbox', 'Sign-off', ['Consent obtained']),
              v3('v3_11', 'Clinician signature', 'signature', 'Sign-off')]
    for f in fields:
        if f['key'] in contexts:
            f['context'] = contexts[f['key']]
    return fields


N01 = ('This is a 30-year-old female seen for headaches. The headaches started two months ago and are worse in the '
       'morning. She denies visual changes, nausea, or weakness. She takes ibuprofen as needed. No known drug '
       'allergies. She is a nonsmoker. Neurological examination is normal. Assessment is tension-type headache. '
       'Plan is to start amitriptyline 10 mg at night. She will follow up in six weeks.')
U = {n + 1: s for n, s in enumerate((
    'This is a 30-year-old female seen for headaches.',
    'The headaches started two months ago and are worse in the morning.',
    'She denies visual changes, nausea, or weakness.', 'She takes ibuprofen as needed.', 'No known drug allergies.',
    'She is a nonsmoker.', 'Neurological examination is normal.', 'Assessment is tension-type headache.',
    'Plan is to start amitriptyline 10 mg at night.', 'She will follow up in six weeks.'))}
N01_PICKS = {'v3_1': [U[1]], 'v3_2': [U[2], U[3]], 'v3_4': [U[4]], 'v3_5': [U[5]], 'v3_6': [U[6]], 'v3_7': [U[7]],
             'v3_8': [U[8]], 'v3_9': [U[9], U[10]]}
NO = {'v3_6': ['v3_6:1']}
YES = {'v3_6': ['v3_6:0']}


def repeated_other():
    """The n02 form: three write-ins labelled 'Other' under three printed parent questions."""
    return [v3('v3_1', 'Other', 'text', 'How would you describe the pain? (tick all that apply)'),
            v3('v3_2', 'Other', 'text', 'Do you notice anything before the headache begins? (tick all that apply)'),
            v3('v3_3', 'Other', 'text', 'What makes the pain worse? (tick all that apply)')]


def order_form():
    return [v3('v3_1', 'Does a Community Treatment Order (CTO) currently apply to this person?', 'long_text',
               'Community care review'),
            v3('v3_2', 'Clinic attendance', 'long_text', 'Community care review')]


class Retained:
    """A provider response carrying the exact retained answer text (the campaign's evidence bodies)."""
    def __init__(self, text):
        self.model = g.SONNET_5; self.stop_reason = 'end_turn'
        self.content = [SimpleNamespace(type='text', text=text)]


def retained(notes, fields, text):
    asked, context, _ = g.v3_generation_fields(fields)
    return r.validated({'anthropic_response': Retained(text), 'ordinary_field_contract': r.CONTRACT, 'notes': notes,
                        'fields': asked, 'full_catalogue': fields, 'context_labels': context})


class Settled:
    def assert_filled(self, notes, fields, answers, expected):
        for key, text in expected.items():
            with self.subTest(key=key):
                self.assertEqual((answers[key]['status'], answers[key]['text']), ('supported', text), answers[key])
        self.assert_stored_clear(notes, fields, answers)

    def assert_stored_clear(self, notes, fields, answers):
        """Page, save and finalization agree with generation: nothing supported is governed."""
        supported = {k: v for k, v in answers.items() if v['status'] == 'supported'}
        self.assertEqual(g.governed_decisions(notes, fields, supported), [])
        governance = g.governance_for(notes, fields)
        for f in fields:
            if f['key'] in supported:
                row = g.as_currently_governed(governance, notes, {**f, **supported[f['key']]})
                self.assertEqual((row['status'], row['text']), ('supported', supported[f['key']]['text']))

    def assert_held(self, notes, fields, picks, key, choices=None, overrides=None):
        answer = offered(notes, fields, picks, choices=choices, overrides=overrides)[key]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), answer)
        # A stored supported copy of the same answer is refused by the page, save and finalization too.
        stored = {k: v for k, v in answer.items() if k != 'held_candidate'}
        stored.update(status='supported', text=(answer.get('held_candidate') or {}).get('text') or picks[key][0])
        label = next(f['label'] for f in fields if f['key'] == key)
        self.assertEqual(g.governed_decisions(notes, fields, {key: stored}), [label])
        return answer


# ─── 1. which contract a deployment runs ─────────────────────────────────────────────────────────────────────────
class ContractSelection(SimpleTestCase):
    def test_field_relations_default_on_only_for_live_claude_sonnet_5(self):
        live5 = {'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-5'}
        self.assertTrue(profile.field_relations(live5))
        for other in ({**live5, 'QUILLMD_AI_MODEL': 'claude-sonnet-4-6'}, {**live5, 'QUILLMD_AI_MODEL': 'gpt-4.1-mini'},
                      {**live5, 'QUILLMD_AI_PROVIDER': 'openai'}, {**live5, 'QUILLMD_AI_MODE': 'fixture'},
                      {k: v for k, v in live5.items() if k != 'QUILLMD_AI_MODE'},
                      {**live5, 'QUILLMD_AI_MODEL': ' claude-sonnet-5'}, {}):
            with self.subTest(environ=other):
                self.assertFalse(profile.field_relations(other))
        # An explicit setting wins either way.
        self.assertFalse(profile.field_relations({**live5, 'QUILLMD_V3_FIELD_RELATIONS': '0'}))
        self.assertFalse(profile.field_relations({**live5, 'QUILLMD_V3_FIELD_RELATIONS': ''}))
        self.assertTrue(profile.field_relations({'QUILLMD_V3_FIELD_RELATIONS': '1'}))

    @override_settings(**dict(RELATIONS, AI_MODEL='claude-sonnet-4-6'))
    def test_another_model_keeps_the_default_request_even_with_the_flag(self):
        fields = clinic_form()
        config = g.configuration(fields)
        self.assertNotIn('ordinary_field_contract', config)
        self.assertEqual(config['request_profile'], g.LEGACY_PROFILE)
        with override_settings(AI_MODEL=g.SONNET_5):
            self.assertEqual(g.configuration(fields)['ordinary_field_contract'], r.CONTRACT)


# ─── 2. the default request carries each question's printed context ─────────────────────────────────────────────
class DefaultRequestContext(SimpleTestCase):
    def captured(self, fields, notes):
        captured = {}

        def create(**kwargs):
            captured['payload'] = json.loads(kwargs['messages'][0]['content'])
            captured['system'] = kwargs['system']
            raise RuntimeError('stop before any request')
        client = MagicMock(); client.messages.create.side_effect = create
        config = {**g.configuration(), 'mode': 'live', 'provider': 'anthropic', 'model': 'claude-sonnet-4-6',
                  'input_rate': '2', 'output_rate': '10', 'cached_rate': '0.2',
                  'request_profile': g.request_profile('anthropic', 'claude-sonnet-4-6', 'disabled', 'medium', '')}
        with patch('anthropic.Anthropic', return_value=client), self.assertRaises(RuntimeError):
            g.generate(notes, fields, config)
        return captured

    @override_settings(**DEFAULT)
    def test_three_other_questions_are_told_apart_by_their_printed_parent_question(self):
        # N02: the default request sent only key, label and answer policy, so three 'Other' questions were identical.
        fields = repeated_other()
        sent = self.captured(fields, 'The patient describes the pain as a tight band around her head.')
        self.assertEqual([q.get('context') for q in sent['payload']['questions']], [f['context'] for f in fields])
        self.assertIn('printed context', sent['system'])
        # A question with no printed context carries none (the request for such a form is unchanged).
        plain = [v3('v3_1', 'Chief complaint'), v3('v3_2', 'Plan', 'long_text')]
        sent = self.captured(plain, 'Patient presents with cough.')
        self.assertEqual(sent['payload']['questions'], [
            {'key': 'v3_1', 'label': 'Chief complaint', 'answer_policy': 'documented_source_only'},
            {'key': 'v3_2', 'label': 'Plan', 'answer_policy': 'documented_source_only'}])
        self.assertNotIn('printed context', sent['system'])


# ─── 3. the first faulty decisions, each with its exact case ─────────────────────────────────────────────────────
@override_settings(**RELATIONS)
class FirstDecisions(Settled, SimpleTestCase):
    def test_n01_with_a_correct_relation_answer_fills_every_answerable_field(self):
        fields = clinic_form()
        answers = offered(N01, fields, N01_PICKS, choices=NO)
        self.assert_filled(N01, fields, answers, {
            'v3_1': U[1], 'v3_2': U[2] + '\n' + U[3], 'v3_4': U[4], 'v3_6': 'No',
            'v3_8': 'tension-type headache.', 'v3_9': 'to start amitriptyline 10 mg at night.\n' + U[10]})
        for key in ('v3_3', 'v3_10', 'v3_11'):
            self.assertEqual(answers[key]['status'], 'missing')
        # CHANGED PIN (refutation round 1, L2:R2-4 / L2:R2-5): 'No known drug allergies.' and 'Neurological examination
        # is normal.' stay held as on 43fcf214. Each summary is contradicted by any finding on its topic ('She had
        # anaphylaxis to penicillin.', 'There is reduced power in the left arm.'), which only meaning tells; the form-title
        # route that released them is withdrawn. They are the remaining false holds of this note.
        for key in ('v3_5', 'v3_7'):
            self.assertEqual(answers[key]['status'], 'conflict')

    def test_a_pronoun_the_actor_reader_resolves_uniquely_to_the_patient_is_the_patient(self):
        # v3_field_relations.py:379 demanded positive patient evidence: 'She takes ibuprofen as needed.' had none.
        fields = clinic_form()
        notes = U[1] + ' ' + U[4]
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': [U[4]]}), {'v3_4': U[4]})
        # The explicit-patient form of the same statement is accepted the same way (its 'or' is not a hedge).
        notes = U[1] + ' The patient denies visual changes, nausea, or weakness.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_2': [notes[len(U[1]) + 1:]]}),
                           {'v3_2': notes[len(U[1]) + 1:]})
        # No antecedent, another person anywhere before, a pronoun of the other gender, or a hedged statement: held.
        for notes, selected in ((U[4], U[4]),
                                ('Her mother has migraines. ' + U[4], U[4]),
                                (U[1] + ' Her mother has migraines. The patient reports headaches. ' + U[4], U[4]),
                                ('45-year-old man presents with cough. ' + U[4], U[4]),
                                (U[1] + ' She possibly takes ibuprofen.', 'She possibly takes ibuprofen.'),
                                (U[1] + ' She may take ibuprofen.', 'She may take ibuprofen.'),
                                (U[1] + ' She may have taken ibuprofen.', 'She may have taken ibuprofen.'),
                                (U[1] + ' She apparently takes ibuprofen.', 'She apparently takes ibuprofen.'),
                                (U[1] + ' She perhaps takes ibuprofen.', 'She perhaps takes ibuprofen.'),
                                # a unit naming another person is never the patient's by this reader
                                (U[1] + ' The patient takes warfarin for her husband.',
                                 'The patient takes warfarin for her husband.'),
                                (U[1] + ' She takes warfarin with her husband.', 'She takes warfarin with her husband.'),
                                # nor one pointing at other lines or scoping itself by them
                                (U[1] + ' She takes these.', 'She takes these.'),
                                (U[1] + ' She used to take ibuprofen.', 'She used to take ibuprofen.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_4': [selected]}, 'v3_4')

    def test_a_thing_acting_on_the_patient_is_the_patients_in_either_object_form(self):
        # The object's form decided nothing clinical: 'The headache wakes her at night.' was the patient's while 'The
        # headache wakes the patient at night.' was held (a surviving mutant of a39a905e's patient-object exclusion).
        fields = clinic_form()
        for key, statement in (('v3_2', 'The headache wakes the patient at night.'),
                               ('v3_2', 'The headache wakes her at night.')):
            notes = U[1] + ' ' + statement
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, offered(notes, fields, {key: [statement]}), {key: statement})
        # CHANGED PIN (refutation round 1, L1:F2): a thing is the patient's only when it names the question or the
        # presented complaint ('seen for headaches' / 'The headache ...'); 'Penicillin' is neither, so it stays held
        # like 'The babysitter has chickenpox.' (the same shape, measured leaking).
        for key, statement in (('v3_5', 'Penicillin gives the patient a rash.'), ('v3_5', 'Penicillin gives her a rash.')):
            notes = U[1] + ' ' + statement
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [statement]}, key)
        attendance = order_form()
        for statement in ('The clinic sees the patient every week.', 'The clinic sees her every week.'):
            notes = 'The patient was reviewed today. ' + statement
            with self.subTest(notes=notes):
                self.assert_filled(notes, attendance, offered(notes, attendance, {'v3_2': [statement]}),
                                   {'v3_2': statement})
        # A member of the care team acting on the patient is the literal reader's, never this one's.
        for key, statement in (('v3_4', 'The clinical supervisor gives the patient warfarin.'),
                               ('v3_9', 'The clinical supervisor will review the patient in six weeks.')):
            notes = U[1] + ' ' + statement
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [statement]}, key)

    def test_the_form_title_route_stays_withdrawn(self):
        # CHANGED PIN (refutation round 1, L2:R2-4 / L2:R2-5): :372 reads 'Neurological examination is normal.' as an
        # unresolved subject because the Examination field's context is the form's title, and 'No known drug allergies.'
        # is self-coupled for the same reason. The first implementation released both; each is a summary any finding on
        # its topic contradicts by meaning alone, so both stay held as on 43fcf214 (remaining false holds, stated).
        fields = clinic_form()
        notes = U[1] + ' ' + U[5] + ' ' + U[7]
        for key, selected in (('v3_5', U[5]), ('v3_7', U[7])):
            with self.subTest(key=key):
                self.assert_held(notes, fields, {key: [selected]}, key)
        # A context that qualifies the field keeps the hold (adverse A1, A2, A4).
        for key, context, selected in (('v3_7', 'Cardiovascular examination', U[7]),
                                       ('v3_5', 'Family history', U[5]),
                                       ('v3_5', TITLE + ' > Family history', U[5])):
            with self.subTest(context=context):
                self.assert_held(notes, clinic_form(**{key: context}), {key: [selected]}, key)
        # A statement about the allergy elsewhere still couples it (adverse C6), and so does the question's own
        # labelled line elsewhere in the note.
        notes = U[1] + ' ' + U[5] + ' Assessment is possible penicillin allergy.'
        self.assert_held(notes, fields, {'v3_5': [U[5]]}, 'v3_5')
        notes = U[1] + ' She has a penicillin allergy. Allergies: latex.'
        self.assert_held(notes, fields, {'v3_5': ['She has a penicillin allergy.']}, 'v3_5')
        # Another unit naming the question keeps it coupled; alone too (CHANGED PIN, L2:R2-4: the wider self-reference
        # is withdrawn, the answer naming its own question stays coupled as on 43fcf214); and a qualified field.
        notes = U[1] + ' She has a penicillin allergy. Referral to the allergy clinic is planned.'
        self.assert_held(notes, fields, {'v3_5': ['She has a penicillin allergy.']}, 'v3_5')
        notes = U[1] + ' She has a penicillin allergy.'
        self.assert_held(notes, fields, {'v3_5': ['She has a penicillin allergy.']}, 'v3_5')
        self.assert_held(notes, clinic_form(v3_5='Family history'), {'v3_5': ['She has a penicillin allergy.']}, 'v3_5')
        # An answer that does not name its question is never its self-reference; nor is one only the literal reader
        # admits for a field the source-subject reader knows ('medication' is not the Medications subject).
        notes = U[1] + ' She has no drug reactions. Allergy testing is planned.'
        self.assert_held(notes, fields, {'v3_5': ['She has no drug reactions.']}, 'v3_5')
        notes = U[1] + ' The prescribed medication is administered by residence staff.'
        self.assert_held(notes, fields, {'v3_4': ['The prescribed medication is administered by residence staff.']}, 'v3_4')
        # One general destination sharing the Examination's context is not a form title: the context qualifies.
        cardio = [v3('v3_1', 'Plan', 'long_text', 'Cardiovascular examination'),
                  v3('v3_2', 'Examination', 'long_text', 'Cardiovascular examination')]
        notes = 'The patient presents for review. ' + U[7]
        self.assert_held(notes, cardio, {'v3_2': [U[7]]}, 'v3_2')
        # A thing is Examination's only when it names it (N06, I1: a procedure is not an examination).
        notes = ('The patient was seen for removal of a skin lesion on the left forearm. The lesion was excised under '
                 'local anesthesia and closed with sutures.')
        self.assert_held(notes, fields, {'v3_7': [notes.split('. ', 1)[1]]}, 'v3_7')

    def test_option_polarity_from_a_pronoun_resolved_to_the_patient(self):
        fields = clinic_form()
        for statement in ('She is a nonsmoker.', 'She does not smoke.'):
            notes = U[1] + ' ' + statement
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, offered(notes, fields, {'v3_6': [statement]}, choices=NO), {'v3_6': 'No'})
                self.assert_held(notes, fields, {'v3_6': [statement]}, 'v3_6', choices=YES)
        notes = U[1] + ' She smokes.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_6': ['She smokes.']}, choices=YES), {'v3_6': 'Yes'})
        # Unresolved, another person's, or the other gender: no polarity, so no option.
        for notes, statement in (('She is a nonsmoker.', 'She is a nonsmoker.'),
                                 ('Her mother has asthma. She is a nonsmoker.', 'She is a nonsmoker.'),
                                 ('45-year-old man presents with cough. She is a nonsmoker.', 'She is a nonsmoker.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_6': [statement]}, 'v3_6', choices=NO)

    def test_an_age_opener_with_an_article_presents_the_patient_on_the_relations_path(self):
        fields = clinic_form()
        notes = 'A 45-year-old man presents with cough.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_1': [notes]}), {'v3_1': notes})
        # CHANGED PIN (refutation round 1, L3:R3-4): the default path reads this opener exactly as 43fcf214 did - its
        # noun is another person and the note is held ('A 35-year-old woman presents for her father. Allergies:
        # penicillin.' was filled on the default path by the first implementation).
        with override_settings(**DEFAULT):
            self.assertEqual(run(notes, {'Chief complaint': [notes]}, fields=fields)['Chief complaint']['status'], 'conflict')
            # N04 opened with 'A ': the whole note stays held on the default path (0 of 9, as on 43fcf214).
            n04 = ('A 45-year-old man presents with right knee pain for three weeks after a fall. He has hypertension '
                   'and takes lisinopril 10 mg daily. Allergies: penicillin. Smoker: No. On examination there is a small '
                   'effusion and medial joint line tenderness. Assessment is a probable medial meniscus tear. Plan is an '
                   'MRI of the right knee and physiotherapy referral.')
            picks = {'Allergies': ['Allergies: penicillin.'], 'Smoker': ['Smoker: No.'],
                     'Examination': ['On examination there is a small effusion and medial joint line tenderness.'],
                     'Assessment': ['Assessment is a probable medial meniscus tear.'],
                     'Plan': ['Plan is an MRI of the right knee and physiotherapy referral.']}
            out = run(n04, picks, fields=fields)
            self.assertEqual({k: out[k]['status'] for k in picks}, {k: 'conflict' for k in picks})
        # An appositive or relative clause naming another person keeps the hold (RR9).
        for notes in ("A 70-year-old woman, the patient's mother, presents with chest pain.",
                      "A 45-year-old man, the patient's husband, presents with cough.",
                      'A 12-year-old boy presents with his mother, who has chest pain.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_1': [notes]}, 'v3_1')
                with override_settings(**DEFAULT):
                    self.assertEqual(run(notes, {'Chief complaint': [notes]}, fields=fields)['Chief complaint']['status'],
                                     'conflict')

    def test_a_clause_matching_the_destinations_own_printed_time_is_not_a_bound(self):
        # N02 v3_2: 'before the headache begins' is the printed question's own scope, about the same patient's
        # symptom; 'sees' is outside the finite-verb list.
        fields = repeated_other()
        notes = ('The patient describes the pain as a tight band around her head. The patient sees zigzag lines before '
                 'the headache begins.')
        pain, aura = notes.split('. ', 1)[0] + '.', notes.split('. ', 1)[1]
        answers = offered(notes, fields, {'v3_1': [pain], 'v3_2': [aura]})
        self.assert_filled(notes, fields, answers, {'v3_1': pain, 'v3_2': aura})
        # Into another question, it is a bounded statement (adverse F3); the wrong time or a condition holds.
        self.assert_held(notes, fields, {'v3_1': [aura]}, 'v3_1')
        for statement in ('The patient sees zigzag lines after the headache begins.',
                          'The patient sees zigzag lines if she skips meals.',
                          'The patient sees zigzag lines before she skips meals.'):
            with self.subTest(statement=statement):
                self.assert_held(statement, fields, {'v3_2': [statement]}, 'v3_2')

    def test_attempt_18_retained_response_fills_both_questions(self):
        notes = 'The patient is subject to a Community Treatment Order (CTO). She attends the clinic every week.'
        fields = order_form()
        text = ('{"fields":{"v3_1":{"unit_ids":[1],"conflict":false,"context":{"1":"answer","2":"independent"}},'
                '"v3_2":{"unit_ids":[2],"conflict":false,"context":{"1":"independent","2":"answer"}}}}')
        answers = retained(notes, fields, text)
        self.assert_filled(notes, fields, answers, {
            'v3_1': 'The patient is subject to a Community Treatment Order (CTO).',
            'v3_2': 'She attends the clinic every week.'})
        # E2-E7 stay held when the model says fill.
        for notes, selected in (('Her husband attends the clinic every week.', None),
                                ('The patient is subject to a Community Treatment Order (CTO). Her brother attends the '
                                 'clinic every week.', 'Her brother attends the clinic every week.'),
                                ('Her mother has migraines. She attends the clinic every week.',
                                 'She attends the clinic every week.'),
                                ('The patient would attend the clinic every week.', None),
                                ('Attends the clinic every week.', None),
                                ('The patient used to attend the clinic every week.', None),
                                ('The patient attends the clinic unless the order lapses.', None),
                                ('The patient attends the clinic every week once the order starts.', None)):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_2': [selected or notes]}, 'v3_2')


# ─── 4. hold-only floors a model's 'independent' cannot remove ───────────────────────────────────────────────────
@override_settings(**RELATIONS)
class HoldOnlyFloors(Settled, SimpleTestCase):
    def test_another_persons_statement_and_an_ambiguous_pronoun_hold_a_proven_unit(self):
        fields = clinic_form()
        right = [v3('v3_1', 'Right knee', 'text')]
        self.assert_held('The patient is caring for her grandmother, who has right knee pain.', right,
                         {'v3_1': ['The patient is caring for her grandmother, who has right knee pain.']}, 'v3_1')
        for notes, key, selected in (
                ('45-year-old woman presents with a rash. The patient says he is allergic to penicillin.', 'v3_5',
                 'The patient says he is allergic to penicillin.'),
                ('His father had a heart attack at 55. He takes rosuvastatin.', 'v3_4', 'He takes rosuvastatin.'),
                ('His father had a heart attack at 55.\n\nHe takes rosuvastatin.', 'v3_4', 'He takes rosuvastatin.'),
                ('The patient presents with cough.\n\nHer husband has hypertension.\n\nHe takes lisinopril.', 'v3_4',
                 'He takes lisinopril.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key)

    def test_a_later_unit_that_points_back_holds_what_it_may_change(self):
        fields = clinic_form()
        for notes, key, selected, choices in (
                ('The patient was seen for removal of a skin lesion on the left forearm. It was postponed.', 'v3_1',
                 'The patient was seen for removal of a skin lesion on the left forearm.', None),        # B1
                ('Patient presents with chest pain. Not anymore.', 'v3_1', 'Patient presents with chest pain.', None),  # B8
                ('Warfarin 5 mg daily. Stopped last month.', 'v3_4', 'Warfarin 5 mg daily.', None),        # B4
                ('Examination is normal. However, this was before the fall.', 'v3_7', 'Examination is normal.', None),  # C3
                ('Smoker: No.\nBut he quit only last month.', 'v3_6', 'Smoker: No.', NO),                  # C2
                ('The patient does not smoke. She quit last month.', 'v3_6', 'The patient does not smoke.', NO),  # G6
                ('Examination is normal.\n\nHowever, this was before the fall.', 'v3_7', 'Examination is normal.', None)):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key, choices=choices)
        # A later statement with its own subject and object does not point back.
        notes = U[1] + ' ' + U[4] + ' ' + U[5] + ' ' + U[6]
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': [U[4]]}), {'v3_4': U[4]})

    def test_a_same_topic_statement_with_a_negation_holds_either_pick(self):
        for notes, label, first, second in (
                ('The patient is on methadone. The patient is not on diazepam or methadone.', 'Medication',
                 'The patient is on methadone.', 'The patient is not on diazepam or methadone.'),        # B7 / N13
                ('The patient is not depressed. Her mood is depressed.', 'Mental state',
                 'The patient is not depressed.', 'Her mood is depressed.'),                             # B9 / N16
                ('The patient smokes.\nThe patient does not smoke.', 'Smoking status',
                 'The patient smokes.', 'The patient does not smoke.'),                                 # N14
                ('The patient is oriented.\nThe patient is not agitated and not oriented.', 'Mental state',
                 'The patient is oriented.', 'The patient is not agitated and not oriented.'),          # N14
                ('The patient is not suicidal.\nThe patient is not psychotic but suicidal.', 'Risk to self',
                 'The patient is not suicidal.', 'The patient is not psychotic but suicidal.'),         # N15
                ('The patient is subject to MAPPA.\nNo MAPPA involvement.', 'MAPPA status',
                 'The patient is subject to MAPPA.', 'No MAPPA involvement.')):                         # N15
            fields = [v3('f', label, 'long_text')]
            for selected in (first, second):
                for layout in (notes, notes.replace('\n', '\n\n').replace('. ', '.\n\n')):
                    with self.subTest(notes=layout, selected=selected):
                        self.assert_held(layout, fields, {'f': [selected]}, 'f')
        fields = clinic_form()
        self.assert_held('Smoker: No.\nHe quit smoking last month.', fields, {'v3_6': ['Smoker: No.']}, 'v3_6',
                         choices=NO)                                                                    # B12
        # An asserted labelled value and a denial of it; an object's 'no' and the object asserted.
        text = [v3('f', 'Allergy status', 'long_text')]
        for notes, selected in (('Allergies: penicillin.\nThe patient is not allergic to penicillin.', 'Allergies: penicillin.'),
                                ('The patient has no allergies. The patient has a penicillin allergy.',
                                 'The patient has a penicillin allergy.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, text + clinic_form()[4:5], {'v3_5' if selected.startswith('Allergies') else 'f':
                                                                    [selected]},
                                 'v3_5' if selected.startswith('Allergies') else 'f')
        # A negation of another topic in the same note is not the same topic (the D30 ordinary shape).
        notes = ('The patient reports stable relationships with family and expects no relationship changes before the '
                 'next report.\n\nThe relationship reporting condition is monitored during weekly supervision visits.'
                 '\n\nNo new physical illness has affected treatment attendance during this reporting period.')
        one = [v3('f', 'Condition monitoring', 'long_text')]
        selected = 'The relationship reporting condition is monitored during weekly supervision visits.'
        self.assert_filled(notes, one, offered(notes, one, {'f': [selected]}), {'f': selected})

    def test_a_denial_of_a_labelled_value_holds_it(self):
        # A labelled answer beside a statement denying it, whose subject is a pronoun with no antecedent or a thing: the
        # word cause reads only an explicit-patient statement, so 'She is not depressed.' was a model-only hold (and on
        # 43fcf214 too). `v3_denies_labelled` and a whole denial in `v3_opposed_predicates` hold it.
        def text(label):
            return [v3('f', label, 'long_text')]
        for notes, fields, key, choices in (
                ('Mental state: depressed.\nShe is not depressed.', text('Mental state'), 'f', None),
                ('Mental state: depressed.\n\nHe is not depressed.', text('Mental state'), 'f', None),
                ('Mental state: depressed.\nMood is not depressed.', text('Mental state'), 'f', None),
                ('Suicidal ideation: present.\nShe is not suicidal.', text('Suicidal ideation'), 'f', None),
                ('Medication: methadone.\nShe is not on methadone.', text('Medication'), 'f', None),
                ('Medication: methadone.\nShe does not take methadone.', text('Medication'), 'f', None),
                ('Medication: methadone.\nShe is not on diazepam or methadone.', text('Medication'), 'f', None),
                ('Medication: methadone.\nShe takes no medication.', text('Medication'), 'f', None),
                ('Allergies: penicillin.\nShe has no allergies.', clinic_form(), 'v3_5', None),
                ('Allergies: penicillin.\nShe is not allergic.', clinic_form(), 'v3_5', None),
                ('Allergies: no known drug allergies.\nShe is allergic to penicillin.', clinic_form(), 'v3_5', None),
                ('Examination: tenderness over the lateral epicondyle.\nThere is no tenderness over the lateral '
                 'epicondyle.', clinic_form(), 'v3_7', None),
                # a line labelled by a word the form does not print, either way round
                ('Mental state: depressed.\nMood: not depressed.', text('Mental state'), 'f', None),
                ('Mood: not depressed.\nMental state: depressed.', text('Mental state'), 'f', None)):
            selected = next(line for line in notes.split('\n') if line.startswith(('Mental state', 'Suicidal',
                                                                                     'Medication', 'Allergies',
                                                                                     'Examination')))
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key, choices=choices)
        # A selected denial beside another printed question's labelled value.
        notes = 'Medication: methadone.\nCurrent medication: not methadone.'
        both = [v3('f', 'Current medication', 'long_text'), v3('g', 'Medication', 'long_text')]
        self.assert_held(notes, both, {'f': ['Current medication: not methadone.']}, 'f')
        # Another object, site, time-free wider complement, topic or person is not a denial of the value.
        for notes, fields, key in (
                ('Mental state: depressed.\nShe is not suicidal.', text('Mental state'), 'f'),
                ('Mental state: depressed.\nShe is not depressed about work.', text('Mental state'), 'f'),
                ('Mental state: depressed.\nHer mother is not depressed.', text('Mental state'), 'f'),
                ('Mental state: depressed.\nPsychosis: not present.', text('Mental state'), 'f'),
                ('Medication: methadone.\nShe is not on diazepam.', text('Medication'), 'f'),
                ('Medication: methadone.\nShe takes no other medication.', text('Medication'), 'f'),
                ('Allergies: penicillin.\nShe is not allergic to latex.', clinic_form(), 'v3_5'),
                ('Examination: tenderness over the lateral epicondyle.\nThere is no tenderness over the medial '
                 'epicondyle.', clinic_form(), 'v3_7'),
                ('Plan: MRI of the right knee.\nShe does not want an MRI of the left knee.', clinic_form(), 'v3_9'),
                # a statement agreeing with the value, and a denial saying only that another finding is not there
                ('Mental state: depressed.\nShe is depressed.', text('Mental state'), 'f'),
                ('Examination: effusion seen.\nFracture: not seen.', clinic_form(), 'v3_7')):
            selected = notes.split('\n')[0]
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, offered(notes, fields, {key: [selected]}),
                                   {key: selected.split(': ', 1)[1]})

    def test_a_same_topic_statement_by_another_person_holds_a_labelled_answer(self):
        fields = clinic_form()
        for notes, key, selected, choices in (
                ('His father had a heart attack at 55. He smoked heavily. Smoker: Yes.', 'v3_6', 'Smoker: Yes.', YES),
                ('His father had a heart attack at 55. He is allergic to penicillin. Allergies: penicillin.', 'v3_5',
                 'Allergies: penicillin.', None),
                ('His father had a heart attack at 55. He is allergic to penicillin.\nAllergies: penicillin.', 'v3_5',
                 'Allergies: penicillin.', None),
                ('His father had a heart attack at 55. He smoked heavily.\nSmoker: Yes.', 'v3_6', 'Smoker: Yes.', YES)):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key, choices=choices)
        # N05: another person's unrelated history does not hold the patient's labelled answers.
        notes = ('Patient presents with chest tightness on exertion for one month. His father had a heart attack at 55. '
                 'He has high cholesterol. He takes rosuvastatin. Allergies: none known. Smoker: Yes. Examination is '
                 'normal. Assessment is possible stable angina. Plan is an exercise stress test and aspirin 81 mg daily.')
        picks = {'v3_5': ['Allergies: none known.'], 'v3_6': ['Smoker: Yes.'], 'v3_7': ['Examination is normal.'],
                 'v3_8': ['Assessment is possible stable angina.'],
                 'v3_9': ['Plan is an exercise stress test and aspirin 81 mg daily.']}
        self.assert_filled(notes, fields, offered(notes, fields, picks, choices=YES), {
            'v3_5': 'none known.', 'v3_6': 'Yes', 'v3_7': 'normal.', 'v3_8': 'possible stable angina.',
            'v3_9': 'an exercise stress test and aspirin 81 mg daily.'})

    def test_a_dated_past_episode_holds_a_current_state_answer(self):
        right = [v3('v3_1', 'Right knee', 'text')]
        for notes in ('The patient had right knee pain last year.', 'The patient used to have right knee pain.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, right, {'v3_1': [notes]}, 'v3_1')
        # CHANGED PIN (refutation round 1, L3:R3-2): a perfect bounded by a time preposition or adverb ('since 2019',
        # 'before', 'in the past') gets no closed evidence; 'since' is settled only in a presentation opener, so this
        # stays held as on 43fcf214 ('has taken methadone before' / 'has been on warfarin in the past' were released).
        meds = [v3('v3_1', 'Medications', 'long_text')]
        notes = 'The patient has been on warfarin since 2019.'
        self.assert_held(notes, meds, {'v3_1': [notes]}, 'v3_1')
        smoker = [v3('v3_1', 'Smoker', 'choice', '', ['Yes', 'No'])]
        self.assert_held('The patient used to smoke.', smoker, {'v3_1': ['The patient used to smoke.']}, 'v3_1',
                         choices={'v3_1': ['v3_1:0']})
        # A noun-phrase question carries no tense of its own; one opening as a tensed question asks about the past too.
        pain = [v3('v3_1', 'Right knee pain?', 'text')]
        notes = 'The patient had right knee pain last year.'
        self.assert_held(notes, pain, {'v3_1': [notes]}, 'v3_1')
        for label, notes in (('Did the patient have right knee pain?', 'The patient had right knee pain last year.'),
                             ('Was the patient admitted?', 'The patient was admitted last month.')):
            asked = [v3('v3_1', label, 'text')]
            with self.subTest(label=label):
                self.assert_filled(notes, asked, offered(notes, asked, {'v3_1': [notes]}), {'v3_1': notes})
        # A question asking what is so now takes no simple past, dated or not; the present and a perfect answer it.
        for label, notes, held in (
                (order_form()[0]['label'], 'The tribunal placed the patient on a community treatment order.', True),
                (order_form()[0]['label'], 'The patient used to be subject to a community treatment order.', True),
                (order_form()[0]['label'], 'The patient is subject to a community treatment order.', False),
                ('Current medication', 'The patient was started on warfarin.', True),
                ('Current medication', 'The patient has been on warfarin since 2019.', True)):
            asked = [v3('v3_1', label, 'long_text')]
            with self.subTest(label=label, notes=notes):
                if held:
                    self.assert_held(notes, asked, {'v3_1': [notes]}, 'v3_1')
                else:
                    self.assert_filled(notes, asked, offered(notes, asked, {'v3_1': [notes]}), {'v3_1': notes})
        # A history field and a question about a past event keep a dated past statement.
        fields = clinic_form()
        notes = U[1] + ' ' + U[2]
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_2': [U[2]]}), {'v3_2': U[2]})
        last = [v3('v3_1', 'When was the patient last seen by you or by another clinical supervisor?', 'long_text')]
        notes = 'The clinical supervisor saw the patient at the community clinic on 20 September 2026.'
        self.assert_filled(notes, last, offered(notes, last, {'v3_1': [notes]}), {'v3_1': notes})

    def test_a_bounded_or_hedged_statement_holds_a_proven_unit(self):
        meds = [v3('v3_1', 'Medications', 'long_text')]
        for notes in ('The patient starts warfarin when the bleeding stops.',
                      'The patient takes warfarin until the bleeding stops.',
                      'The patient will start warfarin when the bleeding stops.',
                      'The patient possibly takes warfarin.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, meds, {'v3_1': [notes]}, 'v3_1')
        right = [v3('v3_1', 'Right knee', 'text')]
        for notes in ('The patient possibly has right knee pain.', 'She possibly has right knee pain.'):
            with self.subTest(notes=notes):
                self.assert_held('The patient presents for review. ' + notes, right, {'v3_1': [notes]}, 'v3_1')

    def test_retained_contradiction_responses_stay_held(self):
        # Attempts 020-023: the model reported both contradictions; every field is held.
        text = ('{"fields":{"v3_1":{"unit_ids":[1,2],"conflict":true,"context":{"1":"contrary","2":"contrary",'
                '"3":"independent","4":"independent"}},"v3_2":{"unit_ids":[3,4],"conflict":true,"context":'
                '{"1":"independent","2":"independent","3":"contrary","4":"contrary"}}}}')
        for notes, labels in (
                ('The patient is suicidal.\nSuicidal ideation: none.\n\nThe patient is on methadone.\nThe patient is not '
                 'on diazepam or methadone.', ('Suicidal ideation', 'Medication')),
                ('The patient smokes.\nThe patient does not smoke.\n\nThe patient is oriented.\nThe patient is not '
                 'agitated and not oriented.', ('Smoking status', 'Mental state'))):
            fields = [v3('v3_1', labels[0], 'long_text', 'Review'), v3('v3_2', labels[1], 'long_text', 'Review')]
            answers = retained(notes, fields, text)
            self.assertEqual({a['status'] for a in answers.values()}, {'conflict'})

    def test_the_floors_leave_their_controls_useful(self):
        fields = clinic_form()
        # Another person's negation of the same topic is not the patient's.
        notes = 'The patient smokes. Her husband does not smoke.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_6': ['The patient smokes.']}, choices=YES),
                           {'v3_6': 'Yes'})
        # A presentation line opening with 'This is' does not point back at the labelled line before it.
        notes = 'Allergies: none known.\nThis is a 30-year-old female seen for headaches.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_5': ['Allergies: none known.']}),
                           {'v3_5': 'none known.'})
        # Another person's same topic does not hold the patient's own explicit statement.
        notes = 'Her husband has asthma. The patient has asthma.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_3': ['The patient has asthma.']}),
                           {'v3_3': 'The patient has asthma.'})
        # The patient's completed elicited report (its reported subject inside the report) answers its own question.
        notes = ('The patient reports stable relationships with family.\n\nThe relationship reporting condition is '
                 'monitored during weekly supervision visits.\n\nWhen asked directly about relationships, the patient '
                 'said the partner knows about the reporting condition; staff also confirm attendance at planned visits.')
        one = [v3('f', 'In relation to the above question, record the patient\'s response about relationships',
                  'long_text', 'Relationships'),
               v3('g', 'Condition monitoring', 'long_text', 'Relationships')]
        monitored = notes.split('\n\n')[1]
        elicited = notes.split('\n\n')[2]
        self.assert_filled(notes, one, offered(notes, one, {'f': [elicited], 'g': [monitored]}),
                           {'f': elicited, 'g': monitored})
        # A labelled answer after that report sharing its words is not held by the partner named inside the report.
        later = 'Support: staff available daily.'
        record = [v3('h', 'Support', 'long_text', 'Relationships')]
        self.assert_filled(notes + '\n\n' + later, record, offered(notes + '\n\n' + later, record, {'h': [later]}),
                           {'h': 'staff available daily.'})
        # A tensed participle in a label does not make it a question about the past.
        reported = [v3('v3_1', 'Symptoms reported by the patient', 'long_text')]
        notes = 'The patient reported headaches last year.'
        self.assert_held(notes, reported, {'v3_1': [notes]}, 'v3_1')

    def test_a_denial_verb_and_a_dependent_line_past_a_plain_value_hold(self):
        fields = clinic_form()
        self.assert_held('The patient smokes. She denies smoking.', fields, {'v3_6': ['The patient smokes.']}, 'v3_6',
                         choices=YES)
        for notes, selected in (('The patient smokes. She denies smoking.', 'The patient smokes.'),
                                ('Her mood is low. The patient denies low mood.', 'Her mood is low.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, [v3('f', 'Clinical observation', 'long_text')], {'f': [selected]}, 'f')
        self.assert_held('The patient does not smoke. Allergies: none. She quit last month.', fields,
                         {'v3_6': ['The patient does not smoke.']}, 'v3_6', choices=NO)

    def test_a_completed_event_is_not_a_plan(self):
        # N06 forbidden: the procedure-tolerance sentence selected with the plan.
        fields = clinic_form()
        notes = 'The patient was seen for removal of a skin lesion. She tolerated the procedure well. Plan is suture removal in ten days.'
        self.assert_held(notes, fields, {'v3_9': ['She tolerated the procedure well.',
                                                  'Plan is suture removal in ten days.']}, 'v3_9')
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_9': ['Plan is suture removal in ten days.']}),
                           {'v3_9': 'suture removal in ten days.'})


# ─── 5. refutation round 1 (2026-09-30): every confirmed finding's exact inputs ────────────────────────────────────
#: The refuters' adverse inputs (and a few of the same classes they did not send), each with the adverse pick and every
#: other unit called 'independent': the model missing the problem. 43fcf214 held every one of them on this path.
REFUTED = json.loads((Path(__file__).with_name('fixtures') / 'notes_relations_refuted_20260930.json').read_text())


def refuted_form(spec):
    if spec == 'clinic':
        return clinic_form()
    if spec == 'order':
        return order_form()
    return [v3(key, label, kind, context) for key, label, kind, context in spec]


OPENER = 'This is a 30-year-old female seen for headaches.'


@override_settings(**RELATIONS)
class RefutationRound1(Settled, SimpleTestCase):
    """The new evidence of this path is POSITIVE and CLOSED: a pronoun, a thing, an article opener or an explicit
    statement with a settled word counts as the patient's only when the note's structure establishes it, never because
    a list of dangers found nothing (a given name, a person noun outside the lexicon, a seeming verb, a condition word
    outside the marker list all read as nothing to such a list)."""
    def assert_refuted_held(self, finding):
        for case in REFUTED[finding]:
            with self.subTest(case=case['id']):
                self.assert_held(case['notes'], refuted_form(case['form']), case['picks'], case['key'],
                                 choices=case.get('choices'))

    def test_l1_f1_a_named_or_unlisted_person_before_a_pronoun_leaves_it_unresolved(self):
        self.assert_refuted_held('L1:F1')

    def test_l1_f2_a_name_or_unlisted_person_noun_is_never_a_thing_of_the_patients(self):
        self.assert_refuted_held('L1:F2')

    def test_l1_f3_intent_seeming_alternatives_and_prepositional_times_give_no_patient_evidence(self):
        self.assert_refuted_held('L1:F3')
        # Controls: a prepositional 'to', a list under a denial, a dosing 'as needed'.
        order = order_form()
        cto = 'The patient is subject to a community treatment order.'
        self.assert_filled(cto, order, offered(cto, order, {'v3_1': [cto]}), {'v3_1': cto})
        fields = clinic_form()
        for key, statement in (('v3_4', 'She takes ibuprofen as needed.'),
                               ('v3_2', 'She denies visual changes, nausea, or weakness.')):
            notes = OPENER + ' ' + statement
            with self.subTest(statement=statement):
                self.assert_filled(notes, fields, offered(notes, fields, {key: [statement]}), {key: statement})

    def test_l1_f4_a_present_tense_question_asks_what_is_so_now(self):
        self.assert_refuted_held('L1:F4')

    def test_l1_f5_a_condition_outside_the_marker_list_gives_no_patient_evidence(self):
        self.assert_refuted_held('L1:F5')

    def test_l1_f6_a_past_examination_or_a_dated_presentation_is_not_current(self):
        self.assert_refuted_held('L1:F6')
        fields = clinic_form()
        notes = ('The patient was seen for removal of a skin lesion on the left forearm. Plan is suture removal in ten '
                 'days.')
        cc = notes.split(' Plan')[0]
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_1': [cc]}), {'v3_1': cc})

    def test_l2_r2_1_a_nonsmoker_answer_beside_a_smoking_statement_is_held(self):
        self.assert_refuted_held('L2:R2-1')

    def test_l2_r2_2_a_later_cessation_or_denial_of_the_same_topic_holds(self):
        self.assert_refuted_held('L2:R2-2')
        fields = clinic_form()
        notes = OPENER + ' She takes warfarin. She plays tennis.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': ['She takes warfarin.']}),
                           {'v3_4': 'She takes warfarin.'})

    def test_l2_r2_3_a_retraction_fragment_or_an_unprinted_label_holds_a_pronoun_answer(self):
        self.assert_refuted_held('L2:R2-3')
        # A printed question's labelled line places itself.
        fields = clinic_form()
        notes = OPENER + ' She takes warfarin. Allergies: none known.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': ['She takes warfarin.']}),
                           {'v3_4': 'She takes warfarin.'})

    def test_l2_r2_4_a_verbless_or_self_named_allergy_denial_stays_held(self):
        self.assert_refuted_held('L2:R2-4')

    def test_l2_r2_5_a_normal_examination_resolved_only_by_the_form_title_stays_held(self):
        self.assert_refuted_held('L2:R2-5')

    def test_l2_r2_6_a_labelled_value_stopped_later_is_held(self):
        self.assert_refuted_held('L2:R2-6')

    def test_the_closure_reads_every_kind_of_other_reference(self):
        """The same class as L1:F1/F2 in the positions the refuters did not send: each reference kind of
        `v3_actors._closed_reading` has an input only it holds."""
        fields = clinic_form()
        opener = 'This is a 40-year-old female seen for review.'
        for notes, key, selected, choices in (
                ('The patient visits Jane weekly. She takes warfarin.', 'v3_4', 'She takes warfarin.', None),   # a name
                ('The patient presents with cough. The cook has asthma. She uses an inhaler.', 'v3_4',
                 'She uses an inhaler.', None),                                                         # a subject
                ('The patient attends with sam. She is a smoker.', 'v3_6', 'She is a smoker.', YES),      # a companion
                (opener + ' She takes warfarin for Mary.', 'v3_4', 'She takes warfarin for Mary.', None),  # its own name
                (opener + ' According to the pharmacy, she takes warfarin.', 'v3_4',
                 'According to the pharmacy, she takes warfarin.', None),                    # its own definite noun
                (opener + ' They take warfarin.', 'v3_4', 'They take warfarin.', None),      # no singular gender
                # an explicit statement the closed reading admits (a settled 'or', 'to') naming someone else
                ('The patient denies smoking or drinking with Jane.', 'v3_2',
                 'The patient denies smoking or drinking with Jane.', None),
                ('The patient is allergic to penicillin like Jane.', 'v3_5',
                 'The patient is allergic to penicillin like Jane.', None)):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key, choices=choices)
        # Only a BARE complaint is one a later thing may name, and a subject is its head noun, not a compound of it.
        for notes, key, selected in (
                ('A 12-year-old boy presents with an au pair. The au pair reports a cough.', 'v3_2',
                 'The au pair reports a cough.'),
                ('A 12-year-old boy presents with an au pair. The au pair reports a cough. He takes salbutamol.', 'v3_4',
                 'He takes salbutamol.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key)
        order = order_form()
        notes = 'The patient is subject to a community treatment order. The clinic cleaner attends every week.'
        self.assert_held(notes, order, {'v3_2': ['The clinic cleaner attends every week.']}, 'v3_2')
        # The presentation's own complaint, whatever its article, is nobody a later pronoun stands for.
        for notes in ('The patient presents with a rash. She takes cetirizine.',
                      'A 40-year-old woman presents with a rash. She takes cetirizine.'):
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': ['She takes cetirizine.']}),
                                   {'v3_4': 'She takes cetirizine.'})
        # The complaint names no Examination, Assessment or Medications answer (N06, I1: history is not examination).
        notes = 'The patient presents with knee pain. The knee pain is worse on stairs.'
        self.assert_held(notes, fields, {'v3_7': ['The knee pain is worse on stairs.']}, 'v3_7')
        # An institution spelled out by its initialism is not a name, even on a form that does not print it.
        notes = 'The patient is subject to a Community Treatment Order (CTO). She takes warfarin.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': ['She takes warfarin.']}),
                           {'v3_4': 'She takes warfarin.'})
        # A thing answer naming the complaint after somebody else, or naming somebody in itself.
        for notes, selected in (('The patient presents with cough. Tom Brown had a stroke. The cough is worse at night.',
                                 'The cough is worse at night.'),
                                ('The patient presents with cough. The cough is worse with the au pair.',
                                 'The cough is worse with the au pair.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_2': [selected]}, 'v3_2')
        notes = 'The patient presents with cough. The cough is worse at night.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_2': ['The cough is worse at night.']}),
                           {'v3_2': 'The cough is worse at night.'})
        # The presented complaint named again with 'the' is not somebody else.
        notes = 'The patient presents with knee pain. The pain started after a fall. She takes ibuprofen.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': ['She takes ibuprofen.']}),
                           {'v3_4': 'She takes ibuprofen.'})

    def test_the_closed_clause_reads_what_is_settled(self):
        fields = clinic_form()
        opener = 'This is a 40-year-old female seen for review.'
        for key, statement in (('v3_4', 'She reportedly takes warfarin.'),        # an adverb outside the settled list
                               ('v3_4', 'She will take warfarin.'),               # 'will' outside a Plan
                               ('v3_4', 'She took warfarin.'),                    # a simple past, current-state question
                               ('v3_4', 'She takes warfarin unless her INR is high.'),
                               ('v3_4', 'She takes warfarin, if tolerated.'),
                               ('v3_3', 'She thinks she has asthma.'),                # a clausal complement
                               ('v3_4', 'Feeling unwell, she takes paracetamol.'),    # an adverbial clause, unmarked
                               ('v3_4', 'She can have paracetamol.'),                 # a modal other than will/shall
                               ('v3_4', 'She must be on warfarin.'),
                               ('v3_4', 'She has an appointment to start warfarin.')):  # an infinitive inside a noun
            notes = opener + ' ' + statement
            with self.subTest(statement=statement):
                self.assert_held(notes, fields, {key: [statement]}, key)
        for key, statement in (('v3_9', 'She will return in two weeks.'), ('v3_4', 'She takes ibuprofen as required.')):
            notes = opener + ' ' + statement
            with self.subTest(statement=statement):
                self.assert_filled(notes, fields, offered(notes, fields, {key: [statement]}), {key: statement})

    def test_the_same_topic_floor_reads_a_change_in_any_words(self):
        fields = clinic_form()
        opener = 'This is a 40-year-old female seen for review.'
        for later in ('Warfarin was withheld.', 'Her warfarin was paused.',
                      'The patient came off warfarin last month.',
                      'Addendum: all medicines were stopped.'):           # a label the form does not print
            notes = opener + ' She takes warfarin. ' + later
            with self.subTest(later=later):
                self.assert_held(notes, fields, {'v3_4': ['She takes warfarin.']}, 'v3_4')
        # An explicit answer beside a pronoun of the other polarity naming the question (the word overlaps hold it).
        notes = 'The patient presents with cough. The patient is a nonsmoker. She is a smoker.'
        self.assert_held(notes, fields, {'v3_6': ['The patient is a nonsmoker.']}, 'v3_6', choices=NO)
        for notes in (opener + ' She takes warfarin. She is a nonsmoker.',
                      opener + ' She takes warfarin. Allergies: none known. Smoker: No.'):
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': ['She takes warfarin.']}),
                                   {'v3_4': 'She takes warfarin.'})

    def test_l3_r3_2_a_perfect_dated_to_the_past_is_not_current(self):
        self.assert_refuted_held('L3:R3-2')

    def test_l3_r3_3_one_statement_of_two_specific_questions_is_held_when_picked_once(self):
        self.assert_refuted_held('L3:R3-3')
        fields = clinic_form()
        notes = '45-year-old man presents with right knee pain. He takes lisinopril 10 mg daily.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_4': ['He takes lisinopril 10 mg daily.']}),
                           {'v3_4': 'He takes lisinopril 10 mg daily.'})

    def test_l3_r3_4_the_default_path_keeps_the_candidates_opener_grammar(self):
        fields = clinic_form()
        with override_settings(**DEFAULT):
            for notes, label, selected in (
                    ('A 35-year-old woman presents for her father. Allergies: penicillin.', 'Allergies',
                     'Allergies: penicillin.'),
                    ('A 35-year-old woman presents with her mother. Medications: warfarin.', 'Medications',
                     'Medications: warfarin.'),
                    ('A 35-year-old woman presents with cough. Allergies: penicillin.', 'Allergies',
                     'Allergies: penicillin.')):
                with self.subTest(notes=notes):
                    self.assertEqual(run(notes, {label: [selected]}, fields=fields)[label]['status'], 'conflict')
        # The relations path reads the article opener as the patient, with the presentation's own time.
        for notes in ('A 45-year-old man presents with cough.',
                      'A 45-year-old man presents with right knee pain for three weeks after a fall.'):
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, offered(notes, fields, {'v3_1': [notes]}), {'v3_1': notes})

    def test_l3_r3_5_a_stored_relations_draft_survives_a_model_string_rollback(self):
        fields = clinic_form()
        notes = OPENER + ' She takes ibuprofen as needed.'
        answers = offered(notes, fields, {'v3_1': [OPENER], 'v3_4': ['She takes ibuprofen as needed.']})
        stored = {k: answers[k] for k in ('v3_1', 'v3_4')}
        self.assertEqual({k: v['status'] for k, v in stored.items()}, {'v3_1': 'supported', 'v3_4': 'supported'})
        live46 = {'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-4-6'}
        # New generations follow the model string; stored relation records are honoured unless explicitly switched off.
        self.assertFalse(profile.field_relations(live46))
        self.assertTrue(profile.field_relations_records(live46))
        self.assertFalse(profile.field_relations_records({**live46, 'QUILLMD_V3_FIELD_RELATIONS': '0'}))
        with override_settings(V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_RECORDS=True, AI_MODEL='claude-sonnet-4-6'):
            self.assertEqual(g.governed_decisions(notes, fields, stored), [])
            governance = g.governance_for(notes, fields)
            for key, value in stored.items():
                f = next(x for x in fields if x['key'] == key)
                self.assertEqual(g.as_currently_governed(governance, notes, {**f, **value})['status'], 'supported')
        # The explicit kill switch still refuses them.
        with override_settings(V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_RECORDS=False):
            self.assertEqual(sorted(g.governed_decisions(notes, fields, stored)), ['Chief complaint', 'Medications'])


class RequestVersion(SimpleTestCase):
    """L3:R3-1: the default request's printed question context is a prompt change, so it has its own prompt version:
    a job quoted before it (v6), or quoted without the complete-sentence evidence contract, is sent what it was quoted
    for, byte for byte."""
    def captured_for(self, fields, notes, version, natural=True):
        captured = {}

        def create(**kwargs):
            captured['payload'] = json.loads(kwargs['messages'][0]['content'])
            captured['system'] = kwargs['system']
            raise RuntimeError('stop before any request')
        client = MagicMock(); client.messages.create.side_effect = create
        config = {**g.configuration(), 'mode': 'live', 'provider': 'anthropic', 'model': 'claude-sonnet-4-6',
                  'input_rate': '2', 'output_rate': '10', 'cached_rate': '0.2', 'prompt_version': version,
                  'request_profile': g.request_profile('anthropic', 'claude-sonnet-4-6', 'disabled', 'medium', '')}
        if not natural:
            config.pop('v3_evidence_contract', None)
        with patch('anthropic.Anthropic', return_value=client), self.assertRaises(RuntimeError):
            g.generate(notes, fields, config)
        return captured

    @override_settings(**DEFAULT)
    def test_l3_r3_1_question_context_is_sent_only_under_its_own_prompt_version(self):
        self.assertEqual(g.CURRENT_PROMPT_VERSION, 'extractive-v7-question-context')
        self.assertEqual(g.PREVIOUS_PROMPT_VERSION, 'extractive-v6-source-scope-attestation')
        self.assertEqual(g.configuration(repeated_other())['prompt_version'], g.CURRENT_PROMPT_VERSION)
        fields, notes = repeated_other(), 'The patient describes the pain as a tight band around her head.'
        current = self.captured_for(fields, notes, g.CURRENT_PROMPT_VERSION)
        self.assertEqual([q.get('context') for q in current['payload']['questions']], [f['context'] for f in fields])
        self.assertIn('printed context', current['system'])
        for version, natural in ((g.PREVIOUS_PROMPT_VERSION, True), (g.CURRENT_PROMPT_VERSION, False),
                                 (g.PREVIOUS_PROMPT_VERSION, False)):
            with self.subTest(version=version, natural=natural):
                sent = self.captured_for(fields, notes, version, natural)
                self.assertFalse(any('context' in q for q in sent['payload']['questions']))
                self.assertNotIn('printed context', sent['system'])
        # v6 and v7 send the same instructions but for that sentence; the attestation and independent-section
        # sentences stay with the versions that introduced them.
        v6 = self.captured_for(fields, notes, g.PREVIOUS_PROMPT_VERSION)
        self.assertEqual(current['system'].replace(v6['system'], '', 1).strip().startswith('A question may carry'), True)
