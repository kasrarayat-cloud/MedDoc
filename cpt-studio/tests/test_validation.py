"""Validation engine: pure tests over synthetic notes, routing results and an in-memory reference.

``studio.gi.detect.status_for_span`` is stubbed through ``checks.span_status`` so each test states exactly
which status reading every evidence passage carries; one class at the end runs the real reader when present.
"""
import importlib
import json
from datetime import date
from types import SimpleNamespace
from unittest import mock, skipUnless

from django.test import SimpleTestCase

from studio.reference.store import UNKNOWN_DATE_NOTE, InMemoryReferenceLookup
from studio.types import (AssessmentResult, EvidenceSpan, Fact, FamilyFinding, NormalizedResponse, PageSpan,
                          ProviderCode, ReferenceSourceInfo, RoutingResult, ServiceMention, Span, from_jsonable,
                          to_jsonable)
from studio.validation import checks
from studio.validation.engine import ENGINE_VERSION, assess

DOS = date(2026, 10, 21)
DISPLAY = 'UNVERIFIED PROVIDER WORDING'
COLON, EGD, EM = 'gi.colonoscopy', 'gi.egd', 'gi.office_em'
EGD_LABEL = 'Upper GI endoscopy (EGD, esophagoscopy, enteroscopy)'
NOT_CONNECTED = {
    'cpt.membership': 'No licensed CPT edition is connected; code-set membership for the service date is not verified.',
    'cpt.descriptor': 'Description withheld — no licensed CPT descriptor is connected.',
    'ncci.ptp': 'NCCI procedure-to-procedure edits are not connected (CMS serves them only behind an AMA '
                'point-and-click agreement).',
}


class Note:
    def __init__(self, *lines):
        self.text = '\n'.join(lines) + '\n'

    def offset(self, phrase, nth=0):
        start = -1
        for _ in range(nth + 1):
            start = self.text.index(phrase, start + 1)
        return start

    def span(self, phrase, *, exact=True, context_index=0, nth=0, shift=0):
        start = self.offset(phrase, nth) + shift
        return EvidenceSpan(context_index=context_index, start=start, end=start + len(phrase), text=phrase, exact=exact)

    def sentence(self, phrase):
        start = self.offset(phrase)
        return Span(start, start + len(phrase), phrase)


def mention(note, family, status, phrase, *cues):
    where = note.sentence(phrase)
    return ServiceMention(family=family, status=status, span=where, sentence=where, section='procedure', cues=cues)


def finding(family, status, *mentions, facts=None, missing=()):
    documented = tuple(Fact(name, value, 'document') for name, value in (facts or {}).items())
    return FamilyFinding(family=family, status=status, mentions=mentions, facts=documented, missing=tuple(missing))


def context(service_date='2026-10-21', *, origin='document', setting=None, patient_status=None, billing=None):
    def fact(name, value):
        if not value:
            return Fact(name, None, 'missing')
        return Fact(name, value, origin if name == 'service_date' else 'document')
    return {'service_date': fact('service_date', service_date), 'setting': fact('setting', setting),
            'billing_context': fact('billing_context', billing),
            'patient_status': fact('patient_status', patient_status)}


def selected(code, *spans, display=DISPLAY):
    return ProviderCode(role='selected', system='cpt', code=code, display=display, evidence=spans)


def listed(code, *spans, role='candidate', parent=None):
    return ProviderCode(role=role, system='cpt', code=code, display=DISPLAY, evidence=spans, parent_code=parent)


def info(key, kind, release, start='2026-10-01', end='2026-12-31'):
    return ReferenceSourceInfo(key=key, kind=kind, publisher='CMS', title=f'{release} synthetic', release=release,
                               url='https://www.cms.gov/synthetic', sha256='0' * 64, effective_start=start,
                               effective_end=end, license_note='licence', scope_note='scope')


def pfs(status='A', days='000', mult='2', base=None, pctc='0'):
    return {'status': status, 'global_days': days, 'mult_proc': mult, 'endo_base': base, 'pctc': pctc}


def mue(value, indicator, label, rationale):
    return {'value': value, 'mai': {'indicator': indicator, 'label': label}, 'rationale': rationale}


POLICY, CLINICAL = 'Date of Service Edit: Policy', 'Date of Service Edit: Clinical'
PFS_INFO = info('cms-pfs-rvu26d', 'cms-pfs', 'RVU26D')
MUE_INFO = info('cms-mue-practitioner-2026q4', 'cms-mue-practitioner', '2026-Q4')
PFS_ROWS = {
    ('43235', ''): pfs(), ('43239', ''): pfs(mult='3', base='43235'), ('43249', ''): pfs(mult='3', base='43235'),
    ('45378', ''): pfs(), ('45378', '53'): pfs(), ('45380', ''): pfs(mult='3', base='45378'),
    ('45385', ''): pfs(mult='3', base='45378'), ('99213', ''): pfs(days='XXX', mult='0'),
    ('99214', ''): pfs(days='XXX', mult='0'), ('74328', ''): pfs('C', 'XXX', '0', pctc='1'),
    ('74328', '26'): pfs('A', 'XXX', '0', pctc='1'), ('74328', 'TC'): pfs('C', 'XXX', '0', pctc='1'),
    ('86153', '26'): pfs('A', 'XXX', '0', pctc='6'),
}
MUE_ROWS = {
    ('43235', ''): mue(1, 3, CLINICAL, 'Nature of Service/Procedure'),
    ('43239', ''): mue(1, 2, POLICY, 'Anatomic Consideration'),
    ('43249', ''): mue(1, 3, CLINICAL, 'Nature of Service/Procedure'),
    ('45378', ''): mue(1, 3, CLINICAL, 'Nature of Service/Procedure'),
    ('45385', ''): mue(1, 2, POLICY, 'Anatomic Consideration'),
    ('99213', ''): mue(2, 3, CLINICAL, 'Clinical: Data'),
    ('74328', ''): mue(1, 3, CLINICAL, 'Clinical: Data'),
}
REFERENCE = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {PFS_INFO.key: PFS_ROWS, MUE_INFO.key: MUE_ROWS})

COLONOSCOPY = Note(
    'Date of service: 2026-10-21',
    'Procedure: Colonoscopy performed to the cecum.',
    'A 6 mm sigmoid polyp was removed with cold snare.',
    'A second 4 mm polyp was removed with cold snare.',
    'Plan: repeat colonoscopy in 3 years.',
)
PERFORMED = 'Colonoscopy performed to the cecum.'
SNARE = 'A 6 mm sigmoid polyp was removed with cold snare.'
SNARE_2 = 'A second 4 mm polyp was removed with cold snare.'
REPEAT = 'Plan: repeat colonoscopy in 3 years.'

VISIT_AND_EGD = Note(
    'Date of service: 2026-10-21',
    'Office visit: established patient seen for dysphagia. Total time 32 minutes.',
    'Procedure: EGD performed to the second portion of the duodenum with cold forceps biopsies.',
    'Diagnostic survey of the esophagus and stomach was completed first.',
    'Esophageal dilation was performed with a balloon.',
)
VISIT = 'Office visit: established patient seen for dysphagia.'
TIME = 'Total time 32 minutes.'
EGD_DONE = 'Procedure: EGD performed to the second portion of the duodenum with cold forceps biopsies.'
SURVEY = 'Diagnostic survey of the esophagus and stomach was completed first.'
DILATION = 'Esophageal dilation was performed with a balloon.'


def colonoscopy_finding(status='performed', **facts):
    return finding(COLON, status, mention(COLONOSCOPY, COLON, status, PERFORMED, 'performed'),
                   facts=facts or {'extent': 'cecum'})


def egd_finding():
    return finding(EGD, 'performed', mention(VISIT_AND_EGD, EGD, 'performed', EGD_DONE, 'performed'),
                   facts={'extent': 'second portion of the duodenum'})


def visit_finding(**facts):
    return finding(EM, 'performed', mention(VISIT_AND_EGD, EM, 'performed', VISIT, 'seen'),
                   facts=facts or {'em_basis': 'total time 32 minutes'})


def visit_context(**overrides):
    values = {'setting': 'office', 'patient_status': 'established', **overrides}
    return context(**values)


class EngineCase(SimpleTestCase):
    maxDiff = None

    def setUp(self):
        self.statuses = {}
        patcher = mock.patch.object(checks, 'span_status',
                                    side_effect=lambda text, start, end, service_date=None: self.statuses.get(
                                        text[start:end]))
        self.reader = patcher.start()
        self.addCleanup(patcher.stop)

    def run_engine(self, note, *codes, findings=(), ctx=None, service_date=DOS, provider_status='succeeded',
                   reference=REFERENCE, pages=None, problems=(), extraction='ok', messages=()):
        response = NormalizedResponse(provider='corti', adapter_version='corti-coding@1', codes=codes,
                                      problems=problems)
        return assess(text=note.text, pages=pages or (PageSpan(1, 0, len(note.text)),),
                      context=context() if ctx is None else ctx,
                      routing=RoutingResult(version='gi-routing@test', document_kind='procedure_report',
                                            findings=tuple(findings)),
                      normalized=response, reference=reference, service_date=service_date,
                      provider_status=provider_status, extraction_status=extraction, extraction_messages=messages)

    @staticmethod
    def proposal(result, code, bucket=None):
        found = [p for p in result.proposals if p.code == code and (bucket is None or p.bucket == bucket)]
        assert len(found) == 1, f'expected one proposal for {code} ({bucket}), found {len(found)}'
        return found[0]

    @staticmethod
    def check(item, check_id):
        found = [c for c in item.checks if c.id == check_id]
        assert len(found) == 1, f'expected one {check_id} check, found {[c.id for c in item.checks]}'
        return found[0]

    @staticmethod
    def encounter_check(result, check_id):
        found = [c for c in result.encounter_checks if c.id == check_id]
        assert len(found) == 1, f'expected one {check_id} encounter check'
        return found[0]


class ProviderStatusTests(EngineCase):
    def test_no_proposals_and_an_exact_reason_when_the_provider_did_not_succeed(self):
        reasons = {'not_run': ('not_verified', 'was not run for this revision'),
                   'failed': ('fail', 'did not return a usable result'),
                   'unknown': ('warn', 'outcome is unknown')}
        for status, (check_status, phrase) in reasons.items():
            with self.subTest(status):
                result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                                         findings=[colonoscopy_finding()], provider_status=status)
                self.assertEqual(result.proposals, ())
                provider = self.encounter_check(result, 'provider.status')
                self.assertEqual(provider.status, check_status)
                self.assertIn(phrase, provider.detail)
                self.assertIn('This is not a finding that no codes apply.', provider.detail)
                self.assertNotIn('no codes found', json.dumps(to_jsonable(result)).lower())
                self.assertNotIn('services.unproposed', [c.id for c in result.encounter_checks])
                self.assertEqual(result.summary['selected'], 0)
                self.reader.assert_not_called()

    def test_contract_violations_are_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unknown provider status'):
            self.run_engine(COLONOSCOPY, provider_status='done')
        with self.assertRaisesRegex(ValueError, 'needs its normalized response'):
            assess(text=COLONOSCOPY.text, pages=(), context=context(), routing=RoutingResult('v', 'unknown'),
                   normalized=None, reference=REFERENCE, service_date=DOS, provider_status='succeeded')
        with self.assertRaisesRegex(ValueError, 'Unknown extraction status'):
            self.run_engine(COLONOSCOPY, extraction='complete')

    def test_a_succeeded_response_with_no_selected_code_is_reported_as_such(self):
        result = self.run_engine(COLONOSCOPY, listed('45378', COLONOSCOPY.span(PERFORMED)),
                                 findings=[colonoscopy_finding()])
        provider = self.encounter_check(result, 'provider.status')
        self.assertEqual(provider.status, 'warn')
        self.assertIn('returned no selected CPT-labelled code', provider.detail)
        self.assertEqual([p.bucket for p in result.proposals], ['alternative'])

    def test_adapter_problems_are_surfaced(self):
        result = self.run_engine(COLONOSCOPY, problems=('Evidence span 3 was outside context 0.',))
        problems = self.encounter_check(result, 'provider.problems')
        self.assertEqual(problems.status, 'warn')
        self.assertIn('Evidence span 3 was outside context 0.', problems.detail)


class ScopeTests(EngineCase):
    def test_code_syntax_decides_scope(self):
        cases = {
            '45385': ('cpt1', ''), '0652T': ('cpt3', ''),
            '0001F': ('cpt2', "CPT Category II performance-measurement code — outside this release's CPT coding scope"),
            '0001U': ('pla',
                      "CPT Proprietary Laboratory Analyses (PLA) code — outside this release's CPT coding scope"),
            'G0121': ('hcpcs', 'HCPCS Level II code — CPT-only results'),
        }
        for code, expected in cases.items():
            with self.subTest(code):
                self.assertEqual(checks.code_scope(code), expected)
        for code in ('4538', '453851', '45385-59', 'g0121', '４５３８５', '', ' 45385', '0002M', 'GG121'):
            with self.subTest(code=code):
                self.assertEqual(checks.code_scope(code), ('invalid', checks.INVALID_REASON))

    def test_out_of_scope_selections_are_excluded_and_not_reinstatable(self):
        self.statuses = {PERFORMED: 'performed'}
        evidence = COLONOSCOPY.span(PERFORMED)
        result = self.run_engine(COLONOSCOPY, selected('0001F', evidence), selected('G0121', evidence),
                                 selected('45385-59', evidence), findings=[colonoscopy_finding()])
        for code, reason in (('0001F', 'CPT Category II'), ('G0121', 'HCPCS Level II code — CPT-only results'),
                             ('45385-59', 'Not a CPT Category I or III code format')):
            with self.subTest(code):
                item = self.proposal(result, code)
                self.assertEqual((item.bucket, item.status, item.reinstatable), ('excluded', 'excluded', False))
                self.assertIn(reason, item.exclusion_reason)
                self.assertEqual([(c.id, c.status) for c in item.checks], [('scope.cpt', 'fail')])
                self.assertEqual(item.clarifications, ())
        self.reader.assert_not_called()

    def test_codes_that_cannot_be_stored_are_reported_not_listed_or_truncated(self):
        self.statuses = {PERFORMED: 'performed'}
        wording = 'Colonoscopy with removal of a lesion by snare'
        result = self.run_engine(COLONOSCOPY, selected('', COLONOSCOPY.span(PERFORMED)),
                                 selected(wording, COLONOSCOPY.span(PERFORMED)), listed('45385-PT-XS'),
                                 selected('45378', COLONOSCOPY.span(PERFORMED)), findings=[colonoscopy_finding()])
        self.assertEqual([p.code for p in result.proposals], ['45378'])
        unlisted = self.encounter_check(result, 'provider.unlisted')
        self.assertEqual(unlisted.status, 'warn')
        self.assertIn('returned 3 codes that cannot be listed', unlisted.detail)
        self.assertNotIn(wording, json.dumps(to_jsonable(result)))

    def test_category_three_is_kept_and_reported_as_outside_the_gi_profiles(self):
        note = Note('Date of service: 2026-10-21', 'Category III service performed today.')
        self.statuses = {'Category III service performed today.': 'performed'}
        result = self.run_engine(note, selected('0652T', note.span('Category III service performed today.')))
        item = self.proposal(result, '0652T')
        self.assertEqual((item.code_kind, item.bucket, item.status), ('cpt3', 'selected', 'ready'))
        routing = self.check(item, 'routing.family')
        self.assertEqual(routing.status, 'not_verified')
        self.assertTrue(routing.detail.startswith('No GI profile for this service in this release.'))
        self.assertEqual(self.check(item, 'pfs.presence').detail, 'Not listed in RVU26D.')
        self.assertEqual(result.unsupported[0]['codes'], ['0652T'])


class EvidenceTests(EngineCase):
    def test_only_re_verified_exact_document_spans_are_kept(self):
        self.statuses = {SNARE: 'performed'}
        spans = (COLONOSCOPY.span(SNARE), COLONOSCOPY.span(SNARE),  # duplicate of the first
                 COLONOSCOPY.span(PERFORMED, exact=False), COLONOSCOPY.span(PERFORMED, context_index=1),
                 COLONOSCOPY.span(PERFORMED, shift=1),  # marked exact but the offsets do not match the text
                 EvidenceSpan(0, len(COLONOSCOPY.text) - 1, len(COLONOSCOPY.text) + 9, 'x' * 10, True),
                 EvidenceSpan(0, 0, 0, '', True))
        result = self.run_engine(COLONOSCOPY, selected('45385', *spans), findings=[colonoscopy_finding()])
        item = self.proposal(result, '45385')
        self.assertEqual([e.text for e in item.evidence], [SNARE])
        self.assertEqual(self.check(item, 'evidence.exact').status, 'pass')
        dropped = self.check(item, 'evidence.dropped')
        self.assertEqual(dropped.status, 'warn')
        for reason in ('1 is not marked exact by the provider adapter', '1 points into provider context 1',
                       '1 does not match the document text at its offsets', '2 lies outside the document text'):
            self.assertIn(reason, dropped.detail)
        self.assertEqual(item.status, 'ready')

    def test_no_exact_evidence_excludes_without_reinstatement(self):
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE, exact=False),
                                                       COLONOSCOPY.span(SNARE, shift=2)),
                                 findings=[colonoscopy_finding()])
        item = self.proposal(result, '45385')
        self.assertEqual((item.bucket, item.status, item.reinstatable), ('excluded', 'excluded', False))
        self.assertEqual(item.exclusion_reason, 'No exact source evidence')
        self.assertEqual(item.evidence, ())
        self.assertEqual([(c.id, c.status) for c in item.checks], [('scope.cpt', 'pass'), ('evidence.exact', 'fail')])
        self.assertEqual(result.summary['excluded'], 1)
        self.assertIn('Possible missed service: Colonoscopy',
                      self.encounter_check(result, 'services.unproposed').detail)

    def test_evidence_carries_the_page_it_starts_on(self):
        self.statuses = {SNARE: 'performed', SNARE_2: 'performed'}
        boundary = COLONOSCOPY.offset(SNARE_2)
        pages = (PageSpan(1, 0, boundary), PageSpan(2, boundary, len(COLONOSCOPY.text)))
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE), COLONOSCOPY.span(SNARE_2)),
                                 findings=[colonoscopy_finding()], pages=pages)
        self.assertEqual([e.page for e in self.proposal(result, '45385').evidence], [1, 2])


class StatusTests(EngineCase):
    def test_performed_evidence_with_documented_facts_is_ready(self):
        self.statuses = {SNARE: ('performed', ('was removed',))}
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                                 findings=[colonoscopy_finding()])
        item = self.proposal(result, '45385')
        self.assertEqual((item.key, item.bucket, item.status, item.exclusion_reason),
                         ('sel:0', 'selected', 'ready', ''))
        status = self.check(item, 'service.status')
        self.assertEqual(status.status, 'pass')
        self.assertEqual(status.detail, f'Documented as performed: “{SNARE}” (cue “was removed”, linked passage).')
        self.assertEqual(item.clarifications, ())
        self.assertEqual(item.modifier_considerations, ())

    def test_planned_historical_cancelled_and_negated_evidence_is_excluded_but_reinstatable(self):
        for status, cue in (('planned', 'in 3 years'), ('historical', 'previously'), ('cancelled', 'cancelled'),
                            ('negated', 'not performed')):
            with self.subTest(status):
                self.statuses = {REPEAT: (status, (cue,))}
                result = self.run_engine(COLONOSCOPY, selected('45378', COLONOSCOPY.span(REPEAT)))
                item = self.proposal(result, '45378')
                self.assertEqual((item.key, item.bucket, item.status, item.reinstatable),
                                 ('exc:0', 'excluded', 'excluded', True))
                self.assertIn(f'Documented as {status}, not as performed on the date of service', item.exclusion_reason)
                self.assertIn(f'cue “{cue}”', item.exclusion_reason)
                self.assertEqual(self.check(item, 'service.status').status, 'fail')
                self.assertEqual(item.clarifications, ())
                self.assertEqual(self.check(item, 'pfs.presence').status, 'pass')  # full checks kept for reinstatement

    def test_routing_decides_only_when_the_evidence_is_silent(self):
        self.statuses = {}
        result = self.run_engine(COLONOSCOPY, selected('45378', COLONOSCOPY.span(PERFORMED)),
                                 findings=[colonoscopy_finding()])
        item = self.proposal(result, '45378')
        self.assertEqual(item.status, 'ready')
        self.assertEqual(self.check(item, 'service.status').detail,
                         f'Documented as performed: “{PERFORMED}” (cue “performed”, routing).')
        planned = finding(COLON, 'planned', mention(COLONOSCOPY, COLON, 'planned', REPEAT, 'in 3 years'),
                          facts={'extent': 'cecum'})
        result = self.run_engine(COLONOSCOPY, selected('45378', COLONOSCOPY.span(PERFORMED)), findings=[planned])
        self.assertEqual(self.proposal(result, '45378').status, 'excluded')

    def test_a_planned_passage_is_not_rescued_by_a_performed_mention_elsewhere(self):
        self.statuses = {REPEAT: ('planned', ('in 3 years',)), SNARE: 'performed'}
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                                 selected('45378', COLONOSCOPY.span(REPEAT)), findings=[colonoscopy_finding()])
        repeat = self.proposal(result, '45378')
        self.assertEqual((repeat.bucket, repeat.reinstatable), ('excluded', True))
        self.assertEqual(repeat.exclusion_reason,
                         f'Documented as planned, not as performed on the date of service: “{REPEAT}” (cue “in 3 '
                         f'years”, linked passage). Colonoscopy is documented as performed elsewhere: “{PERFORMED}” '
                         '(cue “performed”, routing). Reinstate if this code is supported.')
        self.assertEqual(self.proposal(result, '45385').status, 'ready')

    def test_a_performed_passage_wins_but_a_contrary_linked_passage_is_flagged(self):
        self.statuses = {SNARE: 'performed', REPEAT: ('planned', ('in 3 years',))}
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE), COLONOSCOPY.span(REPEAT)),
                                 findings=[colonoscopy_finding()])
        item = self.proposal(result, '45385')
        self.assertEqual(item.status, 'ready')
        status = self.check(item, 'service.status')
        self.assertEqual(status.status, 'warn')
        self.assertIn('Another linked passage reads as planned', status.detail)

    def test_uncertain_or_absent_status_asks_one_scoped_question(self):
        for reading in ('uncertain', None):
            with self.subTest(reading=reading):
                self.statuses = {PERFORMED: reading}
                result = self.run_engine(COLONOSCOPY, selected('45378', COLONOSCOPY.span(PERFORMED)))
                item = self.proposal(result, '45378')
                self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
                asked = {c.fact: c for c in item.clarifications}
                self.assertEqual(set(asked), {'performed_status', 'extent'})
                performed = asked['performed_status']
                self.assertEqual((performed.scope, performed.family, performed.proposal_key),
                                 ('proposal', COLON, 'sel:0'))
                self.assertEqual(performed.question,
                                 'Confirm whether Colonoscopy was performed on the date of service.')
                self.assertEqual(self.check(item, 'service.status').status, 'warn')
                self.assertEqual(result.clarifications, ())

    def test_incomplete_stays_reviewable_with_a_warning_and_no_assigned_modifier(self):
        note = Note('Date of service: 2026-10-21',
                    'Colonoscopy was incomplete; the scope could not pass the splenic flexure.')
        phrase = 'Colonoscopy was incomplete; the scope could not pass the splenic flexure.'
        self.statuses = {phrase: ('incomplete', ('could not pass',))}
        incomplete = finding(COLON, 'incomplete', mention(note, COLON, 'incomplete', phrase, 'incomplete'),
                             facts={'extent': 'splenic flexure'})
        result = self.run_engine(note, selected('45378', note.span(phrase)), findings=[incomplete])
        item = self.proposal(result, '45378')
        self.assertEqual((item.bucket, item.status), ('selected', 'ready'))
        warning = self.check(item, 'service.incomplete')
        self.assertEqual((warning.label, warning.status), ('Incomplete procedure documented', 'warn'))
        consideration = item.modifier_considerations[0]
        self.assertIn('whether modifier 52 or 53 applies, or whether a different code', consideration)
        self.assertIn('not connected to CPT Studio. No modifier is assigned.', consideration)
        self.assertIn('CMS PFS RVU26D carries a separate row for 45378 with modifier 53.', consideration)
        self.assertEqual(item.code, '45378')

    def test_an_incomplete_mention_elsewhere_is_named_as_incomplete(self):
        self.statuses = {REPEAT: ('planned', ('in 3 years',))}
        result = self.run_engine(COLONOSCOPY, selected('45378', COLONOSCOPY.span(REPEAT)),
                                 findings=[colonoscopy_finding('incomplete')])
        reason = self.proposal(result, '45378').exclusion_reason
        self.assertIn('Colonoscopy is documented as incomplete elsewhere', reason)
        self.assertNotIn('as performed elsewhere', reason)

    def test_a_contract_violation_from_the_status_reader_fails_loudly(self):
        self.statuses = {SNARE: 'done'}
        with self.assertRaisesRegex(ValueError, "unknown status 'done'"):
            self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)))

    def test_a_routing_status_outside_the_vocabulary_fails_loudly(self):
        self.statuses = {SNARE: 'performed'}
        odd = finding(COLON, 'done', mention(COLONOSCOPY, COLON, 'done', PERFORMED))
        with self.assertRaisesRegex(ValueError, "Routing gave gi.colonoscopy unknown statuses \\['done'\\]"):
            self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)), findings=[odd])


class SpanStatusContractTests(SimpleTestCase):
    def test_accepted_shapes(self):
        cases = [
            ('performed', ('performed', ())),
            (('planned', ['in 3 years']), ('planned', ('in 3 years',))),
            (('negated', None), ('negated', ())),
            (SimpleNamespace(status='historical', cues=('2019',)), ('historical', ('2019',))),
            ({'status': 'cancelled', 'cues': 'cancelled'}, ('cancelled', ('cancelled',))),
            (None, None),
            (SimpleNamespace(status=None, cues=()), None),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(checks.normalise_span_status(value), expected)

    def test_unrecognised_values_raise(self):
        for value, error in (('done', ValueError), (42, TypeError), (('performed', [1]), TypeError),
                             (('performed', 5), TypeError), ({'cues': ()}, TypeError)):
            with self.subTest(value=value):
                with self.assertRaises(error):
                    checks.normalise_span_status(value)


class RequiredFactsTests(EngineCase):
    def test_a_missing_procedure_fact_is_one_focused_proposal_question(self):
        self.statuses = {SNARE: 'performed'}
        no_extent = finding(COLON, 'performed', mention(COLONOSCOPY, COLON, 'performed', PERFORMED), facts={})
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)), findings=[no_extent])
        item = self.proposal(result, '45385')
        self.assertEqual(item.status, 'needs_clarification')
        (question,) = item.clarifications
        self.assertEqual((question.scope, question.fact, question.proposal_key), ('proposal', 'extent', 'sel:0'))
        self.assertEqual(question.question, 'Colonoscopy: confirm the furthest extent reached.')
        self.assertEqual(self.check(item, 'facts.required').status, 'warn')

    def test_a_fact_routing_lists_as_missing_stays_missing(self):
        self.statuses = {SNARE: 'performed'}
        contradictory = finding(COLON, 'performed', facts={'extent': 'cecum'}, missing=('extent',))
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)), findings=[contradictory])
        self.assertEqual([c.fact for c in self.proposal(result, '45385').clarifications], ['extent'])

    def test_conflicting_values_are_quoted_in_the_question_reason(self):
        self.statuses = {SNARE: 'performed'}
        conflict = Fact('extent', None, 'conflict', evidence=(COLONOSCOPY.sentence('cecum'),
                                                              COLONOSCOPY.sentence('sigmoid')))
        found = FamilyFinding(COLON, 'performed', (), facts=(conflict,))
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)), findings=[found])
        (question,) = self.proposal(result, '45385').clarifications
        self.assertEqual(question.reason, 'The document gives conflicting values for the extent reached: “cecum”, '
                                          '“sigmoid”.')

    def test_office_visit_facts_come_from_context_and_routing(self):
        self.statuses = {TIME: None}
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 findings=[visit_finding()], ctx=visit_context())
        item = self.proposal(result, '99213')
        self.assertEqual(item.status, 'ready')
        self.assertIn('place of service = office', self.check(item, 'facts.required').detail)
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 findings=[visit_finding()], ctx=visit_context(patient_status=None))
        self.assertEqual([c.fact for c in self.proposal(result, '99213').clarifications], ['patient_status'])

    def test_a_member_supplied_context_value_answers_the_question_even_if_routing_lists_it_missing(self):
        self.statuses = {}
        ctx = visit_context(setting=None)
        ctx['setting'] = Fact('setting', 'office', 'user')
        found = finding(EM, 'performed', mention(VISIT_AND_EGD, EM, 'performed', VISIT),
                        facts={'em_basis': 'total time 32 minutes'}, missing=('setting',))
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)), findings=[found], ctx=ctx)
        self.assertEqual(self.proposal(result, '99213').clarifications, ())


class EmWithProcedureTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.statuses = {EGD_DONE: 'performed', TIME: None}

    def test_an_office_visit_beside_a_performed_procedure_needs_a_separate_e_m_answer(self):
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 selected('43239', VISIT_AND_EGD.span(EGD_DONE)),
                                 findings=[visit_finding(), egd_finding()], ctx=visit_context())
        visit = self.proposal(result, '99213')
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertEqual([c.fact for c in visit.clarifications], ['separate_em'])
        self.assertIn('significant, separately identifiable evaluation and management service',
                      visit.clarifications[0].question)
        check = self.check(visit, 'em.same_day_procedure')
        self.assertEqual(check.status, 'warn')
        self.assertEqual(check.detail, f'{EGD_LABEL} is documented as performed on the same date; a significant, '
                                       'separately identifiable E/M service is not established by this document. '
                                       'CMS PFS global days (RVU26D): 43239 000.')
        self.assertEqual(visit.modifier_considerations, (checks.SEPARATE_EM_CONSIDERATION,))
        self.assertEqual(self.proposal(result, '43239').status, 'ready')

    def test_a_documented_separately_identifiable_e_m_releases_the_visit_for_review(self):
        statement = 'Office visit'
        start = VISIT_AND_EGD.offset(statement)
        documented = Fact('separate_em', 'documented', 'document', (Span(start, start + len(statement), statement),))
        base = visit_finding()
        visit = FamilyFinding(family=base.family, status=base.status, mentions=base.mentions,
                              facts=base.facts + (documented,), missing=())
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 selected('43239', VISIT_AND_EGD.span(EGD_DONE)),
                                 findings=[visit, egd_finding()], ctx=visit_context())
        item = self.proposal(result, '99213')
        self.assertEqual((item.status, item.clarifications), ('ready', ()))
        check = self.check(item, 'em.same_day_procedure')
        self.assertEqual(check.status, 'warn')
        self.assertIn('states a significant, separately identifiable E/M service (\u201cOffice visit\u201d)', check.detail)
        self.assertEqual(item.modifier_considerations, (checks.SEPARATE_EM_CONSIDERATION,))

    def test_a_separate_e_m_fact_without_evidence_does_not_release_the_visit(self):
        base = visit_finding()
        visit = FamilyFinding(family=base.family, status=base.status, mentions=base.mentions,
                              facts=base.facts + (Fact('separate_em', 'documented', 'document'),), missing=())
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 selected('43239', VISIT_AND_EGD.span(EGD_DONE)),
                                 findings=[visit, egd_finding()], ctx=visit_context())
        self.assertEqual([c.fact for c in self.proposal(result, '99213').clarifications], ['separate_em'])

    def test_no_e_m_code_is_ever_added_or_suggested_as_missed(self):
        result = self.run_engine(VISIT_AND_EGD, selected('43239', VISIT_AND_EGD.span(EGD_DONE)),
                                 findings=[visit_finding(), egd_finding()], ctx=visit_context())
        self.assertEqual([p.code for p in result.proposals], ['43239'])
        coverage = self.encounter_check(result, 'services.unproposed')
        self.assertEqual((coverage.status, coverage.detail), ('info', checks.VISIT_NOT_MISSED))
        self.assertNotIn('Possible missed service', coverage.detail)

    def test_an_unproposed_visit_without_a_procedure_is_a_possible_missed_service(self):
        result = self.run_engine(VISIT_AND_EGD, findings=[visit_finding()], ctx=visit_context())
        self.assertIn('Possible missed service: Office / outpatient evaluation and management',
                      self.encounter_check(result, 'services.unproposed').detail)

    def test_a_procedure_known_only_from_routing_still_raises_the_question(self):
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 findings=[visit_finding(), egd_finding()], ctx=visit_context())
        check = self.check(self.proposal(result, '99213'), 'em.same_day_procedure')
        self.assertTrue(check.detail.endswith('Global days are not verified: no same-day procedure code is selected.'))

    def test_a_visit_alone_has_no_same_day_check(self):
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 findings=[visit_finding()], ctx=visit_context())
        self.assertNotIn('em.same_day_procedure', [c.id for c in self.proposal(result, '99213').checks])


class ReferenceCheckTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.statuses = {SNARE: 'performed', SNARE_2: 'performed', PERFORMED: 'performed'}

    def snare(self, **kwargs):
        return self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                               findings=[colonoscopy_finding()], **kwargs)

    def test_listed_code_and_units_within_the_mue(self):
        item = self.proposal(self.snare(), '45385')
        pfs_check, mue_check = self.check(item, 'pfs.presence'), self.check(item, 'mue.units')
        self.assertEqual((pfs_check.status, pfs_check.source), ('pass', 'cms-pfs-rvu26d RVU26D'))
        self.assertEqual(pfs_check.detail, 'Listed in RVU26D with status A (global days 000, multiple procedure '
                                           'indicator 3, endoscopic base 45378).')
        self.assertEqual(mue_check.status, 'pass')
        self.assertEqual(mue_check.detail, '1 unit within the MUE of 1 for 45385 in 2026-Q4 (MAI 2: Date of Service '
                                           'Edit: Policy; rationale: Anatomic Consideration).')

    def test_not_listed_codes(self):
        self.statuses[PERFORMED] = 'performed'
        result = self.run_engine(COLONOSCOPY, selected('45380', COLONOSCOPY.span(PERFORMED)),
                                 selected('86153', COLONOSCOPY.span(SNARE)), findings=[colonoscopy_finding()])
        polyp = self.proposal(result, '45380')
        self.assertEqual(self.check(polyp, 'mue.units').detail,
                         '45380 is not listed in 2026-Q4; units are not verified against an MUE.')
        lab = self.proposal(result, '86153')
        self.assertEqual((self.check(lab, 'pfs.presence').status, self.check(lab, 'pfs.presence').detail),
                         ('warn', '86153 is listed in RVU26D only with modifier(s) 26; it has no unmodified row.'))

    def test_a_date_outside_every_window_is_not_verified(self):
        item = self.proposal(self.snare(ctx=context('2027-01-15'), service_date=date(2027, 1, 15)), '45385')
        for check_id, label in (('pfs.presence', 'CMS Physician Fee Schedule'), ('mue.units', 'CMS practitioner MUE')):
            check = self.check(item, check_id)
            self.assertEqual(check.status, 'not_verified')
            self.assertIn(f'No installed {label} release covers 2027-01-15 (installed: ', check.detail)
        self.assertEqual(self.check(item, 'pfs.endoscopic_base').status, 'not_verified')

    def test_two_releases_covering_the_date_are_ambiguous(self):
        overlap = info('cms-pfs-x', 'cms-pfs', 'RVU26X', '2026-10-15', '2027-01-31')
        reference = InMemoryReferenceLookup([PFS_INFO, overlap, MUE_INFO],
                                            {PFS_INFO.key: PFS_ROWS, overlap.key: PFS_ROWS, MUE_INFO.key: MUE_ROWS})
        result = self.snare(reference=reference)
        check = self.check(self.proposal(result, '45385'), 'pfs.presence')
        self.assertEqual(check.status, 'not_verified')
        self.assertIn('2 installed CMS Physician Fee Schedule releases cover 2026-10-21', check.detail)
        entries = {entry['key']: entry for entry in result.reference_sources}
        self.assertFalse(entries['cms-pfs-rvu26d']['applies'])
        self.assertIn('another installed release', entries['cms-pfs-x']['note'])
        self.assertTrue(entries[MUE_INFO.key]['applies'])

    def test_duplicate_selections_become_one_proposal_with_units(self):
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                                 selected('45385', COLONOSCOPY.span(SNARE_2)), findings=[colonoscopy_finding()])
        item = self.proposal(result, '45385')
        self.assertEqual((item.units, len(item.evidence)), (2, 2))
        self.assertEqual(self.check(item, 'units.duplicate').status, 'warn')
        mue_check = self.check(item, 'mue.units')
        self.assertEqual(mue_check.status, 'fail')
        self.assertEqual(mue_check.detail, '2 units exceed the MUE of 1 for 45385 in 2026-Q4 (MAI 2: Date of Service '
                                           'Edit: Policy; rationale: Anatomic Consideration).')
        self.assertEqual(item.status, 'ready')

    def test_units_equal_to_the_mue_pass(self):
        self.statuses = {TIME: 'performed'}
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)),
                                 selected('99213', VISIT_AND_EGD.span(VISIT)), findings=[visit_finding()],
                                 ctx=visit_context())
        self.assertEqual(self.check(self.proposal(result, '99213'), 'mue.units').status, 'pass')

    def test_not_connected_references_are_always_reported(self):
        item = self.proposal(self.snare(), '45385')
        for check_id, detail in NOT_CONNECTED.items():
            check = self.check(item, check_id)
            self.assertEqual((check.status, check.detail), ('not_verified', detail))

    def test_professional_and_technical_rows_are_a_consideration_only(self):
        phrase = 'ERCP with cholangiography was performed; the bile duct was cannulated.'
        note = Note('Date of service: 2026-10-21', phrase)
        self.statuses = {phrase: 'performed'}
        ercp = finding('gi.ercp', 'performed', mention(note, 'gi.ercp', 'performed', phrase),
                       facts={'cannulation': 'bile duct'})
        result = self.run_engine(note, selected('74328', note.span(phrase)), findings=[ercp])
        (consideration,) = self.proposal(result, '74328').modifier_considerations
        self.assertEqual(consideration, 'CMS PFS RVU26D carries separate professional-component (26) and '
                                        'technical-component (TC) rows for 74328; which one applies depends on the '
                                        'billing context (not documented). No modifier is assigned.')


class EndoscopicCombinationTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.statuses = {EGD_DONE: 'performed', SURVEY: 'performed', DILATION: 'performed'}

    def egd(self, *codes):
        spans = {'43235': SURVEY, '43239': EGD_DONE, '43249': DILATION}
        return self.run_engine(VISIT_AND_EGD, *(selected(code, VISIT_AND_EGD.span(spans[code])) for code in codes),
                               findings=[egd_finding()])

    def test_a_base_with_its_therapeutic_code_warns_on_both(self):
        result = self.egd('43235', '43239')
        base = self.check(self.proposal(result, '43235'), 'pfs.endoscopic_base')
        therapeutic = self.check(self.proposal(result, '43239'), 'pfs.endoscopic_base')
        self.assertEqual((base.status, therapeutic.status), ('warn', 'warn'))
        self.assertEqual(base.detail, '43235 is the endoscopic base of 43239 in RVU26D, also selected: base endoscopy '
                                      'reported with a therapeutic code of the same family (CMS PFS endoscopic base '
                                      'relationship).')
        self.assertIn('43239 has the endoscopic base 43235 in RVU26D, also selected', therapeutic.detail)

    def test_two_therapeutic_codes_of_one_family_are_informational(self):
        result = self.egd('43239', '43249')
        check = self.check(self.proposal(result, '43239'), 'pfs.endoscopic_base')
        self.assertEqual((check.status, check.detail),
                         ('info', '43239 and 43249 share the endoscopic base 43235 in RVU26D (multiple procedure '
                                  'indicator 3): multiple endoscopy rule.'))

    def test_the_multiple_endoscopy_rule_is_named_only_for_indicator_three(self):
        rows = dict(PFS_ROWS)
        rows[('43239', '')] = pfs(mult='2', base='43235')
        rows[('43249', '')] = pfs(mult='2', base='43235')
        reference = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {PFS_INFO.key: rows, MUE_INFO.key: MUE_ROWS})
        result = self.run_engine(VISIT_AND_EGD, selected('43239', VISIT_AND_EGD.span(EGD_DONE)),
                                 selected('43249', VISIT_AND_EGD.span(DILATION)), findings=[egd_finding()],
                                 reference=reference)
        detail = self.check(self.proposal(result, '43239'), 'pfs.endoscopic_base').detail
        self.assertEqual(detail, '43239 and 43249 share the endoscopic base 43235 in RVU26D (multiple procedure '
                                 'indicator 2).')

    def test_an_excluded_base_does_not_count(self):
        self.statuses[SURVEY] = ('planned', ('next month',))
        result = self.egd('43235', '43239')
        self.assertEqual(self.proposal(result, '43235').bucket, 'excluded')
        self.assertEqual(self.check(self.proposal(result, '43239'), 'pfs.endoscopic_base').status, 'pass')


class BucketTests(EngineCase):
    def test_keys_buckets_and_order_follow_the_provider(self):
        self.statuses = {SNARE: 'performed', REPEAT: ('planned', ('in 3 years',)), PERFORMED: 'performed'}
        codes = (selected('45385', COLONOSCOPY.span(SNARE)), selected('0001F', COLONOSCOPY.span(PERFORMED)),
                 selected('45378', COLONOSCOPY.span(REPEAT)), selected('45380', COLONOSCOPY.span(PERFORMED)),
                 listed('45384', COLONOSCOPY.span(SNARE)), listed('45380', role='alternative', parent='45385'),
                 listed('1036F', COLONOSCOPY.span(PERFORMED)))
        result = self.run_engine(COLONOSCOPY, *codes, findings=[colonoscopy_finding()])
        self.assertEqual([(p.key, p.code, p.bucket) for p in result.proposals], [
            ('sel:0', '45385', 'selected'), ('sel:1', '45380', 'selected'), ('exc:0', '0001F', 'excluded'),
            ('exc:1', '45378', 'excluded'), ('alt:0', '45384', 'alternative'), ('alt:1', '45380', 'alternative'),
            ('alt:2', '1036F', 'alternative')])
        self.assertEqual({k: result.summary[k] for k in ('selected', 'alternatives', 'excluded')},
                         {'selected': 2, 'alternatives': 3, 'excluded': 2})

    def test_alternatives_are_informational_with_scope_checks_only(self):
        self.statuses = {SNARE: 'performed'}
        result = self.run_engine(COLONOSCOPY, listed('45384', COLONOSCOPY.span(SNARE)),
                                 listed('45380', role='alternative', parent='45385'), listed('1036F'))
        for item in result.proposals:
            with self.subTest(item.key):
                self.assertEqual((item.bucket, item.status, item.reinstatable), ('alternative', 'informational', False))
                self.assertEqual([c.id for c in item.checks], ['scope.cpt'])
                self.assertEqual(item.clarifications, ())
        nested = self.proposal(result, '45380')
        self.assertEqual(nested.exclusion_reason,
                         'Provider alternative to 45385; not selected. Candidates and alternatives cannot be approved.')
        self.assertEqual(self.check(self.proposal(result, '1036F'), 'scope.cpt').status, 'fail')
        self.reader.assert_not_called()

    def test_only_provider_codes_appear(self):
        self.statuses = {SNARE: 'performed'}
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                                 findings=[colonoscopy_finding(), egd_finding(), visit_finding()],
                                 ctx=visit_context())
        self.assertEqual([p.code for p in result.proposals], ['45385'])


class EncounterCheckTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.statuses = {SNARE: 'performed'}

    def snare(self, **kwargs):
        return self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                               findings=[colonoscopy_finding()], **kwargs)

    def test_a_documented_service_date_passes(self):
        check = self.encounter_check(self.snare(), 'context.service_date')
        self.assertEqual(check.status, 'pass')
        user = context(origin='user')
        self.assertIn('entered by a workspace member', self.encounter_check(self.snare(ctx=user),
                                                                            'context.service_date').detail)

    def test_a_missing_service_date_is_one_encounter_question_and_holds_every_proposal(self):
        result = self.snare(ctx=context(None), service_date=None)
        (question,) = result.clarifications
        self.assertEqual((question.scope, question.fact, question.proposal_key), ('encounter', 'service_date', ''))
        self.assertEqual(question.question, 'Confirm the date of service for this encounter.')
        self.assertEqual(self.encounter_check(result, 'context.service_date').status, 'fail')
        item = self.proposal(result, '45385')
        self.assertEqual(item.status, 'needs_clarification')
        self.assertEqual(item.clarifications, ())
        self.assertEqual(self.check(item, 'context.service_date').status, 'fail')
        self.assertEqual(self.check(item, 'pfs.presence').detail, UNKNOWN_DATE_NOTE)
        self.assertTrue(all(not entry['applies'] for entry in result.reference_sources))

    def test_conflicting_or_unreadable_service_dates_are_quoted(self):
        conflict = context(None)
        conflict['service_date'] = Fact('service_date', None, 'conflict',
                                        evidence=(Span(0, 4, 'DOS 2026-10-21'), Span(9, 13, 'DOP 2026-10-22')))
        detail = self.encounter_check(self.snare(ctx=conflict, service_date=None), 'context.service_date').detail
        self.assertIn('Conflicting dates of service are documented (“DOS 2026-10-21”, “DOP 2026-10-22”)', detail)
        unreadable = context('21/10/2026')
        result = self.snare(ctx=unreadable, service_date=None)
        self.assertIn('“21/10/2026” is not a readable date', result.clarifications[0].reason)

    def test_a_service_date_that_disagrees_with_the_context_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'does not match the context service_date fact'):
            self.snare(service_date=date(2026, 10, 22))

    def test_possible_missed_services_are_named(self):
        result = self.run_engine(VISIT_AND_EGD, selected('43239', VISIT_AND_EGD.span(EGD_DONE)),
                                 findings=[egd_finding(), colonoscopy_finding()])
        check = self.encounter_check(result, 'services.unproposed')
        self.assertEqual((check.status, check.detail),
                         ('warn', 'Possible missed service: Colonoscopy is documented as performed with no selected '
                                  'proposal.'))
        self.assertEqual(self.encounter_check(self.snare(), 'services.unproposed').status, 'pass')

    def test_performed_services_outside_the_profiles_are_listed(self):
        note = Note('Date of service: 2026-10-21', 'Esophageal motility study performed today.')
        phrase = 'Esophageal motility study performed today.'
        self.statuses = {phrase: 'performed'}
        other = finding('gi.other', 'performed', mention(note, 'gi.other', 'performed', phrase))
        result = self.run_engine(note, selected('91010', note.span(phrase)), findings=[other])
        (entry,) = result.unsupported
        self.assertEqual((entry['family'], entry['status'], entry['codes']), ('gi.other', 'performed', ['91010']))
        self.assertEqual(self.encounter_check(result, 'services.unsupported').status, 'warn')
        self.assertEqual(self.check(self.proposal(result, '91010'), 'routing.family').status, 'not_verified')

    def test_extraction_status_is_reported_when_supplied(self):
        self.assertEqual(self.encounter_check(self.snare(), 'extraction.status').status, 'pass')
        partial = self.encounter_check(self.snare(extraction='partial', messages=('Page 2 has no text layer.',)),
                                       'extraction.status')
        self.assertEqual(partial.status, 'warn')
        self.assertIn('Page 2 has no text layer.', partial.detail)
        unsupplied = self.encounter_check(self.snare(extraction=None), 'extraction.status')
        self.assertEqual(unsupplied.status, 'not_verified')

    def test_reference_sources_list_installed_and_not_connected_sources(self):
        entries = self.snare().reference_sources
        self.assertEqual([(e['key'], e['applies'], e['connected']) for e in entries], [
            (MUE_INFO.key, True, True), (PFS_INFO.key, True, True), ('ama-cpt', False, False),
            ('cms-ncci-ptp', False, False)])
        self.assertEqual([e['title'] for e in entries[2:]], ['CPT code set (AMA)', 'NCCI PTP edits'])

    def test_assessment_identity(self):
        result = self.snare()
        self.assertEqual((result.engine_version, result.profiles_version), (ENGINE_VERSION, 'gi-profiles@2'))
        self.assertEqual(result.summary['service_date'], '2026-10-21')


class FingerprintTests(EngineCase):
    def setUp(self):
        super().setUp()
        self.statuses = {EGD_DONE: 'performed', TIME: None}

    def visit_and_egd(self, ctx=None, service_date=DOS, reverse=False):
        spans = [VISIT_AND_EGD.span(EGD_DONE), VISIT_AND_EGD.span(SURVEY)]
        self.statuses[SURVEY] = 'performed'
        egd = selected('43239', *(reversed(spans) if reverse else spans))
        result = self.run_engine(VISIT_AND_EGD, selected('99213', VISIT_AND_EGD.span(TIME)), egd,
                                 findings=[visit_finding(), egd_finding()], ctx=ctx or visit_context(),
                                 service_date=service_date)
        return {p.code: p.fingerprint for p in result.proposals}

    def test_fingerprints_are_deterministic_and_order_free(self):
        self.assertEqual(self.visit_and_egd(), self.visit_and_egd())
        self.assertEqual(self.visit_and_egd(), self.visit_and_egd(reverse=True))

    def test_a_service_date_change_changes_every_fingerprint(self):
        later = self.visit_and_egd(visit_context(service_date='2026-10-22'), date(2026, 10, 22))
        before = self.visit_and_egd()
        self.assertNotEqual(later['43239'], before['43239'])
        self.assertNotEqual(later['99213'], before['99213'])

    def test_a_setting_change_affects_the_visit_only(self):
        before = self.visit_and_egd()
        after = self.visit_and_egd(visit_context(setting='hospital_outpatient'))
        self.assertNotEqual(after['99213'], before['99213'])
        self.assertEqual(after['43239'], before['43239'])


class RationaleTests(EngineCase):
    def test_rationale_restates_held_data_and_never_provider_wording(self):
        self.statuses = {SNARE: 'performed'}
        result = self.run_engine(COLONOSCOPY, selected('45385', COLONOSCOPY.span(SNARE)),
                                 findings=[colonoscopy_finding()])
        item = self.proposal(result, '45385')
        self.assertEqual(item.rationale, 'Selected by corti. 1 exact evidence passage. Routed to Colonoscopy; routing '
                                         'also detected this service in the document. Service status: performed. '
                                         'Documented facts: extent reached = cecum.')
        self.assertEqual(item.provider_display, DISPLAY)
        payload = to_jsonable(result)
        for proposal in payload['proposals']:
            proposal.pop('provider_display')
        self.assertNotIn(DISPLAY, json.dumps(payload))


class RoundTripTests(EngineCase):
    def test_the_result_is_json_data_and_deterministic(self):
        self.statuses = {SNARE: 'performed', REPEAT: ('planned', ('in 3 years',))}
        codes = (selected('45385', COLONOSCOPY.span(SNARE)), selected('45378', COLONOSCOPY.span(REPEAT)),
                 listed('45384', COLONOSCOPY.span(SNARE)))
        first = self.run_engine(COLONOSCOPY, *codes, findings=[colonoscopy_finding()], ctx=context(None),
                                service_date=None)
        second = self.run_engine(COLONOSCOPY, *codes, findings=[colonoscopy_finding()], ctx=context(None),
                                 service_date=None)
        self.assertEqual(first, second)
        restored = from_jsonable(AssessmentResult, json.loads(json.dumps(to_jsonable(first))))
        self.assertEqual(restored, first)


def _real_status_for_span():
    try:
        return getattr(importlib.import_module('studio.gi.detect'), 'status_for_span', None)
    except ImportError:
        return None


@skipUnless(_real_status_for_span(), 'studio.gi.detect.status_for_span is not available yet')
class RealStatusReaderTests(SimpleTestCase):
    NOTE = Note('Date of service: 2026-10-21',
                'Procedure: Colonoscopy was performed to the cecum.',
                'Plan: Repeat colonoscopy in 3 years.')

    def run_real(self, routing):
        note = self.NOTE
        codes = (selected('45378', note.span('Colonoscopy was performed to the cecum.')),
                 selected('45380', note.span('Repeat colonoscopy in 3 years.')))
        return assess(text=note.text, pages=(PageSpan(1, 0, len(note.text)),), context=context(), routing=routing,
                      normalized=NormalizedResponse('corti', 'corti-coding@1', codes=codes), reference=REFERENCE,
                      service_date=DOS, provider_status='succeeded', extraction_status='ok')

    def test_the_real_reader_separates_performed_from_planned(self):
        result = self.run_real(RoutingResult('gi-routing@test', 'procedure_report'))
        performed = EngineCase.proposal(result, '45378')
        planned = EngineCase.proposal(result, '45380')
        self.assertEqual(performed.bucket, 'selected')
        self.assertEqual((planned.bucket, planned.reinstatable), ('excluded', True))
        self.assertIn('Documented as planned', planned.exclusion_reason)

    def test_the_engine_runs_on_real_routing(self):
        from studio.gi.detect import route
        result = self.run_real(route(self.NOTE.text))
        for item in result.proposals:
            for span in item.evidence:
                self.assertEqual(self.NOTE.text[span.start:span.end], span.text)
            self.assertIn(item.status, ('ready', 'needs_clarification', 'excluded', 'informational'))
