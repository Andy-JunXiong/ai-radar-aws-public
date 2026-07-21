const REPLACEMENTS: Array<[RegExp, string]> = [
  [/â€”/g, "—"],
  [/â€“/g, "–"],
  [/â€˜|â€™/g, "'"],
  [/â€œ|â€�/g, '"'],
  [/â€¦/g, "..."],
  [/\uFFFD/g, ""],
];

export function cleanDisplayText(value: unknown): string {
  const text = String(value ?? "").trim();
  if (!text) return "";

  let cleaned = text;
  for (const [pattern, replacement] of REPLACEMENTS) {
    cleaned = cleaned.replace(pattern, replacement);
  }

  return cleaned.replace(/\s{2,}/g, " ").trim();
}

export function cleanDisplayList(values: unknown[] | undefined | null): string[] {
  if (!Array.isArray(values)) return [];
  return values.map((value) => cleanDisplayText(value)).filter(Boolean);
}
