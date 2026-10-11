from copy import deepcopy
from decimal import Decimal

from django.test import SimpleTestCase

from core.management.commands.audit_billing import recompute_cost


class SemanticCostEvidenceTests(SimpleTestCase):
    def stage(self, role, attempt=1, *, identifier=None, simulated=False):
        return {'id':identifier or role+str(attempt),'stage':role,'attempt':attempt,
            'provider':'anthropic','request_id':'request-'+(identifier or role+str(attempt)),
            'resource_id':'message-'+(identifier or role+str(attempt)),
            'actual_cost':'0' if simulated else '0.000030000000',
            'usage':{} if simulated else {'input_tokens':10,'output_tokens':1},
            'rates':{} if simulated else {'input_per_million':'2','output_per_million':'10','cached_per_million':'0.2'},
            'simulated':simulated}

    def cost(self, stages, simulated=False):
        return recompute_cost('quillmd:semantic-stages',
            {'protocol':'quillmd-ai-stages-v1','stages':stages},
            {'aggregation':'sum_of_independently_rounded_stage_costs'},simulated)

    def test_three_separately_rounded_stages_and_targeted_repair_settle_once(self):
        stages=[self.stage('extractor'),self.stage('assigner'),self.stage('checker')]
        self.assertEqual(self.cost(stages),Decimal('0.00009'))
        stages.extend([self.stage('assigner',2),self.stage('checker',2)])
        self.assertEqual(self.cost(stages),Decimal('0.00015'))

    def test_stage_meter_and_recorded_cost_cannot_disagree(self):
        stages=[self.stage('extractor')]
        stages[0]['actual_cost']='0.1'
        with self.assertRaises(ValueError):self.cost(stages)

    def test_explicit_unsent_zero_cost_stage_does_not_claim_a_provider_meter(self):
        unsent=self.stage('assigner')
        unsent.update(state='failed',error_code='not_sent',started_at=None,
            request_id='',resource_id='',usage={},rates={},actual_cost='0',result_sha256='')
        self.assertEqual(self.cost([self.stage('extractor'),unsent]),Decimal('0.00003'))
        for change in ({'started_at':'2026-10-10T00:00:00Z'},
                       {'actual_cost':'0.1'},{'request_id':'potentially-charged'}):
            modified={**unsent,**change}
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):
                self.cost([self.stage('extractor'),modified])

    def test_duplicate_stage_or_provider_evidence_cannot_inflate_total(self):
        original=[self.stage('extractor'),self.stage('assigner'),self.stage('checker')]
        for key in ('id','request_id','resource_id'):
            stages=deepcopy(original);stages[1][key]=stages[0][key]
            with self.subTest(key=key),self.assertRaises(ValueError):self.cost(stages)
        with self.assertRaises(ValueError):self.cost(original+[deepcopy(original[-1])])

    def test_simulation_marker_does_not_hide_live_metered_stage(self):
        stages=[self.stage('extractor'),self.stage('assigner',simulated=True)]
        self.assertEqual(self.cost(stages),Decimal('0.00003'))
        with self.assertRaises(ValueError):self.cost(stages,simulated=True)
        simulated=[self.stage('extractor',simulated=True)]
        self.assertEqual(self.cost(simulated,simulated=True),0)
        with self.assertRaises(ValueError):self.cost(simulated)

    def test_aggregate_cannot_hide_unknown_provider_recursive_cost_or_unbounded_calls(self):
        for provider in ('unknown','quillmd:semantic-stages'):
            stage=self.stage('extractor');stage['provider']=provider
            with self.subTest(provider=provider),self.assertRaises(ValueError):self.cost([stage])
        with self.assertRaises(ValueError):self.cost([])
        with self.assertRaises(ValueError):self.cost([self.stage('extractor')]*6)
