"""Frozen input and routing controls only; no account, provider or database access."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core.soap_document import LABELS, original_bytes
from documents import word_v3
from ops import standing_qa as st, standing_qa_soap_form as soap
from . import network_guard


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


class BuiltinSoapVoiceInput(unittest.TestCase):
    def test_freeze_is_exact_application_original_and_four_physical_destinations(self):
        manifest, raw = soap.frozen()
        self.assertEqual(raw, original_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), soap.FORM_SHA256)
        self.assertEqual(manifest['fields'], word_v3.inspect(raw)['fields'])
        self.assertEqual(tuple(field['label'] for field in manifest['fields']), LABELS)
        self.assertFalse(manifest['corpus_qualification'])
        self.assertTrue(manifest['provider_upload_allowed'])

    def test_historical_default_and_procedure_recordings_keep_their_original_forms(self):
        for audio in st.AUDIO_BY_ID:
            self.assertEqual(st.transcription_form_id(audio), 'r1-11')
        self.assertEqual(st.transcription_form_id('colonoscopy-speech',
                         [('colonoscopy-speech', 'synthetic-colonoscopy-voice-v1')]),
                         'synthetic-colonoscopy-voice-v1')

    def test_new_form_is_explicit_and_belongs_only_to_the_unchanged_soap_recording(self):
        self.assertEqual(st.transcription_form_id('soap-ankle-speech',
                         [('soap-ankle-speech', soap.FORM_ID)]), soap.FORM_ID)
        for audio, name in [('colonoscopy-speech', soap.FORM_ID),
                            ('soap-ankle-speech', 'synthetic-colonoscopy-voice-v1'),
                            ('soap-ankle-speech', 'unfrozen-soap')]:
            with self.subTest(audio=audio, name=name):
                with self.assertRaises(st.Refused):
                    st.transcription_form_id(audio, [(audio, name)])

    def test_unknown_supplemental_generator_is_refused(self):
        with self.assertRaises(st.Refused):
            st.voice_forms_module('unfrozen-soap')

    def test_changed_mapping_or_expectation_is_refused_before_a_send(self):
        manifest, _ = soap.frozen()
        send = SimpleNamespace(case='soap-ankle-speech', form=soap.FORM_ID)
        for change in ('mapping', 'expectation'):
            altered = json.loads(json.dumps(manifest))
            if change == 'mapping':
                altered['fields'][0]['locator']['slot'] = 'b/p[0]'
            else:
                altered['expectations'][0]['expected_status'] = 'supported'
            inputs = {'transcription_forms': [('soap-ankle-speech', soap.FORM_ID)],
                      'cases': {'forms': {soap.FORM_ID: altered}}}
            with self.subTest(change=change), self.assertRaises(st.Refused):
                st.transcription_form_spec(send, inputs)

    def test_builds_both_declared_supplements_without_sending_them_to_legacy_generator(self):
        procedure = st.voice_forms_module().frozen()[0]
        manifest, raw = soap.frozen()
        inputs = {'cases': {'forms': {'r1-11': {'id': 'r1-11'},
                                      procedure['id']: procedure, soap.FORM_ID: manifest}}}
        seen = []
        def legacy(target, stage, legacy_inputs):
            seen.append(set(legacy_inputs['cases']['forms']))
            return {'r1-11': b'old fixture'}
        with tempfile.TemporaryDirectory() as directory, patch.object(st.sq.stages_module(), 'build_forms', legacy):
            built = st.build_transcription_forms(directory, inputs)
            self.assertEqual(seen, [{'r1-11'}])
            self.assertEqual(built[soap.FORM_ID], raw)
            self.assertEqual(Path(directory, soap.FORM_ID+'.docx').read_bytes(), raw)
            self.assertEqual(set(built), {'r1-11', soap.FORM_ID, procedure['id']})

    def test_replaced_retained_original_is_refused_instead_of_overwritten(self):
        manifest, _ = soap.frozen()
        inputs = {'cases': {'forms': {soap.FORM_ID: manifest}}}
        with tempfile.TemporaryDirectory() as directory, patch.object(st.sq.stages_module(), 'build_forms', return_value={}):
            path = Path(directory, soap.FORM_ID+'.docx')
            path.write_bytes(b'retained changed original')
            path.chmod(0o600)
            with self.assertRaises(st.Refused):
                st.build_transcription_forms(directory, inputs)
            self.assertEqual(path.read_bytes(), b'retained changed original')

    def test_literal_score_cannot_claim_clinical_correctness_or_credit_edits(self):
        manifest, _ = soap.frozen()
        result = soap.score(manifest, '', {}, {})
        self.assertEqual(result['form_id'], soap.FORM_ID)
        self.assertEqual(result['reference_fields'], 4)
        self.assertEqual(result['first_pass_supported_answers'], 0)
        self.assertIsNone(result['correct_answers'])
        self.assertIsNone(result['unsafe_answers'])
        self.assertEqual(result['clinician_corrected_answers_credited'], 0)
