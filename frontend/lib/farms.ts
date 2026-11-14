import type { Crop, Field, Language, Season } from "./api/farms.ts";

export const colors: Record<string, string> = {
  apple: "#b97845",
  alfalfa: "#46856a",
  maize: "#c7a238",
  wheat: "#b28c50",
  beans: "#8d719d",
};
export const cropName = (crop: Crop | undefined, language: Language) =>
  crop?.[`name_${language}`] || "—";
export function seasonFor(field: Field, year: number): Season | undefined {
  return field.seasons.find((s) => s.year === year && s.is_main);
}
export function stageFor(
  season: Season | undefined,
  month: number,
  year: number,
): "sowing" | "harvest" | "growing" | "rest" | "unknown" {
  if (!season) return "unknown";
  const stamp = `${year}-${String(month).padStart(2, "0")}`;
  if (season.sowing_date?.startsWith(stamp)) return "sowing";
  if (season.harvest_date?.startsWith(stamp)) return "harvest";
  if (!season.sowing_date || !season.harvest_date) return "unknown";
  if (stamp > season.sowing_date.slice(0, 7) && stamp < season.harvest_date.slice(0, 7))
    return "growing";
  return "rest";
}
export function optionalNumber(value: string, integer = false): number | null {
  if (!value.trim()) return null;
  const number = Number(value.replace(",", "."));
  if (
    !Number.isFinite(number) ||
    Math.abs(number) > Number.MAX_SAFE_INTEGER ||
    (integer && !Number.isInteger(number))
  ) {
    throw new Error("invalidNumber");
  }
  return number;
}
export function planYear(fields: Field[]): number {
  const years = fields.flatMap((f) => f.seasons.map((s) => s.year));
  return years.length ? Math.max(...years) : new Date().getFullYear();
}

export function countUnit(count: number, language: Language, kind: "fields" | "cows"): string {
  if (language === "ky") return kind === "fields" ? "талаа" : "баш";
  if (language === "en") return kind === "cows" ? "head" : count === 1 ? "plot" : "plots";
  const form = new Intl.PluralRules("ru").select(count);
  if (kind === "fields")
    return form === "one" ? "участок" : form === "few" ? "участка" : "участков";
  return form === "one" ? "голова" : form === "few" ? "головы" : "голов";
}
