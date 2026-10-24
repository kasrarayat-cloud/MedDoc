"""Regressions for the round-3 integration of routing's gi.other findings with validation.

A routed gi.other finding gathers different procedures (the shared routing contract): "Anoscopy" and "Rubber band
ligation" are mentions of one finding, and its family status ranks one procedure's denial first. Validation must
never let one of those procedures decide another's code, and must never miss a procedure done today because another
one was declined. Most routing readings are stated explicitly; RealRoutingCasesTests runs the routing engineer's
measured inputs through real routing. Synthetic text only; pure functions.
"""
from django.test import SimpleTestCase

from tests.test_repairs_status_r2_validation import SILENT_CUE, placed, real
from tests.test_validation import EM, EngineCase, Note, finding, selected, visit_context

VISIT = 'Office visit: established patient seen for rectal bleeding.'
TIME = 'Total time 32 minutes.'
DECLINED = 'Procedure: Anoscopy - patient declined.'
DONE = 'Rubber band ligation x3 completed today.'
CANDIDATE = 'Grade 2 internal hemorrhoids, banding candidate.'
ANOSCOPY_DONE = 'Anoscopy was performed today.'
NOTE = Note('Date of service: 2026-10-21', VISIT, TIME, DECLINED, ANOSCOPY_DONE, DONE, CANDIDATE)


def office(note=NOTE):
    return finding(EM, 'performed', placed(note, EM, 'performed', VISIT, 'other', 'seen'),
                   facts={'em_basis': 'total time 32 minutes'})


def declined(note=NOTE):
    return placed(note, 'gi.other', 'negated', DECLINED, 'procedure', 'negated: declined')


def done(note=NOTE, phrase=DONE):
    return placed(note, 'gi.other', 'performed', phrase, 'procedure', 'performed: completed')


class OtherFindingNeverDecidesAnotherProceduresCodeTests(EngineCase):
    """A gi.other code's own passages decide its status; the routed gi.other finding is never read for it."""

    def run_case(self, family_status, *mentions, evidence=DONE, own=('performed', ('performed: completed',))):
        self.statuses = {TIME: None, evidence: own}
        found = [office(), finding('gi.other', family_status, *mentions)]
        return self.run_engine(NOTE, selected('99214', NOTE.span(TIME)), selected('46221', NOTE.span(evidence)),
                               findings=found, ctx=visit_context())

    def test_a_declined_anoscopy_never_excludes_a_banding_done_today(self):
        result = self.run_case('negated', declined())
        band = self.proposal(result, '46221')
        self.assertEqual((band.bucket, band.status), ('selected', 'ready'), [c.detail for c in band.checks])
        self.assertNotIn('Anoscopy', self.check(band, 'service.status').detail)
        visit = self.proposal(result, '99214')
        self.assertEqual([c.fact for c in visit.clarifications], ['separate_em'])
        self.assertIn('46221', self.check(visit, 'em.same_day_procedure').detail)

    def test_a_performed_anoscopy_never_makes_a_banding_candidate_ready(self):
        for own in (('uncertain', ('uncertain: candidate',)), None):
            with self.subTest(own=own):
                result = self.run_case('performed', done(phrase=ANOSCOPY_DONE), evidence=CANDIDATE, own=own)
                band = self.proposal(result, '46221')
                self.assertEqual(band.status, 'needs_clarification')
                self.assertIn('performed_status', [c.fact for c in band.clarifications])
                self.assertNotIn(ANOSCOPY_DONE, self.check(band, 'service.status').detail)

    def test_the_code_reads_exactly_as_with_no_gi_other_finding(self):
        for family_status, mentions in (('negated', (declined(),)), ('performed', (done(phrase=ANOSCOPY_DONE),))):
            with self.subTest(family_status=family_status):
                band = self.proposal(self.run_case(family_status, *mentions), '46221')
                self.statuses = {TIME: None, DONE: ('performed', ('performed: completed',))}
                alone = self.proposal(self.run_engine(NOTE, selected('99214', NOTE.span(TIME)),
                                                      selected('46221', NOTE.span(DONE)), findings=[office()],
                                                      ctx=visit_context()), '46221')
                self.assertEqual((band.status, [(c.id, c.status, c.detail) for c in band.checks], band.rationale),
                                 (alone.status, [(c.id, c.status, c.detail) for c in alone.checks], alone.rationale))


class OtherFindingIsReadMentionByMentionTests(EngineCase):
    """At the encounter level each gi.other mention is a procedure of its own: a banding done today holds the E/M,
    is a possible missed service and is listed outside the profiles, whatever the family status ranks first."""

    def run_case(self, family_status, *mentions):
        self.statuses = {TIME: None}
        return self.run_engine(NOTE, selected('99214', NOTE.span(TIME)),
                               findings=[office(), finding('gi.other', family_status, *mentions)],
                               ctx=visit_context())

    def test_a_banding_done_today_holds_the_visit_beside_a_declined_anoscopy(self):
        for family_status in ('negated', 'cancelled', 'uncertain'):
            with self.subTest(family_status=family_status):
                result = self.run_case(family_status, declined(), done())
                visit = self.proposal(result, '99214')
                self.assertEqual(visit.status, 'needs_clarification')
                self.assertEqual([c.fact for c in visit.clarifications], ['separate_em'])
                self.assertIn('Other GI service is documented as performed on the same date',
                              self.check(visit, 'em.same_day_procedure').detail)
                self.assertIn('Possible missed service: Other GI service',
                              self.encounter_check(result, 'services.unproposed').detail)
                self.assertEqual([(e['family'], e['status']) for e in result.unsupported],
                                 [('gi.other', 'performed')])
                self.assertEqual(self.encounter_check(result, 'services.unsupported').status, 'warn')

    def test_an_uncertain_banding_that_speaks_for_today_is_possible(self):
        hedged = placed(NOTE, 'gi.other', 'uncertain', DONE, 'other', 'uncertain: Possible')
        visit = self.proposal(self.run_case('negated', declined(), hedged), '99214')
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('Other GI service is possibly performed on the same date',
                      self.check(visit, 'em.same_day_procedure').detail)

    def test_only_a_declined_or_silent_procedure_holds_nothing(self):
        silent = placed(NOTE, 'gi.other', 'uncertain', DONE, 'other', SILENT_CUE)
        planned = placed(NOTE, 'gi.other', 'planned', DONE, 'plan', 'planned: scheduled')
        for mentions in ((declined(),), (declined(), silent), (declined(), planned)):
            with self.subTest(mentions=[m.status for m in mentions]):
                result = self.run_case('negated', *mentions)
                visit = self.proposal(result, '99214')
                self.assertEqual((visit.status, visit.clarifications), ('ready', ()))
                self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_procedure'])
                self.assertEqual(result.unsupported, ())
                self.assertEqual(self.encounter_check(result, 'services.unproposed').status, 'pass')

    def test_a_detected_family_still_follows_its_family_status(self):
        # One procedure, many mentions: a colonoscopy routing reads as cancelled stays cancelled for the E/M hold.
        note = Note('Date of service: 2026-10-21', VISIT, TIME, 'Colonoscopy was performed.',
                    'Colonoscopy cancelled.')
        self.statuses = {TIME: None}
        colonoscopy = finding('gi.colonoscopy', 'cancelled',
                              placed(note, 'gi.colonoscopy', 'performed', 'Colonoscopy was performed.', 'procedure',
                                     'performed: was performed'),
                              placed(note, 'gi.colonoscopy', 'cancelled', 'Colonoscopy cancelled.', 'procedure',
                                     'cancelled: cancelled'))
        visit = self.proposal(self.run_engine(note, selected('99214', note.span(TIME)),
                                              findings=[office(note), colonoscopy], ctx=visit_context()), '99214')
        self.assertEqual(visit.status, 'ready')
        self.assertFalse([c for c in visit.checks if c.id == 'em.same_day_procedure'])


class RealRoutingCasesTests(SimpleTestCase):
    """The routing engineer's measured inputs (office note, 99214 + 46221 selected), through real routing, the real
    span reader and the engine: the routed anoscopy never decides the banding code, and the E/M stays held."""

    TEMPLATE = ('SYNTHETIC\nDate of service: 2026-10-21\nPlace of service: Office (POS 11)\nEstablished patient office '
                'visit.\nChief complaint: rectal bleeding.\n{body}\nMedical decision making: moderate.\nTotal time: 32 '
                'minutes.\n')

    def run_case(self, body, evidence):
        proposals, _ = real(self.TEMPLATE.format(body=body), ('99214', 'Established patient office visit.'),
                            ('46221', evidence))
        band, visit = proposals['46221'], proposals['99214']
        self.assertEqual([c.fact for c in visit.clarifications], ['separate_em'])
        self.assertNotIn('Anoscopy', next(c for c in band.checks if c.id == 'service.status').detail)
        return band

    def test_a_declined_anoscopy_never_excludes_a_banding_done_today(self):
        for body, evidence in (
                ('Procedure: Anoscopy - patient declined.\nRubber band ligation x3 completed today.',
                 'Rubber band ligation x3 completed today.'),
                ('Procedure: Anoscopy - patient declined.\nInternal hemorrhoids were banded x3 today.',
                 'Internal hemorrhoids were banded x3 today.')):
            with self.subTest(evidence=evidence):
                band = self.run_case(body, evidence)
                self.assertEqual((band.bucket, band.status), ('selected', 'ready'))

    def test_a_performed_anoscopy_never_makes_a_banding_candidate_ready(self):
        band = self.run_case('Anoscopy was performed today.\nGrade 2 internal hemorrhoids, banding candidate.',
                             'Grade 2 internal hemorrhoids, banding candidate.')
        self.assertEqual(band.status, 'needs_clarification')
        self.assertEqual([c.fact for c in band.clarifications], ['performed_status'])

    def test_a_declined_anoscopy_never_decides_a_code_citing_a_finding(self):
        # Only the grab-bag effect is pinned here: whether a finding sentence under a Procedure heading establishes
        # the code is the span reader's question, not routing's gi.other finding.
        band = self.run_case('Procedure: Anoscopy - patient declined.\nGrade 2 internal hemorrhoids.',
                             'Grade 2 internal hemorrhoids.')
        self.assertEqual(band.bucket, 'selected')
