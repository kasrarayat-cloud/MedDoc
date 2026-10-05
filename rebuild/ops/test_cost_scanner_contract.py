"""Negative controls for the two additional priced request shapes; source files never change."""
from pathlib import Path
import ast
import unittest
from unittest.mock import patch

try:
    from . import test_production_deploy as scan
except ImportError:
    import test_production_deploy as scan


class AdditionalCostContracts(unittest.TestCase):
    def check_mutation(self, relative, old, new, check):
        target = scan.REBUILD / relative
        original = target.read_text()
        self.assertIn(old, original)
        mutated = original.replace(old, new, 1)
        real_read = Path.read_text

        def read(path, *args, **kwargs):
            return mutated if path == target else real_read(path, *args, **kwargs)

        with patch.object(Path, 'read_text', read), self.assertRaises(AssertionError):
            check()

    def test_current_general_and_mapping_contracts_resolve(self):
        self.assertEqual(scan.maximum_cost_terms(), (12000, ('profile', frozenset({6000, 8000, 16000, 20000}))))
        self.assertEqual({cap for _, cap in scan.provider_caps(scan.GENERATION)},
                         {('profile', frozenset({6000, 8000, 16000, 20000}))})
        self.assertEqual([cap for _, cap in scan.provider_caps(scan.REBUILD / 'core/mapping_jobs.py')],
                         [('mapping-profile', frozenset({20000}))])

    def test_local_request_alias_cannot_hide_changes(self):
        for inserted in ("request['max_tokens']=90000", 'request.update(max_tokens=90000)',
                         'other=request', 'escape(request)', 'request=dict(request)',
                         'del request["max_tokens"]'):
            with self.subTest(inserted=inserted):
                self.check_mutation('core/generation.py', 'response=client.messages.create(**request)',
                    inserted + '\n    response=client.messages.create(**request)',
                    lambda: scan.provider_caps(scan.GENERATION))

    def test_both_cost_branches_must_price_the_same_bound(self):
        self.check_mutation('core/generation.py', 'len(sent.encode())+12000', 'len(sent.encode())+13000', scan.maximum_cost_terms)
        self.check_mutation('core/generation.py', "Decimal(profile['max_output_tokens'])*r['output_per_million']",
                            "Decimal(6000)*r['output_per_million']", scan.maximum_cost_terms)
        self.check_mutation('core/generation.py', '        return bound', '        return Decimal(0)', scan.maximum_cost_terms)
        self.check_mutation('core/generation.py', '        return bound',
                            '        bound: Decimal = Decimal(0)\n        return bound', scan.maximum_cost_terms)

    def test_history_addition_must_remain_fully_measured_and_additive(self):
        cases = [
            ("if config.get('history_context_contract'):", 'if False:'),
            ('if target_keys:', 'if not target_keys:'),
            ('history.refuse_request(config)', 'pass'),
            ('history.INSTRUCTIONS + json.dumps', "'' + json.dumps"),
            ('json.dumps(history.HistorySelections.model_json_schema())', "'{}'"),
            ("json.dumps({'history_context_targets': target_keys})", "'{}'"),
            ("bound += Decimal(extra)*r['input_per_million']/1000000", 'bound += Decimal(0)'),
            ("bound += Decimal(extra)*r['input_per_million']/1000000",
             "bound -= Decimal(extra)*r['input_per_million']/1000000"),
            ("bound += Decimal(extra)*r['input_per_million']/1000000",
             "bound += Decimal(extra)*r['output_per_million']/1000000"),
            ("bound += Decimal(extra)*r['input_per_million']/1000000",
             "bound += Decimal(extra)*r['input_per_million']/10000000"),
            ("bound += Decimal(extra)*r['input_per_million']/1000000",
             "bound = Decimal(extra)*r['input_per_million']/1000000"),
            ('    return bound\n\nclass Labels', '    extra = 0\n    return bound\n\nclass Labels'),
            ('    return bound\n\nclass Labels', '    target_keys = []\n    return bound\n\nclass Labels'),
            ('    return bound\n\nclass Labels',
             "    bound += Decimal(0)*r['input_per_million']/1000000\n    return bound\n\nclass Labels"),
        ]
        for old, new in cases:
            with self.subTest(mutation=new):
                self.check_mutation('core/generation.py', old, new, scan.maximum_cost_terms)

    def test_history_formula_in_dead_or_bypassed_code_is_not_a_bound(self):
        source = scan.GENERATION.read_text()
        for case in ('false_wrapper', 'early_return', 'conditional_return', 'earlier_return', 'reordered_geo'):
            with self.subTest(case=case):
                tree = ast.parse(source)
                function = scan.one_function(tree, 'maximum_cost')
                index = next(i for i, node in enumerate(function.body)
                             if isinstance(node, ast.If) and ast.unparse(node.test) == "config.get('history_context_contract')")
                if case == 'false_wrapper':
                    function.body[index] = ast.If(test=ast.Constant(value=False), body=[function.body[index]], orelse=[])
                elif case == 'reordered_geo':
                    function.body[index], function.body[index+1] = function.body[index+1], function.body[index]
                else:
                    code = 'return bound' if case != 'conditional_return' else 'if True: return bound'
                    function.body.insert(index if case != 'earlier_return' else index-1, ast.parse(code).body[0])
                mutated = ast.unparse(ast.fix_missing_locations(tree))
                self.check_mutation('core/generation.py', source, mutated, scan.maximum_cost_terms)

    def test_compiled_mapping_changes_fail_closed(self):
        def checked():
            caps = scan.provider_caps(scan.REBUILD / 'core/mapping_jobs.py')
            self.assertEqual([cap for _, cap in caps], [('mapping-profile', frozenset({20000}))])

        cases = [
            ('core/mapping_jobs.py', "    response=client.messages.create(**compiled['request'])",
             "    wrapped={'request':compiled['request']}\n    wrapped['request']['max_tokens']=90000\n    response=client.messages.create(**compiled['request'])"),
            ('core/mapping_jobs.py', 'response=client.messages.create(**compiled[\'request\'])',
             "compiled['request']['max_tokens']=90000\n    response=client.messages.create(**compiled['request'])"),
            ('core/mapping_jobs.py', 'response=client.messages.create(**compiled[\'request\'])',
             "escape(compiled)\n    response=client.messages.create(**compiled['request'])"),
            ('core/mapping_jobs.py', 'compiled=mapping.compile_request(version,job.config)', 'compiled=unpriced(version)'),
            ('core/mapping_jobs.py', 'send(compiled,job.config)', 'send(another,job.config)'),
            ('core/mapping_assistance.py', 'MAX_OUTPUT_TOKENS=20000', 'MAX_OUTPUT_TOKENS=90000'),
            ('core/mapping_assistance.py', "return {'request':request", "return {'request':{}"),
            ('core/mapping_assistance.py', "    return {'request':request",
             "    cost: Decimal = Decimal(0)\n    return {'request':request"),
            ('core/mapping_assistance.py', "str(cost.quantize(generation.COST_QUANTUM,rounding=ROUND_CEILING))", "'0'"),
            ('core/mapping_assistance.py', "Decimal(profile['max_output_tokens'])*rates['output_per_million']",
             "Decimal(8000)*rates['output_per_million']"),
            ('core/mapping_assistance.py', 'cost*=generation.US_INFERENCE_MULTIPLIER', 'cost*=0'),
            ('core/mapping_assistance.py', 'bound=size+12000', 'bound=size'),
            ('core/mapping_assistance.py', 'return profile', 'return base'),
            ('core/mapping_assistance.py', "request=generation.anthropic_request(config['model'],profile,SYSTEM,payload,schema)",
             "request=generation.anthropic_request(config['model'],base,SYSTEM,payload,schema)"),
            # (standing attempt 32's repair: the per-request schema and the model's mapping thinking are pinned too)
            ('core/mapping_assistance.py', "schema=wire.request_schema(payload) if config['model']==generation.SONNET_5_5 else wire.Proposal",
             "schema=dict(wire.request_schema(payload),max_tokens=90000)"),
            ('core/mapping_assistance.py', "'max_output_tokens':MAX_OUTPUT_TOKENS,\n             'timeout_seconds':TIMEOUT_SECONDS}",
             "'max_output_tokens':MAX_OUTPUT_TOKENS,\n             'timeout_seconds':TIMEOUT_SECONDS,**MAPPING_THINKING.get(config['model'],{})}"),
        ]
        for relative, old, new in cases:
            with self.subTest(file=relative, mutation=new):
                self.check_mutation(relative, old, new, checked)


class BatchCostContract(unittest.TestCase):
    check_mutation = AdditionalCostContracts.check_mutation

    def test_reviewed_calendar_refusal_cannot_disappear_or_move_after_pricing(self):
        refusal = ("                if ((by_key[key].get('locator') or {}).get('target') or {}).get('shape') == 'temporal_band':\n"
                   "                    refuse('Uniqueness of divided calendar dates is unsupported; review the form-wide rule.')\n")
        def checked(): scan.provider_caps(scan.REBUILD / 'core/batch_jobs.py')
        self.check_mutation('core/generation_batch.py', refusal, '', checked)
        self.check_mutation('core/generation_batch.py',
            "    manifest = plan_constraints(version, config, live=config['mode'] == 'live')",
            "    manifest = version.generation_constraints", checked)

    def test_batch_compiler_send_and_complete_price_have_reviewed_identities(self):
        self.assertEqual([cap for _,cap in scan.provider_caps(scan.REBUILD/'core/batch_jobs.py')],
                         [('profile',frozenset({6000,8000,16000,20000}))])

    def test_batch_price_control_flow_and_request_mutants_refuse(self):
        def checked():scan.provider_caps(scan.REBUILD/'core/batch_jobs.py')
        cases=[
            ('core/generation_batch.py', 'Decimal(size + 12000)', 'Decimal(size)'),
            ('core/generation_batch.py', "Decimal(wire['max_tokens'])", 'Decimal(6000)'),
            ('core/generation_batch.py', "bound *= g.US_INFERENCE_MULTIPLIER", 'bound *= Decimal(0)'),
            ('core/generation_batch.py', "if config['mode'] != 'live':", 'if True:'),
            ('core/generation_batch.py', "bound * Decimal('1.5')", "bound * Decimal('1.0')"),
            ('core/generation_batch.py', "str(sum((Decimal(p['maximum_charge']) for p in plan['parts']), Decimal(0)))", "str(Decimal(0))"),
            ('core/generation_batch.py', '    rate = g.rates(config)', '    return plan\n    rate = g.rates(config)'),
            ('core/generation_batch.py', 'def request(plan, ordinal):', '@unpriced\ndef request(plan, ordinal):'),
            ('core/generation_batch.py', 'return g.anthropic_request(config[\'model\'], config[\'request_profile\'], instructions, payload, schema)', "return {'max_tokens': 90000}"),
            ('core/batch_jobs.py', 'response=client.messages.create(**wire)', "wire['max_tokens']=90000\n            response=client.messages.create(**wire)"),
            ('core/batch_jobs.py', 'response=client.messages.create(**wire)', 'escape(wire)\n            response=client.messages.create(**wire)'),
            ('core/batch_jobs.py', 'response=client.messages.create(**wire)', 'response=client.messages.create(**replacement)'),
            ('core/batch_jobs.py', 'if plan[\'config\'] != g.configuration():', 'if False:'),
            ('core/batch_jobs.py', '\ndef current_plan(batch):', '\nb.request = replacement\n\ndef current_plan(batch):'),
            ('core/generation_batch.py', '\ndef request(plan, ordinal):', '\ng.anthropic_request = replacement\n\ndef request(plan, ordinal):'),
        ]
        for relative,old,new in cases:
            with self.subTest(relative=relative,mutation=new):self.check_mutation(relative,old,new,checked)


    def test_batch_global_dependency_rebinding_cannot_hide_undercharge(self):
        def checked():scan.provider_caps(scan.REBUILD/'core/batch_jobs.py')
        old='from decimal import Decimal, ROUND_CEILING'
        new="""from decimal import Decimal as _Decimal, ROUND_CEILING

def Decimal(value=0):
    return _Decimal(value) / (10 if type(value) is int else 1)
"""
        self.check_mutation('core/generation_batch.py',old,new,checked)
        for relative,old,new in (
            ('core/generation_batch.py','import json','import different_json as json'),
            ('core/generation_batch.py','MAX_PARTS = 8','MAX_PARTS = 80'),
            ('core/generation_batch.py','ROUND_CEILING','ROUND_DOWN'),
            ('core/batch_jobs.py','from decimal import Decimal','from other_decimal import Decimal'),
            ('core/batch_jobs.py','from .billing import reserve, settle, release, absorb_failed_job',
             'from .other_billing import reserve, settle, release, absorb_failed_job'),
            ('core/generation_batch.py',"    return bool(getattr(settings, 'V3_GENERATION_BATCHES', False))",'    return True'),
        ):
            with self.subTest(relative=relative,mutation=new):self.check_mutation(relative,old,new,checked)

class OrdinaryCostContract(unittest.TestCase):
    check_mutation = AdditionalCostContracts.check_mutation

    def test_reviewed_omission_floor_remains_part_of_the_complete_binding(self):
        def checked(): scan.provider_caps(scan.REBUILD / 'core/batch_jobs.py')
        self.check_mutation('core/generation.py',
                            'or any(MISSING_RECORD_VALUE.fullmatch(reading) for reading in safety_readings(value))',
                            'or False', checked)

    def test_imported_compiler_and_single_and_batch_sends_share_the_reviewed_price(self):
        expected = ('profile', frozenset({6000, 8000, 16000, 20000}))
        self.assertEqual(scan.maximum_cost_terms(), (12000, expected))
        for relative in ('core/v3_field_relations.py', 'core/batch_jobs.py'):
            self.assertEqual([cap for _, cap in scan.provider_caps(scan.REBUILD / relative)], [expected])

    def test_imported_module_changes_cannot_hide_under_the_batch_pin(self):
        def checked(): scan.provider_caps(scan.REBUILD / 'core/batch_jobs.py')
        cases = [
            ('Decimal(len(json.dumps(compiled[\'wire\']).encode()) + 12000)',
             'Decimal(len(json.dumps(compiled[\'wire\']).encode()))'),
            ("Decimal(profile['max_output_tokens'])", 'Decimal(6000)'),
            ('amount *= g.US_INFERENCE_MULTIPLIER', 'amount *= Decimal(0)'),
            ("'catalogue': catalogue", "'catalogue': catalogue[:1]"),
            ("'source_units': list(units)", "'source_units': list(units)[:1]"),
            ("response = client.messages.create(**compiled['wire'])",
             "compiled['wire']['max_tokens'] = 90000\n    response = client.messages.create(**compiled['wire'])"),
            ("response = client.messages.create(**compiled['wire'])",
             "escape(compiled)\n    response = client.messages.create(**compiled['wire'])"),
            ('from decimal import Decimal, ROUND_CEILING', 'from other_decimal import Decimal, ROUND_CEILING'),
            ('import json', 'import replacement_json as json'),
            ('def compile_request(', '@unpriced\ndef compile_request('),
        ]
        for old, new in cases:
            with self.subTest(mutation=new):
                self.check_mutation('core/v3_field_relations.py', old, new, checked)

    def test_single_dispatch_cannot_price_or_send_a_different_input(self):
        cases = [
            ('return ordinary.maximum_cost(notes,fields,config,context_labels,requirements or ())',
             'return Decimal(0)'),
            ('return ordinary.maximum_cost(notes,fields,config,context_labels,requirements or ())',
             'return ordinary.maximum_cost(notes[:1],fields[:1],config,context_labels,requirements or ())'),
            ('return ordinary.generate(notes,fields,config,context_labels=context_labels,requirements=requirements or ())',
             'return ordinary.generate(notes,fields,another,context_labels=context_labels,requirements=requirements or ())'),
            ("if config.get('ordinary_field_contract') and natural_v3(fields):", 'if False:'),
        ]
        def checked(): scan.provider_caps(scan.REBUILD / 'core/v3_field_relations.py')
        for old, new in cases:
            with self.subTest(mutation=new): self.check_mutation('core/generation.py', old, new, checked)

    def test_ordinary_sdk_send_must_remain_in_its_reviewed_function(self):
        def checked(): scan.provider_caps(scan.REBUILD / 'core/v3_field_relations.py')
        for old, new in [
            ("response = client.messages.create(**compiled['wire'])", 'response = client.messages.create(**replacement)'),
            ("response = client.messages.create(**compiled['wire'])", "response = client.messages.create(**compiled['other'])"),
            ('max_retries=0', 'max_retries=2'),
        ]:
            with self.subTest(mutation=new): self.check_mutation('core/v3_field_relations.py', old, new, checked)
