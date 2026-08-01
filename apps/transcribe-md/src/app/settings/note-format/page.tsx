// ============================================================================
// /settings/note-format — the route two live links already pointed at.
// ----------------------------------------------------------------------------
// ⚠️ THIS SEGMENT DID NOT EXIST, AND TWO SHIPPED SURFACES LINKED TO IT.
//
//   · `components/rounds/board-chrome.tsx:133` — the Rounds nav's "Templates"
//   · `lib/email.ts:371` — the certified-template email's "manage" URL, which
//     goes to a REAL DOCTOR'S INBOX and is pinned by
//     `template-certified-email.test.ts:44-45`
//
// Both returned 404. The directory has existed all along holding this feature's
// COMPONENTS (`note-format-manager.tsx` and friends), which is exactly why the
// gap was easy to miss: `ls` shows a folder, Next sees no `page.tsx` and serves
// nothing.
//
// FIXED HERE RATHER THAN AT THE LINKS, deliberately. An email that has already
// been delivered cannot be rewritten, so changing `email.ts` would fix only
// future sends and leave every message already in a doctor's inbox pointing at
// a 404. The route is the side that can be fixed retroactively.
//
// ⚠️ IT MUST WORK ON BOTH SETTINGS BRANCHES, and they are not the same shape.
// `settings/page.tsx` forks on `isSkinBeta()`:
//   · flag ON (production) — the C3 rail, whose seven panels all stay mounted
//     with `hidden`; landing here must PRESELECT the panel or the doctor gets
//     the rail with Profile open and no sign the link meant anything.
//   · flag OFF (the image the required chromium E2E gate builds, e2e.yml:97) —
//     the legacy long-scroll stack, where the section is simply present as
//     `<Section id="note-format">`. Nothing to preselect; it renders.
// Rendering the page component with a prop satisfies both without duplicating
// ~790 lines of server component, and without a redirect — the URL the doctor
// clicked is the URL they stay on.
// ============================================================================

import type { Metadata } from 'next';

import SettingsPage from '../page';

export const metadata: Metadata = { title: 'Note format · Settings' };

export default async function NoteFormatSettingsPage() {
  return <SettingsPage initialSection="note-format" />;
}
