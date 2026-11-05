"""Harness repair 2026-11-05, stage 3, as refutation round 3 left it: the routing-era reader's unresolved negation is
released only where the documented-service reader reads the passage as the service's positive reading and no not-done
act overlaps it - main's rule, exactly (engine._negation_resolved). Stage 3 had set another act's denial apart where the
code's own act read as performed in the passage; three refutation rounds found it believed acts done "at the referring
facility", "elsewhere", "historically" or "unsuccessfully", so it is dropped under the two-cycle rule, and the 88d9db32
shape below is held again (HARNESS.md, "Refutation round 3"). Real engine, no provider or database calls."""

from django.test import SimpleTestCase

from tests.test_services_reconcile import proposal, run, sel, span


HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL - NOT FOR CLINICAL USE\n'
        'Procedure report\nDate of service: 2026-11-04\nColonoscopy\n'
        'The colonoscope was advanced to the cecum. ')


def assess(body, code, quote):
    text = HEAD + body + '\n'
    return proposal(run(text, [sel(code, span(text, quote))]), code)


class OtherKindDenialTests(SimpleTestCase):
    """The 88d9db32 shape: a biopsy performed on a lesion whose snare excision is denied in the next clause."""

    BODY = ('In the distal rectum, a discrete 5 mm erythematous mucosal patch, separate from the sigmoid polyp, was '
            'sampled with cold biopsy forceps for histology; it was not excised by snare.')

    def test_the_biopsy_beside_the_denied_snare_is_held_as_main_holds_it(self):
        # stage 3 pinned READY here; round 3 restored main's release, so the package's correct reading of the snare's
        # denial ("not excised by snare") holds the biopsy code beside it (a hold, recorded as 88d9db32's cost)
        p = assess(self.BODY, '45380', 'cold biopsy forceps for histology; it was not excised by snare.')
        self.assertEqual(p.status, 'needs_clarification', [c.detail for c in p.checks if c.id == 'service.status'])

    def test_the_denied_snare_still_holds_a_snare_code(self):
        # the not-done act is of the code's own kind: the release is refused, as before
        p = assess(self.BODY, '45385', 'cold biopsy forceps for histology; it was not excised by snare.')
        self.assertNotEqual(p.status, 'ready')

    def test_a_denied_biopsy_still_holds_the_biopsy_code(self):
        body = ('In the distal rectum, a discrete 5 mm erythematous mucosal patch was not sampled with cold biopsy '
                'forceps; it was excised by snare.')
        p = assess(body, '45380', 'a discrete 5 mm erythematous mucosal patch was not sampled with cold biopsy forceps;')
        self.assertNotEqual(p.status, 'ready')

    def test_no_biopsy_beside_the_denied_snare_is_never_released(self):
        # nothing in the passage states the code's own act as done: a denial of another act never makes it so
        body = 'In the distal rectum, a discrete 5 mm erythematous mucosal patch was seen; it was not excised by snare.'
        p = assess(body, '45380', 'it was not excised by snare.')
        self.assertNotEqual(p.status, 'ready')

    def test_a_denial_of_another_act_never_stands_for_a_passage_without_the_codes_act(self):
        # the biopsy is documented elsewhere; the passage cited for it states only the examination and a denied snare
        body = ('Biopsies were taken from the cecum with cold forceps. The examination was completed; the rectal patch '
                'was not excised by snare.')
        p = assess(body, '45380', 'The examination was completed; the rectal patch was not excised by snare.')
        self.assertNotEqual(p.status, 'ready')

    def test_a_passage_stating_the_codes_own_act_done_and_denied_stays_held(self):
        # the rule before the repair, kept: a not-done act of the code's own kind in the cited passage refuses the release
        body = 'Cold forceps biopsies were taken from the cecum, and the rectal patch was not biopsied.'
        p = assess(body, '45380', body)
        self.assertNotEqual(p.status, 'ready')

    def test_the_release_refuses_a_not_done_act_of_the_codes_own_kind(self):
        # reaches the release (the routing-era reader's unresolved negation 'not' in its clause, a performed biopsy
        # matched): the rectal patch's negated biopsy is of the code's own kind, so the doubt is not another act's and
        # the code is held ("was not sampled with ..." never reaches it: the routing-era reader resolves that denial)
        body = 'Cold biopsy forceps were used in the cecum; the rectal patch was not excised with cold biopsy forceps.'
        p = assess(body, '45380', body)
        self.assertNotEqual(p.status, 'ready')
