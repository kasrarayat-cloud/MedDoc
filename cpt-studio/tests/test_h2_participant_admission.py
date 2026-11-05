"""Harness repair 2026-11-05: HARNESS.md P-ADMIT (the owner's controlled replacement of D14) and stage 6's two
reconciliation rules (an act no code of its family accounts for; an act that is part of another documented act).
Real engine, no provider or database calls."""
from django.test import SimpleTestCase

from studio.validation import engine
from tests.test_harness_engine import (code, corti, decision, not_coded, peer, proposal, read, reviewed, run,
                                       span)

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nProcedure: Colonoscopy\n'
        'The colonoscope was advanced to the cecum and the examination was completed.\n')
BIOPSY = 'Cold forceps biopsies of the cecum were obtained for histology.'
SNARE = 'A separate 7 mm sessile polyp in the sigmoid colon was removed with a cold snare and retrieved.'
COLON = HEAD + BIOPSY + '\n' + SNARE + '\n'

EGD_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
            'Upper endoscopy report (fictional)\nDate of service: 2026-10-14\nProcedure: Upper endoscopy\n'
            'The gastroscope was passed to the second portion of the duodenum.\n')
DILATION = ('A through-the-scope balloon was positioned across the Schatzki ring and inflated to 18 mm under direct '
            'visualization.')


def unresolved(result):
    return [(u['act'], u['reason']) for u in result.completeness['unresolved_items']]


def origin(item):
    return (item.support or {}).get('origin')


class AdmissionTests(SimpleTestCase):
    def test_a_first_reading_proposal_for_an_unresolved_act_is_admitted_and_read_by_the_same_path(self):
        result = run(COLON, corti(('45380', span(COLON, BIOPSY))), [read('astra', [code(COLON, '45385', SNARE)])])
        snare = proposal(result, '45385')
        self.assertEqual((snare.bucket, snare.status, origin(snare)), ('selected', 'ready', 'participant'))
        self.assertEqual(snare.support['proposed_by'], ['astra'])
        self.assertNotIn(('snare', 'not_covered'), unresolved(result))
        # read as the provider's selection of it would be: the same bucket, status and checks
        alone = proposal(run(COLON, corti(('45380', span(COLON, BIOPSY)), ('45385', span(COLON, SNARE)))), '45385')
        self.assertEqual((snare.bucket, snare.status, [c.id for c in snare.checks]),
                         (alone.bucket, alone.status, [c.id for c in alone.checks]))
        self.assertTrue(snare.rationale.startswith('Proposed by Astra (independent participant)'), snare.rationale)

    def test_agreement_adds_proposers_and_nothing_else(self):
        one = proposal(run(COLON, corti(('45380', span(COLON, BIOPSY))),
                           [read('astra', [code(COLON, '45385', SNARE)])]), '45385')
        two = proposal(run(COLON, corti(('45380', span(COLON, BIOPSY))),
                           [read('astra', [code(COLON, '45385', SNARE)]), read('fable', [code(COLON, '45385', SNARE)])]),
                       '45385')
        self.assertEqual(two.support['proposed_by'], ['astra', 'fable'])
        self.assertEqual(decision(one)[1:], decision(two)[1:])  # bucket, status, checks, evidence, fingerprint...

    def test_a_code_given_only_in_peer_review_is_never_admitted(self):
        review = peer('fable', additional=(code(COLON, '45385', SNARE),))
        result = run(COLON, corti(('45380', span(COLON, BIOPSY))), [reviewed('fable', [], review)])
        snare = proposal(result, '45385')
        self.assertEqual(snare.bucket, 'alternative')
        self.assertIn('proposed only in peer review', snare.exclusion_reason)
        self.assertIn(('snare', 'not_covered'), unresolved(result))

    def test_raw_lists_are_never_promoted(self):
        # a participant's not-coded entry and a provider candidate of the code stay informational
        codes = corti(('45380', span(COLON, BIOPSY))) + [engine.ProviderCode('candidate', 'cpt', '45385', '', ())]
        result = run(COLON, codes, [read('astra', advised=[not_coded(COLON, '45385', SNARE)])])
        self.assertFalse([p for p in result.proposals if p.code == '45385' and p.bucket == 'selected'])
        self.assertIn(('snare', 'not_covered'), unresolved(result))

    def test_a_participant_never_chooses_between_codes_for_one_act(self):
        text = EGD_HEAD + DILATION + '\n'
        result = run(text, corti(), [read('astra', [code(text, '43249', DILATION)]),
                                     read('fable', [code(text, '43248', DILATION)])])
        for value in ('43249', '43248'):
            item = proposal(result, value)
            self.assertEqual(item.bucket, 'alternative', value)
            self.assertIn('propose different codes for the same documented act', item.exclusion_reason)
        self.assertIn(('', 'no_proposal'), unresolved(result))  # the service is still left without a proposal

    def test_codes_for_different_acts_of_one_unproposed_service_never_compete(self):
        biopsy = 'Cold forceps biopsies of the gastric antrum were obtained for histology.'
        text = EGD_HEAD + DILATION + '\n' + biopsy + '\n'
        result = run(text, corti(), [read('astra', [code(text, '43249', DILATION), code(text, '43239', biopsy)])])
        for value in ('43249', '43239'):
            item = proposal(result, value)
            self.assertEqual((item.bucket, origin(item)), ('selected', 'participant'), value)

    def test_one_code_for_one_act_is_admitted_beside_a_failed_provider(self):
        # I10: the proposal provider's failure blocks only itself; the first reading's code is read by the same path
        text = EGD_HEAD + DILATION + '\n'
        result = run(text, (), [read('astra', [code(text, '43249', DILATION)])], provider_status='failed')
        item = proposal(result, '43249')
        self.assertEqual((item.bucket, origin(item)), ('selected', 'participant'))

    def test_a_code_that_accounts_for_nothing_left_open_stays_an_alternative(self):
        result = run(COLON, corti(('45380', span(COLON, BIOPSY)), ('45385', span(COLON, SNARE))),
                     [read('astra', [code(COLON, '45378', 'The colonoscope was advanced to the cecum')])])
        base = proposal(result, '45378')
        self.assertEqual(base.bucket, 'alternative')
        self.assertIn('accounts for no documented service or act the other proposals left unresolved',
                      base.exclusion_reason)


class ProtectedReadingTests(SimpleTestCase):
    """The owner's D10/D12 meaning-check classes, through the participant path: a quote of a failed, denied or earlier
    act never makes a code ready."""

    def assert_not_ready(self, text, value, quote, corti_codes=()):
        result = run(text, corti(*corti_codes), [read('astra', [code(text, value, quote)]),
                                                 read('fable', [code(text, value, quote)])])
        found = [p for p in result.proposals if p.code == value]
        self.assertTrue(found)
        self.assertFalse([p for p in found if p.bucket == 'selected' and p.status == 'ready'],
                         [(p.bucket, p.status, p.exclusion_reason[:120]) for p in found])
        return found

    def test_a_failed_snare(self):
        text = HEAD + BIOPSY + '\nHot snare polypectomy of the 8 mm descending colon polyp failed.\n'
        self.assert_not_ready(text, '45385', 'Hot snare polypectomy of the 8 mm descending colon polyp failed.',
                              [('45380', span(text, BIOPSY))])

    def test_a_denied_removal(self):
        text = HEAD + BIOPSY + '\nNo polyps were removed.\n'
        self.assert_not_ready(text, '45385', 'No polyps were removed.', [('45380', span(text, BIOPSY))])

    def test_an_earlier_procedure(self):
        text = HEAD.replace('The colonoscope', 'Last colonoscopy: 9 mm polyp removed with hot snare.\nThe colonoscope') \
            + BIOPSY + '\n'
        self.assert_not_ready(text, '45385', 'Last colonoscopy: 9 mm polyp removed with hot snare.',
                              [('45380', span(text, BIOPSY))])

    def test_a_planned_resection(self):
        text = HEAD + BIOPSY + '\nThe 12 mm transverse colon lesion will be removed by EMR at a later date.\n'
        self.assert_not_ready(text, '45390', 'The 12 mm transverse colon lesion will be removed by EMR at a later date.',
                              [('45380', span(text, BIOPSY))])


class DecompressionTests(SimpleTestCase):
    """Stage 6: an upper endoscopy's decompression is an act no code of its service accounts for - listed, never
    bundled, never hidden, routine or therapeutic alike; a colonoscopy's is still codable (45393)."""

    def test_a_stomach_decompression_is_listed_as_unsupported(self):
        for ending in ('The stomach was decompressed and the endoscope withdrawn.',
                       'The stomach was decompressed for gastric outlet obstruction and the endoscope withdrawn.',
                       'Decompression of the stomach was attempted but failed.'):
            text = EGD_HEAD + DILATION + '\n' + ending + '\n'
            result = run(text, corti(('43249', span(text, DILATION))))
            items = [u for u in result.completeness['unresolved_items'] if u['act'] == 'decompression']
            if 'failed' in ending and not items:
                continue  # a failed decompression the reader does not read as performed is not an act to code
            self.assertEqual([u['reason'] for u in items], ['unsupported'], ending)
            self.assertFalse([b for b in result.completeness['bundled'] if b['act'] == 'decompression'], ending)
            self.assertEqual(result.completeness['state'], 'incomplete', ending)

    def test_a_colon_decompression_stays_codable(self):
        text = HEAD + 'The colon was decompressed for acute distension.\n'
        result = run(text, corti(('45378', span(text, 'The colonoscope was advanced to the cecum'))))
        self.assertIn(('decompression', 'not_covered'), unresolved(result))


class IncludedActTests(SimpleTestCase):
    """Stage 6: an act that is part of another documented act (the EMR's lift injection) is never what a code accounts
    for while a separate act of its kinds is documented; where none is, the code is held, never ready."""

    EMR = ('In the ascending colon, a 17 mm flat lesion was lifted by a submucosal injection of saline and removed by '
           'snare-based endoscopic mucosal resection.')
    TATTOO = 'Tattoo ink was injected into the submucosa of the transverse colon to mark a separate lesion.'

    def test_the_tattoo_not_the_lift_is_the_injection_codes_act(self):
        text = HEAD + self.EMR + '\n' + self.TATTOO + '\n'
        result = run(text, corti(('45390', span(text, self.EMR)), ('45381', span(text, self.TATTOO))))
        tattoo = proposal(result, '45381')
        self.assertEqual(tattoo.status, 'ready')
        kinds = [a['kind'] for a in tattoo.support['acts']]
        self.assertIn('tattoo', kinds)
        # the lift injection of the resected ascending lesion is the EMR's, never this code's act
        self.assertFalse([a for a in tattoo.support['acts'] if 'ascending' in a['label'] or '17 mm' in a['label']],
                         tattoo.support['acts'])

    def test_an_injection_code_on_the_lift_alone_is_held(self):
        text = HEAD + self.EMR + '\n'
        result = run(text, corti(('45390', span(text, self.EMR)), ('45381', span(text, self.EMR))))
        lift = proposal(result, '45381')
        self.assertNotEqual(lift.status, 'ready')
        self.assertEqual(lift.support.get('reason'), 'act_included')
