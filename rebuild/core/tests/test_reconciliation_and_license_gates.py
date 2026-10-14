"""Synthetic checks for evidence-entry validation and stored CPT display gating."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.billing import reconcile_usage
from core.models import Code, CodeSet, CodeSuggestion, CodingDecision, CodingRun, CostReconciliation, LedgerEntry
from core.tests.test_billing_policy import PolicyFixture, STORAGES


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES)
class ReconciliationInputValidation(PolicyFixture, TestCase):
    def test_invalid_evidence_or_amounts_add_no_adjustment(self):
        usage = self.settled(Decimal('0.5'))
        original = list(LedgerEntry.objects.order_by('pk').values_list('pk', 'amount'))
        invalid = [
            {'reconciled_cost': Decimal('NaN')}, {'reconciled_cost': Decimal('Infinity')},
            {'reconciled_cost': Decimal('-0.1')}, {'reconciled_cost': Decimal('0.400000000001')},
            {'evidence_reference': ''}, {'evidence_reference': 'x' * 241},
            {'evidence_sha256': 'g' * 64}, {'evidence_sha256': 'a' * 63},
            {'provider_credit_applied': Decimal('-1')}, {'discount_applied': Decimal('-1')},
            {'note': 'x' * 241},
        ]
        for changes in invalid:
            args = dict(usage=usage, reconciled_cost=Decimal('0.4'),
                        evidence_reference='SYNTHETIC-INVALID-INPUT', actor=self.user)
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                reconcile_usage(**args)
            self.assertFalse(CostReconciliation.objects.exists())
            self.assertEqual(list(LedgerEntry.objects.order_by('pk').values_list('pk', 'amount')), original)
            self.assertEqual(self.balances(), (Decimal('9.25'), Decimal('0')))


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, AI_MODE='fixture', CPT_ENTITLEMENT_MANIFEST='')
class StoredCptDisplayGate(PolicyFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.encounter.service_date = date(2026, 9, 20)
        self.encounter.notes = 'Synthetic procedure code 99999 explicitly documented.'
        self.encounter.save(update_fields=['notes', 'service_date'])
        release = CodeSet.objects.create(system='CPT', version='SYNTHETIC-ONLY',
                                         effective_from=date(2026, 1, 1), effective_until=date(2026, 12, 31),
                                         source_url='https://example.invalid/synthetic', sha256='a' * 64,
                                         license_reference='synthetic-license')
        code = Code.objects.create(release=release, code='99999',
                                   description='SYNTHETIC LICENSE GATE DESCRIPTOR NOT CPT CONTENT')
        self.suggestion = CodeSuggestion.objects.create(encounter=self.encounter, terminology=code,
                                                        evidence=self.encounter.notes, explanation='Synthetic stored suggestion')
        icd_release = CodeSet.objects.create(system='ICD-10-CM', version='SYNTHETIC-ICD',
                                             effective_from=date(2026, 1, 1), effective_until=date(2026, 12, 31),
                                             source_url='https://example.invalid/synthetic', sha256='b' * 64)
        icd_code = Code.objects.create(release=icd_release, code='M25.532', description='Synthetic ICD descriptor remains visible')
        CodeSuggestion.objects.create(encounter=self.encounter, terminology=icd_code,
                                      evidence=self.encounter.notes, explanation='Synthetic preserved ICD suggestion')

    def assert_not_displayed_or_accepted(self):
        response = self.client.get(f'/encounters/{self.encounter.pk}/?tab=coding')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'SYNTHETIC LICENSE GATE DESCRIPTOR NOT CPT CONTENT')
        self.assertContains(response, 'Synthetic ICD descriptor remains visible')
        self.assertEqual(CodeSuggestion.objects.filter(encounter=self.encounter).count(), 2)
        accepted = self.client.post(f'/encounters/{self.encounter.pk}/coding/{self.suggestion.pk}/accept/')
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(accepted.url, f'/encounters/{self.encounter.pk}/?tab=coding')
        self.suggestion.refresh_from_db()
        self.assertIsNone(self.suggestion.accepted_at)
        self.assertFalse(CodingDecision.objects.exists())
        self.assertFalse(CodingRun.objects.exists())

    @override_settings(CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='')
    def test_stored_cpt_descriptor_is_hidden_without_entitlement(self):
        self.assert_not_displayed_or_accepted()

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2020-01-01')
    def test_stored_cpt_descriptor_is_hidden_after_license_expiry(self):
        self.assert_not_displayed_or_accepted()

    @override_settings(CPT_LICENSE_ID='different-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_current_but_different_entitlement_does_not_display_old_feed(self):
        self.assert_not_displayed_or_accepted()

    @override_settings(CPT_LICENSE_ID='synthetic-license', CPT_LICENSE_EXPIRY='2099-01-01')
    def test_current_matching_environment_id_is_not_an_entitlement_or_new_approval(self):
        self.assert_not_displayed_or_accepted()

    @override_settings(CPT_LICENSE_ID='', CPT_LICENSE_EXPIRY='')
    def test_prior_acceptance_is_preserved_when_descriptor_display_is_disabled(self):
        self.suggestion.accepted_by = self.user
        self.suggestion.accepted_at = timezone.now()
        self.suggestion.save(update_fields=['accepted_by', 'accepted_at'])
        before = CodeSuggestion.objects.filter(pk=self.suggestion.pk).values().get()
        response = self.client.get(f'/encounters/{self.encounter.pk}/?tab=coding')
        self.assertNotContains(response, 'SYNTHETIC LICENSE GATE DESCRIPTOR NOT CPT CONTENT')
        self.assertEqual(CodeSuggestion.objects.filter(pk=self.suggestion.pk).values().get(), before)
