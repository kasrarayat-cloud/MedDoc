"""D10's charge-then-refuse (V1 B-W1, 'D10 charged before a refusal at finalization'), and where its gate may stand.

A contract v3 form whose tab-column answers need the isolated layout verifier can export NO answer while the verifier
is absent: `word_v3.fill` refuses every non-empty answer set when the original has a tab-column layout candidate, even
one answer in an unrelated text field (documents/word_v3.py fill: `layout_nodes and retained_layout is None and any
answer`), and `layout_transport.verify_document` then refuses with 'layout_unavailable'. So a NEW generation request is
refused at ADMISSION — `core.jobs.enqueue`, for the single request and the complete-form batch alike — before any hold
and before any provider call, and its refusal says why.

⚠️ THE GATE IS FILL'S OWN ANSWER, NOT THE INSPECTION'S COUNT (refutation FV:F1). The inspection counts tab-column
candidates without fill's reader; fill's reader (proposal mode) withdraws a candidate whose complete question or section
passes the mapping limit, and that form exports with NO verifier — while the verifier's own preparer refuses it, so a
configured verifier never helps. Admission refused such forms permanently. It now asks the export path itself
(v3_mapping.export_needs_verifier) whenever the fresh inspection counted a tab-column candidate, and refuses only when
export refuses for want of the verifier. That includes an inspection the verifier VERIFIED (refutation L1:RF1:F1): it
carries the verifier's receipt instead of `layout_pending`, and the verifier can still refuse every export of the stored
mapping (a renamed tab-column question, receipts from an earlier renderer profile). For the same reason (FV:F1) the
encounter page no longer explains the layout from the stored note (it cannot tell the two apart), and the
inspection-time note keeps the base wording.

⚠️ ADMISSION ONLY. The first version put this refusal inside `v3_mapping.generation_refusal`, which the worker, the batch
before EVERY part and the batch at adoption also call. A verifier outage after a send then discarded output already paid
for (batch failed, parts absorbed, no answers), where the base adopted the draft and let export ask the verifier again
(refutation L1:F1). After admission the layout never refuses or discards: the request runs as on the base, its cost is
the true cost, and finalization asks the verifier itself. Pinned below in both directions.

Synthetic only: python-docx forms with one tab-column row (the D10 shape) and ordinary text cells, and the two over-limit
shapes of FV:F1. The provider client is patched; its call count is the evidence that nothing was sent.
"""
import hashlib
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

    def test_the_mapping_review_keeps_the_base_note_and_the_refusal_at_generate_is_the_explanation(self):
        """The inspection that writes the upload note does not know whether fill will refuse (FV:F1), so the note claims
        nothing about the other answers and the encounter page states nothing from it (both as on the base). The
        precise words come from fill's own answer: at Generate, and at finalization of a typed answer (below)."""
        template, version, encounter = self.ready()
        self.assertIn(layout_transport.LAYOUT_NEEDED, template.warnings)
        self.assertNotIn(layout_transport.LAYOUT_UNAVAILABLE, template.warnings)
        self.assertContains(self.client.get(f'/templates/{template.pk}/'), layout_transport.LAYOUT_NEEDED)
        page = self.client.get(f'/encounters/{encounter.pk}/')
        self.assertEqual(page.context['export_refusal'], '')
        self.assertNotContains(page, 'data-export-refusal')
        response = self.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': page.context['usage_quote']},
                                    follow=True)
        self.assertEqual([str(m) for m in response.context['messages']], [v3_mapping.GENERATION_LAYOUT_REFUSAL])

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

    def test_no_stored_layout_note_becomes_a_page_explanation(self):
        """Either wording a layout note was ever stored with (base and 7e454096 uploads) explains nothing on the page."""
        template, version, encounter = self.ready()
        for note in (layout_transport.LAYOUT_NEEDED, layout_transport.LAYOUT_UNAVAILABLE):
            with self.subTest(note=note):
                template.warnings = [w for w in template.warnings if 'layout verifier' not in w] + [note]
                template.save(update_fields=['warnings'])
                self.assertEqual(v3_mapping.export_refusal(template), '')

    def test_a_probe_that_cannot_answer_refuses_as_an_unverifiable_original_before_any_job_or_hold(self):
        """Fail closed: when the inspection reports a tab-column candidate and the export probe is refused for any
        reason other than the verifier's, fill's answer is unknown, so the request is refused — never admitted on a
        guess — and only as a new request (after the replay answer), like the layout refusal."""
        from core.jobs import enqueue
        from documents.service import DocumentError
        _, version, encounter = self.ready()
        with patch('documents.fill_template', side_effect=DocumentError('Document processing exceeded its time limit.',
                                                                        'parser_timeout')) as probe, \
                patch('anthropic.Anthropic') as provider:
            self.assertEqual(v3_mapping.admission_refusals(version), ('', v3_mapping.GENERATION_SOURCE_REFUSAL))
            with self.assertRaisesMessage(v3_mapping.ValidationError, v3_mapping.GENERATION_SOURCE_REFUSAL):
                enqueue(encounter, self.user)
            self.assertFalse(provider.called)
            self.assertTrue(probe.called)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        # A mapping the probe cannot run on (no contract v3 field) is the same unknown.
        version.fields = []
        self.assertEqual(v3_mapping.export_needs_verifier(version), v3_mapping.GENERATION_SOURCE_REFUSAL)


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


# ─── FV:F1 (extends L2:F1): admission must ask fill's own question, not the inspection's ─────────────────────────────
#: The two over-limit shapes of the final verification (flow-implement-final/harness test_vf_l2.form(989) and
#: test_fv_verifier.dup_form(850)). The inspection counts their tab-column row as a layout candidate, but fill's reader
#: (word_v3.Detector in proposal mode) withdraws it — its complete question or section exceeds the 1000-character mapping
#: limit once the side heading or the duplicate occurrence is added — so fill finds no layout node and exports WITHOUT any
#: verifier, as on the base. The verifier's own preparer (layout_source.prepare, proposal mode) refuses the same shapes
#: ('No bounded tab-column proposal is available.'), so a configured, answering verifier never verifies them either.
FILLER = 'Tenderness along the medial joint line on palpation with effusion; '
CLINICIAN_NOTES = 'Clinician name: Jane Example.'
#: What the REAL transport (layout_transport.verify_document) raises when the verifier answered 'not verified'.
UNRESOLVED = 'The rendered form does not establish these tab-column answer destinations. Review the original.'


def _text_of(n):
    text = (FILLER * 40)[:n]
    return text[:-1] + 'x' if text.endswith(' ') else text


def _tab_cell(doc, title, label):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    cell = doc.add_table(rows=1, cols=2).cell(0, 0)
    cell.text = title
    header = cell.add_paragraph('\tPresent\tAbsent')
    row = cell.add_paragraph(label)
    for i in range(2):
        row.add_run('\t' + str(5 - i) + ' '); row.add_run('☐')
    for paragraph in (header, row):
        tabs = OxmlElement('w:tabs')
        for i in range(2):
            tab = OxmlElement('w:tab'); tab.set(qn('w:val'), 'center'); tab.set(qn('w:pos'), str(2000 + i * 1000))
            tabs.append(tab)
        paragraph._p.get_or_add_pPr().append(tabs)


def long_row_label_form(chars=989):
    """'Clinician name' + a 'Left knee' heading + one tab-column row whose own label is `chars` long (989 passes the
    source limit; the side heading pushes it past the mapping limit in fill's reader)."""
    from docx import Document
    doc = Document()
    doc.add_paragraph('Clinician name: ______________________')
    doc.add_paragraph('Left knee', style='Heading 2')
    _tab_cell(doc, 'Knee examination', _text_of(chars))
    return _bytes(doc)


def duplicate_long_titles_form(chars=850):
    """'Clinician name' + two identical tab-column tables with `chars`-long titles (the duplicate's occurrence context
    pushes each past the mapping limit in fill's reader)."""
    from docx import Document
    doc = Document()
    doc.add_paragraph('Clinician name: ______________________')
    doc.add_paragraph('Knee findings', style='Heading 2')
    for _ in range(2):
        _tab_cell(doc, _text_of(chars), 'Effusion')
    return _bytes(doc)


OVER_LIMIT_SHAPES = (('989-character row label', long_row_label_form), ('two identical 850-character titles',
                                                                          duplicate_long_titles_form))


class AnsweringVerifier:
    """A configured layout verifier that ANSWERS: it runs the real first step of documents.layout_server.qualify (the
    isolated preparer, documents.layout_source.prepare) and reports 'not verified' exactly as the real transport does
    when that step refuses. It never renders: a form it would have to render is outside these tests (asserted)."""

    def __init__(self):
        self.calls = []

    def __call__(self, raw, mapping=None, answers=None):
        from documents import layout_source, word_v3
        from documents.service import DocumentError
        self.calls.append('inspection' if mapping is None else 'export')
        try:
            layout_source.prepare(raw, mapping=mapping, answers=answers)
        except word_v3.V3Failure:
            raise DocumentError(UNRESOLVED, 'layout_unresolved') from None
        raise AssertionError('the preparer accepted this form; a render would be needed')


class OverLimitShapes:
    """The walk: upload -> confirm -> notes -> Generate -> worker -> review -> finalize -> download."""

    @staticmethod
    def reply(**wire):
        """provider_reply under a fresh provider message id: two walks in one test are two provider responses."""
        reply = provider_reply(**wire)
        reply.id, reply._request_id = 'msg_' + uuid.uuid4().hex, 'req_' + uuid.uuid4().hex
        reply.model_dump = lambda **kwargs: {'id': reply.id}
        return reply

    def walk(self, name, original):
        from core.jobs import run_one
        template, version = self.uploaded(data=original, name='SYNTHETIC over-limit ' + name)
        # Fill's reader withdraws the row; the clinician's text field is the form's one answer.
        self.assertEqual([f['label'] for f in version.fields], ['Clinician name'])
        version = self.confirm(template, version)
        self.assertEqual(self.new_encounter(version, notes=CLINICIAN_NOTES).status_code, 302)
        encounter = Encounter.objects.latest('created_at')
        self.assertEqual(v3_mapping.admission_refusals(version), ('', ''))
        page = self.client.get(f'/encounters/{encounter.pk}/')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = self.reply
            response = self.client.post(f'/encounters/{encounter.pk}/generate/',
                                        {'revision': encounter.revision, 'usage_quote': page.context['usage_quote']},
                                        follow=True)
            self.assertEqual([str(m) for m in response.context['messages']],
                             ['Generation queued. Refresh this page to view the result.'])
            self.assertTrue(run_one())
            self.assertEqual(provider.return_value.messages.create.call_count, 1)
        job = Job.objects.get(encounter=encounter)
        self.assertEqual((job.state, job.error), ('succeeded', ''))
        self.assertTrue(Usage.objects.get(job=job).charged_cost > 0)
        encounter.refresh_from_db()
        self.assertEqual([v.get('text') for v in encounter.answers.values()], ['Jane Example.'])
        status, messages = finalize(self, encounter)
        self.assertEqual(status, 'finalized', messages)
        download = self.client.get(f'/encounters/{encounter.pk}/export/')
        self.assertEqual(download.status_code, 200)
        import hashlib
        import zipfile
        raw = b''.join(download.streaming_content)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), encounter.export_sha256)
        self.assertIn(b'Jane Example', zipfile.ZipFile(io.BytesIO(raw)).read('word/document.xml'))
        return template, encounter


@override_settings(**dict(LIVE, **NO_WITNESS))
class OverLimitShapesWithoutTheVerifier(OverLimitShapes, V3Fixture, TestCase):
    """FV:F1 (a): no verifier configured. 7e454096 refused Generate (0 provider calls) while a typed answer exported."""

    def setUp(self):
        super().setUp()
        deny = patch('socket.socket.connect', side_effect=AssertionError('Network denied')); deny.start()
        self.addCleanup(deny.stop)

    def test_the_over_limit_shapes_generate_and_export_as_on_the_base(self):
        for name, build in OVER_LIMIT_SHAPES:
            with self.subTest(shape=name):
                self.walk(name, build())

    def test_the_page_does_not_say_that_no_answer_can_be_exported(self):
        """The encounter page reads stored notes only; it cannot tell these shapes from D10's, so it states neither (the
        base page). The refusal at Generate is what explains D10 (computed from fill's own question)."""
        for name, build in OVER_LIMIT_SHAPES:
            with self.subTest(shape=name):
                template, version = self.uploaded(data=build(), name='SYNTHETIC over-limit page ' + name)
                self.assertFalse([w for w in template.warnings if 'no answer on this form can be exported' in w])
                version = self.confirm(template, version)
                self.assertEqual(self.new_encounter(version, notes=CLINICIAN_NOTES).status_code, 302)
                page = self.client.get(f"/encounters/{Encounter.objects.latest('created_at').pk}/")
                self.assertEqual(page.context['export_refusal'], '')
                self.assertNotContains(page, 'data-export-refusal')


@override_settings(**dict(LIVE, **ABSENT_WITNESS))
class OverLimitShapesWithAnAnsweringVerifier(OverLimitShapes, V3Fixture, TestCase):
    """FV:F1 (b): a configured verifier that answers. It refuses these shapes at its first step, so on 7e454096 the
    refusal was permanent in every deployment; fill never asks it for them."""

    def setUp(self):
        super().setUp()
        deny = patch('socket.socket.connect', side_effect=AssertionError('Network denied')); deny.start()
        self.addCleanup(deny.stop)
        self.verifier = AnsweringVerifier()
        verifier = patch('documents.layout_transport.verify_document', side_effect=self.verifier)
        verifier.start(); self.addCleanup(verifier.stop)

    def test_the_over_limit_shapes_generate_and_export_and_export_never_asks_the_verifier(self):
        for name, build in OVER_LIMIT_SHAPES:
            with self.subTest(shape=name):
                self.verifier.calls.clear()
                self.walk(name, build())
                self.assertIn('inspection', self.verifier.calls)
                self.assertNotIn('export', self.verifier.calls)

    def test_d10s_shape_is_still_refused_when_the_answering_verifier_does_not_verify_it(self):
        """Positive control: D10's miniature under a configured verifier that answers 'not verified'. Its preparer
        ACCEPTS this form (a render would follow), so the witness here is the transport's own 'not verified' answer to
        every request, from upload on."""
        from core.jobs import enqueue
        from documents.service import DocumentError
        unresolved = DocumentError(UNRESOLVED, 'layout_unresolved')
        with patch('documents.layout_transport.verify_document', side_effect=unresolved) as verifier:
            template, version = self.uploaded(data=mixed_form(), name='SYNTHETIC D10 miniature, verifier unresolved')
            version = self.confirm(template, version)
            self.assertEqual(self.new_encounter(version, notes=NOTES).status_code, 302)
            encounter = Encounter.objects.latest('created_at')
            with patch('anthropic.Anthropic') as provider:
                with self.assertRaisesMessage(v3_mapping.ValidationError, v3_mapping.GENERATION_LAYOUT_REFUSAL):
                    enqueue(encounter, self.user)
                self.assertFalse(provider.called)
            self.assertTrue(verifier.called)
        self.assertFalse(Job.objects.exists())
        self.assertFalse(Reservation.objects.exists())


# ─── L1:RF1:F1: a verified INSPECTION is not a verified EXPORT ────────────────────────────────────────────────────────
#: documents.service replaces an inspection the verifier verified with the verifier's own answer: `layout_pending` is
#: gone and its `layout_receipt` is the only sign that the inspection counted a tab-column candidate. The verifier can
#: still refuse EVERY export of the stored mapping: a tab-column question renamed on the mapping page (its preparer:
#: 'A tab-column mapping changed; verify its complete source again.', mapping_mismatch) or field receipts from an earlier
#: renderer profile (its receipt check: 'Missing, changed or stale source/profile receipt'). 54d1bf6c asked fill only on
#: `layout_pending`, so these were admitted, held, sent and charged, then refused at finalization.
RENDERER_LATER = 'sha256:' + hashlib.sha256(b'SYNTHETIC: a later renderer image').hexdigest()


def stub_render(workspace):
    """Stands in for documents.layout_server.render (docker + LibreOffice): the five bounded files it must produce."""
    out = workspace / 'rendered'
    out.mkdir(mode=0o700)
    for name, body in (('document.pdf', b'%PDF-1.4 synthetic\n'), ('instrumented.pdf', b'%PDF-1.4 synthetic\n'),
                       ('fonts.sha256', b'1' * 64 + b'  /usr/share/fonts/synthetic.ttf\n'),
                       ('font-families.txt', b'Synthetic\n'), ('font-resolution.txt', b'sans-serif\tSynthetic\n')):
        (out / name).write_bytes(body)
    return out


class RenderlessVerifier:
    """The REAL documents.layout_server.qualify — the isolated preparer (worker.py layout_prepare), the renderer profile,
    the receipts and the receipt check — with only the renderer (docker + LibreOffice) and the rendered-PDF proof replaced
    (the proof passes and holds nothing). Its answer reaches the application as the real transport hands it over: any
    refusal is the transport's 'not verified' (layout_unresolved); a verified answer is (response, document)."""

    def __init__(self, test):
        import tempfile
        from pathlib import Path
        directory = tempfile.TemporaryDirectory(prefix='quillmd-layout-evidence-')
        test.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.calls = []

    def __call__(self, raw, mapping=None, answers=None):
        import base64
        from documents import layout_server
        from documents.service import DocumentError
        real_worker = layout_server.worker

        def worker(workspace, name):
            return {'passed': True, 'held': []} if name == 'layout_pdf_worker.py' else real_worker(workspace, name)
        request = {'source': base64.b64encode(raw).decode(), 'mapping': mapping, 'answers': answers}
        mode = 'inspection' if mapping is None else 'export'
        with patch.object(layout_server, 'render', stub_render), patch.object(layout_server, 'worker', worker):
            try:
                response = layout_server.qualify(request, self.root)
            except Exception:
                self.calls.append((mode, sorted(answers or {}), 'not verified'))
                raise DocumentError(UNRESOLVED, 'layout_unresolved') from None
        self.calls.append((mode, sorted(answers or {}), 'verified'))
        return response, base64.b64decode(response['document'])


@override_settings(**dict(LIVE, **ABSENT_WITNESS))
class AVerifiedInspectionIsNotAVerifiedExport(V3Fixture, TestCase):
    """L1:RF1:F1. D10's miniature under a verifier that VERIFIES the fresh inspection and refuses the stored mapping's
    export. Admission must ask fill (and so the verifier, for the export) here too, and refuse before any hold."""

    def setUp(self):
        super().setUp()
        deny = patch('socket.socket.connect', side_effect=AssertionError('Network denied')); deny.start()
        self.addCleanup(deny.stop)
        self.verifier = RenderlessVerifier(self)
        verifier = patch('documents.layout_transport.verify_document', side_effect=self.verifier)
        verifier.start(); self.addCleanup(verifier.stop)

    def ready(self, variant):
        from core.security import private_path
        from documents import inspect_template, layout_server
        template, version = self.uploaded(data=mixed_form(), name='SYNTHETIC verified inspection ' + variant)
        self.assertEqual([(f['label'], bool(f.get('layout_verified'))) for f in version.fields],
                         [('Finding', True), ('Reason for visit', False), ('Plan', False)])
        if variant == 'renamed':
            post = {'action': 'v3_save', 'mapping_version': version.pk}
            for field in version.fields:
                post['label_' + field['key']] = field['label'] + (' (knee)' if field.get('layout_candidate') else '')
                post['kind_' + field['key']] = field['kind']
            self.assertEqual(self.client.post(f'/templates/{template.pk}/', post).status_code, 302)
            version = self.latest(template)
            self.assertEqual([f['label'] for f in version.fields], ['Finding (knee)', 'Reason for visit', 'Plan'])
        version = self.confirm(template, version)
        if variant == 'profile':
            later = patch.object(layout_server, 'IMAGE', RENDERER_LATER); later.start(); self.addCleanup(later.stop)
        self.assertEqual(self.new_encounter(version, notes=NOTES).status_code, 302)
        encounter = Encounter.objects.latest('created_at')
        # The fresh inspection admission reads is VERIFIED: no `layout_pending`, the verifier's receipt instead.
        fresh = inspect_template(private_path(template.original_path), engine='v3')
        self.assertEqual((fresh.get('layout_pending'), 'layout_receipt' in fresh), (None, True))
        return template, version, encounter

    def refused_at_generate(self, variant):
        template, version, encounter = self.ready(variant)
        before = money(self.user)
        self.verifier.calls.clear()
        with patch('anthropic.Anthropic') as provider:
            page = self.client.get(f'/encounters/{encounter.pk}/')
            response = self.client.post(f'/encounters/{encounter.pk}/generate/',
                                        {'revision': encounter.revision, 'usage_quote': page.context['usage_quote']},
                                        follow=True)
            if Job.objects.filter(encounter=encounter).exists():
                self.fail(LayoutGenerationGate.charge_then_refuse(self, encounter, provider))
            self.assertFalse(provider.called)
        self.assertEqual([str(m) for m in response.context['messages']], [v3_mapping.GENERATION_LAYOUT_REFUSAL])
        # Admission asked the verifier for the export (fill's gate fired on the probe) and it refused.
        self.assertIn(('export', [v3_mapping.LAYOUT_PROBE_KEY], 'not verified'), self.verifier.calls)
        self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Usage.objects.exists())
        self.assertFalse(ProviderReceipt.objects.exists())
        self.assertFalse(LedgerEntry.objects.filter(job__isnull=False).exists())
        self.assertEqual(money(self.user), before)
        self.assertEqual(v3_mapping.admission_refusals(version), ('', v3_mapping.GENERATION_LAYOUT_REFUSAL))
        self.assertEqual(v3_mapping.generation_refusal(version), '')
        # The refusal's words are true: one typed answer in an ordinary text field is refused at export by the verifier.
        encounter.refresh_from_db()
        payload = {'revision': encounter.revision}
        for field in version.fields:
            payload['answer_' + field['key']] = 'Typed by the clinician.' if field['label'] == 'Plan' else ''
            payload['reviewed_' + field['key']] = 'on'
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
        encounter.refresh_from_db()
        final = self.client.post(f'/encounters/{encounter.pk}/finalize/', {'revision': encounter.revision, 'reviewed': 'on'},
                                 follow=True)
        self.assertIn(UNRESOLVED, [str(m) for m in final.context['messages']])
        encounter.refresh_from_db()
        self.assertEqual(encounter.status, 'review')

    def test_a_renamed_tab_column_question_is_refused_before_any_hold_or_provider_call(self):
        self.refused_at_generate('renamed')

    def test_receipts_from_an_earlier_renderer_profile_are_refused_before_any_hold_or_provider_call(self):
        self.refused_at_generate('profile')

    def test_positive_control_the_verified_mapping_is_admitted_charged_and_exported(self):
        """The same form, mapping and renderer as uploaded: the verifier verifies the export, so admission admits it."""
        import zipfile
        from core.jobs import run_one
        template, version, encounter = self.ready('control')
        self.assertEqual(v3_mapping.export_needs_verifier(version), '')
        self.assertIn(('export', [v3_mapping.LAYOUT_PROBE_KEY], 'verified'), self.verifier.calls)
        page = self.client.get(f'/encounters/{encounter.pk}/')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect = provider_reply
            response = self.client.post(f'/encounters/{encounter.pk}/generate/',
                                        {'revision': encounter.revision, 'usage_quote': page.context['usage_quote']},
                                        follow=True)
            self.assertEqual([str(m) for m in response.context['messages']],
                             ['Generation queued. Refresh this page to view the result.'])
            self.assertTrue(run_one())
            self.assertEqual(provider.return_value.messages.create.call_count, 1)
        job = Job.objects.get(encounter=encounter)
        self.assertEqual((job.state, job.error), ('succeeded', ''))
        self.assertTrue(Usage.objects.get(job=job).charged_cost > 0)
        encounter.refresh_from_db()
        status, messages = finalize(self, encounter)
        self.assertEqual(status, 'finalized', messages)
        download = self.client.get(f'/encounters/{encounter.pk}/export/')
        self.assertEqual(download.status_code, 200)
        xml = zipfile.ZipFile(io.BytesIO(b''.join(download.streaming_content))).read('word/document.xml')
        written = [v['text'] for v in encounter.answers.values() if (v or {}).get('text')]
        self.assertTrue(written)
        for text in written:
            self.assertIn(text.split('\n')[0].encode(), xml)
