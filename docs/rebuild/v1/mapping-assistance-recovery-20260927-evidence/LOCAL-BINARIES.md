# Retained local synthetic binaries

The pre-commit clinical-document guard does not admit DOCX/PDF files from this
path. No override was used. All originals and outputs are synthetic, generated
by `core.tests.test_mapping_assistance.MappingAssistance`; no patient data.
Their hashes remain in manifest-sha256.json. They remain on this worktree at the
manifest paths, and in `rebuild/.runtime/mapping-assistance-20260927/` under
artifacts/, final-artifacts/ and render-output/. Neither copy was deleted.
The committed screenshots, text-layer results and test generator remain
reviewable in a fresh checkout. Binary hash verification requires the retained
local copies. A local copy of these files is evidence, not a deployed artifact.
