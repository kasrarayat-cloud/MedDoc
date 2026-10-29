"""GI round 3, repair lens "inventory" (session 7c8d38da): the documented-service inventory's fact binding.

The owner's directive of 2026-10-29 asks the inventory's fact binding repaired by the source - never by a document-
specific exception (docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, interpretations 45 and 46). Each rule binds a
documented fact to what the source says it is about:

- R1: a past-tense denial, cancellation or choice not to act, stated in the act's own segment of its clause, denies that
  act ("I deliberately did not take colon biopsies"); a plan ("No repeat manometry is needed"), a finding ("The common
  bile duct was not dilated"), an attributive noun ("biopsy results") and an extraction block deny nothing.
- R2: one table model with routing's (interpretation 45): a header row names columns, never an act; a cell under an act
  column answers that act for its own row's service; a row dated another day, and a table in a history, plan or
  indication part, bind nothing; a table's "Yes" states an act done only in a service already documented as performed
  (interpretation 24), and else holds it.
- R2c and I3: a row's label cell is answered by the table's item-answer column ("Nursing entry", "Performed", "Status"),
  never by another column's answer.
- R3: a lesion's descriptive words never hide it; "the mass" and "it" never bind past a lesion named since and not
  recorded; an act binds a lesion of its own clause and of its own service.
- R4: only a nominal list under a Procedure heading lists acts; a narrative paragraph there reads by its words.
- R5 and interpretation 46: a stent removed or exchanged is no placement, and its removal instrument no polypectomy; a
  selected placement or removal that is part of a documented exchange is held for the reviewer with the exchange named -
  never ready, never excluded.
- R6: a site binds to the mentions of its own segment; on a line naming two services each act takes the service its own
  segment names; one fact makes one conflict.
- R8: a labelled line naming another service's own work as reported or billed apart attributes it.
- RC8 (must-fix, class 2): services' title, plan-heading, list-label, form-field, check-box-row and coordination
  patterns backtracked polynomially over runs of whitespace; each is now linear, matching exactly what it matched.

The corpus (tests/corpus/gi3_inventory) holds the source-reviewed variants: every row read right by the source is pinned
by its checks, every residual by its input and exact output with its reason - a change that fixes one fails loudly and
is updated deliberately. Every document is synthetic. No network, no database.
"""
import json
import random
import re
import time
from datetime import date
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from studio import bounded
from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.reference.store import InMemoryReferenceLookup
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from studio.validation import reconcile
from studio.validation.engine import assess

CORPUS = Path(__file__).resolve().parent / 'corpus' / 'gi3_inventory'
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'


def variant(name: str) -> str:
    return (CORPUS / 'texts' / f'{name}.txt').read_text(encoding='utf-8')


def read(text):
    """The inventory as the assess stage reads it: the context's service date, routing, then the inventory."""
    facts = gi_context.extract_context(text)
    fact = facts['service_date']
    day = date.fromisoformat(fact.value) if fact.value and fact.origin in ('document', 'user') else None
    return services.build(text, service_date=day, routing=detect.route(text, day), context_facts=facts)


def acts(inv, family, kind=None, statuses=None):
    return [(s, a) for s in inv.services if s.family == family for a in s.acts
            if (kind is None or a.kind == kind) and (statuses is None or a.status in statuses)]


def service(inv, family):
    return reconcile.service_for(inv, family)


def selection(codes):
    return [tuple(x.split(':')[::-1]) for x in codes.split(',') if x]


def lesion_of(s, a):
    return next((les for les in s.lesions if les.id == a.lesion), None) if a.lesion else None


def check(inv, ch) -> bool:
    """One machine-checkable fact of a variant's source-reviewed expectation (the corpus's check vocabulary)."""
    t = ch['t']
    if t in ('act', 'act_any_kind'):
        kinds = ch['kinds'] if t == 'act_any_kind' else [ch['kind']]
        found = [(s, a) for k in kinds for s, a in acts(inv, ch['fam'], k, ch['status'])]

        def ok(s, a):
            if 'anat_any' in ch and not set(a.anatomy) & set(ch['anat_any']):
                return False
            if 'anat_none' in ch and set(a.anatomy) & set(ch['anat_none']):
                return False
            if ch.get('lesion') == 'none' and a.lesion:
                return False
            if 'lesion_not_anat' in ch:
                les = lesion_of(s, a)
                if les is not None and les.anatomy == ch['lesion_not_anat']:
                    return False
            return True
        return all(ok(s, a) for s, a in found) if ch.get('every') else any(ok(s, a) for s, a in found)
    if t == 'no_act':
        return not acts(inv, ch['fam'], ch['kind'], ch['status'])
    if t == 'no_act_evidence':
        return not any(ch['ev'] in ' '.join(e.text.split()) for _, a in acts(inv, ch['fam'], ch['kind'], ch['status'])
                       for e in a.evidence)
    if t == 'svc':
        s = service(inv, ch['fam'])
        return s is not None and s.status in ch['status']
    if t == 'svc_not':
        return not any(s.family == ch['fam'] and s.status in ch['status'] for s in inv.services)
    if t in ('conflicts', 'conflicts_min'):
        ids = {s.id for s in inv.services if s.family == ch['fam']}
        n = sum(1 for c in inv.conflicts if c.service in ids and c.subject == ch['subject'])
        return n == ch['n'] if t == 'conflicts' else n >= ch['n']
    if t == 'lesion':
        return any(re.search(ch['noun_re'], les.noun) and les.anatomy == ch['anat']
                   for s in inv.services if s.family == ch['fam'] for les in s.lesions)
    if t == 'no_lesion':
        return not any(re.search(ch['noun_re'], les.noun) for s in inv.services if s.family == ch['fam']
                       for les in s.lesions)
    if t == 'lesion_acts_anat_none':
        for s in inv.services:
            if s.family == ch['fam']:
                ids = {les.id for les in s.lesions if re.search(ch['noun_re'], les.noun)}
                if any(a.lesion in ids and set(a.anatomy) & set(ch['anat_none']) for a in s.acts):
                    return False
        return True
    if t == 'cue_date':
        s = service(inv, ch['fam'])
        return s is not None and any(ch['date'] in cue for cue in s.cues)
    if t in ('unres', 'bundled'):
        unresolved, bundled, _ = reconcile.reconcile(inv, selection(ch['codes']), procedure_day=True)
        ids = {s.id for s in inv.services if s.family == ch['fam']}
        if t == 'unres':
            has = any(u.family == ch['fam'] and u.act == ch['kind'] for u in unresolved)
        else:
            has = any(b.service in ids and b.act == ch['kind'] for b in bundled)
        return has == ch['present']
    if t == 'attribution':
        return any(a.role == ch['role'] for a in inv.attributions)
    if t == 'match':
        m = reconcile.match(ch['code'], inv, ch['fam'])
        return m is not None and m.state in ch['state']
    raise ValueError(t)


def summary(inv, codes) -> str:
    """The inventory and its reconciliation as one line: the exact output a residual is pinned by."""
    out = []
    for s in inv.services:
        described = []
        for a in s.acts:
            les = lesion_of(s, a)
            where = (f'@{les.size} {les.noun} {les.anatomy}'.strip() if les else '') + (
                f'[{",".join(a.anatomy)}]' if a.anatomy else '')
            described.append(f'{a.kind}/{a.status}{"/" + a.role if a.role != "physician" else ""}{where}')
        out.append(f'{s.family}={s.status}' + (f' acts: {"; ".join(described)}' if described else '')
                   + (f' lesions: {"; ".join(f"{les.size} {les.noun} {les.anatomy}" for les in s.lesions)}'
                      if s.lesions else ''))
    for c in inv.conflicts:
        out.append(f'CONFLICT {c.subject} lesion={c.lesion or "-"} sides={[(x.status, x.role) for x in c.sides]}')
    for chosen in sorted(codes):
        unresolved, bundled, _ = reconcile.reconcile(inv, selection(chosen), procedure_day=True)
        parts = [f'match {code}={getattr(reconcile.match(code, inv, fam), "state", None)}'
                 for code, fam in selection(chosen)]
        out.append(f'RECON[{chosen}] ' + ', '.join(parts)
                   + (' unresolved=' + str([(u.family.split('.')[-1], u.act) for u in unresolved]) if unresolved else '')
                   + (' bundled=' + str([b.act for b in bundled]) if bundled else ''))
    return ' | '.join(out)


def corpus_rows():
    return json.loads((CORPUS / 'variants.json').read_text(encoding='utf-8'))['variants']


def assess_picks(text, picks, day):
    """The engine's result for provider-selected (code, quote) picks against an empty reference."""
    codes = []
    for code, quote in picks:
        start = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, start, start + len(quote), quote, True),)))
    return assess(text=text, pages=(), context=gi_context.extract_context(text), routing=detect.route(text, day),
                  normalized=NormalizedResponse('replay', 'test@1', tuple(codes)),
                  reference=InMemoryReferenceLookup((), {}), service_date=day, provider_status='succeeded')


def proposal(result, code):
    return next(p for p in result.proposals if p.code == code)


class VariantCorpusTests(SimpleTestCase):
    """The source-reviewed variants (synthetic: the known cases' texts as the live service read them, and paraphrases,
    layouts and controls written for them): each row read right by the source keeps every check; each residual keeps
    its exact output until a change fixes it, which then fails here and is recorded deliberately."""

    def test_the_corpus_is_whole(self):
        rows = corpus_rows()
        self.assertEqual(len(rows), 94)
        self.assertEqual(len({row['id'] for row in rows}), 94)
        for row in rows:
            with self.subTest(row['id']):
                self.assertTrue((CORPUS / 'texts' / f'{row["id"]}.txt').exists())
                self.assertTrue(row['expected'].strip() and row['review'].strip() and row['checks'])
                self.assertNotIn('\n', row['review'])
                limit = row.get('known_limit')
                self.assertTrue(limit is None or (limit['reason'].strip() and limit['output'].strip()))

    def test_every_row_reads_right_by_its_source_or_as_its_recorded_limit(self):
        for row in corpus_rows():
            with self.subTest(row['id']):
                inv = read(variant(row['id']))
                self.assertEqual(services.validate(inv, variant(row['id'])), ())
                limit = row.get('known_limit')
                if limit is None:
                    failed = [ch for ch in row['checks'] if not check(inv, ch)]
                    self.assertEqual(failed, [], row['expected'])
                else:
                    codes = {ch['codes'] for ch in row['checks'] if 'codes' in ch}
                    self.assertEqual(summary(inv, codes), limit['output'], limit['reason'])
                    self.assertTrue(any(not check(inv, ch) for ch in row['checks']),
                                    'a recorded limit now reads right: record it as such')


class DenialTests(SimpleTestCase):
    """R1: the denial stated in an act's own segment is that act's predicate."""

    def test_a_past_tense_denial_or_choice_denies_the_act(self):
        for name in ('f1-active-did-not-take', 'f1-we-did-not-obtain', 'f1-elected-not-to', 'f1-contraction',
                     'f1-deferred'):
            with self.subTest(name):
                inv = read(variant(name))
                self.assertTrue(acts(inv, 'gi.colonoscopy', 'biopsy', ('negated', 'cancelled')))
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
                self.assertEqual(reconcile.match('45380', inv, 'gi.colonoscopy').state, 'not_performed')
                self.assertEqual([c for c in inv.conflicts if c.subject == 'biopsy'], [])

    def test_an_attempt_or_a_need_denied_in_the_past_denies_the_act(self):
        inv = read(variant('h2-04-live'))
        self.assertTrue(acts(inv, 'gi.egd', 'dilation', ('negated',)))
        self.assertTrue(acts(inv, 'gi.egd', 'bleeding_control', ('negated',)))
        self.assertFalse(acts(inv, 'gi.egd', 'dilation', ('performed',)))

    def test_a_plan_in_the_present_tense_denies_nothing(self):
        """"No repeat dilation is needed" plans another occurrence: today's dilation stays performed, with no
        conflict (the same document's past "no hemostatic treatment was needed" still denies hemostasis)."""
        inv = read(variant('f8-plan-no-repeat-needed'))
        self.assertTrue(acts(inv, 'gi.egd', 'dilation', ('performed',)))
        self.assertFalse(acts(inv, 'gi.egd', 'dilation', ('negated', 'cancelled')))
        self.assertEqual([c for c in inv.conflicts if c.subject == 'dilation'], [])
        self.assertTrue(acts(inv, 'gi.egd', 'bleeding_control', ('negated',)))

    def test_an_attributive_act_noun_denies_nothing(self):
        inv = read(variant('c7-attributive-biopsy-results'))
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('negated', 'cancelled')))

    def test_an_extraction_block_reads_as_before(self):
        """The ruled annotation reading: a white-out annotation ("Biopsy deferred.") names the page partial; the body's
        biopsy stays performed, never a cancelled one beside it (interpretation 46)."""
        inv = read(variant('f8-annotation-covers-biopsy'))
        self.assertTrue(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('negated', 'cancelled')))


H2_01_HEADER = 'Examination | Instrument | Furthest point reached | Tissue sampled'


class TableModelTests(SimpleTestCase):
    """R2: the one table model (interpretation 45), as routing's sections.tables reads it."""

    def table(self, lines):
        text = HEAD + 'Procedure summary\n' + '\n'.join(lines) + '\nImpression\nNormal.\n'
        return text, services._tables(text)

    def test_the_shape_of_a_table(self):
        text = variant('h2-01-live')
        tables = services._tables(text)
        self.assertEqual(len(tables), 1)
        table = tables[0]
        self.assertEqual(text[table.header[0]:table.header[1]], H2_01_HEADER)
        self.assertEqual(table.labels, ('examination', 'instrument', 'furthest point reached', 'tissue sampled'))
        self.assertEqual([[text[a:b] for a, b in row] for row in table.rows],
                         [['Upper endoscopy (EGD)', 'Standard gastroscope', 'Third portion of the duodenum',
                           'Yes, duodenum and stomach'],
                          ['Colonoscopy', 'Adult colonoscope', 'Terminal ileum, about 6 cm beyond the ileocecal valve',
                           'No']])

    def test_a_header_row_is_bare_labels(self):
        row = 'Colonoscopy | Adult colonoscope | Cecum'
        for header, is_table in (('Examination | Instrument | Extent', True),
                                 ('# | Examination | Extent', True), ('No. | Examination | Extent', True),
                                 ('No | Examination | Extent', True), ('Item | Examination | Extent', True),
                                 (' | Examination | Extent', True),
                                 ('Examination | Instrument (if any) | Extent', True),
                                 ('Examination | Instrument | Extent 2', False),  # a digit
                                 ('Examination | Instrument | Yes', False),  # an answer
                                 ('Examination | Instrument | Extent.', False),  # sentence punctuation
                                 ('Examination | Instrument | Furthest point reached by the scope today', False),
                                 ('No | Yes | Extent', False),  # a numbering cell beside only one worded label
                                 ('Examination | Extent', False)):  # two cells: a key and its value
            with self.subTest(header):
                _, tables = self.table([header, row if header.count(' | ') == 2 else 'Colonoscopy | Cecum'])
                self.assertEqual(bool(tables), is_table)

    def test_its_rows_have_the_header_s_cells(self):
        _, tables = self.table(['Examination | Instrument | Extent', 'Colonoscopy | Adult colonoscope | Cecum',
                                'Upper endoscopy | Gastroscope | D2', 'A line of prose after it.'])
        self.assertEqual([len(t.rows) for t in tables], [2])
        _, tables = self.table(['Examination | Instrument | Extent', 'Colonoscopy | Cecum'])
        self.assertEqual(tables, ())  # a header with no row of its cells is no table

    def test_each_line_of_a_table_is_a_sentence_of_its_own(self):
        text = variant('h2-01-live')
        start = text.index(H2_01_HEADER)
        cut = [(a, b) for a, b in services._sentences(text) if start <= a < start + 400 and '|' in text[a:b]]
        self.assertEqual(len(cut), 3)


class TableBindingTests(SimpleTestCase):
    """R2: a cell answers its own column for its own row's service."""

    def test_a_header_cell_is_never_an_act(self):
        one_service = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nThe colonoscope was advanced to the cecum. '
                       'Two polyps were seen and left for a later session.\nPolyp | Site | Size | Tissue sampled\n'
                       'First polyp | Sigmoid colon | 5 mm | No\nSecond polyp | Rectum | 3 mm | No\n')
        for name, text, header in [(name, variant(name), 'Examination | ') for name in (
                'h2-01-live', 'f2-table-col-first', 'c4-table-only-egd-biopsy')] + [
                ('one service', one_service, 'Polyp | Site')]:
            with self.subTest(name):
                at = text.index(header)
                inv = read(text)
                self.assertFalse([a for s in inv.services for a in s.acts
                                  if any(ev.start <= at < ev.end for ev in a.evidence)])
                if name == 'one service':
                    self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed', 'uncertain')))

    def test_a_cell_answers_its_own_row_whatever_the_row_order(self):
        for name in ('f2-table-egd-first', 'f2-table-col-first'):
            with self.subTest(name):
                inv = read(variant(name))
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
                self.assertTrue(acts(inv, 'gi.colonoscopy', 'biopsy', ('negated',)))
                for _, a in acts(inv, 'gi.egd', 'biopsy', ('performed',)):
                    self.assertFalse({'terminal ileum', 'ileocecal valve'} & set(a.anatomy))
                self.assertEqual(reconcile.match('45380', inv, 'gi.colonoscopy').state, 'not_performed')

    def test_a_table_answer_states_an_act_done_only_in_a_documented_service(self):
        """Interpretation 24: the table's "Yes" is the only word that the flexible sigmoidoscopy sampled tissue, and
        nothing documents that service as performed: its biopsy holds. The colonoscopy, documented by its own
        statement, takes its "Yes"."""
        text = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nThe colonoscope was advanced to the cecum and '
                'the cecum was photographed.\nResults reviewed\nExamination | Instrument | Tissue sampled\n'
                'Flexible sigmoidoscopy | Sigmoidoscope | Yes\nColonoscopy | Adult colonoscope | Yes, ascending colon\n')
        inv = read(text)
        self.assertFalse(acts(inv, 'gi.flex_sig', 'biopsy', ('performed',)))
        self.assertTrue(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
        self.assertEqual([a.anatomy for _, a in acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',))],
                         [('ascending colon',)])

    def test_an_answer_cell_that_is_no_answer_binds_nothing(self):
        for value in ('N/A', 'Yes/No', 'Ascending colon', '2 pieces'):
            text = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nThe colonoscope was advanced to the '
                    f'cecum.\nExamination | Instrument | Tissue sampled\nColonoscopy | Adult colonoscope | {value}\n')
            with self.subTest(value):
                inv = read(text)
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed', 'negated')))

    def test_a_row_dated_another_day_binds_nothing(self):
        inv = read(variant('h2-07-live'))
        self.assertEqual(service(inv, 'gi.colonoscopy').status, 'historical')
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))
        self.assertTrue(any('2025-11-12' in cue for cue in service(inv, 'gi.colonoscopy').cues))
        # a dated row under an act column: the 2021 colonoscopy's "Yes" is that occurrence's, never today's biopsy
        text = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nThe colonoscope was advanced to the cecum. '
                'No polyps.\nExamination | Date | Tissue sampled\nColonoscopy | 2021-03-02 | Yes, sigmoid colon\n')
        self.assertFalse(acts(read(text), 'gi.colonoscopy', 'biopsy', ('performed', 'uncertain')))

    def test_a_table_in_a_history_part_binds_nothing(self):
        inv = read(variant('c3-history-table'))
        self.assertFalse(any(s.family == 'gi.egd' and s.status in services.POSITIVE for s in inv.services))
        self.assertEqual([c for c in inv.conflicts if c.subject == 'snare'], [])
        text = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nThe colonoscope was advanced to the cecum. '
                'No polyps.\nPrior procedures:\nExamination | Tissue sampled | Polypectomy\nColonoscopy | Yes | Yes\n')
        self.assertFalse(acts(read(text), 'gi.colonoscopy', None, ('performed', 'uncertain')))


class ItemAnswerTests(SimpleTestCase):
    """R2c and I3: a row's label cell is answered by its table's item-answer column, never by another column."""

    def test_a_checklist_entry_answers_its_label_item(self):
        inv = read(variant('c1-nursing-3col'))
        self.assertTrue(acts(inv, 'gi.colonoscopy', 'tattoo', ('negated',)))
        self.assertFalse(acts(inv, 'gi.colonoscopy', 'snare', ('negated', 'cancelled')))
        self.assertEqual(len([c for c in inv.conflicts if c.subject == 'tattoo']), 1)

    def test_a_status_column_answers_its_row_s_service(self):
        """The "Performed" column's "No" is the upper endoscopy's own denial (its comment says nothing either way)."""
        text = (HEAD + 'Date of service: 2026-10-16\nEndoscopy record\nExamination | Performed | Comment\n'
                'Upper endoscopy (EGD) | No | routine\nColonoscopy | Yes | routine\n'
                'Colonoscopy\nThe colonoscope was advanced to the cecum. No polyps.\n')
        inv = read(text)
        egd = service(inv, 'gi.egd')
        self.assertEqual((egd.status, egd.cues[:1]), ('negated', ('field: the answer \u201cNo\u201d denies it',)))
        self.assertEqual(service(inv, 'gi.colonoscopy').status, 'performed')

    def test_a_status_column_s_yes_alone_holds_its_service(self):
        """I3's affirmative carries interpretation 24's condition: a table's "Yes" is never the only word that a service
        was done, so with nothing else documenting the colonoscopy it stays held."""
        for heading in ('Endoscopy record', 'Procedure summary'):
            text = (HEAD + f'Date of service: 2026-10-16\n{heading}\nExamination | Performed | Comment\n'
                    'Colonoscopy | Yes | none\n')
            with self.subTest(heading):
                self.assertNotIn(service(read(text), 'gi.colonoscopy').status, services.POSITIVE)

    def test_another_column_s_answer_never_answers_the_row_s_service(self):
        """The row's "No" answers "Tissue sampled", never whether the colonoscopy was done."""
        text = (HEAD + 'Date of service: 2026-10-16\nEndoscopy record\nExamination | Instrument | Tissue sampled\n'
                'Colonoscopy | Adult colonoscope | No\n')
        inv = read(text)
        self.assertNotIn(service(inv, 'gi.colonoscopy').status, ('negated', 'cancelled'))


class LesionTests(SimpleTestCase):
    """R3: lesions recorded by their words, and acts bound to their own lesion."""

    def test_a_lesion_s_descriptive_words_never_hide_it(self):
        inv = read(variant('f3-firm-friable'))
        colon = service(inv, 'gi.colonoscopy')
        self.assertTrue(any(les.noun == 'mass' and les.anatomy == 'sigmoid colon' for les in colon.lesions))
        unresolved, bundled, _ = reconcile.reconcile(inv, [('45385', 'gi.colonoscopy')], procedure_day=True)
        self.assertIn(('gi.colonoscopy', 'biopsy'), [(u.family, u.act) for u in unresolved])
        self.assertNotIn('biopsy', [b.act for b in bundled])

    def test_an_act_never_binds_past_a_lesion_named_since(self):
        inv = read(variant('c8-lesion-whose-removal-is-denied'))
        colon = service(inv, 'gi.colonoscopy')
        ascending = {les.id for les in colon.lesions if les.anatomy == 'ascending colon'}
        for a in colon.acts:
            if a.kind in ('tattoo',) or (a.kind == 'biopsy' and '4 mm' in a.evidence[0].text):
                self.assertNotIn(a.lesion, ascending, a)

    def test_two_lesions_of_one_size_and_site_stay_two(self):
        """"A 5 mm polyp" introduces a lesion: the second one is biopsied, never the first one's removal, so its biopsy is
        not bundled as a biopsy of a removed lesion (the prototype's restatement rule merged them outside a report
        part, and is left out)."""
        text = (HEAD + 'Date of service: 2026-10-16\nProcedure note\nFindings: The colonoscope was advanced to the '
                'cecum. A 5 mm polyp in the sigmoid colon was removed with a cold snare. A 5 mm polyp in the sigmoid '
                'colon was biopsied with cold forceps.\n')
        inv = read(text)
        self.assertEqual(len(service(inv, 'gi.colonoscopy').lesions), 2)
        _, bundled, _ = reconcile.reconcile(inv, [('45385', 'gi.colonoscopy')], procedure_day=True)
        self.assertNotIn('biopsy', [b.act for b in bundled])

    def test_a_tattoo_binds_the_lesion_it_marks(self):
        inv = read(variant('ho-01-live'))
        self.assertEqual(len([c for c in inv.conflicts if c.subject == 'tattoo']), 1)


class ProcedureLineTests(SimpleTestCase):
    """R4: only a nominal list under a Procedure heading lists acts."""

    def test_a_narrative_paragraph_under_procedure_reads_by_its_words(self):
        for name, kind in (('f4-procedure-paragraph-old-tattoo', 'tattoo'), ('f4-procedure-paragraph-old-stent', 'stent')):
            with self.subTest(name):
                inv = read(variant(name))
                self.assertFalse([a for s in inv.services for a in s.acts if a.kind == kind and a.status == 'performed'
                                  and a.evidence and 'seen' in a.evidence[0].text.lower()])

    def test_a_list_under_procedure_still_lists_its_acts(self):
        inv = read(variant('f4-procedure-list-line-ctrl'))
        self.assertTrue([a for s in inv.services for a in s.acts if a.status == 'performed'])

    def test_a_list_line_s_nominal_sentences(self):
        self.assertEqual(services._nominal_list_end('1. Colonoscopy. Cold snare polypectomy.'), 39)
        self.assertEqual(services._nominal_list_end('Colonoscopy. The stent was seen. Snare.'), 12)
        self.assertEqual(services._nominal_list_end('The stent was in position. Snare.'), 0)


H2_10_PLACED = 'A new 10 French by 9 cm plastic biliary stent was placed across the stricture'
H2_10_REMOVED = 'It was grasped with a snare and withdrawn through the working channel'


class StentExchangeTests(SimpleTestCase):
    """R5 and interpretation 46: a stent removed or exchanged is no placement; a placement or removal that is part of a
    documented exchange is held for the reviewer with the exchange named - never ready, never excluded."""

    def test_an_exchange_and_its_removal_are_acts_of_their_own(self):
        inv = read(variant('h2-10-live'))
        self.assertTrue(acts(inv, 'gi.ercp', 'stent_exchange', ('performed',)))
        self.assertTrue(acts(inv, 'gi.ercp', 'stent_removal', ('performed',)))
        self.assertFalse(acts(inv, 'gi.ercp', 'snare', ('performed',)))
        self.assertEqual(reconcile.match('43276', inv, 'gi.ercp').state, 'performed')

    def test_a_removal_alone_is_a_removal(self):
        inv = read(variant('f4-ercp-removal-only'))
        self.assertEqual(reconcile.match('43275', inv, 'gi.ercp').state, 'performed')
        self.assertFalse(acts(inv, 'gi.ercp', 'stent', ('performed',)))
        self.assertEqual([c for c in inv.conflicts if c.subject == 'stent'], [])

    def test_a_placement_that_is_part_of_an_exchange_is_held_with_the_exchange_named(self):
        inv = read(variant('h2-10-live'))
        for code in ('43274', '43275'):
            with self.subTest(code):
                m = reconcile.match(code, inv, 'gi.ercp')
                self.assertEqual((m.state, m.reason, m.acts), ('uncertain', reconcile.EXCHANGE_PART, ()))
                self.assertIn('Biliary stent exchanged', m.detail)
                self.assertIn('Biliary stent exchanged', m.question)

    def test_the_engine_holds_it_never_ready_and_never_excluded(self):
        text = variant('h2-10-live')
        for code, quote in (('43274', H2_10_PLACED), ('43275', H2_10_REMOVED)):
            with self.subTest(code):
                result = assess_picks(text, [(code, quote)], date(2026, 10, 23))
                held = proposal(result, code)
                self.assertEqual(held.status, 'needs_clarification')
                self.assertFalse(held.reinstatable or held.exclusion_reason)
                questions = [c.question for c in held.clarifications]
                self.assertTrue(any('stent exchange' in q and 'Biliary stent exchanged' in q for q in questions))
        result = assess_picks(text, [('43276', 'Biliary stent exchanged')], date(2026, 10, 23))
        self.assertEqual(proposal(result, '43276').status, 'ready')

    def test_a_placement_of_its_own_site_is_no_part_of_the_exchange(self):
        inv = read(variant('c6-ercp-exchange-plus-pancreatic'))
        m = reconcile.match('43274', inv, 'gi.ercp')
        self.assertEqual(m.state, 'performed')
        self.assertTrue(all('pancreatic duct' in a.anatomy for a in m.acts))


class SiteBindingTests(SimpleTestCase):
    """R6: sites and services bound by the act's own segment and clause; one fact, one conflict."""

    def test_a_site_binds_the_mentions_of_its_own_segment(self):
        inv = read(variant('f5-impression-gastric-and-polyp'))
        self.assertFalse(acts(inv, 'gi.egd', 'snare', ('performed',)))
        unresolved, _, _ = reconcile.reconcile(inv, [('43239', 'gi.egd'), ('45385', 'gi.colonoscopy')],
                                               procedure_day=True)
        self.assertNotIn(('gi.egd', 'snare'), [(u.family, u.act) for u in unresolved])

    def test_each_act_takes_the_service_its_own_segment_names(self):
        for name in ('f6-procline-two-services', 'f6-procline-two-services-rev'):
            with self.subTest(name):
                inv = read(variant(name))
                self.assertTrue(acts(inv, 'gi.egd', 'biopsy', ('performed',)))
                self.assertTrue(acts(inv, 'gi.colonoscopy', 'snare', ('performed',)))
                self.assertFalse(acts(inv, 'gi.egd', 'snare'))
                self.assertFalse(acts(inv, 'gi.colonoscopy', 'biopsy', ('performed',)))

    def test_one_denial_against_two_statements_is_one_conflict(self):
        text = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nThe colonoscope was advanced to the cecum. A '
                '12 mm polyp in the transverse colon was removed with a cold snare. The site was tattooed with India '
                'ink. A 6 mm polyp in the sigmoid colon was removed with a cold snare and its site was tattooed.\n'
                'Nursing record\nTattoo injected | No\n')
        inv = read(text)
        self.assertEqual(len([c for c in inv.conflicts if c.subject == 'tattoo']), 1)


class AttributionTests(SimpleTestCase):
    """R8: a labelled line naming another service's own work as reported or billed apart."""

    def test_a_labelled_line_attributes_another_service(self):
        for name, role in (('f9-attr-h2-10-radiology', 'radiology'), ('f9-attr-h2-09-cytology', 'pathology'),
                           ('f9-attr-h2-04-pathology', 'pathology')):
            with self.subTest(name):
                self.assertIn(role, [a.role for a in read(variant(name)).attributions])

    def test_a_label_that_says_the_opposite_attributes_nothing(self):
        for line in ('Radiology: not reported separately', 'Pathology: pending', 'Comment: the pathology reported '
                     'separately'):
            text = (HEAD + 'Date of service: 2026-10-16\nColonoscopy report\nThe colonoscope was advanced to the '
                    f'cecum.\n{line}\n')
            with self.subTest(line):
                self.assertEqual([a.role for a in read(text).attributions if a.role in ('radiology', 'pathology')], [])


# --- RC8: linear cost ------------------------------------------------------------------------------------------------
# The pattern TITLE_REPORT_WORDS replaced by _title_report_words, and FORM_FIELD_CHECKED by _form_field_checked, kept
# here as the reference their scans are checked against.
OLD_TITLE_REPORT_WORDS = re.compile(
    r'^[\s\-*#]*(?P<title>[^\n:.]{3,80}?)\s*[:\-–]\s*(?:(?:interpretation|procedure|operative|final|physician|study'
    r'|and|with)\s+){0,4}(?:report|note|record|interpretation|summary)\s*$', re.A | re.I)
OLD_FORM_FIELD_CHECKED = re.compile(
    r'[ \t]*(?P<label>[^:\n]{1,120}?)[ \t]*:[ \t]*(?P<answer>checked|yes)[ \t]*\.?[ \t]*', re.A | re.I)
PIN_CPU = 10  # process seconds a pinned shape may take (the repaired reader takes well under a second)
PIN_WALL = 60  # the bounded child's deadline: a runaway is stopped long before the assess stage's 120 s
DAY = date(2026, 10, 14)


def _cpu_build(text):
    started = time.process_time()
    services.build(text, service_date=None)
    return time.process_time() - started


def _cpu_build_on_day(text):
    started = time.process_time()
    services.build(text, service_date=DAY)
    return time.process_time() - started


class LinearCostTests(SimpleTestCase):
    """RC8 (the scope investigator's, class 2): the title reader backtracked quadratically over a run of whitespace -
    the 7c8 context shape "label, spaces, newline, spaces" (32,226 characters) took services.build about 350 s in the
    assess stage, after the request was sent - and so did the form-field, plan-heading, list-label, check-box-row and
    coordination patterns. Each is now linear (the doubling ratios are in the commit)."""

    def cpu(self, fn, text):
        return bounded.run_bounded(fn, text, seconds=PIN_WALL, memory_bytes=settings.ASSESS_MEMORY_BYTES)

    def test_the_inventory_reads_each_context_shape_in_time(self):
        from tests.test_repairs_7c8_context import LinearCostTests as Shapes
        self.assertEqual(len(Shapes.SHAPES), 7)
        for name, shape in Shapes.SHAPES.items():
            with self.subTest(shape=name):
                self.assertLess(self.cpu(_cpu_build, shape(16000)), PIN_CPU)

    def test_the_sibling_patterns_read_a_run_in_time(self):
        head = HEAD + 'Date of service: 2026-10-14\n'
        colo = 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\n'
        for name, text in (
                ('form-field line', head + colo + '\n[PDF form fields on page 1]\n' + ' ' * 64000 + 'Biopsy x\n'),
                ('bracket rows', head + colo + ('Biopsy a' + ' ' * 280 + 'x [\n') * 1300),
                ('plan line', head + 'History:\nPrior colonoscopy in 2020.\nProcedure: Colonoscopy\nPlan' + ' ' * 64000
                 + 'x\nFindings: The colonoscope was advanced to the cecum.\n')):
            with self.subTest(name):
                self.assertLess(self.cpu(_cpu_build_on_day, text), PIN_CPU)

    def test_a_table_and_a_sentence_of_acts_and_lesions_read_in_time(self):
        """Cost pins for the table model and the segment binding: a 300-row table of four cells, and a 1,200-character
        sentence alternating act and lesion mentions."""
        colo = HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the cecum.\n'
        table = colo + 'Examination | Site | Tissue sampled | Polypectomy\n' + 'Colonoscopy | Sigmoid colon | Yes | No\n' * 300
        sentence = colo + ' '.join(['biopsy', 'a 5 mm polyp'] * 92) + '.\n'
        for name, text in (('table', table), ('sentence', sentence)):
            with self.subTest(name):
                self.assertLess(self.cpu(_cpu_build_on_day, text), PIN_CPU)

    def test_each_fixed_pattern_reads_a_run_once(self):
        """Each pattern on the run its callers can give it, where the replaced one took seconds (quadratic or worse)."""
        run = ' ' * 20000
        for name, call in (
                ('title', lambda: services._title_report_words(run + 'Provider: Dr. A. Synthetic')),
                ('form field', lambda: services._form_field_checked(run + 'Biopsy x', 0, len(run) + 8)),
                ('list label', lambda: services.PROCEDURE_LIST_LABEL.fullmatch('Procedures' + run + 'x:')),
                ('plan heading', lambda: services.PLAN_HEADING.match('Plan' + run + 'x')),
                ('box row', lambda: list(services.BOX_ROW.finditer('a' + run[:2400] + 'x [')))):
            with self.subTest(name):
                started = time.process_time()
                call()
                self.assertLess(time.process_time() - started, 0.5)

    def test_the_patterns_match_what_they_matched(self):
        rng = random.Random(1029)
        atoms = [' ', ' ', '\t', '\n', '-', '–', ':', '.', '*', '#', 'a', 'EGD', 'x', 'report', 'note', 'summary',
                 'interpretation', 'procedure', 'and', 'with', 'checked', 'yes', 'Biopsy', 'Procedures', 'Plan', 'or',
                 ',', '[x]', '[ ]', 'performed', 'no']
        lines = ['SMALL BOWEL CAPSULE ENDOSCOPY: INTERPRETATION AND REPORT', 'Colonoscopy - procedure note',
                 '  - EGD: report', '---: report', ' \n   - report', 'Biopsy taken: checked', '   : yes',
                 'Biopsy: yes' + ' ' * 50 + 'x', ' ' * 40 + 'Biopsy x']
        lines += [''.join(rng.choice(atoms) for _ in range(rng.randint(0, 12))) for _ in range(20000)]
        for line in lines:
            self.assertEqual(services._title_report_words(line), bool(OLD_TITLE_REPORT_WORDS.match(line)), repr(line))
            old = OLD_FORM_FIELD_CHECKED.fullmatch(line)
            self.assertEqual(services._form_field_checked(line, 0, len(line)),
                             (old.start('label'), old.end('label'), old.group('answer')) if old else None, repr(line))
