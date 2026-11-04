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
PINNED = {
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
