"""Refutation r1, cluster R1 - roles and attribution: whose act it is (studio/gi/services.py).

missed-1  a staff field naming a nurse ("Nurse: Jo Rowe, RN") opened a nursing part over the physician's report, so
          every later act of the report was read as nursing and skipped by reconciliation (a hidden missed service and
          a false "every documented service has a proposal").

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
