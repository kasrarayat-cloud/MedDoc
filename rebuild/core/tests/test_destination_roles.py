"""Destination authority through the clinical workflow: whether a place may receive an answer at all.

A model never creates permission to write a signature, perform an attestation or change an identity field; the
permission comes from the ORIGINAL's structure (core.destination_roles). Synthetic blank forms only; every provider is
mocked and no request leaves the process. RF../PC.. ids are the destination-authority matrix's red-first exploits and
positive controls (v1-product-20260930 a1 mapping-matrix redfirst.json).
"""
import copy
import io
import itertools
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from core import destination_roles, generation, mapping_assistance as mapping, v3_mapping
from core.jobs import enqueue, run_one
from core.models import Encounter, MappingConfirmation, Template, TemplateVersion
from core.security import private_path
from core.tests.test_mapping_assistance import SETTINGS as MAPPING_SETTINGS
from core.tests.test_word_v3_workflow import V3, V3Fixture, part_text
from core.tests.test_workflow import TEST_SETTINGS
from documents import DocumentError, fill_template, word_v3

BODY = 'word/document.xml#'
LIVE = {'AI_MODE': 'live', 'AI_PROVIDER': 'anthropic', 'AI_MODEL': 'claude-sonnet-4-6', 'AI_INPUT_RATE': '3',
        'AI_OUTPUT_RATE': '15', 'AI_CACHED_RATE': '.3'}


def saved(doc):
    out = io.BytesIO(); doc.save(out); return out.getvalue()


def box(doc, text=None, pict=False):
    table = doc.add_table(rows=1, cols=1)
    borders = OxmlElement('w:tcBorders')
    for side in ('top', 'left', 'bottom', 'right'):
        edge = OxmlElement('w:' + side); edge.set(qn('w:val'), 'single'); borders.append(edge)
    table.cell(0, 0)._tc.get_or_add_tcPr().append(borders)
    if text:
        table.cell(0, 0).paragraphs[0].add_run(text)
    if pict:
        table.cell(0, 0).paragraphs[0].add_run()._r.append(OxmlElement('w:pict'))
    return table


def lines(*texts, heading='Clinic record'):
    doc = Document(); doc.add_heading(heading, level=2)
    for text in texts:
        doc.add_paragraph(text)
    return saved(doc)


def legacy_rows(*labels):
    doc = Document(); doc.add_paragraph('Clinic record')
    table = doc.add_table(rows=len(labels), cols=2)
    for n, label in enumerate(labels):
        table.cell(n, 0).text = label
    return saved(doc)


def forged(data, slot, kind='text', label='Forged answer'):
    """A field a stored mapping could hold from before this change: exactly the place the engine's locate finds, with
    only the role check bypassed (never the placement)."""
    with patch.object(word_v3, 'destination_roles_of', return_value=[]):
        return word_v3.locate(data, [{'slot': BODY + slot, 'kind': kind, 'label': label}])[0]


def provider_capture(sent):
    """A mocked Anthropic client: records every request and answers every asked question with nothing."""
    def create(**request):
        sent.append(request)
        payload = json.loads(request['messages'][0]['content'])
        units = 'source_units' in payload
        body = {'fields': [{'key': q['key'], ('unit_ids' if units else 'quotes'): [], 'conflict': False}
                           for q in payload['questions']]}
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0),
                               stop_reason='end_turn', model='claude-sonnet-4-6', id='msg_synthetic',
                               content=[SimpleNamespace(type='text', text=json.dumps(body))], _request_id='req_synthetic')
    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return patch('anthropic.Anthropic', return_value=client)


@override_settings(**V3)
class V3Gates(V3Fixture, TestCase):
    SIGNATURE_FORM = ('Signature: ______________', 'Plan: ______')

    def upload_lines(self, *texts, name='Synthetic signing line'):
        data = lines(*texts)
        template, version = self.uploaded(data=data, name=name)
        return data, template, version

    def stored(self, template, fields):
        """A stored mapping version (and its confirmation) as a release before this change could have left it."""
        latest = self.latest(template)
        version = TemplateVersion.objects.create(template=template, number=latest.number + 1, fields=fields,
                                                 contract='v3', created_by=self.user)
        MappingConfirmation.objects.create(version=version, confirmed_by=self.user)
        return version

    def encounter(self, version, notes):
        self.assertEqual(self.new_encounter(version, notes=notes).status_code, 302)
        return Encounter.objects.latest('created_at')

    def test_rf01_remove_then_add_text_on_a_signature_line_is_refused_signature_kind_is_allowed(self):
        data, template, version = self.upload_lines(*self.SIGNATURE_FORM)
        signature = next(f for f in version.fields if f['kind'] == 'signature')
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_save', 'mapping_version': version.pk,
                                                                  'remove_' + signature['key']: 'on'})
        self.assertEqual(response.status_code, 302)
        latest = self.latest(template)
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_add', 'mapping_version': latest.pk,
                                    'slot': BODY + 'b/p[1]', 'kind': 'text', 'label': 'Signature'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('signing, initials or consent area', response.context['v3_error'])
        self.assertEqual(self.latest(template).pk, latest.pk)
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_add', 'mapping_version': latest.pk,
                                    'slot': BODY + 'b/p[1]', 'kind': 'signature', 'label': 'Signature'})
        self.assertEqual(response.status_code, 302)
        self.confirm(template)

    def test_rf18_a_manual_answer_in_a_signing_question_box_is_refused(self):
        doc = Document(); doc.add_heading('Consultant review', level=2); doc.add_paragraph('Signed by the consultant:')
        box(doc); doc.add_paragraph('Plan: ______')
        template, version = self.uploaded(data=saved(doc), name='Synthetic signing box')
        for slot in ('b/tbl[0]/tr[0]/tc[0]', 'b/tbl[0]/tr[0]/tc[0]/p[0]'):
            with self.subTest(slot=slot):
                response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_add', 'mapping_version': version.pk,
                                            'slot': BODY + slot, 'kind': 'long_text', 'label': 'Consultant review'})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(template.versions.count(), 1)

    def test_rf19_a_stored_mapping_on_a_signature_place_is_held_everywhere(self):
        """not confirmed, not asked, save 400, finalize refused, fill protected_signing_area; Plan unaffected."""
        data, template, version = self.upload_lines(*self.SIGNATURE_FORM)
        plan = next(f for f in version.fields if f['label'] == 'Plan')
        bad = forged(data, 'b/p[1]', label='Signature')
        fields = [plan, bad]
        # confirmation of such a mapping is refused (a fresh version, unconfirmed)
        latest = TemplateVersion.objects.create(template=template, number=2, fields=fields, contract='v3', created_by=self.user)
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_confirm', 'mapping_version': latest.pk,
                                                                   'checked_every_field': 'on'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('Signature', response.context['v3_error'])
        self.assertIsNone(TemplateVersion.objects.get(pk=latest.pk).confirmed)
        # a stored confirmed version from before this change
        stored = self.stored(template, fields)
        self.assertEqual(destination_roles.v3_held(stored), {bad['key']: word_v3.ROLE_REFUSALS['signing']})
        e = self.encounter(stored, 'Signature: Dr Forged Signer\nPlan: Rest and fluids.')
        enqueue(Encounter.objects.get(pk=e.pk), self.user); self.assertTrue(run_one())
        e.refresh_from_db()
        self.assertEqual((e.answers[bad['key']]['status'], e.answers[bad['key']]['text']), ('missing', ''))
        self.assertEqual(e.answers[bad['key']]['reason'], word_v3.ROLE_REFUSALS['signing'])
        self.assertEqual(e.answers[plan['key']]['text'], 'Rest and fluids.')
        # never asked: the live request carries no question for it (its label stays a context label)
        sent = []
        with override_settings(**LIVE), provider_capture(sent):
            generation.generate(e.notes, destination_roles.generation_fields(stored), generation.configuration())
        payload = json.loads(sent[0]['messages'][0]['content'])
        self.assertEqual([q['key'] for q in payload['questions']], [plan['key']])
        self.assertIn('Signature', payload['context_labels'])
        # save: any text there is refused, nothing saved
        post = {'revision': e.revision, 'answer_' + plan['key']: 'Rest and fluids.', 'reviewed_' + plan['key']: 'on',
                'answer_' + bad['key']: 'Dr Forged Signer', 'reviewed_' + bad['key']: 'on'}
        response = self.client.post(f'/encounters/{e.pk}/save/', post)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Signature', response.content.decode())
        before = Encounter.objects.get(pk=e.pk)
        self.assertEqual(before.revision, e.revision)
        # finalize: refused, no export (an answer stored by an earlier release)
        answers = dict(before.answers)
        answers[bad['key']] = {'text': 'Dr Forged Signer', 'status': 'edited', 'reviewed': True, 'reviewed_by': str(self.user.pk), 'evidence': []}
        answers[plan['key']] = {**answers[plan['key']], 'reviewed': True, 'reviewed_by': str(self.user.pk)}
        Encounter.objects.filter(pk=e.pk).update(answers=answers)
        response = self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': before.revision, 'reviewed': 'on'}, follow=True)
        self.assertIn('never takes a typed or generated answer', response.content.decode())
        self.assertEqual(Encounter.objects.get(pk=e.pk).status, 'review')
        # the fill itself refuses by the original's roles, never trusting the mapping
        private_path('exports').mkdir(parents=True, exist_ok=True)
        with self.assertRaises(DocumentError) as refused:
            fill_template(private_path(template.original_path), fields, {bad['key']: 'Dr Forged Signer'},
                          private_path('exports/forged.docx'))
        self.assertEqual(refused.exception.code, 'protected_signing_area')

    def test_pc01_name_beside_a_signature_is_generated_and_exported(self):
        data, template, version = self.upload_lines('Name: ______    Signature: ______', 'Plan: ______')
        name = next(f for f in version.fields if f['label'] == 'Name')
        self.confirm(template, version)
        e = self.encounter(version, 'Name: Synthetic Example\nPlan: Rest.')
        enqueue(Encounter.objects.get(pk=e.pk), self.user); self.assertTrue(run_one())
        e.refresh_from_db()
        self.assertEqual((e.answers[name['key']]['status'], e.answers[name['key']]['text']), ('supported', 'Synthetic Example'))
        post = {'revision': e.revision}
        for f in version.fields:
            if f['kind'] in v3_mapping.SIGNING_KINDS:
                continue
            post['answer_' + f['key']] = e.answers[f['key']]['text']; post['reviewed_' + f['key']] = 'on'
        self.assertEqual(self.client.post(f'/encounters/{e.pk}/save/', post).status_code, 302)
        e.refresh_from_db()
        self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'})
        e.refresh_from_db()
        self.assertEqual(e.status, 'finalized')
        self.assertIn('Name: Synthetic Example', part_text(private_path(e.export_path).read_bytes()))


@override_settings(**TEST_SETTINGS)
class LegacyDefaultPath(V3Fixture, TestCase):
    LABELS = ('Patient signature', 'Consultant signature', 'Initials', 'Consent form signed', 'Initial assessment',
              'Electronically signed by', 'Plan')
    NOTES = ('Patient signature: John Example\nConsultant signature: Dr Example\nInitials: JE\n'
             'Consent form signed: Yes\nInitial assessment: Stable\nElectronically signed by: Dr Other\nPlan: Rest.')

    def setUp(self):
        super().setUp()
        self.data = legacy_rows(*self.LABELS)
        self.template, self.version = self.uploaded(data=self.data, name='Synthetic legacy roles')
        self.by = self.by_label(self.version)
        self.assertEqual(self.version.contract, '')

    def generated(self):
        self.assertEqual(self.new_encounter(self.version, notes=self.NOTES).status_code, 302)
        e = Encounter.objects.latest('created_at')
        enqueue(Encounter.objects.get(pk=e.pk), self.user); self.assertTrue(run_one())
        e.refresh_from_db()
        return e

    def test_rf16_rf17_signature_initials_and_signer_rows_are_never_generated_checklist_rows_are(self):
        e = self.generated()
        for label in ('Patient signature', 'Consultant signature', 'Initials', 'Electronically signed by'):
            with self.subTest(label=label):
                answer = e.answers[self.by[label]['key']]
                self.assertEqual((answer['status'], answer['text']), ('missing', ''))
                self.assertTrue(answer['reason'])
        for label, text in (('Consent form signed', 'Yes'), ('Initial assessment', 'Stable'), ('Plan', 'Rest.')):
            with self.subTest(label=label):   # PC09 / PC07: checklist states and adjectives stay ordinary answers
                self.assertEqual(e.answers[self.by[label]['key']]['text'], text)
        sent = []
        with override_settings(**LIVE), provider_capture(sent):
            generation.generate(e.notes, destination_roles.generation_fields(self.version), generation.configuration())
        asked = [q['label'] for q in json.loads(sent[0]['messages'][0]['content'])['questions']]
        self.assertEqual(asked, ['Consent form signed', 'Initial assessment', 'Plan'])

    def review_all(self, e, override=()):
        post = {'revision': e.revision}
        for f in self.version.fields:
            post['answer_' + f['key']] = dict(override).get(f['label'], e.answers.get(f['key'], {}).get('text', ''))
            post['reviewed_' + f['key']] = 'on'
        return self.client.post(f'/encounters/{e.pk}/save/', post)

    def test_generated_or_accepted_text_on_a_role_row_is_refused_typed_text_exports(self):
        e = self.generated()
        key = self.by['Patient signature']['key']
        # a draft from before this change could hold generated text there
        Encounter.objects.filter(pk=e.pk).update(answers={**e.answers, key: {'text': 'John Example', 'status': 'supported',
                                                                              'evidence': [], 'reviewed': False}})
        e.refresh_from_db()
        response = self.review_all(e)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Patient signature', response.content.decode())
        self.assertEqual(Encounter.objects.get(pk=e.pk).revision, e.revision)
        # the clinician's own typed entry is theirs, and it exports (legacy: provenance, not a blanket refusal)
        response = self.review_all(e, override={'Patient signature': 'J. Example (signed on paper)'})
        self.assertEqual(response.status_code, 302)
        e.refresh_from_db()
        self.assertEqual(e.answers[key]['status'], 'edited')
        self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'})
        e.refresh_from_db()
        self.assertEqual(e.status, 'finalized')
        self.assertIn('J. Example (signed on paper)', part_text(private_path(e.export_path).read_bytes()))

    def test_finalize_refuses_generated_text_on_a_role_row(self):
        e = self.generated()
        key = self.by['Initials']['key']
        answers = {k: {**v, 'reviewed': True, 'reviewed_by': str(self.user.pk)} for k, v in e.answers.items()}
        answers[key] = {'text': 'JE', 'status': 'supported', 'evidence': [], 'reviewed': True, 'reviewed_by': str(self.user.pk)}
        Encounter.objects.filter(pk=e.pk).update(answers=answers, status='review')
        response = self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'}, follow=True)
        self.assertIn('never fills from notes', response.content.decode())
        self.assertEqual(Encounter.objects.get(pk=e.pk).status, 'review')

    def test_pc14_the_signer_row_keeps_the_finalizers_name_rule(self):
        e = self.generated()
        key = self.by['Electronically signed by']['key']
        response = self.review_all(e, override={'Electronically signed by': 'Dr Somebody Else'})
        self.assertEqual(response.status_code, 302)
        e.refresh_from_db()
        response = self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'}, follow=True)
        self.assertIn('must match your signed-in clinician name', response.content.decode())
        name = ' '.join((self.user.get_full_name() or self.user.email).split())
        e.refresh_from_db()
        response = self.review_all(e, override={'Electronically signed by': name})
        e.refresh_from_db()
        self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'})
        e.refresh_from_db()
        self.assertEqual(e.status, 'finalized')
        self.assertEqual(e.answers[key]['text'], name)


@override_settings(**TEST_SETTINGS)
class LegacyIdentityReadsThePrintedLabel(V3Fixture, TestCase):
    def test_l05_renaming_a_participants_signature_to_signature_does_not_make_it_the_finalizers(self):
        template, version = self.uploaded(data=legacy_rows("Participant's signature", 'Plan'), name='Synthetic L05')
        by = self.by_label(version)
        response = self.client.post(f'/templates/{template.pk}/', {
            'mapping_version': version.pk, 'labels': json.dumps({by["Participant's signature"]['key']: 'Signature',
                                                                  by['Plan']['key']: 'Plan'})})
        latest = self.latest(template)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.by_label(latest)['Signature']['key'], by["Participant's signature"]['key'])
        self.assertEqual(self.new_encounter(latest, notes='Plan: Rest.').status_code, 302)
        e = Encounter.objects.latest('created_at')
        key = by["Participant's signature"]['key']
        post = {'revision': e.revision, 'answer_' + key: '', 'blank_' + key: 'on', 'reviewed_' + key: 'on',
                'answer_' + by['Plan']['key']: 'Rest.', 'reviewed_' + by['Plan']['key']: 'on'}
        # 'Leave blank - reviewed' is refused only for the finalizer's own signature row; this one is the participant's.
        self.assertEqual(self.client.post(f'/encounters/{e.pk}/save/', post).status_code, 302)


@override_settings(**MAPPING_SETTINGS)
class ModelProposals(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        self.config = generation.configuration()

    def version_of(self, data, name, drop=()):
        template, version = self.uploaded(data=data, name=name)
        if drop:
            fields = [f for f in version.fields if f['label'] not in drop]
            self.assertEqual(len(fields), len(version.fields) - len(drop))
            version = TemplateVersion.objects.create(template=template, number=2, fields=fields, contract='v3',
                                                     created_by=self.user)
        return template, version

    def compiled(self, version):
        compiled = mapping.compile_request(version, self.config)
        return compiled, json.loads(compiled['request']['messages'][0]['content'])

    @staticmethod
    def change(payload, slot, text, kind='text', fid=-1, glyph=-1, role=0):
        sid = next(n for n, row in enumerate(payload['slots']) if row['slot'] == BODY + slot)
        source = payload['slots'][sid][('text', 'heading', 'row_label')[role]]
        ref = payload['text_refs'].index([sid, role, 0])
        start = source.index(text)
        return [fid, sid, mapping.wire.KINDS.index(kind), ref, start, start + len(text), glyph]

    @staticmethod
    def keep_all(payload):
        body = mapping.wire.fixture(payload)
        return body

    def test_rf07_rf08_rf09_a_model_addition_is_never_adopted_it_is_a_review_item(self):
        cases = []
        data = lines('Signature: ______________', 'Plan: ______')
        cases.append(('RF07', data, ('Signature',), 'b/p[1]', 'Signature', 'text'))
        for fill in (None, 'pict', 'Use black ink'):
            doc = Document(); doc.add_heading('Consultant review', level=2); doc.add_paragraph('Signed by the consultant:')
            box(doc, text=fill if fill not in (None, 'pict') else None, pict=fill == 'pict'); doc.add_paragraph('Plan: ______')
            cases.append(('RF08-%s' % fill, saved(doc), (), 'b/tbl[0]/tr[0]/tc[0]/p[0]', 'Consultant review', 'long_text'))
        doc = Document(); doc.add_heading('Clinic record', level=2)
        t = doc.add_table(rows=2, cols=2); t.cell(0, 0).text = 'Name'; t.cell(0, 1).text = 'Signature'; t.cell(1, 1).text = 'Use black ink'
        cases.append(('RF09', saved(doc), (), 'b/tbl[0]/tr[1]/tc[1]/p[0]', 'Use black ink', 'text'))
        for n, (rid, data, drop, slot, label, kind) in enumerate(cases):
            with self.subTest(rid=rid):
                template, version = self.version_of(data, 'Synthetic %s' % rid, drop)
                compiled, payload = self.compiled(version)
                body = self.keep_all(payload)
                role = 1 if label == 'Consultant review' else 0
                body['x'] = [self.change(payload, slot, label, kind, role=role)]
                result = mapping.validate_proposal(version, compiled, body)
                self.assertEqual(result['fields'], version.fields, 'nothing is adopted')
                self.assertEqual(result['review']['changes'], [])
                proposed = [row for row in result['review']['unresolved'] if row.get('proposal')]
                self.assertEqual([(row['slot'], row['proposal']['label']) for row in proposed], [(BODY + slot, label)])
                self.assertIn('never adopted automatically', proposed[0]['reason'])
                if rid != 'RF09':
                    self.assertIn('only a Signature or Initials field can be added', proposed[0]['reason'])

    def test_rf11_one_invalid_change_is_held_and_a_valid_relabel_is_adopted(self):
        doc = Document(); doc.add_paragraph('Section 3: Public protection')
        t = doc.add_table(rows=2, cols=2)
        t.cell(0, 0).text = 'Does a formal offender supervision scheme currently apply to this person?'
        t.cell(1, 0).text = 'Date the lead agency was last informed'
        template, version = self.version_of(saved(doc), 'Synthetic RF11')
        compiled, payload = self.compiled(version)
        body = self.keep_all(payload)
        date = next(f for f in version.fields if f['kind'] == 'date')
        other = next(f for f in version.fields if f['key'] != date['key'])
        fid_date = next(n for n, f in enumerate(payload['fields']) if f['key'] == date['key'])
        fid_other = next(n for n, f in enumerate(payload['fields']) if f['key'] == other['key'])
        for code in ('k',):
            body['f'][code] = [n for n in body['f'][code] if n not in (fid_date, fid_other)]
        body['f']['r'] = [fid_other, fid_date]
        date_slot = date['locator']['slot']
        other_slot = other['locator']['slot']
        # invalid: at its own cell, the label quotes ANOTHER slot's text (the retained evidence/002 change-0 shape)
        question = next(n for n, row in enumerate(payload['slots']) if row['slot'] == BODY + 'b/tbl[0]/tr[0]/tc[0]/p[0]')
        invalid = [fid_other, next(n for n, row in enumerate(payload['slots']) if row['slot'] == BODY + other_slot),
                   0, payload['text_refs'].index([question, 0, 0]), 0, 22, -1]
        valid = self.change(payload, date_slot, 'Date the lead agency was last informed', kind='date', fid=fid_date, role=2)
        body['x'] = [invalid, valid]
        result = mapping.validate_proposal(version, compiled, body)
        adopted = next(f for f in result['fields'] if f['key'] == date['key'])
        self.assertEqual((adopted['label'], adopted['locator'], adopted['origin']),
                         ('Date the lead agency was last informed', date['locator'], 'model_assisted'))
        self.assertEqual(next(f for f in result['fields'] if f['key'] == other['key']), other)
        self.assertEqual(result['review']['changes'], [{'key': date['key'], 'replacement': date['key']}])
        self.assertEqual([r['wire'] for r in result['review']['rejected_changes']], [invalid])

    def test_rf12_the_outcome_is_the_same_for_every_order_of_the_changes(self):
        doc = Document(); doc.add_heading('Clinic record', level=2); doc.add_paragraph('Pulse findings: ______')
        doc.add_paragraph('Allergies'); doc.add_paragraph('Smoker ☐ Yes ☐ No'); doc.add_paragraph('Plan: ______')
        template, version = self.version_of(saved(doc), 'Synthetic permutations', drop=('Smoker',))
        compiled, payload = self.compiled(version)
        pulse = next(f for f in version.fields if f['label'] == 'Pulse findings')
        fid = next(n for n, f in enumerate(payload['fields']) if f['key'] == pulse['key'])
        base = self.keep_all(payload); base['f']['k'].remove(fid); base['f']['r'] = [fid]
        changes = [self.change(payload, 'b/p[1]', 'Pulse findings', fid=fid, kind='long_text'),
                   self.change(payload, 'b/p[2]', 'Allergies'), self.change(payload, 'b/p[2]', 'Allergies', kind='long_text'),
                   self.change(payload, 'b/p[3]', 'Yes', kind='checkbox', glyph=0),
                   self.change(payload, 'b/p[3]', 'No', kind='checkbox', glyph=1),
                   [-1, 0, 0, 399999, 0, 1, -1]]
        outcomes = set()
        # The original never changes across the 720 orders: its role report is read in the isolated parser once per
        # distinct mapping and reused (the reading itself is exercised by every other test).
        reports, real = {}, destination_roles.report
        def report(version, fields=None):
            key = mapping.canonical(fields if fields is not None else version.fields)
            if key not in reports:reports[key] = real(version, fields)
            return copy.deepcopy(reports[key])
        with patch.object(destination_roles, 'report', side_effect=report):
            for order in itertools.permutations(changes):
                body = copy.deepcopy(base); body['x'] = [list(c) for c in order]
                result = mapping.validate_proposal(version, compiled, body)
                outcomes.add(mapping.canonical({'fields': result['fields'], 'changes': result['review']['changes'],
                                                'unresolved': result['review']['unresolved'],
                                                'rejected': result['review']['rejected_changes']}))
        self.assertEqual(len(outcomes), 1, 'the order of the changes decided the outcome')
        result = json.loads(outcomes.pop())
        self.assertEqual(result['changes'], [{'key': pulse['key'], 'replacement': pulse['key']}])
        boxes = [r for r in result['rejected'] if r['slot'] == BODY + 'b/p[3]']
        self.assertEqual(len(boxes), 2)
        self.assertEqual(sorted(boxes[0]['with']), [boxes[1]['id']])   # RF13: one printed option group, named together
        allergies = [r for r in result['rejected'] if r['slot'] == BODY + 'b/p[2]']
        self.assertEqual([len(r['with']) for r in allergies], [1, 1])

    def test_dependent_changes_are_held_naming_each_other_and_an_independent_one_is_adopted(self):
        """D6 (the same question), D3 (an addition landing on a field another change replaces): every member is held
        with its reason; an independent relabel beside them is still adopted."""
        data = lines('Pulse findings: ______', 'Pulse findings (left): ______', 'Plan: ______')
        template, version = self.version_of(data, 'Synthetic dependence')
        compiled, payload = self.compiled(version)
        first, second, plan = [next(f for f in version.fields if f['label'] == label)
                               for label in ('Pulse findings', 'Pulse findings (left)', 'Plan')]
        fid = {f['key']: n for n, f in enumerate(payload['fields'])}
        def body_with(changes, replaced):
            body = self.keep_all(payload)
            body['f']['k'] = [n for n in body['f']['k'] if n not in replaced]; body['f']['r'] = sorted(replaced)
            body['x'] = changes
            return body
        again = self.change(payload, 'b/p[2]', 'Pulse findings', fid=fid[second['key']])
        # a relabel that asks a KEPT field's question: held, depending on that field
        result = mapping.validate_proposal(version, compiled, body_with([again], {fid[second['key']]}))
        self.assertEqual(result['review']['changes'], [])
        self.assertIn(mapping.QUESTION_REASON.format(label='Pulse findings'),
                      ' '.join(r['reason'] for r in result['review']['unresolved']))
        # two relabels asking one question: both held, each naming the other; the independent Plan relabel adopted
        own = self.change(payload, 'b/p[1]', 'Pulse findings', fid=fid[first['key']])
        independent = self.change(payload, 'b/p[3]', 'Plan', fid=fid[plan['key']], kind='long_text')
        result = mapping.validate_proposal(version, compiled, body_with(
            [own, again, independent], {fid[first['key']], fid[second['key']], fid[plan['key']]}))
        self.assertEqual(result['review']['changes'], [{'key': plan['key'], 'replacement': plan['key']}])
        held = {r['key']: r for r in result['review']['rejected_changes']}
        self.assertEqual(held[first['key']]['with'], [held[second['key']]['id']])
        self.assertEqual(held[second['key']]['with'], [held[first['key']]['id']])
        # D3: an addition on the place another change replaces holds that replacement too
        addition = self.change(payload, 'b/p[1]', 'Pulse findings', kind='long_text')
        result = mapping.validate_proposal(version, compiled, body_with([own, addition], {fid[first['key']]}))
        self.assertEqual(result['review']['changes'], [])
        self.assertTrue(all(r['with'] for r in result['review']['rejected_changes']))

    def test_rf14_a_replacement_keeps_its_place(self):
        data = lines('Pulse findings: ______', 'Plan: ______')
        template, version = self.version_of(data, 'Synthetic RF14')
        compiled, payload = self.compiled(version)
        pulse = next(f for f in version.fields if f['label'] == 'Pulse findings')
        fid = next(n for n, f in enumerate(payload['fields']) if f['key'] == pulse['key'])
        body = self.keep_all(payload); body['f']['k'].remove(fid); body['f']['r'] = [fid]
        body['x'] = [self.change(payload, 'b/p[1]', 'Pulse findings', fid=fid, kind='long_text')]
        result = mapping.validate_proposal(version, compiled, body)
        field = next(f for f in result['fields'] if f['key'] == pulse['key'])
        self.assertEqual((field['kind'], field['locator']), ('long_text', pulse['locator']))
        out = private_path('exports/rf14.docx'); out.parent.mkdir(parents=True, exist_ok=True)
        fill_template(private_path(template.original_path), result['fields'], {pulse['key']: 'weak radial pulse'}, out)
        self.assertIn('Pulse findings: weak radial pulse', part_text(out.read_bytes()))
        self.assertNotIn('______', part_text(out.read_bytes()).split('Pulse findings: weak radial pulse')[0][-10:])

    def test_a_replacement_needs_an_automatic_ordinary_field_with_no_role(self):
        data = lines('Signature: ______________', 'Plan: ______')
        template, version = self.version_of(data, 'Synthetic replacement rules')
        signature = next(f for f in version.fields if f['kind'] == 'signature')
        plan = next(f for f in version.fields if f['label'] == 'Plan')
        manual = {**plan, 'origin': 'manual'}
        # (labelled 'Answer': a label the identity check reads as the finalizer's is refused earlier, by NOT_ORDINARY)
        automatic = {k: v for k, v in forged(data, 'b/p[1]', label='Answer').items() if k != 'origin'}
        cases = (('signature kind', [signature, plan], signature, 'Signature', 'text', mapping.SIGNING_REASON),
                 ('manual field', [signature, manual], manual, 'Plan', 'text', mapping.NOT_AUTOMATIC),
                 ('kind to checkbox', [signature, plan], plan, 'Plan', 'checkbox', mapping.KIND_CHANGE),
                 ('an automatic-looking field on a role place', [plan, automatic], automatic, 'Signature', 'text',
                  mapping.ROLE_PLACE))
        for n, (name, fields, prior, label, kind, reason) in enumerate(cases):
            with self.subTest(case=name):
                stored = TemplateVersion.objects.create(template=template, number=n + 2, fields=fields, contract='v3',
                                                        created_by=self.user)
                prior = prior or fields[1]
                compiled, payload = self.compiled(stored)
                fid = next(i for i, f in enumerate(payload['fields']) if f['key'] == prior['key'])
                body = self.keep_all(payload); body['f']['k'].remove(fid); body['f']['r'] = [fid]
                slot = prior['locator']['slot']
                body['x'] = [self.change(payload, slot, label, kind=kind, fid=fid)]
                result = mapping.validate_proposal(stored, compiled, body)
                self.assertEqual(result['fields'], stored.fields)
                self.assertIn(reason, ' '.join(row['reason'] for row in result['review']['unresolved']))

    def test_rf15_resolve_applies_removals_first_and_revalidates(self):
        data = lines('Allergies: ______', 'Plan: ______')
        template, version = self.version_of(data, 'Synthetic RF15')
        allergies = next(f for f in version.fields if f['label'] == 'Allergies')
        slot = BODY + allergies['locator']['slot']
        assisted = TemplateVersion.objects.create(template=template, number=2, fields=version.fields, contract='v3',
            created_by=self.user, assistance={'unresolved': [
                {'slot': slot, 'reason': 'Proposed addition', 'key': '', 'text': ''},
                {'slot': slot, 'reason': 'Existing field requires clinician review', 'key': allergies['key'], 'text': ''}]})
        url = f'/templates/{template.pk}/assistance/'
        # 'mapped' for an area whose only field the same submission removes: refused
        response = self.client.post(url, {'action': 'resolve', 'mapping_version': assisted.pk,
                                          'resolution_0': 'mapped', 'resolution_1': 'not_answer'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.latest(template).pk, assisted.pk)
        # a key-less 'not an answer' on an area a field still writes to: refused
        response = self.client.post(url, {'action': 'resolve', 'mapping_version': assisted.pk,
                                          'resolution_0': 'not_answer', 'resolution_1': 'mapped'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.latest(template).pk, assisted.pk)
        # consistent decisions are saved
        response = self.client.post(url, {'action': 'resolve', 'mapping_version': assisted.pk,
                                          'resolution_0': 'mapped', 'resolution_1': 'mapped'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.latest(template).assistance['unresolved'], [])


# ─── refutation round 1 (e555540d): each test is red on e555540d and names the finding it closes ─────────────────
def framed(h1, inside, prompt=None):
    doc = Document()
    if h1:
        doc.add_heading(h1, level=1)
    if prompt:
        doc.add_paragraph(prompt)
    else:
        doc.add_heading('Clinical details', level=2)
    cell = box(doc).cell(0, 0)
    for n, text in enumerate(inside):
        (cell.paragraphs[0] if n == 0 else cell.add_paragraph()).add_run(text)
    doc.add_heading('Management', level=2); doc.add_paragraph('Plan: ______')
    return saved(doc)


class Walk:
    """generate -> review every row -> finalize, on the fixture generator (no provider)."""

    def generated(self, version, notes):
        self.assertEqual(self.new_encounter(version, notes=notes).status_code, 302)
        e = Encounter.objects.latest('created_at')
        enqueue(Encounter.objects.get(pk=e.pk), self.user); self.assertTrue(run_one())
        e.refresh_from_db()
        return e

    def reviewed(self, e, version, typed=(), skip_signing=False):
        post = {'revision': e.revision}
        for f in version.fields:
            if skip_signing and f.get('kind') in v3_mapping.SIGNING_KINDS:
                continue
            post['answer_' + f['key']] = dict(typed).get(f['label'], e.answers.get(f['key'], {}).get('text', ''))
            post['reviewed_' + f['key']] = 'on'
        response = self.client.post(f'/encounters/{e.pk}/save/', post)
        e.refresh_from_db()
        return response

    def finalized(self, e):
        response = self.client.post(f'/encounters/{e.pk}/finalize/', {'revision': e.revision, 'reviewed': 'on'}, follow=True)
        e.refresh_from_db()
        return response


@override_settings(**TEST_SETTINGS)
class LegacyRound1(Walk, V3Fixture, TestCase):
    def test_l1f1_l1f5_signing_rows_are_never_generated_or_exported(self):
        """L1:F1 (HIGH) and L1:F5: e555540d generated 'Dr Example' / 'JE' into these legacy rows and exported them."""
        for label, value in (('Signed (Consultant)', 'Dr Example'), ('Signed (print name)', 'Dr Example'),
                             ('Electronically signed (print name)', 'Dr Example'), ('Signed (GP)', 'Dr Example'),
                             ('Signed (patient)', 'John Example'), ('Signed for and on behalf of', 'Dr Example'),
                             ('Countersigned by consultant', 'Dr Example'), ('Signature and date', 'Dr Example'),
                             ('Initial here', 'JE'), ('Initial each page', 'JE')):
            with self.subTest(label=label):
                template, version = self.uploaded(data=legacy_rows(label, 'Plan'), name='Synthetic L1 ' + label)
                by = self.by_label(version)
                e = self.generated(version, f'{label}: {value}\nPlan: Rest.')
                answer = e.answers[by[label]['key']]
                self.assertEqual((answer['status'], answer['text']), ('missing', ''))
                self.assertEqual(self.reviewed(e, version).status_code, 302)
                self.finalized(e)
                self.assertEqual(e.status, 'finalized')
                self.assertNotIn(value, part_text(private_path(e.export_path).read_bytes()))

    def test_r2_06_a_numbered_initial_reading_is_generated(self):
        """R2-06: 'Initial 12-lead ECG' was held as an initials row and never generated."""
        template, version = self.uploaded(data=legacy_rows('Initial 12-lead ECG', 'Plan'), name='Synthetic R2-06')
        e = self.generated(version, 'Initial 12-lead ECG: Sinus rhythm\nPlan: Rest.')
        answer = e.answers[self.by_label(version)['Initial 12-lead ECG']['key']]
        self.assertEqual((answer['status'], answer['text']), ('supported', 'Sinus rhythm'))

    def test_r2_07_a_signer_row_with_a_parenthetical_keeps_the_finalizers_name_rule(self):
        """R2-07: 'Electronically signed by (print name)' and 'Signed by (name)' accepted another clinician's name."""
        for label in ('Electronically signed by (print name)', 'Signed by (name)', 'Signature (consultant)'):
            with self.subTest(label=label):
                template, version = self.uploaded(data=legacy_rows(label, 'Plan'), name='Synthetic R2-07 ' + label)
                e = self.generated(version, 'Plan: Rest.')
                self.assertEqual(self.reviewed(e, version, typed={label: 'Dr Somebody Else'}).status_code, 302)
                response = self.finalized(e)
                self.assertIn('must match your signed-in clinician name', response.content.decode())
                self.assertEqual(e.status, 'review')

    def test_r2_08_a_signature_label_may_gain_a_clinicians_parenthetical(self):
        """R2-08: renaming 'Signature' to 'Signature (consultant)' was refused as losing the signature label."""
        for n, label in enumerate(('Signature (consultant)', 'Signature (print name)')):
            with self.subTest(label=label):
                template, version = self.uploaded(data=legacy_rows('Signature', 'Plan'), name='Synthetic R2-08 %d' % n)
                by = self.by_label(version)
                response = self.client.post(f'/templates/{template.pk}/', {
                    'mapping_version': version.pk,
                    'labels': json.dumps({by['Signature']['key']: label, by['Plan']['key']: 'Plan'})})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.latest(template).number, 2)

    def test_another_persons_parenthetical_is_not_the_finalizers(self):
        from core.tab_review import clinician_identity
        for label in ('Signature (participant)', 'Signature (mother)', 'Signature (father)', 'Signature (donor)',
                      'Signed (patient)', 'Signed by (witness)'):
            with self.subTest(label=label):
                self.assertFalse(clinician_identity({'label': label}))
        for label in ('Signed (Consultant)', 'Signature (GP)', 'Signed (print name)', 'Signature (registrar)'):
            with self.subTest(label=label):
                self.assertTrue(clinician_identity({'label': label}))


@override_settings(**V3)
class V3Round1(Walk, V3Fixture, TestCase):
    def confirm_status(self, template, version):
        return self.client.post(f'/templates/{template.pk}/', {'action': 'v3_confirm', 'mapping_version': version.pk,
                                                               'checked_every_field': 'on'}).status_code

    def test_r2_01_a_frame_holding_ordinary_questions_is_confirmed_generated_and_exported(self):
        """R2-01 (HIGH): the frame under 'Initial referral' was a signing box; confirmation listed all three fields."""
        template, version = self.uploaded(data=framed('Initial referral', ('Presenting complaint: ______',
                                          'Current medication: ______', 'Allergies: ______')), name='Synthetic R2-01')
        self.assertEqual(self.confirm_status(template, version), 302)
        e = self.generated(version, 'Presenting complaint: Chest pain\nCurrent medication: Aspirin\n'
                                    'Allergies: None known\nPlan: Rest.')
        self.assertEqual(self.reviewed(e, version).status_code, 302)
        self.finalized(e)
        self.assertEqual(e.status, 'finalized')
        self.assertIn('Presenting complaint: Chest pain', part_text(private_path(e.export_path).read_bytes()))

    def test_r2_02_a_printed_name_beside_a_signature_is_confirmed(self):
        for n, text in enumerate(('Printed name:    Signature: ______', 'Consultant:    Signature: ______    Date: ______')):
            with self.subTest(text=text):
                template, version = self.uploaded(data=lines(text, 'Plan: ______'), name='Synthetic R2-02 %d' % n)
                self.assertEqual(self.confirm_status(template, version), 302)

    def test_r2_03_the_clinician_may_answer_an_initial_presentation_box(self):
        doc = Document(); doc.add_heading('History', level=2); doc.add_paragraph('Describe the initial presentation?')
        box(doc); doc.add_paragraph('Plan: ______')
        template, version = self.uploaded(data=saved(doc), name='Synthetic R2-03')
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_add', 'mapping_version': version.pk,
                                    'slot': BODY + 'b/tbl[0]/tr[0]/tc[0]', 'kind': 'long_text',
                                    'label': 'Describe the initial presentation?'})
        self.assertEqual(response.status_code, 302)

    def test_r2_04_an_initial_reading_can_be_replaced_by_its_text_answer(self):
        template, version = self.uploaded(data=lines('Initial GCS: ______', 'Plan: ______'), name='Synthetic R2-04')
        gcs = self.by_label(version)['Initial GCS']
        self.assertEqual(gcs['kind'], 'initials')
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_save', 'mapping_version': version.pk,
                                                                  'remove_' + gcs['key']: 'on'})
        self.assertEqual(response.status_code, 302)
        latest = self.latest(template)
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_add', 'mapping_version': latest.pk,
                                    'slot': BODY + 'b/p[1]', 'kind': 'text', 'label': 'Initial GCS'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.confirm_status(template, self.latest(template)), 302)

    def test_r2_05_an_unlocked_control_inside_a_locked_frame_is_confirmed(self):
        doc = Document(); doc.add_heading('Clinic record', level=2)
        frame = OxmlElement('w:sdt'); pr = OxmlElement('w:sdtPr'); lock = OxmlElement('w:lock')
        lock.set(qn('w:val'), 'contentLocked'); pr.append(lock); pr.append(OxmlElement('w:richText')); frame.append(pr)
        content = OxmlElement('w:sdtContent'); frame.append(content)
        p = doc.add_paragraph('Hospital number: ')
        sdt = OxmlElement('w:sdt'); spr = OxmlElement('w:sdtPr'); alias = OxmlElement('w:alias')
        alias.set(qn('w:val'), 'Hospital number'); spr.append(alias); spr.append(OxmlElement('w:showingPlcHdr'))
        spr.append(OxmlElement('w:text')); sdt.append(spr); body = OxmlElement('w:sdtContent')
        run = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text = 'Click or tap here to enter text.'; run.append(t)
        body.append(run); sdt.append(body); p._p.append(sdt); content.append(p._p)
        doc.element.body.find(qn('w:sectPr')).addprevious(frame)
        doc.add_paragraph('Plan: ______')
        template, version = self.uploaded(data=saved(doc), name='Synthetic R2-05')
        self.assertEqual(self.confirm_status(template, version), 302)

    def test_l1f2_a_signature_and_date_line_is_never_generated(self):
        """L1:F2 (HIGH): 'Signature and date: ____' was a date field; generation wrote 'Dr Example 30/09/2026'."""
        template, version = self.uploaded(data=lines('Signature and date: ______________', 'Plan: ______'),
                                          name='Synthetic L1F2')
        self.confirm(template, version)
        e = self.generated(version, 'Signature and date: Dr Example 30/09/2026\nPlan: Rest.')
        field = self.by_label(version)['Signature and date']
        self.assertEqual(field['kind'], 'signature')
        self.assertEqual((e.answers[field['key']]['status'], e.answers[field['key']]['text']), ('missing', ''))

    def test_l1f6_the_line_under_a_signature_caption_is_listed_at_confirmation(self):
        """L1:F6(a): the engine's 'Answer' field on the writing line under 'Consultant signature:' sits on the signing
        place; confirmation lists it, and after its removal the mapping confirms."""
        doc = Document(); doc.add_heading('Clinic record', level=2); doc.add_paragraph('Consultant signature:')
        doc.add_paragraph('____________________'); doc.add_paragraph('Plan: ______')
        template, version = self.uploaded(data=saved(doc), name='Synthetic L1F6')
        answer = next(f for f in version.fields if f['locator']['slot'] == 'b/p[2]')
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_confirm', 'mapping_version': version.pk,
                                                                   'checked_every_field': 'on'})
        self.assertEqual(response.status_code, 400)
        self.assertIn(answer['label'], response.context['v3_error'])
        self.client.post(f'/templates/{template.pk}/', {'action': 'v3_save', 'mapping_version': version.pk,
                                                        'remove_' + answer['key']: 'on'})
        self.assertEqual(self.confirm_status(template, self.latest(template)), 302)

    def test_l1f7_a_typed_initial_in_a_log_tables_initials_column_is_refused(self):
        """L1:F7: the initials column of 'Drug | Dose | Nurse initials' took typed 'JE' and exported it."""
        doc = Document(); doc.add_heading('Medication log', level=2)
        t = doc.add_table(rows=3, cols=3); t.style = 'Table Grid'
        for c, h in enumerate(('Drug', 'Dose', 'Nurse initials')):
            t.cell(0, c).text = h
        doc.add_paragraph('Plan: ______')
        template, version = self.uploaded(data=saved(doc), name='Synthetic L1F7')
        self.confirm(template, version)
        e = self.generated(version, 'Plan: Rest.')
        log = next(f for f in version.fields if f['kind'] == 'table_rows')
        response = self.reviewed(e, version, typed={log['label']: 'Paracetamol | 1 g | JE'}, skip_signing=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn('Nurse initials', response.content.decode())
        self.assertEqual(self.reviewed(e, version, typed={log['label']: 'Paracetamol | 1 g |'}, skip_signing=True).status_code, 302)


@override_settings(**MAPPING_SETTINGS)
class ModelProposalsRound1(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        self.config = generation.configuration()

    def proposal(self, version, replaced=(), uncertain=(), dismissed=(), changes=()):
        compiled = mapping.compile_request(version, self.config)
        payload = json.loads(compiled['request']['messages'][0]['content'])
        body = mapping.wire.fixture(payload)
        fids = {f['key']: n for n, f in enumerate(payload['fields'])}
        moved = {fids[k] for k in list(replaced) + list(uncertain)}
        body['f']['k'] = [n for n in body['f']['k'] if n not in moved]
        body['f']['r'] = sorted(fids[k] for k in replaced); body['f']['u'] = sorted(fids[k] for k in uncertain)
        sids = {row['slot']: n for n, row in enumerate(payload['slots'])}
        for slot in dismissed:
            for verdict in ('c', 'u', 'n'):
                body['s'][verdict] = [n for n in body['s'][verdict] if n != sids[slot]]
            body['s']['n'] = sorted(body['s']['n'] + [sids[slot]])
        body['x'] = [change(payload, fids, sids) for change in changes]
        return mapping.validate_proposal(version, compiled, body)

    @staticmethod
    def relabel(key, slot, kind, start, end, role=0):
        def build(payload, fids, sids):
            sid = sids[BODY + slot]
            return [fids[key], sid, mapping.wire.KINDS.index(kind), payload['text_refs'].index([sid, role, 0]), start, end, -1]
        return build

    def test_l3f1_a_replacement_label_is_printed_wording_not_spaces_or_a_blank_line(self):
        """L3:F1: ' ', ':', ': ' and '______' were adopted as the label (question_key(' ') == ''), unasking the question."""
        template, version = self.uploaded(data=lines('Pulse findings: ______', 'Plan: ______'), name='Synthetic L3F1')
        pulse = self.by_label(version)['Pulse findings']
        for name, (start, end) in (('space', (15, 16)), ('colon', (14, 15)), ('colon and space', (14, 16)),
                                   ('blank line', (16, 22))):
            with self.subTest(name=name):
                result = self.proposal(version, replaced=[pulse['key']],
                                       changes=[self.relabel(pulse['key'], 'b/p[1]', pulse['kind'], start, end)])
                self.assertEqual(result['review']['changes'], [])
                self.assertEqual(next(f for f in result['fields'] if f['key'] == pulse['key']), pulse)
                self.assertIn(mapping.LABEL_SHAPE, ' '.join(r['reason'] for r in result['review']['unresolved']))
        result = self.proposal(version, replaced=[pulse['key']],
                               changes=[self.relabel(pulse['key'], 'b/p[1]', pulse['kind'], 0, 15)])
        self.assertEqual(next(f for f in result['fields'] if f['key'] == pulse['key'])['label'], 'Pulse findings')

    def test_l3f2_the_finalizers_signature_label_is_never_relabelled(self):
        """L3:F2: 'Signature/Date' (identity) relabelled to 'Date' was adopted; generation then filled it."""
        template, version = self.uploaded(data=lines('Signature/Date: ______', 'Plan: ______'), name='Synthetic L3F2')
        signed = self.by_label(version)['Signature/Date']
        stored = TemplateVersion.objects.create(template=template, number=2, contract='v3', created_by=self.user,
            fields=[{**f, 'kind': 'date'} if f['key'] == signed['key'] else f for f in version.fields])  # before this repair
        at = 'Signature/Date: ______'.index('Date')
        result = self.proposal(stored, replaced=[signed['key']],
                               changes=[self.relabel(signed['key'], 'b/p[1]', 'date', at, at + 4)])
        self.assertEqual(result['review']['changes'], [])
        self.assertIn(mapping.NOT_ORDINARY, ' '.join(r['reason'] for r in result['review']['unresolved']))

    def test_l3f2_an_identity_label_on_a_place_with_no_role_is_never_relabelled(self):
        """Where no role holds the place, only the identity check does: a stored automatic field labelled as the
        finalizer's signature on the 'Pulse findings' line is never relabelled away from it by a model."""
        template, version = self.uploaded(data=lines('Pulse findings: ______', 'Plan: ______'), name='Synthetic L3F2b')
        pulse = self.by_label(version)['Pulse findings']
        stored = TemplateVersion.objects.create(template=template, number=2, contract='v3', created_by=self.user,
            fields=[{**f, 'label': 'Signed by'} if f['key'] == pulse['key'] else f for f in version.fields])
        result = self.proposal(stored, replaced=[pulse['key']],
                               changes=[self.relabel(pulse['key'], 'b/p[1]', pulse['kind'], 0, 14)])
        self.assertEqual(result['review']['changes'], [])
        self.assertEqual(next(f for f in result['fields'] if f['key'] == pulse['key'])['label'], 'Signed by')

    def test_l3f3_two_answers_on_one_line_are_independent(self):
        """L3:F3: 'Weight: ____ kg  Height: ____ cm' - dependence compared paragraphs, so a Height relabel was held for a
        Weight verdict and two disjoint relabels held each other."""
        text = 'Weight: ______ kg  Height: ______ cm'
        template, version = self.uploaded(data=lines(text, 'Plan: ______'), name='Synthetic L3F3')
        weight, height = version.fields[0], version.fields[1]
        at = text.index('Height')
        height_change = self.relabel(height['key'], 'b/p[1]', height['kind'], at, at + 6)
        weight_change = self.relabel(weight['key'], 'b/p[1]', weight['kind'], 0, 6)
        result = self.proposal(version, replaced=[height['key']], uncertain=[weight['key']], changes=[height_change])
        self.assertEqual(result['review']['changes'], [{'key': height['key'], 'replacement': height['key']}])
        adopted = next(f for f in result['fields'] if f['key'] == height['key'])
        self.assertEqual((adopted['label'], adopted['locator']), ('Height', height['locator']))
        result = self.proposal(version, replaced=[weight['key'], height['key']], changes=[height_change, weight_change])
        self.assertEqual(sorted(c['key'] for c in result['review']['changes']), sorted([weight['key'], height['key']]))

    def test_l3f4_a_change_inside_a_cell_the_proposal_dismisses_is_held(self):
        """L3:F4: the proposal marked the date cell not an answer, and a relabel naming the cell's paragraph was adopted."""
        doc = Document(); doc.add_heading('Section 3: Public protection', level=2)
        t = doc.add_table(rows=2, cols=2); t.style = 'Table Grid'
        t.cell(0, 0).text = 'Name of the lead agency'; t.cell(1, 0).text = 'Date the lead agency was informed'
        doc.add_paragraph('Plan: ______')
        template, version = self.uploaded(data=saved(doc), name='Synthetic L3F4')
        date = next(f for f in version.fields if f['kind'] == 'date')
        cell = date['locator']['slot']
        result = self.proposal(version, replaced=[date['key']], dismissed=[BODY + cell],
                               changes=[self.relabel(date['key'], cell + '/p[0]', 'date', 0, 20, role=2)])
        self.assertEqual(result['review']['changes'], [])
        self.assertIn('not an answer', ' '.join(r['reason'] for r in result['review']['unresolved']))
        # The printed line INSIDE a covered cell called 'not an answer' is not the cell (the retained evidence/002
        # response does exactly this): a relabel of the cell's field is still adopted.
        result = self.proposal(version, replaced=[date['key']], dismissed=[BODY + cell + '/p[0]'],
                               changes=[self.relabel(date['key'], cell, 'date', 0, 20, role=2)])
        self.assertEqual(result['review']['changes'], [{'key': date['key'], 'replacement': date['key']}])


# ─── refutation round 2 (a32243eb): each test is red on a32243eb and names the finding it closes ─────────────────
def wrapped_label(first, second, mode):
    doc = Document(); doc.add_paragraph('Clinic record')
    table = doc.add_table(rows=2, cols=2)
    cell = table.cell(0, 0)
    if mode == 'br':
        p = cell.paragraphs[0]; p.add_run(first).add_break(); p.add_run(second)
    else:
        cell.paragraphs[0].add_run(first); cell.add_paragraph(second)
    table.cell(1, 0).text = 'Plan'
    return saved(doc)


@override_settings(**TEST_SETTINGS)
class LegacyRound2(Walk, V3Fixture, TestCase):
    ROWS = (('Signature, date', 'Dr Somebody Else 30/09/2026'), ('Signature - date', 'Dr Somebody Else 30/09/2026'),
            ('Print name, sign and date', 'Dr Somebody Else'), ('Signed by (name, date)', 'Dr Example 30/09/2026'),
            ('Signature (participant, dd/mm/yyyy)', 'John Example 30/09/2026'),
            ('Signed (mother, DOB)', 'Jane Example 01/01/1990'), ('Initial 1', 'JE'), ('Initial on each page', 'JE'),
            ('Sign in box', 'Dr Somebody Else'), ('Consultant signed', 'Dr Somebody Else'),
            ('Signed patient', 'John Example'), ('To be signed', 'Dr Somebody Else'), ('Sign below', 'Dr Somebody Else'),
            ('Please sign', 'Dr Example'), ('Countersignature', 'Dr Example'), ('Initialled by', 'Dr Example'))

    def test_rr1_02_rr1_03_rr1_04_rr1_10_rr1_11_rr3_02_signing_rows_are_never_generated_or_exported(self):
        """a32243eb generated each value into its signing or initials row, and the finalized export printed it."""
        for n, (label, value) in enumerate(self.ROWS):
            with self.subTest(label=label):
                template, version = self.uploaded(data=legacy_rows(label, 'Plan'), name='Synthetic RR2 %d' % n)
                e = self.generated(version, f'{label}: {value}\nPlan: Rest.')
                answer = e.answers[self.by_label(version)[label]['key']]
                self.assertEqual((answer['status'], answer['text']), ('missing', ''))
                self.assertEqual(self.reviewed(e, version).status_code, 302)
                self.finalized(e)
                self.assertEqual(e.status, 'finalized')
                self.assertNotIn(value, part_text(private_path(e.export_path).read_bytes()))

    def test_rr1_05_a_wrapped_signing_label_is_never_generated(self):
        """'Consultant' + line break (or a second paragraph) + 'signature' read as 'Consultantsignature'."""
        for n, (mode, (first, second, value)) in enumerate(itertools.product(
                ('br', 'paragraphs'), (('Consultant', 'signature', 'Dr Somebody Else'), ('Nurse', 'initials', 'JE')))):
            with self.subTest(mode=mode, label=first + ' ' + second):
                template, version = self.uploaded(data=wrapped_label(first, second, mode), name='Synthetic RR1-05 %d' % n)
                label = first + ' ' + second
                self.assertIn(label, self.by_label(version))
                e = self.generated(version, f'{label}: {value}\nPlan: Rest.')
                answer = e.answers[self.by_label(version)[label]['key']]
                self.assertEqual((answer['status'], answer['text']), ('missing', ''))
                self.assertEqual(self.reviewed(e, version).status_code, 302)
                self.finalized(e)
                self.assertEqual(e.status, 'finalized')
                self.assertNotIn(value, part_text(private_path(e.export_path).read_bytes()))

    def test_pc09_checklist_states_are_still_generated(self):
        for n, label in enumerate(('Consent form signed', 'Drug chart signed', 'Time signed')):
            with self.subTest(label=label):
                template, version = self.uploaded(data=legacy_rows(label, 'Plan'), name='Synthetic PC09 %d' % n)
                e = self.generated(version, f'{label}: Yes\nPlan: Rest.')
                answer = e.answers[self.by_label(version)[label]['key']]
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Yes'))

    def test_rr3_05_a_patient_named_as_possessor_or_object_does_not_make_the_signer_the_patient(self):
        """'Signed by (doctor responsible for patient)' and "Signature (patient's consultant)" finalized another
        clinician's typed name: the patient word turned the finalizer's name rule off."""
        from core.tab_review import clinician_identity
        for label in ('Signed by (doctor responsible for patient)', "Signature (patient's consultant)",
                      'Signed by (doctor caring for the patient)'):
            with self.subTest(label=label):
                self.assertTrue(clinician_identity({'label': label}))
        for label in ('Signature (patient)', "Signature (patient's relative)", 'Signed by (witness)',
                      'Signature (for patient)', 'Signature (participant)'):
            with self.subTest(other=label):
                self.assertFalse(clinician_identity({'label': label}))
        for n, label in enumerate(('Signed by (doctor responsible for patient)', "Signature (patient's consultant)")):
            with self.subTest(walk=label):
                template, version = self.uploaded(data=legacy_rows(label, 'Plan'), name='Synthetic RR3-05 %d' % n)
                e = self.generated(version, 'Plan: Rest.')
                self.assertEqual(self.reviewed(e, version, typed={label: 'Dr Somebody Else'}).status_code, 302)
                response = self.finalized(e)
                self.assertIn('must match your signed-in clinician name', response.content.decode())
                self.assertEqual(e.status, 'review')


@override_settings(**V3)
class V3Round2(Walk, V3Fixture, TestCase):
    def confirmation(self, template, version):
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_confirm', 'mapping_version': version.pk,
                                                                   'checked_every_field': 'on'})
        return response.status_code, (response.context or {}).get('v3_error') if response.status_code == 400 else None

    def test_rr1_01_rr1_06_the_writing_line_of_a_signing_box_or_caption_is_listed_at_confirmation(self):
        """a32243eb confirmed these, generated 'Dr Somebody Else' onto the signing line and exported it."""
        doc = Document(); doc.add_heading('Consultant review', level=2); doc.add_paragraph('Signed by the consultant:')
        box(doc, text='______________________________'); doc.add_paragraph('Plan: ______')
        in_box = saved(doc)
        caption_under = lines('____________________', 'Consultant signature', 'Plan: ______', heading='Consultant review')
        blank_between = lines('Consultant signature:', '', '____________________', 'Plan: ______', heading='Consultant review')
        for n, (name, data) in enumerate((('box', in_box), ('caption under the line', caption_under),
                                          ('a blank paragraph between', blank_between))):
            with self.subTest(name=name):
                template, version = self.uploaded(data=data, name='Synthetic RR1-01/06 %d' % n)
                status, error = self.confirmation(template, version)
                self.assertEqual(status, 400)
                self.assertIn('signing', error)

    def test_rr1_07_a_manual_answer_in_a_hidden_signing_box_is_refused(self):
        doc = Document(); doc.add_heading('Consultant review', level=2); doc.add_paragraph('Signed by the consultant:')
        tbl = box(doc)._tbl; doc.add_paragraph('Plan: ______')
        bs = OxmlElement('w:bookmarkStart'); bs.set(qn('w:id'), '7'); bs.set(qn('w:name'), 'sig'); tbl.addprevious(bs)
        be = OxmlElement('w:bookmarkEnd'); be.set(qn('w:id'), '7'); tbl.addnext(be)
        bookmark = saved(doc)
        doc = Document(); doc.add_heading('Consultant review', level=2)
        outer = doc.add_table(rows=1, cols=1).cell(0, 0); outer.paragraphs[0].add_run('Signed by the consultant:')
        inner = outer.add_table(rows=1, cols=1)
        borders = OxmlElement('w:tcBorders')
        for side in ('top', 'left', 'bottom', 'right'):
            edge = OxmlElement('w:' + side); edge.set(qn('w:val'), 'single'); borders.append(edge)
        inner.cell(0, 0)._tc.get_or_add_tcPr().append(borders); outer.add_paragraph('')
        doc.add_paragraph('Plan: ______')
        nested = saved(doc)
        for n, (name, data, slot) in enumerate((('bookmark', bookmark, 'b/tbl[0]/tr[0]/tc[0]'),
                                                ('nested', nested, 'b/tbl[0]/tr[0]/tc[0]/tbl[0]/tr[0]/tc[0]'))):
            with self.subTest(name=name):
                template, version = self.uploaded(data=data, name='Synthetic RR1-07 %d' % n)
                response = self.client.post(f'/templates/{template.pk}/', {
                    'action': 'v3_add', 'mapping_version': version.pk, 'slot': BODY + slot, 'kind': 'long_text',
                    'label': 'Consultant review'})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.latest(template).pk, version.pk)

    def test_rr1_02_rr1_11_signing_lines_joined_to_a_date_or_another_act_are_never_generated(self):
        for n, (label, value) in enumerate((('Signature, date', 'Dr Example 30/09/2026'),
                                            ('Sign and print name', 'Dr Somebody Else'), ('Nurse sign', 'Dr Example'))):
            with self.subTest(label=label):
                template, version = self.uploaded(data=lines(f'{label}: ______________', 'Plan: ______'),
                                                  name='Synthetic RR2 v3 %d' % n)
                field = self.by_label(version)[label]
                self.assertEqual(field['kind'], 'signature')
                self.assertEqual(self.confirmation(template, version)[0], 302)
                e = self.generated(version, f'{label}: {value}\nPlan: Rest.')
                self.assertEqual((e.answers[field['key']]['status'], e.answers[field['key']]['text']), ('missing', ''))


@override_settings(**MAPPING_SETTINGS)
class ModelProposalsRound2(V3Fixture, TestCase):
    proposal = ModelProposalsRound1.proposal
    relabel = staticmethod(ModelProposalsRound1.relabel)

    def setUp(self):
        super().setUp()
        self.config = generation.configuration()

    def run_job(self, version, body):
        from decimal import Decimal
        from core import jobs, mapping_jobs
        from core.models import Job
        compiled = mapping.compile_request(version, self.config)
        mapping_jobs.enqueue(version, self.user, self.config, compiled['request_sha256'])
        with patch('anthropic.Anthropic', side_effect=AssertionError('provider construction forbidden')), \
                patch('core.mapping_jobs.send', return_value=(body, Decimal(0), {}, {}, 'synthetic-mapping-fixture',
                                                             '', '', True)):
            jobs.run_one()
        job = Job.objects.filter(kind='mapping').latest('created_at')
        return job.state, version.template.versions.latest('number')

    def body(self, version, replaced, changes):
        compiled = mapping.compile_request(version, self.config)
        payload = json.loads(compiled['request']['messages'][0]['content'])
        body = mapping.wire.fixture(payload)
        fids = {f['key']: n for n, f in enumerate(payload['fields'])}
        body['f']['k'] = [n for n in body['f']['k'] if n not in {fids[k] for k in replaced}]
        body['f']['r'] = sorted(fids[k] for k in replaced)
        sids = {row['slot']: n for n, row in enumerate(payload['slots'])}
        body['x'] = [change(payload, fids, sids) for change in changes]
        return body

    def test_rr3_04_a_relabel_never_creates_a_signature_or_identity_label(self):
        """'Reviewed by' relabelled to the printed word 'signature' was adopted: the identity rule then held a place with
        no signing role, and the clinician could not rename it back."""
        for n, text in enumerate(('Reviewed by: ______    Consultant signature: ______', 'Reviewed by: ______ (signature)')):
            with self.subTest(text=text):
                template, version = self.uploaded(data=lines(text, 'Plan: ______'), name='Synthetic RR3-04 %d' % n)
                reviewed = next(f for f in version.fields if f['label'].startswith('Reviewed by'))
                at = text.index('signature')
                result = self.proposal(version, replaced=[reviewed['key']],
                                       changes=[self.relabel(reviewed['key'], 'b/p[1]', reviewed['kind'], at, at + 9)])
                self.assertEqual(result['review']['changes'], [])
                self.assertEqual(next(f for f in result['fields'] if f['key'] == reviewed['key']), reviewed)
                self.assertIn(mapping.SIGNING_LABEL, ' '.join(r['reason'] for r in result['review']['unresolved']))

    def test_rr3_03_an_adopted_relabel_beside_an_inline_control_can_be_resolved_and_confirmed(self):
        """The resolution re-validated overlaps the engine's own mapping already had (a span beside an inline control on
        one line), so the adopted Weight relabel refused every resolution and the mapping could never be confirmed."""
        doc = Document(); doc.add_heading('Clinic record', level=2)
        p = doc.add_paragraph('Hospital number: ')
        sdt = OxmlElement('w:sdt'); pr = OxmlElement('w:sdtPr'); pr.append(OxmlElement('w:text')); sdt.append(pr)
        content = OxmlElement('w:sdtContent'); r = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text = ''
        r.append(t); content.append(r); sdt.append(content); p._p.append(sdt)
        p.add_run('    Weight: ______ kg')
        doc.add_paragraph('Plan: ______')
        template, version = self.uploaded(data=saved(doc), name='Synthetic RR3-03')
        weight = self.by_label(version)['Weight']
        compiled = mapping.compile_request(version, self.config)
        payload = json.loads(compiled['request']['messages'][0]['content'])
        source = next(row['text'] for row in payload['slots'] if row['slot'] == BODY + 'b/p[1]')
        at = source.index('Weight')
        state, new = self.run_job(version, self.body(version, [weight['key']], [
            self.relabel(weight['key'], 'b/p[1]', weight['kind'], at, at + 6)]))
        self.assertEqual(state, 'succeeded')
        self.assertEqual(next(f for f in new.fields if f['key'] == weight['key'])['origin'], 'model_assisted')
        mapped = v3_mapping.mapped_slots(new.fields)
        post = {'action': 'resolve', 'mapping_version': str(new.pk)}
        post.update({'resolution_%d' % n: 'mapped' if row.get('slot') and v3_mapping.is_mapped(row['slot'], mapped)
                     else 'not_answer' for n, row in enumerate(new.assistance.get('unresolved', []))})
        if new.assistance.get('unresolved'):
            self.assertEqual(self.client.post(f'/templates/{template.pk}/assistance/', post).status_code, 302)
        latest = self.latest(template)
        response = self.client.post(f'/templates/{template.pk}/', {'action': 'v3_confirm', 'mapping_version': latest.pk,
                                                                   'checked_every_field': 'on'})
        self.assertEqual(response.status_code, 302)


class SignerNounsInStep(TestCase):
    def test_the_parsers_clinician_signers_are_core_v3_actors_care_nouns(self):
        """The isolated parser keeps its own copy of the clinician nouns (it cannot import core): they must not drift."""
        from core.v3_actors import CARE_NOUNS
        self.assertEqual(word_v3.CARE_SIGNERS, CARE_NOUNS)
