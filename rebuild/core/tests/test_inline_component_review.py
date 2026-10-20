"""Inline Word component drafts retain source evidence and require whole-form consent."""
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.http import QueryDict,Http404
from django.test import TestCase,SimpleTestCase,override_settings
from django.urls import reverse
from core import inline_component_review as inline,component_review as editor,word_contract,preparation
from core.tests.test_component_review import field_post


def part_post(prep,field,current,actor):
    post=field_post({field['key']:current});del post['reviewed_field']
    post.update(component_token=inline.token_for(prep,actor,field['key']),
        rendering=current['component_contract']['rendering'],component_reviewed='on',
        reason='Compared this required part with the complete unchanged original.')
    for part in editor.parts_for(field,current):
        for name in editor.part_controls(current):
            post['part_'+str(part['index'])+'_'+name]=(part['scope'][name]if name in part['scope']else part.get(name))or''
    return post


class InlineComponentReviewPureTests(SimpleTestCase):
    def prep(self):
        from core.tests.test_word_answer_contract import FreshWordContractTests
        fixture=FreshWordContractTests();fixture.setUp();self.addCleanup(fixture.tearDown)
        version=fixture.version();prep=version.preparation
        prep.config=fixture.graph_config()
        proposal,_=preparation.provider_role(prep.inventory,'proposer',prep.config,1)
        checker,_=preparation.provider_role(prep.inventory,'checker',prep.config,1,proposal)
        prep.proposal,prep.checker=proposal,checker
        prep.template.original_path='original.docx';prep.state='guided'
        return prep

    def test_inline_token_binds_actor_field_revision_source_roles_config_and_path(self):
        prep=self.prep();field=prep.inventory['fields'][0];actor=N(pk='synthetic-reviewer')
        token=inline.token_for(prep,actor,field['key']);inline.verify_token(prep,actor,field['key'],token)
        for change in (lambda p:setattr(p,'revision',p.revision+1),
                       lambda p:p.proposal['answer_definitions']['fields'][0]['definition'].update(meaning='Changed role result.'),
                       lambda p:p.config.update(semantic_component_contract='field-components-v1'),
                       lambda p:setattr(p,'candidate_path','different.docx'),
                       lambda p:setattr(p.template,'original_path','different-original.docx')):
            modified=deepcopy(prep);change(modified)
            with self.assertRaises(ValidationError):inline.verify_token(modified,actor,field['key'],token)
        with self.assertRaises(ValidationError):inline.verify_token(prep,N(pk='other'),field['key'],token)
        with self.assertRaises(ValidationError):inline.verify_token(prep,actor,'other-field',token)

    def test_protected_and_unknown_fields_cannot_enter_inline_editor(self):
        prep=self.prep();key=prep.inventory['fields'][0]['key'];prep.inventory['fields'][0]['label']='Clinician signature'
        with self.assertRaises(Http404):inline.current_field(prep,key)
        with self.assertRaises(Http404):inline.current_field(prep,'not-a-field')
        prep.config['semantic_component_contract']='unknown-components'
        with self.assertRaises(Http404):inline.current_field(prep,key)

    def test_component_draft_cannot_reuse_prior_whole_form_consent(self):
        prep=self.prep();values=word_contract.proposed(prep)
        prep.correction_history=[{'review_scope':'answer_definitions','reviewed_fields':list(values),'answer_definitions':deepcopy(values)}]
        self.assertEqual(word_contract.fully_reviewed_keys(prep),set(values))
        prep.correction_history.append({'review_scope':'field_components','reviewed_fields':[],'answer_definitions':deepcopy(values)})
        self.assertEqual(word_contract.fully_reviewed_keys(prep),set())
        with self.assertRaisesMessage(ValidationError,'whole form'):word_contract.require_resolved(prep)


@override_settings(WORD_PREPARATION_ENABLED=True,AI_MODE='fixture',ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
              'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class InlineComponentReviewDatabaseTests(TestCase):
    def setUp(self):
        from core.tests.test_word_answer_contract import OrdinaryClinicianWordTests
        OrdinaryClinicianWordTests.setUp(self)

    def fresh(self,unresolved=False):
        from core.tests.test_word_answer_contract import OrdinaryClinicianWordTests
        original=preparation.provider_role
        def roles(*args,**kwargs):
            # Finalize the explicit mock response before durable evidence capture.
            arguments=list(args)
            callback=arguments[5] if len(arguments)>5 else kwargs.pop('on_response',None)
            if len(arguments)>5:arguments[5]=None
            response,evidence=original(*arguments,**kwargs)
            if unresolved and args[1]=='checker':response['answer_definitions']['fields'][2].update(state='unresolved',reason='An untouched field still needs its own explicit decision.')
            if callback:callback(evidence)
            return response,evidence
        with patch.object(preparation,'provider_role',side_effect=roles):
            self.template,self.prep=OrdinaryClinicianWordTests.fresh_upload(self,'guided'if unresolved else'review')
        self.field=self.prep.inventory['fields'][1];self.url=reverse('template_preparation_components',args=[self.template.pk,self.field['key']])
        self.original=deepcopy((self.prep.inventory,self.prep.proposal,self.prep.checker,self.prep.candidate_path,self.prep.candidate_sha256,self.prep.candidate_info))
        self.current=word_contract.proposed(self.prep)[self.field['key']]

    def send(self,post):return self.client.post(self.url,post.urlencode(),content_type='application/x-www-form-urlencoded')

    def whole_form_post(self):
        page=self.client.get(reverse('template_preparation',args=[self.template.pk]));context=page.context
        values={r['field']['key']:r['definition']for r in context['definition_rows']};post=field_post(values);del post['reviewed_field']
        post.update(compact_review='on',revision=str(context['preparation'].revision),candidate_sha256=context['preparation'].candidate_sha256,
            review_summary='on',review_token_save=context['review_token_save'],review_token_approve=context['review_token_approve'])
        for row in context['definition_rows']:
            if row.get('state')=='unresolved':
                if row['definition']['value_type']=='person_name':post['name_subject_'+row['field']['key']]=row['definition']['scope']['subject']
                else:post['decision_'+row['field']['key']]='accept'
        return post

    def flat_post(self):
        post=field_post(word_contract.proposed(self.prep))
        post.update(revision=str(self.prep.revision),
            correction_reason='Compared every original answer location and the complete original questions.')
        for field in self.prep.candidate_info['fields']:post['label_'+field['key']]=field['label']
        for anchor in self.prep.inventory['anchors']:post.appendlist('reviewed_anchor',anchor['id'])
        return post

    def test_flat_outer_scope_edit_cannot_reuse_parts_but_unchanged_review_can_save(self):
        self.fresh()
        baseline=deepcopy((self.prep.corrections,self.prep.correction_history,self.prep.revision,self.prep.state))
        post=self.flat_post()
        post['field_'+self.field['key']+'_meaning']='The clinician’s documented presenting concern.'
        post['field_'+self.field['key']+'_subject']='clinician'
        url=reverse('template_preparation_correct',args=[self.template.pk])
        response=self.client.post(url,post.urlencode(),content_type='application/x-www-form-urlencoded')
        self.assertContains(response,'Edit required parts',status_code=409)
        self.prep.refresh_from_db()
        self.assertEqual((self.prep.corrections,self.prep.correction_history,self.prep.revision,self.prep.state),baseline)
        self.assertEqual((self.prep.inventory,self.prep.proposal,self.prep.checker,self.prep.candidate_path,self.prep.candidate_sha256,self.prep.candidate_info),self.original)
        self.assertFalse(self.template.versions.exists())
        values=word_contract.proposed(self.prep)
        response=self.client.post(url,self.flat_post().urlencode(),content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code,302)
        self.prep.refresh_from_db()
        self.assertEqual(word_contract.proposed(self.prep),values)
        self.assertEqual(word_contract.fully_reviewed_keys(self.prep),set(values))
        self.assertEqual(self.prep.revision,1)
        self.assertFalse(self.template.versions.exists())

    def test_real_editor_saves_one_draft_then_requires_whole_form_review_and_approval(self):
        self.fresh();self.assertContains(self.client.get(reverse('template_preparation',args=[self.template.pk])),self.url)
        self.assertContains(self.client.get(self.url),'Back to all definitions')
        post=part_post(self.prep,self.field,self.current,self.user)
        post['field_'+self.field['key']+'_meaning']='The clinician’s documented presenting concern.'
        post['field_'+self.field['key']+'_subject']='clinician';post['part_0_subject']='clinician';post['part_0_meaning']=post['field_'+self.field['key']+'_meaning']
        self.assertEqual(self.send(post).status_code,302);self.prep.refresh_from_db()
        self.assertEqual(self.prep.state,'guided');self.assertEqual(self.prep.revision,1);self.assertEqual(self.template.versions.count(),0)
        self.assertEqual((self.prep.inventory,self.prep.proposal,self.prep.checker,self.prep.candidate_path,self.prep.candidate_sha256,self.prep.candidate_info),self.original)
        values=word_contract.proposed(self.prep);self.assertEqual(values[self.field['key']]['component_contract']['components'][0]['scope']['subject'],'clinician')
        self.assertEqual(self.prep.correction_history[-1]['reviewed_fields'],[])
        self.assertEqual(self.prep.receipts.count(),2)
        with self.assertRaisesMessage(ValidationError,'whole form'):word_contract.require_resolved(self.prep)
        post=self.whole_form_post();self.assertEqual(self.client.post(reverse('template_preparation_correct',args=[self.template.pk]),post).status_code,302)
        self.prep.refresh_from_db();self.assertEqual(self.prep.state,'review');self.assertEqual(word_contract.fully_reviewed_keys(self.prep),set(values))
        self.assertEqual(self.client.post(reverse('template_preparation_approve',args=[self.template.pk]),self.whole_form_post()).status_code,302)
        self.assertEqual(word_contract.require_generation(self.template.versions.get()),values)
        self.prep.refresh_from_db();saved=deepcopy((self.prep.corrections,self.prep.correction_history,self.prep.revision))
        current=word_contract.proposed(self.prep)[self.field['key']];self.assertEqual(self.send(part_post(self.prep,self.field,current,self.user)).status_code,409)
        self.prep.refresh_from_db();self.assertEqual((self.prep.corrections,self.prep.correction_history,self.prep.revision),saved)

    def test_other_unresolved_field_is_not_approved_by_component_draft(self):
        self.fresh(unresolved=True);post=part_post(self.prep,self.field,self.current,self.user);post['part_0_meaning']='The complete documented concern for this field.'
        response=self.send(post);self.assertEqual(response.status_code,302,response.content.decode());self.prep.refresh_from_db()
        untouched=self.prep.inventory['fields'][2]['key'];self.assertIn(untouched,word_contract.approval_issues(self.prep))
        self.assertFalse(self.template.versions.exists())
        self.assertEqual(self.prep.checker,self.original[2])

    def test_missing_repeated_stale_cross_field_and_forged_controls_keep_draft_unchanged(self):
        self.fresh();baseline=deepcopy((self.prep.corrections,self.prep.correction_history,self.prep.revision))
        for mode in ('missing','repeated','forged_destination','stale','cross_field'):
            post=part_post(self.prep,self.field,self.current,self.user)
            if mode=='missing':del post['part_0_meaning']
            if mode=='repeated':post.appendlist('part_0_meaning','duplicate')
            if mode=='forged_destination':post['field_'+self.field['key']+'_locator_sha256']='f'*64
            if mode=='stale':post['component_token']=inline.token_for(N(**{**self.prep.__dict__,'pk':self.prep.pk,'template':self.prep.template,'revision':999}),self.user,self.field['key'])
            if mode=='cross_field':post['component_token']=inline.token_for(self.prep,self.user,self.prep.inventory['fields'][0]['key'])
            with self.subTest(mode=mode):self.assertEqual(self.send(post).status_code,409)
            self.prep.refresh_from_db();self.assertEqual((self.prep.corrections,self.prep.correction_history,self.prep.revision),baseline)
        self.assertFalse(self.template.versions.exists())

    def test_cross_actor_and_employee_cannot_use_another_review(self):
        from core.models import Membership,User
        from django.utils import timezone
        self.fresh();post=part_post(self.prep,self.field,self.current,self.user)
        other=User.objects.create_user(username='inline-other',verified_at=timezone.now());Membership.objects.create(user=other,department=self.department,role='clinician')
        self.client.force_login(other);self.assertEqual(self.send(post).status_code,409)
        Membership.objects.filter(user=other).update(role='employee');self.assertEqual(self.client.get(self.url).status_code,404);self.assertEqual(self.send(post).status_code,404)
        self.prep.refresh_from_db();self.assertEqual(self.prep.corrections,{});self.assertEqual(self.prep.correction_history,[])
