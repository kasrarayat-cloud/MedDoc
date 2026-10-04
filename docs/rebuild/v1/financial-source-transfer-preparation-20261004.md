# Paid financial evidence: separate OLD and NEW source identities

This preparation preserves the actual paid attempts and permits a bounded offline comparison against later application source. It creates no provider request, database query, invoice reconciliation, clinical qualification or accepted fingerprint change.

[The prospective plan](financial-source-transfer-PREPARED-20261004.json) deliberately has no final NEW source. It fixes genuine campaign-3 attempts 002/003 to paid source `04fb7603282dc47eda98058c6d790f407951acba`, and representative campaign-4 typed attempt 002 to paid source `5bf3024508c65d99d2e8573fd87e920a754a65e1`. Their original manifest hashes, complete manifest-bound artifacts, authority, synthetic mode and clean runner identity must remain unchanged. The first group is the actual two-child batch; the second is an ordinary single. Neither is relabelled as a later send.

The existing `rebuild/ops/fixtures/current_wire_price_witness.source` stays byte-identical at SHA-256 `c10dba6840c90ccbacec04c4d4a4393d70d6cf9db0f88ab4d505adce3ae6e34c`. The new `financial_source_transfer.source` prepares two independent commands per evidence group. The OLD command uses an exact copy of the original witness and the paid source. The NEW command uses a derivative whose sole change is this assertion:

```python
assert manifest['runner']['commit']==args.revision and manifest['runner']['clean']
# becomes, for this declared paid group only:
assert manifest['runner']['commit']=='DECLARED_OLD_40_CHARACTER_COMMIT' and manifest['runner']['clean']
```

The normal witness's actual worktree/revision, clean source, evidence authority, compiled SDK dictionary, request plan, quote, rates, raw provider response, audit and settlement checks all remain. The helper verifies that replacing that one assertion restores the complete original literal and AST, and saves the independent literal diff and hashes. It never runs a child itself. The normal bounded runner must retain each original child/supervisor exit, timeout/reaping state, source identity, exact argv, script hash, raw result bytes and result hash. Failed or uncertain outcomes refuse adjudication rather than receiving partial-success credit.

Both sources must have all 15 guarded module inventories and four exact parser/package inputs, plus the witness's billing byte identity. The complete `compile_request` and `maximum_cost` function ASTs, the entire `transcript_context.py` AST and the four parser/package input bytes must match before commands are prepared. Other complete AST differences remain explicit inventory differences for the integration owner's adjudication. Matching a few captured wires does not approve an unrelated billing or clinical source change.

After separately retained zero-exit executions, the helper compares every actual paid report row, including the recorded SDK request identity, model/output cap, quote, calculated cost, stored customer limit, actual QA charge, provider request/message identity and sealed audit. The complete geographic/context offline quote-control rows must also match. All 14 original witness module byte identities are mandatory; missing modules and dropped or duplicate attempts refuse. The original report's legacy key `current_actual_provider_rows` is interpreted as **OLD paid rows reconstructed at a specified source**, never as NEW sends. The output keeps both source commits separately and leaves financial-pin approval pending.

## Reviewed voice remains separate

Campaign-4 model attempts 017/019 contain a recorded `patient_default_context` in the SDK payload. The existing witness reconstructs ordinary requests from `configuration(fields)` without that saved context, so it cannot reproduce those actual reviewed-voice wires. Its additional synthetic context fixtures prove offline price behavior; they do not reproduce a clinician's saved review authorization. This preparation keeps reviewed voice explicitly pending. Complete unchanged context-compiler AST and parser/package inputs can bound the unchanged compiler dependency, but cannot confer an actual reviewed-voice replay. A prospective later live voice campaign may supply the distinct actual request and settlement evidence.

## Normal invocation after a reviewed final binding

The integration owner copies the prospective plan to a new protected owned JSON file, sets `status=prospectively_bound`, binds exact clean OLD/NEW worktree paths and commits, and fills `old_files` with the helper's complete `source_identity` objects. `new_source_tree` and `new_files` bind the declared NEW inventory. The fixed groups and pending voice scope stay unchanged. The original PREPARED plan is retained.

```text
PYTHON financial_source_transfer.source --prepare \
  --binding OWNED/prospectively-bound.json \
  --witness rebuild/ops/fixtures/current_wire_price_witness.source \
  --output OWNED/new-transfer-preparation
```

`prepared.json` contains the exact four commands; each receives its own fresh output directory and normal bounded execution receipt. No command should overwrite an earlier failure. The normal runner seals the raw `result.json` bytes in its receipt as `result_bytes`, alongside the exact argv, child/supervisor status, timeout, reaped/source-unchanged flags, script SHA-256 and result SHA-256. The helper then accepts one sealed preparation hash and both owned original receipts for each group:

```text
PYTHON financial_source_transfer.source --adjudicate \
  --prepared OWNED/new-transfer-preparation/prepared.json --prepared-sha256 EXACT_SHA256 \
  --group 1 --old-receipt OWNED/original-old-execution.json \
  --new-receipt OWNED/original-new-execution.json --output OWNED/new-adjudication
```

Preparation and adjudication read source/evidence metadata only. The witness executions require their separate normal resource grant; neither interface grants a service, provider, installation, payment or release action.

## Finite interface verification

Eleven pure controls passed with actual exit 0 in 0.316 seconds; unittest reported 0.123 seconds. They use project-authored synthetic receipt envelopes, not genuine reconstruction results. Source bytes were unchanged. The raw packet is retained at `operations/financial-source-transfer-interface-first-20261004T190100Z` under the protected continuation runtime. Its log SHA-256 is `d6222d255b5278dcd5271601825d942a46c8386643862499cc46f22de9e15715`.

The controls preserve the original witness hash; prove the single assertion change; require complete compiler/context/input inventory; retain separate OLD/NEW identities; refuse unset source and changed evidence/voice scope; and refuse changed model/cap/quote/cost/charge/limit, omitted or duplicate evidence, changed scripts or dependencies, failed/unknown/unreaped receipts, network/DB crossings and semantic/provider/invoice claims. Actual OLD→NEW reconstruction and accepted pin renewal remain pending review and execution.
