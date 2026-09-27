"""Concrete final-diff counterexamples: a provider identity is independent of model.

All responses below are synthetic. No external API is called. Historical rows
mean earlier jobs in the new QuillMD application, never retired application data.
"""
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings

from core.billing import reserve, settle
from core.jobs import run_one
from core.models import Encounter, Job, LedgerEntry, ProviderReceipt, Usage, Wallet
from .test_security import SyntheticFixture


class ProviderDedupRefutation(SyntheticFixture, TestCase):
    def setUp(self):
        self.scope = self.make_scope("provider-dedup-refutation")

    def job(self, suffix, encounter=None):
        job = Job.objects.create(encounter=encounter or self.scope[5], user=self.scope[0],
            request_key="provider-dedup:" + suffix, config={"mode": "live"})
        reserve(job, Decimal("1"))
        return job

    def assert_one_charge(self):
        self.assertEqual(Usage.objects.count(), 1)
        self.assertEqual(LedgerEntry.objects.filter(kind="usage").count(), 1)
        self.assertEqual(Wallet.objects.get(user=self.scope[0], kind="promo").balance, Decimal("9.85"))

    def test_same_http_request_cannot_charge_again_under_another_model(self):
        first, second = self.job("request-a"), self.job("request-b")
        settle(first, Decimal(".1"), {}, {}, "anthropic:synthetic-model-a", "req_same",
               provider_resource_id="msg_first")
        with self.assertRaises(DatabaseError):
            settle(second, Decimal(".1"), {}, {}, "anthropic:synthetic-model-b", "req_same",
                   provider_resource_id="msg_second")
        self.assert_one_charge()

    def test_same_resource_cannot_charge_again_under_another_model(self):
        first, second = self.job("resource-a"), self.job("resource-b")
        settle(first, Decimal(".1"), {}, {}, "anthropic:synthetic-model-a", "req_first",
               provider_resource_id="msg_same")
        with self.assertRaises(DatabaseError):
            settle(second, Decimal(".1"), {}, {}, "anthropic:synthetic-model-b", "req_second",
                   provider_resource_id="msg_same")
        self.assert_one_charge()

    def test_existing_fresh_app_resource_identity_is_deduplicated_across_columns(self):
        first, second = self.job("earlier-fresh-job"), self.job("new-fresh-job")
        # Before separate identifiers were added, this fresh application stored
        # the Anthropic message resource ID in provider_request_id.
        settle(first, Decimal(".1"), {}, {}, "anthropic:synthetic-model", "msg_same")
        with self.assertRaises(DatabaseError):
            settle(second, Decimal(".1"), {}, {}, "anthropic:synthetic-model", "req_new",
                   provider_resource_id="msg_same")
        self.assert_one_charge()

    def test_duplicate_worker_response_keeps_receipt_without_adopting_or_charging(self):
        second_encounter = Encounter.objects.create(department=self.scope[2], patient=self.scope[3],
            template_version=self.scope[5].template_version, created_by=self.scope[0],
            service_date=self.scope[5].service_date, notes=self.scope[5].notes)
        first = self.job("worker-first")
        second = self.job("worker-second", second_encounter)
        response = SimpleNamespace(id="msg_same", stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps({"fields": [
                {"key": "symptoms", "quotes": ["no chest pain"], "conflict": False}]}))],
            model_dump=lambda **kwargs: {"id": "msg_same"})
        replies = [({"anthropic_response": response, "notes": self.scope[5].notes,
                     "fields": self.scope[5].template_version.fields},
                    Decimal(".1"), {}, {}, provider, request, False)
                   for provider, request in [("anthropic:synthetic-model-a", "req_first"),
                                             ("anthropic:synthetic-model-b", "req_second")]]
        # Live jobs run in a live deployment: a job queued live is refused unsent when the deployment is not live
        # (core.generation.refuse_switched_mode), which is the operator's stop and not what this test is about.
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory), AI_MODE="live"), \
                patch("core.jobs.generation.generate", side_effect=replies) as provider:
            self.assertTrue(run_one())
            self.assertTrue(run_one())
            self.assertFalse(run_one())
            self.assertEqual(provider.call_count, 2)
        first.refresh_from_db(); second.refresh_from_db(); second_encounter.refresh_from_db()
        self.assertEqual(first.state, "succeeded")
        self.assertEqual(second.state, "reconciliation")
        self.assertEqual(second_encounter.answers, {})
        self.assertEqual(ProviderReceipt.objects.filter(job__in=[first, second]).count(), 2)
        self.assertEqual(ProviderReceipt.objects.get(job=second).actual_cost, Decimal(".1"))
        self.assert_one_charge()
