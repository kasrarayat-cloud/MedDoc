const WORD_DATE_TOKEN_RE = /yyyy|MMMM|dddd|MMM|ddd|yy|MM|dd|M|d/g;
const WORD_DATE_SEPARATOR_RE = /^[\s,./-]*$/u;
const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/u;

const ENGLISH_MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;
const ENGLISH_MONTHS_SHORT = ENGLISH_MONTHS_LONG.map((month) =>
  month.slice(0, 3),
);
const ENGLISH_WEEKDAYS_LONG = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
] as const;
const ENGLISH_WEEKDAYS_SHORT = ENGLISH_WEEKDAYS_LONG.map((weekday) =>
  weekday.slice(0, 3),
);

export interface WordDateFormatProfile {
  readonly format: string;
  readonly locale: "en-US" | null;
  readonly usesEnglishNames: boolean;
}

/**
 * Bounded Word date grammar used by compiler, renderer, and independent
 * readback. Word's full formatting language is intentionally not emulated.
 */
export function parseSupportedWordDateFormat(
  format: string | undefined,
  locale: string | undefined,
): WordDateFormatProfile | null {
  const candidate = format ?? "yyyy-MM-dd";
  if (!candidate || candidate.length > 64) return null;

  const tokens: string[] = [];
  let cursor = 0;
  for (const match of candidate.matchAll(WORD_DATE_TOKEN_RE)) {
    const index = match.index;
    if (index === undefined) return null;
    if (!WORD_DATE_SEPARATOR_RE.test(candidate.slice(cursor, index))) {
      return null;
    }
    tokens.push(match[0]);
    cursor = index + match[0].length;
  }
  if (!WORD_DATE_SEPARATOR_RE.test(candidate.slice(cursor))) return null;

  const yearTokens = tokens.filter(
    (token) => token === "yyyy" || token === "yy",
  );
  const monthTokens = tokens.filter((token) =>
    ["M", "MM", "MMM", "MMMM"].includes(token),
  );
  const dayTokens = tokens.filter((token) => token === "d" || token === "dd");
  const weekdayTokens = tokens.filter(
    (token) => token === "ddd" || token === "dddd",
  );
  if (
    tokens.length < 3 ||
    yearTokens.length !== 1 ||
    monthTokens.length !== 1 ||
    dayTokens.length !== 1 ||
    weekdayTokens.length > 1
  ) {
    return null;
  }

  const usesEnglishNames =
    monthTokens[0] === "MMM" ||
    monthTokens[0] === "MMMM" ||
    weekdayTokens.length === 1;
  if (locale !== undefined && locale !== "en-US") return null;
  if (usesEnglishNames && locale !== "en-US") return null;

  return Object.freeze({
    format: candidate,
    locale: locale === "en-US" ? "en-US" : null,
    usesEnglishNames,
  });
}

export function formatSupportedWordDate(
  value: string,
  profile: WordDateFormatProfile,
): string | null {
  const parsed = parseStrictIsoDate(value);
  if (!parsed) return null;
  const { year, month, day, weekday } = parsed;
  return profile.format.replace(WORD_DATE_TOKEN_RE, (token) => {
    switch (token) {
      case "yyyy":
        return String(year).padStart(4, "0");
      case "yy":
        return String(year).slice(-2).padStart(2, "0");
      case "MMMM":
        return ENGLISH_MONTHS_LONG[month - 1]!;
      case "MMM":
        return ENGLISH_MONTHS_SHORT[month - 1]!;
      case "MM":
        return String(month).padStart(2, "0");
      case "M":
        return String(month);
      case "dddd":
        return ENGLISH_WEEKDAYS_LONG[weekday]!;
      case "ddd":
        return ENGLISH_WEEKDAYS_SHORT[weekday]!;
      case "dd":
        return String(day).padStart(2, "0");
      case "d":
        return String(day);
      default:
        return token;
    }
  });
}

export function isStrictIsoDate(value: string): boolean {
  return parseStrictIsoDate(value) !== null;
}

function parseStrictIsoDate(
  value: string,
): { year: number; month: number; day: number; weekday: number } | null {
  const match = ISO_DATE_RE.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return { year, month, day, weekday: date.getUTCDay() };
}
