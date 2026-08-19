# Deploy report — F12-f, the operative counterweight counts concepts · 2026-08-19T05:03:56Z

**Deployed commit:** `24b739f9eac155b6f614ab7f80cdc993ad03ee05` (merge of PR #737)
**Declaration judged against:** `docs/foundation/deploys/20260819-fc8e7790.md`
**Resolution:** **CARRY-FORWARD** — `fc8e7790` is an ancestor 2 commits back;
`fc8e7790..24b739f9` is **6 files changed, 0 of them runtime**. The gate's own
non-emptiness control fired: the range is non-empty, so a zero-runtime diff over
an empty range could not have produced this pass.

**Citation on the deployed commit — 4 of 4, every line `a1`:**

- `CI` **32215456960** `a1`
- `e2e` **32215456851** `a1`
- `a11y-ci` **32215456842** `a1`
- `secrets-scan` **32215456821** `a1`

Produced by `scripts/check-citation.sh`, not typed. The PR head
(`99c518d91483c4f6b18296c20d6647e68cfb9f4c`) was separately cited 4 of 4, also
all `a1` — no re-run anywhere, so nothing needs explaining.

## Verdict — **26 of 26 rows judged exact**

| group | rows | result |
|---|---|---|
| MUST CHANGE — structural, read from the running worker | 8 | **8 exact** |
| MUST NOT CHANGE — clinical and twin counts | 12 | **12 unmoved** |
| MUST NOT CHANGE — co-tenants | 5 | **5 at expected** |
| BEHAVIOURAL — production verdict delta | 1 | **exact (zero)** |

### Structural — the running worker's own source

| # | row | declared | observed |
|---|---|---|---|
| 1 | `officeConceptCount(labels) >= OFFICE_COUNTERWEIGHT_FLOOR` | 0 → **1** | **1** ✔ |
| 2 | ⚠️ ABSENCE — `countOfficeSkeleton(labels) >= OFFICE_SKELETON_FLOOR` | 1 → **0** | **0** ✔ |
| 3 | `REFUSED_OFFICE_CONCEPT_SYNONYMS` | 0 → **4** | **4** ✔ |
| 4 | ⚠️ ABSENCE — `'RECOMMENDATIONS', ['PLAN']` | 0 → **0** | **0** ✔ |
| 5 | `officeConceptCount([l]) > 0` — the `templateIsSilent` half | 0 → **1** | **1** ✔ |
| 6 | ⚠️ ABSENCE — `labels.every((l) => OFFICE_SKELETON_SECTIONS.includes(l))` | 1 → **0** | **0** ✔ |
| 7 | traversal control — `OFFICE_SKELETON_SECTIONS` | 6 → **6** | **6** ✔ |
| 8 | both service image ids differ from pre-deploy | differ | **differ** ✔ |

⚠️ **ROW 4 WAS GIVEN ITS OWN POSITIVE CONTROL, BECAUSE `0 → 0` CANNOT
DISCRIMINATE ALONE.** A grep that returns 0 because the file changed and a grep
that returns 0 because it is broken produce the same output. Control: the same
matcher, relaxed to `'RECOMMENDATIONS',` — the label as a plain refused-list
entry — returns **1** in the same file. So the region is reachable, the matcher
works, and the zero is a real absence rather than a blind one.

**Row 8, by digest.** Rollback tags were cut against the RUNNING images
pre-deploy: `transcribe-md` `ea5c6a81…`, `worker` `d0c570a4…`. After deploy the
live containers report `c6b0dd34…` and `c3caed78…`. Both differ.

### Clinical and twin counts — all MUST-NOT-CHANGE, all unmoved

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
| `emScoredCode` | 17 | 17 |
| twin compiled versions | 1 | 1 |
| twin CERTIFIED versions | 0 | 0 (`NEEDS_CONFIRMATION`) |
| twin fill manifests | 0 | 0 |

Most recent visit `createdAt` is still `2026-08-18 20:37:53Z` — **unchanged
across both of tonight's deploys**, so these counts were compared against a
genuinely static population rather than one that happened not to move.

### Behavioural — the declared ZERO

| row | declared | observed |
|---|---|---|
| production visits whose E/M verdict changes | **0** | **0** |

**9 apply / 39 suppressed, before and after.** Measured through the real
`emAppliesToVisit` over all 48 visits in production's flag universe
(`NEXT_PUBLIC_ULTRASOUND_SPECIALTY=true`, read from the running containers).

⚠️ **AND THE HARNESS WAS PROVED TO BE MEASURING THE SHIPPED CODE, NOT A
LOOKALIKE.** `sha256sum` of `note-shape.ts` inside
`meddoc-pro-transcribe-md-worker-1` and of the file the harness imports are
**identical** (`78f2a6c3e299d407dec6ed273c603255b76672a889bfcad873ae209db6f1ccee`).
A behavioural claim run against a same-branch copy that had drifted would look
exactly like this one.

⚠️ **VERIFIED STRUCTURALLY. Nothing was signed, adopted or exported.** A real
doctor's visit is never a smoke target.

### Environment

| check | result |
|---|---|
| co-tenants | 🟢 5 of 5 — `quillmd` 200 · `www` 200 · `app` 307 · `admin` 404 · `pro` 410 (4 distinct codes, so the probe discriminates) |
| `assert-migrations-applied` | 🟢 104 of 104 |
| `check-imaging-em-artifacts` | 🟢 0 of 20 |
| `check-ingress-tls` | 🟢 fresh handshake per SNI |
| container health | 🟢 9 of 9; `transcribe-md` and `worker` recreated, both healthy |

## What this deploy does NOT claim

- **No production verdict moved, by design.** The value is forward: three note
  shapes that would have been over-suppressed no longer are, exercised by
  forward probes in the gate rather than by any row production holds. **A
  verdict movement would have been the finding**, in either direction.
- **The residual is not closed** — an office note in a non-SOAP vocabulary under
  an operative template is still over-suppressed, pinned by a gate arm. The
  template concerned is ACTIVE and bound to **0** visits.
- **F12-g is untouched.** 15 non-ultrasound visits still carry office E/M state
  under a false verdict; `check-imaging-em-artifacts.sh` is
  `where specialty='ultrasound'` and does not watch them. Its 🟢 above is true
  and covers none of them.
- **No rendered PDF or DOCX was produced and compared.**
- ⚠️ **The templated-operative E2E class is not delivered — F12-h**, deferred on
  a measured `e2e` ceiling.

## A note on this deploy's payload versus its declaration

`24b739f9`'s parent is `0c3698b1`, which was already live. So the payload of
this deploy is exactly F12-f and nothing else, and the declaration's scope is
the full diff being shipped — the two-changes-one-deploy hazard does not apply
here. Stated rather than assumed, because *"I deployed `main`" is not the same
claim as "I judged what I deployed."*
