"""DECISIONS D157 (round 5f, narrowing only; repair key egd6), SYNTHETIC. D154 stopped on the withdrawal of D149 (2)'s
adjective key because, built alone, it brought back moves the narrowing rule forbids; this round pairs it with its
companions. Each test is built from its source's own input with the round-5 EGD builders
(tests/test_interpretation_r5_egd.py: a document, a Gemini answer written to prompt.py's contract, the proposer's
citations replayed):
- (1) the round-5d review of D149, egd4 problem 0 (critical): D149's key is withdrawn for the families whose catalogue
  acts list the bleeding control (the upper endoscopy, the enteroscopy, the colonoscopy, the flexible sigmoidoscopy), so
  a device-named control there ("Cautery was applied at this site.", FRESH's attested 'cautery' filing in its performed
  form) is a bleeding control in doubt again, as e5628be56 and c2e53f8e hold it; elsewhere (the ERCP, the EUS) the key
  stays and the device-named control stays listed not covered, as f9013e12e lists it (egd5's measured alternative 2).
- (2) D154's class (iv) - the next reader's fallback: a denial of the code's kind cited alone never excludes the code
  while an act of that kind is in doubt (D87); it is held with the question 7.4 asks of the act in doubt (f9013e12e's
  question, where it read the act as a control done), else with the statement_scope question on the denial.
- (5) the round-5e review of D154, problem 2: the same for D115's hemostatic clip and the adjective-named cautery, which
  every new-path head excluded.
- (3) D154's class (ii): the act a proposed code's own question names yields its (family, fact) service slot to the
  next act in doubt (assess passes the proposals' question events: coverage.in_doubt_questions' ``holding``), and the
  code held not documented names the act in doubt of its kind - so the timed biopsy's "done at this encounter?", whose
  answer decides the missing 43239, is asked again, as f9013e12e and e5628be56 ask it.
- (4) recorded: a code's own question that returns to e5628be56's.
c2e53f8e's outcome on each input is in the test's docstring (run on the very same texts and citations: round5f/egd6's
probe_installed.py). Nothing is sent."""
from __future__ import annotations

import ast
import copy
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.interpretation import coverage, events, mapping
from tests import test_interpretation_r5_egd as e5
from tests import test_interpretation_r5c_egd as e5c
from tests.test_interpretation_events import proposal

at, tgt, event, lesion, report, case = e5.at, e5.tgt, e5.event, e5.lesion, e5.report, e5.case
built, assessed, items, held, held_base = e5.built, e5.assessed, e5.items, e5.held, e5.held_base
EGD, ADV, NORMAL, CLEAN_ULCER, ULCER = e5.EGD, e5.ADV, e5.NORMAL, e5.CLEAN_ULCER, e5.ULCER
APP = Path(__file__).resolve().parents[1]
POSSIBLE, CONTROL = mapping.POSSIBLE_BLEEDING_CONTROL, mapping.BLEEDING_CONTROL
NAMES: list = []  # the inputs this module asserts on, in order (dumped for the installed release's runner)


def mine(name: str) -> str:
    NAMES.append(name)
    return name


def control(line: str, *, kind_words: str, technique_words: str, target_words: str, status_words: str = 'was applied',
            technique: str = 'electrocautery', purpose: str = '', purpose_words: str = '', eid: str = 'E2',
            procedure=EGD, landmark: str = 'gastric_antrum', lesion_id: str = 'L1', passage: str = 'P7',
            time=None) -> dict:
    """A performed bleeding_control event in ``passage``, every words field a part of ``line``; purpose not_stated
    unless given (FRESH's attested 'cautery' filing: kind bleeding_control, technique electrocautery)."""
    for words in (kind_words, technique_words, target_words, status_words) + (
            (purpose_words,) if purpose_words else ()):
        assert words in line, (words, line)
    item = event(eid, procedure, at('bleeding_control', kind_words, [passage]),
                 status=at('performed', status_words, [passage]), technique=at(technique, technique_words, [passage]),
                 target=tgt(lesion_id, landmark, target_words, [passage]),
                 purpose=at(purpose, purpose_words, [passage]) if purpose else at('not_stated'))
    if time is not None:
        item['time'] = time
    return item


def ulcer_case(name: str, line: str, act: dict, codes, *, finding: str = CLEAN_ULCER, finding_lesion=ULCER) -> str:
    return mine(case(name, report(P5=ADV, P6=finding, P7=line, P8=NORMAL), [e5.examination(), act], codes,
                     lesions=[finding_lesion]))


VESSEL = 'A 12 mm ulcer with an oozing visible vessel was seen in the gastric antrum.'
VESSEL_ULCER = lesion('L1', '12 mm ulcer with an oozing visible vessel', 'gastric_antrum', 'gastric antrum', '12 mm',
                      ['P6', 'P7'])
COLON = e5c.COLON
CECUM = 'The colonoscope was advanced to the cecum.'
ANGIO_CECUM = 'A 4 mm angioectasia was seen in the cecum.'
ANGIO = lesion('L1', '4 mm angioectasia', 'cecum', 'cecum', '4 mm', ['P6', 'P7'])
AT_SITE = 'Cautery was applied at this site.'
COLON_REACH = ('E1', 'cecum', 'cecum', 'P5')


def cecal_cautery() -> dict:
    return control(AT_SITE, kind_words='Cautery', technique_words='Cautery', target_words='at this site',
                   procedure=COLON, landmark='cecum')


# --- (1) egd4 problem 0: a device-named control in a family whose catalogue lists the bleeding control --------------

# (a) the colonoscopy: the cecal angioectasia, then FRESH's 'cautery' filing in its performed form
P0A = mine(case('d157_p0a_colon_cautery_at_this_site_45382_45378',
                report('COLONOSCOPY REPORT', P5=CECUM, P6=ANGIO_CECUM, P7=AT_SITE, P8='No other lesion was seen.'),
                [copy.deepcopy(e5c.COLON_EXAM), cecal_cautery()], [('45382', (AT_SITE,)), ('45378', (CECUM,))],
                lesions=[ANGIO], reach=COLON_REACH))
P0A_ALONE = mine(case('d157_p0a_colon_cautery_at_this_site_45382_alone',
                      report('COLONOSCOPY REPORT', P5=CECUM, P6=ANGIO_CECUM, P7=AT_SITE,
                             P8='No other lesion was seen.'),
                      [copy.deepcopy(e5c.COLON_EXAM), cecal_cautery()], [('45382', (AT_SITE,))], lesions=[ANGIO],
                      reach=COLON_REACH))
# (b) beside the clean-based ulcer, alone and with 43235; (c) the prevention and the clips filed as bleeding_control
CAUTERY_BASE = 'Cautery was applied to the ulcer base.'


def cautery_act(line: str = CAUTERY_BASE, kind_words: str = 'Cautery', **kwargs) -> dict:
    return control(line, kind_words=kind_words, technique_words=kind_words, target_words='the ulcer base', **kwargs)


P0B = ulcer_case('d157_p0b_cautery_ulcer_base_43255', CAUTERY_BASE, cautery_act(), [('43255', (CAUTERY_BASE,))])
P0B_BASE = ulcer_case('d157_p0b_cautery_ulcer_base_43255_43235', CAUTERY_BASE, cautery_act(),
                      [('43255', (CAUTERY_BASE,)), ('43235', (ADV,))])
PREVENT = 'Cautery was applied to the ulcer base to prevent bleeding.'
P0C_PREVENT = ulcer_case('d157_p0c_cautery_to_prevent_bleeding_43255', PREVENT,
                         cautery_act(PREVENT, purpose='prophylaxis', purpose_words='to prevent bleeding'),
                         [('43255', (PREVENT,))])
HEMOCLIPS = 'Two hemoclips were placed across the ulcer base.'
P0C_HEMOCLIPS = ulcer_case('d157_p0c_hemoclips_filed_as_bleeding_control_43255', HEMOCLIPS,
                           control(HEMOCLIPS, kind_words='hemoclips', technique='clip', technique_words='hemoclips',
                                   target_words='the ulcer base', status_words='were placed'),
                           [('43255', (HEMOCLIPS,))])
CLIPS2 = 'Two clips were placed across the ulcer.'
P0C_CLIPS = ulcer_case('d157_p0c_clips_filed_as_bleeding_control_43255', CLIPS2,
                       control(CLIPS2, kind_words='clips were placed', technique='clip', technique_words='clips',
                               target_words='the ulcer', status_words='were placed'), [('43255', (CLIPS2,))])
# (d) the wrong act: dilute epinephrine filed as bleeding_control (43255, 43236); argon plasma coagulation (43270)
EPI = 'Dilute epinephrine was injected into the ulcer base.'
P0D_EPI = ulcer_case('d157_p0d_epinephrine_filed_as_bleeding_control_43255_43236', EPI,
                     control(EPI, kind_words='injected', technique='injection', technique_words='Dilute epinephrine',
                             target_words='the ulcer base', status_words='was injected'),
                     [('43255', (EPI,)), ('43236', (EPI,))])
APC = 'Argon plasma coagulation was applied to the angioectasias.'
P0D_APC = ulcer_case('d157_p0d_apc_filed_as_bleeding_control_43255_43270', APC,
                     control(APC, kind_words='Argon plasma coagulation', technique='argon_plasma',
                             technique_words='Argon plasma coagulation', target_words='the angioectasias',
                             landmark='gastric_body'),
                     [('43255', (APC,)), ('43270', (APC,))],
                     finding='Three angioectasias were seen in the gastric body.',
                     finding_lesion=lesion('L1', 'Three angioectasias', 'gastric_body', 'gastric body', '',
                                           ['P6', 'P7']))

# egd5's (i) rows, the key kept: an ERCP and an EUS, whose catalogue acts list no bleeding control
ERCP = at('ercp', 'ERCP', ['P2'])
ERCP_ADV = 'The duodenoscope was advanced to the major papilla.'
CANNULATED = 'Deep biliary cannulation was achieved with a sphincterotome.'
SPHINCTEROTOMY = 'A biliary sphincterotomy was performed.'


def ercp_events() -> list:
    return [event('E1', ERCP, at('examination', 'The duodenoscope was advanced', ['P5']),
                  technique=at('endoscope', 'duodenoscope', ['P5']), status=at('performed', 'was advanced', ['P5'])),
            event('E2', ERCP, at('cannulation', 'Deep biliary cannulation', ['P6']),
                  status=at('performed', 'was achieved', ['P6']),
                  technique=at('sphincterotome', 'sphincterotome', ['P6']),
                  target=tgt('', 'bile_duct', 'biliary', ['P6'])),
            event('E3', ERCP, at('sphincterotomy', 'biliary sphincterotomy', ['P7']),
                  status=at('performed', 'was performed', ['P7']), target=tgt('', 'bile_duct', 'biliary', ['P7']))]


def ercp_case(name: str, line: str, act: dict) -> str:
    return mine(case(name, report('ERCP REPORT', P5=ERCP_ADV, P6=CANNULATED, P7=SPHINCTEROTOMY, P8=line),
                     ercp_events() + [act], [('43262', (SPHINCTEROTOMY,))],
                     reach=('E1', 'ampulla', 'major papilla', 'P5')))


ERCP_CAUTERY = 'Cautery was applied to the sphincterotomy site.'
L_ERCP = ercp_case('d157_i_ercp_cautery_at_the_sphincterotomy_site_43262', ERCP_CAUTERY,
                   control(ERCP_CAUTERY, kind_words='Cautery', technique_words='Cautery',
                           target_words='the sphincterotomy site', eid='E4', procedure=ERCP, landmark='ampulla',
                           lesion_id='', passage='P8'))
ERCP_EPI = 'Dilute epinephrine was injected at the sphincterotomy site.'
L_ERCP_EPI = ercp_case('d157_i_ercp_epinephrine_filed_as_bleeding_control_43262', ERCP_EPI,
                       control(ERCP_EPI, kind_words='injected', technique='injection',
                               technique_words='Dilute epinephrine', target_words='the sphincterotomy site',
                               status_words='was injected', eid='E4', procedure=ERCP, landmark='ampulla',
                               lesion_id='', passage='P8'))
EUS_PROC = at('eus', 'ENDOSCOPIC ULTRASOUND', ['P2'])
EUS_ADV = 'The linear echoendoscope was advanced to the second portion of the duodenum.'
EUS_FNA = 'Fine-needle aspiration of the pancreatic head mass was performed with a 22 gauge needle.'
EUS_CAUTERY = 'Cautery was applied to the puncture site.'
L_EUS = mine(case('d157_i_eus_cautery_at_the_puncture_site_43242',
                  report('ENDOSCOPIC ULTRASOUND REPORT', P5=EUS_ADV, P6=EUS_FNA, P7=EUS_CAUTERY),
                  [event('E1', EUS_PROC, at('examination', 'The linear echoendoscope was advanced', ['P5']),
                         technique=at('endoscope', 'linear echoendoscope', ['P5']),
                         status=at('performed', 'was advanced', ['P5'])),
                   event('E2', EUS_PROC, at('fna', 'Fine-needle aspiration', ['P6']),
                         status=at('performed', 'was performed', ['P6']),
                         technique=at('needle', '22 gauge needle', ['P6']),
                         target=tgt('', 'pancreas', 'the pancreatic head mass', ['P6'])),
                   control(EUS_CAUTERY, kind_words='Cautery', technique_words='Cautery',
                           target_words='the puncture site', eid='E3', procedure=EUS_PROC, landmark='not_stated',
                           lesion_id='', passage='P7')],
                  [('43242', (EUS_FNA,))], reach=('E1', 'second_portion_duodenum', 'second portion of the duodenum',
                                                  'P5')))

# --- (2) and (5): a denial of the kind cited alone beside an act of that kind in doubt ------------------------------

NONE_REQUIRED = 'No other bleeding control was required.'


def none_required(eid: str = 'E3', passage: str = 'P8', words: str = 'No other bleeding control was required') -> dict:
    return event(eid, EGD, at('bleeding_control', 'bleeding control', [passage]),
                 status=at('not_performed', words, [passage]))


X1_LINES = report(P5=ADV, P6=CLEAN_ULCER, P7=CAUTERY_BASE, P8=NONE_REQUIRED, P9=NORMAL)
X1 = mine(case('d157_iv_cautery_then_denial_43255_cites_the_denial', X1_LINES,
               [e5.examination(), cautery_act(), none_required()], [('43255', (NONE_REQUIRED,))], lesions=[ULCER]))
X1_BASE = mine(case('d157_iv_cautery_then_denial_43255_cites_the_denial_43235', X1_LINES,
                    [e5.examination(), cautery_act(), none_required()],
                    [('43255', (NONE_REQUIRED,)), ('43235', (ADV,))], lesions=[ULCER]))
X1_BOTH = mine(case('d157_iv_control_cautery_then_denial_43255_cites_both', X1_LINES,
                    [e5.examination(), cautery_act(), none_required()], [('43255', (CAUTERY_BASE, NONE_REQUIRED))],
                    lesions=[ULCER]))
FURTHER = 'Cautery was applied to the ulcer base, and no further bleeding control was required.'
X2 = mine(case('d157_iv_one_sentence_43255_cites_the_denial_words',
               report(P5=ADV, P6=CLEAN_ULCER, P7=FURTHER, P8=NORMAL),
               [e5.examination(), cautery_act(FURTHER),
                none_required(passage='P7', words='no further bleeding control was required')],
               [('43255', ('no further bleeding control was required',))], lesions=[ULCER]))
# FRESH's denial filing ('No clip or cautery was required at this site.': bleeding_control 'cautery', technique
# electrocautery, not_performed; fresh2-frozen/A/note8/r1 E23) after the polypectomy, the cautery of the angioectasia
# before it; 45382 cites only the denial
SNARED = 'A 5 mm polyp in the sigmoid colon was removed with a cold snare.'
NO_CAUTERY = 'No clip or cautery was required at this site.'
COLON_DEN_LINES = report('COLONOSCOPY REPORT', P5=CECUM, P6=ANGIO_CECUM, P7=AT_SITE, P8=SNARED, P9=NO_CAUTERY)
COLON_LESIONS = [ANGIO, lesion('L2', '5 mm polyp', 'sigmoid_colon', 'sigmoid colon', '5 mm', ['P8', 'P9'])]


def colon_denial_events(scope: dict) -> list:
    denial = event('E4', COLON, at('bleeding_control', 'cautery', ['P9']),
                   status=at('not_performed', 'No clip or cautery was required', ['P9']),
                   technique=at('electrocautery', 'cautery', ['P9']),
                   target=tgt('L2', 'sigmoid_colon', 'at this site', ['P9']))
    denial['scope'] = scope
    return [copy.deepcopy(e5c.COLON_EXAM), cecal_cautery(),
            event('E3', COLON, at('snare', 'removed with a cold snare', ['P8']),
                  status=at('performed', 'was removed', ['P8']), technique=at('cold_snare', 'cold snare', ['P8']),
                  target=tgt('L2', 'sigmoid_colon', 'A 5 mm polyp in the sigmoid colon', ['P8'])),
            denial]


SCOPES = {  # FRESH's own scope (note8 r1 E23), egd5's (the polyp's lesion), and unscoped
    'fresh': {'value': 'single_target', 'targets': [], 'words': 'at this site', 'passages': ['P9']},
    'lesion': {'value': 'single_target', 'targets': ['L2'], 'words': '', 'passages': []},
    'unscoped': {'value': 'all_of_kind', 'targets': [], 'words': '', 'passages': []},
}
X3 = {label: mine(case(f'd157_iv_colon_fresh_denial_{label}_scope_45382_cites_the_denial_45385', COLON_DEN_LINES,
                       colon_denial_events(scope), [('45382', (NO_CAUTERY,)), ('45385', (SNARED,))],
                       lesions=COLON_LESIONS, reach=COLON_REACH))
      for label, scope in SCOPES.items()}
# (5): D115's hemostatic clip, and the adjective-named cautery, in doubt on every new-path head
HEMOSTATIC_CAUTERY = 'Hemostatic cautery was applied to the ulcer base.'
P2_CLIP = mine(case('d157_p2_hemostatic_clips_then_denial_43255_cites_the_denial',
                    report(P5=ADV, P6=CLEAN_ULCER, P7=e5.CLIPS, P8=NONE_REQUIRED, P9=NORMAL),
                    [e5.examination(), e5.clip(), none_required()], [('43255', (NONE_REQUIRED,))], lesions=[ULCER]))
P2_ADJECTIVE = mine(case('d157_p2_hemostatic_cautery_then_denial_43255_cites_the_denial',
                         report(P5=ADV, P6=CLEAN_ULCER, P7=HEMOSTATIC_CAUTERY, P8=NONE_REQUIRED, P9=NORMAL),
                         [e5.examination(), cautery_act(HEMOSTATIC_CAUTERY, kind_words='Hemostatic cautery'),
                          none_required()], [('43255', (NONE_REQUIRED,))], lesions=[ULCER]))
# the timed device-named cautery with the denial cited alone: 7.4 asks of the act in doubt its time, as f9013e12e did
TIMED_CAUTERY = 'At that time, cautery was applied to the ulcer base.'
X4_TIMED = mine(case('d157_iv_timed_cautery_then_denial_43255_cites_the_denial',
                     report(P5=ADV, P6=CLEAN_ULCER, P7=TIMED_CAUTERY, P8=NONE_REQUIRED, P9=NORMAL),
                     [e5.examination(),
                      cautery_act(TIMED_CAUTERY, kind_words='cautery',
                                  time=at('current_encounter', 'At that time', ['P7'])),
                      none_required()], [('43255', (NONE_REQUIRED,))], lesions=[ULCER]))
# the control: the denial with no act of the kind beside it - the rule's own outcome, an exclusion
DENIAL_ALONE = mine(case('d157_control_denial_alone_43255', report(P5=ADV, P6=CLEAN_ULCER, P7=NONE_REQUIRED, P8=NORMAL),
                         [e5.examination(), none_required('E2', 'P7')], [('43255', (NONE_REQUIRED,))], lesions=[ULCER]))

# --- (3) the service slot: the timed device-named cautery (in doubt) before the timed biopsy ------------------------

TIMED_LINES = report(P5=ADV, P6=CLEAN_ULCER, P7=TIMED_CAUTERY, P8=e5c.TIMED_BIOPSY_LINE, P9=NORMAL)


def timed_events(biopsy: bool = True) -> list:
    act = cautery_act(TIMED_CAUTERY, kind_words='cautery', time=at('current_encounter', 'At that time', ['P7']))
    return [e5.examination(), act] + ([copy.deepcopy(e5c.TIMED_BIOPSY)] if biopsy else [])


Q2 = mine(case('d157_ii_timed_cautery_then_timed_biopsy_43255_43235', TIMED_LINES, timed_events(),
               [('43255', (TIMED_CAUTERY,)), ('43235', (ADV,))], lesions=[ULCER]))
Q2_ALONE = mine(case('d157_ii_timed_cautery_then_timed_biopsy_43255', TIMED_LINES, timed_events(),
                     [('43255', (TIMED_CAUTERY,))], lesions=[ULCER]))
Q2_ONLY = mine(case('d157_ii_timed_cautery_alone_43255', report(P5=ADV, P6=CLEAN_ULCER, P7=TIMED_CAUTERY, P8=NORMAL),
                    timed_events(biopsy=False), [('43255', (TIMED_CAUTERY,))], lesions=[ULCER]))
RF11, RF11_ALONE = e5c.RF11, e5c.RF11_ALONE
NAMES.extend((RF11, RF11_ALONE))
CAUTERY_TIME_QUESTION = ('Was the possible bleeding control (electrocautery) of the 12 mm clean-based ulcer in the '
                         'gastric antrum (“was applied”) done at this encounter?')

# --- (4) recorded: the polypectomy-site cautery (D30's adjunct), and FRESH's denial with 45382 on the cautery ------

HOT_POLYP = 'A 12 mm sessile polyp in the transverse colon was removed with a hot snare.'
SITE_CAUTERY = 'Cautery was applied to the polypectomy site.'
ADJ_COLON = mine(case('d157_iii_colon_cautery_of_the_polypectomy_site_45385_45382',
                      report('COLONOSCOPY REPORT', P5=CECUM, P6=HOT_POLYP, P7=SITE_CAUTERY,
                             P8='No other lesion was seen.'),
                      [copy.deepcopy(e5c.COLON_EXAM),
                       event('E2', COLON, at('snare', 'removed with a hot snare', ['P6']),
                             status=at('performed', 'was removed', ['P6']),
                             technique=at('hot_snare', 'hot snare', ['P6']),
                             target=tgt('L1', 'transverse_colon', 'A 12 mm sessile polyp in the transverse colon',
                                        ['P6']),
                             purpose=at('removal', 'removed', ['P6'])),
                       control(SITE_CAUTERY, kind_words='Cautery', technique_words='Cautery',
                               target_words='the polypectomy site', eid='E3', procedure=COLON,
                               landmark='transverse_colon')],
                      [('45385', (HOT_POLYP,)), ('45382', (SITE_CAUTERY,))],
                      lesions=[lesion('L1', '12 mm sessile polyp', 'transverse_colon', 'transverse colon', '12 mm',
                                      ['P6', 'P7'])], reach=COLON_REACH))
FRESH_ON_CAUTERY = mine(case('d157_iii_colon_fresh_denial_45382_cites_the_cautery_45385', COLON_DEN_LINES,
                             colon_denial_events(SCOPES['lesion']), [('45382', (AT_SITE,)), ('45385', (SNARED,))],
                             lesions=COLON_LESIONS, reach=COLON_REACH))

# --- the costs that return (round 5c's egd3 problem 1, D149 (2)'s releases; egd4 problem 3) ------------------------

DUAL = 'Epinephrine was injected into the ulcer base, followed by bipolar cautery.'
A6 = mine(case('d157_cost_a6_dual_therapy_beside_the_oozing_vessel_43255',
               report(P5=ADV, P6=VESSEL, P7=DUAL, P8=NORMAL),
               [e5.examination(),
                event('E2', EGD, at('injection', 'injected', ['P7']), status=at('performed', 'was injected', ['P7']),
                      technique=at('injection', 'Epinephrine', ['P7']),
                      target=tgt('L1', 'gastric_antrum', 'the ulcer base', ['P7'])),
                event('E3', EGD, at('bleeding_control', 'bipolar cautery', ['P7']),
                      status=at('performed', 'followed by', ['P7']),
                      technique=at('electrocautery', 'bipolar cautery', ['P7']),
                      target=tgt('L1', 'gastric_antrum', 'the ulcer base', ['P7']))],
               [('43255', (DUAL,))], lesions=[VESSEL_ULCER]))
TREAT = 'Bipolar cautery was applied to treat the ulcer.'
P3_TREAT = ulcer_case('d157_cost_bipolar_to_treat_the_ulcer_43255', TREAT,
                      control(TREAT, kind_words='Bipolar cautery', technique_words='Bipolar cautery',
                              target_words='the ulcer', purpose='hemostasis', purpose_words='to treat the ulcer'),
                      [('43255', (TREAT,))], finding=VESSEL, finding_lesion=VESSEL_ULCER)


def kind_of(name: str, eid: str = 'E2') -> str:
    return events.Reading.of(built(name)[0]).events[eid]['catalogue_kind']


def listed(result) -> list:
    return [(item['act'], item['reason'], item['second_review'], list(item['events']))
            for item in result.completeness['unresolved_items']]


def service(result) -> list:
    return [(spec.fact, spec.question) for spec in result.clarifications]


def scope_question(statement: str) -> str:
    return f'Does “{statement}” apply to the bleeding control this code accounts for?'


def cautery_scope_question(statement: str, what: str = 'the 12 mm clean-based ulcer in the gastric antrum') -> str:
    return (f'Does “{statement}” apply to the possible bleeding control (electrocautery) of {what} '
            '(“was applied”)?')


def stored(family: str, *, kind_words: str = 'Cautery', technique_words: str = 'Cautery') -> dict:
    """A performed bleeding_control event of ``family`` in its stored shape, its purpose not stated, as far as
    hemostasis_in_doubt reads it."""
    def record(value, text='', state='verified'):
        return {'value': value, 'state': state, 'open': False, 'basis': 'stated',
                'words': {'text': text, 'start': 0, 'end': len(text)} if text else None}
    return {'id': 'E2', 'family': family, 'kind': record('bleeding_control', kind_words),
            'status': record('performed', 'was applied'), 'target': record('not_stated', ''),
            'technique': record('electrocautery', technique_words), 'purpose': record('not_stated', '', 'absent')}


class D157WithdrawnWhereTheCatalogueListsTheControl(SimpleTestCase):
    """(1) egd4 problem 0 (critical): f9013e12e READY on (a)-(d) (D149's key), e5628be56 and c2e53f8e hold them -
    c2e53f8e: 45382 held [performed_status] (45378 base_included), 43255 held [performed_status] on (b) and (c), and on
    (d) 43255 held beside 43236 READY / 43270 READY. Egd5's (i) rows: f9013e12e lists the control not covered (coding
    incomplete); e5628be56 and c2e53f8e list nothing (complete_pending_review)."""

    def test_d157_egd4_problem0_a_the_colonoscopy_cautery_at_this_site_is_in_doubt(self):
        with self.subTest(part='a bleeding control in doubt'):
            self.assertEqual(kind_of(P0A), POSSIBLE)
        result = assessed(P0A)
        held(self, result, '45382', ['performed_status'])
        held_base(self, result, '45378', '45382')
        result = assessed(P0A_ALONE)
        held(self, result, '45382', ['performed_status'])
        with self.subTest(part='listed in doubt, coding incomplete'):
            self.assertEqual((listed(result), result.completeness['state']),
                             ([(POSSIBLE, 'in_doubt', False, ['E2'])], 'incomplete'))

    def test_d157_egd4_problem0_b_c_device_named_controls_beside_the_clean_based_ulcer_are_in_doubt(self):
        for name in (P0B, P0B_BASE, P0C_PREVENT, P0C_HEMOCLIPS, P0C_CLIPS):
            with self.subTest(case=name):
                self.assertEqual(kind_of(name), POSSIBLE)
                held(self, assessed(name), '43255', ['performed_status'])
        held_base(self, assessed(P0B_BASE), '43235', '43255')

    def test_d157_egd4_problem0_d_43255_is_never_ready_on_the_wrong_act(self):
        for name, other in ((P0D_EPI, '43236'), (P0D_APC, '43270')):
            result = assessed(name)
            with self.subTest(case=name):
                held(self, result, '43255', ['performed_status'])
                self.assertNotEqual(proposal(result, other).status, 'ready')  # held on f9013e12e too (a cost)

    def test_d157_alternative2_the_key_stays_where_the_catalogue_lists_no_bleeding_control(self):
        for name, code, eid in ((L_ERCP, '43262', 'E4'), (L_ERCP_EPI, '43262', 'E4'), (L_EUS, '43242', 'E3')):
            with self.subTest(case=name):
                self.assertEqual(kind_of(name, eid), CONTROL)
                result = assessed(name)
                self.assertEqual(proposal(result, code).status, 'ready')
                self.assertEqual((listed(result), result.completeness['state']),
                                 ([(CONTROL, 'not_covered', True, [eid])], 'incomplete'))

    def test_d157_the_key_reads_the_familys_catalogue_acts(self):
        """Structural: in doubt where the family's catalogue acts list the bleeding control, whatever names it;
        elsewhere (and with no family) only when the adjective names it, as D149 keys it."""
        families = sorted(catalogue.CATALOGUE) + ['']
        listing = {family for family in families if catalogue.entry(family) is not None
                   and CONTROL in catalogue.entry(family).acts}
        self.assertEqual(listing, {'gi.egd', 'gi.enteroscopy', 'gi.colonoscopy', 'gi.flex_sig'})
        for family in families:
            with self.subTest(family=family, named='device'):
                self.assertEqual(mapping.hemostasis_in_doubt(stored(family)), family in listing)
            with self.subTest(family=family, named='adjective'):
                self.assertTrue(mapping.hemostasis_in_doubt(stored(family, kind_words='Hemostatic cautery',
                                                                   technique_words='cautery')))


class D157DenialNeverOutweighsADoubt(SimpleTestCase):
    """(2), D154's class (iv), and (5), the round-5e review's problem 2: f9013e12e holds the device-named inputs
    [statement_scope] (its control done, the denial unresolved with it; the timed one [event_time]) but excludes (5)'s;
    e5628be56 excludes every one. c2e53f8e holds the EGD inputs [performed_status] and EXCLUDES the colonoscopy's
    (FRESH's denial cited alone). Here each is held with the question 7.4 asks of the act in doubt - f9013e12e's, the
    act now named as a possible bleeding control - asked through the code, so the identical service question is not
    asked twice (D89); with no 7.4 question on the act, the statement_scope question on the denial."""

    def test_d157_iv_the_cautery_then_the_denial_cited_alone_is_held_never_excluded(self):
        for name in (X1, X1_BASE):
            result = assessed(name)
            with self.subTest(case=name):
                held(self, result, '43255', ['statement_scope'])
                p = proposal(result, '43255')
                self.assertEqual((p.support['reason'], p.support['question_events'], p.clarifications[0].question),
                                 (events.UNRESOLVED, ['E2', 'E3'], cautery_scope_question(NONE_REQUIRED)))
                self.assertIsNone(p.support.get('exclusion'))
            with self.subTest(case=name, part='the cautery stays listed in doubt; its question asked once, by 43255'):
                self.assertEqual(listed(result), [(POSSIBLE, 'in_doubt', False, ['E2'])])
                self.assertEqual(service(result), [])
        held_base(self, assessed(X1_BASE), '43235', '43255')

    def test_d157_iv_the_timed_cautery_then_the_denial_cited_alone_asks_its_time(self):
        """f9013e12e held 43255 [event_time] (the relation on the time); e5628be56 excluded it and asked the same
        question at service scope."""
        result = assessed(X4_TIMED)
        held(self, result, '43255', ['event_time'])
        p = proposal(result, '43255')
        self.assertEqual((p.support['question_events'], p.clarifications[0].question),
                         (['E2', 'E3'], CAUTERY_TIME_QUESTION))
        self.assertEqual((service(result), listed(result)), ([], [(POSSIBLE, 'in_doubt', False, ['E2'])]))

    def test_d157_iv_the_one_sentence_twin_is_held(self):
        result = assessed(X2)
        held(self, result, '43255', ['statement_scope'])
        self.assertEqual(proposal(result, '43255').support['question_events'], ['E2', 'E3'])
        self.assertEqual(listed(result), [(POSSIBLE, 'in_doubt', False, ['E2'])])

    def test_d157_iv_freshs_denial_filing_cited_alone_by_45382_is_held(self):
        for label, name in X3.items():
            result = assessed(name)
            with self.subTest(scope=label):
                held(self, result, '45382', ['statement_scope'])
                # FRESH's own scope words relate the denial to no act: the statement_scope question on the denial
                self.assertEqual(proposal(result, '45382').support['question_events'],
                                 ['E4', 'E2'] if label == 'fresh' else ['E2', 'E4'])
                self.assertEqual(proposal(result, '45385').status, 'ready')
                self.assertEqual(listed(result), [(POSSIBLE, 'in_doubt', False, ['E2'])])

    def test_d157_problem2_the_clip_and_the_adjective_named_cautery_beside_the_denial_are_held(self):
        # the clip has no relation to the denial: the statement_scope question on the denial names it after the denial
        for name, named in ((P2_CLIP, ['E3', 'E2']), (P2_ADJECTIVE, ['E2', 'E3'])):
            result = assessed(name)
            with self.subTest(case=name):
                self.assertEqual(kind_of(name), POSSIBLE)
                held(self, result, '43255', ['statement_scope'])
                self.assertEqual(proposal(result, '43255').support['question_events'], named)
                self.assertEqual(listed(result), [(POSSIBLE, 'in_doubt', False, ['E2'])])

    def test_d157_control_a_denial_with_no_act_in_doubt_still_excludes(self):
        """c2e53f8e holds it [performed_status]; every new-path head excludes it (the rule's own outcome, unchanged)."""
        p = proposal(assessed(DENIAL_ALONE), '43255')
        self.assertEqual((p.bucket, p.status), ('excluded', 'excluded'))

    def test_d157_control_a_partial_cover_is_asked_as_before(self):
        """43255 citing the act and the denial: the statement_scope question on the denial alone, as e5628be56 asks
        it, and the cautery's own service question."""
        result = assessed(X1_BOTH)
        held(self, result, '43255', ['statement_scope'])
        self.assertEqual(proposal(result, '43255').support['question_events'], ['E3'])
        self.assertEqual(service(result), [('statement_scope', cautery_scope_question(NONE_REQUIRED))])


class D157ServiceSlotPassesToTheNextActInDoubt(SimpleTestCase):
    """(3), D154's class (ii) and the round-5e review's problem 1: f9013e12e (43255 held event_time on the cautery) and
    e5628be56 (43255 not documented; D142's profile order) ask the biopsy's question; c2e53f8e asks none (the biopsy
    listed not covered). RF11: f9013e12e asks the clip's, e5628be56 the biopsy's."""

    def test_d157_ii_the_timed_cautery_yields_the_slot_to_the_biopsy(self):
        for name in (Q2, Q2_ALONE):
            result = assessed(name)
            with self.subTest(case=name):
                held(self, result, '43255', ['performed_status'])
                self.assertEqual(proposal(result, '43255').support['question_events'], ['E2'])
                self.assertEqual(service(result), [('event_time', e5c.BIOPSY_QUESTION)])
                self.assertEqual(listed(result), [(POSSIBLE, 'in_doubt', False, ['E2']),
                                                  ('biopsy', 'in_doubt', False, ['E3'])])

    def test_d157_rf11_the_clip_43255_names_yields_the_slot_to_the_biopsy(self):
        for name in (RF11, RF11_ALONE):
            result = assessed(name)
            with self.subTest(case=name):
                self.assertEqual(proposal(result, '43255').support['question_events'], ['E2'])
                self.assertEqual(service(result), [('event_time', e5c.BIOPSY_QUESTION)])

    def test_d157_a_named_act_keeps_its_slot_when_no_other_act_takes_it(self):
        """No fact is dropped: with no other act in doubt the cautery's own question is still asked, as e5628be56
        asks it (f9013e12e asked it through 43255's event_time)."""
        result = assessed(Q2_ONLY)
        held(self, result, '43255', ['performed_status'])
        self.assertEqual(service(result), [('event_time', CAUTERY_TIME_QUESTION)])

    def test_d157_act_identity_only(self):
        """coverage.in_doubt_questions over the timed reading: an act named by a code's question yields the slot; an
        event that is not in doubt (the examination) moves nothing; no fact is ever lost."""
        reading = events.Reading.of(built(Q2)[0])
        item = {'service': 'gi.egd', 'family': 'gi.egd'}
        for holding, expected in (((), CAUTERY_TIME_QUESTION), (('E2',), e5c.BIOPSY_QUESTION),
                                  (('E1',), CAUTERY_TIME_QUESTION), (('E3',), CAUTERY_TIME_QUESTION),
                                  (('E2', 'E3'), CAUTERY_TIME_QUESTION)):
            with self.subTest(holding=holding):
                found = coverage.in_doubt_questions(reading, coverage.Coverage(in_doubt=[(item, 'E2'), (item, 'E3')]),
                                                    holding=holding)
                self.assertEqual([(spec.fact, spec.question) for spec in found], [('event_time', expected)])

    def test_d157_assess_passes_the_proposals_question_events(self):
        tree = ast.parse((APP / 'studio' / 'interpretation' / 'assess.py').read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == 'in_doubt_questions']
        self.assertEqual([(len(call.args), [k.arg for k in call.keywords]) for call in calls], [(3, ['holding'])])
        self.assertIn("'question_events'", ast.unparse(calls[0].keywords[0].value))


class D157RecordedReturns(SimpleTestCase):
    """(4) RECORDED: a code's own question returns to e5628be56's - f9013e12e asked act_target (the polypectomy-site
    cautery's bundling question), event_time (the timed cautery's) or statement_scope (FRESH's denial with 45382 on the
    cautery), each through the control it read as done. c2e53f8e holds each [performed_status]."""

    def test_d157_recorded_the_codes_own_question_is_e5628be56s(self):
        result = assessed(ADJ_COLON)
        held(self, result, '45382', ['performed_status'])
        with self.subTest(part='the polypectomy-site cautery listed in doubt'):
            self.assertEqual(listed(result), [(POSSIBLE, 'in_doubt', False, ['E3'])])
        held(self, assessed(Q2), '43255', ['performed_status'])
        result = assessed(FRESH_ON_CAUTERY)
        held(self, result, '45382', ['performed_status'])
        with self.subTest(part="FRESH's denial: the statement_scope question asked of the cautery, at service scope"):
            self.assertEqual(service(result), [('statement_scope', cautery_scope_question(
                NO_CAUTERY, 'the 4 mm angioectasia in the cecum'))])


class D157ReturningCosts(SimpleTestCase):
    """The costs that return: c2e53f8e READY on both (A6 with the injection listed not covered; the bipolar cautery to
    treat the ulcer complete_pending_review); held here, as e5628be56 holds them."""

    def test_d157_cost_a6_and_the_bipolar_cautery_to_treat_the_ulcer_are_held(self):
        result = assessed(A6)
        held(self, result, '43255', ['performed_status'])
        self.assertEqual(listed(result), [('injection', 'not_covered', True, ['E2']),
                                          (POSSIBLE, 'in_doubt', False, ['E3'])])
        held(self, assessed(P3_TREAT), '43255', ['performed_status'])
