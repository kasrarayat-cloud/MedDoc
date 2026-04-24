# Audit — interactive inventory (master index)

Every clickable element, form, handler, and API route across the three apps.
See detailed per-app files under `audit-evidence/`.

## Inventory files
- `audit-evidence/inventory-transcribe-md.md` — app.quillmd.com (~40 buttons, 15 forms, 8 dialogs, 33 API routes)
- `audit-evidence/inventory-meddoc-pro.md` — pro.quillmd.com (80+ buttons, 50+ links, 15 forms, 25 server actions, 11 API routes)
- `audit-evidence/inventory-marketing.md` — quillmd.com (60+ elements, 0 forms, 10 routes)

## Totals
| Surface | Interactive els | Forms | Server actions | API routes |
|---------|----:|----:|----:|----:|
| transcribe-md | ~75 | 15+ | 8 | 33 |
| meddoc-pro | 130+ | 15 | 25 | 11 |
| marketing | 60+ | 0 | 0 | 0 |
| **Total** | **~265** | **30+** | **33** | **44** |

## Dead / stubbed elements flagged in inventories
- `meddoc-pro/src/components/landing/Hero.tsx:141` — Watch Demo button has no onClick
- `meddoc-pro/src/app/login/page.tsx:170` — "Forgot password?" link is `href="#"` (no meddoc-pro forgot-password flow exists)
- `meddoc-pro/src/app/dashboard/patients/PatientsListClient.tsx:297` — "More Filters" button has no onClick
- `transcribe-md/src/app/settings/page.tsx:207` — 2FA section is read-only "Not Enabled" chrome
- `transcribe-md/src/app/settings/page.tsx:327` — "Manage billing" button is disabled (Stripe not wired — intentional)
- `marketing/src/app/hipaa,security,privacy,terms/page.tsx` — headers note "[DRAFT — PENDING LEGAL REVIEW]"

## Dynamic-probe artefacts
- `audit-evidence/screenshots/` — 30+ full-page PNGs at desktop + mobile viewports
- `audit-evidence/perf/*.json` — Navigation Timing metrics (TTFB, DCL, load complete) per page
- `audit-evidence/console-logs/*.json` — page errors / console errors / 5xx responses per test
- `audit-evidence/api-probes/results.jsonl` — 41 unauth API probes with status codes
- `audit-evidence/test-results-raw.json` — full Playwright run (27 pass, 2 fail, 0 skip)

## Findings by severity
See `audit-report.md`. One-line summary:
- **Critical**: 1 (patient birthYear default=30 corrupts GPT output)
- **High**: 4
- **Medium**: 10
- **Low**: 8
