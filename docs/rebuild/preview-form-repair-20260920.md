# Private preview form repair — 2026-09-20

## Purpose and review target

The owner reported repeated browser-native authentication failures and explicitly
authorized replacing that gate with a normal sign-in page. The inspected live
GET returned401 with a valid Basic challenge; that protocol behavior did not
provide the straightforward access required for the email workflow.

Design path: direct implementation within the existing QuillMD design system,
using the Refero skill's existing-product reference workflow. Primary references
are `rebuild/templates/login.html` and its `auth-shell`/`auth-form` components;
secondary references are the account registration and recovery screens. The
bundled Refero form guidance supplies explicit labels, password-manager
autocomplete, paste support, visible focus and clear retry text.

| Decision | Reference | Preserved role |
|---|---|---|
| Existing two-panel auth shell and CSS | Current QuillMD login | Product consistency without new asset dependencies |
| Explicit preview username/password labels | Refero form craft; owner request | Distinguish preview access from individual account login |
| Original destination resumes after access | Existing recovery journey; owner requirement | No manual URL editing or token copying |
| Inline errors and a safe retry action | Recovery screen; Refero form craft | Explain wrong credentials, expiry and CSRF refusal |
| Synthetic-only notice | Current register/login screens | Preserve the real-patient-data release gate |

No imagery, new typography, new design system or unrelated screen changes are
needed. Native browser UI is replaced by the same accessible form conventions
already used in the application.

## Authentication and destination preservation

- The existing protected preview username/password remain valid, including the
  credentials in the already sent invitation. They are never placed in URLs.
- Django's database session facility holds a separate preview session. Its
  `__Host-quillmd_preview` cookie is Secure, HttpOnly, host-only, path`/`, and
  SameSite=Lax for top-level email navigation. Account cookies remain separate
  and retain their existing Strict policy and MFA requirements.
- A validated local GET destination is stored server-side under a bounded,
  per-tab opaque handle. The original invitation/recovery token is not copied
  into the sign-in URL or hidden fields. An intercepted POST is never replayed.
- The gate checks the exact private HTTPS origin and the proxy-overwritten
  marker. APIs, exports, originals and the external webhook are protected.
  Only public stylesheet assets are available before preview authentication.
- Form submissions use Django CSRF protection and the existing atomic rate
  limiter. Preview login rotates its session key. Idle/absolute expiry,
  logout and changed preview credentials revoke the grant.
- Safe application loopback access stays private and retains individual
  application authorization. Public443 routes remain in maintenance.
- Both application and proxy use `Referrer-Policy: strict-origin`: forms keep
  their same-origin CSRF context while capability paths are excluded from
  referrers. A real Chrome run demonstrated that `no-referrer` caused
  `Origin: null` and rejected valid form submissions; the failed evidence is
  retained and the repaired path is tested in both browsers.

## Activation and rollback

Use the committed declaration
`docs/foundation/mutations/20260920-quillmd-preview-form.md` and
`scripts/activate-preview-form.py` only after exact merged-revision CI passes.
The script snapshots protected configuration, stops only the three private
services, proves all rows/files/schema unchanged after restart, and verifies the
application gate before removing Basic authentication from the dedicated proxy.

On failure it inspects actual file bytes, restores the old independent gate,
disables the form gate and restarts the same reviewed code with an honest
revision stamp. It preserves all data, failures and audit history. This is a
configuration/protection rollback; it is not a historical application rollback.

## Evidence boundaries

Focused tests and operator-driven headed Chrome/Edge runs use isolated synthetic
fixtures. Those runs cannot establish owner inbox receipt or owner workstation
behavior. The exact browser versions, actual executed cases, activation result
and served revision are recorded in the protected continuation checkpoint.

The existing real invitation remains unchanged. No replacement invitation is
authorized merely because browser access failed. After served access passes,
continue the owner's original link in Edge or Chrome, then the one approved
recovery. Provider acceptance, delivery, inbox receipt and completed account
flows must remain separate evidence. No public launch or penetration-test
completion is implied.

## Candidate evidence before activation

On 2026-09-20, headed Linux Chrome for Testing147.0.7727.15 and Microsoft
Edge153.0.4234.48 each passed47 checks in isolated browser contexts under Xvfb,
using normal certificate validation on the loopback-only HTTPS fixture. The
normal invitation and recovery forms completed in each browser, with one
welcome grant, target-only password change, invalidated previous account
session, department/API/file isolation and used-link refusal. Idle and absolute
expiry used explicitly aged isolated sessions, not a claim of elapsed real time.

Protected evidence: `preview-form-browser-20260920/attempt-035801/browser-report-3.json`
and six screenshots. Source hashes were unchanged during that successful run.
Earlier failures remain: a separate Playwright request-client DNS mismatch, then
the demonstrated browser CSRF/referrer defect. The final run uses the corrected
same-origin browser transport. No provider call or owner inbox interaction ran.

Backend evidence includes56 focused checks and17 final boundary checks (these
counts overlap), plus the narrow referrer repair. The final operator regression
batch passed23 checks. A wrong-working-directory test invocation failed before
discovery; its transcript and the correctly rerun passing batch are both kept.
Served regular-profile Chrome/Edge checks and activation are subsequent evidence,
not implied by these candidate results.
