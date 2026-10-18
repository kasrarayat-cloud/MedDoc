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

    def test_complete_shared_negative_lists_and_negative_history_are_not_conditions(self):
        for text in ('She reports no fever, vomiting or blood in the stool.',
                     'She reports no difficulty initiating a swallow, painful swallowing and weight loss.',
                     'She has never had abdominal surgery.',
                     'She has never smoked and does not use alcohol or recreational drugs.',
                     'She has not had a seizure.',
                     'Migraine, epilepsy and an inflammatory disorder have not been diagnosed.',
                     'Infectious and inflammatory causes remain possibilities; neither has been established.',
                     'The cause of these symptoms has not been established.'):
            with self.subTest(text=text):
                notes=self.simple('She reports heartburn today.','Heartburn.\n'+text)
                result=self.result(notes,approved=['R12'])
                self.assertTrue(result['coverage']['complete'],result['inventory'])
                self.assertEqual(len(result['inventory']),1)

    def test_negative_first_clause_never_hides_a_positive_or_ambiguous_tail(self):
        for text in ('No fever, but dysphagia is present today.',
                     'No fever, but dysphagia was evaluated today.',
                     'She reports no fever and ongoing heartburn.',
                     'She has never smoked but reports nausea.',
                     'Migraine and epilepsy have not been diagnosed, but nausea is present.',
                     'She reports no nausea, experiences chest pain.',
                     'She reports no fever despite ongoing vomiting.',
                     'Possible migraine; heartburn is present today.'):
            with self.subTest(text=text):
                inv=completeness.inventory(self.simple('She reports heartburn today.','Heartburn.\n'+text))
                self.assertTrue(inv['unresolved'],inv)

    def test_number_markers_do_not_become_conditions_or_erase_the_following_finding(self):
        inv=completeness.inventory(self.simple('She reports heartburn today.','1. Heartburn.\n2. Nausea.'))
        self.assertEqual([r['condition_text'] for r in inv['items']],['heartburn','Nausea'])
        self.assertFalse(inv['unresolved'])
        for text in ('1. An unexplained disorder requires assessment.', '1.5', '1 unknown condition'):
            with self.subTest(text=text):
                self.assertTrue(completeness.inventory(self.simple('She reports heartburn today.',text))['unresolved'])

    def test_prospective_advice_is_complete_and_cannot_swallow_current_assertions(self):
        for text in ('The patient was advised to seek prompt assessment for severe or worsening pain, vomiting blood or fainting.',
                     'She is instructed to seek urgent evaluation for difficulty swallowing or persistent vomiting.',
                     'He should contact the clinic earlier for inability to maintain hydration.'):
            with self.subTest(text=text):
                result=self.result(self.simple('She reports heartburn today.')+'\nPlan\n'+text,approved=['R12'])
                self.assertTrue(result['coverage']['complete'],result['inventory'])
        for text in ('The patient was advised to seek assessment for vomiting, but nausea is present.',
                     'She was advised to seek assessment for vomiting and reports nausea today.',
                     'She was advised to seek assessment for fever; nausea is evaluated today.',
                     'She should contact the clinic for fever according to an unverified report.'):
            with self.subTest(text=text):
                inv=completeness.inventory(self.simple('She reports heartburn today.')+'\nPlan\n'+text)
                self.assertTrue(inv['unresolved'],inv)

    def test_record_retrieval_action_is_distinct_from_a_governing_account(self):
        for action in ('Requested the previous gastroenterology records.',
                       'Obtained prior rheumatology records.', 'Reviewed available clinical notes.'):
            with self.subTest(action=action):
                notes=self.simple('She reports heartburn today.')+'\nPlan\n'+action+'\nNausea was evaluated today.'
                inv=completeness.inventory(notes)
                self.assertFalse(inv['unresolved'])
                self.assertEqual([r['condition_text'] for r in inv['items']],['heartburn','Nausea'])
        for header in ('According to requested unverified records:', 'Unverified clinical records.'):
            with self.subTest(header=header):
                result=self.result(header+'\n'+self.simple('She reports heartburn today.'),approved=['R12'])
                self.assertFalse(result['coverage']['complete'])

    def test_explicit_presence_with_evaluation_keeps_its_complete_qualification(self):
        notes=self.simple('She is being evaluated for heartburn present for three weeks.')
        inv=completeness.inventory(notes)
        self.assertFalse(inv['unresolved']);self.assertEqual(len(inv['items']),1)
        self.assertEqual(len(inv['items'][0]['evidence']),2)
        self.assertTrue(self.result(notes,approved=['R12'])['coverage']['complete'])
        for body in ('She is being evaluated for heartburn.',
                     'She is being evaluated for heartburn present according to an unverified report.',
                     'She is being evaluated for heartburn present last year.',
                     'She is being evaluated for possible heartburn present today.'):
            with self.subTest(body=body):
                self.assertFalse(self.result(self.simple(body),approved=['R12'])['coverage']['complete'])

    def test_descriptive_report_merges_only_with_its_exact_evaluated_finding(self):
        notes=self.simple('She reports intermittent heartburn for three days.')
        inv=completeness.inventory(notes)
        self.assertEqual(len(inv['items']),1)
        self.assertEqual(inv['items'][0]['source_mentions'],['Heartburn','intermittent heartburn'])
        self.assertEqual(len(inv['items'][0]['evidence']),2)
        self.assertTrue(self.result(notes,approved=['R12'])['coverage']['complete'])
        for phrase in ('left heartburn','maternal heartburn','renal heartburn','possible heartburn'):
            with self.subTest(phrase=phrase):
                result=self.result(self.simple('She reports '+phrase+' today.'),approved=['R12'])
                self.assertFalse(result['coverage']['complete'])
        inv=completeness.inventory(self.simple('She reports intermittent chest pain today.', 'Abdominal pain.'))
        self.assertEqual(len(inv['items']),2)

    def test_complete_rating_and_scoped_summary_preserve_the_existing_finding(self):
        for descriptor in ('The heartburn is rated 4 out of 10.',
                           'Her reported heartburn is rated 2 out of 5 today.',
                           'The heartburn is rated 2.5 out of 10.',
                           'The heartburn is rated 0.25 out of 0.3.',
                           'There are no additional findings beyond the heartburn described above.'):
            with self.subTest(descriptor=descriptor):
                notes=self.simple('She reports heartburn today.')+'\nReview of systems\n'+descriptor
                self.assertTrue(self.result(notes,approved=['R12'])['coverage']['complete'])
        for descriptor in ('The heartburn is rated 4 out of 10 according to her mother.',
                           'The heartburn was rated 4 out of 10 last year.',
                           'The heartburn is not rated 4 out of 10.',
                           'The heartburn is possibly rated 4 out of 10.',
                           'The heartburn is rated 14 out of 10.',
                           'The heartburn is rated 1.1 out of 1.01.',
                           'The heartburn is rated '+('9'*400)+' out of '+('1'*400)+'.',
                           'There are no additional findings beyond the heartburn described above, which is unverified.',
                           'There are no additional findings beyond the heartburn described above; the heartburn has resolved.'):
            with self.subTest(descriptor=descriptor):
                result=self.result(self.simple('She reports heartburn today.')+'\nReview of systems\n'+descriptor,approved=['R12'])
                self.assertFalse(result['coverage']['complete'])
                self.assertFalse(any(c['eligible'] for c in result['suggestions']))

    def test_reported_allergy_history_cannot_erase_current_reaction_or_evaluation(self):
        for history in ('He reports an allergy to amoxicillin, which causes hives.',
                        'She reports an allergy to latex, which causes a rash.'):
            with self.subTest(history=history):
                result=self.result(self.simple('She reports heartburn today.\n'+history),approved=['R12'])
                self.assertTrue(result['coverage']['complete'])
                self.assertTrue(any('allergy history' in e['reason'] for e in result['excluded']))
        for history in ('She reports an allergy to latex, which causes hives today.',
                        'She reports an allergy to latex, which causes hives and she has nausea.',
                        'She reports an allergy to latex, which causes hives; nausea is present today.'):
            with self.subTest(history=history):
                result=self.result(self.simple('She reports heartburn today.\n'+history),approved=['R12'])
                self.assertFalse(result['coverage']['complete'])
        inv=completeness.inventory(self.simple('She reports an allergy to latex, which causes a rash.',
            'Allergic reaction was evaluated today.'))
        self.assertTrue(any('Allergic reaction'==r['condition_text'] for r in inv['items']))

    def test_complete_specific_descendant_does_not_compete_with_its_general_default(self):
        result=self.other_family('The patient reports diarrhea today.',
            'Diarrhea and periumbilical abdominal pain were both evaluated during this encounter.')
        pain=next(r for r in result['inventory'] if r['condition_text']=='periumbilical abdominal pain')
        self.assertEqual([(c['code'],c['eligible']) for c in pain['candidates']],[('R10.33',True)])
        self.assertEqual(pain['candidates'][0]['proof']['excluded_general_routes'][0]['code'],'R10.9')
        for text in ('The patient denies periumbilical pain today.',
                     'The periumbilical pain belongs to her mother.',
                     'The periumbilical pain is uncertain.'):
            with self.subTest(text=text):
                result=self.other_family('The patient reports diarrhea today.',
                    'Diarrhea and periumbilical abdominal pain were both evaluated during this encounter.\n'+text)
                self.assertFalse(any(c['code']=='R10.33' and c['eligible'] for c in result['suggestions']))


class SourceInventoryReferenceBoundaryTests(SimpleTestCase):
    def setUp(self):
        from core.tests.test_corti_semantics import OfficialRouteVocabularyChecks, SOURCE
        self.notes=SOURCE
        fixture=OfficialRouteVocabularyChecks();fixture.setUp()
        self.reference=fixture.reference
        self.reference.release=N(id='unit',system='ICD-10-CM',version='FY2027-unit',
            source_url='https://www.cms.gov/unit',sha256='a'*64,
            effective_from='2026-10-01',effective_until='2027-09-30')
        self.reference.digest=engine.digest({'index':self.reference.index,'tabular':self.reference.tabular})

    def result(self, notes=None, approved=('R10.13','R14.0'), reference=None):
        notes=self.notes if notes is None else notes
        reference=deepcopy(reference or self.reference)
        inv=completeness.inventory(notes);bind(reference,inv)
        run=N(pk='offline',inputs={'notes':notes,'service_date':'2026-10-16'},
            config={'clinical_source_contract':engine.CURRENT_SOURCE_CONTRACT},
            releases=[vars(reference.release)],result={})
        return completeness.evaluate(run,reference,approved_codes=approved,inventory_result=inv)

    def test_retained_full_source_has_two_independently_covered_conditions(self):
        result=self.result()
        self.assertTrue(result['coverage']['complete'],result['inventory'])
        self.assertEqual(len(result['inventory']),2)
        self.assertEqual({r['approved_codes'][0] for r in result['inventory']},{'R10.13','R14.0'})
        self.assertFalse(any(r['condition_text'].startswith('Both ') for r in result['inventory']))
        pain=next(r for r in result['inventory'] if r['approved_codes']==['R10.13'])
        self.assertTrue(any('intermittent' in e['quote'] for e in pain['evidence']))
        bloating=next(r for r in result['inventory'] if r['approved_codes']==['R14.0'])
        self.assertEqual(bloating['source_mentions'],['abdominal bloating','bloating'])
        self.assertTrue(any('Both epigastric pain and bloating' in e['quote'] for e in bloating['evidence']))
        for row in result['inventory']:
            for span in row['evidence']:
                self.assertEqual(self.notes[span['start']:span['end']],span['quote'])

    def test_source_candidate_uses_direct_official_head_and_tabular_modifier_not_a_code_map(self):
        result=self.result(approved=())
        self.assertEqual(result['coverage']['review_required'],2)
        candidate=next(c for c in result['suggestions'] if c['code']=='R14.0')
        self.assertEqual(candidate['route'],'Bloating')
        self.assertEqual(candidate['index_route']['qualified_phrase_proof']['direct_head'],'Bloating')
        self.assertIn('coalesced_source_mentions',candidate['proof'])
        changed=deepcopy(self.reference)
        changed.tabular['codes']['R14.0']='Unrelated swelling'
        result=self.result(reference=changed)
        self.assertFalse(result['coverage']['complete'])
        self.assertFalse(any(c['eligible'] and c['code']=='R14.0' for c in result['suggestions']))

    def test_qualified_head_coverage_never_discards_unknown_modifiers_or_source_holds(self):
        for suffix in ('The reported bloating has resolved.',
                       'The abdominal bloating belongs to her mother.',
                       'The patient denies bloating today.',
                       'It is uncertain whether the bloating is present.',
                       'All the above clinical statements are false.'):
            with self.subTest(suffix=suffix):
                result=self.result(self.notes+'\n'+suffix)
                self.assertFalse(result['coverage']['complete'])
                self.assertFalse(any(c['eligible'] and c['code']=='R14.0' for c in result['suggestions']))
        for prefix in ('left','unverified','maternal','possible'):
            with self.subTest(prefix=prefix):
                result=self.result(self.notes.replace('abdominal bloating',prefix+' abdominal bloating').replace('Abdominal bloating',prefix+' abdominal bloating'))
                self.assertFalse(result['coverage']['complete'])
