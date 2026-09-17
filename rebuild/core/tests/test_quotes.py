from django.test import RequestFactory,SimpleTestCase,override_settings
from django.core import signing
from django.core.exceptions import ValidationError
from types import SimpleNamespace
from core.views import usage_quote
class UsageQuoteTests(SimpleTestCase):
    @override_settings(AI_MODE='live')
    def test_signed_cost_profile_bound_to_user_document_revision(self):
        user=SimpleNamespace(pk='user');doc=SimpleNamespace(pk='document',revision=2)
        raw=signing.dumps({'user':'user','encounter':'document','revision':2,'config':{'model':'approved-model','input_rate':'1'}},salt='usage-quote')
        req=RequestFactory().post('/',{'usage_quote':raw});req.user=user
        self.assertEqual(usage_quote(req,doc)['model'],'approved-model')
        doc.revision=3
        with self.assertRaises(ValidationError):usage_quote(req,doc)
        doc.revision=2;req.user=SimpleNamespace(pk='other-user')
        with self.assertRaises(ValidationError):usage_quote(req,doc)
    @override_settings(AI_MODE='live')
    def test_missing_or_tampered_quote_refuses_live_usage(self):
        req=RequestFactory().post('/');req.user=SimpleNamespace(pk='user')
        with self.assertRaises(ValidationError):usage_quote(req,SimpleNamespace(pk='document',revision=0))
        req=RequestFactory().post('/',{'usage_quote':'forged'});req.user=SimpleNamespace(pk='user')
        with self.assertRaises(ValidationError):usage_quote(req,SimpleNamespace(pk='document',revision=0))
