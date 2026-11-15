"""The owner's checklist examples (FINAL-V2 9.5; the 2026-11-09 directive's checklist: "the original seven cases and the
four reported Gemini slips, particularly unsupported historical extent and biopsy-site conflation ... the scar example,
historical/current acts, different lesions at one site, technique-specific denials, different performers, future
purpose and guidewire-versus-scope extent. Preserve genuine contradictions"), each as (i) and (ii). The original cases
v1-v6 are the FRESH-1 set A development documents themselves (devdocs.py); GI Note #8, the seventh, is the refutation's
CO-3 case (cases_refutation.py). The rest are written for these fixtures."""
from __future__ import annotations

from tests.fixtures.interpretation_v2 import devdocs as D
from tests.fixtures.interpretation_v2.build import Case
from tests.fixtures.interpretation_v2.cases_s4 import (COLO_FINDINGS, EGD_FINDINGS, EXP, NEG, OTHER, SNARE_LINE, H, Q,
                                                       R, X, colo, egd, head, polyp, snare)
from tests.fixtures.interpretation_v2.dsl import Note

TWO = ('i', 'ii')
NOV9 = dict(dos='2026-11-09', dos_line='Date of service: November 9, 2026', dos_words='November 9, 2026')


def dev(name: str) -> str:
    path, digest = D.SOURCES[name]
    return f'development: fresh/inputs/{path} (sha256 {digest}), verbatim'


def sections(n: Note, *labels: tuple) -> list:
    out = [n.opening()]
    for number, (label, role, occasion) in enumerate(labels, start=1):
        out.append(n.part(f'N{number}', label, role, occasion=occasion))
    return out


def colonoscopy(n: Note, exam_words: str, reached: list, events: tuple, parts: tuple, **kw: object) -> dict:
    session_fields = dict(kw.pop('session_fields', {}))
    return n.answer(sections=sections(n, *parts),
                    sessions=[n.session('X1', 'colonoscopy', 'colonoscope', exam='E1', reached=reached,
                                        **session_fields)],
                    events=[n.event('E1', 'examination', exam_words, 'advanced' if 'advanced' in exam_words else
                                    'was advanced', anchor_words=exam_words, session='X1'), *events], **kw)


V_PARTS = (('Indication:', 'indication', None), ('Procedure:', 'procedure', 'today'), ('Findings:', 'findings', 'today'),
           ('Impression:', 'impression', 'today'))


def v1(n: Note, mis: bool) -> dict:
    return colonoscopy(
        n, 'The colonoscope was advanced', [('cecum', 'advanced to the cecum')],
        (n.event('E2', 'snare', 'cold snare', 'was removed en bloc', session='X1', lesion=('L1', 'This polyp'),
                 places=[('sigmoid_colon', 'In the sigmoid colon at 25 cm')], device=('cold_snare', 'cold snare'),
                 restatements=[('the 6 mm polyp removed with a cold snare', 'summarizes')]),
         n.event('E3', 'biopsy', 'Cold forceps biopsies', 'were taken', session='X1',
                 lesion=('L1' if mis else 'L2', 'from it'), device=('cold_forceps', 'Cold forceps'),
                 places=[('sigmoid_colon', 'in the sigmoid colon at 30 cm')]),
         n.event('E4', 'snare', 'snared', 'was not snared', session='X1', status_state=NEG,
                 breadth=('single_target', 'The second polyp'), lesion=('L2', 'The second polyp'))),
        V_PARTS, lesions=[polyp(n, words='6 mm sessile polyp', place=('sigmoid_colon', 'In the sigmoid colon at 25 cm')),
                          n.lesion('L2', 'A second polyp, 3 mm and flat', multiplicity=('single', 'A second polyp'),
                                   places=[('sigmoid_colon', 'in the sigmoid colon at 30 cm')],
                                   distinct_from=[('L1', 'A second polyp')])])


V2_PARTS = (('Procedure:', 'procedure', 'today'), ('Findings:', 'findings', 'today'), ('Impression:', 'impression', 'today'))


def v2(n: Note, mis: bool) -> dict:
    return colonoscopy(
        n, 'The colonoscope was advanced', [('cecum', 'advanced to the cecum')],
        (n.event('E2', 'snare', 'cold snare', 'was removed in one piece', session='X1', lesion=('L1', 'The polyp'),
                 places=[('descending_colon', 'in the descending colon at 40 cm')],
                 device=('hot_snare' if mis else 'cold_snare', 'cold snare')),
         n.event('E3', 'snare', 'hot snare', 'were used', session='X1', status_state=NEG,
                 breadth=('single_target', 'on this polyp'), lesion=('L1', 'this polyp'),
                 device=('hot_snare', 'No hot snare')),
         n.event('E4', 'injection', 'submucosal injection', 'no submucosal injection was given', session='X1',
                 status_state=NEG, breadth=('single_target', 'on this polyp'), lesion=('L1', 'this polyp'))),
        V2_PARTS, lesions=[polyp(n, words='A 9 mm sessile polyp',
                                 place=('descending_colon', 'in the descending colon at 40 cm'))])


V3_PARTS = (('History:', 'history', None), ('Procedure:', 'procedure', 'today'), ('Impression:', 'impression', 'today'))


def v3(n: Note, mis: bool) -> dict:
    relation = ('on_date_of_service' if mis else 'earlier_date', 'At the 2024 colonoscopy')
    return colonoscopy(
        n, 'The colonoscope was advanced', [('anastomosis', 'advanced to the ileocolonic anastomosis')],
        (n.event('E2', 'dilation', 'no dilation', 'no dilation was performed', session='X1', status_state=NEG,
                 date_relation=relation, places=[('anastomosis', 'the anastomosis was narrowed')]),
         n.event('E3', 'dilation', 'was dilated', 'was dilated', session='X1',
                 device=('balloon', 'through-the-scope balloon'), date_relation=('on_date_of_service', 'today'),
                 places=[('anastomosis', 'The anastomotic stricture')], structure=('stricture', 'anastomotic stricture'))),
        V3_PARTS, anatomy=[n.anatomy('Y1', ('anastomosis', 'ileocolonic anastomosis'),
                                     subtype=('ileocolic', 'ileocolonic anastomosis'))],
        session_fields=dict(reached_anatomy=('Y1', 'advanced to the ileocolonic anastomosis')))


V4_PARTS = (('History:', 'history', None), ('Procedure:', 'procedure', 'today'), ('Findings:', 'findings', 'today'),
            ('Impression:', 'impression', 'today'))


def v4(n: Note, mis: bool) -> dict:
    events = [n.event('E2', 'removal', 'No polypectomy', 'No polypectomy was performed', session='X1', status_state=NEG,
                      breadth=('all_of_kind', 'No polypectomy'), date_relation=('earlier_date', 'at the 2024 colonoscopy')),
              n.event('E4', 'snare', 'cold snare', 'was removed', session='X1', lesion=('L1', 'A 6 mm sessile polyp'),
                      places=[('sigmoid_colon', 'sigmoid colon')], device=('cold_snare', 'cold snare'))]
    if not mis:
        events.append(n.event('E3', n.fact('removal', n.src('No polypectomy', 'antecedent')), 'This time as well',
                              'This time as well', session='X1', status_state=NEG,
                              breadth=('all_of_kind', 'This time as well'),
                              date_relation=('on_date_of_service', 'This time as well')))
    return colonoscopy(n, 'The colonoscope was advanced', [('cecum', 'advanced to the cecum')], tuple(events), V4_PARTS,
                       lesions=[polyp(n)])


V5_PARTS = (('History:', 'history', None), ('Procedure:', 'procedure', 'today'), ('Impression:', 'impression', 'today'))


def v5(n: Note, mis: bool) -> dict:
    when = ('on_date_of_service', 'In 2024') if mis else ('earlier_date', 'In 2024')
    who = ('documenting_team', 'removed a 12 mm polyp') if mis else ('other_clinician', 'Dr. Lucas Alvarez')
    return colonoscopy(
        n, 'I advanced the colonoscope', [('cecum', 'colonoscope to the cecum')],
        (n.event('E2', 'snare', 'hot snare', 'removed', session='X1', date_relation=when, performer=who,
                 places=[('ascending_colon', 'from the ascending colon')], device=('hot_snare', 'hot snare')),
         n.event('E3', 'biopsy', 'biopsies', 'took cold', session='X1',
                 places=[('ascending_colon', 'ascending colon polypectomy scar')]),
         n.event('E4', 'removal', 'polyp was removed', 'No polyp was removed today', session='X1', status_state=NEG,
                 breadth=('all_of_kind', 'No polyp was removed today'), date_relation=('on_date_of_service', 'today'))),
        V5_PARTS)


V6_PARTS = (('History:', 'history', None), ('Procedure:', 'procedure', 'today'), ('Impression:', 'impression', 'today'))


def v6(n: Note, mis: bool) -> dict:
    if mis:
        reached, fields = [('neo_terminal_ileum', 'into the neo-terminal ileum')], {}
    else:
        reached = [('anastomosis', 'advanced to the ileocolic anastomosis')]
        fields = dict(reached_anatomy=('Y1', 'advanced to the ileocolic anastomosis'),
                      device_reached=[('neo_terminal_ileum', 'into the neo-terminal ileum')])
    return colonoscopy(
        n, 'The colonoscope was advanced', reached,
        (n.event('E2', 'dilation', 'balloon dilated', 'dilated the anastomosis', session='X1',
                 device=('balloon', 'through-the-scope balloon'), places=[('anastomosis', 'dilated the anastomosis')]),),
        V6_PARTS, anatomy=[n.anatomy('Y1', ('anastomosis', 'ileocolic anastomosis'),
                                     subtype=('ileocolic', 'ileocolic anastomosis'))],
        session_fields=fields)


HIST_TEXT = head('COLONOSCOPY REPORT') + (
    'History: A prior colonoscopy in 2028 reached the cecum.\n'
    'Findings: The colonoscope was advanced to the transverse colon.\n'
    'The examination was stopped there because of poor preparation.\n')


def hist(n: Note, mis: bool) -> dict:
    reached = [('cecum', 'reached the cecum', OTHER)] if mis else [('transverse_colon', 'to the transverse colon')]
    return n.answer(sections=[n.opening(), n.part('N1', 'History:', 'history', occasion=None),
                              n.part('N2', 'Findings:', 'findings')],
                    sessions=[n.session('X1', 'colonoscopy', 'colonoscope', exam='E1', reached=reached,
                                        completion=('incomplete', 'The examination was stopped there', OTHER))],
                    events=[n.event('E1', 'examination', 'colonoscope', 'was advanced', session='X1')])


FUTURE_TEXT = head('UPPER ENDOSCOPY REPORT') + EGD_FINDINGS + (
    'Cold forceps biopsies of the gastric antrum were taken.\n'
    'Balloon dilation of the pylorus is planned in four weeks.\n')


def future(n: Note, mis: bool) -> dict:
    plan = n.event('E3', 'dilation', 'Balloon dilation', 'is planned', session='X2', status='performed' if mis else 'planned',
                   date_relation=('on_date_of_service' if mis else 'later_date', 'in four weeks'),
                   places=[('pylorus', 'of the pylorus')], device=('balloon', 'Balloon dilation'))
    return egd(n, n.event('E2', 'biopsy', 'Cold forceps biopsies', 'were taken', session='X1',
                          places=[('gastric_antrum', 'gastric antrum')], device=('cold_forceps', 'Cold forceps')), plan,
               sessions=(n.session('X2', 'egd', 'Balloon dilation of the pylorus',
                                   encounter=('separate_encounter', 'in four weeks', 'other_statement')),))


BROAD_TEXT = head('COLONOSCOPY REPORT') + COLO_FINDINGS + SNARE_LINE + 'No polyp was removed today.\n'


def broad(n: Note, mis: bool) -> dict:
    scope_fields = dict(breadth=('single_target', 'No polyp'), places=[('rectum', 'No polyp')]) if mis else \
        dict(breadth=('all_of_kind', 'No polyp was removed today'))
    return colo(n, snare(n), n.event('E3', 'removal', 'polyp was removed', 'No polyp was removed today',
                                     anchor_words='No polyp was removed today', session='X1', status_state=NEG,
                                     date_relation=('on_date_of_service', 'today'), **scope_fields),
                lesions=(polyp(n),))


CASES = [
    Case('CK-v1', 'checklist', ('original v1', 'different lesions at one site', 'biopsy-site conflation'),
         'Two lesions at one site; the biopsy-site conflation slip', D.V1, v1, header=dict(NOV9, clinician='Priya Nandakumar'),
         variants=TWO, provenance=dev('V1'), codes=(('45385', 'cold snare'), ('45380', 'Cold forceps biopsies')),
         caught=('target.lesion@E3/0',),
         expect={'i': {'45385': (R, None, None, '4.5 target row: the denial is of the other lesion (distinct, pair '
                                                'controls rejected): INDEPENDENT'),
                       '45380': (R, None, None, 'a biopsy of the lesion left in place: no bundling')},
                 'ii': {'45385': (R, None, None, 'unchanged'),
                        '45380': (H, 'act_target', Q, '4.7 biopsy_of_removed_lesion on an unknown lesion identity: '
                                                      'asked (RANK 17), never bundled silently')}}),
    Case('CK-v2', 'checklist', ('original v2', 'technique-specific denials'), 'Technique-specific denials beside a cold '
         'snare', D.V2, v2, header=dict(NOV9, clinician='Tomas Rivera-Lind'), variants=TWO, provenance=dev('V2'),
         codes=(('45385', 'cold snare'),), caught=('technique.device@E2/0',),
         expect={'i': {'45385': (R, None, None, '4.5 technique row (C-16): a hot snare denial and a cold snare are '
                                                'disjoint devices: INDEPENDENT')},
                 'ii': {'45385': (H, 'technique', Q, '4.5 technique row UNRESOLVED (RANK 10)')}}),
    Case('CK-v3', 'checklist', ('original v3', 'historical and current acts', 'HO-2'), 'A historical denial beside a '
         'current act', D.V3, v3, header=dict(NOV9, clinician='Helena Varga'), variants=TWO, provenance=dev('V3'),
         codes=(('45386', 'was dilated'),), caught=('date_relation@E2/0',), known={'i': {'45386': (R, None, 'R-ANAT')}},
         expect={'i': {'45386': (R, None, None, '4.5 timing row: the 2024 denial is another date (INDEPENDENT); '
                                                'COLFULL by the ileocolic anastomosis reached (D38)')},
                 'ii': {'45386': (H, 'event_time', Q, '4.5 timing row UNRESOLVED (RANK 6)')}}),
    Case('CK-v4', 'checklist', ('original v4', 'genuine contradictions'), '"This time as well" beside today\'s snare',
         D.V4, v4, header=dict(NOV9, clinician='Daniel Achterberg'), variants=TWO, provenance=dev('V4'),
         codes=(('45385', 'cold snare'),),
         unlisted_ii=({'units': ['S6'], 'what': 'denial', 'kind': 'removal', 'session': 'X1'},),
         expect={'i': {'45385': (H, 'conflict:snare', Q, '4.5: "This time as well" denies today\'s polypectomy: a genuine '
                                                         'CONTRADICTION, preserved (RANK 1)')},
                 'ii': {'45385': (H, 'performed_status', Q, '3.2.6 rule 4: the unlisted denial pairs UNRESOLVED (RANK '
                                                            '2, D228)')}}),
    Case('CK-v5', 'checklist', ('original v5', 'the scar', 'different performers', '"No polyp was removed today."'),
         'The scar, a previous surgeon, and "No polyp was removed today."', D.V5, v5,
         header=dict(NOV9, clinician='Grace Okafor'), variants=TWO, provenance=dev('V5'),
         codes=(('45380', 'biopsies from it'), ('45385', 'No polyp was removed today', True)),
         caught=('date_relation@E2/0', 'performer@E2/0'),
         expect={'i': {'45380': (R, None, None, 'the scar biopsy, today, by the team'),
                       '45385': (X, None, None, '4.6: the broad denial, cited, decides; the 2024 removal is another '
                                                'date and performer, so nothing doubts the kind')},
                 'ii': {'45380': (H, 'act_target', Q, '4.7 biopsy_of_removed_lesion: a removal possibly today at the '
                                                      'scar\'s place, lesion identity unknown: asked (RANK 17)'),
                        '45385': (H, 'event_time', Q, '4.6 condition 5: the removal possibly today by the team: never '
                                                      'excluded; SUPPORT row 3 unresolved (RANK 6)')}}),
    Case('CK-v6', 'checklist', ('original v6', 'guidewire-versus-scope extent', 'CO-8'), 'A guidewire\'s reach is not '
         'the scope\'s', D.V6, v6, header=dict(NOV9, clinician='Mei-Lin Castellanos'), variants=TWO, provenance=dev('V6'),
         codes=(('45386', 'balloon dilated'),), caught=('reached@X1/0',), known={'i': {'45386': (R, None, 'R-ANAT')}},
         expect={'i': {'45386': (R, None, None, 'COLFULL by the ileocolic anastomosis reached after a right '
                                                'hemicolectomy (D38, D44); the guidewire\'s point is device_reached, read '
                                                'by no rule [R:CO-8]')},
                 'ii': {'45386': (H, 'extent', Q, 'the guidewire\'s point cited from the dilation\'s sentence fails G5 '
                                                  '(extent_inferred): COLFULL unresolved (RANK 14)')}}),
    Case('CK-hist', 'checklist', ('unsupported historical extent',), 'A historical reach is not today\'s extent',
         HIST_TEXT, hist, variants=TWO, codes=(('45378', 'colonoscope'),), caught=('reached@X1/0',),
         considerations={'i': {'45378': ('52|53',)}},
         expect={'i': {'45378': (R, None, None, '4.3 COLFULL established otherwise: completion incomplete beside a '
                                                'supported reach, the 52/53 consideration')},
                 'ii': {'45378': (H, 'extent', Q, 'the historical reach cited for today, contradicted: COLFULL '
                                                  'unresolved (RANK 14)')}}),
    Case('CK-future', 'checklist', ('future purpose (C-13)',), 'A planned dilation never supports, and a cited plan '
         'excludes', FUTURE_TEXT, future, variants=TWO,
         codes=(('43245', 'Balloon dilation', True), ('43239', 'Cold forceps biopsies')),
         caught=('status@E3/0',),
         expect={'i': {'43245': (X, None, None, '4.6 condition 2: a supported plan decides (C-13), cited'),
                       '43239': (R, None, None, 'SUPPORT met')},
                 'ii': {'43245': (H, 'performed_status', Q, 'SUPPORT row 2: the plan filed as an act whose status '
                                                            'pass 2 did not establish is a positive candidate (4.2 '
                                                            '[R:HO-1]): RANK 4, a question; never excluded'),
                        '43239': (R, None, None, 'unchanged')}}),
    Case('CK-broad', 'checklist', ('"No polyp was removed today."', 'genuine contradictions'), 'A broad denial beside a '
         'snare', BROAD_TEXT, broad, variants=TWO, codes=(('45385', 'cold snare'),),
         caught=('scope.breadth@E3/0', 'target.places@E3/0'),
         expect={'i': {'45385': (H, 'conflict:snare', Q, '4.10: the broad denial contradicts the snare (RANK 1)')},
                 'ii': {'45385': (H, 'statement_scope', Q, '4.5 breadth and target rows UNRESOLVED (RANK 3)')}}),
]


# --- GI Note #8, the owner's original seventh case, verbatim (devdocs.NOTE8) ----------------------------------------

NOTE8_HEADER = dict(dos='2026-11-08', dos_line='Date of service: November 8, 2026', dos_words='November 8, 2026',
                    clinician='E. Morgan')
N8_PARTS = (('Clinical indication and interval history', 'history', None),
            ('Pertinent records reviewed before the examination', 'history', None),
            ('Preprocedure evaluation and consent', 'other', 'today'),
            ('Anesthesia, equipment, and quality measures', 'sedation', 'today'),
            ('Procedure technique and chronological findings', 'procedure', 'today'),
            ('Ileocolonic anastomosis and balloon dilation', 'findings', 'today'),
            ('Neo-terminal ileum and segmental mucosal sampling', 'findings', 'today'),
            ('Distal transverse colon: endoscopic mucosal resection', 'findings', 'today'),
            ('Splenic flexure: unresected lesion and localization tattoo', 'findings', 'today'),
            ('Descending colon: separate cold-snare polypectomy', 'findings', 'today'),
            ('Remaining colon, rectum, and retroflexion', 'findings', 'today'),
            ('Specimens submitted', 'specimens', 'today'),
            ('Technical outcome and immediate complications', 'complications', 'today'),
            ('Postprocedure impression', 'impression', 'today'),
            ('Recovery instructions and management plan', 'plan', None),
            ('Attestation', 'signature', 'today'))


def note8(n: Note, mis: bool) -> dict:
    return gi_note8(n, mis)


def note8_no_place(n: Note) -> dict:
    """GI Note #8 with the tattoo filed with no place and no lesion, and the resection-bed denial with its place alone:
    the shared misreading D241 keeps only as variant (iii)."""
    return gi_note8(n, False, tattoo='no_place')


def gi_note8(n: Note, mis: bool, index: bool = False, tattoo: str = 'faithful') -> dict:
    """GI Note #8's right filing (the owner's checklist: the original seventh case). One colonoscopy X1 today, to the
    ileocolonic anastomosis and, after the dilation, into the neo-terminal ileum (completion and reach told in the
    equipment and neo-terminal-ileum sentences, which anchor no act: CO-6), and its anatomy entry Y1 (the ileocolic
    anastomosis); today's acts - the digital rectal examination, the rim, ileal, transverse and rectosigmoid biopsies,
    the balloon dilation, the saline lift and the piecemeal EMR with its contact coagulation, soft coagulation and
    prophylactic clips, the localization tattoo, the cold snare removal - and its denials, each one event per denied act
    with that act's own words (the wrapped ones each one unit: CO-3); the history's 2024 colonoscopy (its removal, its
    "No dilation") and 2023 outside EGD (its dilation and biopsies), sessions of their own; and the EGD denied for the
    date of service, a denied procedure of another kind than the colonoscopy it is told in, filed as step 2a's pass-1
    instruction says (DECISIONS D244, Q-N8 option (b)): the examination, negated, of an EGD session X4 of its own, never
    with its session empty (an empty session would make it possibly X1's examination, 4.3 row 7). The misfiling reads
    the splenic-flexure denial as covering every biopsy, snare, ablation and dilation of the session (breadth
    all_of_kind, its lesion dropped).

    ``tattoo`` (DECISIONS D241): 'faithful' files the localization tattoo E18 with both readings D241 names as
    faithful - its place, the descending colon ("approximately 4 cm distal (toward the anus) to the splenic-flexure
    lesion": the place injected, never the reference point measured from, TARGETS and S4's BF8), and its lesion L2, the
    splenic-flexure lesion its statement names and its restatement says it "marked" - and the resection-bed denial E19
    on lesion L1, whose resection bed it names (TARGETS: a place named after an earlier act done there is a place or a
    lesion), beside its place; each established difference alone sets the denial apart (4.5 [R:HO-2]). 'no_place' is
    the filing D241 keeps only as variant (iii): the tattoo with no place and no lesion, the denial with its place
    alone.

    ``index``: C2MEM-031, the same document with one sentence more after the anastomosis part - "Those were the findings
    at her index colonoscopy." - which places that part's acts (the rim biopsies, the dilation, the stent denial) at the
    index colonoscopy: the part's occasion earlier_date, link placing (CO-2), its acts a session X5 of their own
    (separate_encounter). Its misfiling leaves the part on the date line (the splenic-flexure denial filed right)."""
    if tattoo not in ('faithful', 'no_place'):
        raise ValueError(tattoo)
    marked = tattoo == 'faithful'
    placed = index and not mis
    sections = [n.opening()]
    for number, (label, role, occasion) in enumerate(N8_PARTS, start=1):
        if placed and label == 'Ileocolonic anastomosis and balloon dilation':
            occasion = ('earlier_date', 'Those were the findings at her index colonoscopy', 'placing')
        sections.append(n.part(f'N{number}', label, role, occasion=occasion,
                               performer=None if occasion is None else 'team'))
    anastomosis_session = 'X5' if placed else 'X1'
    earlier24, earlier23, outside = ('earlier_date', 'from January 2024'), ('earlier_date', 'in March 2023'), \
        ('other_facility', 'An outside upper endoscopy')
    sessions = [
        n.session('X1', 'colonoscopy', 'The colonoscope was introduced', exam='E1',
                  reached=[('anastomosis', 'ileocolonic anastomosis'),
                           ('neo_terminal_ileum', 'The neo-terminal ileum was examined')],
                  completion=('complete', 'completion of the examination was confirmed'),
                  reached_anatomy=('Y1', 'ileocolonic anastomosis')),
        n.session('X2', 'colonoscopy', 'A colonoscopy from January 2024', exam='E26',
                  encounter=('separate_encounter', 'from January 2024')),
        n.session('X3', 'egd', 'An outside upper endoscopy', exam='E29',
                  encounter=('separate_encounter', 'performed in March 2023')),
        n.session('X4', 'egd', 'esophagogastroduodenoscopy or other upper', exam='E32')]
    if placed:
        sessions.append(n.session('X5', 'colonoscopy', 'her index colonoscopy',
                                  encounter=('separate_encounter', 'her index colonoscopy', 'other_statement')))
    splenic = dict(breadth=('all_of_kind', 'was performed on')) if mis and not index else \
        dict(breadth=('single_target', 'this splenic-flexure lesion'), lesion=('L2', 'this splenic-flexure lesion'),
             places=[('splenic_flexure', 'this splenic-flexure lesion')])
    denied_here = 'No biopsy, snare resection, ablation, or balloon dilation'
    events = [
        n.event('E1', 'examination', 'The colonoscope was introduced', 'introduced through the anus', session='X1'),
        n.event('E2', 'examination', 'Digital rectal examination', 'Digital rectal examination showed', session='X1',
                device=('manual', 'Digital rectal examination')),
        n.event('E3', 'biopsy', 'cold-forceps mucosal biopsies', 'were taken', session=anastomosis_session,
                places=[('anastomosis', 'anastomotic rim')], device=('cold_forceps', 'cold-forceps'),
                restatements=[('mucosa at the ileocolonic anastomotic rim, cold-forceps biopsies', 'summarizes')]),
        n.event('E4', 'dilation', 'controlled radial expansion balloon', 'The balloon was inflated sequentially',
                session=anastomosis_session,
                anchor_units=[n.u('controlled radial expansion balloon'), n.u('The balloon was inflated')],
                lesion=('L5', 'anastomotic narrowing'), places=[('anastomosis', 'anastomotic narrowing')],
                structure=('stricture', 'anastomotic narrowing'),
                device=('balloon', 'controlled radial expansion balloon'),
                restatements=[('The anastomotic narrowing was successfully dilated', 'summarizes'),
                              ('balloon dilation to 15 mm', 'summarizes')]),
        n.event('E5', 'stent', 'colonic\nstent', 'No colonic\nstent was placed', session=anastomosis_session,
                status_state=NEG, **({} if placed else dict(breadth=('all_of_kind', 'No colonic\nstent')))),
        n.event('E6', 'biopsy', 'Four targeted cold-forceps biopsies', 'were obtained from representative', session='X1',
                places=[('neo_terminal_ileum', 'inflamed ileal mucosa')], device=('cold_forceps', 'cold-forceps'),
                restatements=[('Specimen A: neo-terminal ileum', 'summarizes')]),
        n.event('E7', 'biopsy', 'Targeted cold-forceps biopsies', 'were obtained from an erythematous patch',
                session='X1', places=[('transverse_colon', 'proximal transverse colon')],
                device=('cold_forceps', 'Targeted cold-forceps'),
                restatements=[('Specimen C: proximal transverse-colon mucosa', 'summarizes')]),
        n.event('E8', 'biopsy', 'rectosigmoid mucosa', 'separately, from mildly granular', session='X1',
                anchor_words='Targeted cold-forceps biopsies', places=[('rectosigmoid', 'rectosigmoid mucosa')],
                device=('cold_forceps', 'Targeted cold-forceps'),
                restatements=[('Specimen F: rectosigmoid mucosa', 'summarizes')]),
        n.event('E9', 'injection', 'A submucosal injection', 'was placed directly beneath', session='X1',
                lesion=('L1', 'this distal transverse-colon lesion'), places=[('transverse_colon', 'distal transverse-colon')],
                purpose=('lift_for_resection', 'The lift was performed solely to facilitate'),
                part_of=('E10', 'to facilitate endoscopic mucosal resection of this lesion'),
                part_relation=('lift_for', 'The lift was performed solely to facilitate'),
                device=('injection', 'A submucosal injection')),
        n.event('E10', 'emr', 'resected using a 15 mm electrocautery snare', 'The lesion was resected', session='X1',
                lesion=('L1', 'The lesion'), places=[('transverse_colon', 'In the distal transverse colon')],
                device=('hot_snare', 'electrocautery snare'),
                restatements=[('Specimen D: distal transverse-colon lesion', 'summarizes'),
                              ('removed by piecemeal mucosal resection', 'summarizes'),
                              ('treated with saline-assisted piecemeal', 'summarizes')]),
        n.event('E11', 'bleeding_control', 'brief contact coagulation', 'resolved with brief contact coagulation',
                session='X1', purpose=('hemostasis', 'Minor oozing'), cause=('act_of_this_session', 'from the cut mucosal edge'),
                cause_event=('E10', 'from the cut mucosal edge'), device=('snare', 'using the snare tip')),
        n.event('E12', 'ablation', 'snare-tip soft coagulation', 'was treated with low-power', session='X1',
                part_of=('E10', 'as an adjunct to the same mucosal'), part_relation=('adjunct_of', 'as an adjunct'),
                device=('snare', 'snare-tip soft coagulation')),
        n.event('E13', 'clip', 'Two through-the-scope clips', 'were placed across the defect', session='X1',
                purpose=('prophylaxis', 'prophylactic closure'), part_of=('E10', 'across the defect'),
                part_relation=('adjunct_of', 'prophylactic closure'), device=('clip', 'through-the-scope clips')),
        n.event('E14', 'biopsy', 'No biopsy', 'was performed on', session='X1', status_state=NEG, **splenic),
        n.event('E15', 'snare', 'snare resection', 'was performed on', anchor_words=denied_here, session='X1',
                status_state=NEG, **splenic),
        n.event('E16', 'ablation', 'ablation, or balloon', 'was performed on', anchor_words=denied_here, session='X1',
                status_state=NEG, **splenic),
        n.event('E17', 'dilation', 'balloon dilation was performed', 'was performed on', anchor_words=denied_here,
                session='X1', status_state=NEG, **splenic),
        n.event('E18', 'tattoo', 'a sterile carbon-particle tattoo', 'was placed in normal mucosa', session='X1',
                anchor_units=[n.u('a sterile carbon-particle tattoo'), n.u('(toward the anus)')],
                purpose=('marking', 'For future localization'), device=('injection', 'two separate submucosal injections'),
                restatements=[('Directed carbon-particle tattooing', 'summarizes'),
                              ('carbon-particle tattoo placed distal and opposite the lesion', 'summarizes')],
                places=[('descending_colon', 'approximately 4 cm distal')] if marked else None,
                lesion=('L2', 'to the splenic-flexure lesion', 'statement') if marked else None),
        n.event('E19', 'tattoo', 'No carbon-particle tattoo', 'No carbon-particle tattoo was placed', session='X1',
                status_state=NEG, breadth=('single_target', 'transverse-colon resection bed'),
                places=[('transverse_colon', 'transverse-colon resection bed')],
                lesion=('L1', 'transverse-colon resection bed') if marked else None),
        n.event('E20', 'snare', 'cold snare', 'was captured at its base', session='X1', lesion=('L3', 'The polyp'),
                places=[('descending_colon', 'in the mid-descending colon')], device=('cold_snare', 'cold snare'),
                restatements=[('cold-snare removal\nen bloc', 'summarizes'), ('completely removed by cold-snare technique',
                                                                              'summarizes')]),
        n.event('E21', 'snare', 'the EMR electrosurgical snare', 'was used to treat this polyp', session='X1',
                status_state=NEG, breadth=('single_target', 'this polyp'), lesion=('L3', 'this polyp'),
                device=('hot_snare', 'EMR electrosurgical snare')),
        n.event('E22', 'dilation', 'Neither the dilation\nballoon', 'was used to treat this polyp', session='X1',
                anchor_words='Neither the dilation', status_state=NEG, breadth=('single_target', 'this polyp'),
                lesion=('L3', 'this polyp'), device=('balloon', 'dilation\nballoon')),
        n.event('E23', 'clip', 'No clip', 'was required at this site', session='X1', status_state=NEG,
                breadth=('single_target', 'at this site'), lesion=('L3', 'at this site')),
        n.event('E24', 'bleeding_control', 'cautery', 'was required at this site', anchor_words='No clip or cautery',
                session='X1', status_state=NEG, breadth=('single_target', 'at this site'), lesion=('L3', 'at this site')),
        n.event('E25', 'ablation', 'photographed but not treated', 'but not treated', session='X1', status_state=NEG,
                breadth=('single_target', 'vascular ectasia'), lesion=('L4', 'vascular ectasia')),
        n.event('E26', 'examination', 'A colonoscopy from January 2024', 'described', session='X2',
                date_relation=earlier24),
        n.event('E27', 'removal', 'was removed at that earlier encounter', 'was removed at that earlier encounter',
                session='X2', date_relation=('earlier_date', 'at that earlier encounter'),
                places=[('rectum', '4 mm rectal hyperplastic polyp')]),
        n.event('E28', 'dilation', 'No dilation', 'No dilation was carried\nout', session='X2', status_state=NEG,
                date_relation=('earlier_date', 'in 2024')),
        n.event('E29', 'examination', 'An outside upper endoscopy', 'performed in March 2023', session='X3',
                date_relation=earlier23, performer=outside),
        n.event('E30', 'dilation', 'balloon dilation and gastric', 'treated with', session='X3', anchor_words='Schatzki ring',
                date_relation=earlier23, performer=outside, device=('balloon', 'balloon dilation and gastric')),
        n.event('E31', 'biopsy', 'gastric biopsies', 'gastric biopsies at that time', session='X3',
                anchor_words='Schatzki ring', date_relation=('earlier_date', 'at that time'), performer=outside,
                places=[('stomach', 'gastric biopsies')]),
        n.event('E32', 'examination', 'esophagogastroduodenoscopy or other upper', 'was performed on November 8, 2026',
                session='X4', status_state=NEG, breadth=('all_of_kind', 'or other upper endoscopic procedure'),
                date_relation=('on_date_of_service', 'on November 8, 2026')),
        n.event('E33', 'other', 'Monitored anesthesia care', 'was administered and supervised', session='X1',
                other_class=('other', 'Monitored anesthesia care'), performer=('other_clinician', 'by the anesthesia team')),
        n.event('E34', 'moderate_sedation', 'moderate sedation service', 'did not\nadminister', session='X1',
                status_state=NEG, breadth=('all_of_kind', 'a separate physician-directed moderate sedation service')),
        n.event('E35', 'other', 'No fluoroscopy', 'No fluoroscopy was used', session='X1', status_state=NEG,
                other_class=('imaging', 'No fluoroscopy'), breadth=('all_of_kind', 'No fluoroscopy')),
        n.event('E36', 'removal', 'A future\nintervention', 'is planned but was not performed', status='planned',
                date_relation=('later_date', 'A future\nintervention'), lesion=('L2', 'for that lesion'))]
    lesions = [
        n.lesion('L1', '23 mm laterally spreading granular-type', multiplicity=('single', '23 mm laterally spreading'),
                 places=[('transverse_colon', 'In the distal transverse colon')]),
        n.lesion('L2', '17 mm non-granular flat lesion', multiplicity=('single', '17 mm non-granular flat lesion'),
                 places=[('splenic_flexure', 'At the splenic flexure')],
                 distinct_from=[('L1', 'a separate 17 mm'), ('L5', 'a separate 17 mm')]),
        n.lesion('L3', 'A separate 9 mm sessile polyp', multiplicity=('single', 'A separate 9 mm sessile polyp'),
                 places=[('descending_colon', 'in the mid-descending colon')],
                 distinct_from=[('L1', 'A separate 9 mm'), ('L2', 'A separate 9 mm'), ('L5', 'A separate 9 mm')]),
        n.lesion('L4', 'flat 4 mm, nonbleeding vascular ectasia', multiplicity=('single', 'flat 4 mm, nonbleeding'),
                 places=[('rectum', 'in the proximal rectum')]),
        n.lesion('L5', 'a single, short, concentric benign-appearing stenosis',
                 multiplicity=('single', 'a single, short, concentric'), places=[('anastomosis', 'At the right-sided')])]
    anatomy = [n.anatomy('Y1', ('anastomosis', 'stapled side-to-side ileocolonic'), subtype=('ileocolic', 'ileocolonic'))]
    return n.answer(sections=sections, sessions=sessions, events=events, lesions=lesions, anatomy=anatomy,
                    role_words='Endoscopist')


N8_CODES = (('45378', 'The colonoscope was introduced'), ('45380', 'cold-forceps mucosal biopsies'),
            ('45381', 'a sterile carbon-particle tattoo'), ('45385', 'was captured at its base'),
            ('45386', 'The balloon was inflated'), ('45390', 'The lesion was resected'))
# D241: the facts the no-place filing (variant (iii)) leaves out of the faithful one
N8_TATTOO_TARGETS = ('target.places@E18/0', 'target.lesion@E18/0', 'target.lesion@E19/0')
# The named residuals beside Note #8's documented outcome (its five codes READY, no contradiction, no open question:
# the owner's trial report, its comparison's decision points D1-D6, and FRESH-A's expectations), each asserted as built
N8B = ('Q-N8b', 'service', 'conflict:injection', 'E9',
       'DECISIONS D244 Q-N8b, option (a), as built and named: "No carbon-particle tattoo was placed into the '
       'transverse-colon resection bed" contradicts the saline lift there, a tattoo and an injection being one act kind '
       '(4.5); the lead counts it at D2-D3')
ANAST = ('Q-ANAST', 'service', 'statement_scope', 'E3',
         'open, unruled (refute-6c-r2 finding E): 4.5 never sets the anastomotic-rim biopsy apart from the splenic-flexure '
         'lesion\'s biopsy denial (an altered place is never disjoint, and the rim biopsy names no lesion)')
THREE = ('i', 'ii', 'iii')
N8_45381_I = ('D241: the tattoo, placed in the descending colon on lesion L2, is set apart from "No carbon-particle '
              'tattoo was placed into the transverse-colon resection bed" (lesion L1, the transverse colon) by place and '
              'by lesion, their pair controls rejected - one established difference suffices (4.5 [R:HO-2]); the tattoo '
              'alone supports the code: the saline lift is the EMR\'s part (4.7 lift_injection, included in 45390) and, '
              'the bed denial contradicting it (Q-N8b, D244 as built), fails 4.3 row 8; 59/XS by 4.7\'s modifier review '
              '(L2 distinct from the EMR\'s L1), as FRESH-A documents it')

CASES += [
    Case('CK-note8', 'checklist', ('original note8', 'CO-3', 'CO-6', 'D241'), 'GI Note #8, the original seventh case',
         D.NOTE8, note8, header=NOTE8_HEADER, variants=THREE, provenance=dev('NOTE8'), codes=N8_CODES,
         caught=('scope.breadth@E14/0', 'scope.breadth@E15/0', 'scope.breadth@E16/0', 'scope.breadth@E17/0'),
         shared=note8_no_place, shared_omits=N8_TATTOO_TARGETS,
         acts={'i': {'45381': ('E18',)}}, considerations={'i': {'45381': ('59|XS',)}},
         named={'i': (N8B, ANAST)},
         note='D241: (i) files the localization tattoo faithfully (its place and its lesion, the resection-bed denial on '
              'the resected lesion) and gives the documented outcome, 45381 READY; the filing with no place and no lesion '
              'is kept only as variant (iii), a residual, never a pass. D244: the EGD denied for the date of service is '
              'the examination, negated, of an EGD session X4 of its own, as step 2a\'s pass-1 instruction files a '
              'denied procedure of another kind (Q-N8 option (b)). Beside the documented outcome stand only the named '
              'residuals: Q-N8b (D244, as built) and the anastomotic-rim question (open, refute-6c-r2 finding E).',
         expect={'i': {'45378': (H, 'base_included', EXP, '4.7 base_included (b): the session\'s reportable acts (RANK '
                                                          '21)'),
                       '45380': (R, None, None, 'the biopsies elsewhere are set apart from the splenic-flexure '
                                                'lesion\'s denials by place, their pair controls rejected (4.5); COLFULL '
                                                'met by the neo-terminal ileum the colonoscope reached (CO-6)'),
                       '45381': (R, None, None, N8_45381_I),
                       '45385': (R, None, None, 'the cold snare removal of the descending polyp: the electrosurgical '
                                                'snare denial is apart by device, the splenic snare denial by lesion '
                                                '(4.5)'),
                       '45386': (R, None, None, 'the balloon dilation of the anastomotic stricture: the two dilation '
                                                'denials name other lesions, distinct from it (4.5 target row)'),
                       '45390': (R, None, None, 'the piecemeal EMR; its lift, contact coagulation, soft coagulation and '
                                                'clips are its parts (4.7 lift and procedural adjunct)')},
                 'ii': {'45378': (H, 'base_included', EXP, 'unchanged'),
                        '45380': (H, 'statement_scope', Q, '4.5 breadth row: the splenic-flexure denial\'s breadth, '
                                                           'contradicted by pass 2, not established: UNRESOLVED (RANK 3); '
                                                           'never READY'),
                        '45381': (R, None, None, 'unchanged (D241): no misfiled denial is of the tattoo\'s kind, and the '
                                                 'resection-bed denial stays apart by place and by lesion (4.5)'),
                        '45385': (H, 'statement_scope', Q, '4.5 breadth row UNRESOLVED (RANK 3)'),
                        '45386': (H, 'statement_scope', Q, '4.5 breadth row UNRESOLVED (RANK 3)'),
                        '45390': (R, None, None, 'no misfiled denial is of the EMR\'s kind')}}),
]
