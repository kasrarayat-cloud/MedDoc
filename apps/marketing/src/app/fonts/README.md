# Self-hosted fonts — marketing

Fetched once from Google Fonts and committed so `next build` does not reach
Google's servers. Same rationale and licence as
`apps/transcribe-md/src/app/fonts/README.md`; full SIL OFL 1.1 text in `OFL.txt`.

| family | file(s) | used by | kind |
|---|---|---|---|
| Inter | `inter-latin.woff2` | `layout.tsx` `--font-sans` | variable, `400 700` |
| JetBrains Mono | `jetbrains-mono-latin.woff2` | `layout.tsx` `--font-mono` | variable, `400 500` |
| Manrope | `manrope-latin.woff2` | `page.tsx` `--font-body` | variable, `200 800` |
| IBM Plex Mono | `ibm-plex-mono-latin-{400,500,600}.woff2` | `page.tsx` `--font-mono` | **static — three distinct files** |

⚠️ **IBM Plex Mono is the exception.** Every other family here is a variable
font that Google serves as ONE file for the whole weight range. IBM Plex Mono's
400/500/600 are genuinely different files (14,708 / 14,888 / 15,620 bytes,
three distinct checksums). Declaring it as a range would load one weight and let
the browser synthesise the others.

Copyright lines are in each family's upstream `OFL.txt` in `google/fonts`;
refresh with `scripts/fetch-self-hosted-fonts.py`.
