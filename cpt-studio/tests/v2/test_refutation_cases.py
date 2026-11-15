"""The refutation's cases as fixtures (docs/gemini-migration/FINAL-V2.md 9.5 [R]; REFUTATIONS-V2.md; step 6c of 8.1):
each finding's case as (i) and (ii), and as (iii) where the finding names a shared misreading. TEXT-ONLY and SYNTHETIC:
the documents and constructed answers are in tests/fixtures/interpretation_v2/ (build.py), run through
tests/v2/test_failure_classes.py's offline pipeline (extract_read, checks, claims, appraise_read, settle, the store,
engine/facts.effective and engine/assess). They prove what the engine and settle do given a filing, never what Gemini
reads, and they are never acceptance evidence (9.5). Every engine case among them is also a gate-6 FactSet
(tests/v2/test_gate6.py, GATE6_FROM_FIXTURES).

What is proved: (i) and (ii) as each case expects them (the design's outcome with its reason, D216-D229 applied); no
(ii) is a wrong READY or a wrong exclusion; the misfiled facts settle not established under (ii) and established under
(iii); (iii) is recorded in RESIDUALS.json, never counted as a pass; and every finding 9.5 names has its case - the
cases another fixture already builds are referenced by name (HO-2's v3: CK-v3; BF17: D1; SC-B's BF6: BF6; CO-8's v6:
CK-v6; CO-1's BF2: T5; GI Note #8's CO-3 and CO-6: CK-note8, beside the shape cases RF-CO3 and RF-CO6). Every
document 9.5 names for CO-1 and CO-2 is the development document itself (VERBATIM)."""
from __future__ import annotations

from tests.v2 import test_failure_classes as FC

FINDINGS = ('HO-1', 'HO-2', 'HO-3', 'HO-5', 'HO-6', 'HO-7', 'HO-8', 'HO-9', 'SC-A', 'SC-B', 'SC-C', 'SC-D', 'CO-1',
            'CO-2', 'CO-3', 'CO-4', 'CO-5', 'CO-6', 'CO-7', 'CO-8')
SHARED = ('HO-3', 'SC-C', 'CO-7')  # the findings that name a shared misreading: their cases carry (iii)
NAMED = ('W1S-499', 'f2-after-002', 'twins-015', 'W1S-222', 'C2MEM-031')  # 9.5's CO-1 and CO-2 documents
# The named documents, each used verbatim (devdocs.SOURCES): each named case's document IS that development document.
VERBATIM = {'W1S-499': 'W1S499', 'f2-after-002': 'F2AFTER002', 'twins-015': 'TWINS015', 'W1S-222': 'W1S222',
            'C2MEM-031': 'C2MEM031'}


class RefutationCaseTests(FC.Fixture):
    def test_every_finding_has_its_case(self):
        refs = FC.refs_of('refutation', 'checklist', 'class', 'borderline')
        self.assertEqual(sorted(set(FINDINGS) - refs), [])
        self.assertEqual(sorted(set(NAMED) - FC.refs_of('refutation')), [])
        self.assertEqual(sorted(set(NAMED) - set(VERBATIM)), [])

    def test_the_named_documents_are_used_verbatim(self):
        from tests.fixtures.interpretation_v2 import devdocs
        for name, source in VERBATIM.items():
            with self.subTest(document=name):
                users = [entry['case'] for entry in FC.manifest()['cases'] if entry['kind'] == 'refutation'
                         and name in entry['refs']]
                self.assertTrue(users)
                for case_id in users:
                    self.assertEqual(FC.document(case_id), getattr(devdocs, source))
                    self.assertIn(devdocs.SOURCES[source][1], FC.manifest_entry(case_id)['provenance'])

    def test_the_shared_misreadings_have_their_third_variant(self):
        for finding in SHARED:
            with self.subTest(finding=finding):
                variants = {variant for entry in FC.manifest()['cases'] if entry['kind'] == 'refutation'
                            and finding in entry['refs'] for variant in entry['variants']}
                self.assertIn('iii', variants)

    def test_the_cases(self):
        for case_id in FC.cases_of('refutation'):
            self.check_case(case_id)

    def test_the_refutation_residuals_are_recorded_never_passes(self):
        for case_id in FC.residual_cases('refutation'):
            with self.subTest(case=case_id):
                record = FC.residuals()['cases'][case_id]
                self.assertIs(record['counted_as_pass'], False)
                self.assertEqual(FC.residual_record(case_id), record)
