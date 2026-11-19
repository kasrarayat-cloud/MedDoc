"""Design v2's readings of the fixture documents of DECISIONS D243's class C suites (docs/gemini-migration/DECISIONS.md,
2026-11-14; step q02), for tests/v2_replay.py: each document and pass 1's synthetic answer to it (FINAL-V2 1.4's shape,
built by hand with tests/v2/test_settle.py's builders). TEXT-ONLY and SYNTHETIC: fictional clinicians, no real patient.

Each document is the v1 fixture document it replaces with ONE line added, the document frame's: the fictional clinician
who documents it, right after the date of service (``v1_twin`` gives the v1 text back, and tests/test_v2_replay.py checks
every pair). Design v2 defaults nothing (FINAL-V2 0: no default; 1.5: a part's performer and an act's entry come from the
document frame), so without a named clinician every act's entry and performer is unestablished and every code is held
on them (measured: build-v2/w7r/q02/logs/exp5.out) - the line is what makes the v2 reading of the same note the same
note. Every other line is the v1 document's, and every quote a provider fake selects is the v1 fixture's own (DECISIONS
D261). tests/test_v2_replay.py's DocumentTests checks the quotes this module defines - TWO_CODES, DENIED_CODES, POLYP
and VISIT_TIME, each equal to v1's, the denial's 45385 quote with its stop - and that every class of the class C modules
that gives a marked test Corti groups of its own (``v2_corti_groups``) gives it its v1 groups. A fake that selects its
own module's constants on both paths gives v1's quotes by identity. DocumentTests reads none of
tests.test_repairs_7c8_p1reports' SNARE and BIOPSY (v1's phrases with no stop, which tests.test_repairs_gi2_reports'
fakes select too), and it reads tests.test_repairs_ec5_reportruns' VISIT, which ec5's fakes select on both paths, as
the v1 side of VISIT_TIME's check.

Each answer files what the document states and nothing else: its parts, the endoscopist, each session with its kind and
the reach the document states (none where it states none), the lesions, and each act with its kind, status, session,
target and device cited at its own words. Pass 2 is the faithful oracle (tests/v2/test_settle.faithful).
"""
from __future__ import annotations

from tests.v2.test_settle import answer, event, fact, frame, lesion, section, session, src

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
ENDOSCOPIST = 'Endoscopist: Corvin Ashdale, MD (fictional)'  # the document frame's one added line
CLINICIAN = 'Clinician: Corvin Ashdale, MD (fictional)'  # the same line in an office note
NAME = 'Corvin Ashdale'


def v1_twin(text: str) -> str:
    """The v1 fixture document ``text`` replaces: ``text`` without its added frame line."""
    for line in (ENDOSCOPIST, CLINICIAN):
        text = text.replace(line + '\n', '', 1)
    return text


def _when(unit: str, words: str, value: str) -> dict:
    return {'state': 'stated', 'value': value, 'sources': [frame([unit], words)], 'options': []}


def _people(unit: str, label: str) -> list:
    return [{'id': 'P1', 'name': src([unit], NAME), 'role': fact('documenting_clinician', src([unit], label))}]


def _opening(frame_unit: str, date_unit: str, first: str) -> dict:
    """N0, the document's opening part (1.4): its role the header at ``first``, its occasion the date of service and its
    performer the documenting team through the document frame."""
    return section('N0', src([], '', 'section'), fact('documenting_clinician', frame([frame_unit])),
                   role=[fact('header', src([first], '', 'frame'))],
                   occasion=[fact('on_date_of_service', frame([date_unit]))],
                   performer=[fact('documenting_team', frame([frame_unit]))])


def _labelled(sid: str, unit: str, label: str, role: str, frame_unit: str, date_unit: str) -> dict:
    """A part opened by ``label`` at ``unit``: its occasion the date of service and its performer the documenting team
    through the document frame."""
    return section(sid, src([unit], label, 'section'), fact('documenting_clinician', frame([frame_unit])),
                   role=[fact(role, src([unit], label, 'section'))],
                   occasion=[fact('on_date_of_service', frame([date_unit]))],
                   performer=[fact('documenting_team', frame([frame_unit]))])


def _single(lid: str, unit: str, words: str, place: str, place_words: str) -> dict:
    return lesion(lid, src([unit], words), multiplicity=[fact('single', src([unit], words))],
                  places=[fact(place, src([unit], place_words))])


# --- tests.test_pipeline_assess_events.two_procedures ------------------------------------------------------------------

G1 = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
G2 = 'EGD: cold forceps biopsies were taken from the gastric antrum.'
P1 = 'Colonoscopy: the colonoscope was inserted.'
POLYP = 'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
TWO_PROCEDURES = (HEAD                                                     # S1
                  + 'Date of service: 11/09/2026.\n'                       # S2
                  + ENDOSCOPIST + '\n'                                     # S3
                  + G1 + '\n'                                              # S4
                  + G2 + '\n'                                              # S5
                  + P1 + '\n'                                              # S6
                  + POLYP + '\n')                                          # S7
TWO_CODES = (('43239', G2), ('45385', POLYP))  # Corti's on TWO_PROCEDURES, as on the v1 document


def two_procedures_answer() -> dict:
    """An EGD part (X1: the gastroscope advanced to the second portion of the duodenum, E1; antral cold forceps biopsies,
    E2) and a colonoscopy part (X2: the colonoscope inserted, its reach not stated, E3; the cold snare removal of the 6 mm
    sigmoid polyp L1, E4). Read by the engine: 43239 READY, 45385 held on the extent (measured: logs/exp1.out)."""
    return answer(
        sections=[_opening('S3', 'S2', 'S1'), _labelled('N1', 'S4', 'EGD:', 'procedure', 'S3', 'S2'),
                  _labelled('N2', 'S6', 'Colonoscopy:', 'procedure', 'S3', 'S2')],
        people=_people('S3', 'Endoscopist'),
        clinician=[fact('P1', frame(['S3'], NAME))],
        sessions=[session('X1', fact('egd', src(['S4'], 'gastroscope')), examination=[fact('E1', src(['S4']))],
                          reached=[fact('second_portion_duodenum',
                                        src(['S4'], 'advanced to the second portion of the duodenum'))]),
                  session('X2', fact('colonoscopy', src(['S6'], 'colonoscope')), examination=[fact('E3', src(['S6']))])],
        lesions=[_single('L1', 'S7', 'A 6 mm sessile polyp', 'sigmoid_colon', 'sigmoid colon')],
        events=[event('E1', ['S4'], 'gastroscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'biopsies', 'were taken', 'biopsy', session=[fact('X1', src(['S5']))],
                      target__places=[fact('gastric_antrum', src(['S5'], 'gastric antrum'))],
                      technique__device=[fact('cold_forceps', src(['S5'], 'cold forceps'))]),
                event('E3', ['S6'], 'colonoscope', 'was inserted', 'examination', session=[fact('X2', src(['S6']))]),
                event('E4', ['S7'], 'cold snare', 'was removed', 'snare', session=[fact('X2', src(['S7']))],
                      target__lesion=[fact('L1', src(['S7'], 'A 6 mm sessile polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S7'], 'sigmoid colon'))],
                      technique__device=[fact('cold_snare', src(['S7'], 'cold snare'))])],
        when=_when('S2', '11/09/2026', '2026-11-09'))


def two_procedures() -> tuple:
    """(pass 1's answer, the document) - the shape of tests.test_pipeline_assess_events' scenarios."""
    return two_procedures_answer(), TWO_PROCEDURES


# --- tests.test_readers_dispatch.denied_removal ------------------------------------------------------------------------

COLONOSCOPE = 'The colonoscope was advanced to the cecum.'
DENIAL = 'No polyp was removed today.'
DENIED_REMOVAL = (HEAD                                                     # S1
                  + 'Date of service: 11/09/2026.\n'                       # S2
                  + ENDOSCOPIST + '\n'                                     # S3
                  + COLONOSCOPE + '\n'                                     # S4
                  + DENIAL + '\n')                                         # S5
# Corti's on DENIED_REMOVAL, v1's quotes: 45385 cites the denial, its stop included (DECISIONS D261). Assess hands C-10
# the kept evidence's letter-or-digit runs as kept_words (contract/geometry.word_runs, through jobs._Integrity), so a
# quote that reaches past the statement only by its stop covers it: 45385 excluded, 45378 READY. Round w7r's fixture
# dropped the stop while C-10 had no kept_words (a partial cover then, statement_scope); D261 restores v1's quote
DENIED_CODES = (('45378', COLONOSCOPE), ('45385', DENIAL))


def denied_removal_answer() -> dict:
    """A colonoscopy (X1) to the cecum (E1), and the broad current denial of any polyp removal (E2: kind snare, status
    negated at 'No polyp was removed today', breadth all_of_kind, today, session X1). Read by the engine: 45385, citing
    the denial with its stop (DENIED_CODES, v1's quote; D261's kept_words), EXCLUDED (reinstatable; 4.6, every condition
    met) and 45378 READY (pinned by tests.test_readers_dispatch.NewPathConsumerTests' reinstated-exclusion test)."""
    return answer(
        sections=[_opening('S3', 'S2', 'S1')],
        people=_people('S3', 'Endoscopist'),
        clinician=[fact('P1', frame(['S3'], NAME))],
        sessions=[session('X1', fact('colonoscopy', src(['S4'], 'colonoscope')), examination=[fact('E1', src(['S4']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('cecum', src(['S4'], 'advanced to the cecum'))])],
        events=[event('E1', ['S4'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'polyp was removed', 'No polyp was removed today', 'snare', state='negated',
                      session=[fact('X1', src(['S5']))],
                      date_relation=[fact('on_date_of_service', src(['S5'], 'today'))],
                      scope__breadth=[fact('all_of_kind', src(['S5'], 'No polyp'))])],
        when=_when('S2', '11/09/2026', '2026-11-09'))


def denied_removal() -> tuple:
    return denied_removal_answer(), DENIED_REMOVAL


# --- tests.test_pipeline_api.OFFICE_NOTE ------------------------------------------------------------------------------

OFFICE_NOTE = (HEAD                                                        # S1
               + '\n'
               + 'Riverbend Digestive Health (fictional)\n'                # S2
               + 'Date of service: 2026-10-20\n'                           # S3
               + CLINICIAN + '\n'                                          # S4
               + 'Place of service: Office, in-person outpatient visit\n'  # S5
               + 'Patient status: Established patient, last seen 2026-03-02.\n'  # S6
               + '\n'
               + 'Chief complaint\n'                                       # S7
               + 'Follow-up of chronic constipation.\n'                    # S8
               + '\n'
               + 'Assessment and plan\n'                                   # S9
               + 'Chronic idiopathic constipation, improved. Continue polyethylene glycol daily.\n'  # S10, S11
               + 'A colonoscopy is scheduled for 2026-12-01.\n'            # S12
               + '\n'
               + 'Medical decision making\n'                               # S13
               + 'Low: one stable chronic illness; prescription drug management.\n'  # S14
               + '\n'
               + 'Time\n'                                                  # S15
               + 'Total time on the date of the encounter was 24 minutes.\n')  # S16
VISIT_TIME = 'Total time on the date of the encounter was 24 minutes.'  # Corti's 99213 quote, as on the v1 document


def office_note_answer() -> dict:
    """The office visit of 2026-10-20 (X1, office_em, this encounter: E1, an em_visit, its basis the stated total time,
    placed by S16) and the colonoscopy scheduled for a later date (X2: E2, planned, later_date). Read by the engine:
    99213 held on the setting alone, a member value (DECISIONS D3: the setting and patient status come only from member
    values) - as v1's production chain held it (tests.test_pipeline_api.OFFICE_NOTE_STATE; measured: logs/exp8.out).
    It is also the answer to an addendum revision of the note whose added line codes nothing ('Setting confirmed as
    office.'): the note's units keep their ids and the addendum's add none any fact cites."""
    return answer(
        sections=[_opening('S4', 'S3', 'S1')],
        people=_people('S4', 'Clinician'),
        clinician=[fact('P1', frame(['S4'], NAME))],
        sessions=[session('X1', fact('office_em', src(['S5'], 'Office')), examination=[fact('E1', src(['S5']))],
                          encounter=[fact('this_encounter', frame(['S3']))]),
                  session('X2', fact('colonoscopy', src(['S12'], 'colonoscopy')), examination=[fact('E2', src(['S12']))])],
        events=[event('E1', ['S5'], 'in-person outpatient visit', 'in-person outpatient visit', 'em_visit',
                      session=[fact('X1', src(['S5']))],
                      visit__basis=[fact('total_time', src(['S16'], '24 minutes', 'placing'))]),
                event('E2', ['S12'], 'colonoscopy', 'is scheduled', 'examination', status='planned',
                      session=[fact('X2', src(['S12']))],
                      date_relation=[fact('later_date', src(['S12'], 'scheduled for 2026-12-01'))])],
        when=_when('S3', '2026-10-20', '2026-10-20'))


# --- tests.test_repairs_7c8_p1reports.COLONOSCOPY (tests.test_services_second_review.REPORT's lines) -------------------

CECUM_DONE = 'The colonoscope was advanced to the cecum and the examination was completed.'
COLONOSCOPY = (HEAD                                                        # S1
               + 'Colonoscopy report (fictional)\n'                        # S2
               + 'Date of service: 2026-10-16\n'                           # S3
               + ENDOSCOPIST + '\n'                                        # S4
               + 'Procedure: Colonoscopy\n'                                # S5
               + CECUM_DONE + '\n'                                         # S6
               + 'A 6 mm polyp in the rectum was removed with a cold snare.\n'  # S7
               + 'A separate 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps; it was not '
                 'removed.\n')                                             # S8


def colonoscopy_answer() -> dict:
    """A colonoscopy (X1) to the cecum, completed (E1); the cold snare removal of the 6 mm rectal polyp L1 (E2); the cold
    forceps biopsy of the separate 10 mm transverse lesion L2 (E3) and that lesion's removal denied (E4: removal,
    negated, single_target, L2) - v1's REPORT_INTERPRETATION, filed in FINAL-V2 1.4's shape."""
    return answer(
        sections=[_opening('S4', 'S3', 'S1'), _labelled('N1', 'S5', 'Procedure:', 'procedure', 'S4', 'S3')],
        people=_people('S4', 'Endoscopist'),
        clinician=[fact('P1', frame(['S4'], NAME))],
        sessions=[session('X1', fact('colonoscopy', src(['S6'], 'colonoscope')), examination=[fact('E1', src(['S6']))],
                          encounter=[fact('this_encounter', frame(['S3']))],
                          reached=[fact('cecum', src(['S6'], 'advanced to the cecum'))],
                          completion=[fact('complete', src(['S6'], 'the examination was completed'))])],
        lesions=[_single('L1', 'S7', 'A 6 mm polyp', 'rectum', 'rectum'),
                 lesion('L2', src(['S8'], 'A separate 10 mm flat lesion'),
                        multiplicity=[fact('single', src(['S8'], 'A separate 10 mm flat lesion'))],
                        places=[fact('transverse_colon', src(['S8'], 'transverse colon'))],
                        distinct_from=[fact('L1', src(['S8'], 'A separate'))])],
        events=[event('E1', ['S6'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S6']))]),
                event('E2', ['S7'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S7']))],
                      target__lesion=[fact('L1', src(['S7'], 'A 6 mm polyp'))],
                      target__places=[fact('rectum', src(['S7'], 'rectum'))],
                      technique__device=[fact('cold_snare', src(['S7'], 'cold snare'))]),
                event('E3', ['S8'], 'sampled', 'was sampled', 'biopsy', session=[fact('X1', src(['S8']))],
                      target__lesion=[fact('L2', src(['S8'], 'A separate 10 mm flat lesion'))],
                      target__places=[fact('transverse_colon', src(['S8'], 'transverse colon'))],
                      technique__device=[fact('cold_forceps', src(['S8'], 'cold biopsy forceps'))]),
                event('E4', ['S8'], 'removed', 'it was not removed', 'removal', state='negated',
                      session=[fact('X1', src(['S8']))],
                      target__lesion=[fact('L2', src(['S8'], 'it'))],
                      scope__breadth=[fact('single_target', src(['S8'], 'it'))])],
        when=_when('S3', '2026-10-16', '2026-10-16'))


# --- tests.test_harness2_pipeline.TWO_EXTENTS -------------------------------------------------------------------------

LANDMARKS = 'Landmarks photographed: appendiceal orifice and ileocecal valve.'
TWO_EXTENTS = (HEAD                                                        # S1
               + 'Colonoscopy report (fictional)\n'                        # S2
               + 'Date of service: 2026-10-14\n'                           # S3
               + ENDOSCOPIST + '\n'                                        # S4
               + 'Place of service: Ambulatory surgery center\n'           # S5
               + 'Procedure: Colonoscopy\n'                                # S6
               + 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'  # S7
               + 'A separate 12 mm flat lesion in the ascending colon was biopsied with cold forceps.\n'  # S8
               + LANDMARKS + '\n')                                         # S9


def two_extents_answer() -> dict:
    """A colonoscopy (X1) whose reach the document does not state - the landmarks line names no endoscope, so pass 1
    files no reach, as v1's answer did - the hot snare removal of the 9 mm sigmoid polyp L1 (E2) and the cold forceps
    biopsy of the separate 12 mm ascending lesion L2 (E3). Each colonoscopy code is held on the extent (measured:
    logs/exp10.out). The procedure line places the session's kind; no examination act is filed: the document states
    none, and the header lines carry no stop, so their units join E2's sentence closure - an examination anchored on
    'Procedure: Colonoscopy' would share E2's card and leave E2's kind cards_indistinct (3.3 row 7; logs/exp9.out)."""
    return answer(
        sections=[_opening('S4', 'S3', 'S1')],
        people=_people('S4', 'Endoscopist'),
        clinician=[fact('P1', frame(['S4'], NAME))],
        sessions=[session('X1', fact('colonoscopy', src(['S6'], 'Colonoscopy', 'placing')),
                          encounter=[fact('this_encounter', frame(['S3']))])],
        lesions=[_single('L1', 'S7', 'A 9 mm pedunculated polyp', 'sigmoid_colon', 'sigmoid colon'),
                 lesion('L2', src(['S8'], 'A separate 12 mm flat lesion'),
                        multiplicity=[fact('single', src(['S8'], 'A separate 12 mm flat lesion'))],
                        places=[fact('ascending_colon', src(['S8'], 'ascending colon'))],
                        distinct_from=[fact('L1', src(['S8'], 'A separate'))])],
        events=[event('E2', ['S7'], 'hot snare', 'was removed', 'snare', session=[fact('X1', src(['S7']))],
                      target__lesion=[fact('L1', src(['S7'], 'A 9 mm pedunculated polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S7'], 'sigmoid colon'))],
                      technique__device=[fact('hot_snare', src(['S7'], 'hot snare'))]),
                event('E3', ['S8'], 'biopsied', 'was biopsied', 'biopsy', session=[fact('X1', src(['S8']))],
                      target__lesion=[fact('L2', src(['S8'], 'A separate 12 mm flat lesion'))],
                      target__places=[fact('ascending_colon', src(['S8'], 'ascending colon'))],
                      technique__device=[fact('cold_forceps', src(['S8'], 'cold forceps'))])],
        when=_when('S3', '2026-10-14', '2026-10-14'))


# --- tests.test_harness2_r5_row.COLON ---------------------------------------------------------------------------------

COLON = (HEAD                                                              # S1
         + 'Colonoscopy report (fictional)\n'                              # S2
         + 'Date of service: 2026-10-21\n'                                 # S3
         + ENDOSCOPIST + '\n'                                              # S4
         + 'Place of service: Ambulatory surgery center\n'                 # S5
         + 'Procedure: Colonoscopy\n'                                      # S6
         + CECUM_DONE + '\n'                                               # S7
         + 'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n')  # S8


def colon_answer() -> dict:
    """A colonoscopy (X1) to the cecum, completed (E1), and the hot snare removal of the 9 mm sigmoid polyp L1 (E2):
    45385 READY, and 45378 beside it held on base_included (one question about 45378, as the v1 chain asked it)."""
    return answer(
        sections=[_opening('S4', 'S3', 'S1')],
        people=_people('S4', 'Endoscopist'),
        clinician=[fact('P1', frame(['S4'], NAME))],
        sessions=[session('X1', fact('colonoscopy', src(['S7'], 'colonoscope')), examination=[fact('E1', src(['S7']))],
                          encounter=[fact('this_encounter', frame(['S3']))],
                          reached=[fact('cecum', src(['S7'], 'advanced to the cecum'))],
                          completion=[fact('complete', src(['S7'], 'the examination was completed'))])],
        lesions=[_single('L1', 'S8', 'A 9 mm pedunculated polyp', 'sigmoid_colon', 'sigmoid colon')],
        events=[event('E1', ['S7'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S7']))]),
                event('E2', ['S8'], 'hot snare', 'was removed', 'snare', session=[fact('X1', src(['S8']))],
                      target__lesion=[fact('L1', src(['S8'], 'A 9 mm pedunculated polyp'))],
                      target__places=[fact('sigmoid_colon', src(['S8'], 'sigmoid colon'))],
                      technique__device=[fact('hot_snare', src(['S8'], 'hot snare'))])],
        when=_when('S3', '2026-10-21', '2026-10-21'))
