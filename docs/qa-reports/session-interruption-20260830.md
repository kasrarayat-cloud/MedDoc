# RECOVERY REPORT — the outage that did not happen, 2026-08-30

**Written after a fresh session opened on the report that "the box was down since
sometime after ~06:30 UTC; unknown what completed."**

## ⚠️ THE PREMISE IS FALSE, AND SAYING SO IS THE FINDING

There was no outage. The host has been up **23 days 8 hours** — `uptime -s` =
`2026-08-07 08:31:29 UTC` — reconciled by six independent routes (`/proc/uptime`
arithmetic, `who -b`, `last -x reboot`, `stat /proc/1`, `/proc/stat btime`, and
seven containers whose `StartedAt` is `2026-08-07T08:31:48Z` with
`RestartCount=0`). There was no reboot, no kernel OOM in the window, and
Postgres carries **zero crash-recovery lines** — `pg_postmaster_start_time()` =
`2026-08-07 08:31:55.740924+00`, `pg_is_in_recovery()` false, checkpointer PID
`[14]` on both sides of the quiet period.

**This is the third time in this programme's record that an inherited claim about
a reboot has been corroborated by a session prompt rather than by the machine.**
The standing rule — *check an INDEPENDENT fact before acting on any inherited
claim* — is what caught it, one command in.

## 1 · OUTAGE WINDOW AND CAUSE

**Downtime window: none.** Production served **219 of 219** five-minute
`/api/health` probes today (00:00:01Z → 18:10:01Z) and **219 of 219** on
`quillmd.com` — **438 URL probes, every one OK**. Largest inter-probe gap all
day: **305 s**, i.e. the normal cadence; no slot was missed.
`/api/health` is not a shallow ping — it returns 503 unless
`postgres && redis && minio` all answer.

⚠️ **POSITIVE CONTROL, because a green from an instrument that cannot go red is
worthless:** this same log carries **312 `DOWN`** and **119 `ALERT`** URL lines
historically, most recently **2026-08-11T05:40:21Z**. The instrument demonstrably
reports failure; today it had none to report.

⚠️ **AND A CORRECTION TO MY OWN FIRST DRAFT, WHICH READ "414 OK / 0 DOWN".** That
was wrong. Today's log does contain **110 `DOWN`** lines — every one of them
`containers state=DOWN problems=1`, the *container-health* monitor, not a URL
probe. Partitioning by line type rather than grepping the token is what separates
them, and the un-partitioned count would have understated a real standing defect
(§7, container-health latch) while overstating the uptime evidence. Zero QuillMD 5xx at Caddy (positive-controlled: 5025 × 404 present
in the same parse) and zero at the host nginx — the four 502s there belong to
co-tenants.

**The one unobserved window, stated honestly.** QuillMD's edge recorded no request
at all between `09:25:06.609Z` and `09:26:27.776Z` — **81.167 seconds** — which
fully contains the deploy's container recreate (`Created 09:25:55.886920949Z`,
`Ready 09:25:58.106Z`, worker listening `09:26:05.594Z`). *No request arrived, so
none could fail; but "no request failed" is not "the service was up."* The old
containers' stop time is recorded nowhere.

| bound | value |
|---|---|
| observed user-facing downtime | **0 s** |
| lower bound on deploy unavailability | ≥ 2.2 s (web), ≈ 10 s (worker) |
| upper bound | 81 s |
| detection floor of this evidence | ~5 min (probe cadence) |

**Nobody was on the system.** `max(user_sessions.lastActiveAt)` = `06:21:01.93+00`
— 3 h 05 m before the swap; zero sessions active 09:00–10:00. The first request
after the swap was the deploy script's own health probe.

**What actually stopped was the agent session.** Session
`f5208c04-4da0-4b7e-a076-e72f873925c2` had its last conversational event at
**09:31:44.493Z**, in `/opt/meddoc-pro/.listval`. Its process then stayed alive
but silent for 6 h 24 m — demonstrably alive, not hung: credential refresh at
13:26:28Z, `.claude.json` backups on an exact 30-minute cadence, a successful
self-update at 15:56:02.008Z — then shut its MCP servers down cleanly at
15:56:35.975Z.

⚠️ **Cause of the session exit: UNKNOWN.** The transcript ends in a clean
coordinated teardown with no error, exception or signal record. A terminal close,
an SSH disconnect and a deliberate kill are indistinguishable from the surviving
artifacts, and no amount of reading makes them distinguishable.

**Why it read as an outage from outside:** the last substantive message on the
owner's phone, at 06:26:06Z, says *"All 35 confirmed — certification running
now"* and nothing ever followed it. Certification actually failed **3 h 01 m 42 s
later**. The FOUNDATION loop was separately dark by his own 02:56Z directive, so
the two silences compounded.

## 2 · PRODUCTION INTEGRITY — SOUND

- **The running code IS `main`.** All **858** tracked files under
  `apps/transcribe-md/src` are byte-identical between the running worker and the
  git tree (`diff` exit 0, negative control proves the diff can report). The web
  `.next` bundle carries PR #912's resolver branch in 3 chunks and it is absent
  from the rollback image.
- **9 of 9 containers** running healthy, `RestartCount=0`, `OOMKilled=false`.
- **Migrations 111 applied**, zero with NULL `finished_at`, zero rolled back.
- **Backups** healthy; `pre_deploy_20260830T092208Z.sql.gz` verified (`gzip -t`
  clean, expands to 8,823,024 B, contains the newest migration name).
- **Not a worktree deploy** — Caddy binds `/opt/meddoc-pro/Caddyfile` by absolute
  path, byte-identical across container, disk and git.
- **Headroom fine** — 75 G free (74 %). Swap reads 82 % but is *static residue,
  not pressure*: PSI `some avg10=0.00`, `si/so` 0, and 95.63 % belongs to
  co-tenants; the two QuillMD app containers hold **0 B**.
- **TLS is NOT urgent.** All five SANs serve one cert expiring **2026-10-31** —
  **62 days**. The "2026-09-01" figure was stale, traced to
  `docs/qa-reports/site-down-20260603.md:93`. ⚠️ Only the *date* half is refuted:
  whether the renewal-and-reload machinery works is **UNKNOWN** — nginx's master
  started 24 days after the cert's `notBefore`, so the served cert cannot
  discriminate a working deploy hook from a missing one. Untestable until
  ~2026-10-01.

## 3 · HEARTBEAT — IT FIRED

Today's beat fired at **15:00:02Z** and is proven **server-side**, not from the
local log: ntfy message id `CRNR9HgA7qdn`, `time 1788102002`, body
*"alive · loop STOPPED (STOP present) · board 26 items · 30 open PRs"*. 15:00Z is
the correct slot (PDT; the script's hour gate exits silently at 16:00Z by design).
Cron has not missed a five-minute slot in 14 days — per-day totals reconcile to
exactly 744 = 31/hour.

**So the designed signal was never absent, and no catch-up ping was owed on
liveness grounds.** A ping was still owed on *content*, and was sent at 18:03:22Z
(id `pA4jhIc6Hb0p`) correcting the false "certification running now".

⚠️ **Two of the beat's own three figures are instrument artifacts** — "30 open
PRs" is `gh pr list`'s default page cap (true count **33**), and "board 26 items"
is a regex that over-counts closed/parked rows *and silently hides 29 of 30* open
findings whose labels do not begin with an uppercase letter, including a red
owner-class row.

## 4 · THE INTERRUPTED ACT — EXACT STATE

Subject: compiled twin `070090d3-95f6-4c69-b658-6a29b5cc273d`.

**Confirmations: 35 / 35 — but only 6 carry a human approver.**

| bucket | n | approvedAt | approvedById |
|---|---|---|---|
| owner, via the product UI | 6 | 06:17:32.176–.185 (ms) | his user id |
| machine, on claimed authorization | **29** | 06:25:23.214102 (µs, identical) | **NULL** |

Three independent proofs the 29 did not come from the application, one of which
was re-derived by hand for this report: `approvedById` and `approvedAt` are set
from a **single paired ternary** at `certification-lifecycle.ts:509-510`, so
`approvedAt` set with `approvedById` NULL is unreachable through the app. The
originating heredoc was additionally recovered verbatim from the session
transcript.

**Certification: attempted repeatedly, never succeeded.** Eight
`TEMPLATE_TWIN_CERTIFY_FAILED` rows today; `certificationStatus` reads
`NEEDS_CONFIRMATION`; every `latestTest*` column is NULL; **zero**
`template_twin_certifications` rows for this twin. The single certification and
both fill manifests in the database belong entirely to a different twin
(Venous Duplex, 2026-08-20) — the JUDGED report's global counts were true and
were never evidence about this one.

Final failure `09:27:48.467Z`: **FIELD_RESOLUTION_INVALID**.

### ⚠️ 4.1 THE LARGER FINDING — THE ACT LANDED ON A TEMPLATE THE DOCTOR NO LONGER USES

Template `cmtfc2bw9001g01qw0i6oxn1h` went **inactive at 06:16:29.499**; the
replacement was created **4 ms later** and is his only active template. Both were
compiled from the byte-identical document.

**Causality is the reverse of "orphaned by supersession":** every one of the 35
confirmations was written **after** the template was already inactive — the first
six 63 seconds later, the other 29 at 06:25:23. Confirm-and-certify traffic then
continued against the dead template for **three more hours**.

His live template today: 35 field definitions, **0 CERTIFIED**, 0 approvers, no
pin, no certification.

⚠️ **Globally: 115 CERTIFIED mappings exist, every one under an INACTIVE
template. Zero under any active template.** No code path carries confirmations
forward across a re-upload, even for a byte-identical document with the same
`structureSha256`. That is a product defect, not an accident of this session.

### 4.2 THE BLANKED FIELDS — MEASURED, NOT ASSERTED

17 rows lost a concept relative to the pristine re-compile of the identical
document. They split cleanly:

- **13 are continuation lines** — the same heading still bears the concept
  (Past Medical History 14/15, Allergies 22, medications 26, Family History
  35/36, Impression 54–56, Plan 59–62). Collapsing those is defensible.
- **4 are SUBSTANTIVE**, where no row under that heading bears the concept any
  more:
  - **Past Surgical History (17, 18, 19)** — the dedupe partitioned by
    `clinicalConcept` **across the whole document** rather than within a heading,
    so it kept row 13 (*Past Medical History*) and blanked all three surgical
    rows. **Past Surgical History can now never fill.**
  - **Marital status (31)** — lost `social_history`, now orphaned: the concept
    appears nowhere in the confirmed set.

**So it was not a blanket substitution — but the dedupe had a real flaw and it
cost two sections.**

## 5 · HALF-COMPLETED WRITES — NONE

Nothing is in flight anywhere. No queue has a `wait`/`active`/`delayed` key;
job hashes reconcile exactly (3 completed + 2 failed on the main queue, 50+3+1 on
cleanup, zero orphans). The DLQ's 2 parked entries date from 2026-08-03 and
2026-08-14 and it has **no consumer by design**. **Zero** visits in any of the
seven processing statuses; all 54 carry both `processingStartedAt` and
`processingFinishedAt`; `max(updatedAt)` = 06:21:01.288, so no visit row was
touched during or after the recreate. Zero orphans across all eight
`template_twin_*` tables. `pg_prepared_xacts` = 0, no idle-in-transaction
backend, deadlocks 0.

⚠️ **The 06:28:01Z failed UPDATE genuinely did not apply** — confirmed by three
routes. **But a corrected variant DID run**: `pg_waldump` dates xid 89103 to
06:30:27.445967 (21 rows) and xid 89109 to 06:34:51.689699 (1 row). **Only the
first of the three writes has an audit row**, and the successful statements'
text is unrecoverable (`log_statement=none`, `track_commit_timestamp` off,
`pg_stat_statements` absent). Mapping content has been stable since
06:34:51.689699Z — 1 h 38 m before the declaration was committed — so the
declaration's `35 → 35 ✓` row is correct.

## 6 · WHAT SURVIVED vs WHAT WAS RESUMED

**Survived intact:** all 35 mappings and the owner's 6 approvals (explicitly
preserved, not overwritten); all 35 field definitions; the pin; the complete
audit trail; every visit row.

**Never existed:** any certification of this twin, any fill manifest, any
`latestTest*` value, any MinIO output object. ⚠️ The pin is **not** a torn write
— it is written before render deliberately and a CI gate specifies exactly this
outcome (*"A TEMPLATE IS CERTIFIED OR IT IS NOT"*). Its operational consequence
does matter: it is content-addressed and will be **REUSED on every retry**, so
the denial-shaped encounter is frozen until the concept set changes.

**Resumed and completed this session:** the evidentiary record. `main` carried
**no §2.5 record for the commit running in production** — the judgement existed
nowhere on this host but an unmerged branch. PRs **#910, #911, #913** were landed
as one **declared batch** through `scripts/merge-pr.sh`, the shared tree was
fast-forwarded to `main`, the three branches were retired on both sides, and the
descendant `da7456bd86108ce21698d91640f3142732fefb65` came back **4 of 4**.
This also recovered the only irreversible act of the last 24 hours — the
annotation backfill's declaration, judgement **and the script that performed it**
— which had no tracked record at all.

## 7 · THE CERTIFICATION BLOCKER — CHARACTERISED, AND ONE DESIGN ALREADY REFUTED

`FIELD_RESOLUTION_INVALID` is raised by `assertResolutionStatus`
(`note-template-docx/renderer.ts:283-310`). The proximate cause is a **scope**
defect, not a vocabulary one: `inferPolarity` tests one unanchored regex against
the flat concatenation `value + quote`, and `EXPLICIT_DENIAL`'s
`no\s+(?:known|current|evidence\s+of)?` carries an **optional** qualifier, so it
collapses to a bare `no\s+`. *"Assessment: stable chronic conditions with no
acute change"* is affirmative prose; the bare " no " at offset 42 denied the
whole Impression, and `explicitly_denied` is legal on a scalar checkbox alone —
so the refusal killed the **entire document**.

**This is pre-existing.** Both halves date to `2290f43f13d58dbf37430f13cd5ec81da0e04262`
(2026-07-22), five weeks unchanged, and `renderer.ts` is not in the deploy range.
Today's deploy merely cleared the earlier `FIELD_CONFLICT` blockers so execution
now *reaches* the render stage — 11 blocking checks → 2 → the render refusal.

⚠️ **THE OBVIOUS FIX IS THE WRONG ONE, AND THE REPRODUCTION SAID SO.** Deleting
the `?` fixes `assessment` and `family_history` and preserves the true
`no known drug allergies` denial — but it regresses genuine short-form denials
("no chest pain", "no fever") into **false affirmations in a clinical record**,
and it reaches only 2 of 3 bad cases: `social_history` is matched by a *separate*
alternative, `never`, which the qualifier change never touches.

⚠️ **AND A FULLY-DESIGNED, EIGHT-WAY MUTATION-PROVED FIX WAS REFUTED BY ONE
READ-ONLY QUERY.** Its positional scan keyed on `quote.indexOf(value)`. Measured
against the twin's real `pinnedSyntheticEntities`: **that returns −1 for all five
entities**, because L3 capitalises the finding while the quote preserves the
sentence's own casing (`"Stable chronic…"` vs `"…stable chronic…"`). So the arm
that *is* the fix would **never have fired in production**; every fact would have
fallen through to the conservative fallback and `assessment` would have stayed
denied. The design's own §7 named this as its untested claim and asked for
exactly that query; running it turned a prediction into a refutation.

**A related latent trap, surfaced not fixed:** ords 13/21/25/34 carry
`polarityBehavior = explicit_denial_allowed` on `narrative_text` fields. The
renderer can never honour that — `explicitly_denied` is checkbox-only — so the
configuration is **unreachable by construction**. It fails to bite today only
because the projection emits fact concept `allergy.substance` while the mapping
expects `allergy`, so Allergies receives no fact at all. **Fixing that concept
mismatch would turn Allergies into an instant whole-document refusal.**

## 8 · WHAT REACHES THE OWNER

Decisions taken by him this session:

1. **Fix the renderer bug first** — in progress; scope-aware polarity with the
   case-insensitivity correction, under the mandatory adversarial pass.
2. **Re-attest the 29 properly.** ⚠️ This is a RULED MUTATION and gated:
   `scripts/run-ruled-mutation.sh --declaration <path>` requires the declaration
   to be TRACKED, UNMODIFIED and COMMITTED *before* the act, so its commit
   timestamp provably precedes the rows. The correct seam is
   `certification-lifecycle.ts:509-510`, whose paired ternary sets
   `approvedById`/`approvedAt` together — which is also the proof the 29 did not
   come from the application.
3. **The per-field list** — delivered; 13 of the 17 losses are continuation
   lines, 4 are substantive (Past Surgical History ×3, Marital status).

Still open, and genuinely his:

- **Should a narrative denial PRINT or BLOCK?** *"No known drug allergies."* is
  the commonest allergy entry in medicine and it is the doctor's own words. The
  deferred resolver guard would make it a blocking `FIELD_AMBIGUOUS`; printing it
  verbatim is the other reading. This is a product decision with no ruled
  precedent — class (a) — and it is deliberately NOT bundled into the fix.
- **The confirmations do not survive a re-upload** — 115 CERTIFIED mappings,
  every one under an inactive template. Whether to build carry-forward, and on
  what identity (`structureSha256`?), is a product decision.
- **The container-health alert is dead.** `~/.meddoc-containers.state` has read
  `DOWN` since 2026-08-04T01:50:02Z, so the edge-triggered alert is unreachable:
  a genuine new container failure would be logged and never alerted. The safe fix
  is a named exclusion for the decommissioned `meddoc-pro-meddoc-pro-1`, written
  with its retirement condition in the same sentence.
- **The only backup of the clinical database is unencrypted and local.**
  Backblaze credentials are empty; no offsite leg since 2026-05-02. Class (d).
- ⚠️ **The 2026-08-30 owner directive exists only in a paste cache and a
  gitignored STOP file.** The loop decommission, the ten-item product board and
  the batched-declaration change are in no tracked ledger, and the tracked
  rulebook still says the opposite (`AGENTS.md:786`, `MASTER.md:15`). One `shred`
  of `~/.claude` erases the current product plan. It should be preserved verbatim
  into a tracked file and filed as PENDING OWNER CONFIRMATION — by him, not
  transcribed by a session that did not receive it.

## 9 · THE FIX — PR #914, AND WHAT IT DOES NOT DO

`fix/polarity-denial-governs-fact` @ `34fb4f2e54fb06f8ff02248d642ae59915d340d3`.
One production file, one new gate. Scoped suites **57 files / 590 tests**, full
app **391 files / 5471 tests**, `tsc --noEmit` clean.

The vocabulary is **byte-identical and pinned**; only *scope* changes. A denial
governs a fact via a determiner at the value's head, a cue standing before the
value inside one clause, an unscoped fallback where the value is not locatable,
or a predicate in a whole-statement value's first clause.

**The mandatory adversarial pass ran over the finished diff, four lenses.** It
found **six defects the gate was green through** — including a critical false
affirmation that would tick a checkbox for a finding the record explicitly
denies. Two departures were taken from its required list, both measured rather
than argued:

- **Its widening of arm (d) was DECLINED.** It closes a false affirmation that
  can only reach a **checkbox**, and production has **zero checkbox fields**,
  while the widening turns **18 live facts** (11 `assessment`, 2 `plan`) from
  correctly affirmed back into `denied` — which on a narrative field is a
  refusal of the whole document, not a blank box. Pinned as gate rows `h1`–`h5`
  with the retirement condition written beside the constant it governs.
- **Its cue-overlap fix was TAKEN** and mutation-proved: reverting
  `if (cue.index >= start) break;` reds the gate on exactly `g1`–`g5`.

⚠️ **AND THE GATE CAUGHT ME TWICE WHILE I BUILT IT**, which is the argument for
its shape. First, seventeen rows I added reached `ALL_ROWS` and were asserted by
**nothing** — the meta-tests saw them and no `check()` did; *a list that is
produced and not worked from is a comment*. Second, its blast-radius assertion
enumerates every changed row by id and **refused my addition until I wrote the
new radius down**. Separately, a blanket `zz-*` scratch sweep of mine deleted a
**tracked** file and had to be restored — a destruction list is a claim.

### ⚠️ IT DOES NOT CERTIFY THE FORM, AND THAT IS MEASURED

| | refusing fields | filled resolutions |
|---|---|---|
| before | 1 (ord 53 `assessment`) | 2 |
| after | **0** | **3** |

`MIN_CERTIFIED_FILLED_FIELDS = 10`. **It is seven short**, and the synthetic
verification has never run on this compiled version at all — every `latestTest*`
column is NULL, so the gate blocks before fill coverage is even evaluated.

⚠️ **And the obvious next step makes it worse.** Fixing the
`allergy.substance` → `allergy` concept mismatch alone turns a currently-blank
field into a document-killer: *"No known drug allergies"* is a **genuine**
denial, and the renderer refuses `explicitly_denied` on **any** non-checkbox
whatever `polarityBehavior` the mapping carries. **The contract change must land
BEFORE the concept fix, never after.**

**The ordered path to a certified form**, therefore, is four steps and the first
is the owner's: (a) make a narrative denial representable — print the prose, or
block loudly; (b) the concept-granularity fix, after (a); (c) a pinned synthetic
encounter that exercises ≥10 fields, since even with (a) and (b) the fill is 5;
(d) an actual synthetic verification run.

### THE CLAIM THAT REMAINS UNTESTED

**Nobody has driven the real `renderTemplateDocx` against this twin's actual
source `.docx`** — it lives in object storage — so every "the refusal clears"
claim asserts the *resolution* and mirrors `assertResolutionStatus` rather than
rendering that template. A binding or package-level failure downstream of the
resolution would be invisible to all of it, mine included.

## 10 · WHAT THIS SESSION CHANGED, AND WHAT IT LEFT ALONE

**Changed:** the evidentiary record (#910, #911, #913 landed as one declared
batch; `da7456bd` cited 4 of 4; three branches retired on both sides); the
shared tree fast-forwarded to `main` and clean; PR #914 opened for the polarity
defect; one correcting ping delivered.

**Deliberately left alone:** the deferred resolver contract change (a product
decision); the concept-granularity fix (must land *after* the contract change,
never before); the 29 unattributed confirmations (a ruled mutation, gated on a
committed declaration); the six remaining worktrees, five of which carry
unmerged commits; the 71 orphan branches; PR #907's red dependabot run.

⚠️ **AND THE STANDING RULEBOOK IS NOW WRONG IN TWO PLACES.** `AGENTS.md:786`
says *"the FOUNDATION loop runs unattended and continuously"* and `MASTER.md:15`
says *"You ARE the unattended session"*. The loop was decommissioned by owner
directive on 2026-08-30 and the only record of that is an untracked `STOP` file
and a paste cache. A session opening tomorrow and reading the tracked rulebook
would relight it. **That correction is queued and belongs with the directive's
own preservation, which is the owner's to confirm rather than a session's to
transcribe.**
