"""Harness repair 3 (owner directive 2026-11-05, second message): refutation round 1 over the stage commit 1974c8cb1 and
its repairs, pinned. This is the first cycle of the programme's two-cycle rule for every rule this repair added.

Six lenses refuted the finished stage diff: L1 the releasing rules, L2 escapes from the holding rules, L3 false holds
and regressions, L4 admission and competition, L5 sections and acts, L6 Stop and Resume. Every input below is a lens's
own counterexample or control, verbatim. The engine cases run both paths - Corti selecting the code, and an independent
participant's first reading proposing it alone (tests.test_h2_refutation_r1.both) - and each row records above it what
the stage commit and base 406843018 read: every finding's input read on the stage commit as its lens reported, and reads
here as pinned. Where this tree still does not read an input as its lens wanted, the row is in RecordedResidualTests
with its reason, never silently. The database cases (L4-5, L4-6, L6) run the real API and pipeline with fake adapters;
nothing is sent. HARNESS.md, "Harness repair 3", "Refutation round 1".

Refutation cycle 2 (HARNESS.md "Harness repair 3, refutation cycle 2") dropped F-TIME R, F-SECTIONS T and L and F-ACTS'
round-1 vocabulary under the two-cycle rule. Cycle 3 narrowed its provider-neutral admission to an act stated done inside
a service documented in doubt, and cycle 4 dropped the rebuilt F-ACTS. Every row is pinned as this tree reads it, with its round-1 reading in its comment where
it moved: a participant's code held beside Corti's where the act is done in a doubted service, and the dropped rules'
inputs read as the base reads them. Those that now read otherwise than their lens wanted are in RecordedResidualTests
with their reasons."""
import hashlib
import json
from decimal import Decimal

from django.test import Client, SimpleTestCase, TestCase

import tests.test_harness2_pipeline as h2p
from studio import answers, customer_api, jobs, models, reports, review, serializers
from studio.gi import context as gi_context
from studio.gi import detect
from studio.participants.loop import summed_usage
from studio.types import NormalizedResponse, to_jsonable
from studio.validation import engine, review_view
from studio.validation.engine import assess
from tests.support import pipeline_factories as pf
from tests.test_cux_review import retrieval_for
from tests.test_h2_refutation_r1 import COLON, EGD, both
from tests.test_harness_engine import REFERENCE, code, corti, read, run, span
from tests.test_repairs_pipeline import FIRST_DATE, NO_DATE_NOTE, RECONCILE_NOTE

SYN = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
# the lenses' own headers, verbatim (L1: EGD_PLAIN; L2: EGD2, NOPOLYP, DOC, DOC_REF; L3: CR)
NOPOLYP = COLON + 'No polyps were found today.\n'
EGD2 = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nProcedure: Upper endoscopy\n'
        'The gastroscope was passed to the second portion of the duodenum.\n'
        'The esophagus was normal, with no residual food.\n')
DOC = (SYN + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nEndoscopist: Jane Synthetic-Doe, MD\n'
       'Procedure: Colonoscopy\nThe colonoscope was advanced to the cecum and the examination was completed.\n')
DOC_REF = DOC.replace('Endoscopist: Jane Synthetic-Doe, MD\n',
                      'Endoscopist: Jane Synthetic-Doe, MD    Referring physician: John Taylor, MD\n')
CR = SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist: Jane Smith, MD\n'
EGD_PLAIN = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD\n'
             'Procedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the duodenum.\n')
READY = ('selected', 'ready')
HELD = ('selected', 'needs_clarification')
ALT = ('alternative', 'informational')
EXCL = ('excluded', 'excluded')

# Each row: (the lens's id, the text, the code, its quote - None for the text's last line -, Corti's outcome, the
# participant's). The comment above a row is what the stage commit and the base read, measured before it was pinned.
R1_L1_1 = [
    # stage READY/READY, base EXCL/ALT
    ('L1-1a', COLON + 'India ink was injected distal to the lesion in the ascending colon for future localization '
                      'at the time of EMR.\n',
     '45390', None, EXCL, ALT),
    # stage READY/READY, base EXCL/ALT
    ('L1-1b', COLON + 'The lesion in the ascending colon was tattooed for future surgery or EMR.\n',
     '45390', None, EXCL, ALT),
    # stage READY/READY, base EXCL/ALT
    ('L1-1c', COLON + 'The lesion in the ascending colon was tattooed for future removal by snare polypectomy.\n',
     '45385', None, EXCL, ALT),
    # stage READY/READY, base EXCL/ALT
    ('L1-1d', EGD + 'The gastric antral lesion was biopsied for future treatment with APC.\n',
     '43270', None, EXCL, ALT),
    # stage READY/READY, base EXCL/ALT
    ('L1-1e', COLON + 'The lesion in the ascending colon was tattooed for future localization and biopsy.\n',
     '45380', None, EXCL, ALT),
    # stage READY/READY, base EXCL/ALT
    ('L1-1f', COLON + 'The lesion in the ascending colon was tattooed for future identification and endoscopic '
                      'mucosal resection.\n',
     '45390', None, EXCL, ALT),
    # stage EXCL/ALT, base EXCL/ALT
    ('L1-1-D1-control', COLON + 'The lesion in the ascending colon was tattooed for future EMR.\n',
     '45390', None, EXCL, ALT),
]
R1_L1_2 = [
    # stage READY/READY, base EXCL/ALT
    ('L1-2a', EGD_PLAIN + 'Duodenal biopsies were obtained for future comparison at colonoscopy to the cecum.\n',
     '45378', None, EXCL, ALT),
    # stage EXCL/ALT, base EXCL/ALT
    ('L1-2-D1-control', EGD_PLAIN + 'Duodenal biopsies were obtained for future colonoscopy to the cecum.\n',
     '45378', None, EXCL, ALT),
]
R1_L1_3 = [
    # stage READY/READY, base HELD/ALT
    ('L1-3a', COLON + 'A 6 mm polyp in the ascending colon was reached with the cold snare and not resected.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L1-3b', COLON + 'The polyp behind the fold in the ascending colon was reached with a cold snare and not '
                      'resected because of a non-lifting sign.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L1-3c', COLON + 'Ascending colon polyp reached with cold snare and not resected.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L1-3d', COLON + 'A 6 mm polyp in the ascending colon was reached with a cold snare and not removed.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L1-3e', COLON + 'The 3 mm polyp in the ascending colon was reached with hot forceps and not removed.\n',
     '45384', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L1-3f', EGD + 'The visible vessel in the gastric ulcer was reached with the bipolar probe and not treated.\n',
     '43255', None, HELD, ALT),
]
R1_L1_4 = [
    # stage READY/ALT, base EXCL/ALT
    ('L1-4a', COLON + 'India ink tattoo was requested for future localization.\n',
     '45381', None, EXCL, ALT),
    # stage READY/ALT, base EXCL/ALT
    ('L1-4b', COLON + 'The patient was counseled about India ink tattoo for future localization.\n',
     '45381', None, EXCL, ALT),
    # stage READY/ALT, base EXCL/ALT
    ('L1-4c', COLON + 'Tattoo needed for future localization.\n',
     '45381', None, EXCL, ALT),
    # stage READY/READY, base EXCL/ALT, round 1 HELD/ALT. Completion repair (2026-11-06, U5; builder A): the purpose's
    # "future" no longer dates the completed marking, so the outside report's heading decides - held as another source,
    # exactly as its plain form below (it had been excluded as planned, the right outcome for the wrong reason)
    ('L1-4d', COLON + 'Outside report:\nThe lesion in the ascending colon was tattooed for future localization.\n',
     '45381', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L1-4d-plain', COLON + 'Outside report:\nThe lesion in the ascending colon was tattooed.\n',
     '45381', None, HELD, ALT),
]
R1_L2_1 = [
    # stage READY/READY, base HELD/ALT
    ('L2-1a', EGD2 + 'At OSH, the meat bolus was removed with a retrieval net.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L2-1b', EGD2 + 'At the transferring hospital, the meat bolus was removed with a retrieval net.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L2-1c', EGD2 + 'Per the patient, the meat bolus was removed with a retrieval net.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L2-1d', EGD2 + 'Before arrival, the meat bolus was removed with a retrieval net.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-1e', COLON + 'At OSH, a 6 mm polyp in the ascending colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-1f', COLON + 'At a community hospital, a 6 mm polyp in the ascending colon was removed with a cold '
                      'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-1h', COLON + 'Per outside GI, a 6 mm polyp in the ascending colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base HELD/ALT
    ('ctl-1', EGD2 + 'At the referring facility, the meat bolus was removed with a retrieval net.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT, round 1 READY/READY. Completion repair (2026-11-06, U1; builder A): the control
    # is today's removal again - the meat bolus is the structural subject of its removal - the corpus's required READY
    ('ctl-1t', EGD2 + 'The meat bolus was removed with a retrieval net.\n',
     '43247', None, READY, READY),
]
R1_L2_2 = [
    # stage READY/READY, base READY/READY
    ('L2-2a', NOPOLYP + 'Outside records:\nA 6 mm polyp in the ascending colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-2b', NOPOLYP + 'Records received from Synthetic Valley Hospital:\nA 6 mm polyp in the ascending colon was '
                        'removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L2-2c', EGD2 + 'Outside records:\nThe meat bolus was removed with a retrieval net.\n',
     '43247', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('ctl-2', NOPOLYP + 'Outside records: a 6 mm polyp in the ascending colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
]
R1_L2_3 = [
    # stage READY/READY, base READY/READY
    ('L2-3a', DOC + 'A 6 mm polyp in the ascending colon was removed with a cold snare by Dr. John Taylor MD.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-3b', DOC_REF + 'A 6 mm polyp in the ascending colon was removed with a cold snare by Dr. Taylor.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-3c', DOC + 'A 6 mm polyp in the ascending colon was removed with a cold snare BY DR. TAYLOR.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('ctl-3a', DOC + 'A 6 mm polyp in the ascending colon was removed with a cold snare by Dr. John Taylor DO.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('ctl-3b', DOC + 'A 6 mm polyp in the ascending colon was removed with a cold snare by Dr. Taylor.\n',
     '45385', None, HELD, ALT),
]
R1_L2_4 = [
    # stage READY/READY, base READY/READY
    ('L2-4a', EGD + 'Before this exam, the stricture was dilated to 15 mm with a balloon.\n',
     '43249', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-4b', EGD + 'Before this EGD, the stricture was dilated to 15 mm with a balloon.\n',
     '43249', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-4c', COLON + 'Before this colonoscopy, a 6 mm polyp in the ascending colon was removed with a cold '
                      'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-4d', EGD + 'The week before, the stricture was dilated to 15 mm with a balloon.\n',
     '43249', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-4e', COLON + 'Prior to this procedure today, a 6 mm polyp in the ascending colon was removed with a cold '
                      'snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('ctl-4', EGD + 'Before this procedure, the stricture was dilated to 15 mm with a balloon.\n',
     '43249', None, HELD, ALT),
]
R1_L2_5 = [
    # stage READY/READY, base READY/READY
    ('L2-5a', COLON + 'In the event that a 6 mm polyp in the ascending colon was removed with a cold snare, '
                      'surgery would follow.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-5b', COLON + 'Should the 6 mm polyp in the ascending colon be removed with a cold snare, surgery would '
                      'follow.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-5c', COLON + 'Providing a 6 mm polyp in the ascending colon was removed with a cold snare, surgery would '
                      'follow.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-5d', COLON + 'There is no documentation that a 6 mm polyp in the ascending colon was removed with a cold '
                      'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-5e', COLON + 'It cannot be confirmed that a 6 mm polyp in the ascending colon was removed with a cold '
                      'snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('ctl-5', COLON + 'If a 6 mm polyp in the ascending colon was removed with a cold snare, surgery would '
                      'follow.\n',
     '45385', None, HELD, ALT),
]
R1_L2_6 = [
    # stage READY/READY, base READY/READY
    ('L2-6a', COLON + 'The 25 mm ascending colon lesion was biopsied with cold forceps and is to be tattooed.\n',
     '45381', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-6b', COLON + 'The ascending colon lesion was biopsied with cold forceps and needs to be tattooed.\n',
     '45381', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-6c', COLON + 'Cold forceps biopsies were obtained and tattoo ink is to be injected distal to the lesion.\n',
     '45381', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('ctl-6', COLON + 'Tattoo ink is to be injected distal to the lesion.\n',
     '45381', None, HELD, ALT),
]
R1_L2_7 = [
    # stage READY/READY, base READY/READY
    ('L2-7a', COLON + 'The 15 mm sigmoid polyp was snared, but the polypectomy was aborted because of bleeding.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-7b', COLON + 'The 15 mm sigmoid polyp was snared with a hot snare; the polypectomy was then stopped '
                      'because of bleeding.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-7c', COLON + 'The 15 mm sigmoid polyp was snared, but the polypectomy was discontinued because of '
                      'bleeding.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-7d', COLON + 'A cold snare was placed around the 6 mm sigmoid polyp, but the polyp could not be '
                      'transected.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('ctl-7', COLON + 'The 15 mm sigmoid polyp was snared, but the polypectomy was unsuccessful because of '
                      'bleeding.\n',
     '45385', None, HELD, ALT),
]
R1_L2_8 = [
    # stage READY/READY, base READY/READY
    ('L2-8a', COLON + "Biopsies won't be obtained from the ascending colon because the patient is on apixaban.\n",
     '45380', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-8b', COLON + 'Polyp in the ascending colon never successfully snared.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L2-8c', COLON + 'Biopsies never actually obtained from the ascending colon.\n',
     '45380', None, HELD, ALT),
    # stage EXCL/ALT, base HELD/ALT
    ('ctl-8', COLON + 'Biopsies never obtained from the ascending colon.\n',
     '45380', None, EXCL, ALT),
]
R1_L3_1 = [
    # stage EXCL/ALT, base READY/READY
    ('L3-1#0', CR + 'Prior procedures:\n\nProcedure\nThe colonoscope was advanced to the cecum and the examination '
                    'was completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage EXCL/ALT, base READY/READY
    ('L3-1#1', CR + 'Interval history:\nProcedure Note\nThe colonoscope was advanced to the cecum and the '
                    'examination was completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage EXCL/ALT, base READY/READY
    ('L3-1#2', CR + 'History:\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                    'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage EXCL/ALT, base READY/READY
    ('L3-1#3', CR + 'Hx:\nProcedure performed\nThe colonoscope was advanced to the cecum and the examination was '
                    'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-1#4', CR + 'History:\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                    'completed.\n',
     '45378', 'The colonoscope was advanced to the cecum', READY, READY),
    # stage READY/READY, base READY/READY
    ('L3-1#5', CR + 'Procedure\nThe colonoscope was advanced to the cecum and the examination was completed.\nA 6 '
                    'mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
]
R1_L3_2 = [
    # stage EXCL/ALT, base HELD/ALT
    ('L3-2#0', COLON + 'Sigmoid colon polyp removed with cold snare, not retrieved.\n',
     '45385', None, HELD, ALT),
    # stage EXCL/ALT, base HELD/ALT
    ('L3-2#1', COLON + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare, not retrieved.\n',
     '45385', None, HELD, ALT),
    # stage EXCL/ALT, base HELD/ALT
    ('L3-2#2', COLON + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare and the site not clipped.\n',
     '45385', None, HELD, ALT),
    # stage EXCL/ALT, base HELD/ALT
    ('L3-2#3', COLON + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare and not tattooed.\n',
     '45385', None, HELD, ALT),
    # stage EXCL/ALT, base HELD/ALT
    ('L3-2#4', COLON + 'Ascending colon lesion biopsied with cold forceps, not tattooed.\n',
     '45380', 'Ascending colon lesion biopsied with cold forceps', HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('L3-2#6', EGD + 'Esophageal varices were banded with four bands and not clipped.\n',
     '43244', 'Esophageal varices were banded with four bands', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-2#7', EGD + 'Biopsies were obtained from the gastric antrum, one specimen not retrieved.\n',
     '43239', 'Biopsies were obtained from the gastric antrum', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-2#8', COLON + 'Sigmoid polyp removed with cold snare, site not clipped.\n',
     '45385', 'Sigmoid polyp removed with cold snare', READY, READY),
    # stage READY/READY, base READY/READY
    ('L3-2#9', COLON + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare but not retrieved.\n',
     '45385', None, READY, READY),
]
R1_L3_3 = [
    # stage HELD/ALT, base READY/READY
    ('L3-3#0', EGD + 'A Schatzki ring, never dilated before, was dilated to 18 mm with a balloon.\n',
     '43249', 'was dilated to 18 mm with a balloon', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-3#1', EGD + 'Large esophageal varices (never banded) were ligated with four bands.\n',
     '43244', 'were ligated with four bands', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-3#2', EGD + 'The gastric ulcer, never biopsied before, was biopsied with cold forceps.\n',
     '43239', 'was biopsied with cold forceps', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-3#3', COLON + 'The ascending colon lesion, never tattooed before, was tattooed with India ink.\n',
     '45381', 'was tattooed with India ink', READY, READY),
]
R1_L3_4 = [
    # stage HELD/ALT, base READY/READY
    ('L3-4#0', COLON + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare, and the polypectomy was '
                       'not complicated by bleeding.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#1', COLON + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare, and the polypectomy did '
                       'not result in bleeding.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#2', EGD + 'Cold forceps biopsies were obtained from the duodenum, and the biopsy sites did not bleed.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#3', EGD + 'Biopsies of the gastric antrum were obtained, and the biopsy was not complicated by '
                     'bleeding.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#4', EGD + 'The stricture was dilated to 15 mm with a through-the-scope balloon, and the dilation was '
                     'not associated with any mucosal tear.\n',
     '43249', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#5', EGD + 'The stricture was dilated to 15 mm with a through-the-scope balloon; the dilation did not '
                     'cause a tear.\n',
     '43249', 'The stricture was dilated to 15 mm with a through-the-scope balloon', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#6', EGD + 'Biopsies were obtained from the gastric antrum, but the biopsy forceps could not be advanced '
                     'through the duodenal stricture.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#7', COLON + 'A 15 mm polyp in the ascending colon was removed with a hot snare, and the polypectomy '
                       'defect was not closed.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-4#8', COLON + 'The lesion in the ascending colon was tattooed with India ink, and the tattoo did not '
                       'spread beyond the injection site.\n',
     '45381', 'The lesion in the ascending colon was tattooed with India ink', READY, READY),
    # stage EXCL/ALT, base HELD/ALT
    ('L3-4#9', COLON + 'A 15 mm polyp in the ascending colon was removed with a hot snare; the polypectomy base '
                       'was not clipped.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY
    ('L3-4#10', COLON + 'A 6 mm polyp in the sigmoid colon was removed with a cold snare, and the polypectomy site '
                        'did not bleed.\n',
     '45385', None, READY, READY),
]
R1_L3_5 = [
    # stage HELD/ALT, base READY/READY
    ('L3-5#0', EGD + 'Four-quadrant biopsies were obtained from the distal esophagus every 2 cm according to the '
                     'Seattle protocol.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#1', EGD + 'Biopsies were obtained from the gastric antrum and body according to the updated Sydney '
                     'system.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#2', COLON + 'The lesion in the ascending colon was tattooed according to institutional protocol.\n',
     '45381', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#3', COLON + 'At the request of the referring physician, biopsies were obtained from the ascending '
                       'colon.\n',
     '45380', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#4', COLON + 'Biopsies were obtained from the ascending colon, with a copy of this report to the '
                       'referring physician.\n',
     '45380', 'Biopsies were obtained from the ascending colon', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#5', EGD + 'Biopsies were obtained from the gastric antrum and elsewhere in the stomach.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#6', EGD + 'Biopsies were obtained from the gastric ulcer rim outside the necrotic center.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#7', COLON + 'The 25 mm polyp in the ascending colon was removed with a hot snare with the assistance of '
                       'another physician.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-5#8', COLON + 'At the request of the referring surgeon, the lesion in the ascending colon was tattooed.\n',
     '45381', None, READY, READY),
]
R1_L3_6 = [
    # stage HELD/ALT, base READY/READY
    ('L3-6#0', SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nPerformed by: Jane Smith, '
                     'MD\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                     'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-6#1', SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nGastroenterologist: Jane Smith, '
                     'MD\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                     'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-6#2', SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nAttending physician: Jane Smith, '
                     'MD\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                     'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-6#3', SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nPerforming endoscopist: Jane Smith, '
                     'MD\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                     'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-6#4', SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nColonoscopist: Jane Smith, '
                     'MD\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                     'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-6#5', SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopists: Jane Smith, '
                     'MD\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                     'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-6#6', SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist:\nJane Smith, '
                     'MD\nProcedure\nThe colonoscope was advanced to the cecum and the examination was '
                     'completed.\nA 6 mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
    # stage READY/READY, base READY/READY
    ('L3-6#7', CR + 'Procedure\nThe colonoscope was advanced to the cecum and the examination was completed.\nA 6 '
                    'mm polyp in the sigmoid colon was removed with a cold snare by Dr. Smith.\n',
     '45385', None, READY, READY),
]
R1_L3_7 = [
    # stage HELD/ALT, base READY/READY
    ('L3-7#0', EGD + 'The Schatzki ring was able to be dilated to 18 mm with a through-the-scope balloon.\n',
     '43249', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-7#1', EGD + 'The stricture had to be dilated to 15 mm with a through-the-scope balloon before the scope '
                     'could pass.\n',
     '43249', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-7#2', EGD + 'The large varix had to be banded twice because the first band slipped.\n',
     '43244', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-7#3', EGD + 'The gastric ulcer had to be biopsied with cold forceps to exclude malignancy.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-7#4', EGD + 'The stricture needed to be dilated to 15 mm with a balloon before the scope could pass.\n',
     '43249', None, READY, READY),
]
R1_L3_8 = [
    # stage HELD/ALT, base READY/READY
    ('L3-8#0', EGD + 'To check if H. pylori is present biopsies were obtained from the gastric antrum and body.\n',
     '43239', 'biopsies were obtained from the gastric antrum and body', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-8#1', EGD + 'To determine whether celiac disease is present biopsies were obtained from the second '
                     'portion of the duodenum.\n',
     '43239', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-8#2', COLON + 'The patient was asked if she wished to proceed and biopsies were obtained from the '
                       'ascending colon.\n',
     '45380', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-8#3', COLON + 'Unless otherwise noted all biopsies were obtained with cold forceps from the ascending '
                       'colon.\n',
     '45380', None, READY, READY),
]
R1_L3_9 = [
    # stage HELD/ALT, base READY/READY
    ('L3-9#0', COLON + 'Prior to withdrawal, the lesion in the ascending colon was tattooed.\n',
     '45381', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-9#1', COLON + 'Earlier in the procedure, the lesion in the ascending colon was tattooed.\n',
     '45381', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-9#2', COLON + 'Prior to the polypectomy, the lesion in the ascending colon was tattooed.\n',
     '45381', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-9#3', COLON + 'Prior to withdrawal, the lesion in the ascending colon was biopsied with cold forceps.\n',
     '45380', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-9#4', EGD + 'Prior to dilation, the Schatzki ring was biopsied with cold forceps.\n',
     '43239', None, READY, READY),
    # stage READY/READY, base READY/READY
    ('L3-9#5', COLON + 'On withdrawal, the lesion in the ascending colon was tattooed.\n',
     '45381', None, READY, READY),
]
R1_L3_12 = [
    # stage HELD/ALT, base READY/READY
    ('L3-12#0', CR + 'Procedure: Colonoscopy with cold snare polypectomy\nThe colonoscope was advanced to the '
                     'cecum and the examination was completed.\nThe 6 mm polyp in the sigmoid colon was able to be '
                     'removed with a cold snare.\n',
     '45385', 'Colonoscopy with cold snare polypectomy', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-12#1', CR + 'Procedure: Colonoscopy with cold snare polypectomy\nThe colonoscope was advanced to the '
                     'cecum and the examination was completed.\nA 6 mm polyp in the sigmoid colon was removed with '
                     'a cold snare, and the polypectomy was not complicated by bleeding.\n',
     '45385', 'Colonoscopy with cold snare polypectomy', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-12#2', SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Jane Smith, '
                      'MD\nProcedure: EGD with balloon dilation\nThe gastroscope was passed to the second portion '
                      'of the duodenum.\nThe stricture had to be dilated to 15 mm with a through-the-scope balloon '
                      'before the scope could pass.\n',
     '43249', 'EGD with balloon dilation', READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-12#3', CR + 'Procedure: Colonoscopy with biopsy\nThe colonoscope was advanced to the cecum and the '
                     'examination was completed.\nThe patient was asked if she wished to proceed and biopsies were '
                     'obtained from the ascending colon.\n',
     '45380', 'Colonoscopy with biopsy', READY, READY),
]
R1_L5_1 = [
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-1:date-in-2nd-sentence', SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: '
                                        'Synthetic Endoscopist, MD (fictional)\nSedation: Monitored anesthesia '
                                        'care.\nIndications: Dysphagia.\nColonoscopy: The colonoscope was advanced '
                                        'to the cecum. This examination was performed on 2026-09-02. A 9 mm polyp '
                                        'in the sigmoid colon was removed with a cold snare.\nProcedure: Upper '
                                        'endoscopy\nThe gastroscope was advanced to the second portion of the '
                                        'duodenum. The examination was normal.\nImpression: Normal upper '
                                        'endoscopy.\nPlan: Follow up in clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-1:CONTROL-todays-date-in-2nd-sentence',
     SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nSedation: Monitored anesthesia care.\nIndications: Dysphagia.\nColonoscopy: The '
           'colonoscope was advanced to the cecum. This examination was performed on 2026-10-14. A 9 mm polyp in '
           'the sigmoid colon was removed with a cold snare.\nProcedure: Upper endoscopy\nThe gastroscope was '
           'advanced to the second portion of the duodenum. The examination was normal.\nImpression: Normal upper '
           'endoscopy.\nPlan: Follow up in clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-1:outside-hospital-in-2nd-sentence',
     SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nSedation: Monitored anesthesia care.\nIndications: Dysphagia.\nColonoscopy: The '
           'colonoscope was advanced to the cecum. That examination was performed at an outside hospital. A 9 mm '
           'polyp in the sigmoid colon was removed with a cold snare.\nProcedure: Upper endoscopy\nThe gastroscope '
           'was advanced to the second portion of the duodenum. The examination was normal.\nImpression: Normal '
           'upper endoscopy.\nPlan: Follow up in clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-1:referring-hospital-in-1st-sentence',
     SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nSedation: Monitored anesthesia care.\nIndications: Dysphagia.\nColonoscopy: At the '
           'referring hospital, the colonoscope was advanced to the cecum.\nA 9 mm polyp in the sigmoid colon was '
           'removed with a cold snare.\nProcedure: Upper endoscopy\nThe gastroscope was advanced to the second '
           'portion of the duodenum. The examination was normal.\nImpression: Normal upper endoscopy.\nPlan: '
           'Follow up in clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-1:paren-outside-in-1st-sentence', SYN + 'Upper Endoscopy Report\nDate of service: '
                                                 '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                                                 '(fictional)\nSedation: Monitored anesthesia care.\nIndications: '
                                                 'Dysphagia.\nColonoscopy: (outside) The colonoscope was advanced '
                                                 'to the cecum.\nA 9 mm polyp in the sigmoid colon was removed '
                                                 'with a cold snare.\nProcedure: Upper endoscopy\nThe gastroscope '
                                                 'was advanced to the second portion of the duodenum. The '
                                                 'examination was normal.\nImpression: Normal upper '
                                                 'endoscopy.\nPlan: Follow up in clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage READY/READY, base HELD/ALT
    ('L5-1:previously-then-extent', SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: '
                                          'Synthetic Endoscopist, MD (fictional)\nSedation: Monitored anesthesia '
                                          'care.\nIndications: Dysphagia.\nColonoscopy: Previously, the '
                                          'colonoscope was introduced through the anus. It was advanced to the '
                                          'cecum. A 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\nProcedure: Upper endoscopy\nThe gastroscope was advanced to the '
                                          'second portion of the duodenum. The examination was '
                                          'normal.\nImpression: Normal upper endoscopy.\nPlan: Follow up in '
                                          'clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-1:year-after-Dr-abbreviation', SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: '
                                              'Synthetic Endoscopist, MD (fictional)\nSedation: Monitored '
                                              'anesthesia care.\nIndications: Dysphagia.\nColonoscopy: The '
                                              'colonoscope was introduced by Dr. Jones in 2019. It was advanced to '
                                              'the cecum.\nA 9 mm polyp in the sigmoid colon was removed with a '
                                              'cold snare.\nProcedure: Upper endoscopy\nThe gastroscope was '
                                              'advanced to the second portion of the duodenum. The examination was '
                                              'normal.\nImpression: Normal upper endoscopy.\nPlan: Follow up in '
                                              'clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, ALT),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-1:index-colonoscopy-named-by-indication',
     SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nSedation: Monitored anesthesia care.\nIndications: Surveillance; the findings of the '
           'index colonoscopy follow.\nColonoscopy: The colonoscope was advanced to the cecum.\nA 9 mm polyp in '
           'the sigmoid colon was removed with a cold snare.\nProcedure: Upper endoscopy\nThe gastroscope was '
           'advanced to the second portion of the duodenum. The examination was normal.\nImpression: Normal upper '
           'endoscopy.\nPlan: Follow up in clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-1:under-reason-for-referral', SYN + 'Upper Endoscopy Report\nDate of service: 2026-10-14\nEndoscopist: '
                                             'Synthetic Endoscopist, MD (fictional)\nSedation: Monitored '
                                             'anesthesia care.\nReason for referral:\nColonoscopy: The colonoscope '
                                             'was advanced to the cecum.\nA 9 mm polyp in the sigmoid colon was '
                                             'removed with a cold snare.\nProcedure: Upper endoscopy\nThe '
                                             'gastroscope was advanced to the second portion of the duodenum. The '
                                             'examination was normal.\nImpression: Normal upper endoscopy.\nPlan: '
                                             'Follow up in clinic.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
]
R1_L5_2 = [
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-2:clinic-note-attending-field', SYN + 'Gastroenterology Clinic Note\nDate of service: '
                                               '2026-10-14\nAttending: Synthetic Endoscopist, MD '
                                               '(fictional)\nReason for visit: Follow-up after '
                                               'colonoscopy.\nColonoscopy: The colonoscope was advanced to the '
                                               'cecum.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                               'snare.\nAssessment: Colon polyp, removed. Iron deficiency anemia, '
                                               'improving.\nMedical decision making: Moderate; reviewed pathology '
                                               'and laboratory results, adjusted iron therapy.\nTotal time: 30 '
                                               'minutes on the date of the encounter.\nPlan: Surveillance '
                                               'colonoscopy in 5 years.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage HELD/ALT, base HELD/ALT
    ('L5-2:CONTROL-clinic-note-without-label',
     SYN + 'Gastroenterology Clinic Note\nDate of service: 2026-10-14\nAttending: Synthetic Endoscopist, MD '
           '(fictional)\nReason for visit: Follow-up after colonoscopy.\nThe colonoscope was advanced to the '
           'cecum.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\nAssessment: Colon polyp, '
           'removed. Iron deficiency anemia, improving.\nMedical decision making: Moderate; reviewed pathology and '
           'laboratory results, adjusted iron therapy.\nTotal time: 30 minutes on the date of the '
           'encounter.\nPlan: Surveillance colonoscopy in 5 years.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, ALT),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-2:office-visit-sedation-in-allergies',
     SYN + 'Gastroenterology office visit\nDate of service: 2026-10-14\nProvider: Synthetic Consultant, MD '
           '(fictional)\nAllergies: No known drug allergies; tolerated sedation well in the past.\nChief '
           'complaint: Results of colonoscopy.\nColonoscopy: The colonoscope was advanced to the cecum.\nA 9 mm '
           'polyp in the sigmoid colon was removed with a cold snare.\nAssessment: Colon polyp, removed. Iron '
           'deficiency anemia, improving.\nMedical decision making: Moderate; reviewed pathology and laboratory '
           'results, adjusted iron therapy.\nTotal time: 30 minutes on the date of the encounter.\nPlan: '
           'Surveillance colonoscopy in 5 years.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-2:office-visit-gastroenterologist-field',
     SYN + 'Office visit\nDate of service: 2026-10-14\nGastroenterologist: Synthetic Consultant, MD '
           '(fictional)\nChief complaint: Follow-up.\nColonoscopy: The colonoscope was advanced to the cecum.\nA 9 '
           'mm polyp in the sigmoid colon was removed with a cold snare.\nAssessment: Colon polyp, removed. Iron '
           'deficiency anemia, improving.\nMedical decision making: Moderate; reviewed pathology and laboratory '
           'results, adjusted iron therapy.\nTotal time: 30 minutes on the date of the encounter.\nPlan: '
           'Surveillance colonoscopy in 5 years.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', HELD, HELD),
]
R1_L5_3 = [
    # stage HELD/ALT, base HELD/ALT
    ('L5-3:title-aside-(pre-op)', SYN + 'Colonoscopy Report (pre-op)\nDate of service: 2026-10-14\nEndoscopist: '
                                        'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to '
                                        'the cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                        'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Preop)', SYN + 'Colonoscopy Report (Preop)\nDate of service: 2026-10-14\nEndoscopist: '
                                       'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                       'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                       'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Preoperative)', SYN + 'Colonoscopy Report (Preoperative)\nDate of service: '
                                              '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                              'colonoscope was advanced to the cecum and the examination was '
                                              'completed.\nA 9 mm polyp in the sigmoid colon was removed with a '
                                              'cold snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base HELD/ALT
    ('L5-3:title-aside-(order)', SYN + 'Colonoscopy Report (order)\nDate of service: 2026-10-14\nEndoscopist: '
                                       'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                       'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                       'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Orders)', SYN + 'Colonoscopy Report (Orders)\nDate of service: 2026-10-14\nEndoscopist: '
                                        'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to '
                                        'the cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                        'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base HELD/ALT
    ('L5-3:title-aside-(possible)', SYN + 'Colonoscopy Report (possible)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Possibly)', SYN + 'Colonoscopy Report (Possibly)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Probably)', SYN + 'Colonoscopy Report (Probably)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base HELD/ALT
    ('L5-3:title-aside-(copy)', SYN + 'Colonoscopy Report (copy)\nDate of service: 2026-10-14\nEndoscopist: '
                                      'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                      'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid colon '
                                      'was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Photocopy)', SYN + 'Colonoscopy Report (Photocopy)\nDate of service: '
                                           '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                           'colonoscope was advanced to the cecum and the examination was '
                                           'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                           'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Duplicate)', SYN + 'Colonoscopy Report (Duplicate)\nDate of service: '
                                           '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                           'colonoscope was advanced to the cecum and the examination was '
                                           'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                           'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Another Facility)', SYN + 'Colonoscopy Report (Another Facility)\nDate of service: '
                                                  '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                                                  '(fictional)\nThe colonoscope was advanced to the cecum and the '
                                                  'examination was completed.\nA 9 mm polyp in the sigmoid colon '
                                                  'was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(External)', SYN + 'Colonoscopy Report (External)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base HELD/ALT
    ('L5-3:title-aside-(not performed)', SYN + 'Colonoscopy Report (not performed)\nDate of service: '
                                               '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                                               '(fictional)\nThe colonoscope was advanced to the cecum and the '
                                               'examination was completed.\nA 9 mm polyp in the sigmoid colon was '
                                               'removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Void)', SYN + 'Colonoscopy Report (Void)\nDate of service: 2026-10-14\nEndoscopist: '
                                      'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                      'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid colon '
                                      'was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Entered in Error)', SYN + 'Colonoscopy Report (Entered in Error)\nDate of service: '
                                                  '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                                                  '(fictional)\nThe colonoscope was advanced to the cecum and the '
                                                  'examination was completed.\nA 9 mm polyp in the sigmoid colon '
                                                  'was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base HELD/ALT
    ('L5-3:title-aside-(2019)', SYN + 'Colonoscopy Report (2019)\nDate of service: 2026-10-14\nEndoscopist: '
                                      'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                      'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid colon '
                                      'was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-3:title-aside-(Two Years Ago)', SYN + 'Colonoscopy Report (Two Years Ago)\nDate of service: '
                                               '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                                               '(fictional)\nThe colonoscope was advanced to the cecum and the '
                                               'examination was completed.\nA 9 mm polyp in the sigmoid colon was '
                                               'removed with a cold snare.\n',
     '45385', None, HELD, HELD),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(October Twelfth)', SYN + 'Colonoscopy Report (October Twelfth)\nDate of service: '
                                                 '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                                                 '(fictional)\nThe colonoscope was advanced to the cecum and the '
                                                 'examination was completed.\nA 9 mm polyp in the sigmoid colon '
                                                 'was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Tomorrow)', SYN + 'Colonoscopy Report (Tomorrow)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage HELD/ALT, base HELD/ALT
    ('L5-3:title-aside-(draft)', SYN + 'Colonoscopy Report (draft)\nDate of service: 2026-10-14\nEndoscopist: '
                                       'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                       'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                       'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Unsigned)', SYN + 'Colonoscopy Report (Unsigned)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Addendum)', SYN + 'Colonoscopy Report (Addendum)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Consult)', SYN + 'Colonoscopy Report (Consult)\nDate of service: 2026-10-14\nEndoscopist: '
                                         'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to '
                                         'the cecum and the examination was completed.\nA 9 mm polyp in the '
                                         'sigmoid colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Request)', SYN + 'Colonoscopy Report (Request)\nDate of service: 2026-10-14\nEndoscopist: '
                                         'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to '
                                         'the cecum and the examination was completed.\nA 9 mm polyp in the '
                                         'sigmoid colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Awaiting)', SYN + 'Colonoscopy Report (Awaiting)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Geplant)', SYN + 'Colonoscopy Report (Geplant)\nDate of service: 2026-10-14\nEndoscopist: '
                                         'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to '
                                         'the cecum and the examination was completed.\nA 9 mm polyp in the '
                                         'sigmoid colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Programada)', SYN + 'Colonoscopy Report (Programada)\nDate of service: '
                                            '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                            'colonoscope was advanced to the cecum and the examination was '
                                            'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                            'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Abgesagt)', SYN + 'Colonoscopy Report (Abgesagt)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Vorlage)', SYN + 'Colonoscopy Report (Vorlage)\nDate of service: 2026-10-14\nEndoscopist: '
                                         'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to '
                                         'the cecum and the examination was completed.\nA 9 mm polyp in the '
                                         'sigmoid colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Borrador)', SYN + 'Colonoscopy Report (Borrador)\nDate of service: '
                                          '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nThe '
                                          'colonoscope was advanced to the cecum and the examination was '
                                          'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                          'snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Copia)', SYN + 'Colonoscopy Report (Copia)\nDate of service: 2026-10-14\nEndoscopist: '
                                       'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                       'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                       'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-3:title-aside-(Previa)', SYN + 'Colonoscopy Report (Previa)\nDate of service: 2026-10-14\nEndoscopist: '
                                        'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to '
                                        'the cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                        'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
]
R1_L5_4 = [
    # stage READY/READY, base EXCL/ALT
    ('L5-4:Prior report: / Received by fax. || Colonoscopy Report (Final)',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nPrior report:\nReceived by fax.\nColonoscopy Report '
           '(Final)\nEndoscopist: Dr. B. Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the '
           'examination was completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, EXCL, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-4:History: see the attached report. || Colonoscopy Report (Final)',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nHistory: see the attached report.\nColonoscopy Report '
           '(Final)\nEndoscopist: Dr. B. Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the '
           'examination was completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-4:Previous procedures: colonoscopy, report below. || Colonoscopy Report (Final)',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nPrevious procedures: colonoscopy, report below.\nColonoscopy '
           'Report (Final)\nEndoscopist: Dr. B. Synthetic (fictional)\nThe colonoscope was advanced to the cecum '
           'and the examination was completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage EXCL/ALT, base EXCL/ALT
    ('L5-4:Prior report: || Colonoscopy Report (Final)',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nPrior report:\nColonoscopy Report (Final)\nEndoscopist: Dr. B. '
           'Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the examination was completed.\nA '
           '9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, EXCL, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-4:Outside report: || Colonoscopy Report (Final)',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nOutside report:\nColonoscopy Report (Final)\nEndoscopist: Dr. '
           'B. Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the examination was '
           'completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
]
R1_L5_5 = [
    # stage HELD/ALT, base HELD/ALT
    ('L5-5:A 50 mg bolus of propofol was given.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nA 50 mg '
           'bolus of propofol was given.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-5:A saline bolus was injected and the polyp was then removed with a hot snare.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nA saline '
           'bolus was injected and the polyp was then removed with a hot snare.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-5:A fentanyl bolus was given and the clip was then removed.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nA fentanyl '
           'bolus was given and the clip was then removed.\n',
     '43247', None, HELD, ALT),
    # stage READY/ALT, base HELD/ALT
    ('L5-5:After a 50 mg propofol bolus, the bite block was removed.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nAfter a 50 '
           'mg propofol bolus, the bite block was removed.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-5:The bolus was cleared by peristalsis.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe bolus '
           'was cleared by peristalsis.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-5:The contrast bolus was cleared from the esophagus by peristalsis.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe '
           'contrast bolus was cleared from the esophagus by peristalsis.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-5:The water bolus was cleared promptly by normal peristalsis.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe water '
           'bolus was cleared promptly by normal peristalsis.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-5:A bolus of retained secretions was cleared with suction.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nA bolus of '
           'retained secretions was cleared with suction.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-5:A bolus of contrast was removed from the field with suction.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nA bolus of '
           'contrast was removed from the field with suction.\n',
     '43247', None, HELD, ALT),
]
R1_L5_6 = [
    # stage READY/READY, base HELD/ALT
    ('L5-6:The meat bolus was passed into the stomach with gentle pressure.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe meat '
           'bolus was passed into the stomach with gentle pressure.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-6:The steak bolus was advanced into the stomach.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe steak '
           'bolus was advanced into the stomach.\n',
     '43247', None, HELD, ALT),
    # stage READY/READY, base HELD/ALT
    ('L5-6:The bolus was cleared into the stomach with gentle insufflation.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe bolus '
           'was cleared into the stomach with gentle insufflation.\n',
     '43247', None, HELD, ALT),
    # stage READY/ALT, base HELD/ALT
    ('L5-6:The bolus was dislodged distally into the stomach with the tip of the scope.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe bolus '
           'was dislodged distally into the stomach with the tip of the scope.\n',
     '43247', None, HELD, ALT),
    # stage READY/ALT, base HELD/ALT
    ('L5-6:The meat impaction resolved spontaneously before arrival.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe meat '
           'impaction resolved spontaneously before arrival.\n',
     '43247', None, HELD, ALT),
]
R1_L5_7 = [
    # stage READY/READY, base HELD/ALT, round 1 HELD/ALT
    ('L5-7:egd-inline-part-then-colon-findings',
     SYN + 'Gastroenterology Procedure Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nSedation: Monitored anesthesia care.\nIndications: Dysphagia and anemia.\nUpper '
           'endoscopy: The gastroscope was advanced into the esophagus and to the second portion of the '
           'duodenum.\nFindings: A 9 mm sigmoid colon polyp was removed with a cold snare.\nImpression: Sigmoid '
           'polyp removed.\n',
     '43251', 'A 9 mm sigmoid colon polyp was removed with a cold snare.', HELD, HELD),
]
R1_RESIDUAL = [
    # stage READY/ALT, base READY/ALT
    ('L1-4a-plain', COLON + 'India ink tattoo was requested.\n',
     '45381', None, READY, ALT),
    # stage READY/READY, base READY/READY, round 1 HELD/ALT
    ('L2-1g', COLON + 'At Synthetic Valley Hospital, a 6 mm polyp in the ascending colon was removed with a cold '
                      'snare.\n',
     '45385', None, READY, READY),
    # stage READY/READY, base READY/READY
    ('L2-1i', COLON + 'She underwent colonoscopy at the referring facility, and a 6 mm polyp in the ascending '
                      'colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage HELD/ALT, base READY/READY
    ('L3-2#5', EGD + 'Two large esophageal varices were ligated with bands, the small ones not banded.\n',
     '43244', 'Two large esophageal varices were ligated with bands', HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('L3-10#0', EGD + 'The food bolus impacted before presentation was removed with a Roth net.\n',
     '43247', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('L3-10#1', EGD + 'The food bolus, impacted since yesterday, was removed with a Roth net.\n',
     '43247', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('L3-10#2', EGD + 'The food bolus, lodged since yesterday evening, was removed with a Roth net.\n',
     '43247', None, HELD, ALT),
    # stage HELD/ALT, base READY/READY
    ('L3-10#3', COLON + "The 6 mm polyp noted on yesterday's CT colonography was removed with a cold snare.\n",
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/ALT
    ('L5-2:inside-a-pathology-addendum', SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: '
                                               'Synthetic Endoscopist, MD (fictional)\nSedation: Monitored '
                                               'anesthesia care.\nProcedure: Upper endoscopy\nThe gastroscope was '
                                               'passed to the second portion of the duodenum. The examination was '
                                               'normal.\nImpression: Normal upper endoscopy.\nPathology '
                                               'addendum\nClinical information: specimen from the separate '
                                               'colonoscopy.\nColonoscopy: The colonoscope was advanced to the '
                                               'cecum.\nA 9 mm polyp in the sigmoid colon was removed with a cold '
                                               'snare.\nDiagnosis: Tubular adenoma.\n',
     '45385', 'A 9 mm polyp in the sigmoid colon was removed with a cold snare.', READY, ALT),
    # stage READY/READY, base HELD/ALT, round 1 READY/READY
    ('L5-3:title-aside-(Final)', SYN + 'Colonoscopy Report (Final)\nDate of service: 2026-10-14\nEndoscopist: '
                                       'Synthetic Endoscopist, MD (fictional)\nThe colonoscope was advanced to the '
                                       'cecum and the examination was completed.\nA 9 mm polyp in the sigmoid '
                                       'colon was removed with a cold snare.\n',
     '45385', None, HELD, ALT),
    # stage READY/READY, base READY/READY, round 1 EXCL/ALT
    ('L5-4:Prior report: / Received by fax. || Colonoscopy Report',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nPrior report:\nReceived by fax.\nColonoscopy '
           'Report\nEndoscopist: Dr. B. Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the '
           'examination was completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage READY/READY, base READY/READY, round 1 HELD/ALT
    ('L5-4:History: see the attached report. || Colonoscopy Report',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nHistory: see the attached report.\nColonoscopy '
           'Report\nEndoscopist: Dr. B. Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the '
           'examination was completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage READY/READY, base READY/READY, round 1 HELD/ALT
    ('L5-4:Previous procedures: colonoscopy, report below. || Colonoscopy Report',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nPrevious procedures: colonoscopy, report below.\nColonoscopy '
           'Report\nEndoscopist: Dr. B. Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the '
           'examination was completed.\nA 9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage EXCL/ALT, base READY/READY, round 1 EXCL/ALT
    ('L5-4:Prior report: || Colonoscopy Report',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nPrior report:\nColonoscopy Report\nEndoscopist: Dr. B. '
           'Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the examination was completed.\nA '
           '9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage READY/READY, base READY/READY, round 1 HELD/ALT
    ('L5-4:Outside report: || Colonoscopy Report',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure: Upper endoscopy\nThe gastroscope was passed to the second portion of the '
           'duodenum. The examination was normal.\nOutside report:\nColonoscopy Report\nEndoscopist: Dr. B. '
           'Synthetic (fictional)\nThe colonoscope was advanced to the cecum and the examination was completed.\nA '
           '9 mm polyp in the sigmoid colon was removed with a cold snare.\n',
     '45385', None, READY, READY),
    # stage READY/ALT, base READY/ALT, round 1 HELD/ALT
    ('L5-6:The food bolus was pushed into the stomach.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe food '
           'bolus was pushed into the stomach.\n',
     '43247', None, READY, ALT),
    # stage READY/READY, base READY/READY, round 1 HELD/ALT
    ('L5-6:The food bolus was passed into the stomach with gentle pressure.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe food '
           'bolus was passed into the stomach with gentle pressure.\n',
     '43247', None, READY, READY),
    # stage READY/READY, base READY/READY, round 1 HELD/ALT
    ('L5-6:The food bolus was advanced into the stomach.',
     SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\nThe food '
           'bolus was advanced into the stomach.\n',
     '43247', None, READY, READY),
    # stage READY/READY, base READY/READY, round 1 HELD/ALT
    ('L5-7:same-under-procedure-heading', SYN + 'Gastroenterology Procedure Report\nDate of service: '
                                                '2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                                                '(fictional)\nSedation: Monitored anesthesia care.\nIndications: '
                                                'Dysphagia and anemia.\nProcedure: Upper endoscopy\nThe '
                                                'gastroscope was advanced into the esophagus and to the second '
                                                'portion of the duodenum.\nFindings: A 9 mm sigmoid colon polyp '
                                                'was removed with a cold snare.\nImpression: Sigmoid polyp '
                                                'removed.\n',
     '43251', 'A 9 mm sigmoid colon polyp was removed with a cold snare.', READY, READY),
]


def check(case, table):
    """Every row of ``table`` reads, on both paths, as pinned."""
    for name, text, which, quote, by_corti, by_participant in table:
        with case.subTest(name):
            quote = quote or text.rstrip('\n').split('\n')[-1]
            case.assertEqual(both(text, which, quote), ([by_corti], [by_participant]))


class L1ReleasingRuleTests(SimpleTestCase):
    """L1 (the releasing rules): each finding's input was a false READY on both paths on the stage commit."""

    def test_l1_1_an_act_inside_the_future_purpose_keeps_its_future(self):
        # F-TIME R is dropped (refutation cycle 2): every purpose's "future" dates its sentence's act as the base reads
        # it, so an act named inside it ("for future localization at the time of EMR") is excluded
        check(self, R1_L1_1)

    def test_l1_2_a_service_inside_the_purpose_stays_planned(self):
        # routing is the base's again (detect.py, gi-routing@7), which reads the purpose's service as planned
        check(self, R1_L1_2)

    def test_l1_3_a_not_after_a_reaching_instrument_denies_its_own_act(self):
        # F-NEG S gives a "not" away only to another act's predicate, never to the instrument's own kind
        check(self, R1_L1_3)

    def test_l1_4_a_request_or_a_counsel_states_no_act_done(self):
        # with F-TIME R dropped the purpose's "future" stands as at the base; under an outside report's heading the
        # tattoo is another source's, and a participant's code for it is held as Corti's is
        check(self, R1_L1_4)


class L2HoldingRuleEscapeTests(SimpleTestCase):
    """L2 (escapes from the holding rules): each finding's input was a false READY on both paths on the stage commit;
    each control shows its rule working on its own words."""

    def test_l2_1_another_facility_or_source_worded_otherwise(self):
        check(self, R1_L2_1)

    def test_l2_2_an_attached_outside_record_under_its_own_heading(self):
        check(self, R1_L2_2)

    def test_l2_3_the_named_agent_surname_check(self):
        check(self, R1_L2_3)

    def test_l2_4_an_earlier_time_or_todays_reference_worded_otherwise(self):
        check(self, R1_L2_4)

    def test_l2_5_a_condition_or_open_question_opened_otherwise(self):
        check(self, R1_L2_5)

    def test_l2_6_an_infinitive_beside_another_acts_finite_predicate(self):
        check(self, R1_L2_6)

    def test_l2_7_the_same_act_stated_aborted_stopped_or_discontinued(self):
        check(self, R1_L2_7)

    def test_l2_8_a_negation_worded_otherwise(self):
        check(self, R1_L2_8)


class L3OverReachTests(SimpleTestCase):
    """L3 (false holds and regressions): each finding's input was held or excluded on the stage commit where the base
    reads it READY, or excluded where the base holds it; each group ends with a control."""

    def test_l3_1_todays_section_after_an_empty_history_field(self):
        # F-SECTIONS T: only a report title, and only on positive evidence that it is another report's
        check(self, R1_L3_1)

    def test_l3_2_a_bare_not_on_another_participle(self):
        check(self, R1_L3_2)

    def test_l3_3_never_before_an_earlier_occasion(self):
        check(self, R1_L3_3)

    def test_l3_4_a_later_clause_denying_a_complication(self):
        check(self, R1_L3_4)

    def test_l3_5_according_to_a_protocol_and_other_sources_that_are_not_the_acts(self):
        check(self, R1_L3_5)

    def test_l3_6_the_reports_own_physician_on_any_physician_line(self):
        check(self, R1_L3_6)

    def test_l3_7_a_past_necessity_or_ability(self):
        check(self, R1_L3_7)

    def test_l3_8_a_purpose_or_a_question_that_is_not_the_acts_condition(self):
        check(self, R1_L3_8)

    def test_l3_9_a_point_inside_todays_procedure(self):
        check(self, R1_L3_9)

    def test_l3_12_a_procedure_lines_listing(self):
        check(self, R1_L3_12)

    def test_l3_11_an_attached_reports_date_never_competes_with_this_reports(self):
        # through the date the pipeline takes (jobs._service_date_of): one date, READY on both paths, as the base reads
        prior = ('Upper endoscopy report (fictional)\nDate of service: 2025-03-01\nProcedure: EGD\n'
                 'The gastroscope was advanced to the second portion of the duodenum. The duodenum was normal.\n')
        cecum = 'The colonoscope was advanced to the cecum'
        for text in (COLON + '\nAttached prior report:\n----------\n' + prior,
                     COLON + '\nAttached prior report:\nSource: scanned record\n' + prior,
                     COLON + '\nAttached prior report:\n' + prior):
            with self.subTest(text.split('\n')[7]):
                facts = gi_context.extract_context(text)
                stored = to_jsonable(facts)
                day = jobs._service_date_of(stored)

                def go(participants, codes, text=text, facts=facts, day=day):
                    return assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                                  normalized=NormalizedResponse('corti', 'test@1', tuple(codes)), reference=REFERENCE,
                                  service_date=day, provider_status='succeeded', participants=tuple(participants))

                self.assertEqual((stored['service_date']['origin'], str(day)), ('document', '2026-10-14'))
                by_corti = go((), corti(('45378', span(text, cecum))))
                by_astra = go([read('astra', [code(text, '45378', cecum)])], [])
                for result in (by_corti, by_astra):
                    self.assertEqual([(p.bucket, p.status) for p in result.proposals if p.code == '45378'], [READY])
                    self.assertEqual([c.status for c in result.encounter_checks if c.id == 'context.service_date'],
                                     ['pass'])


class L5SectionsAndActsTests(SimpleTestCase):
    """L5 (sections and acts): each finding's input was a false READY on the stage commit where the base holds it, does
    not admit it, or excludes it. F-SECTIONS T and L and F-ACTS' round-1 vocabulary are dropped (refutation cycle 2), so
    these read as the base reads them, a participant's code for a doubted act held beside Corti's; the base's own false
    READYs among them are in RecordedResidualTests."""

    def test_l5_1_a_labelled_paragraph_narrating_another_occasion(self):
        check(self, R1_L5_1)

    def test_l5_2_a_procedure_reports_own_title_and_head(self):
        check(self, R1_L5_2)

    def test_l5_3_a_title_aside_is_today_only_on_the_allow_list(self):
        check(self, R1_L5_3)

    def test_l5_4_a_history_section_runs_over_an_attached_reports_title(self):
        check(self, R1_L5_4)

    def test_l5_5_a_medication_contrast_or_secretion_bolus_is_no_foreign_body(self):
        check(self, R1_L5_5)

    def test_l5_6_a_push_or_a_passage_is_no_removal(self):
        check(self, R1_L5_6)

    def test_l5_7_a_labelled_part_takes_no_other_services_findings(self):
        check(self, R1_L5_7)


class RecordedResidualTests(SimpleTestCase):
    """Inputs this tree still reads otherwise than their lens wanted, each with its reason; none is this diff's
    regression against the base on the path named.

    - L1-4a-plain ("India ink tattoo was requested."): READY on Corti's path, on the base too - Corti's own-passage
      release reads the named tattoo; a participant's code is not admitted.
    - L2-1i (another facility in a PRECEDING coordinated clause, "She underwent colonoscopy at the referring facility,
      and a 6 mm polyp ... was removed"): READY on both paths, on the base too; the frame of a coordinated clause is not
      read into the next (the recorded residual of F-TIME P).
    - L3-2#5 ("ligated with bands, the small ones not banded"): held as a conflict - the safe side of a "not" on the
      same act's own participle (base READY).
    - L3-10 (an impaction's or a finding's own time in an event phrase: "impacted before presentation", "lodged since
      yesterday", "noted on yesterday's CT colonography"): held - the reader cannot tell the event's time from the
      removal's (base READY; the safe side, recorded).
    - L5-2 inside a pathology addendum: READY on Corti's path, on the base too; a participant's code is not admitted
      (the stage commit admitted it READY).

    Refutation cycle 2 (each the base's reading again, the rule that had closed it dropped or narrowed; HARNESS.md
    "Harness repair 3, refutation cycle 2", recorded as open):
    - L2-1g (an outside hospital by its proper name alone): READY on both paths, as on the base - F-TIME P names a
      facility by an indefinite article or records from one, never a proper name alone (C2-2-5).
    - L5-3 "(Final)" (a title aside): held, as on the base - F-SECTIONS T is dropped, so the title is an ordinary line
      (a false hold).
    - L5-4 (an attached report's plain title under a history heading): READY on both paths, as on the base - the base's
      own false READY, F-SECTIONS T dropped.
    - L5-6 (a food bolus pushed, passed or advanced into the stomach): READY on Corti's path, as on the base - the
      base's "food bolus" reads as the foreign-body act done; F-ACTS' push guard is dropped with its vocabulary.
    - L5-7 under "Procedure: Upper endoscopy" (an EGD part taking a colon finding): READY on both paths, as on the
      base - F-SECTIONS L dropped."""

    def test_the_residuals_read_as_recorded(self):
        check(self, R1_RESIDUAL)


class AdmissionAndCompetitionTests(SimpleTestCase):
    """L4-1 to L4-4 through the engine, as lens L4's scripts ran them."""

    def outcome(self, result):
        return {p.code: (p.bucket, p.status, [c.fact for c in p.clarifications], (p.support or {}).get('origin'),
                         (p.support or {}).get('competes')) for p in result.proposals}

    def test_l4_1_a_participants_office_visit_reaches_review_whatever_corti_selected(self):
        dos = (SYN + 'Gastroenterology clinic note\nDate of service: 2026-10-14\n'
               'Physician: Synthetic Endoscopist, MD (fictional)\n')
        statement = 'A significant, separately identifiable evaluation and management service was provided.'
        visit = 'Established patient office visit.'
        flex = 'The sigmoidoscope was advanced to 30 cm.'
        mixed = (dos + 'Place of service: 11\n' + visit + '\nChief complaint\nRectal bleeding.\nAssessment\n'
                 'Hemorrhoids versus proctitis.\nMedical decision making\nModerate.\n' + statement + '\n'
                 'Procedure: Flexible sigmoidoscopy\nFindings\n' + flex + '\n')
        result = run(mixed, corti(('45330', span(mixed, flex))),
                     [read('astra', [code(mixed, '99213', visit, statement)])])
        self.assertEqual(self.outcome(result)['99213'], ('selected', 'ready', [], 'participant', None))
        office = (dos + 'Place of service: 11\n' + visit + '\nChief complaint\nRectal bleeding.\nAssessment\n'
                  'Hemorrhoids versus proctitis.\nMedical decision making\nModerate.\nPlan\n'
                  'Colonoscopy to be scheduled.\n')
        result = run(office, corti(('46600', span(office, 'Rectal bleeding.'))),
                     [read('astra', [code(office, '99213', visit)])])
        # beside Corti's held anoscopy the visit reaches review held for its separate-service question, never an
        # alternative with a false "no service of its family is documented" (the stage commit's reason)
        self.assertEqual(self.outcome(result)['99213'], ('selected', 'needs_clarification', ['separate_em'],
                                                         'participant', None))

    def test_l4_2_codes_for_two_different_acts_never_compete(self):
        egd = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
               '(fictional)\nIndications: Dysphagia and early satiety.\nProcedure\n'
               'The gastroscope was passed to the second portion of the duodenum.\n')
        eso = ('A through-the-scope balloon was positioned across the Schatzki ring in the distal esophagus and '
               'inflated to 18 mm under direct visualization.')
        pyl = ('A second through-the-scope balloon was positioned across the pyloric stricture and inflated to 15 mm '
               'under direct visualization.')
        imp = 'Impression: Schatzki ring and pyloric stricture.'
        text = egd + eso + '\n' + pyl + '\n' + imp + '\n'
        result = run(text, corti(('43249', span(text, imp))), [read('astra', [code(text, '43245', pyl)])])
        # refutation cycle 4 (C4-2-3): Corti's 43249 cites an Impression naming both strictures, so its support rests on
        # both dilations and, on the safe side, it competes with the pyloric dilation's code - a recorded false hold
        # (round 1 to cycle 3 read both READY); two codes for one act are never both READY
        self.assertEqual(self.outcome(result), {'43249': ('selected', 'needs_clarification', ['competing_codes'],
                                                          'primary', ['43245']),
                                                '43245': ('selected', 'needs_clarification', ['competing_codes'],
                                                          'participant', ['43249'])})
        # a code for a doubted act holds no code for the act that was done
        egd2 = egd.replace('Indications: Dysphagia and early satiety.\n', '')
        dil = ('A through-the-scope balloon was positioned across the Schatzki ring and inflated to 18 mm under direct '
               'visualization.')
        hedge = 'It is unclear whether the ring was also dilated with a Savary bougie.'
        text = egd2 + dil + '\n' + hedge + '\n'
        result = run(text, corti(('43248', span(text, hedge))), [read('astra', [code(text, '43249', dil)])])
        self.assertEqual(self.outcome(result), {
            '43248': ('selected', 'needs_clarification', ['performed_status'], 'primary', None),
            '43249': ('selected', 'ready', [], 'participant', None)})

    def test_l4_3_two_codes_for_one_act_restated_compete(self):
        egd = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
               '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\n')
        d1 = 'The Schatzki ring in the distal esophagus was dilated with a through-the-scope balloon to 18 mm.'
        d2 = 'Impression: Schatzki ring, dilated with a balloon to 18 mm.'
        text = egd + d1 + '\n' + d2 + '\n'
        held = ['competing_codes']
        for name, participant_codes in (('the restatement', [code(text, '43233', d2)]),
                                        ('beside agreement', [code(text, '43249', d1), code(text, '43233', d2)])):
            with self.subTest(name):
                result = run(text, corti(('43249', span(text, d1))), [read('astra', participant_codes)])
                self.assertEqual(self.outcome(result), {
                    '43249': ('selected', 'needs_clarification', held, 'primary', ['43233']),
                    '43233': ('selected', 'needs_clarification', held, 'participant', ['43249'])})
        b1 = 'Cold forceps biopsies were obtained from the distal esophagus.'
        b2 = 'Biopsies of the esophagus were taken with cold forceps.'
        text = egd + b1 + '\n' + b2 + '\n'
        result = run(text, corti(('43239', span(text, b1))), [read('astra', [code(text, '43202', b2)])])
        self.assertEqual(self.outcome(result), {
            '43239': ('selected', 'needs_clarification', held, 'primary', ['43202']),
            '43202': ('selected', 'needs_clarification', held, 'participant', ['43239'])})

    def test_l4_4_recorded_residual_corti_s_own_passage_reading(self):
        """L4-4, recorded (base same): Corti's selection of the same code with another passage decides that code's
        reading, and Corti's own-passage release - which reads an act the documented-service reader does not - is not
        open to a participant's code. Both stay visible: the first is held for review, the second leaves its service
        unresolved beside the participant's alternative. Never a READY."""
        colon = (SYN + 'Colonoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
                 '(fictional)\nProcedure\nThe colonoscope was advanced to the cecum.\n')
        good = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        bad = 'At the last colonoscopy in 2019 a 12 mm polyp was removed with a hot snare.'
        text = colon + good + '\n' + bad + '\n'
        result = run(text, corti(('45385', span(text, bad))), [read('astra', [code(text, '45385', good)])])
        self.assertEqual(self.outcome(result), {
            '45385': ('selected', 'needs_clarification', ['performed_status'], 'primary', None)})
        egd = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
               '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\n')
        d1 = 'The Schatzki ring in the distal esophagus was dilated to 18 mm.'
        text = egd + d1 + '\n'
        self.assertEqual(self.outcome(run(text, corti(('43249', span(text, d1))), []))['43249'][:2],
                         ('selected', 'ready'))
        result = run(text, corti(), [read('astra', [code(text, '43249', d1)])])
        self.assertEqual(self.outcome(result)['43249'][:2], ('alternative', 'informational'))
        self.assertEqual([(u['family'], u['reason']) for u in result.completeness['unresolved_items']],
                         [('gi.egd', 'no_proposal')])


class CompetitionReleaseTests(SimpleTestCase):
    """L4-5 through the review overlay: a rival that a member's answer to one of its own questions left unavailable is
    no longer in review, so the code left is released from the competition. On the stage commit it stayed held by a
    rival nobody could reject (no action is offered on an unavailable code). An answer to the competing question itself
    never counts."""
    EGD = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\n')  # the extent unstated: each code also carries its own extent question
    DILATION = ('A through-the-scope balloon was positioned across the Schatzki ring and inflated to 18 mm under '
                'direct visualization.')

    def test_a_rival_answered_away_releases_the_competition(self):
        text = self.EGD + self.DILATION + '\n'
        result = run(text, corti(('43248', span(text, self.DILATION))),
                     [read('astra', [code(text, '43249', self.DILATION)])])
        rows = [review_view.stored_from(p) for p in result.proposals]
        keys = {p.code: p.key for p in result.proposals if p.bucket == 'selected'}

        def views(answers=()):
            return review_view.review_view(rows, {}, services=result.services,
                                           reference_sources=result.reference_sources, answers=answers)

        def facts(view):
            return sorted(q.get('fact') for q in view.questions)

        before = views()
        self.assertEqual({code_: facts(before[key]) for code_, key in keys.items()},
                         {'43248': [engine.COMPETING_FACT, 'extent'], '43249': [engine.COMPETING_FACT, 'extent']})
        after = views([{'code': '43248', 'family': 'gi.egd', 'fact': 'extent', 'value': 'not_documented'}])
        self.assertEqual(after[keys['43248']].reason, review_view.DETAIL_UNAVAILABLE)
        kept = after[keys['43249']]
        self.assertEqual((kept.status, facts(kept)), ('needs_clarification', ['extent']))  # its own question stands
        self.assertIn(engine.COMPETING_FACT, kept.released)
        on_the_hold = views([{'code': '43248', 'family': 'gi.egd', 'fact': engine.COMPETING_FACT,
                              'value': 'not_documented'}])
        self.assertEqual(facts(on_the_hold[keys['43249']]), [engine.COMPETING_FACT, 'extent'])


def persist_run(text, codes, participants):
    """A scenario whose assessment is the real engine's for ``text`` (lens L4's DB probes)."""
    s = pf.scenario(text=text)
    facts = {name: to_jsonable(fact) for name, fact in gi_context.extract_context(text).items()}
    ctx = pf.context(s.encounter, s.revision, fact_values=facts)
    result = run(text, codes, participants)
    s.assessment = review.persist_assessment(
        encounter=s.encounter, revision=s.revision, context=ctx, routing_run=pf.routing(s.revision),
        provider_run=pf.provider_run(s.encounter, s.revision), result=result,
        retrieval=retrieval_for(result, [c.code for c in codes]))
    s.encounter.refresh_from_db()
    return s


class CompetitionThroughTheApiTests(TestCase):
    """L4-6 and L4-3 through the customer API: a competing row offers no answer and no addendum - only the reviewer's
    rejection settles it - and refuses an answer as one not offered, never as a clinical detail; each held code says
    what settles its hold; two codes for one act restated never both reach approval."""
    EGD = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
           '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\n')
    DILATION = CompetitionReleaseTests.DILATION

    def client_for(self, user):
        client = Client(enforce_csrf_checks=False)
        client.force_login(user)
        return client

    def payload(self, s):
        response = self.client_for(s.reviewer).get(f'/api/encounters/{s.encounter.pk}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def post(self, s, path, body):
        return self.client_for(s.reviewer).post(path, data=json.dumps(body), content_type='application/json')

    def decide(self, s, which, action):
        proposal = s.encounter.current_assessment.proposals.get(code=which, bucket='selected')
        body = {'proposal_id': str(proposal.pk), 'action': action}
        if action == 'approve':
            body['acknowledgement'] = review.ACKNOWLEDGEMENTS[s.reviewer.actor_kind]
        return self.post(s, f'/api/encounters/{s.encounter.pk}/decisions', body)

    def test_l4_6_the_competing_row_offers_no_answer_and_says_what_settles_it(self):
        text = self.EGD + self.DILATION + '\n'
        s = persist_run(text, corti(('43248', span(text, self.DILATION))),
                        [read('astra', [code(text, '43249', self.DILATION)])])
        doc = self.payload(s)
        rows = [row for row in doc['details_needed'] if row['fact'] == engine.COMPETING_FACT]
        self.assertEqual(sorted(row['affects'] for row in rows), [['43248'], ['43249']])
        self.assertEqual({(tuple(row['allow']), row['addendum_allowed']) for row in rows}, {((), False)})
        for row in doc['codes']:
            with self.subTest(row['code']):
                self.assertEqual((row['status'], row['allowed_actions']), ('needs_detail', ['reject']))
                self.assertIn(customer_api.QUESTION_WORDS[engine.COMPETING_FACT], row['why']['qualifications'])
        for value in ('not_documented', 'cannot_confirm'):
            with self.subTest(value):
                response = self.post(s, f'/api/encounters/{s.encounter.pk}/details',
                                     {'answers': [{'id': rows[0]['id'], 'fact': rows[0]['fact'], 'value': value}]})
                self.assertEqual((response.status_code, response.json()['error']), (400, answers.NOT_OFFERED))
        # the real door (refutation cycle 2, C2-4-4: the pin had posted to a route that does not exist, so its 404 came
        # from URL resolution and no view ran): the details row's id is the clarification it answers
        response = self.post(s, f'/api/encounters/{s.encounter.pk}/addenda',
                             {'text': 'The dilation was with a balloon.', 'clarification_id': rows[0]['id'],
                              'synthetic_attestation': 'yes'})
        self.assertEqual((response.status_code, response.json()['error']),
                         (404, 'That detail is not open on this document.'))
        self.assertFalse(models.MemberAnswer.objects.exists())
        # the reviewer's rejection settles it: the code left is ready, approvable, and alone in the approved export
        self.assertEqual(self.decide(s, '43248', 'reject').status_code, 201)
        left = {row['code']: row for row in self.payload(s)['codes']}['43249']
        self.assertIn('approve', left['allowed_actions'])
        self.assertEqual(self.decide(s, '43249', 'approve').status_code, 201)
        made = self.post(s, f'/api/encounters/{s.encounter.pk}/reports', {'kind': 'approved', 'fmt': 'txt'})
        self.assertEqual(made.status_code, 201, made.content)
        body = self.client_for(s.reviewer).get(made.json()['download_url']).content.decode('utf-8')
        self.assertIn('43249', body)
        self.assertNotIn('43248', body)

    def test_l4_6_positive_control_an_open_confirmation_row_takes_an_addendum(self):
        # the same door takes one from a row that offers it (the extent, unstated here), so the refusal above is the
        # view's own, never the route's
        egd = (SYN + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
               '(fictional)\nProcedure\n')
        text = egd + self.DILATION + '\n'
        s = persist_run(text, corti(('43249', span(text, self.DILATION))), [])
        row = next(r for r in self.payload(s)['details_needed'] if r['fact'] == 'extent')
        self.assertTrue(row['addendum_allowed'])
        response = self.post(s, f'/api/encounters/{s.encounter.pk}/addenda',
                             {'text': 'The gastroscope was passed to the second portion of the duodenum.',
                              'clarification_id': row['id'], 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)

    def test_l4_3_one_act_restated_never_reaches_approval_twice(self):
        d1 = 'The Schatzki ring in the distal esophagus was dilated with a through-the-scope balloon to 18 mm.'
        d2 = 'Impression: Schatzki ring, dilated with a balloon to 18 mm.'
        text = self.EGD + d1 + '\n' + d2 + '\n'
        s = persist_run(text, corti(('43249', span(text, d1))), [read('astra', [code(text, '43233', d2)])])
        rows = {row['code']: row for row in self.payload(s)['codes']}
        self.assertEqual({c: (row['status'], row['allowed_actions']) for c, row in rows.items()},
                         {'43249': ('needs_detail', ['reject']), '43233': ('needs_detail', ['reject'])})
        for which in ('43249', '43233'):
            with self.subTest(which):
                self.assertNotEqual(self.decide(s, which, 'approve').status_code, 201)
        self.assertFalse(models.Decision.objects.filter(action='approve').exists())


class StopResumeBase(h2p.Harness2Case):
    """Lens L6's probes, as F-STOP's claims: a Stop is recoverable, nothing is sent twice or blindly, no participant
    is lost, and a continuation's lineage is kept."""

    def stop_during(self, encounter_id, step):
        def stopped_then(body):
            jobs.stop_encounter(self.encounter(encounter_id), self.reviewer)  # the member's Stop lands mid-loop
            return step
        return stopped_then

    def stop_mid_loop(self, encounter_id, name, call_id, reading):
        self.adapters[name].first = [self.stop_during(encounter_id, h2p.asks(name, h2p.facts_call(call_id, ['99213']))),
                                     h2p.answered(name, reading)]
        h2p.drain()
        (stopped,) = self.runs_of(encounter_id, name, 'independent')
        self.assertEqual((stopped.state, stopped.sent, stopped.scope.get('stopped_after_turn')), ('failed', True, 1))
        return stopped

    def continuations(self, encounter_id, name, stopped):
        return [r for r in self.runs_of(encounter_id, name, 'independent')
                if (r.scope or {}).get('continues') == str(stopped.pk)]


class StopRecoveryTests(StopResumeBase):
    def test_l6_1_a_hold_recorded_after_a_mid_loop_stop_never_hides_the_stopped_run(self):
        encounter_id = self.create(text=NO_DATE_NOTE)
        stopped = self.stop_mid_loop(encounter_id, 'astra', 'call_astra_1', h2p.ASTRA_READING)
        # a member's date makes Corti's request new, its outcome is unknown, and Astra's stage records the hold (a
        # not-sent run of the same request); the member then reconciles Corti's outcome and the chain runs again
        self.corti.outcomes = ['unknown']
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'service_date': FIRST_DATE}).status_code,
                         201)
        h2p.drain()
        unknown = [r for r in self.runs_of(encounter_id, 'corti') if r.state == 'unknown'][-1]
        self.assertEqual(self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                                   {'provider_run_id': str(unknown.pk), 'note': RECONCILE_NOTE}).status_code, 201)
        h2p.drain()
        (continued,) = self.continuations(encounter_id, 'astra', stopped)
        self.assertEqual((continued.state, continued.sent), ('succeeded', True))
        self.assertEqual(self.records(self.encounter(encounter_id).current_assessment)['astra']['state'], 'read')

    def test_l6_2_a_metadata_save_continues_the_last_participants_stopped_loop(self):
        encounter_id = self.create()
        stopped = self.stop_mid_loop(encounter_id, 'fable', 'toolu_fable_1', h2p.FABLE_READING)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        h2p.drain()
        (continued,) = self.continuations(encounter_id, 'fable', stopped)
        self.assertEqual((continued.state, continued.sent), ('succeeded', True))
        self.assertEqual(self.records(self.encounter(encounter_id).current_assessment)['fable']['state'], 'read')

    def test_l6_2_control_a_stop_before_the_send(self):
        encounter_id = self.create()
        job = self.run_until('fable')
        jobs.stop_encounter(self.encounter(encounter_id), self.reviewer)
        jobs.run_job(job)
        h2p.drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        h2p.drain()
        self.assertEqual(self.records(self.encounter(encounter_id).current_assessment)['fable']['state'], 'read')


class SingleProposerStopRecoveryTests(StopResumeBase):
    """L6-1 where Astra is the only proposer (Corti selects nothing): its explicit first-reading code reaches review
    after the hold and the reconciliation, as after a plain Resume."""
    corti_codes = ()

    def test_the_only_proposers_code_reaches_review(self):
        encounter_id = self.create(text=NO_DATE_NOTE)
        self.adapters['fable'].first = [h2p.answered('fable', h2p.reading())]  # Fable proposes nothing
        self.stop_mid_loop(encounter_id, 'astra', 'call_astra_1', h2p.ASTRA_READING)
        self.corti.outcomes = ['unknown']
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'service_date': FIRST_DATE}).status_code,
                         201)
        h2p.drain()
        unknown = [r for r in self.runs_of(encounter_id, 'corti') if r.state == 'unknown'][-1]
        self.assertEqual(self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                                   {'provider_run_id': str(unknown.pk), 'note': RECONCILE_NOTE}).status_code, 201)
        h2p.drain()
        assessment = self.encounter(encounter_id).current_assessment
        found = [(p.bucket, (p.support or {}).get('proposed_by')) for p in assessment.proposals.filter(code='99213')]
        self.assertEqual(found, [('selected', ['astra'])])


class ContinuationLineageTests(StopResumeBase):
    def resumed(self):
        encounter_id = self.create()
        stopped = self.stop_mid_loop(encounter_id, 'astra', 'call_astra_1', h2p.ASTRA_READING)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        h2p.drain()
        first, later = self.runs_of(encounter_id, 'astra', 'independent')
        self.assertEqual((first, (later.scope or {}).get('continues')), (stopped, str(stopped.pk)))
        return encounter_id, stopped, later

    def test_l6_3_a_continuations_references_cover_its_chain(self):
        encounter_id, stopped, later = self.resumed()
        refs = review.participant_references(later)
        used = {item['ref'] for item in refs['used'] if item['retrieved']}
        self.assertTrue(used)
        self.assertLessEqual(used, {item['ref'] for item in refs['retrieved']})
        self.assertEqual([c.exchange.run_id for c in review.run_tool_calls(later)][:1], [stopped.pk])
        encounter = self.encounter(encounter_id)
        current = list(encounter.jobs.filter(revision=encounter.current_revision).order_by('created_at'))
        api = {row['name']: row for row in serializers.harness_json(encounter, current)['participants']}['astra']
        used = {item['ref'] for item in api['references']['used'] if item['retrieved']}
        self.assertLessEqual(used, {item['ref'] for item in api['references']['retrieved']})

    def test_l6_3_the_report_counts_the_chains_usage_and_cost(self):
        encounter_id, stopped, later = self.resumed()
        assessment = self.encounter(encounter_id).current_assessment
        (entry,) = [e for e in reports._participants(assessment) if e['name'] == 'astra']
        self.assertEqual((entry['run'], entry['continues']), (str(later.pk), [str(stopped.pk)]))
        self.assertEqual(entry['usage'], summed_usage([stopped.usage, later.usage]))
        costs = [review.estimated_cost(each) for each in (stopped, later)]
        self.assertTrue(all(cost is not None for cost in costs))
        self.assertEqual(Decimal(entry['estimated_cost_usd']), sum(Decimal(cost) for cost in costs))

    def test_l6_4_a_carried_answer_that_no_longer_matches_its_record_is_never_sent_on(self):
        encounter_id = self.create()
        stopped = self.stop_mid_loop(encounter_id, 'astra', 'call_astra_1', h2p.ASTRA_READING)
        (exchange,) = stopped.exchanges.all()
        original = bytes(exchange.response_bytes)
        self.assertEqual(hashlib.sha256(original).hexdigest(), exchange.response_sha256)
        models.ProviderExchange.objects.filter(pk=exchange.pk).update(response_bytes=original.replace(b'99213',
                                                                                                      b'99214'))
        loops = len(self.adapters['astra'].loops_of('first'))
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        h2p.drain()
        later = self.runs_of(encounter_id, 'astra', 'independent')[-1]
        self.assertNotEqual(later, stopped)
        self.assertFalse(later.sent)
        self.assertIn('no longer matches its record', later.error)
        self.assertFalse(any('99214' in json.dumps(body) for loop_ in self.adapters['astra'].loops_of('first')[loops:]
                             for body in loop_['bodies']))
