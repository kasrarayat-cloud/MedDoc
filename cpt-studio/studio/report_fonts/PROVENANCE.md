# Fonts embedded in the physician PDF report

The physician PDF report (studio/physician_pdf.py) embeds subsets of these fonts. They are the typefaces named in the
owner-approved design handoff of 2026-11-21 (DESIGN-TOKENS.json: Cormorant Garamond Medium, Manrope Regular/SemiBold,
IBM Plex Mono Medium), all under the SIL Open Font License 1.1, plus DejaVu Sans as the fallback for characters the
design fonts do not contain (so an exact quotation never prints a blank box). Nothing is fetched at run time.

| file | source | licence | sha256 |
|---|---|---|---|
| CormorantGaramond-Medium.ttf | static instance (wght=500, fontTools varLib.instancer --update-name-table) of google/fonts@06bfe0d62a98375cb09c942fa18e68bd32cff057 ofl/cormorantgaramond/CormorantGaramond[wght].ttf (sha256 `b20b7d9626dd956b2c5e558692ad328b1f19e3275e2782db4fa07670d83f35e0`) | OFL-CormorantGaramond.txt (no Reserved Font Name) | `fc4881dac34d2f05d11b1bea22d1d01b869c3f7b4a93194ce1eaaf0946ab571c` |
| Manrope-Regular.ttf | static instance (wght=400) of google/fonts@06bfe0d62a98375cb09c942fa18e68bd32cff057 ofl/manrope/Manrope[wght].ttf (sha256 `3ae11c49db0455a3cc33e37d380f20fdb8c7f8b41dc07625c177e3d87a9d6ae6`) | OFL-Manrope.txt (no Reserved Font Name) | `14c777b3f70944b8ccdca5a0d47ec100e9379840a6820f27e570078c9efdbb29` |
| Manrope-SemiBold.ttf | static instance (wght=600) of the same file | OFL-Manrope.txt | `64d1481164999235b2431381ca98e513f167422f8d4c41fe496f868669c30b97` |
| IBMPlexMono-Medium.ttf | google/fonts@06bfe0d62a98375cb09c942fa18e68bd32cff057 ofl/ibmplexmono/IBMPlexMono-Medium.ttf, unmodified | OFL-IBMPlexMono.txt (Reserved Font Name "Plex"; file unmodified) | `a9b4c49bb299e05b5f6c481e7fb5e78943d2793249a0c8874ab574a2d1ea6755` |
| IBMPlexMono-Regular.ttf | google/fonts@06bfe0d62a98375cb09c942fa18e68bd32cff057 ofl/ibmplexmono/IBMPlexMono-Regular.ttf, unmodified | OFL-IBMPlexMono.txt | `6a3412f058c7d8dfd9170c41e85ade48e5156ecb89356110ca57a0a27734af46` |
| DejaVuSans.ttf | dejavu-fonts release 2.37 (dejavu-fonts-ttf-2.37.zip, sha256 `7576310b219e04159d35ff61dd4a4ec4cdba4f35c00e002a136f00e96a908b0a`), ttf/DejaVuSans.ttf, unmodified | LICENSE-DejaVu.txt | `7da195a74c55bef988d0d48f9508bd5d849425c1770dba5d7bfc6ce9ed848954` |

Downloaded 2026-11-21 from raw.githubusercontent.com/google/fonts/06bfe0d62a98375cb09c942fa18e68bd32cff057/ and github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/.

## The copies the operator console serves

`studio/static/studio/fonts/` holds byte-identical copies of Manrope-Regular.ttf, Manrope-SemiBold.ttf,
IBMPlexMono-Regular.ttf and IBMPlexMono-Medium.ttf with OFL-Manrope.txt and OFL-IBMPlexMono.txt (the sha256 above),
served by the site itself (the Content-Security-Policy allows `font-src 'self'` only) to the operator console's pages, the
design of 2026-11-22 (DECISIONS D395). Nothing is fetched from another site. This note stays here, outside the static
tree, so the site does not serve it (tests/test_admin_console.py holds the copies to these files).
