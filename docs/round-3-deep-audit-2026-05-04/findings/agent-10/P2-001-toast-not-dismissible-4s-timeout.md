---
id: A10-P2-001
severity: P2
domain: a11y / UX — toast notifications
title: Sonner toaster has no close button and 4s auto-dismiss — too short for screen-reader users and slow readers
---

## Issue

`apps/transcribe-md/src/components/toaster.tsx` configures Sonner with `closeButton={false}` and `duration={4000}` (4 seconds). The result:

1. Screen-reader users may have the toast announced (Sonner uses `role="status"` for non-error toasts and `role="alert"` for errors), but if they happen to have focus elsewhere or are mid-utterance, the toast disappears before they can navigate to it. There is no way to recall a toast.
2. Sighted users reading carefully — particularly older clinicians, the pre-pilot demographic — have 4 seconds to read multi-line bodies like the post-sign success toast: "Signed and exported. Some destinations failed. Check the visit page for details." Many descriptions are 8-15 words; 4 s is below the [WCAG 2.2.1 (Timing Adjustable)](https://www.w3.org/WAI/WCAG21/Understanding/timing-adjustable.html) Level A guidance.
3. WCAG 2.2.1 explicitly requires that timed messages be either > 20 s, dismissible, extendable, or marked as exceptions. None of those apply here — the toaster is configured against the spec.

## Evidence

`apps/transcribe-md/src/components/toaster.tsx:23-46`:

```tsx
<SonnerToaster
  position="bottom-right"
  theme="dark"
  richColors={false}
  closeButton={false}
  duration={4000}
  visibleToasts={4}
  ...
/>
```

Toast contents observed in code that are too long for 4 s:

- `apps/transcribe-md/src/app/visits/[id]/sign-and-send-modal.tsx:150` — "Email delivery not configured" with multi-line description listing which destinations succeeded.
- `apps/transcribe-md/src/app/visits/[id]/sign-and-send-modal.tsx:159` — "Other destinations also failed" with a `\n`-joined list. Multi-line in 4s is unreadable for almost everyone.
- `apps/transcribe-md/src/app/visits/[id]/visit-lifecycle-actions.tsx:357` — "Visit moved to trash" — short, fine, but not dismissible if the user wants to read it again.
- `apps/transcribe-md/src/app/check-email/check-email-resend.tsx:42` — "Could not resend / Please try again later." — needs longer dwell.

## Risk

- WCAG 2.2.1 Level A violation. Procurement gate.
- Slow-reader doctors miss critical signals about email delivery, which determines whether their just-signed SOAP actually went where they expected. There is **already** a P0-shape failure mode: a doctor signs, sees "Signed", and assumes email delivery worked when it silently failed. The 4 s window plus the lack of a close button means a partial-failure description scrolls off before they can read it.
- Adjacent: `closeButton={false}` means a screen-reader user has no programmatic way to acknowledge / clear a toast — `Esc` does not dismiss Sonner toasts in the default config.

## Recommended fix

In `apps/transcribe-md/src/components/toaster.tsx`:

1. Set `closeButton={true}`. Sonner's default styling fits the Linear V1 chrome; if not, add a `closeButton` className via `toastOptions.classNames`. Critical: position the close in the visual top-right and ensure it has a visible focus ring.
2. Bump `duration` to 8000 ms for non-error toasts. For error / warning toasts, set per-call `duration: Infinity` so they persist until dismissed (Sonner allows per-call override). Update `apps/transcribe-md/src/app/visits/[id]/sign-and-send-modal.tsx:150 / 159 / 187 / 195` to pass `duration: Infinity` for the partial-failure / setup-error / browser-blocked branches — those are the cases where a user-actionable signal is lost on auto-dismiss.
3. Verify that Sonner's `Esc` shortcut clears the focused / topmost toast (it should once `closeButton` is enabled).

Total effort: 1 file + 4-6 call-site annotations. Removes a WCAG 2.2.1 violation and a known UX failure mode from the email-delivery flow.
