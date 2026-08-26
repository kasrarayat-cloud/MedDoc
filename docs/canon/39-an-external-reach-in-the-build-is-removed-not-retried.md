> **ARCHIVED CANON — moved verbatim from `AGENTS.md` on 2026-08-26.**
>
> **This body is the AUTHORITY.** `AGENTS.md` carries a one-line index row
> pointing here; that row is a POINTER, never the rule. Nothing in this file is
> rewritten — corrections are appended and dated and superseded wording is kept,
> because in this programme the correction is the point.
>
> Original position: entry **81 of 124** in `AGENTS.md`, under **This is NOT the Next.js you know**.
> Why the split: `docs/canon/README.md`.

## AN EXTERNAL REACH IN THE BUILD IS REMOVED, NOT RETRIED

**The image build has reached outside this repository exactly twice, and both
cost a night's gate time on 2026-08-10.** They are recorded together because the
second one does not look like the first, and that is the whole lesson.

| reach | how it fails | disposition |
|---|---|---|
| `npm ci` → the npm registry | `npm error code ECONNRESET`, *"network aborted"* — says the word | **retried** (#583): `NPM_CONFIG_FETCH_RETRIES=5` on every stage and workflow, 16 sites |
| `next/font/google` → Google's font servers | **`Module not found: Can't resolve '@vercel/turbopack-next/internal/font/google/font'`** — says nothing | **REMOVED**: self-hosted via `next/font/local` |

⚠️ **THE FONT ONE IS MASKED AS A COMPILE ERROR, AND THAT IS WHY IT IS REMOVED
RATHER THAN RETRIED.** `next/font/google` fetches font CSS at BUILD time. When
that fetch fails, Next emits CSS whose `src:` points at an internal turbopack
module that does not exist, and the build dies pointing at **`layout.tsx`**. It
reads as a code defect in a file nobody touched. There is no retry knob, and a
retry budget would not help a class you cannot recognise.

**If you are reading this because you just saw
`Module not found … turbopack-next/internal/font/google/font`: it is the
network, not your code.** Confirm it in one step — compare the failing commit's
tree SHA with a green one. On 2026-08-10 `725ac66d` and `fefe1c25` had
**byte-identical trees** (`34be7b0e`), passed at 17:09 and failed at 17:53.

The fonts are now committed under each app's `src/app/fonts/`, with provenance,
licence and weight ranges in a README beside them, refreshable via
`scripts/fetch-self-hosted-fonts.py`.

⚠️ **TWO TRAPS IF YOU EVER REFRESH THEM.**
1. **Most Google families are VARIABLE fonts** — one file per style covering the
   whole weight range, served behind a separate `@font-face` per requested
   weight. A naive fetch of 16 weights downloaded **6 unique files and 10 exact
   duplicates**. Declare a weight RANGE, not discrete faces.
2. **Not all of them are.** IBM Plex Mono's 400/500/600 are three genuinely
   different files. Declaring *it* as a range loads one weight and lets the
   browser synthesise the rest — a page that looks nearly right. **Check the
   checksums before you decide which shape to use.**

⚠️ **AND THE SWEEP IS BY IMPORT, NOT BY THE FILE YOU ARE FIXING.**
`grep -rn "next/font/google"` found **ten** importers when the plan assumed two —
including `marketing/page.tsx`, whose fonts are declared in the PAGE rather than
the layout. Migrating an app's layout and not its pages leaves the build
reaching Google and the fix claiming otherwise.

Gotenberg renders exports with its own font stack in its own container. It is a
separate system and none of this touches export typography.

