// ============================================================================
// Smart Procedure Templates — Pre-written SOAP drafts
// ----------------------------------------------------------------------------
// Doctors select a template to instantly create a note pre-filled with a
// standard structure. Bracketed placeholders (e.g., [Right/Left/Bilateral])
// tell the doctor what to fill in — either by typing or voice editing.
// ============================================================================

export interface ProcedureTemplate {
  id: string;
  name: string;
  procedureType: string;
  description: string;
  content: string;
}

export const PROCEDURE_TEMPLATES: ProcedureTemplate[] = [
  {
    id: 'tpl_prp',
    name: 'PRP Injection',
    procedureType: 'PRP',
    description: 'Platelet-rich plasma injection procedure note',
    content: `SUBJECTIVE:
Patient presents for [Right/Left/Bilateral] [knee/hip/shoulder/lumbar] platelet-rich plasma (PRP) injection. Patient reports [duration] of [pain description]. Previous treatments include [conservative measures tried]. Current pain level is [X/10] on the numeric rating scale. Pain is exacerbated by [aggravating factors] and relieved by [alleviating factors].

OBJECTIVE:
Vitals: BP [X/X], HR [X], Temp [X]
Physical Exam: [Joint/region] examination reveals [findings]. Range of motion is [limited/full]. Tenderness noted at [location]. No signs of infection at the injection site. [Imaging findings if applicable].
Procedure: Under sterile technique, [X] mL of autologous PRP was prepared via centrifugation of [X] mL of whole blood. The [joint/region] was prepped and draped in sterile fashion. Using [ultrasound/fluoroscopic] guidance, [X] mL of PRP was injected into the [target structure]. The patient tolerated the procedure well without immediate complications.

ASSESSMENT:
1. [Primary diagnosis] - [ICD-10 code]
2. [Secondary diagnosis if applicable]
PRP injection performed to promote tissue healing and reduce inflammation.

PLAN:
1. Post-procedure: Rest the treated area for 48 hours. Avoid NSAIDs for 2 weeks.
2. Ice may be applied for 20 minutes as needed for soreness.
3. Physical therapy to begin in [X] weeks.
4. Follow-up appointment in [4-6] weeks to assess response.
5. Patient educated on expected recovery timeline and when to seek immediate care.`,
  },

  {
    id: 'tpl_cesi',
    name: 'Cervical ESI (CESI)',
    procedureType: 'CESI',
    description: 'Cervical epidural steroid injection procedure note',
    content: `SUBJECTIVE:
Patient presents for [1st/2nd/3rd] cervical interlaminar epidural steroid injection for [Right/Left/Bilateral] cervical radiculopathy. Patient reports neck pain radiating to the [right/left/bilateral] upper extremity(ies) for [duration]. Pain is described as [sharp/burning/aching] and rated [X/10]. Symptoms are aggravated by [activities]. Prior treatments include [conservative measures].

OBJECTIVE:
Vitals: BP [X/X], HR [X], Temp [X]
Neurological Exam: Upper extremity strength [X/5] bilaterally. Sensation intact/decreased at [dermatome]. Deep tendon reflexes [symmetric/asymmetric] at [location]. Spurling test [positive/negative] on the [right/left].
Procedure: Patient placed in [sitting/prone] position. The [C-level] interlaminar space was identified under fluoroscopic guidance. After sterile prep and drape, local anesthesia was administered with 1% lidocaine. A [gauge] Tuohy needle was advanced into the epidural space using loss-of-resistance technique. Epidural placement was confirmed with [X] mL of contrast under live fluoroscopy. A mixture of [X] mg Dexamethasone and [X] mL of 0.25% Bupivacaine was injected. The needle was removed and a sterile bandage was applied. Patient tolerated the procedure well.

ASSESSMENT:
1. Cervical radiculopathy, [right/left/bilateral] - [ICD-10 code]
2. Cervical disc herniation/spondylosis at [C-level] - [ICD-10 code]

PLAN:
1. Monitor in recovery for [20-30] minutes post-procedure.
2. Avoid strenuous activity for 24-48 hours.
3. May resume normal activities as tolerated.
4. Continue current medications: [medications].
5. Follow-up in [2-4] weeks. If inadequate relief, consider repeat injection or advanced imaging.
6. Return precautions reviewed: fever, worsening weakness, loss of bladder/bowel control.`,
  },

  {
    id: 'tpl_tpi',
    name: 'Trigger Point Injection',
    procedureType: 'TPI',
    description: 'Trigger point injection for myofascial pain',
    content: `SUBJECTIVE:
Patient presents for trigger point injection(s) in the [cervical/thoracic/lumbar paraspinal/trapezius/other] musculature. Patient reports [duration] of localized [muscle group] pain. Pain is described as [dull/aching/sharp] and rated [X/10]. Palpable trigger points were previously identified on examination. Prior treatments include [stretching/physical therapy/medications].

OBJECTIVE:
Vitals: BP [X/X], HR [X]
Physical Exam: Palpation reveals [number] trigger points in the [muscle groups]. Taut bands and local twitch response elicited at [locations]. No overlying skin infection or breakdown noted.
Procedure: Under sterile technique, [number] trigger points were injected in the [muscle groups] using a [gauge] needle. Each site received approximately [X] mL of [0.25% Bupivacaine / 1% Lidocaine / dry needling]. Local twitch responses were elicited at [X] of [X] sites. All sites were dressed with adhesive bandages. Patient tolerated the procedure well.

ASSESSMENT:
1. Myofascial pain syndrome, [region] - M79.1
2. [Additional diagnoses]

PLAN:
1. Apply ice to injection sites for 15-20 minutes as needed today.
2. Gentle stretching of the treated muscles beginning tomorrow.
3. Continue physical therapy program.
4. Follow-up in [2-4] weeks for reassessment.
5. If adequate relief, consider ongoing maintenance injections every [X] weeks.`,
  },

  {
    id: 'tpl_followup',
    name: 'General Follow-up',
    procedureType: 'Follow-up',
    description: 'Standard follow-up visit for pain management patients',
    content: `SUBJECTIVE:
Patient returns for follow-up of [condition/diagnosis]. Since the last visit on [date], patient reports [improvement/worsening/no change] in symptoms. Current pain level is [X/10] compared to [X/10] at last visit. Patient is [compliant/non-compliant] with the prescribed treatment plan. Current medications include [medication list]. Side effects reported: [none/list]. Functional status: [able to work/limited activities/unable to perform ADLs].

OBJECTIVE:
Vitals: BP [X/X], HR [X], Weight [X]
General: Patient appears [comfortable/in mild discomfort].
Musculoskeletal: [Relevant exam findings — ROM, tenderness, strength].
Neurological: [Sensation, reflexes, gait as applicable].
[Relevant imaging/lab results since last visit if applicable].

ASSESSMENT:
1. [Primary diagnosis] - [ICD-10 code] — [improving/stable/worsening]
2. [Secondary diagnosis if applicable]
Overall clinical trajectory: [positive/guarded/declining].

PLAN:
1. Medications: [Continue/adjust/add/discontinue — specify].
2. Procedures: [Schedule next injection / no procedures indicated at this time].
3. Therapy: [Continue PT / new referral / home exercise program].
4. Imaging: [Order new imaging / review pending results / none needed].
5. Follow-up in [X] weeks.
6. Patient counseled on [activity modifications/expectations/red flags].`,
  },
];
