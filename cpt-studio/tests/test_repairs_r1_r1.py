"""Refutation r1, cluster R1 - roles and attribution: whose act it is (studio/gi/services.py).

missed-1  a staff field naming a nurse ("Nurse: Jo Rowe, RN") opened a nursing part over the physician's report, so
          every later act of the report was read as nursing and skipped by reconciliation (a hidden missed service and
          a false "every documented service has a proposal").
missed-2  a nursing or anesthesia signature anywhere in a sentence ("..., placed in formalin and documented by Jo Rowe,
          RN", "Under propofol sedation given by the CRNA and documented in the anesthesia record, ...") relabelled the
          physician's act in it, which hid the act and dropped the base-code hold.

Each text is a fresh synthetic paraphrase written for the case under test; the expected readings are written here,
outside the reader.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess


def span(text, phrase):
    start = text.index(phrase)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def sel(code, *spans):
    return ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING', tuple(spans))


def _day(facts):
    fact = facts['service_date']
    return date.fromisoformat(fact.value) if fact.origin in ('document', 'user') and fact.value else None


def read(text):
    facts = gi_context.extract_context(text)
    day = _day(facts)
    return services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)


def run(text, codes):
    facts = gi_context.extract_context(text)
    day = _day(facts)
    return assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def acts(inv, family):
    return [(a.kind, a.status, a.role) for s in inv.services if s.family == family for a in s.acts]


def unresolved(result):
    return sorted((u['family'], u['act'], u['reason']) for u in result.completeness['unresolved_items'])


def proposal(result, code):
    return next(p for p in result.proposals if p.code == code and p.bucket != 'alternative')


HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'

COLON_WITH_STAFF = HEAD + """COLONOSCOPY REPORT
Date of service: 10/14/2026
Patient: Test Patient (fictional)
Endoscopist: Dana Example, MD (fictional)
{staff}
Indication: Surveillance after prior adenoma.
Findings: The colonoscope was advanced to the cecum; the appendiceal orifice and ileocecal valve were identified. A 6 mm \
sessile polyp in the sigmoid colon was removed with cold snare. A 4 mm polyp in the rectum was removed with cold \
biopsy forceps.
Impression: Two small polyps removed.
"""
REACHED = 'The colonoscope was advanced to the cecum'


class StaffFieldIsNoNursingPartTests(SimpleTestCase):
    """missed-1: a line that names a nurse and gives a value, or a line of prose about a nurse, is a staff field, not
    the heading of a nursing entry. Only a heading that names the nursing role's own entry (its record, notes,
    checklist), or the role's name alone on its line, opens a nursing part."""

    STAFF_FIELDS = ('Nurse: Jo Rowe, RN (fictional)', 'RN: Jo Rowe (fictional)',
                    'Nursing staff: Jo Rowe, RN; Sam Lee, LPN (fictional)', 'Recovery nurse: Pat Kim, RN (fictional)',
                    'Nursing: Jo Rowe, RN (fictional)', 'Nurse present throughout the procedure.',
                    'Intra-procedure nursing: Jo Rowe, RN (fictional)')

    def test_the_finding_input_keeps_the_physicians_acts_unresolved(self):
        text = COLON_WITH_STAFF.format(staff='Nurse: Jo Rowe, RN (fictional)')
        result = run(text, [sel('45378', span(text, REACHED))])
        self.assertEqual(unresolved(result), [('gi.colonoscopy', 'biopsy', 'not_covered'),
                                              ('gi.colonoscopy', 'snare', 'not_covered')])
        base = proposal(result, '45378')
        self.assertEqual(base.status, 'needs_clarification')
        self.assertIn('services.base_included', {c.id for c in base.checks})
        self.assertEqual(result.completeness['state'], 'incomplete')

    def test_every_staff_field_wording_leaves_the_report_to_the_physician(self):
        for staff in self.STAFF_FIELDS:
            with self.subTest(staff=staff):
                text = COLON_WITH_STAFF.format(staff=staff)
                self.assertFalse([p for p in services.parts(text) if p.role != 'physician'])
                self.assertEqual(acts(read(text), 'gi.colonoscopy'), [('snare', 'performed', 'physician'),
                                                                      ('biopsy', 'performed', 'physician')])

    def test_a_staff_field_under_the_title_or_after_the_findings_reads_the_same(self):
        for where in ('title', 'end'):
            with self.subTest(where=where):
                body = COLON_WITH_STAFF.format(staff='').replace('\n\n', '\n')
                if where == 'title':
                    text = body.replace('COLONOSCOPY REPORT\n', 'COLONOSCOPY REPORT\nRN: Jo Rowe (fictional)\n')
                else:
                    text = body.replace('Impression:', 'Nurse: Jo Rowe, RN (fictional)\nImpression:')
                self.assertEqual(acts(read(text), 'gi.colonoscopy'), [('snare', 'performed', 'physician'),
                                                                      ('biopsy', 'performed', 'physician')])

    def test_the_elena_shape_keeps_the_separately_sampled_lesion_visible(self):
        # the provider codes only the snare removal: the forceps removal of a separate lesion stays unresolved
        text = COLON_WITH_STAFF.format(staff='Nurse: Jo Rowe, RN (fictional)')
        result = run(text, [sel('45385', span(text, 'was removed with cold snare'))])
        self.assertEqual(unresolved(result), [('gi.colonoscopy', 'biopsy', 'not_covered')])
        self.assertEqual(result.completeness['state'], 'incomplete')

    def test_a_nursing_entry_heading_still_opens_a_nursing_part(self):
        # the other direction: the role's own entry, under any of its heading forms, is still the nurse's
        rows = 'Time-out completed   [X] Yes   [ ] No\nSpecimen collected   [X] Yes   [ ] No\n'
        report = HEAD + ('Flexible sigmoidoscopy report\nDate of service: 2026-10-14\nThe sigmoidoscope was advanced to '
                         '45 cm. Three internal hemorrhoid columns were ligated with rubber bands.\n'
                         'No biopsies were obtained.\n')
        for heading in ('NURSING PROCEDURE RECORD (Delphine Oakes, LPN (fictional))', 'Nursing record',
                        "Nurse's notes", 'Nurse\u2019s notes', 'Nursing checklist', 'Procedure checklist', 'NURSING',
                        'Nursing:',
                        'Intra-procedure nursing checklist', 'Nursing note: 10/14/2026 08:30'):
            with self.subTest(heading=heading):
                text = report + heading + '\n' + rows
                roles = {p.role for p in services.parts(text) if p.start >= text.index(heading)}
                self.assertEqual(roles, {'nursing'})
                inv = read(text)
                self.assertEqual([c.subject for c in inv.conflicts], ['biopsy'])
                self.assertEqual({side.role for side in inv.conflicts[0].sides}, {'nursing', 'physician'})

    def test_other_roles_headings_are_unchanged(self):
        for heading, role in (('Anesthesia record', 'anesthesia'), ('Anesthesia record: Pat Kim, CRNA (fictional)',
                                                                    'anesthesia'),
                              ('Pathology report: 2026-10-14', 'pathology'), ('Radiology report', 'radiology')):
            with self.subTest(heading=heading):
                text = HEAD + 'Colonoscopy report\n' + heading + '\nSome entry text.\n'
                self.assertIn(role, {p.role for p in services.parts(text)})


EGD_WITH = HEAD + """UPPER ENDOSCOPY REPORT
Date of service: 10/14/2026
Patient: Test Patient (fictional)
Endoscopist: Dana Example, MD (fictional)
Procedure: Esophagogastroduodenoscopy
Indication: Dyspepsia; evaluate for Helicobacter pylori.
Description: The gastroscope was advanced to the second portion of the duodenum. The esophagus and duodenum were normal. \
Mild erythema was seen in the gastric antrum.
{sentence}
Impression: Antral gastritis.
"""
COLON_WITH = HEAD + """COLONOSCOPY REPORT
Date of service: 10/14/2026
Patient: Test Patient (fictional)
Endoscopist: Dana Example, MD (fictional)
Indication: Surveillance after prior adenoma.
Findings: The colonoscope was advanced to the cecum; the appendiceal orifice and ileocecal valve were identified. \
{sentence}
Impression: One small polyp removed.
"""


class SignatureSpeaksOnlyAsItsEntrysLabelTests(SimpleTestCase):
    """missed-2: a signature speaks for an act only as the label its sentence opens with, closed by a colon before the
    act ("Recorded by Jo Fictional RN: India ink tattoo [X] Performed"). Anywhere else it names who recorded something
    else - a specimen, the sedation, the vital signs - never who documented the physician's act."""

    def test_the_specimen_signature_leaves_the_biopsy_to_the_physician(self):
        text = EGD_WITH.format(sentence='Cold forceps biopsies were obtained from the gastric antrum and body, placed in '
                                        'formalin and documented by Jo Rowe, RN (fictional).')
        self.assertEqual(acts(read(text), 'gi.egd'), [('biopsy', 'performed', 'physician')])
        result = run(text, [sel('43235', span(text, 'The gastroscope was advanced to the second portion'))])
        self.assertEqual(unresolved(result), [('gi.egd', 'biopsy', 'not_covered')])
        base = proposal(result, '43235')
        self.assertEqual(base.status, 'needs_clarification')
        self.assertIn('services.base_included', {c.id for c in base.checks})
        self.assertEqual(result.completeness['state'], 'incomplete')

    def test_the_sedation_signature_leaves_the_snare_to_the_physician_and_keeps_the_attribution(self):
        text = COLON_WITH.format(sentence='Under propofol sedation given by the CRNA and documented in the anesthesia '
                                          'record, a 6 mm sigmoid colon polyp was removed with cold snare.')
        inv = read(text)
        self.assertEqual(acts(inv, 'gi.colonoscopy'), [('snare', 'performed', 'physician')])
        self.assertIn('anesthesia', [a.role for a in inv.attributions])
        result = run(text, [sel('45378', span(text, REACHED))])
        self.assertEqual(unresolved(result), [('gi.colonoscopy', 'snare', 'not_covered')])
        self.assertEqual(proposal(result, '45378').status, 'needs_clarification')

    def test_a_signature_in_another_clause_a_parenthesis_or_a_phrase_signs_nothing_of_the_act(self):
        for sentence in ('A 6 mm sigmoid colon polyp was removed with cold snare; the specimen was retrieved and charted '
                         'by the endoscopy nurse.',
                         'A 6 mm sigmoid colon polyp was removed with cold snare and retrieved per the nursing checklist.',
                         'A 6 mm sigmoid colon polyp was removed with cold snare (specimen count recorded by the RN).',
                         'While the CRNA documented vital signs, a 6 mm sigmoid colon polyp was removed with cold snare.',
                         'With deep sedation by the anesthesiologist, recorded separately, an 8 mm cecal polyp was '
                         'removed with hot snare.',
                         'A 6 mm sigmoid colon polyp was removed with cold snare (nursing handoff completed).',
                         'Polypectomy note: a 6 mm sigmoid colon polyp was removed with cold snare, charted by Jo Rowe, '
                         'RN (fictional).'):
            with self.subTest(sentence=sentence):
                text = COLON_WITH.format(sentence=sentence)
                self.assertIn(('snare', 'performed', 'physician'), acts(read(text), 'gi.colonoscopy'))
                result = run(text, [sel('45378', span(text, REACHED))])
                self.assertIn(('gi.colonoscopy', 'snare', 'not_covered'), unresolved(result))
                self.assertEqual(result.completeness['state'], 'incomplete')

    def test_a_signature_that_labels_its_entry_still_speaks_for_it(self):
        # the other direction: the nurse's own entry, signed as its label, stays the nurse's and keeps the conflict
        for entry in ('Recorded by Jo Rowe, RN (fictional): India ink tattoo [X] Performed [ ] Not performed.',
                      'Intra-procedure checklist charted by Lee Park, RN (fictional): Tattoo [X] Performed [ ] Not '
                      'performed.',
                      'Nursing checklist: Tattoo [X] Performed [ ] Not performed.'):
            with self.subTest(entry=entry):
                text = COLON_WITH.format(sentence='No tattoo was placed.\n' + entry)
                inv = read(text)
                self.assertIn(('tattoo', 'performed', 'nursing'), acts(inv, 'gi.colonoscopy'))
                self.assertEqual([(c.subject, sorted({(side.role, side.status) for side in c.sides}))
                                  for c in inv.conflicts],
                                 [('tattoo', [('nursing', 'performed'), ('physician', 'negated')])])
