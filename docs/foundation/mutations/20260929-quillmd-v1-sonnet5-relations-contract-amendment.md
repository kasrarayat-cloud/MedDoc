# Contract-identity amendment: ordinary-notes field relations (2026-09-29)

campaign: quillmd-v1-sonnet5-staged-40
authority_id: quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk
amends_declaration_sha256: 76bfb6af8dea0d7184be00e7ca9d30f3c1bbc99f62057b1002f3d3643efb5d15
amended_pricing_key: ordinary_notes_field_relations
pinned_pricing_version: configured-v1:eb280d15cbfc2cf52477c57040c3ff11d60352aac5d9a9894bdae4e6a0594180
previous_pricing_version: configured-v1:47caed2bcbbabc7f0d1c2713ba8b497db26f9fdf2dfff1de092410fdd7f784b4
previous_ordinary_field_contract: ordinary-field-relations-v1
ordinary_field_contract: ordinary-field-relations-v2
amended_pricing_version: configured-v1:0d357747cbf72641cb621e38c2e2c409fb94fddaf614ce188fc518067749a2f7

This file changes one thing: the identity of the ordinary-notes field-relations response contract, from v1
(positional context, which structured output did not enforce; attempt 17 failed on it) to v2 (context keyed by
source unit and enforced by the per-request schema). The base price both identities are bound to (rates, model and
the ordinary request profile) is unchanged, and the runner proves it by recomputing both versions from that base.
Every limit, rate, request setting and approval term stays the declaration's and the ledger's. This is not a new
allowance and changes no number. It covers only the recorded remainder of the notes plan: N03, N10, N13, N14, N15
and N16 on the field-relations path.
