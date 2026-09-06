// ============================================================================
// /settings/members — ADMIN-1's route segment.
// ----------------------------------------------------------------------------
// The same shape `/settings/note-format` uses, and for the same reason: render
// the settings page with the panel preselected rather than redirect, so the URL
// the doctor was given is the URL they stay on.
//
// ⚠️ IT MUST WORK ON BOTH SETTINGS BRANCHES, and they are not the same shape:
//   · `isSkinBeta()` ON (production) — the C3 rail keeps every panel mounted
//     with `hidden`, so landing here must PRESELECT or the doctor gets Profile
//     and no sign the link meant anything.
//   · flag OFF (the image the required chromium E2E gate builds) — the legacy
//     long-scroll stack, where `<Section id="members">` is simply present.
// One prop satisfies both.
// ============================================================================

import type { Metadata } from 'next';

import SettingsPage from '../page';

export const metadata: Metadata = { title: 'Members · Settings' };

export default async function MembersSettingsPage() {
  return <SettingsPage initialSection="members" />;
}
