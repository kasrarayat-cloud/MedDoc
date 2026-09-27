# Offline mapping implementation lock — 2026-09-27

Base: `0d90fa48104cf820743f000d6d47a59f8f6daa81`, isolated
`/opt/meddoc-pro/.worktrees/v1-mapping-assistance`, branch `v1/mapping-assistance`.
Lead approved extending Job with an exclusive template-version scope and reusing
the existing reservation, receipt, usage and ledger path. No provider calls,
qualification reruns, purchases or deployment are authorized here.

## Product and reference lock

Small direct implementation under the Refero design skill. Existing product
references inspected: `template_detail_v3.html` (field table, warning and
confirmation), `voice_limit.html` (explicit charge limit and queued transition),
`financial_detail.html` (operational evidence). Bundled craft-details guidance
supplies explicit labels, keyboard focus and checkbox hit targets.

| Decision | Reference | Preserved role |
|---|---|---|
| Existing mapping table is the review destination | template_detail_v3 | Original, fields and corrections remain together |
| Reuse notice, table-wrap, form-footer, check-label | current app / craft-details | Warning, tabular evidence, action, explicit acknowledgement |
| Show every unresolved area before confirmation | owner requirement | No silent omissions; manual resolution marked assisted |
| Separate price approval from mapping confirmation | voice_limit | Funds permission does not certify clinical mappings |
| No new CSS, illustrations or branding | current product | Existing typography, focus, spacing and responsive behavior |

## Boundaries

The compiler receives only an integrity-checked blank template and its immutable
mapping version. Its isolated outline contains full source strings, not the
120-character UI previews. Hard size limits refuse whole requests; nothing is
silently shortened. The response cannot supply XML, paths, field keys, arbitrary
locators, option destinations or executable operations. Source-bound proposals
go through existing writers. Every source slot and existing field requires an
explicit verdict. Rejected changes preserve existing fields and become visible
unresolved review records. Qualified legacy/WM mappings retain their existing
backend and are outside this new v3-only operation.

All operations start disabled. Live enablement still requires model/account,
financial authority and release qualification. Offline mocks are not evidence of
Sonnet behavior or Word compatibility. Existing corpus and first-pass results
remain untouched.
