# QuillMD private application design lock

2026-09-17. Direct implementation follows the user's instruction to build the
working application. This record applies to the new doctor and administrator
interfaces; it does not authorize changes to the preserved marketing website.

## Research and scope

Designing a browser workspace for clinicians completing their own clinical forms,
and a separate operational workspace for administrators. The primary goal is to
follow a documented statement from source notes through an editable answer into
the clinician's original form. The principal risk is a polished surface hiding
missing evidence, simulated integrations, or unreviewed clinical content.

Live Refero tools are unavailable. Research used the installed Refero skill's
bundled `typography.md`, `color.md`, `craft-details.md`, `anti-ai-slop.md`, and
`visual-workflow.md` references. These are craft references, not claims that live
product screens or customer research were reviewed.

## Reference lock

Primary direction: a precise, light clinical document workspace. The typography
reference's functional-product guidance owns density and type: system sans,
comfortable reading line heights, compact labels, and restrained heading sizes.
The craft-details reference owns accessible forms, keyboard focus, native links,
inline errors, and URL-addressable page states. The anti-slop reference owns
surface restraint: ruled sections and tables, no decorative cards or gradients.

Preserve: white workspace, near-white document surround, clear teal active state,
compact sidebar navigation, document/evidence split, and real text-based statuses.
The distinctive product detail is a paired answer and source citation, with a
separate review decision. Clinical evidence stays visually adjacent to the text
it supports. No invented preview content or numerical evidence is permitted.

Borrow only: tabular numeric alignment for money and status indicators with text.
Media: document content is the relevant media. There is no decorative bitmap
image requirement, no generated hero, and no fabricated document screenshot.
Reject: generic marketing heroes, statistics without data, rounded card grids,
decorative serif headings, gradients, and color as the sole status indicator.

## Tokens and decision ledger

| Decision | Source | Role | Why |
| --- | --- | --- | --- |
| System sans, 14–16 px interface, 30 px page heading | Typography reference | Functional-product type | Clinicians scan questions and read complete answers |
| White canvas, `#f5f7f7` surround, `#172d31` text | Color reference, user workflow | Neutral content surfaces | Original documents remain the focus |
| `#12695f` teal | Color reference | Actions and current navigation only | Makes the next action visible without coloring clinical claims |
| Amber/red with explanatory text | Craft details, source evidence requirement | Missing/conflicting/error state | Never relies on color alone |
| Thin dividers; 6 px control radius | Anti-slop reference | Grouping and interactive controls | Dense records need clear relationships, not decoration |
| Sidebar + primary page + evidence aside | User's complete workflow | Navigation and source comparison | Preserves orientation while reviewing individual answers |
| Inline errors, skip link, focus ring, explicit labels | Craft details | Accessible interaction | Supports keyboard use and recoverable form errors |
| Source notes never line-clamped | User's no-truncation requirement | Clinical text | Prevents hiding clinically relevant information |
| Explicit synthetic/private environment banner | User's patient-data constraint | Environment disclosure | Distinguishes private verification from approved patient use |
| Separate paid/personal-promotion amounts | User's billing requirement | Financial explanation | Explains which credit pays for usage |
| No external fonts/scripts/assets | User's secrets/private access requirements | Resource loading | Avoids incidental third-party requests from patient workflows |

## Journey lock

Upload original → inspect/version field mapping → select patient and enter notes
→ generate answer draft → compare each answer with evidence and resolve missing
or conflicting information → clinician review → finalize → export filled form.
Coding is a separate tab with explicit acceptance. Payment and terminology
availability appear as actual provider states rather than affirmative claims.

## Verification record

Implementation evidence will be captured against running private doctor/admin
routes at desktop and mobile widths. Inspect navigation, overflow, form errors,
answer/source readability, empty states, and state disclosures. A rendered visual
pass is required before UI handoff; any blocked state must be named below.


### Completed private browser verification

- Chromium at `127.0.0.1:9130` and `127.0.0.1:9131`, 1440×1080 desktop
  and 390×844 mobile; screenshots and reports are private, ignored files under
  `rebuild/.runtime/ui/` and `rebuild/.runtime/ui-*.json`.
- Clinical browser workflow passed: individual sign-in; blank DOCX upload;
  mapping inspection and v2 save; patient/form selection; source notes; synthetic
  answer generation; all three source citations; individual review decisions;
  separate coding tab and availability disclosure; finalization; DOCX download.
- The first run found an HTTP 500 when creating a draft. The lead repaired draft
  model validation. The complete clinical flow then passed. This was an actual
  running application test, not a mocked request or static page.
- The initial all-pages script completed 27 checks, then a test assertion found
  two “Accounts” headings (one statistic and one section). Statistic labels were
  changed to ordinary text. The remaining 11 administrator/audit checks passed
  in a targeted rerun. The script's first failure remains in the private report
  rather than being erased.
- Administrator TOTP sign-in, all eight operational sections, filtered audit
  history, and doctor exclusion from administrator pages passed.
- Six doctor routes and the administrator dashboard have no document-level
  horizontal overflow at 390 px. Tables and navigation scroll within their own
  containers. Mobile sign-out is available.
- Axe WCAG 2 A/AA and 2.1 AA checks reported zero violations on sign-in,
  workspace, upload, and patients. This is a limited automated accessibility
  check, not an accessibility certification.
- Visual inspection against the lock covered desktop sign-in/workspace/review/
  administration and mobile patient/review screens. No unresolved P0/P1/P2 visual
  issue was found. No client JavaScript errors were observed.

The browser proof above used the explicitly labelled synthetic generation
provider. It does not claim verification of a live AI provider, paid Stripe
checkout, licensed CPT content, or microphone hardware. Microphone capture is
implemented with browser permission and explicit transcription submission;
provider-side testing is recorded separately by the lead.


### Usage consent and provider receipts

The next generation/transcription action shows its maximum reservation before
submission, the exact 1.5× final-cost rule, and personal promotional-credit priority.
Synthetic generation explicitly shows a $0 charge and no live AI call. Missing
quote context disables submission until the application supplies a quote.

Administration includes a provider receipt table with provider, request identifier,
full-precision actual cost, job identifier, and job status even while settlement is
held. It does not expose raw clinical provider responses. A departmental document
job offers an authenticated result download only when its stored result path exists. The
backend remains responsible for authorization of that download.


### Durable browser regression gate

`rebuild/browser-tests.mjs` now runs the seeded synthetic clinical workflow through
real loopback HTTP and Chromium. Its latest run passed all **12 checks**, including
desktop/mobile login and workspace Axe checks, explicit fixture/$0 disclosure,
source evidence, clinical review, finalization, DOCX export, and administrator
exclusion. It uses the project's installed Playwright/Axe versions and rejects
non-loopback targets or a live AI provider. The temporary fixture server used for
verification was stopped after the run; the persistent private preview was not
reconfigured.

`.github/workflows/test.yml` defines the **Private browser and accessibility** job
with its own PostgreSQL service, fresh synthetic seed, server, and worker. Only
the nonclinical JSON check report is uploaded as a CI artifact. Screenshots and
exports are local ignored scratch files and are deleted after verification.
Passwords, OTP material, provider response payloads, and raw Playwright exceptions
are never included in its report. Remote CI execution is a separate gate from
this successful local run.

## Private beta recovery extension — 2026-09-17

Reference lock: reuse the existing auth-shell, native labelled inputs, focus states, inline errors and teal action styles above. Refero MCP is unavailable; craft-details forms/focus and the existing sign-in/register screens were reviewed before implementation. Add request → private-outbox/provider-acceptance disclosure → expiring link → password reset → explicit sign-in. Administrator password recovery also requires the existing authenticator; losing it invokes a separately verified operator recovery process. Generic request responses avoid account enumeration. No new visual tokens or external assets.
