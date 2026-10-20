"""Explicit component correction, scoped consent and original-form preservation."""
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.http import QueryDict
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from documents.component_contracts import fixture
from documents.semantic_preparation_roles import (
    build_inventory, default_definitions, fixture_role, identity_scope_issues, validate_definitions,
)
from core import component_review as editor, semantic_preparation as workflow, template_review


def field_post(values):
    from core.tests.test_semantic_preparation import DefinitionPreparationPureTests
    result = DefinitionPreparationPureTests.post(values)
    for key, value in values.items():
        result['field_'+key+'_answer_mode'] = value['answer_mode']
        result['field_'+key+'_patient_name_requirement'] = value['patient_name_requirement']
    return result


def editor_post(prep, field, definition, actor):
    result = field_post({field['key']: definition})
    del result['reviewed_field']
    result['component_token'] = editor.token_for(prep, actor, field['key'])
    result['rendering'] = definition['component_contract']['rendering']
    result['reason'] = 'Compared required parts with the complete original form.'
    result['component_reviewed'] = 'on'
    for part in editor.parts_for(field, definition):
        prefix = 'part_'+str(part['index'])+'_'
        for name in editor.part_controls(definition):
            result[prefix+name] = (part['scope'][name] if name in part['scope'] else part.get(name)) or ''
    return result


class ComponentReviewPureTests(SimpleTestCase):
    def make(self):
        from core.tests.test_semantic_preparation import DefinitionPreparationPureTests
        prep = DefinitionPreparationPureTests().prep(1)
        field = prep.source_version.fields[0]
        field['label'] = 'Name'
        inventory = build_inventory([field], source_version_id='source', source_sha256='a'*64,
                                    original={'questions': ['Name']})
        prep.inventory = inventory; prep.state = 'guided'; prep.config['semantic_definition_version'] = 4
        for role in ('proposer', 'checker'):
            response = fixture_role([field], inventory, role, definition_version=4)
            definition = response['fields'][0]['definition']
            definition.update(value_type='person_name', answer_mode='atomic', meaning='The documented patient name.')
            definition['component_contract'] = fixture(field, definition)
            setattr(prep, 'proposal' if role == 'proposer' else 'checker', response)
        prep.approved_definitions = {}
        return prep, field, N(pk='doctor')

    def test_generic_name_choice_carries_the_disclosed_role_into_its_single_component(self):
        for subject in ('patient', 'clinician', 'other'):
            prep, field, actor = self.make()
            values = workflow.corrected_definitions(prep)
            items = template_review.review_items(prep, [{'field': field, 'definition': values[field['key']], 'state': ''}])
            post = field_post(values)
            post.update(review_summary='on', **template_review.tokens(prep, items, actor.pk))
            post['name_subject_'+field['key']] = subject
            if subject == 'other': post['name_other_'+field['key']] = 'referring clinician'
            updated, _, _ = template_review.submitted(prep, items, actor, post, 'save')
            definition = updated[field['key']]
            validate_definitions([field], updated)
            part = definition['component_contract']['components'][0]
            self.assertEqual(part['scope'], definition['scope'])
            self.assertEqual(part['meaning'], definition['meaning'])
            self.assertEqual(part['scope']['subject'], subject)

    def test_component_draft_is_not_whole_form_or_generic_name_consent(self):
        prep, field, actor = self.make()
        prep.corrections = workflow.corrected_definitions(prep)
        prep.correction_history = [{'review_scope': 'field_components', 'reviewed_fields': [],
                                    'component_reviewed_field': field['key']}]
        self.assertEqual(workflow.fully_reviewed_keys(prep), set())
        rows = template_review.review_items(prep, [{'field':field, 'definition':prep.corrections[field['key']]}])
        self.assertEqual(rows[0]['state'], 'unresolved')

    def test_arbitrary_outer_edit_cannot_keep_stale_component_meaning(self):
        prep, field, actor = self.make()
        field['label'] = 'Patient name'
        definition = workflow.corrected_definitions(prep)[field['key']]
        definition['component_contract']['components'][0]['question_quote'] = field['label']
        items = [{'field':field, 'definition':definition, 'state':''}]
        post = field_post({field['key']:definition})
        post.update(review_summary='on', **template_review.tokens(prep, items, actor.pk))
        post['field_'+field['key']+'_meaning'] = 'The clinician name.'
        post['field_'+field['key']+'_subject'] = 'clinician'
        with self.assertRaisesMessage(ValidationError, 'Edit required parts'):
            template_review.submitted(prep, items, actor, post, 'save')

    def test_editor_allows_explicit_coherent_role_correction_with_fixed_destination(self):
        prep, field, actor = self.make()
        definition = workflow.corrected_definitions(prep)[field['key']]
        post = editor_post(prep, field, definition, actor)
        post['field_'+field['key']+'_subject'] = 'clinician'
        post['field_'+field['key']+'_meaning'] = 'The documented clinician name.'
        post['part_0_subject'] = 'clinician'; post['part_0_meaning'] = 'The documented clinician name.'
        updated = editor.posted_definition(prep, field, definition, post)
        validate_definitions([field], {field['key']:updated})
        self.assertEqual(updated['permitted_destination'], definition['permitted_destination'])
        self.assertEqual(updated['component_contract']['components'][0]['scope']['subject'], 'clinician')

    def test_edited_browser_multiline_meaning_normalizes_only_transport_newlines(self):
        prep, field, actor = self.make()
        definition = workflow.corrected_definitions(prep)[field['key']]
        post = editor_post(prep,field,definition,actor)
        post['field_'+field['key']+'_meaning'] = 'First documented concern.\r\nSecond documented concern.'
        post['part_0_meaning'] = 'First documented concern.\r\nSecond documented concern.'
        updated = editor.posted_definition(prep,field,definition,post)
        validate_definitions([field],{field['key']:updated})
        self.assertEqual(updated['meaning'],'First documented concern.\nSecond documented concern.')
        self.assertEqual(updated['component_contract']['components'][0]['meaning'],updated['meaning'])

    def test_focused_editor_exposes_type_dependent_controls_without_javascript(self):
        from django.template.loader import render_to_string
        prep, field, actor = self.make()
        definition = workflow.corrected_definitions(prep)[field['key']]
        row = template_review.rows([{'field':field,'definition':definition,'state':''}])[0]
        rendered = render_to_string('template_review_field.html',
            {'row':row,'definition_version':4,'editable':True,'component_editing':True})
        for name in ('mode','unit','choices','numeric'):
            self.assertIn('data-control-group="'+name+'" >',rendered)
            self.assertNotIn('data-control-group="'+name+'" hidden',rendered)

    def test_component_token_binds_actor_field_revision_and_prior_definitions(self):
        prep, field, actor = self.make()
        token = editor.token_for(prep, actor, field['key'])
        editor.verify_token(prep, actor, field['key'], token)
        for mutate in (lambda p:setattr(p, 'revision', 1),
                       lambda p:p.proposal['fields'][0]['definition'].update(meaning='Changed'),
                       lambda p:p.source_version.fields[0]['locator'].update(cell=9)):
            other = deepcopy(prep); mutate(other)
            with self.assertRaises(ValidationError): editor.verify_token(other, actor, field['key'], token)
        with self.assertRaises(ValidationError): editor.verify_token(prep, N(pk='other'), field['key'], token)

    def test_missing_or_repeated_consent_and_browser_destination_changes_are_refused(self):
        prep, field, actor = self.make(); value = workflow.corrected_definitions(prep)[field['key']]
        for mutate in (lambda p:p.pop('component_reviewed'),
                       lambda p:p.appendlist('part_0_meaning','second'),
                       lambda p:p.update(field_field_0_locator_sha256='b'*64),
                       lambda p:p.appendlist('part_0_remove','on') or p.appendlist('part_0_remove','on')):
            post = editor_post(prep, field, value, actor); mutate(post)
            with self.assertRaises(ValidationError): editor.posted_definition(prep, field, value, post)

    def test_unresolved_person_role_can_be_reviewed_but_cannot_be_approved_as_complete(self):
        prep, field, actor = self.make(); value = workflow.corrected_definitions(prep)[field['key']]
        value['scope']['subject'] = 'unspecified'
        value['component_contract']['components'][0]['scope']['subject'] = 'unspecified'
        validate_definitions([field], {field['key']:value})
        self.assertIn(field['key'], identity_scope_issues([field], {field['key']:value}))


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
              'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ComponentReviewDatabaseTests(TestCase):
    def setUp(self):
        from core.tests.test_semantic_preparation import DefinitionPreparationDatabaseTests
        DefinitionPreparationDatabaseTests.setUp(self)
        self.prep = workflow.create_preparation(self.source, self.user)
        self.assertTrue(workflow.run_one()); self.prep.refresh_from_db()
        self.client.force_login(self.user)
        self.field = self.source.fields[1]
        self.original = deepcopy((self.source.fields, self.source.semantic_definitions,
                                  self.prep.proposal, self.prep.checker))

    def test_component_save_preserves_all_originals_and_requires_whole_form_review(self):
        current = workflow.corrected_definitions(self.prep)[self.field['key']]
        post = editor_post(self.prep, self.field, current, self.user)
        post['field_'+self.field['key']+'_meaning'] = 'The complete documented presenting concern.'
        post['part_0_meaning'] = 'The complete documented presenting concern.'
        response = self.client.post(reverse('template_definitions_components', args=[self.prep.pk,self.field['key']]), post)
        self.assertEqual(response.status_code, 302)
        self.prep.refresh_from_db(); self.source.refresh_from_db()
        self.assertEqual(self.prep.state, 'guided'); self.assertEqual(self.prep.revision, 1)
        self.assertEqual(self.prep.correction_history[-1]['reviewed_fields'], [])
        self.assertEqual(self.prep.correction_history[-1]['review_scope'], 'field_components')
        self.assertEqual((self.source.fields,self.source.semantic_definitions,self.prep.proposal,self.prep.checker), self.original)
        with self.assertRaises(ValidationError):
            workflow.approve(self.prep.pk, self.user, self.prep.revision,
                self.prep.inventory['inventory_sha256'], list(workflow.corrected_definitions(self.prep)), True)
        self.assertEqual(self.template.versions.count(), 1)

    def test_stale_and_invalid_component_save_keeps_history_and_shows_entered_values(self):
        current = workflow.corrected_definitions(self.prep)[self.field['key']]
        post = editor_post(self.prep, self.field, current, self.user)
        post['part_0_meaning'] = 'Retain this attempted clinical-topic clarification.'
        post['part_0_question_quote'] = 'Not in the original question'
        url = reverse('template_definitions_components', args=[self.prep.pk,self.field['key']])
        response = self.client.post(url, post)
        self.assertContains(response, 'Retain this attempted clinical-topic clarification.', status_code=409)
        self.prep.refresh_from_db(); self.assertEqual(self.prep.corrections, {})
        self.assertEqual(self.prep.correction_history, [])
        self.prep.revision += 1; self.prep.save(update_fields=['revision'])
        self.assertContains(self.client.post(url, post), 'form changed', status_code=409)

    def test_encounter_scope_is_a_bound_draft_until_whole_form_approval(self):
        from documents.component_contracts import CONFIG_KEY, CHOICE_CONTRACT
        self.assertEqual(self.prep.config[CONFIG_KEY], CHOICE_CONTRACT)
        current = workflow.corrected_definitions(self.prep)[self.field['key']]
        url = reverse('template_definitions_components', args=[self.prep.pk,self.field['key']])
        self.assertContains(self.client.get(url), 'name="part_0_encounter_scope"')
        post = editor_post(self.prep, self.field, current, self.user)
        post['part_0_encounter_scope'] = 'all_documented'
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.prep.refresh_from_db(); self.source.refresh_from_db()
        values = workflow.corrected_definitions(self.prep)
        self.assertEqual(values[self.field['key']]['component_contract']['components'][0]['encounter_scope'], 'all_documented')
        self.assertEqual(self.prep.state, 'guided')
        self.assertEqual((self.source.fields,self.source.semantic_definitions,self.prep.proposal,self.prep.checker), self.original)
        self.assertContains(self.client.post(url, post), 'form changed', status_code=409)
        with self.assertRaises(ValidationError):
            workflow.approve(self.prep.pk, self.user, self.prep.revision,
                self.prep.inventory['inventory_sha256'], list(values), True)
        workflow.correct(self.prep.pk, self.user, self.prep.revision, values, list(values),
                         'Compared all encounter scopes and every original field.')
        self.prep.refresh_from_db()
        version = workflow.approve(self.prep.pk, self.user, self.prep.revision,
            self.prep.inventory['inventory_sha256'], list(values), True)
        self.assertEqual(version.semantic_definitions, values)
        self.assertEqual(version.fields, self.source.fields)
        self.assertEqual(workflow.validated_semantic_definitions(version), values)
