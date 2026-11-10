import type { Incident, Mode, Zone } from "./api";
import type { CellEvidence, Heatmap, HeatmapCell, HeatmapPeriod } from "./heatmap";
import type { RouteComparison, RouteOptions } from "./routes";

export type ChatLocation = { type: "Point"; coordinates: [number, number] };
export type ChatContext = {
  location?: ChatLocation;
  period?: HeatmapPeriod;
  start_time?: string;
  end_time?: string;
  cell_size?: number;
  route_ids?: string[];
};
export type ChatPlace = { label: string; point: ChatLocation; source: "gazetteer" | "OpenStreetMap" | "shared location" | "coordinates" };
export type ChatArea = {
  cell: HeatmapCell | null;
  radius_meters: number | null;
  security: CellEvidence;
  road_hazards: CellEvidence;
  window: Heatmap["window"];
  methodology: Heatmap["methodology"];
  generated_at: string;
  period: HeatmapPeriod;
  timezone: string;
  cell_size: number | null;
};
export type ChatResult = {
  conversation_id: string;
  mode: Mode;
  interpretation: "model" | "guided";
  answer: string;
  evidence: { kind: "incident" | "official_zone" | "route" | "area"; reference: string; label: string; source_url: string | null; as_of: string | null }[];
  unavailable_sources: string[];
  places: ChatPlace[];
  choices: ChatPlace[];
  area: ChatArea | null;
  incidents: (Incident & { distance_meters: number })[];
  incident_window: Heatmap["window"] | null;
  advisories: Zone[];
  route_options: RouteOptions | null;
  comparison: RouteComparison | null;
};
