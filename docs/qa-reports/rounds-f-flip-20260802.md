# Rounds item F — the flip. Evidence set, 2026-08-02

`NEXT_PUBLIC_SKIN_ROUNDS=true` is **live in production**. This is the durable
record; `docs/rounds/RELAY.md` carries the ledger rows, `docs/DEPLOYMENT_RUNBOOK.md`
§3.1 and §3.3 carry the rollback.

## Verdict

| Step | Outcome |
|---|---|
| 0 — precondition | ✅ C2-a + C2-b merge-commit CI green; **C2 ledger row closed** (it was `⬜ TODO` with both PRs merged) |
| 1 — pre-flip on a flag-ON build | ✅ six packs 57/57, walker `ok:true`, axe clean |
| 2 — the flip | ✅ tagged first, deployed via `deploy-prod.sh` only, verified on the bytes |
| 3 — prod smokes | ✅ both walks, synthetic account, reset to baseline, audit rows kept |
| 4 — old-skin retirement | ⛔ **STOPPED and recorded** — see "What is parked" |

## The rollback line, verbatim

```bash
docker tag meddoc-pro-transcribe-md:pre-rounds-20260802        meddoc-pro-transcribe-md:latest
docker tag meddoc-pro-transcribe-md-worker:pre-rounds-20260802 meddoc-pro-transcribe-md-worker:latest
docker tag meddoc-pro-gotenberg:pre-rounds-20260802            meddoc-pro-gotenberg:fonts
docker compose -f /opt/meddoc-pro/docker-compose.yml up -d --no-deps --force-recreate \
  transcribe-md transcribe-md-worker gotenberg
```

No rebuild, no `.env` edit, no compose edit. Tags were taken **before** the
build and verified against the RUNNING image ids: app `cfa6df5520f6`, worker
`d391ddb62cff`, gotenberg `4bd4489d15b7` (the stock `gotenberg/gotenberg:8`).

⚠️ **It is a six-item revert, not a one-flag revert.** Production had not been
deployed since 2026-07-29, so the running image predated C1-d…C2-b. Rolling back
also reverts the **flag-independent** A4/US-Letter export fix — the split page
returns for every doctor, including any who never see Rounds — and returns the
converter to an image with neither Charter nor Inter Tight. Runbook §3.3.

## What was found along the way

**The walker pointed at production, three ways** (all fixed, PR #501):
`recentMutations()` ran `docker logs meddoc-pro-caddy-1` unconditionally — QA has
no Caddy, but **production's is always running on this host**, so the call did not
fail and did not return empty: it fed production's write traffic to the
classifier for a click made on QA. Seven walkers defaulted their base URL to
`https://app.quillmd.com` under `QA_AUDITOR_BASE_URL` — a *different* variable
from the `QA_AUDITOR_APP_URL` the fail-closed guard reads. And the board's
`Retry` button, which POSTs `/api/visits/[id]/retry` and re-queues a real job and
a real model call, matched no deny-list pattern.

**Three of my own checks were wrong before the product was.** A `12240` grep
"proving" prod lacked the Letter fix was vacuous — the value is computed by
`toTwip(612)` and is never a literal, so it returns 0 on a fixed *and* an
unfixed build; the real discriminators are `toTwip`/`PAGE_PT` (11/13 vs 0). A
`rounds-strip-blockers` assertion flagged a defect that does not exist — that is
the generic "N blockers before Signed" count, and the attestation legitimately is
one; the imaging invariant is about `rounds-strip-em-artifact`, which was 0. And
`rounds-c1` failed twice because **my driver** carried `MOCK_TEMPLATE_PHI_FLAG=true`
onto the rounds recreate, which CI sets only on the *pre*-rounds one — it forces
the template parse down its PHI-reject branch.

**A "primary-care" walk that was not primary care.** The smoke doctor's own
specialty is Vascular Surgery, so the new-visit form defaulted to `ultrasound`
and the first walk (b) created an imaging visit — then reported the absent E/M
gate as a pass. The absence was real; it was an answer about the other specialty
class. Fixed by setting the specialty explicitly for **both** classes: never let
a default decide the variable under test.

**Two portals, two confirmations.** The E/M override lives in the read-only
paper's gate stack, but the confirm that advances the step is portalled *into*
the open flow — clicking the paper's copy first leaves `next` disabled with
"1 documentation level outstanding". And `SignAndSendModal` carries its **own**
second confirmation (`disabled={pending || (emChangeRequired && !emChangeConfirmed)}`,
a deliberate "belt to the disabled button"), so clearing the flow step is not
enough. Both are correct behaviour; both read as a broken control until you look.

## Proof, on the bytes

Post-deploy, inside the running production container, positive-controlled:

```
qm-rounds-  42 files   data-skin 2   rounds-board 2      (all 0 pre-deploy)
toTwip      11         PAGE_PT   13                      (both 0 pre-deploy)
NEXT_PUBLIC_SKIN_ROUNDS  0        <- inlined, not a surviving runtime read
qm-c3-      25         qm-lin-   82                      <- controls, non-zero
```

Converter: prod moved off stock `gotenberg/gotenberg:8` to
`meddoc-pro-gotenberg:fonts` and resolves **7** Charter/Inter-Tight faces against
352 total (was **0** — it had been silently substituting Noto Serif).

Ingress: app 307 · pro 200 · quillmd 200 · admin 404 (documented SUPER_ADMIN
gate) · staging 200. Co-tenants leathererp 200 / www 301, unaffected. **Host
nginx owns 443**; Caddy is confined to `127.0.0.1:8443`; no container publishes
80/443. All five standing checks exit 0. 10/10 containers healthy.

## The smoke walks

Synthetic account only (`smoke-doctor@smoke.quillmd.invalid` /
`quillmd-smoke-practice`), reset to baseline afterwards — 0 visits, 0 patients,
0 templates — with **381 audit rows deliberately preserved**.

**(a) custom-template ultrasound.** Real pipeline → READY. Board lists it; stage
renders under Rounds; **zero per-section edit pills and zero retired review
panels**; gate steps read `1 | SIGN & LOCK` — no E/M step at all;
`rounds-strip-em-artifact` and `rounds-gate-em-artifact` both 0;
`ANCHOR_FLAGS_RECORDED` written (by the worker, with a null `userEmailSnapshot` —
which is why an audit query filtered on that column misses it); the chat edit
reached the **signed DOCX**; Screen 4 carried no documentation-level row.

**(b) primary-care.** Gate steps read `1 | DOCUMENTATION LEVEL | 2 | SIGN & LOCK`
— the specialty contrast proven on the flow itself. Chat edit → `EM_RESCORED` →
signed, `signedCode` frozen at 99212. On a second visit, the **adjust-level**
path: override to 99202 with a typed required reason (`EM_OVERRIDE_APPLIED`), the
gate **refused to advance** while unacknowledged (`🔒 1 documentation level
outstanding`), and after both confirmations **`signedCode` froze to the doctor's
99202, not the scorer's 99212**.

Audit order, walk (b): `VISIT_CREATED → ANCHOR_FLAGS_RECORDED → CHAT_EDIT_TURN →
EM_RESCORED → VISIT_SIGNED → EXPORT_PDF_DOWNLOADED → EXPORT_DOCX_DOWNLOADED`.

**(c) the Rx gate — closed after this report first said it was not.** The first two walks produced no
critical-Rx warning, so the gate never appeared. That is an absence of *opportunity*, not a pass, and
it was named as unverified rather than counted. A third smoke visit dictated warfarin 5 mg alongside
ibuprofen 600 mg TID; the real pipeline flagged it (`RX_DRUG_PAIR_INTERACTION` +
`RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY`) and the flow became `1 | CRITICAL INTERACTIONS |
2 | DOCUMENTATION LEVEL | 3 | SIGN & LOCK`. **7/7** — the gate arrives by portal into the step host,
there is **exactly one** `review-doc-rx-gate` in the document, `next` is disabled beforehand, the
override demands a typed free-text reason, **confirm is refused while that reason is empty**, the
warning then reads *overridden*, the flow unblocks, and `RX_OVERRIDE_RECORDED` lands in the audit
trail.

**C2-b's gates hold on real signed artifacts:** DOCX `w:pgSz w=12240 h=15840` and
PDF `MediaBox [0 0 612 792]` — the same US Letter page — with Charter as the
document default in `styles.xml` and Inter Tight as the per-run override in
`document.xml`, and the PDF embedding CharterRegular/Bold plus
InterTight-Regular/Medium/SemiBold.

## What is parked, and why

**F-ret — the old-skin retirement. STOPPED, not skipped.**

The bridge is safe (scoped `[data-skin='rounds'] .qm-rounds-host`), but **9 of
the 170 `[data-skin='rounds']` selector lines need no `qm-rounds-*` descendant**
— including `[data-skin='rounds'] body`, which paints the stage gradient, plus
`:focus-visible` and a `*` rule. An unconditional `data-skin` therefore repaints
the ground and the focus ring on every legacy surface. Two **required** checks
build flag-OFF and would inherit it: the default `chromium` pack
(`NEXT_PUBLIC_SKIN_BETA: "false"`, no other flag — 24 of 38 specs) and
**`a11y.yml`, which builds with three `NEXT_PUBLIC_*` vars, none of them the skin
flag, and then runs an axe CONTRAST sweep over those routes**.

Separately, "the else branch" is not all old-skin code:
`visit-ready-view.tsx:1099-1105` is the live ON branch of
`NEXT_PUBLIC_REVIEW_DOC_VIEW` and `:1193-1197` is `NEXT_PUBLIC_UX_SIMPLIFY`'s;
the big legacy blocks are gated by `NEXT_PUBLIC_SKIN_BETA`. Deleting it would
retire three flags at once. And `qm-rounds-*` is composed **on top of**
`qm-c3-*`/`qm-lin-*`, which `rounds-tokens.css` selects directly — removing
old-skin CSS breaks the Rounds branch.

So the default pack and the a11y workflow have to be migrated to the Rounds
contract first. Nothing is at risk meanwhile: the dead branches are compiled but
unreachable, and the skin is fully on — this is deferred cleanup, not a partial
flip.

## Close-out

Filled exports from both walks (4 files) and the walker NDJSON were
`shred -u -n 3 -z`'d, exit codes checked, **zero failures**, then the directory
removed. A stray **filled** export left in `/tmp/c2b/probe.docx` by the C2-b
session — synthetic content, but the ruling does not adjudicate on that — was
found and shredded too.

Sweep boundary: `/` on `/dev/sda2`, `-xdev`, **unbounded depth**. Needles
(`ultrasound-cmsb`, `primary-care-cmsb`, `probe.docx`, the two patient labels) all
**0**, beside a positive control of **33 `.docx` found** — so the traversal
demonstrably entered the tree. `WM IOV Template.docx`, the accepted BLANK tracked
fixture, is intact and untouched.
