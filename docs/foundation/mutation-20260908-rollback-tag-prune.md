# §2.5 DECLARATION — the ruled rollback-tag prune, ruling #297(b)

**Written and COMMITTED before the act.** Ruling #297 amends the keep policy;
this declares what the act will do, in numbers fixed before the evidence exists.

## THE ACT

    bash scripts/ops/prune-rollback-tags.sh --delete

under `scripts/run-ruled-mutation.sh`, from `/opt/meddoc-pro/.wt-keep`.

## THE POLICY BEING APPLIED (ruling #297(b), amending #137)

Keep = **the last 5 JUDGED deploys** ∪ **any tag dated within 72 h**.
A deploy is JUDGED when it carries a §2.5 declaration at
`docs/foundation/deploys/<YYYYMMDD>-<sha>.md`.

⚠️ **#137 IS NOT RELAXED.** It stays, unchanged, for everything inside the
keep-set, and `docker image prune -a` remains forbidden in every form. What
moved is the boundary of the set, not the prohibition.

## DECLARED QUANTITIES — measured by the dry run, before the act

| # | quantity | declared |
|---|---|---|
| **P1** | dated `pre-*` tags in total | **72** |
| **P2** | kept or held | **54** |
| **P3** | deletable BY NAME | **18** |
| **P4** | deploy groups surviving | **5 of 44** |
| **P5** | judged declaration dates found | **27** |
| **P6** | the five survivors, by tag | `pre-123da094-20260907`, `pre-43fcf4a6-20260907`, `pre-832f8e81-20260906`, `pre-dcc8cabf-20260905`, `pre-15d7bf8e-20260904` |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **M1** | the 5 tags in **P6** | still present afterwards | they are the keep-set; losing one means the policy was not what ran |
| **M2** | images a CONTAINER references | untouched — every one is reported `⏸ HELD` | deleting a referenced image breaks a running service |
| **M3** | prod containers | 9 of 9 healthy, unchanged | this touches images, never containers |
| **M4** | `:latest`, `:qa`, `:rounds` | untouched | they carry no `pre-` prefix and are outside the scan |
| **M5** | clinical counts — visits, patients, signatures | unchanged | never omitted, per §2.5 |

## MUST CHANGE

| # | row | expectation |
|---|---|---|
| **C1** | deletable tags | **18 → 0** on a re-run |
| **C2** | disk | frees whatever those 18 layer-sets hold; **no minimum is declared**, because the reclaim goal was already met by #297(a) |

## ⚠️ WHY THIS RUNS EVEN THOUGH THE BLOCKER IS ALREADY CLEARED

#297(a) took the disk from **92% to 78%** by itself, so this act is **not**
needed for headroom. It runs because #297(b) is a POLICY ruling with its
reasoning attached — *"everything older is a redeploy of an older commit anyway,
not a rollback"* — and because a keep-set that kept **72 of 72** tags was not a
policy. Applying it now, while nobody is under pressure, is the calm moment to
do it; the alternative is discovering the policy at 91% again.

**Stated so it is not lost:** this is a class (d) act. It deletes rollback tags
for 39 deploy groups. Every one is older than the last five judged deploys AND
older than 72 hours, which is precisely the set the owner ruled is not a
rollback target.
