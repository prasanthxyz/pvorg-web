/** The app's name wherever the user sees it (SPEC §4.2); `pvorg` stays the technical name. */
export const APP_NAME = "PP Video Organizer";

/** Browser tab title: "Filters – PP Video Organizer". */
export function setPageTitle(page: string): void {
  document.title = `${page} – ${APP_NAME}`;
}

/** "1 video", "3 videos" with locale number formatting (SPEC §2). */
export function counted(count: number, singular: string, plural = `${singular}s`): string {
  return `${count.toLocaleString()} ${count === 1 ? singular : plural}`;
}

/** "0:07", "12:34", "1:02:03" */
export function timecode(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0:00";
  const total = Math.floor(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
}

/** Case- and diacritic-insensitive comparison form. */
export function fold(text: string): string {
  return text.normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase();
}

export function matches(query: string, fields: string[]): boolean {
  const q = fold(query.trim());
  return !q || fields.some((field) => fold(field).includes(q));
}

/** "Jane Doe" — the humanized form of a filename token. */
export function humanize(token: string): string {
  return token
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function joinNames(names: string[]): string {
  return new Intl.ListFormat("en", { style: "long", type: "conjunction" }).format(names);
}
