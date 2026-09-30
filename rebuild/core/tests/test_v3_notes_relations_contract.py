"""The field-relations v2 contract as the ordinary-notes contract for a live claude-sonnet-5 deployment (2026-09-30).

Provider decisions are simulated (the keyed v2 wire, or the exact retained provider text). What is asserted is what the
application does with them: the model's per-unit relations are the evidence that neighbouring statements are
independent; the application keeps the hard floors it can detect structurally, and those floors only ever HOLD.

Each first decision named in the 2026-09-30 reconciliation has its exact case here, and each new floor has the adverse
input it holds with every other unit called 'independent' (the model missing the problem), beside the control it must
leave useful.
"""
import json
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
            'v3_1': U[1], 'v3_2': U[2] + '\n' + U[3], 'v3_4': U[4], 'v3_5': U[5], 'v3_6': 'No', 'v3_7': U[7],
            'v3_8': 'tension-type headache.', 'v3_9': 'to start amitriptyline 10 mg at night.\n' + U[10]})
        for key in ('v3_3', 'v3_10', 'v3_11'):
            self.assertEqual(answers[key]['status'], 'missing')

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
                                (U[1] + ' She used to take ibuprofen.', 'She used to take ibuprofen.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_4': [selected]}, 'v3_4')

    def test_a_form_title_is_not_a_field_qualifier(self):
        # :372 read 'Neurological examination is normal.' as an unresolved subject because the Examination field's
        # context is the form's title; 'No known drug allergies.' was self-coupled for the same reason.
        fields = clinic_form()
        notes = U[1] + ' ' + U[5] + ' ' + U[7]
        answers = offered(notes, fields, {'v3_5': [U[5]], 'v3_7': [U[7]]})
        self.assert_filled(notes, fields, answers, {'v3_5': U[5], 'v3_7': U[7]})
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
        # Another unit naming the question keeps it coupled; alone, the answer names only its own question; and a
        # qualified field is never self-referenced.
        notes = U[1] + ' She has a penicillin allergy. Referral to the allergy clinic is planned.'
        self.assert_held(notes, fields, {'v3_5': ['She has a penicillin allergy.']}, 'v3_5')
        notes = U[1] + ' She has a penicillin allergy.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_5': ['She has a penicillin allergy.']}),
                           {'v3_5': 'She has a penicillin allergy.'})
        self.assert_held(notes, clinic_form(v3_5='Family history'), {'v3_5': ['She has a penicillin allergy.']}, 'v3_5')
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

    def test_an_age_opener_with_an_article_presents_the_patient_on_both_paths(self):
        fields = clinic_form()
        notes = 'A 45-year-old man presents with cough.'
        self.assert_filled(notes, fields, offered(notes, fields, {'v3_1': [notes]}), {'v3_1': notes})
        with override_settings(**DEFAULT):
            self.assertEqual(run(notes, {'Chief complaint': [notes]}, fields=fields)['Chief complaint']['status'], 'supported')
            # N04 opened with 'A ': the whole note was held (0 of 9); the five answers the bare opener fills return.
            n04 = ('A 45-year-old man presents with right knee pain for three weeks after a fall. He has hypertension '
                   'and takes lisinopril 10 mg daily. Allergies: penicillin. Smoker: No. On examination there is a small '
                   'effusion and medial joint line tenderness. Assessment is a probable medial meniscus tear. Plan is an '
                   'MRI of the right knee and physiotherapy referral.')
            picks = {'Allergies': ['Allergies: penicillin.'], 'Smoker': ['Smoker: No.'],
                     'Examination': ['On examination there is a small effusion and medial joint line tenderness.'],
                     'Assessment': ['Assessment is a probable medial meniscus tear.'],
                     'Plan': ['Plan is an MRI of the right knee and physiotherapy referral.']}
            out = run(n04, picks, fields=fields)
            self.assertEqual({k: out[k]['status'] for k in picks}, {k: 'supported' for k in picks})
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
        # A negation of another topic in the same note is not the same topic (the D30 ordinary shape).
        notes = ('The patient reports stable relationships with family and expects no relationship changes before the '
                 'next report.\n\nThe relationship reporting condition is monitored during weekly supervision visits.'
                 '\n\nNo new physical illness has affected treatment attendance during this reporting period.')
        one = [v3('f', 'Condition monitoring', 'long_text')]
        selected = 'The relationship reporting condition is monitored during weekly supervision visits.'
        self.assert_filled(notes, one, offered(notes, one, {'f': [selected]}), {'f': selected})

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
        # A perfect with a date is current ('has been ... since 2019'), and a plan in the present perfect is a plan.
        meds = [v3('v3_1', 'Medications', 'long_text')]
        notes = 'The patient has been on warfarin since 2019.'
        self.assert_filled(notes, meds, offered(notes, meds, {'v3_1': [notes]}), {'v3_1': notes})
        smoker = [v3('v3_1', 'Smoker', 'choice', '', ['Yes', 'No'])]
        self.assert_held('The patient used to smoke.', smoker, {'v3_1': ['The patient used to smoke.']}, 'v3_1',
                         choices={'v3_1': ['v3_1:0']})
        # A noun-phrase question carries no tense of its own.
        pain = [v3('v3_1', 'Right knee pain?', 'text')]
        notes = 'The patient had right knee pain last year.'
        self.assert_held(notes, pain, {'v3_1': [notes]}, 'v3_1')
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

    def test_a_denial_verb_and_a_dependent_line_past_a_plain_value_hold(self):
        fields = clinic_form()
        self.assert_held('The patient smokes. She denies smoking.', fields, {'v3_6': ['The patient smokes.']}, 'v3_6',
                         choices=YES)
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
