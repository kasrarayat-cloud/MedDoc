"""H4: the assess battery. Each row is a synthetic document with a synthetic provider answer (codes with exact
evidence), read as the stages read it: the analyze child's facts and routing (jobs._analyze_child), the member's answer
merged (jobs._merged_facts), and the assess child (jobs._assess_child) with an in-memory answer and no reference rows.
In-process and offline: nothing is sent and no database is read.

Permanent rows: the minimal design's 28 cases (its battery.py, verbatim), the judge's J1-J8, K1-K3, E1-E4 and S1-S3
(judge_battery.py, verbatim), the h4-05 counterfactual (the judge's F1: 43259 citing the narrative is EXCLUDED as
installed, the agreement gate's excluding side; package PA declares it moving to held), and package PA's PA1-PA3 (the
gate's second reader: two that disagree, held; one that agrees under its section's own heading, excluded), and the
R8 register rows (prefix 'R8 ', package P2 READ-HOLD of 2026-11-03: the previously reported false READYs of R8 section
1.2, each with its controls; tests/fixtures/gi4/declarations/cux-hold.json declares their movements). A row may cite
several passages for one code (a tuple of quotes) and be read with a member's answer (R8_USER: the regression walk's
date). Each code carries a PROVISIONAL truth (no qualified GI coder has reviewed it):
  done             performed today: an exclusion is a violation
  done_incomplete  performed today, incompletely: an exclusion is a violation, and READY needs an incompleteness signal
                   (a modifier consideration or a non-pass check)
  not_done         not performed today: READY is a violation
  unsupported      performed today but the cited basis cannot support the code: READY and exclusion are violations
  no_ready         READY is a violation; an exclusion is not judged
  MAY              careful coders could differ (or the second review disputes it): never judged
Properties: no READY where the truth says not done today; no exclusion where it says done; and every movement against
another tree classified against the package's declaration (``--declare FILE``: "battery": [[row, code, from, to]]).

  python -m ops.gi4.battery [--tree DIR] [--only SUBSTRING]
  python -m ops.gi4.battery --base REF|DIR --head REF|DIR [--declare FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from types import SimpleNamespace

from ops.gi4 import boot

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
H405 = (boot.HARNESS_TREE / 'tests' / 'fixtures' / 'gi4' / 'regression' / 'h4-05.txt').read_text(encoding='utf-8')
FILL = ''.join(f'Line {i} of the outside summary lists medications and allergies in detail.\n' for i in range(8))
SNARE = 'A 10 mm polyp was removed with a hot snare.'
# package P2 READ-HOLD's register rows (R8 section 1.2, probes/R8-history-defects/r8_cases.py): their shared texts
R8_COLON = (B + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery '
            'center\nProcedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was '
            'completed.\n')
R8_CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
R8_CO_SNARE = 'A 7 mm polyp in the ascending colon was removed with a cold snare.'
R8_FS_BIOPSY = 'Biopsies of the rectal mucosa were taken with cold forceps.'
R8_EGD_DX = (B + 'Upper endoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory '
             'surgery center\nProcedure: EGD\nThe gastroscope was advanced to the second portion of the duodenum.\n')
R8_SEEN = 'A 9 mm pedunculated polyp in the sigmoid colon was seen.'
R8_SNARE_HEAD = R8_COLON.replace('Procedure: Colonoscopy', 'Procedure: Colonoscopy with hot snare polypectomy')
R8_TOP = B + 'Procedure report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
R8_COLON7N = ('Colonoscopy: The colonoscope was advanced to the cecum and the examination was completed. The colon was '
              'normal. No biopsies were taken.')
R8_COLON1 = ('Colonoscopy: The colonoscope was advanced to the cecum and the examination was completed. The colon was '
             'normal. No polyps were seen.')
R8_TODAY_BX = 'A 4 mm polyp in the transverse colon was biopsied with cold forceps.'
R8_DIAG = B + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
R8_CECUM_LM = ('The colonoscope was advanced to the cecum, identified by the appendiceal orifice and ileocecal valve.')
R8_LAST = 'Last colonoscopy: 9 mm polyp removed with hot snare.'
R8_INDICATION = 'Indication: Surveillance after a sigmoid polyp was removed with a hot snare.'
R8_INDEX = 'At the index colonoscopy, a 9 mm polyp was removed with a hot snare.'
R8_L39 = ('Total time I spent on her care on the date of this visit: 52 minutes, covering her history, review of the '
          'outside results and note, the examination, counseling about the celiac work-up and keeping gluten in her diet, '
          'the orders, and documentation.')
R8_L40 = ('Complexity of decision making: moderate. One new problem with an uncertain diagnosis; outside results and an '
          'outside note reviewed; tests ordered.')
R8_TWIN = R8_L39.replace(' the orders,', '', 1)  # h4-01's time statement, orders-free (R8 D12's chassis)
R8_CC = 'Loose stools, bloating and tiredness for about four months.'
R8_PROC = B + 'Procedure report (fictional)\nDate of service: 2026-11-03\nPlace of service: Ambulatory surgery center\n'
R8_SNARED = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
R8_HISTORY = 'History: a hot snare polypectomy of a rectal polyp was performed at an outside colonoscopy in 2023.'
R8_COMBINED = (R8_PROC + 'Procedure: Upper endoscopy and colonoscopy\nUPPER ENDOSCOPY: The gastroscope was advanced to '
               'the second part of the duodenum.\nCold forceps biopsies were obtained from the gastric antrum.\n'
               'COLONOSCOPY: The colonoscope was advanced to the cecum.\n' + R8_SNARED + '\n')
R8_EGD = (B + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
          'Procedure: EGD\nThe endoscope was advanced to the second part of the duodenum.\n')
R8_ERCP = (B + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
           'Procedure: ERCP\nThe duodenoscope was advanced to the major papilla.\nDeep biliary cannulation was '
           'achieved.\n')


def _r8(head, *lines):
    return head + ''.join(line + '\n' for line in lines)


def _r8_edit(text, *pairs):
    for old, new in pairs:
        assert text.count(old) == 1, old[:60]
        text = text.replace(old, new, 1)
    return text


R8_EM = _r8_edit((boot.HARNESS_TREE / 'tests' / 'fixtures' / 'gi4' / 'regression' / 'h4-01.txt').read_text(
    encoding='utf-8'), ('\n' + R8_L40, ''), (R8_L39, R8_TWIN))


R8_NAMED_EGD = _r8_edit((boot.HARNESS_TREE / 'tests' / 'fixtures' / 'gi4' / 'regression' / 'h4-03.txt').read_text(
    encoding='utf-8'), ('Variceal Banding Session', 'EGD with Variceal Band Ligation'))
R8_STOPPED = _r8_edit(R8_NAMED_EGD, ('Retroflexion showed no gastric varices.',
                                     'Retroflexion showed no gastric varices. We stopped in the stomach.'))
R8_BANDS_PASSED = 'The gastroscope was withdrawn, fitted with a multiband ligation device and passed again.'
R8_BANDS = 'Large esophageal varices with red wale marks; six bands placed for primary prophylaxis.'


def _r8_earlier(line):
    """R8 time-1's document: an earlier colonoscopy's polypectomy on its own line, then today's diagnostic one."""
    return (R8_DIAG + line + '\nProcedure: Colonoscopy\n' + R8_CECUM_LM + '\nA 15 mm sessile polyp was seen in the '
            'transverse colon and was not removed today.\n')


# (text, [(code, quote, truth)]); a truth 'X|MAY' is the author's X disputed by the second review (judged as MAY)
CASES = {
    # --- the minimal design's 28 (S1 / R1 / S3 / E1: occurrences, history, plans) ---
    'polyp details history': (B + 'Date of service: 10/27/2026\n\nPrior Procedures\nColonoscopy in 2023.\n\nPolyp Details\n'
                              'A 6 mm sigmoid polyp was removed by cold snare.\n\nProcedure: Colonoscopy\nThe colonoscope '
                              'was advanced to the cecum. No polyps were found.\n',
                              [('45385', 'A 6 mm sigmoid polyp was removed by cold snare.', 'not_done'),
                               ('45378', 'The colonoscope was advanced to the cecum.', 'done')]),
    'sig report, planned colonoscopy': (B + 'Date of service: 10/27/2026\nEndoscopy note\nThe sigmoidoscope was advanced to '
                                        '40 cm. A 5 mm polyp at 20 cm was removed by cold snare.\nPlan: colonoscopy in '
                                        '3 years.\n',
                                        [('45385', 'A 5 mm polyp at 20 cm was removed by cold snare.', 'not_done'),
                                         ('45338', 'A 5 mm polyp at 20 cm was removed by cold snare.', 'done')]),
    'report from 2023 (deictic)': (B + 'Date of service: 10/27/2026\nProcedure: Colonoscopy\nThe colonoscope was advanced '
                                   'to the cecum. No polyps were found.\n\nPrior Records\nThis is his colonoscopy report '
                                   'from 2023; a 6 mm polyp was removed by cold snare.\n',
                                   [('45378', 'The colonoscope was advanced to the cecum.', 'done'),
                                    ('45385', 'a 6 mm polyp was removed by cold snare.', 'not_done')]),
    'earlier colonoscopy in EGD indication': (B + 'Date of service: 10/27/2026\nIndication: Surveillance; at her colonoscopy '
                                              'last year a 6 mm polyp was removed by cold snare.\nProcedure: EGD to the '
                                              'second part of the duodenum with cold forceps biopsies of the antrum.\n',
                                              [('45385', 'a 6 mm polyp was removed by cold snare', 'not_done'),
                                               ('43239', 'EGD to the second part of the duodenum with cold forceps '
                                                         'biopsies of the antrum', 'done')]),
    'index examination after prior studies': (B + 'Colonoscopy Report\nDate of service: 2026-10-15\nPrior Studies\nEGD '
                                              '2024-01-12: normal.\nIndex Examination\nThe colonoscope reached the cecum; a '
                                              '6 mm polyp was removed by cold snare.\nToday\'s Examination\nThe colonoscope '
                                              'reached the cecum. No polyps were found.\n',
                                              [('45385', 'a 6 mm polyp was removed by cold snare.', 'not_done'),
                                               ('45378', 'No polyps were found.', 'done')]),
    'dated history instrument narration': (B + 'Upper Endoscopy Report\nDate of service: October 19, 2026\nHistory: At her '
                                           '2023 colonoscopy the colonoscope reached the cecum.\nFindings: The gastroscope '
                                           'was advanced to the second part of the duodenum. The mucosa was normal.\n',
                                           [('43235', 'The gastroscope was advanced to the second part of the duodenum.',
                                             'done'),
                                            ('45378', 'the colonoscope reached the cecum.', 'not_done')]),
    'colonoscopy never started': (B + 'Colonoscopy Report\nDate of service: 10/19/2026\nFindings: The colonoscopy was never '
                                  'started because she had eaten breakfast that morning.\n',
                                  [('45378', 'The colonoscopy was never started because she had eaten breakfast that '
                                             'morning.', 'not_done')]),
    'past negation + today denial': (B + 'Colonoscopy Report\nDate of service: October 19, 2026\nIndication: iron '
                                     'deficiency anemia. She has never had a colonoscopy.\nFindings: The bowel preparation '
                                     'was inadequate, so no colonoscopy was performed today.\n',
                                     [('45378', 'She has never had a colonoscopy.', 'not_done')]),
    'gastroscope to descending colon (sig)': (B + 'Flexible Sigmoidoscopy Report\nDate of service: 10/19/2026\nFindings: The '
                                              'gastroscope was advanced to the descending colon. Biopsies were taken from '
                                              'the sigmoid colon.\n', [('45331', 'Biopsies were taken from the sigmoid '
                                                                                 'colon.', 'done')]),
    'duodenoscope (ERCP)': (B + 'ERCP Report\nDate of service: 10/19/2026\nFindings: The duodenoscope was advanced to the '
                            'second part of the duodenum. The bile duct was cannulated and a sphincterotomy was performed.\n',
                            [('43262', 'a sphincterotomy was performed', 'done')]),
    'gastroscopy in sig indication': (B + 'Flexible Sigmoidoscopy Report\nDate of service: 10/19/2026\nIndication: gastric '
                                      'biopsies at last month\'s gastroscopy showed H. pylori.\nFindings: The sigmoidoscope '
                                      'was advanced to 40 cm. Normal mucosa.\n', [('45330', 'The sigmoidoscope was advanced '
                                                                                            'to 40 cm.', 'done')]),
    'colonoscope reaches cecum in a plan': (B + 'Office visit\nDate of service: 10/19/2026\nPlan: colonoscopy next month; the '
                                            'colonoscope reached the cecum at her 2019 study.\n',
                                            [('45378', 'the colonoscope reached the cecum at her 2019 study.', 'not_done')]),
    'colonoscope reaches cecum, undated other doc': (B + 'Office visit note\nDate of service: 10/19/2026\nOutside records '
                                                     'reviewed\nThe colonoscope reached the cecum and a 6 mm polyp was '
                                                     'removed by cold snare.\nAssessment and plan\nRepeat colonoscopy in 3 '
                                                     'years.\n', [('45385', 'a 6 mm polyp was removed by cold snare.',
                                                                   'not_done')]),
    # --- E1 / E2 / E4: completeness
    'stricture at 30 cm': (B + 'Colonoscopy Report\nDate of service: 10/19/2026\nFindings: The colonoscope could not be '
                           'advanced past a tight stricture at 30 cm. Biopsies of the stricture were taken.\n',
                           [('45380', 'Biopsies of the stricture were taken.', 'done_incomplete')]),
    'stricture, cecum named in plan': (B + 'Colonoscopy Report\nDate of service: 10/19/2026\nFindings: The colonoscope could '
                                       'not be advanced past a tight stricture at 30 cm.\nPlan: CT colonography to examine '
                                       'the cecum and terminal ileum.\n',
                                       [('45378', 'The colonoscope could not be advanced past a tight stricture at 30 cm.',
                                         'done_incomplete')]),
    'unpassed pylorus (steered)': (B + 'Upper Endoscopy Report\nDate of service: October 19, 2026\nFindings: The gastroscope '
                                   'was introduced by mouth and steered through the stomach, but the pylorus could not be '
                                   'passed into the duodenum.\n', [('43235', 'The gastroscope was introduced by mouth and '
                                                                             'steered through the stomach',
                                                                    'done_incomplete')]),
    'colorectal anastomosis at 15 cm': (B + 'Procedure: Colonoscopy\nDate of service: 10/27/2026\nHistory: low anterior '
                                        'resection in 2024 with a colorectal anastomosis.\nReach of the examination: '
                                        'colorectal anastomosis at 15 cm; the scope could not be passed beyond it.\n',
                                        [('45378', 'Reach of the examination: colorectal anastomosis at 15 cm', 'MAY')]),
    'outside endpoint line, routing silent': (B + 'Colonoscopy\nDate of service: 10/19/2026\nThe scope stopped in the '
                                              'sigmoid colon because of looping.\nOutside report: Cecum: normal. Terminal '
                                              'ileum: normal.\n', [('45378', 'The scope stopped in the sigmoid colon because '
                                                                             'of looping.', 'done_incomplete')]),
    'withheld label + finding of cecum': (B + 'Colonoscopy Report\nDate of service: 10/19/2026\nColonoscopy was performed.\n'
                                          'Extent: Cecum | Scope: Olympus\nFindings: No polyps were seen in the cecum.\n',
                                          [('45378', 'Colonoscopy was performed.', 'done')]),
    # --- A1 / act binding
    'bulb hot snare + planned colonoscopy': (B + 'Upper and Lower Endoscopy\nDate of service: October 19, 2026\nThe '
                                             'gastroscope was advanced to the second part of the duodenum. In the duodenal '
                                             'bulb, 2 cm beyond the pylorus, a 6 mm polyp was removed with a hot snare.\nA '
                                             'colonoscopy will be scheduled.\n',
                                             [('43251', 'a 6 mm polyp was removed with a hot snare.', 'done')]),
    'two services, snare refers back': (B + 'Gastroscopy and Colonoscopy\nDate of service: 10/19/2026\nThe gastroscope was '
                                        'advanced to the second part of the duodenum. A 12 mm antral polyp was seen.\nA hot '
                                        'snare was closed around its stalk and the polyp was removed.\nThe colonoscope '
                                        'reached the cecum. No polyps were seen in the colon.\n',
                                        [('43251', 'A hot snare was closed around its stalk and the polyp was removed.',
                                          'done'),
                                         ('45378', 'The colonoscope reached the cecum.', 'done')]),
    'two services, colon polyp then it': (B + 'Gastroscopy and Colonoscopy\nDate of service: 10/19/2026\nThe gastroscope '
                                          'was advanced to the second part of the duodenum. The stomach was normal.\nThe '
                                          'colonoscope reached the cecum. A 7 mm sigmoid polyp was seen.\nIt was removed '
                                          'with a cold snare.\n', [('45385', 'It was removed with a cold snare.', 'done')]),
    # --- E/M (visit scope) with codes
    'telephone-only time': (B + 'Telephone encounter\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\n'
                            'Established patient\nThe patient was not seen in the office; we spoke by telephone about her '
                            'reflux.\nTotal time: 15 minutes.\n', [('99212', 'Total time: 15 minutes.', 'not_done')]),
    'last visit time': (B + 'Office visit note\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\nEstablished '
                        'patient\nChief complaint\nHeartburn.\nAssessment and plan\nGERD. Continue omeprazole.\nTotal time '
                        'at her last visit was 40 minutes.\n',
                        [('99213', 'Total time at her last visit was 40 minutes.', 'unsupported')]),
    'future visit time': (B + 'Office visit note\nDate of service: 10/26/2026\nPlace of service: office (POS 11)\n'
                          'Established patient\nChief complaint\nHeartburn.\nAssessment and plan\nGERD.\nTotal time 30 '
                          'minutes at the follow-up visit next month.\n',
                          [('99213', 'Total time 30 minutes at the follow-up visit next month.', 'unsupported')]),
    'elastography + framed time (S-R1)': (B + 'Hepatology clinic note\nDate of service: 2026-10-22\nPlace of service: '
                                          'office (POS 11)\nEstablished patient\nTransient elastography today: 6.1 kPa.\n'
                                          'Assessment and plan\nNo advanced fibrosis. Repeat in one year.\nPhysician time '
                                          'on the date of service: 20 minutes.\n',
                                          [('99213', 'Physician time on the date of service: 20 minutes.', 'no_ready')]),
    'return visit + ultrasound (V3)': (B + 'Office visit note\nDate of service: 10/26/2026\nPlace of service: office (POS '
                                       '11)\nEstablished patient\nChief complaint\nAscites.\nAssessment and plan\nReturn '
                                       'office visit in six months. Surveillance ultrasound in six months.\n',
                                       [('99213', 'Return office visit in six months. Surveillance ultrasound in six '
                                                  'months.', 'unsupported')]),
    'colonoscopy report physician time': (B + 'Colonoscopy Report\nDate of service: 10/26/2026\nSubjective\nScreening.\n'
                                          'Findings: The colonoscope was advanced to the cecum. No polyps.\nPhysician time '
                                          'on the date of service: 35 minutes for the colonoscopy.\n',
                                          [('99213', 'Physician time on the date of service: 35 minutes for the '
                                                     'colonoscopy.', 'not_done'),
                                           ('45378', 'The colonoscope was advanced to the cecum.', 'done')]),
    # --- the judge's J1-J8, E1-E4, S1-S3, K1-K3 (judge_battery.py) ---
    'J1 records review, unnamed family, long gap': (B + 'GI Records Review\nDate of service: 10/20/2026\n\nSummary of '
                                                    'outside records\nThe patient brought copies from Mercy GI.\n' + FILL
                                                    + 'The colonoscope reached the cecum. ' + SNARE + '\n\nAssessment\n'
                                                    'Adenoma history.\nPlan\nRepeat in three years.\n',
                                                    [('45385', SNARE, 'not_done')]),
    'J2 pasted 2024 report under unknown heading': (B + 'Clinic Correspondence\nDate of service: 10/20/2026\n\nAttached '
                                                    'Document\nMercy Endoscopy Center\n' + FILL + 'The colonoscope reached '
                                                    'the cecum, where the appendiceal orifice was photographed. ' + SNARE
                                                    + '\nSigned 03/02/2024.\n', [('45385', SNARE, 'not_done')]),
    'J3 teaching handout': (B + 'Patient Education Handout\nDate of service: 10/20/2026\n\nWhat Happens During the Test\n'
                            'The colonoscope is a flexible tube. During the test the colonoscope reached the cecum in most '
                            'patients we studied.\n',
                            [('45378', 'During the test the colonoscope reached the cecum in most patients we studied.',
                              'not_done')]),
    'J4 records review, colonoscopy named in plan only': (B + 'GI Records Review\nDate of service: 10/20/2026\n\nSummary of '
                                                          'outside records\nThe patient brought copies from Mercy GI.\n'
                                                          + FILL + 'The colonoscope reached the cecum. ' + SNARE + '\n\n'
                                                          'Plan\nSurveillance colonoscopy in three years.\n',
                                                          [('45385', SNARE, 'not_done')]),
    'J5 EGD today + appended outside colonoscopy': (B + 'Upper Endoscopy Report\nDate of service: 10/20/2026\n\nProcedure\n'
                                                    'The gastroscope was advanced to the second part of the duodenum. Cold '
                                                    'forceps biopsies of the antrum were taken.\n\nAttached Report\n' + FILL
                                                    + 'The colonoscope reached the cecum. ' + SNARE + '\n',
                                                    [('43239', 'Cold forceps biopsies of the antrum were taken.', 'done'),
                                                     ('45385', SNARE, 'not_done')]),
    'J6 records review, family named in copied block': (B + 'GI Records Review\nDate of service: 10/20/2026\n\nSummary of '
                                                        'outside records\nThe patient brought copies from Mercy GI.\n' + FILL
                                                        + 'Colonoscopy at Mercy GI. The colonoscope was advanced to the '
                                                        'cecum. ' + SNARE + '\n\nAssessment\nAdenoma history.\n',
                                                        [('45385', SNARE, 'not_done')]),
    'J7 records review, completion rows only': (B + 'GI Records Review\nDate of service: 10/20/2026\n\nSummary of outside '
                                                'records\nThe patient brought copies from Mercy GI.\n' + FILL + 'Colonoscopy '
                                                'at Mercy GI.\nCecum: normal.\nTerminal ileum: normal.\nThe entire colon was '
                                                'examined. ' + SNARE + '\n\nAssessment\nAdenoma history.\n',
                                                [('45385', SNARE, 'not_done')]),
    'J8 surveillance office note, prior colonoscopy in history': (B + 'Colon Surveillance Visit\nDate of service: '
                                                                  '10/20/2026\n\nPrior Surgery and Cancer Care\nRight '
                                                                  'hemicolectomy in 2024. This is his surveillance '
                                                                  'colonoscopy review. Neoterminal ileum: normal. All of the '
                                                                  'remaining colon was inspected on withdrawal. ' + SNARE
                                                                  + '\n\nPlan\nNext colonoscopy in one year.\n',
                                                                  [('45385', SNARE, 'not_done|MAY')]),
    'E1 pre-procedure H&P with framed time': (B + 'Colonoscopy Report\nDate of service: 10/20/2026\nEndoscopist: Synthetic '
                                              'MD\nSedation: propofol by CRNA\n\nHistory of Present Illness\nIron '
                                              'deficiency anemia.\nPhysical Exam\nAbdomen soft.\nPhysician time on the date '
                                              'of service: 40 minutes.\n\nProcedure\nThe colonoscope was advanced to the '
                                              'cecum. No polyps.\n',
                                              [('99214', 'Physician time on the date of service: 40 minutes.', 'no_ready'),
                                               ('45378', 'The colonoscope was advanced to the cecum.', 'done')]),
    'E2 phone follow-up, framed time by telephone': (B + 'Hepatology Follow-up Note\nDate of service: 10/20/2026\nLocation: '
                                                     'GI clinic office, place of service 11\nEstablished patient\n\n'
                                                     'Subjective\nShe called to discuss her labs.\nAssessment and plan\n'
                                                     'Continue lactulose.\nPhysician time on the service date: 25 minutes, '
                                                     'by telephone.\n',
                                                     [('99214', 'Physician time on the service date: 25 minutes, by '
                                                                'telephone.', 'not_done')]),
    'E3 addendum time about a later review': (B + 'Hepatology Follow-up Note\nDate of service: 10/20/2026\nLocation: GI '
                                              'clinic office, place of service 11\nEstablished patient\n\nSubjective\n'
                                              'Fatigue.\nObjective\nNo jaundice.\nAssessment and plan\nRepeat labs.\n\n'
                                              'Addendum 10/24/2026\nPhysician time on the service date: 20 minutes '
                                              'reviewing the outside pathology.\n',
                                              [('99213', 'Physician time on the service date: 20 minutes reviewing the '
                                                         'outside pathology.', 'unsupported|MAY')]),
    'E4 visit template, time framed, nothing recorded': (B + 'Hepatology Follow-up Note\nDate of service: 10/20/2026\n'
                                                         'Location: GI clinic office, place of service 11\nEstablished '
                                                         'patient\n\nSubjective\nPatient did not arrive; no-show.\n'
                                                         'Physician time on the service date: 15 minutes.\n',
                                                         [('99212', 'Physician time on the service date: 15 minutes.',
                                                           'not_done')]),
    'S1 titled colonoscopy, past negation, no head fields': (B + 'Colonoscopy Report\nDate of service: 10/19/2026\n\n'
                                                             'Indication\nIron deficiency anemia. She has never had a '
                                                             'colonoscopy.\n\nFindings\nThe colonoscope reached the cecum; '
                                                             'the appendiceal orifice was photographed. Withdrawal lasted 12 '
                                                             'minutes. No polyps.\n',
                                                             [('45378', 'The colonoscope reached the cecum; the appendiceal '
                                                                        'orifice was photographed.', 'done')]),
    'S2 untitled two-service, past negation, no head fields': (B + 'Gastroscopy Then Colonoscopy\nDate of service: '
                                                               '10/19/2026\n\nWhy Both Were Done\nWeight loss. She has '
                                                               'never had a colonoscopy.\n\nLarge Bowel\nThe colonoscope '
                                                               'reached the cecum; the appendiceal orifice was photographed. '
                                                               'Withdrawal lasted 12 minutes.\n',
                                                               [('45378', 'The colonoscope reached the cecum; the '
                                                                          'appendiceal orifice was photographed.', 'done')]),
    'S3 cited the past negation only': (B + 'Gastroscopy Then Colonoscopy\nDate of service: 10/19/2026\n\nWhy Both Were '
                                        'Done\nWeight loss. She has never had a colonoscopy.\n\nLarge Bowel\nThe colonoscope '
                                        'reached the cecum; the appendiceal orifice was photographed. Withdrawal lasted 12 '
                                        'minutes.\n', [('45378', 'She has never had a colonoscopy.', 'unsupported')]),
    'K1 records review, copied banding narrative': (B + 'GI Records Review\nDate of service: 10/20/2026\n\nSummary of '
                                                    'outside records\nThe patient brought copies from Mercy GI.\n' + FILL
                                                    + 'The gastroscope was passed down the esophagus, through the stomach '
                                                    'and pylorus, into the descending duodenum. The duodenal bulb and '
                                                    'descending duodenum were normal. Six bands were placed at the '
                                                    'gastroesophageal junction.\n\nAssessment\nVarices, banded elsewhere.\n',
                                                    [('43244', 'Six bands were placed at the gastroesophageal junction.',
                                                      'not_done')]),
    'K2 office note with copied EGD named': (B + 'GI Records Review\nDate of service: 10/20/2026\n\nSummary of outside '
                                             'records\nThe patient brought copies from Mercy GI.\n' + FILL + 'EGD at Mercy '
                                             'GI. The esophagus, stomach, duodenal bulb and descending duodenum were '
                                             'normal. Six bands were placed at the gastroesophageal junction.\n\n'
                                             'Assessment\nVarices, banded elsewhere.\n',
                                             [('43244', 'Six bands were placed at the gastroesophageal junction.',
                                               'not_done')]),
    'K3 copied colonoscopy, completion statement': (B + 'GI Records Review\nDate of service: 10/20/2026\n\nSummary of '
                                                    'outside records\nThe patient brought copies from Mercy GI.\n' + FILL
                                                    + 'Colonoscopy at Mercy GI. The cecum and terminal ileum were normal. A '
                                                    '10 mm polyp was removed with a hot snare.\n\nAssessment\nAdenoma '
                                                    'history.\n', [('45385', 'A 10 mm polyp was removed with a hot snare.',
                                                                    'not_done')]),
    # --- the h4-05 counterfactual (the judge's F1; the diagnosis's S3): an EUS code citing the narrative under the
    # runaway "Prior Studies" section, which both readers read as historical from that one section ---
    'S3h h4-05 counterfactual, EUS code citing the narrative': (H405, [('43259', 'A linear echoendoscope was introduced '
                                                                                  'by mouth.', 'done')]),
    # --- package PA: the agreement gate's second reader (engine._agreed_not_done with no act of the code's kind in its
    # passage, then engine._second_reading). PA1 and PA2 reach it with a second reader that DISAGREES (held; an
    # always-agree gate would exclude them), PA3 with one that agrees under the section's own heading (excluded; a gate
    # that never agrees, or one that ignores the heading's reach, would hold it) ---
    'PA1 disagreeing second reader: a plan line it reads nothing in (EUS)': (
        B + 'Endoscopic Ultrasound Report\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol by '
        'CRNA\n\nProcedure\nA linear echoendoscope was introduced by mouth. The pancreas was examined from the head to the '
        'tail. A 12 mm cyst was seen in the pancreatic body.\n\nPlan\nReturn in one year with repeat imaging.\n',
        [('43259', 'Return in one year with repeat imaging.', 'unsupported')]),
    'PA2 disagreeing second reader: "No further" read as uncertain (EUS)': (
        B + 'Endoscopic Ultrasound Report\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol by '
        'CRNA\n\nProcedure\nA linear echoendoscope was introduced by mouth. The pancreas was examined from the head to the '
        'tail.\n\nPlan\nNo further endoscopic ultrasound is needed; the cyst was examined today.\n',
        [('43259', 'No further endoscopic ultrasound is needed; the cyst was examined today.', 'done')]),
    'PA3 agreeing second reader: a headed prior-procedures line (ERCP)': (
        B + 'ERCP Report\nDate of service: 10/20/2026\nEndoscopist: Synthetic MD\nSedation: propofol by CRNA\n\nPrior '
        'Procedures\nThe biliary stent was exchanged.\n\nProcedure\nThe duodenoscope was advanced to the second part of the '
        'duodenum. The bile duct was cannulated and a biliary sphincterotomy was performed.\n',
        [('43276', 'The biliary stent was exchanged.', 'not_done')]),
    # --- package P2 READ-HOLD (2026-11-03): the register's inputs (R8 section 1.2), READY on c9f20a148 where the truth
    # says not done; tests/fixtures/gi4/declarations/cux-hold.json declares each movement ---
    # D1: a failed or attempted act released by the own-passage path
    'R8 D1 N1 hot snare polypectomy failed': (
        _r8(R8_COLON, R8_SEEN, 'Hot snare polypectomy failed.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'Hot snare polypectomy failed.', 'not_done')]),
    'R8 D1 N2 attempted, could not be removed': (
        _r8(R8_COLON, R8_SEEN, 'Hot snare polypectomy was attempted but the polyp could not be removed.'),
        [('45378', R8_CECUM, 'done'),
         ('45385', 'Hot snare polypectomy was attempted but the polyp could not be removed.', 'not_done')]),
    'R8 D1 N3 biopsy attempted, no tissue': (
        _r8(R8_COLON, R8_SEEN, 'Cold forceps biopsy was attempted but no tissue was obtained.'),
        [('45378', R8_CECUM, 'done'),
         ('45380', 'Cold forceps biopsy was attempted but no tissue was obtained.', 'not_done')]),
    'R8 D1 N4 ERCP stent placement failed': (
        _r8(R8_ERCP, 'Biliary stent placement failed.'),
        [('43260', 'Deep biliary cannulation was achieved.', 'done'),
         ('43274', 'Biliary stent placement failed.', 'not_done')]),
    # D2: a failed act read as performed by the clause reader
    'R8 D2 N10 antral biopsy failed': (
        _r8(R8_EGD, 'A small nodule was seen in the gastric antrum.', 'Cold forceps biopsy of the antrum failed.'),
        [('43235', 'The endoscope was advanced to the second part of the duodenum.', 'done'),
         ('43239', 'Cold forceps biopsy of the antrum failed.', 'not_done')]),
    # D3: a denial read as done, or not tied to its act
    'R8 D3 N15 no polyps removed, snare header': (
        _r8(R8_SNARE_HEAD, R8_SEEN, 'No polyps were removed.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'No polyps were removed.', 'no_ready')]),
    'R8 D3 N17 polyp was not removed, snare header': (
        _r8(R8_SNARE_HEAD, R8_SEEN, 'The polyp was not removed.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'The polyp was not removed.', 'no_ready')]),
    'R8 D3 N16 we did not remove it, snare header': (
        _r8(R8_SNARE_HEAD, R8_SEEN, 'We did not remove the polyp.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'We did not remove the polyp.', 'no_ready')]),
    'R8 D3 release-0 none was snared': (
        _r8(R8_COLON, 'Three polyps were seen in the sigmoid colon.', 'Of the three polyps, none was snared.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'Of the three polyps, none was snared.', 'not_done')]),
    'R8 D3 release-0 at no point': (
        _r8(R8_COLON, R8_SEEN, 'At no point was the polyp snared.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'At no point was the polyp snared.', 'not_done')]),
    'R8 D3 release-0 without resection': (
        _r8(R8_COLON, 'The examination was completed without endoscopic resection of the 25 mm sigmoid polyp by hot '
                      'snare.'),
        [('45378', R8_CECUM, 'done'),
         ('45385', 'The examination was completed without endoscopic resection of the 25 mm sigmoid polyp by hot snare.',
          'not_done')]),
    'R8 D3 negtime-0 biopsies not obtained (whether)': (
        _r8(R8_EGD, 'A 1 cm ulcer was seen in the gastric antrum.', 'Biopsies to determine whether this represents '
            'malignancy were not obtained because of anticoagulation.'),
        [('43235', 'The endoscope was advanced to the second part of the duodenum.', 'done'),
         ('43239', 'A 1 cm ulcer was seen in the gastric antrum.', 'not_done')]),
    'R8 D3 declared:1 period-ended row, No checked': (
        _r8(R8_COLON, 'Biopsy of the sigmoid colon. | Yes \u2610 | No \u2612'),
        [('45378', R8_CECUM, 'done'), ('45380', 'Biopsy of the sigmoid colon.', 'no_ready')]),
    # D4: another procedure's sentence in a combined report (the correct code on it is held too: fail-closed)
    'R8 D4 F7N EGD biopsy line, colonoscopy denies': (
        R8_TOP + 'Procedures: EGD and colonoscopy\nEGD: The gastroscope was advanced to the second portion of the '
        'duodenum. Erythema was seen in the gastric antrum.\nBiopsies were taken with cold forceps.\n' + R8_COLON7N + '\n',
        [('43239', 'Biopsies were taken with cold forceps.', 'done'), ('45378', R8_COLON7N, 'done'),
         ('45380', 'Biopsies were taken with cold forceps.', 'not_done')]),
    'R8 D4 F1 EGD snare line, colonoscopy normal': (
        R8_TOP + 'Procedures: EGD and colonoscopy\nEGD: The gastroscope was advanced to the second portion of the '
        'duodenum. A 6 mm sessile polyp was seen in the gastric body.\nThe polyp was removed with a hot snare.\n'
        + R8_COLON1 + '\n',
        [('43251', 'The polyp was removed with a hot snare.', 'done'), ('45378', R8_COLON1, 'done'),
         ('45385', 'The polyp was removed with a hot snare.', 'not_done')]),
    # D5: a pathology addendum's specimen line
    'R8 D5 F4B pathology specimen line': (
        R8_COLON + R8_TODAY_BX + '\n\nPATHOLOGY ADDENDUM (specimens from the colonoscopy of 2026-09-02)\nSigmoid colon '
        'polyp, hot snare polypectomy: tubular adenoma.\n',
        [('45380', R8_TODAY_BX, 'done'), ('45385', 'Sigmoid colon polyp, hot snare polypectomy: tubular adenoma.',
                                         'not_done')]),
    # D6: a pathology addendum heading (dated before the service date)
    'R8 D6 F4C pathology addendum heading': (
        R8_COLON + R8_TODAY_BX + '\n\nPATHOLOGY ADDENDUM - 2026-09-02 hot snare polypectomy specimen, sigmoid colon\n'
        'Sigmoid colon, polypectomy: tubular adenoma.\n',
        [('45380', R8_TODAY_BX, 'done'),
         ('45385', 'PATHOLOGY ADDENDUM - 2026-09-02 hot snare polypectomy specimen, sigmoid colon', 'not_done')]),
    # D8: an indication line inside a titled report (the indication alone is held on c9f20a148 already)
    'R8 D8 C1 indication line in a titled report': (
        R8_DIAG + R8_INDICATION + '\nProcedure: Colonoscopy\n' + R8_CECUM + '\n' + R8_TODAY_BX + '\n',
        [('45380', R8_TODAY_BX, 'done'), ('45385', R8_INDICATION, 'not_done')]),
    'R8 D8 C1 indication line and the reach sentence cited': (
        R8_DIAG + R8_INDICATION + '\nProcedure: Colonoscopy\n' + R8_CECUM + '\n' + R8_TODAY_BX + '\n',
        [('45380', R8_TODAY_BX, 'done'), ('45385', (R8_INDICATION, R8_CECUM), 'not_done')]),
    # D9: an act at another time (history, "last", index or planned)
    'R8 D9 time-1 last colonoscopy line': (_r8_earlier(R8_LAST), [('45385', R8_LAST, 'not_done')]),
    'R8 D9 time-2 last colonoscopy line, base cited': (
        _r8_earlier(R8_LAST), [('45378', R8_CECUM_LM, 'done'), ('45385', R8_LAST, 'not_done')]),
    'R8 D9 index colonoscopy prose': (_r8_earlier(R8_INDEX), [('45385', R8_INDEX, 'not_done')]),
    'R8 D9 release-1 most recent colonoscopy': (
        _r8(R8_COLON, 'At her most recent colonoscopy the polyp was removed by cold snare.'),
        [('45378', R8_CECUM, 'done'),
         ('45385', 'At her most recent colonoscopy the polyp was removed by cold snare.', 'not_done')]),
    'R8 D9 release-1 last spring': (
        _r8(R8_COLON, 'A sigmoid polyp was removed by cold snare last spring.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'A sigmoid polyp was removed by cold snare last spring.', 'not_done')]),
    'R8 D9 release-1 to be removed tomorrow': (
        _r8(R8_COLON, R8_SEEN, 'The polyp is to be removed by hot snare tomorrow.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'The polyp is to be removed by hot snare tomorrow.', 'not_done')]),
    'R8 D9 release-1 ordered by the referrer': (
        _r8(R8_COLON, R8_SEEN, 'Cold snare removal of the polyp was ordered by the referring physician.'),
        [('45378', R8_CECUM, 'done'),
         ('45385', 'Cold snare removal of the polyp was ordered by the referring physician.', 'not_done')]),
    # D12: an E/M visit that is not an in-person visit of this date (h4-01's time-only, orders-free twin; the walk's date)
    'R8 D12 E/M control, h4-01 time-only twin': (R8_EM, [('99204', R8_TWIN, 'done')]),
    'R8 D12 E/M not seen in person, history, plain': (
        _r8_edit(R8_EM, (R8_CC, R8_CC + ' Patient not seen in person today.')), [('99204', R8_TWIN, 'no_ready')]),
    'R8 D12 E/M not seen in person, history, NBSP': (
        _r8_edit(R8_EM, (R8_CC, R8_CC + ' Patient not\u00a0seen\u00a0in\u00a0person today.')),
        [('99204', R8_TWIN, 'no_ready')]),
    'R8 D12 E/M not seen in person, exam, plain': (
        _r8_edit(R8_EM, ('Vital Signs and Exam\n', 'Vital Signs and Exam\nPatient not seen in person today.\n')),
        [('99204', R8_TWIN, 'no_ready')]),
    'R8 D12 E/M not seen in person, exam, NBSP': (
        _r8_edit(R8_EM, ('Vital Signs and Exam\n',
                         'Vital Signs and Exam\nPatient not\u00a0seen\u00a0in\u00a0person today.\n')),
        [('99204', R8_TWIN, 'no_ready')]),
    # D13: a named EGD whose extent a statement of its own contradicts (h4-03 with the EGD named; the walk's date)
    'R8 D13 named EGD control, h4-03 as written': (R8_NAMED_EGD, [('43244', R8_BANDS_PASSED, 'done')]),
    'R8 D13 named EGD, we stopped in the stomach': (R8_STOPPED, [('43244', R8_BANDS_PASSED, 'no_ready')]),
    'R8 D13 named EGD, stopped in the stomach, two passages': (
        R8_STOPPED, [('43244', (R8_BANDS_PASSED, R8_BANDS), 'no_ready')]),
    'R8 D13 named EGD control, two passages': (R8_NAMED_EGD, [('43244', (R8_BANDS_PASSED, R8_BANDS), 'done')]),
    # D15: a base code beside the service that includes it (an EGD inside an EUS)
    'R8 D15 EGD with EUS, base EGD coded': (
        _r8(B + 'Procedure note (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient\n'
                'Procedure: EGD with EUS', 'The echoendoscope was advanced to the second part of the duodenum.',
            'Endosonographic examination of the pancreas showed a 2 cm hypoechoic mass in the pancreatic head.',
            'EUS-guided fine-needle aspiration of the pancreatic head mass was performed.'),
        [('43242', 'EUS-guided fine-needle aspiration of the pancreatic head mass was performed.', 'done'),
         ('43235', 'The echoendoscope was advanced to the second part of the duodenum.', 'no_ready')]),
    # R3 7.5.1, the narrow evidence hold: every cited passage another service's, another time's or a denial
    'R8 D3 N9 considered but not performed': (
        _r8(R8_SNARE_HEAD, R8_SEEN, 'Snare removal was considered but not performed.'),
        [('45378', R8_CECUM, 'done'), ('45385', 'Snare removal was considered but not performed.', 'no_ready')]),
    'R8 E1 history sentence cited, snare also done today': (
        R8_PROC + 'Procedure: Colonoscopy\n' + R8_CECUM + '\n' + R8_SNARED + '\n' + R8_HISTORY + '\n',
        [('45385', R8_HISTORY, 'unsupported')]),
    'R8 E2 EGD biopsy sentence cited for a colon snare': (
        R8_COMBINED, [('45385', 'Cold forceps biopsies were obtained from the gastric antrum.', 'unsupported')]),
    'R8 E3 colon snare sentence cited for an EGD biopsy': (
        R8_COMBINED, [('43239', R8_SNARED, 'unsupported')]),
    # D10: an attached prior report's title
    'R8 D10 attached prior EGD report title': (
        R8_COLON + '\nAttached prior report:\nUpper endoscopy report (fictional)\nDate of service: 2025-03-01\n'
        'Procedure: EGD\nThe gastroscope was advanced to the second portion of the duodenum. The duodenum was normal.\n',
        [('45378', R8_CECUM, 'done'), ('43235', 'Upper endoscopy report (fictional)', 'not_done')]),
    # D7 (lead integration, cux-lead.json L1): a separate same-day note under a 'Label: <service>' heading; its biopsy
    # is the flexible sigmoidoscopy's, never the colonoscopy's (R8's H1, probes/R8-history-defects/r8_cases.py)
    'R8 D7 H1 separate same-day note': (
        _r8(R8_COLON.replace(R8_CECUM + '\n', ''), R8_CECUM, R8_CO_SNARE, '',
            'Separate note: Flexible sigmoidoscopy (fictional), 2026-10-14',
            'The flexible sigmoidoscope was advanced to 60 cm in the descending colon.', R8_FS_BIOPSY),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    # L3 (lead integration, cux-lead.json L3; P1 rule 2): an attributive act compound presupposes an earlier act and
    # states none today, so the own-passage release never stands on it; a biopsy stated today still does
    'R8 L3 biopsy-proven Barrett, no act today': (
        _r8(R8_EGD_DX, 'Surveillance of biopsy-proven Barrett esophagus was performed.'),
        [('43239', 'Surveillance of biopsy-proven Barrett esophagus was performed.', 'not_done')]),
    'R8 L3 biopsy-confirmed adenoma, no act today': (
        _r8(R8_EGD_DX, 'Follow-up of a biopsy-confirmed gastric adenoma was performed.'),
        [('43239', 'Follow-up of a biopsy-confirmed gastric adenoma was performed.', 'not_done')]),
    'R8 L3 control, biopsy-proven Barrett and a biopsy today': (
        _r8(R8_EGD_DX, 'Surveillance of biopsy-proven Barrett esophagus was performed.',
            'Cold forceps biopsies were taken from the distal esophagus.'),
        [('43239', 'Cold forceps biopsies were taken from the distal esophagus.', 'done')]),
}
# --- reader-bind round 2 (2026-11-04; tests/fixtures/gi4/declarations/cux-r2-bind.json): the refutation round's
# reproduced inputs against the reader rules L1 (the 'Label: <service>' part), P1 rule 1 (lesion labels), rule 2
# (attributive compounds) and rule 4 (a combined report's denials), each with its controls. Prefix 'R8 R2 ' (a register
# row: the round-4 counts leave it out; tests/test_cux_hold.RegisterOfferTests reads its offers from cux-r2-bind.json).
R2_HEAD = B + 'Date of service: 2026-11-03\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
R2_CECAL = 'A 5 mm polyp in the cecum was removed with a cold snare.'
R2_SIGMOID = 'A 5 mm polyp in the sigmoid colon was removed with a cold snare.'
R2_NOTE = ('Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
           'Procedure: Colonoscopy\n' + R8_CECUM + '\n\nSeparate note: Flexible sigmoidoscopy (fictional), 2026-10-14\n'
           'The flexible sigmoidoscope was advanced to 60 cm in the descending colon.\nThe rectum was normal.\n')
R2_COLON_FS = (R8_COLON + R8_CO_SNARE + '\n\n{heading}\nThe flexible sigmoidoscope was advanced to 60 cm in the descending '
               'colon.\n' + R8_FS_BIOPSY + '\n')
R2_LEFT = (R2_HEAD + 'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum. A 12 mm sessile polyp was seen in '
           'the sigmoid colon and was left in place because the patient takes clopidogrel.\n')
R2_LEFT_Q = 'A 12 mm sessile polyp was seen in the sigmoid colon'
R2_COMBINED = (R2_HEAD + 'EGD and colonoscopy report\nThe gastroscope was advanced to the second part of the duodenum. Cold '
               'forceps biopsies were taken from the gastric antrum. The colonoscope was advanced to the cecum. A 6 mm '
               'polyp in the transverse colon was removed with a cold snare.\n')
R2_ANTRUM = 'Cold forceps biopsies were taken from the gastric antrum.'
R2_LISTED = ('Findings:\nThe gastroscope was advanced to the second part of the duodenum. Biopsies were taken with cold '
             'forceps. A clip was placed at the biopsy site.\nThe colonoscope was advanced to the cecum. The colon was '
             'normal.\n')
R2_COL_EGD = R2_HEAD + 'Colonoscopy and EGD report\nCOLONOSCOPY\nThe colonoscope was advanced to the cecum.\n'
R2_UPPER = 'UPPER ENDOSCOPY\nThe gastroscope was advanced to the second part of the duodenum. '
R2_PASSING = 'Biopsies were then taken with the same cold forceps used to retrieve COL-1.'
R2_SPECIMEN = 'Biopsies were obtained with cold forceps (specimen 1).'
R2_REUSED = 'P1 was removed with a hot snare.'
R2_SNARED = (R2_HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum. A 7 mm polyp in the sigmoid colon was '
             'removed with a cold snare.\n')
R2_SNARED_Q = 'A 7 mm polyp in the sigmoid colon was removed with a cold snare.'
R2_LABELS = (R2_HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\nCOL-1 - ascending colon: a 2 mm polyp '
             'was removed with cold forceps.\nCOL-2 - sigmoid colon: an 8 mm polyp was removed with a cold snare.\n')
R2_LABELS_Q = 'an 8 mm polyp was removed with a cold snare.'
CASES.update({
    # L1 (R07): the separate note's part runs on over an act at a site its sigmoidoscope cannot reach (the cecum)
    'R8 R2 R07a cecal snare after a separate note': (
        _r8(B + R2_NOTE, '', R2_CECAL),
        [('45378', R8_CECUM, 'done'), ('45385', R2_CECAL, 'done'), ('45338', R2_CECAL, 'not_done')]),
    'R8 R2 R07b cecal snare after a separate note, 45338 only': (
        _r8(B + R2_NOTE, '', R2_CECAL), [('45378', R8_CECUM, 'done'), ('45338', R2_CECAL, 'not_done')]),
    'R8 R2 R07v4 cecal snare inside the separate note': (
        _r8(B + R2_NOTE, R2_CECAL),
        [('45378', R8_CECUM, 'done'), ('45385', R2_CECAL, 'done'), ('45338', R2_CECAL, 'not_done')]),
    'R8 R2 R07v3 control, sigmoid snare inside the separate note': (
        _r8(B + R2_NOTE, R2_SIGMOID),
        [('45378', R8_CECUM, 'done'), ('45385', R2_SIGMOID, 'not_done'), ('45338', R2_SIGMOID, 'done')]),
    # L1 (R10): a separate-note line the labelled-heading reader does not accept; its biopsy is not the colonoscopy's
    'R8 R2 R10a separate note on the service date': (
        R2_COLON_FS.format(heading='Separate note: Flexible sigmoidoscopy (fictional) on 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    'R8 R2 R10b separate same-day note': (
        R2_COLON_FS.format(heading='Separate same-day note: Flexible sigmoidoscopy (fictional), 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    'R8 R2 R10c separate note for rectal bleeding': (
        R2_COLON_FS.format(heading='Separate note: Flexible sigmoidoscopy for rectal bleeding (fictional), 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    'R8 R2 R10h7 addendum by another physician': (
        R2_COLON_FS.format(heading='Addendum - flexible sigmoidoscopy performed the same day by Dr. Vale'),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    # L1 (F01): a labelled line in a plan, or naming a later procedure, is no report of today's
    'R8 R2 F01A plan, second procedure': (
        R2_LEFT + 'Plan:\nSecond procedure: Colonoscopy with cold snare polypectomy\n',
        [('45385', R2_LEFT_Q, 'not_done')]),
    'R8 R2 F01B recommendations, follow-on procedure': (
        R2_LEFT + 'Recommendations:\nFollow-on procedure: colonoscopy with cold snare polypectomy\n',
        [('45385', R2_LEFT_Q, 'not_done')]),
    'R8 R2 F01C subsequent procedure line': (
        R2_LEFT + 'Subsequent procedure: colonoscopy with cold snare polypectomy\n', [('45385', R2_LEFT_Q, 'not_done')]),
    'R8 R2 F01D impression and recommendations, second procedure': (
        R2_LEFT + 'Impression and Recommendations:\nSecond procedure: Colonoscopy with cold snare polypectomy\n',
        [('45385', R2_LEFT_Q, 'not_done')]),
    'R8 R2 F01X cancelled separate note': (
        R2_HEAD + 'EGD report\nThe gastroscope was advanced to the second part of the duodenum. ' + R2_ANTRUM
        + '\nSeparate note: Colonoscopy\nThe colonoscopy was cancelled because of inadequate preparation.\n',
        [('45378', 'Separate note: Colonoscopy', 'not_done')]),
    # P1 rule 4 (F02): a combined report's site-less denial that carries the service date or a history word
    'R8 R2 F02 combined denial on the service date': (
        R2_COMBINED + 'No biopsies were taken on 2026-11-03.\n', [('43239', R2_ANTRUM, 'no_ready')]),
    'R8 R2 F02 combined denial, as previously documented': (
        R2_COMBINED + 'No biopsies were taken, as previously documented.\n', [('43239', R2_ANTRUM, 'no_ready')]),
    'R8 R2 F02 control, undated combined denial': (
        R2_COMBINED + 'No biopsies were taken.\n', [('43239', R2_ANTRUM, 'no_ready')]),
    # L1 (F03): numbered procedure lines listing today's procedures open no part
    'R8 R2 F03a numbered procedure lines': (
        R2_HEAD + 'Upper endoscopy and colonoscopy report\nProcedure 1: EGD\nProcedure 2: Colonoscopy\n' + R2_LISTED,
        [('43239', 'Biopsies were taken with cold forceps.', 'done'),
         ('45380', 'Biopsies were taken with cold forceps.', 'not_done')]),
    'R8 R2 F03b numbered procedure lines, dashes': (
        R2_HEAD + 'EGD and colonoscopy report\nProcedure 1 - EGD\nProcedure 2 - Colonoscopy\n' + R2_LISTED,
        [('43239', 'Biopsies were taken with cold forceps.', 'done'),
         ('45380', 'Biopsies were taken with cold forceps.', 'not_done')]),
    # P1 rule 1 (F04): a label or specimen named in an act's clause never moves the act to another service's lesion
    'R8 R2 F04a colon label named in an upper endoscopy clause': (
        R2_COL_EGD + 'COL-1 - sigmoid colon: an 8 mm polyp was removed with a cold snare.\n' + R2_UPPER
        + 'The antrum showed patchy erythema. ' + R2_PASSING + '\n',
        [('43239', R2_PASSING, 'done'), ('45380', R2_PASSING, 'not_done')]),
    'R8 R2 F04b specimen number restarted for the upper endoscopy': (
        R2_COL_EGD + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare and sent as specimen 1.\n' + R2_UPPER
        + 'The stomach showed patchy erythema. ' + R2_SPECIMEN + '\n',
        [('43239', R2_SPECIMEN, 'done'), ('45380', R2_SPECIMEN, 'not_done')]),
    'R8 R2 F04c label reused under the upper endoscopy': (
        R2_COL_EGD + 'P1 - sigmoid colon: a 4 mm polyp was removed with cold forceps.\n' + R2_UPPER
        + '\nStomach:\nP1: a 9 mm sessile polyp. ' + R2_REUSED + '\n',
        [('43251', R2_REUSED, 'MAY'), ('45385', R2_REUSED, 'not_done')]),
    # P1 rule 2 (F05): a field label or a negated predicate compound denies the act (a genuine same-lesion conflict)
    'R8 R2 F05a snare-resected field answered No': (
        R2_SNARED + 'Polyp 1 - sigmoid colon, 7 mm\nSnare-resected: No\nForceps-removed: Yes\n',
        [('45385', R2_SNARED_Q, 'no_ready')]),
    'R8 R2 F05b hot snare-resected field, not done': (
        R2_SNARED + 'Hot snare-resected: Not done\n', [('45385', R2_SNARED_Q, 'no_ready')]),
    'R8 R2 F05b2 cold snare-resected field answered No': (
        R2_SNARED + 'Cold snare-resected: No\n', [('45385', R2_SNARED_Q, 'no_ready')]),
    'R8 R2 F05c neither snare-resected nor retrieved': (
        R2_SNARED + 'The sigmoid polyp was neither snare-resected nor retrieved.\n', [('45385', R2_SNARED_Q, 'no_ready')]),
    'R8 R2 F05 control, an attributive compound': (
        R2_SNARED + 'The snare-resected sigmoid polyp was not retrieved.\n', [('45385', R2_SNARED_Q, 'done')]),
    # P1 rule 1 (F06): a label never binds a denial whose own clause names another site
    'R8 R2 F06a denial on a label, in another segment': (
        R2_LABELS + 'No snare was used on COL-1 in the sigmoid colon.\n', [('45385', R2_LABELS_Q, 'no_ready')]),
    'R8 R2 F06b denial in another segment, as for a label': (
        R2_LABELS + 'In the sigmoid colon no snare was used, as for COL-1.\n', [('45385', R2_LABELS_Q, 'no_ready')]),
    'R8 R2 F06 control, a denial on a label alone': (
        R2_LABELS + 'No snare was used on COL-1.\n', [('45385', R2_LABELS_Q, 'done')]),
})
# --- reader-em round 2 (2026-11-04; tests/fixtures/gi4/declarations/cux-r2-em.json, its integration amendment): rule 8,
# the explicit "no separate office E/M" statement, read only where the document settles it - a hedge or a same-day
# evaluation stated elsewhere keeps the E/M questions (F07, F08); F09's billing wording stays as designed; Mara's
# sentence alone and beside a future visit still negates the visit. Proposed by the reader-em owner with their truths;
# added by the lead at integration (the owner measured them on c47d71a3 and on its head before the merge).
R2_EM_BODY = (B + 'Upper Endoscopy Report\nDate of service: 2026-10-26\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n'
              'Sedation: propofol by a CRNA (fictional)\nProcedure: EGD\nThe gastroscope was advanced to the second part of '
              'the duodenum. Cold forceps biopsies were taken from the gastric antrum.\n')
R2_EM_BIOPSY = 'Cold forceps biopsies were taken from the gastric antrum.'
R2_EM_MARA = 'No separate office evaluation and management encounter or office-visit time is documented on this date.'
CASES.update({
    'R8 R2 EM F07 hedged absence, documented in the clinic note': (
        R2_EM_BODY + 'The office visit is not documented here; it is documented in the clinic note of today.\n',
        [('43239', R2_EM_BIOPSY, 'done'), ('99203', 'The office visit is not documented here', 'unsupported')]),
    'R8 R2 EM F07 negator of another noun': (
        R2_EM_BODY + "No medication changes at today's office visit were documented.\n",
        [('43239', R2_EM_BIOPSY, 'done'), ('99203', "No medication changes at today's office visit were documented", 'unsupported')]),
    'R8 R2 EM F08 J1 evaluation beside the absence statement': (
        R2_EM_BODY + 'She was also evaluated today for new-onset jaundice, a separate problem, with a history and '
        'examination.\n' + R2_EM_MARA + '\n',
        [('43239', R2_EM_BIOPSY, 'done'), ('99213', 'She was also evaluated today for new-onset jaundice', 'unsupported')]),
    'R8 R2 EM F08 J2 evaluation beside the absence statement': (
        R2_EM_BODY + 'Separately, she was seen and examined today for new-onset jaundice; labs and an MRCP were ordered.\n'
        + R2_EM_MARA + '\n',
        [('43239', R2_EM_BIOPSY, 'done'), ('99213', 'she was seen and examined today for new-onset jaundice', 'unsupported')]),
    'R8 R2 EM F09 billed separately, by design': (
        R2_EM_BODY + 'No office evaluation and management service was billed separately.\n',
        [('43239', R2_EM_BIOPSY, 'done'), ('99213', 'No office evaluation and management service was billed separately', 'no_ready')]),
    'R8 R2 EM rule 8 control, the absence statement alone': (
        R2_EM_BODY + R2_EM_MARA + '\n', [('43239', R2_EM_BIOPSY, 'done'), ('99213', R2_EM_MARA[:-1], 'not_done')]),
    'R8 R2 EM rule 8 control, a future clinic visit': (
        R2_EM_BODY + 'She will be seen in clinic in two weeks to review the pathology.\n' + R2_EM_MARA + '\n',
        [('43239', R2_EM_BIOPSY, 'done'), ('99213', R2_EM_MARA[:-1], 'not_done')]),
})
# The member's answer a row is read with (jobs._merged_facts), by row name; a row not named here is read with none.
R8_USER: dict = {name: {'service_date': '2026-10-26'} for name in (
    'R8 D12 E/M control, h4-01 time-only twin', 'R8 D12 E/M not seen in person, history, plain',
    'R8 D12 E/M not seen in person, history, NBSP', 'R8 D12 E/M not seen in person, exam, plain',
    'R8 D12 E/M not seen in person, exam, NBSP')}
R8_USER.update({name: {'service_date': '2026-10-06'} for name in (
    'R8 D13 named EGD control, h4-03 as written', 'R8 D13 named EGD, we stopped in the stomach',
    'R8 D13 named EGD, stopped in the stomach, two passages', 'R8 D13 named EGD control, two passages')})
# --- variant repair, round 2 (2026-11-04; tests/fixtures/gi4/declarations/cux-r2-variants.json): refutation round 2's
# L1/R05, L1/R06 and L1/R12 - a form a reader already declares, written in a variant spelling or layout - each with its
# controls. Prefix 'R8 R2 V ' (a register row: the round-4 counts leave it out; tests/test_cux_hold.RegisterOfferTests
# reads its offers from cux-r2-variants.json). R05: R8 D8's indication line inside a titled report without its final
# period. R06: P1 rule 2's attributive act compound (the lead's L3) written with a Unicode hyphen or dash. R12: R8 D12's
# "not seen in person" (cues.NOT_IN_PERSON) hyphenated, contracted or written with two spaces.
R2V_IND = 'Indication: Surveillance after a sigmoid polyp was removed with a hot snare'  # R8_INDICATION, no final period
R2V_IND_DASH = 'Indication: surveillance - sigmoid polyp removed with hot snare'
R2V_TODAY_SNARE = 'A 9 mm polyp in the sigmoid colon was removed with a hot snare.'
R2V_BIOPSY_TODAY = 'Cold forceps biopsies were taken from the distal esophagus.'
R2V_PREDICATE = 'A 7 mm polyp in the sigmoid colon was snare\u2013resected.'
R2V_EXAM = 'Vital Signs and Exam\n'


def _r2v_indication(line, *after):
    """R8 D8's titled colonoscopy report with ``line`` as its indication line, and ``after`` at its end."""
    return _r8(R8_DIAG + line + '\nProcedure: Colonoscopy\n' + R8_CECUM + '\n' + R8_TODAY_BX + '\n', *after)


def _r2v_barrett(dash):
    """The lead's L3 sentence with ``dash`` joining its compound."""
    return f'Surveillance of biopsy{dash}proven Barrett esophagus was performed.'


def _r2v_exam(line):
    """R8 D12's h4-01 time-only twin with ``line`` as the first line under its examination heading."""
    return _r8_edit(R8_EM, (R2V_EXAM, R2V_EXAM + line + '\n'))


CASES.update({
    # R05 (R8 D8): the heading line of an indication section is never today's statement, with or without its final
    # punctuation; the lines after it read as before (today's report inside a titled one, the indication outside one)
    'R8 R2 V R05a indication line without its period, the reach sentence cited': (
        _r2v_indication(R2V_IND), [('45380', R8_TODAY_BX, 'done'), ('45385', (R2V_IND, R8_CECUM), 'not_done')]),
    'R8 R2 V R05b dash-form indication line cited alone': (
        _r2v_indication(R2V_IND_DASH), [('45380', R8_TODAY_BX, 'done'), ('45385', R2V_IND_DASH, 'not_done')]),
    'R8 R2 V R05c indication line ending in a semicolon, the reach sentence cited': (
        _r2v_indication(R2V_IND + ';'),
        [('45380', R8_TODAY_BX, 'done'), ('45385', (R2V_IND + ';', R8_CECUM), 'not_done')]),
    'R8 R2 V R05 control, the dash-form line with its period': (
        _r2v_indication(R2V_IND_DASH + '.'),
        [('45380', R8_TODAY_BX, 'done'), ('45385', R2V_IND_DASH + '.', 'not_done')]),
    'R8 R2 V R05 control, a biopsy today under an unterminated indication': (
        _r2v_indication('Indication: surveillance'), [('45380', R8_TODAY_BX, 'done')]),
    'R8 R2 V R05 control, a snare today under the unterminated line': (
        _r2v_indication(R2V_IND, R2V_TODAY_SNARE),
        [('45380', R8_TODAY_BX, 'done'), ('45385', R2V_TODAY_SNARE, 'done')]),
    'R8 R2 V R05 control, the unterminated line in an untitled note': (
        _r8(B + 'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n' + R2V_IND
            + '\nProcedure: Colonoscopy\n' + R8_CECUM + '\n' + R8_TODAY_BX),
        [('45380', R8_TODAY_BX, 'done'), ('45385', (R2V_IND, R8_CECUM), 'not_done')]),
    # R06 (P1 rule 2, the lead's L3): the compound's hyphen in a Unicode spelling, read where the ASCII hyphen is
    'R8 R2 V R06a en dash compound, no act today': (
        _r8(R8_EGD_DX, _r2v_barrett('\u2013')), [('43239', _r2v_barrett('\u2013'), 'not_done')]),
    'R8 R2 V R06 non-breaking hyphen compound, no act today': (
        _r8(R8_EGD_DX, _r2v_barrett('\u2011')), [('43239', _r2v_barrett('\u2011'), 'not_done')]),
    'R8 R2 V R06 em dash compound, no act today': (
        _r8(R8_EGD_DX, _r2v_barrett('\u2014')), [('43239', _r2v_barrett('\u2014'), 'not_done')]),
    'R8 R2 V R06 en dash compound, biopsy-confirmed adenoma': (
        _r8(R8_EGD_DX, 'Follow-up of a biopsy\u2013confirmed gastric adenoma was performed.'),
        [('43239', 'Follow-up of a biopsy\u2013confirmed gastric adenoma was performed.', 'not_done')]),
    'R8 R2 V R06 en dash field label answered No': (
        R2_SNARED + 'Polyp 1 - sigmoid colon, 7 mm\nSnare\u2013resected: No\nForceps\u2013removed: Yes\n',
        [('45385', R2_SNARED_Q, 'no_ready')]),
    'R8 R2 V R06 control, an en dash attributive compound': (
        R2_SNARED + 'The snare\u2013resected sigmoid polyp was not retrieved.\n', [('45385', R2_SNARED_Q, 'done')]),
    'R8 R2 V R06 control, an en dash compound and a biopsy today': (
        _r8(R8_EGD_DX, _r2v_barrett('\u2013'), R2V_BIOPSY_TODAY), [('43239', R2V_BIOPSY_TODAY, 'done')]),
    'R8 R2 V R06 control, an en dash predicate compound': (
        _r8(R8_COLON, R2V_PREDICATE), [('45378', R8_CECUM, 'done'), ('45385', R2V_PREDICATE, 'done')]),
    # R12 (R8 D12, cues.NOT_IN_PERSON): the declared phrase hyphenated, contracted, or written with two spaces
    'R8 R2 V R12a not seen in-person, exam': (
        _r2v_exam('Patient not seen in-person today.'), [('99204', R8_TWIN, 'no_ready')]),
    'R8 R2 V R12a not seen in-person, history': (
        _r8_edit(R8_EM, (R8_CC, R8_CC + ' Patient not seen in-person today.')), [('99204', R8_TWIN, 'no_ready')]),
    "R8 R2 V R12b wasn't seen in person, exam": (
        _r2v_exam("Patient wasn't seen in person today."), [('99204', R8_TWIN, 'no_ready')]),
    'R8 R2 V R12c the contraction with a curly apostrophe, exam': (
        _r2v_exam('Patient wasn\u2019t seen in person today.'), [('99204', R8_TWIN, 'no_ready')]),
    "R8 R2 V R12d isn't seen in person, exam": (
        _r2v_exam("Patient isn't seen in person today."), [('99204', R8_TWIN, 'no_ready')]),
    "R8 R2 V R12e the patient wasn't seen, exam": (
        _r2v_exam("The patient wasn't seen."), [('99204', R8_TWIN, 'no_ready')]),
    'R8 R2 V R12f two spaces in the phrase, exam': (
        _r2v_exam('Patient not  seen in person today.'), [('99204', R8_TWIN, 'no_ready')]),
    'R8 R2 V R12g non-breaking hyphen in in-person, exam': (
        _r2v_exam('Patient not seen in\u2011person today.'), [('99204', R8_TWIN, 'no_ready')]),
    'R8 R2 V R12 control, seen in-person today': (
        _r2v_exam('Patient seen in-person today.'), [('99204', R8_TWIN, 'done')]),
})
R8_USER.update({name: {'service_date': '2026-10-26'} for name in CASES if name.startswith('R8 R2 V R12')})
# Measured and recorded, never repaired here (new wording: ACCURACY-RESIDUALS.md, "Core repair, refutation round 2"):
# each reads READY on e25286af0 and on this package's head. Their truths are honest, so they stay out of CASES (a
# register row carries no violation: tests/test_gi4_battery.AssessBatteryTests.test_no_new_violation);
# tests/test_cux_r2_variants.py reads them with run_row, and the declaration records their readings.
R2V_RESIDUALS = {
    'R8 R2 V residual R06, the space form biopsy proven': (
        _r8(R8_EGD_DX, _r2v_barrett(' ')), [('43239', _r2v_barrett(' '), 'not_done')]),
    'R8 R2 V residual R06, the noun compound polypectomy scar': (
        _r8(R8_COLON, 'The polypectomy scar in the sigmoid colon was healed.'),
        [('45385', 'The polypectomy scar in the sigmoid colon was healed.', 'not_done')]),
    'R8 R2 V residual R12, not evaluated in person': (
        _r2v_exam('Patient not evaluated in person today.'), [('99204', R8_TWIN, 'no_ready')]),
}
R2V_RESIDUAL_USER = {'R8 R2 V residual R12, not evaluated in person': {'service_date': '2026-10-26'}}
# --- reader repair, round 3 (2026-11-04; tests/fixtures/gi4/declarations/cux-r3-reader.json): refutation round 3's lens
# A findings against the round-2 reader repairs - a same-day note under a numbered, 'Subsequent' or 'Follow-on' heading
# (A1), a labelled lesion's denial at another site of its own segment (A2), a label or specimen in a combined report's
# narrative after another examination is told (A3), a cecal polypectomy whose site is in the sentence before it after a
# separate sigmoidoscopy note (A4), a postmodified evaluation beside the E/M absence statement (A5), a header line
# naming another, separately reported service (A6) and a label restated without its site (A7) - each with its controls.
# Prefix 'R8 R3 ' (a register row: the round-4 counts leave it out; tests/test_cux_hold.RegisterOfferTests reads its
# offers from cux-r3-reader.json).
R3_FORCEPS_Q = 'a 2 mm polyp was removed with cold forceps.'
R3_COMBINED = R2_HEAD + 'EGD and colonoscopy report\n'
R3_COLON_LESION = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare and sent as specimen 1.'
R3_GASTRO = 'The gastroscope was advanced to the second part of the duodenum.'
R3_IT = 'It was removed with a cold snare.'
R3_THE_POLYP = 'The polyp was removed with a cold snare.'
R3_ANTRUM = 'Cold forceps biopsies were taken from the gastric antrum.'
R3_XREF = 'Additional procedure: EGD performed today (separate report)'
R3_EGD_TODAY = 'Second procedure: EGD performed today'
R3_HOT = 'A 6 mm polyp was removed with a hot snare.'
R3_SIGMOID_POLYP = 'A 4 mm sessile polyp was found in the sigmoid colon.'
R3_SITELESS_BX = 'Biopsies were taken with cold forceps.'
R3_MARA_LIKE = (R2_HEAD + 'Upper endoscopy and colonoscopy report\nUPPER ENDOSCOPY\n' + R3_GASTRO + ' ' + R3_ANTRUM
                + '\nCOLONOSCOPY\nThe colonoscope was advanced to the cecum.\nCOL-1 - ascending colon: a 2 mm polyp was '
                'removed with cold forceps. No snare resection was performed on COL-1.\nCOL-2 - sigmoid colon: an 8 mm '
                'polyp was removed with a cold snare. No biopsy forceps were used on COL-2.\nSPECIMENS\n{rows}')
R3_ROWS = 'COL-1: ascending colon\n2 mm polyp; cold forceps removal\nCOL-2: sigmoid colon\n8 mm polyp; cold-snare removal\n'
R3_MARA_Q = [('43239', R3_ANTRUM, 'done'), ('45380', R3_FORCEPS_Q, 'done'), ('45385', R2_LABELS_Q, 'done')]
R3_EM_EVAL = 'An evaluation for new-onset jaundice was performed today.'


def _r3_header(line, *body):
    """R8's titled colonoscopy report with ``line`` under its procedure field, then ``body``."""
    return _r8(R8_COLON.replace('Procedure: Colonoscopy\n', 'Procedure: Colonoscopy\n' + line + '\n'), *body)


def _r3_em(*lines):
    """Reader-em round 2's upper endoscopy body with ``lines`` after it."""
    return _r8(R2_EM_BODY, *lines)


CASES.update({
    # A1 (L1c): a same-day note under a numbered, a 'Subsequent procedure:' or a 'Follow-on procedure:' heading is the
    # note's (R8 D7, as 'Separate note:' reads); a numbered line in a list or over shared findings opens no colonoscopy
    'R8 R3 A1a numbered procedure heading over a same-day note': (
        R2_COLON_FS.format(heading='Procedure 2: Flexible sigmoidoscopy (fictional), 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    'R8 R3 A1b subsequent procedure heading over a same-day note': (
        R2_COLON_FS.format(heading='Subsequent procedure: Flexible sigmoidoscopy (fictional), 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    'R8 R3 A1c follow-on procedure heading over a same-day note': (
        R2_COLON_FS.format(heading='Follow-on procedure: Flexible sigmoidoscopy (fictional), 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    "R8 R3 A1d numbered procedure heading, the note's own biopsy code": (
        R2_COLON_FS.format(heading='Procedure 2: Flexible sigmoidoscopy (fictional), 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45331', R8_FS_BIOPSY, 'done')]),
    "R8 R3 A1e subsequent procedure heading, the note's own biopsy code": (
        R2_COLON_FS.format(heading='Subsequent procedure: Flexible sigmoidoscopy (fictional), 2026-10-14'),
        [('45385', R8_CO_SNARE, 'done'), ('45331', R8_FS_BIOPSY, 'done')]),
    'R8 R3 A1 control, one numbered procedure line over shared findings': (
        R2_HEAD + 'Upper endoscopy and colonoscopy report\nProcedure 2: Colonoscopy\n' + R2_LISTED,
        [('43239', 'Biopsies were taken with cold forceps.', 'done'),
         ('45380', 'Biopsies were taken with cold forceps.', 'not_done')]),
    'R8 R3 A1 control, a numbered procedure line naming an EGD performed today': (
        _r3_header('Procedure 2: EGD performed today', R3_SIGMOID_POLYP, R3_IT), [('45385', R3_IT, 'done')]),
    # A2 (R1c): a denial naming a label and a site of the lesion's own segment that is not its recorded site
    'R8 R3 A2a snare denial on a label, a landmark of its own segment': (
        R2_LABELS + 'No snare was used on COL-2, just above the rectosigmoid junction.\n',
        [('45385', R2_LABELS_Q, 'no_ready'), ('45380', R3_FORCEPS_Q, 'done')]),
    'R8 R3 A2b snare denial on a label, the left colon': (
        R2_LABELS + 'No snare was used on COL-2 in the left colon.\n', [('45385', R2_LABELS_Q, 'no_ready')]),
    'R8 R3 A2c forceps denial on a label, near the hepatic flexure': (
        R2_LABELS + 'No forceps were used on COL-1 near the hepatic flexure.\n',
        [('45380', R3_FORCEPS_Q, 'no_ready'), ('45385', R2_LABELS_Q, 'done')]),
    'R8 R3 A2 control, a denial on a label at its own site': (
        R2_LABELS + 'No snare was used on COL-1 in the ascending colon.\n', [('45385', R2_LABELS_Q, 'done')]),
    # A3 (R1a): a label or specimen in a combined report's narrative, after another examination is told
    'R8 R3 A3a specimen number restarted in a combined narrative': (
        R3_COMBINED + 'The colonoscope was advanced to the cecum. ' + R3_COLON_LESION + '\n' + R3_GASTRO
        + ' The stomach showed patchy erythema. ' + R2_SPECIMEN + '\n',
        [('43239', R2_SPECIMEN, 'done'), ('45380', R2_SPECIMEN, 'not_done')]),
    'R8 R3 A3b specimen number restarted in a combined narrative, 43239 only': (
        R3_COMBINED + 'The colonoscope was advanced to the cecum. ' + R3_COLON_LESION + '\n' + R3_GASTRO
        + ' The stomach showed patchy erythema. ' + R2_SPECIMEN + '\n', [('43239', R2_SPECIMEN, 'done')]),
    'R8 R3 A3c colon label named in passing in a combined narrative': (
        R2_HEAD + 'Colonoscopy and EGD report\nThe colonoscope was advanced to the cecum.\nCOL-1 - sigmoid colon: an 8 mm '
        'polyp was removed with a cold snare.\n' + R3_GASTRO + ' The antrum showed patchy erythema. ' + R2_PASSING + '\n',
        [('43239', R2_PASSING, 'done'), ('45380', R2_PASSING, 'not_done')]),
    'R8 R3 A3 control, a labelled clip and denial in a combined narrative': (
        R3_COMBINED + R3_GASTRO + ' ' + R3_ANTRUM + '\nThe colonoscope was advanced to the cecum.\nCOL-1 - sigmoid colon: '
        'an 8 mm polyp was removed with a cold snare.\nOne clip was placed at the COL-1 resection site. No biopsy forceps '
        'were used on COL-1.\n',
        [('43239', R3_ANTRUM, 'done'), ('45385', R2_LABELS_Q, 'done')]),
    'R8 R3 A3 control, the colonoscope told again before the labelled act': (
        R2_HEAD + 'Colonoscopy and EGD report\nThe colonoscope was advanced to the cecum.\nCOL-1 - sigmoid colon: an 8 mm '
        'polyp was seen.\n' + R3_GASTRO + ' The antrum was normal.\nThe colonoscope was then reinserted.\nCOL-1 was removed '
        'with a cold snare.\n', [('45385', 'COL-1 was removed with a cold snare.', 'done')]),
    # A4 (L1e): the cecal polyp's snare told in the sentence after its site, after a separate sigmoidoscopy note
    'R8 R3 A4a cecal polyp, its snare in the next sentence': (
        _r8(B + R2_NOTE, '', 'A 5 mm polyp was seen in the cecum. ' + R3_IT),
        [('45378', R8_CECUM, 'done'), ('45385', R3_IT, 'done'), ('45338', R3_IT, 'not_done')]),
    'R8 R3 A4b cecal polyp, its snare in the next sentence, 45338 only': (
        _r8(B + R2_NOTE, '', 'A 5 mm polyp was seen in the cecum. ' + R3_IT),
        [('45378', R8_CECUM, 'done'), ('45338', R3_IT, 'not_done')]),
    'R8 R3 A4c cecal polyp found, the polyp removed on the next line': (
        _r8(B + R2_NOTE, '', 'A 5 mm cecal polyp was found.', R3_THE_POLYP),
        [('45378', R8_CECUM, 'done'), ('45385', R3_THE_POLYP, 'done'), ('45338', R3_THE_POLYP, 'not_done')]),
    'R8 R3 A4 control, a sigmoid polyp and its snare in the next sentence': (
        _r8(B + R2_NOTE, 'A 5 mm polyp was seen in the sigmoid colon. ' + R3_IT),
        [('45378', R8_CECUM, 'done'), ('45385', R3_IT, 'not_done'), ('45338', R3_IT, 'done')]),
    # A5 (R8b-2): an evaluation stated with a postmodifier beside the E/M absence statement
    'R8 R3 A5a evaluation for a problem beside the absence statement': (
        _r3_em(R3_EM_EVAL, R2_EM_MARA), [('43239', R2_EM_BIOPSY, 'done'), ('99213', R3_EM_EVAL[:-1], 'unsupported')]),
    'R8 R3 A5b history and examination for a problem': (
        _r3_em('A history and examination for new-onset jaundice were performed today.', R2_EM_MARA),
        [('43239', R2_EM_BIOPSY, 'done'),
         ('99213', 'A history and examination for new-onset jaundice were performed today', 'unsupported')]),
    'R8 R3 A5c consultation regarding a problem': (
        _r3_em('A consultation regarding her new-onset jaundice was also provided today.', R2_EM_MARA),
        [('43239', R2_EM_BIOPSY, 'done'),
         ('99213', 'A consultation regarding her new-onset jaundice was also provided today', 'unsupported')]),
    'R8 R3 A5d assessment of a problem, an appositive': (
        _r3_em('An assessment of her new-onset jaundice, a separate problem, was documented today.', R2_EM_MARA),
        [('43239', R2_EM_BIOPSY, 'done'),
         ('99213', 'An assessment of her new-onset jaundice, a separate problem, was documented today', 'unsupported')]),
    'R8 R3 A5e focused history and physical for a problem': (
        _r3_em('A focused history and physical for new-onset jaundice was obtained today.', R2_EM_MARA),
        [('43239', R2_EM_BIOPSY, 'done'),
         ('99213', 'A focused history and physical for new-onset jaundice was obtained today', 'unsupported')]),
    'R8 R3 A5f a GI consultation for a problem': (
        _r3_em('A GI consultation for new-onset jaundice was performed today.', R2_EM_MARA),
        [('43239', R2_EM_BIOPSY, 'done'),
         ('99213', 'A GI consultation for new-onset jaundice was performed today', 'unsupported')]),
    'R8 R3 A5g the absence statement before the evaluation': (
        _r3_em(R2_EM_MARA, R3_EM_EVAL), [('43239', R2_EM_BIOPSY, 'done'), ('99213', R3_EM_EVAL[:-1], 'unsupported')]),
    'R8 R3 A5 control, an evaluation word inside a biopsy statement': (
        _r3_em('Cold forceps biopsies for evaluation of eosinophilic esophagitis were obtained from the distal esophagus.',
               R2_EM_MARA), [('43239', R2_EM_BIOPSY, 'done'), ('99213', R2_EM_MARA[:-1], 'not_done')]),
    'R8 R3 A5 control, an evaluation for a problem planned in clinic': (
        _r3_em('An evaluation for new-onset jaundice will be performed in clinic next week.', R2_EM_MARA),
        [('43239', R2_EM_BIOPSY, 'done'), ('99213', R2_EM_MARA[:-1], 'not_done')]),
    'R8 R3 A5 control, an assessment of the mucosa beside the absence statement': (
        _r3_em('An assessment of the gastric mucosa was documented today.', R2_EM_MARA),
        [('43239', R2_EM_BIOPSY, 'done'), ('99213', R2_EM_MARA[:-1], 'not_done')]),
    # A6 (L1d, L1f): a header line naming another, separately reported service, then the running report's own text
    'R8 R3 A6a header cross-reference to a same-day EGD, a lesion and its snare': (
        _r3_header(R3_XREF, R3_SIGMOID_POLYP, R3_IT), [('45385', R3_IT, 'done')]),
    'R8 R3 A6b header cross-reference to a same-day EGD, a site-less biopsy': (
        _r3_header(R3_XREF, R3_SITELESS_BX), [('45380', R3_SITELESS_BX, 'done')]),
    'R8 R3 A6c header line naming a same-day EGD, a site-less snare': (
        _r3_header('Separate procedure: EGD, performed the same day', 'A 4 mm polyp was removed with a cold snare.'),
        [('45385', 'A 4 mm polyp was removed with a cold snare.', 'done')]),
    "R8 R3 A6d an upper endoscopy report's cross-reference to a same-day colonoscopy": (
        _r8(R8_EGD_DX.replace('Procedure: EGD\n', 'Procedure: EGD\nSecond procedure: Colonoscopy performed the same day, '
                                                  'see separate note\n'), R3_HOT), [('43251', R3_HOT, 'done')]),
    'R8 R3 A6e a labelled line naming an EGD performed today, the colonoscopy narrative after it': (
        _r3_header(R3_EGD_TODAY, R3_SIGMOID_POLYP, R3_IT), [('45385', R3_IT, 'done')]),
    'R8 R3 A6f a labelled line naming an EGD performed today, a site-less biopsy': (
        _r3_header(R3_EGD_TODAY, R3_SITELESS_BX), [('45380', R3_SITELESS_BX, 'done')]),
    'R8 R3 A6 control, a refused note label whose text denies the running instrument': (
        R8_COLON + R8_CO_SNARE + '\n\nSeparate note: Flexible sigmoidoscopy (fictional) on 2026-10-14\nThe colonoscope '
        'was not reinserted.\nThe flexible sigmoidoscope was advanced to 60 cm in the descending colon.\n' + R8_FS_BIOPSY
        + '\n', [('45385', R8_CO_SNARE, 'done'), ('45380', R8_FS_BIOPSY, 'not_done')]),
    # A7 (R1b): a label restated without its site (a specimen table's row), by its size
    'R8 R3 A7a specimen row restating COL-2 by its size': (
        R3_MARA_LIKE.format(rows=R3_ROWS.replace('COL-2: sigmoid colon\n8 mm polyp; ', 'COL-2: 8 mm polyp\n')),
        R3_MARA_Q),
    'R8 R3 A7b specimen row restating COL-1 by its size': (
        R3_MARA_LIKE.format(rows=R3_ROWS.replace('COL-1: ascending colon\n2 mm polyp; ', 'COL-1: 2 mm polyp\n')),
        R3_MARA_Q),
    'R8 R3 A7 control, the specimen rows with their sites': (R3_MARA_LIKE.format(rows=R3_ROWS), R3_MARA_Q),
    'R8 R3 A7 control, a label restated by its size under another examination': (
        R2_HEAD + 'Colonoscopy and EGD report\nCOLONOSCOPY\nThe colonoscope was advanced to the cecum.\nP1 - sigmoid colon: '
        'a 4 mm polyp was removed with cold forceps.\nUPPER ENDOSCOPY\n' + R3_GASTRO + ' \nStomach:\nP1: a 4 mm sessile '
        'polyp. P1 was removed with a hot snare.\n',
        [('43251', 'P1 was removed with a hot snare.', 'MAY'), ('45385', 'P1 was removed with a hot snare.', 'not_done')]),
    'R8 R3 A7 control, a label restated by its size under a stomach heading': (
        R2_HEAD + 'Colonoscopy and EGD report\nCOLONOSCOPY\nThe colonoscope was advanced to the cecum.\nP1 - sigmoid colon: '
        'a 4 mm polyp was removed with cold forceps.\nUPPER ENDOSCOPY\nStomach:\nP1: a 4 mm sessile polyp. P1 was removed '
        'with a hot snare.\n',
        [('43251', 'P1 was removed with a hot snare.', 'MAY'), ('45385', 'P1 was removed with a hot snare.', 'not_done')]),
})
# Added after code (cux-r3-reader.json, its after-code amendment): A4's class without a back-reference (a polypectomy
# naming no site, lesion or service after the cecal polyp), A6's running instrument in a clause of its own, and two
# controls of L1c-r3's date condition (an undated restored label reads as round 2 read it), each with its controls;
# their 'from' cells measured on e020145e1's code with the rows added.
R3_POLYPECTOMY = 'A cold snare polypectomy was performed.'
CASES.update({
    'R8 R3 A4d cecal polyp, a site-less polypectomy in the next sentence': (
        _r8(B + R2_NOTE, '', 'A 5 mm polyp was seen in the cecum. ' + R3_POLYPECTOMY),
        [('45378', R8_CECUM, 'done'), ('45385', R3_POLYPECTOMY, 'done'), ('45338', R3_POLYPECTOMY, 'not_done')]),
    'R8 R3 A4e cecal polyp, a site-less polypectomy on the next line, 45338 only': (
        _r8(B + R2_NOTE, '', 'A 5 mm polyp was seen in the cecum.', R3_POLYPECTOMY),
        [('45378', R8_CECUM, 'done'), ('45338', R3_POLYPECTOMY, 'not_done')]),
    "R8 R3 A4 control, the note's instrument told again before a site-less polypectomy": (
        _r8(B + R2_NOTE, 'A 5 mm polyp was seen in the cecum.', 'The flexible sigmoidoscope was then withdrawn to the '
            'rectum.', R3_POLYPECTOMY),
        [('45378', R8_CECUM, 'done'), ('45385', R3_POLYPECTOMY, 'MAY'), ('45338', R3_POLYPECTOMY, 'MAY')]),
    'R8 R3 A4 control, a cecal polyp of another time before a site-less polypectomy': (
        _r8(B + R2_NOTE, 'A 5 mm polyp in the cecum was removed at a prior colonoscopy in 2023.', R3_POLYPECTOMY),
        [('45378', R8_CECUM, 'done'), ('45385', R3_POLYPECTOMY, 'not_done'), ('45338', R3_POLYPECTOMY, 'done')]),
    'R8 R3 A6g header cross-reference, the colonoscope advanced without difficulty': (
        _r8(R8_COLON.replace('Procedure: Colonoscopy\n', 'Procedure: Colonoscopy\n' + R3_XREF + '\n').replace(
            R8_CECUM, 'The colonoscope was advanced without difficulty to the cecum.'), R3_SIGMOID_POLYP, R3_IT),
        [('45385', R3_IT, 'done')]),
    'R8 R3 A1 control, an undated subsequent procedure line in an upper endoscopy report': (
        _r8(R8_EGD_DX, 'Subsequent procedure: colonoscopy with cold snare polypectomy', R3_SITELESS_BX),
        [('43239', R3_SITELESS_BX, 'MAY'), ('45380', R3_SITELESS_BX, 'MAY')]),
    "R8 R3 A1 control, a numbered procedure line in a combined report's head over shared findings": (
        R2_HEAD + 'Upper endoscopy and colonoscopy report\nProcedure 2: Colonoscopy\nFindings:\n' + R3_SITELESS_BX
        + ' A clip was placed at the biopsy site.\nThe colonoscope was advanced to the cecum. The colon was normal.\n',
        [('43239', R3_SITELESS_BX, 'MAY'), ('45380', R3_SITELESS_BX, 'MAY')]),
    "R8 R3 A1 control, a dated numbered procedure line in a combined report's head over shared findings": (
        R2_HEAD + 'Upper endoscopy and colonoscopy report\nProcedure 2: Colonoscopy (fictional), 2026-11-03\nFindings:\n'
        + R3_SITELESS_BX + ' A clip was placed at the biopsy site.\nThe colonoscope was advanced to the cecum. The colon '
        'was normal.\n', [('43239', R3_SITELESS_BX, 'MAY'), ('45380', R3_SITELESS_BX, 'MAY')]),
    "R8 R3 A6h header cross-reference, a denial in another clause of the instrument's sentence": (
        _r8(R8_COLON.replace('Procedure: Colonoscopy\n', 'Procedure: Colonoscopy\n' + R3_XREF + '\n').replace(
            R8_CECUM, 'The colonoscope was advanced to the cecum and no polyps were seen in the rectum.'),
            R3_SIGMOID_POLYP, R3_IT), [('45385', R3_IT, 'done')]),
})
# Measured and recorded, never repaired here (cux-r3-reader.json residuals_measured): A8, R8 D8's indication line with
# its heading written with a dash ('Indication - ...'). Routing's layout (sections.layout, H2-frozen: gi-context@4) reads
# no indication section there, and V05 reads the layout's indication sections only. Its honest truth makes it a
# violation, so it stays out of CASES (a register row carries none); tests/test_cux_r3_reader.py reads it with run_row.
R3_RESIDUALS = {
    'R8 R3 residual A8, an indication heading written with a dash': (
        _r2v_indication('Indication - surveillance after a sigmoid polyp was removed with a hot snare'),
        [('45380', R8_TODAY_BX, 'done'),
         ('45385', ('Indication - surveillance after a sigmoid polyp was removed with a hot snare', R8_CECUM),
          'not_done')]),
}
REVIEW_NOTE = ('Provisional author truths; no qualified GI coder has reviewed them. "X|MAY" marks a truth the second '
               'review disputes: J8 (its identity sentence reads like h4-06\'s own), E3 (the judge: arguable), and the '
               'anastomosis row (45378-53, 45330 or 45300: coders differ).')


def modules():
    from studio import jobs
    from studio.reference.store import InMemoryReferenceLookup
    from studio.types import EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode
    return SimpleNamespace(jobs=jobs, Lookup=InMemoryReferenceLookup, EvidenceSpan=EvidenceSpan,
                           NormalizedResponse=NormalizedResponse, PageSpan=PageSpan, ProviderCode=ProviderCode)


def response(m, text, codes):
    """The synthetic answer: one selected code per entry, its quote (or each quote of a tuple: several passages of one
    code, as a provider cites them) located exactly in the text."""
    found = []
    for i, (code, quote, _) in enumerate(codes):
        spans = []
        for one in (quote if isinstance(quote, tuple) else (quote,)):
            start = text.index(one)
            spans.append(m.EvidenceSpan(0, start, start + len(one), one, True, 1))
        found.append(m.ProviderCode(role='selected', system='cpt', code=code, display='SYNTHETIC', index=i,
                                    evidence=tuple(spans)))
    return m.NormalizedResponse(provider='corti', adapter_version='corti-coding-v2@cptstudio-1', codes=tuple(found))


def judged_truth(truth: str) -> str:
    return 'MAY' if truth.endswith('|MAY') else truth


def violations(truth: str, p: dict) -> list:
    """The properties a code's outcome breaks under its truth."""
    truth = judged_truth(truth)
    ready = p['bucket'] == 'selected' and p['status'] == 'ready'
    excluded = p['bucket'] == 'excluded' or p['status'] == 'excluded'
    signalled = bool(p['modifiers']) or bool(p['checks'])
    out = []
    if truth in ('not_done', 'unsupported', 'no_ready') and ready:
        out.append('READY where the truth says not done today')
    if truth == 'done_incomplete' and ready and not signalled:
        out.append('READY without an incompleteness signal')
    if truth in ('done', 'done_incomplete', 'unsupported') and excluded:
        out.append('EXCLUDED where the truth says done')
    return out


def run_row(m, name, text, codes, user_values=None) -> dict:
    user_values = user_values or {}
    read = m.jobs._analyze_child(text, user_values, 1000)
    document_facts, day, routing = read
    facts = m.jobs._merged_facts(document_facts, user_values)
    context = m.jobs.context_facts(SimpleNamespace(facts=facts))
    _, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context, response(m, text, codes),
                                     m.Lookup([], {}), 'succeeded', 'ok', ())
    m.jobs.release_routing_caches()
    truths = {code: truth for code, _, truth in codes}
    proposals = {}
    for p in result.proposals:
        if p.bucket == 'alternative' or p.code not in truths:
            continue
        view = {'bucket': p.bucket, 'status': p.status, 'clarifications': sorted(c.fact for c in p.clarifications),
                'modifiers': list(p.modifier_considerations),
                'checks': sorted(c.id for c in p.checks if c.status in ('warn', 'fail')), 'fingerprint': p.fingerprint}
        view['violations'] = violations(truths[p.code], view)
        proposals[p.code] = view
    return {'date': [facts['service_date']['origin'], facts['service_date']['value']],
            'routing': {f['family']: f['status'] for f in routing['findings']},
            'inventory': {s['family']: s['status'] for s in result.services.get('services', [])},
            'proposals': proposals, 'truth': truths}


def run(only='', m=None) -> dict:
    m = m or modules()
    return {name: run_row(m, name, text, codes, R8_USER.get(name)) for name, (text, codes) in CASES.items()
            if only in name}


def movements(base: dict, head: dict) -> list:
    """[row, code, from, to] for every code whose (bucket, status) differs between two runs."""
    out = []
    for name, row in base.items():
        for code, p in row['proposals'].items():
            q = head.get(name, {}).get('proposals', {}).get(code)
            before, after = f"{p['bucket']}/{p['status']}", (f"{q['bucket']}/{q['status']}" if q else 'absent')
            if before != after:
                out.append([name, code, before, after])
    return out


def summary(result: dict) -> dict:
    counts = {'rows': len(result), 'codes': 0, 'violations': 0, 'judged': 0, 'ready': 0, 'excluded': 0, 'held': 0}
    for row in result.values():
        for code, p in row['proposals'].items():
            counts['codes'] += 1
            counts['judged'] += judged_truth(row['truth'][code]) != 'MAY'
            counts['violations'] += bool(p['violations'])
            counts['ready' if p['status'] == 'ready' else 'excluded' if p['bucket'] == 'excluded' else 'held'] += 1
    return counts


def print_rows(result):
    for name, row in result.items():
        route = ' '.join(f'{f[3:]}={s}' for f, s in row['routing'].items())
        props = ' '.join(f"{code}:{p['bucket'][:3]}/{p['status']}" + (f"[{','.join(p['clarifications'])}]"
                                                                     if p['clarifications'] else '')
                         + ('  <-- ' + '; '.join(p['violations']) if p['violations'] else '')
                         for code, p in row['proposals'].items())
        print(f"{name[:44]:44s} date={row['date'][0][:4]} | {route}\n{'':44s} {props}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m ops.gi4.battery')
    parser.add_argument('--tree')
    parser.add_argument('--base')
    parser.add_argument('--head')
    parser.add_argument('--only', default='')
    parser.add_argument('--declare')
    parser.add_argument('--scratch')
    parser.add_argument('--json-out', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.base or args.head:
        scratch = boot.scratch_dir(args.scratch)
        base = boot.run_tool('battery', boot.tree_arg(args.base, scratch), ['--only', args.only], scratch=scratch,
                             label='base')
        head = boot.run_tool('battery', boot.tree_arg(args.head, scratch), ['--only', args.only], scratch=scratch,
                             label='head')
        print(f'== base {summary(base)}\n== head {summary(head)}')
        declared = json.loads(open(args.declare, encoding='utf-8').read()).get('battery', []) if args.declare else []
        moved = movements(base, head)
        undeclared = [m for m in moved if m not in declared]
        new_violations = [[n, c, p['violations']] for n, row in head.items() for c, p in row['proposals'].items()
                          if p['violations'] and not base.get(n, {}).get('proposals', {}).get(c, {}).get('violations')]
        for m_ in moved:
            print(f"  movement {m_[0]} {m_[1]}: {m_[2]} -> {m_[3]}{'' if m_ in declared else '  <-- UNDECLARED'}")
        for v in new_violations:
            print(f'  NEW VIOLATION {v}')
        print(f'== {len(moved)} movements, {len(undeclared)} undeclared; {len(new_violations)} new violations')
        return 1 if undeclared or new_violations else 0
    boot.offline(args.tree)
    result = run(args.only)
    if args.json_out:
        boot.write_json(args.json_out, result)
        return 0
    print_rows(result)
    print(f'== {summary(result)}')
    print(REVIEW_NOTE)
    return 0


if __name__ == '__main__':
    sys.exit(main())
