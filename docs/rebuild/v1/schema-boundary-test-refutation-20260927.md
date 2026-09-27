# Independent mapping schema boundary test review — 2026-09-27

**NOTHING FOUND.** Reviewed test-only commit `91db0eb784b9f3085390154d54dba14814655fd9` against parent `33759ab04c9e0bb6ab93554efec37e9c35abe8f1`.

- Exact git-tree comparison confirms every tracked blob and file mode except `rebuild/core/tests/test_anthropic_schema_compatibility.py` is identical. Production behavior was not changed.
- AST comparison confirms the existing actual-SDK schema tests and wire helper are unchanged. The strict rejection assertion body is unchanged; the stale ASCII 301-character negative becomes 1,001, and an astral 1,001-character negative is added. Empty labels, negative glyphs and boolean glyphs remain rejected.
- The new positives assert exact complete label equality at 301 and 1,000 code points for ASCII and astral characters. These are code-point boundaries, not UTF-16-unit counts.
- Independent execution of all four module tests passes. The SDK body controls run the actual SDK through `httpx.MockTransport`, with a synthetic key and forbidden sockets; there is no real provider request. No database was configured or used.
- Two independent in-memory mutations are killed: restoring the old 300 cap fails the new positive test, and loosening the cap to 1,001 fails the strict negative test. Five aggregate review controls pass; zero socket/process attempts occurred.

Private evidence: `/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus/custodian-20260927/schema-boundary-91db0eb7-20260927`. It includes both complete git-tree manifests, both test snapshots, current source hashes, runner and full normal/mutation results.

No full suite was repeated, and no corpus, tokenizer or native Word was used. The original 33759 CI failure remains historical evidence. This bounded review does not replace required CI on the exact new candidate.

Seal: `065-schema-boundary-review-seal.json`, SHA256 `ec2d854a089366ddec9403ad43e194d7d153732d6ded0c2ccc873817a8de6d0f`.
