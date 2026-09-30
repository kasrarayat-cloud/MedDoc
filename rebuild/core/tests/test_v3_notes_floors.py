"""The field-relations v2 contract as the ordinary-notes contract of a live claude-sonnet-5 deployment, with the
HOLD-ONLY floors a model calling a unit 'independent' cannot remove (2026-09-30).

This is the salvage of fix/v1-notes-relations WITHOUT any of its releases: no statement becomes the patient's here that
43fcf214's relation reader does not already accept (a pronoun, a thing or an implicit subject gets no new evidence), and
the default path validates exactly as on 43fcf214. Provider decisions are simulated (the keyed v2 wire); what is asserted
is what the application does with them. Each floor has an input it holds (43fcf214's relation path adopted it) beside the
control it leaves useful, and every hold is also a refusal of a stored supported copy at finalization.
"""
import json
from unittest.mock import MagicMock, patch

from django.core import signing
from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from core.tests.test_v3_field_relations import offered
from core.tests.test_v3_ordinary_notes import LIVE, field

RELATIONS = dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True, V3_GENERATION_BATCHES=False)
DEFAULT = dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False, V3_GENERATION_BATCHES=False)
TITLE = 'Clinic visit record'
NO, YES = {'v3_6': ['v3_6:1']}, {'v3_6': ['v3_6:0']}
N01 = ('This is a 30-year-old female seen for headaches. The headaches started two months ago and are worse in the '
       'morning. She denies visual changes, nausea, or weakness. She takes ibuprofen as needed. No known drug '
       'allergies. She is a nonsmoker. Neurological examination is normal. Assessment is tension-type headache. '
       'Plan is to start amitriptyline 10 mg at night. She will follow up in six weeks.')
N05 = ('Patient presents with chest tightness on exertion for one month. His father had a heart attack at 55. He has '
       'high cholesterol. He takes rosuvastatin. Allergies: none known. Smoker: Yes. Examination is normal. Assessment '
       'is possible stable angina. Plan is an exercise stress test and aspirin 81 mg daily.')


def v3(key, label, kind='text', context='', options=None):
    made = field(key, label, kind, options)
    made['context'] = context
    return made


def clinic_form():
    """The r1-11 clinic form of the frozen ordinary-notes set (its inspected labels, kinds and contexts)."""
    return [v3('v3_1', 'Chief complaint', 'text', TITLE), v3('v3_2', 'History of present illness', 'long_text', TITLE),
            v3('v3_3', 'Past medical history', 'long_text', TITLE), v3('v3_4', 'Medications', 'long_text', TITLE),
            v3('v3_5', 'Allergies', 'text', TITLE), v3('v3_6', 'Smoker', 'choice', TITLE + ' > Smoker', ['Yes', 'No']),
            v3('v3_7', 'Examination', 'long_text', TITLE), v3('v3_8', 'Assessment', 'long_text', TITLE),
            v3('v3_9', 'Plan', 'long_text', TITLE), v3('v3_10', 'Consent obtained', 'checkbox', 'Sign-off', ['Consent obtained']),
            v3('v3_11', 'Clinician signature', 'signature', 'Sign-off')]


def one(label, kind='long_text', context='Community care review'):
    return [v3('f', label, kind, context)]


def order_form():
    return [v3('v3_1', 'Does a Community Treatment Order (CTO) currently apply to this person?', 'long_text',
               'Community care review'),
            v3('v3_2', 'Clinic attendance', 'long_text', 'Community care review')]


def repeated_other():
    """The n02 form: three write-ins labelled 'Other' under three printed parent questions."""
    return [v3('v3_1', 'Other', 'text', 'How would you describe the pain? (tick all that apply)'),
            v3('v3_2', 'Other', 'text', 'Do you notice anything before the headache begins? (tick all that apply)'),
            v3('v3_3', 'Other', 'text', 'What makes the pain worse? (tick all that apply)')]


class Floors:
    def assert_filled(self, notes, fields, picks, expected, choices=None):
        answers = offered(notes, fields, picks, choices=choices)
        for key, text in expected.items():
            with self.subTest(key=key):
                self.assertEqual((answers[key]['status'], answers[key]['text']), ('supported', text), answers[key])
        supported = {k: v for k, v in answers.items() if v['status'] == 'supported'}
        self.assertEqual(g.governed_decisions(notes, fields, supported), [])
        governance = g.governance_for(notes, fields)
        for f in fields:
            if f['key'] in supported:
                row = g.as_currently_governed(governance, notes, {**f, **supported[f['key']]})
                self.assertEqual((row['status'], row['text']), ('supported', supported[f['key']]['text']))

    def assert_held(self, notes, fields, picks, key, choices=None, shown=None):
        answer = offered(notes, fields, picks, choices=choices)[key]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''), answer)
        if shown is not None:
            # the page shows the line that holds it
            self.assertIn(shown, [c['quote'] for c in answer['held_candidate']['context']])
        # A stored supported copy of the same answer is refused by the page, save and finalization too.
        stored = {k: v for k, v in answer.items() if k != 'held_candidate'}
        stored.update(status='supported', text=(answer.get('held_candidate') or {}).get('text') or picks[key][0])
        label = next(f['label'] for f in fields if f['key'] == key)
        self.assertEqual(g.governed_decisions(notes, fields, {key: stored}), [label])
        return answer


# ─── 1. which contract a deployment runs ─────────────────────────────────────────────────────────────────────────
class ContractSelection(SimpleTestCase):
    def test_field_relations_default_on_only_for_live_claude_sonnet_5(self):
        from quillmd import application_profile as profile
        live5 = {'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-5'}
        self.assertTrue(profile.field_relations(live5))
        for other in ({**live5, 'QUILLMD_AI_MODEL': 'claude-sonnet-4-6'}, {**live5, 'QUILLMD_AI_MODEL': 'gpt-4.1-mini'},
                      {**live5, 'QUILLMD_AI_PROVIDER': 'openai'}, {**live5, 'QUILLMD_AI_MODE': 'fixture'},
                      {k: v for k, v in live5.items() if k != 'QUILLMD_AI_MODE'},
                      {**live5, 'QUILLMD_AI_MODEL': ' claude-sonnet-5'}, {}):
            with self.subTest(environ=other):
                self.assertFalse(profile.field_relations(other))
        self.assertFalse(profile.field_relations({**live5, 'QUILLMD_V3_FIELD_RELATIONS': '0'}))
        self.assertFalse(profile.field_relations({**live5, 'QUILLMD_V3_FIELD_RELATIONS': ''}))
        self.assertTrue(profile.field_relations({'QUILLMD_V3_FIELD_RELATIONS': '1'}))
        # Stored records: read unless explicitly switched off (a model-string rollback turns off only new generations).
        live46 = {**live5, 'QUILLMD_AI_MODEL': 'claude-sonnet-4-6'}
        self.assertTrue(profile.field_relations_records(live46))
        self.assertTrue(profile.field_relations_records({**live46, 'QUILLMD_V3_FIELD_RELATIONS': '1'}))
        self.assertFalse(profile.field_relations_records({**live46, 'QUILLMD_V3_FIELD_RELATIONS': '0'}))

    @override_settings(**dict(RELATIONS, AI_MODEL='claude-sonnet-4-6'))
    def test_another_model_keeps_the_default_request_even_with_the_flag(self):
        fields = clinic_form()
        config = g.configuration(fields)
        self.assertNotIn('ordinary_field_contract', config)
        self.assertEqual(config['request_profile'], g.LEGACY_PROFILE)
        # the installed model reaches the default request builder, never the relations contract
        with patch('core.v3_field_relations.generate', side_effect=AssertionError('relations contract used')), \
                patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = RuntimeError('stop before any request')
            with self.assertRaises(RuntimeError):
                g.generate(N01, fields, {**config, 'mode': 'live'})
            sent = json.loads(provider.return_value.messages.create.call_args.kwargs['messages'][0]['content'])
        self.assertIn('questions', sent)
        self.assertNotIn('catalogue', sent)
        with override_settings(AI_MODEL=g.SONNET_5):
            self.assertEqual(g.configuration(fields)['ordinary_field_contract'], r.CONTRACT)

    @override_settings(**RELATIONS)
    def test_a_stored_draft_survives_a_model_string_rollback_and_the_record_keeps_its_keys(self):
        fields = order_form()
        cto = 'The patient is subject to a Community Treatment Order (CTO).'
        notes = cto + ' The patient attends the clinic every week.'
        stored = {'v3_1': offered(notes, fields, {'v3_1': [cto]})['v3_1']}
        self.assertEqual(stored['v3_1']['status'], 'supported')
        # The signed record carries exactly 43fcf214's seven keys, so a code rollback reads it unchanged.
        record = stored['v3_1']['ordinary_relation']
        self.assertEqual(set(signing.loads(record, salt=r.SALT)),
                         {'contract', 'binding', 'model', 'key', 'competitors', 'competing_output', 'selection'})
        with override_settings(V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_RECORDS=True, AI_MODEL='claude-sonnet-4-6'):
            self.assertEqual(g.governed_decisions(notes, fields, stored), [])
        with override_settings(V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_RECORDS=False):
            self.assertEqual(g.governed_decisions(notes, fields, stored), [fields[0]['label']])


# ─── 2. the default request carries each question's printed context, under its own prompt version ───────────────
class RequestVersion(SimpleTestCase):
    def captured_for(self, fields, notes, version=None, natural=True):
        captured = {}

        def create(**kwargs):
            captured['payload'] = json.loads(kwargs['messages'][0]['content'])
            captured['system'] = kwargs['system']
            raise RuntimeError('stop before any request')
        client = MagicMock(); client.messages.create.side_effect = create
        config = {**g.configuration(), 'mode': 'live', 'provider': 'anthropic', 'model': 'claude-sonnet-4-6',
                  'input_rate': '2', 'output_rate': '10', 'cached_rate': '0.2',
                  'request_profile': g.request_profile('anthropic', 'claude-sonnet-4-6', 'disabled', 'medium', '')}
        if version is not None:
            config['prompt_version'] = version
        if not natural:
            config.pop('v3_evidence_contract', None)
        with patch('anthropic.Anthropic', return_value=client), self.assertRaises(RuntimeError):
            g.generate(notes, fields, config)
        return captured

    @override_settings(**DEFAULT)
    def test_three_other_questions_are_told_apart_by_their_printed_parent_question(self):
        # N02: the default request sent only key, label and answer policy, so three 'Other' questions were identical.
        fields = repeated_other()
        sent = self.captured_for(fields, 'The patient describes the pain as a tight band around her head.')
        self.assertEqual([q.get('context') for q in sent['payload']['questions']], [f['context'] for f in fields])
        self.assertIn('printed context', sent['system'])
        # A question with no printed context carries none (the request for such a form is unchanged).
        plain = [v3('v3_1', 'Chief complaint'), v3('v3_2', 'Plan', 'long_text')]
        sent = self.captured_for(plain, 'Patient presents with cough.')
        self.assertEqual(sent['payload']['questions'], [
            {'key': 'v3_1', 'label': 'Chief complaint', 'answer_policy': 'documented_source_only'},
            {'key': 'v3_2', 'label': 'Plan', 'answer_policy': 'documented_source_only'}])
        self.assertNotIn('printed context', sent['system'])

    @override_settings(**DEFAULT)
    def test_question_context_is_sent_only_under_its_own_prompt_version(self):
        self.assertEqual(g.CURRENT_PROMPT_VERSION, 'extractive-v7-question-context')
        self.assertEqual(g.PREVIOUS_PROMPT_VERSION, 'extractive-v6-source-scope-attestation')
        self.assertEqual(g.configuration(repeated_other())['prompt_version'], g.CURRENT_PROMPT_VERSION)
        fields, notes = repeated_other(), 'The patient describes the pain as a tight band around her head.'
        current = self.captured_for(fields, notes, g.CURRENT_PROMPT_VERSION)
        self.assertEqual([q.get('context') for q in current['payload']['questions']], [f['context'] for f in fields])
        for version, natural in ((g.PREVIOUS_PROMPT_VERSION, True), (g.CURRENT_PROMPT_VERSION, False),
                                 (g.PREVIOUS_PROMPT_VERSION, False)):
            with self.subTest(version=version, natural=natural):
                sent = self.captured_for(fields, notes, version, natural)
                self.assertFalse(any('context' in q for q in sent['payload']['questions']))
                self.assertNotIn('printed context', sent['system'])
        # v6 and v7 send the same instructions but for that one sentence.
        v6 = self.captured_for(fields, notes, g.PREVIOUS_PROMPT_VERSION)
        self.assertTrue(current['system'].replace(v6['system'], '', 1).strip().startswith('A question may carry'))


# ─── 3. the hold-only floors ─────────────────────────────────────────────────────────────────────────────────────
@override_settings(**RELATIONS)
class HoldOnlyFloors(Floors, SimpleTestCase):
    def test_actor_another_persons_statement_holds_a_proven_unit(self):
        self.assert_held('The patient is caring for her grandmother, who has right knee pain.', one('Right knee', 'text'),
                         {'f': ['The patient is caring for her grandmother, who has right knee pain.']}, 'f')
        self.assert_held('45-year-old woman presents with a rash. The patient says he is allergic to penicillin.',
                         clinic_form(), {'v3_5': ['The patient says he is allergic to penicillin.']}, 'v3_5')
        # an age presentation's own noun is the patient (the parser hangs 'seen' on 'woman' as a relative clause)
        self.assert_filled('This is a 30-year-old woman seen for headaches.', clinic_form(),
                           {'v3_1': ['This is a 30-year-old woman seen for headaches.']},
                           {'v3_1': 'This is a 30-year-old woman seen for headaches.'})

    def test_bounded_a_conditioned_statement_holds(self):
        for notes in ('The patient takes warfarin when she travels.',
                      'The patient starts warfarin when the bleeding stops.',
                      'The patient takes warfarin until the bleeding stops.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, one('Medications'), {'f': [notes]}, 'f')

    def test_dated_past_and_the_now_question(self):
        right = one('Right knee', 'text')
        self.assert_held('The patient had right knee pain last year.', right,
                         {'f': ['The patient had right knee pain last year.']}, 'f')
        self.assert_held('The patient used to smoke.', [v3('f', 'Smoker', 'choice', '', ['Yes', 'No'])],
                         {'f': ['The patient used to smoke.']}, 'f', choices={'f': ['f:0']})
        # a present-tense question asks what is so now
        allergic = one('Is the patient allergic to penicillin?')
        self.assert_held('The patient was allergic to penicillin in 2015.', allergic,
                         {'f': ['The patient was allergic to penicillin in 2015.']}, 'f')
        # a question asking what is so now takes no simple past, dated or not
        for label, notes in ((order_form()[0]['label'], 'The tribunal placed the patient on a community treatment order.'),
                             ('Current medication', 'The patient took warfarin.'),
                             ('Current medication', 'The patient was started on warfarin.')):
            with self.subTest(label=label, notes=notes):
                self.assert_held(notes, one(label), {'f': [notes]}, 'f')
        # a presenting-complaint question takes no statement dated to the past
        self.assert_held('The patient presented with a fall in 2019.', clinic_form(),
                         {'v3_1': ['The patient presented with a fall in 2019.']}, 'v3_1')
        # controls: the present answers; a past-tense question and a history keep a dated past
        for label, notes in ((order_form()[0]['label'], 'The patient is subject to a community treatment order.'),
                             ('Did the patient have right knee pain?', 'The patient had right knee pain last year.'),
                             ('Was the patient admitted?', 'The patient was admitted last month.')):
            with self.subTest(label=label, notes=notes):
                self.assert_filled(notes, one(label), {'f': [notes]}, {'f': notes})

    def test_plan_a_completed_event_is_not_a_plan_and_an_intention_is_not_what_is_so_now(self):
        fields = clinic_form()
        notes = ('The patient was seen for removal of a skin lesion. She tolerated the procedure well. Plan is suture '
                 'removal in ten days.')
        self.assert_held(notes, fields, {'v3_9': ['She tolerated the procedure well.',
                                                  'Plan is suture removal in ten days.']}, 'v3_9')
        self.assert_filled(notes, fields, {'v3_9': ['Plan is suture removal in ten days.']},
                           {'v3_9': 'suture removal in ten days.'})
        cto = order_form()
        for notes in ('The patient needs a community treatment order.',
                      'The patient will be placed on a community treatment order.',
                      'The patient is on the waiting list for a community treatment order.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, cto, {'v3_1': [notes]}, 'v3_1')
        for notes in ('The patient declines statins.', 'The patient will start warfarin.',
                      'The patient is a candidate for warfarin.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, one('Medications'), {'f': [notes]}, 'f')
        # controls: a dosing idiom is not an intention; a plan question takes an intention
        self.assert_filled('The patient takes ibuprofen as needed.', one('Medications'),
                           {'f': ['The patient takes ibuprofen as needed.']},
                           {'f': 'The patient takes ibuprofen as needed.'})
        self.assert_filled('The patient will start warfarin.', one('Follow-up plan'),
                           {'f': ['The patient will start warfarin.']}, {'f': 'The patient will start warfarin.'})

    def test_depends_a_later_line_pointing_back_or_a_cessation_naming_nothing(self):
        fields = clinic_form()
        for notes, key, selected, choices in (
                ('The patient was seen for removal of a skin lesion on the left forearm. It was postponed.', 'v3_1',
                 'The patient was seen for removal of a skin lesion on the left forearm.', None),        # B1
                ('Patient presents with chest pain. Not anymore.', 'v3_1', 'Patient presents with chest pain.', None),  # B8
                ('Examination is normal. However, this was before the fall.', 'v3_7', 'Examination is normal.', None),  # C3
                ('Smoker: No.\nBut he quit only last month.', 'v3_6', 'Smoker: No.', NO),                  # C2
                ('Examination is normal.\n\nHowever, this was before the fall.', 'v3_7', 'Examination is normal.', None)):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key, choices=choices)
        # a cessation naming nothing holds wherever it is, before the answer too
        for notes in ('The patient quit five years ago. Smoker: Yes.', 'Smoker: Yes. Allergies: none. The patient quit.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_6': ['Smoker: Yes.']}, 'v3_6', choices=YES)
        # control: a later statement with its own subject and object does not point back
        self.assert_filled('The patient takes warfarin. The patient attends the clinic every week.', one('Medications'),
                           {'f': ['The patient takes warfarin.']}, {'f': 'The patient takes warfarin.'})

    def test_opposed_same_topic(self):
        for notes, label, first, second in (
                ('The patient is on methadone. The patient is not on diazepam or methadone.', 'Medication',
                 'The patient is on methadone.', 'The patient is not on diazepam or methadone.'),        # B7 / N13
                ('The patient smokes.\nThe patient does not smoke.', 'Smoking status',
                 'The patient smokes.', 'The patient does not smoke.'),                                 # N14
                ('The patient is oriented.\nThe patient is not agitated and not oriented.', 'Mental state',
                 'The patient is oriented.', 'The patient is not agitated and not oriented.'),          # N14
                ('The patient is subject to MAPPA.\nNo MAPPA involvement.', 'MAPPA status',
                 'The patient is subject to MAPPA.', 'No MAPPA involvement.')):                         # N15
            for selected in (first, second):
                with self.subTest(notes=notes, selected=selected):
                    self.assert_held(notes, one(label), {'f': [selected]}, 'f')
        fields = clinic_form()
        self.assert_held('Smoker: No.\nHe quit smoking last month.', fields, {'v3_6': ['Smoker: No.']}, 'v3_6', choices=NO)
        # a denial of a labelled value
        for notes, label in (('Mental state: depressed.\nMood is not depressed.', 'Mental state'),
                             ('Medication: methadone.\nThe patient does not take methadone.', 'Medication'),
                             ('Mental state: depressed.\nMood: not depressed.', 'Mental state')):
            with self.subTest(notes=notes):
                self.assert_held(notes, one(label), {'f': [notes.split('\n')[0]]}, 'f')
        # 'no longer', and a denial whose only difference is a word of time
        for notes in ('The patient smokes. The patient no longer smokes.',
                      'The patient smokes. The patient has not smoked in years.'):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_6': ['The patient smokes.']}, 'v3_6', choices=YES)
        # a cessation of what it claims, wherever the parser hangs it
        self.assert_held('The patient presents with chest pain. The pain resolved yesterday.', fields,
                         {'v3_1': ['The patient presents with chest pain.']}, 'v3_1',
                         shown='The pain resolved yesterday.')                                         # B2
        self.assert_held('The patient takes warfarin 5 mg daily. Warfarin was stopped last month.', fields,
                         {'v3_4': ['The patient takes warfarin 5 mg daily.']}, 'v3_4')
        self.assert_held('The patient takes warfarin. The patient came off warfarin.', fields,
                         {'v3_4': ['The patient takes warfarin.']}, 'v3_4')
        # controls: another person's same statement, a cessation of something else
        self.assert_filled('The patient smokes. Her husband smokes.', fields,
                           {'v3_6': ['The patient smokes.']}, {'v3_6': 'Yes'}, choices=YES)
        self.assert_filled('The patient takes warfarin. Aspirin was stopped last month.', one('Medications'),
                           {'f': ['The patient takes warfarin.']}, {'f': 'The patient takes warfarin.'})

    def test_another_persons_same_topic_holds_a_labelled_answer(self):
        fields = clinic_form()
        for notes, key, selected, choices in (
                ('His father had a heart attack at 55. He smoked heavily. Smoker: Yes.', 'v3_6', 'Smoker: Yes.', YES),
                ('His father had a heart attack at 55. He is allergic to penicillin. Allergies: penicillin.', 'v3_5',
                 'Allergies: penicillin.', None),
                ('His father had a heart attack at 55. He smoked heavily.\nSmoker: Yes.', 'v3_6', 'Smoker: Yes.', YES)):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [selected]}, key, choices=choices)
        # N05: another person's unrelated history does not hold the patient's labelled answers
        picks = {'v3_5': ['Allergies: none known.'], 'v3_6': ['Smoker: Yes.'], 'v3_7': ['Examination is normal.'],
                 'v3_8': ['Assessment is possible stable angina.'],
                 'v3_9': ['Plan is an exercise stress test and aspirin 81 mg daily.']}
        self.assert_filled(N05, fields, picks, {
            'v3_5': 'none known.', 'v3_6': 'Yes', 'v3_7': 'normal.', 'v3_8': 'possible stable angina.',
            'v3_9': 'an exercise stress test and aspirin 81 mg daily.'}, choices=YES)

    def test_class_denial(self):
        for notes, selected in (('The patient takes warfarin. The patient takes no anticoagulants.', 'The patient takes warfarin.'),
                                ('The patient takes warfarin. Her husband takes warfarin, not her.', 'The patient takes warfarin.')):
            with self.subTest(notes=notes):
                self.assert_held(notes, clinic_form(), {'v3_4': [selected]}, 'v3_4',
                                 shown=notes.split('. ', 1)[1])
        # control: a denial naming another printed question and not this one
        self.assert_filled('The patient takes warfarin. No known drug allergies.', clinic_form(),
                           {'v3_4': ['The patient takes warfarin.']}, {'v3_4': 'The patient takes warfarin.'})
        # controls: a plain 'not' denies its own predicate (OPPOSED reads its object, time and person), and a quantified
        # thing set apart from what was said is not the class of the answer
        self.assert_filled('The patient smokes. Her husband does not smoke.', clinic_form(),
                           {'v3_6': ['The patient smokes.']}, {'v3_6': 'Yes'}, choices=YES)
        self.assert_filled('The patient is a smoker. The patient is not a drinker.', one('Smoking status'),
                           {'f': ['The patient is a smoker.']}, {'f': 'The patient is a smoker.'})
        self.assert_filled('The patient is subject to MAPPA. Child protection plan: none.', one('MAPPA status'),
                           {'f': ['The patient is subject to MAPPA.']}, {'f': 'The patient is subject to MAPPA.'})
        # STATED OVER-HOLD: a quantified denial naming no printed question ('No fever.') holds every relation answer of
        # the note, since only meaning says whether its class covers one
        self.assert_held('The patient takes warfarin. No fever.', clinic_form(), {'v3_4': ['The patient takes warfarin.']},
                         'v3_4', shown='No fever.')

    def test_reference_answers_stay_filled(self):
        """The independent freeze's answers the relation path already filled on 43fcf214 stay filled."""
        fields = clinic_form()
        self.assert_filled(N01, fields, {'v3_1': ['This is a 30-year-old female seen for headaches.'],
                                         'v3_8': ['Assessment is tension-type headache.']},
                           {'v3_1': 'This is a 30-year-old female seen for headaches.', 'v3_8': 'tension-type headache.'})
        cto = 'The patient is subject to a Community Treatment Order (CTO).'
        self.assert_filled(cto + ' She attends the clinic every week.', order_form(), {'v3_1': [cto]}, {'v3_1': cto})
        self.assert_filled('The patient does not smoke. Allergies: none known.', [
            v3('v3_1', 'Smoker', 'choice', 'Smoking and allergies > Smoker', ['Yes', 'No']),
            v3('v3_2', 'Allergies', 'text', 'Smoking and allergies')],
            {'v3_1': ['The patient does not smoke.'], 'v3_2': ['Allergies: none known.']},
            {'v3_1': 'No', 'v3_2': 'none known.'}, choices={'v3_1': ['v3_1:1']})



def build(form):
    if form == 'clinic':
        return clinic_form()
    if form == 'order':
        return order_form()
    if form.startswith('one:'):
        return one(form[4:])
    if form.startswith('text:'):
        return one(form[5:], 'text')
    raise ValueError(form)


LONG = 'The patient takes ' + ', '.join('drug' + chr(97 + i % 26) + chr(97 + (i // 26) % 26) for i in range(140)) + ' daily.'
#: One input per floor arm that 43fcf214's relation path ADOPTED with every other line called 'independent' and this
#: head holds (the mutation proofs kill each arm's mutant with its row): (arm, form, notes, key, pick, choices).
KILLING = (
    ('ACTOR another person', 'text:Right knee',
     'The patient is caring for her grandmother, who has right knee pain.',
     'f', 'The patient is caring for her grandmother, who has right knee pain.', None),
    ('ACTOR ambiguous pronoun', 'clinic',
     '45-year-old man presents with cough. She takes lisinopril.',
     'v3_4', 'She takes lisinopril.', None),
    ('BOUNDED', 'one:Medications',
     'The patient takes warfarin when she travels.',
     'f', 'The patient takes warfarin when she travels.', None),
    ('DATED PAST current state', 'text:Right knee',
     'The patient had right knee pain last year.',
     'f', 'The patient had right knee pain last year.', None),
    ('DATED PAST verbless labelled value', 'text:Right knee',
     'Right knee: pain last year.',
     'f', 'Right knee: pain last year.', None),
    ('DATED PAST ended habit', 'one:Smoking status',
     'Smoking status: used to smoke.',
     'f', 'Smoking status: used to smoke.', None),
    ('DATED PAST former', 'one:Smoking status',
     'Smoking status: former smoker.',
     'f', 'Smoking status: former smoker.', None),
    ('DATED PAST present-tense question', 'one:Does the patient smoke?',
     'The patient smoked in 2010.',
     'f', 'The patient smoked in 2010.', None),
    ('NOW QUESTION', 'one:Current medication',
     'The patient was on warfarin.',
     'f', 'The patient was on warfarin.', None),
    ('PRESENTING', 'one:Chief complaint',
     'The patient fell last week.',
     'f', 'The patient fell last week.', None),
    ('PLAN completed event', 'one:Plan',
     'The patient tolerated the procedure well.',
     'f', 'The patient tolerated the procedure well.', None),
    ('INTENTION future modal', 'one:Medications',
     'The patient will start warfarin.',
     'f', 'The patient will start warfarin.', None),
    ('INTENTION going to', 'one:Medications',
     'Medications: going to start warfarin.',
     'f', 'Medications: going to start warfarin.', None),
    ('INTENTION word', 'one:Medications',
     'The patient needs warfarin.',
     'f', 'The patient needs warfarin.', None),
    ('INTENTION complement', 'one:Medications',
     'The patient is a candidate for warfarin.',
     'f', 'The patient is a candidate for warfarin.', None),
    ('INTENTION pending status', 'one:Medications',
     'The patient is on the waiting list for insulin.',
     'f', 'The patient is on the waiting list for insulin.', None),
    ('DEPENDS later line', 'clinic',
     'The patient was seen for removal of a skin lesion on the left forearm. It was postponed.',
     'v3_1', 'The patient was seen for removal of a skin lesion on the left forearm.', None),
    ('DEPENDS through a plain value', 'clinic',
     'Examination is normal.\nSmoker: No.\nHowever, this was before the fall.',
     'v3_7', 'Examination is normal.', None),
    ('DEPENDS bare cessation before', 'one:Medications',
     'The patient quit five years ago. The patient takes warfarin.',
     'f', 'The patient takes warfarin.', None),
    ('OPPOSED predicates', 'one:Medication',
     'The patient is on methadone. The patient is not on diazepam or methadone.',
     'f', 'The patient is on methadone.', None),
    ('OPPOSED predicates, the denial picked', 'one:Mental state',
     'The patient is not depressed. Her mood is depressed.',
     'f', 'The patient is not depressed.', None),
    ('OPPOSED no longer', 'one:Smoking status',
     'The patient smokes. The patient no longer smokes.',
     'f', 'The patient smokes.', None),
    ('OPPOSED timeless', 'one:Smoking status',
     'The patient smokes. The patient has not smoked in years.',
     'f', 'The patient smokes.', None),
    ('OPPOSED timeless calendar', 'one:Smoking status',
     'The patient smokes. The patient has not smoked since June.',
     'f', 'The patient smokes.', None),
    ('OPPOSED verbless denial', 'clinic',
     'Smoker: Yes.\nShe denies smoking.',
     'v3_6', 'Smoker: Yes.', YES),
    ('OPPOSED negative labelled value', 'one:Medications',
     'The patient takes warfarin.\nWarfarin: no.',
     'f', 'The patient takes warfarin.', None),
    ('OPPOSED denied labelled value', 'one:Mental state',
     'Mental state: depressed.\nMood is not depressed.',
     'f', 'Mental state: depressed.', None),
    ('OPPOSED unprinted label denial', 'one:Mental state',
     'Mental state: depressed.\nMood: not depressed.',
     'f', 'Mental state: depressed.', None),
    ('OPPOSED labelled topic never had', 'text:Allergies',
     'Allergies: penicillin.\nThe patient has not had an allergic reaction.',
     'f', 'Allergies: penicillin.', None),
    ('OPPOSED cessation passive', 'one:Medications',
     'The patient takes warfarin. Warfarin was stopped last month.',
     'f', 'The patient takes warfarin.', None),
    ('OPPOSED cessation hung on its noun', 'one:Presenting complaint',
     'The patient presents with chest pain. The pain resolved yesterday.',
     'f', 'The patient presents with chest pain.', None),
    ('OPPOSED cessation as a complement', 'one:Presenting complaint',
     'The patient presents with chest pain. The pain is resolved.',
     'f', 'The patient presents with chest pain.', None),
    ('OPPOSED phrasal cessation', 'one:Medications',
     'The patient takes warfarin. The patient came off warfarin.',
     'f', 'The patient takes warfarin.', None),
    ("ANOTHER PERSON'S SAME TOPIC", 'clinic',
     'His father had a heart attack at 55. He smoked heavily. Smoker: Yes.',
     'v3_6', 'Smoker: Yes.', YES),
    ('CLASS DENIAL quantifier', 'one:Anticoagulation',
     'The patient takes warfarin. The patient takes no anticoagulants.',
     'f', 'The patient takes warfarin.', None),
    ('CLASS DENIAL re-attribution', 'one:Medications',
     'The patient takes warfarin. Her husband takes warfarin, not her.',
     'f', 'The patient takes warfarin.', None),
)
#: The control each EXEMPTION keeps useful (43fcf214 and this head fill it; removing the exemption holds it):
#: (exemption, form, notes, pick, expected text, choices).
CONTROLS = (
    ('an age presentation is the patient', 'clinic', 'This is a 30-year-old woman seen for headaches.',
     'This is a 30-year-old woman seen for headaches.', 'This is a 30-year-old woman seen for headaches.', None),
    ('the elicited report', None,
     'When asked directly about relationships, the patient said the partner knows about the reporting condition; staff '
     'also confirm attendance at planned visits.',
     'When asked directly about relationships, the patient said the partner knows about the reporting condition; staff '
     'also confirm attendance at planned visits.',
     'When asked directly about relationships, the patient said the partner knows about the reporting condition; staff '
     'also confirm attendance at planned visits.', None),
    ('a plan question takes an intention', 'one:Follow-up plan', 'The patient will start warfarin.',
     'The patient will start warfarin.', 'The patient will start warfarin.', None),
    ('a dosing idiom', 'one:Medications', 'The patient takes ibuprofen as needed.',
     'The patient takes ibuprofen as needed.', 'The patient takes ibuprofen as needed.', None),
    ('a history co-selecting its own cessation', None, 'The patient took warfarin for a year. The patient discontinued '
     'warfarin last month.', None, 'The patient took warfarin for a year.\nThe patient discontinued warfarin last month.', None),
    ("another person's plain denial", 'clinic', 'The patient smokes. Her husband does not smoke.', 'The patient smokes.',
     'Yes', YES),
    ('a he standing for another person', 'clinic', 'The patient smokes. His father has emphysema. He does not smoke.',
     'The patient smokes.', 'Yes', YES),
    ("another person's run ends at the patient", 'clinic', 'His father smoked. The patient presents with cough. Smoker: No.',
     'Smoker: No.', 'No', NO),
    ("the patient's report of another person", 'clinic', 'The patient reports her husband smokes. Smoker: No.',
     'Smoker: No.', 'No', NO),
    ('a thing set apart', 'one:Medications', 'The patient takes warfarin. The patient has no other symptoms.',
     'The patient takes warfarin.', 'The patient takes warfarin.', None),
    ('a denial naming its own label', 'one:Medications', 'The patient takes warfarin. Diet: none.',
     'The patient takes warfarin.', 'The patient takes warfarin.', None),
    ('a denial naming another printed question', None, 'The patient takes warfarin. The patient has no allergies.',
     'The patient takes warfarin.', 'The patient takes warfarin.', None),
    ('a plain not denies its own predicate', 'one:Smoking status', 'The patient is a smoker. The patient is not a drinker.',
     'The patient is a smoker.', 'The patient is a smoker.', None),
)


@override_settings(**RELATIONS)
class EveryArm(Floors, SimpleTestCase):
    def test_every_floor_arm_holds_its_killing_input(self):
        for arm, form, notes, key, pick, choices in KILLING:
            with self.subTest(arm=arm):
                self.assert_held(notes, build(form), {key: [pick]}, key, choices=choices)

    def test_every_exemption_keeps_its_control_useful(self):
        response = [v3('f', "In relation to the above question, record the patient's response about relationships",
                       'long_text', 'Relationships')]
        for exemption, form, notes, pick, expected, choices in CONTROLS:
            if exemption == 'the elicited report':
                fields = response
            elif exemption == 'a history co-selecting its own cessation':
                fields = one('History of present illness')
            elif exemption == 'a denial naming another printed question':
                fields = one('Medications') + [v3('g', 'Allergies', 'text', 'Community care review')]
            else:
                fields = build(form)
            key = 'f' if fields[0]['key'] == 'f' else ('v3_6' if choices is not None else 'v3_1')
            picks = {key: [pick]} if pick else {key: [s.strip() + ('' if s.strip().endswith('.') else '.')
                                                      for s in notes.split('. ')]}
            with self.subTest(exemption=exemption):
                self.assert_filled(notes, fields, picks, {key: expected}, choices=choices)

    def test_an_unreadable_answer_is_held(self):
        # A unit longer than the parser reads cannot be read by any floor: held (43fcf214 also holds this one).
        self.assert_held(LONG, one('Medications'), {'f': [LONG]}, 'f')


@override_settings(**DEFAULT)
class DefaultPathUntouched(SimpleTestCase):
    def test_the_default_path_never_reads_the_floors(self):
        with patch.object(g, 'v3_relation_causes', side_effect=AssertionError('floor read on the default path')):
            for notes in (N01, N05, 'The patient smokes. The patient does not smoke.'):
                with self.subTest(notes=notes):
                    fields = clinic_form()
                    asked, context, v3_fields = g.v3_generation_fields(fields)
                    units = g.source_units(notes, asked, context_labels=context)[0]
                    chosen = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=[u['id'] for u in units[:1]],
                                                                      conflict=False) for f in asked])
                    answers = g.validate_selections(notes, asked, chosen, context_labels=context,
                                                    evidence_contract=g.TAB_CONTRACT)
                    adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
                    g.governed_decisions(notes, fields, adopted)
