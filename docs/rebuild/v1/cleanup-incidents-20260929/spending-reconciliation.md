# Spending reconciliation — quillmd-v1-sonnet5-staged-40 (2026-09-29T13:3xZ, read-only)

Authority: "Approve the staged $40 maximum", quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk
(record QuillMD-V1-Sonnet5-Budget-Approval-20260928.json: single campaign; caps cumulative across sessions,
retries and workers; routine same-scope repairs need no repeat approval; unused stage budget not transferable;
no expiry stated). Declaration docs/foundation/mutations/20260928-quillmd-v1-sonnet5-staged-campaign.md @01ff8c7d.

Sources compared (all agree):
- ledger 001-017 attempt/outcome + stage decisions (runtime v1-sonnet5-campaign/ledger);
- per-attempt manifests: every listed evidence file present, sha256 equal (verify_campaign.py; 0 problems);
- recomputed cost from recorded usage at pinned rates ($2/$10/$0.20 per M) equals each recorded computed_cost;
- QA database: 17 ProviderReceipt rows, sum 0.079304, 17 distinct request ids identical to the ledger's, 0 simulated;
  17 Usage rows sum 0.079304; 17 reservations settled; jobs: 15 generation succeeded, 1 generation failed, 1 mapping failed;
- `ops/sonnet5_qa.py status` (runner 631d81af): open_attempts [], campaign_stop null, credential_file_present true.

| stage | limit | attempts | calculated exposure | remaining | state |
|---|---|---|---|---|---|
| model_check | 5.00 | 1 | 0.002860 | 4.997140 | passed |
| mapping | 25.00 | 1 | 0.009840 | 24.990160 | failed, 0 reopenings |
| ordinary_notes | 10.00 | 15 | 0.066604 | 9.933396 | failed, 0 reopenings |
| total | 40.00 | 17 | 0.079304 | 39.920696 | no unknown outcome |

These are CALCULATED costs (configured rates × provider-reported usage). No provider billing evidence exists in
this environment: the campaign credential is a Messages API key (it served the model check), and usage/cost
reports need an Admin key, which is not available here. Application charges (1.5× reservations) are separate
and are not provider billing. Credential file: mode 0600, owner-only, 1 link, one line (content not read).
