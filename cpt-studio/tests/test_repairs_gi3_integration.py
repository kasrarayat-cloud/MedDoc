"""CPT Studio GI round 3: the integration owner's tests, run on the four repairs merged (dates, extent, scope, inventory).

- JointH208Tests: h2-08 end to end. Its header's date of service (2026-10-05) and its charge block's (2026-10-06)
  conflict, so the date is asked and the provider request carries no date line; routing reads today's office visit
  with its 44 minutes (the scope repair), and 99215 is never ready while the date is open (the scope repair alone made
  it ready on the contradicted 2026-10-05). A member's answer naming one of the two dates is taken, builds one dated
  request, and closes the question; any other date is held.
- HeadingKindTests (H1, context._Governance.names_a_kind): the encounter's own date-of-service label under a plan's
  block heading that names only a kind of service speaks against the note's own date; a heading naming another
  occurrence, and a table's column label, still govern.
- NoOwnDateTests (H2): B4's visit or procedure field in a note that labels no date of its own stays dropped as the
  installed reading dropped it, so a planned date is never the only answer a member may give.
- ActTechniqueTests (services._OTHER_INSTRUMENT): an act never takes the technique of the instrument its own kind rules
  out (ho-01's biopsy had read as "forceps biopsy (cold snare)").
- IntegrationInvariantTests: H1 and H2 never send a date the installed reading does not send.
"""
import itertools
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context, services
from studio.gi.detect import route
from studio.providers import corti
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess
from tests.test_repairs_gi3_dates import BANNER, binding_disabled, facts, fixture, member

H208 = ('live-text/h2-08__e084b793__2026-10-29.txt', 'h2/h2-08-hepatology-note.txt')
# What Corti cited for 99215 on the live h2-08 encounter: the visit's title and its time statement.
H208_CITED = ('Hepatology follow-up note', 'Physician time on the service date: 44 minutes')


def run(text, picks, ctx, day):
    """The engine on ``text`` with these provider picks ((code, passages)), the context ``ctx`` and the date ``day``
    (None while it is asked), routing read for that date as the pipeline reads it."""
    codes = tuple(ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED', index=index,
                               evidence=tuple(EvidenceSpan(0, text.index(p), text.index(p) + len(p), p, True)
                                              for p in passages))
                  for index, (code, passages) in enumerate(picks))
    result = assess(text=text, pages=(), context=ctx, routing=route(text, day),
                    normalized=NormalizedResponse('replay', 'gi3-integration', codes=codes),
                    reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded',
                    extraction_status='ok')
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}, result


class JointH208Tests(SimpleTestCase):
    def test_the_date_is_asked_and_no_date_line_is_sent(self):
        for name in H208:
            with self.subTest(text=name):
                text = fixture(name)
                fact = facts(text)['service_date']
                self.assertEqual((fact.origin, fact.value), ('conflict', None))
                self.assertEqual(sorted(' '.join(e.text.split()) for e in fact.evidence),
                                 ['Date of service: 2026-10-05', 'Date of service: 2026-10-06'])
                self.assertIsNone(context.service_date_of(text))
                request = corti.build_coding_request('corti', 'gi3-integration', text, None, 10 ** 7)
                self.assertEqual(request.contexts, (text,))

    def test_todays_visit_is_read_and_99215_is_never_ready_while_the_date_is_open(self):
        for name in H208:
            with self.subTest(text=name):
                text = fixture(name)
                em = route(text, None).finding('gi.office_em')
                self.assertEqual(em.status, 'performed')
                self.assertEqual({f.name: f.value for f in em.facts if f.value}.get('time_minutes'), '44')
                proposals, result = run(text, [('99215', H208_CITED)], facts(text), None)
                self.assertNotEqual(proposals['99215'].status, 'ready')
                self.assertIn('service_date', [c.fact for c in result.clarifications])

    def test_a_members_answer_closes_the_question_with_one_dated_request(self):
        for name in H208:
            with self.subTest(text=name):
                text = fixture(name)
                for answer in ('2026-10-05', '2026-10-06'):
                    self.assertEqual(member(text, answer), 'taken', answer)
                for other in ('2026-10-07', '2026-09-28', '1959-06-02'):
                    self.assertEqual(member(text, other), 'held', other)
                merged = context.merge_user_values(facts(text), {'service_date': '2026-10-06'})
                self.assertEqual((merged['service_date'].origin, merged['service_date'].value), ('user', '2026-10-06'))
                day = date(2026, 10, 6)
                request = corti.build_coding_request('corti', 'gi3-integration', text, day, 10 ** 7)
                self.assertEqual(request.contexts, (text, 'Date of service: 2026-10-06'))
                proposals, result = run(text, [('99215', H208_CITED)], merged, day)
                self.assertNotIn('service_date', [c.fact for c in result.clarifications])
                self.assertEqual(proposals['99215'].status, 'ready')


HEADER = (BANNER + 'Synthetic GI clinic (fictional)\nClinic note\nPatient: Synthetic Patient (fictional)\n'
          '{own}Place of service: office (POS 11)\nEstablished patient\n\nSubjective\nFollow-up of anemia.\n\n'
          'Assessment and plan\nIron deficiency anemia. Continue oral iron.\n')
OWN = 'Date of service: 2026-10-05\n'


def billing(heading, label='Date of service: 2026-10-06', own=OWN):
    return HEADER.format(own=own) + heading + '\nCPT: 99214\n' + label + '\nElectronically signed: Synthetic MD (fictional)\n'


def date_of(text):
    fact = facts(text)['service_date']
    return fact.origin, fact.value


class HeadingKindTests(SimpleTestCase):
    # each heading stays a block heading of the plan section ("Procedure" alone opens a procedure section of its own)
    KINDS = ('Office visit', 'Clinic visit', 'Coding review', 'Visit', 'Colonoscopy', 'Upper endoscopy',
             'Office visit charge', 'Consultation')
    OTHERS = ('Next appointment', 'Prior visit', 'Return visit', 'Recall', 'Results', 'Labs', 'Follow-up appointment',
              'Follow up appointment', 'Pending procedures', 'Transplant evaluation', 'Scheduled procedure',
              'Outside records', 'Last colonoscopy', 'Referral')

    def test_a_kind_of_service_heading_lets_the_billing_date_speak(self):
        for heading in self.KINDS:
            with self.subTest(heading=heading):
                self.assertEqual(date_of(billing(heading)), ('conflict', None))
                self.assertEqual(date_of(billing(heading, 'Date of service: 2026-10-05')), ('document', '2026-10-05'))

    def test_a_heading_naming_another_occurrence_still_governs(self):
        for heading in self.OTHERS:
            with self.subTest(heading=heading):
                self.assertEqual(date_of(billing(heading)), ('document', '2026-10-05'))

    def test_only_the_encounters_own_label(self):
        # a visit or procedure date under such a heading keeps B4's reading (the heading governs it)
        self.assertEqual(date_of(billing('Office visit', 'Visit date: 2026-10-06')), ('document', '2026-10-05'))

    def test_a_tables_column_label_dates_its_rows(self):
        table = 'Test | Date of service | Result\nFerritin | 2026-09-30 | 41 ng/mL'
        for heading in ('Office visit', 'Colonoscopy'):
            with self.subTest(heading=heading):
                self.assertEqual(date_of(billing(heading, table)), ('document', '2026-10-05'))

    def test_with_no_own_date_it_stays_dropped_as_installed(self):
        for heading in ('Office visit', 'Colonoscopy'):
            with self.subTest(heading=heading):
                text = billing(heading, own='')
                self.assertEqual(date_of(text)[0], 'missing')
                for answer in ('2026-10-06', '2026-10-01'):
                    self.assertEqual(member(text, answer), 'taken', answer)


class NoOwnDateTests(SimpleTestCase):
    PLANNED = 'Plan:\nColonoscopy with possible polypectomy.\nProcedure date: 11/04/2026\n'

    def note(self, own, plan):
        return (BANNER + 'Synthetic GI clinic (fictional)\nClinic note\nPatient: Synthetic Patient (fictional)\n' + own
                + 'Place of service: office (POS 11)\nEstablished patient\n\nSubjective\nFollow-up of anemia.\n\n' + plan
                + 'Electronically signed: Synthetic MD (fictional)\n')

    def test_a_planned_date_is_never_the_only_answer(self):
        text = self.note('', self.PLANNED)
        self.assertEqual(date_of(text)[0], 'missing')
        for answer in ('2026-11-04', '2026-10-05', '2026-10-01'):
            self.assertEqual(member(text, answer), 'taken', answer)

    def test_with_an_own_date_the_field_still_speaks(self):
        b4 = 'Assessment and plan\nContinue diuretics.\n\nPhysician time on the service date: 38 minutes.\n\nVisit date: 2026-10-06\n'
        self.assertEqual(date_of(self.note(OWN, b4)), ('conflict', None))
        self.assertEqual(date_of(self.note(OWN, 'Plan:\nReturn to clinic in 6 weeks.\nVisit date: 2026-11-16\n')),
                         ('document', '2026-10-05'))


class ActTechniqueTests(SimpleTestCase):
    """services._OTHER_INSTRUMENT: a forceps act never takes a snare technique, a snare act never a forceps one."""

    def acts(self, text):
        day = context.service_date_of(text)
        inventory = services.build(text, service_date=day, routing=route(text, day), context_facts=facts(text),
                                   pages=())
        return [(a.kind, a.technique) for s in inventory.services for a in s.acts]

    def test_ho_01s_biopsy_is_no_snare_biopsy(self):
        for name in ('live-text/ho-01__30d3f32d__2026-10-29.txt', 'ho/ho-01-egd-colonoscopy-tattoo-conflict.txt'):
            with self.subTest(text=name):
                acts = self.acts(fixture(name))
                self.assertTrue(any(kind == 'biopsy' for kind, _ in acts))
                self.assertFalse([t for kind, t in acts if kind in ('biopsy', 'hot_biopsy') and 'snare' in t])
                self.assertIn(('snare', 'cold snare'), acts)

    def test_one_clause_two_instruments(self):
        text = (BANNER + 'Synthetic GI clinic (fictional)\nColonoscopy report\nDate of service: 2026-10-05\n'
                'Findings\nA 6 mm polyp in the ascending colon was removed with a cold snare, and a 3 mm polyp in the '
                'rectum was removed with cold forceps.\nImpression\nTwo polyps removed.\n')
        acts = self.acts(text)
        self.assertFalse([t for kind, t in acts if kind == 'snare' and 'forceps' in t])
        self.assertFalse([t for kind, t in acts if kind in ('biopsy', 'hot_biopsy') and 'snare' in t])


class IntegrationInvariantTests(SimpleTestCase):
    """H1 and H2 only ever ask: over every heading, label, header and plan section here, no date is sent that the
    installed reading (binding_disabled) does not send, and every sent date is the installed one."""
    HEADINGS = HeadingKindTests.KINDS + HeadingKindTests.OTHERS + ('', 'Charge information')
    LABELS = ('Date of service: 2026-10-06', 'DOS: 10/06/2026', 'Encounter date: 2026-10-06', 'Service date: 2026-10-06',
              'Visit date: 2026-10-06', 'Procedure date: 11/04/2026', 'Date of service: 2026-10-05',
              'Test | Date of service | Result\nFerritin | 2026-09-30 | 41 ng/mL')
    OWNS = ('', OWN, 'Date of service: 2026-10-06\n')
    SECTIONS = ('Assessment and plan\n', 'Plan:\n', 'Recommendations:\n', 'Plan:\nColonoscopy with possible polypectomy.\n')

    def test_never_a_new_send(self):
        texts = [BANNER + 'Synthetic GI clinic (fictional)\nClinic note\n' + own + 'Subjective\nFollow-up.\n\n' + section
                 + (heading + '\n' if heading else '') + label + '\nElectronically signed: Synthetic MD (fictional)\n'
                 for own, section, heading, label in itertools.product(self.OWNS, self.SECTIONS, self.HEADINGS,
                                                                       self.LABELS)]
        now = [context.service_date_of(text) for text in texts]
        with binding_disabled():
            before = [context.service_date_of(text) for text in texts]
        for text, a, b in zip(texts, now, before):
            if a is not None:
                self.assertEqual(a, b, text)
