"""S4's failure classes and borderline filings, and the owner's checklist examples, as fixtures (docs/gemini-migration/
FINAL-V2.md 9.5 and Appendix C; step 6c of 8.1). TEXT-ONLY and SYNTHETIC: every document and constructed answer is in
tests/fixtures/interpretation_v2/ (written by its build.py, whose docstring gives a case's shape); nothing is sent
anywhere and no acceptance document is read (only the acceptance owner's DEV-EXCLUSION hashes).

Each variant runs the whole offline pipeline - extract_read, contract/checks, contract/claims (the request pass 2 would
get), appraise_read, settle, store.row_v2 and load_v2, store.textfree_v2, engine/facts.effective and engine/assess - so
these are settle AND engine tests: they prove what CPT Studio does given a filing and an appraisal, and nothing about
Gemini's reading; they are never acceptance evidence (9.5).

What is proved here:
- (i) correct: each case's documented outcome (READY, HELD on the named fact with one item, or EXCLUDED);
- (ii) caught: the misfiling, caught by pass 2 (or by a deterministic check), holds the codes that depend on it, each
  with exactly one item on the expected fact, and no code is a wrong READY or a wrong exclusion against (i);
- the misfiled facts settle not established under (ii) and established under (iii), so (iii) really is a shared
  misreading that reached the engine; a case whose (iii) has a filing of its own (an omission pass 2 has no claim to
  contradict, kept only as (iii): DECISIONS D241, GI Note #8's tattoo with no place and no lesion) instead shows the
  facts it leaves out established under (i) and absent under (iii);
- (iii) shared misreading: its outcome is RECORDED in tests/fixtures/interpretation_v2/RESIDUALS.json (classified as a
  wrong READY, a wrong exclusion, a hold, or the documented outcome) and NEVER counted as a pass: the residual tests
  assert only that every (iii) is recorded, as recorded, and marked counted_as_pass false;
- a NAMED residual (build.Case.named) stands beside a variant's documented outcome where a ruling keeps it as built and
  names it (D244: Q-N8b) or an open question leaves it: asserted as built, so a change is seen (beside a documented
  outcome with no service question, the named residuals are the only ones), recorded in RESIDUALS.json, and never
  counted as a pass;
- every fixture document is synthetic (its banner, or a development document used verbatim, byte-equal to its source)
  and none is on the exclusion list (as written and whitespace-stripped), every unlisted entry lies on a unit of its
  document, and the committed fixture files equal what the builder writes;
- KnownDefectTests: a case may pin a code whose design expectation fails in ANOTHER step's file (a REQUEST) or rests
  on an open design question (a QUESTION, built fail-closed): the other tests hold it to its pin, so a repair is seen,
  and KnownDefectTests hold it to the design's expectation - those tests fail until the request or question is
  settled, so 9.5 is never reported green over a known false READY (the refutation round 1's P5).
The refutation's cases are tests/v2/test_refutation_cases.py, gate 6 tests/v2/test_gate6.py; both use this module's
pipeline.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation import store
from studio.interpretation.contract import appraise_prompt, appraise_read, checks, extract_read, jsonschema, segment
from studio.interpretation.contract import settle
from studio.interpretation.contract import types as contract_types
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as engine_facts
from studio.interpretation.engine.types import IdFamily, Outcome, Result
from studio.participants.peer import code_shaped
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation import checks as validation_checks
from studio.validation.questions import MemberAnswerInput

APP = Path(__file__).resolve().parents[2]
FIXTURES = APP / 'tests' / 'fixtures' / 'interpretation_v2'
RESIDUALS = FIXTURES / 'RESIDUALS.json'
HEALTH_PIN = jsonschema.sha256_of(settle.health_document())  # HEALTH_THRESHOLDS_SHA256 stays '' until step 8 (O3)
USAGE = settle.Usages(settle.usage_of({'promptTokenCount': 1800, 'candidatesTokenCount': 900,
                                       'thoughtsTokenCount': 2100, 'totalTokenCount': 4800}),
                      settle.usage_of({'promptTokenCount': 2600, 'candidatesTokenCount': 480}))
ESTABLISHED = (Result.SUPPORTED, Result.NEGATED)
OUTCOMES = {'ready': Outcome.READY, 'needs_clarification': Outcome.NEEDS_CLARIFICATION, 'excluded': Outcome.EXCLUDED}


# --- the caller's inputs (step 5b hands the same to assess) ----------------------------------------------------------


class Integrity:
    """R1 as the caller hands it in: the allowlisted validation checks and the participants' code rule."""
    word_runs = None

    def code_scope(self, code):
        return validation_checks.code_scope(code)

    def exact_evidence(self, spans, text, pages):
        return validation_checks.exact_evidence(spans, text, pages)

    def code_shaped(self, value):
        return code_shaped(value)


class Lookup:
    """No reference row for any code (R9 is records only)."""

    def lookup(self, code, service_date):
        return SimpleNamespace(pfs=None, mue=None)


# --- loading the fixtures --------------------------------------------------------------------------------------------


@lru_cache(maxsize=None)
def manifest() -> dict:
    return json.loads((FIXTURES / 'MANIFEST.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=None)
def case(case_id: str) -> dict:
    return json.loads((FIXTURES / 'answers' / f'{case_id}.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=None)
def document(case_id: str) -> str:
    return (FIXTURES / 'documents' / f'{case_id}.txt').read_text(encoding='utf-8')


def manifest_entry(case_id: str) -> dict:
    """A case's MANIFEST.json entry."""
    return next(entry for entry in manifest()['cases'] if entry['case'] == case_id)


def cases_of(*kinds: str) -> list:
    return [entry['case'] for entry in manifest()['cases'] if entry['kind'] in kinds]


# --- pass 2's answer from its rule (build.py: a rule over the claim set's facts) -------------------------------------


def roles_of(claim_set) -> dict:
    """What each claim of the request is: claim, control, pair_control, completeness, completeness_control."""
    roles: dict = {}
    for item in claim_set.appraised:
        roles[item.claim] = 'claim'
    for complete in claim_set.completeness:
        roles.setdefault(complete.claim, 'completeness')
    for item in claim_set.appraised:
        if item.control is not None:
            roles.setdefault(item.control, 'control')
    for complete in claim_set.completeness:
        roles.setdefault(complete.control, 'completeness_control')
    for pair in claim_set.pair_controls:
        roles.setdefault(pair.claim, 'pair_control')
    for claim in claim_set.claims:
        roles.setdefault(claim.id, 'control')
    return roles


def fact_name(key) -> str:
    return f'{key.attribute.value}@{key.object}/{key.index}'


def materialize(rule: dict, claim_set) -> dict:
    """Pass 2's answer for ``claim_set`` from ``rule``: each claim's verdict by the facts it appraises and its role (the
    rule's verdicts first), else the faithful reading - a real claim supported, attached, its first unit as evidence;
    a control, pair control or completeness control contradicted. Unlisted entries name their session by object id;
    the card id is the request's."""
    if rule['default'] != 'faithful':
        raise ValueError(rule['default'])
    roles = roles_of(claim_set)
    named: dict = {}
    for item in claim_set.appraised:
        named.setdefault(item.claim, []).append((fact_name(item.key), 'claim'))
        if item.control is not None:
            named.setdefault(item.control, []).append((fact_name(item.key), 'control'))
    for complete in claim_set.completeness:
        named.setdefault(complete.claim, []).append((f'completeness@{complete.session}', 'claim'))
        named.setdefault(complete.control, []).append((f'completeness@{complete.session}', 'control'))
    for pair in claim_set.pair_controls:
        named.setdefault(pair.claim, []).append(
            (f'pair@{pair.subject[1]}:{pair.other[1]}:{pair.value}', 'pair_control'))
    overrides = {(entry['fact'], entry['role']): entry for entry in rule['verdicts']}
    verdicts = []
    for claim in claim_set.claims:
        chosen = next((overrides[key] for key in named.get(claim.id, ()) if key in overrides), None)
        if chosen is not None:
            if chosen['verdict'] is None:
                continue
            verdicts.append({'claim': claim.id, 'verdict': chosen['verdict'], 'attached': chosen.get('attached', 'yes'),
                             'qualifiers': list(chosen.get('qualifiers', ())),
                             'evidence': list(claim.units[:1])})
            continue
        real = roles[claim.id] in ('claim', 'completeness')
        verdicts.append({'claim': claim.id, 'verdict': 'supports' if real else 'contradicts', 'attached': 'yes',
                         'qualifiers': [], 'evidence': list(claim.units[:1])})
    cards = {item: card for card, item in claim_set.objects.items()}
    unlisted = []
    for entry in rule['unlisted']:
        session = entry.get('session', '')
        card = next((card for (family, oid), card in cards.items() if oid == session), '') if session else ''
        unlisted.append({'units': list(entry['units']), 'what': entry['what'], 'kind': entry.get('kind', ''),
                         'session': card})
    return {'verdicts': verdicts, 'unlisted': unlisted}


# --- the pipeline ----------------------------------------------------------------------------------------------------


class Run(SimpleNamespace):
    """One variant's run: the read answer, the checks, the request's claim set, settle's output, the FactSet and the
    assessment."""


def proposals_of(data: dict, text: str) -> NormalizedResponse:
    codes = tuple(ProviderCode('selected', 'CPT', item['code'], '',
                               (EvidenceSpan(0, item['start'], item['end'], text[item['start']:item['end']], True),))
                  for item in data['proposals'])
    return NormalizedResponse('corti', 'synthetic@1', codes=codes)


def pipeline(text: str, answer1: dict, rule: dict, data: dict) -> Run:
    """The offline pipeline over one constructed pass-1 answer and one pass-2 rule (module docstring)."""
    units = segment.units(text)
    read = extract_read.read(json.dumps(answer1), len(units))
    if isinstance(read, extract_read.Refusal):
        raise AssertionError(f'pass 1 refused: {read}')
    # the recorded labels throughout - pass 1 read at gemini-events@2, the @1 request, the row at the @2 pair - so the
    # checks are made for gemini-inventory@2 (DECISIONS D294 F2: a recorded label keeps the rule it was recorded with)
    checked = checks.check(text, (), read, inventory_version=interpretation.INVENTORY_VERSION_V2)
    request = appraise_prompt.build_request(text, (), 'txt', read, findings=checked.findings)
    answer2 = materialize(rule, request.claim_set)
    appraisal = appraise_read.read(json.dumps(answer2), request.claim_set, len(units))
    if isinstance(appraisal, extract_read.Refusal):
        raise AssertionError(f'pass 2 refused: {appraisal}')
    with mock.patch.object(interpretation, 'HEALTH_THRESHOLDS_SHA256', HEALTH_PIN):
        out = settle.settle(read, checked, request.claim_set, request.indistinct, appraisal, USAGE)
    if isinstance(out, settle.Unhealthy):
        raise AssertionError(f'settle refused the appraisal: {out.health}')
    text_sha256 = hashlib.sha256(text.encode('utf-8')).hexdigest()
    fields = store.row_v2(encounter_id=uuid.UUID(int=1), revision_id=uuid.UUID(int=2), provider_run_id=uuid.UUID(int=3),
                          appraisal_run_id=uuid.UUID(int=4), revision_text=text, text_sha256=text_sha256,
                          request_sha256='2' * 64, response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                          appraisal_response_sha256='5' * 64, events=out.events, verification=out.verification)
    loaded = store.load_v2(fields, text_sha256=text_sha256, response_sha256='3' * 64,
                           appraisal_response_sha256='5' * 64)
    dos = datetime.date.fromisoformat(data['date_of_service']) if data['date_of_service'] else None
    R = engine_facts.effective(store.textfree_v2(loaded), dos)
    member = AS.MemberContext(setting=data['member'][0], patient_status=data['member'][1]) if data['member'] else \
        AS.MemberContext(setting='', patient_status='')
    answers = tuple(MemberAnswerInput(**answer) for answer in data.get('answers', ()))
    assessment = AS.assess_facts(R, date_of_service=dos, text=text, pages=(), integrity=Integrity(),
                                 provider_status='succeeded', proposals=proposals_of(data, text), reference=Lookup(),
                                 member=member, label=lambda session: str(session.id), answers=answers)
    return Run(read=read, checked=checked, claim_set=request.claim_set, settled=out, R=R, assessment=assessment)


def filing_of(data: dict[str, Any], variant: str) -> str:
    """The pass-1 filing a variant runs: (i) the right filing, (ii) the misfiling, (iii) the misfiling - or the case's
    own shared filing when its shared misreading is not (ii)'s misfiling (build.Case.shared; DECISIONS D241)."""
    if variant == 'i':
        return 'correct'
    if variant == 'iii' and 'shared' in data['pass1']:
        return 'shared'
    return 'misfiled'


@lru_cache(maxsize=None)
def run(case_id: str, variant: str) -> Run:
    data = case(case_id)
    return pipeline(document(case_id), data['pass1'][filing_of(data, variant)], data['pass2'][variant], data)


def outcome(found) -> dict:
    """A code's outcome as the fixtures write it: status, item fact and kind, the item's subject, the supporting acts,
    every held fact's key, and the considerations (52/53, 25, 59/XS, PC/TC; a READY code's are part of its outcome,
    4.4)."""
    item = found.item
    supporting = found.evaluation.supporting if found.evaluation is not None else ()
    return {'status': found.status.value, 'item': item.held.fact if item is not None else None,
            'item_kind': item.kind.value if item is not None else None,
            'subject': str(item.held.subject) if item is not None and item.held.subject is not None else None,
            'acts': [str(event) for event in supporting], 'held': held_names(found.held_facts),
            'considerations': sorted(consideration.value for consideration in found.considerations)}


def held_names(held_facts) -> list:
    """Every held fact by its key, by key@subject, and by key@subject x its number of witnesses (each statement a
    hold reads is its own witness, 4.4 [R:HO-8])."""
    counts: dict = {}
    for held in held_facts:
        if held.subject is not None:
            counts[f'{held.fact}@{held.subject}'] = counts.get(f'{held.fact}@{held.subject}', 0) + 1
    names = {held.fact for held in held_facts} | set(counts)
    names |= {f'{name}x{n}' for name, count in counts.items() for n in range(2, count + 1)}
    return sorted(names)


def outcomes(assessment) -> dict:
    return {found.code: outcome(found) for found in assessment.codes}


def caught_result(run_: Run, name: str):
    """The settled result of a misfiled fact the fixture names: 'completeness@X1' is the session's completeness claim
    (the FactSet's), anything else a settled fact (``settled_fact``)."""
    if name.startswith('completeness@'):
        found = [result for sid, result in run_.R.completeness.items() if str(sid) == name.split('@')[1]]
        return found[0] if found else None
    fact = settled_fact(run_.settled.events, name)
    return fact.result if fact is not None else None


def settled_fact(events: dict, name: str):
    """The settled fact a fixture names 'attribute@object/index' (an event's, a session's, a lesion's or an anatomy
    entry's; a nested attribute by its dotted path), or None when the object or attribute is not there."""
    attribute, rest = name.split('@')
    oid, index = rest.split('/')
    families = {'E': 'events', 'X': 'sessions', 'L': 'lesions', 'Y': 'anatomy', 'N': 'sections'}
    family = families.get(oid[:1])
    item = next((record for record in events.get(family, ()) if record['id'] == oid), None) if family else None
    if item is None:
        return None
    node = item
    for part in attribute.split('.'):
        if isinstance(node, (list, tuple)):  # a list of records (restatements): the index names the record
            node = node[int(index)] if int(index) < len(node) else {}
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if isinstance(node, (list, tuple)):
        return node[int(index)] if int(index) < len(node) else None
    return node


def omitted(events: dict[str, Any], name: str) -> bool:
    """Whether the settled inventory leaves out the fact a fixture names 'attribute@object/index' while its object is
    there: an empty list (no member at that index) or a silent slot (settle's unknown, reason silent, no claim)."""
    oid = name.split('@')[1].split('/')[0]
    family = {'E': 'events', 'X': 'sessions', 'L': 'lesions', 'Y': 'anatomy', 'N': 'sections'}.get(oid[:1])
    if family is None or not any(record['id'] == oid for record in events.get(family, ())):
        return False  # the object itself is not there: nothing was left out of it
    fact = settled_fact(events, name)
    return fact is None or (fact.claim.state is None and fact.result is Result.UNKNOWN
                            and contract_types.Reason.SILENT in fact.reasons)


def classify(found: dict, documented: dict, acts: list | None = None, considerations: list | None = None) -> str:
    """A (iii) outcome against the documented (i) one: wrong_ready, ready_on_the_wrong_act, wrong_exclusion,
    consideration_dropped (a READY whose documented considerations are not all there - S4's own failure, "dropped
    consideration (52/53)"), consideration_added, held, or as_documented. ``considerations``: (i)'s documented
    considerations of the code, when the case writes them (None: not compared)."""
    if found['status'] == 'ready' and documented['status'] != 'ready':
        return 'wrong_ready'
    if found['status'] == 'ready' and acts is not None and found['acts'] != acts:
        return 'ready_on_the_wrong_act'
    if found['status'] == 'excluded' and documented['status'] != 'excluded':
        return 'wrong_exclusion'
    if found['status'] == documented['status'] and found['item'] == documented['item']:
        if considerations is not None and found['status'] == 'ready':
            got, want = set(found.get('considerations', ())), set(considerations)
            if want - got:
                return 'consideration_dropped'
            if got - want:
                return 'consideration_added'
        return 'as_documented'
    return 'held' if found['status'] == 'needs_clarification' else 'other'


def residual_record(case_id: str) -> dict:
    """What RESIDUALS.json records for a case's (iii): each code's outcome and its class against (i)'s documented
    one (status, item, the supporting acts where (i) names them, and the considerations where (i) names them), never a
    pass."""
    data = case(case_id)
    found = outcomes(run(case_id, 'iii').assessment)
    documented = data['expect']['i']
    acts = data.get('acts', {}).get('i', {})
    documented_considerations = data.get('considerations', {}).get('i', {})
    return {'codes': {code: {'status': found[code]['status'], 'item': found[code]['item'],
                             'item_kind': found[code]['item_kind'], 'acts': found[code]['acts'],
                             'considerations': found[code]['considerations'],
                             'against_documented': classify(found[code], documented[code], acts.get(code),
                                                            documented_considerations.get(code))}
                      for code in sorted(documented)},
            'counted_as_pass': False}


def another_act(held, item) -> bool:
    """Whether a held fact is about an act (an event) other than the one ``item`` is about."""
    return held.subject is not None and held.subject.family is IdFamily.EVENT and held.subject != item.subject


# --- the assertions every case shares --------------------------------------------------------------------------------


class Fixture(SimpleTestCase):
    """Runs a case's variants and asserts its expectations (module docstring)."""
    maxDiff = None

    def check_expected(self, case_id: str, variant: str, design: bool = False) -> dict:
        """The variant's expectations. A code the case pins as a known defect (``known``: a defect or open design
        question of another step's file, the step's REQUEST or QUESTION) is held here to its PIN, so a repair is seen;
        with ``design`` (KnownDefectTests) it is held to the design's expectation instead, which fails until the
        request is repaired - 9.5 is not green while it does."""
        data = case(case_id)
        found = outcomes(run(case_id, variant).assessment)
        known = {} if design else data.get('known', {}).get(variant, {})
        pinned_considerations = set()
        for code, want in data['expect'][variant].items():
            with self.subTest(case=case_id, variant=variant, code=code):
                self.assertIn(code, found, f'{case_id} ({variant}): {code} not assessed')
                got = found[code]
                if code in known:
                    # the design's expectation stays in 'expect' (KnownDefectTests asserts it); this pins what the
                    # engine gives today, so a repair is seen - never counted a pass
                    self.assertEqual((got['status'], got['item']), (known[code]['status'], known[code]['item']),
                                     f'{case_id} ({variant}) {code}: known defect {known[code]["request"]} changed')
                    if 'considerations' in known[code]:
                        pinned_considerations.add(code)
                        self.assertEqual(got['considerations'], sorted(known[code]['considerations']),
                                         f'{case_id} ({variant}) {code}: known defect {known[code]["request"]} changed')
                    continue
                self.assertEqual(got['status'], want['status'], f'{case_id} ({variant}) {code}: {want["why"]}')
                if want['item'] is not None:
                    self.assertEqual(got['item'], want['item'], f'{case_id} ({variant}) {code}: {want["why"]}')
                if want['item_kind'] is not None:
                    self.assertEqual(got['item_kind'], want['item_kind'], f'{case_id} ({variant}) {code}')
        for code, acts in data.get('acts', {}).get(variant, {}).items():
            with self.subTest(case=case_id, variant=variant, code=code, check='supporting acts'):
                self.assertEqual(found[code]['acts'], acts)
        for code, subject in data.get('subjects', {}).get(variant, {}).items():
            with self.subTest(case=case_id, variant=variant, code=code, check='item subject'):
                self.assertEqual(found[code]['subject'], subject)
        for code, facts in data.get('held', {}).get(variant, {}).items():
            with self.subTest(case=case_id, variant=variant, code=code, check='held facts'):
                self.assertTrue(set(facts) <= set(found[code]['held']), (facts, found[code]['held']))
        assessment = run(case_id, variant).assessment
        by_code = {found.code: found for found in assessment.codes}
        if variant in data.get('listed', {}):
            items = [[item['reason'], item['events'], item['second_review']]
                     for item in assessment.completeness['unresolved_items']]
            for wanted in data['listed'][variant]:
                with self.subTest(case=case_id, variant=variant, check='listed', item=wanted):
                    self.assertIn(wanted, items)
        for code, values in data.get('considerations', {}).get(variant, {}).items():
            if code in pinned_considerations:
                continue
            with self.subTest(case=case_id, variant=variant, code=code, check='considerations'):
                self.assertEqual(sorted(c.value for c in by_code[code].considerations), sorted(values))
        named = data.get('named', {}).get(variant, [])
        if variant in data.get('services', {}) or named:
            # the documented service questions (none unless the case writes them) and, beside them, only the named
            # residuals (build.Case.named): asserted as built, so a change is seen; never counted as a pass
            got_services = sorted([found.item.item.fact, str(found.item.item.subject)]
                                  for found in assessment.service_questions)
            wanted = [list(item) for item in data.get('services', {}).get(variant, [])]
            wanted += [[entry['fact'], entry['subject']] for entry in named if entry['where'] == 'service']
            with self.subTest(case=case_id, variant=variant, check='service questions'):
                self.assertEqual(got_services, sorted(wanted))
        for entry in named:
            if entry['where'] != 'service':
                with self.subTest(case=case_id, variant=variant, residual=entry['id'], check='named residual'):
                    self.assertIn(f'{entry["fact"]}@{entry["subject"]}', found[entry['where']]['held'])
        return found

    def check_one_item(self, case_id: str, variant: str) -> None:
        """Every held code carries exactly one item (4.8, D182): one of its held facts, and the highest-ranked one on
        its binding - its rank is the smallest among the held facts about the item's own act and those about no act (a
        session, a lesion, the code itself). A held fact about ANOTHER act that ranks before the item is the witness of
        a positive candidate the binding did not choose (4.8 binding (1): a kept span selects another candidate
        [R:HO-8]), so the case must name the item's act for that code (``subjects``): the binding is asserted, never
        left to chance. A READY code has no item and no held fact."""
        named = case(case_id).get('subjects', {}).get(variant, {})
        for found in run(case_id, variant).assessment.codes:
            with self.subTest(case=case_id, variant=variant, code=found.code):
                if found.status is Outcome.NEEDS_CLARIFICATION and found.held_facts:
                    self.assertIsNotNone(found.item)
                    item = found.item.held
                    self.assertIn(item, found.held_facts)
                    if item.rank is not None:  # service_date, the encounter-scope fact, has no rank (4.8)
                        ranked = [held for held in found.held_facts if held.rank is not None]
                        others = [held for held in ranked if another_act(held, item)]
                        own = [held.rank for held in ranked if not another_act(held, item)]
                        self.assertEqual(item.rank, min(own), f'{case_id} ({variant}) {found.code}: the item '
                                                              f'{item.fact} (rank {item.rank}) is not the first of its '
                                                              f'binding ({sorted(own)})')
                        before = sorted(f'{held.fact}@{held.subject}' for held in others if held.rank < item.rank)
                        if before:
                            self.assertIn(found.code, named, f'{case_id} ({variant}) {found.code}: {before} rank '
                                                             f'before the item on another act; the case must name '
                                                             f'the bound act (subjects)')
                if found.status is Outcome.READY:
                    self.assertIsNone(found.item)
                    self.assertEqual(found.held_facts, ())

    def check_caught(self, case_id: str, design: bool = False) -> None:
        """(ii): the misfiled facts settle not established (pass 2 or a check caught them); (iii): established - the
        shared misreading reached the engine. No code of (ii) is a wrong READY or a wrong exclusion against (i): a
        code pinned as a known defect is skipped here and asserted by KnownDefectTests (``design``), which fails while
        it is one."""
        data = case(case_id)
        documented = data['expect']['i']
        checked = set(data.get('checked', ()))
        shared = 'shared' in data['pass1']
        if shared and 'iii' in data['variants']:
            # (iii)'s own filing (DECISIONS D241): the shared misreading is an omission, so the facts it leaves out are
            # established under (i) and absent under (iii) - the omission reached the engine; (ii)'s caught facts
            # describe (ii)'s misfiling alone
            self.assertTrue(data['shared_omits'], f'{case_id}: a shared filing names no fact it leaves out')
            for name in data['shared_omits']:
                with self.subTest(case=case_id, variant='i', fact=name, check='shared omission'):
                    self.assertIn(caught_result(run(case_id, 'i'), name), ESTABLISHED)
                with self.subTest(case=case_id, variant='iii', fact=name, check='shared omission'):
                    self.assertTrue(omitted(run(case_id, 'iii').settled.events, name),
                                    f'{case_id}: {name} is not left out under (iii)')
        for name in data['caught']:
            if name in checked:
                # a deterministic check demotes the misfiled fact whatever pass 2 says (3.1): not established in (ii)
                # nor in (iii) - the shared misreading never reaches the engine
                for variant in ('ii', 'iii'):
                    if variant in data['variants'] and not (variant == 'iii' and shared):
                        result = caught_result(run(case_id, variant), name)
                        with self.subTest(case=case_id, variant=variant, fact=name, check='deterministic'):
                            self.assertIsNotNone(result)
                            self.assertNotIn(result, ESTABLISHED)
                continue
            if 'ii' in data['variants']:
                result = caught_result(run(case_id, 'ii'), name)
                with self.subTest(case=case_id, variant='ii', fact=name):
                    self.assertIsNotNone(result, f'{name} is not in the settled inventory')
                    self.assertNotIn(result, ESTABLISHED, f'{case_id}: {name} established under (ii)')
            if 'iii' in data['variants'] and not shared:
                result = caught_result(run(case_id, 'iii'), name)
                with self.subTest(case=case_id, variant='iii', fact=name):
                    self.assertIsNotNone(result, f'{name} is not in the settled inventory')
                    self.assertIn(result, ESTABLISHED, f'{case_id}: {name} not established under (iii)')
        if 'ii' in data['variants']:
            found = outcomes(run(case_id, 'ii').assessment)
            known = {} if design else data.get('known', {}).get('ii', {})
            for code, want in documented.items():
                if code in known:
                    continue
                with self.subTest(case=case_id, variant='ii', code=code, check='no wrong READY or exclusion'):
                    self.assertFalse(found[code]['status'] == 'ready' and want['status'] != 'ready',
                                     f'{case_id} (ii): {code} is a wrong READY')
                    self.assertFalse(found[code]['status'] == 'excluded' and want['status'] != 'excluded',
                                     f'{case_id} (ii): {code} is a wrong exclusion')

    def check_case(self, case_id: str) -> None:
        data = case(case_id)
        for variant in ('i', 'ii'):
            if variant in data['variants']:
                self.check_expected(case_id, variant)
                self.check_one_item(case_id, variant)
        self.check_caught(case_id)


S4_CLASSES = tuple([f'T{n}' for n in range(1, 10)] + [f'E{n}' for n in range(1, 6)] + [f'G{n}' for n in range(1, 6)]
                   + [f'S{n}' for n in range(1, 5)] + [f'N{n}' for n in range(1, 4)] + [f'A{n}' for n in range(1, 4)]
                   + [f'C{n}' for n in range(1, 5)] + [f'Y{n}' for n in range(1, 8)] + ['X1']
                   + [f'D{n}' for n in range(1, 4)] + [f'Q{n}' for n in range(1, 8)] + ['O1'])  # S4's 52 (failures.json)
S4_BORDERLINE = tuple(f'BF{n}' for n in range(1, 22))  # S4's 21 borderline filings
CHECKLIST = ('original v1', 'original v2', 'original v3', 'original v4', 'original v5', 'original v6', 'original note8',
             'unsupported historical extent', 'biopsy-site conflation', 'the scar', 'historical and current acts',
             'different lesions at one site', 'technique-specific denials', 'different performers',
             'future purpose (C-13)', 'guidewire-versus-scope extent', 'genuine contradictions',
             '"No polyp was removed today."')


def refs_of(*kinds: str) -> set:
    return {ref for entry in manifest()['cases'] if entry['kind'] in kinds for ref in entry['refs']}


def residual_cases(*kinds: str) -> list:
    return [entry['case'] for entry in manifest()['cases'] if entry['kind'] in kinds and 'iii' in entry['variants']]


@lru_cache(maxsize=None)
def residuals() -> dict:
    return json.loads(RESIDUALS.read_text(encoding='utf-8'))


def named_records() -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Every named residual the cases declare (build.Case.named), case -> variant -> entries, each marked
    counted_as_pass false: what RESIDUALS.json records under 'named'."""
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for entry in manifest()['cases']:
        for variant, entries in case(entry['case']).get('named', {}).items():
            out.setdefault(entry['case'], {})[variant] = [dict(item, counted_as_pass=False) for item in entries]
    return out


def write_residuals() -> None:
    """Records every (iii) outcome in RESIDUALS.json (run by hand after a change of the fixtures or of the engine; the
    residual tests then assert the record is current). A residual is the engine's outcome on a shared misreading: it is
    measured, never expected and never counted as a pass (9.5). The named residuals (build.Case.named) are recorded
    beside them, never counted as a pass either."""
    cases = {case_id: residual_record(case_id) for case_id in residual_cases('class', 'borderline', 'checklist',
                                                                              'refutation')}
    counts: dict = {}
    for record in cases.values():
        for found in record['codes'].values():
            counts[found['against_documented']] = counts.get(found['against_documented'], 0) + 1
    RESIDUALS.write_text(json.dumps({'about': 'FINAL-V2 9.5 variant (iii): pass 2 shares pass 1\'s misreading. Each '
                                              'code\'s outcome is RECORDED as a residual, never counted as a pass; its '
                                              'rate is what the acceptance set measures. A shared filing of its own '
                                              '(DECISIONS D241) is a residual too. named: the residuals a ruling keeps '
                                              'as built and names beside a documented outcome (D244), or an open '
                                              'question leaves there; asserted as built, never counted as a pass.',
                                     'counts_by_class': dict(sorted(counts.items())), 'cases': cases,
                                     'named': named_records()},
                                    indent=1, sort_keys=True) + '\n', encoding='utf-8')


class FailureClassTests(Fixture):
    """S4's 52 classes and 21 borderline filings: (i) and (ii) as expected (9.5's table)."""

    def test_every_class_and_borderline_filing_has_its_three_variants(self):
        refs = refs_of('class', 'borderline')
        self.assertEqual(sorted(set(S4_CLASSES) - refs), [])
        self.assertEqual(sorted(set(S4_BORDERLINE) - refs), [])
        self.assertEqual(len(S4_CLASSES), 52)
        for name in S4_CLASSES + S4_BORDERLINE:
            with self.subTest(ref=name):
                variants = {variant for entry in manifest()['cases'] if name in entry['refs']
                            and entry['kind'] in ('class', 'borderline') for variant in entry['variants']}
                if name == 'N3':  # (ii) has no claim to contradict: the step's NOTES, question Q-N3
                    self.assertEqual(variants, {'i', 'iii'})
                else:
                    self.assertEqual(variants, {'i', 'ii', 'iii'})

    def test_the_cases(self):
        for case_id in cases_of('class', 'borderline'):
            self.check_case(case_id)


class ChecklistTests(Fixture):
    """The owner's checklist examples, each as (i) and (ii) (9.5)."""

    def test_every_checklist_example_has_its_fixture(self):
        refs = refs_of('checklist', 'refutation', 'class')
        self.assertEqual(sorted(set(CHECKLIST) - refs), [])

    def test_the_cases(self):
        for case_id in cases_of('checklist'):
            self.check_case(case_id)

    def test_the_egd_denied_today_is_filed_under_an_egd_session_of_its_own(self) -> None:
        """DECISIONS D244, Q-N8 option (b): GI Note #8's "no esophagogastroduodenoscopy or other upper endoscopic
        procedure was performed on November 8, 2026", a denied procedure of another kind than the colonoscopy it is told
        in, is filed as step 2a's pass-1 instruction says - the examination, negated, of an EGD session of its own,
        never with its session empty - in every filing of CK-note8 and of RF-CO2d (C2MEM-031), and it settles so: its
        session established, its status negated."""
        for case_id in ('CK-note8', 'RF-CO2d'):
            data, text = case(case_id), document(case_id)
            units = {unit.id: unit for unit in segment.units(text)}
            for filing, answer in data['pass1'].items():
                with self.subTest(case=case_id, filing=filing):
                    denial = next(event for event in answer['events'] if event['id'] == 'E32')
                    anchor = units[denial['anchor']['units'][0]]
                    self.assertIn('esophagogastroduodenoscopy', text[anchor.start:anchor.end])
                    self.assertEqual((denial['kind']['value'], denial['status']['value'], denial['status']['state']),
                                     ('examination', 'performed', 'negated'))
                    self.assertEqual([fact['value'] for fact in denial['session']], ['X4'])
                    session = next(item for item in answer['sessions'] if item['id'] == 'X4')
                    self.assertEqual(session['kind']['value'], 'egd')
                    self.assertEqual([fact['value'] for fact in session['examination']], ['E32'])
            for variant in data['variants']:
                with self.subTest(case=case_id, variant=variant, check='settled'):
                    events = run(case_id, variant).settled.events
                    self.assertEqual(settled_fact(events, 'session@E32/0').result, Result.SUPPORTED)
                    self.assertEqual(settled_fact(events, 'status@E32/0').result, Result.NEGATED)


def known_defects() -> dict:
    """Every pinned known defect, by its request or question id: [(case, variant, code), ...] in manifest order."""
    found: dict = {}
    for entry in manifest()['cases']:
        for variant, codes in case(entry['case']).get('known', {}).items():
            for code, pinned in codes.items():
                found.setdefault(pinned['request'], []).append((entry['case'], variant, code))
    return found


# The step's REQUESTS (a defect of another step's file) and QUESTIONS (a reading the design leaves open, the
# fail-closed one built here), each pinned on its cases; NOTES.md gives the input, the found and the wanted outcome.
KNOWN = {'R-N3': 'engine/combination.py base_within (4d): a part session\'s base code READY beside its whole',
         'Q-N1': 'a K3-demoted session read as possibly its claimed session alone: the EGD\'s base code READY',
         'R-ANAT': 'claims/settle (2c, 3a): a control shared by reached and reached_anatomy leaves the anatomy '
                   'unappraised',
         'R-K8': 'engine/assess.py (5a): a reach contradicted by its polarity pair asks extent, not conflict (RANK 1)',
         'Q-S4': 'a terminated ERCP whose completion pass 2 caught: READY with no 52/53 consideration'}


class KnownDefectTests(Fixture):
    """9.5 is NOT green while any of these fails (the refutation round 1's P5, built fail-closed): each known defect's
    DESIGN expectation, (i) or (ii) as the case writes it, and for a (ii) the "never a wrong READY or a wrong exclusion"
    assertion, through the whole pipeline. The other tests hold these codes to their pins (a repair trips them; then the
    pin is removed from the case and this test passes). Each test fails today on purpose: it is the suite's own record
    that the request or question is open, never a defect of this step's files."""

    def check_known(self, request: str) -> None:
        cases = known_defects().get(request, [])
        self.assertTrue(cases, f'{request} pins no case')
        for case_id, variant in dict.fromkeys((case_id, variant) for case_id, variant, _code in cases):
            self.check_expected(case_id, variant, design=True)
            if variant == 'ii':
                self.check_caught(case_id, design=True)

    def test_every_pin_has_its_test(self):
        self.assertEqual(sorted(known_defects()), sorted(KNOWN))
        for request in KNOWN:
            with self.subTest(request=request):
                self.assertTrue(hasattr(self, 'test_' + request.replace('-', '_')))

    def test_R_N3(self):
        self.check_known('R-N3')

    def test_Q_N1(self):
        self.check_known('Q-N1')

    def test_R_ANAT(self):
        self.check_known('R-ANAT')

    def test_R_K8(self):
        self.check_known('R-K8')

    def test_Q_S4(self):
        self.check_known('Q-S4')


class ResidualTests(SimpleTestCase):
    """Variant (iii), the shared misreading: RECORDED as a residual, never counted as a pass (9.5). These tests assert
    the record, not the outcome: every (iii) is in RESIDUALS.json, marked counted_as_pass false, and the record equals
    what the engine gives today (so a changed residual is seen and re-recorded, write_residuals)."""
    maxDiff = None

    def test_every_shared_misreading_is_recorded_and_none_counts_as_a_pass(self):
        recorded = residuals()['cases']
        wanted = residual_cases('class', 'borderline', 'checklist', 'refutation')
        self.assertEqual(sorted(recorded), sorted(wanted))
        for case_id, record in recorded.items():
            with self.subTest(case=case_id):
                self.assertIs(record['counted_as_pass'], False)
                self.assertEqual(set(record['codes']), set(case(case_id)['expect']['i']))

    def test_the_record_is_current(self):
        # the refutation cases' residuals are asserted current by tests/v2/test_refutation_cases.py
        for case_id in residual_cases('class', 'borderline', 'checklist'):
            with self.subTest(case=case_id):
                self.assertEqual(residual_record(case_id), residuals()['cases'][case_id])

    def test_the_counts_add_up(self):
        counts: dict = {}
        for record in residuals()['cases'].values():
            for found in record['codes'].values():
                counts[found['against_documented']] = counts.get(found['against_documented'], 0) + 1
        self.assertEqual(counts, residuals()['counts_by_class'])

    def test_a_shared_filing_of_its_own_is_recorded_as_a_residual(self) -> None:
        """DECISIONS D241: GI Note #8's tattoo filed with no place and no lesion is kept only as variant (iii) - of
        CK-note8 and of C2MEM-031's RF-CO2d - and recorded: 45381 held there, where the documented outcome is READY,
        classed as a hold against it, never as a pass."""
        shared = [entry['case'] for entry in manifest()['cases'] if 'shared' in case(entry['case'])['pass1']]
        self.assertEqual(sorted(shared), ['CK-note8', 'RF-CO2d'])
        for case_id in shared:
            with self.subTest(case=case_id):
                record = residuals()['cases'][case_id]
                self.assertIs(record['counted_as_pass'], False)
                self.assertEqual(case(case_id)['expect']['i']['45381']['status'], 'ready')
                self.assertNotEqual(record['codes']['45381']['against_documented'], 'as_documented')

    def test_every_named_residual_is_recorded_and_none_counts_as_a_pass(self) -> None:
        recorded = residuals()['named']
        self.assertEqual(recorded, named_records())
        self.assertTrue(recorded)
        for case_id, variants in recorded.items():
            for variant, entries in variants.items():
                for entry in entries:
                    with self.subTest(case=case_id, variant=variant, residual=entry['id']):
                        self.assertIs(entry['counted_as_pass'], False)
                        self.assertTrue(entry['naming'])
                        self.assertIn(variant, case(case_id)['variants'])
        # D244: Q-N8b is named beside GI Note #8's documented outcome, in CK-note8 and in RF-CO2d
        self.assertEqual(sorted(case_id for case_id, variants in recorded.items()
                                if any(entry['id'] == 'Q-N8b' for entry in variants.get('i', ()))),
                         ['CK-note8', 'RF-CO2d'])


class FixtureFileTests(SimpleTestCase):
    """The fixture files: synthetic, none on the exclusion list, the development documents byte-identical to their
    sources, the replay slots named, and the committed files equal to what the builder writes."""

    def test_the_committed_files_are_what_the_builder_writes(self):
        from tests.fixtures.interpretation_v2 import build
        for name, text in build.files().items():
            with self.subTest(file=name):
                self.assertEqual((FIXTURES / name).read_text(encoding='utf-8'), text)
        written = {str(path.relative_to(FIXTURES)) for folder in ('documents', 'answers')
                   for path in (FIXTURES / folder).iterdir()}
        self.assertEqual(written, {name for name in build.files() if '/' in name})

    def test_every_document_is_synthetic_and_none_is_an_acceptance_document(self):
        """Every fixture document is synthetic - written for these fixtures with its SYNTHETIC and fictional banner, or a
        development document used verbatim (a FRESH-1 input, synthetic by provenance, 9.6: GI Note #8 carries no banner
        of its own), byte-equal to its recorded source - and none is on the exclusion list, as written or stripped."""
        from tests.fixtures.interpretation_v2 import devdocs
        with open(APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256', encoding='ascii') as f:
            excluded = {line.strip() for line in f if line.strip()}
        self.assertEqual(len(excluded), 288)
        sources = {digest for _path, digest in devdocs.SOURCES.values()}
        for entry in manifest()['cases']:
            text = document(entry['case'])
            with self.subTest(case=entry['case']):
                digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
                if not (digest in sources and digest in entry['provenance']):
                    self.assertIn('SYNTHETIC', text)
                    self.assertTrue('fictional' in text or 'FICTIONAL' in text)
                for data in (text.encode('utf-8'), text.strip().encode('utf-8')):
                    self.assertNotIn(hashlib.sha256(data).hexdigest(), excluded)
                self.assertEqual(entry['not_on_exclusion_list'], {'as_written': True, 'whitespace_stripped': True})

    def test_the_development_documents_are_their_sources_byte_for_byte(self):
        from tests.fixtures.interpretation_v2 import devdocs
        for name, (path, digest) in devdocs.SOURCES.items():
            with self.subTest(document=path):
                self.assertEqual(hashlib.sha256(getattr(devdocs, name).encode('utf-8')).hexdigest(), digest)
                users = [entry['case'] for entry in manifest()['cases'] if digest in entry['provenance']]
                self.assertTrue(users, f'{path} is used by no case')
                for case_id in users:
                    self.assertEqual(hashlib.sha256(document(case_id).encode('utf-8')).hexdigest(), digest)

    def test_the_development_documents_read_for_their_shape_are_no_acceptance_document(self):
        """The documents a stand-in was written in the shape of (not in the repository): exactly the ones some case's
        provenance names, each with its two hashes off the exclusion list."""
        from tests.fixtures.interpretation_v2 import devdocs
        with open(APP / 'docs' / 'gemini-migration' / 'acceptance-a1' / 'DEV-EXCLUSION.sha256', encoding='ascii') as f:
            excluded = {line.strip() for line in f if line.strip()}
        marker = 'in the shape of development document fresh/inputs/'
        shaped = {entry['provenance'].split(marker)[1].split(' ')[0] for entry in manifest()['cases']
                  if marker in entry['provenance']}
        self.assertEqual(set(devdocs.SHAPES), shaped)
        for path, digests in devdocs.SHAPES.items():
            with self.subTest(document=path):
                self.assertEqual(len(digests), 2)
                self.assertFalse(set(digests) & excluded)

    def test_every_unlisted_entry_lies_on_a_unit_of_its_document(self):
        """A constructed pass-2 answer's unlisted entry names units the document has (appraise_read drops any other,
        and the entry then lies on no unit: 3.2.6 rule 2 can never read it)."""
        for entry in manifest()['cases']:
            ids = {unit.id for unit in segment.units(document(entry['case']))}
            for variant, rule in case(entry['case'])['pass2'].items():
                for unlisted in rule['unlisted']:
                    with self.subTest(case=entry['case'], variant=variant, unlisted=unlisted['what']):
                        self.assertTrue(unlisted['units'])
                        self.assertLessEqual(set(unlisted['units']), ids)

    def test_the_replay_recording_slots_are_named(self):
        slots = json.loads((FIXTURES / 'recordings' / 'SLOTS.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(slots['slots']), ['D2', 'D3'])
        for name, slot in slots['slots'].items():
            with self.subTest(slot=name):
                folder = FIXTURES / 'recordings' / slot['directory']
                if slot['status'] == 'empty':
                    self.assertFalse(folder.exists() and any(folder.iterdir()))
                else:  # step 8 fills it and replays it (9.6); until then nothing here reads it
                    self.skipTest(f'recordings {name} are replayed by step 8\'s own test')
