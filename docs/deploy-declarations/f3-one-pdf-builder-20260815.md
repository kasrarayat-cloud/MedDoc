# §2.5 DEPLOY DECLARATION — F3, one PDF builder

**Written BEFORE the act**, and committed in F3's own PR so that its commit
timestamp provably precedes any deploy taken against it. The deploy path's
strictness is `present`, not `strict` (ruling #96(b)'s reversibility logic), so
nothing MECHANICALLY proves the ordering — what does exist is this file's commit
landing in the PR that introduces the change, before the merge commit exists.

Branch `fix/f3-retire-generate-visit-pdf` · rulings **#113**, **#116**, **#116-b**
· RELAY **F3**.

At deploy time this file is copied verbatim to
`docs/foundation/deploys/<UTC-date>-<short-sha>.md`, which is the only filename
`scripts/deploy-prod.sh` accepts. Only a header naming the SHA may differ.

---

## WHAT SHIPS

**A code-only change. No migration. No schema change. No flag change.**

`generateVisitPdf` / `pdf-generator.ts` (pdfkit) is **deleted**. Every visit PDF
is now `generateVisitDocx` → Gotenberg, which is the path the preview has always
taken. Five callers dispositioned per #116: three converged, two deleted.

**Behaviour a doctor can observe:**

1. **The downloaded PDF is now LibreOffice's render of the Word file.** It gains
   the template and `formatHint` awareness the pdfkit builder never had — which
   is the point — and its typography is the converter's rather than pdfkit's.
2. **⚠️ A NEW FAILURE MODE, ACCEPTED AND NAMED IN ADVANCE (#116(c)).** With no
   second builder there is no fallback: if the Gotenberg sidecar is down, the
   PDF download returns **503** naming the converter's reason and pointing at
   the Word export. Before this change it would have returned a pdfkit PDF.
   **This is the declared cost, not a regression.**
3. **Both archive ZIPs** name a failed render in place
   (`visits/<id>/signed.pdf.UNAVAILABLE.txt`) instead of omitting the file.
4. **`POST /sign` and `POST /export/email` no longer render a PDF at all.**

---

## THE BASELINE — MEASURED ON PRODUCTION, READ-ONLY, BEFORE THE ACT

Taken 2026-08-15, ~17:0xZ, on `meddoc`:

| quantity | value |
|---|---|
| `transcribe_visits` | **45** |
| of those, signed (`signedAt` not null) | **27** |
| `transcribe_md_patients` | **32** |
| `visit_deliveries` total | **95** |

`visit_deliveries` by channel, with the population of `sizeBytes`:

| channel | rows | with `sizeBytes` |
|---|---|---|
| `clipboard_epic` | 2 | 2 |
| `docx` | 42 | 21 |
| `email` | **1** | **1** |
| `pdf` | 50 | 25 |

`audit_logs` export actions:

| action | rows |
|---|---|
| `EXPORT_ACCOUNT_ARCHIVE_DOWNLOADED` | 5 |
| `EXPORT_CLIPBOARD_COPIED` | 1 |
| `EXPORT_DOCX_DOWNLOADED` | 35 |
| `EXPORT_PDF_DOWNLOADED` | 42 |
| **`EXPORT_EMAIL_SENT`** | **0** |

---

## ⚠️ WHICH PRODUCTION ROWS THIS ACTUALLY TOUCHES — AND ONE OF THE TWO FIXES IS LATENT

**Ruling #116-b's audit-row fix changes NOTHING that exists today.**
`EXPORT_EMAIL_SENT` has **0 rows on production**. The `sizeBytes` this deploy
stops writing into that row has therefore never been written once. The fix is
**latent, not live** — armed for the first doctor who emails a note, exactly as
#115-b was. Saying so is the point: a declaration that implied it was repairing
live records would be claiming a result it cannot have.

**The `logDelivery` half is nearly as quiet:** one `email` delivery row exists,
and it keeps its value. No existing row is rewritten by this deploy.

**The `pdf` channel keeps writing `sizeBytes`** — site 1 actually delivers the
document it measures, so that number stays honest.

---

## THE DECLARED DELTA — what MUST change, and what must NOT

### MUST change

- the **image ids** of `transcribe-md` and `transcribe-md-worker`
- `pdf-generator.js` must be **absent** from the built app bundle
- `visit-pdf` must be **present** in it

### MUST NOT change

- **`_prisma_migrations`: 104 applied, before and after.** No migration ships.
- **Every clinical count above, unchanged: 45 visits · 27 signed · 32 patients.**
  A deploy that moves one of these has done something nobody asked for.
- **`visit_deliveries` = 95**, and its per-channel breakdown unchanged. No row is
  rewritten and none is created by the deploy itself.
- **`audit_logs` export counts unchanged**, `EXPORT_EMAIL_SENT` still 0.
- **Co-tenants: `app` 307 · `admin` 404 · `quillmd` 200 · `www` 200 · `pro` 410.**
- **Container health: 9 of 9.**
- **No flag value changes.** `NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX` stays ON,
  `NEXT_PUBLIC_SETTINGS_SIMPLE_ROW` stays true, the native-PDF flag is untouched.
- **Twin tables stay at their current values** — this change does not reach them.

### ⚠️ MUST BE VERIFIED SPECIFICALLY, BECAUSE IT IS THE NEW DEPENDENCY

- **`gotenberg` is up and healthy after the deploy.** It was already a hard
  dependency of every preview; it is now a hard dependency of the PDF DOWNLOAD
  too. `scripts/deploy-prod.sh` already builds and recreates it (pinned by
  `gate-c2b-export-parity`), and that is now load-bearing for exports rather
  than only for previews.
- **A structural DOM/route check only.** ⚠️ **No production visit is exported to
  verify this.** A real doctor's visit is never a smoke target — the clinical
  walk belongs on QA against a byte-identical build.

---

## ROLLBACK

Image rollback to the tag cut against the running image ids at deploy time.
There is no flag to flip: the retirement is structural. Reversing it means
restoring `pdf-generator.ts` — ruling #113's own reversal path — after which the
legs diverge again with nothing watching, which is what #113 exists to prevent.

---

## HOW THIS IS JUDGED

Every MUST/MUST-NOT above is re-measured after the deploy **against this
document**, not against a fresh summary. **A difference that is not in this
declaration is THE FINDING**, whatever its explanation sounds like afterwards.

⚠️ **AND THE PAYLOAD MAY BE LARGER THAN THIS DECLARATION'S SCOPE.** If any other
change reaches `main` before this ships, the deploy carries it too and these rows
cannot detect a regression in it. *"I deployed `main`" is not the same claim as
"I judged what I deployed."* If that happens, say so and name the unjudged change.
