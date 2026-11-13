"""Step 1f's engine/requirements.py (docs/gemini-migration/FINAL-V2.md, 8.1 step 1f; 4.3, 4.8, 4.9, 3.2.1, 1.1, 2.5),
TEXT-ONLY and SYNTHETIC: no document, no provider, no network.

The done-when of 8.1 step 1f, each proved here (the other two are tests/v2/test_requirements_table.py's):
- "RANK pinned": RANK is 4.8's table, exactly its 23 ranks and their fact keys, transcribed below from the design and
  pinned by sha under REQUIREMENTS_VERSION;
- "CLAIMED's sha computed": claimed_sha256() is pinned under APPRAISAL_VERSION, so a CLAIMED change that is not
  re-pinned fails here (1.1; DECISIONS D202: until the first recording a changed CLAIMED needs a recomputed pin and no
  version bump), and interpretation.CLAIMED_SHA256, the 2.5 pin the integration owner writes, may only be empty or
  equal to it.
Also: each code's requirements (templates' head and tail, its tags) and spec off the catalogue; every requirement's
items at 4.3's facts and 4.8's ranks, route (b)'s one item (D197); CLAIMED as 3.2.1 writes it with D194 (the umbrellas
are codable) and D195 (every attribute a rule reads is claimed, per kind), its ERCP kinds the fifteen the ERCP entry
names (D207); the read-sets against CLAIMED (a static P-READSET per kind, with no gap left: D195; and P2 per listed
kind: every kind of a kind list that no rule reads is one D194 or D195 keeps, named here) and against 3.2.3's
controlled attributes (D196: every READY or exclusion read is controlled, or named here with its reason, and every
controlled attribute is read on such a path); the kind of moderate sedation and other read on the hold path only
(D194); dependencies (4.9's example: a dilation's device is outside 43239's closure; XCHG's counterparts inside
43276's, the arbiter's 1f#2); the text-free boundary (5.7 measure 4, a fresh interpreter, mypy --strict). The readings
this step's builder made are recorded in DECISIONS D207.
"""
from __future__ import annotations

import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract.jsonschema import sha256_of
from studio.interpretation.contract.types import AnatomyType, Attribute, Kind, SessionKind
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import requirements as R
from studio.interpretation.engine.requirements import (CLAIMED, RANK, RULES, Condition, FactKey, Item, ObjectClass,
                                                       Rank, Requirement, Role)
from studio.interpretation.engine.requirements_table import CODES, FAMILY_KINDS, NAMED_KINDS, Tag, Template
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
ENGINE = APP / 'studio' / 'interpretation' / 'engine'
MODULES = {'engine/requirements': ENGINE / 'requirements.py',
           'engine/requirements_table': ENGINE / 'requirements_table.py'}
# Every file step 1f's patch creates (DECISIONS D207's citation check).
STEP_FILES = (APP / 'scripts' / 'gen_requirements.py', ENGINE / 'requirements.py', ENGINE / 'requirements_table.py',
              Path(__file__), APP / 'tests' / 'v2' / 'test_requirements_table.py')

# --- the pins (1.1, 2.5) ----------------------------------------------------------------------------------------------
# REQUIREMENTS_VERSION names the requirement table, its read-sets, the CLAIMED table and RANK (1.1); APPRAISAL_VERSION
# names CLAIMED by sha (1.1, 2.5). Until the first recording under a label a changed object needs only a recomputed pin
# here, and no version bump (DECISIONS D202); after it, a new version and a new row: the lookup of the current version
# fails until it is written, and a stale sha fails the comparison. Recomputed after the repairs under D194-D197 (the
# arbiter's INT-5): CLAIMED 789b8fcc... and the read-sets bed18467... are superseded, and so is CLAIMED b6ade5f5...,
# whose ERCP kinds were D191's family kinds (the duct of an ERCP examination, intervention, sedation and other claimed).
REQUIREMENTS_PINS = {
    'cpt-requirements@1': {
        'table': '1b0f0d18e5d3328d923f43bd033b75559e439c849dafae259ddd6e64b89820e5',
        'rank': '4c0c972d7c8f05b48bc4cebfaa1628c8e7d772ebb3dbcd4146a0eb80da3c26c1',
        'rules': '72970ffb5ed848e16d97bea385bc7f3f1f9aa3f16deb081463d97d9e7887309f',
        'claimed': '8c95246d6ff8a260b344bb5a52e25f51ac744343ed8ebe5887764ad7e5cd7b81',
    },
}
CLAIMED_PINS = {'gemini-appraisal@1': '8c95246d6ff8a260b344bb5a52e25f51ac744343ed8ebe5887764ad7e5cd7b81'}

# --- 4.8's RANK, as the design writes it ------------------------------------------------------------------------------
DESIGN_RANK = (
    (1, ('conflict',)), (2, ('performed_status',)), (3, ('statement_scope',)), (4, ('performed_status',)),
    (5, ('event_entry',)), (6, ('event_time',)), (7, ('event_performer',)), (8, ('procedure',)), (9, ('act_method',)),
    (10, ('technique',)), (11, ('act_target',)), (12, ('target',)), (13, ('exam_stations',)), (14, ('extent',)),
    (15, ('act_yield',)), (16, ('cannulation',)), (17, ('act_part', 'act_cause', 'act_target')),
    (18, ('performed_status',)), (19, ('em_basis',)), (20, ('separate_em',)), (21, ('base_included',)),
    (22, ('competing_codes',)), (23, ('setting', 'patient_status')))

# --- 3.2.1's CLAIMED, as the design writes it, with D195 (kinds None: every codable kind) -----------------------------
# D195: an act's places and lesion for every codable kind that has a target - every kind (D194 makes the umbrellas
# codable) but the visit, prolonged visit time, moderate sedation and other; 3.2.1 named the fifteen lesion-bearing ones
TARGET = {kind.value for kind in Kind} - {'em_visit', 'em_prolonged', 'moderate_sedation', 'other'}
# 3.2.1's "duct (ERCP kinds)": the fifteen kinds the ERCP catalogue entry names, cannulation included (R6:cannulation
# reads its duct), the builder's reading DECISIONS D207 records; written out here, never read from the generated table.
# D191's family kinds add the examination, intervention, moderate sedation and other, whose duct no rule reads (P2).
ERCP = {'ablation', 'biopsy', 'cannulation', 'cholangioscopy', 'clip', 'dilation', 'foreign_body', 'injection',
        'lithotripsy', 'pressure_measurement', 'sphincterotomy', 'stent', 'stent_exchange', 'stent_removal',
        'stone_extraction'}
DESIGN_CLAIMED = {
    'act': [('kind', 'always', None), ('other_class', 'always', None), ('status', 'always', None),
            ('session', 'always', None), ('date_relation', 'effective', None), ('date', 'always', None),
            ('performer', 'effective', None), ('performer_person', 'other_clinician', None), ('entry', 'always', None),
            ('technique.device', 'always', None),
            ('technique.route', 'always', {'injection', 'tattoo', 'drainage', 'fna'}),  # 3.2.1 names fiducial too
            ('target.structure', 'always', {'drainage'}), ('target.structure', 'eus_session', {'injection'}),
            ('target.duct', 'always', ERCP), ('target.places', 'always', TARGET),
            ('target.lesion', 'always', TARGET),
            ('purpose', 'always', {'clip', 'injection', 'bleeding_control', 'ablation'}),
            ('cause', 'always', {'clip', 'injection', 'bleeding_control', 'ablation'}),
            ('cause_event', 'always', {'clip', 'injection', 'bleeding_control', 'ablation'}),
            ('part_of', 'when_present', None), ('part_relation', 'when_present', None),
            ('yield', 'always', {'stone_extraction', 'foreign_body', 'removal', 'stent_removal'}),
            ('access_outcome', 'always', {'cannulation'}), ('visit.basis', 'always', {'em_visit'}),
            ('visit.separately_identifiable', 'always', {'em_visit'}),
            ('restatements.role', 'restates_in_own_section', None)],
    'statement': [('kind', 'always', None), ('status', 'always', None), ('session', 'always', None),
                  ('date_relation', 'effective', None), ('performer', 'own_when_named', None),
                  ('performer_person', 'own_when_named', None),  # D195: its own named person (4.5's performer row)
                  ('scope.breadth', 'always', None), ('scope.covers', 'always', None),
                  ('scope.excepts', 'always', None),
                  ('target.lesion', 'always', None), ('target.places', 'always', None),
                  ('target.anatomy', 'always', None), ('target.duct', 'always', None),
                  ('scope.targets', 'always', None), ('scope.segment', 'always', None),
                  ('technique.device', 'when_named', None)],
    'session': [('kind', 'always', None), ('encounter', 'holds_visit', None), ('tract', 'always', None),
                ('approach', 'always', None), ('through', 'always', None), ('reached', 'always', None),
                ('reached_anatomy', 'always', None), ('completion', 'always', None), ('stations', 'always', None),
                ('part_of_session', 'always', None), ('stations', 'completeness', None)],
    'anatomy': [('type', 'read_by_a_rule', None), ('organ', 'read_by_a_rule', None),
                ('subtype', 'read_by_a_rule', None),
                ('joins', 'read_by_a_rule', None)],
    'lesion': [('multiplicity', 'of_a_claimed_act', None),
               ('places', 'of_a_claimed_act', None),  # D195: SITE's lesion arm
               ('distinct_from', 'of_a_claimed_act', None), ('same_as', 'of_a_claimed_act', None)],
    'encounter': [('date_of_service', 'always', None)],
}

# --- the read-sets against CLAIMED (P-READSET, 9.4, per kind: DECISIONS D195) -----------------------------------------
# (requirement, role, attribute) -> the codable act kinds read and not claimed ('-' for an object with no kind). D195
# emptied it: the examination's places (R6:target), a lesion's places (SITE), every paired act's lesion and places and a
# statement's own person (4.5's target and performer rows) are claimed. A code-specific row reads the code's supporting
# act, never an umbrella (4.3 row 1), and 4.5's target row the lesion and places of an act whose kind has a target
# (D195's TARGET_KINDS), so no read is left unclaimed and no claim beyond D195's list is needed.
KNOWN_GAPS: dict = {}
# CLAIMED attributes that no requirement reads for any kind (P2: "a claim no rule needs"), kept as 3.2.1 lists them
# (DECISIONS D195: they release nothing; trimming them is a cost question for D3).
CLAIMED_UNREAD = {('statement', 'target.anatomy'), ('statement', 'target.duct'), ('anatomy', 'organ'),
                  ('anatomy', 'joins')}
# The same per listed kind (P2 at the level 3.2.1 writes its kind lists): for each CLAIMED entry whose kinds are listed,
# the codable kinds of its list that no requirement of any code reads. Each is kept by a ruling; any other is a claim
# no rule needs (the ERCP examination's, intervention's, sedation's and other's duct, before this repair):
# - the kind-level extras the step's builder listed (the arbiter's 1f:R8: the route of a drainage and an FNA, the
#   structure of an EUS-session injection, the yield of a foreign body and a stent removal, the duct of eight of the
#   fifteen ERCP kinds), and an ablation's purpose (3.2.1's cause kinds; CAUSE reads a bleeding control's candidates),
#   all kept as 3.2.1 lists them (DECISIONS D195);
# - a removal's yield: D194 makes removal codable and keeps it an extraction kind (design A's X8);
# - the places and lesion of a balloon expulsion and a cannulation: D195's target kinds, every codable kind but four.
KIND_LISTED_UNREAD = {
    ('act', 'technique.route', 'always'): {'drainage', 'fna'},
    ('act', 'target.structure', 'eus_session'): {'injection'},
    ('act', 'target.duct', 'always'): {'ablation', 'biopsy', 'cholangioscopy', 'clip', 'injection', 'lithotripsy',
                                       'pressure_measurement', 'stone_extraction'},
    ('act', 'target.places', 'always'): {'balloon_expulsion', 'cannulation'},
    ('act', 'target.lesion', 'always'): {'balloon_expulsion', 'cannulation'},
    ('act', 'purpose', 'always'): {'ablation'},
    ('act', 'yield', 'always'): {'foreign_body', 'removal', 'stent_removal'},
}

# --- 3.2.3's controlled attributes against the READY and exclusion read paths (P-CONTROLLED's inputs; D196) -----------
# Every (object class, attribute) 3.2.3's table of contrary controls controls, as the design writes it, with D195's
# statement person and D196's duct (biliary/pancreatic/cystic) and through (another anatomy entry); read from the
# design, never from claims.CONTROLS (step 2c).
DESIGN_CONTROLLED = {
    ('act', 'status'), ('act', 'date_relation'), ('act', 'performer'), ('act', 'performer_person'), ('act', 'entry'),
    ('act', 'restatements.role'), ('act', 'session'), ('act', 'kind'), ('act', 'other_class'), ('act', 'target.places'),
    ('act', 'target.lesion'), ('act', 'technique.device'), ('act', 'technique.route'), ('act', 'target.structure'),
    ('act', 'purpose'), ('act', 'cause'), ('act', 'yield'), ('act', 'access_outcome'), ('act', 'visit.basis'),
    ('act', 'visit.separately_identifiable'), ('act', 'target.duct'),
    ('statement', 'status'), ('statement', 'kind'), ('statement', 'date_relation'), ('statement', 'session'),
    ('statement', 'performer'), ('statement', 'performer_person'), ('statement', 'target.lesion'),
    ('statement', 'target.places'), ('statement', 'scope.targets'), ('statement', 'scope.segment'),
    ('statement', 'scope.breadth'), ('statement', 'scope.excepts'), ('statement', 'technique.device'),
    ('session', 'encounter'), ('session', 'stations'), ('session', 'reached'), ('session', 'kind'),
    ('session', 'completion'), ('session', 'approach'), ('session', 'tract'), ('session', 'reached_anatomy'),
    ('session', 'through'),
    ('anatomy', 'type'), ('anatomy', 'organ'), ('anatomy', 'subtype'),
    ('lesion', 'multiplicity'), ('lesion', 'distinct_from'),
}
# Read on a READY or exclusion path and not controlled by 3.2.3, each with its reason (a pinned reason, not a control).
READ_UNCONTROLLED = {
    ('encounter', 'date_of_service'): "3.2.3's UNCONTROLLED: L1 and the member date's precedence check it",
    # SITE's lesion arm reads it (READY, D195 claims it); 3.2.2 gives it no template, and neither 3.2.3 nor D196 a
    # control or an UNCONTROLLED entry: open for the integration owner, pinned so that deciding it moves this row
    ('lesion', 'places'): 'claimed by D195 for SITE; no control decided',
}
# Controlled by 3.2.3 and read on no READY or exclusion path, each with its reason.
CONTROLLED_UNREAD = {
    ('anatomy', 'organ'): 'no rule reads it; CLAIMED keeps it as 3.2.1 lists it (D195)',
}


def ready_reads() -> set:
    """(object class, attribute) of every read made on a READY or an exclusion path, every rule's arms included."""
    found = set()
    for rule in RULES.values():
        for read in rule.every_read():
            object_class = R.ROLE_CLASS[read.role]
            if object_class is not None and read.attribute is not None and read.paths & {R.Path.READY,
                                                                                          R.Path.EXCLUSION}:
                found.add((object_class.value, read.attribute.value))
    return found


def kinds_read(code: str, read: R.Read) -> frozenset:
    """The act kinds ``read`` is made for under ``code``: ACT, the code's candidates (narrowed by the read's kinds);
    STATEMENT, its closure's statement kinds (dependencies: those pairing with its candidates and its counterparts);
    another event role, the read's kinds, else every codable kind."""
    if read.role is Role.ACT:
        candidates = R.candidate_kinds(R.spec(code).groups)
        return candidates & read.kinds if read.kinds is not None else candidates
    if read.role is Role.STATEMENT:
        return R.dependencies(code).statement_kinds
    return read.kinds if read.kinds is not None else R.CODABLE_KINDS


def static_readset() -> tuple[dict, dict, dict]:
    """Every read of every code's requirements (the 163 catalogue codes and route (b)'s 46221) resolved to the act kinds
    it is read for (kinds_read) and checked against CLAIMED. Returns the unclaimed reads (requirement, role, attribute)
    -> kinds, the reads of a kind that is not codable kind -> requirements, and the claimed reads (class, attribute) ->
    kinds."""
    gaps, uncodable, claimed = defaultdict(set), defaultdict(set), defaultdict(set)
    for code in [str(code) for code in CODES] + ['46221']:
        found = R.spec(code)
        for requirement in R.requirements_of(code):
            for read in RULES[requirement].reads_for(found.template):
                object_class = R.ROLE_CLASS[read.role]
                if object_class is None or read.attribute is None:
                    continue
                key = (requirement.value, read.role.value, read.attribute.value)
                if object_class not in (ObjectClass.ACT, ObjectClass.STATEMENT):
                    if R.claimed(object_class, read.attribute):
                        claimed[(object_class.value, read.attribute.value)].add('-')
                    else:
                        gaps[key].add('-')
                    continue
                for kind in kinds_read(code, read):
                    if kind not in R.CODABLE_KINDS:
                        uncodable[kind.value].add(requirement.value)
                    elif R.claimed(object_class, read.attribute, kind):
                        claimed[(object_class.value, read.attribute.value)].add(kind.value)
                    else:
                        gaps[key].add(kind.value)
    return dict(gaps), dict(uncodable), dict(claimed)


class RankTests(SimpleTestCase):
    def test_rank_is_4_8s_table_exactly_its_23_ranks(self):
        self.assertEqual(len(Rank), 23)
        self.assertEqual([rank.value for rank in Rank], list(range(1, 24)))
        self.assertEqual(tuple((rank.value, tuple(fact.value for fact in RANK[rank])) for rank in Rank), DESIGN_RANK)
        self.assertEqual(list(RANK), list(Rank))

    def test_the_first_four_keep_v1s_h1_to_h4_and_service_date_is_unranked(self):
        self.assertEqual([RANK[rank] for rank in list(Rank)[:4]],
                         [(FactKey.CONFLICT,), (FactKey.PERFORMED_STATUS,), (FactKey.STATEMENT_SCOPE,),
                          (FactKey.PERFORMED_STATUS,)])
        self.assertEqual(R.UNRANKED, (FactKey.SERVICE_DATE,))
        self.assertEqual(R.KEY_BOUND, {FactKey.SEPARATE_EM, FactKey.BASE_INCLUDED})
        ranked = {fact for facts in RANK.values() for fact in facts}
        self.assertEqual(ranked | set(R.UNRANKED), set(FactKey))
        self.assertNotIn(FactKey.SERVICE_DATE, ranked)

    def test_rank_is_pinned_under_the_requirements_version(self):
        pins = REQUIREMENTS_PINS[interpretation.REQUIREMENTS_VERSION]
        self.assertEqual(sha256_of(R.rank_canonical()), pins['rank'])

    def test_an_item_names_one_of_its_ranks_facts(self):
        self.assertEqual(Item(Rank.BUNDLING, FactKey.ACT_CAUSE).fact, FactKey.ACT_CAUSE)
        self.assertIsNone(Item(None, FactKey.SERVICE_DATE).rank)
        for rank, fact in ((Rank.TIME, FactKey.EVENT_PERFORMER), (Rank.STATUS, FactKey.ACT_PART),
                           (None, FactKey.EXTENT), (Rank.MEMBER_CONTEXT, FactKey.SERVICE_DATE)):
            with self.subTest(rank=rank, fact=fact), self.assertRaises(ValueError):
                Item(rank, fact)

    def test_fact_keys(self):
        self.assertEqual(R.fact_key(FactKey.CONFLICT, Kind.SNARE), 'conflict:snare')
        self.assertEqual(R.fact_key(FactKey.CONFLICT, Kind.STONE_EXTRACTION), 'conflict:stone_extraction')
        self.assertEqual(R.fact_key(FactKey.EVENT_ENTRY), 'event_entry')
        with self.assertRaises(ValueError):
            R.fact_key(FactKey.CONFLICT)
        with self.assertRaises(ValueError):
            R.fact_key(FactKey.EXTENT, Kind.SNARE)


class PinTests(SimpleTestCase):
    def test_the_table_and_read_sets_are_pinned_under_the_requirements_version(self):
        pins = REQUIREMENTS_PINS[interpretation.REQUIREMENTS_VERSION]
        self.assertEqual(sha256_of(R.table_canonical()), pins['table'])
        self.assertEqual(sha256_of(R.rules_canonical()), pins['rules'])
        self.assertEqual(R.claimed_sha256(), pins['claimed'])

    def test_a_claimed_change_is_re_pinned_under_the_appraisal_version(self):
        # D202: no version bump before the first recording under gemini-appraisal@1; a recomputed pin here
        self.assertEqual(interpretation.APPRAISAL_VERSION, 'gemini-appraisal@1')
        self.assertEqual(R.claimed_sha256(), CLAIMED_PINS[interpretation.APPRAISAL_VERSION])
        # the 2.5 pin the integration owner writes from this step's sha: empty until then, never another value
        self.assertIn(interpretation.CLAIMED_SHA256, ('', R.claimed_sha256()))

    def test_the_claimed_sha_is_its_canonical_bytes_and_moves_with_any_entry(self):
        self.assertEqual(R.claimed_sha256(), sha256_of(R.claimed_canonical()))
        canonical = R.claimed_canonical()
        act = canonical['classes'][0][1]
        changed = dict(canonical, classes=[['act', [entry for entry in act if entry[0] != 'technique.route']],
                                           *canonical['classes'][1:]])
        self.assertNotEqual(sha256_of(changed), R.claimed_sha256())


class ClaimedTests(SimpleTestCase):
    def test_claimed_is_3_2_1s_table(self):
        found = {}
        for object_class, entries in CLAIMED.items():
            found[object_class.value] = [
                (entry.attribute.value, entry.condition.value,
                 None if entry.kinds is None else {kind.value for kind in entry.kinds}) for entry in entries]
        self.assertEqual(found, DESIGN_CLAIMED)
        self.assertEqual(list(CLAIMED), list(ObjectClass))

    def test_the_codable_kinds_are_the_catalogues_with_the_three_3_2_1_adds_and_the_umbrellas(self):
        # D194: removal and intervention are codable, so every Kind is; an event whose kind is not established is not
        self.assertEqual(set(Kind) - R.CODABLE_KINDS, set())
        self.assertEqual(R.CODABLE_KINDS, R.CATALOGUE_KINDS | {Kind.EXAMINATION, Kind.EM_VISIT, Kind.OTHER,
                                                              Kind.REMOVAL, Kind.INTERVENTION})
        self.assertIn(Kind.CANNULATION, R.ERCP_KINDS)  # R6:cannulation reads the cannulation's duct
        # D207: the kinds the ERCP catalogue entry names, never D191's wider kinds of the ERCP session family
        self.assertEqual(R.ERCP_KINDS, NAMED_KINDS[SessionKind.ERCP])
        self.assertEqual(FAMILY_KINDS[SessionKind.ERCP] - R.ERCP_KINDS,
                         {Kind.EXAMINATION, Kind.INTERVENTION, Kind.MODERATE_SEDATION, Kind.OTHER})
        for kind in (Kind.EXAMINATION, Kind.INTERVENTION, Kind.MODERATE_SEDATION, Kind.OTHER):
            self.assertEqual(R.claimed(ObjectClass.ACT, Attribute.TARGET_DUCT, kind), ())
        self.assertEqual(R.ANATOMY_READ_TYPES, {AnatomyType.STOMA, AnatomyType.ILEAL_POUCH, AnatomyType.GASTRIC_POUCH,
                                                AnatomyType.ROUX_LIMB, AnatomyType.BYPASS,
                                                AnatomyType.SURGICALLY_ABSENT})
        self.assertIn(Kind.REMOVAL, R.EXTRACTION_KINDS)  # design A's X8, kept by D194

    def test_the_target_kinds_are_every_codable_kind_that_has_a_target(self):
        # D195: every codable kind but the visit, prolonged visit time, moderate sedation and other; the examination
        # included (R6:target), and the fifteen lesion-bearing kinds 3.2.1 named among them
        self.assertEqual(R.CODABLE_KINDS - R.TARGET_KINDS, {Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION,
                                                            Kind.OTHER})
        lesion_bearing = {Kind.SNARE, Kind.EMR, Kind.ESD, Kind.HOT_BIOPSY, Kind.BIOPSY, Kind.ABLATION, Kind.INJECTION,
                          Kind.TATTOO, Kind.CLIP, Kind.BLEEDING_CONTROL, Kind.DILATION, Kind.STENT, Kind.BAND_LIGATION,
                          Kind.FNA, Kind.DRAINAGE}
        self.assertLess(lesion_bearing | {Kind.EXAMINATION, Kind.FOREIGN_BODY, Kind.REMOVAL}, R.TARGET_KINDS)
        # 4.5's target row reads the paired act's lesion and places for exactly these kinds (SUP.8)
        targets = {read.kinds for read in RULES[Requirement.SUP_CLEAN].reads
                   if read.role is Role.ACT and read.attribute in (Attribute.TARGET_LESION, Attribute.TARGET_PLACES)}
        self.assertEqual(targets, {R.TARGET_KINDS})

    def test_claimed_answers_with_the_conditions(self):
        act, statement, session = ObjectClass.ACT, ObjectClass.STATEMENT, ObjectClass.SESSION
        self.assertEqual(R.claimed(act, Attribute.KIND, Kind.SNARE), (Condition.ALWAYS,))
        self.assertEqual(R.claimed(act, Attribute.TARGET_STRUCTURE, Kind.DRAINAGE), (Condition.ALWAYS,))
        self.assertEqual(R.claimed(act, Attribute.TARGET_STRUCTURE, Kind.INJECTION), (Condition.EUS_SESSION,))
        self.assertEqual(R.claimed(act, Attribute.TARGET_STRUCTURE, Kind.SNARE), ())
        self.assertEqual(R.claimed(act, Attribute.PERFORMER_PERSON, Kind.BIOPSY), (Condition.OTHER_CLINICIAN,))
        self.assertEqual(R.claimed(act, Attribute.TARGET_DUCT, Kind.CANNULATION), (Condition.ALWAYS,))
        self.assertEqual(R.claimed(act, Attribute.ACCESS_OUTCOME, Kind.CANNULATION), (Condition.ALWAYS,))
        self.assertEqual(R.claimed(act, Attribute.ACCESS_OUTCOME, Kind.SPHINCTEROTOMY), ())
        self.assertEqual(R.claimed(act, Attribute.YIELD, Kind.STONE_EXTRACTION), (Condition.ALWAYS,))
        self.assertEqual(R.claimed(statement, Attribute.PERFORMER, Kind.BIOPSY), (Condition.OWN_WHEN_NAMED,))
        self.assertEqual(R.claimed(statement, Attribute.TECHNIQUE_DEVICE, Kind.SNARE), (Condition.WHEN_NAMED,))
        self.assertEqual(R.claimed(session, Attribute.STATIONS), (Condition.ALWAYS, Condition.COMPLETENESS))
        self.assertEqual(R.claimed(session, Attribute.ENCOUNTER), (Condition.HOLDS_VISIT,))
        self.assertEqual(R.claimed(session, Attribute.DEVICE_REACHED), ())  # 1.4: no rule reads it [R:CO-8]
        self.assertEqual(R.claimed(session, Attribute.EXAMINATION), ())  # see SUP.7's reads
        self.assertEqual(R.claimed(ObjectClass.ENCOUNTER, Attribute.DATE_OF_SERVICE), (Condition.ALWAYS,))
        # an event whose kind is not established is never claimed
        self.assertEqual(R.claimed(act, Attribute.KIND, None), ())
        self.assertEqual(R.claimed(statement, Attribute.STATUS, None), ())

    def test_d195s_claims_the_rules_read(self):
        act, statement = ObjectClass.ACT, ObjectClass.STATEMENT
        # R6:target: the examination's places, so an exam-only EUS code can be READY (the arbiter's 1f#5)
        self.assertEqual(R.claimed(act, Attribute.TARGET_PLACES, Kind.EXAMINATION), (Condition.ALWAYS,))
        # SITE's lesion arm: a lesion's places, for a lesion of a claimed act (1f#6)
        self.assertEqual(R.claimed(ObjectClass.LESION, Attribute.PLACES), (Condition.OF_A_CLAIMED_ACT,))
        # 4.5's target row: a paired foreign body removal's places and lesion (1f R5)
        for attribute in (Attribute.TARGET_PLACES, Attribute.TARGET_LESION):
            self.assertEqual(R.claimed(act, attribute, Kind.FOREIGN_BODY), (Condition.ALWAYS,))
        # 4.5's performer row: a statement's own named person (1f R6)
        self.assertEqual(R.claimed(statement, Attribute.PERFORMER_PERSON, Kind.BIOPSY), (Condition.OWN_WHEN_NAMED,))
        # a visit, prolonged time, sedation or other act has no target
        for kind in (Kind.EM_VISIT, Kind.EM_PROLONGED, Kind.MODERATE_SEDATION, Kind.OTHER):
            self.assertEqual(R.claimed(act, Attribute.TARGET_PLACES, kind), ())

    def test_d194s_umbrellas_are_claimed_like_any_other_kind(self):
        act, statement = ObjectClass.ACT, ObjectClass.STATEMENT
        # 4.10's broad denial "No polyp was removed today.": kind removal, breadth all_of_kind, session and date
        # relation established, "its breadth claim has a control" (the arbiter's 1f#4)
        for attribute in (Attribute.KIND, Attribute.STATUS, Attribute.SESSION, Attribute.SCOPE_BREADTH):
            self.assertTrue(R.claimed(statement, attribute, Kind.REMOVAL))
        self.assertEqual(R.claimed(statement, Attribute.DATE_RELATION, Kind.REMOVAL), (Condition.EFFECTIVE,))
        # a positive umbrella act's status, for rank 9's act_method (h5); its places and lesion (D195)
        for kind in (Kind.REMOVAL, Kind.INTERVENTION):
            self.assertEqual(R.claimed(act, Attribute.STATUS, kind), (Condition.ALWAYS,))
            self.assertEqual(R.claimed(act, Attribute.TARGET_PLACES, kind), (Condition.ALWAYS,))
        self.assertEqual(R.claimed(act, Attribute.YIELD, Kind.REMOVAL), (Condition.ALWAYS,))  # X8
        self.assertEqual(R.claimed(act, Attribute.YIELD, Kind.INTERVENTION), ())


class RequirementTests(SimpleTestCase):
    def test_every_requirement_and_tag_has_a_rule(self):
        self.assertEqual(set(RULES), set(Requirement) | set(Tag))

    def test_each_codes_requirements_are_its_templates_head_its_tags_and_its_templates_tail(self):
        support = [requirement for requirement in Requirement if requirement.value.startswith('SUP.')]
        self.assertEqual([requirement.value for requirement in support], [f'SUP.{n}' for n in range(1, 9)])
        for code, row in CODES.items():
            with self.subTest(code=code):
                found = R.requirements_of(str(code))
                self.assertEqual(found, (*R.TEMPLATE_HEAD[row.template], *row.tags, *R.TEMPLATE_TAIL[row.template]))
                if row.template is Template.RECOGNISED:
                    self.assertEqual(found, (*row.tags, Requirement.R7_R9))
                else:
                    self.assertEqual(found[:8], tuple(support))
                    self.assertEqual(Requirement.V_THIS_ENCOUNTER in found,
                                     row.template in (Template.EM, Template.EM_ADDON))
                    self.assertEqual(found[-3:], (Requirement.BUNDLING, Requirement.COMBINATION, Requirement.R7_R9))
                self.assertEqual(Tag.ATT in row.tags, row.template in R.EXAMINATION_TEMPLATES)

    def test_requirements_of_named_codes(self):
        sup = tuple(requirement for requirement in Requirement if requirement.value.startswith('SUP.'))
        tail = (Requirement.BUNDLING, Requirement.COMBINATION, Requirement.R7_R9)
        self.assertEqual(R.requirements_of('43249'), (*sup, Tag.R6_EXTENT, Tag.TECH, Tag.SITE, *tail))
        self.assertEqual(R.requirements_of('43259'),
                         (*sup, Tag.ATT, Tag.R6_TARGET, Tag.TRACT, Tag.STATIONS, *tail))
        self.assertEqual(R.requirements_of('99417'), (*sup, Requirement.V_THIS_ENCOUNTER, Tag.R6_EM_BASIS,
                                                      Tag.R6_CONTEXT, Tag.C3_SEP, Tag.ADDON, *tail))
        self.assertEqual(R.requirements_of('99153'), (Tag.ADDON, Tag.D80, Requirement.R7_R9))
        self.assertEqual(R.requirements_of('46221'), (*sup, Requirement.ROUTE_B, *tail))  # D197
        for unprofiled in ('12345', '043235', '4323', '', '４３２３５'):
            self.assertEqual(R.requirements_of(unprofiled), (Requirement.ROUTE_D, Requirement.R7_R9))

    def test_spec_off_the_catalogue(self):
        route_b = R.spec('46221')
        self.assertEqual((route_b.template, route_b.family, route_b.groups, route_b.tags, route_b.row),
                         (Template.ROUTE_B, SessionKind.OTHER_GI, ((Kind.BAND_LIGATION,),), (), None))
        for code in ('12345', '043235', '99999'):
            found = R.spec(code)
            self.assertEqual((found.template, found.groups, found.tags, found.row), (Template.UNPROFILED, (), (), None))
        self.assertIs(R.spec('43235').row, CODES[43235])
        self.assertEqual(R.NEVER_READY, {Template.RECOGNISED, Template.ROUTE_B, Template.UNPROFILED})

    def test_every_never_ready_code_carries_exactly_one_row_whose_item_is_its_hold(self):
        # 4.8: one clarification per held code. A code held whatever its facts say (D80, route (b) by D197, route (d))
        # carries exactly one requirement that reads nothing and explains performed_status at the status row; no other
        # code carries one (the arbiter's 1f#3)
        status = (Item(Rank.STATUS, FactKey.PERFORMED_STATUS),)

        def hold_rows(code: str) -> list:
            return [requirement for requirement in R.requirements_of(code)
                    if not RULES[requirement].every_read() and RULES[requirement].explains == status]

        for code in [str(code) for code in CODES] + ['46221', '12345', '99999']:
            with self.subTest(code=code):
                self.assertEqual(len(hold_rows(code)), 1 if R.spec(code).template in R.NEVER_READY else 0)
        self.assertEqual(hold_rows('46221'), [Requirement.ROUTE_B])
        self.assertEqual(hold_rows('99152'), [Tag.D80])
        self.assertEqual(hold_rows('12345'), [Requirement.ROUTE_D])
        self.assertEqual((RULES[Requirement.ROUTE_B].asks, RULES[Requirement.ROUTE_B].arms), ((), ()))
        # route (b) keeps SUPPORT, bundling and combination: exclusion, base and competition read its acts (D197)
        self.assertEqual(R.TEMPLATE_HEAD[Template.ROUTE_B], R.TEMPLATE_HEAD[Template.ACT])
        self.assertEqual(R.TEMPLATE_TAIL[Template.ROUTE_B], (Requirement.ROUTE_B, *R.TEMPLATE_TAIL[Template.ACT]))

    def test_each_tags_items_are_4_3s_columns_at_4_8s_ranks(self):
        def items(found):
            return {(item.rank, item.fact) for item in found}

        unmet = {  # 4.3's "unmet -> fact"
            Tag.ATT: set(), Tag.DEF: set(), Tag.ADDON: set(), Tag.D80: set(),
            Tag.R6_EXTENT: {(Rank.EXTENT, FactKey.EXTENT)}, Tag.COLFULL: {(Rank.EXTENT, FactKey.EXTENT)},
            Tag.R6_TARGET: {(Rank.TARGET, FactKey.TARGET)},
            Tag.R6_CANNULATION: {(Rank.CANNULATION, FactKey.CANNULATION)},
            Tag.R6_EM_BASIS: {(Rank.EM_BASIS, FactKey.EM_BASIS)},
            Tag.R6_CONTEXT: {(Rank.MEMBER_CONTEXT, FactKey.SETTING), (Rank.MEMBER_CONTEXT, FactKey.PATIENT_STATUS)},
            Tag.TECH: {(Rank.TECHNIQUE, FactKey.TECHNIQUE)}, Tag.SITE: {(Rank.ACT_TARGET, FactKey.ACT_TARGET)},
            Tag.STRUCT_PFC: {(Rank.TARGET, FactKey.TARGET)}, Tag.ROUTE: {(Rank.TECHNIQUE, FactKey.TECHNIQUE)},
            Tag.TRACT: {(Rank.PROCEDURE, FactKey.PROCEDURE)},
            Tag.STATIONS: {(Rank.EXAM_STATIONS, FactKey.EXAM_STATIONS)},
            Tag.LIMITED: {(Rank.EXAM_STATIONS, FactKey.EXAM_STATIONS)}, Tag.LOWER: {(Rank.EXTENT, FactKey.EXTENT)},
            Tag.ENT: {(Rank.PROCEDURE, FactKey.PROCEDURE), (Rank.EXTENT, FactKey.EXTENT)},
            Tag.YIELD: {(Rank.YIELD, FactKey.ACT_YIELD)},
            Tag.XCHG: {(Rank.ACT_TARGET, FactKey.ACT_TARGET), (Rank.STATUS, FactKey.PERFORMED_STATUS)},
            Tag.CAUSE: {(Rank.BUNDLING, FactKey.ACT_CAUSE)},
            Tag.C3_SEP: {(Rank.TIME, FactKey.EVENT_TIME), (Rank.SEPARATE_EM, FactKey.SEPARATE_EM)},
        }
        self.assertEqual(set(unmet), set(Tag))
        for tag, expected in unmet.items():
            with self.subTest(tag=tag):
                self.assertEqual(items(RULES[tag].asks), expected)
        # 4.3's "established otherwise ->" that are held items (the others are considerations or no support)
        self.assertEqual(items(RULES[Tag.YIELD].explains), {(Rank.YIELD, FactKey.ACT_YIELD)})
        self.assertEqual(items(RULES[Tag.CAUSE].explains), {(Rank.BUNDLED, FactKey.PERFORMED_STATUS)})
        self.assertEqual(items(RULES[Tag.C3_SEP].explains), {(Rank.SEPARATE_EM, FactKey.SEPARATE_EM)})
        self.assertEqual(items(RULES[Tag.D80].explains), {(Rank.STATUS, FactKey.PERFORMED_STATUS)})
        for tag in (Tag.ATT, Tag.R6_EXTENT, Tag.COLFULL, Tag.R6_CANNULATION, Tag.XCHG):
            self.assertEqual(RULES[tag].explains, ())  # a consideration, or "not supported", is no held item

    def test_supports_items_are_4_8s_rows(self):
        def facts(requirement):
            return {(item.rank, item.fact) for item in RULES[requirement].asks}

        self.assertEqual(facts(Requirement.SUP_DATE), {(Rank.TIME, FactKey.EVENT_TIME)})
        self.assertEqual(facts(Requirement.SUP_PERFORMER), {(Rank.PERFORMER, FactKey.EVENT_PERFORMER)})
        self.assertEqual(facts(Requirement.SUP_ENTRY), {(Rank.ENTRY, FactKey.EVENT_ENTRY)})
        self.assertIn((Rank.METHOD, FactKey.ACT_METHOD), facts(Requirement.SUP_KIND))
        self.assertIn((Rank.DOUBT, FactKey.PERFORMED_STATUS), facts(Requirement.SUP_STATUS))
        self.assertIn((Rank.CONFLICT, FactKey.CONFLICT), facts(Requirement.SUP_CLEAN))
        self.assertIn((Rank.STATEMENT_SCOPE, FactKey.STATEMENT_SCOPE), facts(Requirement.SUP_CLEAN))
        self.assertEqual(facts(Requirement.V_THIS_ENCOUNTER), {(Rank.TIME, FactKey.EVENT_TIME)})
        self.assertEqual(facts(Requirement.R7_R9), {(None, FactKey.SERVICE_DATE)})
        self.assertEqual(facts(Requirement.COMBINATION), {(Rank.BASE_INCLUDED, FactKey.BASE_INCLUDED),
                                                          (Rank.COMPETING, FactKey.COMPETING_CODES)})


class ReadSetTests(SimpleTestCase):
    def test_every_read_is_claimed_per_kind(self):
        # P-READSET per kind (D195): no read of any code is left unclaimed
        gaps, _uncodable, _claimed = static_readset()
        self.assertEqual(gaps, KNOWN_GAPS)

    def test_every_kind_read_is_codable(self):
        # D194: the umbrellas are codable, so no read is of a kind CLAIMED cannot claim; SUPPORT reads them
        _gaps, uncodable, claimed = static_readset()
        self.assertEqual(uncodable, {})
        self.assertTrue({'removal', 'intervention'} <= claimed[('act', 'kind')])
        self.assertTrue({'removal', 'intervention'} <= claimed[('statement', 'scope.breadth')])

    def test_the_claimed_attributes_no_rule_reads(self):
        _gaps, _uncodable, claimed = static_readset()
        read = set(claimed)
        unread = {(object_class.value, entry.attribute.value) for object_class, entries in CLAIMED.items()
                  for entry in entries} - read
        self.assertEqual(unread, CLAIMED_UNREAD)

    def test_every_listed_kind_no_rule_reads_is_one_a_ruling_keeps(self):
        # P2 ("a claim no rule needs") per listed kind: a kind list of CLAIMED that grows by a kind no rule reads fails
        # here (the refuter's P-1: ERCP_KINDS as D191's family kinds claimed four ducts no rule reads)
        _gaps, _uncodable, claimed = static_readset()
        found = {}
        for object_class, entries in CLAIMED.items():
            for entry in entries:
                if entry.kinds is None:
                    continue
                listed = {kind.value for kind in entry.kinds if kind in R.CODABLE_KINDS}
                unread = listed - claimed.get((object_class.value, entry.attribute.value), set())
                if unread:
                    found[(object_class.value, entry.attribute.value, entry.condition.value)] = unread
        self.assertEqual(found, KIND_LISTED_UNREAD)

    def test_reads_are_well_formed(self):
        for requirement, rule in RULES.items():
            for read in rule.every_read():
                with self.subTest(requirement=requirement, read=read):
                    self.assertEqual(read.attribute is None, R.ROLE_CLASS[read.role] is None)
                    self.assertTrue(read.paths)
                    self.assertTrue(read.kinds is None or read.kinds)
        self.assertEqual(set(R.ROLE_CLASS), set(Role))

    def test_no_code_specific_row_reads_an_umbrella_act(self):
        # 4.3 row 1: a positive umbrella never supports a method-specific code, and a code-specific row is met on the
        # supporting act; SUPPORT reads every candidate, the umbrellas included (rank 9's act_method)
        umbrellas = set(catalogue.UMBRELLAS)
        for tag in Tag:
            for read in RULES[tag].every_read():
                if read.role is Role.ACT:
                    with self.subTest(tag=tag, read=read):
                        self.assertIsNotNone(read.kinds)
                        self.assertFalse(read.kinds & umbrellas)
                        self.assertEqual(read.kinds, frozenset(Kind) - umbrellas)
        self.assertIsNone(RULES[Requirement.SUP_KIND].reads[0].kinds)
        self.assertIn(Kind.INTERVENTION, R.dependencies('43264').kinds)  # still a candidate: act_method can follow

    def test_uncontrolled_attributes_are_read_on_no_ready_or_exclusion_path_but_the_dates(self):
        # 3.2.3's UNCONTROLLED: part_of, part_relation, statement.covers and same_as decided by a single verdict because
        # a yes-bias there can only hold, and act.date because only the date relation decides a code; D196 adds
        # session.part_of_session, which only bundles (base_within)
        paths = defaultdict(set)
        for rule in RULES.values():
            for read in rule.every_read():
                if read.attribute is not None:
                    paths[(read.role, read.attribute)] |= read.paths
        for role, attribute in ((Role.ACT, Attribute.PART_OF), (Role.ACT, Attribute.PART_RELATION),
                                (Role.STATEMENT, Attribute.SCOPE_COVERS), (Role.LESION, Attribute.SAME_AS),
                                (Role.ACT, Attribute.DATE), (Role.SESSION, Attribute.PART_OF_SESSION)):
            self.assertEqual(paths[(role, attribute)], {R.Path.HOLD}, (role, attribute))
        self.assertIn(R.Path.EXCLUSION, paths[(Role.STATEMENT, Attribute.STATUS)])
        self.assertIn(R.Path.READY, paths[(Role.ACT, Attribute.TECHNIQUE_ROUTE)])

    def test_3_2_3s_controlled_attributes_are_exactly_the_ready_and_exclusion_reads(self):
        # D196 (the arbiter's 1f#1): controls are generated for every attribute a rule reads on a READY or exclusion
        # path (3.2.3), so the two lists are tied both ways - a read moved to READY that 3.2.3 does not control, or a
        # controlled attribute left only on the hold path (lesion.multiplicity before the repair), fails here, each
        # difference named with its reason
        ready = ready_reads()
        self.assertEqual(ready - DESIGN_CONTROLLED, set(READ_UNCONTROLLED))
        self.assertEqual(DESIGN_CONTROLLED - ready, set(CONTROLLED_UNREAD))
        self.assertIn(('lesion', 'multiplicity'), ready)  # an established group un-bundles the biopsy (4.7, C-2)
        self.assertNotIn(('session', 'part_of_session'), ready)

    def test_the_kind_of_other_is_read_on_the_hold_path_only_and_moderate_sedations_on_the_ready_path(self):
        # D194: kind other has no sibling, so no READY or exclusion path reads its kind. D213: the same-day rule's READY
        # path and base_included read moderate sedation's kind (a sibling false of sedation controls it, step 2c3);
        # every other kind a rule reads on one keeps it, and the whole of a bundling is read on the hold path only
        found = defaultdict(set)
        for code in [str(code) for code in CODES] + ['46221']:
            template = R.spec(code).template
            for requirement in R.requirements_of(code):
                for read in RULES[requirement].reads_for(template):
                    if read.attribute is Attribute.KIND and R.ROLE_CLASS[read.role] is ObjectClass.ACT:
                        for kind in kinds_read(code, read) & {Kind.MODERATE_SEDATION, Kind.OTHER}:
                            found[(requirement, read.role, kind)] |= read.paths
        self.assertTrue(found)
        for key, paths in found.items():
            with self.subTest(read=key):
                ready = key[2] is Kind.MODERATE_SEDATION and key[1] is not Role.WHOLE
                self.assertEqual(paths, {R.Path.READY} if ready else {R.Path.HOLD})
        self.assertEqual({key[:2] for key in found}, {(Tag.C3_SEP, Role.SAME_DAY_ACT),
                                                      (Requirement.COMBINATION, Role.SESSION_ACT),
                                                      (Requirement.BUNDLING, Role.WHOLE)})
        snare = [read for read in RULES[Tag.C3_SEP].reads if read.attribute is Attribute.KIND
                 and read.kinds is not None and Kind.SNARE in read.kinds]
        self.assertEqual([read.paths for read in snare], [frozenset({R.Path.READY})])


class DependencyTests(SimpleTestCase):
    def test_a_dilations_device_is_outside_43239s_closure_and_inside_43249s(self):
        # 4.9: "A dilation whose device is unknown holds 43249 and nothing else; 43239's biopsy stands."
        biopsy, dilation = R.dependencies('43239'), R.dependencies('43249')
        self.assertNotIn(Kind.DILATION, biopsy.kinds | biopsy.statement_kinds)
        self.assertNotIn(Role.SESSION_ACT, biopsy.reads)  # no base arm: its session's other acts are outside
        self.assertIn(Kind.DILATION, dilation.kinds)
        self.assertIn(Attribute.TECHNIQUE_DEVICE, dilation.reads[Role.ACT])

    def test_a_read_of_act_kinds_no_candidate_can_be_is_outside_the_closure(self):
        biopsy, bleeding = R.dependencies('43239'), R.dependencies('43255')
        for attribute in (Attribute.CAUSE, Attribute.CAUSE_EVENT, Attribute.PURPOSE, Attribute.TARGET_DUCT,
                          Attribute.YIELD, Attribute.TECHNIQUE_ROUTE):
            self.assertNotIn(attribute, biopsy.reads[Role.ACT])
        self.assertTrue({Attribute.CAUSE, Attribute.PURPOSE} <= bleeding.reads[Role.ACT])
        # a visit has no target (D195): its lesion and places are outside an E/M code's closure
        self.assertFalse({Attribute.TARGET_LESION, Attribute.TARGET_PLACES} & R.dependencies('99214').reads[Role.ACT])

    def test_the_closures_roles_follow_4_9(self):
        base, act, em = R.dependencies('45378'), R.dependencies('45385'), R.dependencies('99214')
        self.assertIn(Role.SESSION_ACT, base.reads)  # base_included: its session's acts
        self.assertNotIn(Role.SESSION_ACT, act.reads)
        self.assertTrue({Role.SAME_DAY_ACT, Role.VISIT} <= set(em.reads))  # the same-day rule and the visit
        self.assertNotIn(Role.SAME_DAY_ACT, act.reads)
        self.assertTrue(em.member and base.member)  # R6:context, and the member date of R7
        self.assertNotIn(Attribute.PERFORMER, em.reads[Role.SAME_DAY_ACT])  # C-3 reads no performer
        self.assertTrue({Attribute.REACHED, Attribute.COMPLETION, Attribute.REACHED_ANATOMY} <= act.reads[Role.SESSION])
        self.assertEqual(R.dependencies('45341').reads[Role.ANATOMY], {Attribute.TYPE})  # LOWER's stoma
        self.assertEqual(R.dependencies('45385').reads[Role.ANATOMY], {Attribute.SUBTYPE})  # COLFULL's anastomosis
        for held in ('99152', '99153', '12345'):
            found = R.dependencies(held)
            self.assertEqual(set(found.reads), {Role.ENCOUNTER, Role.MEMBER} | ({Role.COUNTED} if held == '99153'
                                                                                else set()))
            self.assertEqual((found.kinds, found.statement_kinds), (frozenset(), frozenset()))
        self.assertIn(Attribute.TARGET_PLACES, R.dependencies('46221').reads[Role.ACT])  # route (b)'s regions

    def test_xchgs_counterparts_are_read_as_support_reads_an_act(self):
        # The arbiter's 1f#2 (its probe4): 43276 is met by a stent removal and a stent placement EACH SUPPORTING it
        # (4.3's XCHG row), so a placement's date relation moved to earlier_date, or a paired "No stent was placed."
        # (kind stent), changes 43276 and must lie inside its closure; 43274 and 43275 read the same counterparts
        # (D105's _stent_side: status, date relation, performer, duct)
        stent = frozenset({Kind.STENT, Kind.STENT_REMOVAL, Kind.STENT_EXCHANGE})
        support = {read.attribute for requirement in R.TEMPLATE_HEAD[Template.ACT]
                   for read in RULES[requirement].reads
                   if read.role is Role.ACT and (read.kinds is None or read.kinds & stent)}
        self.assertTrue({Attribute.KIND, Attribute.STATUS, Attribute.DATE_RELATION, Attribute.PERFORMER,
                         Attribute.ENTRY, Attribute.SESSION} <= support)
        for code in ('43274', '43275', '43276'):
            with self.subTest(code=code):
                closure = R.dependencies(code)
                self.assertEqual(closure.reads[Role.COUNTERPART], support | {Attribute.TARGET_DUCT})
                self.assertIn(Attribute.DATE_RELATION, closure.reads[Role.COUNTERPART])
                self.assertTrue({Kind.STENT, Kind.STENT_REMOVAL} <= closure.statement_kinds)
                self.assertTrue(closure.kinds <= closure.statement_kinds)
        # a code with no exchange row reads no counterpart, and its statements are its candidates' alone
        for code in ('43266', '43264'):
            closure = R.dependencies(code)
            self.assertNotIn(Role.COUNTERPART, closure.reads)
            self.assertEqual(closure.statement_kinds, R.statement_kinds(closure.kinds))
        self.assertNotIn(Kind.STENT, R.dependencies('43264').statement_kinds)

    def test_candidate_and_statement_kinds(self):
        self.assertEqual(R.dependencies('45381').kinds, {Kind.INJECTION, Kind.TATTOO, Kind.INTERVENTION})
        self.assertEqual(R.dependencies('43255').kinds,
                         {Kind.BLEEDING_CONTROL, Kind.CLIP, Kind.INJECTION, Kind.INTERVENTION})
        self.assertEqual(R.dependencies('45385').kinds, {Kind.SNARE, Kind.REMOVAL, Kind.INTERVENTION})
        self.assertEqual(R.dependencies('45378').kinds, {Kind.EXAMINATION})
        self.assertEqual(R.dependencies('99214').kinds, {Kind.EM_VISIT})
        self.assertEqual(R.dependencies('43265').kinds, {Kind.LITHOTRIPSY, Kind.INTERVENTION})  # D27
        for code in CODES:
            found = R.dependencies(str(code))
            if Role.STATEMENT in found.reads:  # a statement of an act's own kind pairs with it (4.5)
                self.assertLessEqual(found.kinds, found.statement_kinds)
        self.assertEqual(R.statement_kinds(frozenset({Kind.SNARE})), {Kind.SNARE, Kind.REMOVAL, Kind.INTERVENTION})
        self.assertEqual(R.statement_kinds(frozenset({Kind.TATTOO})), {Kind.TATTOO, Kind.INJECTION, Kind.INTERVENTION})


class BoundaryTests(SimpleTestCase):
    def test_both_modules_keep_measure_4(self):
        for name, path in MODULES.items():
            with self.subTest(module=name):
                self.assertEqual(measure_4(path.read_text(encoding='utf-8'), engine=True), [])

    def test_requirements_imports_no_v1_module(self):
        code = ('import sys\n'
                'import studio.interpretation.engine.requirements\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=60, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip().split(','),
                         ['studio', 'studio.interpretation', 'studio.interpretation.contract',
                          'studio.interpretation.contract.jsonschema', 'studio.interpretation.contract.types',
                          'studio.interpretation.engine', 'studio.interpretation.engine.anatomy',
                          'studio.interpretation.engine.catalogue', 'studio.interpretation.engine.requirements',
                          'studio.interpretation.engine.requirements_table'])

    def test_mypy_strict_passes_on_both_modules(self):
        result = subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull,
                                 'studio/interpretation/engine/requirements.py',
                                 'studio/interpretation/engine/requirements_table.py'],
                                capture_output=True, text=True, timeout=300, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 2 source files', result.stdout)

    def test_no_file_of_the_step_cites_the_report_decisions_records(self):
        # D207: every builder's report was refused by the harness; the readings are DECISIONS D207's, and a citation of
        # the report names nothing that exists (the name is spelled apart so this file does not hold it)
        report = 'REPORT' + '.md'
        for path in STEP_FILES:
            with self.subTest(file=path.name):
                self.assertNotIn(report, path.read_text(encoding='utf-8'))
        self.assertIn('DECISIONS D207', Path(__file__).read_text(encoding='utf-8'))
