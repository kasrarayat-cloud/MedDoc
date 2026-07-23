// Minimal HTML entity escaping for user-authored free text that lands in an
// email/HTML body. Shared so email.ts and admin-notifications.ts don't drift.
export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
