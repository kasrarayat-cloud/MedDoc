// ============================================================================
// Date/time helpers
// ----------------------------------------------------------------------------
// The scheduling forms take a date picker (YYYY-MM-DD) + a time picker (HH:MM)
// and must persist a moment in time that round-trips correctly regardless of
// where the server lives. The old code did `new Date(\`${date}T${time}\`)` on
// the SERVER, which parses in the *server's* local TZ — on a UTC VPS a user
// who picks "10:00 AM" from New York ended up storing 10:00 UTC, which then
// renders as 06:00 EDT when the browser reads it back via `getHours()`. The
// appointment effectively teleports across timezones between write and read.
//
// Fix: construct the Date on the CLIENT using the browser's local TZ
// (`new Date(y, m, d, hh, mm)` is local-TZ by spec), then serialize to ISO
// UTC before sending to the server. The server just stores the instant.
// Round-trip: user picks 10:00 → browser encodes as local-10:00 → ISO UTC →
// DB stores the exact moment → browser reads and `.getHours()` returns 10.
// ============================================================================

/**
 * Convert an HTML `<input type="date">` value + `<input type="time">` value
 * to an ISO-8601 UTC timestamp string, interpreting the inputs in the
 * browser's local timezone.
 *
 * Throws if either string is malformed — the caller's form validation
 * should have caught that already.
 */
export function localDateTimeToISO(dateStr: string, timeStr: string): string {
  const dateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateStr);
  const timeMatch = /^(\d{2}):(\d{2})$/.exec(timeStr);
  if (!dateMatch) throw new Error(`Invalid date format: ${dateStr}`);
  if (!timeMatch) throw new Error(`Invalid time format: ${timeStr}`);

  const [, y, m, d] = dateMatch;
  const [, hh, mm] = timeMatch;

  // `new Date(year, monthIndex, day, hour, minute)` is local-TZ by spec.
  // `.toISOString()` converts to UTC.
  const local = new Date(
    Number(y),
    Number(m) - 1,
    Number(d),
    Number(hh),
    Number(mm),
    0,
    0
  );
  if (Number.isNaN(local.getTime())) {
    throw new Error(`Invalid date/time combination: ${dateStr} ${timeStr}`);
  }
  return local.toISOString();
}
