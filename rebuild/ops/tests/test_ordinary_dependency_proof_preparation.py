"""Finite source-only proof preparation, never a live financial qualification.

Current source is accepted only inside an explicit test-mocked expected-AST
namespace. No accepted scanner fingerprint is rewritten or renewed by tests.
"""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

SCANNER = Path(__file__).parents[1] / 'test_production_deploy.py'
SEED_REBUILD = Path(__file__).parents[2]
RECORDS = []
HELPERS = {
    'core/ordinary_source_scope.py': 'effective',
    'core/reviewed_source.py': 'backward_attribution',
    'core/reviewed_procedure_source.py': 'complete',
    'core/source_scope.py': '_date_scope_backward_dependency',
    'core/v3_actors.py': 'read',
    'core/v3_syntax.py': '_parser',
    'core/v3_literal_facts.py': '_simple_fact',
    'core/reviewed_speaker.py': 'frames',
}


def ast_sha(path):
    return hashlib.sha256(ast.dump(ast.parse(path.read_text()), include_attributes=False).encode()).hexdigest()


def namespace(rebuild):
    names = {'ORDINARY_PRICED_SHA256', 'ORDINARY_PRICED_DEPENDENCY_PATHS',
             'ORDINARY_PRICED_DEPENDENCIES', 'ORDINARY_PRICED_INPUT_PATHS', 'ORDINARY_PRICED_INPUTS'}
    tree = ast.parse(SCANNER.read_text())
    nodes = [node for node in tree.body if
             isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in
             {'Unresolved', 'ordinary_module_proof', 'ordinary_dependency_proof'} or
             isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)]
    env = {'ast': ast, 'hashlib': hashlib, 'REBUILD': rebuild}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SCANNER), 'exec'), env)
    return env


class OrdinaryDependencyPreparation(unittest.TestCase):
    def setUp(self):
        deny = patch.object(socket.socket, 'connect', side_effect=AssertionError('No database/provider/network'))
        deny.start(); self.addCleanup(deny.stop)
        temp = tempfile.TemporaryDirectory(prefix='ordinary-proof-preparation-')
        self.addCleanup(temp.cleanup)
        self.rebuild = Path(temp.name)
        self.proof = namespace(self.rebuild)
        paths = ('core/v3_field_relations.py', *self.proof['ORDINARY_PRICED_DEPENDENCY_PATHS'],
                 *self.proof['ORDINARY_PRICED_INPUT_PATHS'])
        for relative in paths:
            path = self.rebuild / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SEED_REBUILD / relative, path)
        self.caller = (self.rebuild / 'core/v3_field_relations.py').read_bytes()

    def explicit_test_mock_expected_ast(self):
        # Explicit local fixture binding only; production defaults/pins stay unchanged.
        self.proof['ORDINARY_PRICED_SHA256'] = ast_sha(self.rebuild / 'core/v3_field_relations.py')
        self.proof['ORDINARY_PRICED_DEPENDENCIES'] = {
            path: ast_sha(self.rebuild / path) for path in self.proof['ORDINARY_PRICED_DEPENDENCY_PATHS']}
        self.proof['ORDINARY_PRICED_INPUTS'] = {
            path: hashlib.sha256((self.rebuild / path).read_bytes()).hexdigest()
            for path in self.proof['ORDINARY_PRICED_INPUT_PATHS']}

    def refuse(self, label, path=None):
        self.assertEqual((self.rebuild / 'core/v3_field_relations.py').read_bytes(), self.caller)
        with self.assertRaises(self.proof['Unresolved']) as refused:
            self.proof['ordinary_module_proof']('finite pending proof preparation')
        RECORDS.append({'control': label, 'refused': str(refused.exception), 'caller_bytes_unchanged': True,
                        'mutated_path': path, 'test_mock_only': True})

    def mutate_body(self, relative, function_name):
        path = self.rebuild / relative
        tree = ast.parse(path.read_text())
        found = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function_name]
        self.assertEqual(len(found), 1, function_name)
        # An actual used decision/reader body changes; caller/import text remains fixed.
        found[0].body.insert(0, ast.Return(value=ast.Constant(True)))
        path.write_text(ast.unparse(ast.fix_missing_locations(tree)) + '\n')

    def mutate_import(self, relative):
        path = self.rebuild / relative
        tree = ast.parse(path.read_text())
        found = next(n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        # Change an existing import's source identity, retaining the caller unchanged.
        found.names[0].name += '_unreviewed'
        path.write_text(ast.unparse(ast.fix_missing_locations(tree)) + '\n')

    def test_current_source_resolves_only_with_explicit_local_expected_ast_mock(self):
        self.explicit_test_mock_expected_ast()
        self.assertIsInstance(self.proof['ordinary_module_proof']('explicit local test mock'), ast.Module)
        RECORDS.append({'control': self.id(), 'explicit_test_mock_positive': True,
                        'accepted_source_pins_renewed': False})

    def test_prepared_dependency_none_markers_still_refuse_after_caller_test_mock(self):
        self.proof['ORDINARY_PRICED_SHA256'] = ast_sha(self.rebuild / 'core/v3_field_relations.py')
        self.assertTrue(all(v is None for v in self.proof['ORDINARY_PRICED_DEPENDENCIES'].values()))
        self.refuse(self.id())

    def test_prepared_parser_none_markers_refuse_after_module_test_mock(self):
        self.explicit_test_mock_expected_ast()
        self.proof['ORDINARY_PRICED_INPUTS'] = dict.fromkeys(self.proof['ORDINARY_PRICED_INPUT_PATHS'])
        self.refuse(self.id())

    def test_original_accepted_ordinary_fingerprint_is_not_renewed(self):
        self.assertEqual(self.proof['ORDINARY_PRICED_SHA256'],
                         'efe4c9dbf74ee5403e4144fd296b2bdb1e3dc6169c7fa24d9d8284f36deb84fb')
        self.refuse(self.id())

    def test_missing_helper_refuses(self):
        self.explicit_test_mock_expected_ast()
        (self.rebuild / 'core/reviewed_source.py').unlink()
        self.refuse(self.id(), 'core/reviewed_source.py')

    def test_unparseable_helper_refuses(self):
        self.explicit_test_mock_expected_ast()
        (self.rebuild / 'core/reviewed_source.py').write_text('def source_reader(:\n')
        self.refuse(self.id(), 'core/reviewed_source.py')

    def test_missing_dependency_pin_cannot_narrow_the_union(self):
        self.explicit_test_mock_expected_ast()
        self.proof['ORDINARY_PRICED_DEPENDENCIES'].pop('core/source_scope.py')
        self.refuse(self.id())

    def test_extra_dependency_pin_cannot_replace_the_reviewed_union(self):
        self.explicit_test_mock_expected_ast()
        self.proof['ORDINARY_PRICED_DEPENDENCIES']['core/unknown.py'] = '0' * 64
        self.refuse(self.id())

    def test_missing_parser_pin_cannot_narrow_inputs(self):
        self.explicit_test_mock_expected_ast()
        self.proof['ORDINARY_PRICED_INPUTS'].pop('core/v3_syntax_model.json')
        self.refuse(self.id())

    def test_same_helper_ast_ignores_only_nonsemantic_comment_formatting(self):
        self.explicit_test_mock_expected_ast()
        path = self.rebuild / 'core/ordinary_source_scope.py'
        path.write_text(path.read_text() + '\n# same AST, formatting-only control\n')
        self.assertIsInstance(self.proof['ordinary_module_proof']('formatting control'), ast.Module)
        RECORDS.append({'control': self.id(), 'explicit_test_mock_positive': True})


def body_test(relative, function):
    def test(self):
        self.explicit_test_mock_expected_ast()
        self.mutate_body(relative, function)
        self.refuse(self.id(), relative)
    return test


def import_test(relative):
    def test(self):
        self.explicit_test_mock_expected_ast()
        self.mutate_import(relative)
        self.refuse(self.id(), relative)
    return test


for relative, function in HELPERS.items():
    slug = Path(relative).stem
    setattr(OrdinaryDependencyPreparation, 'test_helper_body_' + slug, body_test(relative, function))
    setattr(OrdinaryDependencyPreparation, 'test_helper_import_' + slug, import_test(relative))

for relative, function in [('core/generation.py', 'v3_preceding_warnings'),
                           ('core/transcript_context.py', 'verified'),
                           ('core/v3_destination.py', 'temporal_warnings'),
                           ('core/v3_mapping.py', 'normalize')]:
    setattr(OrdinaryDependencyPreparation, 'test_direct_dependency_body_' + Path(relative).stem,
            body_test(relative, function))

for relative in ('core/v3_syntax_model.json', 'requirements.txt', 'requirements-production.lock',
                 'requirements-production.manifest.json'):
    def make_input_test(path):
        def test(self):
            self.explicit_test_mock_expected_ast()
            target = self.rebuild / path
            # Change valid parser/packaging data; no dependency is installed.
            if path == 'core/v3_syntax_model.json':
                data = json.loads(target.read_text())
                data['parser/model'] = '0' * 64
                target.write_text(json.dumps(data, indent=2) + '\n')
            elif path == 'requirements-production.manifest.json':
                data = json.loads(target.read_text())
                artifact = next(row for row in data['artifacts'] if row['name'] == 'spacy')
                artifact['sha256'] = '0' * 64
                target.write_text(json.dumps(data, indent=2) + '\n')
            else:
                text = target.read_text()
                self.assertIn('spacy==3.8.16', text)
                target.write_text(text.replace('spacy==3.8.16', 'spacy==3.8.17'))
            self.refuse(self.id(), path)
        return test
    setattr(OrdinaryDependencyPreparation, 'test_parser_input_' + Path(relative).name.replace('.', '_').replace('-', '_'),
            make_input_test(relative))
