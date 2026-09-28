# Ordinary request pricing and cost-scanner integration

The new ordinary compiler is an imported SDK send and pricing dependency. A scanner that only approves `generation_batch.py` can miss a changed compiler, Decimal binding, output envelope or actual single-request send. This change binds the complete normalized `v3_field_relations.py` module and checks the exact early price/send dispatch in `generation.py`; batch approval includes the imported ordinary proof. Unknown or changed source fails closed. The existing mapping, history, alias/escape and batch controls remain in force.

Reviewed source union: 40fb602f8f1cf9076ba97edeaf711add4090309b plus c14dda346c29d232b9be8d9a3e31b844d9e20b21, cherry-picked as 808d0f7a8688e269c8a3584706395994875fe010. Ordinary 20k remains default off; this is no operational activation or paid-call authorization.

The financial review traced configuration(fields), quoted config, single and below 100 batch dispatch, complete request compiler, response-byte admission, immutable stored profile, request digest, all-child reservation and unchanged settlement/reconciliation. New ordinary disabled-thinking requests carry a distinct 20,000-token profile; old 8k/16k stored profiles reconstruct exactly. The removed 256-cell admission is replaced by complete serialized-response capacity, retaining 100 requested fields, 512,000 request bytes, 50,000 source characters and eight indivisible children. The actual wire bytes plus 12,000 input overhead and exact output cap are priced, with US 1.1 and retail 1.5 applied. The additional 12k output allowance adds $0.12 provider/$0.18 retail globally, plus $0.000002 input for the extra serialized digit at $2/million. US amounts multiply by 1.1. No retry, free-send or settlement bypass was added.

The union includes disposition quarantine guards at batch run/finish/local-recovery entry. Their current require_processing helper only refuses restored-target processing; it adds no provider/price/reservation path. Any later batch-module change invalidates its reviewed identity and must be reconciled before integration.

Independent execution on the exact combined source:

- 13 ordinary profile, complete batch and authenticated workflow methods PASS in 28.927 seconds, zero skips. Tests cover 20,000/20,001 response capacity, 512,000/512,001 actual request bytes, exact SDK kwargs versus quote, US/retail, every child hold before send, unknown second response held/no retry, cancellation/flag withdrawal and one-time complete adoption. Only mocked provider responses; no provider/token-count calls.
- 15 scanner/document methods PASS in 31.497 seconds, zero skips. New positive single/batch/compiler checks resolve all general caps 6k/8k/16k/20k and keep the distinct mapping 20k profile. 17 new source mutants refuse: input overhead removal, output underpricing, geography zeroing, catalogue/source truncation, post-compile cap mutation, request escape, replaced Decimal/JSON imports, compiler decoration, altered price/send dispatch, alternate SDK payloads and retries. Existing negative controls also pass.
- Historical ordinary-enabled 8k/16k config, full plan, child requests and prices independently replayed against immutable pre-profile inputs and match baseline bytes exactly: SHA256 ba88c6aa9acc95f4f5c2cd2e4d8a39e417f6e45e441e044bfc39a63ab791cd7e.

Evidence is retained at this worktree's `rebuild/.runtime/ordinary-scanner-20260928/`. The financial run used only root-owned synthetic PostgreSQL container 2b8397103aec77d61fe4d363e445ff93e96dd8518ae25341ed3ca69a2c9f8bf1, loopback 55821, uniquely named database `test_v1_ordinary20k_financial_20260928_0436` retained. The run manifest asserts clinical source hashes unchanged. Installed data was not accessed. Historical replay used no DB (port 1) and no provider.

Fixed normalized AST identities (not learned from inspected source during scanner execution):

| Module | SHA256 |
|---|---|
| core/generation_batch.py |9173e760118b7346d83032f6ccad5cc48518ef6be2ee0e9e4fb1fd5a86682ff5|
| core/batch_jobs.py |94e727600ce8386b6751c3de250019a561f1d4cdc0e8a57d5717a35d0cfd6c5a|
| core/v3_field_relations.py |636dcb8f16a6a07f9bcec54141f9ba7a91bc1e3af4add2b35e241be4f39aeff3|

NOTHING FOUND in the bounded financial/compiler/caller review. This does not qualify model clinical semantics, D10, or a production release. Final integration must preserve these reviewed sources or obtain a new bounded review and run the scanner on the actual union. The scanner commit is separate from the c14 source ancestor for explicit integration.
