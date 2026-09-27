# QuillMD V1 — frozen product contract

Frozen 2026-09-27. **V1** means: invited doctors only, real patient data, first clinics and patients in the
United States, and working day-to-day functions. Every function exposed to a user is listed here with the
path it works through, the evidence behind it and its V1 status. **Nothing exposed is silently dropped.** A
function that is not ready is either repaired, gated off with its reason shown, or listed as a blocker.

Base: the installed release `dedac162` (verified via `/health/` on both surfaces). `release/v1` branches from
it; `origin/main` (`80fb591b`) is one tooling PR ahead. PR #1287 (WM narrative) stays a **draft**. It is not
merged to call anything V1. Only its flag-independent review fixes are ported (see "Review guards").

Status words: **READY** — works and tested on synthetic data; **REPAIRED** — defect found and fixed on a
V1 branch (not yet installed); **BUILT** — new V1 work on a branch (not yet installed); **BLOCKED** — cannot
meet V1 until an item on `V1-BLOCKERS.md` clears; **OFF** — deliberately disabled with a visible reason.

## Access and accounts

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Registration | **invitation-only** in real mode (`QUILLMD_REGISTRATION=invite`: `/register/` is 404); clinic-owner invitations | blockers stream `cc7413eb`; refuted (held) | BUILT |
| Email verification / invitation acceptance / password recovery | token links; account email carries only `{link}` — never clinical content | `d97bd05e`; refuted (held) | BUILT (copy per data mode) |
| Login, sessions, logout | Argon2, 12-char minimum, 30-min idle, per-client rate limits behind the trusted proxy | `599aea10` | BUILT |
| MFA | **required for every account** in real mode (`QUILLMD_MFA_REQUIRED_ALL=1`); staff "Reset MFA" with reason | `cb40c17f`; refuted (held) | BUILT |
| Account self-management (password change in session, profile, deletion, data export) | not offered; password changes go through recovery | inventory | OFF — listed, not silently missing |
| Organization / department / role isolation | per-department scoping on routes, files and exports | internal tests | READY; independent retest is a blocker (pentest) |

## Clinical workflow

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Patients (create, list, search) | department-scoped; synthetic attestation removed in real mode | inventory | READY (no patient detail/edit page — OFF, listed) |
| Typed notes | 1–50,000 characters, revision-checked | tests | READY |
| Voice (upload/record → transcript review → notes) | consent, signed quote, Deepgram with `mip_opt_out` in real mode; nothing reaches the notes until reviewed | `45f53519` (+ repair pending) | BUILT; BLOCKED on Deepgram BAA + pricing check |
| **Answers from ordinary (unlabelled) typed or dictated notes on custom forms** | today: only labelled `Label: value` lines; any unlabelled line returns every answer as a conflict | inventory (VERIFIED) | **BLOCKED** — a generic sentence-selection path is designed, not built (B-G1) |
| Answers on the colonoscopy (tab) form | natural sentence-selection contract | tests; live runs in docs | READY |
| Answers on the WM IOV form | labelled lines + prewritten statements; narrative reader stays a draft (PR #1287) | tests | READY (labelled only) |
| Review, correction, held candidates, leave blank | explicit accept by owner/clinician; evidence shown | tests | READY |
| **Review guards** — no generation over reviewed answers; WM statement decisions kept on an employee save; finalized record not re-reviewed; `&` rewrite blocker | ported from PR #1287 onto `v1/review-guards` | in progress | BUILT (pending) |
| Finalization | owner/clinician, confirmation, revision match, original hash match | tests | READY |
| Export | original format only, hash-checked | tests | READY |
| Coding | ICD-10-CM only, explicit codes, by service date | tests | READY; **CPT OFF** (licence) |

## Custom Word forms (release gate)

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Upload of blank `.docx` | sandboxed inspection; macros/active content/external links/tracked changes refused by name; `.doc` refused with a save-as-.docx instruction | engine | READY |
| Detection of every answer area (F1–F10) | contract v3 (`word_v3.py`) behind `QUILLMD_WORD_ENGINE` | dev 3/40, **holdout 0/20** automatic | **BLOCKED** (B-W1) |
| Visual mapping review + corrections (add / remove / kind / label), manual mapping recorded separately, clinician confirmation before use | Word integration stream | in progress | BUILT (pending) |
| Answers for choice / multi-choice / checkbox / table kinds | explicit-option-only filling; everything else held for the clinician | in progress | BUILT (pending) |
| Faithful export | v3 writers: only touched parts change; signatures never filled; bounded capacity where the page cannot grow | 18/20 holdout exports clean; H08 control defect repaired | REPAIRED (to be judged on the qualification cohort) |
| Qualified WM IOV and colonoscopy forms | existing pinned / tab paths | tests | READY |

## Money

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Wallets, holds, 1.5× charge, ledger, "explain this charge" | unchanged; hold before request, charge ≤ hold | tests | READY |
| Top-up (Stripe Checkout) | live mode: live keys, `livemode=true` only, public HTTPS return; real mode refuses sandbox payments | `067b381c` + R1/R2 repairs pending | BUILT; BLOCKED on the live Stripe account (external) |
| Promotional credit | `QUILLMD_WELCOME_CREDIT` (policy is the owner's) | `cc7413eb` | BUILT |
| Refunds, credit adjustments | Stripe dashboard only; console read-only | inventory | OFF by design |

## Language model

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| `claude-sonnet-5` | model-keyed request profile (explicit thinking/effort, no sampling params), refusal/incomplete never adopted, new receipts record geography/thinking/stop, 1.5× preserved, 4.6 rollback byte-identical | `v1/sonnet5` (5 commits + repairs pending) | BUILT — **prepared, not configured**: needs owner config switch + bounded live check |

## Administration, audit, operations

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Admin console (MFA, overview, users, orgs, jobs, costs, audit) | admin behind the TLS proxy honours the proxy header | `169b0b2f` | BUILT |
| Audit | append-only rows, hashes not text | tests | READY |
| Production host (AWS), backups, restore drill, alerts, monitoring, retention/deletion | production profile + hosting package | `v1/prodprofile` | BUILT (package) / BLOCKED (external: accounts, BAA, custodians, counsel) |

## Explicit non-goals for V1 (listed so they are not mistaken for omissions)

CPT coding; the WM narrative reader (PR #1287, draft); PDF output of Word forms; patient detail/edit pages;
self-service account deletion/export; refunds in-app; open registration. Each one stays visible as OFF.
