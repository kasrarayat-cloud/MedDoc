# CPT Studio — GI coverage catalogue

Generated from `studio/gi/catalogue.py` (gi-catalogue@1); do not edit by hand. One GI workspace, one upload flow and one combined results screen: these families are internal profiles, never navigation.

Support levels: **supported** — the documented-service reader reads the family's services and acts, and the catalogue reconciles them with provider-selected codes, with regression documents; **recognised** — listed for review, not reconciled; **unsupported** — named so a result can say so.

The code lists are internal reconciliation profiles (which documented act a code accounts for). They are not a CPT reference and carry no descriptors; CPT code-set membership, NCCI procedure-to-procedure edits and payer policies are not connected, so they stay not verified. No coverage claim is an accuracy claim: accuracy needs independently adjudicated cases.

| Family | Support | Acts reconciled | Codes reconciled |
|---|---|---|---|
| Office / outpatient evaluation and management (`gi.office_em`) | supported | em_visit | 99202, 99203, 99204, 99205, 99211, 99212, 99213, 99214, 99215, 99242, 99243, 99244, 99245, 99417 |
| Upper GI endoscopy (EGD, esophagoscopy, POEM) (`gi.egd`) | supported | biopsy, hot_biopsy, snare, emr, ablation, bleeding_control, injection, tattoo, band_ligation, dilation, stent, foreign_body, decompression, peg, tube_placement, myotomy, fundoplication | 43197, 43198, 43200, 43201, 43202, 43204, 43205, 43210, 43211, 43212, 43213, 43214, 43215, 43216, 43217, 43220, 43226, 43227, 43229, 43233, 43235, 43236, 43239, 43241, 43243, 43244, 43245, 43246, 43247, 43248, 43249, 43250, 43251, 43254, 43255, 43257, 43266, 43270, 43497 |
| Small-bowel enteroscopy (push, balloon-assisted, through a stoma) (`gi.enteroscopy`) | supported | biopsy, hot_biopsy, snare, ablation, bleeding_control, stent, foreign_body, dilation, tube_placement, peg, tube_replacement | 44360, 44361, 44363, 44364, 44365, 44366, 44369, 44370, 44372, 44373, 44376, 44377, 44378, 44379, 44380, 44381, 44382, 44384, 44385, 44386 |
| Colonoscopy (`gi.colonoscopy`) | supported | biopsy, hot_biopsy, snare, emr, ablation, bleeding_control, injection, tattoo, band_ligation, dilation, stent, foreign_body, decompression | 44388, 44389, 44390, 44391, 44392, 44394, 44401, 44402, 44403, 44404, 44405, 44408, 45378, 45379, 45380, 45381, 45382, 45384, 45385, 45386, 45388, 45389, 45390, 45393, 45398 |
| Flexible sigmoidoscopy (`gi.flex_sig`) | supported | biopsy, hot_biopsy, snare, emr, ablation, bleeding_control, injection, tattoo, band_ligation, dilation, stent, foreign_body, decompression | 45330, 45331, 45332, 45333, 45334, 45335, 45337, 45338, 45340, 45346, 45347, 45349, 45350 |
| Endoscopic ultrasound (`gi.eus`) | supported | eus_exam, fna, injection, drainage | 43231, 43232, 43237, 43238, 43240, 43242, 43253, 43259, 44406, 44407, 45341, 45342, 45391, 45392 |
| ERCP (`gi.ercp`) | supported | biopsy, sphincterotomy, stone_extraction, lithotripsy, cholangioscopy, stent, stent_removal, stent_exchange, dilation, ablation, pressure_measurement | 43260, 43261, 43262, 43263, 43264, 43265, 43273, 43274, 43275, 43276, 43277, 43278 |
| Capsule endoscopy (small bowel, esophagus, colon) (`gi.capsule`) | supported | capsule_study | 91110, 91111, 91113 |
| Motility and manometry (esophageal, gastric, duodenal, colonic) (`gi.motility`) | supported | manometry | 91010, 91013, 91020, 91022, 91040, 91117 |
| pH and impedance monitoring (`gi.reflux`) | supported | ph_monitoring | 91030, 91034, 91035, 91037, 91038 |
| Anorectal testing (manometry, sensation and compliance) (`gi.anorectal`) | supported | manometry, rectal_sensation | 91120, 91122 |
| Feeding-tube procedures (gastrostomy and jejunostomy placement and replacement) (`gi.feeding_tube`) | supported | peg, tube_placement, tube_replacement | 43762, 43763, 49440, 49441, 49446, 49450, 49451, 49452 |
| Moderate sedation by the performing physician (`gi.sedation`) | recognised | moderate_sedation | 99152, 99153 |
| Other GI services (anoscopy, hemorrhoid banding, rigid proctosigmoidoscopy, liver biopsy, paracentesis, breath tests, elastography) (`gi.other`) | recognised | — | — |
| Named unsupported services (`unsupported`) | unsupported | — | — |

## Office / outpatient evaluation and management — supported

**Required documentation:**
- date of service
- setting (office or outpatient)
- new or established patient status
- the basis for the level: total time on the date of service, or the level of medical decision making
- on a procedure day: a significant, separately identifiable E/M stated as such
**Verification evidence:**
- a visit documented on the date of service
- the time statement or the MDM statement the level rests on
- on a procedure day: the statement of a separately identifiable E/M
**Rule checks:**
- CMS PFS presence and status for the date
- Same-day procedure: separately identifiable E/M (modifier 25 consideration, never assigned)
**Notes:**
- Office consultation codes (99242-99245) are not paid by Medicare; payer rules are not connected.
**Clarification questions (asked together, when not documented):**
- `setting`: Where did the visit take place (office, hospital outpatient, telehealth)?
- `patient_status`: Was the patient new or established to this clinician and group?
- `em_basis`: What supports the level: total time on the date of service, or the level of medical decision making?
- `service_date`: What is the date of service of the visit?
**Not separately reported (internal profile rules):**
- `em_routine`: The routine history, examination and consent before a procedure belong to the procedure (its global period), not to a separate E/M.

## Upper GI endoscopy (EGD, esophagoscopy, POEM) — supported

**Required documentation:**
- the examination and its extent (esophagus only, or to the duodenum)
- each intervention, its anatomy and technique
- completion, and the reason when it was not completed
**Verification evidence:**
- the examination documented on the date of service (not history or plan)
- each coded act (biopsy, removal, dilation ...) stated as done, at the anatomy the code needs
- the technique where the code depends on it (snare vs hot forceps vs forceps)
**Rule checks:**
- CMS PFS (RVU file): presence and status for the date, global period, endoscopic base family (multiple-endoscopy payment rule), PC/TC indicator
- CMS practitioner MUE: units per day
- Same-day E/M held unless a significant, separately identifiable E/M is documented (global period)
- Modifier considerations (never assigned): distinct lesions or sites within one endoscopic family (59/XS, NCCI not connected), incomplete examination (52/53, payer rule not connected), screening that became therapeutic (PT/33, payer rule not connected)
**Clarification questions (asked together, when not documented):**
- `extent`: How far was the instrument advanced (the landmark reached)?
- `completion`: Was the examination completed as intended? If not, how far did it reach and why was it stopped?
**Not separately reported (internal profile rules):**
- `clip`: A clip placed prophylactically, with no bleeding treated, is not reported as a separate service; a clip that treats bleeding is read as bleeding control (internal profile rule).
- `cannulation`: Instrument passage and cannulation are part of the examination itself.
- `biopsy_of_removed_lesion`: A biopsy of a lesion that is then removed at the same session (snare, hot forceps, EMR) is part of the removal (internal profile rule, NCCI policy principle; NCCI is not connected).
- `lift_injection`: A submucosal injection made to lift a lesion for its resection is part of the resection.
**Unsupported within the family:**
- `esd`: Endoscopic submucosal dissection has no code profile here; a coder decides how it is reported.

## Small-bowel enteroscopy (push, balloon-assisted, through a stoma) — supported

**Required documentation:**
- the depth reached (beyond the second portion of the duodenum; whether the ileum was reached)
- each intervention, its anatomy and technique
**Verification evidence:**
- the examination documented on the date of service (not history or plan)
- each coded act (biopsy, removal, dilation ...) stated as done, at the anatomy the code needs
- the technique where the code depends on it (snare vs hot forceps vs forceps)
**Rule checks:**
- CMS PFS (RVU file): presence and status for the date, global period, endoscopic base family (multiple-endoscopy payment rule), PC/TC indicator
- CMS practitioner MUE: units per day
- Same-day E/M held unless a significant, separately identifiable E/M is documented (global period)
- Modifier considerations (never assigned): distinct lesions or sites within one endoscopic family (59/XS, NCCI not connected), incomplete examination (52/53, payer rule not connected), screening that became therapeutic (PT/33, payer rule not connected)
**Clarification questions (asked together, when not documented):**
- `extent`: How far was the instrument advanced (the landmark reached)?
- `completion`: Was the examination completed as intended? If not, how far did it reach and why was it stopped?
**Not separately reported (internal profile rules):**
- `clip`: A clip placed prophylactically, with no bleeding treated, is not reported as a separate service; a clip that treats bleeding is read as bleeding control (internal profile rule).
- `cannulation`: Instrument passage and cannulation are part of the examination itself.
- `biopsy_of_removed_lesion`: A biopsy of a lesion that is then removed at the same session (snare, hot forceps, EMR) is part of the removal (internal profile rule, NCCI policy principle; NCCI is not connected).
- `lift_injection`: A submucosal injection made to lift a lesion for its resection is part of the resection.

## Colonoscopy — supported

**Required documentation:**
- the extent reached (cecum or terminal ileum for a complete examination)
- bowel preparation
- each lesion (size, site) and what was done to it (sampled, removed, untreated)
- intent (screening, surveillance or diagnostic)
- completion and the reason it was not completed
**Verification evidence:**
- the examination documented on the date of service (not history or plan)
- each coded act (biopsy, removal, dilation ...) stated as done, at the anatomy the code needs
- the technique where the code depends on it (snare vs hot forceps vs forceps)
**Rule checks:**
- CMS PFS (RVU file): presence and status for the date, global period, endoscopic base family (multiple-endoscopy payment rule), PC/TC indicator
- CMS practitioner MUE: units per day
- Same-day E/M held unless a significant, separately identifiable E/M is documented (global period)
- Modifier considerations (never assigned): distinct lesions or sites within one endoscopic family (59/XS, NCCI not connected), incomplete examination (52/53, payer rule not connected), screening that became therapeutic (PT/33, payer rule not connected)
**Clarification questions (asked together, when not documented):**
- `extent`: How far was the instrument advanced (the landmark reached)?
- `completion`: Was the examination completed as intended? If not, how far did it reach and why was it stopped?
**Not separately reported (internal profile rules):**
- `clip`: A clip placed prophylactically, with no bleeding treated, is not reported as a separate service; a clip that treats bleeding is read as bleeding control (internal profile rule).
- `cannulation`: Instrument passage and cannulation are part of the examination itself.
- `biopsy_of_removed_lesion`: A biopsy of a lesion that is then removed at the same session (snare, hot forceps, EMR) is part of the removal (internal profile rule, NCCI policy principle; NCCI is not connected).
- `lift_injection`: A submucosal injection made to lift a lesion for its resection is part of the resection.
**Unsupported within the family:**
- `esd`: Endoscopic submucosal dissection has no code profile here; a coder decides how it is reported.

## Flexible sigmoidoscopy — supported

**Required documentation:**
- the extent reached
- each lesion and what was done to it
- intent
**Verification evidence:**
- the examination documented on the date of service (not history or plan)
- each coded act (biopsy, removal, dilation ...) stated as done, at the anatomy the code needs
- the technique where the code depends on it (snare vs hot forceps vs forceps)
**Rule checks:**
- CMS PFS (RVU file): presence and status for the date, global period, endoscopic base family (multiple-endoscopy payment rule), PC/TC indicator
- CMS practitioner MUE: units per day
- Same-day E/M held unless a significant, separately identifiable E/M is documented (global period)
- Modifier considerations (never assigned): distinct lesions or sites within one endoscopic family (59/XS, NCCI not connected), incomplete examination (52/53, payer rule not connected), screening that became therapeutic (PT/33, payer rule not connected)
**Clarification questions (asked together, when not documented):**
- `extent`: How far was the instrument advanced (the landmark reached)?
- `completion`: Was the examination completed as intended? If not, how far did it reach and why was it stopped?
**Not separately reported (internal profile rules):**
- `clip`: A clip placed prophylactically, with no bleeding treated, is not reported as a separate service; a clip that treats bleeding is read as bleeding control (internal profile rule).
- `cannulation`: Instrument passage and cannulation are part of the examination itself.
- `biopsy_of_removed_lesion`: A biopsy of a lesion that is then removed at the same session (snare, hot forceps, EMR) is part of the removal (internal profile rule, NCCI policy principle; NCCI is not connected).
- `lift_injection`: A submucosal injection made to lift a lesion for its resection is part of the resection.

## Endoscopic ultrasound — supported

**Required documentation:**
- the stations examined (limited to one organ and adjacent structures, or esophagus, stomach and duodenum)
- the target of any fine-needle aspiration or biopsy and the passes made
- any drainage or injection
**Verification evidence:**
- the endosonographic examination on the date of service
- the needle sampling and its target
- the stations examined (whether the examination was limited or full is the reviewer's to judge; this catalogue does not check it)
**Rule checks:**
- CMS PFS (RVU file): presence and status for the date, global period, endoscopic base family (multiple-endoscopy payment rule), PC/TC indicator
- CMS practitioner MUE: units per day
- Same-day E/M held unless a significant, separately identifiable E/M is documented (global period)
- Modifier considerations (never assigned): distinct lesions or sites within one endoscopic family (59/XS, NCCI not connected), incomplete examination (52/53, payer rule not connected), screening that became therapeutic (PT/33, payer rule not connected)
**Clarification questions (asked together, when not documented):**
- `target`: What was examined, and what (if anything) was sampled with the needle?
**Not separately reported (internal profile rules):**
- `biopsy`: A forceps biopsy at the same upper examination is read under the upper GI family.
**Unsupported within the family:**
- `drainage`: EUS-guided drainage other than of a pseudocyst (biliary, gallbladder, gastroenterostomy) has no profiled code.

## ERCP — supported

**Required documentation:**
- cannulation (which duct, success or failure)
- each intervention (sphincterotomy, stone removal, stent placement, dilation, cholangioscopy, lithotripsy)
- stents placed (number, duct)
**Verification evidence:**
- the examination documented on the date of service (not history or plan)
- each coded act (biopsy, removal, dilation ...) stated as done, at the anatomy the code needs
- the technique where the code depends on it (snare vs hot forceps vs forceps)
**Rule checks:**
- CMS PFS (RVU file): presence and status for the date, global period, endoscopic base family (multiple-endoscopy payment rule), PC/TC indicator
- CMS practitioner MUE: units per day
- Same-day E/M held unless a significant, separately identifiable E/M is documented (global period)
- Modifier considerations (never assigned): distinct lesions or sites within one endoscopic family (59/XS, NCCI not connected), incomplete examination (52/53, payer rule not connected), screening that became therapeutic (PT/33, payer rule not connected)
- Radiological supervision and interpretation is a separate service; where the document attributes it to a radiologist it is not the endoscopist's
**Clarification questions (asked together, when not documented):**
- `cannulation`: Was the intended duct cannulated, and which interventions were done?
**Not separately reported (internal profile rules):**
- `cannulation`: Cannulation and contrast injection are part of the ERCP itself.
- `injection`: Contrast injection during ERCP is part of the examination.
- `clip`: A clip placed prophylactically, with no bleeding treated, is not reported as a separate service; a clip that treats bleeding is read as bleeding control (internal profile rule).

## Capsule endoscopy (small bowel, esophagus, colon) — supported

**Required documentation:**
- the capsule study and its segment (small bowel, esophagus or colon)
- the physician interpretation and report
- recording completeness (whether the capsule reached the colon / was excreted)
**Verification evidence:**
- the capsule study and its interpretation by the physician on the date of service
**Rule checks:**
- CMS PFS PC/TC indicator: in a facility setting the professional component is reported with modifier 26 (consideration from the connected PFS file; never assigned)
- CMS practitioner MUE
**Clarification questions (asked together, when not documented):**
- `interpretation`: Who interpreted the capsule recording, and on which date?

## Motility and manometry (esophageal, gastric, duodenal, colonic) — supported

**Required documentation:**
- which study (esophageal manometry, antroduodenal, colonic)
- the recording and the physician interpretation
- provocative stimulation or perfusion, when done
**Verification evidence:**
- the study performed and interpreted on the date of service
**Rule checks:**
- CMS PFS PC/TC indicator (modifier 26 consideration in a facility setting)
- CMS practitioner MUE
**Clarification questions (asked together, when not documented):**
- `interpretation`: Who interpreted the study, and was it a complete recording?

## pH and impedance monitoring — supported

**Required documentation:**
- the method (catheter pH, wireless pH capsule, impedance)
- the recording duration
- the physician interpretation
**Verification evidence:**
- the recording and its interpretation
**Rule checks:**
- CMS PFS PC/TC indicator (modifier 26 consideration in a facility setting)
- CMS practitioner MUE
**Clarification questions (asked together, when not documented):**
- `method`: Which method was used (catheter pH, wireless pH capsule, impedance) and for how long?
**Not separately reported (internal profile rules):**
- `capsule_study`: A wireless pH capsule is part of the pH study, not a capsule endoscopy.

## Anorectal testing (manometry, sensation and compliance) — supported

**Required documentation:**
- anorectal manometry
- rectal sensation, tone and compliance testing
- the physician interpretation
**Verification evidence:**
- each test performed and interpreted on the date of service
**Rule checks:**
- CMS PFS PC/TC indicator (modifier 26 consideration in a facility setting)
- CMS practitioner MUE
**Clarification questions (asked together, when not documented):**
- `interpretation`: Which anorectal tests were performed and interpreted?
**Unsupported within the family:**
- `balloon_expulsion`: A balloon expulsion test has no profiled code of its own here; it is listed for the reviewer.

## Feeding-tube procedures (gastrostomy and jejunostomy placement and replacement) — supported

**Required documentation:**
- placement or replacement
- the route (endoscopic, percutaneous with imaging, bedside replacement)
- whether the tract needed revision
**Verification evidence:**
- the placement or replacement on the date of service, and its route
**Rule checks:**
- CMS PFS presence and status for the date
- CMS practitioner MUE
**Notes:**
- A PEG placed during an EGD is reconciled under the upper GI family (its own EGD code).
**Clarification questions (asked together, when not documented):**
- `route`: Was the tube placed endoscopically, percutaneously with imaging, or replaced at the bedside, and was the tract revised?

## Moderate sedation by the performing physician — recognised

**Required documentation:**
- who provided sedation (the endoscopist, or a separate anesthesia professional)
- intraservice time when the endoscopist provided moderate sedation
**Notes:**
- Anesthesia by a separate professional is that professional's service and is never coded for the endoscopist; moderate sedation is recognised and listed, not reconciled.

## Other GI services (anoscopy, hemorrhoid banding, rigid proctosigmoidoscopy, liver biopsy, paracentesis, breath tests, elastography) — recognised

**Notes:**
- Recognised and listed for review; no service profile reconciles them in this release.

## Named unsupported services — unsupported

**Notes:**
- Endoscopic submucosal dissection (ESD): no code profile in this catalogue; no code is proposed or checked for it, and a coder decides how it is reported (the CPT code set is not connected)
- Endoscopic suturing and endoscopic bariatric procedures (sleeve gastroplasty): not profiled
- EUS-guided drainage other than of a pseudocyst (biliary, gallbladder, gastroenterostomy): not profiled
- Gastric peroral endoscopic myotomy (G-POEM) and flexible Zenker diverticulotomy: not profiled
- Endoscopic necrosectomy: not profiled
- Anal and pelvic-floor EMG, biofeedback: outside the GI code ranges profiled here
- Unlisted GI procedures (43499, 43999, 44799, 45399, 91299): unlisted codes are never reconciled
