"""Fixed synthetic stage controls; no paid evidence, database or credentials."""
from copy import deepcopy
import dataclasses
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from django.test import SimpleTestCase

from ops import provider_campaign as pc, standing_qa as st, standing_qa_elicited as e
from .test_standing_qa import Base, RUNNER_COMMIT, repository

CANONICAL=Path(__file__).parents[3]/'docs/foundation/mutations/20261004-quillmd-v1-standing-api-testing-5.md'


class ElicitedFixedStage(Base):
    def canonical(self, text=None):
        root,path=repository(self,CANONICAL.read_text() if text is None else text,name=CANONICAL.name)
        return st.declared_standing(path,repository=root,uses=('live',),out=io.StringIO())

    def test_complete_fixed_plan_has_five_unique_once_only_send_ids(self):
        inputs=e.frozen_inputs();sends=e.plan_sends(inputs)
        self.assertEqual(tuple(s.case for s in sends),e.CASE_IDS)
        self.assertEqual([s.id for s in sends],[f'elicited:{case}'for case in e.CASE_IDS])
        self.assertEqual([s.index for s in sends],list(range(1,6)))
        self.assertEqual({s.path for s in sends},{'field_relations'})
        self.assertEqual({s.pricing_key for s in sends},{'ordinary_notes_field_relations'})
        self.assertEqual(st.standing_plan(e.STAGE,inputs),sends)

    def test_changed_missing_or_reordered_source_plan_is_refused(self):
        for mutate in (lambda x:x['elicited']['cases'].pop(),
                       lambda x:x['elicited']['cases'].reverse(),
                       lambda x:x['elicited']['cases'][0].update(notes='Changed.'),
                       lambda x:x['elicited']['forms']['elicited-single-v1'].update(sha256='0'*64)):
            inputs=deepcopy(e.frozen_inputs());mutate(inputs)
            with self.assertRaises(pc.Refused):e.plan_sends(inputs)

    def test_arbitrary_send_id_path_form_and_pricing_are_refused(self):
        inputs=e.frozen_inputs();send=e.plan_sends(inputs)[0]
        for key,value in [('id','elicited:E99'),('path','default'),('form','restricted-original'),('pricing_key','ordinary_notes')]:
            with self.subTest(key=key),self.assertRaises(pc.Refused):
                e.send_inputs(dataclasses.replace(send,**{key:value}),inputs)

    def test_blank_original_bytes_and_actual_detected_catalogues_match_manifest(self):
        from documents.service import inspect_template
        from .test_standing_qa import scratch
        inputs=e.frozen_inputs();folder=scratch(self)/'forms';folder.mkdir(mode=0o700)
        for name,spec in inputs['elicited']['forms'].items():
            raw=e.build(name);self.assertEqual(raw,e.build(name));self.assertEqual(hashlib.sha256(raw).hexdigest(),spec['sha256'])
            path=folder/(name+'.docx');path.write_bytes(raw)
            self.assertEqual(inspect_template(path,engine='v3')['fields'],spec['fields'])
            self.assertTrue(all(f['kind']in('text','long_text')and not f.get('write_protected')for f in spec['fields']))

    def test_mapping_manifest_cannot_hide_changed_source_or_omissions(self):
        from documents.import_selection import digest
        fields=e.frozen_inputs()['elicited']['forms']['elicited-single-v1']['fields'];sha='a'*64
        coverage={'block_generation':False,'selected_engine_issues':[], 'legacy_omissions':[], 'legacy_unmapped':[], 'v3_uncovered_legacy_places':[]}
        manifest={'engine':'v3','source_sha256':sha,'mapping_sha256':digest(fields),'initial_mapping_sha256':digest(fields),'coverage':coverage}
        self.assertEqual(e.mapping_admission(sha,fields,manifest),coverage)
        for mutate in (lambda x:x.update(source_sha256='b'*64),lambda x:x.update(mapping_sha256='b'*64),
                       lambda x:x['coverage'].update(block_generation=True),lambda x:x['coverage'].update(selected_engine_issues=[{'id':'omitted'}])):
            bad=deepcopy(manifest);mutate(bad)
            with self.assertRaises(pc.Refused):e.mapping_admission(sha,fields,bad)

    def test_all_eight_correct_answers_and_three_safe_holds_are_scored_separately(self):
        inputs=e.frozen_inputs()['elicited'];counts={}
        for case in inputs['cases']:
            fields=inputs['forms'][case['form']]['fields']
            answers={f['key']:{'status':'supported','text':case['desired_supported'][f['label']]}if f['label']in case['desired_supported']else{'status':'conflict','text':''}for f in fields}
            for outcome in e.usefulness(case,fields,e.stages.steps.field_outcomes(answers)).values():counts[outcome]=counts.get(outcome,0)+1
        self.assertEqual(counts,{'supported_correct':8,'held_correct':3})

    def test_wrong_adopted_answer_is_unsafe_and_missing_positive_is_overheld(self):
        inputs=e.frozen_inputs()['elicited'];case=inputs['cases'][0];fields=inputs['forms'][case['form']]['fields'];key=fields[0]['key']
        self.assertEqual(e.usefulness(case,fields,{key:{'status':'supported','text':'Wrong.'}}),{key:'unsupported_accepted'})
        self.assertEqual(e.usefulness(case,fields,{}),{key:'over_held'})
        negative=inputs['cases'][2]
        self.assertEqual(e.usefulness(negative,fields,{key:{'status':'supported','text':case['notes']}}),{key:'unsupported_accepted'})
        with self.assertRaises(pc.Refused):e.usefulness(case,fields+[{'key':'extra','label':'Unmeasured'}],{})

    def test_canonical_five_is_exact_twenty_four_at_distinct_places(self):
        d=self.canonical();places=st.require_live(d)
        self.assertEqual(d.campaign,'quillmd-v1-standing-api-testing-20261004-5')
        self.assertEqual(str(places['root']),'/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-5')
        self.assertEqual(d.qa_database,'quillmd_qa_standing_20261004_5')
        self.assertEqual([(s.id,s.sends,s.requires)for s in d.stages],[('model_check',1,None),(e.STAGE,5,'model_check'),('notes_qualification',14,'model_check'),('transcription',4,'model_check')])
        self.assertEqual(sum(s.sends for s in d.stages),24)
        self.assertEqual(d.model,'claude-sonnet-5-5');self.assertIsNone(d.monetary_ceiling);self.assertEqual(d.automatic_retries,'none')

    def test_new_stage_requires_whole_count_and_its_declared_synthetic_manifest(self):
        text=CANONICAL.read_text()
        for change in (text.replace('elicited_qualification sends 5','elicited_qualification sends 4'),
                       text.replace('elicited_qualification sends 5','elicited_qualification sends 6'),
                       text.replace(e.MANIFEST_SHA256,'0'*64),
                       text.replace(f'elicited_fixture_manifest: {e.MANIFEST_SHA256}\n','')):
            with self.assertRaises(pc.Refused):self.canonical(change)

    def test_old_campaign_has_no_new_stage_and_comparison_denominators_stay_fixed(self):
        old=CANONICAL.with_name('20261004-quillmd-v1-standing-api-testing-4.md')
        root,path=repository(self,old.read_text(),name=old.name)
        d=st.declared_standing(path,repository=root,uses=('live',),out=io.StringIO())
        with self.assertRaises(pc.Refused):st.stage_inputs(e.STAGE,d)
        inputs=st.sq.stages_module().frozen_inputs()
        self.assertEqual(len(st.standing_plan('notes_comparison',inputs)),28)
        self.assertEqual(len(st.standing_plan('notes_qualification',inputs)),14)

    def test_unsafe_new_result_stops_but_old_worker_record_stays_immutable(self):
        verdict=pc.classify_case({'f':'unsupported_accepted'},[])
        record={'verdict':verdict,'stops_stage':False,'recorded_as':'held_ambiguity'};before=deepcopy(record)
        qualified,stops=st.qualification_result(e.STAGE,record,False)
        self.assertTrue(stops);self.assertEqual(record,before);self.assertTrue(qualified['stops_stage'])
        self.assertEqual(st.qualification_result('notes_comparison',record,False),(record,False))
        with self.assertRaises(pc.Refused):st.qualification_result(e.STAGE,{'verdict':{}},False)

    def test_unknown_attempt_is_terminal_and_is_never_planned_again(self):
        # Only a task-owned temporary synthetic fixture ledger is written.
        # This deliberately leaves an attempt unknown, then uses normal settle.
        campaign=self.campaign(dataclasses.replace(self.canonical(),qa_signing_key_file=None));self.pass_model_check(campaign)
        inputs=st.stage_inputs(e.STAGE,campaign.declaration);send=st.standing_plan(e.STAGE,inputs)[0]
        st.begin_run(campaign,e.STAGE,[send],inputs,1,{'runner_commit':RUNNER_COMMIT})
        campaign.admit(e.STAGE,'0.1',runner_commit=RUNNER_COMMIT)
        attempt=self.notes_attempt(campaign,send,inputs,changes={'stage':e.STAGE})
        campaign.ledger.write_attempt(attempt)
        self.assertNotIn(send,st.remaining_sends(campaign,e.STAGE,e.plan_sends(inputs)))
        st.settle(campaign)
        self.assertEqual(campaign.ledger.stage_state(e.STAGE)['state'],'failed')
        with self.assertRaises(pc.Refused):campaign.stage_open(e.STAGE)


class ElicitedNormalizedGrading(SimpleTestCase):
    """The actual worker normalizes conflict to held before passing first results to its judge."""
    def setUp(self):
        raw = e.MANIFEST.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), e.MANIFEST_SHA256)
        self.inputs = json.loads(raw)

    def grade(self, case_id, raw_answers):
        case = next(case for case in self.inputs['cases'] if case['id'] == case_id)
        fields = self.inputs['forms'][case['form']]['fields']
        return e.usefulness(case, fields, e.stages.steps.field_outcomes(raw_answers))

    def test_actual_conflict_normalization_keeps_all_three_negative_holds(self):
        for case_id in ('E03', 'E04', 'E05'):
            with self.subTest(case=case_id):
                self.assertEqual(self.grade(case_id, {'v3_1': {'status': 'conflict', 'text': ''}}),
                                 {'v3_1': 'held_correct'})

    def test_actual_positive_normalization_keeps_eight_exact_answers(self):
        for case in self.inputs['cases'][:2]:
            fields = self.inputs['forms'][case['form']]['fields']
            raw = {f['key']: {'status': 'supported', 'text': case['desired_supported'][f['label']]}
                   for f in fields}
            self.assertEqual(set(self.grade(case['id'], raw).values()), {'supported_correct'})
        case = self.inputs['cases'][0]
        self.assertEqual(self.grade('E01', {'v3_1': {'status': 'supported', 'text': 'Wrong answer.'}}),
                         {'v3_1': 'unsupported_accepted'})
        self.assertEqual(self.grade('E01', {'v3_1': {'status': 'conflict', 'text': ''}}),
                         {'v3_1': 'over_held'})

    def test_negative_nonempty_hold_and_supported_answer_still_fail(self):
        text = self.inputs['cases'][2]['notes']
        for status in ('conflict', 'held', 'missing', 'supported'):
            with self.subTest(status=status):
                self.assertEqual(self.grade('E03', {'v3_1': {'status': status, 'text': text}}),
                                 {'v3_1': 'unsupported_accepted'})
        self.assertEqual(self.grade('E03', {'v3_1': {'status': 'supported', 'text': ''}}),
                         {'v3_1': 'unsupported_accepted'})

    def test_missing_or_unrecognized_answer_shape_never_gets_hold_credit(self):
        self.assertEqual(self.grade('E03', {}), {'v3_1': 'unsupported_accepted'})
        for status in ('left_blank', 'edited', 'unknown', None):
            with self.subTest(status=status):
                self.assertEqual(self.grade('E03', {'v3_1': {'status': status, 'text': ''}}),
                                 {'v3_1': 'unsupported_accepted'})
        with self.assertRaises(KeyError):
            self.grade('E03', {'v3_1': {}})
