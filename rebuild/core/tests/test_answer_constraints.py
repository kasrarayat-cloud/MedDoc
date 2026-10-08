from django.test import SimpleTestCase
from core.answer_constraints import hold_constraint_mismatches


class ConstraintHeldAnswerTests(SimpleTestCase):
    def test_invalid_ai_choice_is_held_without_losing_the_original_or_evidence(self):
        field={'key':'fever','answer_constraints':{'version':1,'data_type':'choice','options':['Yes','No']}}
        answers={'fever':{'text':'Maybe','status':'supported','reviewed':False,'evidence':['Fever: Maybe']}}
        result=hold_constraint_mismatches([field],answers)
        self.assertEqual(result['fever']['status'],'conflict')
        self.assertEqual(result['fever']['text'],'')
        self.assertEqual(result['fever']['constraint_rejected_text'],'Maybe')
        self.assertEqual(result['fever']['evidence'],answers['fever']['evidence'])
        self.assertEqual(answers['fever']['text'],'Maybe')

    def test_valid_and_legacy_values_are_not_rewritten_or_auto_reviewed(self):
        fields=[{'key':'legacy'}, {'key':'fever','answer_constraints':{'version':1,'data_type':'choice','options':['Yes','No']}}]
        answers={'legacy':{'text':'Whatever source text','status':'supported'},
                 'fever':{'text':'Yes','status':'supported','reviewed':False}}
        self.assertEqual(hold_constraint_mismatches(fields,answers),answers)


from django.test import TestCase, override_settings
from core.tests.test_security import SyntheticFixture
from core.models import TemplateVersion


@override_settings(AI_MODE='fixture', ADMIN_SITE=False,
    STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ConstraintAnswerHTTPTests(SyntheticFixture, TestCase):
    def setUp(self):
        user, _, _, _, template, encounter, _ = self.make_scope('constraint-http')
        self.user, self.encounter = user, encounter
        field = {'key': 'symptoms', 'label': 'Fever', 'kind': 'text', 'locator': {'cell': 0},
                 'answer_constraints': {'version': 1, 'data_type': 'choice', 'options': ['Yes', 'No']}}
        version = TemplateVersion.objects.create(template=template, number=2,
                                                fields=[field], created_by=user)
        encounter.template_version = version
        encounter.save(update_fields=['template_version'])
        self.client.force_login(user)

    def save_answer(self, value, **extra):
        return self.client.post(f'/encounters/{self.encounter.pk}/save/',
            {'revision': self.encounter.revision, 'answer_symptoms': value,
             'reviewed_symptoms': 'on', **extra})

    def test_review_tick_cannot_admit_an_unlisted_value_or_change_any_record(self):
        original = self.encounter.answers.copy()
        response = self.save_answer('Maybe')
        self.assertEqual(response.status_code, 400)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.answers, original)
        self.assertEqual(self.encounter.revision, 0)

    def test_accept_suggestion_cannot_bypass_constraint(self):
        self.encounter.answers = {'symptoms': {'text': '', 'suggestion': 'Maybe',
            'evidence': [], 'status': 'conflict', 'reviewed': False}}
        self.encounter.save(update_fields=['answers'])
        response = self.save_answer('', accept_symptoms='on')
        self.assertEqual(response.status_code, 400)
        self.encounter.refresh_from_db()
        self.assertFalse(self.encounter.answers['symptoms']['reviewed'])

    def test_exact_listed_value_remains_a_separate_explicit_review(self):
        response = self.save_answer('No')
        self.assertEqual(response.status_code, 302)
        self.encounter.refresh_from_db()
        answer = self.encounter.answers['symptoms']
        self.assertEqual(answer['text'], 'No')
        self.assertTrue(answer['reviewed'])
        self.assertEqual(answer['reviewed_by'], str(self.user.pk))

    def test_resolved_constraint_history_does_not_still_claim_a_valid_answer_needs_correction(self):
        self.encounter.answers = {'symptoms': {'text': '', 'evidence': [],
            'status': 'conflict', 'reviewed': False, 'constraint_rejected_text': 'Maybe',
            'constraint_error': 'Choose Yes or No.'}}
        self.encounter.save(update_fields=['answers'])
        self.assertEqual(self.save_answer('No').status_code, 302)
        self.encounter.refresh_from_db()
        self.assertEqual(self.encounter.answers['symptoms']['constraint_rejected_text'], 'Maybe')
        response = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-constraint-held')
        self.assertContains(response, 'data-constraint-history')

    def test_explicit_blank_resolves_the_warning_and_keeps_rejected_source_history(self):
        self.encounter.answers = {'symptoms': {'text': '', 'evidence': [],
            'status': 'conflict', 'reviewed': False, 'constraint_rejected_text': 'Maybe',
            'constraint_error': 'Choose Yes or No.'}}
        self.encounter.save(update_fields=['answers'])
        self.assertEqual(self.save_answer('', blank_symptoms='on').status_code, 302)
        response = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'data-constraint-held')
        self.assertContains(response, 'data-constraint-history')
