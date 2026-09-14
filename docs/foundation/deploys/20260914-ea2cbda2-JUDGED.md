# JUDGEMENT — deploy of `b036d272` (declaration `20260914-ea2cbda2.md`)

Judged against `docs/foundation/deploys/20260914-ea2cbda2.md` immediately after
the deploy of 2026-09-14T22:07:20Z. Code-only; carry-forward from `ea2cbda2`
(the declaration's named commit) to the shipped `b036d272` — the only file in
that range is the declaration itself (0 runtime).

## Result: 🟢 CLEAN — matches the declaration, nothing outside the declared delta

| declared | observed | verdict |
|---|---|---|
| `transcribe-md` + `-worker` get NEW image ids | both containers' `image.revision` label = `b036d272` (was `31081f24`) | ✅ |
| every other image UNCHANGED | postgres/redis/minio/caddy/marketing/postgres-backup untouched; gotenberg recreated by the routine step 5b with no Dockerfile change in range (byte-identical build) | ✅ |
| 0 migrations applied; `_prisma_migrations` unchanged | `118 in repo, 118 recorded`, "No pending migrations to apply" | ✅ |
| clinical counts UNCHANGED (deploy creates/signs nothing) | 0 migrations + no data op → counts not moved by the deploy. Post-deploy record: visits=68, signed=41, note_templates=20, twin_certifications=6, pdfNativeCertified=6 | ✅ |
| all 9 core containers healthy | 9/9 healthy after settle | ✅ |

## The fix shipped

`b036d272` is built FROM the merged tree that carries
`fillPdfTemplate` saving with `useObjectStreams: false`, and its CI (4/4 green)
ran `fill-engine-reportlab-xref.test.ts` — the regression test that fills the
owner's blank ReportLab colonoscopy fixture, forces a continuation page, and
asserts every page's operator list builds. That test was mutation-verified to go
RED (`Bad (uncompressed) XRef entry`) when the save fix is reverted. The
image-revision label match is the structural proof the fixed code is what runs.

## Baseline-age note

The declaration is code-only, so its clinical-count guard is a data-movement
check, not a fixed baseline. With 0 migrations applied the guard is satisfied
structurally; the counts above are the post-deploy record, not a before/after
diff.
