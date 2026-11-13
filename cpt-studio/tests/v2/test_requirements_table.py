"""Step 1f's generated table (docs/gemini-migration/FINAL-V2.md, 8.1 step 1f; Appendix A, 4.3), TEXT-ONLY and SYNTHETIC:
no document, no provider, no network.

The done-when of 8.1 step 1f, each proved here:
- "the committed table equals the regenerated one": scripts/gen_requirements.py regenerates it in this test, in memory
  and through its --check door, and the committed bytes must equal it;
- "every code's tags match 4.3's rows": each tag's codes are written out below as 4.3 and Appendix A write them, read
  from the design and never from the generator, and every code's tags must equal them.
Also: the templates are Appendix A's (B's: its counts and its named codes); the groups and every tag parameter equal
step 1e's engine/catalogue.py and v1's own rules, computed in the test (events.requirements, ercp._read_by_a_rule,
mapping.recognised_only and the rest); the table reproduces design C's tags and design B's templates, its C rules
re-run here over v1's tables, and differs from C exactly where Appendix A amends it; the kinds each family's catalogue
entry names (NAMED_KINDS, CLAIMED's ERCP kinds: DECISIONS D207) equal v1's entries; the kinds of each session family
are DECISIONS D191's table, its rule re-run here over step 1e's tables, and the catalogue kinds CLAIMED reads are every
kind the catalogue names, equal to v1's.

v1 is read only here and by the generator - catalogue and profiles (studio.gi) and mapping, classes, events, ercp
(retired, FINAL-V2 5.0) - never by engine/.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

# v1, read only (the generator's inputs and the parity proofs)
from studio.gi import catalogue as v1_catalogue, profiles as v1_profiles
from studio.interpretation import classes as v1_classes, ercp as v1_ercp, events as v1_events
from studio.interpretation import mapping as v1_mapping
from studio.interpretation.contract.types import Kind, SessionKind, Tract
from studio.interpretation.engine import catalogue, requirements_table as table
from studio.interpretation.engine.requirements_table import CODES, Tag, Template

APP = Path(__file__).resolve().parents[2]
GENERATOR = APP / 'scripts' / 'gen_requirements.py'
TABLE = APP / 'studio' / 'interpretation' / 'engine' / 'requirements_table.py'


def _generator():
    """scripts/gen_requirements.py loaded as a module (it is a script, not a package member)."""
    spec = importlib.util.spec_from_file_location('gen_requirements_under_test', GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _codes(*ranges) -> set:
    """Every catalogue code in the inclusive ``ranges`` (4.3 writes ENT's classes as ranges)."""
    return {code for code in CODES for low, high in ranges if low <= code <= high}


def _family(*families) -> set:
    return {code for code, row in CODES.items() if row.family in families}


# --- 4.3 and Appendix A, as the design writes them (never read from the generator) -----------------------------------

BASE = {43197, 43200, 43235, 43260, 44360, 44376, 44380, 44385, 44388, 45330, 45378}
EUS_EXAM = {43231, 43237, 43259, 45341, 45391, 44406}
EUS_ACT = {43232, 43238, 43240, 43242, 43253, 45342, 45392, 44407}
ADDON_ACT = {43273, 91013}
FEEDING = {43762, 43763, 49440, 49441, 49446, 49450, 49451, 49452}
RECOGNISED = {99152, 99153}
OFFICE_EM = {99202, 99203, 99204, 99205, 99211, 99212, 99213, 99214, 99215, 99242, 99243, 99244, 99245}
TEMPLATE_COUNTS = {Template.BASE: 11, Template.ACT: 97, Template.EUS_EXAM: 6, Template.EUS_ACT: 8,
                   Template.ADDON_ACT: 2, Template.FEEDING: 8, Template.TEST: 15, Template.EM: 13,
                   Template.EM_ADDON: 1, Template.RECOGNISED: 2}
UPPER_EUS = {43231, 43232, 43237, 43238, 43240, 43242, 43253, 43259}
LOWER_EUS = {45341, 45342, 45391, 45392, 44406, 44407}
BALLOON = {43214, 43220, 43233, 43249, 43277, 44381, 44405, 45340, 45386}
WIRE_BOUGIE = {43226, 43248}
ESOPHAGEAL = {43213, 43214, 43220, 43226, 43233, 43248, 43249}
GASTRIC_DUODENAL = {43245}


def expected_tags() -> dict:
    """Each tag's codes: 4.3's rows, with Appendix A's assignment of R6 per family and the codes it names."""
    return {
        Tag.ATT: BASE | EUS_EXAM,  # base and exam-only EUS codes
        Tag.R6_EXTENT: _family(SessionKind.EGD, SessionKind.ENTEROSCOPY, SessionKind.FLEX_SIG),
        Tag.COLFULL: _family(SessionKind.COLONOSCOPY),
        Tag.R6_TARGET: _family(SessionKind.EUS),
        Tag.R6_CANNULATION: _family(SessionKind.ERCP),
        Tag.R6_EM_BASIS: _family(SessionKind.OFFICE_EM),
        Tag.R6_CONTEXT: _family(SessionKind.OFFICE_EM),
        Tag.DEF: {44365, 43232, 43238, 43242, 43253, 43240, 45342, 45392, 44407, 43265, 49440},
        Tag.TECH: BALLOON | WIRE_BOUGIE,
        Tag.SITE: ESOPHAGEAL | GASTRIC_DUODENAL,
        Tag.STRUCT_PFC: {43240},
        Tag.ROUTE: {43253},
        Tag.TRACT: UPPER_EUS | LOWER_EUS,
        Tag.STATIONS: {43242, 43259},
        Tag.LIMITED: {43231, 43232, 43237, 43238},
        Tag.LOWER: LOWER_EUS,
        Tag.ENT: _codes((44360, 44373), (44376, 44379), (44380, 44384), (44385, 44386)),
        Tag.YIELD: {43264},
        Tag.XCHG: {43274, 43275, 43276},
        Tag.CAUSE: {43227, 43255, 44366, 44378, 44391, 45334, 45382},  # every code covering bleeding_control
        Tag.C3_SEP: _family(SessionKind.OFFICE_EM),
        Tag.ADDON: {43273, 91013, 99153, 99417},
        Tag.D80: {99152, 99153},
    }


class RegenerationTests(SimpleTestCase):
    def test_the_committed_table_equals_the_regenerated_one(self):
        self.assertEqual(TABLE.read_text(encoding='utf-8'), _generator().render())

    def test_the_check_door_passes_on_the_committed_table(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(GENERATOR), '--check'], capture_output=True,
                                text=True, timeout=120, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('equals the regenerated table', result.stdout)

    def test_the_check_door_refuses_a_changed_table_and_writes_nothing(self):
        generator = _generator()
        changed = TABLE.read_text(encoding='utf-8').replace('(Tag.R6_CANNULATION, Tag.YIELD)', '(Tag.R6_CANNULATION,)')
        self.assertNotEqual(changed, TABLE.read_text(encoding='utf-8'))  # the plant applied
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'requirements_table.py'
            path.write_text(changed, encoding='utf-8')
            generator.TABLE = path
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                self.assertEqual(generator.main(['--check']), 1)
                self.assertEqual(path.read_text(encoding='utf-8'), changed)  # --check writes nothing
                self.assertEqual(generator.main([]), 0)  # the write door restores it
            self.assertIn('differs from the regenerated table', printed.getvalue())
            self.assertEqual(path.read_text(encoding='utf-8'), TABLE.read_text(encoding='utf-8'))

    def test_the_check_door_needs_no_django_and_reads_only_the_gi_reference_tables(self):
        code = ('import runpy, sys\n'
                f'sys.argv = [{str(GENERATOR)!r}, "--check"]\n'
                'try:\n'
                f'    runpy.run_path({str(GENERATOR)!r}, run_name="__main__")\n'
                'except SystemExit as stop:\n'
                '    print("exit", stop.code)\n'
                'print("django" in sys.modules, sorted(m for m in sys.modules if m.startswith("studio.gi")))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=120,
                                cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('exit 0', result.stdout)
        self.assertIn("False ['studio.gi', 'studio.gi.catalogue', 'studio.gi.profiles']", result.stdout)


class TagTests(SimpleTestCase):
    def test_every_codes_tags_match_4_3s_rows(self):
        expected = expected_tags()
        self.assertEqual(set(expected), set(Tag))
        for code, row in CODES.items():
            with self.subTest(code=code):
                self.assertEqual(row.tags, tuple(tag for tag in Tag if code in expected[tag]))

    def test_each_tags_codes_are_the_designs_count(self):
        counts = {Tag.ATT: 17, Tag.COLFULL: 25, Tag.DEF: 11, Tag.TECH: 11, Tag.SITE: 8, Tag.TRACT: 14,
                  Tag.ENT: 20, Tag.CAUSE: 7, Tag.C3_SEP: 14, Tag.ADDON: 4, Tag.D80: 2}
        for tag, count in counts.items():
            with self.subTest(tag=tag):
                self.assertEqual(sum(tag in row.tags for row in CODES.values()), count)

    def test_tags_are_in_4_3s_order_and_each_parameter_is_present_exactly_with_its_tag(self):
        for code, row in CODES.items():
            with self.subTest(code=code):
                self.assertEqual(list(row.tags), sorted(row.tags, key=list(Tag).index))
                self.assertEqual(bool(row.defining), Tag.DEF in row.tags)
                self.assertEqual(row.technique is not None, Tag.TECH in row.tags)
                self.assertEqual(row.site is not None, Tag.SITE in row.tags)
                self.assertEqual(row.tract is not None, Tag.TRACT in row.tags)
                self.assertEqual(row.enteroscopy_class is not None, Tag.ENT in row.tags)
                self.assertEqual(row.eus_class is not None,
                                 bool({Tag.STATIONS, Tag.LIMITED, Tag.LOWER} & set(row.tags)))

    def test_the_parameters_are_the_ones_4_3_names(self):
        for code in BALLOON:
            self.assertIs(CODES[code].technique, catalogue.TechniqueClass.BALLOON)
        for code in WIRE_BOUGIE:
            self.assertIs(CODES[code].technique, catalogue.TechniqueClass.WIRE_BOUGIE)
        for code in ESOPHAGEAL:
            self.assertIs(CODES[code].site, catalogue.SiteClass.ESOPHAGEAL)
        self.assertIs(CODES[43245].site, catalogue.SiteClass.GASTRIC_DUODENAL)
        self.assertEqual({code for code in CODES if CODES[code].tract is Tract.UPPER}, UPPER_EUS)
        self.assertEqual({code for code in CODES if CODES[code].tract is Tract.LOWER}, LOWER_EUS)
        self.assertEqual({code: CODES[code].eus_class for code in LOWER_EUS},
                         {45341: catalogue.EusClass.SIGMOIDOSCOPIC, 45342: catalogue.EusClass.SIGMOIDOSCOPIC,
                          45391: catalogue.EusClass.COLONOSCOPIC, 45392: catalogue.EusClass.COLONOSCOPIC,
                          44406: catalogue.EusClass.STOMA, 44407: catalogue.EusClass.STOMA})
        self.assertEqual({CODES[code].eus_class for code in (43242, 43259)}, {catalogue.EusClass.FULL})
        self.assertEqual({CODES[code].eus_class for code in (43231, 43232, 43237, 43238)}, {catalogue.EusClass.LIMITED})
        classes = {catalogue.EnteroscopyClass.JEJUNAL: _codes((44360, 44373)),
                   catalogue.EnteroscopyClass.ILEAL: _codes((44376, 44379)),
                   catalogue.EnteroscopyClass.STOMA: _codes((44380, 44384)),
                   catalogue.EnteroscopyClass.POUCH: _codes((44385, 44386))}
        for name, codes in classes.items():
            self.assertEqual({code for code in CODES if CODES[code].enteroscopy_class is name}, codes)
        self.assertEqual(CODES[43265].defining, (Kind.LITHOTRIPSY,))
        self.assertEqual(CODES[44365].defining, (Kind.HOT_BIOPSY,))
        self.assertEqual(CODES[49440].defining, (Kind.PEG,))
        self.assertEqual(CODES[43240].defining, (Kind.DRAINAGE,))
        self.assertEqual(CODES[43253].defining, (Kind.INJECTION,))
        self.assertEqual({CODES[code].defining for code in (43232, 43238, 43242, 45342, 45392, 44407)}, {(Kind.FNA,)})


class TemplateTests(SimpleTestCase):
    def test_the_templates_are_appendix_as(self):
        found = {template: {code for code, row in CODES.items() if row.template is template} for template in Template}
        self.assertEqual({template: len(codes) for template, codes in found.items() if codes}, TEMPLATE_COUNTS)
        self.assertEqual(found[Template.BASE], BASE)
        self.assertEqual(found[Template.EUS_EXAM], EUS_EXAM)
        self.assertEqual(found[Template.EUS_ACT], EUS_ACT)
        self.assertEqual(found[Template.ADDON_ACT], ADDON_ACT)
        self.assertEqual(found[Template.FEEDING], FEEDING)
        self.assertEqual(found[Template.TEST], _family(SessionKind.CAPSULE, SessionKind.MOTILITY, SessionKind.REFLUX,
                                                       SessionKind.ANORECTAL) - ADDON_ACT)
        self.assertEqual(found[Template.EM], OFFICE_EM)
        self.assertEqual(found[Template.EM_ADDON], {99417})
        self.assertEqual(found[Template.RECOGNISED], RECOGNISED)
        self.assertEqual(found[Template.ROUTE_B] | found[Template.UNPROFILED], set())  # off the catalogue only
        self.assertEqual(sum(TEMPLATE_COUNTS.values()), len(CODES))

    def test_the_templates_are_bs_rule_rerun_over_v1s_tables(self):
        def b_template(code: str) -> str:  # B-requirements-data/gen_table.py's template(), over B's codes.json row
            profile = v1_catalogue.CODES[code]
            acts = [kind for kind in profile.covers if kind != 'eus_exam']
            if profile.family == 'gi.sedation':
                return 'RECOGNISED'
            if profile.family == 'gi.office_em':
                return 'EM_ADDON' if profile.addon else 'EM'
            if profile.addon:
                return 'ADDON_ACT'
            if profile.family == 'gi.eus':
                return 'EUS_ACT' if acts else 'EUS_EXAM'
            if profile.base:
                return 'BASE'
            if profile.family in ('gi.capsule', 'gi.motility', 'gi.reflux', 'gi.anorectal'):
                return 'TEST'
            if profile.family == 'gi.feeding_tube':
                return 'FEEDING'
            return 'ACT'

        for code in v1_catalogue.CODES:
            self.assertEqual(CODES[int(code)].template.value, b_template(code), code)


class ParityTests(SimpleTestCase):
    def test_the_table_holds_exactly_the_163_catalogue_codes(self):
        self.assertEqual(len(v1_catalogue.CODES), 163)
        self.assertEqual(sorted(CODES), sorted(int(code) for code in v1_catalogue.CODES))
        self.assertEqual(list(CODES), sorted(CODES))  # sorted by code
        self.assertEqual(sorted(CODES), sorted(catalogue.CODES))  # and exactly step 1e's
        self.assertTrue(all(row.code == code for code, row in CODES.items()))

    def test_families_and_groups_equal_step_1es_catalogue_and_v1s_requirements(self):
        for code, row in CODES.items():
            with self.subTest(code=code):
                link = catalogue.code_link(str(code))
                self.assertIs(row.family, link.family)
                self.assertEqual(row.groups, catalogue.requirements(link))
                v1_groups = v1_events.requirements(v1_mapping.code_link(str(code)))
                self.assertEqual(tuple(tuple('eus_exam' if kind is Kind.EXAMINATION and row.family is SessionKind.EUS
                                             else kind.value for kind in group) for group in row.groups), v1_groups)

    def test_every_parameter_equals_step_1es_and_v1s(self):
        for code, row in CODES.items():
            with self.subTest(code=code):
                text = str(code)
                self.assertEqual(row.defining, catalogue.defining(text))
                self.assertEqual(row.technique, catalogue.code_profile(text).technique)
                self.assertEqual(row.site, catalogue.site_class(text))
                self.assertEqual(row.tract, catalogue.eus_tract(text))
                self.assertEqual(row.eus_class, catalogue.examination_class(text))
                self.assertEqual(row.enteroscopy_class, catalogue.code_class(text))
                self.assertEqual(tuple(kind.value for kind in row.defining), v1_mapping.DEFINING.get(text, ()))
                self.assertEqual(row.technique.value if row.technique else '', v1_catalogue.CODES[text].technique)
                self.assertEqual(row.site.value if row.site else '', v1_mapping.DILATION_SITES.get(text, ''))
                self.assertEqual(row.tract.value if row.tract else '', v1_mapping.eus_tract(text))
                self.assertEqual(row.eus_class.value if row.eus_class else '', v1_mapping.examination_class(text))
                self.assertEqual(row.enteroscopy_class.value if row.enteroscopy_class else '',
                                 v1_classes.code_class(text))

    def test_each_tag_rule_is_v1s(self):
        for code, row in CODES.items():
            with self.subTest(code=code):
                text, tags = str(code), set(row.tags)
                link = v1_mapping.code_link(text)
                read = v1_ercp._read_by_a_rule(link)  # D105 (the stent codes) and D106 (the stone removal code)
                self.assertEqual(Tag.XCHG in tags or Tag.YIELD in tags, read)
                self.assertEqual(Tag.D80 in tags, v1_mapping.recognised_only(link))
                self.assertEqual(Tag.STRUCT_PFC in tags, text in v1_mapping.DEFINING_TARGETS)
                self.assertEqual(Tag.ROUTE in tags, text in v1_mapping.TRANSMURAL_INJECTION_CODES)
                self.assertEqual(Tag.LOWER in tags, text in v1_mapping.LOWER_EUS_CLASS)
                self.assertEqual(Tag.CAUSE in tags, 'bleeding_control' in v1_catalogue.CODES[text].covers)
                self.assertEqual(Tag.ADDON in tags, v1_catalogue.CODES[text].addon)
                required = set(v1_profiles.PROFILES[v1_catalogue.CODES[text].family].required_facts)
                self.assertEqual(Tag.R6_CONTEXT in tags, bool(required & {'setting', 'patient_status'}))
                self.assertEqual(Tag.R6_EXTENT in tags or Tag.COLFULL in tags, 'extent' in required)

    def test_att_is_v1s_examination_code_less_the_office_visits(self):
        # v1's events.examination_code is True for the office E/M codes too (the catalogue marks them base), so v1
        # accepted an attempted visit; Appendix A's ATT is the examination's SUPPORT only (BASE and EUS_EXAM), as B's
        # and C's tables have it. Pinned, so the difference is visible to step 4a, which reads ATT and not
        # examination_code.
        v1_att = {int(code) for code in v1_catalogue.CODES
                  if v1_events.examination_code(v1_mapping.code_link(code))}
        att = {code for code, row in CODES.items() if Tag.ATT in row.tags}
        self.assertEqual(v1_att - att, OFFICE_EM)
        self.assertEqual(att - v1_att, set())
        engine_att = {code for code in catalogue.CODES if catalogue.examination_code(catalogue.code_link(str(code)))}
        self.assertEqual(engine_att - att, OFFICE_EM)


class DesignCTests(SimpleTestCase):
    """The table reproduces design C's tags (C-two-pass-data/required_by_code.py and required_tags.py, whose rules are
    re-run here over v1's tables, read only) and differs from them exactly where Appendix A amends C."""

    @staticmethod
    def c_tags(code: str) -> set:
        profile = v1_catalogue.CODES[code]
        family = profile.family
        tags = set()
        exam_only = all(kind in v1_mapping.EXAMINATION_KINDS for kind in profile.covers) if profile.covers else False
        if family == 'gi.sedation':
            tags.add('D80')
        if (profile.base or exam_only) and family != 'gi.office_em':
            tags.add('ATT')
        r6 = {'extent': 'R6:extent', 'target': 'R6:target', 'cannulation': 'R6:cannulation', 'setting': 'R6:setting',
              'patient_status': 'R6:patient_status', 'em_basis': 'R6:em_basis'}
        tags |= {r6[fact] for fact in v1_profiles.profile(family).required_facts}
        if code in v1_mapping.DEFINING:
            tags.add('DEF:' + '/'.join(v1_mapping.DEFINING[code]))
        if profile.technique:
            tags.add(f'TECH:{profile.technique}')
        if code in v1_mapping.DILATION_SITES:
            tags.add(f'SITE:{v1_mapping.DILATION_SITES[code]}')
        if code == '43240':
            tags.add('STRUCT:pfc')
        if code in v1_mapping.TRANSMURAL_INJECTION_CODES:
            tags.add('ROUTE:transmural')
        if code in v1_mapping.UPPER_EUS_CODES:
            tags.add('TRACT:upper')
        if profile.exam == 'full':
            tags.add('STATIONS:all3+EXT:duodenum')
        elif profile.exam == 'limited':
            tags.add('LIMITED')
        if code in v1_mapping.LOWER_EUS_CLASS:
            tags.add(f'LOWER:{v1_mapping.LOWER_EUS_CLASS[code]}')
        if v1_classes.code_class(code):
            tags.add(f'ENT:{v1_classes.code_class(code)}')
        if family == 'gi.colonoscopy':
            tags.add('COLFULL')
        if 'stone_extraction' in profile.covers:
            tags.add('YIELD')
        if code in ('43274', '43275', '43276'):
            tags.add('XCHG')
        if 'bleeding_control' in profile.covers:
            tags.add('CAUSE')
        if family == 'gi.office_em':
            tags.add('C3+SEP')
        if profile.addon:
            tags.add('ADDON')
        return tags

    @staticmethod
    def as_c(row) -> set:
        """The row's tags written in C's notation."""
        names = {Tag.STATIONS: 'STATIONS:all3+EXT:duodenum', Tag.ROUTE: 'ROUTE:transmural'}
        out = set()
        for tag in row.tags:
            if tag is Tag.DEF:
                out |= {f'DEF:{kind.value}' for kind in row.defining}
            elif tag in (Tag.TECH, Tag.SITE, Tag.TRACT, Tag.LOWER, Tag.ENT):
                value = {Tag.TECH: row.technique, Tag.SITE: row.site, Tag.TRACT: row.tract, Tag.LOWER: row.eus_class,
                         Tag.ENT: row.enteroscopy_class}[tag]
                out.add(f'{tag.value}:{value.value}')
            else:
                out.add(names.get(tag, tag.value))
        return out

    def test_the_table_is_cs_tags_with_appendix_as_amendments_and_no_other_difference(self):
        amendments = {}
        for code in v1_catalogue.CODES:
            theirs, ours = self.c_tags(code), self.as_c(CODES[int(code)])
            if theirs != ours:
                amendments.setdefault((tuple(sorted(theirs - ours)), tuple(sorted(ours - theirs))), set()).add(
                    int(code))
        self.assertEqual(amendments, {
            # Appendix A: "COLFULL: colonoscopy" is the colonoscopy's R6
            (('R6:extent',), ()): _family(SessionKind.COLONOSCOPY),
            # 4.3: the member context is one row, R6:context
            (('R6:patient_status', 'R6:setting'), ('R6:context',)): _family(SessionKind.OFFICE_EM),
            # 4.3, Appendix A: YIELD is 43264's; 43265's one group is its defining lithotripsy (D27)
            (('YIELD',), ()): {43265},
            # 4.3: TRACT "lower for 45341-45392 and 44406-44407"
            ((), ('TRACT:lower',)): LOWER_EUS,
        })


def named_kinds(family: SessionKind) -> set:
    """The kinds ``family``'s catalogue entry names, over step 1e's tables: its acts, its bundled and unsupported kinds
    and every kind one of its codes accounts for (DECISIONS D191's first terms)."""
    named = set(catalogue.FAMILY_ACTS[family]) | catalogue.BUNDLED_KINDS[family] | catalogue.UNSUPPORTED_KINDS[family]
    return named | {kind for kind in Kind if catalogue.family_codes_act(family, kind)}


def v1_named_kinds(slug: str) -> set:
    """The same from v1's own tables: FamilyEntry.acts, the Kind-valued items of bundled and unsupported_acts, and
    studio.gi.catalogue.family_codes_act (the EUS's 'eus_exam' is its examination, C-1)."""
    entry, values = v1_catalogue.CATALOGUE[slug], {member.value for member in Kind} | {'eus_exam'}
    named = set(entry.acts) | {name for name, _why in entry.bundled + entry.unsupported_acts}
    named |= {value for value in values if v1_catalogue.family_codes_act(slug, value)}
    return {Kind.EXAMINATION if value == 'eus_exam' else Kind(value) for value in named if value in values}


class FamilyKindTests(SimpleTestCase):
    """DECISIONS D191: FAMILY_KINDS is the one table of "the kinds of a session family", read by K2 and by possibly's
    kind arm, generated from step 1e's tables; NAMED_KINDS is its first terms, the kinds each family's catalogue entry
    names, of which CLAIMED's ERCP kinds are the ERCP entry's (D207). Its rule is re-run here from D191's text over
    those tables, apart from the generator, and its first terms are proved equal to v1's catalogue entries."""

    def test_the_family_kinds_are_d191s_union_over_step_1es_tables(self):
        expected = {}
        for family in catalogue.FAMILY_ACTS:
            kinds = named_kinds(family)
            if family in catalogue.ENDOSCOPIC_FAMILIES:  # the examination and the never-reported kinds
                kinds |= {Kind.EXAMINATION, Kind.CLIP, Kind.CANNULATION}
            if kinds & set(catalogue.REMOVAL_MEMBERS):
                kinds.add(Kind.REMOVAL)
            if kinds & set(catalogue.INTERVENTION_MEMBERS):
                kinds.add(Kind.INTERVENTION)
            if family in catalogue.PROCEDURAL_FAMILIES:
                kinds.add(Kind.MODERATE_SEDATION)
            if kinds:
                kinds.add(Kind.OTHER)
            expected[family] = kinds
        self.assertEqual(dict(table.FAMILY_KINDS), expected)
        self.assertEqual(list(table.FAMILY_KINDS), list(catalogue.FAMILY_ACTS))  # keyed as FAMILY_ACTS, in its order
        self.assertEqual(catalogue.NOT_REPORTED, {Kind.CLIP, Kind.CANNULATION})

    def test_k2s_cases_and_the_unknown_kind_cases(self):
        # D191's K2 cases: an ERCP cannulation, a colonoscopy clip and an EGD esd are kinds their session can hold; a
        # peg in a colonoscopy session is not. 2d#1's P-UNKNOWN-KIND cases: each is in its family's set.
        kinds = table.FAMILY_KINDS
        for family, kind in ((SessionKind.ERCP, Kind.CANNULATION), (SessionKind.COLONOSCOPY, Kind.CLIP),
                             (SessionKind.EGD, Kind.ESD), (SessionKind.COLONOSCOPY, Kind.EXAMINATION),
                             (SessionKind.ANORECTAL, Kind.BALLOON_EXPULSION), (SessionKind.COLONOSCOPY, Kind.REMOVAL),
                             (SessionKind.COLONOSCOPY, Kind.INTERVENTION), (SessionKind.EGD, Kind.MODERATE_SEDATION),
                             (SessionKind.OFFICE_EM, Kind.EM_PROLONGED), (SessionKind.OFFICE_EM, Kind.OTHER)):
            with self.subTest(family=family.value, kind=kind.value):
                self.assertIn(kind, kinds[family])
        for family, kind in ((SessionKind.COLONOSCOPY, Kind.PEG), (SessionKind.ERCP, Kind.REMOVAL),
                             (SessionKind.OFFICE_EM, Kind.MODERATE_SEDATION), (SessionKind.SEDATION, Kind.INTERVENTION),
                             (SessionKind.OFFICE_EM, Kind.INTERVENTION)):
            with self.subTest(family=family.value, kind=kind.value):
                self.assertNotIn(kind, kinds[family])
        self.assertEqual(kinds[SessionKind.OTHER_GI], frozenset())  # no entry names a kind, so not even other
        self.assertFalse(catalogue.family_codes_act(SessionKind.ERCP, Kind.CANNULATION))  # no ERCP code accounts for it

    def test_the_named_kinds_are_each_entrys_and_the_family_kinds_first_terms(self):
        # NAMED_KINDS is what each family's catalogue entry names, and FAMILY_KINDS only adds to it (D191)
        for family in catalogue.FAMILY_ACTS:
            with self.subTest(family=family.value):
                self.assertEqual(table.NAMED_KINDS[family], named_kinds(family))
                self.assertLessEqual(table.NAMED_KINDS[family], table.FAMILY_KINDS[family])
        self.assertEqual(list(table.NAMED_KINDS), list(catalogue.FAMILY_ACTS))
        # CLAIMED's ERCP kinds (3.2.1; the builder's reading DECISIONS D207 records): the fifteen the ERCP entry names,
        # cannulation included. D191 adds the examination, intervention, moderate sedation and other to the family's
        # kinds only; no rule reads their duct (P2)
        ercp = table.NAMED_KINDS[SessionKind.ERCP]
        self.assertEqual(len(ercp), 15)
        self.assertIn(Kind.CANNULATION, ercp)
        self.assertEqual(table.FAMILY_KINDS[SessionKind.ERCP] - ercp,
                         {Kind.EXAMINATION, Kind.INTERVENTION, Kind.MODERATE_SEDATION, Kind.OTHER})

    def test_the_named_kinds_equal_v1s_catalogue_entries(self):
        for family in catalogue.FAMILY_ACTS:
            with self.subTest(family=family.value):
                self.assertEqual(named_kinds(family), v1_named_kinds(v1_mapping.family(family.value)))
                self.assertEqual(table.NAMED_KINDS[family], v1_named_kinds(v1_mapping.family(family.value)))
        self.assertEqual({v1_mapping.family(family.value) for family in table.FAMILY_KINDS},
                         set(v1_catalogue.CATALOGUE))

    def test_the_catalogue_kinds_are_every_kind_but_the_two_umbrellas_and_other(self):
        self.assertEqual(set(Kind) - table.CATALOGUE_KINDS, {Kind.REMOVAL, Kind.INTERVENTION, Kind.OTHER})
        self.assertEqual(table.CATALOGUE_KINDS,
                         frozenset().union(*(named_kinds(family) for family in catalogue.FAMILY_ACTS))
                         | catalogue.NOT_REPORTED | catalogue.UNSUPPORTED_ACTS
                         | {kind for _family, kind in catalogue.READ_UNDER}
                         | {kind for kinds in catalogue.UNRECONCILED_ACTS.values() for kind in kinds})
        self.assertEqual(table.CATALOGUE_KINDS,  # and v1's, by value
                         frozenset().union(*(v1_named_kinds(slug) for slug in v1_catalogue.CATALOGUE))
                         | {Kind(value) for value in v1_catalogue.NOT_REPORTED | v1_catalogue.UNSUPPORTED_ACTS}
                         | {Kind(value) for _family, value in v1_catalogue.READ_UNDER}
                         | {Kind(value) for values in v1_catalogue.UNRECONCILED_ACTS.values() for value in values})


class BoundaryTests(SimpleTestCase):
    def test_the_table_imports_no_v1_module(self):
        code = ('import sys\n'
                'import studio.interpretation.engine.requirements_table\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().split(','),
                         ['studio', 'studio.interpretation', 'studio.interpretation.contract',
                          'studio.interpretation.contract.types', 'studio.interpretation.engine',
                          'studio.interpretation.engine.anatomy', 'studio.interpretation.engine.catalogue',
                          'studio.interpretation.engine.requirements_table'])
