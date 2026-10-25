"""Regressions for refutation round 3 over validation (round 3b repairs): validation:0 and routing:4, and the helpers
the other round-3b validation modules share.

Each class reproduces one confirmed finding through the real router (JSON round-tripped as the assess stage stores it),
the real span reader and the engine, and pins controls that must keep their reading. Synthetic text only; pure
functions.
"""
import json
from datetime import date

from django.test import SimpleTestCase

from studio.gi.context import extract_context
from studio.gi.detect import route
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, RoutingResult, from_jsonable,
                          to_jsonable)
from studio.validation import checks
from studio.validation.engine import assess
from tests.test_validation import MUE_INFO, PFS_INFO, pfs

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nDate of service: 2026-10-21\n'
ROWS = {(code, ''): pfs(days='XXX', mult='0') for code in ('99213', '99214', '91010', '91110', '91122')}
ROWS.update({('46221', ''): pfs(days='010'), ('46600', ''): pfs(), ('45300', ''): pfs(), ('45378', ''): pfs(),
             ('45380', ''): pfs(mult='3', base='45378'), ('45385', ''): pfs(mult='3', base='45378'),
             ('45330', ''): pfs(), ('43239', ''): pfs(mult='3', base='43235'), ('43450', ''): pfs()})
REFERENCE = InMemoryReferenceLookup([PFS_INFO, MUE_INFO], {PFS_INFO.key: ROWS, MUE_INFO.key: {}})


def real(text, *picks, reference=REFERENCE):
    """picks: (code, evidence phrase, ...). Real routing on the documented date, the real span reader and the engine.
    Returns (proposals by code, result)."""
    context = extract_context(text)
    fact = context['service_date']
    day = date.fromisoformat(fact.value) if fact.origin == 'document' and fact.value else None
    routing = from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, day)))))
    codes = []
    for index, (code, *phrases) in enumerate(picks):
        spans = []
        for phrase in phrases:
            assert text.count(phrase) == 1, phrase
            start = text.index(phrase)
            spans.append(EvidenceSpan(0, start, start + len(phrase), phrase, True))
        codes.append(ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED', evidence=tuple(spans),
                                  index=index))
    result = assess(text=text, pages=(PageSpan(1, 0, len(text)),), context=context, routing=routing,
                    normalized=NormalizedResponse('corti', 'corti-coding@1', codes=tuple(codes)),
                    reference=reference, service_date=day, provider_status='succeeded', extraction_status='ok')
    return {p.code: p for p in result.proposals}, result


def check_of(item, check_id):
    found = [c for c in item.checks if c.id == check_id]
    return found[0] if found else None


def encounter_check(result, check_id):
    (found,) = [c for c in result.encounter_checks if c.id == check_id]
    return found


class Case(SimpleTestCase):
    maxDiff = None

    def assertReady(self, item):
        self.assertEqual((item.bucket, item.status, item.clarifications), ('selected', 'ready', ()),
                         [c.detail for c in item.checks])

    def assertVisitReady(self, proposals, code='99214'):
        visit = proposals[code]
        self.assertReady(visit)
        self.assertIsNone(check_of(visit, 'em.same_day_procedure'))

    def assertVisitHeld(self, proposals, phrase, code='99214'):
        visit = proposals[code]
        self.assertEqual(visit.status, 'needs_clarification')
        self.assertIn('separate_em', [c.fact for c in visit.clarifications])
        self.assertIn(phrase, check_of(visit, 'em.same_day_procedure').detail)


# --- validation:0 and routing:4: a gi.other code's section default names no procedure -----------------------

COLONOSCOPY_A = (HEAD + 'Procedure: Colonoscopy\nIndication: Average-risk screening.\nFindings: The colonoscope was '
                 'advanced to the cecum. The colon was normal. Grade 2 internal hemorrhoids were seen on '
                 'retroflexion.\n'
                 'Impression: Internal hemorrhoids; banding may be considered at a later date.\n'
                 'Plan: Repeat colonoscopy in 10 years.\n')
RETROFLEXION = 'Grade 2 internal hemorrhoids were seen on retroflexion.'
OFFICE_OTHER = (HEAD + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n'
                'Chief complaint: rectal bleeding.\n{body}\nMedical decision making: moderate.\n'
                'Total time: 32 minutes.\n')
VISIT = 'Established patient office visit.'
DECLINED = 'Procedure: Anoscopy - patient declined.'
BANDED = 'Rubber band ligation x3 completed today.'
FLEX_SIG = (HEAD + 'Procedure: Flexible sigmoidoscopy\nIndication: Rectal bleeding.\n'
            'Findings: The sigmoidoscope was advanced to 40 cm. Normal mucosa.\nPlan: Fiber supplementation.\n')
GI03 = open('ops/verification/documents/gi-03-screening-colonoscopy-polypectomy-biopsy.txt', encoding='utf-8').read()


class Validation0SectionOnlyOtherCodeTests(Case):
    """validation:0 and routing:4 — a gi.other code whose only positive passage reads performed by its section alone,
    and names no procedure, is held for clarification like a detected family's code; it is never ready."""

    def assertHeldUnnamed(self, item, passage):
        self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'),
                         [c.detail for c in item.checks])
        self.assertEqual([c.fact for c in item.clarifications if c.fact == 'performed_status'], ['performed_status'])
        status = check_of(item, 'service.status')
        self.assertEqual(status.status, 'warn')
        self.assertNotIn('Documented as performed', status.detail)
        self.assertIn(f'“{passage}”', status.detail)
        # round 5 validation:1: worded from the rule, never 'names no procedure' (a held passage may name one)
        self.assertIn('is not read as documenting that service as done on that date', status.detail)
        self.assertNotIn('names no procedure', status.detail)
        self.assertNotIn('never names', status.detail)
        self.assertIn('Service status: not established as performed.', item.rationale)

    def test_a_findings_sentence_of_a_colonoscopy_report(self):
        proposals, result = real(COLONOSCOPY_A, ('45378', 'The colonoscope was advanced to the cecum.'),
                                 ('46221', RETROFLEXION), ('46600', 'The colon was normal.'))
        self.assertReady(proposals['45378'])
        self.assertHeldUnnamed(proposals['46221'], RETROFLEXION)
        self.assertHeldUnnamed(proposals['46600'], 'The colon was normal.')
        unsupported = encounter_check(result, 'services.unsupported')
        self.assertNotIn('Performed without a GI profile', unsupported.detail)
        self.assertNotIn('No selected code', unsupported.detail)
        self.assertIn('46221', unsupported.detail)
        self.assertEqual([(e['family'], e['status'], e['codes']) for e in result.unsupported],
                         [('gi.other', 'uncertain', ['46221', '46600'])])

    def test_a_finding_under_a_procedure_heading_whose_anoscopy_was_declined(self):
        for line in ('Grade 2 internal hemorrhoids.', 'Grade 2 internal hemorrhoids, banding candidate.'):
            for code in ('46221', '46600'):
                with self.subTest(line=line, code=code):
                    proposals, _ = real(OFFICE_OTHER.format(body=f'{DECLINED}\n{line}'), ('99214', VISIT), (code, line))
                    self.assertHeldUnnamed(proposals[code], line)
                    # still held as a possible same-day procedure: never released by the code's doubt
                    self.assertVisitHeld(proposals, f'the service reported as {code} is possibly performed')

    def test_a_procedure_section_that_says_none(self):
        note = OFFICE_OTHER.format(body='Procedure: None.\nFindings: Grade 2 internal hemorrhoids.')
        proposals, _ = real(note, ('46221', 'Grade 2 internal hemorrhoids.'))
        self.assertHeldUnnamed(proposals['46221'], 'Grade 2 internal hemorrhoids.')

    def test_a_procedure_word_that_is_not_the_procedure_done(self):
        # Routing reads each line performed by its Procedure section; the form rule rejects the name it opens with: a
        # consult, a request and a condition name no procedure done.
        for line in ('Hemorrhoid banding consult.', 'Requested banding, columns 1 and 2.',
                     'Should banding fail, sclerotherapy is next.'):
            with self.subTest(line=line):
                proposals, _ = real(OFFICE_OTHER.format(body=f'Procedure: Anoscopy.\n{line}'), ('46221', line))
                self.assertHeldUnnamed(proposals['46221'], line)

    def test_a_flexible_sigmoidoscopy_finding_for_a_rigid_proctosigmoidoscopy_code(self):
        proposals, _ = real(FLEX_SIG, ('45300', 'Normal mucosa.'))
        self.assertHeldUnnamed(proposals['45300'], 'Normal mucosa.')

    def test_the_unmodified_verification_document_gi_03(self):
        hemorrhoids = 'Small non-bleeding internal hemorrhoids were seen on retroflexion.'
        proposals, _ = real(GI03, ('46221', hemorrhoids), ('46600', hemorrhoids))
        for code in ('46221', '46600'):
            with self.subTest(code=code):
                self.assertHeldUnnamed(proposals[code], hemorrhoids)
        for passage in ('The remaining colonic mucosa was normal to the cecum.', 'Withdrawal time was 14 minutes.',
                        # a passage about another family's procedure names no gi.other procedure
                        'Colonoscopy with cold snare polypectomy and cold forceps biopsy.'):
            with self.subTest(passage=passage):
                proposals, _ = real(GI03, ('46221', passage))
                self.assertHeldUnnamed(proposals['46221'], passage)

    def test_the_office_visit_s_own_documentation_names_no_procedure(self):
        """Routing reads the visit statement and the time statement performed as E/M documentation: that is no
        evidence that a banding or an anoscopy was done."""
        body = f'{DECLINED}\n{BANDED}'
        for code, passage in (('46221', VISIT), ('46600', 'Total time: 32 minutes.')):
            with self.subTest(code=code):
                proposals, _ = real(OFFICE_OTHER.format(body=body), (code, passage))
                self.assertHeldUnnamed(proposals[code], passage)
                self.assertIn('only as E/M documentation', check_of(proposals[code], 'service.status').detail)
        proposals, _ = real(OFFICE_OTHER.format(body=body), ('46221', VISIT, BANDED))
        self.assertEqual(proposals['46221'].status, 'ready')
        self.assertIn(f'Documented as performed: “{BANDED}”', check_of(proposals['46221'], 'service.status').detail)

    def test_a_cited_fragment_is_read_in_its_sentence(self):
        """A provider may cite part of a sentence: the sentence's own leading name decides, never the fragment's
        first word ("banding" cut out of "Grade 2 internal hemorrhoids, banding candidate.")."""
        for line, fragment in (('Grade 2 internal hemorrhoids, banding candidate.', 'banding candidate'),
                               ('Grade 2 internal hemorrhoids, banding candidate.', 'banding'),
                               ('Grade 2 internal hemorrhoids, suitable for banding.', 'suitable for banding')):
            with self.subTest(fragment=fragment):
                proposals, _ = real(OFFICE_OTHER.format(body=f'{DECLINED}\n{line}'), ('46221', fragment))
                self.assertHeldUnnamed(proposals['46221'], fragment)
        # the stated act's sentence names the banding done today, whatever fragment is cited
        proposals, _ = real(OFFICE_OTHER.format(body=f'{DECLINED}\nInternal hemorrhoids were banded x3 today.'),
                            ('46221', 'Internal hemorrhoids'))
        self.assertEqual(proposals['46221'].status, 'ready')

    def test_controls_a_detected_family_code_citing_the_same_passage_is_held_as_before(self):
        proposals, _ = real(COLONOSCOPY_A, ('45330', RETROFLEXION), ('43239', RETROFLEXION))
        for code in ('45330', '43239'):
            self.assertIn('never names', check_of(proposals[code], 'service.status').detail)

    def test_controls_a_passage_that_names_or_states_the_procedure_stays_ready(self):
        cases = (
            # af35d0ed0's real-routing control: the act stated by its participle, today
            (f'{DECLINED}\nInternal hemorrhoids were banded x3 today.', 'Internal hemorrhoids were banded x3 today.',
             '46221'),
            (f'{DECLINED}\nTwo internal hemorrhoids were banded today without complication.',
             'Two internal hemorrhoids were banded today without complication.', '46221'),
            (f'{DECLINED}\nToday we banded two internal hemorrhoids.', 'Today we banded two internal hemorrhoids.',
             '46221'),
            # an explicit performance cue, with or without a procedure name the form rule reads
            (f'{DECLINED}\nRubber band ligation x3 completed today.', 'Rubber band ligation x3 completed today.',
             '46221'),
            (f'{DECLINED}\nBands were placed on three columns.', 'Bands were placed on three columns.', '46221'),
        )
        report = HEAD + 'Procedure: \u2612 Informed consent \u2612 Rubber band ligation of two columns\n' \
            'Findings: Grade 2 internal hemorrhoids.\n'
        texts = [(OFFICE_OTHER.format(body=body), passage, code) for body, passage, code in cases]
        # a check-box line whose first item is no procedure: routing's gi.other mention (read done) names the banding
        texts.append((report, '\u2612 Informed consent \u2612 Rubber band ligation of two columns', '46221'))
        for text, passage, code in texts:
            with self.subTest(passage=passage):
                proposals, _ = real(text, (code, passage))
                item = proposals[code]
                self.assertEqual((item.bucket, item.status), ('selected', 'ready'), [c.detail for c in item.checks])
                self.assertEqual(check_of(item, 'service.status').status, 'pass')

    def test_round_4_holds_a_section_that_only_names_the_procedure(self):
        """Round 4 (validation:2, evidence:0, release:11) made the rule fail closed: a section-only passage counts for
        a gi.other code only when a routed gi.other mention read as done, the code's own procedure, lies in it (or in
        the first sentence of its procedure section), or the code's own act is stated today. In these office notes
        routing reads the procedure heading only as uncertain (an office note's heading alone does not establish it),
        the later lines of a procedure section are no routed mention, and a cauterization is no banding: each is now
        held (an accepted over-hold, medium), never excluded."""
        cases = (
            # the routing:4 verifier's control G: the procedure named in its section, but not as its first sentence
            (f'{DECLINED}\nRubber band ligation of a grade 2 internal hemorrhoid x1.',
             'Rubber band ligation of a grade 2 internal hemorrhoid x1.', '46221'),
            (f'{DECLINED}\nRubber band ligation of a grade 2 internal hemorrhoid x1.', 'grade 2 internal hemorrhoid x1',
             '46221'),
            ('Procedure: Anoscopy with rubber band ligation of two internal hemorrhoids.',
             'Anoscopy with rubber band ligation of two internal hemorrhoids.', '46221'),
            ('Procedure: Anoscopy.\nFindings: Anoscopy revealed grade 2 internal hemorrhoids.',
             'Anoscopy revealed grade 2 internal hemorrhoids.', '46600'),
            ('Procedure: Anoscopy.\nFindings: On anoscopy, grade 2 internal hemorrhoids were seen.',
             'On anoscopy, grade 2 internal hemorrhoids were seen.', '46600'),
            ('Procedure: Anoscopy.\n2) Rubber band ligation of two columns.', '2) Rubber band ligation of two columns.',
             '46221'),
            ('Procedure: Anoscopy.\n(2) Rubber band ligation of two columns.',
             '(2) Rubber band ligation of two columns.', '46221'),
            ('Procedure: Anoscopy.\nThe hemorrhoid was cauterized.', 'The hemorrhoid was cauterized.', '46221'),
        )
        for body, passage, code in cases:
            with self.subTest(passage=passage, code=code):
                proposals, _ = real(OFFICE_OTHER.format(body=body), (code, passage))
                self.assertHeldUnnamed(proposals[code], passage)

    def test_resolve_status_holds_only_when_every_positive_passage_is_unnamed(self):
        section_only = checks.Reading('performed', ('section: findings (Findings)',), 'evidence', RETROFLEXION,
                                      unnamed=True)
        named = checks.Reading('performed', ('section: procedure (Procedure)',), 'evidence', 'Rubber band ligation x3.')
        negated = checks.Reading('negated', ('negated: declined',), 'evidence', 'Anoscopy - patient declined.')
        held = checks.resolve_status([section_only])
        self.assertEqual((held.state, held.reason, held.decisive), ('uncertain', 'section_only', section_only))
        # never an exclusion: a negative passage beside an unnamed positive one still holds
        held = checks.resolve_status([negated, section_only])
        self.assertEqual((held.state, held.reason, held.contrary), ('uncertain', 'section_only', negated))
        detail = checks.status_check(held, 'the service reported as 46221').detail
        self.assertIn('is not read as documenting that service as done on that date', detail)
        self.assertNotIn('names no procedure', detail)
        self.assertIn('Another linked passage reads as negated: “Anoscopy - patient declined.”', detail)
        ready = checks.resolve_status([section_only, named])
        self.assertEqual((ready.state, ready.decisive), ('performed', named))
