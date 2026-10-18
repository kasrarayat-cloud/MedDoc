"""Complete source phrases and time qualifications; no provider or database."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from core import coding_engine as engine, corti_coding, corti_semantics
from core.coding_terminology import parse_reference


class CompleteSourceCodingTests(SimpleTestCase):
    def setUp(self):
        parsed = parse_reference(
            '<ICD10CM.index><version>2027</version><letter><mainTerm><title>Bloating</title>'
            '<code>R14.0</code></mainTerm></letter></ICD10CM.index>',
            '<ICD10CM.tabular><version>2027</version><chapter><name>unit</name><section id="unit">'
            '<diag><name>R14.0</name><desc>Abdominal distension (gaseous)</desc></diag>'
            '</section></chapter></ICD10CM.tabular>', {'R14.0':'Abdominal distension (gaseous)'})
        self.reference = SimpleNamespace(**parsed, release_id='synthetic-reference', digest='a'*64,
            release=SimpleNamespace(version='SYNTHETIC-UNIT'))
        self.notes = ('Patient: Synthetic Ellis Vale\nSubjective:\n'
            'He reports intermittent epigastric pain for three weeks and abdominal bloating for five weeks.\n'
            'Assessment:\nEpigastric pain and abdominal bloating were both assessed today.')
        quote = 'abdominal bloating for five weeks'
        start = self.notes.index(quote)
        self.proposal = {'id':'selected:1', 'code':'R14.0',
            'terminology':{'description':'Abdominal distension (gaseous)'},
            'evidence':[{'text':quote, 'start':start, 'end':start+len(quote), 'status':'valid', 'context_index':0}]}

    def route(self, notes=None, *, contract=engine.PROSPECTIVE_SOURCE_CONTRACT, proposal=None):
        run = SimpleNamespace(inputs={'notes':notes or self.notes}, config={'clinical_source_contract':contract})
        return corti_coding._icd_source(run, self.reference, proposal or self.proposal, ['R14.0'])

    def test_provider_uses_the_same_complete_authoritative_phrase_as_source_review(self):
        original = deepcopy(self.proposal)
        self.assertIsNone(self.route(contract=engine.CURRENT_SOURCE_CONTRACT)[1])
        concept, candidate, check = self.route()
        self.assertEqual(concept['term'], 'abdominal bloating')
        self.assertEqual(concept['id'], 'selected:1')
        self.assertEqual(candidate['code'], 'R14.0')
        self.assertEqual(candidate['qualified_phrase_proof']['literal'], 'abdominal bloating')
        self.assertTrue(check['source_condition_id'].startswith('source-condition:'))
        self.assertEqual(self.proposal, original)

    def test_complete_phrase_does_not_hide_retraction_denial_or_unknown_modifier(self):
        for suffix in ('\nThe abdominal bloating statement is incorrect.',
                       '\nHe does not have abdominal bloating.',
                       '\nThe abdominal bloating belongs to another patient.'):
            with self.subTest(suffix=suffix):
                self.assertIsNone(self.route(self.notes+suffix)[1])
        for modifier in ('unverified', 'fabricated', 'possible'):
            notes = self.notes.replace('abdominal bloating', modifier+' bloating')
            proposal = deepcopy(self.proposal)
            quote = modifier+' bloating for five weeks'
            start = notes.index(quote)
            proposal['evidence'] = [{'text':quote, 'start':start, 'end':start+len(quote), 'status':'valid', 'context_index':0}]
            with self.subTest(modifier=modifier):
                self.assertIsNone(self.route(notes, proposal=proposal)[1])

    def test_clipped_or_foreign_provider_evidence_cannot_use_a_complete_source_phrase(self):
        for text, context, status in (('bloating',0,'valid'), ('abdominal bloating for five weeks',1,'valid'),
                                      ('abdominal bloating for five weeks',0,'invalid')):
            proposal = deepcopy(self.proposal)
            start = self.notes.index(text)
            proposal['evidence'] = [{'text':text, 'start':start, 'end':start+len(text),
                                     'context_index':context, 'status':status}]
            with self.subTest(text=text,context=context,status=status):
                self.assertIsNone(self.route(proposal=proposal)[1])


class CompleteOfficeTimeTests(SimpleTestCase):
    def setUp(self):
        self.notes = ('Patient: Synthetic Ellis Vale\nDate of service: 18 October 2026\n'
            'Treating clinician: Dr. Amina Reed\n'
            'Visit: Established-patient, in-person visit in a U.S. gastrointestinal office.\n'
            'Office E/M selection is based on total physician time on the date of service. '
            'Dr. Reed personally spent 26 minutes on 18 October 2026: three minutes reviewing the available records, '
            '18 minutes obtaining the history, performing the examination and counseling the patient, '
            'and five minutes entering the test order and documenting the visit. '
            'These activities were all performed by the physician on the encounter date. '
            'The 26 minutes exclude six minutes of staff intake work and eight minutes of physician record review '
            'performed on the preceding day. The total also excludes any time for separately reported services.')

    def test_complete_visit_and_work_qualification_bind_all_eight_facts(self):
        old = corti_semantics.office_time_facts(self.notes, contract=engine.CURRENT_SOURCE_CONTRACT)
        self.assertEqual(old['status'], 'requires_clarification')
        result = corti_semantics.office_time_facts(self.notes, contract=engine.PROSPECTIVE_SOURCE_CONTRACT)
        self.assertEqual(result['status'], 'documented', result['blockers'])
        self.assertEqual({f['key'] for f in result['facts']}, set(corti_semantics.REQUIRED_TIME_FACTS))
        self.assertEqual(next(f['value'] for f in result['facts'] if f['key']=='time_minutes'), 26)
        self.assertFalse(result['clinician_confirmed'])
        for fact in result['facts']:
            self.assertEqual(self.notes[fact['start']:fact['end']], fact['quote'])
        self.assertEqual(corti_semantics.office_service_eligibility(self.notes, date(2026,10,18),
            contract=engine.PROSPECTIVE_SOURCE_CONTRACT), [])
        self.assertEqual(corti_semantics.citation_adequacy([], result['facts'])['status'],
            'insufficient_for_time_review')

    def test_qualification_must_not_bridge_unknown_foreign_or_other_day_work(self):
        original = 'These activities were all performed by the physician on the encounter date.'
        for replacement in ('These activities were all performed by the nurse on the encounter date.',
                            'These activities were all performed by the physician on the preceding day.',
                            'These activities were not all performed by the physician on the encounter date.',
                            original+' Another 10 minutes might also count toward this total.'):
            with self.subTest(replacement=replacement):
                notes = self.notes.replace(original, replacement)
                result = corti_semantics.office_time_facts(notes, contract=engine.PROSPECTIVE_SOURCE_CONTRACT)
                self.assertEqual(result['status'], 'requires_clarification')
