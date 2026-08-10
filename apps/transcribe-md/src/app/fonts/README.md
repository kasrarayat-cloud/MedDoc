# Self-hosted fonts — provenance and licence

These files were fetched **once** from Google Fonts and committed so that
`next build` no longer reaches Google's servers. See the note in
`AGENTS.md` (external faults) for why.

Every family here is licensed under the **SIL Open Font License 1.1**, whose
full text is in `OFL.txt` alongside this file. The copyright lines below are
taken verbatim from each family's own `OFL.txt` in `google/fonts`.

| family | file | copyright |
|---|---|---|
| Inter | `inter-latin.woff2` | Copyright 2020 The Inter Project Authors (https://github.com/rsms/inter) |
| JetBrains Mono | `jetbrains-mono-latin.woff2` | Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono) |
| Bricolage Grotesque | `bricolage-grotesque-latin.woff2` | Copyright 2022 The Bricolage Grotesque Project Authors (https://github.com/ateliertriay/bricolage) |
| Figtree | `figtree-latin.woff2` | Copyright 2022 The Figtree Project Authors (https://github.com/erikdkennedy/figtree) |
| Source Serif 4 | `source-serif-4-latin{,-italic}.woff2` | Copyright 2014 The Source Serif 4 Project Authors (https://github.com/adobe-fonts/source-serif) |

## What was fetched, exactly

Each file is the **latin** subset, which is the only subset the previous
`next/font/google` configuration requested (`subsets: ['latin']`).

⚠️ **These are VARIABLE fonts.** Google serves one file per style covering the
whole weight range, and emits a separate `@font-face` per requested weight all
pointing at that same file. The first fetch downloaded 16 files and 10 were
byte-identical duplicates; the canonical set is **6**. They are declared here
with weight RANGES rather than as discrete faces, which is what the file
actually is.

| family | style(s) | weight range declared | previously requested |
|---|---|---|---|
| Inter | normal | `400 700` | 400, 500, 600 (app) · 400–700 (marketing) |
| JetBrains Mono | normal | `400 500` | 400, 500 |
| Bricolage Grotesque | normal | `500 700` | 500, 600, 700 |
| Figtree | normal | `400 600` | 400, 500, 600 |
| Source Serif 4 | normal + italic | `400 600` | 400, 600 × normal, italic |

## Refreshing them

Re-run `scripts/fetch-self-hosted-fonts.py`. It asserts the woff2 magic number
on every download — a captive portal or an error page would otherwise be
committed as a font and fail only in a browser.

## Not in scope

Gotenberg renders DOCX/PDF exports with its **own** font stack inside its own
container. It is a separate system, untouched by this change, and nothing here
affects export typography.
