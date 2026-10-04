# Finished clinical source refutation: repair required

## 09:07 UTC corrective result — integrated, qualification pending

Original failures below remain evidence. Root replayed corrective source `d7f4ebf7759cecf3d9517d208d6c2d8d7c40e3fc` against five fixed packets. The first four passed with actual exits 0: 60 ordinary/procedure controls in 30.299 seconds; 24 backward-attribution controls in 21.465 seconds; 30 time/exclusion/authorship controls in 29.799 seconds; 12 unrelated appointment/object-owner controls in 14.421 seconds. These 126 controls had zero unsafe releases, false holds or source/page/final discrepancies.

The final 12 preceding-annotation controls had actual exit 1 in 13.209 seconds: zero unsafe releases or fidelity discrepancies, three conservative holds when a previous maternal report precedes an explicitly current-patient colonoscopy. Those were already held on earlier source and remain a coverage limit. Doctor and maternal report annotations are held; explicit current-patient annotations work. All 138 wires, expectations and outputs remain retained. The earlier three adjudicated expectation corrections do not regrade the historical failed run.

| Corrective result under the retained evidence root | SHA256 |
| --- | --- |
| `root-ordinary-procedure-d7f-independent/result.json` | `4a78c6da2a35c1b19ca52318f7e25e7b8524ceea571ee513b83eb1caa7875e97` |
| `root-procedure-backward-attribution-d7f-independent/result.json` | `99cad9dd13e79af154196db43867039fe3779dd11168b47ceca2f79250b3e29a` |
| `root-procedure-source-attribution-supplement-d7f-independent/result.json` | `01eb66be15961153ebdf9d9aac61b567fc053cb5e7923e9b028f19966c50b44d` |
| `root-procedure-independent-object-d7f/result.json` | `f82a3d4661e58d86e599ce0a664ec02a3850d02b6b2f7d8e3cf3f0ba5a54de58` |
| `root-procedure-preceding-report-d7f/result.json` | `452f5d9a9c975fd7107efcc0fb20242dc0680cd376d6ccdab6e9dfe8370054ce` |

The clinical chain was integrated through `36190ae1` after refutation, with source identical to the frozen tested files. The retained 14 qualified provider-response replay projects 35/36 useful positives and 40/40 intended holds. This is offline evidence, not new paid qualification. N01 HPI and C08 remain held. Exact integrated-source qualification, financial renewal and CI remain pending; no new provider sends or installation occurred.

Frozen implementation `9b5d55e050ecfe73f34b496f516061c1849128a5` is **not integrated or qualified**. Provider preparation is paused. The existing PR remains a draft.

Root independently preserved60 full-wire controls through validation, page governance and finalization. Actual exit1 in34.485seconds; source unchanged; no provider or database calls. One ordinary medication positive remains unnecessarily held: `A 30-year-old woman presents with headaches. She takes ibuprofen as needed. She denies bleeding.` Three initial flags with a separately attributed family event later in the note are withdrawn instrument expectations: they do not explicitly assign the preceding values to that person. The original60-control exit1 and raw flags remain retained; this is not a regraded passing qualification. Adjudication JSON SHA256 `6609d8f49dea171ea9fa2067de8171acbbf91b87728b57d826666831aa0b22e3`.

A second24-control pass demonstrates nine concrete unsafe releases. Each of the following previously subjectless procedure values remains supported when followed by an explicit statement assigning **the report itself** to another person:

- `The scope was advanced to the cecum.`
- `Sigmoid diverticulosis and small internal hemorrhoids.`
- `Recommendation, follow-up with the referring clinician in two weeks.`

The three report statements are `This report belongs to her mother.`, `This report is from her mother's colonoscopy.` and `This report describes the doctor.` Each resulting answer is offered on the page and remains supported at finalization. Current patient-default transcript review must not erase that explicit source attribution. Past-visit, invalid-report and quoted-report negatives in the same packet remain held.

The exact same24 full wires on frozen7907 produce zero unsafe releases: the three ordinary positives are held, and all nine explicit report-bearer negatives are held. This establishes a new unsafe release in the changed ownership path, rather than merely finding a historical defect.

The cause is the new complete-source proof at `rebuild/core/reviewed_source.py:119`: it accounts for foreign scopes before the selected unit, while the existing backward-dependency guard does not recognize these demonstrative report-bearer assignments. The specialist is repairing structural backward source ownership with independent current-patient and separate-family-event positive controls. A broader foreign-word hold would not establish the required correction.

Evidence root: `/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/`.

| Preserved record | SHA256 |
| --- | --- |
| `root-ordinary-procedure-9b5-independent/result.json` | `afc76b4e74c666f1a015c52d716180ac3d558ea5bf2fc44ba53e3dce33bd2e68` |
| `root-procedure-backward-attribution-9b5-independent/result.json` | `b1980c95d47af9f22d5c417a40d2058c7f7ae59e56cc88875d5ef715ceba7ba7` |
| `root-procedure-backward-attribution-7907-baseline/result.json` | `313859cd842894edc82f2dc41801aaa76da73a332202a48459916cb8db76a87e` |

All raw inputs, fields, complete provider-equivalent wires, resulting answers and page/final states are retained per case. The local synthetic transcript proof reconstructs an equivalent immutable review for offline testing; it does not replace an authentic historical token or claim a new live-provider result. C08 remains held in the retained original complete procedure wire. No new paid campaign has begun.

At08:08UTC, a prospectively prepared independent30-control supplement on the same unchanged9b source demonstrates nine additional wrong releases: each of the three procedure destinations remains supported after `This report may belong to her mother.`, `This report is not from the current patient.` or `This report describes the patient next year.` Source-bearer uncertainty, explicit current-patient exclusion and future-visit attribution must remain held. All18 current-patient/negated-foreign/another-report/clinician-authorship/separate-family positive controls pass. Actual exit1 in33.737seconds, zero false holds, no network/DB calls. Record `root-procedure-source-attribution-supplement-9b-baseline/result.json` SHA256 `e1c4f1750c58351a5af635f71efe7aa56e67ee311c4239a5f1fb369ebe88d1e3`. The new wrong outputs are retained and delivered to the specialist before integration; the source remains unqualified.

## Corrective7af result and new scope overholds

Frozen `7af94030fd3d5d8a2fa5ff4b14c9c64528f86187` passes the independent60 original controls,24 report-bearer controls and30 contrasting time/exclusion/authorship controls, actual exits0 in33.491/23.021/30.512seconds. Their immutable result hashes are respectively `a288842460e0b98c8d1f10e6bdd621d0757cbc57cd5c58cc6387c9d7fe92e280`, `57e72c92426e7480bf06889be4665ce325307dc6bf2a226895bc55815dd70d21` and `e7808212c0e4860456d4fb11717bc636cd0b263f0c128cd06e9364390ce73304`. The60-control replay corrects only the three separately documented instrument expectations; original inputs/failed result are not replaced or regraded.

A further12 independent positive controls find nine newly unnecessary holds. Each of the same three procedure values becomes conflict when followed by a separately owned appointment or object: `The appointment is with the clinician next week.`, `The equipment belongs to the doctor.` or `The bottle belongs to her mother.` The three passive reviewer controls remain supported. The guard erroneously recognizes every definite nonperson subject as a backward report pointer; an appointment's own future time is not the report's time. Original9b supports all12 unchanged input wires, establishing a new overhold rather than merely an unsupported family.

| Record | SHA256 | Actual result |
| --- | --- | --- |
| `root-procedure-independent-object-7af/result.json` | `4404f299228ba6c68ea86f848f8c1da75caaf7df53f247db482f04e5e91244a2` | exit1/12.386s;9 unnecessary holds |
| `root-procedure-independent-object-9b-baseline/result.json` | `b1b7473dc8c89c5f77c0aae2925049bf67dffb45e05baea57f270c3f916fe783` | exit0/14.306s;12 supported |

All five corrective/comparison packets deny network and database access and prove identical clean source before/after.7af remains unintegrated, while the specialist narrows source references with these exact positives and all retained safety negatives. No provider call, price renewal or installation is authorized by these passing partial packets.
