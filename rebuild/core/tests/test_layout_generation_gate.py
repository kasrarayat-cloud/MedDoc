"""D10's charge-then-refuse (V1 B-W1, 'D10 charged before a refusal at finalization'), and where its gate may stand.

A contract v3 form whose tab-column answers need the isolated layout verifier can export NO answer while the verifier
is absent: `word_v3.fill` refuses every non-empty answer set when the original has a tab-column layout candidate, even
one answer in an unrelated text field (documents/word_v3.py fill: `layout_nodes and retained_layout is None and any
answer`), and `layout_transport.verify_document` then refuses with 'layout_unavailable'. The fresh inspection already
knows: it reports `layout_pending` and the verifier's refusal. So a NEW generation request is refused at ADMISSION —
`core.jobs.enqueue`, for the single request and the complete-form batch alike — before any hold and before any provider
call, and the encounter page says why.

⚠️ ADMISSION ONLY. The first version put this refusal inside `v3_mapping.generation_refusal`, which the worker, the batch
before EVERY part and the batch at adoption also call. A verifier outage after a send then discarded output already paid
for (batch failed, parts absorbed, no answers), where the base adopted the draft and let export ask the verifier again
(refutation L1:F1). After admission the layout never refuses or discards: the request runs as on the base, its cost is
the true cost, and finalization asks the verifier itself. Pinned below in both directions.

Synthetic only: python-docx forms with one tab-column row (the D10 shape) and ordinary text cells. The provider client
is patched; its call count is the evidence that nothing was sent.
"""
import io
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from core import v3_mapping
from core.models import (AuditEvent, Encounter, GenerationBatch, Job, LedgerEntry, PlatformCost, ProviderReceipt,
                         Reservation, TemplateVersion, Usage, Wallet)
from documents import layout_transport
from .test_v3_ordinary_notes import LIVE
from .test_word_v3_workflow import V3Fixture

NO_WITNESS = dict(QUILLMD_LAYOUT_SOCKET='', QUILLMD_LAYOUT_SERVICE_UID='')
#: Configured, and absent: the REAL verify_document lstat()s it, fails, and raises its own transient refusal.
ABSENT_WITNESS = dict(QUILLMD_LAYOUT_SOCKET='/run/synthetic-layout-absent.sock', QUILLMD_LAYOUT_SERVICE_UID='1000')
REAL_VERIFY = layout_transport.verify_document
TRANSIENT = 'The isolated layout verifier is unavailable or returned incomplete evidence.'
NOTES = 'Reason for visit: Right knee pain after a fall on the stairs.\n\nPlan: Physiotherapy referral and review in four weeks.'


def mixed_form(rows=None):
    """D10's shape in miniature: one tab-column row the verifier must measure, then ordinary answer cells."""
    from documents.test_question_boxes import TabColumnOwnership   # imported here: the runner would collect its tests
    labels = rows or ['Reason for visit', 'Plan']
    doc = TabColumnOwnership().form()
    doc.add_paragraph('Visit details')
    table = doc.add_table(rows=len(labels), cols=2)
    for i, label in enumerate(labels):
        table.cell(i, 0).text = label
    return _bytes(doc)


def _bytes(doc):
    out = io.BytesIO(); doc.save(out)
    return out.getvalue()


def ordinary_form():
    from docx import Document
    doc = Document()
    doc.add_paragraph('Visit details')
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = 'Reason for visit'
    table.cell(1, 0).text = 'Plan'
    return _bytes(doc)


def provider_reply(**wire):
    """A completed provider-shaped reply selecting, for each question, the source units that name its label."""
    payload = json.loads(wire['messages'][0]['content'])
    units = payload.get('source_units') or []
    body = {'fields': [{'key': q['key'], 'unit_ids': [u['id'] for u in units if q['label'].lower() in u['quote'].lower()],
                        'conflict': False} for q in payload.get('questions') or []]}
    return SimpleNamespace(id='msg_synthetic_gate', _request_id='req_synthetic_gate', stop_reason='end_turn',
                           usage=SimpleNamespace(input_tokens=1000, output_tokens=100, cache_read_input_tokens=0,
                                                 cache_creation_input_tokens=0),
                           content=[SimpleNamespace(type='text', text=json.dumps(body))],
                           model_dump=lambda **kwargs: {'id': 'msg_synthetic_gate'})


def money(user):
    return [(w.kind, w.balance, w.reserved) for w in Wallet.objects.filter(user=user).order_by('kind')]


def finalize(test, encounter):
    payload = {'revision': encounter.revision}
    for field in encounter.template_version.fields:
        payload['answer_' + field['key']] = (encounter.answers.get(field['key']) or {}).get('text', '')
        payload['reviewed_' + field['key']] = 'on'
    test.assertEqual(test.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
    encounter.refresh_from_db()
    final = test.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'},
                             follow=True)
    encounter.refresh_from_db()
    return encounter.status, [str(m) for m in final.context['messages']]


class Witness:
    """The layout verifier as the application meets it: verifying (synthetic), or down (the REAL verify_document against
    the configured settings, so its own refusal is what the code under test receives)."""

    def __init__(self):
        self.down = False
        self.outages = 0

    def __call__(self, raw, mapping=None, answers=None):
        from documents.test_layout_verification import synthetic_verified
        if self.down:
            self.outages += 1
            return REAL_VERIFY(raw, mapping, answers)
        return synthetic_verified(raw, mapping, answers)


@override_settings(**dict(LIVE, **NO_WITNESS))
class LayoutGenerationGate(V3Fixture, TestCase):

    def ready(self, original=None, name='SYNTHETIC tab-column visit'):
        template, version = self.uploaded(data=original or mixed_form(), name=name)
        version = self.confirm(template, version)
        self.assertEqual(self.new_encounter(version, notes=NOTES).status_code, 302)
        return template, version, Encounter.objects.latest('created_at')

    def charge_then_refuse(self, encounter, provider):
        """Only reached when a job was queued: complete the old path and report what it cost, as the failure."""
        from core.jobs import run_one
        held = list(Reservation.objects.filter(job__encounter=encounter).values_list('state', 'amount'))
        provider.return_value.messages.create.side_effect = provider_reply
        run_one()
        encounter.refresh_from_db()
        status, messages = finalize(self, encounter)
        return ('generation was queued: hold %s; provider calls %d; settled %s; charged %s; then finalization: %s -> %s'
                % (held, provider.return_value.messages.create.call_count,
                   list(Reservation.objects.filter(job__encounter=encounter).values_list('state', 'amount')),
                   list(Usage.objects.filter(job__encounter=encounter).values_list('charged_cost', flat=True)),
                   status, messages))

    def test_without_the_verifier_generation_is_refused_before_any_hold_or_provider_call(self):
        template, version, encounter = self.ready()
        self.assertEqual([f['label'] for f in version.fields], ['Reason for visit', 'Plan'])
        before = money(self.user)
        with patch('anthropic.Anthropic') as provider:
            page = self.client.get(f'/encounters/{encounter.pk}/')
            response = self.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': page.context['usage_quote']},
                                        follow=True)
            if Job.objects.filter(encounter=encounter).exists():
                self.fail(self.charge_then_refuse(encounter, provider))
            self.assertFalse(provider.called)
            self.assertFalse(provider.return_value.messages.create.called)
        self.assertEqual([str(m) for m in response.context['messages']], [v3_mapping.GENERATION_LAYOUT_REFUSAL])
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Usage.objects.exists())
        self.assertFalse(ProviderReceipt.objects.exists())
        self.assertEqual(money(self.user), before)
        self.assertFalse(LedgerEntry.objects.filter(job__isnull=False).exists())
        encounter.refresh_from_db()
        self.assertEqual((encounter.status, encounter.answers), ('draft', {}))

    def test_the_explanation_is_on_the_mapping_review_and_the_encounter_page_before_generation(self):
        template, version, encounter = self.ready()
        self.assertIn(layout_transport.LAYOUT_UNAVAILABLE, template.warnings)
        self.assertContains(self.client.get(f'/templates/{template.pk}/'), layout_transport.LAYOUT_UNAVAILABLE)
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertEqual(page.context['export_refusal'], layout_transport.LAYOUT_UNAVAILABLE)
        self.assertContains(page, 'data-export-refusal')
        self.assertContains(page, layout_transport.LAYOUT_UNAVAILABLE)

    def test_enqueue_refuses_before_any_job_or_hold_and_the_worker_gate_is_unchanged(self):
        from core.jobs import enqueue
        _, version, encounter = self.ready()
        with patch('anthropic.Anthropic') as provider:
            with self.assertRaisesMessage(v3_mapping.ValidationError, v3_mapping.GENERATION_LAYOUT_REFUSAL):
                enqueue(encounter, self.user)
            self.assertFalse(provider.called)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        # The admission gate is enqueue's; the gate the worker, the batch parts and adoption share answers as on the base.
        self.assertEqual(v3_mapping.admission_refusals(version), ('', v3_mapping.GENERATION_LAYOUT_REFUSAL))
        self.assertEqual(v3_mapping.generation_refusal(version), '')

    def test_a_typed_answer_is_refused_at_finalization_with_the_same_words_and_a_blank_export_is_the_original(self):
        template, version, encounter = self.ready()
        payload = {'revision': encounter.revision}
        for field in version.fields:
            payload['answer_' + field['key']] = 'Typed by the clinician.' if field['label'] == 'Plan' else ''
            payload['reviewed_' + field['key']] = 'on'
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
        encounter.refresh_from_db()
        final = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'},
                                 follow=True)
        self.assertIn(layout_transport.LAYOUT_UNAVAILABLE, [str(m) for m in final.context['messages']])
        encounter.refresh_from_db()
        self.assertEqual(encounter.status, 'review')

    def test_old_stored_wording_is_still_recognised_on_the_page(self):
        template, version, encounter = self.ready()
        template.warnings = [w if w != layout_transport.LAYOUT_UNAVAILABLE else layout_transport.LAYOUT_UNAVAILABLE_BEFORE
                             for w in template.warnings]
        template.save(update_fields=['warnings'])
        self.assertEqual(v3_mapping.export_refusal(template), layout_transport.LAYOUT_UNAVAILABLE)


@override_settings(**dict(LIVE, **ABSENT_WITNESS))
class LayoutGenerationGateControls(V3Fixture, TestCase):
    """Positive controls: the gate is the verifier's absence AT ADMISSION, never 'a form with tab columns', 'a v3 form',
    or an outage met after the request was admitted."""

    def setUp(self):
        super().setUp()
        self.witness = Witness()
        verifier = patch('documents.layout_transport.verify_document', side_effect=self.witness)
        self.verifier = verifier.start(); self.addCleanup(verifier.stop)

    def admitted(self, name):
        template, version = self.uploaded(data=mixed_form(), name=name)
        version = self.confirm(template, version)
        self.assertEqual(self.new_encounter(version, notes=NOTES).status_code, 302)
        return template, version, Encounter.objects.latest('created_at')

    def test_with_a_verifier_that_verifies_generation_is_admitted_and_charged_as_before(self):
        from core.jobs import enqueue, run_one
        template, version = self.uploaded(data=mixed_form(), name='SYNTHETIC verified tab-column visit')
        self.assertTrue(any(f.get('layout_candidate') for f in version.fields))
        self.assertFalse([w for w in template.warnings if 'layout verifier' in w])
        version = self.confirm(template, version)
        self.assertEqual(self.new_encounter(version, notes=NOTES).status_code, 302)
        encounter = Encounter.objects.latest('created_at')
        self.assertEqual(v3_mapping.generation_refusal(version), '')
        self.assertEqual(v3_mapping.admission_refusals(version), ('', ''))
        self.assertEqual(v3_mapping.export_refusal(template), '')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = provider_reply
            job = enqueue(encounter, self.user)
            self.assertTrue(run_one())
            self.assertEqual(provider.return_value.messages.create.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')
        self.assertTrue(Usage.objects.get(job=job).charged_cost > 0)

    def test_a_cost_after_a_real_provider_call_is_kept_when_finalization_later_fails(self):
        """The gate is before the hold; it never erases a charge. Verifier present at generation, gone at finalization."""
        from core.jobs import enqueue, run_one
        template, version, encounter = self.admitted('SYNTHETIC verifier lost later')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = provider_reply
            job = enqueue(encounter, self.user)
            self.assertTrue(run_one())
        charged = Usage.objects.get(job=job).charged_cost
        self.assertTrue(charged > 0)
        encounter.refresh_from_db()
        payload = {'revision': encounter.revision}
        for field in version.fields:
            payload['answer_' + field['key']] = (encounter.answers.get(field['key']) or {}).get('text', '')
            payload['reviewed_' + field['key']] = 'on'
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
        encounter.refresh_from_db()
        # The verifier is gone by finalization: its own refusal, raised by the real verify_document.
        self.witness.down = True
        with override_settings(**NO_WITNESS):
            final = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'},
                                     follow=True)
        self.assertIn(layout_transport.LAYOUT_UNAVAILABLE, [str(m) for m in final.context['messages']])
        self.assertEqual(Usage.objects.get(job=job).charged_cost, charged)
        self.assertEqual(list(Reservation.objects.filter(job=job).values_list('state', flat=True)), ['settled'])

    def test_a_verifier_that_does_not_verify_now_refuses_generation_before_the_hold(self):
        from core.jobs import enqueue
        from documents.service import DocumentError
        template, version, encounter = self.admitted('SYNTHETIC unresolved now')
        self.verifier.side_effect = DocumentError('The rendered form does not establish these tab-column answer '
                                                  'destinations. Review the original.', 'layout_unresolved')
        with patch('anthropic.Anthropic') as provider:
            with self.assertRaisesMessage(v3_mapping.ValidationError, v3_mapping.GENERATION_LAYOUT_REFUSAL):
                enqueue(encounter, self.user)
            self.assertFalse(provider.called)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())

    def test_an_outage_at_the_worker_runs_the_admitted_request_as_before(self):
        """L1:F2's shape: admitted while the verifier verified, down when the worker re-checks the original, back for
        finalization. The worker never re-applies the admission gate: one provider call, the true cost, the draft kept,
        and export succeeds once the verifier answers (as on the base)."""
        from core.jobs import enqueue, run_one
        template, version, encounter = self.admitted('SYNTHETIC worker outage')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = provider_reply
            job = enqueue(encounter, self.user)
            self.witness.down = True
            self.assertTrue(run_one())
            self.witness.down = False
            self.assertEqual(provider.return_value.messages.create.call_count, 1)
        self.assertTrue(self.witness.outages >= 1, 'the outage must have been met by the worker')
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), ('succeeded', ''))
        self.assertTrue(Usage.objects.get(job=job).charged_cost > 0)
        encounter.refresh_from_db()
        self.assertEqual(finalize(self, encounter)[0], 'finalized')


@override_settings(**dict(LIVE, **ABSENT_WITNESS, V3_GENERATION_BATCHES=True, V3_HISTORY_CONTEXT=False))
class LayoutGateOnTheCompleteFormBatch(V3Fixture, TestCase):
    """L1:F1: above 100 answerable fields the request is a complete-form batch (two parts here). The batch re-checks the
    original before EVERY part and once more at adoption (core.batch_jobs.current_plan / finish), so an admission-only
    refusal must not live in that shared check."""

    def setUp(self):
        super().setUp()
        from .test_generation_batch import manifest
        deny = patch('socket.socket.connect', side_effect=AssertionError('Network denied')); deny.start()
        self.addCleanup(deny.stop)
        self.witness = Witness()
        verifier = patch('documents.layout_transport.verify_document', side_effect=self.witness)
        verifier.start(); self.addCleanup(verifier.stop)
        self.template, first = self.uploaded(data=mixed_form(['Question %03d' % (i + 1) for i in range(101)]),
                                             name='SYNTHETIC tab-column batch')
        self.version = TemplateVersion.objects.create(template=self.template, number=2, fields=first.fields, contract='v3',
            generation_constraints=manifest(first.fields, self.template.sha256), created_by=self.user)
        self.confirm(self.template, self.version)
        self.assertEqual(len(self.version.fields), 102)
        self.assertEqual([f['label'] for f in self.version.fields if f.get('layout_candidate')], ['Finding'])
        notes = '\n'.join(f"{f['label']}: documented {i:03d}." for i, f in enumerate(self.version.fields)
                          if not f.get('layout_candidate'))
        self.assertEqual(self.new_encounter(self.version, notes).status_code, 302)
        self.encounter = Encounter.objects.latest('created_at')

    def provider(self, calls):
        from .test_generation_batch import response

        def call(**kw):
            calls.append(kw)
            batch = GenerationBatch.objects.get(encounter=self.encounter)
            raw = response(batch.plan, len(calls))
            reply = SimpleNamespace(**{k: v for k, v in raw.items() if k not in ('content', 'usage')},
                                    content=[SimpleNamespace(**c) for c in raw['content']],
                                    usage=SimpleNamespace(**raw['usage']), _request_id='request_' + str(uuid.uuid4()))
            reply.model_dump = lambda **_kw: raw
            return reply
        return call

    def admit(self, page=None):
        page = page or self.client.get(f'/encounters/{self.encounter.pk}/')
        response = self.client.post(f'/encounters/{self.encounter.pk}/generate/',
                                    {'revision': self.encounter.revision, 'usage_quote': page.context['usage_quote']},
                                    follow=True)
        return page, [str(m) for m in response.context['messages']]

    def work(self, down_at=()):
        """Run the worker step by step; the verifier is down for exactly the steps named (1, 2: the parts; 3: adoption)."""
        from core import jobs
        calls = []
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = self.provider(calls)
            for step in range(1, 5):
                self.witness.down = step in down_at
                worked = jobs.run_one()
                self.witness.down = False
                if not worked:
                    break
        self.encounter.refresh_from_db()
        return GenerationBatch.objects.get(encounter=self.encounter), len(calls)

    def assert_adopted(self, batch, calls):
        self.assertEqual((batch.state, batch.error), ('succeeded', ''),
                         list(batch.parts.values_list('ordinal', 'job__state', 'job__error')))
        self.assertEqual(calls, 2)
        self.assertEqual((self.encounter.status, len(self.encounter.answers)), ('review', 102))
        self.assertEqual(list(batch.parts.order_by('ordinal').values_list('job__state', flat=True)), ['succeeded'] * 2)
        self.assertFalse(PlatformCost.objects.filter(job__encounter=self.encounter).exists())
        self.assertEqual(Usage.objects.filter(job__encounter=self.encounter, charged_cost__gt=0).count(), 2)

    def test_an_outage_before_the_second_part_neither_refuses_nor_discards_the_paid_first_part(self):
        self.assertEqual(self.admit()[1], ['Generation queued. Refresh this page to view the result.'])
        batch, calls = self.work(down_at=(2,))
        self.assertTrue(self.witness.outages >= 1, 'the outage must have been met before the second part')
        self.assert_adopted(batch, calls)

    def test_an_outage_at_adoption_keeps_the_complete_paid_draft_and_export_asks_the_verifier_itself(self):
        self.assertEqual(self.admit()[1], ['Generation queued. Refresh this page to view the result.'])
        batch, calls = self.work(down_at=(3,))
        self.assertTrue(self.witness.outages >= 1, 'the outage must have been met at adoption')
        self.assert_adopted(batch, calls)
        status, messages = finalize(self, self.encounter)
        self.assertEqual(status, 'finalized', messages)
        self.assertTrue(self.encounter.export_sha256)

    def test_a_batch_admission_without_the_verifier_is_refused_whole_before_any_hold(self):
        for settings, wording in ((ABSENT_WITNESS, TRANSIENT), (NO_WITNESS, layout_transport.LAYOUT_UNAVAILABLE)):
            with self.subTest(wording=wording), override_settings(**settings):
                before = money(self.user)
                page = self.client.get(f'/encounters/{self.encounter.pk}/')
                self.witness.down, self.witness.outages = True, 0
                with patch('anthropic.Anthropic') as provider:
                    _, messages = self.admit(page)
                    self.assertFalse(provider.called)
                self.witness.down = False
                self.assertTrue(self.witness.outages >= 1)
                self.assertEqual(messages, [v3_mapping.GENERATION_LAYOUT_REFUSAL])
                self.assertFalse(GenerationBatch.objects.exists())
                self.assertFalse(Job.objects.exists())
                self.assertFalse(Reservation.objects.exists())
                self.assertEqual(money(self.user), before)
                # Page views audit themselves; what must not survive is any record of an admission or a hold.
                self.assertFalse(AuditEvent.objects.filter(
                    action__in=['generation_batch.admitted', 'usage.reserve', 'job.queued']).exists())

    def test_a_replayed_admission_during_an_outage_is_answered_as_the_admitted_batch(self):
        page, messages = self.admit()
        self.assertEqual(messages, ['Generation queued. Refresh this page to view the result.'])
        held = list(Reservation.objects.order_by('created_at').values_list('state', 'amount'))
        self.witness.down = True
        with patch('anthropic.Anthropic') as provider:
            _, again = self.admit(page)
            self.assertFalse(provider.called)
        self.witness.down = False
        self.assertNotIn(v3_mapping.GENERATION_LAYOUT_REFUSAL, again)
        self.assertEqual(GenerationBatch.objects.count(), 1)
        self.assertEqual(list(Reservation.objects.order_by('created_at').values_list('state', 'amount')), held)
        self.assert_adopted(*self.work())


@override_settings(**dict(LIVE, **NO_WITNESS))
class OrdinaryFormIsNotGated(V3Fixture, TestCase):
    def test_a_v3_form_with_no_tab_column_answer_generates_without_the_verifier(self):
        from core.jobs import enqueue, run_one
        template, version = self.uploaded(data=ordinary_form(), name='SYNTHETIC ordinary visit')
        self.assertFalse([w for w in template.warnings if 'layout verifier' in w])
        version = self.confirm(template, version)
        self.assertEqual(self.new_encounter(version, notes=NOTES).status_code, 302)
        encounter = Encounter.objects.latest('created_at')
        self.assertEqual(v3_mapping.generation_refusal(version), '')
        self.assertEqual(v3_mapping.admission_refusals(version), ('', ''))
        self.assertEqual(v3_mapping.export_refusal(template), '')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = provider_reply
            job = enqueue(encounter, self.user)
            self.assertTrue(run_one())
            self.assertEqual(provider.return_value.messages.create.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, 'succeeded')
