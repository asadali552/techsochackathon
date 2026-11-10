import type { Feature, Polygon } from "geojson";

import type { Category, Mode } from "./api";

export type RiskBand = "green" | "yellow" | "red" | "grey";
export type RiskDimension = "security" | "road_hazards";
export type HeatmapPeriod = "full_day" | "morning" | "afternoon" | "evening" | "night";
export type CellEvidence = {
  band: RiskBand;
  score: number | null;
  report_count: number;
  category_counts: Partial<Record<Category, number>>;
  latest_report_at: string | null;
  coverage: "sufficient" | "limited" | "unavailable";
};
export type CellProperties = Record<RiskDimension, CellEvidence> & { is_demo: boolean; scoring_version: string };
export type HeatmapCell = Feature<Polygon, CellProperties> & { id: string };
export type Heatmap = {
  cells: { type: "FeatureCollection"; features: HeatmapCell[] };
  window: { from: string; to: string };
  period: HeatmapPeriod;
  local_hour: number | null;
  timezone: string;
  generated_at: string;
  cell_size: number;
  mode: Mode;
  scoring_version: string;
  methodology: { minimum_reports: number; moderate_threshold: number; elevated_threshold: number; half_life_days: number };
};
