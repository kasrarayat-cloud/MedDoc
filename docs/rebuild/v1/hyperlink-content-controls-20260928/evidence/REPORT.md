# Independent fixed-hyperlink refutation and replay — 2026-09-28

**NOTHING FURTHER FOUND within the bounded finished-diff claims.** The independently demonstrated hyperlink mutations below close on final `word_v3.py` SHA256 `bc7933b67b044197c3ff632530af09ca5c8f9f32090a1f671b70fc46b6ebc7ff`. This is a pure document-engine refutation and replay, not an application workflow, renderer, native Word, provider or whole-document compatibility result.

The initial source was commit `c55f5ffb2942caf2e4d66791f11ee9302e7e07cb`, with `word_v3.py` SHA256 `70ccc1d00e5e26032adfc293d9507324bbcb33f31686e8181b7b35b21da7be52`. Initial findings were generated independently against that unchanged tree. The first repair was separately frozen at SHA256 `8d9df73582a61b0aa1bdc80ca54c4c2f17cc0cd9c72ad0182eddab4bfb5a37c3`; the checkbox-control counterexample refuted that repair. The complete final source/test/CI delta was read independently before replay. No source file was edited by this reviewer.

## Demonstrated first failures

| Source and location | Concrete input → wrong output |
| --- | --- |
| c55, `word_v3.py:3399–3430`, reached through content-control detection at 1348–1374 | Block placeholder SDT with text `Enter report. Contact: ` and a fixed `forms@example.invalid` hyperlink → detector emits one text destination; filling `Synthetic patient answer` deletes the hyperlink. |
| c55, same path | Inline SDT whose content is a hyperlink reading `Enter name` → one text destination; filling it deletes the hyperlink. |
| c55, `set_glyph` at 3164 | Hyperlink containing `☐ Send copies` → one checkbox destination; filling true changes linked source text to `☒ Send copies`. |
| First repair, `set_sdt_checkbox` at 3247–3277 | Native checkbox SDT contains its normal glyph followed by fixed `forms@example.invalid` hyperlink; ` Send copies` follows outside the control → one checkbox destination; filling true blanks the hyperlink's visible text. The writer overwrote its first descendant text node and cleared every later text node. |
| First repair, same path | Native checkbox SDT whose displayed glyph is itself linked → filling true changes the hyperlink text from `☐` to `☒`. |

The hyperlink-around-SDT probe did **not** produce an automatic field on c55 and is not counted as an automatic-path finding. Its direct low-level writer changed linked text before repair and now refuses with `protected_hyperlink`. This direct boundary control does not establish historical application reachability.

## Exact final replay

- The six original `before/*.docx` files were read back byte-for-byte; their captured SHA256 values were asserted before replay. Both content-control failures and the linked glyph now produce no automatic destination, preserve their links, and refuse their original historical nonempty mapping with `protected_hyperlink`.
- The two exact `checkbox-first/*.docx` originals were replayed without regeneration. Both now produce no automatic destination and retain their hyperlinks. Their original historical mappings refuse a true answer with `protected_hyperlink`; empty answers preserve the complete original DOCX bytes. Direct setters refuse before changing the control XML or its checked state.
- Ordinary unlinked SDT and a separate SDT beside fixed linked instructions remain fillable. The final results retain actual answer visibility and unchanged hyperlink XML.
- Ordinary glyph checkboxes before linked option text, and after a separate instruction link, remain fillable with unchanged links. A separate native checkbox beside linked option text likewise remains mapped; its actual checked state becomes `1` while hyperlink XML is unchanged.
- The link-ancestor SDT direct writer now refuses with `protected_hyperlink`.

This closes the retained source/deletion counterexamples under the stated OOXML hyperlink-element scope. Field-code hyperlink representations, all fixed instructions, full application integration, D10/R-T3, model qualification and native Word behavior are outside this evidence. Prior whole-document failures and denominators remain unchanged.

## Retained evidence and provenance

Private synthetic originals/outputs and logs are under `/opt/meddoc-pro/.worktrees/v1-hyperlink-content-controls/rebuild/.runtime/independent-hyperlinks/`. `artifact-manifest.json` records every retained file's relative path, byte size and SHA256. Binary DOCX artifacts stay outside Git; the scripts, JSON results and this report contain synthetic values only and are suitable for a reviewed text-evidence commit.

- `probe.py`, `before/results.json`, `before-first.log`: c55 first capture, including all original failures and positive controls.
- `edges.py`, `before-edges/`, `after-edges/`, `final-edges/`: linked-option boundaries and direct ancestor control.
- `replay.py`, `after/`, `final/`: exact original bytes and original mapping replay on the first/final repairs; first capture is unchanged.
- `sdt_checkbox.py`, `checkbox-first/`, `checkbox-first.log`, `final-checkbox/`: first-repair checkbox data loss and exact-source final replay.
- `final_controls.py`, `final-controls/results.json`: historical checkbox mappings, byte-identical missing answers, refusal before mutation and native-checkbox positive control.
- `source-first-repair.py`: reconstructed from the final source by reversing only the second repair, then required to match the independently recorded first-repair SHA256 exactly. This is a hash-verified reconstruction, not a contemporaneous source snapshot. `source-final.py` is the directly read final source snapshot.

All Python ran with bytecode writes disabled using the existing isolated release interpreter. No database, network, provider, paid call, rendering, infrastructure mutation, deployment, push or merge occurred. All first observations remain separate from repaired outcomes.
