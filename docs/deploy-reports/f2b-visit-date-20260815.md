# DEPLOY REPORT — F2-b, the visit date is the encounter's date

**Deployed `85e82be5190890aa2f24a52292c9a458e18904bd` at `2026-08-15T12:50Z`.**
Judged against `docs/foundation/deploys/20260815-85e82be5.md`, which is a
verbatim copy of the declaration committed in PR #670 **before this merge commit
existed**.

**Merge-commit citation — 4 of 4, every line `a1` (no re-runs):**
`CI` 31883766135 · `e2e` 31883766151 · `a11y-ci` 31883766123 ·
`secrets-scan` 31883766185. Produced by `scripts/check-citation.sh`, not typed.

---

## VERDICT — 14 of 14 declared rows matched

### MUST CHANGE

| # | declared | measured | ✓ |
|---|---|---|---|
| 1 | `transcribe-md` image id moves | `bc4e06c609be…` → `d1108cb1081b…` | ✓ |
| 2 | `transcribe-md-worker` image id moves | `b8f373321a21…` → `cffabcc2d97b…` | ✓ |
| 3 | the visit-date row renders `createdAt` on every surface | shipped in the running worker: docx **1**, pdf **1**, ehr **1**, loader **1**; old fallback **0** | ✓ |
| 4 | Redis preview keys move to `visitdoc:v4:` | `visitdoc:v4` **2** occurrences (writer + SCAN), `visitdoc:v3:` **0** | ✓ |

### MUST NOT CHANGE

| # | declared | measured | ✓ |
|---|---|---|---|
| 5 | visits **45** | 45 | ✓ |
| 6 | signed **27** | 27 | ✓ |
| 7 | patients **32** | 32 | ✓ |
| 8 | templates **9** | 9 | ✓ |
| 9 | `audit_logs` monotonic from **11475** | 11477 (+2, the deploy's own rows) | ✓ |
| 10 | migrations stay **104** | 104 in repo, 104 recorded | ✓ |
| 11 | twin tables stay **0 / 0** | compiled 0, manifests 0 | ✓ |
| 12 | **the signature chrome still reads `signedAt`** | docx **1**, pdf **1**, ehr **1** read `data.signedAt`; **0** read `createdAt`; the form attestation still reads `signedWhen` | ✓ |
| 13 | the two email senders keep sending the SIGNING date | `signedDate: … signedAt ?? createdAt` intact, both sites | ✓ |
| 14 | co-tenants unchanged | `app` 307 · `admin` 404 · `quillmd` 200 · `www` 200 · `pro` 410 | ✓ |

Containers: 9 of 9 healthy; app and worker both `Up` and healthy after recreate.
`app /api/health` → **200**.

⚠️ **ROW 12 IS THE ONE THAT MATTERED MOST TO CHECK.** The over-correction — an
encounter date leaking into the signature line — is a worse document than the
defect being fixed, and a presence-only declaration cannot see it. It is
measured as an ABSENCE row (`0` signature lines reading `createdAt`) against
three must-exist controls, so a blind probe would have failed the controls
rather than passing the absence.

---

## ⚠️ FINDING — I DECLARED A ROLLBACK PATH THAT DID NOT EXIST

The declaration's ROLLBACK section named
`meddoc-pro-transcribe-md:pre-visitdate-20260815` and its worker twin as *"image
tags cut against the RUNNING ids before the deploy"*.

**`deploy-prod.sh` does not cut rollback tags.** It has no `docker tag` anywhere;
every previous `pre-*` tag on this host was cut BY HAND by the session that
deployed. So immediately after the deploy the declared rollback path did not
exist, and the sentence naming it was false at the moment it was most likely to
be needed.

**Caught by verifying my own declaration row rather than by any check** — the
deploy log echoes the declaration back, so the words *"Image tags cut…"* appear
in the log output and read exactly like a confirmation that they were.

**Repaired in place, and it was still repairable only by luck of timing:** both
pre-deploy images survived as dangling (`<none>:<none>`), so the tags were cut
against the exact ids the declaration names —

    bc4e06c609be  meddoc-pro-transcribe-md:pre-visitdate-20260815
    b8f373321a21  meddoc-pro-transcribe-md-worker:pre-visitdate-20260815

⚠️ **A `docker image prune` in that window would have made the rollback path
unrecoverable**, and nothing would have said so until somebody reached for it
during an incident. **Recorded as a standing hazard: a §2.5 declaration that
names rollback tags must CUT them, or say plainly that the operator must.**

---

## WHAT WAS NOT VERIFIED, NAMED HONESTLY

**The one document this deploy changes was NOT re-exported.**
`cmsdvjgf5000m01mmbs0srykk` is a real visit; a real doctor's visit is never a
smoke target, and exporting one to prove a change works is editing a medical
record for convenience. The proof here is structural — the corrected code is
present in the running images, with must-exist controls proving the probe
discriminates — and the clinical confirmation is the **owner ping** below.

**Neither native-fill leg was exercised.** `pdf-native` is live in production (4
certified templates, canvases in MinIO, 8 signed visits bound) but needs a real
export to exercise; the twin leg has 0 compiled versions. Both are asserted at
source, by consumption, and the gap is real.

**The `#115-b` half changed zero documents today** — 8 signed visits sit on
`dd/dt` templates and 0 of them have diverging dates (measured directly, not
deduced). It is armed for the next operative note whose dictation and signing
fall on different days.

---

## OWNER PING

**Re-export visit `cmsdvjgf5000m01mmbs0srykk`. The visit-date row should read
2026-08-03; the signature line should still read 2026-08-10.** That single
document is the entire live payload of this deploy.
