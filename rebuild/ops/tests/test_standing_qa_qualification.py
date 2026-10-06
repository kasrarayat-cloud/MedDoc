"""Fixed prospective qualified arm; pure normal-ledger tests, never paid evidence."""
from copy import deepcopy
import dataclasses
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from decimal import Decimal
from contextlib import nullcontext
import sys
import types

from ops import provider_campaign as pc, standing_qa as st, standing_qa_notes_review as nr
from . import network_guard
from .test_standing_qa import (Base, FakeWorker, RUNNER_COMMIT, SYNTHETIC_KEY,
                              fixture_text, parse, repository, sq)

CANONICAL = Path(__file__).parents[3] / 'docs/foundation/mutations/20261004-quillmd-v1-standing-api-testing-4.md'
CASES = tuple(f'N{i:02d}' for i in range(1, 14)) + ('N16',)


def setUpModule():
    network_guard.start()


def tearDownModule():
    network_guard.stop()


def qualified_fixture():
    return fixture_text().replace('stage: notes_comparison sends 28', 'stage: notes_qualification sends 14') + \
        f'\nnotes_mapping_review: {nr.MANIFEST_SHA256}\n'


class QualificationPlanAndDeclaration(unittest.TestCase):
    def setUp(self):
        self.inputs = sq.stages_module().frozen_inputs()

    def canonical(self, text=None):
        root, path = repository(self, CANONICAL.read_text() if text is None else text,
                                name=CANONICAL.name)
        return st.declared_standing(path, repository=root, uses=('live',), out=io.StringIO())

    def test_historical_comparison_remains_twenty_eight_and_never_changes_inputs(self):
        before = deepcopy(self.inputs)
        historical = st.standing_plan('notes_comparison', self.inputs)
        qualified = st.standing_plan('notes_qualification', self.inputs)
        self.assertEqual(self.inputs, before)
        self.assertEqual(len(historical), 28)
        self.assertEqual([s.path for s in historical], ['default'] * 14 + ['field_relations'] * 14)
        self.assertEqual([s.record() for s in qualified],
                         [dataclasses.replace(s, index=i).record() for i,s in enumerate(historical[14:], 1)])

    def test_complete_qualified_arm_has_fixed_ids_order_inputs_and_pricing(self):
        sends = st.standing_plan('notes_qualification', self.inputs)
        self.assertEqual(tuple(s.case for s in sends), CASES)
        self.assertEqual([s.index for s in sends], list(range(1, 15)))
        self.assertEqual([s.id for s in sends], [f'notes:{case}:field_relations' for case in CASES])
        self.assertEqual({s.path for s in sends}, {'field_relations'})
        self.assertEqual({s.pricing_key for s in sends}, {'ordinary_notes_field_relations'})
        for original, qualified in zip(st.standing_plan('notes_comparison', self.inputs)[14:], sends):
            self.assertEqual(st.send_inputs(original, self.inputs), st.send_inputs(qualified, self.inputs))

    def test_missing_duplicate_unknown_and_substituted_cases_refuse(self):
        for change in ('missing', 'duplicate', 'unknown', 'other_id'):
            inputs = deepcopy(self.inputs)
            cases = inputs['cases']['cases']
            row = next(c for c in cases if c['id'] == 'N16')
            if change == 'missing': cases.remove(row)
            elif change == 'duplicate': row['id'] = 'N01'
            elif change == 'unknown': row['id'] = 'N99'
            else: row['id'] = 'N14'
            with self.subTest(change=change), self.assertRaises(pc.Refused):
                st.standing_plan('notes_qualification', inputs)

    def test_synthesized_wrong_path_price_and_duplicate_wire_ids_refuse(self):
        original = st.standing_plan('notes_comparison', self.inputs)
        for field, value in [('path', 'default'), ('pricing_key', 'ordinary_notes'),
                             ('kind', 'mapping'), ('id', original[14].id)]:
            rows = list(original)
            rows[-1] = dataclasses.replace(rows[-1], **{field:value})
            with self.subTest(field=field), patch.object(st, 'standing_plan', wraps=st.standing_plan) as plan:
                real = plan._mock_wraps
                plan.side_effect = lambda stage, inputs: rows if stage == 'notes_comparison' else real(stage, inputs)
                with self.assertRaises(pc.Refused): real('notes_qualification', self.inputs)

    def test_canonical_four_is_nineteen_sends_at_its_own_places(self):
        d = self.canonical()
        self.assertEqual(d.campaign, 'quillmd-v1-standing-api-testing-20261004-4')
        places = st.require_live(d)
        self.assertEqual(str(places['root']), '/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-4')
        self.assertEqual(d.qa_database, 'quillmd_qa_standing_20261004_4')
        self.assertEqual([(s.id,s.sends,s.requires) for s in d.stages],
                         [('model_check',1,None),('notes_qualification',14,'model_check'),('transcription',4,'model_check')])
        self.assertEqual(sum(s.sends for s in d.stages), 19)
        self.assertEqual(d.notes_mapping_review, nr.MANIFEST_SHA256)
        self.assertEqual(d.model, 'claude-sonnet-5-5')
        self.assertEqual(d.automatic_retries, 'none')
        self.assertIsNone(d.monetary_ceiling)

    def test_qualified_declaration_requires_complete_count_and_exact_review(self):
        text = CANONICAL.read_text()
        variants = [text.replace('notes_qualification sends 14', f'notes_qualification sends {n}') for n in (13,15)]
        variants += [text.replace(f'notes_mapping_review: {nr.MANIFEST_SHA256}\n', ''),
                     text.replace(nr.MANIFEST_SHA256, '0'*64)]
        for number, changed in enumerate(variants):
            with self.subTest(number=number), self.assertRaises(pc.Refused): self.canonical(changed)

    def test_canonical_model_substitution_and_other_campaign_places_refuse(self):
        text = CANONICAL.read_text()
        with self.assertRaises(pc.Refused): self.canonical(text.replace('model: claude-sonnet-5-5', 'model: claude-sonnet-5'))
        for old,new in [('root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-4',
                         'root: /opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-2'),
                        ('qa_database: quillmd_qa_standing_20261004_4','qa_database: quillmd_qa_standing_20261004_2')]:
            with self.subTest(old=old), self.assertRaises(pc.Refused): st.require_live(self.canonical(text.replace(old,new)))

    def test_original_declarations_parse_with_original_plans(self):
        d = parse(self)
        self.assertEqual(d.stage('notes_comparison').sends, 28)
        self.assertEqual(d.notes_mapping_review, '')
        self.assertNotIn('notes_qualification', [s.id for s in d.stages])
        self.assertEqual(st.STAGE_FLAGS['notes_qualification'], st.STAGE_FLAGS['notes_comparison'])
        self.assertEqual(st.STAGE_PRICING['notes_qualification'], st.STAGE_PRICING['notes_comparison'])

    def test_retained_canonical_two_and_three_keep_their_original_stage_counts(self):
        folder = CANONICAL.parent
        for suffix, counts in [('2',[('model_check',1),('notes_comparison',28),('transcription',4)]),
                               ('3',[('model_check',1),('ordinary_batch',2)])]:
            source = folder / f'20261004-quillmd-v1-standing-api-testing-{suffix}.md'
            root, path = repository(self, source.read_text(), name=source.name)
            d = st.declared_standing(path, repository=root, uses=('live',), out=io.StringIO())
            with self.subTest(campaign=suffix):
                self.assertEqual([(s.id,s.sends) for s in d.stages],counts)
                self.assertEqual(d.campaign,f'quillmd-v1-standing-api-testing-20261004-{suffix}')
                self.assertNotIn('notes_qualification',[s.id for s in d.stages])

    def test_reviewed_qualified_inputs_preserve_source_gold_and_human_protection(self):
        d = self.canonical()
        inputs = st.stage_inputs('notes_qualification', d)
        self.assertEqual(inputs['cases']['cases'], self.inputs['cases']['cases'])
        old = self.inputs['cases']['forms']['r1-11']
        current = inputs['cases']['forms']['r1-11']
        self.assertEqual(current['sha256'], old['sha256'])
        self.assertEqual(inputs['notes_mapping_review_manifest_sha256'], nr.MANIFEST_SHA256)
        for original, reviewed in zip(old['fields'], current['fields']):
            if original['key'] == 'v3_10': self.assertTrue(reviewed['write_protected'])
            else: self.assertEqual(original, reviewed)

    def test_new_stage_report_is_undeclared_for_old_campaign_and_review_bound_for_four(self):
        old = parse(self)
        d = self.canonical()
        for declaration, declared in ((old,False),(d,True)):
            with self.subTest(campaign=declaration.campaign):
                report = st.plan_report('notes_qualification',root=Path(declaration.repository)/'pure-runtime',
                                       declaration_path=declaration.path,repository=declaration.repository)
                stage = report['stages']['notes_qualification']
                if not declared:
                    self.assertFalse(stage['declared'])
                    self.assertNotIn('remaining',stage)
                else:
                    self.assertEqual(stage['notes_mapping_review_manifest_sha256'],nr.MANIFEST_SHA256)
                    self.assertEqual(stage['remaining'],[f'notes:{case}:field_relations' for case in CASES])

    def test_qualified_quote_boundary_uses_reviewed_fields_and_original_comparison_is_unchanged(self):
        d = self.canonical()
        seen = []
        utils = types.ModuleType('django.test.utils')
        utils.override_settings = lambda **kw: nullcontext()
        def capture(stage,sends,inputs,*args,**kwargs):
            protected = next(f for f in inputs['cases']['forms']['r1-11']['fields'] if f['key']=='v3_10')
            seen.append((stage,len(sends),inputs.get('notes_mapping_review_manifest_sha256'),protected.get('write_protected',False)))
            return {s.id:{'maximum_cost':Decimal('.10'),'bound':Decimal('.10')} for s in sends}
        with patch.object(st,'declared_standing',return_value=d),\
             patch.object(st,'_offline_django',lambda env:None),\
             patch.object(st,'price_sends',capture),\
             patch.dict(sys.modules,{'django.test.utils':utils}):
            st.priced_plan('notes_qualification',d.path)
            st.priced_plan('notes_comparison',d.path)
        self.assertEqual(seen,[('notes_qualification',14,nr.MANIFEST_SHA256,True),
                               ('notes_comparison',28,None,False)])


class QualificationResultPolicy(unittest.TestCase):
    def test_unsafe_historical_veto_remains_original_but_new_qualification_stops(self):
        verdict = pc.classify_case({'f1':'unsupported_accepted'}, [])
        old_stops, why = sq.stages_module().stop_decision(verdict, 'field_relations')
        self.assertFalse(old_stops)
        original = {'verdict':verdict, 'stops_stage':old_stops, 'recorded_as':why}
        before = deepcopy(original)
        qualified, stops = st.qualification_result('notes_qualification', original, old_stops)
        self.assertEqual(original, before)
        self.assertTrue(stops); self.assertTrue(qualified['stops_stage'])
        self.assertFalse(qualified['qualification_policy']['worker_stops_stage'])
        self.assertEqual(qualified['qualification_policy']['worker_recorded_as'], why)
        legacy, decision = st.qualification_result('notes_comparison', original, old_stops)
        self.assertIs(legacy, original); self.assertFalse(decision)

    def test_usefulness_holds_are_not_unsafe_and_contract_unknown_stops_are_retained(self):
        for outcome in ('supported_correct','held_correct','over_held','held_unadjudicated'):
            row = {'verdict':pc.classify_case({'f1':outcome}, []), 'stops_stage':False}
            with self.subTest(outcome=outcome):
                result, stops = st.qualification_result('notes_qualification', row, False)
                self.assertIs(result,row); self.assertFalse(stops)
        for kind in ('contract','interrupted_unknown'):
            row = {'class':kind, 'stops_stage':True}
            result, stops = st.qualification_result('notes_qualification', row, True)
            self.assertIs(result,row); self.assertTrue(stops)

    def test_missing_or_malformed_unsafe_classification_never_becomes_safe(self):
        for verdict in (None, {}, {'unsafe':None}, {'unsafe':'wrong_side'}):
            with self.subTest(verdict=verdict), self.assertRaises(pc.Refused):
                st.qualification_result('notes_qualification', {'verdict':verdict}, False)

    def test_tampered_classifier_or_nonstopping_contract_never_becomes_safe(self):
        correct = pc.classify_case({'f1':'unsupported_accepted'}, [])
        inconsistent = {**correct,'unsafe':[],'verdict':'usefulness','stops_stage':False}
        unknown = {**pc.classify_case({'f1':'supported_correct'}, []),'verdict':'unknown'}
        contract = pc.classify_case({'f1':'held_correct'}, ['export_verification_failed'])
        for verdict in (inconsistent,unknown,contract):
            with self.subTest(verdict=verdict), self.assertRaises(pc.Refused):
                st.qualification_result('notes_qualification',{'verdict':verdict},False)


class QualifiedWorker(FakeWorker):
    outcome = 'supported_correct'
    review_override = None
    original_records = []

    def run_send(self, send):
        write = self.ledger.write_attempt
        def reviewed(row):
            row['notes_mapping_review_manifest_sha256'] = nr.MANIFEST_SHA256 if self.review_override is None else self.review_override
            return write(row)
        with patch.object(self.ledger, 'write_attempt', reviewed):
            done = super().run_send(send)
        if done is None: return None
        row, _ = done
        verdict = pc.classify_case({'f1':self.outcome}, [])
        stops, why = sq.stages_module().stop_decision(verdict, send.path)
        row.update(verdict=verdict, stops_stage=stops, recorded_as=why)
        self.original_records.append(deepcopy(row))
        return row, stops


class QualificationNormalRun(Base):
    def setUp(self):
        stages = sq.stages_module()
        FakeWorker.hooks, FakeWorker.refused_jobs = {}, []
        QualifiedWorker.outcome, QualifiedWorker.review_override, QualifiedWorker.original_records = 'supported_correct', None, []
        for stand_in in (patch.object(stages,'stage_preconditions',lambda *a,**k: {'pure_fixture':True}),
                         patch.object(stages,'build_forms',lambda *a,**k: {}),
                         patch.object(stages,'seed_account',lambda root: object()),
                         patch.object(sq,'cancel_stale_jobs',lambda *a: []),
                         patch.object(stages,'Run',QualifiedWorker),
                         patch.object(st,'price_sends',lambda stage,sends,*a,**k: {s.id:{'maximum_cost':Decimal('.10')} for s in sends})):
            stand_in.start();self.addCleanup(stand_in.stop)

    def prepared(self):
        campaign = self.campaign(parse(self, qualified_fixture()))
        self.pass_model_check(campaign)
        folder = campaign.root/'preflight/001';folder.mkdir(parents=True)
        (folder/'result.json').write_text(json.dumps({'matches_declared':True,'campaign':campaign.declaration.campaign,'model_returned':campaign.declaration.model}))
        return campaign

    def run_qualified(self, campaign, **kw):
        return st.run_stage(campaign,'notes_qualification',secret=SYNTHETIC_KEY,provenance={'runner_commit':RUNNER_COMMIT},**kw)

    def attempts(self,campaign):
        return [a for a,_ in campaign.ledger.rows() if a['stage']=='notes_qualification']

    def test_maximum_requested_cap_still_runs_exactly_one_qualified_send(self):
        c=self.prepared(); result=self.run_qualified(c,max_sends=6)
        self.assertEqual(result['decision'],'partial');self.assertEqual(len(self.attempts(c)),1)
        opened,closed=c.runs.listing()[-1]
        self.assertEqual(opened['max_sends'],1);self.assertEqual(opened['sends'],['notes:N01:field_relations'])
        self.assertEqual(len(result['summary']['remaining_after']),13)

    def test_complete_fourteen_distinct_runs_finish_without_default_or_duplicate(self):
        c=self.prepared()
        for _ in range(14): result=self.run_qualified(c,max_sends=6)
        self.assertEqual((result['decision'],result['verdict']),('passed','PASS'))
        self.assertEqual([a['send']['id'] for a in self.attempts(c)],[f'notes:{case}:field_relations' for case in CASES])
        with self.assertRaises(pc.Refused): self.run_qualified(c)
        self.assertEqual(len(self.attempts(c)),14)

    def test_unsafe_qualified_veto_fails_new_stage_and_never_admits_another_send(self):
        c=self.prepared();QualifiedWorker.outcome='wrong_side_adopted'
        result=self.run_qualified(c,max_sends=6)
        self.assertEqual((result['decision'],result['verdict']),('failed','FAIL'))
        self.assertFalse(QualifiedWorker.original_records[-1]['stops_stage'])
        self.assertTrue(result['summary']['sends'][-1]['stops_stage'])
        self.assertEqual(result['summary']['sends'][-1]['recorded_as'],'qualification_unsafe')
        self.assertTrue(st.earlier_stops(c,'notes_qualification'))
        with self.assertRaises(pc.Refused): self.run_qualified(c)
        self.assertEqual(len(self.attempts(c)),1)

    def test_wrong_mapping_review_refuses_before_attempt_and_fails_run(self):
        c=self.prepared();QualifiedWorker.review_override='0'*64
        result=self.run_qualified(c)
        self.assertEqual(result['decision'],'failed');self.assertEqual(self.attempts(c),[])

    def test_missing_prerequisite_is_refused_before_new_run(self):
        c=self.campaign(parse(self,qualified_fixture()))
        folder=c.root/'preflight/001';folder.mkdir(parents=True)
        (folder/'result.json').write_text(json.dumps({'matches_declared':True,'campaign':c.declaration.campaign,'model_returned':c.declaration.model}))
        with self.assertRaises(pc.Refused): self.run_qualified(c)
        self.assertEqual(c.runs.listing(),[]);self.assertEqual(self.attempts(c),[])

    def test_edited_review_or_price_after_first_request_is_refused(self):
        for change in ('review','price'):
            c=self.prepared();self.run_qualified(c)
            if change=='review': c.declaration=dataclasses.replace(c.declaration,notes_mapping_review='')
            else: c.declaration=dataclasses.replace(c.declaration,model='claude-sonnet-5')
            with self.subTest(change=change),self.assertRaises(pc.Refused):self.run_qualified(c)
            self.assertEqual(len(self.attempts(c)),1)

    def test_unknown_outcome_is_reconciled_and_no_qualified_request_is_resent(self):
        c=self.prepared();inputs=st.stage_inputs('notes_qualification',c.declaration)
        send=st.standing_plan('notes_qualification',inputs)[0]
        st.begin_run(c,'notes_qualification',[send],inputs,1,{'runner_commit':RUNNER_COMMIT})
        c.admit('notes_qualification','.10',runner_commit=RUNNER_COMMIT)
        row=self.notes_attempt(c,send,inputs,{'stage':'notes_qualification','notes_mapping_review_manifest_sha256':nr.MANIFEST_SHA256})
        c.ledger.write_attempt(row)
        self.assertIsNone(c.ledger.rows()[-1][1])
        st.settle(c)
        self.assertEqual(c.ledger.rows()[-1][1]['class'],'interrupted_unknown')
        self.assertEqual(c.ledger.stage_state('notes_qualification')['state'],'failed')
        with self.assertRaises(pc.Refused):self.run_qualified(c)
        self.assertEqual(len(self.attempts(c)),1)
