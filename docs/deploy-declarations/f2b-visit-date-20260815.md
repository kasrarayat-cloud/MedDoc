# §2.5 DEPLOY DECLARATION — F2-b, the visit date is the encounter's date

**Written BEFORE the act**, at `2026-08-15T11:17Z`, while PR for
`fix/visit-date-is-encounter-date` was still open and **before the merge commit
existed**. Every number below was measured on production, read-only, while the
outcome was still unknown. After the merge this file is copied verbatim to
`docs/foundation/deploys/20260815-<short-sha>.md` — the path
`scripts/deploy-prod.sh` reads — with only a header line naming the SHA the
original could not know.

Branch `fix/visit-date-is-encounter-date` · rulings **#115**, **#115-b** ·
RELAY **F2-b**.

---

## WHAT SHIPS

A **document-visible** change to what every clinical export says the visit date
is.

1. **The visit/surgery date renders `createdAt`, never `signedAt ?? createdAt`**
   — eight sites: `pdf-generator`, `docx-generator`, `ehr-formatters` (all five
   clipboard formats via one shared header), `visit-export-server` (the
   `DATE OF SURGERY` header field), `pdf-native/export`,
   `template-twin/native-export`, and both export FILENAMES.
2. **`DD:` / `DT:` on a form-only export render `createdAt`** (ruling #115-b).
   They are the DICTATION and TRANSCRIPTION dates; they were rendering the
   signing date.
3. **The preview fill-cache prefix moves `visitdoc:v3` → `visitdoc:v4`**, writer
   and `invalidateVisitFills` SCAN pattern together.

**Two sites deliberately UNCHANGED**: both email senders keep
`signedAt ?? createdAt`, because their body reads *"A note you SIGNED ON ${x}"*.
The parameter is renamed `visitDate` → `signedDate`.

---

## ⚠️ WHICH PRODUCTION ROWS THIS ACTUALLY TOUCHES — MEASURED, NOT ASSUMED

Measured read-only on `meddoc` at `2026-08-15T11:16Z`:

| population | count |
|---|---|
| visits total | **45** |
| signed (`signedAt IS NOT NULL`) | **27** |
| **signed AND `date(createdAt) <> date(signedAt)`** | **1** |
| signed, same UTC day | **26** |
| unsigned | **18** |

**Exactly ONE production document changes**, and it is ruling #115's own
reference visit:

    cmsdvjgf5000m01mmbs0srykk · ultrasound · noteTemplateId = NONE
    created 2026-08-03   signed 2026-08-10

Its exported document says **"Visit date: 2026-08-10"** today and must say
**"2026-08-03"** after.

**Why the other 44 are byte-identical, and it is arithmetic rather than hope:**
for the 26 same-day signed rows `formatVisitDate` is `toISOString().slice(0,10)`,
so both expressions produce the same string; for the 18 unsigned rows the old
`signedAt ?? createdAt` already resolved to `createdAt`.

### The form-only exposure — LATENT, and declared so it is not mistaken for live

| | count |
|---|---|
| templates with `formSignature.dd` or `.dt` | **4** |
| templates with `formOnlyExport = true` | **5** |
| **signed visits bound to a dd/dt template** | **8** |

⚠️ **All 8 have `date(createdAt) = date(signedAt)`, so ZERO documents change from
the #115-b half today.** It is armed for the next signed operative note whose
dictation and signing fall on different days — which is precisely the practice
whose form drove the ruling.

---

## BASELINE — measured on production immediately before

| quantity | value |
|---|---|
| visits | **45** |
| signed | **27** |
| patients | **32** |
| templates | **9** |
| `audit_logs` | **11475** (monotonic) |
| migrations applied | **104** |
| `template_twin_compiled_versions` | **0** |
| `template_twin_fill_manifests` | **0** |

Running images before the deploy:

| service | image id |
|---|---|
| `transcribe-md` | `sha256:bc4e06c609be…` |
| `transcribe-md-worker` | `sha256:b8f373321a21…` |

Co-tenants: `app` 307 · `admin` 404 · `quillmd` 200 · `www` 200 · `pro` 410.

---

## MUST CHANGE

1. **Image ids** for `transcribe-md` and `transcribe-md-worker`.
2. **The exported bytes of visit `cmsdvjgf5000m01mmbs0srykk`** — its Word, PDF
   and clipboard exports move from `2026-08-10` to `2026-08-03` on the visit-date
   row. **No stored column changes**; the record's content was always
   `createdAt`, and the export was the thing misreporting it.
3. **Both export FILENAMES for that visit** — `visit-…-2026-08-10.{docx,pdf}`
   becomes `visit-…-2026-08-03.{docx,pdf}`. ⚠️ **Worth saying out loud: a copy
   downloaded before this deploy and one downloaded after will not collide, so
   the same note can be filed into a chart twice under two names.** Strictly
   better alignment with the document; a real operational consequence.
4. **Redis preview keys move to the `visitdoc:v4:` prefix.** Existing `v3`
   entries become unreachable and expire on their own 30-minute TTL. **This is
   the point of the bump** — without it a doctor reloading the pre-sign canvas
   would be served the OLD date while the exports served the new one, and the
   visit most likely to be reloaded right after signing is exactly the one whose
   two dates differ.

## MUST NOT CHANGE

- **Every clinical count**: visits **45**, signed **27**, patients **32**,
  templates **9**; `audit_logs` monotonic from **11475**.
- **Migrations stay 104.** This change carries NO migration.
- **The twin tables stay 0 / 0.** Nothing here compiles, certifies or fills a
  twin. ⚠️ A non-zero would mean a doctor uploaded a `.docx` during the window —
  RC-2's intended behaviour, and it would need saying, not hiding.
- **The 26 same-day signed visits and the 18 unsigned ones are byte-identical.**
- **The signature chrome is unchanged everywhere** — `Signed electronically by …
  on <signedAt>`, the `Status: Signed` row, and the form's
  `Electronically Signed – <name> <signedAt>` line all still carry the SIGNING
  date. ⚠️ **This is the row that catches the over-correction**, which is the
  worse failure than the one being fixed.
- **The two email senders keep sending the SIGNING date.**
- Co-tenant status unchanged.

---

## ⚠️ WHAT WOULD MAKE ME ROLL BACK

- any clinical count moving.
- migrations reading anything but **104**.
- `app /api/health` not 200, or either container failing to settle.
- **the reference visit still exporting `Visit date: 2026-08-10`** — the built
  image does not contain the fix.
- **any surface printing `2026-08-03` in the SIGNATURE line** — the
  over-correction, and a worse document than the defect.
- a form-only export showing `DD:` with a date differing from its own
  `DATE OF SURGERY`.

## ROLLBACK

Image tags cut against the RUNNING ids before the deploy:

    meddoc-pro-transcribe-md:pre-visitdate-20260815
    meddoc-pro-transcribe-md-worker:pre-visitdate-20260815

Reverting the commits is also sufficient — no migration, no data change.
⚠️ **A rollback re-introduces the defect**: the signed record resumes asserting a
visit date that is not the visit's date, and the form-only export resumes
claiming it was dictated on the signing day. The `visitdoc:v4` keys go stale in
the other direction, under the same 30-minute TTL.

---

## OWNER PING — carried into the morning report

**Re-export visit `cmsdvjgf5000m01mmbs0srykk` and check the visit-date row reads
2026-08-03 while the signature line still reads 2026-08-10.** That single
document is the entire live payload of this deploy.
