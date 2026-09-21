"""What the legacy generation contract must instruct, and what its validator must keep.

A table, multi-column or mixed form selects the LEGACY contract: the model returns quotes and
`validate_selections` grounds them. That validator is strong — a quote must be a whole source
line or the whole value of THIS question's label, offsets are re-verified, and a value labelled
for another question is refused outright, so negation cannot be stripped and sections cannot
borrow from each other.

What it cannot do is judge whether a grounded sentence ANSWERS a given question. Offered the
one-line note "The scope was advanced to the cecum." for a `Consent` answer cell, it accepts:
every grounding rule is satisfied. The tab contract has instructed against exactly that since
v4 ("Do not infer consent or dictated/transcribed dates from procedure facts"). The legacy
contract never did — and it is the contract these newly supported layouts use.

So the repair is in the instruction, gated on the current prompt version so queued jobs keep
theirs, plus a real validator fix for signature fields, which were protected only when the
locator happened to be `tab_form`.

⚠️ A BROADER VALIDATOR FIX WAS TRIED AND REVERTED. Widening `inherited_context` to every
unscoped note would have flagged the Consent case — and also destroyed the legitimate case of a
single unlabelled sentence answering the only question on a form. That rule is about context a
PRECEDING line imposes ("The following findings are denied:"), which a one-line note cannot
have; `len(lines) > 1` is correct, not an off-by-one. test_labelled_answer_values caught it.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.generation import Selection, Selections, validate_selections


def _legacy_instructions(config):
    """The system instruction the LEGACY branch builds, captured without a provider call.

    `generate()` sends it as `client.messages.create(system=...)`, so the Anthropic client is
    replaced and the call is stopped the moment the instruction is in hand.
    """
    from unittest.mock import MagicMock, patch

    captured = {}

    def create(**kwargs):
        captured['instructions'] = kwargs.get('system', '')
        raise RuntimeError('stop before any request')

    client = MagicMock()
    client.messages.create.side_effect = create
    # generate() refuses before building a request when rates are unset; supply synthetic ones
    # so the instruction is reached. Nothing is sent: create() raises on entry.
    config = {**config, 'input_rate': '0.000003', 'output_rate': '0.000015', 'cached_rate': '0.0000003'}
    fields = [{'key': 'cell_0', 'label': 'Consent', 'kind': 'text', 'locator': {'cell': 0}}]
    from core import generation
    with patch('anthropic.Anthropic', return_value=client):
        try:
            generation.generate('Consent: documented', fields, config)
        except Exception:
            pass
    assert 'instructions' in captured, 'the instruction was never built; the capture is broken'
    return captured['instructions']


def two_column_form(*labels):
    return [{'key': f'cell_{i}', 'label': label, 'kind': 'text', 'locator': {'cell': i}}
            for i, label in enumerate(labels)]


def response(fields, quotes_by_key, conflict=()):
    return Selections(fields=[
        Selection(key=f['key'], quotes=list(quotes_by_key.get(f['key'], [])),
                  conflict=f['key'] in conflict)
        for f in fields])


class UnlabelledSourceIsNotAnAnswer(TestCase):
    def test_the_legacy_contract_now_forbids_inferring_consent_and_dates(self):
        """THE DEFECT, and where it actually lives.

        Offered the one-line note "The scope was advanced to the cecum." for a `Consent` answer
        cell, the validator ACCEPTS it: the text is in the source, unshortened, and not borrowed
        from another question's label, so every grounding rule is satisfied. Whether that
        sentence *answers consent* is a judgement no validator here can make.

        The tab contract has instructed against exactly this since v4. The legacy contract —
        the one a table, multi-column or mixed form selects — never did. That was the gap.
        """
        from core.generation import CURRENT_PROMPT_VERSION, configuration

        config = dict(configuration())
        config['mode'] = 'live'
        config['prompt_version'] = CURRENT_PROMPT_VERSION
        instructions = _legacy_instructions(config)

        for phrase in ('consent', 'signature', 'dictated/transcribed date',
                       'Preprinted form text is context'):
            self.assertIn(phrase, instructions,
                          f'the legacy contract must instruct against inferring {phrase!r}')

    def test_a_queued_job_keeps_the_instructions_it_was_created_with(self):
        """Prospective only: an older prompt version must not gain the new sentence."""
        from core.generation import configuration

        config = dict(configuration())
        config['mode'] = 'live'
        config['prompt_version'] = 'extractive-v4-tab-evidence-units'
        self.assertNotIn('Preprinted form text is context', _legacy_instructions(config),
                         'changing a queued job\'s instructions would relabel its history')

    def test_the_multi_line_form_of_the_same_hazard_was_already_caught(self):
        """The positive control for the guard that already worked."""
        fields = two_column_form('Consent', 'Findings')
        notes = ('Fictional software test only. The scope was advanced to the cecum.\n'
                 'There were no immediate complications.')
        out = validate_selections(notes, fields, response(
            fields, {'cell_0': ['Fictional software test only. The scope was advanced to the cecum.']}))
        self.assertEqual(out['cell_0']['status'], 'conflict')

    def test_a_scoped_single_line_still_answers_its_own_question(self):
        """The capability that must NOT be lost — this is what keeps ordinary forms working."""
        fields = two_column_form('Height')
        out = validate_selections('Height: 170 cm', fields, response(fields, {'cell_0': ['170 cm']}))
        self.assertEqual(out['cell_0']['status'], 'supported')
        self.assertEqual(out['cell_0']['text'], '170 cm')

    def test_a_scoped_multi_line_note_still_answers_every_question(self):
        fields = two_column_form('Height', 'Weight')
        notes = 'Height: 170 cm\nWeight: 70 kg'
        out = validate_selections(notes, fields, response(
            fields, {'cell_0': ['170 cm'], 'cell_1': ['70 kg']}))
        self.assertEqual((out['cell_0']['status'], out['cell_0']['text']), ('supported', '170 cm'))
        self.assertEqual((out['cell_1']['status'], out['cell_1']['text']), ('supported', '70 kg'))

    def test_cross_label_borrowing_is_still_refused_outright(self):
        """Unchanged behaviour, asserted so the repair cannot loosen it."""
        fields = two_column_form('Height', 'Weight')
        notes = 'Height: 170 cm\nWeight: 70 kg'
        with self.assertRaises(ValidationError):
            validate_selections(notes, fields, response(fields, {'cell_0': ['70 kg']}))

    def test_a_single_unlabelled_sentence_still_answers_the_only_question(self):
        """The capability a broader fix would have destroyed, kept deliberately.

        Widening `inherited_context` to every unscoped note was tried and reverted: that rule is
        about context a PRECEDING line imposes ("The following findings are denied:"), which a
        one-line note cannot have. test_labelled_answer_values caught the regression.
        """
        fields = two_column_form('Findings')
        notes = 'sigmoid diverticulosis and small internal hemorrhoids were seen'
        out = validate_selections(notes, fields, response(fields, {'cell_0': [notes]}))
        self.assertEqual((out['cell_0']['status'], out['cell_0']['text']), ('supported', notes))
        self.assertEqual(notes[out['cell_0']['evidence'][0]['start']:out['cell_0']['evidence'][0]['end']],
                         out['cell_0']['evidence'][0]['quote'])

    def test_a_signature_field_is_still_never_generated(self):
        fields = two_column_form('Electronically signed by')
        out = validate_selections('Electronically signed by: Dr Synthetic Example', fields,
                                  response(fields, {'cell_0': ['Dr Synthetic Example']}))
        self.assertEqual(out['cell_0']['status'], 'missing')
        self.assertEqual(out['cell_0']['text'], '')


class SubjectGuardsAreSymmetric(TestCase):
    """⚠️ ONE STEM PER SUBJECT, ON BOTH SIDES — the asymmetry was the whole defect.

    The label side tested `\\bdictated\\b` while the quote side already accepted `dictation`, so
    a form whose question reads `Date of dictation` disarmed the guard entirely and the
    PROCEDURE date was asserted as the dictation date. Pointing the other way, `\\bconsent\\b`
    does not match `consented`, so standard operative phrasing was BLANKED and finalization
    refused until the clinician retyped documentation that was already correct.
    """

    def judge(self, label, notes, quote=None):
        field = {'key': 'cell_0', 'label': label, 'kind': 'text', 'locator': {'cell': 0}}
        chosen = Selections(fields=[Selection(key='cell_0', quotes=[notes if quote is None else quote],
                                              conflict=False)])
        answer = validate_selections(notes, [field], chosen, evidence_contract='legacy')['cell_0']
        return answer['status'], answer['text']

    def test_a_noun_form_question_still_guards_the_documentation_date(self):
        notes = 'Procedure date: September 21, 2026.'
        for label in ('Date of dictation', 'Dictation date', 'Transcription date',
                      'Date of transcription', 'DD (dictated)', 'DT (transcribed)'):
            with self.subTest(label=label):
                self.assertEqual(self.judge(label, notes), ('conflict', ''))

    def test_documented_consent_in_the_verb_form_is_not_blanked(self):
        for notes in ('The patient was consented for the procedure after discussion of risks.',
                      'Patient consented in the pre-operative area.',
                      'Informed consent was obtained.'):
            with self.subTest(notes=notes):
                self.assertEqual(self.judge('CONSENT', notes), ('supported', notes))

    def test_a_procedure_sentence_is_still_refused_as_consent_evidence(self):
        notes = 'The scope was advanced to the cecum.'
        self.assertEqual(self.judge('CONSENT', notes), ('conflict', ''))

    def test_a_date_the_question_own_label_introduced_survives(self):
        """The exemption this guard already needed: the LABEL establishes the subject."""
        notes = 'DD (dictated): 2026-09-18'
        self.assertEqual(self.judge('DD (dictated)', notes, quote='2026-09-18'),
                         ('supported', '2026-09-18'))


class SignatureIsRecognisedByPolicyOrLabel(TestCase):
    """⚠️ NO SHORT-CIRCUIT. Judging a tab field "by its policy alone" is false whenever the
    inspector did not set one — a heading-continuation signature arrives with no policy at all.
    """

    def recognised(self, label, locator=None):
        from core.tab_review import clinician_identity
        return clinician_identity({'key': 'k', 'label': label, 'kind': 'text',
                                   'locator': locator or {'cell': 0}})

    def test_signature_shaped_questions_are_recognised_wherever_they_sit(self):
        for label in ('Electronically signed by', 'Signed by', 'Signature', 'Signature:',
                      'Physician signature', 'Surgeon signature', 'Signature of surgeon',
                      'Signed', 'Signed by (MD)', 'Electronically signed by (print name)',
                      'Signature/Date', 'Electronically signed by\uff1a', 'Electronically signed by.'):
            for locator in ({'cell': 0}, {'tab_form': {'version': 1}}):
                with self.subTest(label=label, locator=tuple(locator)):
                    self.assertTrue(self.recognised(label, locator))

    def test_a_date_question_that_merely_says_signature_is_not_an_identity_field(self):
        """The false-refusal control. Treating these as signatures would block finalization."""
        for label in ('Signature date', 'Date of signature', 'Attestation',
                      'Attending attestation', 'DD (dictated)'):
            with self.subTest(label=label):
                self.assertFalse(self.recognised(label))

    def test_an_explicit_policy_still_wins_regardless_of_the_label(self):
        from core.tab_review import clinician_identity
        self.assertTrue(clinician_identity({'key': 'k', 'label': 'Anything at all', 'kind': 'text',
                                            'locator': {'tab_form': {'version': 1}},
                                            'answer_policy': 'clinician_identity'}))
