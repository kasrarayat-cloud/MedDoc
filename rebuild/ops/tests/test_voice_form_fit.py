"""Offline supplemental voice-plan/refutation controls; no providers or database."""
import copy
import dataclasses
import hashlib
import io
import json
import socket
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from lxml import etree
from documents import word_v3
from ops import provider_campaign as pc, standing_qa as st, standing_qa_voice_forms as vf
from .test_standing_qa import Base, FIXTURE, RUNNER_COMMIT, parse, scratch

_network = None


def setUpModule():
    global _network
    _network = patch.object(socket.socket, 'connect', side_effect=AssertionError('No network or database in voice-fit tests'))
    _network.start()


def tearDownModule():
    _network.stop()


class VoiceFormFitTests(Base):
    def declaration(self):
        old = parse(self)
        return dataclasses.replace(old, transcription=dataclasses.replace(old.transcription,
            forms=(('colonoscopy-speech', vf.FORM_ID),)))

    def test_frozen_independent_original_maps_and_fills_all_eleven_destinations(self):
        manifest, data = vf.frozen()
        self.assertEqual(data, vf.build())
        self.assertEqual(hashlib.sha256(data).hexdigest(), vf.FORM_SHA256)
        inspected = word_v3.inspect(data)
        self.assertEqual(inspected['fields'], manifest['fields'])
        self.assertEqual(inspected['notes'], [])
        answers = {f['key']: f'SYNTHETIC ANSWER {i}' for i, f in enumerate(manifest['fields'])}
        out = word_v3.fill(data, manifest['fields'], answers)
        with zipfile.ZipFile(io.BytesIO(out)) as filled, zipfile.ZipFile(io.BytesIO(data)) as original:
            xml = etree.fromstring(filled.read('word/document.xml'))
            rows = xml.findall('.//w:tbl/w:tr', word_v3.NS)
            self.assertEqual(len(rows), 11)
            for i, (row, field) in enumerate(zip(rows, manifest['fields'])):
                cells = row.findall('w:tc', word_v3.NS)
                self.assertEqual(''.join(cells[0].itertext()).strip(), field['label'])
                self.assertEqual(''.join(cells[1].itertext()).strip(), f'SYNTHETIC ANSWER {i}')
            for name in original.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(filled.read(name), original.read(name), name)

    def test_a_tampered_manifest_is_refused_before_a_form_is_built(self):
        changed = json.loads(vf.MANIFEST.read_text()); changed['provider_upload_allowed'] = False
        with (patch.object(pc, 'committed_file', return_value=(json.dumps(changed).encode(), '1'*40, '', '')),
              patch.object(vf, 'build') as build):
            with self.assertRaisesRegex(pc.Refused, 'pinned hash'):
                vf.frozen()
            build.assert_not_called()

    def test_historical_default_records_and_r1_plan_remain_unchanged(self):
        old = parse(self)
        record = old.transcription.record()
        self.assertNotIn('forms', record)
        inputs = st.stage_inputs('transcription', old)
        self.assertNotIn(vf.FORM_ID, inputs['cases']['forms'])
        sends = st.standing_plan('transcription', inputs)
        self.assertEqual({send.form for send in sends}, {'r1-11'})
        self.assertEqual([st.send_inputs(s, inputs)['form_sha256'] for s in sends],
                         [st.TRANSCRIPTION_FORM_HASHES['r1-11']] * 4)

    def test_declared_per_audio_form_changes_only_the_colonoscopy_pair(self):
        d = self.declaration(); inputs = st.stage_inputs('transcription', d)
        sends = st.standing_plan('transcription', inputs)
        self.assertEqual([s.form for s in sends], ['r1-11', 'r1-11', vf.FORM_ID, vf.FORM_ID])
        self.assertEqual([st.send_inputs(s, inputs)['form_sha256'] for s in sends],
                         [st.TRANSCRIPTION_FORM_HASHES['r1-11']] * 2 + [vf.FORM_SHA256] * 2)
        self.assertEqual(d.transcription.record()['forms'], [{'audio_id': vf.AUDIO_ID,
                         'id': vf.FORM_ID, 'sha256': vf.FORM_SHA256}])
        # Rates, request parameters, send identities and notes contract are unchanged.
        old = parse(self)
        self.assertEqual(d.transcription.parameters(), old.transcription.parameters())
        self.assertEqual(d.pricing_versions, old.pricing_versions)
        self.assertEqual([s.id for s in sends], [s.id for s in st.standing_plan('transcription', st.stage_inputs('transcription', old))])

    def test_plan_report_discloses_actual_per_recording_forms_and_hashes(self):
        d = self.declaration()
        with patch.object(st, 'declared_standing', return_value=d):
            report = st.plan_report('transcription', root=scratch(self) / 'campaign', declaration_path=FIXTURE)
        entry = report['stages']['transcription']
        self.assertEqual(entry['form'], 'per_recording')
        self.assertEqual([row['id'] for row in entry['forms']], ['r1-11', vf.FORM_ID])
        self.assertEqual([row['form'] for row in entry['sends']], ['r1-11', 'r1-11', vf.FORM_ID, vf.FORM_ID])
        self.assertEqual(entry['sends'][-1]['inputs']['form_sha256'], vf.FORM_SHA256)

    def test_form_declaration_parser_requires_exact_id_hash_recording_and_plain_line(self):
        text = FIXTURE.read_text()
        line = f'transcription_form: {vf.AUDIO_ID} {vf.FORM_ID} {vf.FORM_SHA256}\n'
        stages = (st.StandingStage('transcription', 4, ()),)
        terms = st.transcription_terms(text + line, st._seen(text + line), stages, '/other/anthropic-key')
        self.assertEqual(terms.forms, ((vf.AUDIO_ID, vf.FORM_ID),))
        bad = [line + line, line.replace(vf.AUDIO_ID, 'soap-ankle-speech'),
               line.replace(vf.AUDIO_ID, 'unlisted-speech'), line.replace(vf.FORM_ID, 'unlisted-form'),
               line.replace(vf.FORM_SHA256, 'f'*64), '- ' + line, line.upper()]
        for value in bad:
            with self.subTest(value=value[:80]), self.assertRaises(pc.Refused):
                st.transcription_terms(text + value, st._seen(text + value), stages, '/other/anthropic-key')

    def test_tampered_mapping_and_swapped_recording_form_are_refused(self):
        inputs = st.stage_inputs('transcription', self.declaration())
        send = st.standing_plan('transcription', inputs)[2]
        wrong = dataclasses.replace(send, form='r1-11')
        with self.assertRaisesRegex(pc.Refused, 'declared per-recording'):
            st.send_inputs(wrong, inputs)
        altered = copy.deepcopy(inputs)
        altered['cases']['forms'][vf.FORM_ID]['fields'][0]['label'] = 'Other person signature'
        with self.assertRaisesRegex(pc.Refused, 'committed freeze'):
            st.send_inputs(send, altered)

    def test_the_new_original_is_persisted_once_and_bad_reused_file_is_refused(self):
        inputs = st.stage_inputs('transcription', self.declaration()); target = scratch(self) / 'forms'
        built = st.build_transcription_forms(target, inputs)
        self.assertEqual(built[vf.FORM_ID], vf.build())
        path = target / (vf.FORM_ID + '.docx'); first = path.stat()
        st.build_transcription_forms(target, inputs)
        self.assertEqual(path.stat().st_ino, first.st_ino)
        path.write_bytes(b'changed original')
        with self.assertRaisesRegex(pc.Refused, 'retained supplemental original'):
            st.build_transcription_forms(target, inputs)

    def test_final_ledger_door_binds_form_to_recording_not_the_allowed_union(self):
        campaign = self.campaign(self.declaration()); self.pass_model_check(campaign)
        inputs = st.stage_inputs('transcription', campaign.declaration)
        sends = st.standing_plan('transcription', inputs)
        st.begin_run(campaign, 'transcription', sends, inputs, 4, {'runner_commit': RUNNER_COMMIT})
        send = sends[2]
        record = {'number': 2, 'campaign': campaign.declaration.campaign, 'authority_id': st.AUTHORITY_ID,
                  'stage': 'transcription', 'send': send.record(), 'maximum_cost': '.01',
                  'form_sha256': vf.FORM_SHA256, 'audio_sha256': st.AUDIO_BY_ID[vf.AUDIO_ID].sha256,
                  'rates': campaign.declaration.rates.as_dict(), 'limits': campaign.limits().record(),
                  'terms': campaign.pinned_terms().record(), 'runner_commit': RUNNER_COMMIT, 'started_at': pc.now()}
        wrong = copy.deepcopy(record); wrong['form_sha256'] = st.TRANSCRIPTION_FORM_HASHES['r1-11']
        self.assertIn(wrong['form_sha256'], campaign.runs.current()['allowed_inputs'])
        with self.assertRaisesRegex(pc.Refused, 'exact declared form'):
            campaign.ledger.write_attempt(wrong)
        self.assertEqual(len(campaign.ledger.rows()), 1)
        campaign.ledger.write_attempt(record); self.completed(campaign, 2)
        flipped = dataclasses.replace(campaign.declaration,
            transcription=dataclasses.replace(campaign.declaration.transcription, forms=()))
        with self.assertRaisesRegex(pc.Refused, 'earlier transcript requests used another form'):
            st.StandingCampaign(flipped, campaign.root).stage_open('transcription')

    def test_literal_reference_score_keeps_correction_and_missing_transcript_separate(self):
        manifest, _ = vf.frozen()
        notes = '. '.join(unit[0] for r in manifest['expectations'] for unit in r['source_units'])
        answers = {r['key']: {'status': r['expected_status'], 'text': r['accepted_answers'][0]
                   if r['expected_status'] == 'supported' else ''} for r in manifest['expectations']}
        support = {key: {'problems': []} for key, answer in answers.items() if answer['status'] == 'supported'}
        score = vf.score(manifest, notes, answers, support)
        self.assertEqual(score['schema'], 'supplemental-literal-reference-v2')
        self.assertEqual((score['reference_fields'], score['literal_reference_matches'], score['required_hold_shapes']), (11, 10, 1))
        self.assertEqual((score['first_pass_supported_answers'], score['first_pass_unadopted_answers'],
                          score['first_pass_missing_answers']), (10, 1, 0))
        self.assertEqual(score['valid_citation_shapes'], 10)
        self.assertIsNone(score['correct_answers'])
        self.assertIsNone(score['unsafe_answers'])
        self.assertIsNone(score['unnecessarily_held_answers'])
        answers['v3_7'] = {'status': 'supported', 'text': 'No polyps were seen but a polyp was removed'}
        mismatched = vf.score(manifest, notes, answers, support)
        self.assertEqual((mismatched['literal_reference_matches'], mismatched['literal_reference_mismatches']), (9, 1))
        answers['v3_7'] = {'status': 'missing', 'text': ''}
        score = vf.score(manifest, notes, answers, support)
        self.assertEqual((score['available_reference_unadopted_answers'], score['available_reference_missing_answers']), (1, 1))
        absent = notes.replace('No polyps were seen', '')
        score = vf.score(manifest, absent, answers, support)
        self.assertEqual((score['available_literal_references'], score['transcript_reference_words_missing'],
                          score['available_reference_unadopted_answers']), (10, 1, 0))
        self.assertEqual(vf.score(manifest, notes, answers, {})['valid_citation_shapes'], 0)

    def test_exact_family_and_negated_plan_matches_never_certify_correctness(self):
        tr = st.transcription_module(); manifest, _ = vf.frozen()
        cases = (
            ('ordinary-literal-positive', 'v3_7', 'No polyps were seen.', 'No polyps were seen'),
            ('explicit-other-person', 'v3_7',
             "The patient's father had colonoscopy. No polyps were seen in his examination.", 'No polyps were seen'),
            ('explicit-negated-plan', 'v3_11', 'Do not follow up with the referring clinician in two weeks.',
             'follow up with the referring clinician in two weeks'),
        )
        for name, key, notes, text in cases:
            with self.subTest(case=name):
                evidence = scratch(self)
                first = {key: {'status': 'supported', 'text': text,
                              'evidence': [{'start': 0, 'end': len(notes), 'quote': notes}]}}
                (evidence / 'answers-adopted.json').write_text(json.dumps({'answers': first}))
                _, findings, details = tr.TranscriptionRun.judge_transcript(notes, supplemental=manifest)(
                    None, SimpleNamespace(fields=manifest['fields']), {key: {'status': 'supported'}}, b'', b'',
                    raw={}, reviewed={}, evidence=evidence)
                score = details['supplemental_first_pass']
                self.assertEqual(findings, [])  # Existing exact-citation check is not a semantic grader.
                self.assertEqual((score['literal_reference_matches'], score['valid_citation_shapes']), (1, 1))
                self.assertIn('pending independent', score['semantic_adjudication'])
                self.assertIsNone(score['correct_answers'])
                self.assertIsNone(score['unsafe_answers'])
                self.assertIsNone(score['unnecessarily_held_answers'])
                self.assertNotIn('correct_adopted_answers', score)
                self.assertNotIn('correct_required_holds', score)
                self.assertNotIn('incorrect_adopted_answers', score)
                self.assertEqual(score['clinician_corrected_answers_credited'], 0)

    def test_clinician_review_cannot_improve_the_saved_first_pass_score(self):
        tr = st.transcription_module(); manifest, _ = vf.frozen(); evidence = scratch(self)
        ref = manifest['expectations'][0]; notes = ref['source_units'][0][0]
        answers = {ref['key']: {'status': 'missing', 'text': '', 'evidence': []}}
        (evidence / 'answers-adopted.json').write_text(json.dumps({'answers': answers}))
        reviewed = {ref['key']: {'status': 'supported', 'text': ref['accepted_answers'][0]}}
        _, findings, details = tr.TranscriptionRun.judge_transcript(notes, supplemental=manifest)(
            None, SimpleNamespace(fields=manifest['fields']), {ref['key']: {'status': 'missing'}}, b'', b'',
            raw={}, reviewed=reviewed, evidence=evidence)
        self.assertEqual(findings, [])
        self.assertEqual(details['supplemental_first_pass']['literal_reference_matches'], 0)
        self.assertEqual(details['supplemental_first_pass']['clinician_corrected_answers_credited'], 0)
        self.assertEqual(json.loads((evidence / 'supplemental-first-pass-score.json').read_text()), details['supplemental_first_pass'])
        adopted_evidence = scratch(self)
        first = {ref['key']: {'status': 'supported', 'text': ref['accepted_answers'][0],
                             'evidence': [{'start': 0, 'end': len(notes), 'quote': notes}]}}
        (adopted_evidence / 'answers-adopted.json').write_text(json.dumps({'answers': first}))
        _, _, details = tr.TranscriptionRun.judge_transcript(notes, supplemental=manifest)(
            None, SimpleNamespace(fields=manifest['fields']), {ref['key']: {'status': 'supported'}}, b'', b'',
            raw={}, reviewed={ref['key']: {'status': 'missing', 'text': ''}}, evidence=adopted_evidence)
        self.assertEqual(details['supplemental_first_pass']['literal_reference_matches'], 1)
        self.assertIsNone(details['supplemental_first_pass']['correct_answers'])
        self.assertEqual(details['supplemental_first_pass']['clinician_corrected_answers_credited'], 0)
