# §2.5 AUTHOR ROWS — ADMIN-3 PR-1 (`feat/admin3-reportkind-catalog`), ruling #197

**Written before the act**, at PR-open, per `docs/foundation/board/ADMIN1-ROWS-AT-PR-OPEN.md`
and ruling #184. Rename to `PR-<n>.md` once the PR number exists; keep the body
byte-identical.

**Lane:** Design/Admin (ADMIN arc, #310). **CODE-ONLY.** It has no migration, no
schema change, no compose, env or Dockerfile change, and no data write.

> **Declaration, one line: nothing but the image ids.**

The rows below exist for two reasons. This PR is on the **clinical generation
path**. And two byte-level changes are expected, so they must not be read as
findings: the client chunk carries a new key, and the RSC payload does too.

**Runtime files.**
- **Catalog:** `packages/shared/src/specialties.ts`, which reaches both the web and
  the worker images.
- **Worker:**
  - `apps/transcribe-md/src/worker/note-templates/imaging-report-builders.ts`
    (new);
  - `…/worker/layers/04-generate-soap.ts` (L4);
  - `…/src/worker.ts`.
- **Import-only removals:**
  - `app/visits/[id]/page.tsx`;
  - `api/visits/[id]/em-score/{override,apply-additions}/route.ts`;
  - `api/visits/[id]/sign/route.ts`;
  - `actions/soap.ts`;
  - `actions/rescore-em.ts`.

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **AR3-C1** | image ids of `meddoc-pro-transcribe-md-1` and `meddoc-pro-transcribe-md-worker-1` | baseline | new | this IS the change |
| **AR3-C2** | the worker runs the registry. It runs from source (`Dockerfile.worker:133` `npx tsx src/worker.ts`, WORKDIR `/app/apps/transcribe-md`): `grep -c imagingReportBuilderFor src/worker.ts` | **0** | **2** (import + call) | 0 means the worker still runs the old code. The venous rebuild is then still bound directly, and the new fail-closed guard is absent |
| **AR3-C3** | the catalog key reaches client chunks: `grep -rl reportKind .next/static \| wc -l`, run from the web container's app dir | **0** (the key exists nowhere else in the tree; `git grep reportKind` hits only this PR and docs) | **>= 1** | a property key survives minification, so 0 means the catalog shipped to the pickers is the old one |
| **AR3-C4** | the `/visits/new` RSC payload / HTML | — | each specialty option object gains `"reportKind":"office"`, and Ultrasound also gains `"reportKind":"imaging","reportBuilder":"ultrasound"` | ⚠️ **declared so a byte-diff is not read as a finding.** `pickerSpecialties` is passed as props into `'use client'` components (`new-visit-client*.tsx`, `visit-form-step2.tsx`). The options' **ids, labels and order** must not move; see N3 |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **AR3-N1** | **clinical counts** — `transcribe_visits` total, `status='SIGNED'`, `patients` | unchanged against the deploy's OWN baseline. Last measured by others, and not re-measured by this author: visits by specialty ultrasound 22 / bariatric-surgery 20 / gastroenterology 14 / primary-care 2 (the 6fcd21d0 recon) | **never omitted.** A code-only deploy that moves a visit, signature or patient count has done something nobody asked for |
| **AR3-N2** | `NEXT_PUBLIC_ULTRASOUND_SPECIALTY` in both containers | **`true` / `true`**, measured by this author 2026-09-10 (`docker inspect`, that one var only) | the PR keeps the flag's meaning exactly. If the deploy moves the flag, every imaging route moves with it, and no row here could tell the two apart |
| **AR3-N3** | the flag is still **INLINED** in client chunks: `grep -rl 'process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY' .next/static \| wc -l` | **0** before, **0** after. **Positive control:** `grep -rl Ultrasound .next/static \| wc -l` >= 1 on both sides | a surviving read means it was NOT inlined. The browser then reads the flag as unset and Ultrasound vanishes from every picker in production. The source form is pinned by the oracle, and mutation M9 proves that pin; only this row proves the bundle |
| **AR3-N4** | `_prisma_migrations` row count; `practices` column count | unchanged; **10** columns (the 6fcd21d0 recon, F15) | `Practice.specialty` is PR-2. Movement here means a migration rode unnamed |
| **AR3-N5** | `AuditAction` enum cardinality; `audit_logs` gains no new action name | unchanged | no enum work in this PR |
| **AR3-N6** | the imaging route. Checked **on QA only** (never a real visit; AGENTS.md "Production verification"). A synthetic `ultrasound` visit with the flag ON and no custom template should get `noteTemplateId = tmpl_ultrasound_report`, an ultrasound-report prompt, no E/M level and CPT/E&M `skipped`. A synthetic `primary-care` visit should get the SOAP route | identical to the pre-deploy image on QA | the unit oracle drives the real L4 over every derived specialty string × 4 flag values × both anchor states. What it cannot see is the whole worker (`worker.ts` has no integration test; its rebuild gate is pinned by EXACT FORM, mutation M15). If QA cannot run it, say so and leave the row UNVERIFIED |

## VERIFY — structural, mutating nothing

    # AR3-N2 — the flag, value only (never dump the full env: it carries secrets)
    for c in meddoc-pro-transcribe-md-1 meddoc-pro-transcribe-md-worker-1; do
      docker inspect "$c" --format '{{range .Config.Env}}{{println .}}{{end}}' \
        | grep -E '^NEXT_PUBLIC_ULTRASOUND_SPECIALTY='; done                 # =true, =true

    # AR3-C2 — worker source
    docker exec meddoc-pro-transcribe-md-worker-1 sh -c 'grep -c imagingReportBuilderFor src/worker.ts'   # 0 -> 2

    # AR3-C3 / AR3-N3 — client chunks. Find the app dir first
    # (`docker exec … sh -c 'ls -d .next apps/transcribe-md/.next 2>/dev/null'`).
    #   reportKind                                  0 -> >=1
    #   process.env.NEXT_PUBLIC_ULTRASOUND_SPECIALTY   0 -> 0
    #   Ultrasound (control)                        >=1 -> >=1

    # AR3-N1 / N4 / N5 — counts only
    psql -tAc "SELECT count(*) FROM transcribe_visits;"
    psql -tAc "SELECT count(*) FROM transcribe_visits WHERE status='SIGNED';"
    psql -tAc "SELECT count(*) FROM patients;"
    psql -tAc "SELECT count(*) FROM _prisma_migrations;"
    psql -tAc "SELECT count(*) FROM information_schema.columns WHERE table_name='practices';"   # 10 -> 10
    psql -tAc "SELECT count(*) FROM unnest(enum_range(NULL::\"AuditAction\"));"

⚠️ **A DECLARATION IS BOUND TO A CHANGE; A DEPLOY SHIPS A TREE.** If this PR
rides a deploy with other changes queued, these rows judge ONLY this PR's
payload. Say so in the deploying declaration.
