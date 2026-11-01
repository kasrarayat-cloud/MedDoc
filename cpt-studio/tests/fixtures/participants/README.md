# Participant fixtures (synthetic)

Hand-written test data for the harness participant adapters (`cpt-studio/HARNESS.md`). **None of it is vendor output.**
No request was sent to OpenAI or Anthropic to make it, and no credential was used. The note describes no real patient.
The two response files follow the documented shapes of the OpenAI Responses API and the Anthropic Messages API
(`docs/cpt-harness/vendor-and-reference-facts-20261101.md`). Their ids carry `synthetic_fixture` so they can never be
mistaken for a live response.

| file | what it is | sha256 |
|---|---|---|
| `colonoscopy.note.txt` | a two-page synthetic colonoscopy report; page 2 starts at character 343 | `9436025908574d0e062d54bc450521b378f013a55f4530fab1457a234b9c3d67` |
| `astra-colonoscopy.response.json` | a completed Responses API answer from `gpt-6-astra` whose output text is a `harness-reading@2` reading of the note | `f544bc0a2b76299c4f9b367d028411f3cc2b710c75daa17d43e59f7451a781e1` |
| `fable-colonoscopy.response.json` | an `end_turn` Messages API answer from `claude-fable-5-1` (an empty thinking block, then the same reading as text) | `c8884bd5da425fed5186c934ddecb8fd58b5e48115874e3e4ff384c0653ce34c` |

Every quote in the reading is copied from the note, so each is located exactly; the tests build the refused, truncated,
wrong-model, fallback and malformed variants from these files in code. `tests/test_participants_reading.py` pins the
sha256 values above.

**2026-11-01:** both response files gained an empty `references_used` list inside their reading, for `harness-reading@2` (`cpt-studio/HARNESS.md` 11.2). Nothing else in them changed; the sha256 values above are the updated files'.
