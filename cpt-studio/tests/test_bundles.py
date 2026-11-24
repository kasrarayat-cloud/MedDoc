"""Release 1, D2: returning a document's or a whole practice's data (studio.record_bundle, studio.bundle_api and the
export_workspace command).

- A member's bundle of one document: the original, the converted PDF of a Word document, the latest report, record.json
  - whose document block IS the app's own payload, and whose rounds are what the app shows of each - and manifest.json,
  whose sha256s verify. Nothing of another document or practice enters it.
- Another practice's document answers 404 with a refused row; over the cap 413 with the sentence; the eleventh bundle in
  ten minutes 429; a read that cannot be recorded 503 with nothing of the document in it.
- The practice export holds every document of one practice and nothing of the other.

Synthetic practices only, on originals and export folders of the tests' own."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import stat
import tempfile
import uuid
import zipfile
from pathlib import Path
from unittest import mock

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from studio import audit, bundle_api, jobs, models, rate, read_audit, record_bundle
from studio.fable import document as fable_document
from tests.support import coding as f
from tests.support import rounds

Round, Access = models.CodingRound, models.AccessRecord
DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
DOCX_BYTES = b'PK\x03\x04 synthetic word bytes, never opened by the tests'
CONVERTED = b'%PDF-1.7\n% the synthetic conversion of a Word file\n%%EOF\n'


def unzip(data) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


class BundleCase(rounds.CustomerCase):
    def coded(self, *, ws=None, member=None, marker='X'):
        """A coded PDF document: two rounds (the second after an answer), a decision on each, and a report."""
        ws, member = ws or self.ws, member or self.reviewer
        enc = f.encounter(ws, member, service_date='2026-11-02', insurance='medicare',
                          title=f'ZZ-TITLE-MARKER-{marker}')
        f.upload(enc, member, data=f.PDF_BYTES + f'ZZ-TEXT-MARKER-{marker}'.encode(),
                 filename=f'zz-file-marker-{marker}.pdf')
        audit.record(ws, 'encounter.created', encounter=enc, actor=member, kind='upload')
        jobs.start_round(enc, enc.current_revision, Round.UPLOAD, member)
        self.code_round(enc)
        self.assertEqual(self.decide(enc, 'L1', '45385', 'approve', user=member, note=f'ZZ-NOTE-{marker}').status_code,
                         201)
        client = self.client_for(member)
        question = client.get(f'/api/encounters/{enc.pk}').json()['questions'][0]['id']
        self.assertEqual(client.post(f'/api/encounters/{enc.pk}/answers', json.dumps(
            {'answers': [{'question_id': question, 'text': f'ZZ-ANSWER-MARKER-{marker}'}]}),
            content_type='application/json').status_code, 201)
        self.code_round(enc)
        self.assertEqual(self.decide(enc, 'L3', '43239', 'reject', user=member).status_code, 201)
        self.assertEqual(client.post(f'/api/encounters/{enc.pk}/reports', json.dumps(
            {'kind': 'draft', 'fmt': 'pdf', 'round': 2}), content_type='application/json').status_code, 201)
        enc.refresh_from_db()
        return enc

    def word(self, *, ws=None, member=None, marker='W'):
        ws, member = ws or self.ws, member or self.reviewer
        enc = f.encounter(ws, member, title=f'ZZ-TITLE-MARKER-{marker}')
        f.upload(enc, member, data=DOCX_BYTES + marker.encode(), filename=f'zz-file-marker-{marker}.docx',
                 media_type=DOCX)
        jobs.start_round(enc, enc.current_revision, Round.UPLOAD, member)
        with mock.patch.object(fable_document, 'convert_docx', return_value=CONVERTED + marker.encode()):
            self.code_round(enc)
        return enc

    def get_bundle(self, enc, user=None, **headers):
        return self.client_for(user or self.reviewer).get(f'/api/encounters/{enc.pk}/bundle', **headers)


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class DocumentBundleTests(BundleCase, TestCase):
    def test_the_bundle_holds_the_document_and_its_json_is_the_apps_own(self):
        enc = self.coded()
        client = self.client_for(self.reviewer)
        moment = timezone.now()
        with mock.patch('django.utils.timezone.now', return_value=moment):
            app = client.get(f'/api/encounters/{enc.pk}').json()
            answer = client.get(f'/api/encounters/{enc.pk}/bundle')
        self.assertEqual(answer.status_code, 200)
        self.assertEqual(answer['Content-Type'], 'application/zip')
        self.assertEqual(answer['Content-Disposition'], f'attachment; filename="cpt-studio-document-{enc.pk}.zip"')
        files = unzip(answer.content)
        export = models.ExportArtifact.objects.get(encounter=enc)
        self.assertEqual(sorted(files), sorted(['original/zz-file-marker-X.pdf', f'reports/{export.filename}',
                                                'record.json', 'manifest.json']))
        self.assertEqual(files['original/zz-file-marker-X.pdf'], f.PDF_BYTES + b'ZZ-TEXT-MARKER-X')
        self.assertEqual(files[f'reports/{export.filename}'], bytes(export.content))
        record = json.loads(files['record.json'])
        self.assertEqual(record['document'], app)  # the app's own payload, byte for byte as JSON
        self.assertEqual(record['format'], record_bundle.FORMAT)
        self.assertEqual([item['number'] for item in record['rounds']], [1, 2])
        self.assertEqual(record['rounds'][-1]['codes'], app['codes'])  # the latest round as the page shows it
        self.assertTrue(all(code['quotes'] for code in record['rounds'][0]['codes']))  # the citations, as shown
        self.assertEqual([(row['line'], row['code'], row['action'], row['note']) for row in record['rounds'][0]['decisions']],
                         [('L1', '45385', 'approve', 'ZZ-NOTE-X')])
        self.assertEqual([row['action'] for row in record['rounds'][1]['decisions']], ['reject'])
        self.assertTrue(all(row['by'] == self.reviewer.label() and row['at'] for round_ in record['rounds']
                            for row in round_['decisions']))
        self.assertEqual([row['answer'] for row in record['rounds'][0]['answers']], ['ZZ-ANSWER-MARKER-X'])
        self.assertEqual(record['document']['activity'], app['activity'])
        manifest = json.loads(files['manifest.json'])
        self.assertEqual(manifest['document'], str(enc.pk))
        self.assertEqual({item['path'] for item in manifest['files']}, set(files) - {'manifest.json'})
        for item in manifest['files']:  # the sha256s verify
            with self.subTest(path=item['path']):
                self.assertEqual((len(files[item['path']]), hashlib.sha256(files[item['path']]).hexdigest()),
                                 (item['bytes'], item['sha256']))
        (row,) = Access.objects.filter(view=read_audit.MEMBER_BUNDLE_DOWNLOAD)
        self.assertEqual((row.outcome, row.workspace_id, row.encounter_ids, row.actor_id, row.actor_role),
                         (read_audit.SERVED, self.ws.pk, [str(enc.pk)], self.reviewer.pk, models.Membership.REVIEWER))

    def test_a_word_documents_bundle_holds_its_converted_pdf(self):
        enc = self.word()
        files = unzip(self.get_bundle(enc).content)
        self.assertEqual(files['original/zz-file-marker-W.docx'], DOCX_BYTES + b'W')
        self.assertEqual(files['converted/zz-file-marker-W.pdf'], CONVERTED + b'W')
        self.assertNotIn('reports', ' '.join(files))  # no report was made

    def test_a_pasted_documents_bundle_holds_its_text(self):
        enc = self.done(pdf=False)
        files = unzip(self.get_bundle(enc).content)
        self.assertEqual(files['original/pasted-text.txt'], f.NOTE.encode('utf-8'))

    def test_every_view_of_the_bundle_is_recorded_and_each_download_writes_its_row(self):
        enc = self.coded()
        for _ in range(3):
            self.assertEqual(self.get_bundle(enc).status_code, 200)
        self.assertEqual(Access.objects.filter(view=read_audit.MEMBER_BUNDLE_DOWNLOAD, outcome='served').count(), 3)

    def test_the_bundle_is_marked_as_a_read_and_keeps_the_csrf_check(self):
        from django.urls import resolve
        callback = resolve(f'/api/encounters/{uuid.uuid4()}/bundle').func
        self.assertEqual(read_audit.read_kind(callback), read_audit.MEMBER_BUNDLE_DOWNLOAD)
        self.assertFalse(getattr(callback, 'csrf_exempt', False))

    def test_signed_out_and_other_methods_serve_nothing(self):
        enc = self.coded()
        self.assertEqual(self.client.get(f'/api/encounters/{enc.pk}/bundle').status_code, 401)
        member = self.client_for(self.reviewer)
        for method in ('head', 'post', 'put', 'delete'):
            with self.subTest(method=method):
                self.assertEqual(getattr(member, method)(f'/api/encounters/{enc.pk}/bundle').status_code, 405)
        self.assertFalse(Access.objects.filter(view=read_audit.MEMBER_BUNDLE_DOWNLOAD).exists())


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class BundleRefusalTests(BundleCase, TestCase):
    def test_another_practices_document_answers_404_with_a_refused_row(self):
        enc = self.coded()
        unknown = self.client_for(self.outsider).get(f'/api/encounters/{uuid.uuid4()}/bundle')
        refused = self.get_bundle(enc, self.outsider)
        self.assertEqual((refused.status_code, refused.json()), (404, bundle_api.NOT_FOUND))
        self.assertEqual((unknown.status_code, unknown.content), (404, refused.content))  # the same answer
        (row,) = Access.objects.filter(view=read_audit.MEMBER_BUNDLE_DOWNLOAD)
        self.assertEqual((row.outcome, row.actor_id, row.encounter_ids, row.actor_role),
                         (read_audit.REFUSED, self.outsider.pk, [str(enc.pk)], ''))

    def test_a_refused_row_that_cannot_be_written_still_answers_the_same_404(self):
        enc = self.coded()
        with mock.patch.object(read_audit, 'record', side_effect=read_audit.NotRecorded(read_audit.NOT_RECORDED)):
            refused = self.get_bundle(enc, self.outsider)
        self.assertEqual((refused.status_code, refused.json()), (404, bundle_api.NOT_FOUND))

    def test_a_destroyed_document_answers_404(self):
        enc = self.coded()
        models.Encounter.objects.filter(pk=enc.pk).update(destroyed_at=timezone.now())
        self.assertEqual(self.get_bundle(enc).status_code, 404)
        self.assertFalse(Access.objects.exists())

    def test_over_the_cap_answers_413_with_the_sentence_and_records_nothing(self):
        enc = self.coded()
        with override_settings(BUNDLE_MAX_BYTES=2_000):
            answer = self.get_bundle(enc)
        self.assertEqual((answer.status_code, answer.json()['error']), (413, record_bundle.TOO_LARGE))
        self.assertEqual(record_bundle.TOO_LARGE, 'This document is too large for one bundle; download the original '
                                                  'and the report separately.')
        self.assertFalse(Access.objects.exists())

    def test_the_eleventh_bundle_in_ten_minutes_is_refused_per_member(self):
        enc = self.coded()
        limit, window = (10, 600)
        with override_settings(BUNDLE_LIMIT_PER_MEMBER=(limit, window)):
            for _ in range(limit):
                self.assertEqual(self.get_bundle(enc).status_code, 200)
            for _ in range(2):
                refused = self.get_bundle(enc)
                self.assertEqual(refused.status_code, 429)
                self.assertEqual(set(refused.json()), {'error', 'retry_after'})
                self.assertEqual(refused.json()['error'], 'rate_limited')
                self.assertTrue(0 < refused.json()['retry_after'] <= window)
                self.assertEqual(refused['Retry-After'], str(refused.json()['retry_after']))
            other = f.member(self.ws)
            self.assertEqual(self.get_bundle(enc, other).status_code, 200)  # per member
        (event,) = models.SecurityEvent.objects.filter(event=bundle_api.LIMITED_EVENT)  # the first refusal only
        self.assertEqual((event.actor_id, event.workspace_id, event.data), (self.reviewer.pk, self.ws.pk,
                                                                            {'limit': limit, 'window_seconds': window}))
        self.assertEqual(rate.count(bundle_api.RATE_SCOPE, str(self.reviewer.pk),
                                    since=rate.window_start(window)), limit + 2)
        self.assertEqual(Access.objects.filter(view=read_audit.MEMBER_BUNDLE_DOWNLOAD).count(), limit + 1)

    def test_a_read_that_cannot_be_recorded_serves_nothing(self):
        enc = self.coded()
        with mock.patch.object(read_audit.AccessRecord.objects, 'create', side_effect=RuntimeError('synthetic')):
            answer = self.get_bundle(enc)
        self.assertEqual((answer.status_code, answer.json()), (503, {'error': read_audit.NOT_RECORDED}))
        for marker in (b'ZZ-TITLE-MARKER', b'ZZ-TEXT-MARKER', b'ZZ-ANSWER-MARKER', b'zz-file-marker', b'%PDF', b'PK'):
            self.assertNotIn(marker, answer.content)

    def test_a_stored_file_that_changed_answers_409_and_records_nothing(self):
        enc = self.coded()
        path = Path(self._originals.name) / enc.files.get().storage_name
        path.write_bytes(b'%PDF-1.7 changed on the disk %%EOF')
        answer = self.get_bundle(enc)
        self.assertEqual(answer.status_code, 409)
        self.assertFalse(Access.objects.exists())


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class IsolationTests(BundleCase, TestCase):
    def test_a_bundle_holds_nothing_of_another_document_or_practice(self):
        mine = self.coded(marker='MINE')
        neighbour = self.coded(marker='NEXT')  # same practice
        foreign = self.coded(ws=self.other_ws, member=self.outsider, marker='FAR')  # another practice
        files = unzip(self.get_bundle(mine).content)
        blob = b'\n'.join(files.values())
        self.assertIn(b'ZZ-TITLE-MARKER-MINE', blob)  # the control: the markers are in the bundle at all
        others = [neighbour, foreign]
        for other in others:
            ids = [str(other.pk)] + [str(pk) for pk in Round.objects.filter(encounter=other).values_list('pk', flat=True)]
            ids += [str(pk) for pk in models.CodeDecision.objects.filter(encounter=other).values_list('pk', flat=True)]
            ids += [str(pk) for pk in models.ExportArtifact.objects.filter(encounter=other).values_list('pk', flat=True)]
            for value in ids:
                with self.subTest(other=other.title, id=value):
                    self.assertNotIn(value.encode(), blob)
        for marker in (b'MARKER-NEXT', b'ZZ-NOTE-NEXT', b'MARKER-FAR', b'ZZ-NOTE-FAR'):
            self.assertNotIn(marker, blob)
        record = json.loads(files['record.json'])
        self.assertEqual(len(record['rounds']), 2)
        self.assertEqual(sum(len(round_['decisions']) for round_ in record['rounds']), 2)


# --- a whole practice -------------------------------------------------------------------------------------------------------

@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                             'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class PracticeExportTests(BundleCase, TestCase):
    def setUp(self):
        super().setUp()
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name)
        self.reason = self.scratch / 'reason.txt'
        self.reason.write_text('Synthetic: the practice ended its contract and asked for its data.', encoding='utf-8')

    def export(self, ws, name='export'):
        out = io.StringIO()
        call_command('export_workspace', '--workspace', str(ws.pk), '--out', str(self.scratch / name),
                     '--by', 'Synthetic Operator', '--reason-file', str(self.reason), stdout=out)
        return self.scratch / name, out.getvalue()

    def test_the_practice_export_holds_every_document_of_one_practice_and_nothing_of_the_other(self):
        note, word, paste = self.coded(marker='ONE'), self.word(marker='TWO'), self.done(pdf=False)
        foreign = self.coded(ws=self.other_ws, member=self.outsider, marker='FAR')
        folder, output = self.export(self.ws)
        documents = sorted(path.name for path in (folder / 'documents').iterdir())
        self.assertEqual(documents, sorted(str(enc.pk) for enc in (note, word, paste)))
        everything = b'\n'.join(path.read_bytes() for path in folder.rglob('*') if path.is_file())
        for value in (str(foreign.pk).encode(), b'MARKER-FAR', b'ZZ-NOTE-FAR', str(self.other_ws.pk).encode()):
            self.assertNotIn(value, everything)
        for value in (b'ZZ-TITLE-MARKER-ONE', b'ZZ-ANSWER-MARKER-ONE', CONVERTED + b'TWO'):
            self.assertIn(value, everything)  # the control: the practice's own data is there
        note_folder = folder / 'documents' / str(note.pk)
        self.assertEqual((note_folder / 'original' / 'zz-file-marker-ONE.pdf').read_bytes(),
                         f.PDF_BYTES + b'ZZ-TEXT-MARKER-ONE')
        self.assertEqual(json.loads((note_folder / 'record.json').read_text())['document']['id'], str(note.pk))
        manifest = json.loads((folder / 'manifest.json').read_text())
        self.assertEqual(manifest['workspace']['id'], str(self.ws.pk))
        self.assertEqual({item['id'] for item in manifest['documents']}, set(documents))
        self.assertTrue(manifest['decisions'] and manifest['answers'] and manifest['codes'])
        self.assertTrue(all(row['by'] and row['at'] for row in manifest['decisions']))
        self.assertEqual({row['event'] for row in manifest['audit_trail']} >= {'encounter.created', 'decision.recorded'},
                         True)
        with open(folder / 'codes.csv', newline='', encoding='utf-8') as handle:
            self.assertEqual({row['document'] for row in csv.DictReader(handle)}, {str(note.pk), str(word.pk),
                                                                                    str(paste.pk)})
        sums = dict(reversed(line.split('  ', 1)) for line in (folder / 'SHA256SUMS').read_text().splitlines())
        on_disk = {str(path.relative_to(folder)) for path in folder.rglob('*') if path.is_file()} - {'SHA256SUMS'}
        self.assertEqual(set(sums), on_disk)
        for path, digest in sums.items():  # every file's sha256 verifies
            self.assertEqual(hashlib.sha256((folder / path).read_bytes()).hexdigest(), digest)
        self.assertEqual(stat.S_IMODE(folder.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)
                            for path in folder.rglob('*')))
        event = models.DisposalEvent.objects.get(stage=models.DisposalEvent.EXPORTED)
        self.assertEqual((event.workspace_id, sorted(event.encounter_ids), event.run_by),
                         (self.ws.pk, documents, 'Synthetic Operator'))
        self.assertEqual(event.manifest_digest, hashlib.sha256((folder / 'manifest.json').read_bytes()).hexdigest())
        self.assertIn(event.manifest_digest, output)
        for marker in ('ZZ-TITLE-MARKER', 'zz-file-marker', 'ZZ-ANSWER-MARKER'):
            self.assertNotIn(marker, output)  # the receipt carries counts and digests only

    def test_an_export_is_written_once_into_a_new_folder(self):
        self.coded()
        self.export(self.ws)
        with self.assertRaises(CommandError):
            self.export(self.ws)
        self.assertEqual(models.DisposalEvent.objects.filter(stage=models.DisposalEvent.EXPORTED).count(), 1)

    def test_an_export_that_fails_midway_leaves_no_folder(self):
        self.coded()
        with mock.patch.object(record_bundle, '_audit_trail', side_effect=RuntimeError('synthetic failure')):
            with self.assertRaises(RuntimeError):
                self.export(self.ws, 'broken')
        self.assertFalse((self.scratch / 'broken').exists())
        self.assertFalse(models.DisposalEvent.objects.exists())
        self.assertEqual(os.listdir(self.scratch), ['reason.txt'])
