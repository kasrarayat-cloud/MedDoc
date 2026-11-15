"""Gate 6 (docs/gemini-migration/FINAL-V2.md 9.5; step 6c of 8.1): the engine alone, offline, at unit speed, over a
corpus of settled FactSets. Being facts, they carry no words, so paraphrase invariance holds by construction; the
paraphrase risk lives in Gemini and the recordings measure it. Gate 6 gates every engine change and never replaces the
acceptance set.

The corpus, two parts:
1. GENERATED from Appendix A (engine/requirements_table.CODES and engine/requirements.requirements_of, step 1f's
   generated table): for every catalogue code, a READY baseline FactSet built from the code's row (its family, template,
   groups and tags: the family's session and examination, the supporting act of the code's group with the attributes its
   tags read), then, for EVERY requirement the code carries, a T case (the baseline), a U case (the requirement's fact
   left unresolved) and an F case (an established fact that fails it). The expected outcome of each is written below
   from 4.3's columns ("met", "unmet -> fact", "established otherwise ->"), 4.4's outcome function and 4.8's RANK -
   never from what the engine returns: ``perturb`` gives each (requirement, state) its status, the item's fact key and,
   where 4.3 names it, the item's kind. A requirement with no established-otherwise form in 4.3 has its F case built
   from 4.4's reading of an established failure (an act of another date or performer is no positive candidate, so the
   code is held and never READY), its item kind left open where the design gives none (the step's NOTES, question
   Q-F). The bundling row has its C-2 (a biopsy of the single lesion a removal removed) and D45 (an ERCP sphincterotomy
   or dilation beside a stent of its duct) forms; the combination row its U for every code another catalogue code can
   rival (base_included (a) beside a base code, competing_codes otherwise) - a rival that claims the act, D29's site fit
   included (DECISIONS D240: a site code claims no act outside its site class, so 43245 has no rival); LOWER its misfit;
   XCHG all three states. A state with no generated case records the design's reason (``no_form``), and the coverage
   test re-derives every "neither U nor F" from the code's own row. tests/fixtures/interpretation_v2/gate6/CORPUS.json
   is the committed manifest of every generated case and its expectation, and of the rulings' NAMED cases as facts
   (``named``: D240's two dilations at two sites - 43249 READY on the esophageal act, 43245 READY on the duodenal one,
   together and each alone); this module regenerates it and asserts equality, so a change of the table or of the
   expectations is reviewed, as step 1f's committed table is.
2. FROZEN from the fixtures (9.5: "the directive's named cases as facts" and "every engine case among [the refutation's
   cases] is also a gate-6 FactSet"): the settled FactSet of every checklist and refutation case's (i) and (ii), as
   tests/fixtures/interpretation_v2/gate6/fixtures/<case>-<variant>.json (a typed JSON codec of engine/types), run
   through engine/assess alone and held to the case's own expectations.
TEXT-ONLY and SYNTHETIC: no document is read by the generated part (the synthetic TEXT of tests/v2/test_assess.py, its
R1 the allowlisted checks); the frozen part reads each case's synthetic document for R1 only."""
from __future__ import annotations

import dataclasses
import datetime
import json
from dataclasses import replace
from enum import Enum
from functools import lru_cache
from types import MappingProxyType
from typing import Any

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import catalogue as CAT
from studio.interpretation.engine import requirements as RQ
from studio.interpretation.engine import requirements_table as TABLE
from studio.interpretation.engine import types as et
from studio.interpretation.engine.types import Fact, FactSet, Id, IdFamily, IsoDate, Outcome
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_failure_classes as FC

GATE6 = FC.FIXTURES / 'gate6'
CORPUS = GATE6 / 'CORPUS.json'
FROZEN = GATE6 / 'fixtures'
K, S, A, Res = ct.Kind, ct.SessionKind, ct.Attribute, ct.Result
sup, unres, neg, X, E, Y, L = EF.sup, EF.unres, EF.neg, EF.X, EF.E, EF.Y, EF.L
H_, R_, X_ = 'needs_clarification', 'ready', 'excluded'
Q_, EXP_ = 'question', 'explanation'
Req, Tag = RQ.Requirement, TABLE.Tag
ENTERED = AS.MemberContext(setting='office', patient_status='established')
NO_CONTEXT = AS.MemberContext(setting='', patient_status='')


# --- a typed JSON codec for engine/types (the frozen part) ---------------------------------------------------------

ENUMS = {cls.__name__: cls for module in (ct, et) for cls in vars(module).values()
         if isinstance(cls, type) and issubclass(cls, Enum) and cls.__module__ == module.__name__}
RECORDS = {cls.__name__: cls for cls in (et.Fact, et.Cited, et.Anchor, et.UnlistedStatement, ct.Span)}


def encode(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Enum):
        return {'e': f'{type(value).__name__}.{value.value}'}
    if isinstance(value, Id):
        return {'id': str(value)}
    if isinstance(value, IsoDate):
        return {'date': value.value.isoformat(), 'precision': encode(value.precision)}
    if isinstance(value, (tuple, list)):
        return {'tuple': [encode(item) for item in value]}
    if isinstance(value, (dict, MappingProxyType)):
        return {'map': [[encode(key), encode(item)] for key, item in value.items()]}
    if dataclasses.is_dataclass(value) and type(value).__name__ in RECORDS:
        return {'record': type(value).__name__,
                'fields': {field.name: encode(getattr(value, field.name)) for field in dataclasses.fields(value)}}
    raise TypeError(f'no encoding for {type(value).__name__}')


def decode(value: object) -> object:
    if not isinstance(value, dict):
        return value
    if 'e' in value:
        name, _, member = value['e'].partition('.')
        return ENUMS[name](member)
    if 'id' in value:
        return Id.parse(value['id'])
    if 'date' in value:
        return IsoDate(datetime.date.fromisoformat(value['date']), decode(value['precision']))
    if 'tuple' in value:
        return tuple(decode(item) for item in value['tuple'])
    if 'map' in value:
        return {decode(key) if not isinstance(key, list) else tuple(decode(k) for k in key): decode(item)
                for key, item in value['map']}
    if 'record' in value:
        return RECORDS[value['record']](**{name: decode(item) for name, item in value['fields'].items()})
    raise ValueError(f'not an encoding: {value}')


def encode_factset(R: FactSet) -> dict:
    return {field.name: encode(getattr(R, field.name)) for field in dataclasses.fields(R)}


def decode_factset(data: dict) -> FactSet:
    fields = {name: decode(item) for name, item in data.items()}
    return FactSet(**fields)


# --- part 2: the frozen fixtures -------------------------------------------------------------------------------------

def frozen_cases() -> list:
    return [(case_id, variant) for case_id in FC.cases_of('checklist', 'refutation')
            for variant in ('i', 'ii') if variant in FC.case(case_id)['variants']]


def frozen_record(case_id: str, variant: str) -> dict:
    run = FC.run(case_id, variant)
    data = FC.case(case_id)
    return {'case': case_id, 'variant': variant, 'factset': encode_factset(run.R),
            'date_of_service': data['date_of_service'], 'member': data['member'], 'proposals': data['proposals'],
            'expect': data['expect'][variant], 'known': data['known'].get(variant, {})}


def write_frozen() -> None:
    """Writes every frozen FactSet (run by hand after a change of the fixtures; FrozenTests asserts they are current)."""
    FROZEN.mkdir(parents=True, exist_ok=True)
    for case_id, variant in frozen_cases():
        (FROZEN / f'{case_id}-{variant}.json').write_text(json.dumps(frozen_record(case_id, variant), sort_keys=True,
                                                                    separators=(',', ':')) + '\n', encoding='utf-8')


def assess_frozen(record: dict) -> AS.Assessment:
    """engine/assess alone over a frozen FactSet (no settle, no store)."""
    text = FC.document(record['case'])
    dos = datetime.date.fromisoformat(record['date_of_service']) if record['date_of_service'] else None
    member = AS.MemberContext(*record['member']) if record['member'] else NO_CONTEXT
    return AS.assess_facts(decode_factset(record['factset']), date_of_service=dos, text=text, pages=(),
                           integrity=FC.Integrity(), provider_status='succeeded',
                           proposals=FC.proposals_of(record, text), reference=FC.Lookup(), member=member,
                           label=lambda session: str(session.id))


class FrozenTests(SimpleTestCase):
    """The checklist's and the refutation's cases as gate-6 FactSets: engine/assess alone gives each case's expected
    outcome (its known defects as pinned)."""
    maxDiff = None

    def test_the_frozen_factsets_are_current(self):
        for case_id, variant in frozen_cases():
            with self.subTest(case=case_id, variant=variant):
                stored = json.loads((FROZEN / f'{case_id}-{variant}.json').read_text(encoding='utf-8'))
                self.assertEqual(stored, json.loads(json.dumps(frozen_record(case_id, variant), sort_keys=True)))

    def test_the_codec_round_trips(self):
        for case_id, variant in frozen_cases()[:6]:
            with self.subTest(case=case_id, variant=variant):
                R = FC.run(case_id, variant).R
                self.assertEqual(decode_factset(json.loads(json.dumps(encode_factset(R)))), R)

    def test_the_engine_alone_gives_each_expected_outcome(self):
        names = sorted(path.name for path in FROZEN.iterdir())
        self.assertEqual(names, sorted(f'{case_id}-{variant}.json' for case_id, variant in frozen_cases()))
        for name in names:
            record = json.loads((FROZEN / name).read_text(encoding='utf-8'))
            found = FC.outcomes(assess_frozen(record))
            for code, want in record['expect'].items():
                with self.subTest(fixture=name, code=code):
                    got = found[code]
                    if code in record['known']:
                        self.assertEqual((got['status'], got['item']),
                                         (record['known'][code]['status'], record['known'][code]['item']))
                        continue
                    self.assertEqual(got['status'], want['status'], want['why'])
                    if want['item'] is not None:
                        self.assertEqual(got['item'], want['item'], want['why'])
                    if want['item_kind'] is not None:
                        self.assertEqual(got['item_kind'], want['item_kind'], want['why'])


# --- part 1: the corpus generated from Appendix A --------------------------------------------------------------------

THIS = ct.EncounterRelation.THIS_ENCOUNTER
UPPER3 = (ct.Station.ESOPHAGUS, ct.Station.STOMACH, ct.Station.DUODENUM)
ENDOSCOPIC = frozenset({S.EGD, S.ENTEROSCOPY, S.COLONOSCOPY, S.FLEX_SIG, S.EUS, S.ERCP})
REACH = {S.EGD: ct.Extent.SECOND_PORTION_DUODENUM, S.COLONOSCOPY: ct.Extent.CECUM, S.FLEX_SIG: ct.Extent.SIGMOID_COLON,
         S.ERCP: ct.Extent.AMPULLA}
PLACE = {S.EGD: ct.Landmark.GASTRIC_ANTRUM, S.COLONOSCOPY: ct.Landmark.SIGMOID_COLON,
         S.FLEX_SIG: ct.Landmark.SIGMOID_COLON, S.ERCP: ct.Landmark.COMMON_BILE_DUCT}
ENT = TABLE.CODES[44361].enteroscopy_class.__class__
ENT_SESSION = {ENT.JEJUNAL: (ct.Approach.ORAL, None, ct.Extent.JEJUNUM, ct.Landmark.JEJUNUM),
               ENT.ILEAL: (ct.Approach.ORAL, None, ct.Extent.ILEUM, ct.Landmark.ILEUM),
               ENT.STOMA: (ct.Approach.THROUGH_STOMA, ct.AnatomyType.STOMA, ct.Extent.ILEUM, ct.Landmark.ILEUM),
               ENT.POUCH: (ct.Approach.THROUGH_POUCH, ct.AnatomyType.ILEAL_POUCH, ct.Extent.POUCH, ct.Landmark.POUCH)}
SITE_PLACE = {'esophageal': ct.Landmark.DISTAL_ESOPHAGUS, 'gastric_duodenal': ct.Landmark.PYLORUS}
SITE_OUTSIDE = {'esophageal': ct.Landmark.PYLORUS, 'gastric_duodenal': ct.Landmark.DISTAL_ESOPHAGUS}
TECH_DEVICE = {'balloon': ct.Device.BALLOON, 'wire_bougie': ct.Device.WIRE_BOUGIE, 'bougie': ct.Device.BOUGIE}
TECH_OTHER = {'balloon': ct.Device.WIRE_BOUGIE, 'wire_bougie': ct.Device.BALLOON, 'bougie': ct.Device.BALLOON}
UMBRELLA = {kind: umbrella for umbrella, members in (
    (K.REMOVAL, (K.SNARE, K.EMR, K.HOT_BIOPSY, K.ESD)),) for kind in members}
NO_TARGET = frozenset({K.EM_VISIT, K.EM_PROLONGED, K.MODERATE_SEDATION, K.OTHER})


@dataclasses.dataclass
class Built:
    """One generated case: the FactSet, the codes the provider selects ((code, event number)), the member context and
    the date of service."""
    doc: EF.Doc
    codes: list
    member: AS.MemberContext = ENTERED
    date: datetime.date | None = TA.DAY
    act: int = 2


def code_row(code: str) -> TABLE.CodeRow:
    return TABLE.CODES[int(code)]


NO_RIVAL = (TABLE.Template.RECOGNISED, TABLE.Template.ADDON_ACT, TABLE.Template.EM_ADDON)
BASE_TEMPLATES = (TABLE.Template.BASE, TABLE.Template.EUS_EXAM, TABLE.Template.EM)


def base_code(code: str) -> bool:
    """A base code (4.7 base_included: an endoscopic family's examination code, an examination-only EUS code, an office
    visit code)."""
    return code_row(code).template in BASE_TEMPLATES


def act_technique(row: TABLE.CodeRow) -> object:
    """The technique class of the baseline act (``act_fields``): the code's own, a balloon for any other dilation."""
    if row.technique is not None:
        return row.technique
    return TABLE.CODES[43249].technique if row.groups[0][0] is K.DILATION else None


def baseline_places(row: TABLE.CodeRow) -> tuple[object, ...]:
    """The supported places ``act_fields`` gives a code's baseline act (none for a kind with no target)."""
    return tuple(fact.value for fact in act_fields(row, row.groups[0][0]).get('places', ()))


def site_fits(other: TABLE.CodeRow, places: tuple[object, ...]) -> bool:
    """D29's site fit, which combination's claims carry (DECISIONS D240): a site code (4.3 SITE) claims an act only
    when every supported place of the act lies in its site class, at least one ("A verified target outside the class
    does not support"); a code with no site class, any act."""
    if other.site is None:
        return True
    return bool(places) and all(place in CAT.SITE_CLASSES[other.site] for place in places)


@lru_cache(maxsize=None)
def rival(code: str, site_fit: bool = True) -> str | None:
    """The other counted code 4.3's combination U case proposes beside ``code`` (4.7), the first in code order of its
    family, never a recognised-only code or an add-on (an add-on beside its primary is the T case's Q-ADDON):
    - beside an office visit code, another office visit code (4.7's two codes of one visit);
    - beside another base code, a non-base code of its family (and of its EUS tract, D177(1)) - base_included (a),
      a counted code accounting for an act, here with none documented;
    - beside any other code, a non-base code that claims the baseline act (4.7's claims): one of its groups names the
      act's kind, a technique code only of the act's technique class (a technique code never claims a dilation of
      another class, R4), and a site code only of the act's site class (D29's site fit, DECISIONS D240: 43213 claims
      no dilation of the pylorus, so 43245 has no rival).
    None when the catalogue has no such code: competition needs two codes claiming one act. ``site_fit`` False reads
    the claims without D29's site fit (only ``no_form`` asks, to name the reason)."""
    row = code_row(code)
    if row.template in NO_RIVAL:
        return None
    kind = row.groups[0][0]
    places = baseline_places(row)
    for number in sorted(TABLE.CODES):
        other = TABLE.CODES[number]
        if number == row.code or other.family is not row.family or other.template in NO_RIVAL:
            continue
        if row.template is TABLE.Template.EM:
            if other.template is TABLE.Template.EM:
                return str(number)
            continue
        if base_code(str(number)):
            continue
        if base_code(code):
            if other.tract == row.tract:
                return str(number)
            continue
        if any(kind in group for group in other.groups) and other.technique in (None, act_technique(row)) \
                and (not site_fit or site_fits(other, places)):
            return str(number)
    return None


def act_fields(row: TABLE.CodeRow, kind: K) -> dict:
    """The supporting act's facts the code's tags read (4.3's second table), beside SUPPORT's rows."""
    out: dict = {}
    fam = row.family
    place = PLACE.get(fam)
    if fam is S.ENTEROSCOPY:
        place = ENT_SESSION[row.enteroscopy_class][3]
    if fam is S.EUS:
        place = ct.Landmark.RECTUM if row.tract is ct.Tract.LOWER else ct.Landmark.PANCREAS
    if row.site is not None:
        place = SITE_PLACE[row.site.value]
    if place is not None and kind not in NO_TARGET:
        out['places'] = [sup(place)]
    if row.technique is not None:
        out['device'] = sup(TECH_DEVICE[row.technique.value])
    elif kind is K.DILATION:
        out['device'] = sup(ct.Device.BALLOON)
    if kind is K.BLEEDING_CONTROL:
        out.update(purpose=sup(ct.Purpose.HEMOSTASIS), cause=sup(ct.Cause.PRE_EXISTING_LESION))
    if kind is K.STONE_EXTRACTION:
        out['yield_'] = sup(ct.Material.STONES)
    if kind in (K.STENT, K.STENT_REMOVAL, K.STENT_EXCHANGE, K.SPHINCTEROTOMY, K.STONE_EXTRACTION, K.LITHOTRIPSY,
                K.CHOLANGIOSCOPY, K.PRESSURE_MEASUREMENT) and fam is S.ERCP:
        out['duct'] = sup(ct.Duct.BILIARY)
    if kind is K.DRAINAGE:
        out['structure'] = sup(ct.Structure.PANCREATIC_FLUID_COLLECTION)
    if Tag.ROUTE in row.tags:
        out['route'] = sup(ct.Route.EUS_TRANSMURAL)
    return out


def session_fields(row: TABLE.CodeRow, doc: EF.Doc) -> dict:
    fam = row.family
    out: dict = dict(encounter=sup(THIS))
    if fam in REACH:
        out['reached'] = [sup(REACH[fam])]
    if fam is S.ENTEROSCOPY:
        approach, entry, reach, _ = ENT_SESSION[row.enteroscopy_class]
        out.update(approach=sup(approach), reached=[sup(reach)])
        if entry is not None:
            doc.entry(1, type=sup(entry))
            out['through'] = sup(Y(1))
    if fam is S.EUS:
        lower = row.tract is ct.Tract.LOWER
        out['tract'] = sup(ct.Tract.LOWER if lower else ct.Tract.UPPER)
        eus_class = (row.eus_class.value if row.eus_class is not None else None)
        if lower:
            reach = {'sigmoidoscopic': ct.Extent.SIGMOID_COLON, 'colonoscopic': ct.Extent.CECUM,
                     'stoma': ct.Extent.STOMA}[eus_class]
            out['reached'] = [sup(reach)]
            if eus_class == 'stoma':
                doc.entry(1, type=sup(ct.AnatomyType.STOMA))
                out.update(approach=sup(ct.Approach.THROUGH_STOMA), through=sup(Y(1)))
            else:
                out['approach'] = sup(ct.Approach.TRANSANAL)
        elif eus_class == 'limited':
            if row.code in (43231, 43232):
                out.update(reached=[sup(ct.Extent.STOMACH)], stations=[sup(ct.Station.ESOPHAGUS),
                                                                       sup(ct.Station.STOMACH)])
            else:
                out.update(reached=[sup(ct.Extent.STOMACH)],
                           stations=[sup(ct.Station.ESOPHAGUS), sup(ct.Station.STOMACH), neg(ct.Station.DUODENUM)])
        else:
            out.update(reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)], stations=[sup(s) for s in UPPER3])
    return out


def baseline(code: str) -> Built:
    """A FactSet in which ``code`` meets every requirement (its T case), built from its Appendix A row."""
    row = code_row(code)
    fam, kind = row.family, row.groups[0][0]
    doc = EF.Doc()
    if fam is S.OFFICE_EM:
        doc.session(1, S.OFFICE_EM, encounter=sup(THIS))
        doc.act(1, K.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
        if kind is K.EM_PROLONGED:
            doc.act(2, K.EM_PROLONGED)
            return Built(doc, [(code, 2), ('99215', 1)], act=2)
        return Built(doc, [(code, 1)], act=1)
    doc.session(1, fam, **session_fields(row, doc))
    if fam in ENDOSCOPIC:
        if fam is S.EUS:
            doc.exam(1, places=[sup(ct.Landmark.RECTUM if row.tract is ct.Tract.LOWER else ct.Landmark.PANCREAS)])
        else:
            doc.exam(1)
    if fam is S.ERCP:
        doc.act(3, K.CANNULATION, access=sup(ct.AccessOutcome.ACHIEVED), duct=sup(ct.Duct.BILIARY))
    if kind is K.EXAMINATION:
        built = Built(doc, [(code, 1)], act=1)
    else:
        doc.act(2, kind, **act_fields(row, kind))
        built = Built(doc, [(code, 2)], act=2)
    if Tag.ADDON in row.tags:
        primary = str(min(AS.ADDON_PRIMARIES[row.code]))
        p_row = code_row(primary)
        p_kind = p_row.groups[0][0]
        if p_kind is K.EXAMINATION:
            built.codes.append((primary, 1))
        elif p_kind is kind:  # one act of the add-on's own kind is the primary's act too (91013 beside 91010)
            built.codes.append((primary, built.act))
        else:
            doc.act(4, p_kind, **act_fields(p_row, p_kind))
            built.codes.append((primary, 4))
    return built


def run(built: Built) -> AS.Assessment:
    R = built.doc.build()
    return TA.run(R, *built.codes, date=built.date, member=built.member)


# --- each requirement's U and F perturbation, and its expectation from the design --------------------------------------

def _set(doc: EF.Doc, family: str, oid: Id, attribute: A, *facts: Fact) -> None:
    table = getattr(doc, family)
    table[oid] = {**table[oid], attribute: tuple(facts)}


def _drop(doc: EF.Doc, family: str, oid: Id, attribute: A) -> None:
    table = getattr(doc, family)
    table[oid] = {key: value for key, value in table[oid].items() if key is not attribute}


def _first(doc: EF.Doc, family: str, oid: Id, attribute: A) -> Fact:
    return getattr(doc, family)[oid][attribute][0]


def perturb(code: str, requirement: object, state: str) -> tuple[Built, tuple] | None:
    """The case of ``requirement`` in ``state`` (T, U, F) for ``code``: a Built and its expectation (status, item fact,
    item kind, the design's reason), or None when the design gives the state no form for this code (recorded as not
    applicable in CORPUS.json, with its reason)."""
    built = baseline(code)
    row = code_row(code)
    doc, act = built.doc, E(built.act)
    kind = row.groups[0][0]
    never = row.template is TABLE.Template.RECOGNISED
    if state == 'T':
        if never:
            return built, (H_, 'performed_status', None, 'D80: a recognised-only code is never READY')
        if Tag.ADDON in row.tags and code_row(built.codes[1][0]).groups == row.groups:
            # the add-on and its primary are acts of one kind: each claims the other's act, and 4.7's competition holds
            # both (the step's NOTES, question Q-ADDON)
            return built, (H_, 'competing_codes', Q_, '4.7: an add-on of its primary\'s kind competes with it')
        return built, (R_, None, None, '4.3: every requirement met')
    if never:
        return None
    U = state == 'U'
    if requirement in (Req.SUP_KIND, Tag.DEF):
        if U:
            _set(doc, 'events', act, A.KIND, unres(kind))
            return built, (H_, 'performed_status', Q_, '4.3 row 1 unresolved: performed_status (RANK 4)')
        if kind in UMBRELLA:
            _set(doc, 'events', act, A.KIND, sup(UMBRELLA[kind]))
            return built, (H_, 'act_method', Q_, '4.3 row 1: a positive umbrella never supports (RANK 9)')
        _set(doc, 'events', act, A.KIND, sup(K.OTHER))
        return built, (H_, 'performed_status', None, '4.4: no candidate of the group: not documented (RANK 4)')
    if requirement is Req.SUP_STATUS:
        if U:
            _set(doc, 'events', act, A.STATUS, unres(ct.Status.PERFORMED))
            return built, (H_, 'performed_status', Q_, '4.3 row 2 unresolved (RANK 4)')
        _set(doc, 'events', act, A.STATUS, sup(ct.Status.ATTEMPTED_NOT_COMPLETED))
        if Tag.ATT in row.tags and row.enteroscopy_class in (ENT.ILEAL,):
            return built, (H_, 'extent', EXP_, 'D217 and D72: the deeper class is F when every examination of the '
                                               'session is established attempted')
        if Tag.ATT in row.tags:
            return built, (R_, None, None, '4.3 ATT: attempted accepted for a base or exam-only code (52/53)')
        return built, (H_, 'performed_status', EXP_, '4.3 row 2: attempted on another code (C-9), an explanation')
    if requirement is Req.SUP_DATE:
        if U:
            _set(doc, 'events', act, A.DATE_RELATION, unres(ct.DateRelation.ON_DATE_OF_SERVICE))
            return built, (H_, 'event_time', Q_, '4.3 row 3 unresolved (RANK 6)')
        _set(doc, 'events', act, A.DATE_RELATION, sup(ct.DateRelation.EARLIER_DATE))
        return built, (H_, None, None, '4.4: an act of another date is no positive candidate: never READY')
    if requirement is Req.SUP_PERFORMER:
        if U:
            _set(doc, 'events', act, A.PERFORMER, unres(ct.Performer.DOCUMENTING_TEAM))
            return built, (H_, 'event_performer', Q_, '4.3 row 4 unresolved (RANK 7)')
        _set(doc, 'events', act, A.PERFORMER, sup(ct.Performer.OTHER_CLINICIAN))
        return built, (H_, None, None, '4.4: an act of another performer is no positive candidate: never READY')
    if requirement is Req.SUP_ENTRY:
        if U:
            _set(doc, 'events', act, A.ENTRY, unres(ct.Owner.DOCUMENTING_CLINICIAN))
            return built, (H_, 'event_entry', Q_, '4.3 row 5 unresolved (RANK 5)')
        _set(doc, 'events', act, A.ENTRY, sup(ct.Owner.NURSING))
        return built, (H_, 'event_entry', EXP_, '4.3 row 5: another role\'s entry, an explanation (RANK 5)')
    if requirement is Req.SUP_SESSION:
        if U:
            _set(doc, 'events', act, A.SESSION, unres(X(1)))
            if row.family is S.OFFICE_EM:
                return built, (H_, 'event_time', Q_, '4.3 row 6 unresolved: the visit\'s session not established, '
                                                     'so neither is its encounter (V.this_encounter, RANK 6 before 8)')
            return built, (H_, 'procedure', Q_, '4.3 row 6 unresolved (RANK 8)')
        other = S.MOTILITY if row.family is not S.MOTILITY else S.REFLUX
        doc.session(9, other)
        _set(doc, 'events', act, A.SESSION, sup(X(9)))
        return built, (H_, None, None, '4.3 row 6: a session of another family, never READY')
    if requirement is Req.SUP_SESSION_DONE:
        if built.act == 1 or E(1) not in doc.events or row.family not in ENDOSCOPIC:
            return None  # the act is the session's examination, or the session has none: row 7 is rows 2-5
        if U:
            _set(doc, 'events', E(1), A.STATUS, unres(ct.Status.PERFORMED))
            return built, (H_, 'performed_status', Q_, '4.3 row 7: the examination\'s status unresolved (RANK 4)')
        _set(doc, 'events', E(1), A.ENTRY, sup(ct.Owner.NURSING))
        return built, (H_, 'event_entry', EXP_, '4.3 row 7: the examination told in another role\'s entry (RANK 5)')
    if requirement is Req.SUP_CLEAN:
        number = 7
        if U:
            doc.event(number, kind=sup(kind), status=unres(ct.Status.PERFORMED), session=sup(X(1)),
                      date=sup(ct.DateRelation.ON_DATE_OF_SERVICE))
            return built, (H_, None, None, '4.5 [R:HO-3]: a possible statement of the kind pairs: never READY')
        doc.event(number, kind=sup(kind), status=neg(ct.Status.PERFORMED), session=sup(X(1)),
                  date=sup(ct.DateRelation.ON_DATE_OF_SERVICE), breadth=sup(ct.Breadth.ALL_OF_KIND))
        return built, (H_, f'conflict:{kind.value}', Q_, '4.5: a broad denial of the kind: CONTRADICTION (RANK 1)')
    if requirement is Req.V_THIS_ENCOUNTER:
        value = unres(THIS) if U else sup(ct.EncounterRelation.SEPARATE_ENCOUNTER)
        _set(doc, 'sessions', X(1), A.ENCOUNTER, value)
        return built, (H_, 'event_time', Q_ if U else None, '4.3 E/M: the visit\'s session not this encounter (RANK 6)')
    if requirement in (Tag.R6_EXTENT, Tag.COLFULL, Tag.LOWER):
        if U:
            reach = _first(doc, 'sessions', X(1), A.REACHED)
            _set(doc, 'sessions', X(1), A.REACHED, unres(reach.value))
            return built, (H_, 'extent' if requirement is not Tag.LOWER else 'extent', Q_,
                           '4.3: the reach unresolved (RANK 14)')
        if requirement is Tag.LOWER:
            # 4.3 LOWER "established otherwise -> misfit: held (class)", an established failure: an explanation (4.8).
            # The sigmoidoscopic class reaches no further than the sigmoid colon, so a supported cecum misfits it; the
            # colonoscopic class reaches beyond it, so a supported sigmoid colon alone misfits it; the stoma class's
            # misfit is its approach - another approach supported, asked as the approach (D225 P5: RANK row 8)
            lower_class = row.eus_class.value if row.eus_class is not None else None
            if lower_class == 'stoma':
                _set(doc, 'sessions', X(1), A.APPROACH, sup(ct.Approach.TRANSANAL))
                return built, (H_, 'procedure', EXP_, '4.3 LOWER: the stoma class entered transanally is the misfit; '
                                                      'D225 P5 names the approach (RANK 8), an explanation')
            outside = ct.Extent.CECUM if lower_class == 'sigmoidoscopic' else ct.Extent.SIGMOID_COLON
            _set(doc, 'sessions', X(1), A.REACHED, sup(outside))
            return built, (H_, 'extent', EXP_, '4.3 LOWER: a supported reach outside the class reach, the misfit: held '
                                               '(class), an explanation (RANK 14)')
        short = ct.Extent.TRANSVERSE_COLON if requirement is Tag.COLFULL else _first(doc, 'sessions', X(1), A.REACHED).value
        _set(doc, 'sessions', X(1), A.REACHED, sup(short))
        _set(doc, 'sessions', X(1), A.COMPLETION, sup(ct.Completion.INCOMPLETE))
        if row.enteroscopy_class is ENT.ILEAL:
            return built, (H_, 'extent', EXP_, 'D217: the deeper class reads an established incomplete completion as '
                                               'F (the class explanation)')
        return built, (R_, None, None, '4.3: completion incomplete beside a supported reach: met, the 52/53 '
                                       'consideration (established otherwise)')
    if requirement is Tag.R6_TARGET:
        if not U:
            return None  # 4.3: no established-otherwise form
        for event in list(doc.events):
            _drop(doc, 'events', event, A.TARGET_PLACES)
        return built, (H_, 'target', Q_, '4.3 R6:target unmet (RANK 12)')
    if requirement is Tag.R6_CANNULATION:
        value = unres(ct.AccessOutcome.ACHIEVED) if U else sup(ct.AccessOutcome.FAILED)
        _set(doc, 'events', E(3), A.ACCESS_OUTCOME, value)
        if U:
            return built, (H_, 'cannulation', Q_, '4.3 R6:cannulation unmet (RANK 16)')
        return built, (R_, None, None, '4.3: a failed cannulation is the D107 52/53 consideration (established '
                                       'otherwise)')
    if requirement is Tag.R6_EM_BASIS:
        if not U:
            return None
        _set(doc, 'events', E(1), A.VISIT_BASIS, unres(ct.EmBasis.TOTAL_TIME))
        return built, (H_, 'em_basis', Q_, '4.3 R6:em_basis unmet (RANK 19)')
    if requirement is Tag.R6_CONTEXT:
        if not U:
            return None
        built.member = NO_CONTEXT
        return built, (H_, 'setting', Q_, '4.3 R6:context unmet: setting (RANK 23)')
    if requirement is Tag.TECH:
        value = unres(TECH_DEVICE[row.technique.value]) if U else sup(TECH_OTHER[row.technique.value])
        _set(doc, 'events', act, A.TECHNIQUE_DEVICE, value)
        return built, (H_, 'technique', Q_ if U else EXP_, '4.3 TECH: ' + ('unresolved (RANK 10)' if U else
                                                                            'another class, an explanation'))
    if requirement is Tag.SITE:
        value = unres(SITE_PLACE[row.site.value]) if U else sup(SITE_OUTSIDE[row.site.value])
        _set(doc, 'events', act, A.TARGET_PLACES, value)
        return built, (H_, 'act_target', Q_ if U else EXP_, '4.3 SITE: ' + ('unresolved (RANK 11)' if U else
                                                                              'another site, an explanation'))
    if requirement is Tag.STRUCT_PFC:
        value = unres(ct.Structure.PANCREATIC_FLUID_COLLECTION) if U else sup(ct.Structure.GALLBLADDER)
        _set(doc, 'events', act, A.TARGET_STRUCTURE, value)
        return built, (H_, 'target', Q_ if U else EXP_, '4.3 STRUCT:pfc (RANK 12)')
    if requirement is Tag.ROUTE:
        value = unres(ct.Route.EUS_TRANSMURAL) if U else sup(ct.Route.SUBMUCOSAL)
        _set(doc, 'events', act, A.TECHNIQUE_ROUTE, value)
        return built, (H_, 'technique', Q_ if U else EXP_, '4.3 ROUTE (RANK 10)')
    if requirement is Tag.TRACT:
        tract = _first(doc, 'sessions', X(1), A.TRACT).value
        other = ct.Tract.UPPER if tract is ct.Tract.LOWER else ct.Tract.LOWER
        _set(doc, 'sessions', X(1), A.TRACT, unres(tract) if U else sup(other))
        return built, (H_, 'procedure', Q_ if U else None, '4.3 TRACT (RANK 8)')
    if requirement is Tag.STATIONS:
        if U:
            _drop(doc, 'sessions', X(1), A.STATIONS)
            return built, (H_, 'exam_stations', Q_, '4.3 STATIONS: an empty list with no completeness claim '
                                                    '[R:SC-B] (RANK 13)')
        _set(doc, 'sessions', X(1), A.STATIONS, sup(ct.Station.ESOPHAGUS), neg(ct.Station.STOMACH),
             sup(ct.Station.DUODENUM))
        return built, (H_, 'exam_stations', EXP_, '4.3 STATIONS: a station negated, the class explanation')
    if requirement is Tag.LIMITED:
        if U:
            _set(doc, 'sessions', X(1), A.REACHED, unres(ct.Extent.STOMACH))
            _set(doc, 'sessions', X(1), A.STATIONS, *(unres(s) for s in UPPER3))
            return built, (H_, 'exam_stations', Q_, '4.3 LIMITED unmet (RANK 13)')
        _set(doc, 'sessions', X(1), A.REACHED, sup(ct.Extent.SECOND_PORTION_DUODENUM))
        _set(doc, 'sessions', X(1), A.STATIONS, *(sup(s) for s in UPPER3))
        return built, (H_, 'exam_stations', None, '4.3 LIMITED: all three examined, the class')
    if requirement is Tag.ENT:
        approach = _first(doc, 'sessions', X(1), A.APPROACH).value
        # another approach that fits no class reach of this code (D219: transanal through an ileal pouch fits POUCH)
        other = ct.Approach.TRANSANAL if approach is ct.Approach.ORAL else ct.Approach.ORAL
        _set(doc, 'sessions', X(1), A.APPROACH, unres(approach) if U else sup(other))
        return built, (H_, 'procedure', Q_ if U else None, '4.3 ENT: the approach (RANK 8)')
    if requirement is Tag.YIELD:
        value = unres(ct.Material.STONES) if U else neg(ct.Material.ANYTHING)
        _set(doc, 'events', act, A.YIELD, value)
        return built, (H_, 'act_yield', Q_ if U else EXP_, '4.3 YIELD (RANK 15)')
    if requirement is Tag.XCHG:
        if row.code == 43276:
            # 4.3 XCHG for 43276: a stent removal and a stent placement each supporting, in one duct (duct supported
            # and equal); the baseline's exchange act becomes the placement, beside a removal
            _set(doc, 'events', act, A.KIND, sup(K.STENT))
            if U:
                doc.act(8, K.STENT_REMOVAL, duct=unres(ct.Duct.BILIARY))
                return built, (H_, 'act_target', Q_, '4.3 XCHG: the removal\'s duct not established beside the '
                                                     'placement: the duct asked (act_target, RANK 11)')
            doc.act(8, K.STENT_REMOVAL, status=neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                    duct=sup(ct.Duct.BILIARY))
            return built, (H_, 'performed_status', None, '4.3 XCHG "the removal negated: 43276 not supported": not '
                                                         'documented (RANK 4)')
        counterpart = K.STENT_REMOVAL if kind is not K.STENT_REMOVAL else K.STENT
        if U:
            doc.act(8, counterpart, duct=unres(ct.Duct.BILIARY))
            return built, (H_, 'act_target', Q_, '4.3 XCHG: a possibly performed counterpart in an unknown duct: the '
                                                 'duct asked (act_target, RANK 11); never READY')
        doc.act(8, counterpart, status=neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                duct=sup(ct.Duct.BILIARY))
        return built, (R_, None, None, '4.3 XCHG "the removal negated ... 43274 can be READY (X1)": the counterpart '
                                       'negated is no possibly performed counterpart')
    if requirement is Tag.CAUSE:
        value = unres(ct.Cause.PRE_EXISTING_LESION) if U else sup(ct.Cause.ACT_OF_THIS_SESSION)
        _set(doc, 'events', act, A.CAUSE, value)
        if U:
            return built, (H_, 'act_cause', Q_, '4.3 CAUSE unresolved (RANK 17)')
        return built, (H_, None, None, '4.3 CAUSE: act_of_this_session, bundled as a procedural adjunct')
    if requirement is Tag.C3_SEP:
        doc.session(5, S.FLEX_SIG, reached=[sup(ct.Extent.SIGMOID_COLON)])
        doc.exam(5, session=X(5))
        if U:
            _set(doc, 'events', E(5), A.DATE_RELATION, unres(ct.DateRelation.ON_DATE_OF_SERVICE))
            return built, (H_, 'event_time', Q_, '4.7 C-3: an undatable act, no established procedure day (RANK 6)')
        _set(doc, 'events', E(1), A.VISIT_SEPARATELY_IDENTIFIABLE, neg(ct.Separate.STATED))
        return built, (H_, 'separate_em', EXP_, '4.7 C-3: a procedure day, the separate statement denied (RANK 20)')
    if requirement is Tag.ADDON:
        if not U:
            return None
        built.codes = built.codes[:1]
        return built, (H_, 'performed_status', Q_, '4.3 ADDON: no primary counted (RANK 4)')
    if requirement is Tag.ATT:
        if U:
            return None  # ATT has no unmet form (4.3 "-"); its F is SUP.2's attempted examination
        _set(doc, 'events', E(1), A.STATUS, sup(ct.Status.ATTEMPTED_NOT_COMPLETED))
        if row.enteroscopy_class is ENT.ILEAL:
            return built, (H_, 'extent', EXP_, 'D217 and D72: the deeper class is F when every examination is '
                                               'established attempted')
        return built, (R_, None, None, '4.3 ATT: attempted accepted, the 52/53 consideration')
    if requirement is Req.BUNDLING:
        if kind is K.BIOPSY:
            # 4.7 biopsy_of_removed_lesion (C-2): a biopsy of the lesion a removal removed, the lesion single; the
            # whole's status read by possibly (4.3's bundling row), so a removal whose status is not established asks
            doc.lesion(1, multiplicity=sup(ct.Multiplicity.SINGLE))
            _set(doc, 'events', act, A.TARGET_LESION, sup(L(1)))
            fields = {key: value for key, value in act_fields(row, K.SNARE).items() if key in ('places',)}
            doc.act(6, K.SNARE, lesion=sup(L(1)), status=unres(ct.Status.PERFORMED) if U else sup(ct.Status.PERFORMED),
                    **fields)
            if U:
                return built, (H_, 'act_part', Q_, '4.7 biopsy_of_removed_lesion: the removal, its status not '
                                                   'established, read by possibly: asked, never silent (RANK 17)')
            return built, (H_, 'performed_status', EXP_, '4.7 biopsy_of_removed_lesion (C-2): the biopsy of the single '
                                                         'lesion the removal removed is bundled: an explanation naming '
                                                         'the whole (RANK 18)')
        if kind in (K.SPHINCTEROTOMY, K.DILATION) and row.family is S.ERCP:
            # 4.7 stent_included (D45): an ERCP sphincterotomy or dilation beside a stent placement of the same duct
            # ("both ducts established": the part's duct is stated too)
            _set(doc, 'events', act, A.TARGET_DUCT, sup(ct.Duct.BILIARY))
            doc.act(6, K.STENT, duct=unres(ct.Duct.BILIARY) if U else sup(ct.Duct.BILIARY))
            if U:
                return built, (H_, 'act_target', Q_, '4.7 stent_included (D45): the stent\'s duct not established: '
                                                     'asked, never READY alone (bundling identity, RANK 17)')
            return built, (H_, 'performed_status', EXP_, '4.7 stent_included (D45): a stent placement in the same duct '
                                                         'includes it: bundled, an explanation (RANK 18)')
        whole = {K.SNARE: K.EMR, K.HOT_BIOPSY: K.EMR, K.INJECTION: K.EMR, K.FNA: K.DRAINAGE,
                 K.ABLATION: K.SNARE, K.BLEEDING_CONTROL: K.SNARE, K.CLIP: K.SNARE}.get(kind)
        if whole is None or kind is K.BLEEDING_CONTROL:
            return None  # no bundling rule includes this kind in another act (the bleeding control: CAUSE's F)
        doc.act(6, whole, **({} if whole is not K.DRAINAGE else dict(structure=sup(ct.Structure.PANCREATIC_FLUID_COLLECTION))))
        relation = ct.PartRelation.ADJUNCT_OF if whole is K.SNARE else ct.PartRelation.STEP_OF
        _set(doc, 'events', act, A.PART_OF, unres(E(6)) if U else sup(E(6)))
        _set(doc, 'events', act, A.PART_RELATION, sup(relation))
        if U:
            return built, (H_, None, None, '4.7: a bundling into another act read on an unresolved part_of: never '
                                           'READY (act_part, RANK 17, unless the whole\'s code holds first)')
        return built, (H_, None, EXP_, '4.7: part of another act, bundled (an explanation naming the whole, RANK 18)')
    if requirement is Req.COMBINATION:
        if row.template in (TABLE.Template.BASE, TABLE.Template.EUS_EXAM) and not U:
            reportable = {S.EGD: K.BIOPSY, S.COLONOSCOPY: K.BIOPSY, S.FLEX_SIG: K.BIOPSY, S.ENTEROSCOPY: K.BIOPSY,
                          S.ERCP: K.SPHINCTEROTOMY, S.EUS: K.FNA}[row.family]
            doc.act(6, reportable, **act_fields(row, reportable))
            return built, (H_, 'base_included', EXP_, '4.7 base_included (b): a reportable act of the session (RANK 21)')
        if not U:
            return None  # 4.3: combination has no established-otherwise form ("-")
        other = rival(code)
        if other is None:
            return None
        if base_code(code):
            # base_included (a): another counted code of its family beside it, no act of its own documented
            built.codes.append((other, 9))
            return built, (H_, 'base_included', Q_, '4.7 base_included (a): another counted code of the family beside '
                                                    'it, with no act documented: a question (RANK 21)')
        built.codes.append((other, built.act))
        return built, (H_, 'competing_codes', Q_, '4.7 competition (P-ADMIT2, D40): another counted code claims the '
                                                  'same documented act: one competing_codes question (RANK 22)')
    if requirement is Req.R7_R9:
        if not U:
            return None
        built.date = None
        return built, (H_, None, None, '4.4 R7: with no date of service every code is held (service_date)')
    return None


# The parts 4.7's bundling row bundles into another act: NOT_REPORTED's clip; the lift (an injection or a tattoo);
# the resection technique (a snare or hot-forceps removal); the procedural adjunct (a bleeding control, an ablation, a
# clip or an injection); biopsy_of_removed_lesion's biopsy; drainage_step's aspiration; and, in an ERCP session,
# stent_included's sphincterotomy and dilation (D45). A code of any other kind has no bundling form to generate.
BUNDLED_PARTS = frozenset({K.CLIP, K.INJECTION, K.TATTOO, K.SNARE, K.HOT_BIOPSY, K.BLEEDING_CONTROL, K.ABLATION,
                           K.BIOPSY, K.FNA})
ERCP_BUNDLED_PARTS = frozenset({K.SPHINCTEROTOMY, K.DILATION})


def no_form(code: str, requirement: object, state: str) -> str:
    """Why ``perturb`` generates no case for ``requirement`` in ``state`` for ``code``: the design's reason, read from
    4.3's columns and 4.7 - or 'not generated' when none applies (the coverage test refuses that one)."""
    row = code_row(code)
    kind = row.groups[0][0]
    if row.template is TABLE.Template.RECOGNISED:
        return 'D80: a recognised-only code is never READY; its requirements give it no U or F form'
    if requirement is Req.SUP_SESSION_DONE:
        return '4.3 row 7: the act is the session\'s examination, or its session has none (rows 2-5 decide)'
    if state == 'F' and requirement in (Tag.R6_TARGET, Tag.R6_EM_BASIS, Tag.R6_CONTEXT, Tag.ADDON, Req.R7_R9,
                                        Req.COMBINATION):
        return '4.3: no established-otherwise form ("-")'
    if state == 'U' and requirement is Tag.ATT:
        return '4.3 ATT: no unmet form ("-")'
    if requirement is Req.BUNDLING:
        if kind is K.BLEEDING_CONTROL:
            return '4.3 CAUSE: a bleeding control caused by an act of this session is the procedural adjunct (CAUSE\'s F)'
        if kind not in BUNDLED_PARTS and not (kind in ERCP_BUNDLED_PARTS and row.family is S.ERCP):
            return '4.7: no bundling rule bundles an act of this kind into another act'
    if requirement is Req.COMBINATION and state == 'U' and rival(code) is None:
        if row.template in NO_RIVAL:
            return '4.3 ADDON: an add-on beside its primary is its T case (the step\'s NOTES, Q-ADDON); no other rival'
        if rival(code, site_fit=False) is not None:
            return ('4.7 with D29\'s site fit (DECISIONS D240): every other catalogue code that claims this act\'s kind '
                    'and technique is of another site class and claims no act outside it, so none competes for this '
                    'act; the named case D240 (two dilations at two sites) holds the rule')
        return '4.7: no other catalogue code claims this act (competition needs two codes) and it is no base code'
    return 'not generated'


def corpus() -> list:
    """Every generated case: code, requirement, state, and its expectation - or, with expect null, why the design gives
    that state no form for that code (``no_form``)."""
    out = []
    for code in sorted(str(code) for code in TABLE.CODES):
        for requirement in RQ.requirements_of(code):
            for state in ('T', 'U', 'F'):
                found = perturb(code, requirement, state)
                name = requirement.value
                if found is None:
                    out.append({'code': code, 'requirement': name, 'state': state, 'expect': None,
                                'why': no_form(code, requirement, state)})
                    continue
                status, item, kind, why = found[1]
                out.append({'code': code, 'requirement': name, 'state': state,
                            'expect': {'status': status, 'item': item, 'item_kind': kind, 'why': why}})
    return out


# --- the rulings' named cases as facts (9.5: "the directive's named cases as facts") --------------------------------


def two_site_dilations() -> EF.Doc:
    """DECISIONS D240's input as facts - "The distal esophageal stricture was dilated with a balloon. The duodenal bulb
    stricture was dilated with a balloon." - an EGD X1 of this encounter to the second portion of the duodenum (its
    examination E1), a balloon dilation E2 at the distal esophagus and a balloon dilation E3 at the duodenal bulb, each
    done today by the documenting team in the documenting clinician's entry."""
    doc = EF.egd(encounter=sup(THIS))
    doc.act(2, K.DILATION, places=[sup(ct.Landmark.DISTAL_ESOPHAGUS)], device=sup(ct.Device.BALLOON))
    doc.act(3, K.DILATION, places=[sup(ct.Landmark.DUODENAL_BULB)], device=sup(ct.Device.BALLOON))
    return doc


D240_WHY = {'43249': 'D240 (D29\'s site fit): evaluate\'s code rows read only the supporting acts within the code\'s SITE '
                     'class, so 43249 is supported by the esophageal balloon dilation alone, and combination\'s claims '
                     'carry the site fit, so no code competes for it: READY on E2',
            '43245': 'D240 (D29\'s site fit): 43245 is supported by the duodenal bulb dilation alone, inside its gastric '
                     'or duodenal class, and no code competes for it: READY on E3'}
# Each named case: (name, shape, the codes the provider selects with the event their evidence cites, the expected
# supporting acts of each READY code). Every proposal cites the examination's unit, so no kept span selects either
# dilation and the site fit alone decides.
NAMED = (('D240', 'both codes', (('43249', 1), ('43245', 1)), {'43249': ('E2',), '43245': ('E3',)}),
         ('D240', '43249 alone', (('43249', 1),), {'43249': ('E2',)}),
         ('D240', '43245 alone', (('43245', 1),), {'43245': ('E3',)}))
NAMED_BUILDERS = {'D240': two_site_dilations}


def named() -> list[dict[str, object]]:
    """The named cases as CORPUS.json records them: each code's expected outcome (READY, no item, its supporting acts)
    and its reason, from the ruling."""
    return [{'case': name, 'shape': shape, 'codes': [[code, number] for code, number in codes],
             'expect': {code: {'status': R_, 'item': None, 'acts': list(acts[code]), 'why': D240_WHY[code]}
                        for code in sorted(acts)}}
            for name, shape, codes, acts in NAMED]


def run_named(record: dict[str, Any]) -> AS.Assessment:
    built = Built(NAMED_BUILDERS[record['case']](), [(code, number) for code, number in record['codes']])
    return run(built)


def write_corpus() -> None:
    GATE6.mkdir(parents=True, exist_ok=True)
    cases = corpus()
    CORPUS.write_text(json.dumps({'about': 'FINAL-V2 9.5 gate 6: every catalogue code x requirement x state (T, U, F), '
                                           'generated from Appendix A by tests/v2/test_gate6.py; expect null: no case '
                                           'is generated, and why says the design\'s reason (4.3\'s "-", 4.7). named: '
                                           'the rulings\' named cases as facts (DECISIONS D240: two dilations at two '
                                           'sites).',
                                  'cases': cases, 'named': named()}, indent=1, sort_keys=True) + '\n',
                      encoding='utf-8')


@lru_cache(maxsize=None)
def committed() -> dict:
    return json.loads(CORPUS.read_text(encoding='utf-8'))


class GeneratedTests(SimpleTestCase):
    """Part 1: the generated corpus."""
    maxDiff = None

    def test_the_committed_corpus_is_the_generated_one(self):
        self.assertEqual(committed()['cases'], json.loads(json.dumps(corpus())))

    def test_every_code_and_requirement_has_a_t_case_and_u_or_f_where_the_design_gives_one(self):
        cases = committed()['cases']
        self.assertEqual({case['code'] for case in cases}, {str(code) for code in TABLE.CODES})
        self.assertEqual(len(TABLE.CODES), 163)
        by = {}
        for case in cases:
            by.setdefault((case['code'], case['requirement']), {})[case['state']] = case['expect']
        for (code, requirement), states in by.items():
            with self.subTest(code=code, requirement=requirement):
                self.assertIsNotNone(states['T'])
                if code_row(code).template is not TABLE.Template.RECOGNISED and states['U'] is None and \
                        states['F'] is None:
                    # neither form: only where the design gives neither, each re-derived here from the code's row
                    row = code_row(code)
                    kind = row.groups[0][0]
                    if requirement == 'SUP.7':
                        self.assertTrue(kind is K.EXAMINATION or row.family not in ENDOSCOPIC, (code, requirement))
                    elif requirement == 'bundling':
                        self.assertTrue(kind is K.BLEEDING_CONTROL or kind not in BUNDLED_PARTS | (
                            ERCP_BUNDLED_PARTS if row.family is S.ERCP else frozenset()), (code, requirement))
                    elif requirement == 'combination':
                        self.assertTrue(not base_code(code) and rival(code) is None, (code, requirement))
                    else:
                        self.fail(f'{code} {requirement}: neither a U nor an F case')
        for case in cases:
            if case['expect'] is None:
                with self.subTest(code=case['code'], requirement=case['requirement'], state=case['state']):
                    self.assertNotEqual(case['why'], 'not generated')

    def test_the_engine_gives_every_generated_expectation(self):
        for case in committed()['cases']:
            if case['expect'] is None:
                continue
            requirement = next(r for r in RQ.requirements_of(case['code']) if r.value == case['requirement'])
            built, _ = perturb(case['code'], requirement, case['state'])
            found = {item.code: FC.outcome(item) for item in run(built).codes}[case['code']]
            want = case['expect']
            with self.subTest(code=case['code'], requirement=case['requirement'], state=case['state']):
                self.assertEqual(found['status'], want['status'], want['why'])
                if want['item'] is not None:
                    self.assertEqual(found['item'], want['item'], want['why'])
                if want['item_kind'] is not None:
                    self.assertEqual(found['item_kind'], want['item_kind'], want['why'])

    def test_competition_never_crosses_a_site_class(self) -> None:
        """DECISIONS D240 in the generated corpus: 43245's combination U is no longer the competing reading (43213, an
        esophageal code, claims no dilation of the pylorus), and every esophageal dilation code keeps a rival of its own
        class."""
        cases = {(case['code'], case['requirement'], case['state']): case for case in committed()['cases']}
        entry = cases[('43245', 'combination', 'U')]
        self.assertIsNone(entry['expect'])
        self.assertIn('D240', entry['why'])
        self.assertIsNone(rival('43245'))
        self.assertEqual(rival('43245', site_fit=False), '43213')  # the rival the site fit removes
        for code in sorted(str(number) for number, site in CAT.DILATION_SITES.items()
                           if site is CAT.SiteClass.ESOPHAGEAL):
            with self.subTest(code=code):
                other = rival(code)
                self.assertIsNotNone(other)
                assert other is not None
                self.assertIs(code_row(other).site, CAT.SiteClass.ESOPHAGEAL)
                self.assertEqual(cases[(code, 'combination', 'U')]['expect']['item'], 'competing_codes')


class NamedTests(SimpleTestCase):
    """The rulings' named cases as gate-6 FactSets (9.5): D240's two dilations at two sites."""
    maxDiff = None

    def test_the_committed_named_cases_are_the_generated_ones(self) -> None:
        self.assertEqual(committed()['named'], json.loads(json.dumps(named())))
        self.assertEqual({record['case'] for record in committed()['named']}, {'D240'})

    def test_the_engine_gives_every_named_expectation(self) -> None:
        """D240: "The distal esophageal stricture was dilated with a balloon. The duodenal bulb stricture was dilated
        with a balloon." - 43249 READY on the esophageal act and 43245 READY on the duodenal one, proposed together and
        each alone (evaluate's half, step 4a's engine/evaluate.py; combination's half, step 4d's
        engine/combination.py)."""
        for record in committed()['named']:
            found = {item.code: FC.outcome(item) for item in run_named(record).codes}
            for code, want in record['expect'].items():
                with self.subTest(case=record['case'], shape=record['shape'], code=code):
                    self.assertEqual((found[code]['status'], found[code]['item']), (want['status'], want['item']),
                                     want['why'])
                    self.assertEqual(found[code]['acts'], want['acts'], want['why'])
