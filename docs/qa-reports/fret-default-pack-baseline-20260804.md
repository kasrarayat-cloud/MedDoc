# F-ret.1 — default `chromium` pack against the FLAG-ON build

**Measured 2026-08-04** on the isolated QA stack (`127.0.0.1:9020`), against the
`:rounds` image built from the code deployed to production that day.

> **19 failed · 22 passed · 18 skipped, of 59 tests in 26 files.**

This is the BASELINE for F-ret.1, not a conclusion. Each row still has to be
read and marked **drift** / **retire-with-note** / **real defect**.

## Two warnings before the table

**1. The run's own summary reads like a pass.** The `list` reporter's tail
prints the failing test *names* and then:

```
  18 skipped
  22 passed (7.8m)
```

There is no `19 failed` line. `22 + 18 = 40` against a collected 59, and the
only unambiguous signal is `EXIT=1`. Reconcile the arithmetic against
`--list`'s `Total:` before believing a Playwright tail.

**2. The account menu fixed exactly two of the original 21.** The prediction on
record was that `helpers/auth.ts:51` — the *shared* logout helper — accounted
for a large share. It did not: most of these specs never log out. A shared
helper is not automatically a broad blast radius.

## By error class

The class predicts the fix better than the spec does.

| Class | Count | Reading |
|---|---:|---|
| `locator.click` timeout | 8 | a control the skin moved or renamed |
| `expect(locator).toBeVisible()` | 4 | an element the skin no longer renders there |
| `expect(page).toHaveURL()` | 3 | **almost certainly `/dashboard` → `/board`** — the confirmed cause of the nightly's two failures |
| `locator.fill` timeout | 2 | an input that moved |
| `toHaveAttribute` | 1 | — |

**Start with the three `toHaveURL` rows.** The nightly had exactly this shape
and it cost one line once named (`/(board|dashboard)`, both spellings so a
flag-OFF rollback cannot make it a false red). Likely the same bug three times
— *likely*, not certainly. Read each one.

## The 19

| # | Spec | Line | Test | First error |
|---:|---|---:|---|---|
| 1 | `scenarios/1-audio-upload-full.spec.ts` | 31 | scenario 1: fresh signup → audio upload → sign clipboard+PDF+DOCX | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 2 | `scenarios/10-visit-lifecycle.spec.ts` | 22 | lifecycle: delete a READY visit → trash → restore | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 3 | `scenarios/10-visit-lifecycle.spec.ts` | 75 | lifecycle: archive a SIGNED visit → hidden from the active list | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 4 | `scenarios/14-auth-signup-onboarding.spec.ts` | 19 | signup: a brand-new account lands on the first-run dashboard | `Error: expect(page).toHaveURL(expected) failed` |
| 5 | `scenarios/15-auth-mfa.spec.ts` | 22 | MFA: enroll TOTP → verify → recovery codes, then enforced at login | `Error: expect(page).toHaveURL(expected) failed` |
| 6 | `scenarios/16-account-settings.spec.ts` | 19 | account: profile edit persists across reload | `Error: expect(locator).toBeVisible() failed` |
| 7 | `scenarios/16-account-settings.spec.ts` | 40 | account: logged-in password change takes effect at next login | `TimeoutError: locator.fill: Timeout 15000ms exceeded.` |
| 8 | `scenarios/17-password-reset.spec.ts` | 23 | password reset: request → reset link → set new password → login | `Error: expect(page).toHaveURL(expected) failed` |
| 9 | `scenarios/2-voice-dictation.spec.ts` | 39 | scenario 2: fresh signup → voice dictation → READY → sign clipboard | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 10 | `scenarios/27-error-resilience.spec.ts` | 40 | scenario 27: a nonexistent route renders the styled 404 page (not a crash) + the recovery CTA works | `Error: expect(locator).toBeVisible() failed` |
| 11 | `scenarios/27-error-resilience.spec.ts` | 58 | scenario 27: a nonexistent visit renders the visit-404 (not a crash, no ID enumeration leak) | `Error: expect(locator).toBeVisible() failed` |
| 12 | `scenarios/29-sign-modal-geometry.spec.ts` | 38 | the sign modal keeps its signature controls on screen › attestation + submit are both inside the viewport @desktop-chrome-720 | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 13 | `scenarios/29-sign-modal-geometry.spec.ts` | 38 | the sign modal keeps its signature controls on screen › attestation + submit are both inside the viewport @short-640 | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 14 | `scenarios/3-text-to-soap.spec.ts` | 31 | scenario 3: fresh signup → text → READY → sign PDF | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 15 | `scenarios/4-back-to-dashboard.spec.ts` | 23 | scenario 4: back-to-dashboard navigates from a visit page | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |
| 16 | `scenarios/6-patients.spec.ts` | 24 | patients list: standalone-created patients render + name filter narrows | `TimeoutError: locator.fill: Timeout 15000ms exceeded.` |
| 17 | `scenarios/6-patients.spec.ts` | 46 | patient detail: header + stats + visit history reflect a real visit | `Error: expect(locator).toBeVisible() failed` |
| 18 | `scenarios/8-visit-detail-tabs.spec.ts` | 19 | visit detail: open an existing visit → SOAP note renders + tabs switch | `Error: expect(locator).toHaveAttribute(expected) failed` |
| 19 | `scenarios/9-soap-edit.spec.ts` | 20 | SOAP edit: inline-editing a section persists + survives reload | `TimeoutError: locator.click: Timeout 15000ms exceeded.` |

## Boundary of this measurement

- **Where:** the isolated QA stack, project `meddoc-qa`, port 9020, MOCK_AI,
  synthetic database. Not production.
- **What:** the default `chromium` Playwright project only — the pack that is a
  REQUIRED CI check and that currently builds **flag-OFF**. The eight Rounds
  packs are green and are not in scope here.
- **Which build:** the `:rounds` image, app-identical to the production deploy
  of 2026-08-04 (the only non-test delta between them is
  `playwright.config.ts`).
- **Collected count checked, not assumed:** `--list` reports `Total: 59 tests
  in 26 files`, unchanged from the earlier measurement.
- **Not established:** whether any of the 19 is a real product defect rather
  than harness drift. That is the work, and it has not been done.

