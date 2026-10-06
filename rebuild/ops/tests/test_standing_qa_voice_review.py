"""Finite synthetic edits, changed ASR refusal, and retained ambiguity; no providers or database."""
import copy
import json
import unittest

from ops import provider_campaign as pc
from ops import standing_qa_voice_review as review


class ProspectiveSyntheticReview(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(review.MANIFEST.read_text())

    def test_each_explicit_review_uses_exact_audio_and_raw_asr(self):
        rows = review.validate(self.data)
        self.assertEqual(set(rows), {'soap-ankle-speech', 'colonoscopy-speech'})
        for row in rows.values():
            self.assertEqual(review.reviewed(row, row['audio_sha256'], row['raw_text']), row['reviewed_text'])
            for changed_audio, changed_raw in [(row['audio_sha256'], row['raw_text'] + ' '),
                                               ('0' * 64, row['raw_text'])]:
                with self.assertRaisesRegex(pc.Refused, 'current ASR differs'):
                    review.reviewed(row, changed_audio, changed_raw)

    def test_an_unrecorded_edit_or_replacement_is_refused(self):
        for change in ('unrecorded', 'duplicate_source', 'wrong_hash'):
            data = copy.deepcopy(self.data)
            row = data['rows'][0]
            if change == 'unrecorded':
                row['edits'].pop()
            elif change == 'duplicate_source':
                row['edits'][0]['raw'] = 'not found in transcript'
            else:
                row['prior_raw_sha256'] = '0' * 64
            with self.subTest(change=change), self.assertRaises(pc.Refused):
                review.validate(data)

    def test_c08_and_clinical_source_context_are_not_silently_rewritten(self):
        rows = review.validate(self.data)
        colon = rows['colonoscopy-speech']
        ambiguity = 'Estimated blood loss was zero milliliters. Less than one milliliter.'
        self.assertIn(ambiguity, colon['raw_text'])
        self.assertIn(ambiguity, colon['reviewed_text'])
        self.assertNotIn('correction, less than one', colon['reviewed_text'])
        soap = rows['soap-ankle-speech']
        self.assertIn('The clinician explicitly documents', soap['raw_text'])
        self.assertIn('The clinician explicitly documents', soap['reviewed_text'])
        self.assertIn('The clinician explicitly directs', soap['reviewed_text'])
        self.assertIn('Pain score correction three out of 10.', soap['reviewed_text'])
        self.assertFalse(self.data['corpus_qualification'])

