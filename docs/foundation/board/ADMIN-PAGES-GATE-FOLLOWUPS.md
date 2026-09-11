# FILED 2026-09-11 — what the #310 admin-gate hotfix did NOT change

Source: the four-lens adversarial pass over `daaa379d` (branch
`fix/admin-pages-gate-own-data`). It made twelve findings, all confirmed and all
non-blocking. Seven were holes in the derived census. One was a test gap (MFA
before freshness, pinned in the pages arms). Two were declaration wording (N5,
and the audit semantics), corrected in
`docs/foundation/deploys/rows/PR-admin-pages-gate-own-data.md`. All of those were
closed on that branch.

**These are the remainder.** Items 1 and 2 are **pre-existing**: the code moved
unchanged from main's `app/admin/layout.tsx` into `_lib/admin-gate.ts`. Neither
one weakens the access verdict that the hotfix exists for. They are filed here
rather than folded in, because each needs a **production-code** change, and item
1 is also a product call.

## 1 · The access audit is fire-and-forget — OPEN

- **Where.** `recordAdminPageAccess` in `apps/transcribe-md/src/app/admin/_lib/admin-gate.ts`
  calls `void logAudit({...})`. `logAudit` (`src/lib/audit.ts`) catches every
  error and writes it to stderr only.
- **Measured.** This comes from the `rsc:failclosed` lens and two independent
  verifiers. They used scratch vitest files that drove the REAL hipaa page, gate,
  `getAllFindings` and `logAudit` against recorders:
  - `hipaaFinding.findMany` ran before `auditLog.create` at every auth latency
    tried (0, 2 and 20 ms).
  - Whether the insert is even *attempted* before the page returns depends on
    latency: it was not at 2 and 20 ms, and it was at 0 ms.
  - When `auditLog.create` rejects, the page still returns its finding. The only
    trace is `[audit] write failed action=ADMIN_DASHBOARD_ACCESS …` on stderr.
- **Same on main.** `layout.tsx` on `158af24f` used the same `void logAudit(...)`.
- **Why it is not a one-word fix.** A verifier's mutation changed `void` to
  `await`. That moved the insert ahead of the data read, but the page **still
  served data when the insert failed**, because `logAudit` never throws. The real
  change is an **awaited writer that re-throws**, for example a `logAuditOrThrow`
  variant, or an `await prisma.auditLog.create(...)` without the swallow. The
  verifier's M2 control showed that this puts the insert before any data read and
  refuses the data when the insert fails.
- **Why it is filed, not done.** Making the audit a precondition is a **product
  decision** (AGENTS.md class **a**): an `audit_logs` outage would then take every
  /admin page down. The rows doc now states the semantics honestly: best-effort,
  attempted after the gate, not awaited, and a failed write does not block the
  render.

## 2 · The audit path is always `'/admin'` — OPEN

- **Where.** `recordAdminPageAccess` reads
  `next-url ?? x-invoke-path ?? x-pathname ?? '/admin'`.
- **Why it is always the fallback.** Three reasons:
  - Next deletes the `Next-URL` request header for any path that cannot be
    intercepted (`node_modules/next/dist/server/base-server.js`, `setVaryHeader`,
    about lines 1162–1180). /admin has no intercepting routes.
  - On a soft navigation, the client router sends `Next-URL` as the page it is
    navigating **from**.
  - Nothing sets `x-invoke-path` or `x-pathname`. `src/proxy.ts` sets neither.
- **Measured.**
  - The verifier reproduced this on a Next 16.2.11 `next build` + `next start`,
    with a positive control: adding an intercepting route kept `next-url`.
  - The lens ran a read-only production query and found that **1003 of 1003**
    `ADMIN_DASHBOARD_ACCESS` rows have `targetId = '/admin'`. That figure is as
    the lens reported it. The verifier did not re-query production, and QA has 0
    such rows.
- **Two points the lens did not make:**
  - `x-pathname` and `x-invoke-path` come from the client and reach `headers()`
    unfiltered. So a caller who has already passed the gate (only a SUPER_ADMIN
    reaches the write) can put any path into their **own** row's `targetId`.
  - `gate-310-admin-pages-behavioural.test.ts` mocks `headers()` with
    `next-url: /admin/some-page?x=1` and asserts `targetId '/admin/some-page'`.
    That is behaviour production cannot produce. It should be corrected together
    with the fix below.
- **The verifier's fix. It is production code, so it is filed and not done:**
  - Change the gate to `requireAdminPage(route?: string)`, and write the audit
    only when a route is given.
  - Take the route from a **per-page literal**: `await requireAdminPage('/admin/hipaa')`,
    and `'/admin'` for the overview.
  - The layout calls it with no route. It still gates but writes nothing, so a
    full render still writes exactly one row, the page's.
  - Delete the three header reads.
  - In the pages arms, stop mocking `next-url` and assert each page's own route.
  - Extend the derived census so that every `page.tsx` must pass a literal equal
    to its route on disk.

## 3 · The lens's test-count claim — RECORDED, nothing to fix

The verifiers flagged that the `rsc:falsegreen` lens's "186 of 186" was wrong,
because they measured **165**. Measured again on `5d9e89ba` (the branch head
before the hardening commit):

| file set | tests |
|---|---|
| the three `gate-310-*` files | **165** (derived 18, pages 52, data 95) |
| + `detector-enum-cast` (3) + `gate-admin5-doors-behavioural` (18) | **186** |

**Both numbers are right for their own file sets.** The lens's own `what_i_ran`
states 186 over **five** files. So "186" is wrong only if it is read as the count
of the three gate-310 suites, which is how the finding text, quoted alone, reads.
The lesson is the usual one: a count without its file set is not a measurement.

## 4 · Smaller verifier notes, outside the twelve — OPEN

- **The data arm's universe is listed, not derived.**
  `gate-310-admin-data-behavioural.test.ts` drives five hard-coded modules, even
  though its heading says "derived, not listed". The derived census does red on
  an ungated new `_lib` module, but the behavioural arm never drives one.
  Suggested fix: walk `app/admin/**/_lib` on disk (minus `admin-gate` and
  `admin-format`) and assert that the set equals `Object.keys(MODULES)`.
- **The census does not see a module-scope read in a page.** A top-level
  `await prisma.hipaaFinding.count()` in a `page.tsx` runs when the module loads,
  before any gate. The lens's B7 went red only by accident, because the pages
  suite's prisma mock has no `hipaaFinding`.
- **The pages table still walks the `app/admin` folder.** URL-derived coverage
  (route groups, `@slots`, intercepting routes) now lives in the derived census
  (its FIX 5). A page in a route group reds there, not in the pages table.
- **The proxy matcher does not cover `/admin`.** Adding it would put a cookie
  check at the edge, but it would also turn N3's unauthenticated 404 into a
  `/login` redirect. That is a visible behaviour change, so it is not done here.
