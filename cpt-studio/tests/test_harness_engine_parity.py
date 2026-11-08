"""HARNESS.md I1, pinned: with no independent participant configured the engine's result is byte-identical to the
round-4 engine's.

Each case below is a synthetic document with the proposal provider's answer (or its failure), read by the real routing,
the real inventory and the engine. PINNED holds sha256_json of each result as the round-4 engine made it - this module
loaded, unchanged, against an export of 80f2f2dc8 (the harness branch once the integrated round 4, 443e67032, was
merged: the round-4 engine, cpt-studio-validation@5, with the participant types added and no participant read;
re-pinned 2026-11-01 from 01f39cd5d's digests because round 4's own declared integration moved every result) - so any change to what the engine makes without participants fails here, not
only the fields the H1 replay and the H4 battery compare. ``cases`` uses only what that tree already had; nothing here
imports a name the harness added, except inside a test.

Re-pin only with a declaration of the change: a moved digest is a change to every Corti-only assessment.
Re-pinned 2026-11-04 for the core repair (the PINNED comment says what moved and why).
"""
from datetime import date

from unittest import mock

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode, ReferenceSourceInfo, sha256_json
from studio.validation.engine import assess

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
COLON = HEAD + """Colonoscopy report (fictional)
Date of service: 2026-10-14
Place of service: Ambulatory surgery center
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.
A separate 12 mm flat lesion in the ascending colon was biopsied with cold forceps.
Plan: Surveillance colonoscopy in three years.
"""
VISIT = HEAD + """Office visit and same-day procedure (fictional)
Date of service: 2026-10-14
Place of service: Office
Established patient seen for rectal bleeding. History, examination and medical decision making of moderate complexity
are documented separately from the procedure.
Procedure: Flexible sigmoidoscopy. The sigmoidoscope was advanced to 50 cm. Two cold forceps biopsies were taken.
"""
CONFLICT = HEAD + """Colonoscopy report (fictional)
Date of service: 2026-10-14
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.
Nursing checklist
Recorded by Jo Fictional RN: India ink tattoo [X] Performed [ ] Not performed.
Physician note: no tattoo or other submucosal injection was given at this session.
"""


def _info(key, kind, release):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=f'{release} synthetic', release=release,
                               url='https://www.cms.gov/synthetic', sha256='0' * 64, effective_start='2026-10-01',
                               effective_end='2026-12-31', license_note='licence', scope_note='scope')


def _reference():
    pfs, mue = _info('cms-pfs-rvu26d', 'cms-pfs', 'RVU26D'), _info('cms-mue-practitioner-2026q4',
                                                                     'cms-mue-practitioner', '2026-Q4')
    rows = {'45378': ('2', None), '45380': ('3', '45378'), '45385': ('3', '45378'), '45331': ('3', '45330'),
            '45330': ('2', None)}
    pfs_rows = {(code, ''): {'status': 'A', 'global_days': '000', 'mult_proc': mult, 'endo_base': base, 'pctc': '0'}
                for code, (mult, base) in rows.items()}
    pfs_rows[('99213', '')] = {'status': 'A', 'global_days': 'XXX', 'mult_proc': '0', 'endo_base': None, 'pctc': '0'}
    mue_rows = {(code, ''): {'value': 1, 'mai': {'indicator': '2', 'label': 'Date of Service Edit: Policy'},
                             'rationale': 'Anatomic Consideration'} for code in rows}
    return InMemoryReferenceLookup([pfs, mue], {pfs.key: pfs_rows, mue.key: mue_rows})


def _span(text, phrase):
    start = text.index(phrase)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def _code(text, code, phrase, role='selected', parent=None):
    return ProviderCode(role, 'cpt', code, 'UNVERIFIED PROVIDER WORDING', (_span(text, phrase),), parent)


def _inputs(text, codes, *, status='succeeded', user_values=None, refused=False, **extra):
    facts = gi_context.merge_user_values(gi_context.extract_context(text), user_values or {})
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None
    normalized = (NormalizedResponse('corti', 'test@1', tuple(codes), (), ('a problem reading it',) if refused else (),
                                     refused) if status == 'succeeded' else None)
    return dict(text=text, pages=(), context=facts, routing=detect.route(text, day), normalized=normalized,
                reference=_reference(), service_date=day, provider_status=status, extraction_status='ok', **extra)


def cases():
    """{name: assess keyword arguments}, built only from what the round-4 engine's tree has."""
    second_start = COLON.index('Procedure: Colonoscopy')
    second = NormalizedResponse('corti', 'test@1', (_code(COLON, '45380', 'was biopsied with cold forceps'),
                                                    _code(COLON, '45381', 'was advanced to the cecum')))
    return {
        'polypectomy-and-a-candidate': _inputs(COLON, [_code(COLON, '45385', 'was removed with a hot snare'),
                                                       _code(COLON, '45378', 'The colonoscope was advanced',
                                                             role='candidate')]),
        'two-codes-a-plan-code-and-hcpcs': _inputs(COLON, [
            _code(COLON, '45385', 'was removed with a hot snare'),
            _code(COLON, '45380', 'was biopsied with cold forceps'),
            _code(COLON, '45378', 'Surveillance colonoscopy in three years.'),
            _code(COLON, 'G0105', 'Procedure: Colonoscopy')]),
        'second-review': _inputs(COLON, [_code(COLON, '45385', 'was removed with a hot snare')], second=second,
                                 second_scope={'start': second_start, 'end': len(COLON),
                                               'items': ['the ascending colon biopsy']}),
        'visit-beside-a-procedure': _inputs(VISIT, [
            _code(VISIT, '99213', 'Established patient seen for rectal bleeding'),
            _code(VISIT, '45331', 'Two cold forceps biopsies were taken')]),
        'a-conflict-in-the-record': _inputs(CONFLICT, [_code(CONFLICT, '45385', 'was removed with a hot snare')]),
        'provider-failed': _inputs(COLON, (), status='failed'),
        'provider-unknown': _inputs(COLON, (), status='unknown'),
        'provider-not-run': _inputs(COLON, (), status='not_run'),
        'response-refused': _inputs(COLON, (), refused=True),
        'member-date-conflict-failed': _inputs(COLON, (), status='failed', user_values={'service_date': '2026-10-15'}),
        'member-date-conflict-answered': _inputs(COLON, [_code(COLON, '45385', 'was removed with a hot snare')],
                                                 user_values={'service_date': '2026-10-15'}),
    }


# sha256_json(assess(**cases()[name])) as the core-repair engine (cpt-studio-validation@6, gi-services@3, gi-routing@6;
# 2026-11-04) computes it. Re-pinned beside tests/fixtures/gi4/declarations/cux-lead.json: with the core repair's
# three labels set back to installed 41e03656df61's (@5, @2, @5) every case equals its round-4 pin (01f39cd5d) but
# two-codes-a-plan-code-and-hcpcs, whose 45378 gains P2's performed_status hold beside base_included (cux-hold.json;
# its status unchanged); every other digest moved by the labels alone.
CORE_REPAIR_PINNED = {
    'a-conflict-in-the-record': '3dd3f13e7262eb0151eae3da06ca2c993f408ff3abc125518b3cfff6db3986b1',
    'member-date-conflict-answered': 'df71c3807895c254fb7e147c70d813b5a15f769ed3757ce22eaf7dc9c09e9e91',
    'member-date-conflict-failed': '2b3dfb5841cf0b44b9174d3ccfcd819b665b5b09a23791542dea375ee18d5734',
    'polypectomy-and-a-candidate': '08c620687f4f510577a74b94833478a6ad61dda21e9d796edd55a388c80cdecb',
    'provider-failed': '826a8e6b351b3428568282790c5bc9a11a8741f26cb942131fac36a0635c1b1c',
    'provider-not-run': '303981b83fc05559534fe8fbf683c2fdae92a744f3d511d89c2a6205967ee970',
    'provider-unknown': '41c0234ca9f048722851e40d5a0da58ae98c536fb4505d610477ee83297d977b',
    'response-refused': '0f26542f1e56a17f40cf55f4358443fd1bccda8ebed129b90a908831cfb2787b',
    'second-review': '447848d09d49f13d39c8c2614474acbb2fad7dead0a09e67a8963b637e7686e7',
    'two-codes-a-plan-code-and-hcpcs': 'cdb9178aa19209ff098b1b0c6f1c837500e94a7fd82bd91dc48cae8a414089d0',
    'visit-beside-a-procedure': '4a818c01c0c879c0c7ba90e33428feacb85eb95ee0d255715b35befb4a186189',
}

# The harness repair (2026-11-05; cpt-studio-validation@7, gi-services@4, gi-routing@7) computes these. With the three
# labels set back to installed b0dc3446c64c's every case equals CORE_REPAIR_PINNED above but response-refused, whose
# completeness now says the provider response was not available (a response refused whole is no available answer);
# every other digest moved by the labels alone (ServedLabelParityTests).
HARNESS_REPAIR_PINNED = {
    'a-conflict-in-the-record': '53cabbcc2d96179ba11becd37e6c731420835c04563d57091d920bbfca5d9ede',
    'member-date-conflict-answered': '398562dc0d18c31a75d705e9cf38a5f905d3d1e7608639de26f48253faf6195c',
    'member-date-conflict-failed': '80f1ecf8b5d5b567338623edeb85d8d197875d694aef9a60f149a917cb628fe6',
    'polypectomy-and-a-candidate': '6b17ccdb0e97d5fd7db29fd227ae6fe9d12e73e5c8c79831ccb185e1e46fab26',
    'provider-failed': '09a9e98522e347925919bed412f4f3cfb32941c01542b1911d107ec61caa1e6a',
    'provider-not-run': '0e52c8b60a90675d7eb06cc94fc74f455e181042009976b34e2e4b94a8ae4367',
    'provider-unknown': '60e2bab7e4b00416b9b336cfd8e1cb3032ccbe6e288109f89e4b656b9b521639',
    'response-refused': '0054024dcdd7a962cab9b0aaf9d77b85fc2b2a9dbdbc15b6baa44b97c4eb7550',
    'second-review': 'dc56ff838b19a3f09aca08af6e7f1b324dd6ab0606fff181b96e335af8163cb0',
    'two-codes-a-plan-code-and-hcpcs': '40540bd0a36ea88dc0f585d8fdb1b0d9c9e075250a7cc865b0030b2972c0281c',
    'visit-beside-a-procedure': 'b0e0feeca5683863ece0e638b9b9dddf9071ad4a8fc12627bc651102ffe01ad7',
}

# Harness repair 3 (2026-11-05, second message; cpt-studio-validation@8, gi-services@5, gi-routing@7 kept) computes these.
# With the three labels set back to installed e6d451f03d86's every case equals HARNESS_REPAIR_PINNED above, byte for
# byte: on these Corti-only cases the repair moves the labels and nothing else (ServedLabelParity3Tests).
HARNESS_REPAIR_3_PINNED = {
    'a-conflict-in-the-record': '1ced964ed8d58c29bb808880287fbb409f52850c67242a99231ad1722675cd90',
    'member-date-conflict-answered': 'b213b8002bfb5af16ac96a913b6a07c0f4ad4c784f6805518d04b151c366524a',
    'member-date-conflict-failed': 'a06d4d8f47fc76b9e8d8b4f2ed9fdb6a4723a05d07881dccdc554ee13e1bf483',
    'polypectomy-and-a-candidate': '9a85322e6979a14175ab2abd8c647c7d20ed1ad8abcc6e31a959573b8200eacf',
    'provider-failed': '027b76059ae773d3b4da8b02d7508033973f88591357b0b4cc48f4285d4c04b6',
    'provider-not-run': 'd9238ee827640b4862170d6fc8e5f9035b47e31d9247012a742070adbca1d8cf',
    'provider-unknown': '6df0fe9c9e318ed257da09cc60cf9bc1618555c32a7bc2deadfb71d4cfc84ded',
    'response-refused': '3dcc8a43a5499d7f8ee37678da699001c95906512048770b538cebc4fe8d9555',
    'second-review': 'bcbb384aeaaec8387d1ec3a956d43784a04eee6937f385114d0dee773459be01',
    'two-codes-a-plan-code-and-hcpcs': 'a63817cea859ec3c37f7bfe35e8841940196b5ff4be45c7a015a0b5868990a8c',
    'visit-beside-a-procedure': 'dd5138e408497a1b0459595584188fede5c01e579de33fb6239f57ccd50a83d2',
}

# The walk round (2026-11-07; cpt-studio-validation@10, gi-services@6, gi-routing@10, gi-catalogue@2) re-pinned these
# on its labels alone, three times: the readers' labels, then the engine's (@10; with ENGINE_VERSION set back to @9 every
# case equals the previous pin, byte for byte - measured), then the inventory's back to the installed @6 when its two
# repairs were dropped (with gi-services@7 restored every case equals the previous pin - measured), and the served-label
# parity below still holds. The completion repair (owner directive 2026-11-06)
# computes these. With its labels set back to installed fd8040d71e44's (and the catalogue's to @1, which every release
# before it carried) every case equals HARNESS_REPAIR_3_PINNED, byte for byte: on these Corti-only cases the repair moves
# the labels and nothing else (ServedLabelParityCompletionTests; measured on the base tree and the head tree alike).
WALK_ROUND_PINNED = {
    'a-conflict-in-the-record': '04f320d02d9a39362ff01e016f92f2d777e7033764719ac8da0bf8dc14b242e0',
    'member-date-conflict-answered': '514c6a02363eb8d776e7512d04f91e7f8c317af7c0a1c09bba23f36040280e24',
    'member-date-conflict-failed': '167a68ce485009b189c05ba67c9df67593f4992a8fa10e964818b87f45dad7a4',
    'polypectomy-and-a-candidate': '5ca8fecaa2d5921f1f86752b8af84f3b76ee4ebe53723840fd25e44cae6b78fb',
    'provider-failed': '1050398056576754c33b63ecd79781994a3ab9b6f81b66673d1de80a4c9e63e0',
    'provider-not-run': 'c0e3aa3b3c8c0ddb7a460f6d2811d380a33645ceca352993a8503b7a369f6919',
    'provider-unknown': '2dd901defb0740a7b8768faf0eefd04127ed6644108d091fd1ed8ac1cf2a73d4',
    'response-refused': 'b8c1dbd49cbf4f8963a51364115dd90fdf740b24e3aded88d21fffef4f7fb99e',
    'second-review': '64653716b5e6bade3b4faadc03c49f0f663ae257a806a5c225a0508017d2a456',
    'two-codes-a-plan-code-and-hcpcs': 'e16a02dac8a2d16f2617b4724efd05a82c78d13f71686dc664b2d8612a942315',
    'visit-beside-a-procedure': 'b504dcf1cff552d21bb3ea2ee05d4a9e6ffe04ee3927e390ce41ea6504ca0e29',

}
# The structure round (2026-11-08; gi-services@7 and cpt-studio:gi-services@7, gi-routing@12) re-pinned these on its
# labels alone: with routing, the inventory and its source set back to installed aeae34bebbe5's
# (STRUCTURE_ROUND_INSTALLED_LABELS) every case equals WALK_ROUND_PINNED, byte for byte, and with this head's labels
# every case moves (ServedLabelParityStructureTests; measured on the head tree).
PINNED = {
    'a-conflict-in-the-record': '6380134d7590246aca7435c1e44beda22278f39e7534a86bbad8626f92539cec',
    'member-date-conflict-answered': 'b3b60803633a31eebaf25586edab15a29c04b60c42393141569a6f4a20bbb0f6',
    'member-date-conflict-failed': '7e8f169be7284bfdc6cf2dcb5539cf95ce5928e874fa4a12da392eb5e5a8225c',
    'polypectomy-and-a-candidate': '1b15b762da8fa7a34267eeed6608b8690c0d75636dc1ade360d6bb4ec80ae487',
    'provider-failed': '49d0bb6a86033c2ab0ac66a28180c6e79f6f19a536b6acf6a5357e77381c9d6a',
    'provider-not-run': 'd69ef509f946ce3a12eb94eb132d3c7af92de1054ab87d236df64367ce8522d0',
    'provider-unknown': '62930a1168a5711c2dd1f93698a75d29aad47f465289df76b47c8189464c1c50',
    'response-refused': 'a9dec7b137a13fd07240a0b631a844c2a27947ffecc826ca6d551001cc591049',
    'second-review': '632a9e01e371e6441a35e3b1cce47c2c001ef272fbe6e04285ad0552001b56d4',
    'two-codes-a-plan-code-and-hcpcs': '67b598bfab21775fc68b8d449084e5403c4a8cc14a52d2c88b12efec2a4136b0',
    'visit-beside-a-procedure': '5450110af72eebd9e3e6ecd46e50448280292392919c0681817abac8cba06c69',
}


def _earlier_catalogue(stack):
    """Every release before the completion repair reconciled with gi-catalogue@1: the older parity tests set it back."""
    from studio.gi import catalogue
    from studio.validation import reconcile
    stack.enter_context(mock.patch.object(catalogue, 'CATALOGUE_VERSION', 'gi-catalogue@1'))
    stack.enter_context(mock.patch.object(reconcile, 'SOURCE', 'cpt-studio:gi-catalogue@1'))
    return stack


class ServedLabelParityTests(SimpleTestCase):
    """The harness repair's I1 declaration (HARNESS.md "GI core and harness repair (2026-11-05)"): with the three reader
    labels set back to installed b0dc3446c64c's, every Corti-only case is byte-identical to the served engine's pin, but
    response-refused, whose only difference is its completeness: a response refused whole is no available answer."""

    def served(self):
        import contextlib
        from unittest import mock
        from tests.test_gi4_state import HARNESS_REPAIR_INSTALLED_LABELS
        stack = contextlib.ExitStack()
        for (module, name), value in HARNESS_REPAIR_INSTALLED_LABELS.items():
            stack.enter_context(mock.patch.object(module, name, value))
        return _earlier_catalogue(stack)

    def test_every_case_but_the_refused_response_is_the_served_engines_byte_for_byte(self):
        with self.served():
            for name, kwargs in cases().items():
                if name != 'response-refused':
                    self.assertEqual(sha256_json(assess(**kwargs)), CORE_REPAIR_PINNED[name], name)

    def test_the_refused_response_differs_only_by_its_completeness(self):
        from studio.validation import engine
        kwargs = cases()['response-refused']
        with self.served():
            ours = assess(**kwargs)
            with mock.patch.object(engine.reconcile, 'completeness', wraps=engine.reconcile.completeness) as spy:
                assess(**kwargs)
            self.assertEqual(spy.call_args.args[3], False)  # provider_ok: the refused response is no available answer
        self.assertNotEqual(sha256_json(ours), CORE_REPAIR_PINNED['response-refused'])
        self.assertIn('the provider response was not available', ours.completeness['reasons'])
        self.assertEqual(ours.completeness['state'], 'incomplete')
        self.assertEqual(ours.proposals, ())


class ServedLabelParity3Tests(SimpleTestCase):
    """Harness repair 3's I1 declaration (HARNESS.md "Harness repair 3"): with the three reader labels set back to
    installed e6d451f03d86's, every Corti-only case is byte-identical to the harness repair's pin - P-ADMIT2, F-TIME,
    F-NEG S and the layout repairs move nothing a Corti-only assessment of these cases records but its labels."""

    def test_every_case_is_the_installed_engines_byte_for_byte(self):
        import contextlib
        from unittest import mock
        from tests.test_gi4_state import HARNESS_REPAIR_3_INSTALLED_LABELS
        with contextlib.ExitStack() as stack:
            for (module, name), value in HARNESS_REPAIR_3_INSTALLED_LABELS.items():
                stack.enter_context(mock.patch.object(module, name, value))
            _earlier_catalogue(stack)
            for name, kwargs in cases().items():
                self.assertEqual(sha256_json(assess(**kwargs)), HARNESS_REPAIR_PINNED[name], name)
        # and the labels moved every digest: no case is pinned twice by accident
        for name, kwargs in cases().items():
            self.assertNotEqual(sha256_json(assess(**kwargs)), HARNESS_REPAIR_PINNED[name], name)


class ServedLabelParityCompletionTests(SimpleTestCase):
    """The completion repair's I1 declaration (HARNESS.md, "Completion repair, 2026-11-06"): with its four reader labels set
    back to installed fd8040d71e44's and the catalogue's to @1, every Corti-only case is byte-identical to harness repair
    3's pin - the readers' repairs, equal eligibility, member answers and the dilation technique move nothing these
    assessments record but their labels."""

    def test_every_case_is_the_installed_engines_byte_for_byte(self):
        import contextlib
        from tests.test_gi4_state import COMPLETION_INSTALLED_LABELS
        with contextlib.ExitStack() as stack:
            for (module, name), value in COMPLETION_INSTALLED_LABELS.items():
                stack.enter_context(mock.patch.object(module, name, value))
            _earlier_catalogue(stack)
            for name, kwargs in cases().items():
                self.assertEqual(sha256_json(assess(**kwargs)), HARNESS_REPAIR_3_PINNED[name], name)
        for name, kwargs in cases().items():
            self.assertNotEqual(sha256_json(assess(**kwargs)), HARNESS_REPAIR_3_PINNED[name], name)

class ServedLabelParityStructureTests(SimpleTestCase):
    """The structure round's I1 declaration (HARNESS.md, "The structure round"): with routing, the inventory and its
    source set back to installed aeae34bebbe5's, every Corti-only case is byte-identical to the walk round's pin - the
    direct-reach twin (U14), the full twin's bolus removal (U16) and the computed heading twin's release (U18) move
    nothing these assessments record but their labels."""

    def test_every_case_is_the_installed_engines_byte_for_byte(self):
        import contextlib
        from tests.test_gi4_state import STRUCTURE_ROUND_INSTALLED_LABELS
        with contextlib.ExitStack() as stack:
            for (module, name), value in STRUCTURE_ROUND_INSTALLED_LABELS.items():
                stack.enter_context(mock.patch.object(module, name, value))
            for name, kwargs in cases().items():
                self.assertEqual(sha256_json(assess(**kwargs)), WALK_ROUND_PINNED[name], name)
        for name, kwargs in cases().items():
            self.assertNotEqual(sha256_json(assess(**kwargs)), WALK_ROUND_PINNED[name], name)


class PinnedParityTests(SimpleTestCase):
    def test_every_case_is_pinned(self):
        self.assertEqual(sorted(PINNED), sorted(cases()))

    def test_no_participant_is_byte_identical_to_the_round_4_engine(self):
        from studio.validation.engine import participant_codes  # noqa: F401 - this tree is the harness's
        for name, kwargs in cases().items():
            self.assertEqual(sha256_json(assess(**kwargs)), PINNED[name], name)
            self.assertEqual(sha256_json(assess(**kwargs, participants=())), PINNED[name], name)

    def test_no_participant_and_no_confirmation_is_byte_identical_to_the_round_4_engine(self):
        """harness@2 (HARNESS.md 11.3): with no reviewer-confirmed finding either, nothing changes - in every call form."""
        for name, kwargs in cases().items():
            self.assertEqual(sha256_json(assess(**kwargs, confirmed=())), PINNED[name], name)
            self.assertEqual(sha256_json(assess(**kwargs, participants=(), confirmed=())), PINNED[name], name)
            self.assertEqual(sha256_json(assess(**kwargs, confirmed=[], participants=[])), PINNED[name], name)

    def test_the_cases_reach_the_paths_they_name(self):
        """The pins are only as good as what the cases exercise: a selected, an excluded and an alternative proposal; a
        second review's proposal; the same-day E/M rule; a conflict; every provider status; a member's date conflict."""
        results = {name: assess(**kwargs) for name, kwargs in cases().items()}
        buckets = {p.bucket for p in results['two-codes-a-plan-code-and-hcpcs'].proposals}
        self.assertEqual(buckets, {'selected', 'excluded'})
        self.assertIn('alternative', {p.bucket for p in results['polypectomy-and-a-candidate'].proposals})
        self.assertIn('second_review', {p.support.get('origin') for p in results['second-review'].proposals})
        visit = next(p for p in results['visit-beside-a-procedure'].proposals if p.code == '99213')
        self.assertIn('em.same_day_procedure', {c.id for c in visit.checks})
        self.assertTrue(results['a-conflict-in-the-record'].services['conflicts'])
        for name in ('provider-failed', 'provider-unknown', 'provider-not-run', 'response-refused',
                     'member-date-conflict-failed'):
            self.assertEqual(results[name].proposals, (), name)
        self.assertEqual(cases()['member-date-conflict-failed']['context']['service_date'].origin, 'conflict')
