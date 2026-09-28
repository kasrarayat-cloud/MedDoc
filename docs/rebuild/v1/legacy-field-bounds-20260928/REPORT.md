# Legacy text limits and protected micro guidance

Prepared from `17f0aefe963be64c45aa15789df8d792b042f351` in the isolated `fix/v1-legacy-field-bounds` branch. Shared main, prior branches and original documents remain unchanged. No provider, payment, database, native Word, push, merge, deployment or activation was used.

## Source rules

[Microsoft’s OOXML MaxLength reference](https://learn.microsoft.com/en-us/dotnet/api/documentformat.openxml.wordprocessing.maxlength?view=openxml-3.0.1) specifies a character limit before field formatting; omission leaves no native character limit. An already overlength stored value is preserved on load. [Microsoft’s Word implementation note for 17.16.26](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-oi29500/e6ea592a-fffb-4630-a068-94e9d7139d4f) narrows the attribute to a positive XML Schema short, so supported explicit values are1..32767. Explicit zero is therefore protected as unsupported; the zero-as-unlimited convention of binary .doc FFData is a different representation and is not borrowed for OOXML. Missing, zero and malformed source attributes are not conflated.

New mappings expose supported native limits through existing max_chars metadata, intersected with existing layout bounds and every repeated header copy. The actual writer reads the native limit again from the source field before changing its result. Old maps, removed/enlarged max_chars metadata and direct helper callers cannot enlarge that native cap. Nothing is truncated. Existing populated overlength values remain exact on an unanswered export; replacing them with a value within the cap remains possible. Unsupported explicit limits remain visible protected fields and unchanged on missing export.

A tiny guidance carrier is recognized only from the complete source conjunction: regular FORMTEXT, no name, a blank explicit default and result, native one-character cap, nonempty literal status/help text, blank paragraph outside a table cell, and explicit half-point or one-point typography on every run from begin through end. These controls remain enabled and physically present with their complete original help, result, field properties and navigation. They remain in the mapping with write_protected and a specific review reason. Complete literal status/help is retained as fingerprint-bound source_instructions. This is protection of ambiguous guidance ownership, not a declaration that enabled controls cease to be native inputs.

Protection is derived again from original source before any field mutation, including ancestor destinations from older/forged maps. Removing write_protected, its reason or source metadata cannot permit a write. Named, visibly labelled, visibly sized, populated and mixed-style input controls remain outside this narrow guidance classification; their valid native character caps still apply. Visible paired-cell one-character input and omitted-cap text have positive controls. No-op validated exports retain exact original ZIP bytes, matching the separately prepared D10 no-op repair.

## Preserved first failures and original replay

Ignored evidence is under `rebuild/.runtime/legacy-field-bounds/`. `baseline-and-original.json` imports the unchanged17f source into an isolated module and records two exact failures: visible Code maxLength1 accepts AB; blank unnamed1pt guidance accepts A. The repaired module refuses both. The earlier D31 navigation field accepted a56-character sentence at1pt, preserved in the independent header review runtime of `v1-ordinary-facts`. No baseline result was overwritten.

Unchanged original D31 SHA `f730aa53671ab367eb5e89376d653ef0d51f096962ae616480711a292eeed36d` has ten such controls across b/p[2],p[60],p[62],p[69],p[89]. All66 detected fields remain in the new map; exactly those ten legacy controls are protected. Every attempted one-character write to them refuses. Missing export is byte-identical to the original and every original legacy field XML is unchanged. Their full help is retained. This does not close D31’s unrelated mapping, attestation, reference ownership or whole-workflow gaps.

Initial eight focused methods PASS in4.005seconds. The finished affected Word union passed202 methods in93.660seconds, with zero skips (`word-union-01.log`), including the final ten native-field methods. Tests include old/enlarged metadata, direct writer, parent destination bypass, cap omission versus invalid/zero, existing overlength preservation, complete help and actual sandbox JSON/export.

## Integration boundary

Root has concurrent reference-guidance protection in word_v3.fill. Union its source_detector.protected_regions with this independent source-derived legacy protection; retain both checks. Root has three new guidance tests in the same module; keep all methods. The no-op package-write line is intentionally the same as the separately prepared D10 component. Independent finished-diff refutation remains required before integration qualification.
