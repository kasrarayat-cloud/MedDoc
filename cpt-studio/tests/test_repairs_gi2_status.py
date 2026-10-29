"""GI round 2 (session 7c8d38da), fix round "status": the refutation lens "status" found four places where the round's
conflict-pairing repair (studio/gi/services.py, repair "conflicts") lost or invented a conflict the installed reader
read correctly. Each is narrowed back toward the installed reading here, while the round's intended changes (ho-01's
tattoo conflict, ho-07's and ho-10's removed false conflicts) stay as they are.

status-1 - a site denial is another subject from an act at a lesion only when the act's sentence names that lesion as
its own (by its size, its site or its own noun). "The lesion" that falls back to an earlier lesion in another region (a
rectal mass the reader does not record as a lesion) pairs as the installed reader paired it.

status-2 - regions are not a partition: the small bowel holds the duodenum, the duodenum holds the papilla, and the
large bowel holds the colon and the rectum. A denial whose site holds the act's site (or lies inside it) is about it;
only disjoint sites are different subjects.

status-3 - in a nurse's denying answer with a note, a negation governs its own clause: a later clause that states the
item's own act done, by whoever did it ("No - not by nursing; placed by the physician"), makes the answer no denial. A
note that only explains the denial ("none used", "not indicated", another act named) stays a denial.

status-5 - a checklist whose heading names one documented service ("Nursing checklist - colonoscopy") is about that
service: its denials are set beside that service only, never beside another service's acts.

Every text is a fresh synthetic paraphrase written for these tests; the expected readings are written here, outside the
reader, from the documents' own wording.
"""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation.engine import assess

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'


def _day(text):
    fact = gi_context.extract_context(text).get('service_date')
    return date.fromisoformat(fact.value) if fact is not None and fact.origin == 'document' and fact.value else None


def inventory(text):
    day = _day(text)
    return services.build(text, service_date=day, routing=detect.route(text, day),
                          context_facts=gi_context.extract_context(text))


def conflicts(inv, family, subject=None):
    ids = {s.id for s in inv.for_family(family)}
    return [c for c in inv.conflicts if c.service in ids and (subject is None or c.subject == subject)]


def acts(inv, family, kind, status=None, role=None):
    return [a for s in inv.for_family(family) for a in s.acts if a.kind == kind
            and (status is None or a.status == status) and (role is None or a.role == role)]


def span(text, phrase):
    start = text.index(phrase)
    return EvidenceSpan(0, start, start + len(phrase), phrase, True)


def run(text, codes):
    facts = gi_context.extract_context(text)
    day = _day(text)
    response = NormalizedResponse('replay', 'test@1', tuple(codes))
    return assess(text=text, pages=(), context=facts, routing=detect.route(text, day), normalized=response,
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def sel(code, *spans):
    return ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING', tuple(spans))


def proposal(result, code):
    found = [p for p in result.proposals if p.code == code and p.bucket != 'alternative']
    assert found, f'{code} not in {[p.code for p in result.proposals]}'
    return found[0]


def asked(result, item):
    return {c.fact for c in item.clarifications} | {c.fact for c in result.clarifications}


# --- status-1: an act at a lesion its sentence does not name as its own -------------------------------------------

def lower(findings, impression, procedure='Procedure: Colonoscopy.'):
    return (HEAD + 'Colonoscopy Report\nDate of service: 2026-10-15\n' + procedure + '\n\nTechnique\nThe colonoscope was '
            'passed to the cecum and the ileocecal valve was seen.\n\nFindings\n' + findings + '\n\nImpression\n'
            + impression + '\n')


def upper_report(findings, impression, procedure='Procedure: EGD.'):
    return (HEAD + 'Upper Endoscopy Report\nDate of service: 2026-10-15\n' + procedure + '\n\nTechnique\nThe gastroscope '
            'was passed to the second portion of the duodenum.\n\nFindings\n' + findings + '\n\nImpression\n'
            + impression + '\n')


# lesion phrasings the lesion reader does not record (a description word it does not list), so "the lesion" after them
# falls back to the polyp recorded before
UNRECORDED = ('a 4 cm circumferential mass', 'a 30 mm friable, fungating mass', 'a 2 cm nodular lesion',
              'a 25 mm firm, ulcerated lesion')


class LesionFallbackTests(SimpleTestCase):
    def test_a_tattoo_at_the_lesion_the_rectum_denial_names_stays_a_conflict(self):
        # "The lesion" is the rectal mass of its own item; the impression denies a tattoo in the rectum: the same act at
        # the same site, stated done and not done
        for mass in UNRECORDED:
            with self.subTest(mass=mass):
                text = lower('1. Ascending colon: a 9 mm sessile polyp, resected with a cold snare.\n'
                             f'2. Rectum at 6 cm: {mass}. The lesion was marked with India ink 2 cm distal to it.',
                             'No tattoo was placed in the rectum.')
                self.assertTrue(conflicts(inventory(text), 'gi.colonoscopy', 'tattoo'), inventory(text).conflicts)

    def test_the_tattoo_code_is_held_for_that_conflict(self):
        text = lower('1. Ascending colon: a 9 mm sessile polyp, resected with a cold snare.\n'
                     '2. Rectum at 6 cm: a 4 cm circumferential mass. The lesion was marked with India ink 2 cm distal '
                     'to it.', 'No tattoo was placed in the rectum.')
        result = run(text, [sel('45381', span(text, 'The lesion was marked with India ink 2 cm distal to it.'))])
        item = proposal(result, '45381')
        self.assertEqual(item.status, 'needs_clarification')
        self.assertIn('conflict:tattoo', asked(result, item))

    def test_a_biopsy_of_the_lesion_the_rectal_denial_names_stays_a_conflict(self):
        for mass in UNRECORDED:
            with self.subTest(mass=mass):
                text = lower('1. Ascending colon: a 9 mm sessile polyp, resected with a cold snare.\n'
                             f'2. Rectum at 6 cm: {mass}. Cold forceps biopsies of the lesion were obtained.',
                             'No rectal biopsies were obtained.')
                inv = inventory(text)
                self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'biopsy'), inv.conflicts)
                result = run(text, [sel('45380', span(text, 'Cold forceps biopsies of the lesion were obtained.'))])
                self.assertIn('conflict:biopsy', asked(result, proposal(result, '45380')))

    def test_the_same_noun_after_a_lesion_the_reader_does_not_record_stays_a_conflict(self):
        # "The polyp" is the rectal polyp just described (with a description word the lesion reader does not list), not
        # the ascending colon polyp recorded before it
        text = lower('1. Ascending colon: a 9 mm sessile polyp, resected with a cold snare.\n'
                     '2. Rectum at 6 cm: a flat, granular polyp. The polyp was marked with India ink 2 cm distal to it.',
                     'No tattoo was placed in the rectum.')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)

    def test_a_pronoun_after_a_lesion_the_reader_does_not_record_stays_a_conflict(self):
        text = lower('1. Ascending colon: a 9 mm sessile polyp, resected with a cold snare.\n'
                     '2. Rectum at 6 cm: a 4 cm circumferential mass. It was marked with India ink 2 cm distal to it.',
                     'No tattoo was placed in the rectum.')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)

    def test_the_same_fall_back_in_an_upper_endoscopy(self):
        text = upper_report('1. Gastric antrum: a 6 mm sessile polyp, removed with a cold snare.\n'
                            '2. Duodenal bulb: a 2 cm nodular lesion. Cold forceps biopsies of the lesion were taken.',
                            'No duodenal biopsies were taken.')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_an_act_at_a_lesion_its_sentence_names_by_size_is_still_at_that_site(self):
        # "The 9 mm polyp" is the ascending colon polyp: a snare denial scoped to the rectum is about another site
        text = lower('1. Ascending colon: a 9 mm sessile polyp.\n2. Rectum: the mucosa was normal.\n'
                     'The 9 mm polyp was resected with a cold snare.',
                     'No snare polypectomy was performed in the rectum.')
        inv = inventory(text)
        self.assertTrue(acts(inv, 'gi.colonoscopy', 'snare', 'performed'))
        self.assertFalse(conflicts(inv, 'gi.colonoscopy', 'snare'), inv.conflicts)

    def test_an_act_at_a_lesion_its_sentence_names_by_its_own_noun_is_still_at_that_site(self):
        # the ho-07 shape in other words: "the stricture" is the bile duct stricture, and the pancreatic stent denial is
        # about another site
        text = (HEAD + 'ERCP Report\nDate of service: 2026-10-15\nProcedure: ERCP with stricture dilation and biliary '
                'stent placement.\nFindings\nThe cholangiogram showed a 2 cm stricture of the mid common bile duct. '
                'Deep cannulation of the bile duct was achieved. The stricture was dilated to 6 mm with a balloon. '
                'A 10 mm fully covered metal stent was then deployed across the stricture with good drainage. '
                'A pancreatic duct stent was not placed.\n')
        inv = inventory(text)
        self.assertTrue(acts(inv, 'gi.ercp', 'stent', 'performed'))
        self.assertFalse(conflicts(inv, 'gi.ercp', 'stent'), inv.conflicts)


# --- status-2: a denial whose site holds the act's site ----------------------------------------------------------

def upper(procedure, *sentences):
    return (HEAD + 'Upper Endoscopy Report\nDate of service: 2026-10-15\n' + procedure + '\nFindings\nThe gastroscope '
            'was passed to the second portion of the duodenum. ' + ' '.join(sentences) + '\n')


def colon(procedure, *sentences):
    return (HEAD + 'Colonoscopy Report\nDate of service: 2026-10-15\n' + procedure + '\nFindings\nThe colonoscope was '
            'passed to the cecum. ' + ' '.join(sentences) + '\n')


UPPER_SUMMARY = 'Procedure: EGD with cold forceps biopsies.'
LOWER_SUMMARY = 'Procedure: Colonoscopy with cold forceps biopsies.'


class ContainedSiteTests(SimpleTestCase):
    def test_a_small_bowel_denial_holds_the_duodenum(self):
        for denial in ('No small bowel biopsies were obtained.', 'No biopsies of the small intestine were taken.'):
            with self.subTest(denial=denial):
                text = upper(UPPER_SUMMARY, 'Biopsies of the second portion of the duodenum were obtained for '
                                            'celiac disease.', denial)
                inv = inventory(text)
                self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)
                result = run(text, [sel('43239', span(text, UPPER_SUMMARY))])
                self.assertIn('conflict:biopsy', asked(result, proposal(result, '43239')))

    def test_a_large_bowel_denial_holds_the_rectum(self):
        for denial in ('No large bowel biopsies were obtained.', 'No biopsies of the large intestine were taken.'):
            with self.subTest(denial=denial):
                text = colon(LOWER_SUMMARY, 'Rectal biopsies were obtained.', denial)
                inv = inventory(text)
                self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'biopsy'), inv.conflicts)
                result = run(text, [sel('45380', span(text, LOWER_SUMMARY))])
                self.assertIn('conflict:biopsy', asked(result, proposal(result, '45380')))

    def test_a_duodenal_denial_holds_the_papilla(self):
        # the major papilla is in the wall of the second part of the duodenum
        text = upper(UPPER_SUMMARY, 'The major papilla looked bulky and biopsies of the papilla were taken.',
                     'No duodenal biopsies were taken.')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_an_act_at_the_holding_site_pairs_with_the_held_site_s_denial(self):
        # "small bowel biopsies" in an EGD may be the duodenal ones the denial names
        text = upper(UPPER_SUMMARY, 'Small bowel biopsies were taken.', 'No duodenal biopsies were taken.')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_disjoint_sites_stay_different_subjects(self):
        # each pair names sites with nothing in common: the summary is about the documented biopsies, not the denied
        # site (the installed reader paired these; the round's repair separates them and that is kept)
        for make, summary, done, denial, family in (
                (colon, LOWER_SUMMARY, 'Biopsies of the terminal ileum were obtained.',
                 'No colon biopsies were obtained.', 'gi.colonoscopy'),
                (colon, LOWER_SUMMARY, 'Rectal biopsies were obtained.', 'No colon biopsies were obtained.',
                 'gi.colonoscopy'),
                (colon, LOWER_SUMMARY, 'Biopsies of the anal canal were obtained.', 'No rectal biopsies were obtained.',
                 'gi.colonoscopy'),
                (upper, UPPER_SUMMARY, 'Biopsies of the gastric cardia were taken.',
                 'No esophageal biopsies were taken.', 'gi.egd'),
                (upper, UPPER_SUMMARY, 'Biopsies of the duodenal bulb were taken.',
                 'No biopsies of the papilla were taken.', 'gi.egd'),
                (upper, UPPER_SUMMARY, 'Biopsies were taken from the mid esophagus.',
                 'No gastric or duodenal biopsies were taken.', 'gi.egd')):
            with self.subTest(done=done, denial=denial):
                inv = inventory(make(summary, done, denial))
                self.assertFalse(conflicts(inv, family, 'biopsy'), inv.conflicts)


# --- status-3: a note's later clause that states the act done ------------------------------------------------------

PHYSICIAN_TATTOO = 'A submucosal tattoo was placed 2 cm distal to the polypectomy site.'


def checklist(physician, row):
    return (HEAD + 'Colonoscopy Report\nDate of service: 2026-10-15\nProcedure: Colonoscopy.\n\nFindings\nThe '
            'colonoscope was passed to the cecum. ' + physician + '\n\nNursing Intraprocedure Checklist\n'
            'Checklist item | Nursing entry\nTime-out completed | Yes\n' + row + '\n')


WITH_TATTOO = 'A 15 mm polyp in the descending colon was resected with a hot snare. ' + PHYSICIAN_TATTOO
# (A note whose negated clause has a predicate of its own - "No - the nurse did not inject; the physician injected
# Spot" - is denied by that clause's own words, not by the note grammar, on the installed reader too: not read here.)
AFFIRMING = ('No - not by nursing; placed by the physician', 'No (not by the RN) - injected by the fellow',
             'No - none by nursing, the attending injected India ink', 'No, not by nursing staff; tattoo placed by MD',
             'No - not charted here, see MD note: tattoo injected', 'No - not by nursing but placed by the physician')
EXPLAINING = ('No - none used', 'No - not indicated', 'No - none placed; the lesion was completely removed',
              'No - none used; biopsies only', 'No, not placed - the polyp was removed whole')


class NoteClauseTests(SimpleTestCase):
    def test_a_later_clause_that_states_the_act_done_is_no_denial(self):
        for note in AFFIRMING:
            for sep in (' | ', ': '):
                with self.subTest(note=note, sep=sep):
                    inv = inventory(checklist(WITH_TATTOO, 'Tattoo or marking agent injected' + sep + note))
                    self.assertFalse(acts(inv, 'gi.colonoscopy', 'tattoo', 'negated', 'nursing'))
                    self.assertFalse(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)

    def test_the_physician_tattoo_code_is_not_held_for_a_conflict(self):
        row = 'Tattoo or marking agent injected | No - not by nursing; placed by the physician'
        text = checklist(WITH_TATTOO, row)
        result = run(text, [sel('45381', span(text, PHYSICIAN_TATTOO))])
        item = proposal(result, '45381')
        self.assertNotIn('conflict:tattoo', asked(result, item))
        self.assertNotEqual(item.support.get('reason'), 'conflict', item.support)

    def test_word_order_does_not_decide(self):
        # the same note with its negation last reads the same: neither is a nursing denial
        for first, last in (('No - not by nursing; placed by the physician', 'No - placed by the physician, not by '
                                                                            'nursing'),
                            ('No (not by the RN) - injected by the fellow', 'No - injected by the fellow (not by the '
                                                                            'RN)')):
            with self.subTest(first=first):
                readings = []
                for note in (first, last):
                    inv = inventory(checklist('The mucosa was normal.', 'Tattoo or marking agent injected | ' + note))
                    readings.append(sorted((a.status, a.role) for a in acts(inv, 'gi.colonoscopy', 'tattoo')))
                self.assertEqual(readings[0], readings[1])
                self.assertNotIn(('negated', 'nursing'), readings[0])

    def test_a_note_that_only_explains_the_denial_stays_a_denial(self):
        for note in EXPLAINING:
            for sep in (' | ', ': '):
                with self.subTest(note=note, sep=sep):
                    inv = inventory(checklist(WITH_TATTOO, 'Tattoo or marking agent injected' + sep + note))
                    self.assertTrue(acts(inv, 'gi.colonoscopy', 'tattoo', 'negated', 'nursing'))
                    self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)


# --- status-5: a checklist whose heading names one service ---------------------------------------------------------

EGD_BIOPSY = 'Cold forceps biopsies were obtained from the gastric body.'
COLON_BIOPSY = 'Cold forceps biopsies were obtained from the transverse colon.'


def two_services(heading, row, colon_biopsy=False):
    return (HEAD + 'Combined Endoscopy Record\nDate of service: 2026-10-15\n\nUpper Endoscopy\nThe gastroscope was passed '
            'to the second portion of the duodenum. ' + EGD_BIOPSY + '\n\nColonoscopy\nThe colonoscope was passed to '
            'the cecum. ' + (COLON_BIOPSY if colon_biopsy else 'The colonic mucosa was normal and no polyps were seen.')
            + '\n\n' + heading + '\nChecklist item | Nursing entry\nTime-out completed | Yes\n' + row + '\n')


NAMED_COLONOSCOPY = ('Nursing checklist - colonoscopy', 'Nursing Intraprocedure Checklist (colonoscopy)',
                     'Nursing record: colonoscopy', 'Procedure checklist for colonoscopy')


class NamedChecklistTests(SimpleTestCase):
    def test_a_colonoscopy_checklist_says_nothing_about_the_egd_biopsies(self):
        for heading in NAMED_COLONOSCOPY:
            for row in ('Biopsy taken | No', 'Biopsy taken: No', 'Biopsies obtained | None'):
                with self.subTest(heading=heading, row=row):
                    text = two_services(heading, row)
                    inv = inventory(text)
                    self.assertFalse(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)
                    result = run(text, [sel('43239', span(text, EGD_BIOPSY))])
                    self.assertNotIn('conflict:biopsy', asked(result, proposal(result, '43239')))

    def test_its_denial_is_still_the_colonoscopy_s(self):
        # the colonoscopy documents a biopsy too: the nurse's "No" contradicts that one, never the EGD's
        text = two_services('Nursing checklist - colonoscopy', 'Biopsy taken | No', colon_biopsy=True)
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'biopsy'), inv.conflicts)
        self.assertFalse(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_a_checklist_naming_the_upper_endoscopy_pairs_with_its_biopsies(self):
        inv = inventory(two_services('Nursing checklist - upper endoscopy', 'Biopsy taken | No'))
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_a_checklist_naming_no_service_is_still_the_encounter_s(self):
        # nothing says which service the nurse meant: the denial is set beside each service documenting a biopsy
        inv = inventory(two_services('Nursing Intraprocedure Checklist', 'Biopsy taken | No'))
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_the_inventory_stays_internally_consistent(self):
        for heading in NAMED_COLONOSCOPY:
            text = two_services(heading, 'Biopsy taken | No', colon_biopsy=True)
            self.assertEqual(services.validate(inventory(text), text), ())
