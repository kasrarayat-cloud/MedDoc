"""contract/segment.py: the units of design v2 (docs/gemini-migration/FINAL-V2.md 1.2, revised for CO-3, CO-4 and CO-5;
step 1a of 8.1). TEXT-ONLY and SYNTHETIC: no network, no provider, no document of the acceptance set.

What is proved here, item by item against the done-when of 8.1 step 1a and 9.3's segment row:
- boundaries on fixtures: initials and short titles, hard wraps joined and not joined, pages, forced splits, list
  enumerators (UnitRuleTests), and a differential check against an independent oracle of 1.2 written here with
  regular expressions and str methods, over random texts and random pages (OracleTests);
- rule 3's letters are what str.isalpha accepts and its uppercase letters what str.isupper accepts (DECISIONS D205):
  "of O\u2082. The scope" ends a unit, as a fraction, a Roman-numeral character, a caseless or a titlecase letter does
  (UnitRuleTests, PinTests, and OracleTests, whose random alphabet holds each and which compares every short-token
  shape over them);
- GI Note #8's three wrapped denials and its extent sentence each one unit, and its 181 units as 1.2 measured;
  PAIR-4-W2's "At / this examination" and "endoscopic mucosal / resection" each inside one unit (FixtureTests).
  Both are development documents of FRESH-1 (fresh/inputs/A/note8.txt, fresh/inputs/C/PAIR-4-W2.txt), embedded
  byte for byte (a test asserts each sha256); neither hashes, as written or stripped, to any line of the
  acceptance set's DEV-EXCLUSION.sha256;
- closures of at most 12 units, extended as rule 6 says (ClosureTests);
- the [S\\d+] refusal, scanned by characters and equal to the pattern on every code point (FramingTests);
- every unit's offsets reproduce its revision slice, and the framed text writes each unit as that slice with its joined
  wraps as one space (OracleTests, FramingTests);
- the framed text is a pure function of the text: byte-identical across calls, page orders and fresh interpreters with
  different hash seeds; the module keeps no state; its direct imports are the standard library's and contract types',
  and a fresh interpreter importing it loads no retired module, nothing of studio.gi and nothing outside the contract
  package and the standard library (FramingTests, GuardTests);
- the pinned constants describe the predicates exactly, and the module's code is pinned by a normalized-AST sha256,
  which sees a rule change the constants miss (PinTests, DECISIONS D202); 5.7 measure 4 (SingleCharacterGeometry,
  NoWordLists) holds over the module with the forms D205 admits, each rule refusing a planted control (GuardTests).
"""
from __future__ import annotations

import __future__
import ast
import dataclasses
import hashlib
import itertools
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio import interpretation
from studio.interpretation.contract import jsonschema, segment
from studio.interpretation.contract.types import Unit
from studio.types import PageSpan

APP = Path(__file__).resolve().parents[2]
SEGMENT = APP / 'studio' / 'interpretation' / 'contract' / 'segment.py'
CLOSERS = '"\'\u201d\u2019)]}\u00bb'


def texts(text: str, units) -> list:
    return [text[unit.start:unit.end] for unit in units]


def covering(units, text: str, needle: str) -> list:
    """The units a needle's characters fall in, the needle located with any whitespace run matching any whitespace
    run (a hard wrap in the document is a line break, in the needle a space)."""
    pattern = r'\s+'.join(re.escape(part) for part in needle.split())
    match = re.search(pattern, text)
    assert match is not None, needle
    return [unit for unit in units if unit.end > match.start() and unit.start < match.end()]


def tiled(text: str, cuts) -> tuple:
    """Pages tiling ``text`` at the sorted offsets ``cuts`` (a repeated cut makes an empty page)."""
    bounds = [0, *sorted(cuts), len(text)]
    return tuple(PageSpan(page=index + 1, start=bounds[index], end=bounds[index + 1])
                 for index in range(len(bounds) - 1))


# --- the fixtures -----------------------------------------------------------------------------------------------------

# GI Note #8 (FRESH-1 set A, fresh/inputs/A/note8.txt): synthetic, 19,398 characters, the live maximum of 1.8.
NOTE8_SHA256 = '25ef61e4bf743b70a99fea032a83a429bc6e954c89564ff4b53aaddf9ef00a85'
NOTE8 = """\
GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 1
DIVISION OF GASTROENTEROLOGY AND HEPATOLOGY / ADVANCED ENDOSCOPY
COLONOSCOPY AND THERAPEUTIC IBD ENDOSCOPY REPORT
Patient: Elena Brooks, 52-year-old woman
Date of service: November 8, 2026 | Procedure location: Advanced Endoscopy Unit
Endoscopist: E. Morgan, MD | Referring physician: R. Chen, MD
Procedure: High-definition ileocolonoscopy with therapeutic intervention and dysplasia surveillance
Reason for referral: Symptomatic ileocolonic anastomotic narrowing in established Crohn disease; surveillance for
colonic dysplasia; evaluation of iron-deficiency anemia
Clinical indication and interval history
The patient has longstanding ileocolonic Crohn disease diagnosed in 2005 and underwent a laparoscopic ileocecal
resection with a stapled side-to-side ileocolonic anastomosis in 2017 for medically refractory fibrostenotic disease.
She is currently maintained on vedolizumab infusions every eight weeks. Over the preceding four months, she has
developed intermittent postprandial cramping, bloating, and transient nausea, particularly after high-residue meals,
without sustained vomiting or inability to pass flatus. She reports two to three nonbloody stools per day. Her recent
hemoglobin was 10.6 g/dL with ferritin 12 ng/mL despite oral iron; fecal calprotectin was mildly elevated. There is
no current fever, overt gastrointestinal hemorrhage, or unintentional rapid weight loss.
MR enterography performed September 21, 2026 demonstrated a short, fixed narrowing at the ileocolonic
anastomosis with modest upstream neo-terminal ileal caliber change and without an abscess, fistula, phlegmon, or
high-grade obstruction. The narrowing was estimated at approximately 1 cm in length. The multidisciplinary IBD
service considered a trial of endoscopic balloon dilation reasonable, provided the endoscopic appearance showed no
deep ulceration or suspicion for malignancy. The examination was also requested for dysplasia surveillance given the
duration of colonic involvement and a remote history of an inflammatory polyp.
Pertinent records reviewed before the examination
A colonoscopy from January 2024 described a patent but narrowed ileocolonic anastomosis, mild neo-terminal ileal
ulceration, and a 4 mm rectal hyperplastic polyp that was removed at that earlier encounter. No dilation was carried
out in 2024. An outside upper endoscopy performed in March 2023 documented a Schatzki ring treated with
balloon dilation and gastric biopsies at that time. Those upper gastrointestinal interventions are historical only; no
esophagogastroduodenoscopy or other upper endoscopic procedure was performed on November 8, 2026.
Available prior pathology did not document dysplasia. The present report records only the lower gastrointestinal
examination and interventions performed today.
Preprocedure evaluation and consent
Medical history includes Crohn disease, prior ileocecal resection, iron-deficiency anemia, controlled hypertension,
and mild osteopenia. Prior abdominal surgery is limited to the bowel resection and an uncomplicated laparoscopic
cholecystectomy. Her medications include vedolizumab, lisinopril, ferrous gluconate, vitamin D, and as-needed
acetaminophen. She is not taking warfarin, a direct oral anticoagulant, aspirin, or a P2Y12 inhibitor. No known allergy
to latex or standard endoscopic sedation agents was reported. She denied any recent cardiopulmonary symptoms.
Airway and anesthetic assessment were completed by the anesthesia service; the patient was classified as ASA II.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 2
Risks, benefits, and alternatives were discussed in detail, including the particular risks of perforation or delayed
bleeding following dilation of a Crohn-related narrowing, bleeding after mucosal resection, incomplete excision or
recurrence of large colorectal lesions, missed dysplasia, aspiration, and cardiopulmonary events related to sedation.
The possibility that a lesion encountered today might require referral rather than immediate resection was reviewed.
Written informed consent was obtained. A formal time-out was completed immediately before insertion, verifying
patient identity, intended lower endoscopic procedure, planned potential dilation and resection, and consent.
Anesthesia, equipment, and quality measures
Monitored anesthesia care with propofol was administered and supervised by the anesthesia team, with continuous
electrocardiographic, oxygen saturation, blood-pressure, and ventilation monitoring. The endoscopist did not
administer or bill for a separate physician-directed moderate sedation service. A high-definition pediatric
colonoscope with water-jet capability was used, along with narrow-band imaging for lesion characterization, a
through-the-scope wire-guided dilation balloon, an electrosurgical snare, cold biopsy forceps, and a submucosal
injection catheter as indicated. No fluoroscopy was used.
Bowel preparation was adequate after washing and suctioning, with a Boston Bowel Preparation Scale score of 2 in
the proximal remnant colon, 3 in the transverse colon, and 3 in the left colon, total 8. Because of the prior ileocecal
resection, the native cecum and ileocecal valve are surgically absent; completion of the examination was confirmed
by direct identification and photodocumentation of the ileocolonic anastomosis and subsequent intubation of the
neo-terminal ileum after dilation. Photographs were obtained of the anastomosis before and after therapy, the ileal
mucosa, each lesion before and after intervention, and the location of the tattoo in relation to the unresected lesion.
Procedure technique and chronological findings
The patient was positioned in the left lateral decubitus position. Digital rectal examination showed normal sphincter
tone, no palpable mass, and no gross blood. The colonoscope was introduced through the anus and advanced
carefully under direct vision through the rectum, sigmoid, descending and transverse colon to the right-sided
ileocolonic anastomosis. Carbon-dioxide insufflation and water exchange were used to limit distention. Luminal
anatomy was consistent with prior ileocecal resection. The mucosa was inspected on insertion where necessary, and
a deliberate, segment-by-segment assessment was performed during withdrawal, with additional inspection of
visually abnormal areas using high-definition white-light imaging and narrow-band imaging.
Ileocolonic anastomosis and balloon dilation
At the right-sided ileocolonic anastomosis there was a single, short, concentric benign-appearing stenosis measuring
approximately 8-9 mm in luminal diameter and 9 mm in longitudinal extent. The anastomotic rim contained two
superficial erosions without deep excavation, mass effect, heaped edges, or active bleeding. The pediatric
colonoscope could not pass the narrowing initially with gentle pressure. The mucosal appearance was reviewed
carefully and no endoscopic feature suggested a malignant stricture. Two cold-forceps mucosal biopsies were taken
from an inflamed portion of the anastomotic rim and placed in a dedicated container.
A guidewire was passed under direct endoscopic vision through the stenosis into the neo-terminal ileum. A
through-the-scope controlled radial expansion balloon was advanced over the wire and centered across the
anastomotic narrowing. The balloon was inflated sequentially to 12 mm for 60 seconds, 13.5 mm for 60 seconds,
and 15 mm for 45 seconds, with complete deflation and inspection between stages. A superficial mucosal split was
observed at the final diameter, an expected dilation effect; there was no deep mural injury, transmural defect, or
significant hemorrhage. The balloon and guidewire were removed, and the colonoscope then traversed the treated
narrowing without resistance. The passage and patency of the dilated anastomosis were photographed. No colonic
stent was placed.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 3
Neo-terminal ileum and segmental mucosal sampling
The neo-terminal ileum was examined for approximately 15 cm beyond the anastomosis. Within its distal 8 cm there
were six discrete, 2- to 3-mm aphthous erosions with narrow erythematous halos, separated by intervening
normal-appearing villous mucosa. There was no deeper ulcer, spontaneous bleeding, or additional ileal narrowing.
Four targeted cold-forceps biopsies were obtained from representative inflamed ileal mucosa, away from the
dilation site. The proximal neo-terminal ileum was unremarkable. The postoperative appearance was consistent with
mild endoscopic recurrence of Crohn disease, corresponding descriptively to a modified Rutgeerts i2b pattern,
pending clinical correlation and histology.
During withdrawal, the colonic mucosa was examined with dye-free electronic chromoendoscopy. There were
isolated areas of mild loss of vascular pattern in the transverse colon and left colon, but no extensive confluent
ulceration or deep inflammatory lesions. Targeted cold-forceps biopsies were obtained from an erythematous patch
in the proximal transverse colon and, separately, from mildly granular rectosigmoid mucosa. These samples were
collected for assessment of inflammatory activity and dysplasia surveillance; they were not taken from any
subsequently resected polyp or the unresected suspicious lesion described below. The mucosal samples were placed
in separately designated pathology containers by location.
Distal transverse colon: endoscopic mucosal resection
In the distal transverse colon, approximately 58 cm from the anal verge, a 23 mm laterally spreading granular-type
lesion was identified on a fold, with a homogeneous regular surface and no ulceration, spontaneous bleeding, or
focal depression. High-definition and narrow-band imaging showed a pattern consistent with a superficial
noninvasive adenomatous or serrated lesion. A submucosal injection of approximately 7 mL of saline with dilute
methylene blue was placed directly beneath this distal transverse-colon lesion, resulting in a uniform, satisfactory
lift. The lift was performed solely to facilitate endoscopic mucosal resection of this lesion.
The lesion was resected using a 15 mm electrocautery snare in two overlapping pieces, encompassing all visible
neoplastic tissue. The two fragments were retrieved using a net and submitted together in one specimen container.
Careful inspection under white light and narrow-band imaging showed no visible residual polyp at the resection bed.
Minor oozing from the cut mucosal edge resolved with brief contact coagulation using the snare tip. The perimeter
of the resection defect was treated with low-power snare-tip soft coagulation as an adjunct to the same mucosal
resection, not as treatment of a separate lesion. Two through-the-scope clips were placed across the defect for
prophylactic closure; the clips were not used to treat a separate active bleeding source. No immediate bleeding or
deep mural injury was observed.
Splenic flexure: unresected lesion and localization tattoo
At the splenic flexure, approximately 48 cm from the anal verge, a separate 17 mm non-granular flat lesion with a
subtle centrally depressed area and focally distorted vascular pattern was identified. The surface appearance raised
concern for superficial submucosal invasion. In view of this morphology and the anticipated need for expert en bloc
assessment, this lesion was left in situ. No biopsy, snare resection, ablation, or balloon dilation was performed on
this splenic-flexure lesion during the present encounter.
For future localization, a sterile carbon-particle tattoo was placed in normal mucosa approximately 4 cm distal
(toward the anus) to the splenic-flexure lesion, on the opposite wall, using two separate submucosal injections of
approximately 0.6 mL each. The tattoo formed two visible submucosal blebs, and its relationship to the unresected
lesion was photographed. This tattoo was anatomically and procedurally distinct from the saline/methylene-blue lift
used for the mucosal resection in the distal transverse colon. No carbon-particle tattoo was placed into the
transverse-colon resection bed.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 4
Descending colon: separate cold-snare polypectomy
A separate 9 mm sessile polyp with a smooth surface was present in the mid-descending colon, approximately 35 cm
from the anal verge. The polyp was captured at its base with a cold snare and removed completely in one piece
without electrocautery. The specimen was retrieved and placed in its own pathology container. The post-resection
site was clean, without residual polyp tissue, significant bleeding, or a visible deep defect. Neither the dilation
balloon nor the EMR electrosurgical snare was used to treat this polyp. No clip or cautery was required at this site.
Remaining colon, rectum, and retroflexion
A few small-mouthed diverticula were seen in the sigmoid colon without associated inflammation or bleeding. One
flat 4 mm, nonbleeding vascular ectasia in the proximal rectum was photographed but not treated; there was no
oozing, adherent clot, or visible bleeding vessel. There were no additional polyps requiring removal. Retroflexion in
the rectum disclosed small, nonbleeding internal hemorrhoids and otherwise normal distal rectal anatomy. No
hemostatic cautery, hemostatic clipping, injection for bleeding, or band ligation was performed in the rectum. The
scope was withdrawn after a final inspection, and the patient tolerated the examination well.
Specimens submitted
Specimen A: neo-terminal ileum, targeted cold-forceps biopsies from aphthous erosions. Specimen B: inflamed
mucosa at the ileocolonic anastomotic rim, cold-forceps biopsies. Specimen C: proximal transverse-colon mucosa,
targeted cold-forceps biopsies for activity and dysplasia evaluation. Specimen D: distal transverse-colon lesion, two
fragments from the single endoscopic mucosal resection. Specimen E: descending-colon polyp, cold-snare removal
en bloc. Specimen F: rectosigmoid mucosa, targeted cold-forceps biopsies. No tissue was taken from the unresected
splenic-flexure lesion. Histopathology was pending at the time this report was finalized.
Technical outcome and immediate complications
The anastomotic narrowing was successfully dilated to 15 mm and subsequently traversed. The 23 mm distal
transverse-colon lesion was removed by piecemeal mucosal resection, and the separate 9 mm descending-colon
polyp was removed completely by cold snare. Both specimens were retrieved. Directed carbon-particle tattooing
successfully marked the distinct, unresected splenic-flexure lesion. There was no sustained intraprocedural bleeding,
endoscopically evident perforation, aspiration, anesthesia-related instability, or other immediate adverse event.
Estimated blood loss was minimal. A procedure time of 84 minutes reflected the detailed surveillance examination
and multiple therapeutic interventions; the patient was transferred to monitored recovery awake and
hemodynamically stable.
Postprocedure impression
1. Short fibrotic-appearing ileocolonic anastomotic stricture in a patient with postoperative Crohn disease,
successfully treated with wire-guided through-the-scope balloon dilation to 15 mm, with successful subsequent
intubation of the neo-terminal ileum.
2. Mild recurrent neo-terminal ileitis with scattered aphthous erosions and mild patchy colonic erythema, sampled by
targeted mucosal biopsy at sites separate from the therapeutic polypectomy and mucosal-resection lesions.
3. Distal transverse-colon 23 mm granular laterally spreading lesion, treated with saline-assisted piecemeal
endoscopic mucosal resection and prophylactic defect closure.
4. Distinct 17 mm non-granular splenic-flexure lesion with depressed morphology, intentionally not biopsied or
removed; carbon-particle tattoo placed distal and opposite the lesion for accurate future localization.


GASTROENTEROLOGY  /  PROCEDURE REPORT
NOV 08, 2026  |  ELENA BROOKS
Advanced Endoscopy Unit   •   Endoscopist: E. Morgan, MD
Page 5
5. Mid-descending-colon 9 mm sessile polyp, completely removed by cold-snare technique. Nonbleeding rectal
vascular ectasia, mild sigmoid diverticulosis, and small internal hemorrhoids were incidental findings and required no
therapy.
Recovery instructions and management plan
The patient may begin clear liquids after recovery and advance to a low-residue diet as tolerated for the next 48
hours, with particular attention to post-dilation discomfort, progressive abdominal distention, or persistent pain. She
was instructed to avoid nonsteroidal anti-inflammatory drugs unless specifically directed by her prescribing
physician. Written instructions reviewed signs requiring urgent evaluation, including sustained severe abdominal
pain, fever, hematochezia, melena, persistent vomiting, syncope, or inability to pass gas. Standard post-anesthesia
supervision and driving restrictions were discussed with the patient and accompanying adult.
Histology from all submitted specimens will be reviewed when available and incorporated into the IBD management
plan. The IBD team will reassess symptoms after dilation and discuss ongoing biologic treatment using pathology,
prior imaging, biomarkers, and clinical response; endoscopic dilation does not by itself establish resolution of active
inflammation. The 23 mm transverse-colon resection site will require surveillance to evaluate for residual or
recurrent tissue, with exact timing determined by histology and the multidisciplinary plan. The suspicious
splenic-flexure lesion will be reviewed by advanced endoscopy and colorectal surgery for consideration of en bloc
resection or other management after expert optical assessment; tattoo photographs and precise location will
accompany the referral.
The patient and her family were informed that the unresected splenic-flexure lesion requires timely further
evaluation and that no diagnosis of invasive cancer can be made from optical appearance alone. A future
intervention for that lesion is planned but was not performed at this encounter. The untreated rectal vascular
ectasia will be observed unless bleeding or another indication for therapy develops. The plan and immediate findings
were reviewed verbally before discharge, and a copy of the endoscopy report was forwarded to the referring IBD
clinician.
Attestation
I personally performed the lower gastrointestinal examination, reviewed the video and image documentation, and
carried out the tissue sampling, balloon dilation, mucosal resection, cold-snare polypectomy, and separate
localization tattooing described above. The procedures and outcomes recorded in the findings sections occurred
during the single date of service stated at the top of this report. Prior endoscopic procedures mentioned in the
history and possible future interventions described in the plan are not part of the services performed today.
E. Morgan, MD | Advanced Endoscopy and Inflammatory Bowel Disease
Electronically authenticated: November 8, 2026, 2:36 PM
"""

# PAIR-4-W2 (FRESH-1 set C, fresh/inputs/C/PAIR-4-W2.txt): synthetic, 898 characters.
PAIR4_SHA256 = 'c319dd358c93fef4c34802071282fa8f4c85149bc074b21e309de8c8b8a954d1'
PAIR4 = """\
SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
GASTROENTEROLOGY ASSOCIATES (FICTIONAL)  |  PROCEDURE REPORT
Page 1 of 1

COLONOSCOPY WITH ENDOSCOPIC MUCOSAL RESECTION
Patient: Synthetic Patient (fictional), 58-year-old man
Date of service: November 9, 2026
Endoscopist: A. Current, MD (fictional)
Sedation: Monitored anesthesia care by the anesthesia team

Indication: Referred for resection of an 18 mm sigmoid lesion.

Procedure
The colonoscope reached the cecum. Dr. B. Prior (fictional) placed a tattoo 3
cm distal to the sigmoid lesion at the referring hospital in October 2026. At
this examination I resected the 18 mm sigmoid lesion by endoscopic mucosal
resection after a saline lift; the earlier tattoo was seen distal to the
resection site.

Impression
18 mm sigmoid lesion removed by EMR; prior tattoo identified.

Electronically signed by A. Current, MD (fictional)
"""

# FINAL-V2 1.9's worked example, one unit per line as 1.9 shows it.
WORKED = """\
COLONOSCOPY REPORT
Date of service: 11/09/2026
Endoscopist: Anselm Wrenfield, MD (fictional)
History: Prior colonoscopy in 2023 with removal of two adenomas.
Findings: The colonoscope was advanced to the cecum.
A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.
Neither biopsy nor tattoo was performed.
Documented by Jo Rowe, RN: A 4 mm polyp in the rectum at approx.
5 cm was biopsied with cold forceps.
"""


# --- the rule, case by case -------------------------------------------------------------------------------------------


class UnitRuleTests(SimpleTestCase):
    def test_lines_paragraphs_and_numbering(self):
        text = 'Title line\n\n   \nFirst sentence. Second sentence.\nThird line\n\n\nLast.'
        got = segment.units(text)
        self.assertEqual(texts(text, got), ['Title line', 'First sentence.', 'Second sentence.', 'Third line', 'Last.'])
        self.assertEqual([unit.id for unit in got], ['S1', 'S2', 'S3', 'S4', 'S5'])
        self.assertEqual([unit.line for unit in got], [1, 4, 4, 5, 8])
        self.assertEqual([unit.paragraph for unit in got], [1, 2, 2, 2, 3])  # blank and whitespace-only lines break
        self.assertEqual({unit.page for unit in got}, {1})
        self.assertFalse(any(unit.forced for unit in got))
        self.assertTrue(all(isinstance(unit, Unit) for unit in got))
        self.assertEqual(segment.units(''), ())
        self.assertEqual(segment.units(' \n\t\n'), ())

    def test_a_hard_wrap_is_joined(self):
        cases = {
            'Neither biopsy nor\ntattoo was performed.': 'a lowercase continuation after an open line',
            'No colonic\nstent was placed.': "Note #8's shape",
            'The polyp was\n    removed with a snare.': 'indentation before the lowercase letter',
            'The scope reached the\nterminal ileum and\nthe cecum.': 'two wraps in a row',
            'Biopsies (cold\nforceps) were taken.': 'an open bracket',
            'Seen "on\nwithdrawal" only.': 'an open quote',
            'Pathology,\npending.': 'a comma',
            'It measured 8-\n9 mm, then\nremoved.': 'a digit never continues, a lowercase letter does',
        }
        for text, why in cases.items():
            with self.subTest(why=why):
                got = segment.units(text)
                if why.startswith('a digit'):
                    self.assertEqual(texts(text, got), ['It measured 8-', '9 mm, then\nremoved.'])
                else:
                    self.assertEqual(texts(text, got), [text.strip()])

    def test_a_line_break_that_is_not_a_hard_wrap_ends_the_unit(self):
        cases = {
            'The polyp was removed.\nnext the scope was withdrawn.': 'the earlier line ends in a period',
            'Was it removed?\nyes, by snare.': 'a question mark',
            'Removed!\nthen clipped.': 'an exclamation mark',
            'Findings:\nthe cecum was reached.': 'a colon',
            'He said "done."\nthen left.': 'a closing quote after the period',
            '(Biopsies taken.)\nthen the scope.': 'a closing bracket after the period',
            'Findings were\nNormal throughout.': 'an uppercase continuation',
            'Biopsies of the\n2 sites.': 'a digit continuation',
            'Biopsies of the\n(sigmoid) colon.': 'a punctuation continuation',
            'No colonic\n\nstent was placed.': 'a blank line between',
            'No colonic\n  \nstent was placed.': 'a whitespace-only line between',
        }
        for text, why in cases.items():
            with self.subTest(why=why):
                self.assertEqual(len(segment.units(text)), 2, texts(text, segment.units(text)))

    def test_a_unit_ends_after_a_sentence_end_followed_by_space_and_not_a_lowercase_letter(self):
        cases = {
            'One. Two.': ['One.', 'Two.'],
            'One! Two? Three.': ['One!', 'Two?', 'Three.'],
            'One.  \t Two.': ['One.', 'Two.'],
            'One.\u00a0Two.': ['One.', 'Two.'],  # a no-break space is a space
            'Removed (en bloc.) Then clipped.': ['Removed (en bloc.)', 'Then clipped.'],
            'He wrote "removed." Then left.': ['He wrote "removed."', 'Then left.'],
            'Measured approx. 5 cm.': ['Measured approx.', '5 cm.'],  # 1.9's S8 / S9
            'Seen. (Small) polyp.': ['Seen.', '(Small) polyp.'],
            'Done. ': ['Done.'],
            'Done.Then': ['Done.Then'],  # no space follows
            'Polyp removed. then clipped.': ['Polyp removed. then clipped.'],  # a lowercase letter follows
            'The pH was 7.4 today.': ['The pH was 7.4 today.'],
            'Really?! Yes.': ['Really?!', 'Yes.'],
            'Wait... Then.': ['Wait...', 'Then.'],
            'Done: Then more.': ['Done: Then more.'],  # a colon never ends a unit inside a line
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(texts(text, segment.units(text)), expected)

    def test_initials_and_short_titles_keep_their_unit(self):
        kept = ['Endoscopist: E. Morgan, MD', 'Dr. B. Prior (fictional) placed a tattoo.',
                'Signed by A. Current, MD (fictional)', 'Seen at St. Mary hospital.', 'Seen by Mr. Rowe today.',
                'Referred by Dr. \u00c1. P\u00e9rez today.', 'Read by J. R. Lee.', 'Cleared by (Dr. Lee) today.']
        for text in kept:
            with self.subTest(text=text):
                self.assertEqual(texts(text, segment.units(text)), [text])
        split = {
            'Seen by Mrs. Rowe today.': ['Seen by Mrs.', 'Rowe today.'],  # three letters: no list, so it cuts
            'Small lesions, e.g. These two.': ['Small lesions, e.g.', 'These two.'],  # first letter lowercase
            'Done in 3D. Then removed.': ['Done in 3D.', 'Then removed.'],  # preceded by a digit
            'Measured 5 cm. Then removed.': ['Measured 5 cm.', 'Then removed.'],
            'Go! Now.': ['Go!', 'Now.'],  # the exception is for a period only
        }
        for text, expected in split.items():
            with self.subTest(text=text):
                self.assertEqual(texts(text, segment.units(text)), expected)
        # a residual of the character shape, stated rather than patched (a limit recorded in DECISIONS D207): two
        # letters, the first uppercase, end no unit
        self.assertEqual(texts('Signed by A. Rowe, MD. The patient left.',
                               segment.units('Signed by A. Rowe, MD. The patient left.')),
                         ['Signed by A. Rowe, MD. The patient left.'])

    def test_a_short_token_is_letters_whose_first_is_uppercase(self):
        # DECISIONS D205 (arbiter triage 1a#1): a letter is what str.isalpha accepts and an uppercase letter what
        # str.isupper accepts, so a token holding a subscript, a fraction or a Roman-numeral character is no short
        # token, and neither is one whose first letter is caseless or titlecase: each period below ends a unit
        split = {
            'Oxygen was given at 2 L/min of O\u2082. The scope was inserted.':
                ['Oxygen was given at 2 L/min of O\u2082.', 'The scope was inserted.'],  # a subscript (No)
            'The dose was cut to \u00bd. Then it was stopped.':
                ['The dose was cut to \u00bd.', 'Then it was stopped.'],  # a fraction (No)
            'Graded stage \u2163. Then treated.': ['Graded stage \u2163.', 'Then treated.'],  # a Roman numeral (Nl)
            'Read by Dr. \u674e. Then signed.': ['Read by Dr. \u674e.', 'Then signed.'],  # a caseless letter (Lo)
            'Read by \u01c5. Then signed.': ['Read by \u01c5.', 'Then signed.'],  # a titlecase letter (Lt)
            'Measured \u00b2A. Then removed.': ['Measured \u00b2A.', 'Then removed.'],  # a numeral before the letter
        }
        for text, expected in split.items():
            with self.subTest(text=text):
                self.assertEqual(texts(text, segment.units(text)), expected)
                self.assertEqual(texts(text, oracle_units(text)), expected)
        # an uppercase letter of any script is still an initial
        for text in ('Signed by \u0141. Nowak today.', 'Seen by \u0394. Lee today.', 'Seen by Dr. \u00c9. Roy today.'):
            with self.subTest(text=text):
                self.assertEqual(texts(text, segment.units(text)), [text])

    def test_list_enumerators(self):
        text = ('Impression\n1. Short stricture, dilated.\n10. Two polyps removed.\nA. Ileum normal.\n'
                'a. Biopsies taken.\n1) Cecum reached.\n(2) Rectum normal.\n- Clips placed.\n\u2022 Tattoo placed.\n'
                'IV. Fourth item.\ni. Fifth item.')
        self.assertEqual(texts(text, segment.units(text)), [
            'Impression', '1.', 'Short stricture, dilated.', '10.', 'Two polyps removed.',
            'A. Ileum normal.',  # an uppercase one-letter token: kept with its item
            'a.', 'Biopsies taken.',  # a lowercase one-letter token: no exception
            '1) Cecum reached.', '(2) Rectum normal.', '- Clips placed.', '\u2022 Tattoo placed.',
            'IV. Fourth item.',  # two letters, the first uppercase
            'i.', 'Fifth item.'])
        # an item never runs into the next item's enumerator line, unless that line begins with a lowercase letter
        # after an open line: the hard-wrap rule joins it (a residual of the two-character test, stated; a limit
        # recorded in DECISIONS D207)
        self.assertEqual(texts('- polyp\n- clip', segment.units('- polyp\n- clip')), ['- polyp', '- clip'])
        self.assertEqual(texts('a) polyp removed\nb) clip placed', segment.units('a) polyp removed\nb) clip placed')),
                         ['a) polyp removed\nb) clip placed'])
        # the closure of an item's sentence never reaches back over its enumerator, which ends in a period
        got = segment.units(text)
        self.assertEqual(segment.closure(text, got, ['S3']), ('S3',))

    def test_forced_splits(self):
        words = ' '.join(['word'] * 300)  # 1,499 characters, no sentence end
        got = segment.units(words + '.')
        self.assertEqual([unit.end - unit.start for unit in got], [599, 599, 300])
        self.assertTrue(all(unit.forced for unit in got))  # every piece of a split unit is marked
        self.assertEqual(''.join(''.join(part.split()) for part in texts(words + '.', got)),
                         ''.join((words + '.').split()))
        for unit in got[:-1]:  # each cut at the last space before 600
            self.assertTrue((words + '.')[unit.end].isspace())
            self.assertNotIn(' ', (words + '.')[unit.end + 1:unit.start + 600])
        exact = 'x' * 599 + '.'
        self.assertEqual([(u.start, u.end, u.forced) for u in segment.units(exact)], [(0, 600, False)])
        over = 'x' * 600 + '.'
        self.assertEqual([(u.start, u.end, u.forced) for u in segment.units(over)], [(0, 600, True), (600, 601, True)])
        spaced = 'ab ' * 199 + ' ' + 'c' * 50 + '.'  # two spaces before the cut: the piece is trimmed
        cut = segment.units(spaced)
        self.assertEqual([(u.start, u.end, u.forced) for u in cut], [(0, 596, True), (598, 649, True)])
        wrapped = 'x' * 300 + ' ' + 'y' * 250 + '\nz' + 'z' * 100 + ' end.'  # a joined wrap is a space
        self.assertEqual([(u.start, u.end) for u in segment.units(wrapped)], [(0, 551), (552, 658)])
        short = 'One short sentence. ' + 'Another.'
        self.assertFalse(any(unit.forced for unit in segment.units(short)))

    def test_pages(self):
        text = 'No snare polypectomy was performed today.'
        cut = text.find('polypectomy')
        pages = (PageSpan(page=1, start=0, end=cut), PageSpan(page=2, start=cut, end=len(text)))
        got = segment.units(text, pages)
        self.assertEqual(texts(text, got), ['No snare', 'polypectomy was performed today.'])  # never across
        self.assertEqual([unit.page for unit in got], [1, 2])
        self.assertEqual([unit.paragraph for unit in got], [1, 1])  # a page boundary is not a paragraph break
        self.assertEqual([unit.line for unit in got], [1, 1])
        self.assertEqual(segment.closure(text, got, ['S2']), ('S1', 'S2'))  # the closure reaches across it
        # a hard wrap across a page boundary is not joined
        wrap = 'Neither biopsy nor\ntattoo was performed.'
        nl = wrap.find('\n')
        got = segment.units(wrap, (PageSpan(1, 0, nl + 1), PageSpan(2, nl + 1, len(wrap))))
        self.assertEqual(texts(wrap, got), ['Neither biopsy nor', 'tattoo was performed.'])
        # extraction joins pages with a blank line, and the job tiles each page on to the next page's start
        two = 'Page one text.\n\nPage two text.'
        got = segment.units(two, (PageSpan(1, 0, 16), PageSpan(2, 16, len(two))))
        self.assertEqual([(unit.page, unit.paragraph, unit.line) for unit in got], [(1, 1, 1), (2, 2, 3)])
        # page numbers are the spans' own, in the spans' order by start; an empty page holds nothing
        got = segment.units(two, (PageSpan(7, 16, len(two)), PageSpan(5, 0, 16), PageSpan(6, 16, 16)))
        self.assertEqual([unit.page for unit in got], [5, 7])
        # no pages: one page numbered 1
        self.assertEqual({unit.page for unit in segment.units(two)}, {1})

    def test_pages_must_tile_the_text(self):
        text = 'One. Two.'
        for pages in [(PageSpan(1, 1, 9),), (PageSpan(1, 0, 8),), (PageSpan(1, 0, 4), PageSpan(2, 5, 9)),
                      (PageSpan(1, 0, 5), PageSpan(2, 4, 9)), (PageSpan(1, 0, 10),)]:
            with self.subTest(pages=pages):
                with self.assertRaises(ValueError):
                    segment.units(text, pages)
                self.assertIsNone(segment.framed(text, pages))
        for bad in [(PageSpan(True, 0, 9),), (PageSpan(1, 0.0, 9),), (PageSpan('1', 0, 9),)]:
            with self.subTest(pages=bad):
                with self.assertRaises(TypeError):
                    segment.units(text, bad)
        with self.assertRaises(TypeError):
            segment.units(b'One.')
        with self.assertRaises(TypeError):
            segment.framed(None)

    def test_worked_example_of_1_9(self):
        got = segment.units(WORKED)
        self.assertEqual(texts(WORKED, got), WORKED.splitlines())  # 1.9's nine units, S8 and S9 included
        self.assertEqual(segment.closure(WORKED, got, ['S8', 'S9']), ('S8', 'S9'))  # E5's anchor


# --- the fixtures the done-when names ---------------------------------------------------------------------------------


class FixtureTests(SimpleTestCase):
    def test_the_fixtures_are_the_development_documents_byte_for_byte(self):
        self.assertEqual(hashlib.sha256(NOTE8.encode('utf-8')).hexdigest(), NOTE8_SHA256)
        self.assertEqual(hashlib.sha256(PAIR4.encode('utf-8')).hexdigest(), PAIR4_SHA256)
        self.assertEqual(len(NOTE8), 19398)

    def test_gi_note_8(self):
        got = segment.units(NOTE8)
        self.assertEqual(len(got), 181)  # 1.2: "GI Note #8 has 181 units instead of 317"
        denials = {
            'historical only; no esophagogastroduodenoscopy':
                'Those upper gastrointestinal interventions are historical only; no\nesophagogastroduodenoscopy or '
                'other upper endoscopic procedure was performed on November 8, 2026.',
            'No colonic stent was placed.': 'No colonic\nstent was placed.',
            'No hemostatic cautery, hemostatic clipping, injection for bleeding, or band ligation was performed in '
            'the rectum.':
                'No\nhemostatic cautery, hemostatic clipping, injection for bleeding, or band ligation was performed '
                'in the rectum.',
        }
        for needle, unit_text in denials.items():
            with self.subTest(denial=needle):
                hit = covering(got, NOTE8, needle)
                self.assertEqual(len(hit), 1)  # the negator is in the same unit as the act it denies
                self.assertEqual(texts(NOTE8, hit), [unit_text])
        extent = ('Because of the prior ileocecal resection, the native cecum and ileocecal valve are surgically '
                  'absent; completion of the examination was confirmed by direct identification and '
                  'photodocumentation of the ileocolonic anastomosis and subsequent intubation of the neo-terminal '
                  'ileum after dilation.')
        hit = covering(got, NOTE8, extent)
        self.assertEqual(len(hit), 1)
        self.assertEqual(' '.join(NOTE8[hit[0].start:hit[0].end].split()), extent)
        # initials keep their unit: every "Endoscopist: E. Morgan, MD" line is one unit
        for match in re.finditer(r'Endoscopist: E\. Morgan, MD', NOTE8):
            self.assertEqual(len([u for u in got if u.end > match.start() and u.start < match.end()]), 1)
        self.assertEqual(len(covering(got, NOTE8, 'occurred during the single date of service')), 1)
        # every closure of the note's units holds at most 12 units, and the denials' closures are themselves
        for unit in got:
            self.assertLessEqual(len(segment.closure(NOTE8, got, [unit.id])), segment.CLOSURE_UNITS)
        for needle in denials:
            unit = covering(got, NOTE8, needle)[0]
            self.assertEqual(segment.closure(NOTE8, got, [unit.id]), (unit.id,))

    def test_pair_4_w2(self):
        got = segment.units(PAIR4)
        self.assertEqual(len(got), 16)
        for needle in ('At this examination', 'endoscopic mucosal resection'):
            with self.subTest(needle=needle):
                self.assertEqual(len(covering(got, PAIR4, needle)), 1)
        both = covering(got, PAIR4, 'At this examination')[0]
        self.assertEqual(covering(got, PAIR4, 'endoscopic mucosal resection'), [both])  # one sentence, one unit
        self.assertEqual(PAIR4[both.start:both.end],
                         'At\nthis examination I resected the 18 mm sigmoid lesion by endoscopic mucosal\nresection '
                         'after a saline lift; the earlier tattoo was seen distal to the\nresection site.')
        self.assertEqual([len(covering(got, PAIR4, needle)) for needle in (
            'Dr. B. Prior (fictional) placed a tattoo 3 cm distal', 'Endoscopist: A. Current, MD (fictional)',
            'Electronically signed by A. Current, MD (fictional)')], [1, 1, 1])
        framed = segment.framed(PAIR4)
        self.assertIn('[S13] At this examination I resected the 18 mm sigmoid lesion by endoscopic mucosal resection '
                      'after a saline lift; the earlier tattoo was seen distal to the resection site.', framed)


# --- the sentence closure ---------------------------------------------------------------------------------------------


class ClosureTests(SimpleTestCase):
    def test_a_wrap_the_join_misses_still_brings_the_negator(self):
        text = 'Findings:\nNo\nColonic stent was placed. The scope was withdrawn.'
        got = segment.units(text)
        self.assertEqual(texts(text, got), ['Findings:', 'No', 'Colonic stent was placed.', 'The scope was withdrawn.'])
        self.assertEqual(segment.closure(text, got, ['S3']), ('S2', 'S3'))  # back to the negator, not to the label
        self.assertEqual(segment.closure(text, got, ['S2']), ('S2', 'S3'))  # forward until a unit ends a sentence
        self.assertEqual(segment.closure(text, got, ['S4']), ('S4',))
        self.assertEqual(segment.closure(text, got, ['S1']), ('S1',))  # a unit ending in a colon is closed

    def test_closers_and_paragraphs_bound_the_closure(self):
        text = 'Biopsy of the\nEsophagus was not performed.)\nThe rectum\nWas normal\n\nAnother part'
        got = segment.units(text)
        self.assertEqual(segment.closure(text, got, ['S1']), ('S1', 'S2'))
        self.assertEqual(segment.closure(text, got, ['S3']), ('S3', 'S4'))  # stops at the paragraph's end
        self.assertEqual(segment.closure(text, got, ['S5']), ('S5',))  # never back over a paragraph break

    def test_at_most_12_units_backward_first(self):
        text = '\n'.join(f'Line {index} Of a table' for index in range(1, 31)) + '.'  # 30 units, one sentence end
        got = segment.units(text)
        self.assertEqual(len(got), 30)
        for unit in got:
            self.assertEqual(len(segment.closure(text, got, [unit.id])), 12)
        self.assertEqual(segment.closure(text, got, ['S20']), tuple(f'S{k}' for k in range(9, 21)))  # backward first
        self.assertEqual(segment.closure(text, got, ['S5']), tuple(f'S{k}' for k in range(1, 13)))
        self.assertEqual(segment.closure(text, got, ['S29', 'S30']), tuple(f'S{k}' for k in range(19, 31)))
        twelve = [f'S{k}' for k in range(10, 22)]
        self.assertEqual(segment.closure(text, got, twelve), tuple(twelve))

    def test_a_run_is_consecutive_units_of_one_paragraph_within_the_bound(self):
        text = 'A one. B two. C three.\n\nD four.'
        got = segment.units(text)
        for run in ([], ['S9'], ['S1', 'S3'], ['S2', 'S1'], ['S1', 'S1'], ['S3', 'S4'],
                    [f'S{k}' for k in range(1, 14)]):
            with self.subTest(run=run):
                with self.assertRaises(ValueError):
                    segment.closure(text, got, run)
        with self.assertRaises(ValueError):
            segment.closure('short', got, ['S1'])  # units of another text
        long = '\n'.join(f'Row {index}' for index in range(1, 15))
        many = segment.units(long)
        with self.assertRaises(ValueError):
            segment.closure(long, many, [unit.id for unit in many[:13]])

    @hypothesis.settings(max_examples=150, deadline=None)
    @hypothesis.given(st.data())
    def test_closure_properties(self, data):
        text = data.draw(st.text(alphabet=st.sampled_from(list('Aab .:\n!?")')), max_size=160))
        got = segment.units(text)
        hypothesis.assume(got)
        first = data.draw(st.integers(0, len(got) - 1))
        size = data.draw(st.integers(1, segment.CLOSURE_UNITS))
        run = [unit for unit in got[first:first + size] if unit.paragraph == got[first].paragraph]
        out = segment.closure(text, got, [unit.id for unit in run])
        index = [unit.id for unit in got]
        lo, hi = index.index(out[0]), index.index(out[-1])
        self.assertEqual(list(out), index[lo:hi + 1])  # consecutive
        self.assertTrue(set(unit.id for unit in run) <= set(out))
        self.assertEqual({got[k].paragraph for k in range(lo, hi + 1)}, {run[0].paragraph})
        self.assertLessEqual(len(out), segment.CLOSURE_UNITS)

        def closed(unit):
            body = text[unit.start:unit.end].rstrip(CLOSERS)
            return body[-1:] in ('.', '!', '?', ':') and body != ''

        if len(out) < segment.CLOSURE_UNITS:  # maximal: nothing open is left before or after it
            if lo > 0 and got[lo - 1].paragraph == run[0].paragraph:
                self.assertTrue(closed(got[lo - 1]))
            if hi + 1 < len(got) and got[hi + 1].paragraph == run[0].paragraph:
                self.assertTrue(closed(got[hi]))


# --- the framing ------------------------------------------------------------------------------------------------------


class FramingTests(SimpleTestCase):
    def test_the_framed_layout(self):
        text = ('COLONOSCOPY REPORT\nDate of service: 11/09/2026\n\nFindings: The colonoscope was advanced.  A 6 mm '
                'polyp   \n   in the sigmoid colon was removed. Neither biopsy\nnor tattoo was performed.\n\n\nEnd')
        self.assertEqual(segment.framed(text), (
            '[Page 1]\n'
            '[S1] COLONOSCOPY REPORT\n'
            '[S2] Date of service: 11/09/2026\n'
            '\n'
            '[S3] Findings: The colonoscope was advanced. [S4] A 6 mm polyp in the sigmoid colon was removed. '
            '[S5] Neither biopsy nor tattoo was performed.\n'
            '\n'
            '\n'
            '[S6] End'))
        self.assertEqual(segment.framed(''), '[Page 1]\n')  # one empty line, as v1 frames an empty text
        self.assertEqual(segment.framed('One.\n'), '[Page 1]\n[S1] One.\n')

    def test_the_framed_pages(self):
        text = 'Page one text.\n\nPage two text. No snare\npolypectomy was done.'
        cut = text.find('Page two')
        inner = text.find('No snare') + 3
        pages = (PageSpan(1, 0, cut), PageSpan(2, cut, inner), PageSpan(3, inner, len(text)))
        self.assertEqual(segment.framed(text, pages), (
            '[Page 1]\n[S1] Page one text.\n\n'
            '[Page 2]\n[S2] Page two text. [S3] No\n'
            '[Page 3]\n[S4] snare polypectomy was done.'))
        # an empty page keeps its line; a page holding only spaces of a line writes nothing more
        text = 'One.\nTwo.'
        pages = (PageSpan(1, 0, 5), PageSpan(2, 5, 5), PageSpan(3, 5, len(text)))
        self.assertEqual(segment.framed(text, pages), '[Page 1]\n[S1] One.\n[Page 2]\n[Page 3]\n[S2] Two.')
        text = 'One   two.'
        pages = (PageSpan(1, 0, 4), PageSpan(2, 4, 5), PageSpan(3, 5, len(text)))
        self.assertEqual(segment.framed(text, pages), '[Page 1]\n[S1] One\n[Page 2]\n[Page 3]\n[S2] two.')

    def test_a_text_holding_a_unit_label_is_never_framed(self):
        refused = {'Seen at [S1] today.': 8, 'x[S42]': 1, '[S007] y': 0, 'Ref [S\u0663] z': 4, '[[S1]]': 1,
                   'a [S]b [S12]': 7, 'first [S9] and [S10]': 6}
        for text, offset in refused.items():
            with self.subTest(text=text):
                self.assertEqual(segment.label_collision(text), offset)
                self.assertIsNone(segment.framed(text))
                self.assertEqual(re.search(r'\[S\d+\]', text).start(), offset)  # the pattern of 1.2 rule 8
                self.assertIsInstance(segment.units(text), tuple)  # units are geometry: they are still cut
        allowed = ['[S]', '[s1]', '[S1', 'S1]', '[ S1]', '[S1a]', '[S-1]', '[SS1]', '[S1 ]', '[Page 1]', '[S\u00b2]',
                   'S12', '[', ']', '[S', '']
        for text in allowed:
            with self.subTest(text=text):
                self.assertIsNone(segment.label_collision(text))
                self.assertIsNone(re.search(r'\[S\d+\]', text))
                self.assertIsNotNone(segment.framed(text))

    def test_the_digit_scan_is_exactly_the_patterns_d(self):
        mismatched = [code for code in range(sys.maxunicode + 1)
                      if segment._decimal(chr(code), 0) != (re.fullmatch(r'\d', chr(code)) is not None)]
        self.assertEqual(mismatched, [])
        self.assertEqual([segment._decimal('a1\u0663', at) for at in range(3)], [False, True, True])  # reads text[at]

    @hypothesis.settings(max_examples=200, deadline=None)
    @hypothesis.given(st.text(alphabet=st.sampled_from(list('[]S1\u0663a ')), max_size=40))
    def test_the_collision_scan_equals_the_pattern(self, text):
        match = re.search(r'\[S\d+\]', text)
        self.assertEqual(segment.label_collision(text), None if match is None else match.start())
        self.assertEqual(segment.framed(text) is None, match is not None)

    def test_the_framed_text_is_a_pure_function_of_the_text(self):
        for text in (NOTE8, PAIR4, WORKED):
            with self.subTest(document=text[:20]):
                once = segment.framed(text)
                self.assertEqual(segment.framed(text), once)
                self.assertEqual(segment.units(text), segment.units(text))
        pages = (PageSpan(1, 0, 10), PageSpan(2, 10, 300), PageSpan(3, 300, len(PAIR4)))
        self.assertEqual(segment.framed(PAIR4, pages), segment.framed(PAIR4, tuple(reversed(pages))))
        self.assertEqual(segment.framed(PAIR4, pages), segment.framed(PAIR4, list(pages)))
        # in fresh interpreters with different hash seeds: the same bytes (what such an interpreter loads is
        # GuardTests.test_a_fresh_interpreter_loads_only_the_contract_and_the_standard_library)
        here = {name: hashlib.sha256(segment.framed(text).encode('utf-8')).hexdigest()
                for name, text in (('note8', NOTE8), ('pair4', PAIR4))}
        code = ('import hashlib, sys\n'
                f'sys.path.insert(0, {str(APP)!r})\n'
                'from studio.interpretation.contract import segment\n'
                'text = sys.stdin.buffer.read().decode("utf-8")\n'
                'print(hashlib.sha256(segment.framed(text).encode("utf-8")).hexdigest())\n')
        for seed in ('0', '4242'):
            for name, text in (('note8', NOTE8), ('pair4', PAIR4)):
                with self.subTest(seed=seed, document=name):
                    result = subprocess.run([sys.executable, '-B', '-s', '-c', code], input=text.encode('utf-8'),
                                            capture_output=True, timeout=60, cwd=APP,
                                            env={**os.environ, 'PYTHONHASHSEED': seed})
                    self.assertEqual(result.returncode, 0, result.stderr.decode())
                    self.assertEqual(result.stdout.decode().splitlines(), [here[name]])

    def test_the_module_keeps_no_state(self):
        for name, value in vars(segment).items():
            if (name.startswith('__') or callable(value) or isinstance(value, type(segment))
                    or value is __future__.annotations):
                continue
            with self.subTest(name=name):
                self.assertIsInstance(value, int)  # only the rule's numbers and the line kinds, all immutable

    @hypothesis.settings(max_examples=300, deadline=None)
    @hypothesis.given(st.data())
    def test_the_framed_text_writes_every_unit_and_nothing_else(self, data):
        text = data.draw(st.text(alphabet=st.sampled_from(list(
            'aAbB1 .:!?)"\'\u201d(\n\n\t-,\u00a0\u00e9\u00c9[S]')), max_size=220))
        cuts = data.draw(st.lists(st.integers(0, len(text)), max_size=4))
        pages = tiled(text, cuts)
        out = segment.framed(text, pages)
        if segment.label_collision(text) is not None:
            self.assertIsNone(out)
            return
        got = segment.units(text, pages)
        lines = out.split('\n')
        self.assertEqual([line for line in lines if re.fullmatch(r'\[Page \d+\]', line)],
                         [f'[Page {page.page}]' for page in pages])
        labels = re.findall(r'\[S(\d+)\] ', out)
        self.assertEqual(labels, [unit.id[1:] for unit in got])  # every unit once, in order
        written = []
        for line in lines:
            if re.fullmatch(r'\[Page \d+\]', line) or line == '':
                continue
            self.assertTrue(line.startswith('[S'), line)
            parts = re.split(r'(?:^| )\[S\d+\] ', line)
            written += [parts[1:]]
        flat = [part for line in written for part in line]
        self.assertEqual(flat, [re.sub(r'\s*\n\s*', ' ', text[u.start:u.end]) for u in got])
        # units of one framed line are the units of one stretch of joined lines, inside one page
        position = 0
        for line in written:
            stretch = got[position:position + len(line)]
            position += len(line)
            self.assertEqual(len({unit.page for unit in stretch}), 1)
            for before, after in zip(stretch, stretch[1:]):
                self.assertEqual(text[before.end:after.start].strip(), '')
        self.assertEqual(lines.count(''), sum(1 for line in text.split('\n') if line.strip() == ''))


# --- an independent oracle of 1.2, written with regular expressions and str methods ----------------------------------

_ENDS = re.compile(r'[.!?:][' + re.escape(CLOSERS) + r']*$')
_ALNUM = re.compile(r'[^\W_]')  # \w minus _: str.isalnum, as the re module defines \w for a str pattern


def letters_before(head: str) -> str:
    """The letters (str.isalpha, DECISIONS D205) that end ``head``: rule 3's token, read right to left."""
    return ''.join(itertools.takewhile(str.isalpha, reversed(head)))[::-1]


def oracle_units(text: str, pages=()) -> tuple:
    """1.2 rules 1-5 again, by other means: str.split, strip, regular expressions and a list scan, never segment's
    code."""
    spans = sorted((page.start, page.end, page.page) for page in pages) or [(0, len(text), 1)]

    def page_of(offset):
        return max(index for index, span in enumerate(spans) if span[0] <= offset)

    stretches, paragraph, previous, current, starts = [], 0, None, None, []
    offset = 0
    for line in text.split('\n'):
        start, offset = offset, offset + len(line) + 1
        starts.append(start)
        if line.strip() == '':
            previous = current = None
            continue
        if previous is None:
            paragraph += 1
        first = start + len(line) - len(line.lstrip())
        last = start + len(line.rstrip()) - 1
        joined = (previous is not None and _ENDS.search(previous[0]) is None and text[first].islower()
                  and page_of(previous[1]) == page_of(first))
        if not joined:
            current = None
        for index, (begin, end, _) in enumerate(spans):
            lo, hi = max(begin, first), min(end, last + 1)
            if lo >= hi:
                continue
            if current is not None and current[2] == index:
                current[1] = hi
            else:
                current = [lo, hi, index, paragraph]
                stretches.append(current)
        previous = (line.rstrip(), last)
    found = []
    for begin, end, index, paragraph in stretches:
        segment_text = text[begin:end]
        cuts, at = [], 0
        for match in re.finditer(r'[.!?]', segment_text):
            i = match.start()
            if i < at:
                continue
            closer = re.match(r'[' + re.escape(CLOSERS) + r']*', segment_text[i + 1:]).end()
            spaces = re.match(r'\s*', segment_text[i + 1 + closer:]).end()
            follow = i + 1 + closer + spaces
            if not spaces or follow >= len(segment_text) or segment_text[follow].islower():
                continue
            if segment_text[i] == '.':
                token = letters_before(segment_text[:i])
                before = segment_text[:i - len(token)]
                if 1 <= len(token) <= 2 and not (before and _ALNUM.match(before[-1])) and token[0].isupper():
                    continue  # rule 3's exception: one or two letters, the first uppercase (str.isupper, D205)
            cuts.append((i + 1 + closer, follow))
            at = follow
        bounds = [0] + [value for pair in cuts for value in pair] + [len(segment_text)]
        for lo, hi in zip(bounds[0::2], bounds[1::2]):
            piece = segment_text[lo:hi]
            lo, hi = begin + lo + len(piece) - len(piece.lstrip()), begin + lo + len(piece.rstrip())
            if lo >= hi:
                continue
            pieces = []
            while hi - lo > 600:
                window = text[lo:lo + 600]
                spaces = [m.start() for m in re.finditer(r'\s', window) if m.start() > 0]
                if spaces:
                    stop, resume = lo + len(window[:spaces[-1]].rstrip()), lo + spaces[-1]
                else:
                    stop = resume = lo + 600
                rest = text[resume:hi]
                pieces.append((lo, stop))
                lo = resume + len(rest) - len(rest.lstrip())
            pieces.append((lo, hi))
            for a, b in pieces:
                found.append((a, b, text.count('\n', 0, a) + 1, paragraph, spans[index][2], len(pieces) > 1))
    return tuple(Unit(id=f'S{k}', start=a, end=b, line=line, paragraph=paragraph, page=page, forced=forced)
                 for k, (a, b, line, paragraph, page, forced) in enumerate(found, 1))


# the last five are where rule 3's letter and uppercase classes (D205) differ from "alphanumeric and not a decimal
# digit" and "a letter that is not lowercase": a subscript, a fraction, a Roman-numeral character, a caseless letter
# and a titlecase letter
ALPHABET = list('aAbBeEdDrRmM1 2 \n\n\t.:!?"\')]}\u201d\u2019\u00bb(-,;\u00a0\u00c9\u00e9\u2022'
                '\u2082\u00bd\u2163\u674e\u01c5')
# where rule 3's classes (D205) are decided: a letter of each case and a digit, those five, a superscript and an
# uppercase letter outside ASCII
RULE_3_CHARACTERS = 'Aa1\u2082\u00bd\u2163\u674e\u01c5\u00b2\u0141'


class OracleTests(SimpleTestCase):
    def test_the_oracle_agrees_on_the_fixtures(self):
        for text in (NOTE8, PAIR4, WORKED):
            with self.subTest(document=text[:20]):
                self.assertEqual(segment.units(text), oracle_units(text))

    @hypothesis.settings(max_examples=400, deadline=None)
    @hypothesis.given(st.data())
    def test_units_equal_the_oracle_on_random_texts_and_pages(self, data):
        text = data.draw(st.text(alphabet=st.sampled_from(ALPHABET), max_size=300))
        pages = tiled(text, data.draw(st.lists(st.integers(0, len(text)), max_size=5)))
        self.assertEqual(segment.units(text, pages), oracle_units(text, pages))

    @hypothesis.settings(max_examples=60, deadline=None)
    @hypothesis.given(st.data())
    def test_units_equal_the_oracle_on_long_texts(self, data):
        text = data.draw(st.text(alphabet=st.sampled_from(list('ab\n .A')), min_size=500, max_size=2500))
        pages = tiled(text, data.draw(st.lists(st.integers(0, len(text)), max_size=2)))
        self.assertEqual(segment.units(text, pages), oracle_units(text, pages))

    def test_units_equal_the_oracle_on_every_short_token_shape(self):
        # every token of one or two of rule 3's deciding characters before a period, after each kind of neighbour and
        # before each kind of follower: D205's classes, read by the module and by the oracle, on all 3,080 shapes
        tokens = [*RULE_3_CHARACTERS, *(a + b for a in RULE_3_CHARACTERS for b in RULE_3_CHARACTERS)]
        shapes = [f'{before}{token}. {after}' for before in ('', ' ', '(', 'a', 'B', '1', '\u00b2')
                  for token in tokens for after in ('A', 'a', '1', '"')]
        self.assertEqual(len(shapes), 3080)
        self.assertEqual([text for text in shapes if segment.units(text) != oracle_units(text)], [])
        self.assertEqual({len(segment.units(text)) for text in shapes}, {1, 2})  # both outcomes occur in the grid

    @hypothesis.settings(max_examples=300, deadline=None)
    @hypothesis.given(st.data())
    def test_every_unit_is_its_revision_slice(self, data):
        text = data.draw(st.text(max_size=300) | st.text(alphabet=st.sampled_from(ALPHABET), max_size=300))
        pages = tiled(text, data.draw(st.lists(st.integers(0, len(text)), max_size=4)))
        got = segment.units(text, pages)
        self.assertEqual([unit.id for unit in got], [f'S{k}' for k in range(1, len(got) + 1)])
        covered = []
        for before, unit in zip((None, *got), got):
            piece = text[unit.start:unit.end]
            self.assertTrue(piece and piece == piece.strip())  # trimmed, never empty
            self.assertLessEqual(len(piece), segment.UNIT_CHARS)
            if before is not None:
                self.assertLessEqual(before.end, unit.start)  # in order, disjoint
            page = next(span for span in pages if span.start <= unit.start and unit.end <= span.end)
            self.assertEqual(unit.page, page.page)  # never across a page
            self.assertEqual(unit.line, text.count('\n', 0, unit.start) + 1)
            covered += [index for index in range(unit.start, unit.end) if not text[index].isspace()]
        self.assertEqual(covered, [index for index, char in enumerate(text) if not char.isspace()])

    def test_dataclass_shape(self):
        self.assertEqual([field.name for field in dataclasses.fields(Unit)],
                         ['id', 'start', 'end', 'line', 'paragraph', 'page', 'forced'])


# --- the pin and the guard --------------------------------------------------------------------------------------------


# SEGMENTATION_SHA256's object (FINAL-V2 2.5): the sha256 of rule_constants(), which the integration owner writes into
# interpretation.SEGMENTATION_SHA256 after the wave's repairs (DECISIONS D202, arbiter triage INT-5)
RULE_CONSTANTS_SHA256 = '41d2245ada69f2a573d0354486323d9f30e00fef7091f531e2e0541a11af8e78'
# segment.py's code (DECISIONS D202, arbiter triage 1a#3): code_sha256 of the module, so a rule change that keeps
# rule_constants() (a character class, the wrap test, the closure order) is still seen
SEGMENT_CODE_SHA256 = '302074eda2b840ac89689fba7c7ff7584510f746a71f60aaf13dc0841df8ed4b'
CODE_PIN_MESSAGE = ("segment.py's rule changed: recompute SEGMENTATION_SHA256's object and, once gemini-events@2 is "
                    'recorded, bump INTERPRETATION_VERSION')


def code_sha256(source: str) -> str:
    """The sha256 of ``ast.dump`` of the module's AST with the docstring of the module and of every class and function
    removed: comments, docstrings and layout leave it unchanged, and any change to the code changes it."""
    tree = ast.parse(source)
    for node in list(ast.walk(tree)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                node.body = node.body[1:]
    return hashlib.sha256(ast.dump(tree).encode('utf-8')).hexdigest()


class PinTests(SimpleTestCase):
    def test_the_constants_describe_the_predicates_exactly(self):
        constants = segment.rule_constants()
        self.assertEqual((constants['unit_chars'], constants['closure_units'], constants['short_token_letters']),
                         (600, 12, 2))
        sets = {'unit_enders': segment._ender, 'closers': segment._closer,
                'line_enders': lambda c: segment._ender(c) or c == ':'}
        for key, predicate in sets.items():
            with self.subTest(set=key):
                self.assertEqual({chr(code) for code in range(sys.maxunicode + 1) if predicate(chr(code))},
                                 set(constants[key]))
        self.assertEqual(constants['closers'], CLOSERS)
        self.assertEqual(jsonschema.canonical(constants), jsonschema.canonical(segment.rule_constants()))

    def test_rule_3s_classes_are_isalpha_and_isupper(self):
        # DECISIONS D205: rule 3's letter is what str.isalpha accepts and its uppercase letter what str.isupper
        # accepts, on every code point
        for name, predicate, method in (('letter', segment._letter, str.isalpha),
                                        ('uppercase', segment._uppercase, str.isupper)):
            with self.subTest(character_class=name):
                self.assertEqual([code for code in range(sys.maxunicode + 1)
                                  if predicate(chr(code)) != method(chr(code))], [])

    def test_the_rule_is_pinned(self):
        # until gemini-events@2 is recorded (D1), a changed constant needs only a recomputed pin; after it, a changed
        # byte needs gemini-events@3 (FINAL-V2 2.5, DECISIONS D202)
        self.assertEqual(jsonschema.sha256_of(segment.rule_constants()), RULE_CONSTANTS_SHA256)
        # the pin the integration owner writes is empty until then, and this value once written (triage INT-5)
        self.assertIn(interpretation.SEGMENTATION_SHA256, ('', RULE_CONSTANTS_SHA256))

    def test_the_code_is_pinned(self):
        self.assertEqual(code_sha256(SEGMENT.read_text(encoding='utf-8')), SEGMENT_CODE_SHA256, CODE_PIN_MESSAGE)

    def test_the_code_pin_sees_a_rule_change_the_constants_miss(self):
        source = SEGMENT.read_text(encoding='utf-8')
        # a reworded docstring, a comment and a blank line leave the code pin unchanged
        anchor = '    """A letter, for the short-token exception'
        self.assertEqual(source.count(anchor), 1)
        relaid = source.replace(anchor, '    """Reworded. A letter, for the short-token exception')
        relaid += '\n\n# a comment\n'
        self.assertNotEqual(relaid, source)
        self.assertEqual(code_sha256(relaid), code_sha256(source))
        # rule 3's letter class widened back to str.isalnum, in memory: the code pin moves and the constants' does not
        line = '    return character.isalpha()\n'
        self.assertEqual(source.count(line), 1)
        widened = source.replace(line, '    return character.isalnum()\n')
        self.assertIn('return character.isalnum()', widened)  # the plant is applied
        self.assertNotEqual(code_sha256(widened), code_sha256(source))
        planted = {'__name__': 'segment_widened'}
        exec(compile(widened, 'segment_widened.py', 'exec'), planted)  # the plant, in memory only (5.7 measure 7)
        self.assertEqual(jsonschema.sha256_of(planted['rule_constants']()), RULE_CONSTANTS_SHA256)
        text = 'Oxygen was given at 2 L/min of O\u2082. The scope was inserted.'
        self.assertEqual((len(planted['units'](text)), len(segment.units(text))), (1, 2))  # it segments differently


STR_METHODS = frozenset(name for name in dir(str) if not name.startswith('_'))
# the str methods SingleCharacterGeometry admits: three character classes, and the two DECISIONS D205 adds
ADMITTED = ('isspace', 'islower', 'isalnum', 'isalpha', 'isupper')


def single_character_geometry(source: str) -> list:
    """FINAL-V2 5.7 measure 4's SingleCharacterGeometry as DECISIONS D205 states it (step 6a writes the guard proper):
    no import of re (nor regex, unicodedata, difflib, fnmatch); no string literal longer than one character in a
    comparison; no str call but isspace, islower, isalnum, isalpha, isupper, and find or rfind given a one-character
    literal. The forms D205 has step 6a refuse beyond these (a getattr-built str call, a multi-character slice compared
    with a named constant) are 6a's (arbiter triage 1a#2); the forms segment.py takes are pinned below."""
    tree, out = ast.parse(source), []
    for node in ast.walk(tree):
        names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [node.module or ''] if isinstance(node, ast.ImportFrom) else [])
        out += [f'imports {name}' for name in names
                if name.split('.')[0] in ('re', 'regex', 'unicodedata', 'difflib', 'fnmatch')]
        if isinstance(node, ast.Compare):
            for operand in (node.left, *node.comparators):
                out += [f'compares with {leaf.value!r} at line {node.lineno}' for leaf in ast.walk(operand)
                        if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str) and len(leaf.value) > 1]
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in STR_METHODS
              and node.func.attr not in ADMITTED):
            first = node.args[0] if node.args else None
            if not (node.func.attr in ('find', 'rfind') and isinstance(first, ast.Constant)
                    and isinstance(first.value, str) and len(first.value) == 1):
                out.append(f'calls .{node.func.attr}() at line {node.lineno}')
    return out


def no_word_lists(source: str) -> list:
    """FINAL-V2 5.7 measure 4's NoWordLists: no module-level tuple, list, set or dict of two or more string literals."""
    out = []
    for statement in ast.parse(source).body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None:
            for node in ast.walk(statement.value):
                items = ([*node.keys, *node.values] if isinstance(node, ast.Dict)
                         else getattr(node, 'elts', []) if isinstance(node, (ast.Tuple, ast.List, ast.Set)) else [])
                if sum(1 for item in items if isinstance(item, ast.Constant) and isinstance(item.value, str)) >= 2:
                    out.append(f'a module-level word list at line {node.lineno}')
    return out


RETIRED = tuple(f'studio.interpretation.{name}' for name in (
    'prompt', 'schema', 'read', 'normalize', 'verify', 'literals', 'identity', 'lexicon', 'relations', 'mapping',
    'classes', 'ercp', 'facts', 'events', 'coverage', 'combination', 'assess'))  # FINAL-V2 5.0
CONTRACT = 'studio.interpretation.contract'


def foreign(modules) -> list:
    """The modules of ``modules`` that importing segment may not load (arbiter triage 1a#5): one of the 17 retired v1
    modules, one of studio.gi, or any module outside the contract package (the two parent packages a package import
    loads aside) and the standard library."""
    out = []
    for name in modules:
        if any(name == module or name.startswith(module + '.') for module in RETIRED):
            out.append(f'{name}: a retired v1 module (FINAL-V2 5.0)')
        elif name == 'studio.gi' or name.startswith('studio.gi.'):
            out.append(f'{name}: studio.gi')
        elif name in ('studio', 'studio.interpretation') or name == CONTRACT or name.startswith(CONTRACT + '.'):
            continue
        elif name.split('.')[0] not in sys.stdlib_module_names:
            out.append(f'{name}: outside the contract package and the standard library')
    return out


class GuardTests(SimpleTestCase):
    def test_the_module_keeps_measure_4(self):
        source = SEGMENT.read_text(encoding='utf-8')
        self.assertEqual(single_character_geometry(source), [])
        self.assertEqual(no_word_lists(source), [])

    def test_each_rule_refuses_a_planted_control(self):
        plants = {
            'import re\n': 'imports re',
            'from unicodedata import category\n': 'imports unicodedata',
            "def f(c):\n    return c == 'no'\n": "compares with 'no'",
            "def f(c):\n    return c in '.!?'\n": "compares with '.!?'",
            "def f(c):\n    return c not in ('no', 'x')\n": "compares with 'no'",
            "def f(t):\n    return t.startswith('No')\n": 'calls .startswith()',
            "def f(t):\n    return t.find('no')\n": 'calls .find()',
            'def f(t, w):\n    return t.find(w)\n': 'calls .find()',
            "def f(t):\n    return ''.join(t)\n": 'calls .join()',
            'def f(t):\n    return t.istitle()\n': 'calls .istitle()',
            'def f(t):\n    return t.isdigit()\n': 'calls .isdigit()',
            'def f(t):\n    return t.split()\n': 'calls .split()',
        }
        for plant, expected in plants.items():
            with self.subTest(plant=plant.strip()):
                self.assertTrue(any(expected in finding for finding in single_character_geometry(plant)),
                                single_character_geometry(plant))
        for plant in ("MARKERS = ('no', 'not')\n", "TABLE = {'denied': 1, 'without': 2}\n", "W = ['no', 'nor']\n"):
            with self.subTest(plant=plant.strip()):
                self.assertTrue(no_word_lists(plant))
        controls = ("def f(c):\n    return c == '.'\n", "def f(t):\n    return t.find('.', 3)\n",
                    'def f(t):\n    return t[0].isspace()\n', "ENDS = ('.',)\n", 'SIZE = 600\n',
                    'def f(t, at):\n    return t[at].isalpha() and t[at].isupper()\n')  # D205 admits both classes
        for control in controls:
            with self.subTest(control=control.strip()):
                self.assertEqual(single_character_geometry(control) + no_word_lists(control), [])

    def test_int_and_slices_take_only_the_forms_d205_admits(self):
        # DECISIONS D205: int() of one character of the text (a subscript, never a slice) and slices of the text only
        # to copy a unit into the framed text (``out += text[a:b]``); no getattr, eval or exec (arbiter triage 1a#2)
        tree = ast.parse(SEGMENT.read_text(encoding='utf-8'))
        parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        ints = [call for call in calls if call.func.id == 'int']
        self.assertEqual(len(ints), 1)  # _decimal's
        for call in ints:
            self.assertEqual((len(call.args), call.keywords), (1, []))
            self.assertIsInstance(call.args[0], ast.Subscript)
            self.assertNotIsInstance(call.args[0].slice, ast.Slice)
        slices = [node for node in ast.walk(tree)
                  if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice)]
        self.assertEqual(len(slices), 2)  # _rendered's two copies of a unit's characters
        for node in slices:
            self.assertIsInstance(parent[node], ast.AugAssign)
            self.assertIsInstance(parent[node].op, ast.Add)
            self.assertIs(parent[node].value, node)
        self.assertEqual([call.func.id for call in calls if call.func.id in ('getattr', 'eval', 'exec', '__import__')],
                         [])

    def test_the_imports(self):
        # the module's own imports, exactly (arbiter triage 1a#5): bisect, collections.abc and typing of the standard
        # library and contract types, beside the __future__ directive
        tree = ast.parse(SEGMENT.read_text(encoding='utf-8'))
        imported = sorted({alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                           for alias in node.names}
                          | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)})
        self.assertEqual(imported, ['__future__', 'bisect', 'collections.abc', 'studio.interpretation.contract.types',
                                    'typing'])

    def test_a_fresh_interpreter_loads_only_the_contract_and_the_standard_library(self):
        # arbiter triage 1a#5: the modules a fresh interpreter gains by importing segment, read by what they are rather
        # than as one exact set, so an import another step adds inside the contract package or from the standard
        # library keeps this green, and a retired, studio.gi or other module turns it red
        code = ('import json, sys\n'
                f'sys.path.insert(0, {str(APP)!r})\n'
                'before = set(sys.modules)\n'
                'from studio.interpretation.contract import segment\n'
                'print(json.dumps(sorted(set(sys.modules) - before)))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True, timeout=60,
                                cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = json.loads(result.stdout)
        # the positive control: the import itself was seen, so an empty finding is not an instrument that saw nothing
        self.assertLessEqual({f'{CONTRACT}.segment', f'{CONTRACT}.types'}, set(loaded), loaded)
        self.assertEqual(foreign(loaded), [])

    def test_the_load_check_refuses_each_planted_module(self):
        planted = ['studio.interpretation.lexicon', 'studio.interpretation.assess', 'studio.gi', 'studio.gi.cues',
                   'studio.interpretation.store', 'studio.jobs', 'django.conf']
        self.assertEqual([finding.split(':')[0] for finding in foreign(planted)], planted)
        self.assertEqual([finding.split(': ')[1] for finding in foreign(planted)],
                         ['a retired v1 module (FINAL-V2 5.0)'] * 2 + ['studio.gi'] * 2
                         + ['outside the contract package and the standard library'] * 3)
        self.assertEqual(foreign(['json', 'collections.abc', '_bisect', 'typing', 'studio', 'studio.interpretation',
                                  CONTRACT, f'{CONTRACT}.types', f'{CONTRACT}.jsonschema']), [])
