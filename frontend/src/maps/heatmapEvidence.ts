import type { HeatmapPeriod, RiskBand, RiskDimension } from "../types/heatmap";

export const riskBands: Record<RiskBand, { label: string; color: string }> = {
  green: { label: "Lower observed risk", color: "#16a34a" },
  yellow: { label: "Moderate reported risk", color: "#f5ac16" },
  red: { label: "Elevated reported risk", color: "#dc2626" },
  grey: { label: "Insufficient information", color: "#8d969d" },
};
export const periods: Record<HeatmapPeriod, string> = {
  full_day: "Full day",
  morning: "Morning · 06:00–12:00",
  afternoon: "Afternoon · 12:00–17:00",
  evening: "Evening · 17:00–22:00",
  night: "Night · 22:00–06:00",
};
export const dimensions: Record<RiskDimension, string> = { security: "Community safety", road_hazards: "Road hazards" };

export function heatmapTime(value: string, timezone: string, timeOnly = false) {
  return new Intl.DateTimeFormat("en-PK", timeOnly
    ? { timeStyle: "medium", timeZone: timezone }
    : { dateStyle: "medium", timeStyle: "short", timeZone: timezone }).format(new Date(value));
}
