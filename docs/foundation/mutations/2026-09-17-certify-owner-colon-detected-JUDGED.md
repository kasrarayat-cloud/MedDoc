# RULED-ACT JUDGMENT — Slice D acceptance certify (`2026-09-17-certify-owner-colon-detected.md`)

**Ran 2026-09-17 04:16:13→04:16:39Z inside `transcribe-md-worker`** at revision
`a995c101` (== the declaration's tree HEAD; guard verdict `ok — equals`). Declaration
committed `06be121e`; act started after. Exit 0 (`__RULED_ACT_COMPLETE__`).

## Verdict: 9 of 9 declared rows correct. The owner's colon form is CERTIFIED through the DETECT pipeline (draft, no cutover).

| declared | expected | observed | ✓ |
|---|---|---|---|
| `note_templates` | 22 → 23 | 23 | ✓ |
| owner templates | 14 → 15 | 15 | ✓ |
| `formDetectCertified` | 0 → 1 | 1 | ✓ |
| new template status | draft (NOT active) | `e9c987ca…` status=draft, formDetect=true | ✓ |
| active templates | 7 (unchanged) | 7 | ✓ |
| `template_twin` certifications | 7 (unchanged) | 7 | ✓ |
| `pdfNativeCertified` | 7 (unchanged) | 7 | ✓ |
| `transcribe_visits` | 73 (unchanged) | 73 | ✓ |
| signed | 41 (unchanged) | 41 | ✓ |

## The transfer

Detected 29 boxes → 25 grouped → transfer-by-identity from the certified twin
(`4de6f662`): **24 labeled boxes mapped to twin-approved concepts, 0 unmapped, 1 unlabeled
box excluded**. Every numbered slot mapped by position — FINDINGS 1·2·3 → `procedure.findings`,
RECOMMENDATIONS 1·2·3 → `procedure.recommendations`. Certify: 24 fields, 20 filled, 4 policy
blanks (DOB / ID / DD / DT — blank-unless-dictated, #247/#319), pixel-fidelity 1 page @ 150dpi.
The sample-filled preview (synthetic, PHI-free) was rendered and handed to the owner: every
section + both numbered lists fill on his own page; the policy blanks are correctly empty.

## After — the real-visit acceptance is the owner's

New Visit → the picker shows his draft "Colonoscopy Operative Note (detected · #326)" →
dictate → export PDF (routes through the detect pipeline, his practice allowlisted). His
eyeball on that page is the acceptance. No cutover until he accepts.
