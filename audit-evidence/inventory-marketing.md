# Interactive Elements Inventory: apps/marketing/src

**Audit Date:** 2026-04-24  
**Scope:** /opt/meddoc-pro/apps/marketing/src  
**Thoroughness Level:** Medium  
**Total Pages:** 9 routes + 1 home + components

---

## HOME PAGE (/)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/page.tsx`

Composition of subcomponents with interactive elements:

### Nav Component
- **File:** `components/home/Nav.tsx:18-40`
- `<Link href="/">` — "QuillMD" logo (brand)
- `<Link>` array (lines 27-31):
  - href="/#how" — "How"
  - href="/#features" — "Features"
  - href="/#compare" — "Vs. others"
  - href="/#security" — "Security"
  - href="/#pricing" — "Pricing"
  - href="/#faq" — "FAQ"
- `<a href={APP_URL}>` — "Sign in" (line 34)
- `<a href={APP_SIGNUP_URL}>` — "Start free trial →" (line 37)

### Hero Component
- **File:** `components/home/Hero.tsx:83-88`
- `<a href={APP_SIGNUP_URL}>` — "Start 14‑day free trial →" (line 83)
- `<a href="#demo">` — "▸ Watch 90s demo" (line 86)

### FinalCTA Component
- **File:** `components/home/FinalCTA.tsx:33-38`
- `<a href={APP_SIGNUP_URL}>` — "Start 14‑day free trial →" (line 33)
- `<a href="/demo">` — "Book a 15‑min demo" (line 37)

### FAQ Component (Home)
- **File:** `components/home/FAQ.tsx:55-63`
- `<details>` elements with native `<summary>` toggles (no onClick, uses browser default)
- `<a href="mailto:kasra@quillmd.com">` — Email link (line 50)

### Footer Component
- **File:** `components/home/Footer.tsx:49-91`
- `<Link href="/">` — Logo/brand (line 49)
- Product column:
  - href="/#features" — "Features"
  - href="/#demo" — "Live demo"
  - href="/#pricing" — "Pricing"
  - href="/#compare" — "Vs. others"
- Trust column:
  - href="/#security" — "Security"
  - href="/hipaa" — "HIPAA & BAA"
  - href="/privacy" — "Privacy policy"
  - href="/terms" — "Terms of service"
- Resources column:
  - href="/#faq" — "FAQ"
  - href="/demo" — "Watch demo"
  - href="/about" — "About"
  - href="/contact" — "Contact"
- Contact column:
  - href="mailto:kasra@quillmd.com" — Email (external)
  - href="/contact" — "Book a call"

---

## DEMO PAGE (/demo)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/demo/page.tsx`

- **NavBar Component** — See NavBar inventory below
- `<SpecularButton href={APP_SIGNUP_URL}>` (line 65) — "Start free trial instead"
- `<SpecularButton href="/">` (line 68) — "Back to home"

---

## SIGNUP REDIRECT PAGE (/signup)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/signup/page.tsx`

- **NavBar Component** — See NavBar inventory below
- `<SpecularButton href={APP_SIGNUP_URL}>` (line 55) — "Continue to signup" + ArrowRight icon
- `<Link href={...}>` (lines 62-67) — "Sign in →" (computed href: APP_SIGNUP_URL with /login)

---

## PRICING PAGE (/pricing)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/pricing/page.tsx`

- **NavBar Component** — See NavBar inventory below
- **PricingTiers Component:**
  - **File:** `app/pricing/pricing-tiers.tsx:145-154`
  - Three `<SpecularButton href={APP_SIGNUP_URL}>` elements (Free Trial, Pro, Unlimited tiers)
  - CTA text varies by tier: "Start free trial", "Start Pro", "Start Unlimited"

- **PricingFaq Component:**
  - **File:** `app/pricing/pricing-faq.tsx:60-80`
  - Radix `<Accordion.Root>` (collapsible FAQ items, no onClick required—Radix handles internally)
  - Accordion.Trigger uses `data-[state=open]` CSS binding, no explicit onClick handler

---

## ABOUT PAGE (/about)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/about/page.tsx`

- **NavBar Component** — See NavBar inventory below
- No interactive elements beyond navigation
- Content-only page with text and GradientText component

---

## CONTACT PAGE (/contact)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/contact/page.tsx`

Contact mailto links (all `<a href="mailto:...">` tags):
- line 45: `mailto:support@ashtechgroup.com` — "support@ashtechgroup.com"
- line 62: `mailto:sales@ashtechgroup.com` — "sales@ashtechgroup.com"
- line 79: `mailto:compliance@ashtechgroup.com` — "compliance@ashtechgroup.com"
- line 96: `mailto:security@ashtechgroup.com` — "security@ashtechgroup.com"
- line 114: `mailto:privacy@ashtechgroup.com` — "privacy@ashtechgroup.com"
- line 138: `mailto:legal@ashtechgroup.com` — "legal@ashtechgroup.com"

Additional link:
- line 123-127: `<a href="/privacy">` — "Privacy Policy" (inline link in Legal section)

---

## HIPAA PAGE (/hipaa)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/hipaa/page.tsx`

- **NavBar Component** — See NavBar inventory below
- No interactive elements; content-only compliance page

---

## SECURITY PAGE (/security)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/security/page.tsx`

- **NavBar Component** — See NavBar inventory below
- line 159: `<a href="/hipaa">` — "BAAs and operational controls" (inline link)
- No form elements; content-only page

---

## PRIVACY PAGE (/privacy)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/privacy/page.tsx`

- **NavBar Component** — See NavBar inventory below
- line 88: `<a href="/hipaa">` — "HIPAA page" (inline link)
- No form elements; content-only page

---

## TERMS PAGE (/terms)

**File:** `/opt/meddoc-pro/apps/marketing/src/app/terms/page.tsx`

- **NavBar Component** — See NavBar inventory below
- line 54: `<a href="/privacy">` — "Privacy Policy" (inline link in legal acceptance)
- line 139: `<a href="/privacy">` — "Privacy Policy" (inline link in termination section)
- No form elements; content-only page

---

## SHARED COMPONENTS

### NavBar (sticky header, all pages except home)
**File:** `components/nav-bar.tsx`

- **'use client'** component with scroll listener (no onClick handlers)
- `<Link href="/">` — Logo (line 43-54)
- Navigation links array (lines 57-67):
  - href="/#how" — "How it works"
  - href="/#features" — "Features"
  - href="/pricing" — "Pricing"
  - href="/about" — "About"
- `<SpecularButton href={APP_URL/login}>` (line 70-77) — "Sign in"
- `<SpecularButton href={APP_SIGNUP_URL}>` (line 79-81) — "Start free trial"

### SpecularButton Component
**File:** `components/specular-button.tsx`

Discriminated union type supporting:
- **Link mode** (`href` prop): renders as `next/link`
- **Button mode** (no href): renders as `<button>` with optional onClick handler

Variants: primary, secondary, ghost  
Sizes: sm, md, lg  
Optional sweep effect (specular hover animation)

No empty handlers detected. All onClick assignments are within button-mode only and properly typed.

### Footer (all pages)
**File:** `components/footer.tsx`

Grid layout with 4 link columns + brand section. All links properly categorized as internal (Link) or external (`<a>` with target="_blank"). See full inventory above in HOME PAGE section.

---

## FLAGGED ISSUES

### 1. Domain Routing Change — Old quillmd.com URLs
**Severity:** Medium  
**Locations:**
- `/opt/meddoc-pro/apps/marketing/src/lib/constants.ts:12-14`
  - APP_URL defaults to IP: `http://5.231.107.93:9020`
  - Requires NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL env override for production
  - Comment notes T-M2 context; pre-DNS state documented

**Action:** Verify DNS + HTTPS routing is set before production. Update env var in deployment config.

### 2. Placeholder Content — Draft Legal Pages
**Severity:** Low (documented)  
**Locations:**
- `/hipaa/page.tsx:29-38` — "[DRAFT — PENDING LEGAL REVIEW]" warning
- `/security/page.tsx:29-38` — Same warning
- `/privacy/page.tsx:27-37` — Same warning
- `/terms/page.tsx:29-39` — Same warning

**Action:** Replace with reviewed versions before paid customers onboard. Contact: legal@ashtechgroup.com

### 3. Empty onClick Handlers
**Finding:** None detected. All onClick assignments in SpecularButton are properly implemented.

### 4. Undefined Variable References
**Finding:** None detected. APP_URL and APP_SIGNUP_URL are consistently imported and used.

### 5. Commented-Out Handler Logic
**Finding:** None detected in click/submit handlers.

### 6. href="#" Links Without onClick Intercept
**Finding:** None detected. The "#demo" link in Hero (line 86) resolves to `id="demo"` on Demo component (valid anchor).

### 7. External Link to Possible 404 URLs
**Severity:** Low  
**Location:** Footer and components reference GitHub:
- `https://github.com/kasrarayat-cloud/MedDoc` (appears twice: Product "Docs" and Social "GitHub")

**Status:** Public repo exists; no 404 risk at this URL.

### 8. TODO/FIXME Comments in Handlers
**Finding:** None in handler functions themselves.

**File-level TODOs noted:**
- `app/pricing/pricing-tiers.tsx:12` — "Real pricing to be finalized after pilot"
- `security/page.tsx:138` — Sentry integration tracked in T-M15 audit (not a handler TODO)

---

## FORM ELEMENTS

**Finding:** No `<form>` tags detected in the marketing app.

All CTAs route to external signup service (APP_SIGNUP_URL) via `<a>` or `<Link>`.  
Pricing and FAQ use Radix primitives (Accordion) which manage internal state without form submission.

---

## SUMMARY METRICS

- **Total Pages:** 9
- **Total Interactive Buttons/Links:** ~60 (including duplicates across components)
- **Unique Routes:** /, /demo, /signup, /pricing, /about, /contact, /hipaa, /security, /privacy, /terms
- **External Links:** 1 (GitHub repo)
- **Mailto Links:** 7
- **Anchor Links (hash):** 6
- **Forms:** 0
- **Client Components with Handlers:** 2 (NavBar scroll, SpecularButton onClick in button-only mode)
- **Known Issues:** 1 (env-based routing, documented)

All interactive elements follow Next.js Link patterns for internal navigation and standard `<a>` tags for external URLs. No security or UX red flags detected.

