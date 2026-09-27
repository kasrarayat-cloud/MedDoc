# Correction to original full-test mutation evidence

2026-09-27. The root found that the original `probe.py` first populated the scanner's `all_provider_caps` LRU cache by running the baseline. Its subsequent `Path.read_text` mapping mutations did not invalidate that cache. The original `probe.json` and `REPORT.md` therefore overstate the two mapping full-test PASS results as proof that mutated mapping source was re-read. Those full-test citations are withdrawn as mapping mutation proof. All original files and outputs remain preserved.

The extracted fake-client alias execution still demonstrates that the mutated statements submit 90,000 tokens, and the annotated assignment still demonstrably sets cost to zero. Those executions alone do not prove that the original full scanner read those mutations. The code inspection identified the permissive Dict and missing annotated-store rules; the root separately reported direct `provider_caps` controls supporting the pre-fix holes.

The narrative return-zero case goes through `maximum_cost_terms`, which is not that cached function, but the final recheck avoids the ambiguity entirely by rerunning the original three mutations against the scanner with caching removed.

Final reviewed scanner before rerun: `f6b59ca04cc69f8f3d4b20a8c6b4c75696df073e468c35976b75368daf45ed66`.
Negative-controls source: `3f83f448a8a93333809236c493de7ff45d4180d880c74682f5bd28ad2c449c17`.
The same unmodified probe now runs into a separate `probe-repaired-uncached.json`; its result is the current evidence. No application source file is edited by the probe.
