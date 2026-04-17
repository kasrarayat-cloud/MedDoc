import { redirect } from 'next/navigation';

// Root is a shortcut to the visit list. Auth-gating happens at the
// (dashboard) route group layout, so unauthenticated users hitting /
// will bounce to MedDoc Pro /login via the redirect chain there.
export default function ScribeHome() {
  redirect('/visits');
}
