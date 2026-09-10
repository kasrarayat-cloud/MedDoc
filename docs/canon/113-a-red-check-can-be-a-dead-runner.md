# A RED REQUIRED CHECK CAN BE A DEAD RUNNER, AND IT LOOKS EXACTLY LIKE A FAILING TEST

**2026-09-06. Found independently by two sessions within hours of each other,
which is why it is canon and not a note.**

`AGENTS.md` already keeps a list of instruments that lie in the direction that
costs you something — `gh pr checks` reporting `pending` for a completed run,
`gh run list --commit` returning `[]` for a short SHA and again during the
propagation window, `gh pr edit --body-file` failing while printing a notice,
`gh pr merge --delete-branch` reporting one failure and hiding another.

**This is one more, and it is the expensive one:**

> **A required check can go RED because the runner process died holding it, and
> at the surface every session actually reads, that is INDISTINGUISHABLE from a
> test asserting false.**

`gh pr checks` printed:

    unit tests (transcribe-md + packages)   fail   36m3s

A true sentence about a gate that **never ran to completion**.

Both failure modes are `conclusion: failure` on a required context. One means
*your code is wrong*; the other means *nothing measured your code*. Treating the
second as the first sends a session hunting a defect that does not exist.
Treating the first as the second is `re-run-and-hope`, which canon forbids —
so guessing is not available in either direction.

## THE DISCRIMINATORS, STRONGEST FIRST

### 1 · THE ANNOTATION — GitHub says it in words, and it is the DURABLE half

**Two sessions hit this event from different endpoints within hours, neither
having seen the other's work.** One captured the step record live, before a
re-run existed to erase it; the other found the annotation, which is still
retrievable afterwards. **The pair is the finding** — one event, corroborated by
two independent instruments. The annotation route was contributed by the peer
session `meddoc-pro-3e` and verified here before being written down.

    gh api repos/<owner>/<repo>/check-runs/<job-id>/annotations

On job `101462315011` it returned, verbatim:

> `annotation_level: "failure"`
> **"The self-hosted runner lost communication with the server. Verify the
> machine is running and has a healthy network connection. Anything in your
> workflow that terminates the runner process, starves it for CPU/Memory, or
> blocks its network access can cause this error."**

One call, no log download, and it is GitHub naming the cause rather than you
inferring it.

### 2 · THE STEP RECORD — a step left running inside a finished job

    gh api repos/<owner>/<repo>/actions/jobs/<job-id> \
      --jq '{conclusion, steps: [.steps[] | {number,name,status,completed_at}]}'

On the same job, read **before** the re-run existed:

| | |
|---|---|
| the job | `"status":"completed"`, `"conclusion":"failure"` |
| step 6 `Run in-scope unit suite` | `"status":"in_progress"`, **`"completed_at": null`** |
| step 11 `Post Run actions/setup-node@v4` | `"status":"pending"`, `"started_at": null` |
| step 12 `Post Run actions/checkout@v4` | `"status":"pending"`, `"started_at": null` |

⚠️ **A vitest failure COMPLETES its step, UPLOADS its log, and RUNS the
post-steps.** None of those three things happened. A step still `in_progress`
inside a `completed` job is not a verdict — it is the process that was going to
write the verdict going away.

⚠️ **HONEST LIMIT, STATED SO NOBODY INHERITS IT AS PROVEN:** that record was
read **live, before the re-run**. Whether the job endpoint still returns attempt
1's step states *after* a re-run was **not tested**. Plausibly it does — job ids
are attempt-scoped — but it is not claimed. **Route 1 is proven retrievable
after the fact; route 2 is proven only live.** That asymmetry is the whole
reason the annotation goes first.

### 3 · THE LOG BLOB — a 404 where a log should be

    gh api -i repos/<owner>/<repo>/actions/jobs/<job-id>/logs | head -1

| attempt 1 | `HTTP/1.1 404 The specified blob does not exist.` (`BlobNotFound`) |
|---|---|
| attempt 2 | `HTTP/1.1 200 OK` — and the suite's own summary inside it |

The missing log is the same event seen from the other side: there was nothing
left alive to upload it.

⚠️ **Do not reach for this one first.** A log can 404 for retention reasons on
an old run, so a 404 alone is weaker than either route above. It corroborates;
it does not decide.

## ⚠️ AND A RE-RUN ERASES THE EVIDENCE FROM THE SURFACE EVERYONE READS

**This is the half that makes the reason MANDATORY rather than tidy.** After the
re-run, on the same SHA:

    gh api repos/<owner>/<repo>/commits/<sha>/check-runs

returned **exactly one** `unit tests` row — the *successful* attempt-2 run, id
`101519824571`, `conclusion: success`. **The failed check-run is not in the
listing at all.**

So a session auditing that commit tomorrow sees an **unbroken green with no
trace that a gate ever died**. The log is gone, the listing never mentions it,
and the only thing that still answers is the old **job id** — which nothing on
the commit points at any more. The evidence is not merely hard to find; it is
unreachable from the commit.

> **A re-run erases its own history.** The reason therefore has to be written
> into the PR body **at the time it is known**, by the only session that will
> ever be able to find it.

That is what `scripts/check-citation.sh` is doing when it reports `4 of 4`, then
flags `a>1`, then refuses to let the run id stand alone:

    ⚠️ AT LEAST ONE RUN IS ON A RE-RUN (a>1). The run id alone hides that.
       The row must say WHY it was re-run — canon forbids re-run-and-hope,
       so an unexplained re-run is a finding of its own.

⚠️ **That warning is load-bearing, not bureaucratic.** By the time anyone reads
the citation, the surface it points at no longer shows what happened.

## THE CONTROLS — because a step record is still a reading

An inference from three API fields is not a finding. Four independent
measurements, none of which shares the others' assumptions:

| control | result |
|---|---|
| **the same suite, the same runner, twelve minutes earlier, on `main`** (job `101460823072`, `quillmd-ci-1`) | **7m 34s, success.** The suite is not 36 minutes long on that box. |
| **the runner afterwards** | `quillmd-ci-1` last completed a job at `09:18:19Z` and its next was `11:42:08Z` — **2h 24m dark**, with a `typecheck` job *from this very run* queued for it the whole time. A healthy runner takes that at `09:54:24Z`. |
| **the same SHA, run locally**, on a worktree whose `@meddoc/*` resolution was verified local first | **430 files, 6046 passed, 0 failed, 68.71s, exit 0** |
| **the re-run, same SHA, same runner** | **5m 33s, success**, `434 passed \| 2 skipped`, `Duration 271.26s` |

**36 minutes against 5m33s and 7m34s on the same machine** is the arithmetic
that does not reconcile, and *arithmetic that does not reconcile is a finding*.

## ⚠️ THIS IS NOT A LICENCE TO RE-RUN A RED, AND THE DISTINCTION IS THE POINT

The rule this entry adds is **narrow on purpose**:

> **A step left `in_progress` in a `completed` job, or an annotation saying the
> runner lost communication, means THE GATE DID NOT RUN. Re-running that is not
> overriding a red — the red was never a verdict.**
>
> **Re-running a job whose step DID complete and whose log DOES exist is exactly
> the `re-run-and-hope` canon forbids.**

The two commands cost seconds and they tell the cases apart **before** you
decide, which is the only moment the distinction is worth anything. Running them
*after* choosing to re-run is building the case for a decision already made.

⚠️ **AND THE REASON GOES IN THE PR BODY REGARDLESS.** `check-citation.sh` will
report `4 of 4` on a re-run and then tell you, in its own output, that an
unexplained re-run is a finding of its own. That warning is not decoration: by
the time anyone reads the citation, the listing no longer shows what happened.

## WHAT IS **NOT** ESTABLISHED

⚠️ **WHY the runner died is unknown, and the obvious suspect is not evidence.**
`quillmd-ci-1` is `white-gorilla-87822` — **4 vCPU / 7.8 GiB**, a different
machine from the application host — and a 43-minute `e2e` job was running
concurrently. OOM fits the annotation's own list of causes (*"starves it for
CPU/Memory"*) and fits the box size. **It remains a suspect.** No session on the
application host can inspect that machine: `ps` there shows no runner process,
and `dmesg` / `journalctl -k` are permission-blind even locally
(`docs/preflight-reports/preflight-20260906T162708Z.md` records that as a
*cannot-tell*, not a pass, and explains that `dmesg` exits **0** while printing
its permission error — so the preflight skill's own Check 5 pipeline would have
scored it green).

**Naming the mechanism honestly is the whole product here.** *"The gate did not
run"* is provable from three endpoints. *"The runner was OOM-killed"* is not,
and writing it down as though it were would put a guess where the next incident
will read it as a fact.

## THE GENERAL FORM

**This is the WATCHED-SET failure wearing a new costume, and the instrument is
not even broken.** `gh pr checks` reported the check-run's `conclusion`
faithfully. The field means *"this context did not go green"* — it has never
meant *"a test failed"*, and every session reads it as though it did.

> **`conclusion: failure` answers "did this context go green". It does not
> answer "did anything measure your code". Those are different questions and
> only one of them has an answer at that endpoint.**

Same shape as `--commit` returning `[]` correctly about a set the server has not
finished populating: **the right question asked of the wrong universe.**
