# Native Microsoft Word acceptance — WM IOV original and fresh export

Prepared 2026-09-17 for release `8f8a6763b80d345e432074df64b907c2db50be2a`.

**Status: native Word appearance acceptance is PENDING.** Microsoft Word is not
installed on the Linux VPS and no other renderer can establish native Word
appearance. Everything below is structural/XML evidence plus a watermarked
evaluation render with substituted fonts; the owner's inspection in native Word
is the acceptance step. Do not mark any row below as accepted from a non-Word
renderer.

## The review pair (private files, owner-only, 0600)

Fetch these through the existing SSH tunnel with SFTP/scp; do not email them.
They contain synthetic clinical text only (synthetic patient, synthetic clinician).

| Document | Path on the VPS | SHA-256 | Bytes |
| --- | --- | --- | --- |
| Original blank template (tracked fixture) | `/opt/meddoc-pro/WM IOV Template.docx` | `c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b` | — |
| **Fresh export — live Anthropic run, `absent` scenario, zero clinician corrections** | `/opt/meddoc-pro/rebuild/.runtime/wm-live-browser-8f8a6763b80d-fresh-absent/synthetic-wm-fresh-absent.docx` | `3997ce06b4d7e2e6ef7e03001b55afcaaf35a5bea97f9739fff75e0f9cd95b11` | 46,744 |
| Previous export — live run, `positive` scenario, 90 clinician edits (pre-repair mapper) | `/opt/meddoc-pro/rebuild/.runtime/wm-live-browser-8f8a6763b80d-clinician-review-existing-377b1c3d/synthetic-wm-live.docx` | `3ef3539b587a3f3ecaf90cc4991c753ffc712fc58481e4decbbdb77200742489` | 46,604 |
| Long-answer overflow fixture (SDK qualification, no AI, synthetic) | `/opt/meddoc-pro/.worktrees/private-os-isolation/rebuild/.runtime/wm-complete-qualified/long-answer.docx` | `5e55c2395707ed17ce24b010dc5fa4c1d4447d78edff07508fcf155601d61e3b` | 47,181 |
| All-blank fixture (every answer reviewed as missing) | `/opt/meddoc-pro/.worktrees/private-os-isolation/rebuild/.runtime/wm-complete-qualified/all-blanks.docx` | `90217bfe71d9164edc46dd02ff0b68594ba418417da4062f4007622f95403629` | 46,901 |

Verify a copy before opening it: `sha256sum <file>` must print the value above.

## What is already established (not native Word)

- Independent XML/ledger verifier on the fresh export: 42/42 checks
  (`/opt/meddoc-pro/rebuild/.runtime/wm-fresh-document-billing-verification-20260917.json`).
  All 28 content-control ids and option lists identical to the original; 48 body
  paragraphs / 133 total paragraphs / 28 table rows × 3 cells preserved; all 90
  answers and 14 reviewed statements at their original anchors; headers and
  media byte-identical; signer and finalization timestamp from the server.
- Evaluation render (Aspose.Words evaluation copy, watermarked, Liberation
  Serif / DejaVu Sans substituted for Times New Roman / Aptos): see the
  `render-evidence.json` and page PNGs in
  `/opt/meddoc-pro/rebuild/.runtime/wm-fresh-layout-8f8a6763b80d-absent-evaluation/`.
  Font metrics differ from native Word, so line breaks and page fill are not
  representative.

## Checklist — complete in native Microsoft Word (Windows or macOS)

Record Word version and OS. For each row mark ACCEPT / REJECT and note the page.

### A. Document opens and structure
1. Both files open without repair prompts or compatibility warnings.
2. Page count and section layout match the original (the original ends with a
   trailing next-page section, so a blank final page is expected in both).
3. No tracked changes, comments, or "Evaluation" watermark in the export.
4. Headers, letterhead image and footer identical to the original on every page.

### B. All 28 content controls (dropdowns)
5. In the export, each of the 28 controls shows the selected answer text and is
   still a content control (Developer → Design Mode shows the control boundary;
   the dropdown still lists the original options; no control was converted to
   plain text).
6. Control formatting (font, size, bold) matches the original placeholder run.
7. No control shows "Choose an item." unless the answer was reviewed as missing
   (the fresh export has zero missing answers).

### C. All 90 answer locations
8. Walk the table below. Body-paragraph answers (rows 29–32) follow the original
   question text on the same line; table answers sit inside the original cell
   with the original unit text; location answers replace the original
   `<<insert location>>` marker.
9. Every question label from the original is still present and unchanged.

| 1 | Practice address | choice | Content control (dropdown) id `1519045110` · 5 original options |
| 2 | Exam side | choice | Content control (dropdown) id `1475334564` · 7 original options |
| 3 | Referring physician | choice | Content control (dropdown) id `469715844` · 5 original options |
| 4 | Ultrasound technologist | choice | Content control (dropdown) id `-1477830258` · 7 original options |
| 5 | Ultrasound machine | choice | Content control (dropdown) id `-388341802` · 5 original options |
| 6 | Exam location | choice | Content control (dropdown) id `143014188` · 4 original options |
| 7 | Clinical indication: leg pain | choice | Content control (dropdown) id `-1124008635` · 1 original options |
| 8 | Clinical indication: swelling | choice | Content control (dropdown) id `269290727` · 2 original options |
| 9 | Clinical indication: heaviness | choice | Content control (dropdown) id `722175654` · 1 original options |
| 10 | Clinical indication: history or skin changes | choice | Content control (dropdown) id `-770853925` · 5 original options |
| 11 | Clinical indication: sensory symptoms | choice | Content control (dropdown) id `-49312682` · 3 original options |
| 12 | Clinical indication: asymptomatic or itching | choice | Content control (dropdown) id `2005853103` · 2 original options |
| 13 | Diagnosis | choice | Content control (dropdown) id `-1316494373` · 6 original options |
| 14 | Technique: venous systems | choice | Content control (dropdown) id `429781496` · 2 original options |
| 15 | Right previous treatment: vein | choice | Content control (dropdown) id `-1287346867` · 4 original options |
| 16 | Right previous treatment: start | choice | Content control (dropdown) id `-346030703` · 8 original options |
| 17 | Right previous treatment: end | choice | Content control (dropdown) id `599910328` · 6 original options |
| 18 | Right previous treatment: outcome | choice | Content control (dropdown) id `1706206184` · 2 original options |
| 19 | Left previous treatment: vein | choice | Content control (dropdown) id `1093284141` · 4 original options |
| 20 | Left previous treatment: start | choice | Content control (dropdown) id `-505521617` · 8 original options |
| 21 | Left previous treatment: end | choice | Content control (dropdown) id `519430350` · 6 original options |
| 22 | Left previous treatment: outcome | choice | Content control (dropdown) id `-1268837810` · 2 original options |
| 23 | Right impression: vein | choice | Content control (dropdown) id `-892962961` · 10 original options |
| 24 | Right impression: reflux or absence | choice | Content control (dropdown) id `-213273323` · 2 original options |
| 25 | Right deep venous system | choice | Content control (dropdown) id `-170105994` · 3 original options |
| 26 | Left impression: vein | choice | Content control (dropdown) id `2001841928` · 10 original options |
| 27 | Left impression: reflux or absence | choice | Content control (dropdown) id `605543147` · 2 original options |
| 28 | Left deep venous system | choice | Content control (dropdown) id `-1029175652` · 3 original options |
| 29 | Date of service | text | Body paragraph 4 (appended after the original question text) |
| 30 | Patient ID | text | Body paragraph 5 (appended after the original question text) |
| 31 | Patient name | text | Body paragraph 6 (appended after the original question text) |
| 32 | Date of birth | text | Body paragraph 7 (appended after the original question text) |
| 33 | Right GSV at the SFJ: diameter (mm) | measurement | Table 0, row 1, column 1 · numeric value, unit `mm` printed by the original cell |
| 34 | Right GSV at the SFJ: reflux time (ms) | measurement | Table 0, row 1, column 2 · numeric value, unit `ms` printed by the original cell |
| 35 | Right GSV at the Proximal Thigh: diameter (mm) | measurement | Table 0, row 2, column 1 · numeric value, unit `mm` printed by the original cell |
| 36 | Right GSV at the Proximal Thigh: reflux time (ms) | measurement | Table 0, row 2, column 2 · numeric value, unit `ms` printed by the original cell |
| 37 | Right GSV at the Knee: diameter (mm) | measurement | Table 0, row 3, column 1 · numeric value, unit `mm` printed by the original cell |
| 38 | Right GSV at the Knee: reflux time (ms) | measurement | Table 0, row 3, column 2 · numeric value, unit `ms` printed by the original cell |
| 39 | Right GSV Below Knee: diameter (mm) | measurement | Table 0, row 4, column 1 · numeric value, unit `mm` printed by the original cell |
| 40 | Right GSV Below Knee: reflux time (ms) | measurement | Table 0, row 4, column 2 · numeric value, unit `ms` printed by the original cell |
| 41 | Right SSV at the SPJ: diameter (mm) | measurement | Table 0, row 5, column 1 · numeric value, unit `mm` printed by the original cell |
| 42 | Right SSV at the SPJ: reflux time (ms) | measurement | Table 0, row 5, column 2 · numeric value, unit `ms` printed by the original cell |
| 43 | Right SSV at the Proximal Calf: diameter (mm) | measurement | Table 0, row 6, column 1 · numeric value, unit `mm` printed by the original cell |
| 44 | Right SSV at the Proximal Calf: reflux time (ms) | measurement | Table 0, row 6, column 2 · numeric value, unit `ms` printed by the original cell |
| 45 | Right AAGSV at the SFJ: diameter (mm) | measurement | Table 0, row 7, column 1 · numeric value, unit `mm` printed by the original cell |
| 46 | Right AAGSV at the SFJ: reflux time (ms) | measurement | Table 0, row 7, column 2 · numeric value, unit `ms` printed by the original cell |
| 47 | Right AAGSV at the Proximal Thigh: diameter (mm) | measurement | Table 0, row 8, column 1 · numeric value, unit `mm` printed by the original cell |
| 48 | Right AAGSV at the Proximal Thigh: reflux time (ms) | measurement | Table 0, row 8, column 2 · numeric value, unit `ms` printed by the original cell |
| 49 | Right PAGSV at the SFJ: diameter (mm) | measurement | Table 0, row 9, column 1 · numeric value, unit `mm` printed by the original cell |
| 50 | Right PAGSV at the SFJ: reflux time (ms) | measurement | Table 0, row 9, column 2 · numeric value, unit `ms` printed by the original cell |
| 51 | Right PAGSV at the Proximal Thigh: diameter (mm) | measurement | Table 0, row 10, column 1 · numeric value, unit `mm` printed by the original cell |
| 52 | Right PAGSV at the Proximal Thigh: reflux time (ms) | measurement | Table 0, row 10, column 2 · numeric value, unit `ms` printed by the original cell |
| 53 | Right tributary row 11: diameter (mm) | measurement | Table 0, row 11, column 1 · numeric value, unit `mm` printed by the original cell |
| 54 | Right tributary row 11: reflux time (ms) | measurement | Table 0, row 11, column 2 · numeric value, unit `ms` printed by the original cell |
| 55 | Right tributary row 11: anatomical location | text | Table 0, row 11, column 0 · replaces the original marker `<<insert location>>` |
| 56 | Right tributary row 12: diameter (mm) | measurement | Table 0, row 12, column 1 · numeric value, unit `mm` printed by the original cell |
| 57 | Right tributary row 12: reflux time (ms) | measurement | Table 0, row 12, column 2 · numeric value, unit `ms` printed by the original cell |
| 58 | Right tributary row 12: anatomical location | text | Table 0, row 12, column 0 · replaces the original marker `<<insert location>>` |
| 59 | Right tributary row 13: diameter (mm) | measurement | Table 0, row 13, column 1 · numeric value, unit `mm` printed by the original cell |
| 60 | Right tributary row 13: reflux time (ms) | measurement | Table 0, row 13, column 2 · numeric value, unit `ms` printed by the original cell |
| 61 | Right tributary row 13: anatomical location | text | Table 0, row 13, column 0 · replaces the original marker `<<insert location>>` |
| 62 | Left GSV at the SFJ: diameter (mm) | measurement | Table 0, row 15, column 1 · numeric value, unit `mm` printed by the original cell |
| 63 | Left GSV at the SFJ: reflux time (ms) | measurement | Table 0, row 15, column 2 · numeric value, unit `ms` printed by the original cell |
| 64 | Left GSV at the Proximal Thigh: diameter (mm) | measurement | Table 0, row 16, column 1 · numeric value, unit `mm` printed by the original cell |
| 65 | Left GSV at the Proximal Thigh: reflux time (ms) | measurement | Table 0, row 16, column 2 · numeric value, unit `ms` printed by the original cell |
| 66 | Left GSV at the Knee: diameter (mm) | measurement | Table 0, row 17, column 1 · numeric value, unit `mm` printed by the original cell |
| 67 | Left GSV at the Knee: reflux time (ms) | measurement | Table 0, row 17, column 2 · numeric value, unit `ms` printed by the original cell |
| 68 | Left GSV Below Knee: diameter (mm) | measurement | Table 0, row 18, column 1 · numeric value, unit `mm` printed by the original cell |
| 69 | Left GSV Below Knee: reflux time (ms) | measurement | Table 0, row 18, column 2 · numeric value, unit `ms` printed by the original cell |
| 70 | Left SSV at the SPJ: diameter (mm) | measurement | Table 0, row 19, column 1 · numeric value, unit `mm` printed by the original cell |
| 71 | Left SSV at the SPJ: reflux time (ms) | measurement | Table 0, row 19, column 2 · numeric value, unit `ms` printed by the original cell |
| 72 | Left SSV at the Proximal Calf: diameter (mm) | measurement | Table 0, row 20, column 1 · numeric value, unit `mm` printed by the original cell |
| 73 | Left SSV at the Proximal Calf: reflux time (ms) | measurement | Table 0, row 20, column 2 · numeric value, unit `ms` printed by the original cell |
| 74 | Left AAGSV at the SFJ: diameter (mm) | measurement | Table 0, row 21, column 1 · numeric value, unit `mm` printed by the original cell |
| 75 | Left AAGSV at the SFJ: reflux time (ms) | measurement | Table 0, row 21, column 2 · numeric value, unit `ms` printed by the original cell |
| 76 | Left AAGSV at the Proximal Thigh: diameter (mm) | measurement | Table 0, row 22, column 1 · numeric value, unit `mm` printed by the original cell |
| 77 | Left AAGSV at the Proximal Thigh: reflux time (ms) | measurement | Table 0, row 22, column 2 · numeric value, unit `ms` printed by the original cell |
| 78 | Left PAGSV at the SFJ: diameter (mm) | measurement | Table 0, row 23, column 1 · numeric value, unit `mm` printed by the original cell |
| 79 | Left PAGSV at the SFJ: reflux time (ms) | measurement | Table 0, row 23, column 2 · numeric value, unit `ms` printed by the original cell |
| 80 | Left PAGSV at the Proximal Thigh: diameter (mm) | measurement | Table 0, row 24, column 1 · numeric value, unit `mm` printed by the original cell |
| 81 | Left PAGSV at the Proximal Thigh: reflux time (ms) | measurement | Table 0, row 24, column 2 · numeric value, unit `ms` printed by the original cell |
| 82 | Left tributary row 25: diameter (mm) | measurement | Table 0, row 25, column 1 · numeric value, unit `mm` printed by the original cell |
| 83 | Left tributary row 25: reflux time (ms) | measurement | Table 0, row 25, column 2 · numeric value, unit `ms` printed by the original cell |
| 84 | Left tributary row 25: anatomical location | text | Table 0, row 25, column 0 · replaces the original marker `<<insert location>>` |
| 85 | Left tributary row 26: diameter (mm) | measurement | Table 0, row 26, column 1 · numeric value, unit `mm` printed by the original cell |
| 86 | Left tributary row 26: reflux time (ms) | measurement | Table 0, row 26, column 2 · numeric value, unit `ms` printed by the original cell |
| 87 | Left tributary row 26: anatomical location | text | Table 0, row 26, column 0 · replaces the original marker `<<insert location>>` |
| 88 | Left tributary row 27: diameter (mm) | measurement | Table 0, row 27, column 1 · numeric value, unit `mm` printed by the original cell |
| 89 | Left tributary row 27: reflux time (ms) | measurement | Table 0, row 27, column 2 · numeric value, unit `ms` printed by the original cell |
| 90 | Left tributary row 27: anatomical location | text | Table 0, row 27, column 0 · replaces the original marker `<<insert location>>` |

### D. Tables and measurements
10. The measurement table keeps 28 rows × 3 cells; no row height change clips a
    value; numeric values are visible with the original unit text (mm / ms).
11. Column widths and borders unchanged from the original.

### E. Long-answer overflow (use the long-answer fixture)
12. Open `long-answer.docx`: paragraphs with 19,000+ characters flow across pages
    with no clipped text in fixed-height cells and no text running off-page.
13. Page breaks inserted by Word for the overflow do not split a table row so
    that a value becomes invisible.

### F. Prewritten statements and signature area
14. The 14 prewritten statements read as the selected alternatives; wording is
    complete and side-correct (right/left).
15. "INTERPRETING PHYSICIAN:" and the signature block show the actual signing
    clinician's display name (synthetic), and "Electronically Signed On" shows
    the server finalization time (UTC). No signature image or drawn signature
    was generated, and none should appear.
16. The signature block stays on the same page as the signer line.

### G. Formatting parity
17. Fonts render as the original's (Aptos / Aptos Display / Times New Roman) —
    no substitution prompts.
18. Paragraph spacing, indentation, bullets and bold/italic runs match the
    original; answer text inherits the surrounding run formatting.

## Reporting back
Reply with the checklist rows marked, the Word version, and any page/row that
looks wrong. A rejected row becomes a defect with the row number, the exact
control id or table cell, and a screenshot (synthetic content only).
