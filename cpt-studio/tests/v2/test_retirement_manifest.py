"""The retirement manifest (docs/gemini-migration/FINAL-V2.md 5.7 measure 10; 5.1-5.4; step 6a of its 8.1). TEXT-ONLY and
SYNTHETIC: nothing here reads a document or sends anything.

5.7 measure 10: "tests/v2/test_retirement_manifest.py holds the 145 names of 5.1-5.4 and asserts that each resolves to a
code object inside a RETIRED module, so each is armed by measure 1; the count is pinned."

MANIFEST holds them as the design's tables give them - module, qualified name, and the line each table names (the def's
own line: a decorated function's code object starts at its first decorator, so the resolution reads the definition from
the module's syntax tree and checks both) - in the tables' order: 5.1's 73 meaning readers (row 9 is
events.another_role_hold with its 16 nested helpers, each its own code object, by its qualified name), 5.2's 19 literal
readers and primitives, 5.3's 46 contract-layer word checks and 5.4's 7 consumers. Each resolves to exactly ONE code
object of the sentinel's RETIRED set (sentinel.retired_set(): the code objects the install armed with PY_START, the
nested ones included), in the file of a module of sentinel.RETIRED_MODULES, and each is armed now.

ONE ENTRY IS A CLASS, NOT A FUNCTION, AND IS PINNED AS SUCH (fail-closed; the step's NOTES carry the question).
5.3's normalize.py row names ``_Default`` (line 130), a frozen dataclass: its only code objects are the methods dataclasses
generate (filename '<string>'), which the sentinel arms for no module (sentinel docstring: "Not in it: dataclass-generated
methods"), so no code object of its own exists to be armed. The test pins exactly that - a dataclass of normalize.py with
no method of its own - and asserts that both functions of the list that construct or read it (Draft._defaulted and
Draft._fall_back) are armed: what decides with it is counted, and building the record alone decides nothing. 5.3's other
five normalize names are methods of normalize.Draft (the table gives their lines), resolved as Draft.<name>.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib
import sys
import types
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import sentinel

# (section, module, qualified name, the table's line) for every name of FINAL-V2 5.1-5.4, in the tables' order
MANIFEST = (
    # 5.1 survey 2's meaning readers (57 rows; row 9's 16 nested helpers by qualified name)
    ('5.1', 'lexicon', 'other_occasion', 519),
    ('5.1', 'lexicon', 'current_frame', 560),
    ('5.1', 'lexicon', 'dated_frame', 576),
    ('5.1', 'facts', '_same_day_word', 171),
    ('5.1', 'facts', '_frame_parts', 200),
    ('5.1', 'facts', '_same_day_frame', 211),
    ('5.1', 'facts', 'day_of', 239),
    ('5.1', 'lexicon', 'markers', 502),
    ('5.1', 'events', 'another_role_hold', 634),
    ('5.1', 'events', 'another_role_hold.<locals>.fold', 675),
    ('5.1', 'events', 'another_role_hold.<locals>.whole', 678),
    ('5.1', 'events', 'another_role_hold.<locals>.phrase_end', 681),
    ('5.1', 'events', 'another_role_hold.<locals>.unlead', 684),
    ('5.1', 'events', 'another_role_hold.<locals>.entry_rest', 690),
    ('5.1', 'events', 'another_role_hold.<locals>.label_of', 707),
    ('5.1', 'events', 'another_role_hold.<locals>.heading_of', 725),
    ('5.1', 'events', 'another_role_hold.<locals>.physician', 762),
    ('5.1', 'events', 'another_role_hold.<locals>.heading_end', 768),
    ('5.1', 'events', 'another_role_hold.<locals>.signed', 784),
    ('5.1', 'events', 'another_role_hold.<locals>.signed.<locals>.word', 824),
    ('5.1', 'events', 'another_role_hold.<locals>.signed.<locals>.standing', 827),
    ('5.1', 'events', 'another_role_hold.<locals>.signed.<locals>.spaced', 839),
    ('5.1', 'events', 'another_role_hold.<locals>.signed.<locals>.read', 851),
    ('5.1', 'events', 'another_role_hold.<locals>.role_of', 934),
    ('5.1', 'events', 'another_role_hold.<locals>.role_of.<locals>.by_sentence', 942),
    ('5.1', 'relations', 'Context.places', 246),
    ('5.1', 'mapping', 'compared_landmark', 374),
    ('5.1', 'mapping', 'defining_target', 481),
    ('5.1', 'coverage', 'eus_places', 514),
    ('5.1', 'lexicon', 'device_named', 368),
    ('5.1', 'classes', 'route_phrase', 285),
    ('5.1', 'classes', 'named_routes', 317),
    ('5.1', 'classes', 'examination_route', 340),
    ('5.1', 'mapping', 'submucosal_act', 555),
    ('5.1', 'mapping', 'wall_place', 531),
    ('5.1', 'assess', '_stated_stations', 516),
    ('5.1', 'lexicon', '_without_through_the_scope', 404),
    ('5.1', 'lexicon', 'device_reach', 408),
    ('5.1', 'lexicon', 'scope_named', 414),
    ('5.1', 'coverage', 'beyond_reach', 578),
    ('5.1', 'assess', '_full_colonoscopy_reach', 253),
    ('5.1', 'events', '_h3_denial', 1304),
    ('5.1', 'lexicon', 'negation', 467),
    ('5.1', 'ercp', '_simple_clause', 491),
    ('5.1', 'ercp', '_negator', 504),
    ('5.1', 'ercp', '_governed', 508),
    ('5.1', 'ercp', '_denial', 520),
    ('5.1', 'ercp', '_guarded', 545),
    ('5.1', 'ercp', '_yield_pairs', 553),
    ('5.1', 'ercp', '_states_yield', 575),
    ('5.1', 'ercp', '_simple_yield', 582),
    ('5.1', 'ercp', '_own_yield', 602),
    ('5.1', 'ercp', '_yields', 623),
    ('5.1', 'ercp', '_clause_yield', 649),
    ('5.1', 'ercp', '_nominal', 665),
    ('5.1', 'ercp', '_appositive_yield', 672),
    ('5.1', 'ercp', '_free_simple_yield', 710),
    ('5.1', 'ercp', '_own_sentence_yield', 730),
    ('5.1', 'ercp', 'states_nothing_retrieved', 742),
    ('5.1', 'ercp', '_later_statement', 807),
    ('5.1', 'ercp', 'nothing_retrieved', 849),
    ('5.1', 'ercp', '_states_own_yield', 1110),
    ('5.1', 'relations', 'performer_row', 363),
    ('5.1', 'combination', 'separate_statement', 400),
    ('5.1', 'combination', '_stated_procedure', 282),
    ('5.1', 'lexicon', 'anastomosis_type_places', 301),
    ('5.1', 'mapping', 'anastomosis_place', 355),
    ('5.1', 'lexicon', 'anastomosis_places', 294),
    ('5.1', 'classes', 'gastric_beside', 215),
    ('5.1', 'classes', 'pouch_types', 179),
    ('5.1', 'mapping', 'hemostasis_in_doubt', 209),
    ('5.1', 'mapping', 'bleeding_stated', 194),
    ('5.1', 'lexicon', 'procedure_named', 448),
    # 5.2 literal readers with meaning uses only (15) and the phrase-search primitives (4)
    ('5.2', 'lexicon', 'landmarks_named', 272),
    ('5.2', 'literals', 'durations_min', 234),
    ('5.2', 'literals', '_number', 227),
    ('5.2', 'literals', 'names', 285),
    ('5.2', 'literals', 'name_tokens', 325),
    ('5.2', 'literals', 'Name.surname', 256),
    ('5.2', 'literals', 'Name.as_record', 260),
    ('5.2', 'literals', '_without_parentheticals', 272),
    ('5.2', 'literals', '_word', 279),
    ('5.2', 'relations', '_name_tokens', 290),
    ('5.2', 'relations', 'named_family', 296),
    ('5.2', 'literals', 'sizes_mm', 214),
    ('5.2', 'literals', 'distances_cm', 209),
    ('5.2', 'literals', '_mm', 200),
    ('5.2', 'literals', '_clean', 205),
    ('5.2', 'lexicon', 'found', 77),
    ('5.2', 'lexicon', 'holds', 88),
    ('5.2', 'lexicon', '_alternation', 66),
    ('5.2', 'lexicon', '_compiled', 73),
    # 5.3 contract-layer word checks: verify (15), normalize (6), identity (18), relations (7)
    ('5.3', 'verify', 'time_words', 138),
    ('5.3', 'verify', '_date_reasons', 184),
    ('5.3', 'verify', 'performer_words', 201),
    ('5.3', 'verify', 'size_words', 233),
    ('5.3', 'verify', 'landmark_words', 239),
    ('5.3', 'verify', 'reach_words', 256),
    ('5.3', 'verify', 'device_words', 265),
    ('5.3', 'verify', 'procedure_words', 274),
    ('5.3', 'verify', 'status_words', 283),
    ('5.3', 'verify', 'scope_words', 297),
    ('5.3', 'verify', 'basis_words', 306),
    ('5.3', 'verify', 'separate_words', 318),
    ('5.3', 'verify', 'identity_literals', 326),
    ('5.3', 'verify', 'single_family', 368),
    ('5.3', 'verify', 'exclusion_basis', 420),
    ('5.3', 'normalize', '_Default', 130),
    ('5.3', 'normalize', 'Draft._defaulted', 317),
    ('5.3', 'normalize', 'Draft._fall_back', 326),
    ('5.3', 'normalize', 'Draft._place_free', 366),
    ('5.3', 'normalize', 'Draft._bind_names', 408),
    ('5.3', 'normalize', 'Draft._team_for', 430),
    ('5.3', 'identity', 'content_tokens', 103),
    ('5.3', 'identity', 'reference_only', 114),
    ('5.3', 'identity', 'specimen_labels', 121),
    ('5.3', 'identity', 'lesion_facts', 156),
    ('5.3', 'identity', 'sizes_apart', 184),
    ('5.3', 'identity', 'sizes_meet', 199),
    ('5.3', 'identity', '_apart', 207),
    ('5.3', 'identity', 'same_place', 211),
    ('5.3', 'identity', 'distinct_reason', 217),
    ('5.3', 'identity', 'distinguish', 235),
    ('5.3', 'identity', '_lexical_tie', 293),
    ('5.3', 'identity', '_conflicts', 304),
    ('5.3', 'identity', '_literal_single', 315),
    ('5.3', 'identity', '_distance', 332),
    ('5.3', 'identity', '_adjacent', 342),
    ('5.3', 'identity', '_single', 356),
    ('5.3', 'identity', 'judge', 365),
    ('5.3', 'identity', 'link', 406),
    ('5.3', 'relations', 'judge_claim', 485),
    ('5.3', 'relations', 'judge_positive_claim', 518),
    ('5.3', 'relations', 'Context.distinct', 235),
    ('5.3', 'relations', 'Context.stated_places', 271),
    ('5.3', 'relations', 'adjacent', 684),
    ('5.3', 'relations', 'adjunct_apart', 699),
    ('5.3', 'relations', '_adjunct_places_apart', 707),
    # 5.4 consumers whose rule moves into Gemini's facts
    ('5.4', 'events', '_off_the_date', 1736),
    ('5.4', 'events', 'deciding', 1712),
    ('5.4', 'events', 'session_doubt', 1001),
    ('5.4', 'ercp', '_other_times', 787),
    ('5.4', 'ercp', 'cannulation_conflict', 1324),
    ('5.4', 'ercp', '_named_only_apart', 253),
    ('5.4', 'coverage', 'coding_family', 612),
)
COUNTS = {'5.1': 73, '5.2': 19, '5.3': 46, '5.4': 7}  # FINAL-V2 5.0's table
TOTAL = 145
# the one entry with no code object of its own (module docstring): a frozen dataclass of normalize.py; the listed
# functions that read it (each takes one, its parameter annotated _Default), and the function that builds it
CLASSES = {('normalize', '_Default'): {'read by': ('Draft._defaulted', 'Draft._fall_back'), 'built by': 'Draft._event'}}


def _module(name):
    return importlib.import_module(f'{sentinel.INTERPRETATION}.{name}')


def _definitions(module) -> dict:
    """{qualified name: (the def's line, its first decorator's line)} of every function and class in ``module``'s file,
    nested ones by '<locals>' as Python qualifies them."""
    tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
    out = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f'{prefix}{child.name}'
                first = min([child.lineno] + [item.lineno for item in child.decorator_list])
                out[name] = (child.lineno, first)
                visit(child, f'{name}.<locals>.' if not isinstance(child, ast.ClassDef) else f'{name}.')
            else:
                visit(child, prefix)

    visit(tree, '')
    return out


def resolved() -> dict:
    """{(module, qualified name): [the RETIRED set's code objects of that file with that qualified name]}."""
    out = {}
    for code in sentinel.retired_set().values():
        stem = Path(code.co_filename).stem
        out.setdefault((stem, code.co_qualname), []).append(code)
    return out


class ManifestTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        status = sentinel.install()
        assert status['state'] == 'ok', status

    def test_the_count_is_pinned_and_each_section_is_the_designs(self):
        self.assertEqual(len(MANIFEST), TOTAL)
        self.assertEqual(len({(module, name) for _, module, name, _ in MANIFEST}), TOTAL)  # no name twice
        by_section = {}
        for section, *_ in MANIFEST:
            by_section[section] = by_section.get(section, 0) + 1
        self.assertEqual(by_section, COUNTS)
        self.assertEqual(sum(COUNTS.values()), TOTAL)
        # every module named is one of the 17 retired modules (FINAL-V2 5.0: "all inside the 17 denied modules")
        self.assertLessEqual({module for _, module, _, _ in MANIFEST}, set(sentinel.RETIRED_NAMES))
        # row 9: another_role_hold and its 16 nested helpers
        nested = [name for _, module, name, _ in MANIFEST if name.startswith('another_role_hold.<locals>.')]
        self.assertEqual(len(nested), 16)

    def test_each_name_resolves_to_one_armed_code_object_inside_a_retired_module(self):
        found = resolved()
        retired_files = {Path(_module(name).__file__).resolve() for name in sentinel.RETIRED_NAMES}
        monitoring = sys.monitoring
        armed = 0
        for section, module, name, line in MANIFEST:
            if (module, name) in CLASSES:
                continue
            with self.subTest(name=f'{section} {module}.{name}'):
                codes = found.get((module, name), [])
                self.assertEqual(len(codes), 1, f'{module}.{name} resolves to {len(codes)} code objects')
                code = codes[0]
                self.assertIn(Path(code.co_filename).resolve(), retired_files)
                self.assertIn(id(code), sentinel.retired_set())
                self.assertEqual(sentinel.kind_of(id(code)), sentinel.RETIRED)
                self.assertTrue(monitoring.get_local_events(sentinel.TOOL_ID, code) & monitoring.events.PY_START,
                                f'{module}.{name} is not armed')
                definition, first = _definitions(_module(module))[name]
                self.assertEqual(definition, line, f'{module}.{name} is defined at {definition}, the table says {line}')
                self.assertEqual(code.co_firstlineno, first)
                armed += 1
        self.assertEqual(armed, TOTAL - len(CLASSES))

    def test_the_one_class_has_no_code_of_its_own_and_what_reads_and_builds_it_is_armed(self):
        found = resolved()
        listed = {(m, n) for _, m, n, _ in MANIFEST}
        for (module, name), uses in CLASSES.items():
            with self.subTest(name=f'{module}.{name}'):
                value = getattr(_module(module), name)
                self.assertTrue(isinstance(value, type) and dataclasses.is_dataclass(value))
                self.assertEqual(_definitions(_module(module))[name][0],
                                 dict(((m, n), line) for _, m, n, line in MANIFEST)[(module, name)])
                own = [item for item in vars(value).values() if isinstance(item, types.FunctionType)]
                self.assertTrue(own)  # the methods dataclasses generated ...
                written = Path(_module(module).__file__).resolve()
                self.assertFalse([item.__qualname__ for item in own if item.__code__.co_filename != '<string>'
                                  and Path(item.__code__.co_filename).resolve() == written])  # none written there
                self.assertFalse([item for item in own if id(item.__code__) in sentinel.retired_set()])
                self.assertEqual(found.get((module, name), []), [])
                tree = ast.parse(Path(_module(module).__file__).read_text(encoding='utf-8'))
                functions = {f'{owner.name}.{item.name}': item for owner in tree.body if isinstance(owner, ast.ClassDef)
                             for item in owner.body if isinstance(item, ast.FunctionDef)}
                for reader in uses['read by']:
                    self.assertIn((module, reader), listed)
                    [code] = found[(module, reader)]
                    self.assertIn(id(code), sentinel.retired_set())
                    annotations = [ast.unparse(arg.annotation) for arg in functions[reader].args.args if arg.annotation]
                    self.assertTrue(any(name in annotation for annotation in annotations), (reader, annotations))
                [code] = found[(module, uses['built by'])]
                self.assertIn(id(code), sentinel.retired_set())
                self.assertIn(name, code.co_names)  # the one place it is built: armed, though not on the list

    def test_the_resolution_refuses_a_name_no_retired_module_holds(self):
        # the positive control of the resolution: a kept module's function, a new-path function and a name nothing
        # defines resolve to no RETIRED code object; the v2 fork of a retired name lives in engine/, never here
        found = resolved()
        from studio.interpretation import dates
        from studio.interpretation.engine import combination as engine_combination

        for stem, name in (('dates', 'member_date_state'), ('combination', 'no_such_function'),
                           ('lexicon', 'no_such_reader')):
            with self.subTest(name=f'{stem}.{name}'):
                self.assertEqual(found.get((stem, name), []), [])
        self.assertNotIn(id(dates.member_date_state.__code__), sentinel.retired_set())
        self.assertNotIn(id(engine_combination.procedure_day.__code__), sentinel.retired_set())
        # engine/combination.py's procedure_day shares a file stem with v1's combination.py and no code object
        self.assertNotIn(('combination', 'procedure_day'), {(m, n) for _, m, n, _ in MANIFEST})
        v1_day = [code for code in found.get(('facts', 'day_of'), [])]
        self.assertEqual(len(v1_day), 1)
        self.assertTrue(v1_day[0].co_filename.endswith('studio/interpretation/facts.py'))
