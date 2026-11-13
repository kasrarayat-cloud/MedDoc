"""The Reading-compatible accessor layer (docs/gemini-migration/FINAL-V2.md 4.1; step 2d of its 8.1), TEXT-ONLY and
SYNTHETIC: engine/reading.py keeps v1's names over the FactSet - Reading, usable (result supported), value (the claimed
value in any state), done (4.3 rows 2-5), the established other date and performer, own_spans, all_spans, anchors and
the label ids - each read here over a row the store wrote and read back, as the engine reads it: store.textfree_v2's
view (DECISIONS D188; tests/v2/test_facts.py's synthetic colonoscopy).
Every document here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import reading as RD
from studio.interpretation.engine.types import Id, IdFamily
from tests.v2.test_facts import (E1, E2, E3, E4, E5, L1, N2, X1, X2, Ledger, at, colonoscopy, est, fact, src, unit_span,
                                 view)

A = ct.Attribute


def reading(events=None, effective_date=...) -> RD.Reading:
    row = view(events if events is not None else colonoscopy())
    return RD.Reading(F.factset(row) if effective_date is ... else F.effective(row, effective_date))


class ReadingTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reading = reading()

    def test_the_reading_indexes_the_factset_in_pass_1s_order(self):
        r = self.reading
        self.assertEqual((r.events, r.sessions), ((E1, E2, E3, E4, E5), (X1, X2)))
        self.assertEqual(dict(r.order), {E1: 0, E2: 1, E3: 2, E4: 3, E5: 4})
        self.assertIs(RD.Reading.of(r), r)
        self.assertEqual(RD.Reading.of(r.facts).events, r.events)
        self.assertIs(r.fact(E2, A.KIND), F.fact(r.facts, E2, A.KIND))
        self.assertEqual(r.members(X1, A.REACHED), F.members(r.facts, X1, A.REACHED))
        self.assertIsNone(r.anchor(Id(IdFamily.EVENT, 9)))
        self.assertEqual(len(r.unlisted), 1)

    def test_usable_is_result_supported_and_value_the_claimed_value_in_any_state(self):
        r = self.reading
        self.assertTrue(RD.usable(r, E2, A.KIND))
        self.assertFalse(RD.usable(r, E3, A.STATUS))  # negated is established, never usable as a value
        self.assertFalse(RD.usable(r, E3, A.PERFORMER))  # doubted
        self.assertTrue(RD.usable(r, X1, A.REACHED))  # a list with a supported member
        self.assertFalse(RD.usable(r, X1, A.STATIONS))
        self.assertIs(RD.value(r, E3, A.STATUS), ct.Status.PERFORMED)  # the denied value
        self.assertIs(RD.value(r, E3, A.PERFORMER), ct.Performer.DOCUMENTING_TEAM)  # kept beside the doubt
        self.assertIs(RD.value(r, X2, A.KIND), ct.SessionKind.EUS)  # unresolved, the claimed value
        self.assertIsNone(RD.value(r, L1, A.MULTIPLICITY))  # contradicted: its values are its options
        self.assertIsNone(RD.value(r, E5, A.DATE_RELATION))  # silent
        self.assertTrue(RD.holds(r, X1, A.REACHED, ct.Extent.CECUM))

    def test_done_is_4_3_rows_2_to_5(self):
        r = self.reading
        self.assertEqual([RD.done(r, event) for event in r.events], [True, True, False, False, False])

        def changed(change):
            events = colonoscopy()
            k = Ledger()
            k.claims = events['claims']
            change(events['events'][1], k)
            return RD.done(reading(events), E2)

        # each row in turn fails E2, a done act
        self.assertTrue(changed(lambda e, k: e.update(status=est(k, 'E2', 'status', 'attempted_not_completed', [
            src(['S6'])], control='performed'))))  # begun counts (v1's POSITIVE)
        self.assertFalse(changed(lambda e, k: e.update(status=est(k, 'E2', 'status', 'planned', [src(['S6'])],
                                                                  control='performed'))))
        self.assertFalse(changed(lambda e, k: e.update(date_relation=est(
            k, 'E2', 'date_relation', 'earlier_date', [src(['S4'], 'section')], control='on_date_of_service'))))
        self.assertFalse(changed(lambda e, k: e.update(performer=fact('documenting_team', [src(['S3'])]))))
        self.assertFalse(changed(lambda e, k: e.update(entry=est(k, 'E2', 'entry', 'nursing', [src(['S5'],
                                                                                                   'section')],
                                                                 control='documenting_clinician'))))

    def test_done_reads_the_effective_facts(self):
        # under a member's other date the date relations L1 re-judges are no longer established: nothing is done
        r = reading(effective_date='2026-11-08')
        self.assertEqual([RD.done(r, event) for event in r.events], [False] * 5)
        self.assertEqual([RD.done(reading(effective_date='2026-11-09'), e) for e in r.events],
                         [True, True, False, False, False])

    def test_the_established_other_date_and_performer(self):
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        events['events'][1]['date_relation'] = est(k, 'E2', 'date_relation', 'earlier_date', [src(['S4'], 'section')],
                                                   control='on_date_of_service')
        events['events'][1]['performer'] = est(k, 'E2', 'performer', 'other_facility', [src(['S3'])],
                                               control='documenting_team')
        r = reading(events)
        self.assertTrue(RD.verified_other_time(r, E2) and RD.established_other_date(r, E2))
        self.assertTrue(RD.verified_other_performer(r, E2) and RD.established_other_performer(r, E2))
        for event in (E1, E3, E4, E5):  # on the date of service, doubted, or silent: never another
            with self.subTest(event=event):
                self.assertFalse(RD.verified_other_time(r, event) or RD.verified_other_performer(r, event))

    def test_own_spans_all_spans_and_anchors(self):
        r = self.reading
        self.assertEqual(RD.own_spans(r, E2), (unit_span(6),))  # kind, status and target: all in S6
        self.assertEqual(RD.all_spans(r, E2), (unit_span(2), unit_span(3), unit_span(6)))  # + timing and performer
        self.assertEqual(RD.anchors(r, E2), (unit_span(6),))
        self.assertEqual(RD.anchors(r, E5), (unit_span(11),))
        self.assertEqual(RD.anchors(r, Id(IdFamily.EVENT, 9)), ())

    def test_the_label_ids(self):
        r = self.reading
        self.assertEqual(RD.event_label(r, E2), RD.EventLabel(kind=ct.Kind.SNARE, family=None,
                                                               device=ct.Device.COLD_SNARE, lesion=L1, place=None))
        self.assertEqual(RD.event_label(r, E1), RD.EventLabel(kind=None, family=ct.SessionKind.COLONOSCOPY,
                                                               device=None, lesion=None, place=None))
        self.assertEqual(RD.event_label(r, E5), RD.EventLabel(kind=ct.Kind.BIOPSY, family=None, device=None,
                                                               lesion=None, place=ct.Landmark.TRANSVERSE_COLON))
        self.assertEqual(RD.lesion_label(r, L1), RD.LesionLabel(lesion=L1, place=ct.Landmark.SIGMOID_COLON))
        base = catalogue.code_link('45378')
        self.assertEqual(RD.group_label(base, catalogue.requirements(base)[0]),
                         RD.GroupLabel(family=ct.SessionKind.COLONOSCOPY, kinds=()))
        snare = catalogue.code_link('45385')
        self.assertEqual(RD.group_label(snare, catalogue.requirements(snare)[0]),
                         RD.GroupLabel(family=None, kinds=(ct.Kind.SNARE,)))
        self.assertIs(RD.service_label(ct.SessionKind.EGD), ct.SessionKind.EGD)

    def test_a_hemostatic_clip_is_labelled_a_bleeding_control_only_on_a_supported_purpose(self):
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        e5 = events['events'][4]
        e5['kind'] = est(k, 'E5', 'kind', 'clip', [src(['S11'])], control='injection')
        e5['purpose'] = fact('hemostasis', [src(['S11'])])  # not established
        self.assertIs(RD.event_label(reading(events), E5).kind, ct.Kind.CLIP)
        e5['purpose'] = est(k, 'E5', 'purpose', 'hemostasis', [src(['S11'], words=at('Biopsies'))],
                            control='prophylaxis')
        self.assertIs(RD.event_label(reading(events), E5).kind, ct.Kind.BLEEDING_CONTROL)

    def test_a_section_is_read_through_the_same_accessors(self):
        self.assertTrue(RD.holds(self.reading, N2, A.OCCASION, ct.DateRelation.ON_DATE_OF_SERVICE))
