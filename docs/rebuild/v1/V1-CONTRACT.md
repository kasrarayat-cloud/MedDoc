# QuillMD V1 — frozen product contract

Frozen 2026-09-27. **V1** means: invited doctors only, real patient data, first clinics and patients in the
United States, and working day-to-day functions. Every function exposed to a user is listed here with the
path it works through, the evidence behind it and its V1 status. **Nothing exposed is silently dropped.** A
function that is not ready is either repaired, gated off with its reason shown, or listed as a blocker.

Base: the installed release `dedac162` (verified via `/health/` on both surfaces). `release/v1` branches from
it; `origin/main` (`80fb591b`) is one tooling PR ahead. PR #1287 (WM narrative) stays a **draft**. It is not
merged to call anything V1. Its shared review fixes and ordinary narrative path are classified against the
promised workflows; required narrative repairs remain in V1 scope (see B-G1).

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
| Voice (upload/record → transcript review → notes) | consent, signed quote, Deepgram with `mip_opt_out` in real mode; nothing reaches the notes until reviewed | reviewed account/input workflow repairs locally integrated | BUILT; BLOCKED on Deepgram BAA + pricing check |
| **Answers from ordinary (unlabelled) typed or dictated notes on custom forms** | source-unit selection, exact evidence, correction/negation/side guards; bounded whole-paragraph adoption for a unique narrative field | reviewed ordinary-note repairs locally integrated; additional source-context repairs in progress; synthetic worker-to-export evidence retained | **BUILT / BLOCKED** — excessive holds and useful positive coverage still need acceptance (B-G1); labelled notes are not a required workaround |
| Answers on the colonoscopy (tab) form | natural sentence-selection contract | tests; live runs in docs | READY |
| Answers on the WM IOV form | qualified original adapter retained; ordinary dictated/typed narratives require the necessary PR #1287 path and reviewed shared repairs | required subset locally integrated via `v1/wm-required-repairs`; 273 checks and repaired cleared-answer guard with80targeted checks; original PR #1287 preserved | **BLOCKED** for the promised ordinary-note workflow (B-G1); labelled-only operation does not satisfy V1 |
| Review, correction, held candidates, leave blank | explicit accept by owner/clinician; evidence shown | tests | READY |
| **Review guards** — no generation over reviewed answers; WM statement decisions kept on an employee save; finalized record not re-reviewed; `&` rewrite blocker | ported from PR #1287 onto `v1/review-guards` | `review-round4-recovery-20260927.md`; 1,224 core tests, 11 skips plus79finalfocused; independently refuted and locally integrated | REPAIRED locally; not installed |
| Finalization | owner/clinician, confirmation, revision match, original hash match | tests | READY |
| Export | original format only, hash-checked | tests | READY |
| Coding | ICD-10-CM only, explicit codes, by service date | tests | READY; **CPT OFF** (licence) |

## Custom Word forms (release gate)

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Upload of blank `.docx` | sandboxed inspection; macros/active content/external links/tracked changes refused by name; `.doc` refused with a save-as-.docx instruction | engine | READY |
| Detection of every answer area (F1–F10) | contract v3 (`word_v3.py`) behind `QUILLMD_WORD_ENGINE` | historical engine proxy: dev 3/40, **holdout 0/20**; incomplete end-to-end evidence; 44 declared lineages across 60 files | **BLOCKED** (B-W1); not a measured V1 automatic success rate |
| Visual mapping review + corrections (add / remove / kind / label), manual mapping recorded separately, clinician confirmation before use | Word integration stream; immutable original and mapping versions | 74 combined Word workflow checks; bounded Sonnet5 mapping assistance integrated with flags off and existing financial ledger | BUILT locally; corpus workflow qualification pending |
| Answers for choice / multi-choice / checkbox / table kinds | explicit-option-only filling; everything else held for the clinician | reviewed deterministic Word repairs and affected tests; corpus qualification pending | BUILT locally |
| Faithful export | v3 writers: only touched parts change; signatures never filled; bounded capacity where the page cannot grow | historical export proxy 18/20; earlier scorer lacked checkbox correctness and native Word acceptance; H08 control defect repaired | REPAIRED on branch; qualification remains open |
| Qualified WM IOV and colonoscopy forms | existing pinned / tab paths | tests | READY |

## File-format boundary

| format | current boundary |
|---|---|
| Editable `.docx` | Broad structural support is the V1 target and remains unqualified; the qualified WM original keeps its own adapter. No placeholder rewriting is required by the intended workflow. |
| Legacy binary `.doc` | Live upload explicitly refuses it with a save-as-unprotected-`.docx` instruction. The original D19 legacy file is preserved; an earlier conversion/render probe found only 2/17 expected areas correct and does not qualify a faithful automatic conversion path. This exception stays in the scored denominator. |
| Fillable PDF | Existing narrow text-only AcroForm path: fixed-size Helvetica, unrotated ordinary text fields, no checkbox/radio/dropdown/signature widgets or actions. It is not scanned-form recognition or Word-to-PDF export. |
| Encrypted/corrupt files, macros/active code, external relationships, tracked revisions, image-only/scanned forms | Explicit refusal or visible unsupported-area handling; no embedded code execution, external fetch, silent revision acceptance or OCR compatibility claim. |

Ordinary merged/nested tables, text boxes and content controls remain in the required Word families. They
are not broadly excluded to improve a percentage. A detected field is not proof of a successful export.

## Money

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Wallets, holds, 1.5× charge, ledger, "explain this charge" | unchanged; hold before request, charge ≤ hold | tests | READY |
| Top-up (Stripe Checkout) | live mode: live keys, `livemode=true` only, public HTTPS return; real mode refuses sandbox payments | reviewed real-mode/R5 repairs locally integrated, including independent statement-trigger finding | BUILT; BLOCKED on the live Stripe account (external) |
| Promotional credit | `QUILLMD_WELCOME_CREDIT` (policy is the owner's) | `cc7413eb` | BUILT |
| Refunds, credit adjustments | Stripe dashboard only; console read-only | inventory | OFF by design |

## Language model

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| `claude-sonnet-5` | model-keyed request profile (disabled thinking / medium effort), refusal/incomplete never adopted, new receipts record geography/thinking/stop, 1.5× preserved, 4.6 rollback preserved | account model metadata verified; four free token-count requests recorded; migration code on candidate | BUILT — **prepared, not served**; paid request and worker verification require eligible authority |

## Administration, audit, operations

| function | V1 path | evidence | V1 status |
|---|---|---|---|
| Admin console (MFA, overview, users, orgs, jobs, costs, audit) | admin behind the TLS proxy honours the proxy header | `169b0b2f` | BUILT |
| Audit | append-only rows, hashes not text | tests | READY |
| Production host (AWS), backups, restore drill, alerts, monitoring, retention/deletion | production profile + hosting package | production profile, hash-locked dependencies, RDS role/admin bootstrap and cutover package | BUILT (package) / BLOCKED (external: accounts, BAA, custodians, counsel) |

## Explicit non-goals for V1 (listed so they are not mistaken for omissions)

CPT coding; PDF output of Word forms; patient detail/edit pages;
self-service account deletion/export; refunds in-app; open registration. Each one stays visible as OFF.

The necessary WM narrative work is explicitly **not** a non-goal. No flag, labelled-note workaround or
assisted mapping result reduces the ordinary-note and automatic Word launch requirements.
