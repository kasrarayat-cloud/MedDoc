"""Complete negative subtype lists and unknown-cause nouns, with no IO."""
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch

from django.test import SimpleTestCase

from core import coding_engine as engine, corti_coding, corti_semantics
from core.coding_terminology import parse_reference


class QualifiedAssertionTests(SimpleTestCase):
    def setUp(self):
        codes = {'R12': 'Heartburn', 'K59.00': 'Constipation, unspecified',
                 'K59.01': 'Slow transit constipation', 'K59.03': 'Drug induced constipation',
                 'K30': 'Functional dyspepsia'}
        parsed = parse_reference(
            '<ICD10CM.index><version>2027</version><letter>'
            '<mainTerm><title>Heartburn</title><code>R12</code></mainTerm>'
            '<mainTerm><title>Constipation</title><code>K59.00</code>'
            '<term><title>slow transit</title><code>K59.01</code></term>'
            '<term><title>drug induced</title><code>K59.03</code></term>'
            '</mainTerm></letter></ICD10CM.index>',
            '<ICD10CM.tabular><version>2027</version><chapter><name>unit</name><section id="unit">'
            + ''.join('<diag><name>'+code+'</name><desc>'+description+'</desc>'
                      + ('<excludes1><note>functional dyspepsia (K30)</note></excludes1>' if code=='R12' else '')
                      + '</diag>' for code, description in codes.items())
            + '</section></chapter></ICD10CM.tabular>', codes)
        self.reference = N(**parsed, release_id='synthetic-reference', digest='a'*64,
                           release=N(version='SYNTHETIC-UNIT'))
        self.contract = engine.QUALIFIED_SOURCE_CONTRACT
        self.prefix = 'Patient: Synthetic Ellis Vale\nAssessment:\n'

    def route(self, note, code='K59.00', *, quote=None, contract=None, selected=None):
        quote = quote or 'The patient reports constipation today.'
        start = note.index(quote)
        proposal = {'id':'selected:0', 'code':code,
            'terminology':{'description':self.reference.tabular['codes'][code]},
            'evidence':[{'text':quote, 'start':start, 'end':start+len(quote), 'status':'valid', 'context_index':0}]}
        run = N(inputs={'notes':note}, config={'clinical_source_contract':contract or self.contract})
        return corti_coding._icd_source(run, self.reference, proposal, selected or [code])

    def symptom(self):
        return {'id':'symptom', 'term':'Heartburn', 'index_terms':['Heartburn'],
            'kind':'symptom', 'evidence':'The patient reports heartburn today.',
            'subject':'patient', 'temporality':'current', 'certainty':'confirmed',
            'relevant':True, 'missing_detail':'', 'integral_to':''}

    def holds(self, extra, *, contract=None, extra_rows=()):
        rows = [{'eligible':True, 'concept':self.symptom()}, *extra_rows]
        note = self.prefix+self.symptom()['evidence']+'\n'+extra
        original = deepcopy(rows)
        result = corti_coding.integral_holds(rows, note, source_contract=contract or self.contract)
        self.assertEqual(rows, original)
        return result

    def test_complete_unknown_cause_noun_does_not_claim_a_causal_relationship(self):
        for text in ('The cause of the heartburn is not established.',
                     'The cause of heartburn remains unknown.',
                     'The etiology of heartburn is undetermined.',
                     'Heartburn cause is not identified.'):
            with self.subTest(text=text):
                self.assertEqual(self.holds(text), {})
        self.assertEqual(self.holds('The cause of the heartburn is not established.',
            contract=engine.SOAP_SOURCE_CONTRACT), {'symptom':'source-causal-wording'})

    def test_causal_predicates_and_unconsumed_unknown_cause_qualifiers_stay_held(self):
        for text in ('Reflux causes heartburn.', 'Possible reflux causes heartburn.',
                     'Heartburn is due to reflux.', 'Heartburn is not due to reflux.',
                     'The cause of heartburn is not established for another patient.',
                     'The cause of heartburn is not established and the report is withdrawn.',
                     'The cause of heartburn is not established except reflux.',
                     'The cause of heartburn is not established but reflux causes heartburn.'):
            with self.subTest(text=text): self.assertTrue(self.holds(text))

    def test_confirmed_parent_veto_is_unchanged(self):
        parent = {**self.symptom(), 'id':'disease', 'term':'Reflux', 'index_terms':['Reflux'], 'kind':'diagnosis'}
        self.assertEqual(self.holds('Reflux causes heartburn.', extra_rows=[{'eligible':True,'concept':parent}]),
                         {'symptom':'disease'})

    def test_unknown_cause_is_not_positive_evidence_or_source_scope_permission(self):
        text = 'The cause of heartburn is not established.'
        self.assertIsNone(self.route(self.prefix+text, 'R12', quote=text)[1])
        for heading in ('Mother:', 'Prior encounter:', 'Quoted example:'):
            with self.subTest(heading=heading): self.assertTrue(self.holds(heading+'\n'+text))

    def test_complete_denied_subtype_list_does_not_veto_documented_parent(self):
        positive = 'The patient reports constipation today.'
        negative = ('Slow-transit constipation, outlet dysfunction, drug-induced constipation '
                    'and irritable bowel syndrome are not diagnosed today.')
        note = self.prefix+positive+'\n'+negative
        self.assertIsNone(self.route(note, contract=engine.SOAP_SOURCE_CONTRACT)[1])
        self.assertEqual(self.route(note)[1]['code'], 'K59.00')
        for text in ('Slow transit constipation is not diagnosed today.',
                     'Slow-transit constipation and drug-induced constipation are not established.',
                     'Drug-induced constipation, slow-transit constipation, and nausea are not confirmed at this encounter.'):
            with self.subTest(text=text): self.assertEqual(self.route(self.prefix+positive+'\n'+text)[1]['code'],'K59.00')

    def test_unqualified_parent_in_denied_list_still_conflicts(self):
        for text in ('Constipation and nausea are not diagnosed today.',
                     'Slow-transit constipation, constipation and nausea are not diagnosed today.',
                     'Constipation, slow-transit constipation and nausea are not established.'):
            with self.subTest(text=text):
                self.assertIsNone(self.route(self.prefix+'The patient reports constipation today.\n'+text)[1])

    def test_unknown_list_tail_or_scope_cannot_be_dropped(self):
        base = 'Slow-transit constipation and nausea are not diagnosed today'
        for text in (base+' except as previously noted.', base+' for her mother.',
                     base+' and the symptom statement is withdrawn.',
                     'Possible slow-transit constipation and nausea are not diagnosed today.',
                     'Slow-transit constipation or nausea are not diagnosed today.'):
            with self.subTest(text=text):
                self.assertIsNone(self.route(self.prefix+'The patient reports constipation today.\n'+text)[1])

    def test_affirmed_subtype_elsewhere_still_blocks_default(self):
        note = (self.prefix+'The patient reports constipation today.\n'
            'Slow-transit constipation and nausea are not diagnosed today.\n'
            'The patient reports slow transit constipation today.')
        self.assertIsNone(self.route(note)[1])

    def test_negative_list_cannot_establish_parent_or_select_denied_subtype(self):
        text = 'Slow-transit constipation and nausea are not diagnosed today.'
        self.assertIsNone(self.route(self.prefix+text, quote=text)[1])
        note = self.prefix+'The patient reports constipation today.\n'+text
        self.assertIsNone(self.route(note, 'K59.01', quote=text)[1])

    def test_excludes_instruction_is_not_changed_by_unknown_cause_exception(self):
        quote = 'The patient reports heartburn today.'
        note = self.prefix+quote+'\nThe cause of heartburn is not established.'
        self.assertEqual(self.route(note,'R12',quote=quote)[1]['code'],'R12')
        self.assertIsNone(self.route(note,'R12',quote=quote,selected=['R12','K30'])[1])

    def test_v7_preserves_all_eight_time_facts_and_unconfirmed_status(self):
        from core.tests.test_soap_coding_time import SoapCodingTimeTests
        note = SoapCodingTimeTests.note
        before = corti_semantics.office_time_facts(note, contract=engine.SOAP_SOURCE_CONTRACT)
        after = corti_semantics.office_time_facts(note, contract=self.contract)
        self.assertEqual(after, before)
        self.assertEqual(after['status'], 'documented')
        self.assertEqual({f['key'] for f in after['facts']}, set(corti_semantics.REQUIRED_TIME_FACTS))
        self.assertFalse(after['clinician_confirmed'])

    def test_source_review_v7_is_explicit_and_older_review_bytes_stay_identical(self):
        from core import coding_completeness as completeness
        from core.tests.test_coding_completeness import bind
        from core.tests.test_coding_nec import retained_case
        case = retained_case()
        note = ('Patient: Synthetic Uma Bell\nHistory of present illness\n'
                'She reports heartburn today.\nAssessment\nHeartburn.')
        outputs = []
        for contract in (engine.CURRENT_SOURCE_CONTRACT, engine.PROSPECTIVE_SOURCE_CONTRACT,
                         engine.SOAP_SOURCE_CONTRACT, self.contract):
            run = case.run_value(notes=note, contract=contract)
            reference = bind(deepcopy(case.reference), completeness.inventory(note, source_contract=contract))
            outputs.append(completeness.evaluate(run, reference, approved_codes=['R12']))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])
        self.assertEqual(outputs[3]['bindings']['source_contract'], self.contract)
        self.assertTrue(outputs[3]['coverage']['complete'])
        for suggestion in outputs[3]['suggestions']:
            self.assertEqual(suggestion['proof']['source_contract'], self.contract)

    def test_general_engine_preserves_selected_contract_at_specificity_boundary(self):
        from core.tests.test_coding_engine import run, concept
        quote = 'The patient reports constipation today.'
        note = self.prefix+quote+'\nSlow-transit constipation, drug-induced constipation and nausea are not diagnosed today.'
        extraction = {'documented_patient_name':'', 'patient_name_evidence':'',
                      'concepts':[concept('Constipation',quote,kind='diagnosis')]}
        def execute(_run, stage, payload, *_rest):
            if stage == 'concepts':
                return deepcopy(extraction)
            candidate = next(x for x in payload['candidates']['c1'] if x['code']=='K59.00')
            return {'choices':[{'concept_id':'c1','entry_id':candidate['entry_id'],
                'code':'K59.00','explanation':'Unit-controlled official route.','missing_detail':''}]}
        results = []
        for contract in (engine.SOAP_SOURCE_CONTRACT,self.contract):
            current = run(note);current.config={'clinical_source_contract':contract}
            with patch.object(engine,'reference_for',return_value=self.reference), \
                 patch.object(engine.coding_provider,'execute',side_effect=execute), \
                 patch('core.coding_licensing.cpt_status',return_value={'available':False}):
                results.append(engine.generate(current))
        self.assertFalse(results[0]['suggestions'])
        self.assertEqual([row['code'] for row in results[1]['suggestions']],['K59.00'])

    def test_plural_and_coordinated_parent_denials_cannot_hide_behind_denied_subtypes(self):
        positive = 'The patient reports constipation today.'
        subtype = 'Slow-transit constipation and drug-induced constipation are not diagnosed today.'
        for denial in ('They deny constipation.', 'They deny nausea and constipation.',
                       'Constipation and nausea are absent.', 'Nausea and constipation are absent.',
                       'They reportedly deny constipation.', 'Constipation and nausea are absent except as noted.',
                       'They deny constipation according to an unresolved account.',
                       'They report the absence of constipation.', 'Constipation and nausea are denied.'):
            for listing in ('', subtype+'\n'):
                with self.subTest(denial=denial, listing=bool(listing)):
                    self.assertIsNone(self.route(self.prefix+positive+'\n'+listing+denial)[1])

    def test_complete_subtype_absence_does_not_become_a_parent_denial(self):
        positive = 'The patient reports constipation today.'
        for denial in ('Slow-transit constipation and drug-induced constipation are absent.',
                       'They deny slow-transit constipation and drug-induced constipation.'):
            with self.subTest(denial=denial):
                self.assertEqual(self.route(self.prefix+positive+'\n'+denial)[1]['code'], 'K59.00')
        for frame in ('Mother:\n', 'Prior encounter:\n'):
            with self.subTest(frame=frame):
                note = self.prefix+positive+'\n'+frame+'They deny constipation.'
                self.assertEqual(self.route(note)[1]['code'], 'K59.00')

    def test_duplicate_current_denial_survives_foreign_and_past_copies(self):
        positive = 'The patient reports constipation today.'
        subtype = 'Slow-transit constipation and drug-induced constipation are not diagnosed today.'
        for denial in ('They deny constipation.', 'Constipation and nausea are absent.',
                       'They categorically deny constipation.', 'They also deny constipation.',
                       'Constipation and nausea are reportedly absent.',
                       'They categorically deny constipation according to their mother.',
                       'Constipation and nausea are reportedly absent according to the mother.'):
            for frame in ('Mother:', 'Prior encounter:', 'Prior encounter on 31 February 2027 for her mother:'):
                with self.subTest(denial=denial, frame=frame):
                    note = self.prefix+positive+'\n'+subtype+'\n'+denial+'\n'+frame+'\n'+denial
                    self.assertIsNone(self.route(note)[1])
            for frame in ('Unverified account:', 'Prior encounter on 31 February 2027:'):
                with self.subTest(denial=denial, frame=frame):
                    note = self.prefix+positive+'\n'+subtype+'\n'+frame+'\n'+denial
                    self.assertIsNone(self.route(note)[1])
