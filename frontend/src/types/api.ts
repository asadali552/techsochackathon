export type ApiSuccess<T> = { data: T; error: null };
export type ApiFailure = { data: null; error: { code: string; message: string; details?: { field: string; message: string }[] } };
export type Health = { status: "ok" };
export type Mode = "live" | "demo";
export type Bounds = { min_lat: number; max_lat: number; min_lng: number; max_lng: number };
export type Coordinate = { latitude: number; longitude: number };

export type Category =
  | "robbery" | "theft" | "harassment" | "suspicious_activity" | "road_accident"
  | "unsafe_road" | "poor_lighting" | "landslide" | "road_closure" | "other";
export type Verification = "pending" | "corroborated" | "verified";
export type IncidentFilters = {
  category?: Category;
  verification_status?: Verification;
  start_time?: string;
  end_time?: string;
};
export type Incident = {
  id: string;
  category: Category;
  public_summary: string | null;
  location: { type: "Point"; coordinates: [number, number] };
  occurred_at: string;
  created_at: string;
  severity: number | null;
  verification_status: Verification;
  source: "community" | "demo";
  is_demo: boolean;
};
export type IncidentPage = { items: Incident[]; limit: number; offset: number; mode: Mode };
export type IncidentDraft = Coordinate & { category: Category; description: string; occurred_at: string };

export type Designation = "restricted" | "unsafe_advisory" | "caution" | "road_closure";
export type Zone = {
  type: "Feature";
  id: string;
  geometry: { type: "MultiPolygon"; coordinates: [number, number][][][] };
  properties: {
    name: string;
    description: string;
    designation: Designation;
    issuing_authority: string;
    source_url: string | null;
    source_reference: string | null;
    effective_from: string;
    effective_until: string | null;
    last_verified_at: string;
    is_demo: boolean;
  };
};
export type ZoneCollection = { type: "FeatureCollection"; features: Zone[]; mode: Mode };
export type Selection = { kind: "incident" | "zone"; id: string };

export type IncidentAnalysis = {
  incident_id: string;
  status: "not_started" | "processing" | "completed" | "failed" | "unavailable";
  review_status: Verification | "rejected";
  suggestion: {
    category: Category;
    severity: number;
    summary: string;
    classification_confidence: number;
    requires_review: true;
  } | null;
  processing_error: string | null;
};
