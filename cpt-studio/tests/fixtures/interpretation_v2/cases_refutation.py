"""The refutation's cases (FINAL-V2 9.5 [R]; REFUTATIONS-V2.md), each as (i) and (ii), and as (iii) where the finding
names a shared misreading (HO-3's probe (a), SC-C's sphincteroplasty, CO-7's fb08) or a ruling keeps one (DECISIONS D241:
C2MEM-031's tattoo filed with no place and no lesion, as CK-note8's). PAIR-4-W2 and fb08 are the FRESH-1
development documents themselves (devdocs.py); every other document is written for these fixtures, a few in the shape
of a named development document (its provenance names it; read for its shape only, checked against the exclusion
list). The cases a class or checklist fixture already builds are referenced there: HO-2's v3 (CK-v3), BF17 (D1), SC-B's
BF6 (BF6), CO-8's v6 (CK-v6), CO-1's BF2 (T5)."""
from __future__ import annotations

from tests.fixtures.interpretation_v2 import devdocs as D
from tests.fixtures.interpretation_v2.build import Case
from tests.fixtures.interpretation_v2.cases_checklist import (N8_CODES, N8_TATTOO_TARGETS, N8B, NOTE8_HEADER, NOV9,
                                                               TWO, colonoscopy, dev, gi_note8, sections)
from tests.fixtures.interpretation_v2.cases_s4 import (COLO_FINDINGS, EGD_FINDINGS, ERCP_HEAD, EXP, HEAD_OFFICE, NEG,
                                                       OTHER, SNARE_LINE, TIME, VISIT, H, Q, R, X, cannulation, colo,
                                                       egd, ercp, head, office, polyp, snare)
from tests.fixtures.interpretation_v2.dsl import Note, unit_at

THREE = ('i', 'ii', 'iii')
COLO = head('COLONOSCOPY REPORT') + COLO_FINDINGS


# HO-3: probe (a) beside a genuine snare
HO3_TEXT = COLO + SNARE_LINE + 'Neither biopsy nor snare polypectomy was performed.\n'


def ho3(n: Note, mis: bool) -> dict:
    denial = n.event('E3', 'snare', 'snare polypectomy', 'was performed', session='X1',
                     status_state='supported' if mis else NEG,
                     status_source=n.src('Neither biopsy nor snare polypectomy was performed'),
                     breadth=None if mis else ('all_of_kind', 'Neither biopsy nor snare polypectomy'))
    return colo(n, snare(n), denial, lesions=(polyp(n),))


# HO-1: one fixture per consumer of the doubt arm
HO1A_TEXT = COLO + 'It is unclear whether the polyp was removed with the cold snare.\n'


def ho1a(n: Note, mis: bool) -> dict:
    act = n.event('E2', 'snare', 'cold snare', 'was removed', session='X1', device=('cold_snare', 'cold snare'))
    doubts = () if mis else (n.doubt('status', ('E2',), 'It is unclear whether', 'stated', ('performed',)),)
    return colo(n, act, doubts=doubts)


HO1B_TEXT = HEAD_OFFICE + VISIT + 'A flexible sigmoidoscopy may have been performed in the office today.\n' + TIME


def ho1b(n: Note, mis: bool) -> dict:
    exam = n.event('E2', 'examination', 'flexible sigmoidoscopy', 'may have been performed', session='X2',
                   status_state=NEG if mis else 'supported')
    doubts = () if mis else (n.doubt('status', ('E2',), 'may have been performed', 'stated', ('performed',)),)
    return office(n, exam, sessions=(n.session('X2', 'flex_sig', 'flexible sigmoidoscopy', exam='E2'),), doubts=doubts)


HO1C_TEXT = COLO + ('Biopsies of the sigmoid colon may have been taken.\n'
                    'No biopsies were taken from the rectum.\n')


def ho1c(n: Note, mis: bool) -> dict:
    doubted = n.event('E2', 'biopsy', 'Biopsies', 'may have been taken', session='X1',
                      places=[('sigmoid_colon', 'sigmoid colon')], status_state=NEG if mis else 'supported')
    denial = n.event('E3', 'biopsy', 'No biopsies', 'No biopsies were taken', session='X1', status_state=NEG,
                     breadth=('single_target', 'from the rectum'), places=[('rectum', 'from the rectum')])
    doubts = () if mis else (n.doubt('status', ('E2',), 'may have been taken', 'stated', ('performed',)),)
    return colo(n, doubted, denial, doubts=doubts)


# HO-2: "No prior colonoscopy."
HO2_TEXT = head('COLONOSCOPY REPORT') + 'History: No prior colonoscopy.\n' + COLO_FINDINGS


def ho2(n: Note, mis: bool) -> dict:
    prior = n.event('E2', 'examination', 'No prior colonoscopy', 'No prior colonoscopy', session='X1',
                    status_state=NEG, date_relation=('on_date_of_service' if mis else 'earlier_date', 'No prior colonoscopy'))
    return n.answer(sections=[n.opening(), n.part('N1', 'History:', 'history', occasion=None),
                              n.part('N2', 'Findings:', 'findings')],
                    sessions=[n.session('X1', 'colonoscopy', 'colonoscope', exam='E1',
                                        reached=[('cecum', 'advanced to the cecum')])],
                    events=[n.event('E1', 'examination', 'colonoscope', 'was advanced', session='X1'), prior])


# HO-5: the sibling-misfiled denial
HO5_TEXT = COLO + SNARE_LINE + 'No polypectomy was performed.\n'


def ho5(n: Note, mis: bool) -> dict:
    denial = n.event('E3', 'biopsy' if mis else 'removal', 'polypectomy', 'No polypectomy was performed', session='X1',
                     status_state=NEG, breadth=('all_of_kind', 'No polypectomy'))
    return colo(n, snare(n), denial, lesions=(polyp(n),))


# SC-A, HO-6: the stent exchange, the biopsy-then-snare sentence, the shared denial anchor
SCA1_TEXT = ERCP_HEAD + 'The existing biliary stent was removed and replaced with a new plastic stent.\n'


def sca1(n: Note, mis: bool) -> dict:
    placement = n.event('E4', 'stent', 'new plastic stent', 'replaced', session='X1', duct=('biliary', 'biliary'))
    removal = n.event('E3', 'stent_removal', 'existing biliary stent', 'was removed', session='X1',
                      duct=('biliary', 'biliary'))
    return ercp(n, cannulation(n), *((placement,) if mis else (removal, placement)))


# D216's own case (4a p10): the removal and the placement in two sentences, the code citing the placement alone, so no
# unlisted unit lies on its evidence (3.2.6 rule 2) and only XCHG's absence condition reads the unlisted removal
SCA1B_TEXT = ERCP_HEAD + 'The existing biliary stent was removed.\nA new 10 Fr plastic biliary stent was placed.\n'


def sca1b(n: Note, mis: bool) -> dict:
    placement = n.event('E4', 'stent', 'plastic biliary stent', 'was placed', session='X1',
                        duct=('biliary', 'plastic biliary stent'))
    removal = n.event('E3', 'stent_removal', 'existing biliary stent', 'was removed', session='X1',
                      duct=('biliary', 'existing biliary stent'))
    return ercp(n, cannulation(n), *((placement,) if mis else (removal, placement)))


SCA2_TEXT = COLO + 'A polyp in the descending colon was biopsied with cold forceps and then removed with a hot snare.\n'


def sca2(n: Note, mis: bool) -> dict:
    lesion = n.lesion('L1', 'A polyp in the descending colon', multiplicity=('single', 'A polyp'),
                      places=[('descending_colon', 'descending colon')])
    biopsy = n.event('E2', 'biopsy', 'biopsied', 'was biopsied', session='X1', lesion=('L1', 'A polyp'),
                     device=('cold_forceps', 'cold forceps'))
    removal = n.event('E3', 'snare', 'hot snare', 'removed', session='X1', lesion=('L1', 'A polyp'),
                      device=('hot_snare', 'hot snare'))
    return colo(n, *((removal,) if mis else (biopsy, removal)), lesions=(lesion,))


SCA3_TEXT = COLO + 'Neither biopsy nor tattoo was performed.\n'


def sca3(n: Note, mis: bool) -> dict:
    words = 'Neither biopsy nor tattoo was performed'
    biopsy = n.event('E2', 'biopsy', 'biopsy', words, session='X1', status_state=NEG, breadth=('all_of_kind', words))
    tattoo = n.event('E3', 'tattoo', 'tattoo', words, session='X1', status_state=NEG, breadth=('all_of_kind', words))
    return colo(n, *((biopsy,) if mis else (biopsy, tattoo)))


# SC-B: the short place list beside a rectal denial
SCB_TEXT = COLO + ('Cold forceps biopsies were taken from the sigmoid colon and the rectum.\n'
                   'No biopsies were taken from the rectum after the polyp was found.\n')


def scb(n: Note, mis: bool) -> dict:
    places = [('sigmoid_colon', 'sigmoid colon')] + ([] if mis else [('rectum', 'and the rectum')])
    return colo(n, n.event('E2', 'biopsy', 'Cold forceps biopsies', 'were taken', session='X1', places=places,
                           device=('cold_forceps', 'Cold forceps')),
                n.event('E3', 'biopsy', 'No biopsies', 'No biopsies were taken', session='X1', status_state=NEG,
                        breadth=('single_target', 'from the rectum after'),
                        places=[('rectum', 'from the rectum after')]))


# SC-C: a balloon sphincteroplasty filed as a sphincterotomy
SCC_TEXT = ERCP_HEAD + 'Balloon sphincteroplasty of the papilla was performed to 12 mm.\n'


def scc(n: Note, mis: bool) -> dict:
    return ercp(n, cannulation(n), n.event('E3', 'sphincterotomy' if mis else 'dilation', 'Balloon sphincteroplasty',
                                           'was performed', session='X1', places=[('ampulla', 'of the papilla')],
                                           device=('balloon', 'Balloon sphincteroplasty'), duct=('biliary', 'papilla')))


# SC-D: a nursing note with a summarizing impression
SCD_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + (
    'Nursing note: A 5 mm rectal polyp was removed with a cold snare.\n'
    'Impression: A 5 mm rectal polyp was removed with a cold snare by me.\n')


def scd(n: Note, mis: bool) -> dict:
    act = n.event('E2', 'snare', 'cold snare', 'was removed', session='X1', places=[('rectum', 'rectal polyp')],
                  device=('cold_snare', 'cold snare'),
                  restatements=[('by me', 'restates' if mis else 'summarizes')])
    return colo(n, act, sections=(n.part('N2', 'Nursing note:', 'nursing_note', owner='nursing',
                                         owner_words='Nursing note:', performer=None),
                                  n.part('N3', 'Impression:', 'impression')))


# HO-7: two performers in one session
HO7_TEXT = COLO + SNARE_LINE + 'A 4 mm rectal polyp was removed with a cold snare by Dr. Ines Varro, a visiting surgeon.\n'


def ho7(n: Note, mis: bool) -> dict:
    who = ('documenting_team', 'by Dr. Ines Varro') if mis else ('other_clinician', 'by Dr. Ines Varro')
    other = n.event('E3', 'snare', 'cold snare', 'was removed', anchor_words='A 4 mm rectal polyp', session='X1',
                    places=[('rectum', 'rectal polyp')], device=('cold_snare', 'cold snare'), performer=who)
    return colo(n, snare(n), other, lesions=(polyp(n),))


# HO-8: the two binding cases
HO8A_TEXT = COLO + ('Cold forceps biopsies of the sigmoid colon were taken.\n'
                    'Nursing note: Cold forceps biopsies of the rectum were taken.\n')


def ho8a(n: Note, mis: bool) -> dict:
    contradicted = n.fact('', n.src('Cold forceps biopsies of the sigmoid colon'), state='contradicted',
                          options=({'value': 'on_date_of_service', 'sources': [n.src('were taken', nth=0)]},
                                   {'value': 'earlier_date', 'sources': [n.src('of the sigmoid colon')]}))
    first = n.event('E2', 'biopsy', 'Cold forceps biopsies', 'were taken', session='X1',
                    places=[('sigmoid_colon', 'sigmoid colon')], date_relation=contradicted)
    second = n.event('E3', 'biopsy', 'Cold forceps biopsies', 'were taken', nth=1, session='X1',
                     places=[('rectum', 'of the rectum')])
    owner = 'documenting_clinician' if mis else 'nursing'
    return colo(n, first, second, sections=(n.part('N2', 'Nursing note:', 'nursing_note', owner=owner,
                                                    owner_words='Nursing note:', performer='team'),))


HO8B_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'The distal esophageal stricture was dilated.\n'
    'The duodenal bulb stricture was dilated with a balloon.\n')


def ho8b(n: Note, mis: bool) -> dict:
    return egd(n, n.event('E2', 'dilation', 'distal esophageal stricture', 'was dilated', session='X1',
                          places=[('distal_esophagus', 'distal esophageal')],
                          device=('balloon', 'was dilated') if mis else None),
               n.event('E3', 'dilation', 'dilated with a balloon', 'was dilated', session='X1',
                       places=[('duodenal_bulb', 'duodenal bulb')], device=('balloon', 'balloon')))


# HO-9: a reach given both polarities
HO9_TEXT = COLO + 'The cecum was not reached because of a stricture.\n'


def ho9(n: Note, mis: bool) -> dict:
    reached = [('cecum', 'advanced to the cecum')]
    if not mis:
        reached.append(('cecum', 'The cecum was not reached', OTHER, NEG))
    return colo(n, reached=tuple(reached))


# CO-3: GI Note #8's wrapped denial shape (a negator on the line before)
CO3_TEXT = COLO + 'No biopsies\nwere taken.\n'


def co3(n: Note, mis: bool) -> dict:
    words = 'No biopsies\nwere taken'
    return colo(n, n.event('E2', 'biopsy', 'biopsies', words, anchor_words=words, session='X1',
                           status_state='supported' if mis else NEG, breadth=None if mis else ('all_of_kind', words)))


# CO-6: an examination told across several parts
CO6_TEXT = head('COLONOSCOPY REPORT') + (
    'Procedure: The colonoscope was inserted into the rectum.\n'
    'Findings: The colonoscope was advanced through the colon.\n'
    'Biopsies of the cecum were taken with cold forceps.\n'
    'Impression: The colonoscope reached the cecum.\n')


def co6(n: Note, mis: bool) -> dict:
    reached = [('cecum', 'Biopsies of the cecum', OTHER)] if mis else [('cecum', 'The colonoscope reached the cecum', OTHER)]
    exam = n.event('E1', 'examination', 'The colonoscope was inserted', 'was inserted', session='X1',
                   restatements=[('The colonoscope reached the cecum', 'restates')])
    return n.answer(sections=sections(n, ('Procedure:', 'procedure', 'today'), ('Findings:', 'findings', 'today'),
                                      ('Impression:', 'impression', 'today')),
                    sessions=[n.session('X1', 'colonoscopy', 'The colonoscope was inserted', exam='E1', reached=reached)],
                    events=[exam, n.event('E2', 'biopsy', 'Biopsies', 'were taken', session='X1',
                                          places=[('cecum', 'of the cecum')], device=('cold_forceps', 'cold forceps'))])


# CO-4, CO-5: PAIR-4-W2 itself
PAIR4_HEADER = dict(NOV9, clinician='A. Current')


def pair4(n: Note, mis: bool) -> dict:
    when = ('on_date_of_service', 'this examination I resected', 'placing') if mis else \
        ('earlier_date', 'in October 2026')
    who = ('documenting_team', 'I resected', 'placing') if mis else ('other_clinician', 'Dr. B. Prior')
    return n.answer(
        sections=[n.opening(role=[n.fact('header', n.whole(n.units[0].id, 'section'))]),
                  n.part('N1', 'Indication:', 'indication', occasion=None),
                  n.part('N2', 'Procedure', 'procedure'), n.part('N3', 'Impression', 'impression')],
        sessions=[n.session('X1', 'colonoscopy', 'The colonoscope reached the cecum', exam='E1',
                            reached=[('cecum', 'reached the cecum')])],
        events=[n.event('E1', 'examination', 'The colonoscope reached the cecum', 'reached', session='X1'),
                n.event('E2', 'tattoo', 'placed a tattoo', 'placed', session='X1', date_relation=when, performer=who,
                        places=[('sigmoid_colon', 'sigmoid lesion at the referring')]),
                n.event('E3', 'emr', 'resected', 'I resected', session='X1', lesion=('L1', 'the 18 mm sigmoid lesion'),
                        places=[('sigmoid_colon', 'the 18 mm sigmoid lesion')]),
                n.event('E4', 'injection', 'saline lift', 'after a saline lift', session='X1',
                        purpose=('lift_for_resection', 'saline lift'), part_of=('E3', 'after a saline lift'),
                        part_relation=('lift_for', 'after a saline lift'))],
        lesions=[n.lesion('L1', 'the 18 mm sigmoid lesion', multiplicity=('single', 'the 18 mm sigmoid lesion'),
                          places=[('sigmoid_colon', 'the 18 mm sigmoid lesion')])])


# CO-7: fb08 itself
FB08_HEADER = dict(dos='2026-11-03', dos_line='Date of service: November 3, 2026', dos_words='November 3, 2026',
                   clinician='Beatrix Lowenthal')


def fb08(n: Note, mis: bool) -> dict:
    today = ('earlier_date', 'at the last colonoscopy') if mis else ('on_date_of_service', 'today either')
    return n.answer(
        sections=[n.opening(), n.part('N1', 'Indication:', 'indication', occasion=None),
                  n.part('N2', 'History:', 'history', occasion=None), n.part('N3', 'Procedure:', 'procedure'),
                  n.part('N4', 'Findings:', 'findings'), n.part('N5', 'Impression:', 'impression'),
                  n.part('N6', 'Plan:', 'plan', occasion=None)],
        sessions=[n.session('X1', 'colonoscopy', 'The colonoscope was advanced', exam='E1',
                            reached=[('terminal_ileum', 'into the terminal ileum')])],
        events=[n.event('E1', 'examination', 'The colonoscope was advanced', 'was advanced', session='X1'),
                n.event('E2', 'removal', 'No polypectomy', 'No polypectomy was performed', session='X1',
                        status_state=NEG, date_relation=('earlier_date', 'at the last colonoscopy'),
                        breadth=('all_of_kind', 'No polypectomy')),
                n.event('E3', 'removal', 'No polypectomy', 'none was performed today either', session='X1',
                        status_state=NEG, date_relation=today, breadth=('all_of_kind', 'none was performed'))])


# CO-1 and CO-2: W1S-499 (a finding against an act, 2.2 BF24) and W1S-222 (a plan sentence that places the narratives
# above), the development documents themselves: one note of an EGD and a colonoscopy, told alike in both up to their
# differences (W1S-499's "No other biopsies were taken.", its hot-forceps removal and its impression's seventh item;
# W1S-222's plan line).
W1S_HEADER = dict(dos='2026-10-14', dos_line='Service date: Oct 14, 2026', dos_words='Oct 14, 2026',
                  clinician='Synthetic Endoscopist')


def w1s(n: Note, which: str, mis: bool) -> dict:
    """The right filing of W1S-499 (``which`` '499') or W1S-222 ('222'), or its misfiling:
    - the header's propofol is the anesthesia team's act (other, medication); the Indication's history - the 2023 ERCP at
      another hospital (its sphincterotomy and stone extraction, a session of its own, separate_encounter) and the later
      cholecystectomy - are acts of an earlier date;
    - EGD X1 (to the second part of the duodenum): the two biopsy sets of jars 1 and 2; W1S-499's "No other biopsies
      were taken." excepts both;
    - colonoscopy X2 (to the terminal ileum in W1S-499; W1S-222 states no reach): the digital rectal examination
      (manual), the cold snare removal of the
      sigmoid polyp and the prophylactic clip closing its defect (adjunct_of), W1S-499's hot-forceps removal;
    - W1S-499's impression item 7, the only statement of a gastric body polyp removal: the act as stated (session not
      stated: empty), with a doubt about its status, basis conflict, citing "Body and fundus normal" and item 7 (BF24);
      its misfiling drops the doubt;
    - W1S-222's plan: "No endoscopy was done today" a broad denial of the examination today, and "the narratives above
      are from 2023" placing the EGD, colonoscopy and impression parts at an earlier date (link placing, 1.5); its
      misfiling leaves the parts on the date line."""
    placed = which == '222' and not mis

    def told(sid: str, label: str, role: str, nth: int = 0) -> dict:
        if placed:
            return n.part(sid, label, role, nth=nth,
                          occasion=('earlier_date', 'the narratives above are from 2023', 'placing'))
        return n.part(sid, label, role, nth=nth)

    sections = [n.opening(), n.part('N1', 'INDICATION', 'indication', occasion=None, performer=None),
                told('N2', 'EGD', 'procedure', 1),
                told('N3', 'COLONOSCOPY', 'procedure', 1), told('N4', 'IMPRESSION', 'impression'),
                n.part('N5', 'PLAN', 'plan', occasion=None, performer=None)]
    sessions = [n.session('X1', 'egd', 'Gastroscope passed', exam='E1',
                          reached=[('second_portion_duodenum', 'to the second part of the duodenum')]),
                n.session('X2', 'colonoscopy', 'The colonoscope was inserted', exam='E6',
                          reached=[('terminal_ileum', 'The terminal ileum was intubated')] if which == '499' else []),
                n.session('X3', 'ercp', 'ERCP with biliary sphincterotomy',
                          encounter=('separate_encounter', 'in 2023', 'other_statement'))]
    earlier, elsewhere = ('earlier_date', 'in 2023'), ('other_facility', 'at another')
    events = [
        n.event('E1', 'examination', 'Gastroscope passed', 'passed under direct vision', session='X1'),
        n.event('E2', 'biopsy', 'Biopsies, cold forceps: antrum and body', 'Biopsies, cold forceps', session='X1',
                places=[('gastric_antrum', 'antrum and body'), ('gastric_body', 'antrum and body')],
                device=('cold_forceps', 'cold forceps'), restatements=[('mild antral erythema, biopsied', 'summarizes')]),
        n.event('E3', 'biopsy', 'duodenal\nbulb and second portion', 'for celiac disease (jar 2)', session='X1',
                anchor_words='Biopsies, cold forceps',
                places=[('duodenal_bulb', 'bulb and second portion'),
                        ('second_portion_duodenum', 'bulb and second portion')],
                device=('cold_forceps', 'cold forceps'), restatements=[('biopsied for celiac disease', 'summarizes')]),
        n.event('E5', 'examination', 'Rectal exam', 'Rectal exam', session='X2', device=('manual', 'Rectal exam')),
        n.event('E6', 'examination', 'The colonoscope was inserted', 'inserted and advanced', session='X2'),
        n.event('E7', 'snare', 'cold\nsnare', 'removed en bloc', session='X2', lesion=('L1', '10 mm sessile polyp'),
                places=[('sigmoid_colon', 'Sigmoid colon, 30 cm')], device=('cold_snare', 'cold\nsnare'),
                restatements=[('10 mm sigmoid polyp removed with cold snare', 'summarizes')]),
        n.event('E8', 'clip', 'one clip', 'placed to close the defect', session='X2',
                purpose=('prophylaxis', 'to close the defect'), part_of=('E7', 'to close the defect'),
                part_relation=('adjunct_of', 'to close the defect'), device=('clip', 'one clip'),
                restatements=[('prophylactic clip placed', 'summarizes')]),
        n.event('E10', 'sphincterotomy', 'biliary sphincterotomy', 'ERCP with biliary sphincterotomy', session='X3',
                date_relation=earlier, performer=elsewhere, duct=('biliary', 'biliary sphincterotomy'),
                restatements=[('Healed sphincterotomy at the papilla from the 2023 ERCP', 'summarizes')]),
        n.event('E11', 'stone_extraction', 'stone extraction', 'stone extraction', session='X3',
                date_relation=earlier, performer=elsewhere),
        n.event('E12', 'other', 'laparoscopic cholecystectomy', 'followed by laparoscopic cholecystectomy',
                other_class=('procedure', 'laparoscopic cholecystectomy'),
                date_relation=('earlier_date', 'followed by laparoscopic cholecystectomy')),
        n.event('E13', 'other', 'Propofol', 'administered by anesthesia', other_class=('medication', 'Propofol'),
                performer=('other_clinician', 'administered by anesthesia (CRNA)'))]
    lesions = [n.lesion('L1', '10 mm sessile polyp', multiplicity=('single', '10 mm sessile polyp'),
                        places=[('sigmoid_colon', 'Sigmoid colon, 30 cm')])]
    doubts: list = []
    if which == '499':
        events.insert(3, n.event('E4', 'biopsy', 'No other biopsies', 'No other biopsies were taken', session='X1',
                                 status_state=NEG, breadth=('exceptive', 'No other'), excepts=['E2', 'E3']))
        events.append(n.event('E9', 'hot_biopsy', 'hot biopsy forceps', 'was removed', session='X2',
                              lesion=('L2', 'A 3 mm polyp'), places=[('rectum', 'in the rectum')],
                              device=('hot_forceps', 'hot biopsy forceps')))
        events.append(n.event('E14', 'snare', 'cold snare', 'removed with cold snare',
                              anchor_words='Gastric body polyp removed', lesion=('L3', 'Gastric body polyp'),
                              places=[('gastric_body', 'Gastric body polyp')], device=('cold_snare', 'cold snare')))
        lesions += [n.lesion('L2', 'A 3 mm polyp', multiplicity=('single', 'A 3 mm polyp'),
                             places=[('rectum', 'in the rectum')]),
                    n.lesion('L3', 'Gastric body polyp', multiplicity=('single', 'Gastric body polyp'),
                             places=[('gastric_body', 'Gastric body polyp')])]
        if not mis:
            doubts.append({'about': 'status', 'objects': ['E14'], 'units': [n.u('Body and fundus normal'),
                                                                        n.u('Gastric body polyp removed')],
                           'basis': 'conflict', 'readings': ['performed']})
    else:
        events.append(n.event('E15', 'examination', 'No endoscopy', 'No endoscopy was done today',
                              status_state=NEG, breadth=('all_of_kind', 'No endoscopy'),
                              date_relation=('on_date_of_service', 'today')))
    return n.answer(sections=sections, sessions=sessions, events=events, lesions=lesions, doubts=doubts)


def co1(n: Note, mis: bool) -> dict:
    return w1s(n, '499', mis)


# CO-2: placing sentences (f2-after-002 after the act; twins-015 in the indication; W1S-222 in the plan; C2MEM-031's
# attestation over the findings). f2-after-002, twins-015 and W1S-222 are the development documents themselves.
F2AFTER_HEADER = dict(dos='2026-10-14', dos_line='Date of service: 2026-10-14', dos_words='2026-10-14', clinician='')


def co2a(n: Note, mis: bool) -> dict:
    """f2-after-002 (2.2 BF22): the removal's own date relation and performer cite the placing sentence after it; a
    procedure done at the referring facility in 2024 is a session of its own (encounter separate_encounter), never
    today's colonoscopy X1. The misfiling files it in X1 with nothing of its own: it inherits today and the team."""
    placed = {} if mis else dict(date_relation=('earlier_date', 'in 2024', 'placing'),
                                 performer=('other_facility', 'at the referring facility', 'placing'))
    sessions = () if mis else (n.session('X2', 'colonoscopy', 'A 22 mm polyp in the ascending colon',
                                         encounter=('separate_encounter', 'at the referring facility')),)
    return n.answer(sections=[n.opening(), n.part('N1', 'Procedure:', 'procedure')],
                    sessions=[n.session('X1', 'colonoscopy', 'The colonoscope was advanced', exam='E1',
                                        reached=[('cecum', 'advanced to the cecum')],
                                        completion=('complete', 'the examination was completed')), *sessions],
                    events=[n.event('E1', 'examination', 'The colonoscope was advanced', 'was advanced', session='X1'),
                            n.event('E2', 'snare', 'cold snare', 'was removed', session='X1' if mis else 'X2',
                                    lesion=('L1', 'A 22 mm polyp'), places=[('ascending_colon', 'ascending colon')],
                                    device=('cold_snare', 'cold snare'), **placed)],
                    lesions=[n.lesion('L1', 'A 22 mm polyp', multiplicity=('single', 'A 22 mm polyp'),
                                      places=[('ascending_colon', 'ascending colon')])])


TWINS015_HEADER = dict(dos='2026-10-14', dos_line='Date of service: 2026-10-14', dos_words='2026-10-14',
                       clinician='Synthetic Endoscopist')


def co2b(n: Note, mis: bool) -> dict:
    """twins-015 (2.2 BF23): the Indication's "done elsewhere" places the procedure described below - the Procedure,
    Findings and Impression parts' occasion earlier_date and performer other_facility, link placing to the Indication;
    the header's anesthesia care is the anesthesia team's act; the Plan's repeat EGD is planned, in eight weeks. The
    misfiling leaves the described parts on the inherited date line and team."""
    def described(sid: str, label: str, role: str) -> dict:
        if mis:
            return n.part(sid, label, role)
        return n.part(sid, label, role, occasion=('earlier_date', 'done elsewhere', 'placing'),
                      performer=('other_facility', 'done elsewhere', 'placing'))
    return n.answer(
        sections=[n.opening(), n.part('N1', 'Indication:', 'indication', occasion=None, performer=None),
                  described('N2', 'Procedure:', 'procedure'), described('N3', 'Findings:', 'findings'),
                  described('N4', 'Impression:', 'impression'),
                  n.part('N5', 'Plan:', 'plan', occasion=None, performer=None)],
        sessions=[n.session('X1', 'egd', 'The adult gastroscope was passed', exam='E1',
                            reached=[('second_portion_duodenum', 'into the second part of the duodenum')]),
                  n.session('X2', 'egd', 'Repeat EGD', exam='E4', encounter=('separate_encounter', 'in 8 weeks'))],
        events=[n.event('E1', 'examination', 'The adult gastroscope was passed', 'was passed', session='X1'),
                n.event('E2', 'biopsy', 'cold forceps biopsies', 'were taken', session='X1',
                        places=[('proximal_esophagus', 'proximal and distal esophagus'),
                                ('distal_esophagus', 'proximal and distal esophagus')],
                        device=('cold_forceps', 'cold forceps'), restatements=[('biopsied', 'summarizes')]),
                n.event('E3', 'other', 'Monitored anesthesia care', 'Monitored anesthesia care',
                        other_class=('other', 'Monitored anesthesia care'),
                        performer=('other_clinician', 'by the anesthesia team')),
                n.event('E4', 'examination', 'Repeat EGD', 'Repeat EGD', status='planned', session='X2',
                        date_relation=('later_date', 'in 8 weeks'))])


def co2c(n: Note, mis: bool) -> dict:
    return w1s(n, '222', mis)


def co2d(n: Note, mis: bool) -> dict:
    """C2MEM-031 (CO-2): GI Note #8 with "Those were the findings at her index colonoscopy." after its anastomosis part,
    filed as CK-note8 is, that part placed at the index colonoscopy (cases_checklist.gi_note8, ``index``); the tattoo
    filed faithfully (D241)."""
    return gi_note8(n, mis, index=True)


def co2d_no_place(n: Note) -> dict:
    """C2MEM-031 filed right but for the tattoo, with no place and no lesion: D241's variant (iii)."""
    return gi_note8(n, False, index=True, tattoo='no_place')


SHAPE = 'synthetic: written for this fixture in the shape of development document {} (read for its shape only)'

CASES = [
    Case('RF-HO3', 'refutation', ('HO-3',), 'Probe (a) beside a genuine snare', HO3_TEXT, ho3, variants=THREE,
         codes=(('45385', 'cold snare'),), caught=('status@E3/0',),
         expect={'i': {'45385': (H, 'conflict:snare', Q, '4.5: the denial pairs with the genuine snare on every row: '
                                                         'CONTRADICTION (RANK 1)')},
                 'ii': {'45385': (H, 'statement_scope', Q, '4.5 [R:HO-3]: an event whose status pass 2 did not '
                                                           'establish is a possible statement and pairs (RANK 3)')}}),
    Case('RF-HO1a', 'refutation', ('HO-1',), 'A stated doubt beside a base code', HO1A_TEXT, ho1a, variants=TWO,
         codes=(('45378', 'colonoscope'),), caught=('status@E2/0',),
         expect={'i': {'45378': (H, 'base_included', Q, '4.7 [R:HO-1]: a doubted act is possibly performed: '
                                                        'base_included (c), a question')},
                 'ii': {'45378': (H, 'base_included', Q, 'the status not established: a doubted act')}}),
    Case('RF-HO1b', 'refutation', ('HO-1',), 'A doubted same-day sigmoidoscopy beside an office visit', HO1B_TEXT, ho1b,
         variants=TWO, codes=(('99214', 'seen in the office'),), caught=('status@E2/0',),
         expect={'i': {'99214': (H, 'separate_em', Q, '4.7 C-3 [R:HO-1]: a doubted procedure is a possible procedure '
                                                      'day')},
                 'ii': {'99214': (H, 'separate_em', Q, '4.7 C-3: the sigmoidoscopy whose status pass 2 did not '
                                                       'establish is possibly positive (4.2 [R:HO-1]) on the date of '
                                                       'service it inherits: a procedure day, and no separately '
                                                       'identifiable statement (RANK 20); never READY')}}),
    Case('RF-HO1c', 'refutation', ('HO-1',), 'A cited rectal denial beside a doubted sigmoid biopsy', HO1C_TEXT, ho1c,
         variants=TWO, codes=(('45380', 'No biopsies were taken', True),), caught=('status@E2/0',),
         expect={'i': {'45380': (H, 'performed_status', Q, '4.6 condition 5 [R:HO-1]: the doubted biopsy is a positive '
                                                           'candidate: never excluded (RANK 2)')},
                 'ii': {'45380': (H, 'statement_scope', Q, '4.6: a citation beside a doubt (the biopsy\'s status not '
                                                           'established) asks statement_scope, never an exclusion')}}),
    Case('RF-HO2', 'refutation', ('HO-2',), '"No prior colonoscopy." beside today\'s colonoscopy', HO2_TEXT, ho2,
         variants=TWO, codes=(('45378', 'colonoscope'),), caught=('date_relation@E2/0',),
         expect={'i': {'45378': (R, None, None, '4.5 timing row: the denial is of an earlier date (INDEPENDENT) '
                                                '[R:HO-2]')},
                 'ii': {'45378': (H, 'performed_status', Q, '4.3 row 7: an event that may be the session\'s examination, '
                                                            'possibly today, is established not done (RANK 4)')}}),
    Case('RF-HO5', 'refutation', ('HO-5',), 'A sibling-misfiled denial', HO5_TEXT, ho5, variants=TWO,
         codes=(('45385', 'cold snare'),), caught=('kind@E3/0',),
         expect={'i': {'45385': (H, 'conflict:snare', Q, '4.5: the removal denial contradicts the snare (RANK 1)')},
                 'ii': {'45385': (H, 'conflict:snare', Q, '4.5 [R:HO-5]: a statement whose kind is not established '
                                                          'is compatible with every kind of its family, so it pairs; no '
                                                          'row reads the kind, every row is SAME and both statuses are '
                                                          'established: CONTRADICTION (RANK 1), never set apart')}}),
    Case('RF-SCA1', 'refutation', ('SC-A', 'HO-6'), 'A stent exchange whose removal only pass 2 reports', SCA1_TEXT,
         sca1, variants=TWO, codes=(('43274', 'existing biliary stent'),),
         unlisted_ii=({'units': [unit_at(SCA1_TEXT, 'The existing biliary stent was removed')], 'what': 'act',
                       'kind': 'stent_removal', 'session': 'X1'},),
         held={'ii': {'43274': ('performed_status', 'act_target')}},
         expect={'i': {'43274': (H, 'performed_status', None, '4.3 XCHG: a possibly performed counterpart (the removal) '
                                                              'in the same duct: 43274 unmet (performed_status)')},
                 'ii': {'43274': (H, 'performed_status', Q, '3.2.6 rule 2: the unlisted removal\'s unit is the code\'s '
                                                            'evidence (RANK 2); XCHG reads the same removal as a '
                                                            'possibly performed counterpart in an unknown duct (D216), '
                                                            'its act_target a held fact too; never READY')}}),
    Case('RF-SCA1b', 'refutation', ('SC-A', 'D216'), 'D216: an unlisted removal in its own sentence beside a placement',
         SCA1B_TEXT, sca1b, variants=TWO, codes=(('43274', 'A new 10 Fr plastic biliary stent was placed'),),
         unlisted_ii=({'units': [unit_at(SCA1B_TEXT, 'The existing biliary stent was removed')], 'what': 'act',
                       'kind': 'stent_removal', 'session': 'X1'},),
         expect={'i': {'43274': (H, 'performed_status', None, '4.3 XCHG: the removal, performed in the same duct, is a '
                                                              'counterpart: 43274 unmet (performed_status)')},
                 'ii': {'43274': (H, 'act_target', Q, 'D216: XCHG reads the unlisted removal (3.2.6 rule 3\'s '
                                                      'synthetic doubted act, no duct) as a possibly performed '
                                                      'counterpart in an unknown duct: the duct asked (RANK 11, D225 '
                                                      'P6); no unlisted unit lies on the code\'s evidence, so rule 2 '
                                                      'does not hold it; never READY')}}),
    Case('RF-SCA2', 'refutation', ('SC-A', 'HO-6'), 'The biopsy-then-snare sentence', SCA2_TEXT, sca2, variants=TWO,
         codes=(('45380', 'biopsied'), ('45385', 'hot snare')),
         unlisted_ii=({'units': ['S5'], 'what': 'act', 'kind': 'biopsy', 'session': 'X1'},),
         expect={'i': {'45380': (H, 'performed_status', EXP, '4.7 biopsy_of_removed_lesion: bundled into the removal '
                                                             '(RANK 18)'),
                       '45385': (R, None, None, 'the hot snare removal')},
                 'ii': {'45380': (H, 'performed_status', Q, '3.2.6 rule 2: the unlisted act\'s unit is on the code\'s '
                                                            'evidence (RANK 2); never READY'),
                        '45385': (H, 'performed_status', Q, '3.2.6 rule 2: the same unit (RANK 2)')}}),
    Case('RF-SCA3', 'refutation', ('SC-A', 'HO-6'), 'A shared denial anchor', SCA3_TEXT, sca3, variants=TWO,
         codes=(('45380', 'Neither biopsy nor tattoo was performed', True),
                ('45381', 'Neither biopsy nor tattoo was performed', True)),
         unlisted_ii=({'units': ['S5'], 'what': 'denial', 'kind': 'tattoo', 'session': 'X1'},),
         expect={'i': {'45380': (X, None, None, '4.6 by citation (C-10\'s shared sentence)'),
                       '45381': (X, None, None, '4.6 by citation')},
                 'ii': {'45380': (H, 'performed_status', Q, '3.2.6 rule 2: an unlisted unit on the evidence: never '
                                                            'excluded (RANK 2)'),
                        '45381': (H, 'performed_status', Q, '3.2.6 rule 2 (RANK 2)')}}),
    Case('RF-SCB', 'refutation', ('SC-B',), 'A short place list beside a rectal denial', SCB_TEXT, scb, variants=TWO,
         codes=(('45380', 'Cold forceps biopsies'),),
         ii_rules=({'fact': 'pair@E2:E3:rectum', 'role': 'pair_control', 'verdict': 'supports', 'qualifiers': []},
                   {'fact': 'pair@E3:E2:rectum', 'role': 'pair_control', 'verdict': 'supports', 'qualifiers': []}),
         expect={'i': {'45380': (H, 'conflict:biopsy', Q, '4.5: the biopsies of the rectum and the rectal denial: '
                                                          'CONTRADICTION (RANK 1)')},
                 'ii': {'45380': (H, 'statement_scope', Q, '4.5 target row UNRESOLVED: a pair control pass 2 supports '
                                                           'is not rejected, so the short list is never apart (4.2 '
                                                           '[R:SC-B]); an UNRESOLVED target asks statement_scope (RANK '
                                                           '3)')}}),
    Case('RF-SCC', 'refutation', ('SC-C',), 'A balloon sphincteroplasty filed as a sphincterotomy', SCC_TEXT, scc,
         variants=THREE, codes=(('43262', 'Balloon sphincteroplasty'),), caught=('kind@E3/0',),
         expect={'i': {'43262': (H, 'performed_status', None, '4.4: no sphincterotomy: not documented (RANK 4)')},
                 'ii': {'43262': (H, 'performed_status', Q, 'SUPPORT row 1 unresolved (RANK 4)')}}),
    Case('RF-SCD', 'refutation', ('SC-D',), 'A nursing note with a summarizing impression', SCD_TEXT, scd, variants=TWO,
         codes=(('45385', 'Nursing note: A 5 mm'),), caught=('restatements.role@E2/0',),
         expect={'i': {'45385': (H, 'event_entry', EXP, 'a summarizes restatement moves no entry (1.5): the nursing '
                                                        'entry (RANK 5)')},
                 'ii': {'45385': (H, 'event_entry', EXP, '[R:SC-D] the restates role not established moves no entry: '
                                                         'the nursing entry, established (RANK 5)')}}),
    Case('RF-HO7', 'refutation', ('HO-7',), 'Two performers in one session', HO7_TEXT, ho7, variants=TWO,
         codes=(('45385', 'A 6 mm sessile polyp'),), caught=('performer@E3/0',),
         expect={'i': {'45385': (R, None, None, '4.5 performer row: the visiting surgeon\'s removal is apart; K2 never '
                                                'touches the examination (HO-7)')},
                 'ii': {'45385': (R, None, None, 'the team\'s own snare supports; the other act\'s performer touches '
                                                'no other act')}}),
    Case('RF-HO8a', 'refutation', ('HO-8',), 'A contradicted date on the act the item does not name', HO8A_TEXT, ho8a,
         variants=TWO, codes=(('45380', 'of the rectum were taken'),), caught=('entry@E3/0',),
         held={'i': {'45380': ('conflict:biopsy@E2',)}, 'ii': {'45380': ('conflict:biopsy@E2',)}},
         subjects={'i': {'45380': 'E3'}, 'ii': {'45380': 'E3'}},
         expect={'i': {'45380': (H, 'event_entry', EXP, '4.8 binding (1): the kept span selects the rectal biopsy; the '
                                                        'other candidate\'s contradicted date stays a held fact [R:HO-8]')},
                 'ii': {'45380': (H, 'event_entry', Q, '4.8 binding (1): the kept span selects the rectal biopsy, whose '
                                                       'entry pass 2 did not establish (RANK 5, a question); every '
                                                       'candidate\'s witnesses kept [R:HO-8]')}}),
    Case('RF-HO8b', 'refutation', ('HO-8',), 'Two dilations at two sites: the esophageal one\'s device asked',
         HO8B_TEXT, ho8b, variants=TWO, codes=(('43249', 'Findings: The gastroscope'),),
         caught=('technique.device@E2/0',), subjects={'i': {'43249': 'E2'}},
         expect={'i': {'43249': (H, 'technique', Q, '4.3 TECH on the esophageal dilation, whose device is not stated '
                                                    '(RANK 10); the duodenal bulb dilation lies outside 43249\'s SITE '
                                                    'class, so its code rows never read it (D29, D240)')},
                 'ii': {'43249': (H, 'technique', Q, 'the device unresolved (RANK 10)')}}),
    Case('RF-HO9', 'refutation', ('HO-9',), 'A reach given both polarities', HO9_TEXT, ho9, variants=TWO,
         codes=(('45378', 'colonoscope'),), caught=('reached@X1/0',), known={'i': {'45378': (H, 'conflict:examination', 'R-K8')}},
         expect={'i': {'45378': (H, 'conflict:examination', Q, '3.1 K8 [R:HO-9]: a reach given both polarities is '
                                                               'contradicted, and a contradicted required fact asks '
                                                               'RANK 1 (4.8)')},
                 'ii': {'45378': (H, 'extent', Q, 'COLFULL unresolved (RANK 14)')}}),
    Case('RF-CO3', 'refutation', ('CO-3',), 'A hard-wrapped denial (GI Note #8\'s shape)', CO3_TEXT, co3,
         variants=TWO, provenance=SHAPE.format('fresh/inputs/A/note8.txt'),
         codes=(('45380', 'No biopsies\nwere taken', True),), caught=('status@E2/0',),
         expect={'i': {'45380': (X, None, None, '1.2 rule 2: the wrap is joined, so the negator is in the unit; 4.6 by '
                                                'citation')},
                 'ii': {'45380': (H, 'performed_status', Q, 'SUPPORT row 2 unresolved (RANK 4): never excluded, never '
                                                            'READY')}}),
    Case('RF-CO6', 'refutation', ('CO-6', 'D36'), 'An examination told across three parts', CO6_TEXT, co6,
         variants=TWO, codes=(('45378', 'The colonoscope was inserted'),), caught=('reached@X1/0',),
         expect={'i': {'45378': (H, 'base_included', EXP, 'G5 accepts the reach told in the impression\'s restatement '
                                                          '(COLFULL met); the cecal biopsy is a reportable act')},
                 'ii': {'45378': (H, 'extent', Q, 'G5: a reach cited only from the biopsy\'s sentence is inferred '
                                                  '(D36): COLFULL unresolved (RANK 14)')}}),
    Case('RF-CO4', 'refutation', ('CO-4', 'CO-5'), 'PAIR-4-W2: the wrapped "At / this examination"', D.PAIR4, pair4,
         header=PAIR4_HEADER, variants=TWO, provenance=dev('PAIR4'),
         codes=(('45390', 'I resected'), ('45381', 'placed a tattoo')),
         caught=('date_relation@E2/0', 'performer@E2/0'),
         expect={'i': {'45390': (R, None, None, 'the EMR today; its saline lift bundled (lift_for)'),
                       '45381': (H, 'performed_status', EXP, '4.7 lift_injection: the lift is part of the resection; the '
                                                             'tattoo is another date and performer')},
                 'ii': {'45390': (R, None, None, 'unchanged'),
                        '45381': (H, 'performed_status', EXP, '4.4: the lift supports the code, so the tattoo\'s witnesses '
                                                              'are not recorded; the lift stays bundled')}}),
    Case('RF-CO7', 'refutation', ('CO-7',), 'fb08: two denials, distinct cards', D.FB08, fb08, header=FB08_HEADER,
         variants=THREE, provenance=dev('FB08'), codes=(('45385', 'none was performed today either', True),),
         caught=('date_relation@E3/0',),
         expect={'i': {'45385': (X, None, None, '4.6: today\'s broad denial, cited (the cards differ by status words, '
                                                'CO-7)')},
                 'ii': {'45385': (X, None, None, '4.6 condition 2: the status negated is the deciding fact, established '
                                                '(today or earlier, either excludes); cited')}}),
    Case('RF-CO1', 'refutation', ('CO-1', 'W1S-499'), 'W1S-499: a finding against an act, a conflict doubt',
         D.W1S499, co1, header=W1S_HEADER, variants=TWO, provenance=dev('W1S499'),
         codes=(('43251', 'Gastric body polyp removed'),), caught=('status@E14/0',),
         expect={'i': {'43251': (H, 'conflict:snare', Q, '2.2 BF24 and 3.3 row 2: the conflict doubt ("Body and fundus '
                                                         'normal" against item 7) contradicts the removal\'s status '
                                                         '[R:CO-1]: RANK 1, both statements quoted')},
                 'ii': {'43251': (H, 'performed_status', Q, 'SUPPORT row 2: the status pass 2 contradicts, unresolved '
                                                            '(RANK 4); never READY')}}),
    Case('RF-CO2a', 'refutation', ('CO-2', 'f2-after-002'), 'f2-after-002: a placing sentence after the act',
         D.F2AFTER002, co2a, header=F2AFTER_HEADER, variants=TWO, provenance=dev('F2AFTER002'),
         codes=(('45385', 'cold snare'),), caught=('date_relation@E2/0', 'performer@E2/0'),
         expect={'i': {'45385': (H, 'statement_scope', Q, '2.2 BF22: another date and facility established by the '
                                                          'placing sentence, so no positive candidate; the code cites '
                                                          'the whole removal sentence, more than its kind, status, '
                                                          'target and timing words (4.6 condition 4): statement_scope '
                                                          '(RANK 3), never READY')},
                 'ii': {'45385': (H, 'event_time', Q, 'SUPPORT rows 3 and 4: the inherited today and team, contradicted '
                                                      'by pass 2, unresolved; RANK 6 first')}}),
    Case('RF-CO2b', 'refutation', ('CO-2', 'twins-015'), 'twins-015: an indication that places the procedure elsewhere',
         D.TWINS015, co2b, header=TWINS015_HEADER, variants=TWO, provenance=dev('TWINS015'),
         codes=(('43239', 'cold forceps biopsies'),), caught=('date_relation@E2/0', 'performer@E2/0'),
         expect={'i': {'43239': (H, 'statement_scope', Q, '2.2 BF23 and 1.5: the Procedure part\'s placed occasion and '
                                                          'performer are inherited, so the biopsy is a statement of '
                                                          'another date and facility (no positive candidate), cited '
                                                          'partly (4.6 condition 4): statement_scope (RANK 3), never '
                                                          'READY')},
                 'ii': {'43239': (H, 'event_time', Q, 'SUPPORT rows 3 and 4: the inherited date line and team, '
                                                      'contradicted by pass 2, unresolved; RANK 6 first')}}),
    Case('RF-CO2c', 'refutation', ('CO-2', 'W1S-222'), 'W1S-222: a plan sentence that places the narratives above',
         D.W1S222, co2c, header=W1S_HEADER, variants=TWO, provenance=dev('W1S222'),
         codes=(('45385', 'removed en bloc'),), caught=('date_relation@E7/0',),
         expect={'i': {'45385': (H, 'statement_scope', Q, '1.5: the colonoscopy part\'s earlier date, placed by the '
                                                          'plan\'s sentence, is inherited, so the removal is a statement '
                                                          'of an earlier date (no positive candidate), cited partly (4.6 '
                                                          'condition 4): statement_scope (RANK 3), never READY')},
                 'ii': {'45385': (H, 'performed_status', Q, '4.3 row 7 (as 4a-2 builds it; the refutation\'s P11): the '
                                                            'plan\'s "No endoscopy was done today", its session not '
                                                            'stated, may be the colonoscopy\'s examination, established '
                                                            'not done (RANK 4); the caught date relation, contradicted by '
                                                            'pass 2, stays a held fact (event_time, RANK 6); never READY')}},
         held={'ii': {'45385': ('event_time@E7',)}}),
    Case('RF-CO2d', 'refutation', ('CO-2', 'C2MEM-031', 'D241'), 'C2MEM-031: a sentence that places the part above it',
         D.C2MEM031, co2d, header=NOTE8_HEADER, variants=THREE, provenance=dev('C2MEM031'), codes=N8_CODES,
         caught=('date_relation@E3/0', 'date_relation@E4/0'),
         shared=co2d_no_place, shared_omits=N8_TATTOO_TARGETS,
         acts={'i': {'45381': ('E18',)}}, considerations={'i': {'45381': ('59|XS',)}},
         named={'i': (N8B,)},
         # round r3's silent-link rule (DESIGN-v2 b.8, DECISIONS D308 Q-B; declared at round r3's integration), as
         # CK-note8's: the engine alone holds 45381 on the tattoo's unstated part link until Fable's proven answer
         declared={'i': {'45381': (H, 'act_part', 'B8')}, 'ii': {'45381': (H, 'act_part', 'B8')}},
         note='D241, as CK-note8: (i) files the tattoo faithfully and gives 45381 READY; the filing with no place and no '
              'lesion is kept only as variant (iii), a residual, never a pass. The anastomosis part\'s acts are the '
              'index colonoscopy\'s, so no question on the rim biopsy stands beside the documented outcome; Q-N8b (D244, '
              'as built) is its one named residual.',
         expect={'i': {'45378': (H, 'base_included', EXP, '4.7 base_included (b): today\'s reportable acts (RANK 21)'),
                       '45380': (R, None, None, 'today\'s ileal, transverse and rectosigmoid biopsies (CK-note8); the '
                                                'rim biopsies are the index colonoscopy\'s'),
                       '45381': (R, None, None, 'as CK-note8 (D241): the faithfully filed tattoo is apart from the '
                                                'resection-bed denial by place and by lesion (4.5)'),
                       '45385': (R, None, None, 'as CK-note8'),
                       '45386': (H, 'statement_scope', Q, '1.5 and CO-2: the placing sentence gives the anastomosis '
                                                          'part the index colonoscopy\'s earlier date, so the dilation '
                                                          'is a statement of another date (no positive candidate), '
                                                          'cited partly (4.6 condition 4): statement_scope (RANK 3), '
                                                          'never READY'),
                       '45390': (R, None, None, 'as CK-note8')},
                 'ii': {'45378': (H, 'base_included', EXP, 'unchanged'),
                        '45380': (R, None, None, 'unchanged: today\'s other biopsies support it'),
                        '45381': (R, None, None, 'unchanged (D241): the misfiled placement touches no tattoo'),
                        '45385': (R, None, None, 'unchanged'),
                        '45386': (H, 'event_time', Q, 'SUPPORT row 3: the dilation\'s inherited date line, contradicted '
                                                      'by pass 2, unresolved (RANK 6); never READY'),
                        '45390': (R, None, None, 'unchanged')}}),
]
