"""The per-code rule of the events engine (Gemini migration slice S08; design/FINAL.md 7.2-7.6, as design/ADJUDICATION.md
C-1, C-6, C-7, C-9 and C-10 amend it), SYNTHETIC: one test per row of 7.2 (R1-R9), per rule of 7.4 (h1-h6 and C-9, and
their order), per arm of 7.5 (the deciding attributes and their bases; the broad statement, which excludes only the code
citing it and otherwise asks its scope, C-7; the citation within the statement's own kind, status, time and target
words, C-10; C-10's partial citation, one span or two; the omission case of P4, the broad denial beside an omitted act;
the exceptive statement of C-7; the doubt of condition 4), and 7.6. C-1's examination-as-session is tested on every EUS
code, on an examination-only document and with the act.

Each fixture is a synthetic Gemini answer over a synthetic document, read by read.read and normalized with the real
linked steps (slices S01-S03), then assessed through assess.assess with a synthetic Corti response whose spans are the
document's own. Nothing is sent. The builders here are the S08 test modules' shared builders (test_interpretation_
{assess,coverage,combination,cases} import them)."""
from __future__ import annotations

import hashlib
from unittest import mock

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.interpretation import assess, events, facts, mapping, normalize
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, ReferenceSourceInfo
from tests.test_interpretation_identity import a, accepted, act, answer, les, sc, snare, tg

# --- the shared builders -----------------------------------------------------------------------------------------------

ENDOSCOPIST = 'Endoscopist: Ana Ruiz, MD (fictional).'
NAMED = {'documenting_endoscopist': {'words': 'Ana Ruiz, MD (fictional)', 'passages': ['P9']}}
COLONOSCOPE = 'The colonoscope was advanced to the cecum.'
POLYP = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
L1 = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='6 mm')


def exam(eid: str = 'E1', passage: str = 'P1', words: str = 'colonoscope', status_words: str = 'was advanced',
         **changes) -> dict:
    """A current performed examination by the documenting team, its endoscope named by ``words``."""
    return act(eid, passage, 'examination', words, status_words=status_words,
               technique=a('endoscope', words, [passage]), **changes)


def reached(eid: str = 'E1', landmark: str = 'cecum', words: str = 'cecum', passage: str = 'P1') -> dict:
    return {'event': eid, 'landmark': landmark, 'words': words, 'passages': [passage], 'completion': a('not_stated')}


def removed(eid: str = 'E2', passage: str = 'P2', lesion: str = 'L1', **changes) -> dict:
    """The cold snare removal of L1 in the sigmoid colon (POLYP)."""
    return snare(eid, passage, target=tg(lesion, 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', [passage]),
                 **changes)


def inventory(lines: dict, *, events=(), lesions=(), reach=(), visits=(), named=False, open_questions=(),
              **encounter):
    """(the normalized inventory, the document's text) of a synthetic answer (P0 is the date line)."""
    lines = dict(lines)
    extra = dict(encounter)
    if named:
        lines['P9'] = ENDOSCOPIST
        extra.update(NAMED)
    if reach:
        extra['reach'] = list(reach)
    if visits:
        extra['visit_facts'] = list(visits)
    value, text = answer(lines, events=list(events), lesions=list(lesions), open_questions=list(open_questions),
                         **extra)
    return normalize.normalize(accepted(value), text), text


def colonoscopy(*more, lines=None, lesions=(L1,), reach=True, polyp=None, **options):
    """A colonoscopy to the cecum (E1, P1) with the cold snare removal of L1 (E2, P2), plus ``more`` events."""
    base = {'P1': COLONOSCOPE, 'P2': POLYP}
    base.update(lines or {})
    return inventory(base, events=[exam(), polyp if polyp is not None else removed(), *more], lesions=lesions,
                     reach=[reached()] if reach else (), **options)


def response(text: str, codes, provider: str = 'corti') -> NormalizedResponse:
    """A synthetic Corti response: (code, the document's phrase it cites - or a tuple of phrases, one span each[,
    role]) each."""
    out = []
    for item in codes:
        code, cited = item[0], item[1]
        role = item[2] if len(item) > 2 else 'selected'
        phrases = (cited,) if isinstance(cited, str) else tuple(cited)
        spans = tuple(EvidenceSpan(0, text.index(phrase), text.index(phrase) + len(phrase), phrase, True)
                      for phrase in phrases)
        out.append(ProviderCode(role, 'cpt', code, 'UNVERIFIED PROVIDER WORDING', spans))
    return NormalizedResponse(provider, 'test@1', tuple(out))


def _info(key: str, kind: str, release: str) -> ReferenceSourceInfo:
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=key, release=release, url='https://x',
                               sha256=hashlib.sha256(key.encode()).hexdigest(), effective_start='2026-10-01',
                               effective_end='2026-12-31', license_note='', scope_note='')


def _pfs(mult_proc: str, endo_base, global_days: str = '000') -> dict:
    return {'status': 'A', 'global_days': global_days, 'mult_proc': mult_proc, 'endo_base': endo_base, 'pctc': '0'}


# Synthetic reference rows (test data only), in the shape of tests/test_cux_review.py's.
ROWS = {'43235': _pfs('2', None), '43239': _pfs('3', '43235'), '43249': _pfs('3', '43235'),
        '43248': _pfs('3', '43235'), '43242': _pfs('2', None), '43237': _pfs('2', None),
        '45378': _pfs('2', None), '45380': _pfs('3', '45378'), '45381': _pfs('3', '45378'),
        '45384': _pfs('3', '45378'), '45385': _pfs('3', '45378'), '45386': _pfs('3', '45378'),
        '45390': _pfs('3', '45378'), '43260': _pfs('2', None), '43262': _pfs('3', '43260'),
        '99213': _pfs('0', None, 'XXX'), '99214': _pfs('0', None, 'XXX')}
MUE_ROW = {'value': 1, 'mai': {'indicator': '2', 'label': 'Date of Service Edit: Policy'}, 'rationale': 'Anatomic'}
PFS_KEY, MUE_KEY = 'cms-pfs-rvu26d', 'cms-mue-practitioner-2026q4'
LOOKUP = InMemoryReferenceLookup([_info(PFS_KEY, 'cms-pfs', 'RVU26D'), _info(MUE_KEY, 'cms-mue-practitioner', '2026-Q4')],
                                 {PFS_KEY: {(code, ''): row for code, row in ROWS.items()},
                                  MUE_KEY: {(code, ''): MUE_ROW for code in ROWS}})


def run(inv, text: str, codes, *, user_values=None, reference=LOOKUP, provider_status: str = 'succeeded', **options):
    derived = facts.derive(inv, user_values or {})
    return assess.assess(inventory=inv, context=derived.facts,
                         normalized=response(text, codes) if provider_status == 'succeeded' else None,
                         provider_status=provider_status, reference=reference, text=text,
                         pages=(PageSpan(1, 0, len(text)),), extraction_status='ok', **options)


def proposal(result, code: str, bucket=None):
    found = [p for p in result.proposals if p.code == code and (bucket is None or p.bucket == bucket)]
    assert len(found) == 1, [(p.key, p.code, p.bucket) for p in result.proposals]
    return found[0]


def asked(p) -> list:
    return [spec.fact for spec in p.clarifications]


def check(p, cid: str):
    found = [item for item in p.checks if item.id == cid]
    return found[0] if found else None


def evaluate(inv, code: str, phrase: str, text: str):
    start = text.index(phrase)
    kept = (EvidenceSpan(0, start, start + len(phrase), phrase, True),)
    return events.evaluate(code, kept, events.Reading.of(inv))


# --- 7.2: the rule, in order -------------------------------------------------------------------------------------------

class RuleRows(SimpleTestCase):
    def test_r1_out_of_scope_is_excluded_and_not_reinstatable(self):
        inv, text = colonoscopy()
        result = run(inv, text, [('45385', POLYP), ('G0105', COLONOSCOPE)])
        p = proposal(result, 'G0105')
        self.assertEqual((p.bucket, p.status, p.reinstatable), ('excluded', 'excluded', False))
        self.assertEqual(check(p, 'scope.cpt').status, 'fail')

    def test_r1_no_exact_evidence_is_excluded_and_not_reinstatable(self):
        inv, text = colonoscopy()
        codes = response(text, [('45385', POLYP)]).codes + (ProviderCode('selected', 'cpt', '45380', 'X', (
            EvidenceSpan(0, 0, 10, 'not there!', True),)),)
        derived = facts.derive(inv, {})
        result = assess.assess(inventory=inv, context=derived.facts, normalized=NormalizedResponse('corti', 't@1', codes),
                               provider_status='succeeded', reference=LOOKUP, text=text)
        p = proposal(result, '45380')
        self.assertEqual((p.status, p.reinstatable, p.exclusion_reason), ('excluded', False, 'No exact source evidence'))

    def test_r2_a_code_with_no_profile_is_held_never_ready(self):
        """C-6: route (c) is removed - an unprofiled code (45305, gi.other) beside a performed examination of its own
        procedure and a biopsy denial is held 'outside CPT Studio's coding profiles; review required'."""
        lines = {'P1': 'The rigid proctoscope was advanced to 15 cm.', 'P2': 'No biopsies were taken.'}
        inv, text = inventory(lines, events=[
            act('E1', 'P1', 'examination', 'rigid proctoscope', status_words='was advanced',
                procedure=a('other_gi', 'rigid proctoscope', ['P1'])),
            act('E2', 'P2', 'biopsy', 'biopsies', status='not_performed', status_words='No biopsies were taken',
                procedure=a('other_gi', 'biopsies', ['P2']), scope=sc('all_of_kind', 'No', ['P2']))])
        result = run(inv, text, [('45305', lines['P1'])])
        p = proposal(result, '45305')
        self.assertEqual(p.status, 'needs_clarification')
        self.assertEqual(asked(p), ['performed_status'])
        self.assertIn("outside CPT Studio's coding profiles; review required", p.clarifications[0].reason)
        self.assertEqual(p.support['reason'], events.UNPROFILED)

    def test_r3_a_supporting_event_makes_the_act_code_ready(self):
        inv, text = colonoscopy()
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual(p.status, 'ready')
        self.assertEqual(p.support['state'], 'performed')
        self.assertEqual([act_['id'] for act_ in p.support['acts']], ['E2'])
        self.assertEqual(check(p, 'service.status').status, 'pass')
        self.assertEqual(check(p, 'events.match').status, 'pass')

    def test_r4_the_device_class_of_a_technique_code(self):
        lines = {'P1': 'The gastroscope was advanced to the second portion of the duodenum.',
                 'P2': 'The distal esophageal stricture was dilated with a through-the-scope balloon to 15 mm.'}

        def dilation(technique):
            return act('E2', 'P2', 'dilation', 'dilated', procedure=a('egd'), technique=technique,
                       target=tg('', 'distal_esophagus', 'distal esophageal', ['P2']))

        def assessed(technique):
            inv, text = inventory(lines, events=[exam(words='gastroscope', procedure=a('egd')), dilation(technique)],
                                  reach=[reached(landmark='second_portion_duodenum',
                                                 words='second portion of the duodenum')])
            return proposal(run(inv, text, [('43249', lines['P2'])]), '43249')

        self.assertEqual(assessed(a('balloon', 'through-the-scope balloon', ['P2'])).status, 'ready')
        unstated = assessed(a('not_stated'))
        self.assertEqual((unstated.status, asked(unstated)), ('needs_clarification', ['technique']))
        self.assertIn('Which technique was used for the dilation', unstated.clarifications[0].question)
        lines['P2'] = 'The distal esophageal stricture was dilated with Savary dilators over a guide wire to 15 mm.'
        savary = assessed(a('wire_bougie', 'Savary dilators over a guide wire', ['P2']))
        self.assertEqual(asked(savary), ['technique'])
        self.assertIn('states a dilation with dilators passed over a guide wire. Was a balloon dilation performed',
                      savary.clarifications[0].question)
        self.assertNotEqual(savary.status, 'excluded')  # h6: never excluded

    def test_r5_every_supporting_act_part_of_another_holds_with_the_legacy_sentence(self):
        lines = {'P2': 'A 25 mm flat lesion in the cecum was lifted with a submucosal injection and resected by EMR.'}
        lesion = les('L1', '25 mm flat lesion', 'P2', landmark='cecum', site_words='cecum', size_words='25 mm')
        emr = act('E2', 'P2', 'emr', 'EMR', status_words='resected by EMR',
                  target=tg('L1', 'cecum', '25 mm flat lesion in the cecum', ['P2']))
        lift = act('E3', 'P2', 'injection', 'submucosal injection', status_words='was lifted with a submucosal injection',
                   target=tg('L1', 'cecum', '25 mm flat lesion in the cecum', ['P2']), part_of='E2',
                   purpose=a('lift_for_resection', 'lifted', ['P2']))
        inv, text = colonoscopy(lift, polyp=emr, lesions=(lesion,), lines=lines)
        result = run(inv, text, [('45390', lines['P2']), ('45381', lines['P2'])])
        self.assertEqual(proposal(result, '45390').status, 'ready')
        p = proposal(result, '45381')
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status']))
        self.assertIn('which is part of another documented act: A submucosal injection made to lift a lesion',
                      check(p, 'service.status').detail)
        self.assertEqual(p.support['reason'], events.BUNDLED)

    def test_r6_a_required_fact_the_inventory_does_not_verify_is_asked(self):
        inv, text = colonoscopy(reach=False)
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual(asked(p), ['extent'])
        self.assertEqual(check(p, 'facts.required').status, 'warn')

    def test_r7_an_unknown_date_holds_every_code(self):
        inv, text = colonoscopy(date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [],
                                                 'other_dates': []})
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        self.assertEqual(p.status, 'needs_clarification')
        self.assertEqual(check(p, 'context.service_date').status, 'fail')
        self.assertEqual([spec.fact for spec in result.clarifications], ['service_date'])

    def test_r9_the_reference_checks_are_recorded_and_a_failed_mue_never_holds(self):
        inv, text = colonoscopy()
        result = run(inv, text, [('45385', POLYP), ('45385', POLYP)])
        p = proposal(result, '45385')
        self.assertEqual(p.units, 2)
        self.assertEqual(check(p, 'mue.units').status, 'fail')
        self.assertEqual(check(p, 'pfs.presence').status, 'pass')
        self.assertIsNotNone(check(p, 'pfs.endoscopic_base'))
        self.assertEqual(p.status, 'ready')


# --- C-1: the examination is the session, never an act ----------------------------------------------------------------

EUS_LINES = {'P1': 'A linear echoendoscope was advanced to the duodenum.',
             'P2': 'The pancreatic head was examined; a 2.5 cm hypoechoic mass in the pancreatic head was seen.',
             'P3': 'The mass was sampled with a 22-gauge needle, three passes.',
             'P4': 'No fine-needle aspiration was performed.'}


def eus(*more, act_lines=('P1', 'P2'), reach=()):
    """An upper EUS (E1: the echoendoscope advanced to the duodenum, P1; the pancreatic head examined, P2) plus ``more``
    events; ``reach`` the encounter's reach entries (none by default: the EUS examination's reach is then not stated, and
    a code with an EUS examination class asks it, DECISIONS D28)."""
    lines = {pid: EUS_LINES[pid] for pid in act_lines + tuple(event['status']['passages'][0] for event in more)}
    examination = exam(words='echoendoscope', procedure=a('eus'), target=tg('', 'pancreas', 'pancreatic head', ['P2']))
    examination['target']['passages'] = ['P2']
    return inventory(lines, events=[examination, *more], reach=reach)


DUODENAL_REACH = reached('E1', 'duodenum', 'duodenum', 'P1')  # EUS_LINES['P1']: a full examination's reach (D28)


FNA = act('E2', 'P3', 'fna', 'sampled', status_words='was sampled with a 22-gauge needle',
          technique=a('needle', '22-gauge needle', ['P3']), procedure=a('eus'))
NO_FNA = act('E2', 'P4', 'fna', 'fine-needle aspiration', status='not_performed',
             status_words='No fine-needle aspiration was performed', procedure=a('eus'),
             scope=sc('all_of_kind', 'No', ['P4']))


class ExaminationIsTheSession(SimpleTestCase):
    """ADJUDICATION C-1: every EUS code covers eus_exam, the session; a code covering it beside another kind needs a
    supporting event of that other kind. One test per EUS code, on an examination-only document and with the act."""
    WITH_ACT = {code: profile.covers for code, profile in catalogue.CODES.items()
                if profile.family == 'gi.eus' and len(profile.covers) > 1}
    EXAM_ONLY = tuple(code for code, profile in catalogue.CODES.items()
                      if profile.family == 'gi.eus' and profile.covers == ('eus_exam',))

    def test_the_eus_codes_are_all_covered_here(self):
        self.assertEqual(set(self.WITH_ACT) | set(self.EXAM_ONLY),
                         {code for code, profile in catalogue.CODES.items() if profile.family == 'gi.eus'})
        self.assertEqual(len(self.WITH_ACT) + len(self.EXAM_ONLY), 14)

    def test_every_act_code_on_an_examination_only_document_is_never_ready(self):
        inv, text = eus()
        for code in self.WITH_ACT:
            with self.subTest(code=code):
                p = proposal(run(inv, text, [(code, EUS_LINES['P1'])]), code)
                self.assertNotEqual(p.status, 'ready')
                self.assertNotIn('E1', [item['id'] for item in p.support['acts']])

    def test_every_act_code_beside_its_acts_denial_is_never_ready(self):
        """The refuter's C-1 scenario: an examination and an explicit FNA denial."""
        inv, text = eus(NO_FNA)
        for code, covers in self.WITH_ACT.items():
            with self.subTest(code=code):
                p = proposal(run(inv, text, [(code, EUS_LINES['P1'])]), code)
                self.assertNotEqual(p.status, 'ready')

    def test_an_fna_code_with_the_sampling_is_supported_by_it(self):
        inv, text = eus(FNA)
        for code, covers in self.WITH_ACT.items():
            if 'fna' not in covers:
                continue
            with self.subTest(code=code):
                p = proposal(run(inv, text, [(code, EUS_LINES['P3'])]), code)
                self.assertEqual([item['id'] for item in p.support['acts']], ['E2'])
                self.assertEqual(p.support['state'], 'performed')

    def test_an_injection_or_drainage_code_needs_its_own_act_not_the_fna(self):
        inv, text = eus(FNA)
        for code, covers in self.WITH_ACT.items():
            if 'fna' in covers:
                continue
            with self.subTest(code=code):
                p = proposal(run(inv, text, [(code, EUS_LINES['P3'])]), code)
                self.assertEqual(p.support['state'], 'uncertain')
                self.assertNotEqual(p.status, 'ready')

    def test_every_examination_only_code_is_supported_by_the_examination(self):
        inv, text = eus()
        for code in self.EXAM_ONLY:
            with self.subTest(code=code):
                p = proposal(run(inv, text, [(code, EUS_LINES['P1'])]), code)
                self.assertEqual([item['id'] for item in p.support['acts']], ['E1'])

    def test_the_requirement_groups(self):
        self.assertEqual(events.requirements(mapping.code_link('43242')), (('fna',),))
        self.assertEqual(events.requirements(mapping.code_link('43259')), (('eus_exam',),))
        self.assertEqual(events.requirements(mapping.code_link('45378')), (('examination',),))
        self.assertEqual(events.requirements(mapping.code_link('45381')), (('injection', 'tattoo'),))  # one act
        self.assertEqual(events.requirements(mapping.code_link('46221')), (('band_ligation',),))
        self.assertEqual(events.requirements(mapping.code_link('45305')), ())


# --- DECISIONS D27: the defining kinds (FINAL 7.3) ---------------------------------------------------------------------

ERCP_LINES = {'P1': 'The duodenoscope was advanced to the major papilla.', 'P2': 'The common bile duct was cannulated.',
              'P3': 'Three stones were extracted from the bile duct with an extraction balloon.',
              'P4': 'Mechanical lithotripsy of a 15 mm stone was performed.', 'P5': 'No lithotripsy was performed.',
              'P6': 'No stones were extracted.'}
LITHOTRIPSY = act('E4', 'P4', 'lithotripsy', 'lithotripsy', status_words='was performed', procedure=a('ercp'))
NO_LITHOTRIPSY = act('E4', 'P5', 'lithotripsy', 'lithotripsy', status='not_performed',
                     status_words='No lithotripsy was performed', procedure=a('ercp'),
                     scope=sc('all_of_kind', 'No', ['P5']))


def ercp(*more, extraction=True):
    """An ERCP (E1) with the common bile duct cannulated (E2) and, by default, a balloon stone extraction (E3)."""
    acts = [exam(words='duodenoscope', procedure=a('ercp')),
            act('E2', 'P2', 'cannulation', 'cannulated', status_words='was cannulated', procedure=a('ercp'),
                target=tg('', 'common_bile_duct', 'common bile duct', ['P2']))]
    if extraction:
        acts.append(act('E3', 'P3', 'stone_extraction', 'extracted', status_words='were extracted', procedure=a('ercp'),
                        technique=a('extraction_balloon', 'extraction balloon', ['P3'])))
    lines = {pid: ERCP_LINES[pid] for pid in ('P1', 'P2') + (('P3',) if extraction else ())
             + tuple(event['status']['passages'][0] for event in more)}
    return inventory(lines, events=acts + list(more))


class DefiningKinds(SimpleTestCase):
    """DECISIONS D27 (fb13: 43265 READY on a balloon extraction): a code D27 narrows is matched only by an event of a
    defining kind - a kind no other code of its family accounts for alone; with none, R3's failure path over those kinds
    (7.6 here: not documented, naming the defining act). Every other code is unaffected."""

    def test_the_lithotripsy_code_on_a_balloon_extraction_is_held_not_documented_and_43264_stays_ready(self):
        inv, text = ercp()
        result = run(inv, text, [('43264', ERCP_LINES['P3']), ('43265', ERCP_LINES['P3'])])
        self.assertEqual((proposal(result, '43264').status, [item['id'] for item in proposal(result, '43264')
                                                             .support['acts']]), ('ready', ['E3']))
        p = proposal(result, '43265')
        self.assertEqual((p.status, asked(p), p.support['reason'], p.support['acts']),
                         ('needs_clarification', ['performed_status'], events.NOT_DOCUMENTED, []))
        self.assertEqual(p.clarifications[0].reason, "CPT Studio's reading of the document records no lithotripsy "
                                                     'documented as done on the date of service.')
        self.assertEqual(p.support['summary'], 'CPT Studio could not confirm the lithotripsy as done on the date of '
                                               'service.')
        self.assertEqual(result.completeness['unresolved_items'], [])  # the extraction is 43264's

    def test_alone_the_lithotripsy_code_leaves_the_extraction_uncovered(self):
        inv, text = ercp()
        result = run(inv, text, [('43265', ERCP_LINES['P3'])])
        self.assertEqual(proposal(result, '43265').status, 'needs_clarification')
        self.assertEqual([(item['act'], item['reason']) for item in result.completeness['unresolved_items']],
                         [('stone_extraction', 'not_covered')])

    def test_the_lithotripsy_code_with_its_lithotripsy_is_ready(self):
        inv, text = ercp(LITHOTRIPSY)
        result = run(inv, text, [('43264', ERCP_LINES['P3']), ('43265', ERCP_LINES['P4'])])
        p = proposal(result, '43265')
        self.assertEqual((p.status, [item['id'] for item in p.support['acts']]), ('ready', ['E4']))
        self.assertEqual(proposal(result, '43264').status, 'ready')

    def test_r3s_failure_path_reads_the_defining_kinds_only(self):
        """A denial of the defining act the code cites excludes it (7.5, reinstatable); a denial of the act another
        code accounts for alone no longer concerns it (7.6, held)."""
        inv, text = ercp(NO_LITHOTRIPSY)
        p = proposal(run(inv, text, [('43264', ERCP_LINES['P3']), ('43265', 'No lithotripsy was performed')]), '43265')
        self.assertEqual((p.bucket, p.reinstatable, p.support['exclusion']['event']), ('excluded', True, 'E4'))
        no_extraction = act('E3', 'P6', 'stone_extraction', 'extracted', status='not_performed',
                            status_words='No stones were extracted', procedure=a('ercp'), scope=sc('all_of_kind', 'No',
                                                                                                    ['P6']))
        inv, text = ercp(no_extraction, extraction=False)
        result = run(inv, text, [('43264', 'No stones were extracted'), ('43265', 'No stones were extracted')])
        self.assertEqual(proposal(result, '43264').bucket, 'excluded')
        p = proposal(result, '43265')
        self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.NOT_DOCUMENTED))

    def test_the_hot_forceps_enteroscopy_code_needs_its_hot_forceps_removal(self):
        lines = {'P1': 'The enteroscope was advanced to the jejunum.',
                 'P2': 'Two jejunal angioectasias were treated with argon plasma coagulation.',
                 'P3': 'A 5 mm jejunal polyp was removed with hot biopsy forceps.'}

        def enteroscopy(event):
            pid = event['status']['passages'][0]
            return inventory({'P1': lines['P1'], pid: lines[pid]},
                             events=[exam(words='enteroscope', procedure=a('enteroscopy')), event],
                             reach=[reached(landmark='jejunum', words='jejunum')])

        inv, text = enteroscopy(act('E2', 'P2', 'ablation', 'argon plasma coagulation', status_words='were treated',
                                    procedure=a('enteroscopy'),
                                    technique=a('argon_plasma', 'argon plasma coagulation', ['P2'])))
        result = run(inv, text, [('44365', lines['P2']), ('44369', lines['P2'])])
        self.assertEqual(proposal(result, '44369').status, 'ready')
        p = proposal(result, '44365')
        self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.NOT_DOCUMENTED))
        self.assertIn('records no hot forceps removal documented', p.clarifications[0].reason)
        inv, text = enteroscopy(act('E2', 'P3', 'hot_biopsy', 'hot biopsy forceps', status_words='was removed',
                                    procedure=a('enteroscopy'), technique=a('hot_forceps', 'hot biopsy forceps', ['P3'])))
        self.assertEqual(proposal(run(inv, text, [('44365', lines['P3'])]), '44365').status, 'ready')

    def test_the_percutaneous_gastrostomy_code_needs_its_gastrostomy(self):
        lines = {'P1': 'A 14 Fr jejunostomy tube was placed percutaneously under fluoroscopic guidance.',
                 'P2': 'A 20 Fr gastrostomy tube was placed percutaneously under fluoroscopic guidance.'}
        inv, text = inventory({'P1': lines['P1']}, events=[act('E1', 'P1', 'tube_placement', 'jejunostomy tube',
                                                               status_words='was placed',
                                                               procedure=a('feeding_tube'))])
        result = run(inv, text, [('49440', lines['P1']), ('49441', lines['P1'])])
        self.assertEqual(proposal(result, '49441').status, 'ready')
        p = proposal(result, '49440')
        self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.NOT_DOCUMENTED))
        self.assertIn('records no gastrostomy (PEG) placement documented', p.clarifications[0].reason)
        inv, text = inventory({'P2': lines['P2']}, events=[act('E1', 'P2', 'peg', 'gastrostomy tube',
                                                               status_words='was placed', procedure=a('feeding_tube'))])
        self.assertEqual(proposal(run(inv, text, [('49440', lines['P2'])]), '49440').status, 'ready')

    def test_the_requirement_groups_of_the_narrowed_codes(self):
        self.assertEqual([events.requirements(mapping.code_link(code)) for code in ('43265', '44365', '49440')],
                         [(('lithotripsy',),), (('hot_biopsy',),), (('peg',),)])
        # not narrowed: both kinds their own (44372, 45381), or every kind another code's alone too (45385 and 44394)
        self.assertEqual([events.requirements(mapping.code_link(code)) for code in ('44372', '45381', '45385')],
                         [(('tube_placement', 'peg'),), (('injection', 'tattoo'),), (('snare',),)])
        self.assertEqual(events.accounted(mapping.code_link('43265')), ('lithotripsy',))
        self.assertEqual(events.accounted(mapping.code_link('43242')), ('fna',))


# --- DECISIONS D29: the site of a dilation (R4) --------------------------------------------------------------------------

EGD_REACH = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'


def dilated(line: str, target: dict, lesions=(), technique=('balloon', 'through-the-scope balloon')):
    """An EGD to the second portion of the duodenum (E1, G1) with one dilation (E2, G2) at ``target``."""
    dilation = act('E2', 'G2', 'dilation', 'dilated', procedure=a('egd'), target=target,
                   technique=a(technique[0], technique[1], ['G2']))
    return inventory({'G1': EGD_REACH, 'G2': line}, lesions=lesions,
                     events=[exam('E1', 'G1', words='gastroscope', procedure=a('egd')), dilation],
                     reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'G1')])


ESOPHAGEAL = ('The distal esophageal stricture was dilated with a through-the-scope balloon to 15 mm.',
              tg('', 'distal_esophagus', 'distal esophageal', ['G2']))
PYLORIC = ('A pyloric stricture was dilated with a through-the-scope balloon to 15 mm.',
           tg('', 'pylorus', 'pyloric', ['G2']))
ANASTOMOTIC = ('The gastrojejunal anastomotic stricture was dilated with a through-the-scope balloon to 12 mm.',
               tg('', 'anastomosis', 'anastomotic', ['G2']))
UNPLACED = ('The stricture was dilated with a through-the-scope balloon to 12 mm.', tg())


class DilationSite(SimpleTestCase):
    """DECISIONS D29 (fb07: 43249 READY on a gastrojejunal anastomotic stricture): a site-specific dilation code is
    supported only by a dilation verified in its class - directly or through its verified lesion's verified site. One
    verified outside the class is the "dilation at another site" hold; one whose place is not settled (not verified, an
    anastomosis) asks which structure was dilated. Never excluded; every other dilation code is unaffected."""

    def assessed(self, case, codes=('43249', '43245'), lesions=()):
        line, target = case
        inv, text = dilated(line, target, lesions)
        result = run(inv, text, [(code, line) for code in codes])
        return [proposal(result, code) for code in codes]

    def test_an_esophageal_dilation_supports_the_esophageal_code_only(self):
        esophageal, gastric = self.assessed(ESOPHAGEAL)
        self.assertEqual((esophageal.status, [item['id'] for item in esophageal.support['acts']]), ('ready', ['E2']))
        self.assertEqual((gastric.status, asked(gastric), gastric.support['reason'], gastric.bucket),
                         ('needs_clarification', ['act_target'], events.ANOTHER_SITE, 'selected'))
        self.assertEqual(gastric.clarifications[0].question,
                         'The documented dilation (“dilated”) is at the distal esophagus. Was a dilation of the stomach '
                         'or duodenum performed on the date of service?')

    def test_a_pyloric_dilation_supports_the_gastric_or_duodenal_code_only(self):
        esophageal, gastric = self.assessed(PYLORIC)
        self.assertEqual(gastric.status, 'ready')
        self.assertEqual((esophageal.status, asked(esophageal), esophageal.support['reason']),
                         ('needs_clarification', ['act_target'], events.ANOTHER_SITE))
        self.assertIn('this code accounts for a dilation of the esophagus, which CPT Studio could not find',
                      check(esophageal, 'service.status').detail)

    def test_an_anastomotic_or_unplaced_dilation_asks_which_structure_was_dilated(self):
        for case in (ANASTOMOTIC, UNPLACED):
            for p in self.assessed(case):
                with self.subTest(line=case[0], code=p.code):
                    self.assertEqual((p.status, asked(p), p.support['reason'], p.bucket),
                                     ('needs_clarification', ['act_target'], events.SITE, 'selected'))
                    self.assertTrue(p.clarifications[0].question.startswith('Which lesion or site was the dilation'))
                    self.assertIn('could not confirm from the document which structure', p.clarifications[0].reason)

    def test_the_verified_site_of_the_verified_lesion_places_the_dilation(self):
        line = ('A 2 cm distal esophageal stricture was found; the stricture was dilated with a through-the-scope '
                'balloon to 15 mm.')
        stricture = les('L1', '2 cm distal esophageal stricture', 'G2', landmark='distal_esophagus',
                        site_words='distal esophageal', size_words='2 cm')
        inv, _ = dilated(line, tg('L1', 'not_stated', 'the stricture', ['G2']), (stricture,))
        reading = events.Reading.of(inv)
        self.assertEqual((mapping.target_landmark(reading.events['E2']), events.site_places(reading, reading.events['E2'])),
                         ('', ('distal_esophagus',)))
        esophageal, gastric = self.assessed((line, tg('L1', 'not_stated', 'the stricture', ['G2'])), lesions=(stricture,))
        self.assertEqual((esophageal.status, gastric.support['reason']), ('ready', events.ANOTHER_SITE))

    def test_the_fit_of_each_place(self):
        reading = events.Reading.of(dilated(*UNPLACED)[0])

        def fit(*places, site=mapping.ESOPHAGEAL):
            with mock.patch.object(events, 'site_places', return_value=places):
                return events.site_fit(reading, reading.events['E2'], site)

        self.assertEqual([fit('distal_esophagus'), fit('gastroesophageal_junction'), fit('stomach'), fit('anastomosis'),
                          fit(), fit('distal_esophagus', 'anastomosis'), fit('distal_esophagus', 'stomach'),
                          fit('stomach', 'anastomosis'), fit('jejunum', 'stomach')],
                         [events.FITS, events.FITS, events.OUTSIDE, events.UNSETTLED, events.UNSETTLED, events.FITS,
                          events.UNSETTLED, events.UNSETTLED, events.OUTSIDE])
        self.assertEqual([fit('duodenal_bulb', site=mapping.GASTRIC_DUODENAL), fit('ampulla', site=mapping.GASTRIC_DUODENAL),
                          fit('gastroesophageal_junction', site=mapping.GASTRIC_DUODENAL)],
                         [events.FITS, events.OUTSIDE, events.OUTSIDE])

    def test_the_technique_is_read_first_and_codes_not_in_the_table_are_unaffected(self):
        line = 'The gastrojejunal anastomotic stricture was dilated with Savary dilators over a guide wire to 12 mm.'
        inv, text = dilated(line, ANASTOMOTIC[1], technique=('wire_bougie', 'Savary dilators over a guide wire'))
        result = run(inv, text, [('43248', line), ('43249', line)])
        p = proposal(result, '43249')  # a balloon code, a dilation over a guide wire: R4's technique decides first
        self.assertEqual((asked(p), p.support['reason']), (['technique'], events.ANOTHER_TECHNIQUE))
        p = proposal(result, '43248')  # the technique fits; the anastomosis does not settle the site
        self.assertEqual((asked(p), p.support['reason']), (['act_target'], events.SITE))
        lines = {'P1': COLONOSCOPE, 'P2': 'The ileocolonic anastomotic stricture was dilated with a through-the-scope '
                                          'balloon to 15 mm.'}
        inv, text = inventory(lines, reach=[reached()], events=[exam(), act(
            'E2', 'P2', 'dilation', 'dilated', technique=a('balloon', 'through-the-scope balloon', ['P2']),
            target=tg('', 'anastomosis', 'anastomotic', ['P2']))])
        self.assertEqual(proposal(run(inv, text, [('45386', lines['P2'])]), '45386').status, 'ready')


# --- 7.4: a positive candidate, no supporting event: held, ONE focused question ----------------------------------------

class Focused(SimpleTestCase):
    def assert_question(self, p, fact: str, *quoted):
        self.assertEqual(p.status, 'needs_clarification')
        self.assertEqual(asked(p), [fact])
        self.assertEqual(p.support['state'], 'uncertain')
        for text in quoted:
            self.assertIn(text, [span['text'] for span in p.support['source']])

    def test_h1_a_contradiction_quotes_both_sides(self):
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']))
        inv, text = colonoscopy(denial, lines={'P3': 'No polyp was removed today.'})
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_question(p, 'conflict:snare', POLYP, 'No polyp was removed today.')
        self.assertIn('both as performed and as not performed', p.clarifications[0].question)
        self.assertEqual((p.support['reason'], [act_['kind'] for act_ in p.support['acts']]), ('conflict', ['snare']))
        self.assertEqual(check(p, 'events.relation').status, 'warn')

    def test_h2_a_doubt(self):
        doubt = act('E3', 'P3', 'removal', 'removed', status='uncertain',
                    status_words='It is unclear whether any polyp was removed', scope=sc('all_of_kind', 'any', ['P3']))
        inv, text = colonoscopy(doubt, lines={'P3': 'It is unclear whether any polyp was removed.'})
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_question(p, 'performed_status', 'It is unclear whether any polyp was removed.')
        self.assertEqual(p.support['reason'], events.DOUBT)

    def test_h2_the_candidates_own_uncertain_status(self):
        inv, text = colonoscopy(polyp=removed(status='uncertain', status_words='was removed'))
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_question(p, 'performed_status', POLYP)

    def test_h3_unresolved_time(self):
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']), time=a('unknown'))
        inv, text = colonoscopy(denial, lines={'P3': 'No polyp was removed.'})
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_question(p, 'event_time')
        self.assertIn('done at this encounter?', p.clarifications[0].question)
        self.assertEqual(p.support['reason'], events.UNRESOLVED)

    def test_h3_unresolved_scope_asks_whether_the_statement_applies(self):
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed')
        inv, text = colonoscopy(denial, lines={'P3': 'No polyp was removed.'})
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assert_question(p, 'statement_scope')
        self.assertIn('Does “No polyp was removed” apply to the snare removal', p.clarifications[0].question)

    def test_h4_each_unusable_attribute_of_lines_1_to_3(self):
        cases = {'event_time': removed(time=a('unknown')), 'event_performer': removed(performer=a('unknown')),
                 'performed_status': removed(status_words='was excised')}
        for fact, polyp in cases.items():
            with self.subTest(fact=fact):
                inv, text = colonoscopy(polyp=polyp)
                p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
                self.assert_question(p, fact, POLYP)
                self.assertEqual(p.support['reason'], events.UNVERIFIED)
                self.assertEqual(check(p, 'events.attributes').status, 'warn')

    def test_h4_an_unsettled_procedure(self):
        lines = {'P0b': 'EGD: the gastroscope was advanced to the duodenum.', 'P1': 'Colonoscopy: ' + COLONOSCOPE,
                 'P2': POLYP}
        inv, text = inventory(lines, lesions=[L1], events=[
            exam('E0', 'P0b', words='gastroscope', procedure=a('egd', 'EGD', ['P0b'])),
            exam(procedure=a('colonoscopy', 'Colonoscopy', ['P1'])), removed()], reach=[reached()])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual(asked(p), ['procedure'])
        self.assertIn('In which procedure was the snare removal', p.clarifications[0].question)

    def test_h5_a_removal_of_unstated_method_asks_the_method(self):
        polyp = act('E2', 'P2', 'removal', 'removed', target=tg('L1', 'sigmoid_colon',
                                                                '6 mm sessile polyp in the sigmoid colon', ['P2']))
        inv, text = colonoscopy(polyp=polyp, lines={'P2': 'A 6 mm sessile polyp in the sigmoid colon was removed.'})
        p = proposal(run(inv, text, [('45385', 'A 6 mm sessile polyp in the sigmoid colon was removed.')]), '45385')
        self.assertEqual(asked(p), ['act_method'])
        self.assertEqual(p.clarifications[0].question,
                         'By which method was the 6 mm sessile polyp in the sigmoid colon removed?')

    def test_c9_an_act_begun_and_not_completed_is_held_never_excluded(self):
        line = 'Piecemeal EMR of the 30 mm lesion in the ascending colon was incomplete because of fibrosis.'
        lesion = les('L1', '30 mm lesion', 'P2', landmark='ascending_colon', site_words='ascending colon',
                     size_words='30 mm')
        emr = act('E2', 'P2', 'emr', 'EMR', status='attempted_not_completed', status_words='was incomplete',
                  target=tg('L1', 'ascending_colon', '30 mm lesion in the ascending colon', ['P2']))
        inv, text = colonoscopy(polyp=emr, lesions=(lesion,), lines={'P2': line})
        p = proposal(run(inv, text, [('45390', line)]), '45390')
        self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['performed_status']))
        self.assertTrue(any(text_.startswith('Incomplete procedure: whether modifier 52 or 53 applies')
                            for text_ in p.modifier_considerations))
        self.assertEqual(p.support['reason'], events.ATTEMPTED)

    def test_an_examination_begun_and_not_completed_supports_its_base_code(self):
        line = 'The colonoscope could not be advanced beyond the splenic flexure.'
        inv, text = inventory({'P1': line}, events=[exam(status='attempted_not_completed',
                                                         status_words='could not be advanced')])
        p = proposal(run(inv, text, [('45378', line)]), '45378')
        self.assertEqual(p.support['state'], 'incomplete')
        incomplete = check(p, 'service.incomplete')
        self.assertEqual(incomplete.status, 'warn')
        self.assertIn('“could not be advanced”', incomplete.detail)  # R-4: worded from its own failure-marker words
        self.assertTrue(any('modifier 52 or 53' in text_ for text_ in p.modifier_considerations))

    def test_rule_order_a_contradiction_wins_over_an_unusable_attribute(self):
        """7.4's order is by RULE, then by candidate: h1 over every positive candidate before h4 over any. The first
        candidate in document order (the sigmoid snare, E2) has only an unusable time (h4; the rectal denial is of
        another lesion, so it is independent of E2); the second (the rectal snare, E4) is the positive side of a
        CONTRADICTION (h1). The one question is the conflict, quoting the rectal statements - never E2's time."""
        lines = {'P3': 'A 4 mm polyp in the rectum was removed with a cold snare.',
                 'P4': 'The rectal polyp was not removed.'}
        rectal = les('L2', '4 mm polyp', 'P3', landmark='rectum', site_words='rectum', size_words='4 mm')
        second = snare('E4', 'P3', target=tg('L2', 'rectum', '4 mm polyp in the rectum', ['P3']))
        denial = act('E5', 'P4', 'removal', 'not removed', status='not_performed', status_words='was not removed',
                     scope=sc('single_target', 'The rectal polyp', ['P4']),
                     target=tg('L2', 'rectum', 'The rectal polyp', ['P4']))
        inv, text = colonoscopy(second, denial, polyp=removed(time=a('unknown')), lesions=(L1, rectal), lines=lines)
        reading = events.Reading.of(inv)  # the fixture is what the test says it is:
        self.assertEqual([item['type'] for item in reading.relations_of('E4')], ['contradiction'])  # h1 on E4
        self.assertEqual(reading.relations_of('E2'), [])  # no blocking relation on E2 (the denial is independent of it)
        self.assertFalse(events.usable(reading.events['E2'], 'time'))  # so only h4 applies to E2
        self.assertLess(reading.order['E2'], reading.order['E4'])  # and E2 comes first in document order
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual(asked(p), ['conflict:snare'])  # exactly one question, and it is h1's
        self.assertEqual(p.support['reason'], events.CONFLICT)
        self.assertEqual({span['text'] for span in p.support['source']}, {lines['P3'], lines['P4']})


# --- 7.5: exclusion, and 7.6: not documented ---------------------------------------------------------------------------

class Exclusion(SimpleTestCase):
    def excluded(self, p, attribute: str, basis: str):
        self.assertEqual((p.bucket, p.status, p.reinstatable), ('excluded', 'excluded', True))
        self.assertEqual((p.support['exclusion']['attribute'], p.support['exclusion']['basis']), (attribute, basis))
        self.assertTrue(p.exclusion_reason.endswith('Reinstate if this code is supported.'))

    def test_status_not_performed_by_a_negator_cited_within_its_own_words(self):
        line = 'No dilation was performed.'
        inv, text = colonoscopy(act('E3', 'P3', 'dilation', 'dilation', status='not_performed',
                                    status_words='No dilation was performed', scope=sc('all_of_kind', 'No', ['P3'])),
                                lines={'P3': line})
        p = proposal(run(inv, text, [('45386', line)]), '45386')
        self.excluded(p, 'status', 'literal')
        self.assertEqual(p.exclusion_reason, 'The document states the dilation was not done: “No dilation was '
                                             'performed”. Reinstate if this code is supported.')

    def test_status_planned_by_a_planning_marker(self):
        line = 'Dilation is planned.'
        inv, text = colonoscopy(act('E3', 'P3', 'dilation', 'Dilation', status='planned',
                                    status_words='Dilation is planned', time=a('future', 'is planned', ['P3'])),
                                lines={'P3': line})
        p = proposal(run(inv, text, [('45386', line)]), '45386')
        self.excluded(p, 'status', 'marker')

    def test_time_earlier_by_a_date_literal(self):
        line = 'Snare polypectomy 2024.'
        inv, text = colonoscopy(act('E3', 'P3', 'snare', 'Snare polypectomy', status_words='Snare polypectomy',
                                    time=a('earlier_encounter', '2024', ['P3'])), lines={'P3': line},
                                polyp=act('E2', 'P2', 'biopsy', 'biopsied'), )
        p = proposal(run(inv, text, [('45385', line)]), '45385')
        self.excluded(p, 'time', 'literal')
        self.assertIn('at an earlier encounter', p.exclusion_reason)

    def test_time_earlier_by_a_marker(self):
        line = 'Prior snare polypectomy.'
        inv, text = colonoscopy(act('E3', 'P3', 'snare', 'snare polypectomy', status_words='snare polypectomy',
                                    time=a('earlier_encounter', 'Prior', ['P3'])), lines={'P3': line},
                                polyp=act('E2', 'P2', 'biopsy', 'removed'))
        p = proposal(run(inv, text, [('45385', line)]), '45385')
        self.excluded(p, 'time', 'marker')

    def assert_scope_question(self, p, statement: str):
        self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['statement_scope']))
        self.assertEqual(p.support['reason'], events.STATEMENT_SCOPE)
        self.assertIsNone(p.support.get('exclusion'))
        self.assertIn(f'Does “{statement}” apply to the', p.clarifications[0].question)

    def test_performer_another_clinician_by_a_titled_name(self):
        """The code cites the statement's own act words (its kind and status words): excluded by the verified other
        clinician. C-10's union is the deciding event's kind, status, time and target words, so a citation reaching
        the performer's name gives the statement_scope question instead - never an exclusion."""
        line = 'Dr. Lena Ortiz snared the polyp.'
        other = act('E3', 'P3', 'snare', 'snared', status_words='snared',
                    performer=a('other_clinician', 'Dr. Lena Ortiz', ['P3']))
        inv, text = colonoscopy(other, lines={'P3': line}, polyp=act('E2', 'P2', 'biopsy', 'removed'), named=True)
        p = proposal(run(inv, text, [('45385', 'snared')]), '45385')
        self.excluded(p, 'performer', 'literal')
        self.assertIn('by another clinician', p.exclusion_reason)
        self.assert_scope_question(proposal(run(inv, text, [('45385', 'Dr. Lena Ortiz snared')]), '45385'), 'snared')

    def test_performer_another_facility_by_a_facility_marker(self):
        line = 'The polyp was snared at an outside hospital.'
        other = act('E3', 'P3', 'snare', 'snared', status_words='was snared',
                    performer=a('other_facility', 'at an outside hospital', ['P3']))
        inv, text = colonoscopy(other, lines={'P3': line}, polyp=act('E2', 'P2', 'biopsy', 'removed'), named=True)
        p = proposal(run(inv, text, [('45385', 'was snared')]), '45385')
        self.excluded(p, 'performer', 'marker')
        self.assert_scope_question(proposal(run(inv, text, [('45385', 'snared at an outside hospital')]), '45385'),
                                   'was snared')

    def test_c7_a_broad_current_denial_excludes_only_the_code_citing_it(self):
        """The v5 class, as ADJUDICATION C-7 decides it: a broad current denial of removal (verified quantifier and
        negator) has no cover of its own. A removal code citing another passage (the scar) is asked whether the
        statement applies - held, never excluded; a removal code citing the denial itself, within its own words, is
        excluded."""
        lines = {'P2': 'A scar from an earlier polypectomy was seen in the rectum.', 'P3': 'No polyp was removed today.'}
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']), time=a('current_encounter', 'today', ['P3']))
        inv, text = colonoscopy(denial, lines=lines, lesions=(), polyp=act('E2', 'P2', 'other', 'scar'))
        held = proposal(run(inv, text, [('45385', lines['P2'])]), '45385')
        self.assert_scope_question(held, 'No polyp was removed')
        self.assertIn(lines['P3'], [span['text'] for span in held.support['source']])  # both sides are quoted
        p = proposal(run(inv, text, [('45385', lines['P3'])]), '45385')
        self.excluded(p, 'status', 'literal')
        self.assertEqual(p.support['exclusion']['cover'], 'citation')

    def test_c7_a_broad_denial_beside_an_omitted_act_asks_its_scope(self):
        """C-7 (c), the omission path it closed: Gemini drops the snare of P2 and records only the broad current denial
        of P3; the proposer cites the snare's own sentence. The code is held with the statement_scope question, never
        excluded by a statement it does not cite."""
        lines = {'P2': POLYP, 'P3': 'No polyp was removed today.'}
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']), time=a('current_encounter', 'today', ['P3']))
        inv, text = inventory({'P1': COLONOSCOPE, **lines}, events=[exam(), denial], reach=[reached()])
        self.assert_scope_question(proposal(run(inv, text, [('45385', POLYP)]), '45385'), 'No polyp was removed')

    def test_c10_a_citation_reaching_beyond_the_statements_words_asks_its_scope(self):
        """The shared-sentence omission (C-10): Gemini dropped today's dilation; the only dilation statement is the
        historical denial in the very sentence the code cites. Held with statement_scope, never excluded."""
        line = ('The anastomotic stricture, which had not been dilated at the 2024 colonoscopy, was dilated today to '
                '15 mm with a through-the-scope balloon.')
        historical = act('E3', 'P3', 'dilation', 'dilated', status='not_performed', status_words='had not been dilated',
                         time=a('earlier_encounter', 'at the 2024 colonoscopy', ['P3']),
                         scope=sc('single_target', 'The anastomotic stricture', ['P3']),
                         target=tg('', 'anastomosis', 'anastomotic stricture', ['P3']))
        inv, text = colonoscopy(historical, lines={'P3': line})
        p = proposal(run(inv, text, [('45386', line)]), '45386')
        self.assertEqual((p.bucket, p.status), ('selected', 'needs_clarification'))
        self.assertEqual(asked(p), ['statement_scope'])
        self.assertEqual(p.support['reason'], events.STATEMENT_SCOPE)

    def test_p4_the_omission_case_is_held_never_excluded(self):
        """P4: Gemini drops a current act; the proposer cites that act's own passage; only a historical denial of the
        kind exists, in another sentence. Coverage fails: held by 7.6. Cited beside the historical denial (two spans of
        one code, the shape of Note #8), the act's span reaches words no word of the denial covers: held with the
        statement_scope question (C-10), never excluded by the one span that lies within the denial's words."""
        lines = {'P3': 'The stricture was dilated to 15 mm with a balloon.',
                 'P4': 'No dilation was carried out in 2024.'}
        historical = act('E3', 'P4', 'dilation', 'dilation', status='not_performed',
                         status_words='No dilation was carried out', time=a('earlier_encounter', 'in 2024', ['P4']),
                         scope=sc('all_of_kind', 'No', ['P4']))
        inv, text = colonoscopy(historical, lines=lines)
        p = proposal(run(inv, text, [('45386', lines['P3'])]), '45386')
        self.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['performed_status']))
        self.assertEqual(p.support['reason'], events.NOT_DOCUMENTED)
        self.assertIn("CPT Studio's reading of the document records no dilation documented as done",
                      p.clarifications[0].reason)
        both = proposal(run(inv, text, [('45386', (lines['P3'], lines['P4']))]), '45386')
        self.assertEqual(len(both.evidence), 2)
        self.assert_scope_question(both, 'No dilation was carried out')
        alone = proposal(run(inv, text, [('45386', lines['P4'])]), '45386')  # the control: the denial alone is cited
        self.excluded(alone, 'status', 'literal')  # the first deciding attribute with a basis: its negator

    def test_c7_an_exceptive_statement_never_excludes(self):
        line = 'No further intervention was performed.'
        exceptive = act('E3', 'P3', 'intervention', 'intervention', status='not_performed',
                        status_words='No further intervention was performed',
                        scope=sc('exceptive', 'No further', ['P3']))
        inv, text = colonoscopy(exceptive, lines={'P3': line})
        p = proposal(run(inv, text, [('45386', line)]), '45386')
        self.assertEqual((p.bucket, p.support['reason']), ('selected', events.NOT_DOCUMENTED))

    def test_an_unverified_deciding_attribute_never_excludes(self):
        line = 'Dilation was performed elsewhere.'
        unverified = act('E3', 'P3', 'dilation', 'Dilation', status='not_performed', status_words='Dilation was performed',
                         scope=sc('all_of_kind', 'Dilation', ['P3']))  # no negator: negation_missing
        inv, text = colonoscopy(unverified, lines={'P3': line})
        p = proposal(run(inv, text, [('45386', line)]), '45386')
        self.assertEqual(p.bucket, 'selected')

    def test_condition_4_a_doubt_of_the_kind_prevents_the_exclusion(self):
        """A broad current denial would exclude 45386; an uncertain dilation verified at an earlier time (so no positive
        candidate of 7.4) still doubts the kind, and the code is held as not documented instead."""
        lines = {'P3': 'No dilation was performed.',
                 'P4': 'It is unclear whether the stricture was dilated previously.'}
        denial = act('E3', 'P3', 'dilation', 'dilation', status='not_performed', status_words='No dilation was performed',
                     scope=sc('all_of_kind', 'No', ['P3']))
        doubt = act('E4', 'P4', 'dilation', 'dilated', status='uncertain', status_words='It is unclear whether',
                    time=a('earlier_encounter', 'previously', ['P4']))
        inv, text = colonoscopy(denial, doubt, lines=lines)
        p = proposal(run(inv, text, [('45386', lines['P3'])]), '45386')
        self.assertEqual((p.bucket, p.support['reason']), ('selected', events.NOT_DOCUMENTED))
        inv, text = colonoscopy(denial, lines=lines)  # the control: without the doubt, the same denial excludes
        self.assertEqual(proposal(run(inv, text, [('45386', lines['P3'])]), '45386').bucket, 'excluded')

    def test_76_no_candidate_at_all_is_not_documented(self):
        inv, text = colonoscopy()
        p = proposal(run(inv, text, [('45386', POLYP)]), '45386')
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['performed_status'], events.NOT_DOCUMENTED))
        self.assertEqual(p.clarifications[0].question,
                         'Confirm whether 45386 is supported by what was done on the date of service.')


class Helpers(SimpleTestCase):
    def test_within_words_ignores_spaces_and_punctuation(self):
        span = {'start': 10, 'end': 25, 'text': 'No polyp, today'}
        self.assertTrue(events.within_words(span, [{'start': 10, 'end': 18}, {'start': 20, 'end': 25}]))
        self.assertFalse(events.within_words(span, [{'start': 10, 'end': 18}]))

    def test_only_a_digital_examination_is_set_apart_from_its_familys_session(self):
        """FINAL 5.6 E13 names the digital examination (technique ``manual``) only: an examination of an endoscopic
        family whose device is verified as anything else (an echoendoscope read as ``other``, a balloon enteroscope)
        is its session; an unverified device never sets one apart."""
        def examination(device: str, state: str = 'verified', family: str = 'gi.eus') -> dict:
            return {'family': family, 'technique': {'value': device, 'state': state, 'open': False}}

        for device in ('endoscope', 'other', 'balloon', 'catheter'):
            with self.subTest(device=device):
                self.assertTrue(events.endoscopic_examination(examination(device)))
        self.assertTrue(events.endoscopic_examination(examination('not_stated', 'absent')))  # as normalize stores it
        self.assertFalse(events.endoscopic_examination(examination('manual', family='gi.colonoscopy')))
        self.assertTrue(events.endoscopic_examination(examination('manual', 'unverified', 'gi.colonoscopy')))

    def test_evaluate_reads_a_stored_row_shape(self):
        inv, text = colonoscopy()
        stored = {'events': inv.events, 'encounter_facts': inv.encounter_facts, 'open_questions': inv.open_questions}
        self.assertEqual(evaluate(stored, '45385', POLYP, text).supporting, ('E2',))
