"""Round r2c's geometry rules (DECISIONS D299 and D300): contract/geometry.py and contract/checks.py, from the geometry
up to the engine. TEXT-ONLY and SYNTHETIC: every note here was written for these tests (fictional clinicians, no
patient), and checked against the acceptance set's DEV-EXCLUSION list; every pass-1 answer is constructed by hand with
tests/v2/test_settle's builders; pass 2 is test_settle's faithful second reading; nothing is sent anywhere.

What is proved:
- D299 (P3-PART): G1's ``section`` link also holds for a source lying in the start of the containing section's
  PROCEDURE PART - the nearest section before it whose role pass 1 states as procedure, no section between them (nor the
  containing section itself) stating or offering procedure - so a findings part's act may cite its part's heading
  ("PART 1: ...", "FINDINGS:", "PART 2: ...", "FINDINGS:"); a source in another part's heading still fails, an offered,
  overfilled, negated or unplaceable procedure role heads no part, and every other G1 rule stands
  (R2CGProcedurePartTests at the geometry, R2CGProcedurePartCheckTests at check(), R2CGProcedurePartPipelineTests end to
  end: 43239 and 45385 READY where both were held on "In which procedure was this act done?");
- D300 RBFX-FRAME-1: whenever N0 passes G2 - D199's empty N0 of length zero included - the frame part starts at N0's
  start and joins the leading sections as D295 states; only an N0 with a G2 reason leaves none (R2CGEmptyOpeningTests,
  R2CGEmptyOpeningPipelineTests: a note that opens with its first heading is READY with its date of service, as the same
  note under a title line is; the walk still stops where an event is told);
- D300 RBFX-FRAME-2: the told offset counts every event pass 1 filed - a denial, and an anchor that fails to locate,
  told in a leading part before the date line leave that line outside the frame part, at check() itself
  (R2CGToldOffsetCheckTests), under a title line and in a note that opens with its first heading.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import uuid

from django.test import SimpleTestCase

from studio import interpretation, jobs
from studio.interpretation import store
from studio.interpretation.contract import checks, extract_read, geometry, segment, settle
from studio.interpretation.contract import extract_schema as xs
from studio.interpretation.contract.extract_read import FactKey
from studio.interpretation.contract.geometry import Anchor, Layout, Section, Sections
from studio.interpretation.contract.types import Attribute, Link, Reason, Source, Span
from studio.interpretation.engine import assess as engine_assess
from studio.interpretation.engine import derive
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from tests.v2.test_settle import (DEV_EXCLUSION, USAGE, Prepared, answer, event, fact, frame, labelled, lesion, opening,
                                  section, session, src)

A, F, R = Attribute, xs.Family, Reason

# --- the synthetic notes ----------------------------------------------------------------------------------------------

# D299: a note in procedure parts with findings subsections (each line one unit, S1-S11)
PARTS = ('SYNTHETIC ENDOSCOPY NOTE\n'                                              # S1: N0, the title
         'Date of service: 03/14/2031\n'                                           # S2: the date line
         'Endoscopist: Corvin Ashdale, MD (fictional)\n'                           # S3: the author line
         '\n'
         'PART 1: UPPER ENDOSCOPY\n'                                               # S4: N1, role procedure
         'The gastroscope was advanced to the second part of the duodenum.\n'      # S5: E1, X1's examination
         'FINDINGS:\n'                                                             # S6: N2, role findings
         'Biopsies of the gastric antrum were taken with cold forceps.\n'          # S7: E2, a biopsy in X1
         '\n'
         'PART 2: COLONOSCOPY\n'                                                   # S8: N3, role procedure
         'The colonoscope was advanced to the cecum.\n'                            # S9: E3, X2's examination
         'FINDINGS:\n'                                                             # S10: N4, role findings
         'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n')     # S11: E4, a snare removal in X2

# D300 RBFX-FRAME-1: a header in labelled parts with no title line - the note opens with its first heading (S1-S8)
LABEL_FIRST = ('PATIENT INFORMATION\n'                                             # S1: N1 at offset 0 (N0 empty)
               'Patient: synthetic patient R-22\n'                                 # S2
               'Date of service: 05/21/2032\n'                                     # S3: the date line, in N1
               'PROCEDURE DETAILS\n'                                               # S4: N2
               'Endoscopist: Corvin Ashdale, MD (fictional)\n'                     # S5: the author line, in N2
               'Instrument: adult colonoscope\n'                                   # S6
               '\n'
               'Findings: The colonoscope was advanced to the cecum.\n'            # S7: N3, the first act
               'A 5 mm polyp in the sigmoid colon was removed with a cold snare.\n')  # S8

# the same header under a title line (N0 holds the title, so it has a span) - the shape D295 already admitted
TITLED = 'SYNTHETIC COLONOSCOPY NOTE\n' + LABEL_FIRST

# D300 RBFX-FRAME-2: LABEL_FIRST with an event told in the first labelled part BEFORE its date line (S2: a denial, or
# an act whose anchor words do not locate), under a title line and with none; every other line as LABEL_FIRST's
TOLD_FIRST = LABEL_FIRST.replace('Patient: synthetic patient R-22\n', 'No sedation was given for the examination.\n')
TOLD_TITLED = 'SYNTHETIC COLONOSCOPY NOTE\n' + TOLD_FIRST

NOTES = {'PARTS': PARTS, 'LABEL_FIRST': LABEL_FIRST, 'TITLED': TITLED, 'TOLD_FIRST': TOLD_FIRST,
         'TOLD_TITLED': TOLD_TITLED}

SNARE = 'A 5 mm polyp in the sigmoid colon was removed with a cold snare.'
BIOPSY = 'Biopsies of the gastric antrum were taken with cold forceps.'


def key(family, name, attribute, index=0):
    return FactKey(family, name, attribute, index)


def read(text, data):
    """Pass 1's answer read as the current path reads it (gemini-events@3: an overfilled slot is an item-level
    finding, AMENDMENT-2 4.3.1)."""
    found = extract_read.read(json.dumps(data), len(segment.units(text)),
                              version=interpretation.INTERPRETATION_VERSION_V3)
    assert not isinstance(found, extract_read.Refusal), found
    return found


def checked(text, data):
    return checks.check(text, (), read(text, data))


def findings(found, family, name, attribute, index=0):
    return found.findings.get(key(family, name, attribute, index), ())


class _NoReference:
    """No reference row for any code (R9 is records only)."""

    def lookup(self, code, service_date):
        from types import SimpleNamespace

        return SimpleNamespace(pfs=None, mue=None)


def assessed(text, data, quotes):
    """``data`` read, checked, claimed, appraised by test_settle's faithful second reading, settled under the Fable
    path's label (gemini-appraisal@2) and stored at the product's pair (jobs.V2_VERSIONS), as jobs._appraisal_child
    does, then derived and assessed with one proposal per code quoting its sentence: (the effective date of service,
    {code: (status, sorted (fact, subject - '' for none -, cause) of its held facts)})."""
    prepared = Prepared(text, data)
    settled = settle.settle(prepared.read, prepared.checked, prepared.claim_set, prepared.request.indistinct,
                            prepared.appraisal(), USAGE, appraisal_version=interpretation.APPRAISAL_VERSION_V3)
    assert not isinstance(settled, settle.Unhealthy), settled
    text_sha = hashlib.sha256(text.encode('utf-8')).hexdigest()
    fields = store.row_v2(encounter_id=uuid.UUID(int=1), revision_id=uuid.UUID(int=2), provider_run_id=uuid.UUID(int=3),
                          appraisal_run_id=uuid.UUID(int=4), revision_text=text, text_sha256=text_sha,
                          request_sha256='2' * 64, response_sha256='3' * 64, appraisal_request_sha256='4' * 64,
                          appraisal_response_sha256='5' * 64, events=settled.events,
                          verification=settled.verification, versions=jobs.V2_VERSIONS)
    view = store.textfree_v2(store.load_v2(fields, text_sha256=text_sha, response_sha256='3' * 64,
                                           appraisal_response_sha256='5' * 64))
    effective = derive.derive(view, {}).effective
    codes = []
    for code, quote in quotes.items():
        at = text.index(quote)
        codes.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                  (EvidenceSpan(0, at, at + len(quote), quote, True),)))
    found = engine_assess.assess(
        inventory=view, date_of_service=datetime.date.fromisoformat(effective) if effective else None, text=text,
        pages=(), integrity=jobs._Integrity(), provider_status='succeeded',
        proposals=NormalizedResponse('replay', 'test@1', tuple(codes)), reference=_NoReference(),
        member=engine_assess.MemberContext(), label=lambda item: str(item.id))
    out = {}
    for item in found.codes:
        assert item.code not in out, item.code
        out[item.code] = (item.status.value, sorted((held.fact, '' if held.subject is None else str(held.subject),
                                                     held.cause) for held in item.held_facts))
    return effective, out


class R2CGFixtureTests(SimpleTestCase):
    def test_no_note_here_is_on_the_acceptance_exclusion_list(self):
        with open(DEV_EXCLUSION, encoding='ascii') as handle:
            excluded = {line.strip() for line in handle if line.strip()}
        self.assertTrue(excluded and all(len(value) == 64 for value in excluded), 'the exclusion list is readable')
        listed = [name for name, text in NOTES.items()
                  if {hashlib.sha256(text.encode('utf-8')).hexdigest(),
                      hashlib.sha256(text.strip().encode('utf-8')).hexdigest()} & excluded]
        self.assertEqual(listed, [])

    def test_the_notes_cut_one_unit_per_line(self):
        for name, text in NOTES.items():
            with self.subTest(note=name):
                lines = [line for line in text.split('\n') if line]
                self.assertEqual([text[unit.start:unit.end] for unit in segment.units(text)], lines)


# --- D299 (P3-PART) ---------------------------------------------------------------------------------------------------


def parts_answer(e2_session=('S4', 'PART 1: UPPER ENDOSCOPY'), e4_session=('S8', 'PART 2: COLONOSCOPY'), roles=None):
    """PARTS' pass-1 answer, filed as D299's motivating note was: N0 the title; N1 'PART 1: UPPER ENDOSCOPY' (role
    procedure) and its findings part N2; N3 'PART 2: COLONOSCOPY' (role procedure) and its findings part N4. The upper
    endoscopy X1 (its examination E1 told in N1) and an antral biopsy E2 told in N2; the colonoscopy X2 (E3 in N3) and
    a cold-snare removal of L1 E4 told in N4. Each act's session is cited at ``e2_session`` / ``e4_session`` (unit,
    words) through the link section - by default its part's heading, as pass 1 sourced that note's acts. ``roles``
    replaces a section's role slot."""
    roles = roles or {}

    def part(sid, unit, label, role):
        made = labelled(sid, unit, label, role)
        if sid in roles:
            made['role'] = roles[sid]
        return made

    return answer(
        sections=[opening(), part('N1', 'S4', 'PART 1: UPPER ENDOSCOPY', 'procedure'),
                  part('N2', 'S6', 'FINDINGS:', 'findings'), part('N3', 'S8', 'PART 2: COLONOSCOPY', 'procedure'),
                  part('N4', 'S10', 'FINDINGS:', 'findings')],
        sessions=[session('X1', fact('egd', src(['S5'], 'gastroscope')), examination=[fact('E1', src(['S5']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('duodenum', src(['S5'], 'advanced to the second part of the duodenum'))]),
                  session('X2', fact('colonoscopy', src(['S9'], 'colonoscope')), examination=[fact('E3', src(['S9']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('cecum', src(['S9'], 'advanced to the cecum'))])],
        lesions=[lesion('L1', src(['S11'], 'A 5 mm polyp'), multiplicity=[fact('single', src(['S11'], 'A 5 mm polyp'))],
                        places=[fact('sigmoid_colon', src(['S11'], 'sigmoid colon'))])],
        events=[event('E1', ['S5'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S5']))]),
                event('E2', ['S7'], 'Biopsies', 'were taken', 'biopsy',
                      session=[fact('X1', src([e2_session[0]], e2_session[1], 'section'))],
                      target__places=[fact('gastric_antrum', src(['S7'], 'gastric antrum'))],
                      technique__device=[fact('cold_forceps', src(['S7'], 'cold forceps'))]),
                event('E3', ['S9'], 'colonoscope', 'was advanced', 'examination', session=[fact('X2', src(['S9']))]),
                event('E4', ['S11'], 'cold snare', 'was removed', 'snare',
                      session=[fact('X2', src([e4_session[0]], e4_session[1], 'section'))],
                      target__lesion=[fact('L1', src(['S11'], 'A 5 mm polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S11'], 'sigmoid colon'))],
                      technique__device=[fact('cold_snare', src(['S11'], 'cold snare'))])])


class R2CGProcedurePartTests(SimpleTestCase):
    """D299 at the geometry: procedure_parts and the ``section`` link of link_reasons, over PARTS' sections."""

    def setUp(self):
        self.layout = layout = Layout.of(PARTS)
        self.sections = Sections(layout, (
            Section('N0', Source((), '', Link.SECTION), ()),
            Section('N1', Source(('S4',), 'PART 1: UPPER ENDOSCOPY', Link.SECTION), ()),
            Section('N2', Source(('S6',), 'FINDINGS:', Link.SECTION), ()),
            Section('N3', Source(('S8',), 'PART 2: COLONOSCOPY', Link.SECTION), ()),
            Section('N4', Source(('S10',), 'FINDINGS:', Link.SECTION), ())))
        self.biopsy = geometry.event_subject(layout, self.sections, Anchor(('S7',), 'Biopsies', 'were taken'))
        self.snare = geometry.event_subject(layout, self.sections, Anchor(('S11',), 'cold snare', 'was removed'))
        self.part1 = Source(('S4',), 'PART 1: UPPER ENDOSCOPY', Link.SECTION)
        self.part2 = Source(('S8',), 'PART 2: COLONOSCOPY', Link.SECTION)

    def parts(self, stated=('N1', 'N3'), possible=()):
        return geometry.procedure_parts(self.sections, frozenset(stated), frozenset(possible) | frozenset(stated))

    def links(self, subject, source, procedure):
        return geometry.link_reasons(self.layout, self.sections, subject, source, procedure=procedure)

    def test_each_findings_part_has_its_procedure_part_head(self):
        self.assertEqual([place.reasons for place in self.sections.places], [()] * 5)
        heads = self.parts()
        self.assertEqual({name: head.id for name, head in heads.items()}, {'N2': 'N1', 'N4': 'N3'})
        self.assertEqual((self.biopsy.section.id, self.snare.section.id), ('N2', 'N4'))

    def test_an_act_may_cite_its_procedure_parts_heading(self):
        heads = self.parts()
        self.assertEqual(self.links(self.biopsy, self.part1, heads), ())
        self.assertEqual(self.links(self.snare, self.part2, heads), ())
        # words inside the heading's place hold too; the part's other lines are not its start
        self.assertEqual(self.links(self.snare, Source(('S8',), 'COLONOSCOPY', Link.SECTION), heads), ())
        self.assertEqual(self.links(self.snare, Source(('S9',), 'colonoscope', Link.SECTION), heads),
                         (R.GEOMETRY_SECTION,))
        # before D299 (no procedure parts given): the containing section's own start only
        self.assertEqual(self.links(self.biopsy, self.part1, None), (R.GEOMETRY_SECTION,))
        self.assertEqual(self.links(self.snare, self.part2, {}), (R.GEOMETRY_SECTION,))
        # the containing section's own start holds as before
        self.assertEqual(self.links(self.snare, Source(('S10',), 'FINDINGS:', Link.SECTION), heads), ())

    def test_another_parts_heading_still_fails(self):
        heads = self.parts()
        self.assertEqual(self.links(self.snare, self.part1, heads), (R.GEOMETRY_SECTION,))
        self.assertEqual(self.links(self.biopsy, self.part2, heads), (R.GEOMETRY_SECTION,))

    def test_a_section_that_may_open_another_part_closes_the_part_before_it(self):
        # N3 only offered as procedure (a contradiction's side, an overfilled slot): N4 has no head - neither N3's
        # heading (not stated) nor N1's (another part may begin at N3)
        heads = self.parts(stated=('N1',), possible=('N3',))
        self.assertEqual({name: head.id for name, head in heads.items()}, {'N2': 'N1'})
        self.assertEqual(self.links(self.snare, self.part2, heads), (R.GEOMETRY_SECTION,))
        self.assertEqual(self.links(self.snare, self.part1, heads), (R.GEOMETRY_SECTION,))
        # N3 with no procedure role at all: N4's part is N1's
        heads = self.parts(stated=('N1',))
        self.assertEqual({name: head.id for name, head in heads.items()}, {'N2': 'N1', 'N3': 'N1', 'N4': 'N1'})
        self.assertEqual(self.links(self.snare, self.part1, heads), ())

    def test_a_section_that_is_or_may_be_a_procedure_part_has_no_other_head(self):
        heads = self.parts(stated=('N1', 'N3'), possible=('N4',))
        self.assertNotIn('N4', heads)
        self.assertNotIn('N3', heads)
        self.assertEqual(self.links(self.snare, self.part2, heads), (R.GEOMETRY_SECTION,))

    def test_a_head_without_a_span_or_without_a_cited_start_heads_nothing(self):
        broken = Sections(self.layout, (
            Section('N0', Source((), '', Link.SECTION), ()),
            Section('N1', Source(('S4',), 'PART 1: UPPER ENDOSCOPY', Link.SECTION), ()),
            Section('N2', Source(('S6',), 'FINDINGS:', Link.SECTION), ()),
            Section('N3', Source(('S8',), 'no such words', Link.SECTION), ()),
            Section('N4', Source(('S10',), 'FINDINGS:', Link.SECTION), ())))
        self.assertEqual(broken.place('N3').reasons, (R.SECTION_START_UNLOCATED,))
        heads = geometry.procedure_parts(broken, frozenset({'N1', 'N3'}), frozenset({'N1', 'N3'}))
        self.assertNotIn('N4', heads)
        self.assertNotIn('N2', heads, "N2's end is unknown (the next listed start is unlocated): it has no span")
        # N0 stated procedure: its start cites no unit, so it heads nothing
        heads = geometry.procedure_parts(self.sections, frozenset({'N0'}), frozenset({'N0'}))
        self.assertEqual(heads, {})

    def test_every_other_link_stands(self):
        heads = self.parts()
        # frame: inside the containing section's own span, never the part's
        self.assertEqual(self.links(self.snare, Source(('S9',), '', Link.FRAME), heads), (R.GEOMETRY_FRAME,))
        self.assertEqual(self.links(self.snare, Source(('S11',), '', Link.FRAME), heads), ())
        # a session's statement, the antecedent and the document frame do not read the part
        self.assertEqual(self.links(self.snare, Source(('S8',), '', Link.STATEMENT), heads), (R.GEOMETRY_STATEMENT,))
        self.assertEqual(self.links(self.snare, Source(('S8',), '', Link.DOCUMENT_FRAME), heads),
                         (R.GEOMETRY_DOCUMENT_FRAME,))
        # the encounter has no containing section: its section source fails, part or none
        self.assertEqual(self.links(geometry.unplaced_subject(), self.part2, heads), (R.GEOMETRY_SECTION,))

    def test_a_sections_own_fact_reads_its_procedure_part_too(self):
        # the rule is the link's: for a section's own facts the containing section is the section itself
        heads = self.parts()
        n4 = geometry.section_subject(self.sections, 'N4')
        self.assertEqual(self.links(n4, self.part2, heads), ())
        self.assertEqual(self.links(n4, self.part1, heads), (R.GEOMETRY_SECTION,))
        self.assertEqual(self.links(geometry.section_subject(self.sections, 'N3'), self.part1, heads),
                         (R.GEOMETRY_SECTION,))


SESSION_OF = ((F.EVENT, 'E2', A.SESSION), (F.EVENT, 'E4', A.SESSION))


class R2CGProcedurePartCheckTests(SimpleTestCase):
    """D299 at check(): the procedure parts come from pass 1's section roles, read through the merged view."""

    def session_findings(self, data):
        found = checked(PARTS, data)
        return {name: findings(found, family, name, attribute) for family, name, attribute in SESSION_OF}

    def test_each_act_cites_its_parts_heading_and_passes(self):
        self.assertEqual(self.session_findings(parts_answer()), {'E2': (), 'E4': ()})

    def test_another_parts_heading_still_fails(self):
        found = self.session_findings(parts_answer(e4_session=('S4', 'PART 1: UPPER ENDOSCOPY')))
        self.assertEqual(found['E4'], (R.GEOMETRY_SECTION,))

    def test_an_offered_or_overfilled_procedure_role_heads_no_part_and_closes_the_one_before(self):
        offered = fact('', src(['S8'], 'PART 2: COLONOSCOPY', 'section'), state='contradicted',
                       options=[{'value': 'procedure', 'sources': [src(['S8'], 'PART 2', 'section')]},
                                {'value': 'findings', 'sources': [src(['S8'], 'COLONOSCOPY', 'section')]}])
        overfilled = [fact('procedure', src(['S8'], 'PART 2', 'section')),
                      fact('findings', src(['S8'], 'COLONOSCOPY', 'section'))]
        for name, slot in (('contradicted', [offered]), ('overfilled', overfilled)):
            for e4_session in (('S8', 'PART 2: COLONOSCOPY'), ('S4', 'PART 1: UPPER ENDOSCOPY')):
                with self.subTest(role=name, cited=e4_session[1]):
                    data = parts_answer(e4_session=e4_session, roles={'N3': slot})
                    self.assertEqual(self.session_findings(data)['E4'], (R.GEOMETRY_SECTION,))

    def test_a_negated_malformed_or_unplaceable_procedure_role_heads_no_part(self):
        heading = src(['S4'], 'PART 1: UPPER ENDOSCOPY', 'section')
        negated = [fact('procedure', heading, state='negated')]
        unplaced = [fact('procedure', src(['S4'], 'PART 9: NOWHERE', 'section'))]
        unknown = [fact('procedure', src(['S99'], '', 'section'))]
        sourceless = [fact('procedure')]  # S2: a supported fact cites a source (shape_inconsistent)
        optioned = [fact('procedure', heading, options=[{'value': 'findings', 'sources': [heading]}])]  # S2 likewise
        reported = [fact('procedure', heading, qualifiers=['reported'])]  # Q1: qualified:reported
        for name, slot in (('negated', negated), ('words not in units', unplaced), ('unit unknown', unknown),
                           ('no source', sourceless), ('options on a supported fact', optioned),
                           ('qualified (Q1)', reported)):
            with self.subTest(role=name):
                self.assertEqual(self.session_findings(parts_answer(roles={'N1': slot}))['E2'], (R.GEOMETRY_SECTION,))

    def test_an_approximate_procedure_role_still_heads_its_part(self):
        # Q1 records approximate and never lowers: the only qualifier a heading role may carry
        approximate = [fact('procedure', src(['S4'], 'PART 1: UPPER ENDOSCOPY', 'section'), qualifiers=['approximate'])]
        self.assertEqual(self.session_findings(parts_answer(roles={'N1': approximate}))['E2'], ())

    def test_a_findings_part_with_no_role_between_keeps_its_part(self):
        # N2 and N4 with no role: their parts are still N1's and N3's (a silent role names no procedure part)
        found = self.session_findings(parts_answer(roles={'N2': [], 'N4': []}))
        self.assertEqual(found, {'E2': (), 'E4': ()})


class R2CGProcedurePartPipelineTests(SimpleTestCase):
    """D299 end to end: PARTS' answer read, checked, claimed, faithfully appraised, settled under gemini-appraisal@2,
    stored at the product's pair, derived and assessed - the antral biopsy (43239) and the cold-snare polypectomy
    (45385) are READY; before D299 each act's session failed G1 and both were held on "In which procedure was this act
    done?"."""

    def test_both_procedures_codes_are_ready(self):
        effective, found = assessed(PARTS, parts_answer(), {'43239': BIOPSY, '45385': SNARE})
        self.assertEqual(effective, '2031-03-14')
        self.assertEqual(found, {'43239': ('ready', []), '45385': ('ready', [])})

    def test_a_session_cited_at_another_parts_heading_still_holds(self):
        effective, found = assessed(PARTS, parts_answer(e4_session=('S4', 'PART 1: UPPER ENDOSCOPY')), {'45385': SNARE})
        self.assertEqual(effective, '2031-03-14')
        self.assertEqual(found, {'45385': ('needs_clarification',
                                           [('procedure', 'E4', 'unestablished:geometry_section')])})


# --- D300 RBFX-FRAME-1: a note that opens with its first heading -----------------------------------------------------


def header_answer(title=False):
    """LABEL_FIRST's pass-1 answer (TITLED's with ``title``: every unit one down, the title S1 N0's role), the labelled
    header filed as the pass-1 instruction asks: N0 the opening part (its start cites no unit; with no title line it has
    length zero, D199, and holds nothing to give it a role); N1 'PATIENT INFORMATION' and N2 'PROCEDURE DETAILS' (role
    header); N3 the findings part with the colonoscopy X1 (E1) and a cold-snare removal of L1 (E2). The date of service,
    every part's occasion and the session's encounter cite the date line, the documenting clinician and every part's
    owner and performer the author line - all through the document frame."""
    def unit(name):
        return f'S{int(name[1:]) + 1}' if title else name

    date, author = unit('S3'), unit('S5')
    owner = fact('documenting_clinician', frame([author]))
    occasion = fact('on_date_of_service', frame([date]))
    team = fact('documenting_team', frame([author]))

    def part(sid, at, label, role):
        start = src([unit(at)], label, 'section')
        return section(sid, start, owner, role=[fact(role, start)], occasion=[occasion], performer=[team])

    n0_role = [fact('header', src(['S1'], '', 'frame'))] if title else []
    return answer(
        sections=[section('N0', src([], '', 'section'), owner, role=n0_role, occasion=[occasion], performer=[team]),
                  part('N1', 'S1', 'PATIENT INFORMATION', 'header'), part('N2', 'S4', 'PROCEDURE DETAILS', 'header'),
                  part('N3', 'S7', 'Findings:', 'findings')],
        when={'state': 'stated', 'value': '2032-05-21', 'sources': [frame([date], '05/21/2032')], 'options': []},
        clinician=[fact('P1', frame([author], 'Corvin Ashdale'))],
        people=[{'id': 'P1', 'name': src([author], 'Corvin Ashdale'),
                 'role': fact('documenting_clinician', src([author], 'Endoscopist'))}],
        sessions=[session('X1', fact('colonoscopy', src([unit('S7')], 'colonoscope')),
                          examination=[fact('E1', src([unit('S7')]))],
                          encounter=[fact('this_encounter', frame([date]))],
                          reached=[fact('cecum', src([unit('S7')], 'advanced to the cecum'))])],
        lesions=[lesion('L1', src([unit('S8')], 'A 5 mm polyp'),
                        multiplicity=[fact('single', src([unit('S8')], 'A 5 mm polyp'))],
                        places=[fact('sigmoid_colon', src([unit('S8')], 'sigmoid colon'))])],
        events=[event('E1', [unit('S7')], 'colonoscope', 'was advanced', 'examination',
                      session=[fact('X1', src([unit('S7')]))]),
                event('E2', [unit('S8')], 'cold snare', 'was removed', 'snare', session=[fact('X1', src([unit('S8')]))],
                      target__lesion=[fact('L1', src([unit('S8')], 'A 5 mm polyp'))],
                      target__places=[fact('sigmoid_colon', src([unit('S8')], 'sigmoid colon'))],
                      technique__device=[fact('cold_snare', src([unit('S8')], 'cold snare'))])])


FRAMED = ((F.ENCOUNTER, '', A.DATE_OF_SERVICE), (F.ENCOUNTER, '', A.DOCUMENTING_CLINICIAN), (F.SECTION, 'N3', A.OWNER),
          (F.SECTION, 'N3', A.OCCASION), (F.SECTION, 'N3', A.PERFORMER), (F.SESSION, 'X1', A.ENCOUNTER))


class R2CGEmptyOpeningTests(SimpleTestCase):
    """D300 RBFX-FRAME-1 at the geometry and at check(): D199's empty N0 of length zero starts the frame part."""

    def setUp(self):
        self.layout = layout = Layout.of(LABEL_FIRST)
        self.sections = Sections(layout, (
            Section('N0', Source((), '', Link.SECTION), ()),
            Section('N1', Source(('S1',), 'PATIENT INFORMATION', Link.SECTION), ()),
            Section('N2', Source(('S4',), 'PROCEDURE DETAILS', Link.SECTION), ()),
            Section('N3', Source(('S7',), 'Findings:', Link.SECTION), ())))
        self.told = LABEL_FIRST.index('colonoscope was advanced')
        self.findings = LABEL_FIRST.index('Findings:')

    def test_an_empty_opening_part_starts_the_frame_part_and_joins_the_leading_parts(self):
        opening = self.sections.opening
        self.assertEqual((opening.start, opening.span, opening.reasons), (0, None, ()), 'D199: length zero, G2 passed')
        self.assertEqual(self.sections.place('N1').span, Span(0, LABEL_FIRST.index('PROCEDURE DETAILS')))
        self.assertEqual(geometry.frame_part(self.sections, self.told), Span(0, self.findings))
        frame_units = geometry.frame_units((Source(('S3',), '05/21/2032', Link.DOCUMENT_FRAME),
                                            Source(('S5',), 'Corvin Ashdale', Link.DOCUMENT_FRAME)))
        part = geometry.frame_part(self.sections, self.told)
        for source in (Source(('S3',), '05/21/2032', Link.DOCUMENT_FRAME),
                       Source(('S5',), 'Corvin Ashdale', Link.DOCUMENT_FRAME)):
            with self.subTest(source=source.units):
                self.assertEqual(geometry.link_reasons(self.layout, self.sections, geometry.unplaced_subject(), source,
                                                       frame_units, part), ())

    def test_the_walk_still_stops_where_an_event_is_told_and_no_event_leaves_the_empty_part(self):
        # told inside N1: the part is N0's, of length zero - it holds no source
        self.assertEqual(geometry.frame_part(self.sections, LABEL_FIRST.index('Patient:')), Span(0, 0))
        part = geometry.frame_part(self.sections, LABEL_FIRST.index('Patient:'))
        date = Source(('S3',), '05/21/2032', Link.DOCUMENT_FRAME)
        self.assertEqual(geometry.link_reasons(self.layout, self.sections, geometry.unplaced_subject(), date,
                                               frozenset({'S3'}), part), (R.GEOMETRY_DOCUMENT_FRAME,))
        # told inside N2: N0 and N1
        self.assertEqual(geometry.frame_part(self.sections, LABEL_FIRST.index('Instrument:')),
                         Span(0, LABEL_FIRST.index('PROCEDURE DETAILS')))
        # no event told: N0's part alone, as D295 left it
        self.assertEqual(geometry.frame_part(self.sections, None), Span(0, 0))

    def test_only_an_opening_part_with_a_g2_reason_leaves_no_frame_part(self):
        worded = Sections(self.layout, (
            Section('N0', Source(('S1',), 'PATIENT INFORMATION', Link.SECTION), ()),
            Section('N1', Source(('S1',), 'PATIENT INFORMATION', Link.SECTION), ()),
            Section('N2', Source(('S4',), 'PROCEDURE DETAILS', Link.SECTION), ())))
        self.assertEqual(worded.opening.reasons, (R.SECTION_ORDER,))
        self.assertIsNone(geometry.frame_part(worded, self.told))
        late = Sections(self.layout, (
            Section('N0', Source(('S4',), 'PROCEDURE DETAILS', Link.SECTION), ()),
            Section('N1', Source(('S7',), 'Findings:', Link.SECTION), ())))
        self.assertEqual(late.opening.reasons, (R.SECTION_ORDER,), 'a unit stands before it')
        self.assertIsNone(geometry.frame_part(late, self.told))

    def test_an_opening_part_whose_end_is_unknown_frames_nothing(self):
        unknown = Sections(self.layout, (
            Section('N0', Source((), '', Link.SECTION), ()),
            Section('N1', Source(('S1',), 'no such words', Link.SECTION), ()),
            Section('N2', Source(('S4',), 'PROCEDURE DETAILS', Link.SECTION), ())))
        self.assertEqual((unknown.opening.reasons, unknown.opening.span), ((), None))
        part = geometry.frame_part(unknown, self.told)
        self.assertEqual(part, Span(0, 0))
        for unit in ('S1', 'S2', 'S3'):
            with self.subTest(unit=unit):
                self.assertEqual(geometry.link_reasons(self.layout, unknown, geometry.unplaced_subject(),
                                                       Source((unit,), '', Link.DOCUMENT_FRAME), frozenset({unit}),
                                                       part), (R.GEOMETRY_DOCUMENT_FRAME,))

    def test_check_frames_the_date_the_author_and_every_part(self):
        found = checked(LABEL_FIRST, header_answer())
        self.assertIsNone(found.sections[0].span)
        for family, name, attribute in FRAMED:
            with self.subTest(fact=(name, attribute.value)):
                self.assertNotIn(R.GEOMETRY_DOCUMENT_FRAME, findings(found, family, name, attribute))


class R2CGEmptyOpeningPipelineTests(SimpleTestCase):
    """D300 RBFX-FRAME-1 end to end: the same header with and without its title line - both READY with their date of
    service (before D300 the note that opens with its first heading had no frame part and was held whole)."""

    def test_a_note_that_opens_with_its_first_heading_is_ready(self):
        effective, found = assessed(LABEL_FIRST, header_answer(), {'45385': SNARE})
        self.assertEqual((effective, found), ('2032-05-21', {'45385': ('ready', [])}))

    def test_the_same_note_under_a_title_line_is_ready_too(self):
        effective, found = assessed(TITLED, header_answer(title=True), {'45385': SNARE})
        self.assertEqual((effective, found), ('2032-05-21', {'45385': ('ready', [])}))

    def test_an_event_told_in_the_first_part_still_leaves_no_frame(self):
        # the walk stops where an event is told: a denial in the first labelled part leaves the part of length zero
        effective, found = assessed(TOLD_FIRST, told_answer('denial'), {'45385': SNARE})
        self.assertIsNone(effective)
        self.assertEqual(found['45385'][0], 'needs_clarification')
        self.assertIn(('service_date', '', 'date_unknown'), found['45385'][1])


# --- D300 RBFX-FRAME-2: the told offset counts denials and unlocated anchors, at check() ------------------------------


def told_answer(told, title=False):
    """TOLD_FIRST's pass-1 answer (TOLD_TITLED's with ``title``): LABEL_FIRST's filing with one more event E3 told on
    the first labelled part's second line, BEFORE its date line - a denial of moderate sedation ('denial'), an act whose
    anchor words do not locate there ('unlocated'), or none (None, the control)."""
    data = header_answer(title)
    line = 'S3' if title else 'S2'
    if told == 'denial':
        data['events'].append(event('E3', [line], 'sedation', 'No sedation was given', 'moderate_sedation',
                                    state='negated', status_source=src([line], 'No sedation was given')))
    elif told == 'unlocated':
        data['events'].append(event('E3', [line], 'propofol', 'was given', 'moderate_sedation'))
    return data


class R2CGToldOffsetPipelineTests(SimpleTestCase):
    """D300 RBFX-FRAME-2 end to end: under a title line, an event told in the first labelled part before its date line
    - a denial, or an act whose anchor words do not locate - leaves the date line outside the frame part, so the date of
    service is unknown and 45385 is held on it; with neither, the same note is READY with its date."""

    def test_an_event_before_the_date_line_leaves_the_date_unknown(self):
        effective, found = assessed(TOLD_TITLED, told_answer(None, title=True), {'45385': SNARE})
        self.assertEqual((effective, found), ('2032-05-21', {'45385': ('ready', [])}))
        for told in ('denial', 'unlocated'):
            with self.subTest(told=told):
                effective, found = assessed(TOLD_TITLED, told_answer(told, title=True), {'45385': SNARE})
                self.assertIsNone(effective)
                self.assertEqual(found['45385'][0], 'needs_clarification')
                self.assertIn(('service_date', '', 'date_unknown'), found['45385'][1])


class R2CGToldOffsetCheckTests(SimpleTestCase):
    """D300 RBFX-FRAME-2 at check(): a denial, and an anchor that fails to locate, told in a leading part before the
    date line end the frame part before that part, so the date line lies outside it (geometry_document_frame on the date
    of service, the session's encounter and every part's occasion); with neither, the date line frames the document.
    Under a title line and with none (D300 RBFX-FRAME-1)."""

    DATED = ((F.ENCOUNTER, '', A.DATE_OF_SERVICE), (F.SESSION, 'X1', A.ENCOUNTER), (F.SECTION, 'N3', A.OCCASION))

    def frame_findings(self, told, title):
        text = TOLD_TITLED if title else TOLD_FIRST
        found = checked(text, told_answer(told, title))
        return found, {(name, attribute.value): R.GEOMETRY_DOCUMENT_FRAME in findings(found, family, name, attribute)
                       for family, name, attribute in self.DATED}

    def test_without_an_event_before_it_the_date_line_frames_the_document(self):
        for title in (True, False):
            with self.subTest(title=title):
                _, failed = self.frame_findings(None, title)
                self.assertEqual(set(failed.values()), {False})

    def test_a_denial_told_before_the_date_line_leaves_it_outside_the_frame_part(self):
        for title in (True, False):
            with self.subTest(title=title):
                found, failed = self.frame_findings('denial', title)
                self.assertEqual(findings(found, F.EVENT, 'E3', A.STATUS), ())
                self.assertEqual(set(failed.values()), {True})

    def test_an_anchor_that_does_not_locate_before_the_date_line_leaves_it_outside_the_frame_part(self):
        for title in (True, False):
            with self.subTest(title=title):
                found, failed = self.frame_findings('unlocated', title)
                self.assertIsNone(found.anchors['E3'].place, 'the anchor fails I2 (anchor_words)')
                self.assertIn(R.ANCHOR_INVALID, findings(found, F.EVENT, 'E3', A.KIND))
                self.assertEqual(set(failed.values()), {True})
