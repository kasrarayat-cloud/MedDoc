"""contract/appraise_read.py: the strict reader of pass 2's answer (docs/gemini-migration/FINAL-V2.md 3.2.4, 3.2.5, 2.4
and 1.8; step 2c of 8.1). TEXT-ONLY and SYNTHETIC: the claim sets are tests/v2/test_claims.py's, built from its notes.

Proved, item by item (9.3: "extract_read, appraise_read: every refusal stage and bound by count; item-level demotions;
the evidence check"): each refusal stage (json, schema, bounds) with a planted case, each bound by count; the item-level
findings (an unknown claim id ignored, a repeated one read for none, a missing verdict, an unknown evidence unit
ignoring the evidence, an unlisted entry kept with its unknown units and session dropped); the evidence attachment check
of 3.2.5; every verdict bound to its claim's content key [R:MO-5]; the pin; 5.7 measure 4.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract import appraise_read, appraise_schema, extract_read, jsonschema, segment
from studio.interpretation.contract.types import Attached, Kind, Qualifier2, UnlistedWhat, VerdictValue
from tests.v2 import test_claims as fixtures
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'contract' / 'appraise_read.py'
PIN = {'APPRAISAL_LOCAL_SCHEMA_SHA256': jsonschema.sha256_of(appraise_schema.LOCAL_SCHEMA)}
UNITS = len(segment.units(fixtures.NOTE))


def claim_set():
    return fixtures.build(fixtures.NOTE, fixtures.note_answer())


def answer_for(claims_, **change):
    """A valid answer: every claim supported, attached, its first cited unit as evidence; no unlisted entry."""
    data = {'verdicts': [{'claim': claim.id, 'verdict': 'supports', 'attached': 'yes', 'qualifiers': [],
                          'evidence': [claim.units[0]]} for claim in claims_.claims],
            'unlisted': []}
    data.update(change)
    return data


def read(data, claims_=None, units=UNITS):
    with mock.patch.multiple(interpretation, **PIN):
        return appraise_read.read(data if isinstance(data, str) else json.dumps(data), claims_ or claim_set(), units)


class WholeAnswerTests(SimpleTestCase):
    def test_a_valid_answer_is_read(self):
        claims_ = claim_set()
        found = read(answer_for(claims_), claims_)
        self.assertIsInstance(found, appraise_read.ReadAppraisal)
        self.assertEqual([item.claim for item in found.verdicts], [claim.id for claim in claims_.claims])
        self.assertTrue(all(item.verdict is not None and not item.findings for item in found.verdicts))
        self.assertTrue(all(item.attached_evidence for item in found.verdicts))
        self.assertEqual(found.unknown, ())

    def test_every_refusal_stage_with_a_planted_case(self):
        claims_ = claim_set()
        cases = {
            'json': [None, '{"verdicts": [', '{"verdicts": [], "verdicts": [], "unlisted": []}',
                     '{"verdicts": [], "unlisted": [], "x": NaN}'],
            'schema': [answer_for(claims_, extra=1), {'verdicts': []},
                       answer_for(claims_, unlisted=[{'units': [], 'what': 'plan', 'kind': '', 'session': ''}])],
        }
        for stage, plants in cases.items():
            for plant in plants:
                with self.subTest(stage=stage, plant=str(plant)[:40]):
                    with mock.patch.multiple(interpretation, **PIN):
                        found = appraise_read.read(plant if plant is None or isinstance(plant, str)
                                                   else json.dumps(plant), claims_, UNITS)
                    self.assertIsInstance(found, extract_read.Refusal)
                    self.assertEqual(found.stage, stage)
                    self.assertTrue(found.reason.startswith(extract_read.REFUSED))

    def test_every_bound_by_count(self):
        claims_ = claim_set()
        count = len(claims_.claims)
        too_many = answer_for(claims_)
        too_many['verdicts'].append(dict(too_many['verdicts'][0]))
        evidence = answer_for(claims_)
        evidence['verdicts'][3]['evidence'] = ['S1'] * 9
        unlisted = answer_for(claims_, unlisted=[{'units': ['S1'], 'what': 'act', 'kind': '', 'session': ''}] * 33)
        for plant, words in ((too_many, f'gives {count + 1:,} verdicts, more than the {count:,} claims'),
                             (evidence, 'verdicts[3].evidence lists 9 units, more than the 8 one verdict may cite'),
                             (unlisted, 'unlisted lists 33 statements, more than the 32')):
            with self.subTest(words=words):
                found = read(plant, claims_)
                self.assertIsInstance(found, extract_read.Refusal)
                self.assertEqual(found.stage, 'bounds')
                self.assertIn(words, found.reason)
        # at the bounds exactly, nothing is refused
        evidence['verdicts'][3]['evidence'] = ['S1'] * 8
        self.assertIsInstance(read(evidence, claims_), appraise_read.ReadAppraisal)
        self.assertIsInstance(read(answer_for(claims_, unlisted=unlisted['unlisted'][:32]), claims_),
                              appraise_read.ReadAppraisal)

    def test_the_refusal_never_repeats_the_models_text(self):
        found = read('{"verdicts": [{"claim": "K1", "verdict": "SECRET-WORDS"}], "unlisted": []}')
        self.assertIsInstance(found, extract_read.Refusal)
        self.assertNotIn('SECRET-WORDS', found.reason)


class ItemTests(SimpleTestCase):
    def test_unknown_repeated_and_missing_claims(self):
        claims_ = claim_set()
        data = answer_for(claims_)
        first, second = data['verdicts'][0]['claim'], data['verdicts'][1]['claim']
        data['verdicts'][1] = dict(data['verdicts'][0])  # the first claim twice; the second claim missing
        data['verdicts'][2] = dict(data['verdicts'][2], claim='K999')  # names no claim
        found = read(data, claims_)
        self.assertEqual(found.unknown, (2,))
        self.assertEqual(found.verdict(first).findings, (appraise_read.VerdictFinding.REPEATED,))
        self.assertIsNone(found.verdict(first).verdict)
        self.assertEqual(found.verdict(second).findings, (appraise_read.VerdictFinding.MISSING,))
        third = claims_.claims[2].id
        self.assertEqual(found.verdict(third).findings, (appraise_read.VerdictFinding.MISSING,))
        others = [item for item in found.verdicts if item.claim not in (first, second, third)]
        self.assertTrue(others and all(item.verdict is not None for item in others))

    def test_an_unknown_evidence_unit_ignores_the_evidence(self):
        claims_ = claim_set()
        data = answer_for(claims_)
        data['verdicts'][0]['evidence'] = [claims_.claims[0].units[0], f'S{UNITS + 1}']
        found = read(data, claims_).verdicts[0]
        self.assertEqual(found.findings, (appraise_read.VerdictFinding.EVIDENCE_UNKNOWN,))
        self.assertEqual(found.verdict.evidence, ())
        self.assertFalse(found.attached_evidence)  # fail-closed: a supports resting on it does not count

    def test_the_verdict_is_read_as_given_and_bound_to_its_content_key(self):
        claims_ = claim_set()
        data = answer_for(claims_)
        data['verdicts'][0].update(verdict='qualified', attached='unclear', qualifiers=['history_only', 'reported'])
        found = read(data, claims_)
        verdict = found.verdicts[0].verdict
        self.assertEqual((verdict.verdict, verdict.attached, verdict.qualifiers),
                         (VerdictValue.QUALIFIED, Attached.UNCLEAR, (Qualifier2.HISTORY_ONLY, Qualifier2.REPORTED)))
        for item, claim in zip(found.verdicts, claims_.claims):
            self.assertEqual((item.claim, item.content), (claim.id, claim.content))

    def test_unlisted_entries_are_kept(self):
        claims_ = claim_set()
        session_card = next(card.id for card in claims_.cards if card.type.value == 'session')
        data = answer_for(claims_, unlisted=[
            {'units': ['S4', f'S{UNITS + 3}'], 'what': 'act', 'kind': 'snare', 'session': session_card},
            {'units': ['S7'], 'what': 'denial', 'kind': '', 'session': ''},
            {'units': [f'S{UNITS + 1}'], 'what': 'doubt', 'kind': 'biopsy', 'session': 'X9'}])
        found = read(data, claims_).unlisted
        self.assertEqual(len(found), 3)
        self.assertEqual((found[0].unlisted.units, found[0].unlisted.what, found[0].unlisted.kind,
                          found[0].unlisted.session, found[0].session, found[0].findings),
                         (('S4',), UnlistedWhat.ACT, Kind.SNARE, session_card, 'X1',
                          (appraise_read.UnlistedFinding.UNIT_UNKNOWN,)))
        self.assertEqual((found[1].unlisted.kind, found[1].unlisted.session, found[1].session, found[1].findings),
                         (None, None, None, ()))
        self.assertEqual((found[2].unlisted.units, found[2].unlisted.session, found[2].findings),
                         ((), None, (appraise_read.UnlistedFinding.UNIT_UNKNOWN,
                                     appraise_read.UnlistedFinding.SESSION_UNKNOWN)))


class EvidenceTests(SimpleTestCase):
    def test_supports_counts_only_with_evidence_in_the_claim_or_its_card(self):
        claims_ = claim_set()
        # an inherited fact: the claim cites the section's units (S1-S3), the card the act's own sentence (S6)
        date = next(item for item in claims_.appraised if item.key.object == 'E2'
                    and item.key.attribute.value == 'date_relation')
        claim = claims_.claim(date.claim)
        card = claims_.card(claims_.about[date.claim])
        self.assertEqual((claim.units, card.units), (('S1', 'S2', 'S3'), ('S6',)))
        for evidence, attached in ((('S2',), True), (('S6',), True), (('S4',), False), ((), False),
                                   (('S4', 'S6'), True)):
            with self.subTest(evidence=evidence):
                self.assertIs(appraise_read.attached_evidence(claims_, date.claim, evidence), attached)
        # the document's own claim (the date of service) has no card: its cited units alone count
        when = next(item for item in claims_.appraised if item.key.attribute.value == 'date_of_service')
        self.assertEqual(claims_.about[when.claim], '')
        self.assertTrue(appraise_read.attached_evidence(claims_, when.claim, ('S2',)))
        self.assertFalse(appraise_read.attached_evidence(claims_, when.claim, ('S6',)))
        self.assertFalse(appraise_read.attached_evidence(claims_, 'K999', ('S2',)))

    def test_the_check_is_carried_on_every_read_verdict(self):
        # without the history's removal (an umbrella, claimed since DECISIONS D194), no claim of the note cites the
        # History part (S4) and no card shows it
        note = fixtures.note_answer()
        note['events'] = [event for event in note['events'] if event['id'] != 'E4']
        claims_ = fixtures.build(fixtures.NOTE, note)
        self.assertFalse([claim for claim in claims_.claims if 'S4' in claim.units])
        self.assertFalse([card for card in claims_.cards if 'S4' in card.units])
        data = answer_for(claims_)
        for verdict in data['verdicts']:
            verdict['evidence'] = ['S4']
        found = read(data, claims_)
        self.assertTrue(all(not item.attached_evidence for item in found.verdicts))


class PinAndGuardTests(SimpleTestCase):
    def test_no_answer_is_read_under_an_empty_or_changed_pin(self):
        claims_ = claim_set()
        # step 0b's placeholder, planted: the integration owner has written the pin (DECISIONS D202, triage INT-5)
        with mock.patch.object(interpretation, 'APPRAISAL_LOCAL_SCHEMA_SHA256', ''):
            with self.assertRaisesMessage(RuntimeError, 'has no pin yet'):
                appraise_read.read(json.dumps(answer_for(claims_)), claims_, UNITS)
        # until the first recording under the label a changed schema needs only its pin recomputed (DECISIONS D202)
        with mock.patch.object(interpretation, 'APPRAISAL_LOCAL_SCHEMA_SHA256', '0' * 64):
            with self.assertRaisesMessage(RuntimeError, 'no longer matches'):
                appraise_read.read(json.dumps(answer_for(claims_)), claims_, UNITS)
        self.assertIn(interpretation.APPRAISAL_LOCAL_SCHEMA_SHA256, ('', PIN['APPRAISAL_LOCAL_SCHEMA_SHA256']))
        with self.assertRaises(ValueError):
            read(answer_for(claims_), claims_, units=-1)

    def test_measure_4_holds(self):
        source = MODULE.read_text(encoding='utf-8')
        self.assertEqual(measure_4(source, engine=False), [])
        imported = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {'__future__', 'collections.abc', 'dataclasses', 'enum', 'typing', 'studio',
                                    'studio.interpretation.contract', 'studio.interpretation.contract.extract_read',
                                    'studio.interpretation.contract.types', 'studio.participants'})
