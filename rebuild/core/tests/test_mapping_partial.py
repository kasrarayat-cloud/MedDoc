"""The retained live Sonnet 5 mapping response (synthetic form f1, campaign attempt 2) through the real app path.

The fixture pair in fixtures/mapping_live_f1/ is the exact request body that was sent and the exact provider result
that came back; both are synthetic (the frozen diagnostic form f1, blank, no patient data). The original .docx is not
tracked: it is rebuilt byte for byte by the frozen generator (docs/rebuild/v1/sonnet5-campaign/diagnostics/mapping/
build_forms.py) and its sha256 must equal the request's own source_sha256 before anything else runs.

What the response did: change 0 [0,3,0,3,0,79,-1] took its label from reference 3 = [2,0,0] (slot 2's text) for a
replacement at slot 3, and change 1 [1,7,2,6,0,40,-1] targeted slot 7 (the question paragraph, not field 1's answer
cell) with reference 6 = [3,1,0]. Both are individually invalid. Before this repair the first one raised
'Source text belongs to another destination.' and the WHOLE proposal was refused. The design (model-assisted-mapping.md
step 4) keeps the existing field for a rejected replacement and retains the rejection as an unresolved review record
that blocks confirmation. Native transports are always mocked; no request leaves this process.
"""
import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.utils import timezone
from core import generation, jobs, mapping_assistance as mapping, mapping_jobs, mapping_wire as wire, v3_mapping
from core.billing import welcome_credit
from core.models import Department, Membership, Organization, Template, TemplateVersion, User
from core.security import private_path
from core.tests.test_mapping_assistance import SETTINGS
from documents.service import inspect_template

REPOSITORY = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'mapping_live_f1'
BUILD_FORMS = REPOSITORY / 'docs' / 'rebuild' / 'v1' / 'sonnet5-campaign' / 'diagnostics' / 'mapping' / 'build_forms.py'


def f1_original():
    """The frozen, byte-deterministic synthetic f1 form (no engine, no network)."""
    spec = importlib.util.spec_from_file_location('sonnet5_mapping_build_forms', BUILD_FORMS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.f1_guidance_confirmation()


def native(result):
    """The retained Messages result as the SDK object the worker reads (attributes, usage, model_dump)."""
    usage = result['usage']
    return SimpleNamespace(model=result['model'], stop_reason=result['stop_reason'],
                           content=[SimpleNamespace(**block) for block in result['content']],
                           id=result['id'], _request_id='req_retained_fixture',
                           usage=SimpleNamespace(input_tokens=usage['input_tokens'], output_tokens=usage['output_tokens'],
                                                 cache_read_input_tokens=0, cache_creation_input_tokens=0),
                           model_dump=lambda **kwargs: copy.deepcopy(result))


def strip_presentation(payload):
    """The payload without the per-slot/per-field reference lists this repair adds (everything else is compared)."""
    payload = copy.deepcopy(payload)
    for row in payload['slots']:
        row.pop('refs', None)
    for field in payload['fields']:
        field.pop('label_ref', None)
    return payload


@override_settings(**SETTINGS)
class RetainedLiveResponse(TestCase):
    def setUp(self):
        deny = patch('anthropic.Anthropic', side_effect=AssertionError('Unmocked provider construction is forbidden in offline tests.'))
        deny.start(); self.addCleanup(deny.stop)
        self.directory = tempfile.TemporaryDirectory(prefix='mapping-partial-')
        self.addCleanup(self.directory.cleanup)
        override = override_settings(MEDIA_ROOT=Path(self.directory.name)); override.enable(); self.addCleanup(override.disable)
        self.request = json.loads((FIXTURES / 'request.json').read_text())
        self.result = json.loads((FIXTURES / 'provider-result.json').read_text())
        self.body = self.request['body_json']
        self.payload = json.loads(self.body['messages'][0]['content'])
        self.original = f1_original()
        self.assertEqual(hashlib.sha256(self.original).hexdigest(), self.payload['source_sha256'])
        self.user = User.objects.create_user(username='partial', email='partial@synthetic.invalid', verified_at=timezone.now())
        self.org = Organization.objects.create(name='Synthetic partial mapping')
        self.department = Department.objects.create(organization=self.org, name='Synthetic partial mapping')
        Membership.objects.create(user=self.user, department=self.department, role='clinician')
        welcome_credit(self.user)
        path = private_path('originals/f1.docx'); path.parent.mkdir(parents=True); path.write_bytes(self.original)
        info = inspect_template(path, engine='v3')
        self.template = Template.objects.create(department=self.department, name='Synthetic f1', format='docx',
            original_name='f1.docx', original_path='originals/f1.docx', sha256=info['sha256'], created_by=self.user)
        self.version = TemplateVersion.objects.create(template=self.template, number=1, fields=info['fields'],
                                                      contract='v3', created_by=self.user)
        self.client.force_login(self.user)

    def retained(self):
        return {'request': self.body, 'request_sha256': mapping.digest(self.body),
                'profile_sha256': self.payload['profile_sha256']}

    def own_slot(self, key):
        field = next(f for f in self.version.fields if f['key'] == key)
        return next(iter(sorted(v3_mapping.mapped_slots([field]))))

    def test_the_retained_request_is_this_form_and_version(self):
        # The version rebuilt here is the one the live request was compiled from: same slots, fields and catalog.
        self.assertEqual([f['key'] for f in self.payload['fields']], [f['key'] for f in self.version.fields])
        self.assertEqual([f['slots'] for f in self.payload['fields']],
                         [sorted(v3_mapping.mapped_slots([f])) for f in self.version.fields])
        self.assertEqual(self.payload['text_refs'], wire.catalog(self.payload))
        compiled = mapping.compile_request(self.version, generation.configuration())
        now = json.loads(compiled['request']['messages'][0]['content'])
        # The one profile difference is its recorded name (the new prompt/payload version); nothing else in it moved.
        self.assertEqual(compiled['profile']['profile'], mapping.PROFILE)
        self.assertNotEqual(mapping.PROFILE, 'claude-sonnet-5-blank-mapping-v3')
        self.assertEqual(mapping.digest({**compiled['profile'], 'profile': 'claude-sonnet-5-blank-mapping-v3'}),
                         self.payload['profile_sha256'])
        self.assertEqual(now['profile_sha256'], compiled['profile_sha256'])
        # Additive only: without the new per-slot/per-field lists the payload is the retained one — every slot, field,
        # catalog entry and so every existing ID is identical.
        self.assertEqual({**strip_presentation(now), 'profile_sha256': self.payload['profile_sha256']}, self.payload)
        self.assertEqual(now['text_refs'], self.payload['text_refs'])
        # So the retained answer means exactly the same thing against today's request.
        answer = json.loads(self.result['content'][0]['text'])
        self.assertEqual(wire.expand(now, copy.deepcopy(answer)), wire.expand(self.payload, copy.deepcopy(answer)))
        # The per-slot lists are the catalog positions, and the ones the live response confused are visible: slot 3
        # lists 5/6/7 (its text/heading/row_label), never 3 (slot 2's text).
        slots, labels = wire.presented(now)
        self.assertEqual([row['refs'] for row in now['slots']], slots)
        self.assertEqual([f['label_ref'] for f in now['fields']], labels)
        self.assertEqual(now['slots'][3]['refs'], {'text': 5, 'heading': 6, 'row_label': 7})
        self.assertEqual(now['slots'][8]['refs'], {'heading': 17, 'row_label': 18})
        self.assertEqual(labels, [22, 23])
        self.assertIn(wire.INSTRUCTIONS, compiled['request']['system'])
        self.assertNotEqual(compiled['request']['system'], self.body['system'])
        # The quote still prices exactly this (larger) request under the unchanged pricing rule.
        self.assertEqual(compiled['input_token_bound'], len(mapping.canonical(compiled['request']).encode()) + 12000)

    def test_live_response_keeps_every_field_and_holds_both_rejected_changes(self):
        parsed = mapping_jobs.parse_response(native(self.result), False)
        self.assertEqual(parsed, json.loads(self.result['content'][0]['text']))
        result = mapping.validate_proposal(self.version, self.retained(), parsed)
        # No field changed, nothing adopted.
        self.assertEqual(result['fields'], self.version.fields)
        review = result['review']
        self.assertEqual(review['changes'], [])
        # Both replacements were rejected: each field is kept and its verdict is uncertain, with no target.
        verdicts = {v['key']: v for v in review['verdicts']['fields']}
        self.assertEqual({k: v['verdict'] for k, v in verdicts.items()}, {'v3_1': 'uncertain', 'v3_2': 'uncertain'})
        self.assertTrue(all(v['target'] is None for v in verdicts.values()))
        self.assertEqual(review['verdicts']['additions'], [])
        # The other verdicts are kept exactly as returned.
        returned = {self.payload['slots'][sid]['slot']: verdict for code, verdict in
                    (('c', 'covered'), ('n', 'not_answer'), ('u', 'uncertain')) for sid in parsed['s'][code]}
        self.assertEqual({v['slot']: v['verdict'] for v in review['verdicts']['slots']}, returned)
        # Every rejection is recorded in the stored proposal with its wire change and reason.
        slots = [row['slot'] for row in self.payload['slots']]
        rejected = review['rejected_changes']
        self.assertEqual([(r['change'], r['wire'], r['type'], r['key'], r['slot']) for r in rejected],
                         [(0, [0, 3, 0, 3, 0, 79, -1], 'replacement', 'v3_1', slots[3]),
                          (1, [1, 7, 2, 6, 0, 40, -1], 'replacement', 'v3_2', slots[7])])
        self.assertIn('Source text belongs to another destination.', rejected[0]['reason'])
        self.assertIn('Replacement target belongs to another field destination.', rejected[1]['reason'])
        # Each field is held by a KEYED unresolved record on its own destination (so 'I checked its mapped answer
        # field' keeps it and 'not an answer' removes it), naming the proposed slot and the reason.
        keyed = {row['key']: row for row in review['unresolved'] if row['key']}
        self.assertEqual(set(keyed), {'v3_1', 'v3_2'})
        for rejection in rejected:
            record = keyed[rejection['key']]
            self.assertEqual(record['slot'], self.own_slot(rejection['key']))
            self.assertEqual(record['proposed_slot'], rejection['slot'])
            self.assertIn(rejection['reason'], record['reason'])
            self.assertIn(rejection['slot'], record['reason'])
        # The covered-but-unmapped question paragraph and the two uncertain slots stay visible too.
        self.assertTrue({slots[4], slots[7], slots[8]} <= {row['slot'] for row in review['unresolved'] if not row['key']})

    @override_settings(AI_MODE='live', QUILLMD_MAPPING_ASSISTANCE_LIVE=True)
    def test_worker_adopts_nothing_and_confirmation_is_blocked_until_resolved(self):
        config = generation.configuration()
        compiled = mapping.compile_request(self.version, config)
        job = mapping_jobs.enqueue(self.version, self.user, config, compiled['request_sha256'])
        with patch('anthropic.Anthropic') as client:
            # The retained answer text, unchanged, against today's request: every ID in it means what it meant.
            client.return_value.messages.create.return_value = native(self.result)
            self.assertTrue(jobs.run_one())
        client.return_value.messages.create.assert_called_once()
        job.refresh_from_db(); self.assertEqual(job.state, 'succeeded', job.error)
        latest = self.template.versions.latest('number')
        self.assertNotEqual(latest.pk, self.version.pk)
        self.assertEqual(latest.fields, self.version.fields)
        self.assertEqual(len(latest.assistance['rejected_changes']), 2)
        self.assertEqual({row['key'] for row in latest.assistance['unresolved'] if row['key']}, {'v3_1', 'v3_2'})
        response = self.client.post(f'/templates/{self.template.pk}/', {'action': 'v3_confirm',
                                    'mapping_version': latest.pk, 'checked_every_field': 'on'})
        self.assertEqual(response.status_code, 400)
        # The records are resolvable without losing a field: "mapped" on each keyed record keeps the field.
        mapped = v3_mapping.mapped_slots(latest.fields)
        body = {'action': 'resolve', 'mapping_version': str(latest.pk)}
        for number, row in enumerate(latest.assistance['unresolved']):
            body['resolution_' + str(number)] = 'mapped' if v3_mapping.is_mapped(row['slot'], mapped) else 'not_answer'
            if row['key']:
                self.assertEqual(body['resolution_' + str(number)], 'mapped')
        self.assertEqual(self.client.post(f'/templates/{self.template.pk}/assistance/', body).status_code, 302)
        resolved = self.template.versions.latest('number')
        self.assertEqual(resolved.fields, self.version.fields)
        self.assertEqual(resolved.assistance['unresolved'], [])
        self.assertEqual(len(resolved.assistance['rejected_changes']), 2)
