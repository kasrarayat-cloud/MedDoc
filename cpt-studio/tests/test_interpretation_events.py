"""The per-code rule of the events engine (Gemini migration slice S08; design/FINAL.md 7.2-7.6, as design/ADJUDICATION.md
C-1, C-6, C-9 and C-10 amend it), SYNTHETIC: one test per row of 7.2 (R1-R9), per rule of 7.4 (h1-h6 and C-9), per arm
of 7.5 (the deciding attributes and their bases, the broad statement, the citation within the statement's own words,
C-10's partial citation, the omission case of P4, the exceptive statement of C-7, the doubt of condition 4), and 7.6.
C-1's examination-as-session is tested on every EUS code, on an examination-only document and with the act.

Each fixture is a synthetic Gemini answer over a synthetic document, read by read.read and normalized with the real
linked steps (slices S01-S03), then assessed through assess.assess with a synthetic Corti response whose spans are the
document's own. Nothing is sent. The builders here are the S08 test modules' shared builders (test_interpretation_
{assess,coverage,combination,cases} import them)."""
from __future__ import annotations

import hashlib

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
    """A synthetic Corti response: (code, the document's phrase it cites[, role]) each."""
    out = []
    for item in codes:
        code, phrase = item[0], item[1]
        role = item[2] if len(item) > 2 else 'selected'
        start = text.index(phrase)
        out.append(ProviderCode(role, 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                (EvidenceSpan(0, start, start + len(phrase), phrase, True),)))
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


def eus(*more, act_lines=('P1', 'P2')):
    lines = {pid: EUS_LINES[pid] for pid in act_lines + tuple(event['status']['passages'][0] for event in more)}
    examination = exam(words='echoendoscope', procedure=a('eus'), target=tg('', 'pancreas', 'pancreatic head', ['P2']))
    examination['target']['passages'] = ['P2']
    return inventory(lines, events=[examination, *more])


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
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']))
        inv, text = colonoscopy(denial, polyp=removed(performer=a('unknown')), lines={'P3': 'No polyp was removed.'})
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual(len(p.clarifications), 1)  # exactly one question per code
        self.assertIn(asked(p)[0], ('conflict:snare', 'event_performer'))


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

    def test_performer_another_clinician_by_a_titled_name(self):
        line = 'Dr. Lena Ortiz snared the polyp.'
        other = act('E3', 'P3', 'snare', 'snared', status_words='snared',
                    performer=a('other_clinician', 'Dr. Lena Ortiz', ['P3']))
        inv, text = colonoscopy(other, lines={'P3': line}, polyp=act('E2', 'P2', 'biopsy', 'removed'), named=True)
        p = proposal(run(inv, text, [('45385', 'Dr. Lena Ortiz snared')]), '45385')
        self.excluded(p, 'performer', 'literal')
        self.assertIn('by another clinician', p.exclusion_reason)

    def test_performer_another_facility_by_a_facility_marker(self):
        line = 'The polyp was snared at an outside hospital.'
        other = act('E3', 'P3', 'snare', 'snared', status_words='was snared',
                    performer=a('other_facility', 'at an outside hospital', ['P3']))
        inv, text = colonoscopy(other, lines={'P3': line}, polyp=act('E2', 'P2', 'biopsy', 'removed'), named=True)
        p = proposal(run(inv, text, [('45385', 'snared at an outside hospital')]), '45385')
        self.excluded(p, 'performer', 'marker')

    def test_a_broad_current_denial_covers_a_code_citing_another_passage(self):
        """The v5 class: a broad current denial of removal (verified quantifier and negator) excludes a removal code
        whatever passage it cites."""
        lines = {'P2': 'A scar from an earlier polypectomy was seen in the rectum.', 'P3': 'No polyp was removed today.'}
        denial = act('E3', 'P3', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                     scope=sc('all_of_kind', 'No', ['P3']), time=a('current_encounter', 'today', ['P3']))
        inv, text = colonoscopy(denial, lines=lines, lesions=(), polyp=act('E2', 'P2', 'other', 'scar'))
        p = proposal(run(inv, text, [('45385', lines['P2'])]), '45385')
        self.excluded(p, 'status', 'literal')
        self.assertEqual(p.support['exclusion']['cover'], 'broad')

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
        kind exists, in another sentence. Coverage fails: held by 7.6."""
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

    def test_evaluate_reads_a_stored_row_shape(self):
        inv, text = colonoscopy()
        stored = {'events': inv.events, 'encounter_facts': inv.encounter_facts, 'open_questions': inv.open_questions}
        self.assertEqual(evaluate(stored, '45385', POLYP, text).supporting, ('E2',))
