# Independent preserved-value refutation — frozen 952c7e21

Source `/opt/meddoc-pro/.worktrees/v1-batch-preserved-values`, frozen `952c7e2100e451882c1fd837980ab0212dc4f586`. The later `3da5932c` commit is evidence-only; source identity is retained in `01-results.json`. No source, scanner pin, installed service, database, provider or external account changed. Synthetic DOCX packages remained in memory. Network/DB connection methods were explicitly denied; the interpreter environment was scrubbed and bytecode disabled.

## F-B5 — false/invalid placeholder markers erase preserved constrained values

`rebuild/documents/word_v3.py:3783` trusts `sdt_info(...)["placeholder"]` when reading a scalar. `:3742–3747` delegates the new constrained dropdown reading to the same old displayed reader. The underlying `:632` treats the presence of `w:showingPlcHdr` as true without reading its `w:val`.

Concrete input: a real inspected 103-field package contains native scalar date or dropdown Priority A with content `1` and `w:showingPlcHdr w:val="0"`. A is blank/reviewed; B is answered `1`. The complete source-bound uniqueness rule permits 1/2/3 and forbids duplicates.

Observed: validation **ACCEPTED**, effective A `[]`, B `["1"]`; actual output XML retains A's `1` and writes B's `1`. `false` and `off` produce the same result in both scalar and dropdown controls. Installed python-docx `ST_OnOff.convert_from_xml` independently evaluates each of `0`, `false`, `off` as false; that result is retained, so the interpretation is not inferred from the element name alone.

Two malformed `w:val="bogus"` variants are also accepted as blank instead of unknown. These are the same placeholder-reading defect, distinguished from the six valid false-marker inputs.

Controls: absent-marker known scalar/dropdown values are counted; their duplicates refuse. Genuine placeholder controls stay usable, and ordinary explicit valid replacements pass. Original F-B3 and F-B4 refuse in this candidate.

## F-B6 — missing legacy result boundary is accepted as known empty

`rebuild/documents/word_v3.py:3765–3778` obtains the legacy result runs and checks nested/foreign structures and nonempty defaults, but never requires a `separate` boundary for a preserved result.

Concrete input: a legacy FORMTEXT A contains its instruction, a `w:t` holding `1`, and an `end`, but no `separate`. Blank/reviewed A plus explicit B `1` is **ACCEPTED** with A `[]` and B `["1"]`; the output retains A's original `w:t="1"` and B's written `1`.

The demonstrated defect is an unresolved/malformed boundary treated as a known empty value. No native Word rendering was performed, and this report does not certify how desktop Word renders that malformed field. Hyperlinked/nested legacy results and a nonempty default without result correctly refuse in the same probe; a genuinely empty well-delimited field passes.

## Finite results and limit

33 probe cases completed: 23 matched their declared expectation; 9 unexpected acceptances are the two findings above. A tenth unexpected acceptance was a dropdown missing `sdtContent`; the actual XML contains no A value, so that observation alone is **not promoted to a demonstrated wrong-value finding**. Replicated scalar and dropdown controls agree when preserved, disagreeing copies refuse, and explicit writes resolving both copies pass.

First source and results stay immutable in `probe.py` and `01-results.json`. Invocation, from the root repair tree:

```sh
env -i PATH=/usr/bin:/bin QUILLMD_ENV_MANAGED=1 PYTHONDONTWRITEBYTECODE=1 /opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python -B rebuild/.runtime/batch-second-review/probe.py > rebuild/.runtime/batch-second-review/01-results.json
```

This is a pure in-memory component refutation, not an HTTP/worker/sandbox-subprocess or native Word qualification. After repair, replay against new output files and retain these first results.
