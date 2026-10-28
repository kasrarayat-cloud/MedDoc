"""GI round 2 (session 7c8d38da), repair "conflicts": which statements of an act the documented-service reader pairs
as a conflict (studio/gi/services.py).

PR2 - a row of a two-column table ("<label> | <entry>", the DOCX reader's one line per row) is a form field: its entry
cell, never a participle in its label, says whether the act its label names was done, and it says so for that row only.
A denying entry ("No", "None", "Not done", "No - none used") denies the act with the role of the part it stands in
(a nursing checklist), so the physician's statement of the act and the nurse's denial are kept as one conflict. A
denial that names no service and no site in a record of several services is set beside the service that documents
that act done, never dropped.

PR1 - a denial scoped to sites: an act stated at a lesion is at that lesion's site, so a denial of another region
("No pancreatic stent was placed") is not about it; a summary of the procedure that names no site ("EGD with ...
biopsies") is about the documented acts at another region, not the denied sites, when there are such acts. Same-site
statements still pair, and a summary with nothing else to be about still pairs (genuine uncertainty is kept).

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


def sides(conflict):
    return {(side.role, side.status) for side in conflict.sides}


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


def facts_asked(item):
    return {c.fact for c in item.clarifications}


# --- PR2: a two-column checklist table ---------------------------------------------------------------------------

def bidirectional(rows):
    """An upper endoscopy and a colonoscopy in one record, the tattoo stated by the physician at the colon mass, and a
    nursing checklist table with ``rows`` (each "<item> | <entry>")."""
    return (HEAD + 'Combined Endoscopy Record\nDate of procedure: 2026-10-14\n'
            'Procedures: Upper endoscopy with biopsies; colonoscopy with cold snare polypectomy, biopsies of a mass '
            'and submucosal tattoo.\n\n'
            'Upper Endoscopy\nThe gastroscope was advanced to the second portion of the duodenum. Cold forceps '
            'biopsies were taken from the gastric antrum for Helicobacter pylori (container 1).\n\n'
            'Colonoscopy\nThe colonoscope was advanced to the cecum and the ileocecal valve was identified.\n'
            '1. Hepatic flexure: an 8 mm sessile polyp was removed with a cold snare (container 2).\n'
            '2. Descending colon at 45 cm: a separate 30 mm ulcerated mass, not resected. Cold forceps biopsies were '
            'taken from its margin (container 3). A submucosal tattoo of carbon particle suspension was injected 2 cm '
            'distal to the mass in two quadrants.\n\n'
            'Nursing Intraprocedure Checklist\n'
            'Entries recorded by the procedure nurse, Pat Fictional, RN, at 10:05:\n'
            'Checklist item | Nursing entry\n' + '\n'.join(rows) + '\n\n'
            'Impression\n1. Antral erythema; biopsies for Helicobacter pylori.\n2. Hepatic flexure polyp removed.\n'
            '3. Descending colon mass, biopsied and tattooed.\n')


ROWS = ['Time-out completed | Yes', 'Upper endoscopy biopsies | Yes, 1 container',
        'Snare polypectomy | Yes, hepatic flexure', 'Colon biopsies | Yes, descending colon',
        'Tattoo or marking agent injected | No - none used', 'Specimen containers sent | 3']


class ChecklistTableTests(SimpleTestCase):
    def test_a_nursing_table_denial_of_the_tattoo_is_kept_as_a_conflict(self):
        inv = inventory(bidirectional(ROWS))
        found = conflicts(inv, 'gi.colonoscopy', 'tattoo')
        self.assertTrue(found, inv.conflicts)
        for conflict in found:
            self.assertIn(('physician', 'performed'), sides(conflict))
            self.assertIn(('nursing', 'negated'), sides(conflict))
        # the nurse's entry is a denial of the act its label names, never a done tattoo read from "injected"
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'tattoo', 'performed', 'nursing'))
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'injection', 'performed', 'nursing'))
        # the upper endoscopy documents no tattoo: no denial is set beside it
        self.assertFalse(conflicts(inv, 'gi.egd'))
        self.assertFalse(acts(inv, 'gi.egd', 'tattoo'))
        # only the tattoo is in conflict
        self.assertEqual({c.subject for c in inv.conflicts}, {'tattoo'}, inv.conflicts)

    def test_the_tattoo_code_is_held_for_that_conflict(self):
        text = bidirectional(ROWS)
        result = run(text, [sel('45381', span(text, 'A submucosal tattoo of carbon particle suspension was injected')),
                            sel('45385', span(text, 'an 8 mm sessile polyp was removed with a cold snare'))])
        tattoo = proposal(result, '45381')
        self.assertEqual(tattoo.status, 'needs_clarification')
        self.assertIn('conflict:tattoo', facts_asked(tattoo) | {c.fact for c in result.clarifications})
        self.assertEqual(tattoo.support.get('reason'), 'conflict', tattoo.support)
        snare = proposal(result, '45385')
        self.assertNotEqual(snare.support.get('reason'), 'conflict', snare.support)
        self.assertFalse({f for f in facts_asked(snare) if f.startswith('conflict:')})

    def test_every_denying_entry_denies_the_row_s_act(self):
        for entry in ('No', 'None', 'Not done', 'Not performed', 'No - none used', 'No (none used)', 'No, none used',
                      'NO'):
            with self.subTest(entry=entry):
                inv = inventory(bidirectional(ROWS[:4] + [f'Tattoo or marking agent injected | {entry}']))
                self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)
                self.assertTrue(acts(inv, 'gi.colonoscopy', 'tattoo', 'negated', 'nursing'))

    def test_a_bare_item_label_is_its_own_question(self):
        for label in ('Tattoo', 'Tattoo placed', 'Tattoo injected', 'Was a tattoo placed'):
            with self.subTest(label=label):
                inv = inventory(bidirectional(ROWS[:4] + [f'{label} | No']))
                self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)

    def test_an_entry_that_does_not_deny_is_no_denial(self):
        # an affirmation, a doubt, an answer this reader cannot read, or a note that says it was done after all
        for entry in ('Yes', 'Yes, two quadrants', 'Unknown', 'N/A', 'Not applicable', 'No?', 'No - unclear',
                      'No - placed by the fellow', 'No - Spot used instead', 'No - India ink', 'None obtained',
                      'See physician note'):
            with self.subTest(entry=entry):
                inv = inventory(bidirectional(ROWS[:4] + [f'Tattoo or marking agent injected | {entry}']))
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'tattoo', 'negated', 'nursing'))
                self.assertFalse(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)

    def test_a_label_that_asks_something_else_about_the_act_denies_nothing(self):
        # "None" answers the bleeding, the recommendation or the time span, never the act named among other words
        for label in ('Post-tattoo bleeding', 'Bleeding after the tattoo injection', 'Tattoo recommended',
                      'Tattoo or marking agent', 'Tattoo in the last 10 years', 'Snare polypectomy complications'):
            with self.subTest(label=label):
                inv = inventory(bidirectional(ROWS[:4] + [f'{label} | None']))
                self.assertFalse(conflicts(inv, 'gi.colonoscopy'), inv.conflicts)

    def test_a_row_s_entry_never_reaches_the_next_row(self):
        # the tattoo row's "No" is that row's: the snare row after it still reads as the nurse's affirmation
        rows = ['Time-out completed | Yes', 'Tattoo or marking agent injected | No', 'Snare polypectomy | Yes',
                'Colon biopsies | Yes']
        inv = inventory(bidirectional(rows))
        self.assertFalse(conflicts(inv, 'gi.colonoscopy', 'snare'), inv.conflicts)
        self.assertFalse(conflicts(inv, 'gi.colonoscopy', 'biopsy'), inv.conflicts)
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'snare', 'negated'))
        self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)

    def test_the_same_entry_in_a_colon_field_reads_the_same(self):
        # format family: a typed "label: entry" field holds what the table cell holds
        text = bidirectional(ROWS[:4]).replace(
            'Colon biopsies | Yes, descending colon\n',
            'Colon biopsies | Yes, descending colon\nTattoo or marking agent injected: No - none used\n')
        inv = inventory(text)
        self.assertTrue(conflicts(inv, 'gi.colonoscopy', 'tattoo'), inv.conflicts)

    def test_a_single_service_record_keeps_its_conflict(self):
        text = (HEAD + 'Colonoscopy Report\nDate of service: 2026-10-14\n'
                'The colonoscope reached the cecum. A 25 mm mass in the sigmoid colon was biopsied and a submucosal '
                'tattoo was injected distal to it.\n\nNursing checklist\nItem | Entry\nTattoo placed | Not done\n'
                'Biopsies | Yes\n')
        inv = inventory(text)
        found = conflicts(inv, 'gi.colonoscopy', 'tattoo')
        self.assertEqual(len(found), 1, inv.conflicts)
        self.assertEqual(sides(found[0]), {('physician', 'performed'), ('nursing', 'negated')})
        # the tattoo row's "Not done" is that row's: the biopsies row after it is no denied biopsy
        self.assertEqual({c.subject for c in inv.conflicts}, {'tattoo'}, inv.conflicts)

    def test_a_table_entry_never_denies_an_act_nobody_documented_done(self):
        # the nurse denies a band ligation nobody documented: no service is given that denial, so nothing is in conflict
        rows = ['Time-out completed | Yes', 'Snare polypectomy | Yes', 'Band ligation | No']
        inv = inventory(bidirectional(rows))
        self.assertEqual(inv.conflicts, ())
        self.assertFalse([a for s in inv.services for a in s.acts if a.kind == 'band_ligation'])
        self.assertEqual(services.validate(inv, bidirectional(rows)), ())

    def test_the_inventory_stays_internally_consistent(self):
        text = bidirectional(ROWS)
        self.assertEqual(services.validate(inventory(text), text), ())


# --- PR1: denials scoped to sites ---------------------------------------------------------------------------------

def upper(procedure, *sentences):
    return (HEAD + 'Upper Endoscopy Report\nDate of service: 2026-10-14\n' + (procedure + '\n' if procedure else '')
            + 'Findings\nThe gastroscope was advanced to the second portion of the duodenum. ' + ' '.join(sentences)
            + '\n')


SITED_ELSEWHERE = upper('Procedure: EGD with through-the-scope balloon dilation and cold forceps biopsies.',
                        'Rings and furrows were seen in the esophagus.',
                        'Biopsies: cold forceps biopsies were taken from the distal esophagus at 35 cm and the '
                        'proximal esophagus at 22 cm.',
                        'The narrowing at the gastroesophageal junction was dilated with a through-the-scope balloon '
                        'to 18 mm.',
                        'No gastric or duodenal biopsies were taken.')


def ercp(denial):
    return (HEAD + 'ERCP Procedure Report\nDate of service: 2026-10-14\n'
            'Procedure: ERCP with balloon dilation of a bile duct stricture and placement of a self-expanding metal '
            'stent.\nFindings\nCholangiography showed a 3 cm stricture of the distal common bile duct with upstream '
            'dilation. Deep cannulation of the bile duct was achieved over a guidewire. The stricture was dilated with '
            'a 6 mm balloon so that the stent delivery system could pass. One 10 mm by 60 mm fully covered '
            'self-expanding metal biliary stent was deployed across the stricture with brisk drainage. '
            + denial + '\n')


class ScopedDenialTests(SimpleTestCase):
    def test_a_summary_with_documented_acts_elsewhere_is_not_the_denied_sites(self):
        inv = inventory(SITED_ELSEWHERE)
        self.assertFalse(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)
        result = run(SITED_ELSEWHERE, [sel('43239', span(SITED_ELSEWHERE, 'cold forceps biopsies were taken from the '
                                                                           'distal esophagus'))])
        item = proposal(result, '43239')
        self.assertNotIn('conflict:biopsy', facts_asked(item) | {c.fact for c in result.clarifications})
        self.assertNotEqual(item.support.get('reason'), 'conflict', item.support)

    def test_an_act_at_a_lesion_is_not_another_region_s_denial(self):
        text = ercp('No pancreatic stent was placed.')
        inv = inventory(text)
        self.assertFalse(conflicts(inv, 'gi.ercp', 'stent'), inv.conflicts)
        result = run(text, [sel('43274', span(text, 'self-expanding metal biliary stent was deployed across the '
                                                    'stricture'))])
        item = proposal(result, '43274')
        self.assertNotIn('conflict:stent', facts_asked(item) | {c.fact for c in result.clarifications})

    def test_an_act_at_a_lesion_still_pairs_with_its_own_region_s_denial(self):
        inv = inventory(ercp('No stent was placed in the common bile duct.'))
        self.assertTrue(conflicts(inv, 'gi.ercp', 'stent'), inv.conflicts)

    def test_the_same_site_stays_a_conflict(self):
        inv = inventory(upper(None, 'Cold forceps biopsies were taken from the antrum.',
                              'No antral biopsies were taken.'))
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_a_summary_with_nothing_else_to_be_about_stays_in_doubt(self):
        inv = inventory(upper('Procedure: EGD with biopsies.', 'The mucosa looked normal.',
                              'No gastric biopsies were taken.'))
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_an_act_inside_the_denied_region_never_explains_the_summary_away(self):
        # the only sited biopsy is in the stomach the denial names: the summary may still be about the denied site
        inv = inventory(upper('Procedure: EGD with biopsies.', 'Biopsies were taken from the antrum.',
                              'No gastric biopsies were taken.'))
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_one_act_inside_the_denied_region_keeps_the_summary_paired(self):
        # the esophageal biopsy is outside "gastric" but the antral one is inside it: the summary may be about either,
        # and the antrum against "no gastric biopsies" is a contradiction the site names alone never pair (the
        # installed reader asks it through the summary; a rule that let the esophageal biopsy explain the summary away
        # would lose it)
        inv = inventory(upper('Procedure: EGD with biopsies.',
                              'Cold forceps biopsies were taken from the distal esophagus.',
                              'Biopsies were also taken from the antrum.', 'No gastric biopsies were taken.'))
        self.assertTrue(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_a_summary_explained_by_a_lesion_elsewhere(self):
        inv = inventory(upper('Procedure: EGD with biopsies.',
                              'A 12 mm ulcerated mass in the distal esophagus was biopsied with cold forceps.',
                              'No gastric or duodenal biopsies were taken.'))
        self.assertFalse(conflicts(inv, 'gi.egd', 'biopsy'), inv.conflicts)

    def test_a_service_wide_denial_still_pairs_with_an_act_at_a_lesion(self):
        # "No stent was placed" names no site: it is about every stent, the one across the stricture included
        inv = inventory(ercp('No stent was placed.'))
        self.assertTrue(conflicts(inv, 'gi.ercp', 'stent'), inv.conflicts)
