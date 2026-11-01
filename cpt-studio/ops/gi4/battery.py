"""H4: the assess battery. Each row is a synthetic document with a synthetic provider answer (codes with exact
evidence), read as the stages read it: the analyze child's facts and routing (jobs._analyze_child), the member's answer
merged (jobs._merged_facts), and the assess child (jobs._assess_child) with an in-memory answer and no reference rows.
In-process and offline: nothing is sent and no database is read.

Permanent rows: the minimal design's 28 cases (its battery.py, verbatim) and the judge's J1-J8, K1-K3, E1-E4 and S1-S3
(judge_battery.py, verbatim). Each code carries a PROVISIONAL truth (no qualified GI coder has reviewed it):
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
FILL = ''.join(f'Line {i} of the outside summary lists medications and allergies in detail.\n' for i in range(8))
SNARE = 'A 10 mm polyp was removed with a hot snare.'

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
    found = []
    for i, (code, quote, _) in enumerate(codes):
        start = text.index(quote)
        found.append(m.ProviderCode(role='selected', system='cpt', code=code, display='SYNTHETIC', index=i,
                                    evidence=(m.EvidenceSpan(0, start, start + len(quote), quote, True, 1),)))
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
    return {name: run_row(m, name, text, codes) for name, (text, codes) in CASES.items() if only in name}


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
