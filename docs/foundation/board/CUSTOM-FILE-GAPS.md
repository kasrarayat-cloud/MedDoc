# FILED 2026-09-10/11 BY THE CUSTOM-FILE SESSION — thirteen gaps the sequence to 🟢 found and did not fix

The filings are numbered 1–12, plus 9b. The first version of this header said
"five", written when there were five. It is corrected here, not rewritten
silently.

Each was measured, and each is filed here rather than improvised: a gap given
a quiet workaround is a gap nobody can see.

## 1 · ROW3-PLACEHOLDERS — `{patient}` / `{age}` in STATIC text are never filled

The owner's consult form carries the sentence *"{patient} is a pleasant
{age}-year-old presenting for gastroenterology evaluation indicated by the
following:"* as **static paragraph text**, not as a control. **Nothing in the
fill or render path substitutes it.** The only occurrence of `{patient}` in
`lib/` is a comment in `compiler.ts`. On the certified round-trip export of the
ACTIVE form (`18a7ae19`, sha `87832bf3…`) it prints with its literal braces.
Acceptance row 3 asks for these tokens to come *from the record*.

⚠️ **Why it was not built in this sequence:** it changes static text, and
static-content byte-identity is the certification invariant
(`staticContentSha256`). The honest designs are a compile-time token control
(new IR structure, new identity, a recertification) or a declared exemption to
the invariant. Either is a design decision with its own pass.

## 2 · MANUAL-ROWS-HAVE-NO-ENTRY-PATH — telehealth consent AND total time ×2 can be printed by nobody

⚠️ **WIDENED 2026-09-11 by #312 amendment 3.** The two total-time controls
(display order 70 and 71) are now `manual` with no concept, like telehealth
consent. Neither override kind can write a concept-less row:
- `option` (`clinician-override.ts:64`) refuses with `no_approved_concept`
  (~:570);
- `scaffold_default` (:70) refuses with `no_approved_concept` (~:634).

Neither override takes free text. So **three** controls on the re-issued form
can only be written by hand on the exported document. That matches the owner's
ACTIVE form today, so no capability is lost; the gap is that the product never
offers the doctor a way in. **Needs:** a free-text clinician entry for `manual`
rows, with its own pass. Total time is a billing quantity, so that entry is
where a typed figure should come from, not from extraction.

(Original filing, kept below.)

### TELEHEALTH-CONSENT — the line can be printed by nobody

Under #312 the consent control is `manual` with no concept. The machine never
prints it, and **the doctor cannot insert it at review either**:
`scaffoldDefaultOfferable` refuses a row with no concept, and the overlay
declines `no_approved_concept`. That is identical to the ACTIVE form today.
Row 6's *supported* half (printing the line on a telehealth visit) has no path.
**Needs:** a registered concept plus an extractor, or a REVIEW-DEFAULTS insert
for concept-less `manual` scaffolds.

## 3 · UNGROUNDED-QUOTES — a fact is `direct` even when its quote is not in the transcript

`projectEncounterFacts` keeps a fact whose evidence quote cannot be located:
the offsets fall back to null and the fact stays `direct`. #314 closes this for
`total_time_minutes` only, because that one is a billing quantity. **Before
widening the rule, measure how often L3 paraphrases quotes today.** A blind
widening would blank fields across every visit.

## 4 · ROS-AFFIRMED-RENDER — a contradicted ROS clause prints the bare finding

On the certified round-trip export of the ACTIVE form, the clause control
*"The patient denies heartburn, odynophagia, dysphagia"* prints **`heartburn`**,
and likewise `nausea`, `abdominal pain`, `diarrhea`, `hematemesis`,
`weight loss`. The dictated polarity is affirmed, but the word *"reports"* is
not on the page. The ROS paragraph then reads as a bare list. **A document is
read by a doctor (class c).** Whether an affirmed clause renders as a sentence
is a rendering decision that belongs with the owner's eye on a real export.

## 5 · WRITER-APPROVAL-STAMP — the one mapping writer stamps approval on every row it certifies

`updateTemplateTwinMappings` sets `approvedById`/`approvedAt` on every
certified row of the full set it is given, including rows the save did not
change. The #312 confirm declares this and attributes it with an aggregate
audit row; changing the shared writer was **declined for that act, with its
reason recorded**. A writer change (stamp only a row that MOVES into CERTIFIED)
is its own clinical-path change and needs its own pass.

## 6 · CERTIFIED-ROWS-UNPROTECTED — the comment says a trigger protects them; no trigger exists

`certification-lifecycle.ts` says *"database triggers reject any subsequent
changes"* after certification. **Measured 2026-09-10: no trigger touches any
template-twin table.** The only triggers are 2 on `users` and 4 on
`ledger_entries`. A certified compiled version such as `18a7ae19` is protected
by application code alone. Either the comment is corrected, or the trigger it
promises is written, with its own migration and pass.

## 7 · ALLERGIES-PAIR-STAYS-WHOLE-LIST — #313 correctly refuses to group two controls whose mappings differ

On the re-issued form, Allergies d26 is `affirmative_only` and d27 is
`explicit_denial_allowed`, with different synonym lists. G7 requires identical
mappings, so the pair is not a bullet group, and both keep printing the whole
allergy list. **Reconciling the two mappings is a confirm-time decision about
how allergies are written, not a code change.** It is filed for the owner's
next look at the form.

## 8 · WITNESS-CLEANUP-SILENT — the deploy witness announced a removal it never made

The mammoth witness is recorded only as prose in the deploy documents, with a
script in a session scratchpad (`witness.ts`, sha `e2e9dcde…`). Its procedure
`docker cp`s the script and the blank fixture into the live worker, runs it,
then runs `rm` and prints *"(scratch removed from container)"*
**unconditionally**. `docker cp` writes root-owned files, and the container's
default user cannot remove them. **Measured 2026-09-11T00:14Z: the `rm` was
refused (`Permission denied` / `Operation not permitted`), and both files stayed
in the running production worker.** They were removed with `docker exec -u 0`
and their absence was verified. The previous deploy's copy very likely stayed
behind the same way, until that deploy replaced the container.

The fixture is BLANK, so no PHI was involved. The defect is the class: a
clean-up that reports success without checking. **Needs:** a tracked
`scripts/deploy-witness.sh` that copies, runs, removes as root and asserts
absence — landed in its own PR, because a `scripts/` file in a declarations PR
defeats the resolver's docs-only carry-forward.

## 9 · PRE-COMMIT-HEREDOC-EXECUTES — the conflict-marker block runs its own guidance text

`scripts/hooks/pre-commit`'s conflict-marker block prints its message through
an UNQUOTED heredoc (`cat >&2 <<MSG`), which must stay unquoted because it
expands `$conflicted`. The body contains
``git diff --name-only --diff-filter=U     # the authority, never `| tail` ``.
Bash reads the backticks as a command substitution. **Measured 2026-09-11 in a
trial merge:** it printed `command substitution: line 73: syntax error near
unexpected token '|'`, and the words were silently dropped from the guidance the
operator reads. The block itself still fired, and the commit was refused.

This is the *prose is never a shell argument* class, inside the hook that
enforces hygiene. **Fix:** escape the two backticks, and add an arm that runs
the hook against a staged marker and asserts that stderr contains `| tail` and
no `command substitution`. Shared infra, so it is filed here, not fixed by
the custom-file lane.

## 9b · DEPLOY-HAS-NO-DISK-GUARD — deploy-prod.sh builds until the disk says no

`deploy-prod.sh` checks no free space before, or while, it builds. The disk is
shared with postgres. **Measured 2026-09-11: 33G free.** The one cold deploy on
record (2026-09-09) consumed ~34G, almost all of it build-cache regrowth. The
images themselves are ~1.7G (app 311MB unique, worker 1.43GB unique). Image
deletion is DENIED to sessions (`docker rmi`, `docker system prune`). ~41G of
untagged images, referenced by no container, is held for the owner.

The custom-file lane wrapped its deploy in a watchdog.
- It runs `deploy-prod.sh` in its own process group, and polls free disk every
  2s.
- Below 8G it kills the deploy, but ONLY before the `=== 5b.` marker, which is
  the first production recreate. Production is untouched at that point. It
  then reclaims with `docker builder prune -af`.
- It re-reads the marker immediately before any kill. Its first version had a
  start race that killed at t≈0, caught by its own fake-deploy test B.

**Needs:** a tracked guard INSIDE `deploy-prod.sh`, placed before the build and
armed until the first recreate. The scratch watchdog is the prototype. Then an
owner decision on the untagged images.

## 10 · STALE-MANIFEST-ACROSS-RULE-CHANGE — a rule change does not make a stored manifest stale

Round two of #314, finding 1, was CONFIRMED and NON-BLOCKING. Freshness is
decided by `manifestMatchesDocument` (`note-identity.ts`), which compares the
note, the overrides and the patient row. It does **not** compare the grounding
rule, the resolver version or the context text.

So a VERIFIED manifest filled before a rule change stays "fresh" on an
unchanged, unsigned visit: export serves its stored bytes, and the sign-time
freeze returns `already_fresh` and pins it. Meanwhile the preview recomputes
under the new rule. The resolver-version bump does not help, because no serve
path reads it.

**Population at measurement: 0** VERIFIED manifests on unsigned visits. The
composed deploy declares that count as a blocking row.

**Needs:** a rule or version term in the freshness check, with its own pass.
Re-filling on read changes what every stored manifest serves.

## 11 · CONVERSATION-TOTAL-TIME — the proper fix #314 v3 deliberately did not build

#314 v3 refuses a total time on any conversation (`audio_upload`) visit, at the
one call site every caller reaches.

The worker grounds against the role-labelled transcript L3 read. The doors have
only `transcriptText`, which has no labels and different joins. That mismatch
made the preview show 45 while the signed document showed blank.

**Needs:** persist L3's context text, or rebuild the labelled transcript at the
doors from stored utterances. Then the worker and every door ground the same
text, and a doctor-spoken canonical total can ground. There are 0
`audio_upload` visits in production today.

## 12 · PROD-SMOKE-EMPTY-CONTEXT — the manual twin export smoke re-fills against ''

Round two of #314, finding 2, was REFUTED for CI. One sub-claim held:
`scripts/prod-smoke/twin-visit-export.ts`, which no workflow runs, now re-fills
its donor visit against empty text. Its donor is `inputMode 'text'`, with no
`rawTextInput` or `transcriptText`. Severity is low; this affects the evidence
fidelity of a manual script. **Needs:** a donor that carries `rawTextInput`,
or a fixture that states what the smoke can and cannot see.

**Widened by round three's every-door lens (low, confirmed by its own scratch
arm).** The same script creates a `text_notes` visit with `transcriptText` set
and `rawTextInput` unset. It then calls `processTemplateTwinVisit` with its OWN
context (`extracted.contextText`, mode `text`), not `groundingContextFor`, and
writes a manifest. So the smoke proves a fill that no door performs.

The gate that claims "exactly four doors / no sixth copy"
(`gate-314-grounding-context-doors.test.ts`, source arms at ~:507–535) scans
`src/` only, so it cannot see a caller under `scripts/`. **Needs:** the gate's
source scan widened to `scripts/`, and the smoke routed through
`groundingContextFor`. Both belong to #314's deferred PR (#1101).
