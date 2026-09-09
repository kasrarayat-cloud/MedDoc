# §2.5 JUDGEMENT — the composed deploy of `b21a9cdb`

**Judged against `docs/foundation/deploys/20260909-a7b46b40.md` and nothing else.**

## THE ROWS

| # | declared | measured | verdict |
|---|---|---|---|
| 1 | image revision = the shipped commit | `b21a9cdb7aa4bca377ca17ad4ac7ec3ee6d5f3a0` | ✅ |
| 2 | `next` 16.2.11 → **16.3.4** | **16.3.4** | ✅ |
| 3 | `sharp` 0.35.3 → **0.35.4** | **0.35.4** | ✅ |
| 4 | `@xmldom/xmldom` 0.8.13 → **0.8.15** | **0.8.15** | ✅ |
| 5 | mammoth witness **byte-identical** to `0b82bdd1` | `{"ok":true,"fields":80,"tables":1,"unsupported":0,"structureSha256":"37813a6031d4ae56"}` | ✅ |
| 6 | visits **58** | 58 | ✅ |
| 7 | patients **46** | 46 | ✅ |
| 8 | signed visits **40** | 40 | ✅ |
| 9 | note templates **16** | 16 | ✅ |
| 10 | compiled versions **5** | 5 | ✅ |
| 11 | certified versions **4** | 4 | ✅ |
| 12 | field definitions **238** | 238 | ✅ |
| 13 | certified mappings **238** | 238 | ✅ |
| 14 | fill manifests **5** | 5 | ✅ |
| 15 | applied migrations **115** | **116** | 🔴 **THE FINDING** |

**14 of 15.** The advisory bump is live — the two CRITICAL Next RCEs are no
longer running — and the witness is byte-identical, so the docx path the other
twelve passengers serve still parses the reference document to the same
structure hash.

## 🔴 ROW 15 — A MIGRATION SHIPPED THAT THIS DECLARATION DID NOT NAME

`20260907040000_admin5_last_owner_trigger`, applied `2026-09-09 07:46:34Z`
during this deploy.

**It is a peer lane's properly-ruled work** — ADMIN-5, ruling #210, merged
through its own PR (#1036) and citation at `341c7b07`. Nothing about the
migration is wrong, and it applied cleanly.

⚠️ **THE DEFECT IS MINE: I ENUMERATED THE PASSENGERS BY READING A TRUNCATED
LIST.** The filter was correct and matched **81 files**. My displayed output
ended at `package-lock.json` — and `packages/` sorts *after* it, so every
`packages/db/prisma/migrations/…` entry fell past the end of what I read. I
never counted. One `wc -l` would have shown 81 against the 25 I saw.

> **THE SAME SHAPE AS CANON 143, IN A NEW COSTUME.** There, a `grep` pattern
> could not display the line that said `Errors`. Here, a list could not display
> its own tail. Both times the instrument was correct and the READING was the
> failure — and both times the tell was that I did not check a count.

**AND IT IS THE "OVERTAKEN, NOT OVERRIDDEN" HAZARD LANDING FOR REAL.** The
lockfile case, four hours earlier, was the same shape and I *did* catch it —
because I re-derived the range. This one I enumerated once and trusted.

**WHAT IT MEANS IN PRACTICE:**

- the deploy was declared **code-only**; it was migration-carrying
- ⚠️ **the strictness logic would have caught it and did not need to** — it
  compares repo (116) against applied (115) and raises to `strict`. The owner
  had already ruled `strict`, so the raise was invisible. **A gate that would
  have spoken was silenced by a correct decision taken for a different reason.**
- no declared quantity moved because of it: every clinical row held

**IS THE TRIGGER SAFE ON LIVE DATA?** Checked rather than assumed. Six practices
carry **0 active owners** — `Solo — Edge long-prefix`, `Solo — Edge apostrophe`,
`Test Clinic B`, and three `QA …` rows, all synthetic by name. The trigger is
`AFTER`-write and fires only on a write that REDUCES an owner count, exempting
rows that were not active owners. Pre-existing states are neither validated nor
blocked. **Nothing is broken and nothing is fixed by it; the six are ADMIN-5's
to judge, not this deploy's.**

## WHAT THIS DEPLOY DID NOT DO

Nothing was certified, activated, demoted or de-certified. No template changed
status. The re-issue act had not run at the time of this judgement.
