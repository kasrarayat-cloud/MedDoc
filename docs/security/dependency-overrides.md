# `npm` overrides — why each exists, and **what retires it**

**`package.json` is strict JSON and cannot carry comments, so the rationale lives
here.** Every override below names **its advisory** and **the condition that
kills it**, per the exemption canon: *an exemption is written with the condition
that retires it, in the same sentence, so checking it is a LOOKUP rather than a
judgement.*

⚠️ **A pin without a retirement condition is a future archaeology dig.** If you
add an override and cannot state what would make it unnecessary, that is the
finding — not a reason to skip the line.

---

## Added 2026-08-17 — the high-severity audit gate

Owner-ruled the same day. A new advisory batch turned the `high+critical` CI gate
red on **every** PR; `npm audit`'s own remedy was `prisma@6.12.0`, a **major ORM
downgrade under 104 applied migrations**. That was **REFUSED permanently** — a
schema-engine rollback is a second incident, not a remedy. These three pins fix
the findings at the leaf instead.

| override | advisory | **retires when** |
|---|---|---|
| `deepmerge-ts: ^8.0.1` | *DeepmergeTS stack exhaustion merging recursive object graphs* (fixed ≥8.0.0) | **`@prisma/config` ships `deepmerge-ts` ≥8 naturally.** It pinned `7.1.5` in both 7.9.0 and 7.9.1 — check `npm view @prisma/config@<ver> dependencies.deepmerge-ts`; when it reads `^8` or higher, delete this line. |
| `undici: ^7.29.0` | cross-user information disclosure; response desync via retry interceptor; CRLF injection; cookie attribute injection (fixed 7.29.0) | **`jsdom` ships `undici` ≥7.29.0.** It is a TEST-ONLY transitive — `jsdom@29.0.2 → undici`. When `npm ls undici` shows ≥7.29.0 without the override, delete this line. |
| `js-yaml: ^4.3.1` | CVE-2026-59870 — quadratic CPU in `!!omap` resolution, not backported (fixed 4.3.1) | **every consumer resolves ≥4.3.1 on its own.** Dev-only. Same check: drop the override, `npm ls js-yaml`, and if nothing regresses below 4.3.1, delete this line. |

⚠️ **`npm install` ALONE DOES NOT APPLY A NEW ROOT OVERRIDE TO AN ALREADY-PINNED
LOCK ENTRY.** Measured here: after adding all three, `deepmerge-ts` moved and
**`undici` and `js-yaml` did not** — they stayed at 7.28.0 / 4.3.0 until
`npm update undici js-yaml`. **Verify the resolved version on disk; never assume
the override took.**

### What was NOT done, and why it stays that way

**`prisma` is NOT downgraded.** The advisory chain
(`prisma → @prisma/config → deepmerge-ts`) is cut at `deepmerge-ts`, so the ORM
stays at **7.9.0**. ⚠️ **`prisma@7.9.1` does not clear it either** —
`@prisma/config@7.9.1` still pins `deepmerge-ts 7.1.5`, so upgrading forward is
not a fix. **Do not "resolve" this by moving prisma in either direction.**

### The remaining moderates are deliberate

The gate is `high+critical`. Four moderates survive and are recorded rather than
silenced: `@anthropic-ai/sdk` (fix is a breaking major) and `valibot ≤1.4.1` via
`@prisma/dev` — the latter **does** clear on `prisma@7.9.1`, whose
`@prisma/dev@0.24.17` carries `valibot 1.4.2`.
