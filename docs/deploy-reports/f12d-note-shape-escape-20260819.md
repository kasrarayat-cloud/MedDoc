# Deploy report — F12-d, the note-shape E/M escape · 2026-08-19T03:00Z

**Deployed commit:** `0c3698b1087141d9fa55c56675487e17b9506380`
**Declaration judged against:** `docs/foundation/deploys/20260819-ed2058c8.md`
**Runtime change:** PR #735 (`ed2058c8`); `0c3698b1` and `924c29a6` are docs-only.

⚠️ **PROVENANCE OF THIS FILE, STATED FIRST BECAUSE IT CHANGES HOW TO READ IT.**
The deploy and its judgement were performed by **run `20260818-232127-b1`
session 01**. This report is written by **session 02** and is a TRANSCRIPTION of
that session's judgement out of its log
(`docs/foundation/logs/20260818-232127-b1-run01.log`) into the tracked path,
which session 01 recorded as owed. **The numbers in §1 and §2 were observed by
session 01 at deploy time and are not re-measurable after the fact** — a
post-deploy comparison run later would be describing a different moment. §3 is
session 02's own re-measurement, taken at `03:08Z`, and is labelled as such.

*Evidence is only evidence on the tree it describes; saying which half you have
is the whole discipline.*

## 1 · Verdict — 15 of 16 rows judged exact, 1 declared value wrong

| | |
|---|---|
| declared rows | 16 |
| matched exactly | **15** |
| differed | **1** — declared row 3, the traversal control |

### The row that differed, and why it is recorded rather than absorbed

Declaration row 3 was a **traversal control**: *"`note-shape.ts` contains
`OFFICE_SKELETON_SECTIONS` — before **5**, after **5** (non-zero)"*. Measured
after the deploy it read **6**.

⚠️ **THE CAUSE IS THE AUTHOR'S OWN DIFF.** F12-d added `officeConceptCount`,
which introduces a sixth reference to `OFFICE_SKELETON_SECTIONS`. The row's
PURPOSE held — it is there so a broken grep is distinguishable from a true zero,
and a non-zero value satisfies that — but the *declared value* was not measured
against the change being declared.

**Session 01 recorded this against itself rather than absorbing it**, and the
rule it invokes is the right one: *a difference the declaration does not name is
the finding, whatever the explanation sounds like afterwards.*

**Carried forward:** F12-f's declaration
(`docs/foundation/deploys/20260819-6ee342aa.md`) declares its traversal control
at **7**, measured on the branch file rather than predicted, and says in the row
itself that the figure moves because the diff adds references.

## 2 · The rows, as judged at deploy time (session 01)

**Clinical counts — all MUST-NOT-CHANGE, all unmoved:**

| quantity | declared | observed |
|---|---|---|
| visits | 48 | 48 |
| signed visits | 30 | 30 |
| patients | 35 | 35 |
| note_templates | 10 | 10 |
| migrations applied | 104 | 104 |
| `cptCodes.em.code` | 10 | 10 |
| frozen `cptCodes.em.signedCode` | 6 | 6 |
| `cptCodes.emSuppressed` | 0 | 0 |
| twin compiled versions | 1 | 1 |
| twin CERTIFIED | 0 | 0 |
| twin fill manifests | 0 | 0 |

**Structural:** row 1 (`officeConceptCount` present) 0 → ≥1 ✔ · row 2 — the
ABSENCE row, the old unconditional template arm — 1 → 0 ✔ · row 4 (both service
image ids differ) ✔.

**Behavioural:** exactly ONE production visit's verdict changes —
`cmsu1mhrp000h01nsxpvxxshk`, from suppressed to applies. Measured through the
shipped predicate over all 48 visits in production's flag universe: **+0 newly
suppressed, 1 newly applied.** Verified structurally; no visit was signed,
adopted or exported to check it.

**Environment:** co-tenants 5 of 5 at their expected codes · ingress TLS 🟢 ·
imaging E/M invariant 🟢 (0 of 20).

## 3 · Independent re-measurement — session 02, 2026-08-19T03:08Z

Taken ~8 minutes after the deploy, as this session's STEP 0. **This is a
statement about the system now, not a re-judgement of the deploy.**

| check | result |
|---|---|
| `assert-migrations-applied` (prod) | 🟢 104 of 104 |
| `assert-migrations-applied --qa` | 🟢 104 of 104 |
| `check-imaging-em-artifacts` | 🟢 0 of 20 |
| `check-qa-mock-posture` | 🟢 vendor-severed, flag manifest matches live containers |
| `check-minio-encrypted-mount` | 🟢 verified against the kernel |
| `check-pg-encrypted-mount` | 🟢 verified against the kernel |
| `check-ingress-tls` | 🟢 fresh handshake per SNI, bogus-SNI control refused |
| `check-composite-fk` | 🟢 present and correctly shaped |
| `check-bind-mount-agreement` | 🟢 content agrees (one inode diverged — expected after a branch switch, not a fault) |
| `check-hooks-installed` | 🟢 both hooks live |
| `check-cotenants` | 🟢 5 of 5, 4 distinct codes so the probe discriminates |
| citation on `0c3698b1` | 🟢 **4 of 4**, every line `a1` — `CI` 32208357606 · `e2e` 32208357602 · `a11y-ci` 32208357610 · `secrets-scan` 32208357603 |

Baseline re-read at `03:31Z` for F12-f's declaration is identical on every
shared row, and the most recent visit is still `2026-08-18 20:37:53Z` — **no
doctor activity between the two deploys**, so the MUST-NOT-CHANGE rows above are
being compared against a genuinely static population.

## 4 · What this report does not cover

- **It is not an independent re-run of the deploy-time comparison.** §1 and §2
  are session 01's observations, transcribed. Their falsifiability comes from
  the declaration's commit preceding the act, not from this file.
- **No rendered PDF or DOCX was produced and compared**, at deploy time or now.
- The behavioural row was verified **structurally**, against stored columns and
  the shipped predicate inside the worker container. Nothing was signed,
  adopted or exported.
