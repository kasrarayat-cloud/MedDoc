"""DECISIONS D296 (P1-LESION): the lesion pair claim (FINAL-V2 4.2 as amended). TEXT-ONLY and SYNTHETIC: every note here
is written for these tests (fictional clinicians), every pass-1 answer is built by hand with test_settle's builders and
every pass-2 answer by an oracle; nothing is sent anywhere.

What is proved:
- claims: under gemini-appraisal@2 a statement whose target names a lesion, against each act its pair controls ask about
  whose target names a different lesion, asks "Lesions {L} and {M} are different lesions." with its contrary "... are
  the same lesion.", citing both lesions' description runs; each lesion pair once, however many statements and acts
  meet it; none where pass 1 wrote a same_as or distinct_from between the two or doubted either's; none under
  gemini-appraisal@1 (R2LClaimsTests);
- settle: the pair is established (supported) only when pass 2 supports the claim and rejects the control; a split
  polyp (pass 2 supports the sameness), an incoherent pair (both supported), an uninformative one (both rejected) and a
  missing verdict leave it unresolved (R2LSettleTests);
- store: the @3 row keeps the settled pairs bound to their two stored claims; an older pair's row drops settle's empty
  list and refuses a non-empty one (R2LStoreTests);
- engine: facts.apart_by_lesion reads an established pair as a written distinct_from, the pair controls still required
  rejected (R2LEngineTests);
- end to end (extract_read -> checks -> claims -> pass 2 -> settle -> store -> assess): a denial of an intervention on an
  unplaced group of polyps beside cold-snare removals of placed single polyps leaves the polypectomy READY under a
  faithful pass 2 and held under every other verdict pattern (R2LPipelineTests).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid

from django.test import SimpleTestCase

from studio import interpretation, jobs
from studio.interpretation import store
from studio.interpretation.contract import appraise_prompt, appraise_read, checks, extract_read, segment, settle
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.engine import assess as engine_assess
from studio.interpretation.engine import derive
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Attribute, Id
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from tests.v2.test_settle import USAGE, colonoscopy, doubt, event, fact, faithful, lesion, src, verdict

V3 = interpretation.APPRAISAL_VERSION_V3

# A cold-snare removal of two placed single polyps and a denial of any intervention on an unplaced group of polyps.
NOTE = ('SYNTHETIC COLONOSCOPY NOTE\n'                                                        # S1: N0
        'Date of service: 03/14/2031\n'                                                       # S2
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                       # S3
        '\n'
        'Findings: The colonoscope was advanced to the cecum.\n'                              # S4: N1, E1
        'A 6 mm polyp in the ascending colon was removed with a cold snare.\n'                # S5: E2 on L1
        'A 5 mm polyp in the transverse colon was removed with a cold snare.\n'               # S6: E3 on L2
        'Several diminutive polyps were seen; no intervention was performed on them.\n'       # S7: E4 denies, on L3
        'No snare polypectomy was performed on them either.\n')                                # S8: E5 denies, on L3
# One polyp told twice: a removal, and a sentence about "this polyp" pass 1 files as a second lesion (R06b's split).
SPLIT = ('SYNTHETIC COLONOSCOPY NOTE\n'                                                       # S1
         'Date of service: 03/14/2031\n'                                                      # S2
         'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                      # S3
         '\n'
         'Findings: The colonoscope was advanced to the cecum.\n'                             # S4
         'A 6 mm polyp in the ascending colon was removed with a cold snare.\n'               # S5: E2 on L1
         'No other intervention was performed on this polyp.\n')                              # S6: E3 denies, on L2


def removal(eid, unit, lid, words, place, place_words):
    return event(eid, [unit], 'cold snare', 'was removed', 'snare', session=[fact('X1', src([unit]))],
                 target__lesion=[fact(lid, src([unit], words))], target__places=[fact(place, src([unit], place_words))],
                 technique__device=[fact('cold_snare', src([unit], 'cold snare'))])


def denial(eid, unit, kind, kind_words, status_words, lid, lesion_words, breadth_words):
    return event(eid, [unit], kind_words, status_words, kind, state='negated',
                 status_source=src([unit], status_words), session=[fact('X1', src([unit]))],
                 scope__breadth=[fact('single_target', src([unit], breadth_words))],
                 target__lesion=[fact(lid, src([unit], lesion_words))])


def note_answer(*, extra_lesions=(), second_denial=True, **l3_fields):
    """NOTE's answer: the colonoscopy X1 (E1) to the cecum; E2 and E3 remove L1 (ascending colon) and L2 (transverse
    colon); E4 denies any intervention on L3 (a group, no place) and, with ``second_denial``, E5 any snare polypectomy on
    it. ``l3_fields`` set L3's other fields (same_as, distinct_from)."""
    events = [removal('E2', 'S5', 'L1', 'A 6 mm polyp', 'ascending_colon', 'ascending colon'),
              removal('E3', 'S6', 'L2', 'A 5 mm polyp', 'transverse_colon', 'transverse colon'),
              denial('E4', 'S7', 'intervention', 'intervention', 'was performed', 'L3', 'Several diminutive polyps',
                     'on them')]
    if second_denial:
        events.append(denial('E5', 'S8', 'snare', 'snare polypectomy', 'was performed', 'L3', 'them', 'on them'))
    lesions = [lesion('L1', src(['S5'], 'A 6 mm polyp'), multiplicity=[fact('single', src(['S5'], 'A 6 mm polyp'))],
                      places=[fact('ascending_colon', src(['S5'], 'ascending colon'))]),
               lesion('L2', src(['S6'], 'A 5 mm polyp'), multiplicity=[fact('single', src(['S6'], 'A 5 mm polyp'))],
                      places=[fact('transverse_colon', src(['S6'], 'transverse colon'))]),
               lesion('L3', src(['S7'], 'Several diminutive polyps'),
                      multiplicity=[fact('group', src(['S7'], 'Several diminutive polyps'))], **l3_fields),
               *extra_lesions]
    return colonoscopy(NOTE, *events, lesions=lesions)


def split_answer():
    """SPLIT's answer as a reader that splits one polyp files it: E2 removes L1, E3 denies any intervention on L2."""
    return colonoscopy(
        SPLIT, removal('E2', 'S5', 'L1', 'A 6 mm polyp', 'ascending_colon', 'ascending colon'),
        denial('E3', 'S6', 'intervention', 'intervention', 'was performed', 'L2', 'this polyp', 'on this polyp'),
        lesions=[lesion('L1', src(['S5'], 'A 6 mm polyp'), multiplicity=[fact('single', src(['S5'], 'A 6 mm polyp'))],
                        places=[fact('ascending_colon', src(['S5'], 'ascending colon'))]),
                 lesion('L2', src(['S6'], 'this polyp'), multiplicity=[fact('single', src(['S6'], 'this polyp'))])])


def read_answer(text, data):
    found = extract_read.read(json.dumps(data), len(segment.units(text)))
    assert not isinstance(found, extract_read.Refusal), found
    return found


def request(text, data, version=V3):
    """Pass 1's answer read and checked, and the appraisal request built under ``version`` (the Fable path's by
    default: appraise_prompt.build_request_fable)."""
    read = read_answer(text, data)
    checked = checks.check(text, (), read)
    build = appraise_prompt.build_request_fable if version == V3 else appraise_prompt.build_request
    return read, checked, build(text, (), 'txt', read, findings=checked.findings)


def lesion_oracle(claim_value='supports', control_value='contradicts', pair_controls='contradicts'):
    """Pass 2: the lesion pair claims and their controls answered as given (None leaves them without a verdict), the
    act-lesion pair controls as ``pair_controls``, every other claim faithfully (test_settle.faithful)."""
    def oracle(claim, role, claim_set):
        pairs = getattr(claim_set, 'lesion_pairs', ())
        for value, ids in ((claim_value, {pair.claim for pair in pairs}),
                           (control_value, {pair.control for pair in pairs})):
            if claim.id in ids:
                return None if value is None else verdict(claim, value)
        if role == 'pair_control':
            return verdict(claim, pair_controls)
        return faithful(claim, role, claim_set)
    return oracle


def roles(claim_set):
    from tests.v2.test_settle import roles_of
    return roles_of(claim_set)


def settled(text, data, oracle):
    read, checked, built = request(text, data)
    claim_set = built.claim_set
    found = roles(claim_set)
    answer = {'verdicts': [item for item in (oracle(claim, found[claim.id], claim_set) for claim in claim_set.claims)
                           if item is not None], 'unlisted': []}
    appraisal = appraise_read.read(json.dumps(answer), claim_set, len(segment.units(text)))
    assert not isinstance(appraisal, extract_read.Refusal), appraisal
    out = settle.settle(read, checked, claim_set, built.indistinct, appraisal, USAGE, appraisal_version=V3)
    assert not isinstance(out, settle.Unhealthy), out
    return claim_set, out


def row(text, out, versions=None):
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return store.row_v2(encounter_id=uuid.UUID(int=1), revision_id=uuid.UUID(int=2), provider_run_id=uuid.UUID(int=3),
                        appraisal_run_id=uuid.UUID(int=4), revision_text=text, text_sha256=sha,
                        request_sha256='2' * 64, response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                        appraisal_response_sha256='5' * 64, events=out.events, verification=out.verification,
                        versions=jobs.V2_VERSIONS if versions is None else versions)


def view(text, fields):
    sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return store.textfree_v2(store.load_v2(fields, text_sha256=sha, response_sha256='3' * 64,
                                           appraisal_response_sha256='5' * 64))


class _NoReference:
    def lookup(self, code, service_date):
        from types import SimpleNamespace
        return SimpleNamespace(pfs=None, mue=None)


def status(text, data, oracle, code='45385', quote='A 6 mm polyp in the ascending colon was removed with a cold snare.'):
    """The code's status end to end: pass 1 read, checked, claimed under @2, appraised by ``oracle``, settled, stored at
    the product's pair, derived and assessed."""
    _claim_set, out = settled(text, data, oracle)
    inventory = view(text, row(text, out))
    effective = derive.derive(inventory, {}).effective
    at = text.index(quote)
    proposals = NormalizedResponse('replay', 'test@1', (ProviderCode(
        'selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING', (EvidenceSpan(0, at, at + len(quote), quote, True),)),))
    found = engine_assess.assess(
        inventory=inventory, date_of_service=datetime.date.fromisoformat(effective) if effective else None, text=text,
        pages=(), integrity=jobs._Integrity(), provider_status='succeeded', proposals=proposals,
        reference=_NoReference(), member=engine_assess.MemberContext(), label=lambda session: str(session.id))
    statuses = [item.status.value for item in found.codes if item.code == code]
    assert len(statuses) == 1, statuses
    return statuses[0]


class R2LClaimsTests(SimpleTestCase):
    def setUp(self):
        self.claim_set = request(NOTE, note_answer())[2].claim_set

    def test_a_denial_beside_removals_asks_one_claim_per_lesion_pair(self):
        pairs = self.claim_set.lesion_pairs
        self.assertEqual(sorted((pair.lesion, pair.other) for pair in pairs), [('L3', 'L1'), ('L3', 'L2')])
        cards = {object_: card for card, object_ in self.claim_set.objects.items()}
        for pair in pairs:
            claim, control = self.claim_set.claim(pair.claim), self.claim_set.claim(pair.control)
            # DECISIONS D300 RF-L3 (round r2c): L3 is a group and the removed L1 and L2 single, so the pair asks the
            # membership of the act's lesion among the statement's (D296's distinctness forms before D300)
            self.assertEqual((claim.template, control.template), ('lesion.not_member', 'lesion.member'))
            self.assertEqual((claim.subject, claim.value, control.subject, control.value),
                             (pair.lesion, pair.other, pair.lesion, pair.other))
            first, second = cards[(xs.Family.LESION, pair.lesion)], cards[(xs.Family.LESION, pair.other)]
            self.assertEqual(self.claim_set.sentences[pair.claim],
                             f'Lesion {second} is not one of the lesions of {first}.')
            self.assertEqual(self.claim_set.sentences[pair.control], f'Lesion {second} is one of the lesions of {first}.')
            self.assertIn(pair.control, self.claim_set.controls)
            self.assertNotIn(pair.claim, self.claim_set.controls)
            # both lesions' description runs, nothing of any act
            self.assertEqual(set(claim.units), {'S7', 'S5' if pair.other == 'L1' else 'S6'})

    def test_the_count_is_one_claim_per_lesion_pair_whatever_meets_it(self):
        # two denials of L3 (E4, E5) against two removals (E2, E3): four statement-act pairs, two lesion pairs
        lone = request(NOTE, note_answer(second_denial=False))[2].claim_set
        self.assertEqual(len(self.claim_set.lesion_pairs), 2)
        self.assertEqual(len(lone.lesion_pairs), 2)
        self.assertEqual(len({pair.claim for pair in self.claim_set.lesion_pairs}), 2)
        self.assertEqual(len(self.claim_set.claims) - len(lone.claims) > 0, True)  # E5's own claims, no lesion pair more
        lesion_claims = [claim for claim in self.claim_set.claims  # D300 RF-L3: the membership forms (L3 a group)
                         if claim.template in ('lesion.not_member', 'lesion.member')]
        self.assertEqual(len(lesion_claims), 4)

    def test_a_written_same_as_or_distinct_from_asks_none(self):
        written = note_answer(distinct_from=[fact('L1', src(['S7'], 'Several diminutive polyps'))])
        self.assertEqual([(pair.lesion, pair.other) for pair in request(NOTE, written)[2].claim_set.lesion_pairs],
                         [('L3', 'L2')])
        denied = note_answer(same_as=[fact('L2', src(['S7'], 'Several diminutive polyps'), state='negated')])
        self.assertEqual([(pair.lesion, pair.other) for pair in request(NOTE, denied)[2].claim_set.lesion_pairs],
                         [('L3', 'L1')])
        data = note_answer()
        data['doubts'] = [doubt('identity', ['L3'], ['S7'], 'unclear')]
        self.assertEqual(request(NOTE, data)[2].claim_set.lesion_pairs, ())

    def test_none_under_gemini_appraisal_at_1(self):
        claim_set = request(NOTE, note_answer(), version=interpretation.APPRAISAL_VERSION)[2].claim_set
        self.assertEqual(claim_set.lesion_pairs, ())
        self.assertFalse(any(claim.template in ('lesion.distinct_from', 'lesion.same_as') for claim in claim_set.claims))


class R2LSettleTests(SimpleTestCase):
    def outcomes(self, oracle):
        claim_set, out = settled(NOTE, note_answer(), oracle)
        return {(item['lesion'], item['other']): (item['result'], tuple(item['reasons']))
                for item in out.events['lesion_pairs']}

    def test_established_only_when_the_claim_is_supported_and_its_control_rejected(self):
        self.assertEqual(self.outcomes(lesion_oracle()),
                         {('L3', 'L1'): ('supported', ()), ('L3', 'L2'): ('supported', ())})

    def test_every_other_verdict_pattern_leaves_it_unresolved(self):
        for name, oracle in (('split: the sameness supported', lesion_oracle('contradicts', 'supports')),
                             ('incoherent: both supported', lesion_oracle('supports', 'supports')),
                             ('uninformative: both rejected', lesion_oracle('contradicts', 'contradicts')),
                             ('the control unanswered', lesion_oracle('supports', None)),
                             ('unclear', lesion_oracle('unclear', 'contradicts'))):
            with self.subTest(case=name):
                found = self.outcomes(oracle)
                self.assertEqual({result for result, _reasons in found.values()}, {'unresolved'})
                self.assertTrue(all(reasons for _result, reasons in found.values()))

    def test_the_pair_is_stored_as_a_claim_and_a_control(self):
        claim_set, out = settled(NOTE, note_answer(), lesion_oracle())
        stored = {item.id: item for item in out.events['claims']}
        for pair in claim_set.lesion_pairs:
            self.assertEqual((stored[pair.claim].role.value, stored[pair.control].role.value), ('claim', 'control'))
            self.assertEqual((stored[pair.claim].attribute, stored[pair.control].attribute),
                             (Attribute.DISTINCT_FROM, Attribute.SAME_AS))


class R2LStoreTests(SimpleTestCase):
    def test_the_at_3_row_keeps_the_pairs_bound_to_their_claims(self):
        _claim_set, out = settled(NOTE, note_answer(), lesion_oracle())
        fields = row(NOTE, out)
        self.assertEqual(len(fields['events']['lesion_pairs']), 2)
        R = F.factset(view(NOTE, fields))
        self.assertIs(R.pair_controls[(Id.parse('L3'), Attribute.DISTINCT_FROM, Id.parse('L1'))], True)

    def test_a_pair_naming_no_stored_claim_of_its_form_is_refused(self):
        _claim_set, out = settled(NOTE, note_answer(), lesion_oracle())
        events = dict(out.events)
        events['lesion_pairs'] = [dict(item) for item in out.events['lesion_pairs']]
        events['lesion_pairs'][0]['control'] = events['lesion_pairs'][0]['claim']
        with self.assertRaises(store.StoreError):
            store.row_v2(encounter_id=uuid.UUID(int=1), revision_id=uuid.UUID(int=2), provider_run_id=uuid.UUID(int=3),
                         appraisal_run_id=uuid.UUID(int=4), revision_text=NOTE,
                         text_sha256=hashlib.sha256(NOTE.encode('utf-8')).hexdigest(), request_sha256='2' * 64,
                         response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                         appraisal_response_sha256='5' * 64, events=events, verification=out.verification,
                         versions=jobs.V2_VERSIONS)

    def test_an_older_pair_drops_an_empty_list_and_refuses_a_held_one(self):
        _claim_set, out = settled(NOTE, note_answer(), lesion_oracle())
        with self.assertRaises(store.StoreError):
            row(NOTE, out, versions=store.READ_VERSIONS[0])
        # gemini-appraisal@1's claims ask no lesion pair: settle's empty list is no field of the older pair's row
        read, checked, built = request(NOTE, note_answer(), version=interpretation.APPRAISAL_VERSION)
        found = roles(built.claim_set)
        answer = {'verdicts': [faithful(claim, found[claim.id], built.claim_set) for claim in built.claim_set.claims],
                  'unlisted': []}
        appraisal = appraise_read.read(json.dumps(answer), built.claim_set, len(segment.units(NOTE)))
        older = settle.settle(read, checked, built.claim_set, built.indistinct, appraisal, USAGE, appraisal_version=V3)
        self.assertEqual(older.events['lesion_pairs'], [])
        fields = row(NOTE, older, versions=store.READ_VERSIONS[0])
        self.assertNotIn('lesion_pairs', fields['events'])
        self.assertEqual(F.factset(view(NOTE, fields)).pair_controls.get(
            (Id.parse('L3'), Attribute.DISTINCT_FROM, Id.parse('L1'))), None)


class R2LEngineTests(SimpleTestCase):
    def test_an_established_pair_sets_the_lesions_apart_with_the_pair_controls_rejected(self):
        _claim_set, out = settled(NOTE, note_answer(), lesion_oracle())
        R = F.factset(view(NOTE, row(NOTE, out)))
        E4, E2 = Id.parse('E4'), Id.parse('E2')
        self.assertTrue(F.apart_by_lesion(R, E4, E2))
        self.assertTrue(F.appraised_distinct(R, Id.parse('L1'), Id.parse('L3')))  # either orientation
        _claim_set, out = settled(NOTE, note_answer(), lesion_oracle(pair_controls='unclear'))
        R = F.factset(view(NOTE, row(NOTE, out)))
        self.assertTrue(F.appraised_distinct(R, Id.parse('L3'), Id.parse('L1')))
        self.assertFalse(F.apart_by_lesion(R, E4, E2), 'the pair controls are still required rejected')

    def test_an_unestablished_pair_sets_nothing_apart(self):
        _claim_set, out = settled(NOTE, note_answer(), lesion_oracle('contradicts', 'supports'))
        R = F.factset(view(NOTE, row(NOTE, out)))
        self.assertIs(R.pair_controls[(Id.parse('L3'), Attribute.DISTINCT_FROM, Id.parse('L1'))], False)
        self.assertFalse(F.apart_by_lesion(R, Id.parse('E4'), Id.parse('E2')))


class R2LPipelineTests(SimpleTestCase):
    def test_a_denial_on_an_unplaced_group_beside_removals_leaves_the_polypectomy_ready(self):
        self.assertEqual(status(NOTE, note_answer(), lesion_oracle()), 'ready')

    def test_the_split_polyp_stays_held(self):
        # R06b: pass 1 split one polyp; pass 2 rejects the act-lesion controls but supports the sameness
        oracle = lesion_oracle('contradicts', 'supports')
        self.assertEqual(status(SPLIT, split_answer(), oracle), 'needs_clarification')
        claim_set, _out = settled(SPLIT, split_answer(), oracle)
        self.assertEqual([(pair.lesion, pair.other) for pair in claim_set.lesion_pairs], [('L2', 'L1')])

    def test_an_incoherent_or_uninformative_pair_stays_held(self):
        for name, oracle in (('both supported', lesion_oracle('supports', 'supports')),
                             ('both rejected', lesion_oracle('contradicts', 'contradicts'))):
            with self.subTest(case=name):
                self.assertEqual(status(NOTE, note_answer(), oracle), 'needs_clarification')
