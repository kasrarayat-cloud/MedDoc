#!/usr/bin/env python3
# ============================================================================
# B8 step 3 — ASSERT THE `failure cost` LOG LINES THE QA HARNESS PREDICTED
# ----------------------------------------------------------------------------
# The product of B8 step 3 is a LOG LINE. `observeFailedVisitUsage` writes
# nothing anywhere — no ledger row, no column, no audit row — so there is no
# database state a harness could read back. The measurement IS the line:
#
#   {"ts":…,"level":"info","scope":"transcribe-md-worker","message":"failure cost",
#    "visitId":…,"layer":…,"accountability":…,"wouldChargeMicroUsd":…,…}
#
# ⚠️ SO THE PROOF HAD TO BE SPLIT, AND THIS IS THE HALF THE HARNESS CANNOT DO.
# `apps/transcribe-md/scripts/qa/b8-failure-cost-on-qa.ts` runs under
# `docker exec` — a SIBLING process of the worker, not its parent. A sibling
# does not share a container's stdout, so that file can read every row the visit
# produced and still cannot see the one thing the item exists to emit.
#
# ⚠️ AND THE ORDER IS THE POINT. The harness writes its expectations to a
# manifest BEFORE any log is read; this script only ever CHECKS them. A single
# script that read the log and then decided what it should have said would be
# unfalsifiable — the §2.5 "declare the delta before it runs" discipline,
# applied to an assertion instead of to a deploy.
#
# ============================================================================
# ⚠️ WHY THIS IS PYTHON READING FILES, AND NOT A SHELL SCRIPT CALLING DOCKER
# ----------------------------------------------------------------------------
# The obvious shape is one bash script that shells out to `docker logs` and
# `docker exec cat`. It was written that way first and the FOUNDATION loop
# cannot run it: `bash scripts/<new>.sh` is not in the loop's allowlist, which
# names ten scripts one per line and deliberately refuses a `scripts/` wildcard
# (a session that may write a script and then run it has no allowlist at all).
#
# Shelling out from Python would route around that rather than respect it. So
# the two DOCKER reads stay outside — each one independently granted, each one
# visible in the transcript — and this file is pure: two paths in, a verdict
# out, no subprocess, no network, no writes.
#
#   docker exec  <ctr> cat /tmp/b8-failure-cost-manifest.tsv  > <manifest>
#   docker logs  <ctr>                                        > <log>
#   python3 scripts/qa/b8-failure-cost-log-assert.py <manifest> <log>
#
# ============================================================================
# ⚠️ EVERY ZERO HERE IS POSITIVE-CONTROLLED, BECAUSE THIS IS AN EMPTINESS TEST
# ----------------------------------------------------------------------------
# "I found no bad line" and "my matcher never matched anything" produce
# identical output, and AGENTS.md records that a check run to prove nothing
# happened is the one most likely to be believed without scrutiny. Two controls
# run BEFORE any expectation is judged:
#
#   POSITIVE — the reader must find `failure cost` lines in the stream at all.
#              An empty, truncated or rotated log must report CANNOT-TELL, never
#              green.
#   NEGATIVE — a visit id that cannot exist must match ZERO lines. If it
#              matches, the matcher is too loose and every green below is
#              meaningless.
#
# Exit: 0 = every expectation held · 1 = FINDING · 2 = cannot tell
# ============================================================================
import json
import sys

COST_MESSAGE = "failure cost"

# A visit id that cannot be produced: real ids are cuid2s and carry no dashes.
IMPOSSIBLE_VISIT_ID = "visit-that-cannot-exist-0000000000"

findings: list[str] = []
cannot: list[str] = []


def ok(msg: str) -> None:
    print(f"   ✔ {msg}")


def bad(msg: str) -> None:
    print(f"   ✖ {msg}")
    findings.append(msg)


def unknown(msg: str) -> None:
    print(f"   ? {msg}")
    cannot.append(msg)


def section(title: str) -> None:
    print(f"\n== {title}")


def cost_events(lines: list[str]) -> list[dict]:
    """Every parseable `failure cost` event in the stream.

    ⚠️ PARSED AS JSON, NEVER SUBSTRING-MATCHED ON THE FIELDS. AGENTS.md records
    four sightings of the substring trap, one of them a matcher satisfied by its
    own explanatory comment. `"accountability":"ours"` inside a line that also
    happens to contain the word elsewhere is exactly its shape. The MESSAGE is
    matched as a whole field value for the same reason.
    """
    out = []
    for line in lines:
        line = line.strip()
        if not line or COST_MESSAGE not in line:
            continue
        # The worker's stdout can interleave non-JSON (console.error from other
        # code paths). A line that does not parse is not an event.
        brace = line.find("{")
        if brace < 0:
            continue
        try:
            ev = json.loads(line[brace:])
        except (ValueError, TypeError):
            continue
        if isinstance(ev, dict) and ev.get("message") == COST_MESSAGE:
            out.append(ev)
    return out


def judge(ev: dict, arm: str, want_acct: str, want_observed: str, want_charge: str) -> None:
    problems: list[str] = []

    got = ev.get("accountability")
    if got != want_acct:
        problems.append(f"accountability={got!r}, expected {want_acct!r}")

    # Each arm of `FailedVisitObservation` is identified by the field only IT
    # emits. That is stricter than reading a status string, because the log line
    # does not carry one — the arm is expressed in the SHAPE of the payload, so
    # the shape is what gets asserted.
    if want_observed == "priced":
        if "componentCount" not in ev:
            problems.append("no componentCount — this is not the `priced` arm")
        if ev.get("charged") is not False:
            problems.append(
                f"charged={ev.get('charged')!r}, expected False — THE ITEM CHARGED SOMETHING"
            )
        if want_charge and ev.get("wouldChargeMicroUsd") != want_charge:
            problems.append(
                f"wouldChargeMicroUsd={ev.get('wouldChargeMicroUsd')!r}, expected {want_charge!r}"
            )
    elif want_observed == "unpriceable":
        # ⚠️ THE KEY IS `unpriceable`, NOT `reason`, AND THIS ASSERTION WAS
        # WRONG ON ITS FIRST RUN. It expected `reason` — the field name on the
        # `FailedVisitObservation` union — and went RED against a log line that
        # was entirely correct. `logFailedVisitCost` renames it on the way out:
        #
        #   unpriceable: observation.reason        → "nothing_billable"
        #   pricedSoFarMicroUsd: …toString()
        #
        # which is strictly better than what this file predicted, because one
        # field then carries BOTH the arm's identity and its reason. Recorded
        # rather than quietly fixed: an expectation derived from the type and
        # not from the emitter is a check measuring the wrong quantity, and the
        # only thing that caught it was running it.
        if not isinstance(ev.get("unpriceable"), str):
            problems.append(
                f"unpriceable={ev.get('unpriceable')!r} — the `unpriceable` arm must carry B6's "
                "reason as a string, so a pricing gap is distinguishable from a genuinely free "
                "failure (B9 must not chase the second)"
            )
        if not isinstance(ev.get("pricedSoFarMicroUsd"), str):
            problems.append(
                f"pricedSoFarMicroUsd={ev.get('pricedSoFarMicroUsd')!r}, expected a string"
            )
        if "componentCount" in ev:
            problems.append("componentCount present — this is the `priced` arm, not `unpriceable`")
        # There is no charge in this arm, so the field that names one must be
        # absent. Present-and-zero would be a different claim from not-priced.
        if "wouldChargeMicroUsd" in ev:
            problems.append(
                "wouldChargeMicroUsd present on an `unpriceable` line — nothing was priced, so "
                "naming a charge here would make a pricing gap look like a zero charge"
            )
        if ev.get("charged") is not False:
            problems.append(f"charged={ev.get('charged')!r}, expected False")
    elif want_observed == "not_started":
        if ev.get("note") != "admission refused before any vendor call":
            problems.append(f"note={ev.get('note')!r} — not the `not_started` arm")
        if ev.get("wouldChargeMicroUsd") != "0":
            problems.append(
                f'wouldChargeMicroUsd={ev.get("wouldChargeMicroUsd")!r}, expected the string "0"'
            )
    else:
        unknown(f"{arm}: manifest names an unknown arm {want_observed!r}")
        return

    # ⚠️ TYPE, NOT ONLY VALUE. `logFailedVisitCost` emits this field as a STRING
    # in every arm on purpose — JSON cannot serialise a bigint, so a bare 0 in
    # one arm would give one log key two types and break any consumer that
    # parses the field rather than eyeballing it. That is a claim the code makes
    # in a comment, and this is the only thing that checks it.
    if "wouldChargeMicroUsd" in ev and not isinstance(ev["wouldChargeMicroUsd"], str):
        problems.append(
            f"wouldChargeMicroUsd is {type(ev['wouldChargeMicroUsd']).__name__}, not str"
        )

    if problems:
        bad(f"{arm}: " + " ; ".join(problems))
        return

    # ⚠️ THE DISPLAY LISTS EVERY FIELD THIS FUNCTION JUDGED. A green line that
    # printed a subset would make the evidence narrower than the check — the
    # first version omitted `unpriceable` and `pricedSoFarMicroUsd`, so the arm
    # whose assertion had just been corrected showed nothing of what it now
    # asserts, and a reader could not tell the two versions apart.
    shown = {
        k: ev.get(k)
        for k in (
            "accountability",
            "wouldChargeMicroUsd",
            "componentCount",
            "unpriceable",
            "pricedSoFarMicroUsd",
            "note",
            "charged",
        )
        if k in ev
    }
    ok(f"log says {json.dumps(shown)}")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__ or "")
        print("usage: b8-failure-cost-log-assert.py <manifest.tsv> <worker.log>")
        return 2
    manifest_path, log_path = sys.argv[1], sys.argv[2]

    print("B8 step 3 — asserting the `failure cost` log lines against the worker stream")

    section("INSTRUMENT — can this script read both inputs?")
    try:
        with open(manifest_path, encoding="utf8") as fh:
            manifest_rows = [r for r in (line.rstrip("\n") for line in fh) if r.strip()]
    except OSError as exc:
        unknown(f"cannot read the manifest at {manifest_path}: {exc}")
        return 2
    if not manifest_rows:
        unknown(f"the manifest at {manifest_path} is empty — run the in-container harness first")
        return 2
    ok(f"manifest: {len(manifest_rows)} expectation(s)")

    try:
        with open(log_path, encoding="utf8", errors="replace") as fh:
            log_lines = fh.readlines()
    except OSError as exc:
        unknown(f"cannot read the log dump at {log_path}: {exc}")
        return 2
    if not log_lines:
        unknown(f"the log dump at {log_path} is empty — cannot tell")
        return 2
    ok(f"log stream: {len(log_lines)} line(s)")

    section("CONTROLS — before any zero below is believed")
    events = cost_events(log_lines)
    if not events:
        unknown(
            "the stream carries ZERO `failure cost` events. Either the worker image predates "
            "B8 step 3, or no visit has failed — cannot tell"
        )
        return 2
    ok(f"positive control: {len(events)} `failure cost` event(s) parsed — the reader finds them")

    if [e for e in events if e.get("visitId") == IMPOSSIBLE_VISIT_ID]:
        bad(
            "negative control FAILED: a visit id that cannot exist matched an event — the "
            "matcher is too loose and every result below is meaningless"
        )
        return 1
    ok("negative control: an impossible visit id matches 0 events — the matcher discriminates")

    section("EXPECTATIONS — each one written before the log was read")
    for row in manifest_rows:
        parts = row.split("\t")
        if len(parts) != 5:
            unknown(f"manifest row is not 5 tab-separated fields: {row!r}")
            continue
        visit_id, arm, want_acct, want_observed, want_charge = parts
        print(f"\n   -- {arm}  ({visit_id})")

        matched = [e for e in events if e.get("visitId") == visit_id]
        if not matched:
            bad(
                f"{arm}: NO `failure cost` event for this visit. The seam did not run on a "
                "visit that really failed."
            )
            continue
        # ⚠️ EXACTLY ONE, AND THIS IS NOT PEDANTRY. `worker.ts` reaches the
        # observation only when `shouldFailNow` — the final BullMQ attempt, or a
        # `permanent` category — so a terminal failure emits it ONCE however many
        # attempts it burned. Two events would mean the observation runs per
        # ATTEMPT, which is B8 step 3b's over-charge shape arriving inside the
        # measurement built to describe it.
        if len(matched) != 1:
            bad(
                f"{arm}: {len(matched)} `failure cost` events for ONE visit — expected exactly 1. "
                "The observation is running per ATTEMPT, not per terminal failure."
            )
            continue
        ok("exactly 1 `failure cost` event")
        judge(matched[0], arm, want_acct, want_observed, want_charge)

    print("")
    if findings:
        print(f"\U0001F534 {len(findings)} FINDING(S) — the log does not say what the harness predicted:")
        for f in findings:
            print(f"   - {f}")
        return 1
    if cannot:
        print(f"\U0001F7E1 {len(cannot)} thing(s) could not be established:")
        for c in cannot:
            print(f"   - {c}")
        return 2
    print("\U0001F7E2 every predicted `failure cost` line is present and says what was declared.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
