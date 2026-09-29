"""CHECK.md N6: walk every notes case through the ACTUAL app path, offline, with a mocked provider.

upload (the case's real synthetic .docx) -> inspect/mapping (the stored v3 mapping must equal the fields cases.json
carries) -> confirm -> new encounter with the case's notes -> quote -> generate (anthropic.Anthropic patched: the mock
returns the case's REFERENCE selection, built against the request the application actually sent) -> worker ->
validation/adoption -> review page -> save (supported answers kept and reviewed; held/missing fields "Leave blank -
reviewed") -> finalize -> export (only word/document.xml may change; every adopted answer is in its own field).

It records, per case and sent path, the request the application built, every field's adopted status/text, what the
review page shows, whether finalize/export succeeded, and whether each field's app-path outcome equals the
generation-layer replay's reference observation (offline_replay.py). A difference is a finding, never a failure
of the walk. Exports stay in the test's temporary directory and only their sha256 is kept.

Run it with run_app_path_walk.py (a quillmd_qa_diag_* test database on the campaign QA PostgreSQL); never directly
against any other database. Python sockets are denied in every test (positive control asserted); the database
driver connects through libpq, not Python sockets.

The steps that must stay identical to the campaign's live ordinary_notes stage (the path flags, the reference answer,
the review save, the export verification) live in app_path_steps.py, which both import (2026-09-29 re-freeze).
"""
import copy
import hashlib
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings
from lxml import html

from core.jobs import run_one
from core.models import Encounter, Job
from core.security import private_path
from core.tests.test_v3_field_relations_workflow import sdk_response
from core.tests.test_v3_ordinary_notes import LIVE
from core.tests.test_word_v3_workflow import V3Fixture

import app_path_steps as steps

NOTES_DIR = Path(os.environ['NOTES_DIR'])
CASES = json.loads((NOTES_DIR / 'cases.json').read_text())
OBSERVATIONS_PATH = Path(os.environ.get('NOTES_OBSERVATIONS', NOTES_DIR / 'offline-observations.json'))
OBSERVATIONS = json.loads(OBSERVATIONS_PATH.read_text()) if OBSERVATIONS_PATH.exists() else {}
OUT = Path(os.environ['NOTES_WALK_OUT'])
PATH_SETTINGS = {path: dict(LIVE, **flags) for path, flags in steps.PATH_FLAGS.items()}


class NotesAppPath(V3Fixture, TestCase):
    def setUp(self):
        super().setUp()
        deny = patch('socket.socket.connect', side_effect=AssertionError('External Python network denied'))
        deny.start()
        self.addCleanup(deny.stop)
        try:
            socket.create_connection(('127.0.0.1', 9), timeout=1)
        except AssertionError:
            self.network = 'denied (positive control: create_connection raised the denial)'
        else:
            raise AssertionError('network denial positive control failed')

    def walk(self, cid, path):
        case = next(c for c in CASES['cases'] if c['id'] == cid)
        form = CASES['forms'][case['form']]
        original = (Path(form['runtime_dir']) / form['docx']).read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), form['sha256'])
        result = {'case': cid, 'path': path, 'form': case['form'], 'form_sha256': form['sha256'],
                  'network': self.network, 'http': [], 'workflow_success': False}

        def stage(name, response):
            result['http'].append({'stage': name, 'status': response.status_code})
            return response
        try:
            with override_settings(**PATH_SETTINGS[path]):
                template, version = self.uploaded(data=original, name='SYNTHETIC NOTES %s %s' % (cid, path))
                result['mapping_equals_cases_json'] = version.fields == form['fields']
                self.assertTrue(result['mapping_equals_cases_json'], 'stored mapping differs from cases.json fields')
                stage('mapping-review', self.client.get(f'/templates/{template.pk}/'))
                self.confirm(template, version)
                stage('new-encounter', self.new_encounter(version, notes=case['notes']))
                encounter = Encounter.objects.latest('created_at')
                self.assertEqual(encounter.notes, case['notes'])
                page = stage('before-generation', self.client.get(f'/encounters/{encounter.pk}/'))
                result['quote_error'] = page.context.get('generation_quote_error')
                quote = page.context['usage_quote']
                reference = steps.reference_selection(case, path)
                captured = []

                def respond(**wire):
                    captured.append(wire)
                    payload = json.loads(wire['messages'][0]['content'])
                    answer, units = steps.reference_answer(case['notes'], version.fields, payload, reference)
                    if units is not None:
                        self.assertEqual(units['sent'], units['expected'],
                                         'the request carries different source units than the replay')
                    result.setdefault('requests', []).append(steps.request_summary(wire))
                    return sdk_response(answer)

                with patch('anthropic.Anthropic') as provider:
                    provider.return_value.messages.create.side_effect = respond
                    stage('generate', self.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': quote}))
                    jobs = list(Job.objects.filter(encounter=encounter))
                    if jobs:
                        result['worker_ran'] = run_one()
                    result['provider_calls'] = provider.return_value.messages.create.call_count
                jobs = list(Job.objects.filter(encounter=encounter))
                result['jobs'] = [{'state': j.state, 'error': j.error} for j in jobs]
                if not jobs or any(j.state != 'succeeded' for j in jobs):
                    result['failure_boundary'] = 'generation admission' if not jobs else 'worker'
                    return result
                encounter.refresh_from_db()
                generated = copy.deepcopy(encounter.answers)
                result['fields'] = steps.field_outcomes(generated)
                replay = (((OBSERVATIONS.get('cases') or {}).get(cid) or {}).get('reference') or {}).get(path, {}).get('fields', {})
                result['agrees_with_generation_layer_replay'] = {
                    k: (replay[k]['status'], replay[k]['text']) == (v['status'], v['text']) if k in replay else None
                    for k, v in result['fields'].items()}
                page = stage('generated-review', self.client.get(f'/encounters/{encounter.pk}/'))
                result['review_rows'] = {row['key']: row.get('status') for row in page.context['answer_rows']}
                controls = set(html.fromstring(page.content).xpath('//*[@name]/@name'))
                payload = steps.review_payload(version.fields, generated, controls, encounter.revision,
                                               version.review_requirements)
                saved = stage('save-review', self.client.post(f'/encounters/{encounter.pk}/save/', payload))
                if saved.status_code != 302:
                    result['failure_boundary'] = 'review save'
                    return result
                encounter.refresh_from_db()
                stage('finalize', self.client.post(f'/encounters/{encounter.pk}/finalize/',
                                                   {'revision': encounter.revision, 'reviewed': 'on'}))
                encounter.refresh_from_db()
                result['encounter_status'] = encounter.status
                if encounter.status != 'finalized':
                    page = stage('finalize-refusal', self.client.get(f'/encounters/{encounter.pk}/'))
                    result['finalize_messages'] = [str(m) for m in page.context.get('messages', [])][:5]
                    result['failure_boundary'] = 'finalization'
                    return result
                download = stage('export', self.client.get(f'/encounters/{encounter.pk}/export/'))
                exported = b''.join(download.streaming_content)
                result['export_sha256'] = hashlib.sha256(exported).hexdigest()
                self.assertEqual(result['export_sha256'], encounter.export_sha256)
                self.assertEqual(private_path(template.original_path).read_bytes(), original)
                result.update(steps.export_verification(original, exported, version.fields, result['fields']))
                return result
        except Exception as error:
            result['exception'] = type(error).__name__ + ': ' + str(error)[:500]
            raise
        finally:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / ('%s-%s.json' % (cid, path))).write_text(json.dumps(result, indent=1, ensure_ascii=False))


def _make(cid, path):
    def test(self):
        self.walk(cid, path)
    test.__name__ = 'test_%s_%s' % (cid, path)
    return test


for _case in CASES['cases']:
    for _path in _case['send_paths']:
        _test = _make(_case['id'], _path)
        setattr(NotesAppPath, _test.__name__, override_settings(**PATH_SETTINGS[_path])(_test))
