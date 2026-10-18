"""Pure source-inventory and authoritative completeness controls; no requests."""
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_completeness as completeness, coding_engine as engine
from core.tests.test_coding_nec import retained_case
from core.tests.test_coding_source_governance import NOTES


def bind(reference, inv):
    reference.completeness_scope = {'contract': completeness.REFERENCE_CONTRACT,
        'source_sha256': inv['source_sha256'], 'inventory_sha256': inv['inventory_sha256'],
        'terms': sorted(set(inv['reference_terms'])), 'complete': True}
    return reference


class SourceCompletenessTests(SimpleTestCase):
    def setUp(self):
        self.case = retained_case()

    def result(self, notes=NOTES, approved=(), reference=None, run=None):
        run = run or self.case.run_value(notes=notes)
        reference = reference or deepcopy(self.case.reference)
        inv = completeness.inventory(notes)
        bind(reference, inv)
        return completeness.evaluate(run, reference, approved_codes=approved, inventory_result=inv)

    def simple(self, body, assessment='Heartburn.'):
        return ('Patient: Synthetic Uma Bell\nHistory of present illness\n' + body
            + '\nAssessment\n' + assessment)

    def test_actual_complete_source_independent_of_extractor_omission(self):
        empty = completeness.inventory(NOTES)
        annotated = completeness.inventory(NOTES, retained_facts=[{'id':'fake','value':'heartburn'}])
        self.assertEqual(empty, annotated)
        self.assertEqual([x['condition_text'] for x in empty['items']], ['esophageal dysphagia', 'heartburn'])
        self.assertFalse(empty['unresolved'])
        for row in empty['items']:
            self.assertTrue(row['current_evaluation_evidence'])
            for span in row['evidence']:
                self.assertEqual(NOTES[span['start']:span['end']], span['quote'])
        self.assertIn('Dysphagia', empty['reference_terms'])

    def test_actual_underspecified_provider_does_not_control_separate_source_candidate(self):
        run = self.case.run_value()
        run.result = {'suggestions':[{'code':'R13.10','eligible':False},{'code':'R12','eligible':True}],
            'adapter':{'alternatives':[{'code':'R13.19','eligible':False}]} }
        before = deepcopy(vars(run))
        result = self.result(run=run, approved=['R12','99204'])
        self.assertEqual(vars(run), before)
        self.assertEqual([(x['condition_text'],x['state']) for x in result['inventory']],
            [('esophageal dysphagia','review_required'),('heartburn','covered')])
        self.assertEqual([(c['code'],c['eligible']) for c in result['suggestions']], [('R13.19',True),('R12',True)])
        self.assertFalse(result['coverage']['complete'])
        candidate = result['suggestions'][0]
        self.assertEqual(candidate['origin'], 'saved_source')
        self.assertTrue(candidate['id'].startswith('source:'))
        self.assertEqual(candidate['route'],'Dysphagia > specified NEC')
        self.assertIn('clinical_specificity',candidate['index_route'])
        self.assertTrue(any(i.get('resolution') for i in candidate['instructions']))

    def test_omitted_and_correct_predictions_make_identical_source_candidates(self):
        run = self.case.run_value()
        outputs = []
        for provider in ({}, {'suggestions':[{'code':'R13.19','eligible':True}]},
                         {'alternatives':[{'code':'K21.9','eligible':True}]}):
            run.result = provider
            outputs.append(self.result(run=run)['suggestions'])
        self.assertEqual(outputs[0],outputs[1]); self.assertEqual(outputs[1],outputs[2])

    def test_legitimate_approved_codes_are_rechecked_and_cpt_is_not_coverage(self):
        result = self.result(approved=['R12','R13.19'])
        self.assertTrue(result['coverage']['complete'])
        result = self.result(approved=['R13.10','99204'])
        self.assertEqual(result['coverage']['covered'],0)
        self.assertEqual(result['coverage']['review_required'],2)

    def test_legacy_contract_result_and_selection_remain_unchanged(self):
        run = self.case.run_value(contract=engine.SOURCE_CONTRACT)
        run.selection={'selected_ids':['selected:1'],'overrides':{}}
        before=deepcopy(vars(run))
        result=self.result(run=run,approved=['R12'])
        self.assertEqual(vars(run),before)
        self.assertEqual(result['bindings']['source_contract'],engine.CURRENT_SOURCE_CONTRACT)
        self.assertEqual(result['coverage']['review_required'],1)

    def test_unfamiliar_current_wording_and_nominal_retrieval(self):
        for text in ('She experiences heartburn for nine days.',
                     'The patient endorses intermittent heartburn today.',
                     'The patient describes heartburn after meals.'):
            notes=self.simple(text)
            with self.subTest(text=text):
                result=self.result(notes)
                self.assertTrue(any(c['code']=='R12' and c['eligible'] for c in result['suggestions']))
        terms=completeness.reference_terms('periumbilical abdominal pain')
        self.assertIn('pain',terms);self.assertIn('periumbilical abdominal pain',terms)
        self.assertNotIn('peri',terms)

    def other_family(self, text, assessment='Periumbilical abdominal pain.'):
        from core.tests.test_coordinated_coding import reference, run
        value=reference()
        # The retained reduced fixture predates persisted CodingRelease digest
        # metadata. This local fixture binding is not a live release receipt.
        value.digest=engine.digest({'index':value.index,'tabular':value.tabular})
        notes=self.simple(text,assessment)
        current=run(notes=notes);current.releases=[vars(value.release)];current.result={}
        return self.result(notes,reference=value,run=current)

    def test_complete_official_qualified_phrase_supports_independent_family(self):
        result=self.other_family('The patient reports periumbilical abdominal pain today and diarrhea for three days.',
            'Periumbilical abdominal pain.\nDiarrhea.')
        self.assertEqual([(c['code'],c['eligible']) for c in result['suggestions']],[('R10.33',True),('R19.7',True)])
        self.assertIn('qualified_phrase_proof',result['suggestions'][0]['index_route'])
        self.assertEqual(result['coverage']['unresolved'],0)

    def test_qualified_phrase_unknown_modifiers_and_disconnected_sites_are_held(self):
        for term in ('potential periumbilical abdominal pain','maternal periumbilical abdominal pain',
                     'left periumbilical abdominal pain','renally periumbilical abdominal pain',
                     'periumbilically abdominal pain','periumbilical fullness and shoulder pain'):
            with self.subTest(term=term):
                result=self.other_family('The patient reports '+term+' today.',term+'.')
                self.assertFalse(any(c['code']=='R10.33' and c['eligible'] for c in result['suggestions']))

    def test_qualified_phrase_keeps_parent_denial_retraction_and_ownership_checks(self):
        for suffix in ('The patient denies pain today.', 'The pain was documented in error.',
                       'The pain belongs to another patient.', 'The pain is uncertain.'):
            text='The patient reports periumbilical abdominal pain today.\n'+suffix
            with self.subTest(suffix=suffix):
                result=self.other_family(text)
                self.assertFalse(any(c['code']=='R10.33' and c['eligible'] for c in result['suggestions']))

    def test_current_condition_reference_cannot_leave_a_selectable_candidate(self):
        for suffix in ('The pain described above has resolved.',
                       'The pain described above was last year.',
                       'The reported abdominal pain is hypothetical.',
                       'The reported pain is attributed to her mother.',
                       'The patient is not experiencing pain now.',
                       'The documented pain remains uncertain after chart review.',
                       'Her reported pain is possibly unrelated to the current encounter.',
                       'The pain mentioned earlier was from a previous visit.',
                       'The previously reported pain has resolved.',
                       'The pain previously described above has resolved.',
                       'She no longer experiences abdominal pain.',
                       'The pain described above may be historical.'):
            with self.subTest(suffix=suffix):
                result=self.other_family('The patient reports periumbilical abdominal pain today.',
                    'Periumbilical abdominal pain.\n'+suffix)
                self.assertFalse(any(c['code']=='R10.33' and c['eligible'] for c in result['suggestions']))
                self.assertEqual(result['coverage']['review_required'],0)

    def test_current_reference_guard_preserves_independent_foreign_history_and_affirmations(self):
        for suffix in ('', 'Her mother has abdominal pain.',
                       'Her mother denies pain.',
                       'Previous encounter:\nThe pain described above has resolved.',
                       'Mother:\nThe reported abdominal pain is hypothetical.',
                       'The pain described above is present today.',
                       'The reported abdominal pain persists today.',
                       'The pain was not documented in error.',
                       'Nausea has resolved.',
                       'The patient denies chest pain.'):
            with self.subTest(suffix=suffix):
                result=self.other_family('The patient reports periumbilical abdominal pain today.',
                    'Periumbilical abdominal pain.\n'+suffix)
                self.assertTrue(any(c['code']=='R10.33' and c['eligible'] for c in result['suggestions']))

    def test_condition_reference_guard_also_protects_ordinary_source_routes(self):
        for suffix in ('The heartburn described above has resolved.',
                       'The reported heartburn is attributed to her father.',
                       'The patient is not experiencing heartburn now.'):
            with self.subTest(suffix=suffix):
                result=self.result(self.simple('The patient reports heartburn today.')+'\n'+suffix)
                self.assertFalse(any(c['eligible'] for c in result['suggestions']))

    def test_outer_condition_predicate_is_not_erased_by_embedded_presence(self):
        for suffix in ('It is false that the reported pain is present.',
                       'It is uncertain whether the reported pain is present.',
                       'After assuming the reported pain is present.',
                       'If the reported pain is present.',
                       'It is false that the pain is present.',
                       'It is uncertain whether pain is present.',
                       'We cannot verify that the documented pain is present.'):
            with self.subTest(suffix=suffix):
                result=self.other_family('The patient reports periumbilical abdominal pain today.',
                    'Periumbilical abdominal pain.\n'+suffix)
                self.assertFalse(any(c['eligible'] for c in result['suggestions']))
        result=self.other_family('The patient reports periumbilical abdominal pain today.',
            'Periumbilical abdominal pain.\nThe patient reports the pain today.')
        self.assertTrue(any(c['code']=='R10.33' and c['eligible'] for c in result['suggestions']))

    def test_unresolved_current_assertion_vetoes_its_condition_candidate(self):
        for suffix in ('It is false that the patient experiences heartburn today.',
                       'After assuming the patient reports heartburn today.',
                       'We cannot independently verify that she reports heartburn today.'):
            with self.subTest(suffix=suffix):
                result=self.result(self.simple('The patient reports heartburn today.')+'\n'+suffix)
                self.assertFalse(any(c['eligible'] for c in result['suggestions']))
                self.assertEqual(result['coverage']['review_required'],0)
        result=self.result(self.simple('The patient reports heartburn today.')+
            '\nIt is false that the patient experiences nausea today.')
        self.assertTrue(any(c['code']=='R12' and c['eligible'] for c in result['suggestions']))
        self.assertFalse(result['coverage']['complete'])

    def test_qualified_account_headers_govern_all_following_structural_sections(self):
        for header in ('According to an unverified account:',
                       'Based on a disputed clinical record:',
                       'From a possibly fabricated source:',
                       'Per an unconfirmed report:',
                       'Unconfirmed clinical statements:',
                       'According to an account whose owner is uncertain:'):
            for position in ('before_identity','after_identity'):
                notes=self.simple('The patient reports heartburn today.')
                if position=='before_identity':notes=header+'\n'+notes
                else:notes=notes.replace('History of present illness',header+'\nHistory of present illness')
                with self.subTest(header=header,position=position):
                    result=self.result(notes,approved=['R12'])
                    self.assertFalse(result['coverage']['complete'])
                    self.assertFalse(any(c['eligible'] for c in result['suggestions']))
                    self.assertGreater(result['coverage']['unresolved'],0)
        for header in ('History of present illness:', 'Current encounter:', 'Subjective:'):
            with self.subTest(neutral=header):
                result=self.result(self.simple('The patient reports heartburn today.').replace(
                    'History of present illness',header+'\nHistory of present illness'),approved=['R12'])
                self.assertTrue(result['coverage']['complete'])
        for frame in ('Mother:', 'Previous encounter:'):
            notes=('Patient: Synthetic Uma Bell\n'+frame+'\nAccording to an unverified account:\n'
                'She has nausea.\nCurrent patient: Synthetic Uma Bell\nHistory of present illness\n'
                'The patient reports heartburn today.\nAssessment\nHeartburn.')
            with self.subTest(separate=frame):
                result=self.result(notes,approved=['R12'])
                self.assertTrue(result['coverage']['complete'])

    def test_account_scope_does_not_depend_on_header_punctuation(self):
        for framing in ('Unverified account', 'According to an unverified account',
                        'Unconfirmed clinical statements', 'From a disputed report',
                        'Unverified reports', 'Unverified records'):
            for punctuation in ('', '.', ':'):
                for before_identity in (False, True):
                    header=framing+punctuation
                    notes=self.simple('The patient reports heartburn today.')
                    notes=(header+'\n'+notes if before_identity else notes.replace(
                        'History of present illness',header+'\nHistory of present illness'))
                    with self.subTest(header=header,before_identity=before_identity):
                        result=self.result(notes,approved=['R12'])
                        self.assertFalse(result['coverage']['complete'])
                        self.assertFalse(any(c['eligible'] for c in result['suggestions']))
        for framing in ('Unverified account', 'According to an unverified account.'):
            for scope in ('Mother:', 'Previous encounter:'):
                notes=('Patient: Synthetic Uma Bell\n'+scope+'\n'+framing+'\n'
                    'She has nausea.\nCurrent patient: Synthetic Uma Bell\nHistory of present illness\n'
                    'The patient reports heartburn today.\nAssessment\nHeartburn.')
                with self.subTest(separate=scope,framing=framing):
                    self.assertTrue(self.result(notes,approved=['R12'])['coverage']['complete'])

    def test_evaluated_for_alone_is_not_affirmed_disease_or_symptom(self):
        for text in ('Heartburn was evaluated today.', 'The patient was evaluated for heartburn.'):
            with self.subTest(text=text):
                result=self.result('Patient: Synthetic Uma Bell\nAssessment\n'+text)
                self.assertFalse(any(c['eligible'] for c in result['suggestions']))
                self.assertFalse(result['coverage']['complete'])

    def test_unknown_current_assertion_remains_visible_without_model_fact(self):
        notes=self.simple('The patient reports heartburn today.', 'Heartburn.\nAn unexplained syndrome requires further assessment.')
        result=self.result(notes,approved=['R12'])
        self.assertEqual(result['coverage']['unresolved'],1)
        self.assertFalse(result['coverage']['complete'])
        self.assertIn('unexplained',result['inventory'][-1]['condition_text'])

    def test_unknown_current_condition_assertions_outside_assessment_stay_visible(self):
        for extra in ('She suffers from an unexplained disorder.',
                      'Current problems: An unexplained disorder.',
                      'Her current complaint is an unexplained disorder.',
                      'An unexplained disorder is present today.'):
            notes=self.simple('The patient reports heartburn today.')+'\nPlan\n'+extra
            with self.subTest(extra=extra):
                result=self.result(notes,approved=['R12'])
                self.assertEqual(result['coverage']['unresolved'],1)
                self.assertFalse(result['coverage']['complete'])

    def test_evaluation_discovery_is_broader_than_code_permission(self):
        extras=('Nausea was also evaluated today.','I evaluated her nausea today.',
            'We assessed nausea today.','Nausea was carefully assessed today.',
            'We addressed her active nausea during this visit.',
            'Other problems addressed today: nausea.',
            'At today’s visit we evaluated nausea and headache.',
            'Nausea evaluated today.','Today she reports nausea.',
            'I diagnosed migraine today.','Assessment and plan\nNausea.',
            'Problems addressed\nNausea.','A/P\nNausea.',
            'Clinical assessment / plan\nNausea.')
        for extra in extras:
            notes=self.simple('She reports heartburn today.')+'\nPlan\n'+extra
            with self.subTest(extra=extra):
                result=self.result(notes,approved=['R12'])
                self.assertFalse(result['coverage']['complete'])
                self.assertGreater(result['coverage']['unresolved'],0)
                self.assertFalse(any(c['code']!='R12' and c['eligible'] for c in result['suggestions']))
        for extra in ('No nausea.','Possible nausea.','Her mother had nausea.',
                      'Nausea was evaluated last year.'):
            with self.subTest(excluded=extra):
                result=self.result(self.simple('She reports heartburn today.')+'\nPlan\n'+extra,approved=['R12'])
                self.assertTrue(result['coverage']['complete'])

    def test_uncertainty_history_negative_and_foreign_are_not_current_codes(self):
        for text in ('Possible heartburn.', 'No heartburn.', 'Heartburn is not established.',
                     'The patient asks whether she has heartburn.', 'A risk of heartburn.'):
            with self.subTest(text=text):
                result=self.result('Patient: Synthetic Uma Bell\nAssessment\n'+text)
                self.assertFalse(any(c['eligible'] for c in result['suggestions']))
        for heading in ('Mother:', 'Previous encounter:', 'Hypothetical example:'):
            notes='Patient: Synthetic Uma Bell\n'+heading+'\nAssessment\nHeartburn.'
            with self.subTest(heading=heading):
                self.assertFalse(any(c['eligible'] for c in self.result(notes)['suggestions']))

    def test_unknown_modifiers_never_become_permission_from_retrieval(self):
        for modifier in ('familial','conjectured','unconfirmed','renal','left','unverified'):
            text='The patient reports '+modifier+' heartburn today.'
            notes=self.simple(text,modifier+' heartburn.')
            with self.subTest(modifier=modifier):
                self.assertFalse(any(c['eligible'] for c in self.result(notes)['suggestions']))

    def test_later_correction_denial_and_global_governance_revoke_current_candidate(self):
        for suffix in ('Heartburn was documented in error.',
                       'The reported heartburn actually concerned another patient.',
                       'The patient denies heartburn today.',
                       'All the above clinical statements are false.'):
            notes=self.simple('The patient reports heartburn today.')+'\n'+suffix
            with self.subTest(suffix=suffix):
                self.assertFalse(any(c['eligible'] for c in self.result(notes)['suggestions']))

    def test_qualified_reports_and_active_retractions_stay_held(self):
        for text in ('The patient reports heartburn according to an unverified report.',
                     'The patient reports heartburn and retracts that statement.',
                     'The patient reports heartburn and it is now denied.'):
            with self.subTest(text=text):
                result=self.result(self.simple(text, 'Heartburn is a possibility only.'))
                self.assertFalse(any(c['eligible'] for c in result['suggestions']))

    def test_instructions_and_unknown_causality_are_not_waived(self):
        for suffix in ('She had a stroke last year.',
                       'She attributes her swallowing difficulty to an earlier neurological event.'):
            result=self.result(NOTES+'\n'+suffix)
            with self.subTest(suffix=suffix):
                self.assertFalse(any(c['code']=='R13.19' and c['eligible'] for c in result['suggestions']))
        with self.assertRaises(ValidationError):
            self.result(self.simple('The patient reports heartburn today.'),approved=['K30'])

    def test_reference_attestation_dates_and_inventory_are_mandatory(self):
        run=self.case.run_value(); inv=completeness.inventory(NOTES)
        for mutation in ('absent','source','inventory','terms','complete','date','release'):
            reference=bind(deepcopy(self.case.reference),inv)
            if mutation=='absent': del reference.completeness_scope
            elif mutation in ('source','inventory'):reference.completeness_scope[mutation+'_sha256']='0'*64
            elif mutation=='terms':reference.completeness_scope['terms'].pop()
            elif mutation=='complete':reference.completeness_scope['complete']=False
            elif mutation=='date':reference.release.effective_until='2026-10-01'
            else:reference.release.sha256='0'*64
            with self.subTest(mutation=mutation),self.assertRaises(ValidationError):
                completeness.evaluate(run,reference)
        run.inputs['service_date']='2026-10-18'
        with self.assertRaises(ValidationError):
            completeness.evaluate(run,bind(deepcopy(self.case.reference),inv))

    def test_complete_forest_required_even_if_selected_route_still_exists(self):
        run=self.case.run_value();inv=completeness.inventory(NOTES)
        for mode in ('missing-child','cycle','duplicate'):
            reference=bind(deepcopy(self.case.reference),inv)
            if mode=='missing-child':reference.index.pop(2)
            elif mode=='duplicate':reference.index.append(deepcopy(reference.index[0]))
            else:
                root=reference.index[1];child=reference.index[2]
                root['parent_id']=child['id'];child['children'].append(root['id'])
            with self.subTest(mode=mode),self.assertRaises(ValidationError):
                completeness.evaluate(run,reference)

    def test_empty_source_and_zero_condition_inventory_do_not_manufacture_success(self):
        with self.assertRaises(ValidationError):completeness.inventory('')
        result=self.result('Patient: Synthetic Uma Bell\nPlan\nFollow-up is planned.')
        self.assertEqual(result['inventory'],[])
        self.assertFalse(result['coverage']['complete'])

    def test_finite_bounds_and_stale_inventory_fail_closed(self):
        with self.assertRaises(ValidationError):
            completeness.inventory('Patient: Synthetic Uma Bell\nAssessment\n'+' '.join('word'+chr(97+i) for i in range(20))+'.')
        run=self.case.run_value();inv=completeness.inventory(NOTES);reference=bind(deepcopy(self.case.reference),inv)
        inv['inventory_sha256']='0'*64
        with self.assertRaises(ValidationError):completeness.evaluate(run,reference,inventory_result=inv)
