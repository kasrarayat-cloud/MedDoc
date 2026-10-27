# CPT Studio GI services corpus (synthetic) — a development corpus and regression guard

**How it is used.** An agent that had not read the product's GI or validation code wrote these 43 documents and
their expectations on 2026-10-27. The documented-service reader was then repaired against them, so this corpus is a
**regression guard, not an accuracy measure**: `tests/test_services_corpus.py` requires every document to keep reading
as it reads at the commit that added it, with the remaining differences from the author's expectations recorded in
`known_differences.json` with their reasons. The live acceptance set is held out separately and is never tuned to.
The expectations are the author's provisional readings, not an independent GI coder's adjudication.


All 43 documents in `documents/` are fictional. Every patient, clinician and facility is invented and marked "(fictional)". `expectations.json` (schema `cpt-studio-services-corpus@1`) records what the author reads each document as documenting. These are the author's provisional expectations, written without reading the product's GI or validation code. They are NOT an independent coder's adjudication. Code numbers appear only inside `provisional_codes`; this README names services in words.

**Conventions used throughout.**
- `services` lists only services documented as done on the date of service. `not_done` and `acts_not_done` list services and acts that are named but negated, planned, historical or cancelled. A history entry that is also performed today appears in both places.
- `acts` contains every distinct act the performing physician documents as done, including acts whose code is bundled into another act's code on that date: pre-stent dilation, sphincterotomy before a stent, forceps sampling of a lesion that is then snared, a decompression tube, and prophylactic closure clips. Bundling is expressed only in `provisional_codes`. Steps that are part of another act's own technique are folded into that act and not listed: the lift injection of an EMR, the submucosal bleb of a POEM or ESD, guidewire passage, and the injection, thermal or clip methods used to stop bleeding (recorded once as `bleeding_control`). Brushings are not biopsies.
- `completion` is set only where the family has a defined endpoint and the document speaks to it. That means the cecum for colonoscopy, beyond the pylorus for an EGD, the cecum for a capsule, deep cannulation for ERCP, and a full upper examination for EUS. Otherwise it is `null`, including office E/M, flexible sigmoidoscopy, enteroscopy, physiology studies, tube replacement, esophagus-only examinations, POEM and limited EUS.
- `attributions` lists another provider's service only when the document says so explicitly (separate anesthesia professional, specimens to a pathology or cytology service, facility billing, radiology interpretation), and only for this date.
- Family choices a reviewer may want to adjudicate: PEG placement during EGD, esophagoscopy, POEM and gastric ESD are modelled as `gi.egd`. An EGD that only carries a limited EUS is one `gi.eus` service, not two.
- `anatomy_includes` is given only where the act's own sentence or table row names the site. A few values are stems (`esophag`, `duoden`, `jejun`, `sigmoid`).

## Documents

**svc-01-em-new-office-mdm.** A new-patient office consultation leveled on MDM. The note states that she has never been seen in the group and states moderate MDM; the content supports that (new undiagnosed problem, three or more data items, prescription management). Bidirectional endoscopy on 2026-11-06 is planned, and the 2019 outside colonoscopy is history, so neither is a service today.

**svc-02-em-established-time.** An established-patient visit leveled on time: 34 total minutes on the date of the encounter. The note says "last seen on 2026-04-21", books a surveillance ileocolonoscopy for 2026-12-03 (planned) and cites a 2024 ileocolonoscopy (historical). The encounter date uses the long-month format. The nursing vaccine is outside the GI families.

**svc-03-em-sparse.** A deliberately thin visit note. It has a service date (10/20/2026), but no place of service, no new/established status, no time and no usable MDM content, so the expectation is a performed office E/M with questions for setting, patient status and E/M basis, and no code.

**svc-04-em-undated.** An established-patient office visit leveled on time (22 minutes) that has no date of service anywhere. The date of birth and a 2026-09-30 laboratory date are present and must not be taken as the service date. Expected: `service_date` null and a `service_date` question.

**svc-05-em25-and-variceal-banding.** One document, two services on 2026-10-14. A hepatology visit manages ascites and encephalopathy and explicitly says it is separate from the pre-procedure assessment, so it is a separately identifiable E/M (modifier consideration 25). It is followed by an EGD with band ligation of esophageal varices. Two earlier banding sessions are historical, the 2026-11-11 session is planned, and "No biopsies were obtained" is a negation. Anesthesia is a CRNA, billed separately.

**svc-06-hp-and-colonoscopy-random-biopsies.** A routine same-day pre-procedure H&P followed by the colonoscopy report. The H&P must NOT produce an office E/M service. The colonoscopy reached the cecum and terminal ileum and took random biopsies from right and left colon in two jars: two biopsy acts, but one biopsy code. Results are pending, anesthesia is by an anesthesiologist, and pathology is an outside group.

**svc-07-em-established-partner-mdm-high.** The author has never met the patient, but a same-specialty partner in the same practice saw her on 2024-05-02, so she is established. MDM is high: a threat to bodily function, independent review of CT images, discussion with an outside surgeon, and a documented decision against hospitalization. EUS with biopsy and ERCP with stent on 2026-10-29 are planned, and the 2024 EGD is historical.

**svc-08-egd-multisite-biopsy-list-negation.** An EGD with biopsies of the esophagus, stomach and duodenum in three containers: three biopsy acts, one biopsy code. It carries the list negation "No EUS, fine-needle sampling, ERCP or dilation was performed", which yields negated EUS and ERCP services and negated dilation and FNA acts. Moderate sedation by the endoscopist with an observer runs 18 minutes, so the initial sedation code only. Pathology is pending.

**svc-09-egd-balloon-dilation-impression-only.** The findings section describes the rings, furrows and biopsies. The through-the-scope balloon dilation of the Schatzki ring appears ONLY in the impression, and it is still a performed act. The proximal and mid esophagus biopsies are a different site from the distal ring, hence a distinct-site modifier consideration on the biopsy code. The 2025 food-bolus removal is a historical foreign-body act. The date uses MM/DD/YYYY.

**svc-10-egd-savary-dilation.** Guidewire-directed bougie (Savary-Gilliard) dilation of a peptic stricture under fluoroscopy run by the GI team, so there is no radiology attribution. The 2023 and 2024 dilations and the 2025 stricture biopsy are historical, "Biopsies were not taken today" is a negation, and the date is written 14-Oct-2026.

**svc-11-egd-ulcer-bleeding-control.** An inpatient EGD for a duodenal ulcer with a visible vessel, treated with epinephrine injection, bipolar coagulation and clips. That is one `bleeding_control` act and one hemostasis code, not separate injection or clip services. Biopsies were deferred (negated, and planned for the repeat EGD in 8-12 weeks). Anesthesia and facility are attributed separately.

**svc-12-egd-peg.** A pull-technique PEG placed during an EGD, recorded as an EGD with a `peg` act. Moderate sedation runs 24 minutes, so the initial code plus one additional unit. It has check-box lines, including "Biopsy [ ] Performed [X] Not performed". The word "snare" appears only for grasping the guidewire and must not become a snare removal. The 2019 PEG is historical.

**svc-13-tne-barrett-biopsy.** An unsedated office transnasal esophagoscopy with Seattle-protocol biopsies at three levels: one biopsy act, the esophagoscopy code range. The examination is explicitly confined to the esophagus. The 2022 and 2024 endoscopies are historical. "Endoscopic ablation is not indicated at this time" is a negated ablation. The conditional "next surveillance in three to five years" is not listed as planned.

**svc-14-esophagoscopy-stricture-not-traversed.** A planned EGD stopped by an obstructing esophageal mass: the stomach and duodenum were not examined. It is recorded as an incomplete `gi.egd` whose rendered service is a transoral esophagoscopy with biopsy (with an alternative reduced-EGD reading noted). "Dilation was not attempted" is a negation, and staging EUS on 2026-10-30 is planned.

**svc-15-egd-rfa-barrett.** Circumferential and focal radiofrequency ablation of a Barrett's segment with low-grade dysplasia in one session: one ablation act, one ablation code. "No biopsies were obtained today" is a negation, the 2026-07-08 biopsies are historical, and the next ablation session in about three months is planned. Anesthesia is separate.

**svc-16-egd-esophageal-stent.** Palliative covered metal stent for a malignant stricture after balloon pre-dilation to 12 mm. Both acts are listed, but the dilation and guidewire passage are bundled into the stent code. Fluoroscopy was run by the endoscopy team. General anesthesia and facility billing are attributed to others.

**svc-17-poem.** Peroral endoscopic myotomy for type II achalasia. The acts are the myotomy and the closure clips; the clips are integral and do not count as control of bleeding. "No fundoplication was performed" is a negation. The 2026-08-20 manometry, the 2023 pneumatic dilation and the 2024 botulinum injection are history and must not be coded.

**svc-18-colo-snare-plus-separate-biopsy-table.** Word-like " | " tables. Lesion 1 (transverse colon) was removed by hot snare. Lesion 2, a SEPARATE rectal polyp, was removed with cold biopsy forceps, which is coded as a biopsy. So: snare code plus biopsy code with a distinct-lesion modifier consideration. It also contains the phrase "No other biopsies were taken" and a 2021 surveillance history.

**svc-19-colo-biopsy-then-snare-same-lesion.** Forceps samples were taken from the head of an 18 mm sigmoid polyp, and the SAME polyp was then removed by hot snare. Both acts carry lesion L1, but only the snare code is expected. Results are pending and the date is written "October 13, 2026".

**svc-20-colo-cold-hot-snare-hot-biopsy.** Three lesions: a hot biopsy forceps removal (cecum), a hot snare (descending) and a cold snare (sigmoid). Hot and cold snare share one snare code, and hot biopsy forceps is its own act and code, with a distinct-lesion modifier consideration. The screening indication adds a screening modifier consideration. Moderate sedation runs 31 minutes, so the initial code plus one additional unit.

**svc-21-colo-emr-tattoo-clips-nursing-conflict.** Piecemeal EMR after a submucosal lift, prophylactic clips, and a distal tattoo by the physician. The physician narrative documents the tattoo, but the nursing checklist reads "Tattoo injection [ ] Performed [X] Not performed", so the tattoo is both an act (physician authority) and a conflict. The lift is part of the EMR, while the tattoo is a separate injection (modifier consideration). The clips are prophylactic, and the checklist also says no hemostasis. The outside colonoscopy is historical, and six-month surveillance is planned.

**svc-22-colo-incomplete-poor-prep.** The colonoscopy was stopped at the hepatic flexure for solid stool and the cecum was not reached, so the service is incomplete. This is a diagnostic colonoscopy with a discontinued-procedure modifier consideration. The repeat on 2026-11-12 is planned, the 2020 cold-snare polypectomy is historical, and "No biopsies were taken" is a negation.

**svc-23-colo-incomplete-obstruction.** A near-obstructing sigmoid mass stopped both adult and pediatric colonoscopes. The mass was biopsied and tattooed distally, so these are therapeutic acts on an incomplete colonoscopy (reduced-service modifier consideration on each). Completion colonoscopy after resection is planned.

**svc-24-colo-screening-complete-not-discontinued.** A normal screening colonoscopy to the terminal ileum that contains the trap phrases "The procedure was not discontinued; it was completed without interruption". These must not trigger an incomplete or discontinued reading. Biopsy and snare are negated, and the 10-year repeat is planned. Moderate sedation runs 21 minutes, so the initial code only.

**svc-25-colo-screening-to-therapeutic-extent-missing.** A Medicare screening that became therapeutic: two cold-snare polypectomies, one snare code, and a screening-converted modifier consideration. The report never states how far the colonoscope was advanced (no cecum, landmarks or terminal ileum), so `completion` is null and `extent` is a question. "More than ten years ago" is an undated historical colonoscopy.

**svc-26-colo-lst-referred-for-emr.** A structured check-box report. A 35 mm laterally spreading lesion was NOT resected ("Removed today: [ ] Yes [X] No") and was deliberately not biopsied. It was tattooed ("Tattoo injection [X] Performed"), and EMR is planned at another unit for 2026-11-17. Only the tattoo is coded today.

**svc-27-flexsig-biopsy-impression-only.** An unsedated flexible sigmoidoscopy for proctosigmoiditis. The findings section never mentions sampling; the biopsies of the rectum and sigmoid colon appear only in the impression, and they are still performed. That gives two biopsy acts and one sigmoidoscopy biopsy code.

**svc-28-flexsig-hemorrhoid-banding-nursing-conflict.** An office flexible sigmoidoscopy with band ligation of three internal hemorrhoid columns: one band-ligation act and one code. The physician writes "No biopsies were obtained", but the nursing record checks "Specimen collected [X] Yes" with a rectum label, so biopsy is negated by the physician and listed as a conflict. The 2023 colonoscopy and the office anoscopy are history.

**svc-29-flexsig-volvulus-decompression.** Inpatient detorsion and decompression of a sigmoid volvulus with a decompression tube placed over a guidewire. Both acts are listed, and the tube is bundled into the decompression code. The 2025 endoscopic decompression is historical. Biopsy and tattoo are negated, and the facility is attributed.

**svc-30-eus-pancreas-fnb-node-not-sampled.** A full upper EUS (esophagus, stomach, bulb and second portion) with FNB of a pancreatic head mass. That is one sampling act, on lesion L1. A peripancreatic lymph node "was not sampled": the negated FNA in `acts_not_done` refers to that node, not the mass. Celiac plexus neurolysis is a negated injection, and the phrase "completed without interruption" appears. ERCP with stent on 2026-10-21 is planned, and the 2023 EGD is historical. Rapid on-site cytopathology is a separate pathology service.

**svc-31-eus-limited-esophageal-wall.** An EGD to the duodenum, then a radial EUS limited to the esophageal wall: one limited-EUS service that includes the endoscopic portion. `completion` is null because the exam was limited by design. "FNA was not performed" is a negation. Moderate sedation runs 19 minutes, so the initial code only. The outside upper endoscopy is undated history.

**svc-32-ercp-sphincterotomy-stone-extraction.** Deep biliary cannulation, sphincterotomy and balloon stone extraction, so two therapeutic codes. Fluoroscopy is interpreted by radiology, which is the radiology attribution. "No stent was placed" is a negation, and the 2024 EUS is historical.

**svc-33-ercp-biliary-stent-brushing.** Biliary sphincterotomy, brush cytology and a covered metal stent across a malignant stricture. Same-duct sphincterotomy is bundled into the stent code, and brushings are part of the ERCP, not a biopsy ("No biopsy forceps were used" is a negated biopsy). The outside EUS-guided biopsy is historical. Fluoroscopy is read by the endoscopist this time, so there is no radiology attribution.

**svc-34-ercp-failed-cannulation.** Deep biliary cannulation failed beside a periampullary diverticulum, so the ERCP is incomplete and has no therapeutic acts. The list negation "No sphincterotomy, stent placement or stone extraction was performed" applies, along with the unattempted precut and the unplaced pancreatic stent. A repeat ERCP or EUS-guided rendezvous on 2026-11-02 is planned. The diagnostic code carries a reduced or discontinued modifier consideration.

**svc-35-push-enteroscopy-apc.** A push enteroscopy about 70 cm into the jejunum with APC of five NON-bleeding angioectasias. That is ablation, not control of bleeding, with one unit for all lesions. The 2026-09-14 capsule and the 2026-08-05 bidirectional endoscopy are history. The conditional deep enteroscopy is not listed as planned.

**svc-36-balloon-enteroscopy-apc-biopsy-table.** The second Word-like table document. An antegrade double-balloon enteroscopy to the mid jejunum (ileum not reached) treated two angioectasias with APC (L1, L2) and biopsied a separate nodule (L3). That gives an ablation code plus a biopsy code with a distinct-lesion modifier consideration. "No tattoo was placed" is a negation, and the earlier capsule study is undated history.

**svc-37-capsule-small-bowel.** Small-bowel capsule endoscopy with physician review and report. The capsule reached the cecum, so `completion` is complete. Mixed dates: the date of service is the ingestion date (2026-10-13), the reading was 2026-10-14, and push enteroscopy with APC on 2026-10-28 is planned. The hospital owns the equipment and reports the technical component, hence a professional-component modifier consideration.

**svc-38-bravo-96h.** Wireless pH capsule placed transorally without endoscopy ("No EGD was performed with this placement" is a negated EGD), followed by a 96-hour recording. It is one reflux service dated at placement (2026-10-05), not at report signing (2026-10-12). The 2026-09-28 manometry used to locate the sphincter is a historical motility study. The surgeon's possible fundoplication is outside the GI families and is not listed.

**svc-39-hrm-and-ph-impedance.** Two services on one date: high-resolution esophageal manometry, then a 24-hour catheter pH-impedance study whose recording ended the next day. That gives manometry and prolonged impedance-pH codes.

**svc-40-hrm-achalasia-poem-planned.** An HRM diagnosing type II achalasia. POEM on 2026-11-18 is planned (a planned myotomy act under `gi.egd`). Pneumatic dilation was discussed and declined (negated or cancelled). The 2026-10-03 barium esophagram is a prior radiology study, so there is no radiology attribution for this date.

**svc-41-anorectal-manometry-bet.** High-resolution anorectal manometry plus graded-balloon rectal sensation and compliance testing and a balloon expulsion test, giving manometry and rectal-sensation acts. Pairing the two codes is flagged as payer-dependent. The balloon expulsion test has no code of its own, and biofeedback is only a referral.

**svc-42-gtube-bedside-replacement.** Inpatient bedside replacement of a dislodged balloon gastrostomy tube through a mature tract, confirmed by aspirating gastric contents, with no imaging, no endoscopy and no tract revision. The 2025 endoscopic PEG and the September 2025 exchange are historical.

**svc-43-egd-gastric-esd.** En bloc gastric ESD under general anesthesia. ESD has no specific CPT code, so `unsupported` is `["esd"]` and no code is asserted. The coagulation marking dots are not ablation. Coagulation of small vessels during dissection is not bleeding control: "no active bleeding requiring treatment" is a negated `bleeding_control`, and "no clips were placed" is a negated clip. The 2026-08-14 outside biopsies are historical. Anesthesia, pathology and facility are attributed.

## Coverage matrix

| Row | Documents |
|---|---|
| Office/outpatient E/M | svc-01 (new, MDM), svc-02 (established, time, last seen, planned), svc-03 (sparse), svc-04 (no date), svc-05 (separate E/M on procedure day), svc-06 (routine H&P only), svc-07 (established via partner, high MDM, last seen, planned) |
| EGD / esophagoscopy | svc-08 (multi-site biopsy), svc-09 (balloon dilation), svc-10 (Savary), svc-05 (variceal banding), svc-11 (bleeding control), svc-12 (PEG), svc-13 (transnasal), svc-14 (transoral esophagoscopy) |
| Colonoscopy | svc-18 (snare + separate-lesion biopsy), svc-19 (biopsy then snare, same lesion), svc-20 and svc-25 (hot vs cold snare), svc-21 (EMR with lift), svc-21/23/26 (tattoo), svc-22 and svc-23 (incomplete) vs svc-24 (complete, not discontinued), svc-25 and svc-20 (screening became therapeutic), svc-26 (referred for later EMR), svc-06 (random biopsies) |
| Flexible sigmoidoscopy | svc-27 (biopsy), svc-28 (band ligation), svc-29 (decompression) |
| EUS | svc-30 (full, FNB, node not sampled), svc-31 (limited, no sampling) |
| ERCP | svc-32 (sphincterotomy + stone extraction), svc-33 (stent), svc-34 (failed cannulation) |
| Enteroscopy | svc-35 (push, APC), svc-36 (balloon-assisted, APC) |
| Capsule and physiology | svc-37 (capsule), svc-38 (wireless pH 96 h), svc-39 (pH-impedance + HRM), svc-40 (HRM), svc-41 (anorectal manometry, sensation/compliance, balloon expulsion) |
| Feeding tube | svc-42 (bedside replacement without imaging), svc-12 (PEG during EGD) |
| Advanced treatments | svc-17 (POEM), svc-15 (RFA), svc-16 (esophageal stent), svc-43 (ESD, unsupported) |
| Cross-cutting traps | list negation svc-08, svc-34; not discontinued / without interruption svc-24, svc-30; "No other biopsies were taken" svc-18; mixed dates svc-01, svc-02, svc-07, svc-37, svc-38; pending pathology svc-06, svc-08, svc-13, svc-18, svc-19; nursing conflict svc-21, svc-28; separate anesthesia, pathology, facility and radiology across many documents (radiology in svc-32); historical procedure in history svc-10, svc-17, svc-35 and others; performed only in impression svc-09, svc-27; " | " tables svc-18, svc-36 |
