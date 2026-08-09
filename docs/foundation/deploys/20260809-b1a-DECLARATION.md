# Deploy declaration — B1-a, `ai_calls.requestId`

**Written 2026-08-09T01:2xZ, BEFORE the deploy runs.** Per `DEPLOYMENT_RUNBOOK.md`
§2.5 and the standing rule in `AGENTS.md`: a post-deploy check written afterwards
is unfalsifiable, because every number has a story available to it and a
migration supplies a ready-made excuse for *any* movement. Declaring first
removes the excuse — the comparison has one correct answer, fixed before the
evidence existed.

**Merge commit:** *(filled at deploy time — the citation is on the MERGE commit,
never the PR head)*
**Branch:** `feat/b1a-vendor-request-id` → PR #557
**Rollback tags to cut:** `:pre-b1a-20260809`, against the **RUNNING** image ids
below, digest-verified before the deploy proceeds.

## Baseline, captured 2026-08-09T01:1xZ (READ-ONLY, production)

| quantity | value |
|---|---|
| `transcribe_visits` | **26** |
| `transcribe_md_patients` | **15** |
| visits with `signedAt` NOT NULL | **16** |
| `users` | **196** |
| `ai_calls` | **1122** |
| `api_usage_events` | **1312** |
| applied migrations | **93** |

Running image ids (rollback tags are cut against THESE, not against `:latest`):

    transcribe-md         sha256:e127943edacd0ce78de670991db172d8394c0a9c5511f0cf4b4a65f8d258619e
    transcribe-md-worker  sha256:09886c6b26daebe9295cd00338cb4f456d7df64ec01284a4faec9b2efcb70791

Co-tenant HTTP, verified at STEP 0 and re-verified after:
`app` 307 · `admin` 404 · `quillmd` 200 · `www` 200 · `pro` 410.

## WHAT MUST CHANGE

| # | quantity | from → to | why |
|---|---|---|---|
| 1 | applied migrations | **93 → 94** | `20260809010000_b1a_ai_calls_request_id` |
| 2 | `ai_calls.requestId` in `information_schema` | **absent → present** | `data_type=text`, `is_nullable=YES`, `column_default` **(none)** |
| 3 | image ids for `transcribe-md` + `transcribe-md-worker` | both move | new build |

## WHAT MUST NOT CHANGE

| # | quantity | expected | note |
|---|---|---|---|
| 4 | `transcribe_visits` | **26** | ⚠️ the clinical-count row is never omitted |
| 5 | `transcribe_md_patients` | **15** | |
| 6 | visits with `signedAt` NOT NULL | **16** | a deploy that moves a signature count has done something nobody asked for |
| 7 | `users` | **196** | |
| 8 | `ai_calls` **row count** | **1122** | the column is added; **no row is written, updated or deleted** |
| 9 | `api_usage_events` | **1312** | B1-a does not touch this table's rows |
| 10 | every existing `ai_calls.requestId` | **NULL, all 1122** | ADD COLUMN with no default and no backfill. **A non-NULL here would mean something back-filled it, which nothing was asked to do** |
| 11 | `api_usage_events.unitsSource` census | **`vendor` 1312**, 0 NULL, 0 off-domain | B0-b's invariant must survive |
| 12 | co-tenant HTTP | 307 · 404 · 200 · 200 · 410 | a change here is a finding even if nothing else moved |
| 13 | container health | 9 of 9 healthy | |

## The one-line summary

**This is a code-and-migration deploy whose migration adds one nullable column
and writes nothing.** So the declaration is unusually strong: *rows 4 through 11
must ALL be byte-identical*, and the only movement anywhere in the system is the
migration count, the new column's existence, and two image ids.

⚠️ **Row 10 is the one to read carefully.** `ADD COLUMN … TEXT` with no default
leaves every existing row NULL, and that is the intended, permanent state for the
1122 historical rows — no backfill can invent a request id for a call that
finished months ago. If any historical row comes back non-NULL, something ran
that this deploy did not declare, and **that is the finding** whatever its
explanation sounds like afterwards.

⚠️ **And row 8 is not the same as row 10.** The count staying at 1122 says no row
was added; every value being NULL says no row was *modified*. A backfill would
satisfy row 8 and violate row 10, which is exactly why both are listed.

## A difference not in this table IS THE FINDING

Whatever its explanation sounds like after the fact.
