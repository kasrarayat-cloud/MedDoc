"""Purposeful cohort refusals; no network, installed data or provider access."""
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import preparation_campaign as campaign


@override_settings(WORD_PREPARATION_CAMPAIGN=campaign.CAMPAIGN,
                   WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256=campaign.SCOPE_SHA256, SYNTHETIC_ONLY=True)
class DeliveryCampaignTests(SimpleTestCase):
    def config(self):
        return {'mode': 'fixture', 'provider': 'anthropic', 'model': 'configured-label',
                'campaign': campaign.CAMPAIGN, 'campaign_scope_sha256': campaign.SCOPE_SHA256,
                'campaign_actor_scope_sha256': campaign.ACTOR_SCOPE_SHA256}

    def actor(self):
        return SimpleNamespace(pk=next(iter(campaign.ACTORS)), is_active=True)

    def test_old_configuration_remains_byte_for_byte_unclassified(self):
        old = {'mode': 'live', 'model': 'older-label', 'input_rate': '2'}
        self.assertIsNone(campaign.campaign_identity(old))
        with override_settings(WORD_PREPARATION_CAMPAIGN='', WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256=''):
            self.assertEqual(campaign.active_campaign_config(old), old)
        self.assertNotIn('campaign', old)

    def test_partial_null_wrong_or_fabricated_campaign_is_never_legacy(self):
        bad = [{'campaign': None}, {'campaign_scope_sha256': campaign.SCOPE_SHA256},
               {'campaign_actor_scope_sha256': campaign.ACTOR_SCOPE_SHA256},
               {**self.config(), 'campaign': 'other'},
               {**self.config(), 'campaign_scope_sha256': '0' * 64},
               {**self.config(), 'campaign_actor_scope_sha256': '0' * 64}]
        for config in bad:
            with self.subTest(config=config), self.assertRaises(ValidationError):
                campaign.campaign_identity(config)

    def test_runtime_opt_in_cannot_select_unrecorded_scope_or_nonsynthetic_mode(self):
        for name, scope, synthetic in [(campaign.CAMPAIGN, '', True),
                                       ('invented', campaign.SCOPE_SHA256, True),
                                       (campaign.CAMPAIGN, campaign.SCOPE_SHA256, False)]:
            with self.subTest(name=name, synthetic=synthetic), override_settings(
                    WORD_PREPARATION_CAMPAIGN=name, WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256=scope,
                    SYNTHETIC_ONLY=synthetic), self.assertRaises(ValidationError):
                campaign.active_campaign_config({'mode': 'live'})

    def test_exact_opt_in_still_refuses_unknown_original(self):
        with override_settings(WORD_PREPARATION_CAMPAIGN=campaign.CAMPAIGN,
                WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256=campaign.SCOPE_SHA256, SYNTHETIC_ONLY=True):
            with self.assertRaises(ValidationError):
                campaign.active_campaign_config({'mode': 'live'}, '0' * 64)
            result = campaign.active_campaign_config({'mode': 'live'}, next(iter(campaign.FORM_LIMITS)))
            self.assertEqual(campaign.campaign_identity(result), campaign.CAMPAIGN)

    def test_paid_actor_cannot_cross_departments_or_use_admin_identity(self):
        actor = self.actor()
        with patch('core.security.membership') as membership:
            campaign.admit_actor(actor, campaign.ACTORS[str(actor.pk)])
            membership.assert_called_once()
        for bad_actor, department, synthetic in [
                (actor, '46a5abdd-36f1-41f0-968f-8c09c39d9daa', True),
                (SimpleNamespace(pk='2a3e0faf-f261-464d-95f5-35bed5c69efe', is_active=True),
                 campaign.ACTORS[str(actor.pk)], True),
                (SimpleNamespace(pk=actor.pk, is_active=False), campaign.ACTORS[str(actor.pk)], True),
                (actor, campaign.ACTORS[str(actor.pk)], False)]:
            with self.subTest(department=department, synthetic=synthetic), override_settings(SYNTHETIC_ONLY=synthetic), \
                    patch('core.security.membership') as membership, self.assertRaises(ValidationError):
                campaign.admit_actor(bad_actor, department)
            membership.assert_not_called()

    def test_completed_failure_and_unknown_usage_keep_reservations_and_actual_overruns(self):
        receipts = Mock();receipts.values_list.return_value = [
            (Decimal('0.10'), None), (Decimal('0.16'), Decimal('0.24')), (Decimal('0.10'), Decimal('0.01'))]
        jobs = Mock();jobs.values_list.return_value = [('job1', {**self.config(), 'campaign_quote_usd': '0.20'})]
        clinical = Mock();clinical.values_list.return_value = [('job1', Decimal('0.31'))]
        with patch.object(campaign, '_receipts', return_value=receipts), \
                patch('core.models.Job.objects.filter', return_value=jobs), \
                patch('core.models.ProviderReceipt.objects.filter', return_value=clinical):
            self.assertEqual(campaign.exposure(), Decimal('0.75'))

    def test_remaining_budget_cannot_be_bought_by_missing_cost(self):
        with patch.object(campaign, 'exposure', return_value=Decimal('1.60')):
            with self.assertRaises(ValidationError):campaign._admit_quote(Decimal('0.16'))
            campaign._admit_quote(Decimal('0.10'))

    def test_second_attempt_for_same_original_refuses_before_creating(self):
        rows = Mock();rows.count.return_value = 1;rows.filter.return_value.exists.return_value = True
        template = SimpleNamespace(sha256=next(iter(campaign.FORM_LIMITS)),
                                   department_id=next(iter(campaign.ACTORS.values())))
        with patch.object(campaign, 'admit_actor'), patch.object(campaign.transaction, 'atomic', return_value=nullcontext()), \
                patch.object(campaign, '_lock'), patch.object(campaign, '_preparations', return_value=rows), \
                patch('core.models.TemplatePreparation.objects.create') as create, self.assertRaises(ValidationError):
            campaign.create_campaign_preparation(template, self.actor(), self.config())
        create.assert_not_called()

    def test_checker_cannot_skip_proposer_or_pay_for_an_incomplete_proposal(self):
        source = next(iter(campaign.FORM_LIMITS))
        prep = SimpleNamespace(config=self.config(), requested_by=self.actor(),
            template=SimpleNamespace(sha256=source, department_id=next(iter(campaign.ACTORS.values()))))
        rows = Mock();rows.count.return_value = 1
        manager = Mock();manager.filter.return_value.exists.return_value = False
        with patch.object(campaign, 'admit_actor'), patch.object(campaign.transaction, 'atomic', return_value=nullcontext()), \
                patch.object(campaign, '_lock'), patch.object(campaign, '_receipts', return_value=rows), \
                patch('core.models.PreparationReceipt.objects', manager), self.assertRaises(ValidationError):
            campaign.reserve_campaign_role(prep, 'checker', 'a' * 64, Decimal('0.10'))
        manager.create.assert_not_called()

    def test_bad_job_quotes_and_other_job_kinds_refuse(self):
        for quote in ['NaN', 'Infinity', '-1', '0.19', '0.21', None, '']:
            with self.subTest(quote=quote), self.assertRaises(ValidationError):
                campaign._job_quote({**self.config(), 'campaign_quote_usd': quote})
        with self.assertRaises(ValidationError):campaign.campaign_job_config({'mode': 'live'}, 'other')

    def test_provider_contention_never_enters_send_body(self):
        cursor = Mock();cursor.fetchone.return_value = (False,)
        fake_connection = Mock();fake_connection.cursor.return_value = nullcontext(cursor)
        with patch.object(campaign, 'connection', fake_connection):
            entered = False
            with self.assertRaises(ValidationError):
                with campaign.provider_slot(self.config()):entered = True
            self.assertFalse(entered)

    def test_provider_failure_releases_slot_without_an_automatic_retry(self):
        cursor = Mock();cursor.fetchone.side_effect = [(True,), (True,)]
        fake_connection = Mock();fake_connection.cursor.side_effect = [nullcontext(cursor), nullcontext(cursor)]
        with patch.object(campaign, 'connection', fake_connection), \
                patch.object(campaign.transaction, 'atomic', return_value=nullcontext()), \
                patch.object(campaign, '_lock'), patch.object(campaign, 'exposure', return_value=Decimal('0.20')), \
                self.assertRaisesRegex(RuntimeError, 'one failure'):
            with campaign.provider_slot(self.config()):raise RuntimeError('one failure')
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn('pg_advisory_unlock', cursor.execute.call_args[0][0])
