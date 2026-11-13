"""Generate studio/interpretation/engine/requirements_table.py: every catalogue code's template, requirement groups and
code-specific requirement tags (docs/gemini-migration/FINAL-V2.md Appendix A and 4.3; step 1f of 8.1).

    python -B scripts/gen_requirements.py           # write the table (run from cpt-studio/)
    python -B scripts/gen_requirements.py --check   # exit 1, writing nothing, when the committed table differs

The table is generated, committed, and never edited by hand: tests/v2/test_requirements_table.py regenerates it and
requires the committed bytes to equal the regenerated ones.

**What it reads, at build time only** (Appendix A: "Step 1f generates the committed table from the worktree's own
tables"): for the codes, studio.gi.catalogue (CODES), studio.gi.profiles (each family's required facts) and two of the
17 retired v1 modules (FINAL-V2 5.0), mapping (code_link, DEFINING, DILATION_SITES, DEFINING_TARGETS' keys,
TRANSMURAL_INJECTION_CODES, examination_class, eus_tract, LOWER_EUS_CLASS, recognised_only) and classes (code_class);
for the kinds of each family and of the catalogue, step 1e's engine/catalogue.py (FAMILY_ACTS, BUNDLED_KINDS,
UNSUPPORTED_KINDS, family_codes_act, ENDOSCOPIC_FAMILIES, NOT_REPORTED, UMBRELLAS, PROCEDURAL_FAMILIES,
UNSUPPORTED_ACTS, READ_UNDER, UNRECONCILED_ACTS: DECISIONS D191), each proved equal to v1's by value in 1e's tests. This
script is a build tool, not the new path: the engine never imports v1 (5.7 measure 4), only the table this script
writes, which holds enumeration members and integers.

**Where it starts** (8.1 step 1f): design B's generator (design-v2/designs/B-requirements-data/gen_requirements.py and
gen_table.py: the per-code parameters and the template rule) and design C's tags (C-two-pass-data/required_by_code.py
and required_tags.py: one tag per code-specific rule). The judge's Appendix A and 4.3 govern where they differ, and the
table follows them:
- the tag names are 4.3's; a tag's parameter (DEF's kinds, TECH's technique class, SITE's site class, TRACT's tract,
  LOWER's and the STATIONS and LIMITED codes' EUS class, ENT's enteroscopy class) is a typed field of the row;
- a colonoscopy code's extent requirement is COLFULL alone (Appendix A: "R6 per family (extent: egd, enteroscopy,
  flex_sig; COLFULL: colonoscopy; ...)"), where C's table gave colonoscopy codes R6:extent beside COLFULL;
- an office E/M code's member context is the one tag R6:context (4.3), where C's table gave R6:setting and
  R6:patient_status;
- YIELD is 43264's alone (4.3, Appendix A), where C's table also gave it to 43265, whose one requirement group is its
  defining lithotripsy (D27); the rule here is v1's (ercp._read_by_a_rule: the ERCP code whose one requirement group is
  stone_extraction);
- TRACT covers the lower EUS codes too (4.3: "lower for 45341-45392 and 44406-44407"), where C's table tagged the upper
  EUS codes only; the rule here is v1's mapping.eus_tract;
- ATT is the tag of the codes whose SUPPORT is the examination's (B's BASE and EUS_EXAM templates; Appendix A: "the
  examination's SUPPORT for base and exam-only codes, with ATT"). The office E/M codes, base codes in the catalogue, are
  not among them: their SUPPORT is the visit's (B's EM template; C excluded them likewise).

Each rule cites the v1 table it reads; tests/v2/test_requirements_table.py proves every rule equal to v1's computed in
the test (ercp._read_by_a_rule, events.requirements, mapping.recognised_only and the rest) and every code's tags
equal to the code lists 4.3 and Appendix A write out.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Iterable, Sequence
from enum import Enum
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
TABLE = APP / 'studio' / 'interpretation' / 'engine' / 'requirements_table.py'
WIDTH = 120

# The templates of design B (B-requirements.md 4.4; FINAL-V2 Appendix A), in B's order: (member, value, what it is).
# route (b) and UNPROFILED are the two links off the catalogue; no catalogue code has either.
TEMPLATES = (
    ('BASE', 'BASE', "the family's examination without an intervention: the examination's SUPPORT, with ATT"),
    ('ACT', 'ACT', 'a therapeutic endoscopic code: a supporting act per requirement group'),
    ('EUS_EXAM', 'EUS_EXAM', "an examination-only EUS code: the examination's SUPPORT, with ATT"),
    ('EUS_ACT', 'EUS_ACT', 'an EUS code with acts: a supporting act of each, the examination being the session (C-1)'),
    ('ADDON_ACT', 'ADDON_ACT', 'an add-on code of acts (43273, 91013)'),
    ('FEEDING', 'FEEDING', 'a feeding-tube code outside an endoscopy'),
    ('TEST', 'TEST', 'a capsule, motility, reflux or anorectal test'),
    ('EM', 'EM', 'an office E/M code: the visit, its encounter, the same-day rule'),
    ('EM_ADDON', 'EM_ADDON', 'the office E/M add-on (99417), over its em_prolonged act'),
    ('RECOGNISED', 'RECOGNISED', 'a code of a recognised-only family (D80): held, never READY'),
    ('ROUTE_B', 'route (b)', 'a code off the catalogue with an unreconciled act (46221): held, never READY'),
    ('UNPROFILED', 'UNPROFILED', 'any other code, route (d) (C-6): held, never READY'),
)

# The code-specific requirement tags, in the order of 4.3's table, with the codes each applies to as 4.3 writes them.
TAGS = (
    ('ATT', 'ATT', 'base and exam-only EUS codes: attempted_not_completed accepted for the examination'),
    ('R6_EXTENT', 'R6:extent', 'egd, enteroscopy, flex_sig: a reached point, or completion incomplete or terminated'),
    ('COLFULL', 'COLFULL', 'every gi.colonoscopy code: reached at a FULL_REACH landmark, or an ileocolic anastomosis'),
    ('R6_TARGET', 'R6:target', "eus: the examination's or a supporting act's places"),
    ('R6_CANNULATION', 'R6:cannulation', 'ercp: a cannulation of the session with status, access_outcome and duct'),
    ('R6_EM_BASIS', 'R6:em_basis', 'office_em: visit.basis'),
    ('R6_CONTEXT', 'R6:context', 'office_em: member-entered setting and patient status (D3)'),
    ('DEF', 'DEF', "the D27 narrowed codes: a supporting act of the defining kind (the row's defining)"),
    ('TECH', 'TECH', "balloon and wire_bougie codes: technique.device in the row's technique class"),
    ('SITE', 'SITE', "the site-specific dilation codes: every place within the row's site class"),
    ('STRUCT_PFC', 'STRUCT:pfc', '43240: target.structure pancreatic_fluid_collection, no place biliary or hepatic'),
    ('ROUTE', 'ROUTE', '43253: technique.route eus_transmural'),
    ('TRACT', 'TRACT', "the upper and lower EUS codes: the session's tract (the row's tract)"),
    ('STATIONS', 'STATIONS', '43242, 43259: esophagus, stomach and duodenum examined, reached at or past the duodenum'),
    ('LIMITED', 'LIMITED', '43231, 43232, 43237, 43238: reached short of the duodenum, or a station negated'),
    ('LOWER', 'LOWER', "the lower EUS codes: reached in the row's class reach (the stoma codes: a stoma)"),
    ('ENT', 'ENT', "44360-44386: approach and reach of the row's enteroscopy class"),
    ('YIELD', 'YIELD', '43264: yield in stones, stone_fragments, sludge or debris'),
    ('XCHG', 'XCHG', '43274, 43275, 43276: the stent exchange rules (D105, D127)'),
    ('CAUSE', 'CAUSE', 'every code covering bleeding_control: purpose hemostasis, cause not this session'),
    ('C3_SEP', 'C3+SEP', 'office_em: the same-day rule and the separate statement'),
    ('ADDON', 'ADDON', '43273, 91013, 99153, 99417: its primary counted'),
    ('D80', 'D80', '99152, 99153: recognised only, never READY'),
)

# B's template families (gen_table.template): the four test families and the feeding-tube family, by v1 slug.
TEST_FAMILIES = ('gi.capsule', 'gi.motility', 'gi.reflux', 'gi.anorectal')
FEEDING_FAMILY = 'gi.feeding_tube'
OFFICE_EM_FAMILY = 'gi.office_em'
EUS_FAMILY = 'gi.eus'
ERCP_FAMILY = 'gi.ercp'
COLONOSCOPY_FAMILY = 'gi.colonoscopy'
# v1's ercp._read_by_a_rule (D105): the stent kinds whose ERCP codes the exchange rules read (ercp.REMOVAL, PLACEMENT,
# EXCHANGE), and (D106) the one requirement group of the stone removal code.
STENT_KINDS = ('stent_removal', 'stent', 'stent_exchange')
STONE_EXTRACTION = 'stone_extraction'
BLEEDING_CONTROL = 'bleeding_control'
# profiles' required facts -> 4.3's tag (Appendix A: R6 per family; R6:context for the member's setting and status).
R6_TAGS = {'extent': 'R6_EXTENT', 'target': 'R6_TARGET', 'cannulation': 'R6_CANNULATION', 'em_basis': 'R6_EM_BASIS',
           'setting': 'R6_CONTEXT', 'patient_status': 'R6_CONTEXT'}


def _v1() -> tuple:
    """v1's tables, imported only here (a build-time read of the worktree; nothing is written to it)."""
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    from studio.gi import catalogue, profiles
    from studio.interpretation import classes, mapping
    return catalogue, profiles, mapping, classes


def _v2() -> tuple:
    """The enumerations the table is written in: contract/types.py's and engine/catalogue.py's (step 1e)."""
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    from studio.interpretation.contract import types
    from studio.interpretation.engine import catalogue
    return types, catalogue


def _family(types, mapping, slug: str):
    """A v1 family slug as its SessionKind: the value whose slug v1's mapping.family gives is ``slug``."""
    found = [family for family in types.SessionKind if mapping.family(family.value) == slug]
    if len(found) != 1:
        raise ValueError(f'{slug!r} is the slug of {len(found)} session kinds')
    return found[0]


def _kind(types, value: str):
    """A v1 catalogue kind as its Kind: the EUS examination ('eus_exam') is the examination (C-1)."""
    return types.Kind.EXAMINATION if value == 'eus_exam' else types.Kind(value)


def _groups(mapping, link) -> tuple:
    """v1's events.requirements over v1's code link (copied as its rule; the test proves it equal to v1's)."""
    if not link.linked:
        return ()
    if link.route == mapping.UNRECONCILED_ROUTE:
        return (tuple(link.kinds),)
    if link.acts and any(kind in mapping.EXAMINATION_KINDS for kind in link.kinds):
        return tuple((kind,) for kind in link.acts)
    kinds = link.defining or link.kinds
    return (tuple(kinds),) if kinds else ()


def _template(mapping, profile, link) -> str:
    """B's gen_table.template, with D80 read as v1 reads it (mapping.recognised_only) in place of B's family name."""
    if mapping.recognised_only(link):
        return 'RECOGNISED'
    if profile.family == OFFICE_EM_FAMILY:
        return 'EM_ADDON' if profile.addon else 'EM'
    if profile.addon:
        return 'ADDON_ACT'
    if profile.family == EUS_FAMILY:
        return 'EUS_ACT' if link.acts else 'EUS_EXAM'
    if profile.base:
        return 'BASE'
    if profile.family in TEST_FAMILIES:
        return 'TEST'
    if profile.family == FEEDING_FAMILY:
        return 'FEEDING'
    return 'ACT'


def _tags(v1, code: str, profile, link, template: str, groups: tuple) -> list[str]:
    """The code's tags, each by the v1 table that marks it (module docstring), in 4.3's order."""
    catalogue, profiles, mapping, classes = v1
    found = set()
    if template in ('BASE', 'EUS_EXAM'):
        found.add('ATT')
    for fact in profiles.PROFILES[profile.family].required_facts:
        if fact not in R6_TAGS:
            raise ValueError(f'{code}: a required fact 4.3 does not tag: {fact!r}')
        tag = R6_TAGS[fact]
        found.add('COLFULL' if tag == 'R6_EXTENT' and profile.family == COLONOSCOPY_FAMILY else tag)
    marks = {
        'DEF': code in mapping.DEFINING,
        'TECH': bool(profile.technique),
        'SITE': code in mapping.DILATION_SITES,
        'STRUCT_PFC': code in mapping.DEFINING_TARGETS,
        'ROUTE': code in mapping.TRANSMURAL_INJECTION_CODES,
        'TRACT': bool(mapping.eus_tract(code)),
        'STATIONS': profile.exam == mapping.FULL,
        'LIMITED': profile.exam == mapping.LIMITED,
        'LOWER': code in mapping.LOWER_EUS_CLASS,
        'ENT': bool(classes.code_class(code)),
        'YIELD': profile.family == ERCP_FAMILY and groups == ((STONE_EXTRACTION,),),
        'XCHG': profile.family == ERCP_FAMILY and bool(set(link.kinds) & set(STENT_KINDS)),
        'CAUSE': BLEEDING_CONTROL in profile.covers,
        'C3_SEP': profile.family == OFFICE_EM_FAMILY,
        'ADDON': profile.addon,
        'D80': mapping.recognised_only(link),
    }
    found.update(tag for tag, marked in marks.items() if marked)
    return [member for member, _value, _what in TAGS if member in found]


def rows() -> list[dict]:
    """One row per catalogue code, sorted by code: every field the table writes, as enumeration members."""
    v1 = _v1()
    catalogue, _profiles, mapping, classes = v1
    types, v2_catalogue = _v2()
    out = []
    for code in sorted(catalogue.CODES):
        profile = catalogue.CODES[code]
        link = mapping.code_link(code)
        if link.route != mapping.CATALOGUE_ROUTE:
            raise ValueError(f'{code}: a catalogue code off route (a): {link.route!r}')
        groups = _groups(mapping, link)
        template = _template(mapping, profile, link)
        eus_class = mapping.examination_class(code)
        out.append({
            'code': int(code),
            'family': _family(types, mapping, profile.family),
            'template': template,
            'groups': tuple(tuple(_kind(types, kind) for kind in group) for group in groups),
            'tags': _tags(v1, code, profile, link, template, groups),
            'defining': tuple(_kind(types, kind) for kind in mapping.DEFINING.get(code, ())),
            'technique': v2_catalogue.TechniqueClass(profile.technique) if profile.technique else None,
            'site': v2_catalogue.SiteClass(mapping.DILATION_SITES[code]) if code in mapping.DILATION_SITES else None,
            'tract': types.Tract(mapping.eus_tract(code)) if mapping.eus_tract(code) else None,
            'eus_class': v2_catalogue.EusClass(eus_class) if eus_class else None,
            'enteroscopy_class': (v2_catalogue.EnteroscopyClass(classes.code_class(code))
                                  if classes.code_class(code) else None),
        })
    return out


def _named_kinds(types, catalogue, family) -> set:
    """The act kinds ``family``'s catalogue entry names, over step 1e's tables (DECISIONS D191's first terms): its
    reconciled acts (FAMILY_ACTS), its bundled and unsupported kinds (BUNDLED_KINDS, UNSUPPORTED_KINDS: the Kind-valued
    parts of v1's FamilyEntry.bundled and unsupported_acts; an item that names a rule, such as lift_injection, is no
    kind) and every kind one of its codes accounts for (family_codes_act: a code's covers, a tattoo and an injection
    as one act)."""
    named = set(catalogue.FAMILY_ACTS[family]) | catalogue.BUNDLED_KINDS[family] | catalogue.UNSUPPORTED_KINDS[family]
    return named | {kind for kind in types.Kind if catalogue.family_codes_act(family, kind)}


def named_kinds() -> list[tuple]:
    """(family, kinds) for every family with a catalogue entry, in its order (step 1e's FAMILY_ACTS): the act kinds its
    catalogue entry names (_named_kinds), DECISIONS D191's first terms. 3.2.1's "duct (ERCP kinds)" is the ERCP
    entry's: the fifteen the builder's reading names, cannulation included (DECISIONS D207). It is never the family's
    kinds (family_kinds), which add the examination, intervention, moderate sedation and other, whose duct no rule
    reads (P2: a claim no rule needs)."""
    types, catalogue = _v2()
    out = []
    for family in catalogue.FAMILY_ACTS:
        named = _named_kinds(types, catalogue, family)
        out.append((family, tuple(kind for kind in types.Kind if kind in named)))
    return out


def family_kinds() -> list[tuple]:
    """(family, kinds) for every family with a catalogue entry, in its order (step 1e's FAMILY_ACTS): DECISIONS D191's
    table, the one answer to "the kinds of a session family" (3.1 K2 and possibly's kind arm). Family F's set is the
    union of the kinds its catalogue entry names (_named_kinds); for an endoscopic family, the examination and the
    never-reported kinds (clip, cannulation); an umbrella (removal, intervention) when one of its members is in the
    set; moderate sedation, for a procedural family; and other, when the set is not empty."""
    types, catalogue = _v2()
    out = []
    for family in catalogue.FAMILY_ACTS:
        kinds = _named_kinds(types, catalogue, family)
        if family in catalogue.ENDOSCOPIC_FAMILIES:
            kinds |= {types.Kind.EXAMINATION} | catalogue.NOT_REPORTED
        kinds |= {umbrella for umbrella, members in catalogue.UMBRELLAS.items() if kinds & set(members)}
        if family in catalogue.PROCEDURAL_FAMILIES:
            kinds.add(types.Kind.MODERATE_SEDATION)
        if kinds:
            kinds.add(types.Kind.OTHER)
        out.append((family, tuple(kind for kind in types.Kind if kind in kinds)))
    return out


def catalogue_kinds() -> tuple:
    """Every act kind the catalogue names anywhere, over step 1e's tables: the kinds each family's entry names
    (_named_kinds), NOT_REPORTED, UNSUPPORTED_ACTS, the READ_UNDER rules' and route (b)'s UNRECONCILED_ACTS, in Kind's
    order. CLAIMED's codable kinds are these, with an examination, an em_visit, kind other and the umbrellas (3.2.1;
    DECISIONS D194)."""
    types, catalogue = _v2()
    named = set().union(*(_named_kinds(types, catalogue, family) for family in catalogue.FAMILY_ACTS))
    named |= catalogue.NOT_REPORTED | catalogue.UNSUPPORTED_ACTS
    named |= {kind for _family, kind in catalogue.READ_UNDER}
    named |= {kind for kinds in catalogue.UNRECONCILED_ACTS.values() for kind in kinds}
    return tuple(kind for kind in types.Kind if kind in named)


# --- rendering --------------------------------------------------------------------------------------------------------


def _member(member: Enum) -> str:
    return f'{type(member).__name__}.{member.name}'


def _tuple(items: Sequence[str]) -> str:
    return f'({items[0]},)' if len(items) == 1 else f'({", ".join(items)})'


def _wrap(head: str, parts: Iterable[str], tail: str, indent: str) -> list[str]:
    """``head`` + the comma-separated ``parts`` + ``tail``, broken after a comma so no line passes WIDTH."""
    lines, line = [], head
    parts = list(parts)
    for index, part in enumerate(parts):
        piece = part + (', ' if index < len(parts) - 1 else tail)
        if len(line) + len(piece.rstrip()) > WIDTH and line.strip():
            lines.append(line.rstrip())
            line = indent
        line += piece
    lines.append(line.rstrip())
    return lines


def _row(row: dict) -> list[str]:
    fields = [str(row['code']), _member(row['family']), f'Template.{row["template"]}',
              _tuple([_tuple([_member(kind) for kind in group]) for group in row['groups']]) if row['groups'] else '()',
              _tuple([f'Tag.{tag}' for tag in row['tags']]) if row['tags'] else '()']
    named: list[tuple[str, Callable[[object], str]]] = [
        ('defining', lambda value: _tuple([_member(kind) for kind in value])), ('technique', _member),
        ('site', _member), ('tract', _member), ('eus_class', _member), ('enteroscopy_class', _member)]
    fields += [f'{name}={show(row[name])}' for name, show in named if row[name]]
    return _wrap('    CodeRow(', fields, '),', ' ' * 12)


def _kinds_table(name: str, families: Sequence[tuple]) -> list[str]:
    """A ``Mapping[SessionKind, frozenset[Kind]]`` named ``name``: one entry per (family, kinds), in their order."""
    lines = [f'{name}: Mapping[SessionKind, frozenset[Kind]] = MappingProxyType({{']
    for family, kinds in families:
        if not kinds:
            lines += [f'    {_member(family)}: frozenset(),']
            continue
        lines += _wrap(f'    {_member(family)}: frozenset({{', [_member(kind) for kind in kinds], '}),', ' ' * 8)
    return lines + ['})']


def _enum(name: str, doc: str, members: Sequence[tuple[str, str, str]]) -> list[str]:
    lines = ['@unique', f'class {name}(Enum):', f'    """{doc}"""']
    for member, value, what in members:
        lines += [f'    {member} = {value!r}  # {what}']
    return lines


HEADER = '''"""GENERATED by scripts/gen_requirements.py from the worktree's own tables - never edit by hand.
Regenerate with ``python -B scripts/gen_requirements.py`` (from cpt-studio/) and commit;
tests/v2/test_requirements_table.py requires the committed bytes to equal the regenerated ones.

Every catalogue code's template, requirement groups and code-specific requirement tags (docs/gemini-migration/
FINAL-V2.md Appendix A and 4.3; step 1f of 8.1), the act kinds each family's catalogue entry names (NAMED_KINDS:
CLAIMED's ERCP kinds, 3.2.1 and DECISIONS D207), the kinds of each session family (FAMILY_KINDS, DECISIONS D191: read by
K2 and possibly's kind arm) and the act kinds the catalogue names (CLAIMED's codable kinds, 3.2.1). The generator reads
v1's studio.gi.catalogue, studio.gi.profiles, mapping and classes, and step 1e's engine/catalogue.py, at build time;
this module holds their values as enumeration members and integers, imports contract/types.py and engine/catalogue.py
only, and reads no text. engine/requirements.py reads it: what each template and tag requires and reads, CLAIMED, RANK
and dependencies(code).

A row (CodeRow) per catalogue code, sorted by code:
- template: design B's (Template; Appendix A's counts: BASE 11, ACT 97, EUS_EXAM 6, EUS_ACT 8, ADDON_ACT 2, FEEDING 8,
  TEST 15, EM 13, EM_ADDON 1, RECOGNISED 2);
- groups: the requirement groups, each needing a supporting act of one of its kinds (v1's events.requirements: C-1's
  one group per act of an EUS code, D27's defining kinds where they narrow a code, the examination for a base code);
- tags: the code-specific rows of 4.3 that apply to it (Tag), in 4.3's order. Every code also needs 4.3's SUPPORT, the
  bundling and combination rules and R7 and R9 (engine/requirements.py, by template);
- the tags' parameters, None (or ()) where the tag is absent: defining (DEF: D27's kinds, mapping.DEFINING), technique
  (TECH: the catalogue's CodeProfile.technique), site (SITE: mapping.DILATION_SITES), tract (TRACT:
  mapping.eus_tract), eus_class (STATIONS, LIMITED and LOWER: mapping.examination_class) and enteroscopy_class
  (ENT: classes.code_class).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, unique
from types import MappingProxyType

from studio.interpretation.contract.types import Kind, SessionKind, Tract
from studio.interpretation.engine.catalogue import EnteroscopyClass, EusClass, SiteClass, TechniqueClass
'''

ROW_CLASS = '''@dataclass(frozen=True, slots=True)
class CodeRow:
    """One catalogue code's required facts (FINAL-V2 Appendix A): the module docstring gives each field."""
    code: int
    family: SessionKind
    template: Template
    groups: tuple[tuple[Kind, ...], ...]
    tags: tuple[Tag, ...]
    defining: tuple[Kind, ...] = ()
    technique: TechniqueClass | None = None
    site: SiteClass | None = None
    tract: Tract | None = None
    eus_class: EusClass | None = None
    enteroscopy_class: EnteroscopyClass | None = None'''


def render() -> str:
    """The table module's text, a pure function of the worktree's tables."""
    lines = HEADER.split('\n')[:-1]
    lines += ['', '']
    lines += _enum('Template', "Design B's templates (B-requirements.md 4.4; FINAL-V2 Appendix A), each catalogue "
                   'code in exactly one;\n    route (b) and UNPROFILED are the two links off the catalogue.', TEMPLATES)
    lines += ['', '']
    lines += _enum('Tag', 'The code-specific requirement rows of FINAL-V2 4.3 that Appendix A tags codes with, in '
                   "4.3's order.\n    DEF, TECH and SITE are 4.3's DEF:k, TECH:c and SITE:s; each parameter is a field "
                   'of the row.', TAGS)
    lines += ['', '']
    lines += ROW_CLASS.split('\n')
    lines += ['', '', '# Every catalogue code, sorted by code.',
              'CODES: Mapping[int, CodeRow] = MappingProxyType({row.code: row for row in (']
    for row in rows():
        lines += _row(row)
    lines += [')})', '']
    lines += ["# The act kinds each family's catalogue entry names (DECISIONS D191's first terms), over step 1e's "
              'tables, keyed as', '# its FAMILY_ACTS: its acts, its bundled and unsupported kinds, and every kind one '
              "of its codes accounts for. 3.2.1's",
              "# ERCP kinds are the ERCP entry's (CLAIMED; DECISIONS D207), never the family's (FAMILY_KINDS)."]
    lines += _kinds_table('NAMED_KINDS', named_kinds())
    lines += ['# The kinds of each session family (DECISIONS D191; FINAL-V2 3.1 K2, 4.2 possibly), keyed as '
              'NAMED_KINDS: the kinds', '# its catalogue entry names; for an endoscopic family, the examination, clip '
              'and cannulation; an umbrella with a', '# member here; moderate sedation, for a procedural family; '
              'other, when the set is not empty.']
    lines += _kinds_table('FAMILY_KINDS', family_kinds())
    lines += ["# Every act kind the catalogue names anywhere: each family entry's, NOT_REPORTED, "
              "UNSUPPORTED_ACTS, READ_UNDER's and", "# route (b)'s (CLAIMED's codable kinds are these, with an "
              'examination, an em_visit, kind other and the umbrellas:', '# 3.2.1, DECISIONS D194).']
    lines += _wrap('CATALOGUE_KINDS: frozenset[Kind] = frozenset({', [_member(kind) for kind in catalogue_kinds()],
                   '})', ' ' * 4)
    return '\n'.join(lines) + '\n'


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--check', action='store_true', help='compare with the committed table; write nothing')
    options = parser.parse_args(argv)
    text = render()
    if options.check:
        current = TABLE.read_text(encoding='utf-8') if TABLE.exists() else ''
        if current != text:
            print(f'{TABLE} differs from the regenerated table: run scripts/gen_requirements.py and commit.')
            return 1
        print(f'{TABLE} equals the regenerated table.')
        return 0
    TABLE.write_text(text, encoding='utf-8')
    print(f'wrote {TABLE} ({len(text.splitlines())} lines)')
    return 0


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.exit(main(sys.argv[1:]))
