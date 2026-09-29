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
"""
import copy
import hashlib
import io
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from django.test import TestCase, override_settings
from lxml import html

from core import generation as g
from core.jobs import run_one
from core.models import Encounter, Job
from core.security import private_path
from core.tests.test_v3_field_relations_workflow import sdk_response
from core.tests.test_v3_ordinary_notes import LIVE
from core.tests.test_word_v3_workflow import V3Fixture
from documents import word_v3 as w

NOTES_DIR = Path(os.environ['NOTES_DIR'])
CASES = json.loads((NOTES_DIR / 'cases.json').read_text())
OBSERVATIONS_PATH = Path(os.environ.get('NOTES_OBSERVATIONS', NOTES_DIR / 'offline-observations.json'))
OBSERVATIONS = json.loads(OBSERVATIONS_PATH.read_text()) if OBSERVATIONS_PATH.exists() else {}
OUT = Path(os.environ['NOTES_WALK_OUT'])
PATH_SETTINGS = {'default': dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False,
                                 V3_GENERATION_BATCHES=False, WM_NARRATIVE=False),
                 'field_relations': dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True,
                                         V3_GENERATION_BATCHES=False, WM_NARRATIVE=False)}


def applies(selection, path):
    return path in selection.get('paths', ('default', 'field_relations'))


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
                reference = {k: next(s for s in e['raw_model_expectation']['acceptable'] if applies(s, path))
                             for k, e in case['fields'].items()}
                captured = []

                def respond(**wire):
                    captured.append(wire)
                    payload = json.loads(wire['messages'][0]['content'])
                    fields = version.fields
                    asked, context, _ = g.v3_generation_fields(fields)
                    units = g.source_units(case['notes'], asked, context_labels=context)[0]
                    by_quote = {u['quote']: u['id'] for u in units}
                    if 'catalogue' in payload:
                        from core import v3_field_relations as rel
                        body = []
                        for f in asked:
                            s = reference.get(f['key'], {})
                            ids = [by_quote[q] for q in s.get('units', [])]
                            options = {o['text']: o['id'] for o in rel.options(f)}
                            body.append({'key': f['key'], 'unit_ids': ids, 'conflict': bool(s.get('conflict')),
                                         'option_ids': [options[t] for t in s.get('options', [])],
                                         'context': ['answer' if u['id'] in ids else
                                                     s.get('relations', {}).get(u['quote'], 'independent') for u in units]})
                        answer = {'fields': body}
                    else:
                        sent = {u['quote']: u['id'] for u in payload['source_units']}
                        self.assertEqual(sent, by_quote, 'the request carries different source units than the replay')
                        keys = [q['key'] for q in payload['questions']]
                        answer = {'fields': [{'key': k, 'unit_ids': [sent[q] for q in reference.get(k, {}).get('units', [])],
                                              'conflict': bool(reference.get(k, {}).get('conflict'))} for k in keys]}
                    result.setdefault('requests', []).append({
                        'payload_keys': sorted(payload), 'relations_payload': 'catalogue' in payload,
                        'questions': len(payload.get('questions') or []), 'source_units': len(payload.get('source_units') or []),
                        'catalogue': len(payload.get('catalogue') or []), 'max_tokens': wire.get('max_tokens'),
                        'model': wire.get('model'), 'request_bytes': len(json.dumps(wire).encode())})
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
                state = {'conflict': 'held'}
                result['fields'] = {k: {'status': state.get(v['status'], v['status']), 'text': v.get('text', '')}
                                    for k, v in generated.items()}
                replay = (((OBSERVATIONS.get('cases') or {}).get(cid) or {}).get('reference') or {}).get(path, {}).get('fields', {})
                result['agrees_with_generation_layer_replay'] = {
                    k: (replay[k]['status'], replay[k]['text']) == (v['status'], v['text']) if k in replay else None
                    for k, v in result['fields'].items()}
                page = stage('generated-review', self.client.get(f'/encounters/{encounter.pk}/'))
                result['review_rows'] = {row['key']: row.get('status') for row in page.context['answer_rows']}
                controls = set(html.fromstring(page.content).xpath('//*[@name]/@name'))
                payload = {'revision': encounter.revision}
                for f in version.fields:
                    value = generated.get(f['key'], {})
                    text = value.get('text', '') if value.get('status') == 'supported' else ''
                    if 'answer_' + f['key'] in controls:
                        payload['answer_' + f['key']] = text
                    if 'reviewed_' + f['key'] in controls:
                        payload['reviewed_' + f['key']] = 'on'
                    if not text and 'blank_' + f['key'] in controls:
                        payload['blank_' + f['key']] = 'on'
                for requirement in version.review_requirements:
                    payload['requirement_' + requirement['key']] = 'on'
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
                with ZipFile(io.BytesIO(original)) as a, ZipFile(io.BytesIO(exported)) as b:
                    result['zip_members_unchanged'] = a.namelist() == b.namelist()
                    result['changed_parts'] = [p for p in a.namelist() if a.read(p) != b.read(p)]
                new = w.SlotIndex(w.open_package(exported))
                written = {}
                for f in version.fields:
                    text = result['fields'].get(f['key'], {}).get('text', '')
                    if result['fields'].get(f['key'], {}).get('status') != 'supported' or not text:
                        continue
                    target = new.by_id[f['locator']['part'] + '#' + f['locator']['slot']]
                    exported_text = w.text_of(target.el)
                    written[f['key']] = (text in exported_text) or (f['kind'] in ('choice', 'checkbox'))
                result['supported_answers_in_their_fields'] = written
                result['workflow_success'] = (result['zip_members_unchanged'] and set(result['changed_parts']) <= {'word/document.xml'}
                                              and all(written.values()))
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
