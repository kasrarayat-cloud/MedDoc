---
id: A10-P2-005
severity: P2
domain: UX — form validation
title: Login + signup forms validate only on submit — no inline (onBlur) feedback for email format, password strength
---

## Issue

The auth forms use Next 15's `useActionState` + Zod server-action validation. The validation cycle is:

1. User fills in fields.
2. User clicks submit.
3. Server action runs, returns errors keyed by field, including the entered values for re-render.
4. The form re-renders with `<AuthFieldError>` components below each field.

This means a user with a typo in their email (e.g. `you@gmail.con`) or a too-short password gets no feedback until they press the button and wait for the round-trip. For a brand-new user signing up — the highest-conversion-pressure moment in the entire product — this round-trip is friction. For a doctor on a slow waiting-room WiFi, it's a 300-700 ms re-render with potential re-blur of the field.

The signup form **does** have inline confirm-password validation (good). It does **not** have inline:
- Email format checking (Zod email validator at submit only).
- Password strength preview (the spec is "10 chars + upper + lower + digit"; user types and discovers at submit).
- Name presence / length.
- Acceptance of terms (only revealed on submit).

The login form has no inline feedback at all.

## Evidence

`apps/transcribe-md/src/app/login/login-form.tsx:108-135` — no onBlur / onChange validation. Inputs only sync to the form's submit handler.

`apps/transcribe-md/src/app/signup/signup-form.tsx:60-82` — only `confirmPassword` is checked client-side; everything else falls through to `signupAction`.

`apps/transcribe-md/src/actions/auth.ts:333` — duplicate-email error returns "An account with this email exists. Sign in instead." This is excellent copy, but it surfaces only after the network round-trip.

## Risk

- Onboarding click count target is < 10. Adding a re-submit cycle for any common typo (~10% baseline rate for typed emails) pushes the median user to 12-14 effective clicks.
- Frustration on slow networks (3G simulation pushed this to a 1-2s delay).
- Doctors abandoning signup because "the form yelled at me twice" is not hypothetical — Round 1 user-research notes (see docs/qa-sweep-* if available) flagged this pattern.

## Recommended fix

In `apps/transcribe-md/src/app/login/login-form.tsx` and `signup-form.tsx`, add lightweight onBlur-only client validation alongside the server-side Zod gate. Keep the server-side as the authoritative gate — client is a UX hint:

```tsx
const [emailError, setEmailError] = useState<string | undefined>();

<input
  id="email"
  ...
  onBlur={(e) => {
    const v = e.target.value.trim();
    if (v && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)) {
      setEmailError("Check the email format — looks like a typo.");
    } else {
      setEmailError(undefined);
    }
  }}
  onFocus={() => setEmailError(undefined)} // clear on re-edit
/>
<AuthFieldError message={errors.email ?? emailError} />
```

For the signup password field, render a tiny live strength meter (the spec is already documented in the help text below the field — extend it to highlight which requirements are met):

```tsx
const reqs = [
  { ok: password.length >= 10, label: "10+ characters" },
  { ok: /[a-z]/.test(password) && /[A-Z]/.test(password), label: "Mixed case" },
  { ok: /\d/.test(password), label: "A digit" },
];
// render as 3 mono dots: ● (sage) for ok, ○ (text-3) otherwise
```

Estimated effort: ~30 lines per form. No server-action changes needed — server stays authoritative; client adds preview.

Bonus: surface acceptance-of-terms inline (the checkbox already exists; add a `aria-invalid` + red border treatment when blurred-and-not-checked).
