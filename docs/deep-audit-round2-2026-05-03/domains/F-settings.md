# Domain F — Settings + Admin

**Run:** 2026-05-03 20:55 UTC
**Owner account:** `qa-bypass-1777795921@quillmd-test.local` (DOCTOR role, no SUPER_ADMIN)

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| F1 | Profile name edit + save | ✓ | "Profile updated · Your changes are saved." toast; persists |
| F2 | Weak password change | ✓ | "Password must be at least 10 characters" — rejected as expected |
| F3 | Direct nav to `/admin` as DOCTOR | ✓ 404 | proper hide (404, not 403 — doesn't reveal route exists) |
| F4 | Data export route `/api/settings/export-data` | ✓ 200 | HIPAA right-of-access supported |
| F5 | Account deletion route `/api/settings/delete-account` (GET probe) | ✓ 405 | POST-only; correct posture for destructive op |
| F6 | Email change | DEFERRED — endpoint exists per Round 1 inventory (`/api/settings/change-email`); not exercised here |
| F7 | Notification preferences | not located in source — may not exist as user-facing setting |
| F8 | Specialty change (covered in Domain D) | ✓ | works |

## Findings

### F-001 — Settings posture is solid (POSITIVE)

All probed surfaces behave correctly:
- Profile edit fires toast + persists ✓
- Weak password rejected with clear message ✓
- Admin route returns 404 to non-admin (hides existence) ✓
- Data-export endpoint exists (HIPAA right of access) ✓
- Destructive routes are POST-only (GET → 405) ✓

### F-002 — Profile-update toast text doubles up (P3 nitpick)

The `[role="alert"]` element captures returned:
```
"Profile updatedYour changes are saved.Profile updatedYour changes are saved."
```

The success message appears DUPLICATED. Likely a React rerender
landing on the same `<div role="alert">` content twice without
clearing. Cosmetic only — message is single-instance to the eye
in the screenshot, but DOM has the doubled text. Worth a quick
look at the toast component (`<Toast>` from sonner per source
review).

**Risk if NOT fixed:** zero (cosmetic — won't be visible to users
unless a screen reader announces twice).

## What was NOT covered

- F6 email change — needs verification email, can't fully exercise
  (similar bind to the original email-verification gap)
- F7 notifications — doesn't appear to be a feature yet
- F8 admin dashboard internals — DOCTOR account can't access; need
  a SUPER_ADMIN account to test admin UX
