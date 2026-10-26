# Corti fixtures — retained synthetic exchanges (byte-identical copies)

Everything here is **synthetic**: fictional patients ("Synthetic Taylor Reed",
"Synthetic Rowan Blake") written for software testing. No real patient data.
The files are byte-for-byte copies of fixtures the QuillMD rebuild retained from
earlier synthetic Corti runs, copied (not imported) so CPT Studio's provider
tests run offline against real provider output. Source revision: the
`rebuild/` tree at `a82c6bcfd` on `feat/cpt-studio-gi-20261023`; the last
commit touching the sources is `dcd24d079`.

| copy | source (repository path) | bytes | sha256 |
|---|---|---|---|
| `taylor-reed.request.json` | `rebuild/core/tests/fixtures/corti/request.json` | 840 | `ad7eab6f2c3a95a0ea7e3a3d01345bb9762325a52d0b6d22e619386585fe5bd3` |
| `taylor-reed.response.raw.json` | `rebuild/core/tests/fixtures/corti/response.raw.json` | 6141 | `560b4c979bf734a3b6ad6cf2aafaeadfc67226e3c5463da0959bd80181e5dc7f` |
| `taylor-reed.provenance.txt` | `rebuild/core/tests/fixtures/corti/README.txt` | 314 | `8c1f5740a21cbc0a717fab8ba4882592af4c483e1b66fbb6676762451ed9df9b` |
| `rowan.response.raw.json` | `rebuild/core/tests/fixtures/rowan_corti_live_response.json` | 7864 | `205c8e586139407bf959d4f69420a41e0ebe1b50e972242f72d18e4e9cd12d86` |
| `rowan.source.txt` | `rebuild/core/tests/fixtures/rowan/source.txt` | 2135 | `462613fe7482464d9cfdd73e0cf7dea28b532f7416e1e428aaa4a49143ef0f08` |

`tests/test_providers.py` asserts every hash above, so a changed byte fails the suite.

## What each file is, and what it is not

- **Taylor Reed** — the original request (one text context; the service date
  is inside the note) and Corti's raw response. `taylor-reed.provenance.txt` is
  the rebuild's own README for them, kept as provenance: it records the
  original verdict `FAIL_RESPONSE_QUALITY_WITH_SELECTED_CODES_PASS` and the
  response sha256, which equals the copy's.
- **Rowan Blake** — Corti's raw response and, in `rowan.source.txt`, the note
  its evidence offsets point into. The note was not in the requested copy list;
  it is copied because evidence exactness cannot be checked without the exact
  source text. Its sha256 equals the `source_sha256` recorded in the provenance
  of `rebuild/core/tests/fixtures/rowan_objective_retained.json`. It has CRLF
  line endings, kept verbatim: the offsets count those characters. The original
  Rowan **request** was not retained as a file; the tests build one from this
  note with a service date. Every evidence span in the response references
  context 0, which that build reproduces exactly; no claim is made that the
  rebuilt request hashes to the original.

Provider `display` strings are untrusted provider wording — the 99213 display
in the Taylor Reed response is the documented defect — and are never used as
descriptors. `usageInfo` values are historical; replaying them is not new usage.
