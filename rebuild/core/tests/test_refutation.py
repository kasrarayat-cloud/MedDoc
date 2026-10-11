"""Concrete counterexamples found by independent backend refutation.

All data is synthetic. No provider, payment, or old-system calls are made.
"""

from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core.billing import reserve, settle, welcome_credit
from core.generation import Selection, Selections, validate_selections
from core.models import Department, Encounter, Job, Membership, Organization, Patient, Template, TemplateVersion, User, Usage, Wallet, Reservation, CodeSet, Code, CodeSuggestion, ProviderReceipt
from core.security import membership
from core.tests.audio_fixtures import wav_bytes


class ClinicalRefutation(SimpleTestCase):
    def safe_or_complete(self, source, fragment):
        fields = [{"key": "symptoms", "label": "Symptoms"}]
        selections = Selections(fields=[Selection(key="symptoms", quotes=[fragment], conflict=False)])
        try:
            answer = validate_selections(source, fields, selections)["symptoms"]
        except ValidationError:
            return
        if answer["status"] == "supported":
            self.assertEqual(answer["text"], source)

    def test_provider_fragment_cannot_drop_negation(self):
        self.safe_or_complete("Patient denies chest pain.", "chest pain")

    def test_provider_fragment_cannot_drop_uncertainty(self):
        self.safe_or_complete("Pneumonia cannot be excluded.", "Pneumonia")

    def test_provider_fragment_cannot_change_family_history_to_patient_finding(self):
        self.safe_or_complete("Mother has diabetes; patient does not.", "diabetes")

    def test_whole_line_cannot_drop_negated_list_heading(self):
        self.safe_or_complete("The following symptoms are denied:\nchest pain\nshortness of breath", "chest pain")

    def test_whole_line_cannot_drop_family_history_heading(self):
        self.safe_or_complete("Family history:\nDiabetes", "Diabetes")

    def test_provider_cannot_hide_known_repeated_label_conflict(self):
        source = "Symptoms: no chest pain\nSymptoms: chest pain"
        selections = Selections(fields=[Selection(key="symptoms", quotes=["chest pain"], conflict=False)])
        try:
            answer = validate_selections(source, [{"key": "symptoms", "label": "Symptoms"}], selections)["symptoms"]
        except ValidationError:
            return
        self.assertEqual(answer["status"], "conflict")

    def test_exact_quote_cannot_be_adopted_under_another_explicit_question(self):
        source = "Symptoms: No chest pain.\nPlan: Start antibiotics."
        fields = [{"key": "symptoms", "label": "Symptoms"}, {"key": "plan", "label": "Plan"}]
        selections = Selections(fields=[Selection(key="symptoms", quotes=["Plan: Start antibiotics."], conflict=False), Selection(key="plan", quotes=["Symptoms: No chest pain."], conflict=False)])
        try:
            answers = validate_selections(source, fields, selections)
        except ValidationError:
            return
        for answer in answers.values():
            self.assertNotEqual(answer["status"], "supported")


class AuthorizationAndPayerRefutation(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=Path(self.directory.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.directory.cleanup)
        self.user = User.objects.create_user(username="refute-synthetic", email="refute@synthetic.invalid", verified_at=timezone.now())
        self.org = Organization.objects.create(name="Synthetic refutation organization")
        self.department = Department.objects.create(name="X-ray", organization=self.org)
        Membership.objects.create(user=self.user, department=self.department, role="clinician")
        # This empty opaque fixture tests reservation/configuration boundaries,
        # not Word semantic admission or automatic clinical extraction.
        template = Template.objects.create(department=self.department, name="Synthetic", format="pdf", original_name="synthetic.pdf", original_path="unused.pdf", sha256="0" * 64, created_by=self.user)
        mapping = TemplateVersion.objects.create(template=template, number=1, fields=[], created_by=self.user)
        patient = Patient.objects.create(department=self.department, display_name="Synthetic patient", reference="refute", created_by=self.user)
        encounter = Encounter.objects.create(department=self.department, patient=patient, template_version=mapping, created_by=self.user, service_date=timezone.localdate(), notes="Synthetic notes")
        self.job = Job.objects.create(encounter=encounter, user=self.user, request_key="refute:1")
        welcome_credit(self.user)

    def test_deactivated_user_cannot_pass_with_cached_user_object(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            membership(self.user, self.department)

    def test_payer_is_attributed_to_reservation_not_later_policy(self):
        reserve(self.job, Decimal("1"))
        self.department.organization_pays = True
        self.department.save(update_fields=["organization_pays"])
        usage = settle(self.job, Decimal("1"), {}, {}, "synthetic-test", "synthetic-request", False)
        self.assertEqual(usage.payer, f"user:{self.user.pk}")

    @override_settings(AI_MODE="fixture")
    def test_repeated_transcription_request_after_completion_is_not_charged_again(self):
        from core.jobs import enqueue, run_one
        self.job.state = "failed"
        self.job.save(update_fields=["state"])
        encounter = self.job.encounter
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=Path(directory)), patch.dict(os.environ, {"QUILLMD_DEEPGRAM_RATE_PER_SECOND": "0.01"}):
            audio = Path(directory) / "audio" / "same-submitted-recording.webm"
            audio.parent.mkdir()
            audio.write_bytes(wav_bytes(tag="same-submitted-recording"))
            first = enqueue(encounter, self.user, "transcription", "audio/same-submitted-recording.webm")
            result = ("Synthetic transcript", Decimal("0.125"), {}, {}, "synthetic-test", "synthetic-transcription-1", False)
            with patch("core.jobs.transcribe", return_value=result):
                run_one()
            # A response was lost; the identical submitted request is delivered again.
            second = enqueue(encounter, self.user, "transcription", "audio/same-submitted-recording.webm")
        self.assertEqual(first.pk, second.pk)

    @override_settings(AI_MODE="live")
    def test_invalid_clinical_output_retains_real_cost_before_rejection(self):
        from core.jobs import run_one
        reserve(self.job, Decimal("0.2"))
        invalid = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="not valid provider JSON")])
        invalid.model_dump = lambda **kwargs: {"stop_reason": "end_turn", "content": [{"type": "text", "text": "not valid provider JSON"}]}
        result = ({"anthropic_response": invalid, "notes": self.job.encounter.notes, "fields": []}, Decimal("0.125"), {"input_tokens": 100}, {"input_per_million": "1"}, "synthetic-provider", "known_invalid_output", False)
        with patch("core.jobs.generation.generate", return_value=result):
            run_one()
        usage = Usage.objects.get(job=self.job)
        self.assertEqual(usage.actual_cost, Decimal("0.125"))
        self.assertEqual(usage.charged_cost, Decimal("0.1875"))
        self.job.refresh_from_db()
        self.assertEqual(self.job.state, "failed")
        self.assertEqual(self.job.encounter.answers, {})

    @override_settings(AI_MODE="live")
    def test_unknown_provider_timeout_keeps_hold_and_does_not_retry(self):
        from core.jobs import run_one
        reserve(self.job, Decimal("0.2"))
        with patch("core.jobs.generation.generate", side_effect=TimeoutError("synthetic uncertain provider outcome")) as provider:
            self.assertTrue(run_one())
            self.assertFalse(run_one())
        self.assertEqual(provider.call_count, 1)
        self.job.refresh_from_db()
        self.assertEqual(self.job.state, "reconciliation")
        self.assertFalse(Usage.objects.filter(job=self.job).exists())
        self.assertEqual(Wallet.objects.get(user=self.user, kind="promo").reserved, Decimal("0.3"))
        self.assertEqual(Reservation.objects.get(job=self.job).state, "held")

    @override_settings(AI_MODE="live")
    def test_observed_provider_request_survives_settlement_over_reservation(self):
        from core.jobs import run_one
        reserve(self.job, Decimal("0.1"))
        result = ({}, Decimal("1"), {"input_tokens": 1000}, {"input_per_million": "1000"}, "synthetic-provider", "known_over_reservation", False)
        with patch("core.jobs.generation.generate", return_value=result):
            run_one()
        self.job.refresh_from_db()
        # The held limit binds: the charge is capped at it and the rest is absorbed as a platform cost (charge limit policy).
        # The request identity and receipt survive exactly as before.
        from core.models import PlatformCost
        usage = Usage.objects.get(job=self.job)
        self.assertEqual(usage.actual_cost, Decimal("1")); self.assertEqual(usage.charged_cost, Decimal("0.15"))
        self.assertEqual(PlatformCost.objects.get(job=self.job, kind="absorbed_over_limit").amount, Decimal("1.35"))
        self.assertEqual(self.job.state, "succeeded")
        self.assertEqual(self.job.provider_request_id, "known_over_reservation")
        receipt = ProviderReceipt.objects.get(job=self.job)
        self.assertEqual(receipt.actual_cost, Decimal("1"))
        self.assertEqual(receipt.units, {"input_tokens": 1000})

    @override_settings(AI_MODE="live")
    def test_observed_cost_survives_receipt_file_write_failure(self):
        from core.jobs import run_one
        reserve(self.job, Decimal("0.2"))
        result = ({}, Decimal("0.125"), {"input_tokens": 100}, {"input_per_million": "1250"}, "synthetic-provider", "known_file_write_failure", False)
        with patch("core.jobs.generation.generate", return_value=result), patch("pathlib.Path.open", side_effect=OSError("synthetic receipt storage full")):
            run_one()
        receipt = ProviderReceipt.objects.filter(job=self.job).first()
        self.assertIsNotNone(receipt, "Known provider cost must survive failure to store clinical result bytes")
        self.assertEqual(receipt.actual_cost, Decimal("0.125"))
        self.assertEqual(receipt.provider_request_id, "known_file_write_failure")

    @override_settings(AI_MODE="live")
    def test_transcription_missing_text_preserves_valid_provider_usage_metadata(self):
        from core.jobs import run_one
        audio = Path(self.directory.name) / "synthetic.wav"
        audio.write_bytes(wav_bytes(tag="missing-text"))
        self.job.state = "failed"
        self.job.save(update_fields=["state"])
        self.job = Job.objects.create(encounter=self.job.encounter, user=self.user,
            request_key="refute:transcription", kind="transcription", input_path="synthetic.wav",
            config={"mode": "live", "voice_rate_minute": "0.01", "voice_rate_second": ""})
        reserve(self.job, Decimal("0.2"))
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"metadata": {"duration": 60, "request_id": "known_transcription_missing_text"}, "results": {"channels": []}})
        with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "synthetic-not-a-live-key"}), patch("core.jobs.httpx.post", return_value=response):
            run_one()
        receipt = ProviderReceipt.objects.filter(job=self.job).first()
        self.assertIsNotNone(receipt, "Provider duration/request metadata is known even when clinical transcript structure is invalid")
        self.assertEqual(receipt.actual_cost, Decimal("0.01"))
        self.assertEqual(receipt.provider_request_id, "known_transcription_missing_text")

    def test_queued_configuration_is_passed_unchanged_after_runtime_settings_change(self):
        from core import generation
        from core.jobs import enqueue, run_one
        self.job.state = "failed"
        self.job.save(update_fields=["state"])
        # A new saved source revision explicitly authorizes a distinct request.
        encounter = self.job.encounter
        encounter.revision += 1
        encounter.save(update_fields=["revision"])
        with override_settings(AI_MODE="fixture", AI_PROVIDER="anthropic", AI_MODEL="synthetic-original", AI_INPUT_RATE="1", AI_OUTPUT_RATE="5", AI_CACHED_RATE="0.1"):
            job = enqueue(encounter, self.user)
        self.assertNotEqual(job.pk, self.job.pk)
        expected = job.config.copy()
        with override_settings(AI_MODE="live", AI_PROVIDER="openai", AI_MODEL="synthetic-changed", AI_INPUT_RATE="100", AI_OUTPUT_RATE="500", AI_CACHED_RATE="10"), patch("core.jobs.generation.generate", wraps=generation.generate) as provider:
            self.assertTrue(run_one())
        provider.assert_called_once()
        self.assertEqual(provider.call_args.args[2], expected)
        job.refresh_from_db()
        self.assertEqual(job.config, expected)
        self.assertTrue(Usage.objects.get(job=job).simulated)
        self.assertEqual(Usage.objects.get(job=job).charged_cost, 0)

    def test_live_timeout_classification_uses_queued_mode_not_current_mode(self):
        from core.jobs import enqueue, run_one
        self.job.state = "failed"
        self.job.save(update_fields=["state"])
        # A replay of the failed revision is observation, not a new paid request.
        encounter = self.job.encounter
        encounter.revision += 1
        encounter.save(update_fields=["revision"])
        with override_settings(AI_MODE="live", AI_PROVIDER="anthropic", AI_MODEL="synthetic-original", AI_INPUT_RATE="1", AI_OUTPUT_RATE="5", AI_CACHED_RATE="0.1"):
            job = enqueue(encounter, self.user)
        self.assertNotEqual(job.pk, self.job.pk)
        reserved_before = Wallet.objects.get(user=self.user, kind="promo").reserved
        with override_settings(AI_MODE="fixture"), patch("core.jobs.generation.generate", side_effect=TimeoutError("synthetic unknown live request")) as provider:
            self.assertTrue(run_one())
        provider.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.state, "reconciliation")
        self.assertEqual(Wallet.objects.get(user=self.user, kind="promo").reserved, reserved_before)

    @override_settings(AI_MODE="live")
    def test_transcription_source_change_invalidates_prior_coding_acceptance(self):
        from core.jobs import run_one
        encounter = self.job.encounter
        encounter.notes = "Diagnosis code: R00.0"
        encounter.save(update_fields=["notes"])
        release = CodeSet.objects.create(system="ICD-10-CM", version="synthetic-test", effective_from=timezone.localdate() - timedelta(days=1), effective_until=timezone.localdate() + timedelta(days=1), source_url="https://synthetic.invalid/codes", sha256="0" * 64)
        code = Code.objects.create(release=release, code="R00.0", description="Synthetic fixture; no clinical use")
        CodeSuggestion.objects.create(encounter=encounter, terminology=code, explanation="Synthetic documented code", evidence=encounter.notes, accepted_by=self.user, accepted_at=timezone.now())
        self.job.kind = "transcription"
        self.job.save(update_fields=["kind"])
        reserve(self.job, Decimal("0.2"))
        result = ("Correction: R00.0 was not applicable.", Decimal("0.125"), {}, {}, "synthetic-provider", "synthetic-transcription-correction", False)
        with patch("core.jobs.transcribe", return_value=result):
            run_one()
        self.job.refresh_from_db()
        self.assertEqual(self.job.state, "succeeded")
        self.assertFalse(CodeSuggestion.objects.filter(encounter=encounter, accepted_at__isnull=False).exists())
