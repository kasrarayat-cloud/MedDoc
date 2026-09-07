# A BUNDLE-PRESENCE ROW MUST NAME AN **EXPORTED** SYMBOL, OR IT MEASURES THE MINIFIER

**Ratified 2026-09-07, from the `43fcf4a6` deploy judgement.**

A §2.5 rows file asserted that four new symbols would appear in the shipped
Next.js server bundle, each measured **0** in the running image beforehand — a
properly discriminating check, on the face of it.

**Two of the four came back 0 after a deploy that had demonstrably shipped them.**

> **They were LOCAL (non-exported) functions, and the bundler renames them.**

## THE CONTROL THAT SETTLED IT, AND WHY IT HAD TO COME FROM ANOTHER ERA

A same-era control could not distinguish "did not ship" from "cannot be seen".
The discriminator was three functions that have shipped for **months**:

| symbol | kind | count in bundle |
|---|---|---|
| `resolveRosFinding`, `symptomsFor` | **exported**, pre-existing | **6, 8** |
| `inferTextKind`, `isScaffolded`, `normalizeLabel` | **local**, pre-existing | **0, 0, 0** |
| `readableRosToken`, `isEmptyText` | **exported**, new | **9, 5** |
| `rosDocumentValue`, `isProseLabel` | **local**, new | **0, 0** |

Three functions in production for months read zero. **The check was measuring
the minifier**, and the two exported symbols in the very same row worked exactly
as intended — which is what proves the instrument was fine and the *choice of
symbol* was the defect.

## THE RULE

> **`grep <symbol> .next/server` is a valid deploy row ONLY when the symbol is
> EXPORTED.** For anything local, the row proves nothing and will read as a
> failed deploy on a deploy that succeeded.

**And the better answer is usually behaviour, not presence.** What actually
settled the change here was that the certified production compiled version
records the field `kind` the change was written to produce. A behavioural row
survives minification, bundler upgrades and tree-shaking, none of which a name
does.

⚠️ **THE FAILURE MODE IS THE EXPENSIVE DIRECTION.** A row like this reads as
*"the fix did not ship"* on a deploy that shipped it perfectly — inviting a
rollback, or a second deploy, to fix nothing.
