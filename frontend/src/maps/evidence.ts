import type { Category, Designation, Verification } from "../types/api";

export const categoryLabels: Record<Category, string> = {
  robbery: "Robbery",
  theft: "Theft",
  harassment: "Harassment",
  suspicious_activity: "Suspicious activity",
  road_accident: "Road accident",
  unsafe_road: "Unsafe road",
  poor_lighting: "Poor lighting",
  landslide: "Landslide",
  road_closure: "Road closure",
  other: "Other report",
};

export const verificationLabels: Record<Verification, string> = {
  pending: "Pending verification",
  corroborated: "Corroborated",
  verified: "Verified",
};

export const markerGroups = {
  security: { label: "Robbery or theft", color: "#aa3654", glyph: "◆" },
  harassment: { label: "Harassment", color: "#7545ab", glyph: "!" },
  suspicious: { label: "Suspicious activity", color: "#98345f", glyph: "?" },
  accident: { label: "Road accident", color: "#a74f24", glyph: "✚" },
  hazard: { label: "Road hazard", color: "#a67718", glyph: "▲" },
  other: { label: "Other report", color: "#476c99", glyph: "•" },
};

const groupByCategory: Record<Category, keyof typeof markerGroups> = {
  robbery: "security",
  theft: "security",
  harassment: "harassment",
  suspicious_activity: "suspicious",
  road_accident: "accident",
  unsafe_road: "hazard",
  poor_lighting: "hazard",
  landslide: "hazard",
  road_closure: "hazard",
  other: "other",
};

export function incidentStyle(category: Category) {
  return markerGroups[groupByCategory[category]];
}

export const designations: Record<Designation, { label: string; color: string; dash?: string }> = {
  restricted: { label: "Restricted", color: "#bf244a" },
  unsafe_advisory: { label: "Unsafe advisory", color: "#b94722" },
  caution: { label: "Caution", color: "#a67718" },
  road_closure: { label: "Road closure", color: "#b24d22", dash: "7 5" },
};

const multanTime = new Intl.DateTimeFormat("en-PK", {
  dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Karachi",
});

export function formatMultanTime(value: string) {
  return `${multanTime.format(new Date(value))} PKT`;
}
