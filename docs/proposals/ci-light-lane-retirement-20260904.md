# Proposal — retire the self-hosted CI box? (light lane)

**Written 2026-09-04, for the owner's decision.** Requested as: *"move the light
lane too and RETIRE the self-hosted CI box entirely … Propose with the measured
monthly minutes."*

**RECOMMENDATION: DO NOT move the light lane yet. Defer ~2 weeks.** The premise
the request rests on — *"light jobs are short, so the cost is small"* — is the
one thing the measurement does not support. The detail is below; the short
version is that `unit tests` is the single largest job in the entire pipeline
after `e2e`, and it lives on the light lane.

---

## 1 · What was measured, and the three times the instrument lied first

⚠️ **Recorded because the corrections are the reason the final numbers are
trustworthy, and because the same defect recurred three times in one sitting.**

| attempt | what it returned | why it was wrong |
|---|---|---|
| `gh run list --limit 200` | `200 / 200 / 200 / 200` | the cap, not a count — four identical numbers is the tell |
| `gh run list --limit 400`, bucketed by week | `w1=161 w2=239 w3=0 w4=0` | w1+w2 = 400 exactly; the `0`s were the cap, **not a quiet fortnight** |
| `?created=A..B` week windows | 28d total **1,251** | boundary dates counted in BOTH adjacent windows |

**The authority is `total_count` on `?created=>=DATE&per_page=1`** — a server-side
count, unbounded by any page size. It is the only form used below.

This is the same class as the `--limit 40` false "wedge" of 2026-09-02: *a
bounded list counts the window, not the world.* It cost nothing here only
because four identical numbers are conspicuous.

## 2 · Run volume — the cost driver, and it is not job length

| window | runs per workflow | per day |
|---|---|---|
| **last 28 days** | **1,106** | **39.5** |
| last 90 days | 1,844 | 20.5 |

Four workflows fire on essentially every push, so a "run" here means ~4 runs.
The programme has roughly **doubled its pace** in the last month; which rate you
plan against changes the bill by ~2x, so both are carried through below.

Cancellation reclaims little — `cancel-in-progress` is already set on all four
workflows, and docs-only PRs already skip `e2e`:

| workflow | success | failure | cancelled |
|---|---|---|---|
| test.yml | 866 | 130 | 110 (10%) |
| e2e.yml | 830 | 113 | 161 (15%) |
| a11y.yml | 941 | 79 | 99 |
| secrets-scan.yml | 1,069 | 0 | 39 |

**The cheap levers are already pulled.** 39.5 pushes/day is the real pace, not
waste to be optimised away.

## 3 · The measurement that changes the answer

Moving the heavy lane off the box (#955) made the light lane **~3x faster** —
measured on #955's own run, the first with the box to itself:

| light job | contended median (n=12–24, 14d) | uncontended (#955, n=1) |
|---|---|---|
| `unit tests` | 12.1 min | **8.0 min** |
| `typecheck` | 4.1 min | **2.0 min** |
| `npm audit` | 4.3 min | **1.3 min** |
| `dev-dep advisories` | 6.1 min | **1.4 min** |
| `TruffleHog` | 0.6 min | 1.0 min |
| `detect docs-only` | 0.2 min | 0.2 min |
| **per push** | **~27.7 min** | **~13.9 min** |

⚠️ **The right-hand column is n=1 per job** and must not be read as a median.
It is one run, and it is reported as one run. What it establishes is direction
and rough magnitude, both large.

**The queue pain that motivated retiring the box was contention, and the heavy
lane leaving is what cured it.** Retiring the box now would be paying to solve a
problem that has already been solved for free.

## 4 · The bill

GitHub-hosted Linux 2-core is **$0.006/min**, and the $0.002/min platform charge
is **already included** in that rate (not added on top). Included allowance is
2,000 min/month (Free) or 3,000 (Pro/Team) — and the heavy lane alone exhausts
it, so the light lane's marginal cost is the full rate.

**Light lane, if moved to hosted:**

| volume assumption | min/month | $/month |
|---|---|---|
| 90-day pace (615 runs), 13.9 min | 8,549 | **$51** |
| recent pace (1,185 runs), 13.9 min | 16,472 | **$99** |
| recent pace, 2-vCPU penalty on `unit` (~26 min/push) | 30,810 | **$185** |

⚠️ **The third row is the honest one to plan against and it is an ESTIMATE, not a
measurement.** The box is 8-core; a hosted runner is 2-vCPU. `unit tests` is the
job most exposed to that (it is the longest, and vitest parallelises), so its
8 minutes could become 20+. **I have no measurement of `unit` on a hosted runner
and have not claimed one.**

**Heavy lane — already committed, and the owner accepted it without a number:**

| component | min/month (recent pace) | $/month |
|---|---|---|
| `test` 2.4 + `axe` 4.6, every run | 8,295 | $50 |
| `e2e` **41.1 min measured hosted**, real runs only (46%) | 22,397 | $134 |
| **total heavy lane** | **30,692** | **$184** |

At the 90-day pace it is 15,929 min → **$96/month**. So the heavy lane costs
**~$96–184/month**, materially LESS than the $305 upper bound this section
originally carried.

⚠️ **AND THE MOVE PAID FOR ITSELF IN WALL-CLOCK, WHICH WAS NOT THE ARGUMENT FOR
IT.** `e2e` on the hosted runner finished in **41m08s** (#955, 2026-09-04,
`success`) against a self-hosted real-run median of **78 min** (n=6). Nearly half.
The heavy lane was starving on a box it shared with everything else.

⚠️ **What that does NOT license, said explicitly because it is the tempting
inference:** 41 min hosted beat *contended* self-hosted, and every one of those
six self-hosted samples was taken while the heavy lane still shared the box. It
says nothing about hosted vs **uncontended** self-hosted — which is exactly the
comparison the light-lane decision turns on. The 2-vCPU penalty on `unit tests`
in the table above therefore remains **unmeasured**, not refuted.

## 5 · One input I could not measure, and one the docs contradict

- **The actual invoice.** `/users/.../settings/billing/actions` needs the `user`
  OAuth scope, which this session's token does not carry — and granting it is the
  owner's own action, not something to do on his behalf. **Read it at
  <https://github.com/settings/billing>**; it settles §4 outright and beats every
  estimate above.
- ⚠️ **GitHub's own docs disagree on whether SELF-HOSTED runners are billed.**
  The [2026 pricing-changes page](https://github.com/resources/insights/2026-pricing-changes-for-github-actions)
  says a **$0.002/min charge applies to self-hosted runners from 2026-03-01**;
  the [billing concepts doc](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
  says Actions is **"free for self-hosted runners."** Today is after that date, so
  it is live either way. If the charge is real, keeping the box costs an extra
  ~$33/month in Actions charges *on top of* the VPS — still well under the $99–185
  of moving the lane, so **it does not change the recommendation**, but the owner's
  bill is the thing that settles it.

## 6 · The argument FOR retiring anyway, stated fairly

Cost is not the only axis, and the owner named the real one: **babysitting.**

- The box is a **single point of failure for every merge** — if it dies, the light
  lane blocks everything, and nothing routes around it.
- The virtio-balloon, the sshd, and the "wedge" false alarms all lived there.
- One less machine is one less thing to hold in mind.

**That is a resilience argument, and it is worth money.** The counterweight is
that the failure modes named were *amplified by saturation*, and the box now
carries ~14 min/push on 8 cores — it is no longer near capacity.

## 7 · What I recommend, and why deferring is cheap

**Keep the box. Re-decide in ~2 weeks, on the invoice rather than on my estimates.**

1. The decision is **cheap to defer and expensive to get wrong** — the light lane
   works today and is 3x faster than it was.
2. ⚠️ **The input this section originally said to wait for has ARRIVED, and it
   came in better than feared** — hosted `e2e` measured 41 min, putting the heavy
   lane at ~$96–184/month rather than $305. **That weakens the case for
   deferring, and it is recorded here rather than quietly dropped.** The decision
   can now be made on measurements rather than on the next bill.
3. What remains genuinely unmeasured is one number: **`unit tests` on a hosted
   2-vCPU runner.** It is the difference between $99 and $185/month, and it is
   cheap to obtain — one temporary `runs-on: ubuntu-latest` on that job, one run,
   revert. **If the owner wants the decision closed now rather than deferred,
   that is the single experiment to run.**

**If the owner wants to retire it regardless**, the resilience argument is
legitimate and this is not a blocking objection — the ask is only that it be
decided as *"$50–185/month buys me one less machine to babysit"* rather than as
*"the cost is small."* The first is a trade; the second is not true.
