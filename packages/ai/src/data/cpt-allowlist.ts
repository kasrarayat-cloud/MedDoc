// ============================================================================
// Round 3 PR-D — CPT allowlist (audit A06-P0-002)
// ----------------------------------------------------------------------------
// Closes the same False Claims Act vector the ICD-10 allowlist closes, on
// the procedure-coding side. The 07b-cpt-coding layer's validator drops
// codes not in this list and emits CODING_COACH_REJECTED_INVALID_CPT.
//
// SCOPE LIMITATION (intentional for pre-pilot)
// --------------------------------------------
// CPT codes are AMA-licensed for commercial redistribution. Shipping the
// full CPT canonical list in this repo would require an AMA agreement
// that we don't yet have at pre-pilot scale. This file is a HAND-CURATED
// top-N covering the M5 specialties (E&M, common procedures, vaccines,
// modifiers).
//
// Codes here are common-knowledge (publicly documented in CMS PFS RVU
// files, AAPC public references, MedicareNCD lookup, etc). The allowlist
// is therefore safe to ship pre-pilot without an AMA license, while
// providing the same fail-closed safety floor.
//
// PHASE 7 PATH: AMA license + swap this file for a full CPT canonical
// set OR rely on the CMS PFS RVU file (which contains the codes that
// have RVUs assigned, ~95% of E&M and procedures). Validator API stays
// the same.
// ============================================================================

const STARTER_CPT_CODES: ReadonlyArray<string> = [
  // === E&M — Office / Outpatient — established patient ===
  '99211', // Min, no/min presenting problem
  '99212', // Self-limited / minor (10 min)
  '99213', // Low-moderate (15 min)
  '99214', // Moderate (25 min)
  '99215', // High (40 min)

  // === E&M — Office / Outpatient — new patient ===
  '99202', // Straightforward (15 min)
  '99203', // Low (30 min)
  '99204', // Moderate (45 min)
  '99205', // High (60 min)

  // === E&M — Inpatient/observation — initial ===
  '99221', // Low MDM (40 min)
  '99222', // Moderate MDM (55 min)
  '99223', // High MDM (75 min)

  // === E&M — Inpatient/observation — subsequent ===
  '99231', // Low MDM (25 min)
  '99232', // Moderate MDM (35 min)
  '99233', // High MDM (50 min)

  // === E&M — ER ===
  '99281', // Minimal
  '99282', // Low
  '99283', // Moderate
  '99284', // High
  '99285', // High complexity (life/limb threat)

  // === E&M — Critical care ===
  '99291', // Critical care, first 30-74 min
  '99292', // Critical care, each additional 30 min

  // === E&M — Preventive ===
  '99381', // Preventive, new pt, infant
  '99382', // Preventive, new pt, age 1-4
  '99383', // Preventive, new pt, age 5-11
  '99384', // Preventive, new pt, age 12-17
  '99385', // Preventive, new pt, age 18-39
  '99386', // Preventive, new pt, age 40-64
  '99387', // Preventive, new pt, 65+
  '99391', // Preventive, est pt, infant
  '99392', // Preventive, est pt, age 1-4
  '99393', // Preventive, est pt, age 5-11
  '99394', // Preventive, est pt, age 12-17
  '99395', // Preventive, est pt, age 18-39
  '99396', // Preventive, est pt, age 40-64
  '99397', // Preventive, est pt, 65+

  // === Telephone / online ===
  '99441', // Telephone E&M, 5-10 min (legacy)
  '99442', // Telephone E&M, 11-20 min (legacy)
  '99443', // Telephone E&M, 21-30 min (legacy)

  // === Psychiatry / behavioral health ===
  '90791', // Psychiatric diagnostic eval (no medical services)
  '90792', // Psychiatric diagnostic eval with medical services
  '90832', // Psychotherapy 30 min
  '90834', // Psychotherapy 45 min
  '90837', // Psychotherapy 60 min
  '90846', // Family psychotherapy without patient
  '90847', // Family psychotherapy with patient
  '96127', // Brief emotional / behavioral assessment
  '96130', // Psychological testing eval, first hour
  '96131', // Psychological testing eval, each addl hour
  '96136', // Psych test admin/scoring, first 30 min
  '96137', // Psych test admin/scoring, each addl 30 min

  // === Vaccines + administration ===
  '90460', // Immunization admin first/only component, age <= 18
  '90461', // Immunization admin each addl component, age <= 18
  '90471', // Immunization admin one vaccine
  '90472', // Immunization admin each addl vaccine
  '90686', // Influenza vaccine, quadrivalent IIV4
  '90715', // Tdap vaccine
  '90734', // Meningococcal MCV4
  '90740', // Hep B vaccine

  // === Common labs / point-of-care ===
  '36415', // Routine venipuncture
  '81002', // Urinalysis dip-stick (non-auto)
  '81003', // Urinalysis dip-stick automated
  '85027', // Complete CBC, automated
  '85610', // Prothrombin time
  '99173', // Visual acuity screening
  '94010', // Spirometry
  '94060', // Bronchodilation responsiveness
  '93000', // ECG with interpretation/report
  '93005', // ECG, tracing only
  '93010', // ECG, interpretation/report only

  // === Behavioral / SDOH screening (HEDIS-aligned) ===
  '96160', // Health risk assessment instrument
  '96161', // Caregiver-focused health risk assessment

  // === Office procedures (most common in family/IM) ===
  '11042', // Debridement, subq tissue, first 20 cm²
  '11043', // Debridement, muscle/fascia, first 20 cm²
  '11055', // Paring/cutting of benign hyperkeratotic lesion (1)
  '17000', // Destruction premalignant lesion (1)
  '17110', // Destruction benign lesion (up to 14)
  '17111', // Destruction benign lesion (15+)
  '69210', // Cerumen removal, one or both ears

  // === Ortho / MSK ===
  '20550', // Injection tendon sheath/ligament
  '20551', // Injection tendon origin/insertion
  '20552', // Injection trigger point, 1-2 muscles
  '20553', // Injection trigger point, 3+ muscles
  '20600', // Arthrocentesis, small joint
  '20605', // Arthrocentesis, intermediate joint
  '20610', // Arthrocentesis, major joint

  // === Bariatric Surgery (2026-05-12) — laparoscopic + open ===
  // Captures the procedure codes a bariatric surgeon would bill on the
  // operative day. Added with the `bariatric-surgery` specialty so the
  // L7b validator accepts these instead of dropping them as "not in
  // allowlist." Open codes carried because revisional / complication
  // cases routinely convert from lap to open.
  '43644', // Laparoscopic Roux-en-Y gastric bypass (RYGB), with ≤ 150 cm Roux limb
  '43645', // Laparoscopic RYGB with small intestine reconstruction for malabsorption
  '43775', // Laparoscopic sleeve gastrectomy
  '43770', // Laparoscopic adjustable gastric band, placement
  '43771', // Adjustable gastric band, revision
  '43772', // Adjustable gastric band, removal of subcutaneous port only
  '43773', // Adjustable gastric band, removal and replacement of subcutaneous port only
  '43774', // Adjustable gastric band, removal (entire device, complete)
  '43842', // Open vertical-banded gastroplasty
  '43843', // Open gastric restrictive procedure NEC
  '43845', // Open biliopancreatic diversion with duodenal switch (BPD-DS)
  '43846', // Open Roux-en-Y gastric bypass (≤ 150 cm Roux limb)
  '43847', // Open RYGB with small intestine reconstruction for malabsorption
  '43848', // Revision, open, of bariatric bypass procedure
  '43886', // Gastric restrictive procedure, open; revision of subcutaneous port
  '43887', // Gastric restrictive procedure, open; removal of subcutaneous port
  '43888', // Gastric restrictive procedure, open; removal and replacement of subcutaneous port

  // === Vascular Surgery (2026-05-12) — full scope ===
  // Added with the `vascular-surgery` specialty. Covers endovascular
  // peripheral (372xx), EVAR / TEVAR (347xx, 33880-33891), open
  // vascular (35xxx), carotid intervention (37215-37218), endovenous
  // (RFA / EVLT / sclero), AV fistula creation + maintenance, selective
  // catheter placement, noninvasive vascular diagnostics (939xx), and
  // inpatient E&M (99221-99239) that vascular surgery routinely bills
  // for in-hospital post-op management.

  // ── Inpatient E&M discharge (99221-99233 already present above) ──
  '99238', // Hospital discharge day management ≤ 30 minutes
  '99239', // Hospital discharge day management > 30 minutes

  // ── Endovascular peripheral arterial (372xx) ──
  '37220', // Iliac angioplasty
  '37221', // Iliac stent placement
  '37222', // Each additional iliac territory, angioplasty
  '37223', // Each additional iliac territory, stent
  '37224', // Femoral / popliteal angioplasty
  '37225', // Femoral / popliteal angioplasty with atherectomy
  '37226', // Femoral / popliteal stent
  '37227', // Femoral / popliteal stent with atherectomy
  '37228', // Tibial / peroneal angioplasty
  '37229', // Tibial / peroneal angioplasty with atherectomy
  '37230', // Tibial / peroneal stent
  '37231', // Tibial / peroneal stent with atherectomy
  '37236', // Transcatheter placement of intravascular stent(s), arterial
  '37237', // Each additional stent
  '37238', // Transcatheter placement of intravascular stent(s), venous
  '37239', // Each additional venous stent
  '37252', // IVUS, initial non-coronary vessel
  '37253', // IVUS, each additional non-coronary vessel

  // ── Carotid intervention ──
  '37215', // Transcatheter placement of stent(s), cervical carotid, with distal embolic protection
  '37216', // Same, without distal embolic protection
  '37217', // Transcatheter placement of stent(s), intrathoracic common carotid or innominate, retrograde
  '37218', // Same, intrathoracic common carotid or innominate, antegrade

  // ── EVAR / TEVAR ──
  '34701', // EVAR, infrarenal aorta, percutaneous
  '34702', // EVAR, infrarenal aorta with iliac extension, percutaneous
  '34703', // EVAR, infrarenal aorta, open
  '34704', // EVAR, infrarenal aorta with iliac extension, open
  '34705', // EVAR, infrarenal aorta with aorto-uni-iliac configuration
  '34706', // EVAR, infrarenal aorta + femoral-femoral bypass
  '34707', // Ipsilateral iliac endoprosthesis with aorto-uni-iliac configuration
  '34708', // Contralateral iliac endograft extension
  '34709', // Placement of extension prosthesis for endoleak / migration
  '34710', // Each additional secondary extension
  '34711', // Each additional secondary stent
  '34712', // Percutaneous access closure, large-bore (sheath ≥ 12F)
  '34714', // Fenestrated EVAR with renal/visceral artery endoprostheses, 1-3 vessels
  '34715', // Same, 4+ vessels
  '34716', // Iliac branch endoprosthesis
  '34717', // Iliac branch with internal iliac endoprosthesis
  '34718', // Fenestrated visceral aortic endoprosthesis, juxta- or pararenal
  '33880', // TEVAR thoracic descending aorta, distal subclavian to celiac
  '33881', // TEVAR thoracic descending aorta, not involving zone 0-2
  '33883', // TEVAR proximal extension prosthesis
  '33884', // TEVAR proximal extension, each additional
  '33886', // TEVAR placement of distal extension
  '33889', // Open subclavian-to-carotid transposition for TEVAR
  '33891', // Bypass-graft from carotid to subclavian for TEVAR

  // ── Open vascular — aortic, iliac, carotid, peripheral ──
  '35081', // Open AAA repair, infrarenal aorta
  '35082', // Open AAA repair for ruptured AAA, infrarenal aorta
  '35091', // Open AAA repair, aorto-iliac
  '35092', // Open AAA repair for ruptured aorto-iliac AAA
  '35102', // Open AAA repair, suprarenal / juxtarenal
  '35103', // Open AAA repair for ruptured suprarenal / juxtarenal
  '35131', // Open iliac aneurysm repair, common iliac
  '35141', // Open iliac aneurysm repair, internal iliac
  '35211', // Open vascular repair, carotid (intracranial occlusion / aneurysm)
  '35221', // Open vascular repair, intra-abdominal vessels other than aorta
  '35226', // Open vascular repair, blood vessel of lower extremity
  '35256', // Open repair of femoral / popliteal aneurysm
  '35286', // Open repair of artery of lower extremity, other
  '35301', // Carotid endarterectomy (CEA)
  '35302', // CEA with contralateral CEA same operative session
  '35311', // Endarterectomy, subclavian / innominate
  '35321', // Endarterectomy, axillary-brachial
  '35331', // Endarterectomy, aortoiliac
  '35341', // Endarterectomy, iliofemoral
  '35351', // Endarterectomy, aortoiliofemoral
  '35361', // Endarterectomy, femoral
  '35363', // Endarterectomy, deep femoral (profunda)
  '35371', // Endarterectomy, popliteal
  '35372', // Endarterectomy, tibial
  '35381', // Endarterectomy, tibioperoneal trunk
  '35460', // Transluminal balloon angioplasty, open, of artery of the abdomen
  '35480', // Atherectomy, open, of artery of the abdomen
  '35481', // Atherectomy, open, of artery of the lower extremity
  '35482', // Atherectomy, open, of artery of the upper extremity
  '35483', // Atherectomy, open, other artery
  '35490', // Atherectomy, percutaneous, of artery of the abdomen
  '35491', // Atherectomy, percutaneous, of artery of the lower extremity
  '35495', // Atherectomy, percutaneous, of artery of the upper extremity

  // ── Open vascular bypass (35501-35672 family — common ones) ──
  '35501', // Bypass graft, common carotid-vertebral
  '35506', // Carotid-subclavian bypass
  '35508', // Carotid-axillary bypass
  '35511', // Subclavian-subclavian bypass
  '35515', // Subclavian-vertebral bypass
  '35525', // Brachial-brachial bypass
  '35526', // Aortosubclavian / aortoinnominate / aortocarotid bypass
  '35531', // Aortoceliac / aortomesenteric / aortorenal bypass
  '35536', // Splenorenal bypass
  '35541', // Aortoiliac / aortobifemoral / aortobi-iliac bypass
  '35546', // Aortofemoral / aortobifemoral bypass
  '35551', // Aortofemoral-popliteal bypass
  '35556', // Femoral-popliteal bypass with vein
  '35566', // Femoral-tibial / tibial-popliteal bypass with vein
  '35571', // Popliteal-tibial / tibial-tibial bypass with vein
  '35583', // Saphenous vein in situ, femoral-popliteal
  '35585', // Saphenous vein in situ, femoral-tibial
  '35587', // Saphenous vein in situ, popliteal-tibial
  '35601', // Axillary-femoral / axillary-axillary bypass
  '35612', // Axillary-femoral-femoral bypass
  '35621', // Axillary-femoral bypass with prosthetic graft
  '35623', // Bypass, with prosthetic graft, of subclavian-axillary
  '35631', // Aortoceliac / aortomesenteric bypass with prosthetic graft
  '35641', // Aortoiliac / aortobifemoral bypass with prosthetic graft
  '35646', // Aortofemoral bypass with prosthetic graft
  '35651', // Femoral-popliteal bypass with prosthetic graft
  '35654', // Femoral-femoral cross-over bypass
  '35656', // Femoral-femoral / fem-pop with prosthetic graft
  '35661', // Femoral-tibial bypass with prosthetic graft
  '35666', // Popliteal-tibial bypass with prosthetic graft
  '35671', // Tibial-tibial / tibial-peroneal bypass with prosthetic graft
  '35672', // Tibial-pedal bypass with prosthetic graft
  '35761', // Open ligation of inferior vena cava
  '37607', // Ligation of carotid artery

  // ── Open venous + endovenous (vein care) ──
  '37700', // Ligation of saphenofemoral junction
  '37718', // Ligation, division, and stripping, short saphenous vein
  '37722', // Ligation, division, and stripping, long (greater) saphenous vein
  '37735', // Ligation and division and complete stripping of long or short saphenous veins with radical excision of ulcer
  '37761', // Ligation of perforator veins, open
  '37765', // Stab phlebectomy of varicose veins, 10-20 incisions
  '37766', // Stab phlebectomy of varicose veins, > 20 incisions
  '37780', // Ligation and division of short saphenous vein at sapheno-popliteal junction
  '36465', // Injection of non-compounded foam sclerosant
  '36466', // Injection of non-compounded foam sclerosant, multiple veins
  '36468', // Single or multiple injections of sclerosing solutions, spider veins
  '36471', // Injection of sclerosing solution, reticular veins
  '36475', // Endovenous ablation of incompetent vein by radiofrequency, first vein
  '36476', // Each additional vein, RFA
  '36478', // Endovenous ablation of incompetent vein by laser, first vein
  '36479', // Each additional vein, EVLT
  '36482', // Endovenous ablation of incompetent vein by chemical adhesive (e.g. cyanoacrylate), first vein
  '36483', // Each additional vein, MOCA / chemical adhesive

  // ── AV fistula + dialysis access ──
  '36818', // AV anastomosis, open, by upper arm cephalic vein transposition
  '36819', // AV anastomosis, open, by upper arm basilic vein transposition
  '36820', // AV anastomosis, open, by forearm vein transposition
  '36821', // AV anastomosis, open, direct (e.g. Cimino fistula)
  '36823', // Insertion of arterial and venous cannula(e) for extracorporeal circulation
  '36825', // Creation of AV fistula by other than direct AV anastomosis, autogenous graft
  '36830', // Creation of AV fistula by other than direct AV anastomosis, nonautogenous graft (PTFE)
  '36831', // Thrombectomy, open, AV fistula (without revision)
  '36832', // Revision, open, AV fistula (without thrombectomy)
  '36833', // Revision, open, AV fistula with thrombectomy
  '36901', // Diagnostic dialysis-circuit fistulogram
  '36902', // Same, with transluminal balloon angioplasty
  '36903', // Same, with stent placement
  '36904', // Percutaneous transluminal mechanical thrombectomy / infusion for thrombolysis, dialysis circuit
  '36905', // Same, with transluminal balloon angioplasty
  '36906', // Same, with stent placement
  '36907', // Transluminal balloon angioplasty, central dialysis segment
  '36908', // Stent placement, central dialysis segment
  '36909', // Embolization, percutaneous, of dialysis-circuit branch vessels

  // ── Selective catheter placement ──
  '36223', // Selective catheter placement, common carotid or innominate (with cervicocerebral angio)
  '36224', // Selective catheter placement, internal carotid (with cerebral angio)
  '36225', // Selective catheter placement, subclavian or innominate (with vertebral angio)
  '36245', // Selective catheter placement, arterial, first order, abdominal / pelvic / LE
  '36246', // Same, second-order branch
  '36247', // Same, third-order branch
  '36248', // Each additional second- or third-order selective placement
  '36251', // Selective renal artery catheter placement, unilateral
  '36252', // Same, bilateral
  '36253', // Selective renal artery catheter placement with renal angiography, unilateral
  '36254', // Same, bilateral

  // ── Diagnostic noninvasive vascular (939xx) ──
  '93875', // Cerebrovascular bilateral noninvasive physiologic, complete
  '93880', // Duplex scan of extracranial arteries, complete bilateral study
  '93882', // Duplex scan of extracranial arteries, unilateral or limited
  '93922', // Noninvasive physiologic studies of upper or lower extremity arteries, single level
  '93923', // Same, complete bilateral, multiple levels
  '93924', // Noninvasive physiologic studies, bilateral, with exercise stress testing
  '93925', // Duplex scan of LE arteries, complete bilateral
  '93926', // Same, unilateral or limited
  '93930', // Duplex scan of UE arteries, complete bilateral
  '93931', // Same, unilateral or limited
  '93970', // Duplex scan of extremity veins including responses to compression, complete bilateral
  '93971', // Same, unilateral or limited
  '93975', // Duplex scan of arterial inflow and venous outflow of abdominal, pelvic, scrotal contents, retroperitoneal organs, complete
  '93976', // Same, limited
  '93978', // Duplex scan of aorta, IVC, iliac vasculature, complete
  '93979', // Same, unilateral or limited

  // === Modifiers (tracked separately from codes) ===
  // These are appended to a CPT code (e.g. "99213-25"). The validator
  // accepts a code with or without a trailing "-NN" modifier.
  // See isValidCpt() below — modifier suffix is stripped before lookup.
];

/** Allowlist set — strings preserved as documented (CPT codes are
 *  always five digits; some HCPCS Level II add a letter prefix like
 *  J3490 — those aren't included in this starter set). */
export const CPT_ALLOWLIST: ReadonlySet<string> = new Set(
  STARTER_CPT_CODES.map((c) => c.trim().toUpperCase())
);

/** Common AMA modifiers. Appended to codes via "-NN" suffix; stripped
 *  before allowlist lookup. The list is small + well-known so we
 *  validate them too rather than accept any "-NN". */
const VALID_MODIFIERS: ReadonlySet<string> = new Set([
  '22', // Increased procedural services
  '24', // Unrelated E&M during postop period
  '25', // Significant, separately identifiable E&M same day
  '26', // Professional component
  '27', // Multiple outpatient hospital E&Ms same day
  '32', // Mandated services
  '33', // Preventive service
  '47', // Anesthesia by surgeon
  '50', // Bilateral procedure
  '51', // Multiple procedures
  '52', // Reduced services
  '53', // Discontinued procedure
  '54', // Surgical care only
  '55', // Postop management only
  '56', // Preop management only
  '57', // Decision for surgery
  '58', // Staged/related procedure during postop period
  '59', // Distinct procedural service
  '62', // Two surgeons
  '63', // Procedure on infant <4kg
  '76', // Repeat procedure same physician
  '77', // Repeat procedure other physician
  '78', // Unplanned return to OR
  '79', // Unrelated procedure during postop period
  '95', // Synchronous telemedicine via real-time interactive audio/video
  'GT', // Telehealth (legacy; mostly replaced by 95)
  'GQ', // Asynchronous telehealth
  'XE', // Separate encounter
  'XP', // Separate practitioner
  'XS', // Separate structure
  'XU', // Unusual non-overlapping service
]);

/**
 * Validates a CPT code against the allowlist. Strips any
 * "-MM" modifier suffix before lookup, then verifies the modifier
 * (if any) is in the canonical AMA modifier set.
 *
 * Returns true iff:
 *   - Base code (5 chars, before any "-") is in CPT_ALLOWLIST, AND
 *   - If a modifier is present, it's in VALID_MODIFIERS.
 */
export function isValidCpt(code: string | null | undefined): boolean {
  if (!code) return false;
  const trimmed = code.trim().toUpperCase();
  if (trimmed.length === 0) return false;

  const dashIdx = trimmed.indexOf('-');
  const base = dashIdx === -1 ? trimmed : trimmed.slice(0, dashIdx);
  const modifier = dashIdx === -1 ? null : trimmed.slice(dashIdx + 1);

  if (!CPT_ALLOWLIST.has(base)) return false;
  if (modifier !== null && !VALID_MODIFIERS.has(modifier)) return false;
  return true;
}

/** Total size — surfaced in admin diagnostics. */
export const CPT_ALLOWLIST_SIZE = CPT_ALLOWLIST.size;
