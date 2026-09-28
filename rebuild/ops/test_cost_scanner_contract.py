"""Negative controls for the two additional priced request shapes; source files never change."""
from pathlib import Path
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
        self.assertEqual(scan.maximum_cost_terms(), (12000, ('profile', frozenset({6000, 8000, 16000}))))
        self.assertEqual({cap for _, cap in scan.provider_caps(scan.GENERATION)},
                         {('profile', frozenset({6000, 8000, 16000}))})
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
            ('core/mapping_assistance.py', "request=generation.anthropic_request(config['model'],profile,SYSTEM,payload,wire.Proposal)",
             "request=generation.anthropic_request(config['model'],base,SYSTEM,payload,wire.Proposal)"),
        ]
        for relative, old, new in cases:
            with self.subTest(file=relative, mutation=new):
                self.check_mutation(relative, old, new, checked)
