---
id: A10-P2-002
severity: P2
domain: UX — print fidelity
title: No print stylesheet anywhere; Cmd+P on a SOAP note prints the dark canvas + chrome + sidebar
---

## Issue

The transcribe-md app has zero `@media print` rules and zero Tailwind `print:` utility usages. A doctor pressing Cmd+P / Ctrl+P on a signed SOAP note (`/visits/[id]`) gets:

- The 240-px IconRail sidebar reproduced on every page (wastes ~25% of page width).
- The 48-px sticky TopNav at the top of every page.
- The dark `--color-linear-bg: #08090a` canvas as page background — which most printers attempt to render as solid black, eating toner and obscuring text. Browsers default to "Background graphics: off" but the visit-detail SOAP body uses inline `style={{ background: 'var(...)' }}` heavily, which shows up regardless when the user enables backgrounds (or in Print to PDF, which most clinicians use).
- The processing-state pulsing halo, animated grid background, and command-palette mount inside the layout get included in the print stream.
- No page-break logic — long SOAP narratives split mid-paragraph or mid-sentence between pages.
- No printed header (patient name, visit date, signing clinician) or footer (page X of Y, signed timestamp) — required for a printed clinical artefact.

The product offers PDF export via the sign-and-send modal — but doctors *will* press Cmd+P. It is muscle memory. The current behaviour is unacceptable as a printed clinical document.

## Evidence

```bash
$ grep -rn "@media print\|print:" apps/transcribe-md/src/
# (no matches outside docs)
```

`apps/transcribe-md/src/app/globals.css` — 4000+ lines, zero print-scoped rules.
`apps/transcribe-md/src/app/visits/[id]/page.tsx` and the `soap-editor.tsx` it mounts — no print-aware structural classes.

The PDF export route does the right thing via pdfkit (server-rendered, structured, paginated) — but Cmd+P bypasses it.

## Risk

- A doctor in a clinic that still uses paper handoff to a referring specialist prints the visit, ends up with 12 pages of mostly-empty page chrome and a black background. That doctor will hit Print, look at the preview, and leave the product.
- HIPAA / charting workflows in many practices still rely on a paper trail signed and tucked into a chart. This is a real workflow.
- The sign-and-send PDF is accessible only inside the export modal; first-time users won't know it exists.

## Recommended fix

Add a `@media print` block at the bottom of `apps/transcribe-md/src/app/globals.css`:

```css
@media print {
  /* 1. Strip every chrome surface. */
  .qm-lin-app { display: block !important; }
  .qm-lin-chrome,            /* TopNav */
  [data-icon-rail],          /* IconRail — add a data attr */
  .qm-lin-spotlight,         /* Modals — Esc-out before printing, but defensive */
  [data-sonner-toaster],     /* Toasts */
  .qm-lin-rx-rail-filter,    /* Right-rail filters */
  [data-tab-bar],            /* Tab nav inside visit detail */
  button { display: none !important; }

  /* 2. Force light page. */
  html, body, .qm-lin-app, main, * {
    background: white !important;
    color: black !important;
    box-shadow: none !important;
  }

  /* 3. SOAP body — full-bleed, serif for readability. */
  .qm-lin-soap-section {
    page-break-inside: avoid;
    break-inside: avoid-page;
    margin-bottom: 1.5em;
  }
  .qm-lin-soap-section-body {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 11.5pt;
    line-height: 1.45;
  }

  /* 4. Headers + footers — running elements would be ideal but not
   * universal; for now bake a printable visit-meta header into the
   * page top by un-hiding a print-only class. */
  .qm-print-header { display: block !important; }

  /* 5. Page setup — letter, 0.75" margins. */
  @page {
    size: letter;
    margin: 0.75in;
  }
}
```

Then add a `<div className="qm-print-header" hidden>` block to `apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx` rendering: visit ID, patient name, DOB, specialty, signing clinician, signed timestamp. The `hidden` attribute keeps it off-screen; the `display: block !important` print rule reveals it.

For pagination in long SOAPs, add `page-break-inside: avoid` to each section card and `page-break-after: avoid` to section headings — keeps S/O/A/P labels with their first paragraph.

Test by hitting Cmd+P on a signed visit before and after; PDF preview should be a clean white-paper letter-format document with no sidebar/chrome.
