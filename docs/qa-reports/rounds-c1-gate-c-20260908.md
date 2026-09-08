# QA — ruling #295: the `rounds-c1` Gate-C failures, adjudicated

**2026-09-08.** #295: *rebuild the QA image through the sanctioned QA compose
build, so `rounds-c1`'s four Gate-C failures either clear or become real — a
stale fixture is not a baseline.*

## VERDICT: they CLEARED, and the whole spec did

| | before | after |
|---|---|---|
| `rounds-c1` | **11 passed / 4 failed** | **15 passed / 0 failed** |

The four were `C1-f` templates (×2) and `C2` Gate C (×2), all failing on
`/dev/states?state=… did not serve`.

## ⚠️ TWO COMPOUNDING CAUSES, AND THE FIRST DIAGNOSIS WAS WRONG

**It was reported as "a stale QA image, 32 hours old". Both halves of that were
wrong**, and the correction is the point of this report.

1. **`docker ps` shows UPTIME, not image age.** The container had been *up* 32
   hours; the image was built **2026-08-30**.
2. **It was the WRONG TAG, not merely an old one.** The stack ran
   `meddoc-pro-transcribe-md:qa`, and the base `docker-compose.qa.yml` build args
   do not include `NEXT_PUBLIC_DEV_STATES` — only the `:rounds` recipe does.
   **Rebuilding `:qa` would not have fixed anything.** `/dev/states` is gated on
   that build-time flag (deliberately, not on `NODE_ENV` — see the route's own
   header), so it 404s in any image built without it.

**A third fault was found while preflighting**, unrelated to the image and worse
in kind: `check-qa-mock-posture` reported the QA **worker STOPPED with
`MOCK_AI_CALLS` unset**, i.e. the stack was not running the fixture configuration
it declares. Anything certified against it was certifying something else.

## ⚠️ AND A FOURTH, WHICH WOULD HAVE MADE ANY ANSWER UNSOUND

After the rebuild the spec got **worse** — 1 passed, 14 failed — on

    axe-core version drift: resolved 4.11.3, gates calibrated on 4.10.0

That is not the image and not a flake: **`apps/transcribe-md/node_modules/axe-core`
was ABSENT**, so resolution fell through to the hoisted root copy at 4.11.3 and
the a11y gate refused an uncalibrated analyser. The lockfile pins **4.10.0**
nested and 4.11.3 hoisted, so `node_modules` had drifted off-lockfile. **The gate
was working**; had it not existed, every a11y sweep would have re-baselined
itself silently against a different analyser.

Repaired surgically (`npm install axe-core@4.10.0 --workspace transcribe-md
--no-save`), lockfile verified **byte-identical** afterwards and no tracked file
touched — rather than `npm ci` on a shared box with other sessions mid-run.

## EVIDENCE

- built `:rounds` with the documented build args; prod's `:latest` never
  referenced or rebuilt;
- `check-qa-tag-isolation` — **24 container/tag pairs compared by DIGEST, none
  shared** with production;
- `check-qa-mock-posture` — **vendor-severed AND the flag manifest matches, in
  the live containers**, both services;
- direct HTTP, before running any spec: `/dev/states?state=` **error /
  not-found / loading / empty → 200, 200, 200, 200** (was "did not serve"), with
  `/login → 200` as the not-gated control;
- `rounds-c1`: **15 passed**.

## ONE THING FIXED IN PASSING

The recipe in `docker-compose.qa.rounds.yml` still instructed
`--build-arg NEXT_PUBLIC_SKIN_ROUNDS=true`. That flag and its reader were deleted
**2026-08-05** when Rounds became unconditional, so the build printed
`[Warning] One or more build-args [NEXT_PUBLIC_SKIN_ROUNDS] were not consumed` —
the exact alarm that file teaches you to read as *"the flag never inlined"*.
Harmless in effect, and that is the hazard: a stale instruction that raises a
real alarm for a false reason trains the reader to discount the alarm.
`gate-flag-coverage` dropped the flag the same day; this file had not.
