import type { FieldworkDay, FieldworkLocation } from "$lib/types";

export const ACTIVITY_OPTIONS = [
  { key: "talajművelés", label: "Talajművelés", target: "talajművelésre" },
  { key: "vetés", label: "Vetés", target: "vetésre" },
  { key: "betakarítás", label: "Betakarítás", target: "betakarításra" },
  { key: "permetezés", label: "Permetezés", target: "permetezésre" },
] as const;

const STORAGE_KEY = "fieldwork.summaryActivities";
const DEFAULT_SELECTION: string[] = ["talajművelés"];
const WEEKDAYS_ON = ["vasárnap", "hétfőn", "kedden", "szerdán", "csütörtökön", "pénteken", "szombaton"];

export function loadSelection(): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null");
    if (Array.isArray(raw)) {
      const valid = ACTIVITY_OPTIONS.map((o) => o.key as string).filter((k) => raw.includes(k));
      return valid;
    }
  } catch {
    // sérült érték: alapértelmezés
  }
  return [...DEFAULT_SELECTION];
}

export function saveSelection(keys: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
}

const dayNumber = (iso: string) => Math.round(new Date(`${iso}T12:00:00`).getTime() / 86400000);
const dayName = (iso: string) => WEEKDAYS_ON[new Date(`${iso}T12:00:00`).getDay()];

function runs(dates: string[]): string[][] {
  const out: string[][] = [];
  for (const d of dates) {
    const last = out[out.length - 1];
    if (last && dayNumber(d) - dayNumber(last[last.length - 1]) === 1) last.push(d);
    else out.push([d]);
  }
  return out;
}

const formatRun = (r: string[]) => (r.length === 1 ? dayName(r[0]) : `${dayName(r[0])}–${dayName(r[r.length - 1])}`);

const daysWith = (days: FieldworkDay[], activity: string, status: string) =>
  days.filter((d) => d.assessments.find((a) => a.activity === activity)?.status === status).map((d) => d.date);

const favourable = (days: FieldworkDay[], activity: string) => daysWith(days, activity, "kedvező");

export function locationSummary(loc: FieldworkLocation, selected: string[]): string {
  return ACTIVITY_OPTIONS.filter((o) => selected.includes(o.key))
    .map((o) => {
      const r = runs(favourable(loc.days, o.key));
      const fair = runs(daysWith(loc.days, o.key, "megoldható"));
      const fairText = fair.length ? ` Megoldható, de nem kedvező: ${fair.map(formatRun).join(", ")}.` : "";
      if (!r.length) return `A héten nincs ${o.target} kedvező nap.${fairText}`;
      const best = r.reduce((a, b) => (b.length > a.length ? b : a));
      const others = r.filter((x) => x !== best);
      return (
        `${o.target[0].toUpperCase() + o.target.slice(1)} kedvező: ${formatRun(best)}.` +
        (others.length ? ` További kedvező nap(ok): ${others.map(formatRun).join(", ")}.` : "") +
        fairText
      );
    })
    .join(" ");
}

export function regionSummary(locations: FieldworkLocation[], selected: string[]): string {
  return ACTIVITY_OPTIONS.filter((o) => selected.includes(o.key))
    .map((o) => {
      const sets = locations.map((l) => new Set(favourable(l.days, o.key)));
      const common = favourable(locations[0].days, o.key).filter((d) => sets.every((s) => s.has(d)));
      if (!common.length) return `Nincs olyan nap, amikor a térség minden településén kedvező a ${o.label.toLowerCase()}.`;
      return `Az egész térségben kedvező ${o.target}: ${runs(common).map(formatRun).join(", ")}.`;
    })
    .join(" ");
}
