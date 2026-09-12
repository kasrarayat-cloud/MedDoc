# TOKEN-1 / PANEL-1 — follow-ups from the adversarial pass

The refutation pass over `feat/token1-panel1` found four MAJOR/BLOCKING items,
all FIXED before merge (the insert door mirrors the token decline and scans the
inserted value; the cert self-test scans scaffold + practice-default TEXTS
non-vacuously; the choice-marker strip that ate an embedded token was removed;
the byte-scan covers footnotes/endnotes; the token-only offer-drop was removed).
These MINOR items are accepted for this change and left as follow-ups.

## 1 · RESIDUAL-SCAN NO-SEPARATOR FALSE POSITIVE (minor)

`residualPlaceholdersInDocx` concatenates every `<w:t>` run in a part with NO
separator, to catch a token Word split across runs (`{`,`patient`,`}`). The
tradeoff: a stray `{` ending one paragraph and a `word}` starting the next
concatenate into a spurious `{word}` and could block a fresh CERTIFICATION of a
document that has no placeholder. Realism is low (needs a literal dangling brace
in prose), so MINOR. The door path is unaffected — it scans the inserted VALUE
(one string), not concatenated runs. **Fix option:** join runs within a
paragraph but separate paragraphs, or scan `<w:p>` blocks individually.

## 2 · FIELD-CODE (`w:instrText`) AND UNUSUAL PARTS NOT SCANNED (minor)

`residualPlaceholdersInDocx` reads `<w:t>` only, and `PART_RE` now covers
document/header/footer/footnotes/endnotes but not `word/glossary/*` or
building-block parts. A token in a field instruction (`w:instrText`) or a
glossary part escapes the byte-scan. Scaffold inserts write visible `w:t` in the
body, so realism is low. The STATIC cert scan (scaffold + practiceDefault text)
is the primary non-vacuous gate and is unaffected.

## 3 · FILL-CACHE STALENESS ON A PATIENT-RECORD EDIT (minor)

The docx fill cache key is `visitdoc:v9:variant:visitId:soapVersion`. TOKEN-1
now bakes the patient name/age into the cached bytes. The cache is invalidated
on override writes and soapVersion change, but NOT on a patient-record edit
(a corrected DOB or name). So a corrected age/name can serve stale from a warm
cache until TTL expiry or a soapVersion bump. **Same-visit only** — the key pins
`visitId`, so it can never serve another patient's data. **Fix option:**
invalidate a visit's fills when its patient's `name`/`dateOfBirth` changes, or
fold a patient-record version into the cache key.

## 4 · UNRESOLVABLE-TOKEN READING IS FIELD-LEVEL, NOT TOKEN-LEVEL (owner call)

Ruling #315 reads "an unresolvable token renders blank with a named reason" as
declining the WHOLE scaffold-default insert (the field renders blank), rather
than substituting the resolvable tokens and blanking only the unresolvable one
(which would leave a malformed sentence, e.g. "… is a pleasant -year-old …").
This is a judgment on ambiguous wording, chosen for clinical safety. The owner
may reverse it to token-level if a partial sentence is preferred.
