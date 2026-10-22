"""Scoped call authority: exact roles, conservative money, honest first-pass holds."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID

from django.core.exceptions import ValidationError
from core import clinical_call_authority as authority
from core import generation_recovery as recovery
from core import source_assertion_generation as graph_generation
from core.tests.test_source_assertion_graph import IDENTITY, base_case, assignments, checker


class ClinicalCallAuthorityTests(TestCase):
    def test_explicit_owner_authority_is_separate_from_global_eight(self):
        grants = json.loads(authority.GRANTS_JSON)
        self.assertEqual(len(grants), 1)
        grant = authority.record(next(iter(grants)))
        self.assertEqual(grant['authorization_sha256'],
            'aa57fa7df8b1560d2dee6a260c94a9d7b7e30790aa9522f980c9b8485399b686')
        self.assertEqual(len(grant['jobs']), 6)
        self.assertEqual(authority.FAMILY_CALLS, 9)
        self.assertEqual(recovery.V2_FAMILY_MAX_CALLS, 8)
        self.assertEqual(recovery.PER_BATCH_MAX_CALLS, 5)
        self.assertEqual(authority.STAGES, (('extractor', 1), ('assigner', 1), ('checker', 1)))
        self.assertEqual(authority.CEILING, Decimal('8.15'))
        grant['jobs'].clear()
        self.assertEqual(len(authority.record(next(iter(grants)))['jobs']), 6)

    def test_unknown_partial_or_noncanonical_grant_is_not_authority(self):
        grants = json.loads(authority.GRANTS_JSON); key = next(iter(grants))
        with self.assertRaises(ValueError): authority.record('unknown')
        for mutate in (lambda g:g.pop('authorization_sha256'), lambda g:g.update(revision=True),
            lambda g:g.update(jobs=[]), lambda g:g['jobs'].__setitem__(1,g['jobs'][0]),
            lambda g:g.update(definitions_sha256=None), lambda g:g.update(global_max_calls=9),
            lambda g:g.update(clinical_exposure='NaN')):
            changed=deepcopy(grants); mutate(changed[key])
            with self.subTest(mutation=mutate), patch.object(authority,'GRANTS_JSON',json.dumps(changed)):
                with self.assertRaises((ValueError,TypeError)): authority.record(key)

    def receipts(self, count):
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        return [SimpleNamespace(pk=UUID(int=i+1),created_at=now+timedelta(seconds=i),
            stage=role,attempt=attempt,state='succeeded',actual_cost=Decimal('.1'),
            quote_maximum=Decimal('.4'),simulated=False,config={'exact':'TESTONLY'})
            for i,(role,attempt)in enumerate(authority.STAGES[:count])]

    def test_exact_roles_and_max_of_each_actual_or_quote_are_counted(self):
        for count,(role,attempt)in enumerate(authority.STAGES):
            rows=self.receipts(count)
            self.assertEqual(authority.stage_exposure({'exact':'TESTONLY'},rows,Decimal('.3'),role,attempt),
                Decimal('.4')*count+Decimal('.3'))
        rows=self.receipts(2);rows[0].actual_cost=Decimal('.8')
        self.assertEqual(authority.stage_exposure({'exact':'TESTONLY'},rows,Decimal('.2'),'checker',1),Decimal('1.4'))
        self.assertEqual(authority.stage_exposure({'exact':'TESTONLY'},list(reversed(rows)),Decimal('.2'),'checker',1),Decimal('1.4'))

    def test_no_second_attempt_fourth_role_missing_or_unresolved_prefix(self):
        config={'exact':'TESTONLY'}
        for rows,role,attempt in [(self.receipts(0),'assigner',1),(self.receipts(0),'extractor',True),
            (self.receipts(0),'checker',1),(self.receipts(1),'checker',1),
            (self.receipts(2),'assigner',2),(self.receipts(3),'checker',2),
            (self.receipts(3),'extractor',1)]:
            with self.subTest(role=role,attempt=attempt,count=len(rows)),self.assertRaises(ValueError):
                authority.stage_exposure(config,rows,Decimal('.1'),role,attempt)
        for key,bad in [('state','failed'),('state','unknown'),('actual_cost',None),
            ('actual_cost',Decimal('NaN')),('actual_cost',Decimal('-1')),('quote_maximum',Decimal('-1')),
            ('quote_maximum',None),('simulated',True),('config',{'changed':'TESTONLY'}),
            ('attempt',True),('stage','assigner')]:
            rows=self.receipts(1);setattr(rows[0],key,bad)
            with self.subTest(key=key,bad=bad),self.assertRaises((ValueError,TypeError)):
                authority.stage_exposure(config,rows,Decimal('.1'),'assigner',1)
        for bad in (None,True,'0',Decimal('NaN'),Decimal('-1')):
            with self.subTest(cap=bad),self.assertRaises(ValueError):
                authority.stage_exposure(config,[],bad,'extractor',1)

    def graph_run(self, allow_repair):
        notes,fields,defs,raw,good=base_case();initial=assignments(fields,{'field0':[]});calls=[]
        def send(role,attempt,payload,*_):
            calls.append((role,attempt))
            if role=='extractor':return deepcopy(raw)
            assigned=initial if attempt==1 else good
            if role=='assigner':return deepcopy(assigned)
            checked=checker(payload['graph'],fields,defs,assigned)
            if attempt==1:
                checked['components'][0].update(verdict='omission',cause='assignment',fact_ids=['f1'],reason='Existing symptom omitted.')
                checked['fields'][0].update(verdict='omission',cause='assignment',reason='Existing symptom omitted.')
            return checked
        options={}if allow_repair is None else {'allow_repair':allow_repair}
        result=graph_generation.run(notes,fields,defs,send,identity=IDENTITY,**options)
        return notes,result,calls

    def test_one_attempt_retains_checker_hold_and_restores_without_repair(self):
        notes,result,calls=self.graph_run(False)
        self.assertEqual(calls,list(authority.STAGES))
        self.assertNotEqual(result['answers']['field0']['status'],'supported')
        self.assertEqual(len(result['interpretation']['attempts']),1)
        self.assertEqual(result['interpretation']['attempts'][0]['checker']['fields'][0]['verdict'],'omission')
        self.assertEqual(graph_generation.restore(notes,result['interpretation']),result['answers'])
        self.assertEqual(len(graph_generation.raw_outputs(result['interpretation'])),3)

    def test_unscoped_default_still_performs_original_checked_repair(self):
        for option in (None,True):
            _,result,calls=self.graph_run(option)
            self.assertEqual(len(calls),5)
            self.assertEqual(result['answers']['field0']['status'],'supported')
        for option in (None,1,'false',{}):
            # None above means use the historical default; an explicit None is
            # tested directly so truthy/falsy policy substitutions never pass.
            with self.subTest(option=option),self.assertRaises(ValidationError):
                graph_generation.run('',[],{},lambda *a:None,identity=IDENTITY,allow_repair=option)
