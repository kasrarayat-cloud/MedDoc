"""Neutral source-binding regressions: real engine, no provider or database calls."""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context, detect, services
from tests.test_services_reconcile import proposal, run, sel, span


DAY = date(2026, 11, 4)
HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL - NOT FOR CLINICAL USE\n'
        'Procedure report\nDate of service: 2026-11-04\nColonoscopy\n'
        'The colonoscope was advanced to the cecum. ')


def inventory(body):
    text = HEAD + body + '\n'
    return services.build(text, service_date=DAY, routing=detect.route(text, DAY),
                          context_facts=context.extract_context(text))


def colon(inv):
    return inv.for_family('gi.colonoscopy')[0]


def assess_body(body, codes):
    text = HEAD + body + '\n'
    return run(text, [sel(code, span(text, quote)) for code, quote in codes])


class TattooPredicateTests(SimpleTestCase):
    # The first three, and test_bare_completed_marking_keeps_its_own_purpose below, were the package's two releases.
    # Harness repair round 6 dropped them after two refutation cycles of their whole-sentence form (HARNESS.md
    # "Refutation round 6") and pinned main's reading. Harness repair 3 (F-NEG S, F-TIME R; the owner's second message of
    # 2026-11-05, item 4) reads the same sentences by two narrower rules, through every other reading, so these pin the
    # package's own intent again: the denial is the resection's, and the purpose's "future" is the localization's. The
    # rest are the package's holds, kept.

    def test_nominal_tattoo_and_its_purpose_do_not_inherit_resection_denial(self):
        body = ('Carbon tattoo ink was injected into the transverse colon submucosa. '
                'The transverse colon lesion was marked with submucosal tattoo for future localization '
                'and not resected today.')
        inv = inventory(body)
        # harness repair 3: the denial is the resection's, so no conflict with the injection, and 45381 is ready
        self.assertEqual(inv.conflicts, ())
        self.assertFalse([a for a in colon(inv).acts if a.kind == 'tattoo' and a.status == 'negated'])
        result = assess_body(body, [('45381', 'Carbon tattoo ink was injected into the transverse colon submucosa.')])
        self.assertEqual(proposal(result, '45381').status, 'ready')

    def test_future_purpose_does_not_date_a_completed_injection(self):
        body = 'Tattoo ink was injected into the transverse colon submucosa for future localization.'
        tattoo = [a for a in colon(inventory(body)).acts if a.kind == 'tattoo']
        self.assertTrue(tattoo)
        # harness repair 3 (F-TIME R): "future" is the localization's time, so the completed injection is done today
        self.assertEqual({a.status for a in tattoo}, {'performed'})
        result = assess_body(body, [('45381', body)])
        self.assertEqual(proposal(result, '45381').status, 'ready')

    def test_noun_tattoo_does_not_inherit_a_tissue_resection_denial(self):
        body = 'The transverse colon lesion was marked with tattoo and not resected today.'
        # harness repair 3 (F-NEG S): the coordinated denial is the resection's, never the tattoo's
        tattoo = [a for a in colon(inventory(body)).acts if a.kind == 'tattoo']
        self.assertEqual({a.status for a in tattoo}, {'performed'})

    def test_future_tattoo_stays_planned(self):
        body = 'Tattoo ink will be injected into the transverse colon submucosa for future localization.'
        result = assess_body(body, [('45381', body)])
        self.assertNotEqual(proposal(result, '45381').status, 'ready')
        self.assertFalse([a for a in colon(inventory(body)).acts
                          if a.kind in ('tattoo', 'injection') and a.status == 'performed'])

    def test_purpose_does_not_overrule_a_genuine_denial(self):
        body = 'Tattoo placement was not performed in the transverse colon for future localization.'
        result = assess_body(body, [('45381', body)])
        self.assertNotEqual(proposal(result, '45381').status, 'ready')

    def test_a_genuine_tattoo_contradiction_is_still_held(self):
        body = ('Tattoo ink was injected into the transverse colon submucosa. '
                'No tattoo was placed in the transverse colon.')
        result = assess_body(body, [('45381', 'Tattoo ink was injected into the transverse colon submucosa.')])
        self.assertTrue(inventory(body).conflicts)
        self.assertEqual(proposal(result, '45381').status, 'needs_clarification')

    def test_nominal_shared_denial_is_not_a_separate_predicate(self):
        body = 'Tattoo and injection were not performed in the transverse colon.'
        self.assertFalse([a for a in colon(inventory(body)).acts if a.status == 'performed'])

    def test_marking_does_not_make_another_act_done_or_current(self):
        body = ('Biopsy of the transverse colon lesion for future localization was recommended; '
                'tattoo ink was injected into the rectum.')
        self.assertFalse([a for a in colon(inventory(body)).acts
                          if a.kind == 'biopsy' and a.status == 'performed'])

    def test_own_contradictory_marking_predicate_is_not_ignored(self):
        body = 'Tattoo ink was injected in the transverse colon and not performed today.'
        result = assess_body(body, [('45381', body)])
        self.assertNotEqual(proposal(result, '45381').status, 'ready')

    def test_marked_as_an_adjective_is_not_a_biopsy_predicate(self):
        body = 'Marked erythema in the rectum; biopsy is planned.'
        self.assertFalse([a for a in colon(inventory(body)).acts
                          if a.kind == 'biopsy' and a.status == 'performed'])

    def test_bare_completed_marking_keeps_its_own_purpose(self):
        body = ('Tattoo ink was injected into the transverse colon submucosa. '
                'Transverse colon lesion marked with submucosal tattoo for future localization and not resected today.')
        # harness repair 3 (F-NEG S, F-TIME R): the fragment's denial is the resection's - no tattoo conflict
        self.assertEqual(inventory(body).conflicts, ())

    def test_marking_an_object_does_not_establish_a_clinical_tattoo(self):
        for body in (
                'The vial of tattoo ink was marked with the transverse colon specimen label for future identification.',
                'The syringe of tattoo ink was marked with the transverse colon specimen label for future identification.',
                'The transverse colon diagram was marked with the injection site for future identification.',
                'The transverse colon injection site was marked for future localization.'):
            with self.subTest(body=body):
                result = assess_body(body, [('45381', body)])
                self.assertNotEqual(proposal(result, '45381').status, 'ready')
                self.assertFalse([a for a in colon(inventory(body)).acts
                                  if a.kind in ('tattoo', 'injection') and a.status == 'performed'])


class ComparedLesionTests(SimpleTestCase):
    def test_rectal_patch_does_not_take_the_comparison_polyp_site(self):
        for relation in ('separate from', 'distinct from', 'different from'):
            with self.subTest(relation=relation):
                body = ('In the distal rectum, a discrete 5 mm erythematous mucosal patch, '
                        + relation + ' the sigmoid polyp, was sampled with cold biopsy forceps.')
                biopsies = [a for a in colon(inventory(body)).acts
                            if a.kind == 'biopsy' and a.status == 'performed']
                self.assertTrue(biopsies)
                self.assertEqual({site for a in biopsies for site in a.anatomy}, {'rectum'})
                result = assess_body(body, [('45380', body)])
                item = proposal(result, '45380')
                self.assertEqual(item.status, 'ready')
                support = next(c.detail for c in item.checks if c.id == 'service.status')
                self.assertIn('in the rectum', support)
                self.assertNotIn('sigmoid', support)

    def test_true_multisite_biopsies_keep_both_sites(self):
        body = 'Biopsies were obtained with cold forceps from the rectum and sigmoid colon.'
        biopsies = [a for a in colon(inventory(body)).acts if a.kind == 'biopsy']
        self.assertEqual({site for a in biopsies for site in a.anatomy}, {'rectum', 'sigmoid colon'})

    def test_parenthesized_comparison_does_not_add_another_biopsy_site(self):
        body = ('In the rectum, a 5 mm mucosal patch (distinct from the sigmoid polyp) '
                'was sampled with cold forceps.')
        biopsies = [a for a in colon(inventory(body)).acts if a.kind == 'biopsy' and a.status == 'performed']
        self.assertTrue(biopsies)
        self.assertEqual({site for a in biopsies for site in a.anatomy}, {'rectum'})

    def test_unclosed_comparison_does_not_consume_a_second_subject(self):
        for joiner, noun, action, kind, code in (
                ('and', 'polyp', 'was removed with a cold snare', 'snare', '45385'),
                ('whereas', 'nodule', 'was biopsied', 'biopsy', '45380')):
            with self.subTest(joiner=joiner):
                own = 'a cecal ' + noun + ' ' + action
                body = ('In the rectum a 5 mm patch was seen separate from the sigmoid polyp '
                        + joiner + ' ' + own + '.')
                acts = [a for a in colon(inventory(body)).acts if a.kind == kind and a.status == 'performed']
                self.assertTrue(acts)
                self.assertEqual({site for a in acts for site in a.anatomy}, {'cecum'})
                result = assess_body(body, [(code, own)])
                self.assertEqual(proposal(result, code).status, 'ready')
                detail = next(c.detail for c in proposal(result, code).checks if c.id == 'service.status')
                self.assertIn('cecum', detail)

    def test_new_patch_owns_the_following_snare_denial(self):
        body = ('A 7 mm sigmoid colon polyp was completely removed using a cold snare. '
                'In the distal rectum, a discrete 5 mm erythematous mucosal patch, separate from the sigmoid polyp, '
                'was sampled with cold biopsy forceps for histology; it was not excised by snare.')
        inv = inventory(body)
        self.assertFalse(inv.conflicts, inv.conflicts)
        svc = colon(inv)
        # harness repair round 5 (L4B-2, L5-2): the package's bare "excised" is dropped, so "it was not excised by
        # snare" is no act of the patch's; no snare act is denied anywhere else either, so nothing conflicts and both
        # codes stay ready (recorded in ACCURACY-RESIDUALS.md, round 5)
        self.assertFalse([a for a in svc.acts if a.kind == 'snare' and a.status == 'negated'
                          and a.lesion != next(l for l in svc.lesions if l.anatomy == 'rectum').id])
        result = assess_body(body, [('45385', 'A 7 mm sigmoid colon polyp was completely removed using a cold snare.'),
                                   ('45380', 'was sampled with cold biopsy forceps for histology')])
        self.assertEqual(proposal(result, '45385').status, 'ready')
        self.assertEqual(proposal(result, '45380').status, 'ready')

    def test_genuine_same_lesion_snare_contradiction_stays_held(self):
        body = ('A 7 mm sigmoid colon polyp was removed with a cold snare. '
                'This sigmoid colon polyp was not removed by snare.')
        result = assess_body(body, [('45385', 'A 7 mm sigmoid colon polyp was removed with a cold snare.')])
        self.assertTrue(inventory(body).conflicts)
        self.assertEqual(proposal(result, '45385').status, 'needs_clarification')
