# Independent batch constraint refutation — 2026-09-28

Reviewed frozen `36d23068ba38683aa3d01aa3ac4921a83711b4e7` without editing any existing implementation. Both probes use real inspected synthetic 103-field DOCX packages and the actual whole-result constraint function plus Word writer. They do not invoke an HTTP route, database, worker, provider or document-service subprocess. Documents stay in memory. Network connections are explicitly denied, environment is scrubbed, and no bytecode is written.

## Confirmed F-B3: preserved scalar priority escapes uniqueness

Input: legacy FORMTEXT Priority A displays `1`; its answer is blank/reviewed. Priority B is answered `1`. A valid source-bound `unique_values` manifest permits `1`, `2`, `3` and forbids duplicates.

Observed: validator **ACCEPTED**, effective A `[]`, B `["1"]`; actual Word export contains Priority A `1` and Priority B `1`.

Cause: `rebuild/core/generation_batch.py:193` reads only stored answer text for non-option scalar fields, while `rebuild/documents/word_v3.py:3434` preserves the original field when the answer is omitted. The new effective-state reader only reads option kinds. This demonstrates a remaining global-rule bypass, not a claim about live provider quality.

## Confirmed F-B4: unknown displayed dropdown becomes unchecked

Input: a nonplaceholder native SDT dropdown displays `4`, while its declared options are `1`, `2`, `3`; the original and stored mapping agree. All answers are blank/reviewed. The unique-priority manifest permits only `1`, `2`, `3`.

Observed: validator **ACCEPTED**, effective Priority A `[]`; the actual export is byte-identical to the original and still displays Priority A `4`.

Cause: `rebuild/documents/word_v3.py:3717` obtains an unrecognized displayed option as `None` and returns all `False`, so `rebuild/core/generation_batch.py:200` sees a known boolean state and treats it as empty. The claimed unreadable-state refusal does not cover this state.

## Exact invocation and evidence

From `/opt/meddoc-pro/.worktrees/v1-batch-effective-constraints`:

```sh
env -i PATH=/usr/bin:/bin QUILLMD_ENV_MANAGED=1 /opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B /opt/meddoc-pro/.worktrees/v1-hyperlink-content-controls/rebuild/.runtime/independent-batch/probe_constraints.py > /opt/meddoc-pro/.worktrees/v1-hyperlink-content-controls/rebuild/.runtime/independent-batch/01-results.json
```

Exit 0, 1.03 seconds. Script: `probe_constraints.py`; immutable original observed output: `01-results.json`. Output includes exact source hashes, mapped field locators, effective sets, original/export paragraph content and package hashes. Later replays must use a new result filename; DOCX package timestamps can change package hashes between fresh probes.

## Recovered integration identity, held

Relative to recovered workflow candidate `3ee445b84786d4457d0e236ddd751548edaef6d6`, the batch lineage is:

1. `72c1a793a23998778e6c2c96b0421ccb2ba1057a` design contract.
2. `39c682bc64c06a2f67e426d33814617d7c517628` batch implementation.
3. `a306e04474a4249a55390d33910deff82600ad5a` restore contract correction.
4. `5a36e75276397c19175c5de8dc43a976329a3e2e` financial closeout correction.
5. `b1c3b95cca1a807f31eb5e3244258e8373bf9751` versioned payload deduplication.
6. `36d23068ba38683aa3d01aa3ac4921a83711b4e7` incomplete effective-state repair, refuted above.
7. `9eb7158aaa81810ce11d9cfb5d1993e59bc7ec03` independent evidence and scanner; whole-module pins bind only step 5 and require another reviewed update after final fixes.

The scanner tree's `3d6da8ad`, `03693f0c`, and `dd1a146b` are cherry-picked equivalents of steps 3, 4, 5; do not apply both sets. Its pre-scanner cost files are byte-identical to the recovered workflow candidate's cost files, so the older history-price commits `900c1b55` / `359020f6` do not need reapplying for those files.

No integration or activation is recommended until both findings are fixed and independently replayed. Already documented separate release blockers remain: the ordinary opposite-side source defect, missing automatic qualified rule producer, ordinary source/context/choice defects, unqualified actual Sonnet5 execution and broad Word compatibility. Default-off batch work does not certify V1 launch.
