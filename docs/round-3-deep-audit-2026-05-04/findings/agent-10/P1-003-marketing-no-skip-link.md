---
id: A10-P1-003
severity: P1
domain: a11y / WCAG 2.4.1 (Bypass Blocks)
title: Marketing site has no skip-to-content link on any page
---

## Issue

The transcribe-md root layout renders a "Skip to main content" link (broken targeting aside, see A10-P1-002). The marketing app at `apps/marketing/src/app/layout.tsx` has **no skip link**. A keyboard or screen-reader user landing on quillmd.com must tab through the entire 56-px sticky `.top` nav (brand, 5 nav links, Cmd-K chip, sign-in, sign-up CTA = 9+ tab stops) on every page navigation before reaching the page heading.

The marketing site is the public face — pricing, privacy, security, HIPAA pages are likely audited by hospital procurement teams using assistive tech. A failing WCAG 2.4.1 gate on the public site is the most visible compliance liability in the build.

## Evidence

`apps/marketing/src/app/layout.tsx:51-65`:

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
```

No equivalent of the transcribe-md skip-link block. Each page (`apps/marketing/src/app/page.tsx`, `pricing/page.tsx`, `privacy/page.tsx`, `terms/page.tsx`, `security/page.tsx`, `hipaa/page.tsx`, `contact/page.tsx`, `about/page.tsx`, `demo/page.tsx`, `signup/page.tsx`, `not-found.tsx`) renders its own `<main>`, but no `id` is set on any of them and there is no anchor in the layout pointing to one.

`apps/marketing/src/components/home/Nav.tsx` and `nav-bar.tsx` — the nav is a `position: sticky; top: 0` row with no programmatic landmark to skip past.

## Risk

- **WCAG 2.4.1 Level A failure on every public page.** Marketing is the first impression for a hospital systems administrator vetting QuillMD; a missing skip link is the kind of thing a procurement a11y review will flag in 30 seconds.
- Keyboard users vetting pricing or privacy waste 9+ tab presses per page on every navigation.
- HIPAA / compliance perception: the security and HIPAA marketing pages themselves fail Level A. Optics aside, this is a real liability.

## Recommended fix

Add a skip link to `apps/marketing/src/app/layout.tsx` body. Reuse the landing.css `--sage` token for visibility-on-focus consistency with the rest of the public site:

```tsx
<body className="min-h-screen antialiased">
  <a href="#main" className="skip-link">Skip to main content</a>
  {children}
</body>
```

And add to `apps/marketing/src/app/landing.css`:

```css
.skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
}
.skip-link:focus {
  position: fixed;
  left: 12px;
  top: 12px;
  z-index: 100;
  padding: 8px 14px;
  background: var(--sage);
  color: #061509;
  border-radius: 6px;
  font-weight: 600;
  text-decoration: none;
  font-size: 13px;
  outline: 2px solid var(--sage-bright);
  outline-offset: 2px;
}
```

Then add `id="main" tabIndex={-1}` to every page's `<main>` (10 pages). After the change, run axe with the project=a11y suite extended to cover quillmd.com routes — currently the suite only hits app.quillmd.com.
