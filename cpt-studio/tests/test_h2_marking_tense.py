"""Harness repair 2026-11-05, refutation time-1, and harness repair 3 (F-TIME R): the purpose rule ("for future
localization" is a completed marking's purpose, never its time) applies only to a marking stated as done. A bare
participle an auxiliary or an infinitive marker governs ("to be injected", "is injected") states none, so its "future"
stays a plan word and 45381 is never READY on it - through Corti's selection or a participant's first reading. Real
engine, no provider or database calls."""
from django.test import SimpleTestCase

from tests.test_harness_engine import code, corti, read, run, span

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
        'Date of service: 2026-10-14\nProcedure: Colonoscopy\n'
        'The colonoscope was advanced to the cecum and the examination was completed.\n')
CECUM = 'The colonoscope was advanced to the cecum'
SITE = 'into the transverse colon submucosa for future localization'
NOT_DONE = (f'Tattoo ink has yet to be injected {SITE}.', f'Tattoo ink is to be injected {SITE}.',
            f'Tattoo ink needs to be injected {SITE}.', f'Tattoo ink would need to be injected {SITE}.',
            f'Tattoo ink ought to be injected {SITE}.', f'Tattoo ink is going to be injected {SITE}.',
            f'Tattoo ink remains to be injected {SITE}.', f'Tattoo ink is being injected {SITE} next week.',
            f'Ideally, tattoo ink is injected {SITE} at the referral endoscopy.',
            f'Disposition:\nTattoo ink to be injected {SITE} at surgery.')
DONE = (f'Tattoo ink was injected {SITE}.', f'Tattoo ink injected {SITE}.')


def outcomes(line):
    text = HEAD + line + '\n'
    quote = line.split('\n')[-1]
    by_corti = [(p.bucket, p.status) for p in run(text, corti(('45378', span(text, CECUM)), ('45381', span(text, quote))))
                .proposals if p.code == '45381']
    by_astra = [(p.bucket, p.status) for p in run(text, corti(('45378', span(text, CECUM))),
                                                     [read('astra', [code(text, '45381', quote)])]).proposals
                if p.code == '45381']
    return by_corti, by_astra


class MarkingTenseTests(SimpleTestCase):
    def test_a_marking_not_stated_as_done_is_never_ready(self):
        for line in NOT_DONE:
            with self.subTest(line):
                by_corti, by_astra = outcomes(line)
                self.assertNotIn(('selected', 'ready'), by_corti)
                self.assertNotIn(('selected', 'ready'), by_astra)

    def test_a_completed_marking_with_a_future_purpose_is_ready(self):
        # round 6 dropped the package's whole-sentence purpose rule. Harness repair 3 (F-TIME R, one rule in cues for
        # both readers): "for future localization" is the purpose's time where the clause states the marking done, so
        # a completed marking is READY on both paths (the owner's second message of 2026-11-05, item 4)
        for line in DONE:
            with self.subTest(line):
                self.assertEqual(outcomes(line), ([('selected', 'ready')], [('selected', 'ready')]))
