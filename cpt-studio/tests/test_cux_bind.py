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
