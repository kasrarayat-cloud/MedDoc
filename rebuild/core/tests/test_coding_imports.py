"""Artificial owner documents exercise the real CPT importer and database gate.

The fixture grants no actual rights and contains no licensed CPT content.
"""
from copy import deepcopy
from datetime import date
import hashlib
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core import coding_licensing
from core.models import AuditEvent, Code, CodeSet, CodingRelease


class LicensedCptImportFixture:
    def set_up_licensed_cpt(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.path = self.root / 'licensed-synthetic.csv'
        self.entitlement_path = self.root / 'entitlement.json'
        self.payload = b'code,description\n00000,Synthetic procedure for testing only\n'
        self.artifact(self.path.name, self.payload)
        self.release_metadata = {'version':'synthetic-test', 'effective_from':'2026-01-01',
            'effective_until':'2026-12-31', 'source_url':'https://example.invalid/synthetic-licensed-feed',
            'sha256':hashlib.sha256(self.payload).hexdigest(), 'code_count':1}
        self.rules = {'format':'quillmd-cpt-rules-v1', 'release':deepcopy(self.release_metadata),
            'index':[{'code':'00000','terms':['synthetic procedure'],'reference':'SYNTHETIC index reference'}],
            'tabular':{'codes':{'00000':{'description':'Synthetic procedure for testing only',
                'kind':'procedure','reference':'SYNTHETIC rule reference','instructions':['SYNTHETIC instruction only'],
                'requirements':{'performed_terms':['synthetic procedure performed'], 'required_details':[]}}}}}
        self.manifest = {'format':'quillmd-cpt-entitlement-v1',
            'agreement':self.artifact('agreement.txt',b'SYNTHETIC agreement fixture. No real rights granted.'),
            'issuer':'SYNTHETIC test issuer','license_id':'synthetic-license','product':'QuillMD',
            'users':{'scope':'all_authorized_quillmd_users','terms_reference':'SYNTHETIC user scope'},
            'distribution':{'uses':['application_display','clinical_export','coding_suggestions'],
                            'terms_reference':'SYNTHETIC distribution scope'},
            'intended_ai_use':{'uses':['provider_processing','coding_assistance'],
                'training':'not_authorized_by_this_application','terms_reference':'SYNTHETIC AI permission'},
            'validity':{'from':'2025-01-01','until':'2027-12-31'},
            'content_release':deepcopy(self.release_metadata),'rules':{},'permission_review':{}}
        self.write_entitlement()
        configured = override_settings(CPT_ENTITLEMENT_MANIFEST=str(self.entitlement_path),
            CPT_LICENSE_ID='environment-is-not-authority', CPT_LICENSE_EXPIRY='2099-01-01')
        configured.enable();self.addCleanup(configured.disable)
        clock = patch.object(coding_licensing.timezone,'localdate',return_value=date(2026,10,14))
        clock.start();self.addCleanup(clock.stop)
        self.args = dict(system='CPT',path=str(self.path),sha256=self.release_metadata['sha256'],
            release_version=self.release_metadata['version'],effective_from=self.release_metadata['effective_from'],
            effective_until=self.release_metadata['effective_until'],source_url=self.release_metadata['source_url'],
            expected_count=1,stdout=StringIO())

    def artifact(self, name, raw):
        path = self.root / name
        path.write_bytes(raw);path.chmod(0o600)
        return {'filename':name,'sha256':hashlib.sha256(raw).hexdigest()}

    def write_entitlement(self):
        self.rules['release'] = deepcopy(self.manifest['content_release'])
        self.manifest['rules'] = self.artifact('rules.json',coding_licensing.canonical(self.rules))
        keys = ('agreement','issuer','license_id','product','users','distribution','intended_ai_use',
                'validity','content_release','rules')
        review = {'format':'quillmd-cpt-permission-review-v1','reviewed_by':'SYNTHETIC reviewer',
            'reviewed_at':'2026-10-14','decision':'approved','coverage':{k:deepcopy(self.manifest[k]) for k in keys}}
        self.manifest['permission_review'] = self.artifact('review.json',coding_licensing.canonical(review))
        self.artifact(self.entitlement_path.name,coding_licensing.canonical(self.manifest))


class LicensedCptImports(LicensedCptImportFixture, TestCase):
    def setUp(self):
        self.set_up_licensed_cpt()

    def test_protected_agreement_review_rules_and_feed_reach_real_atomic_import(self):
        before = coding_licensing.cpt_status(date(2026,10,14))
        self.assertFalse(before['available'])
        self.assertTrue(before['license_verified'])
        self.assertEqual(before['missing_requirements'],['dated_content_release'])
        call_command('import_terminology',**self.args)
        release = CodeSet.objects.get()
        reference = CodingRelease.objects.get(release=release)
        proof = coding_licensing.verified_entitlement()
        self.assertEqual(dict(Code.objects.values_list('code','description')),
                         {'00000':'Synthetic procedure for testing only'})
        self.assertEqual(reference.index,self.rules['index'])
        self.assertEqual(reference.tabular,self.rules['tabular'])
        self.assertEqual(reference.provenance,{
            'entitlement_sha256':proof['manifest_sha256'],'rules_sha256':proof['rules_sha256'],
            'agreement_sha256':proof['agreement_sha256'],'permission_review_sha256':proof['permission_review_sha256']})
        self.assertTrue(coding_licensing.cpt_status(date(2026,10,14))['available'])
        outside = coding_licensing.cpt_status(date(2027,1,1))
        self.assertTrue(outside['license_verified']);self.assertFalse(outside['available'])
        self.assertEqual(outside['missing_requirements'],['dated_content_release'])
        self.assertEqual(AuditEvent.objects.filter(action='terminology.import').count(),1)

    def test_matching_manifest_without_licensed_rules_never_writes_a_partial_release(self):
        (self.root/'rules.json').unlink()
        with self.assertRaises(CommandError):call_command('import_terminology',**self.args)
        self.assertEqual((CodeSet.objects.count(),Code.objects.count(),CodingRelease.objects.count(),AuditEvent.objects.count()),(0,0,0,0))

    def test_verified_rule_descriptor_disagreement_rolls_back_the_whole_import(self):
        self.rules['tabular']['codes']['00000']['description']='Different synthetic rule description'
        self.write_entitlement()
        with self.assertRaises(CommandError):call_command('import_terminology',**self.args)
        self.assertEqual((CodeSet.objects.count(),Code.objects.count(),CodingRelease.objects.count(),AuditEvent.objects.count()),(0,0,0,0))
