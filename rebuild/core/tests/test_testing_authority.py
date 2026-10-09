"""Standing authority is explicit, scoped and independent of artificial funds."""
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from core import testing_authority as authority
from core import preparation_campaign as campaign

SETTINGS = dict(TESTING_AUTHORITY_MODE=authority.MODE, TESTING_AUTHORITY_ID=authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256, SYNTHETIC_ONLY=True,
    AI_PROVIDER='anthropic', AI_MODEL='authorized-configured-label')


@override_settings(**SETTINGS)
class StandingAuthorityTests(SimpleTestCase):
    def base(self):
        return {'mode': 'live', 'provider': 'anthropic', 'model': SETTINGS['AI_MODEL']}

    def config(self, kind='preparation'):
        return authority.active_config(self.base(), kind)

    def test_only_explicit_exact_prospective_authority_activates(self):
        self.assertEqual(authority.identity(self.config()), authority.AUTHORITY_ID)
        for mode, name, sha, synthetic in [('',authority.AUTHORITY_ID,authority.AUTHORITY_SHA256,True),
                ('invented',authority.AUTHORITY_ID,authority.AUTHORITY_SHA256,True),
                (authority.MODE,authority.AUTHORITY_ID,'0'*64,True),
                (authority.MODE,authority.AUTHORITY_ID,authority.AUTHORITY_SHA256,False)]:
            with self.subTest(mode=mode, sha=sha), override_settings(TESTING_AUTHORITY_MODE=mode,
                    TESTING_AUTHORITY_ID=name,TESTING_AUTHORITY_SHA256=sha,SYNTHETIC_ONLY=synthetic), self.assertRaises(ValidationError):
                authority.active_config(self.base(),'preparation')

    def test_history_is_never_relabelled_when_authority_disabled(self):
        old=self.base()
        with override_settings(TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256=''):
            self.assertEqual(authority.active_config(old,'preparation'),old)
        self.assertIsNone(authority.identity(old))
        self.assertFalse(authority.KEYS.intersection(old))

    def test_partial_unknown_mixed_and_wrong_purpose_never_fall_back_to_legacy(self):
        for key in authority.KEYS:
            bad={**self.config(),key:None}
            with self.subTest(key=key),self.assertRaises(ValidationError):authority.identity(bad)
        for bad in [{**self.config(),'campaign':campaign.CAMPAIGN},
                    {**self.config(),'testing_purpose':'unrelated-project'},
                    {'testing_authority_id':authority.AUTHORITY_ID}]:
            with self.assertRaises(ValidationError):authority.identity(bad)
        with self.assertRaises(ValidationError):authority.active_config(self.config(),'transcription')
        with self.assertRaises(ValidationError):authority.active_config({**self.base(),'campaign':campaign.CAMPAIGN},'preparation')

    def test_scope_rejects_other_provider_model_kind_and_inactive_actor(self):
        for change in [{'provider':'unapproved'},{'model':'other'},{'mode':'invented'}]:
            with self.subTest(change=change),self.assertRaises(ValidationError):authority.active_config({**self.base(),**change},'generation')
        with self.assertRaises(ValidationError):authority.active_config(self.base(),'unrelated')
        actor=SimpleNamespace(pk=next(iter(authority.ACTORS)),is_active=True)
        department=authority.ACTORS[str(actor.pk)]
        with patch('core.security.membership') as member:
            authority.admit_actor(actor,department);member.assert_called_once()
        for candidate,dept in [(actor,'other'),(SimpleNamespace(pk=actor.pk,is_active=False),department),
                               (SimpleNamespace(pk='admin',is_active=True),department)]:
            with self.assertRaises(ValidationError):authority.admit_actor(candidate,dept)

    def test_estimate_records_cost_without_old_dollar_ceiling(self):
        self.assertEqual(authority.quote('18.0000000000001'),Decimal('18.000000000001'))
        self.assertEqual(authority.quote('2500'),Decimal('2500'))
        for value in ['NaN','Infinity','-1',None]:
            with self.subTest(value=value),self.assertRaises(ValidationError):authority.quote(value)
        self.assertEqual(campaign.campaign_job_config(self.base(),'generation')['testing_purpose'],authority.PURPOSES['generation'])
        self.assertEqual(campaign.active_campaign_config(self.base(),'not-a-finite-form-hash')['testing_purpose'],authority.PURPOSES['preparation'])

    def test_voice_funding_ceiling_is_superseded_but_duration_bound_remains(self):
        from core import jobs
        config=self.config('transcription')
        fake=SimpleNamespace(measured=Decimal('120'),confirmed=Decimal('120'))
        quoted={'too_long':False,'charge_limit':'5.00','within_standard':False,'standard_limit':'0.30'}
        path=Mock();path.read_bytes.return_value=b'synthetic-audio'
        with patch('core.jobs.private_path',return_value=path),patch('core.audio.measure_bounds',return_value=fake), \
                patch('core.jobs.transcription_quote',return_value=quoted):
            bounds,estimate,_=jobs.recording_charge_limit(None,'synthetic.wav',config)
            self.assertIs(bounds,fake);self.assertEqual(estimate,Decimal('5.00'))
        with patch('core.jobs.private_path',return_value=path),patch('core.audio.measure_bounds',return_value=fake), \
                patch('core.jobs.transcription_quote',return_value={**quoted,'too_long':True}),self.assertRaises(ValidationError):
            jobs.recording_charge_limit(None,'synthetic.wav',config)

    def test_provider_contention_refuses_before_send_and_failure_has_no_retry(self):
        cursor=Mock();cursor.fetchone.return_value=(False,)
        db=Mock();db.cursor.return_value=nullcontext(cursor)
        entered=False
        with patch.object(authority,'connection',db),self.assertRaises(authority.TestingProviderRefusal):
            with campaign.provider_slot(self.config()):entered=True
        self.assertFalse(entered)
        cursor=Mock();cursor.fetchone.side_effect=[(True,),(True,)]
        db=Mock();db.cursor.side_effect=[nullcontext(cursor),nullcontext(cursor)]
        with patch.object(authority,'connection',db),self.assertRaisesRegex(RuntimeError,'one-send'):
            with campaign.provider_slot(self.config()):raise RuntimeError('one-send')
        self.assertEqual(cursor.execute.call_count,2)
        self.assertIn('pg_advisory_unlock',cursor.execute.call_args[0][0])
