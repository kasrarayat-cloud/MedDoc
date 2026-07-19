/**
 * Server-side data export rollout flag shared by the settings page and route.
 * Route modules may only export Next.js route handlers and route metadata, so
 * keep this policy helper outside the route boundary.
 */
export function isDataExportEnabled(): boolean {
  const raw = process.env.ENABLE_DATA_EXPORT?.trim().toLowerCase();
  // Preserve the established default: absence or unset keeps export enabled.
  return raw !== 'false' && raw !== '0';
}
