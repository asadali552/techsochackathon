import type { Mode, Zone } from "./api";
import type { CellEvidence } from "./heatmap";

export type Endpoint = "origin" | "destination";
export type RouteLine = {
  id: string;
  geometry: { type: "LineString"; coordinates: [number, number][] };
  distance_m: number;
  duration_s: number;
};
export type RouteOptions = { routes: RouteLine[]; departure_at: string; provider: string };
export type ComparedRoute = RouteLine & {
  security: CellEvidence;
  road_hazards: CellEvidence;
  official_zones: Zone[];
  official_coverage: "available" | "unavailable";
  trade_offs: string[];
};
export type RouteComparison = {
  routes: ComparedRoute[];
  mode: Mode;
  preference: "balanced" | "shortest" | "fastest" | "fewer_reported_incidents";
  scoring_version: string;
  corridor_m: number;
  evidence_window_days: number;
  departure_at: string;
};
