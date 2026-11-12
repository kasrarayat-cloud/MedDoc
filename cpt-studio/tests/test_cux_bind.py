"""Core repair and customer interface (2026-11-03), package P1 READ-BIND: how the shared reader binds a statement to its
procedure, lesion and scope, the explicit statement that no separate office E/M service is documented, and the gating
of office E/M documentation questions (DESIGN.md section 10, adopting R1-services-binding section 9, R2 1.4 and R3
7.5.3; declared before code in tests/fixtures/gi4/declarations/cux-bind.json).

Every document is synthetic. Each rule has a positive class document and must-stay-held twins in other wordings
(tests/fixtures/cux/reader/, each opening "SYNTHETIC TEST DOCUMENT - FICTIONAL"); Mara (tests/fixtures/cux/mara/), the
owner's worked example, is replayed end to end with its retained provider response. No document name, code or expected
result is known to the readers: every expectation lives here. No database, nothing sent.
"""
import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase

from ops.gi4 import battery
from studio import jobs
from studio.gi import context as gi_context
from studio.gi import cues, detect, services
from studio.providers import corti
from studio.reference.store import InMemoryReferenceLookup
from studio.types import PageSpan
from studio.validation import engine, reconcile

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'cux'
READER = FIXTURES / 'reader'
MARA = FIXTURES / 'mara'
B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
HEAD = B + 'Date of service: 2026-11-03\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
EM_QUESTIONS = {'setting', 'patient_status', 'em_basis'}


def document(name: str) -> str:
    return (READER / f'{name}.txt').read_text(encoding='utf-8')


def day_of(text: str):
    fact = gi_context.extract_context(text).get('service_date')
    try:
        return date.fromisoformat(fact.value) if fact is not None and fact.origin == 'document' and fact.value else None
    except ValueError:
        return None


def inventory(text: str, pages=()):
    day = day_of(text)
    return services.build(text, service_date=day, routing=detect.route(text, day),
                          context_facts=gi_context.extract_context(text), pages=pages)


def acts(inv, family=None, kind=None, status=None):
    return [a for s in inv.services if family is None or s.family == family for a in s.acts
            if (kind is None or a.kind == kind) and (status is None or a.status == status)]


def service(inv, family):
    return next((s for s in inv.services if s.family == family), None)


def conflicts(inv, family=None, subject=None):
    ids = {s.id for s in inv.services if family is None or s.family == family}
    return [c for c in inv.conflicts if c.service in ids and (subject is None or c.subject == subject)]


def run(text: str, codes=(), pages=None, normalized=None):
    """The analyze and assess children, as the stages (and ops.gi4.battery) read a document, with a synthetic provider
    answer selecting ``codes`` [(code, exact quote)] or the given ``normalized`` response; member values none."""
    m = battery.modules()
    document_facts, day, _routing = jobs._analyze_child(text, {}, 1000)
    facts = jobs._merged_facts(document_facts, {})
    context = jobs.context_facts(SimpleNamespace(facts=facts))
    response = normalized or battery.response(m, text, [(c, q, 'MAY') for c, q in codes])
    pages = (PageSpan(1, 0, len(text)),) if pages is None else pages
    _, result = jobs._assess_child(text, day, pages, context, response, InMemoryReferenceLookup([], {}), 'succeeded',
                                   'ok', ())
    jobs.release_routing_caches()
    return result


def outcomes(result) -> dict:
    return {p.code: (p.bucket, p.status, sorted(c.fact for c in p.clarifications))
            for p in result.proposals if p.bucket != 'alternative'}


def em_questions(result) -> set:
    return {c.fact for c in result.clarifications if c.scope == 'service' and c.family == 'gi.office_em'}


def bundled(result) -> list:
    families = {s['id']: s['family'] for s in result.services.get('services', [])}
    return [(families.get(b['service']), b['act']) for b in result.completeness.get('bundled', [])]


READY = ('selected', 'ready', [])


def held(*facts):
    return ('selected', 'needs_clarification', sorted(facts))


class ClassDocumentTests(SimpleTestCase):
    def test_every_class_document_is_marked_synthetic(self):
        names = sorted(p.stem for p in READER.glob('*.txt'))
        self.assertTrue(names)
        for name in names:
            with self.subTest(name):
                self.assertTrue(document(name).startswith('SYNTHETIC TEST DOCUMENT - FICTIONAL'))


# --- rule 2: an attributive participle compound is never an act statement ----------------------------------------

class AttributiveCompoundTests(SimpleTestCase):
    SNARE = 'A 6 mm sessile polyp in the descending colon was removed with a hot snare.'

    def test_the_compound_is_no_act_mention_and_its_participle_no_predicate(self):
        text = 'The forceps removal was not a biopsy of the snare-treated sigmoid lesion.'
        self.assertNotIn('snare', [k for k, _, _ in services._acts_in(text, 0, len(text))])
        self.assertTrue(services._attributive_compound(text, text.index('snare'), text.index('snare') + 5))
        at = text.index('treated')
        self.assertTrue(services._compound_participle(text, at))
        self.assertFalse(services._predicate_participle(text, text, 0))
        for line in ('Biopsy-proven Barrett esophagus.', 'a clip-closed defect', 'the APC-treated area',
                     'two snare-resected polyps'):
            with self.subTest(line):
                self.assertEqual(services._acts_in(line, 0, len(line)), [], line)

    def test_a_noun_after_the_hyphen_is_no_participle(self):
        for line in ('The biopsy-specimen jar was labelled.', 'The polyp was placed in the polypectomy-bed container.',
                     'The stent-lumen was patent.'):
            with self.subTest(line):
                self.assertTrue(services._acts_in(line, 0, len(line)), line)

    def test_a_predicative_compound_is_still_the_act(self):
        for line in ('The polyp was snare-resected.', 'The polyp was not snare-resected.', 'We snare-resected it.',
                     "The polyp wasn't snare-resected."):
            with self.subTest(line):
                self.assertIn('snare', [k for k, _, _ in services._acts_in(line, 0, len(line))])

    def test_the_snared_lesion_s_attribute_denies_no_snare(self):
        result = run(document('r2-attributive-positive'), [('45385', self.SNARE)])
        self.assertEqual(outcomes(result)['45385'], READY)
        inv = inventory(document('r2-attributive-positive'))
        self.assertEqual(acts(inv, 'gi.colonoscopy', 'snare', 'negated'), [])
        self.assertEqual(conflicts(inv), [])

    def test_a_biopsy_proven_diagnosis_documents_no_biopsy(self):
        text = document('r2-attributive-proven')
        inv = inventory(text)
        self.assertEqual(acts(inv, 'gi.egd', 'biopsy'), [])
        match = reconcile.match('43239', inv, 'gi.egd')
        self.assertEqual((match.state, match.reason), ('uncertain', 'act_missing'))

    def test_twin_a_predicative_compound_still_states_the_snare(self):
        quote = 'A 6 mm sessile polyp in the descending colon was snare-resected and retrieved.'
        self.assertEqual(outcomes(run(document('r2-twin-predicative'), [('45385', quote)]))['45385'], READY)
        self.assertTrue(acts(inventory(document('r2-twin-predicative')), 'gi.colonoscopy', 'snare', 'performed'))

    def test_twin_a_denied_predicative_compound_still_denies_the_snare(self):
        result = run(document('r2-twin-denied'), [('45385', self.SNARE)])
        self.assertEqual(outcomes(result)['45385'], held('conflict:snare'))
        self.assertTrue(conflicts(inventory(document('r2-twin-denied')), 'gi.colonoscopy', 'snare'))


# --- rule 7, the invariant: genuine conflicts are still held ---------------------------------------------------------

class GenuineConflictTests(SimpleTestCase):
    def test_a_blanket_denial_inside_one_service_beside_a_forceps_removal(self):
        text = HEAD + ('Colonoscopy report\nThe colonoscope was advanced to the cecum. A 3 mm polyp in the ascending colon '
                       'was removed with cold forceps. No biopsies were taken.\n')
        self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'biopsy'))
        result = run(text, [('45380', 'A 3 mm polyp in the ascending colon was removed with cold forceps.')])
        self.assertEqual(outcomes(result)['45380'], held('conflict:biopsy'))

    def test_the_same_lesion_snared_and_not_snared(self):
        text = HEAD + ('Colonoscopy report\nThe colonoscope was advanced to the cecum. A 7 mm polyp in the sigmoid colon was '
                       'removed with a cold snare.\nThe sigmoid polyp was not removed with a snare.\n')
        self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'snare'))
        result = run(text, [('45385', 'A 7 mm polyp in the sigmoid colon was removed with a cold snare.')])
        self.assertEqual(outcomes(result)['45385'], held('conflict:snare'))


# --- rule 1: lesion labels and specimen labels bind the act to the lesion, its service and its region ---------------

class LesionLabelTests(SimpleTestCase):
    CODES = [('43239', 'Cold forceps biopsies were taken from the gastric antrum'),
             ('45380', 'a 4 mm sessile polyp was removed with cold forceps and sent as specimen 2.'),
             ('45385', 'a 9 mm pedunculated polyp was removed with a hot snare and sent as specimen 3.')]

    def lesion(self, inv, size):
        return next(les for s in inv.services for les in s.lesions if les.size == size)

    def test_each_statement_binds_to_the_labelled_lesion(self):
        text = document('r1-labels-positive')
        inv = inventory(text)
        a, b = self.lesion(inv, '4 mm'), self.lesion(inv, '9 mm')
        colon = service(inv, 'gi.colonoscopy')
        self.assertEqual({a.service, b.service}, {colon.id})
        denied = {(x.kind, x.lesion) for x in acts(inv, 'gi.colonoscopy', status='negated')}
        self.assertEqual(denied, {('snare', a.id), ('biopsy', b.id)})
        self.assertEqual([(x.kind, x.lesion) for x in acts(inv, 'gi.colonoscopy', 'clip')], [('clip', b.id)])
        self.assertEqual([x.kind for x in acts(inv, 'gi.egd')], ['biopsy'])
        self.assertEqual(conflicts(inv), [])
        result = run(text, self.CODES)
        self.assertEqual(outcomes(result), {'43239': READY, '45380': READY, '45385': READY})
        self.assertEqual(bundled(result), [('gi.colonoscopy', 'clip')])

    def test_twin_a_denial_of_the_same_labelled_lesion_stays_a_conflict(self):
        text = document('r1-twin-same-lesion')
        inv = inventory(text)
        found = conflicts(inv, 'gi.colonoscopy', 'snare')
        self.assertEqual([c.lesion for c in found], [self.lesion(inv, '9 mm').id])
        self.assertEqual(outcomes(run(text, self.CODES))['45385'], held('conflict:snare'))

    def test_twin_an_ambiguous_label_binds_nothing(self):
        text = document('r1-twin-ambiguous')
        self.assertEqual(services._unique_labels(services._label_definitions(text)), frozenset())
        inv = inventory(text)
        # read as installed: the denial stays in the colonoscopy's own section, at the lesion its noun "Lesion" names
        # last there - never moved by the label to the gastric lesion it also names
        colon = service(inv, 'gi.colonoscopy')
        self.assertEqual([(x.service, x.lesion) for x in acts(inv, kind='biopsy', status='negated')],
                         [(colon.id, colon.lesions[-1].id)])
        self.assertEqual(conflicts(inv), [])

    def test_twin_an_unknown_label_reads_as_before(self):
        text = document('r1-twin-unknown-label')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'biopsy'))  # the blanket denial still pairs (rule 7)
        self.assertEqual(outcomes(run(text, [('45380', 'a 4 mm sessile polyp was removed with cold forceps.')]))['45380'],
                         held('conflict:biopsy'))

    def test_twin_a_label_over_two_lesions_resolves_to_neither(self):
        head = HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\n'
        # the definition line describes two lesions - in one clause or in two, the second with a site of its own or
        # none: which one COL-1 names is not told, so it resolves to neither, the snare it denies reads as before (no
        # lesion) and the genuine contradiction is kept
        for line in ('a 6 mm polyp was removed with a cold snare and another 3 mm polyp in the cecum was removed with '
                     'cold forceps.',
                     'a 6 mm polyp was removed with a cold snare, and a separate 3 mm polyp in the cecum was removed with '
                     'cold forceps.',
                     'a 2 mm polyp was removed with cold forceps, and a separate 5 mm polyp was removed with a cold snare.'):
            with self.subTest(line):
                inv = inventory(head + 'COL-1 - ascending colon: ' + line + '\nNo snare was used on COL-1.\n')
                self.assertEqual(len(service(inv, 'gi.colonoscopy').lesions), 2)  # never merged into one
                self.assertEqual([x.lesion for x in acts(inv, kind='snare', status='negated')], [''])
                self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'snare'))

    def test_twin_a_denial_naming_a_lesion_of_its_own_is_placed_as_before(self):
        # "No snare was used on COL-1 or the 3 mm polyp.": the clause names a lesion of its own beside the label, so the
        # label does not place it; it is placed as before (on the 3 mm polyp) and the contradiction there is kept
        text = (HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\n'
                'COL-1 - ascending colon: a 2 mm polyp was removed with cold forceps.\n'
                'COL-2 - sigmoid colon: a 3 mm polyp was removed with a cold snare.\n')
        for denial in ('No snare was used on COL-1 or the 3 mm polyp.', 'No snare was used on COL-1 or the polyp.'):
            with self.subTest(denial):
                inv = inventory(text + denial + '\n')
                three = self.lesion(inv, '3 mm')
                self.assertEqual([x.lesion for x in acts(inv, kind='snare', status='negated')], [three.id])
                self.assertEqual([c.lesion for c in conflicts(inv, 'gi.colonoscopy', 'snare')], [three.id])

    def test_a_label_alone_binds_the_denial_to_the_lesion_it_names(self):
        text = (HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\n'
                'COL-1 - ascending colon: a 2 mm polyp was removed with cold forceps.\n'
                'COL-2 - sigmoid colon: a 3 mm polyp was removed with a cold snare.\n')
        inv = inventory(text + 'No snare was used on COL-1.\n')
        self.assertEqual([x.lesion for x in acts(inv, kind='snare', status='negated')], [self.lesion(inv, '2 mm').id])
        self.assertEqual(conflicts(inv, 'gi.colonoscopy', 'snare'), [])

    def test_labels_are_exact_tokens_defined_over_a_site_or_a_lesion(self):
        defs = services._label_definitions('COL-1 - ascending colon: a 2 mm polyp\nP2: 6 mm polyp\nD2: normal\n'
                                           'Polyp  3 - rectum\nPage 2\nCOL-1\n')
        self.assertEqual(sorted(defs), ['COL-1', 'P2', 'Polyp 3'])
        index = {'COL-1': object()}
        self.assertEqual(len(services._labels_in('on COL-1.', 0, 9, index)), 1)
        for other in ('on COL-10.', 'on col-1.', 'on XCOL-1.'):
            with self.subTest(other):
                self.assertEqual(services._labels_in(other, 0, len(other), index), set())

    def test_a_specimen_reference_binds_only_a_clause_with_no_site_of_its_own(self):
        text = (HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\nA 6 mm polyp in the transverse colon '
                       'was removed with a cold snare and retrieved as specimen 3.\nA hemoclip was placed at the site of '
                       'specimen 3.\nCold forceps biopsies of the rectum were also placed in specimen 3.\n')
        inv = inventory(text)
        polyp = self.lesion(inv, '6 mm')
        self.assertEqual([x.lesion for x in acts(inv, 'gi.colonoscopy', 'clip')], [polyp.id])
        rectal = [x for x in acts(inv, 'gi.colonoscopy', 'biopsy') if 'rectum' in x.anatomy]
        self.assertEqual([x.lesion for x in rectal], [''])  # its own site places it, as before


# --- rule 4: a report title naming several services binds no single family ---------------------------------------

class CombinedTitleTests(SimpleTestCase):
    def test_a_combined_title_binds_no_family(self):
        self.assertTrue(services._names_separate_services('Upper endoscopy and colonoscopy | Outpatient professional '
                                                          'record'))
        self.assertFalse(services._names_separate_services('EGD with EUS report'))  # an examination its EUS includes
        self.assertFalse(services._names_separate_services('Colonoscopy report'))
        text = document('r4-combined-positive')
        plist = services.parts(text, service_date=day_of(text))
        title = next(p for p in plist if p.title is not None and 'Procedure Note' in p.title.text)
        self.assertEqual((title.family, title.kind, title.combined), ('', 'report', True))
        located = []
        inv = services.build(text, service_date=day_of(text), routing=detect.route(text, day_of(text)),
                             context_facts=gi_context.extract_context(text), located=located)
        in_title = {family: status for what, family, _, status, start, _ in located
                    if what == 'service' and title.title.start <= start < title.title.end}
        # the title reading stays the one service it gave it before; the other is read by its own statements
        self.assertEqual(in_title, {'gi.egd': 'performed', 'gi.colonoscopy': 'uncertain'})
        for family in ('gi.egd', 'gi.colonoscopy'):
            with self.subTest(family):
                self.assertEqual(service(inv, family).status, 'performed')

    def test_twin_a_combined_title_never_documents_a_service_the_body_does_not(self):
        head = (B + 'EGD and Colonoscopy Report\nDate of service: 10/28/2026\nEndoscopist: Synthetic MD\nSedation: propofol '
                'by CRNA\nThe gastroscope was advanced to the second part of the duodenum. Cold forceps biopsies were '
                'taken from the antrum.\n')
        excluded = ('excluded', 'excluded')
        for body, want in (('The colonoscopy was not performed because of inadequate preparation.\n', excluded),
                           ('Colonoscopy: cancelled, the patient had eaten breakfast.\n', excluded),
                           ('No colonoscopy was done today.\n', excluded),
                           ('Colonoscopy will be scheduled next week.\n', 'held'),
                           ('The colonoscope could not be passed beyond the rectum and the examination was abandoned.\n',
                            'held'), ('', 'held')):
            with self.subTest(body):
                p = outcomes(run(head + body, [('45378', 'EGD and Colonoscopy Report')]))['45378']
                if want == 'held':
                    self.assertEqual(p[:2], ('selected', 'needs_clarification'))
                    self.assertIn('performed_status', p[2])
                else:
                    self.assertEqual(p[:2], want)

    def test_a_section_s_tail_is_never_the_first_named_service_s(self):
        text = document('r4-combined-positive')
        inv = inventory(text)
        self.assertEqual([x.kind for x in acts(inv, 'gi.egd')], ['biopsy'])  # base: the colon's clip on the EGD
        egd = service(inv, 'gi.egd')
        self.assertLess(egd.scope_end, text.index('The colonoscope was advanced'))
        self.assertGreater(egd.scope_start, text.index('Gastroscopy and Colonoscopy Procedure Note'))
        result = run(text, [('43239', 'Cold forceps biopsies were taken from the gastric'),
                            ('45385', 'A 7 mm sessile polyp in the sigmoid colon was removed with a cold snare.')])
        self.assertEqual(outcomes(result), {'43239': READY, '45385': READY})
        self.assertNotIn(('gi.egd', 'clip'), bundled(result))

    def test_twin_a_site_less_denial_is_set_beside_every_service_that_documents_the_act(self):
        text = document('r4-twin-blanket-denial')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'))
        result = run(text, [('43239', 'Cold forceps biopsies were obtained from the gastric'),
                            ('45385', 'A 7 mm polyp in the transverse colon was removed with a cold snare.')])
        self.assertEqual(outcomes(result)['43239'], held('conflict:biopsy'))

    def test_twin_r1_probe_8c_a_combined_report_with_an_unheaded_narrative_keeps_its_conflict(self):
        text = (HEAD + 'EGD and colonoscopy report\nThe gastroscope was advanced to the second part of the duodenum. Cold '
                       'forceps biopsies were taken from the gastric antrum. The colonoscope was advanced to the cecum. A '
                       '6 mm polyp in the transverse colon was removed with a cold snare.\nNo biopsies were taken.\n')
        self.assertTrue(conflicts(inventory(text), 'gi.egd', 'biopsy'))
        result = run(text, [('43239', 'Cold forceps biopsies were taken from the gastric antrum.')])
        self.assertEqual(outcomes(result)['43239'], held('conflict:biopsy'))


# --- rule 3: a copular negation negates only its predicate nominal, at its object ---------------------------------

class CopularNegationTests(SimpleTestCase):
    SNARE = 'A 10 mm polyp in the descending colon was removed en bloc with a hot snare.'

    def test_the_subject_and_the_object_state_no_act(self):
        text = document('r3-copular-positive')
        inv = inventory(text)
        self.assertEqual(acts(inv, 'gi.colonoscopy', 'snare', 'negated'), [])
        snared = next(les for les in service(inv, 'gi.colonoscopy').lesions if les.size == '10 mm')
        self.assertEqual([x.lesion for x in acts(inv, 'gi.colonoscopy', 'biopsy', 'negated')], [snared.id])
        self.assertEqual(conflicts(inv), [])
        result = run(text, [('45380', 'A 5 mm sessile polyp in the hepatic flexure was removed with cold forceps.'),
                            ('45385', self.SNARE)])
        self.assertEqual(outcomes(result), {'45380': READY, '45385': READY})

    def test_twin_verbal_negation_still_denies_the_act(self):
        text = document('r3-twin-verbal')
        self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'snare'))
        self.assertEqual(outcomes(run(text, [('45385', self.SNARE)]))['45385'], held('conflict:snare'))

    def test_twin_the_nominal_itself_is_still_denied(self):
        text = document('r3-twin-existential')
        self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'biopsy'))
        self.assertEqual(outcomes(run(text, [('45380', 'Cold forceps biopsies were taken from the cecum.')]))['45380'],
                         held('conflict:biopsy'))

    def test_twin_another_negation_in_the_clause_reads_as_before(self):
        text = HEAD + ('Colonoscopy report\nThe colonoscope was advanced to the cecum. A 6 mm polyp in the sigmoid colon was '
                       'removed with a cold snare.\nThe sigmoid polyp, which was not a large one, was not removed with a '
                       'snare.\n')
        self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'snare'))

    def test_another_occurrence_is_never_performance_evidence(self):
        text = HEAD + ('EGD report\nThe gastroscope was advanced to the second part of the duodenum.\nAn outside endoscopy '
                       'in 2024 was a prior service, not a second upper endoscopy today.\n')
        located = []
        inv = services.build(text, service_date=day_of(text), routing=detect.route(text, day_of(text)),
                             context_facts=gi_context.extract_context(text), located=located)
        second = text.index('upper endoscopy today')
        self.assertEqual([status for what, _, _, status, start, _ in located if start == second], ['uncertain'])
        self.assertEqual(service(inv, 'gi.egd').status, 'performed')  # its own report still documents it

    def test_not_a_repeat_act_denies_only_another_occurrence(self):
        text = HEAD + ('Colonoscopy report\nThe colonoscope was advanced to the cecum. Cold forceps biopsies were taken from '
                       'the ascending colon. This was not a repeat biopsy of the earlier site.\n')
        self.assertEqual(conflicts(inventory(text)), [])


# --- the A1 must-stay shapes (pi.json PI-A1-HEADING-LAPSE-REBINDS); rule 5 is out of this change (decision (c))

class HeadingLapseShapeTests(SimpleTestCase):
    """pi.json PI-A1-HEADING-LAPSE-REBINDS (tests/test_gi4_pi.py DroppedA1Tests, read again here): after a sub-heading
    the unsited snare binds to neither service, and the base codes stay READY."""
    HEAD = (B + 'Gastroscopy and Colonoscopy\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol '
            'by CRNA\n\nFindings\n')
    FORWARD = ('The colonoscope was advanced to the cecum. The colon was normal.\nThe gastroscope was advanced to the '
               'second part of the duodenum. A 12 mm polyp was seen in the gastric body. {aside}\n{heading}\nA hot snare '
               'was used to remove the polyp.\n')
    REVERSE = ('The gastroscope was advanced to the second part of the duodenum. The stomach was normal.\nThe colonoscope '
               'was advanced to the cecum. A 7 mm polyp was seen in the transverse colon. The gastroscopy had been done '
               'first, under the same sedation.\n{heading}\nA hot snare was used to remove the polyp.\n')
    SNARE = 'A hot snare was used to remove the polyp.'
    HEADINGS = ('Polypectomy', 'Intervention', 'Treatment', 'Removal', 'Therapeutic Intervention', 'Polyp Removal',
                'Snare Polypectomy')
    ASIDES = ('The colonoscopy had been done first, under the same sedation.',
              'It looked similar to the polyps found at the colonoscopy just completed.',
              'Colonoscopy findings are listed above.')

    def snares(self, text):
        return [(s.family, a.status) for s in inventory(text).services for a in s.acts if a.kind == 'snare']

    def test_the_gastric_snare_is_never_the_colonoscopy_s(self):
        for heading in self.HEADINGS:
            for aside in self.ASIDES:
                with self.subTest(heading=heading, aside=aside):
                    text = self.HEAD + self.FORWARD.format(aside=aside, heading=heading)
                    self.assertEqual(self.snares(text), [])
                    result = run(text, [('45378', 'The colonoscope was advanced to the cecum.'), ('43251', self.SNARE)])
                    self.assertEqual(outcomes(result)['45378'], READY)

    def test_the_colonic_snare_is_never_the_upper_endoscopy_s(self):
        for heading in self.HEADINGS:
            with self.subTest(heading):
                text = self.HEAD + self.REVERSE.format(heading=heading)
                self.assertEqual(self.snares(text), [])
                result = run(text, [('43235', 'The gastroscope was advanced to the second part of the duodenum.'),
                                    ('45385', self.SNARE)])
                self.assertEqual(outcomes(result)['43235'], READY)


# --- rule 8: an explicit statement that no separate office E/M service is documented -------------------------------

class EmAbsenceTests(SimpleTestCase):
    BIOPSY = [('43239', 'Cold forceps biopsies were taken from the gastric antrum.')]

    def test_the_shared_pattern(self):
        for line in ('No separate office evaluation and management encounter or office-visit time is documented on this '
                     'date.', 'No separately identifiable office visit or outpatient evaluation and management service '
                     'was provided on this date.', 'Evaluation and management was not provided.',
                     'No record of a separate office visit is documented.', 'No separate clinic visit occurred today.'):
            with self.subTest(line):
                self.assertIsNotNone(cues.EM_ABSENCE.search(line))
        for line in ('Office visit not billed separately.', 'The office visit was not separately billable.',
                     'The office visit was not separately reported.', 'An office visit was also completed today.',
                     'No biopsies were taken and an office visit was documented.', 'No separate cyst-management visit '
                     'occurred today.',
                     # round-2 repair (L2/F07; tests/test_cux_r2_em.py): a hedge, and a negator of another noun
                     'The office visit is not documented here; it is documented in the clinic note of today.',
                     "No medication changes at today's office visit were documented."):
            with self.subTest(line):
                self.assertIsNone(cues.EM_ABSENCE.search(line))

    def test_the_statement_negates_the_visit_for_both_readers(self):
        for name in ('r8-em-absent-positive', 'r8-em-absent-post'):
            with self.subTest(name):
                text = document(name)
                finding = detect.route(text, day_of(text)).finding('gi.office_em')
                self.assertEqual(finding.status, 'negated')
                self.assertTrue(all(detect.EM_ABSENT_CUE in m.cues for m in finding.mentions))
                em = service(inventory(text), 'gi.office_em')
                self.assertEqual(em.status, 'negated')
                self.assertIn(services.EM_ABSENT_SERVICE_CUE, em.cues)
                result = run(text, self.BIOPSY)
                self.assertEqual(em_questions(result), set())
                self.assertEqual(outcomes(result)['43239'], READY)

    def test_twin_an_affirmative_statement_elsewhere_still_asks(self):
        text = document('r8-twin-contradiction')
        finding = detect.route(text, day_of(text)).finding('gi.office_em')
        self.assertEqual(finding.status, 'uncertain')
        self.assertTrue(any(detect.EM_ABSENT_CONTRADICTED in m.cues for m in finding.mentions))
        self.assertEqual(service(inventory(text), 'gi.office_em').status, 'uncertain')
        self.assertEqual(em_questions(run(text, self.BIOPSY)), {'patient_status', 'em_basis'})

    def test_twin_a_billing_wording_reads_as_before(self):
        text = document('r8-twin-billing')
        finding = detect.route(text, day_of(text)).finding('gi.office_em')
        self.assertEqual(finding.status, 'uncertain')
        self.assertTrue(all(detect.EM_WITHOUT_BASIS in m.cues for m in finding.mentions))
        self.assertEqual(service(inventory(text), 'gi.office_em').status, 'uncertain')
        # with an E/M code to decide, the visit is held as before (never excluded, never ready)
        result = run(text, self.BIOPSY + [('99213', 'The office visit was not billed separately.')])
        self.assertEqual(outcomes(result)['99213'][:2], ('selected', 'needs_clarification'))

    def test_another_date_in_the_sentence_reads_as_before(self):
        text = HEAD + ('EGD report\nThe gastroscope was advanced to the second part of the duodenum.\nEvaluation and '
                       'management was not provided on 2026-09-01.\n')
        finding = detect.route(text, day_of(text)).finding('gi.office_em')
        self.assertNotIn(detect.EM_ABSENT_CUE, [c for m in finding.mentions for c in m.cues])


# --- decision (b) of 2026-11-03: E/M questions are removed at the reader only, never by a validation-side gate ---------

class EmQuestionsStayForAStatedVisitTests(SimpleTestCase):
    """The completeness critique's counterexample: a separate visit the note states ("An office visit was also completed
    today.") beside a procedure, with no time or decision-making documented, still asks its E/M questions - no
    validation-side suppression hides them (only an explicit "no separate E/M ... documented" statement does, at the
    reader)."""

    TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
            'Procedure report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
            'Procedure: EGD\nThe gastroscope was advanced to the second portion of the duodenum.\n'
            'Cold forceps biopsies were taken from the gastric antrum.\n'
            'An office visit was also completed today.\n')

    def test_a_stated_visit_with_no_basis_still_asks(self):
        result = run(self.TEXT, [('43239', 'Cold forceps biopsies were taken from the gastric antrum.')])
        self.assertTrue(em_questions(result) & EM_QUESTIONS, em_questions(result))


# --- Mara, end to end, with the retained provider response (design section 10's acceptance) ------------------------

class MaraEndToEndTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.text = (MARA / 'rev1.txt').read_text(encoding='utf-8')
        cls.readme = json.loads((MARA / 'README.json').read_text(encoding='utf-8'))
        starts = [i for i in range(len(cls.text)) if cls.text.startswith('SYNTHETIC TEST CASE - ALL PEOPLE', i)]
        # the revision's pages, at its repeated letterhead, joined by the extraction's two newlines
        cls.pages = tuple(PageSpan(n + 1, s, (starts[n + 1] - 2) if n + 1 < len(starts) else len(cls.text))
                          for n, s in enumerate(starts))

    def response(self):
        body = (MARA / 'corti-response.json').read_bytes()
        self.assertEqual(hashlib.sha256(body).hexdigest(), self.readme['corti_response_sha256'])
        request = corti.build_coding_request('corti', corti.ADAPTER_VERSION, self.text, date(2026, 11, 3),
                                             corti.DEFAULT_MAX_REQUEST_BYTES)
        self.assertEqual(request.canonical_sha256, self.readme['corti_request_sha256'])
        return corti.normalize_coding_response('corti', request, body)

    def test_the_fixture_is_the_retained_revision(self):
        self.assertEqual(hashlib.sha256(self.text.encode('utf-8')).hexdigest(), self.readme['revision_text_sha256'])
        self.assertEqual(len(self.pages), 3)

    def test_the_acceptance(self):
        for label, pages in (('the revision pages', self.pages), ('one page', None), ('no pages', ())):
            with self.subTest(label):
                result = run(self.text, normalized=self.response(), pages=pages)
                self.assertEqual(outcomes(result), {'43239': READY, '45380': READY, '45385': READY})
                self.assertEqual(sum(len(p.clarifications) for p in result.proposals), 0)
                self.assertEqual(em_questions(result), set())
                self.assertEqual(result.services['conflicts'], [])
                self.assertEqual(bundled(result), [('gi.colonoscopy', 'clip')])
                for code in ('45380', '45385'):
                    p = next(x for x in result.proposals if x.code == code and x.bucket == 'selected')
                    self.assertTrue(any('59 or XS' in m for m in p.modifier_considerations), code)

    def test_the_bindings(self):
        inv = inventory(self.text, self.pages)
        colon, egd = service(inv, 'gi.colonoscopy'), service(inv, 'gi.egd')
        by_size = {les.size: les.id for les in colon.lesions}
        self.assertEqual(sorted(by_size), ['2 mm', '8 mm'])  # the specimen table restates them: no new lesions
        self.assertEqual({(a.kind, a.status, a.lesion) for a in colon.acts if a.lesion},
                         {('biopsy', 'performed', by_size['2 mm']), ('snare', 'negated', by_size['2 mm']),
                          ('snare', 'performed', by_size['8 mm']), ('biopsy', 'negated', by_size['8 mm']),
                          ('clip', 'performed', by_size['8 mm'])})
        # Completion repair (2026-11-06, U13; builder A): "from the proximal and distal esophagus" reads both sites, in
        # the order written (the coordinated modifier shares the head), where the base had read the distal one only
        self.assertEqual({a.anatomy[0] if a.anatomy else '' for a in egd.acts if a.kind == 'biopsy'},
                         {'proximal esophagus', 'gastric antrum and body', 'duodenum'})
        self.assertIn(('proximal esophagus', 'distal esophagus'),
                      [tuple(a.anatomy) for a in egd.acts if a.kind == 'biopsy'])
        self.assertNotIn('clip', [a.kind for a in egd.acts])
        self.assertLess(egd.scope_end, self.text.index('COLONOSCOPY - PERFORMED TODAY') + 1)
        self.assertEqual(service(inv, 'gi.office_em').status, 'negated')
