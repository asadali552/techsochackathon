# API contracts

Base path `/api`. Health, incidents, official zones, heatmap, private incident analysis, routes, and AI chat are implemented. The standalone safety-area endpoint remains a future contract. Chat exposes area evidence through its tool layer.

Success is `{"data": <result>, "error": null}`. Failure is `{"data": null, "error": {"code": "validation_error", "message": "Invalid request", "details": [{"field": "location", "message": "Invalid point"}]}}`. Error details may be omitted. Phase 1 uses 401 `unauthorized`, 403 `forbidden`, 404 `not_found`, 422 `validation_error`, 500 `database_error`, and 503 `auth_unavailable` or `database_unavailable` as applicable. Never include private input or upstream credentials in errors.

Dates are ISO 8601 UTC strings ending in `Z`. IDs are UUID strings unless marked opaque. Coordinates are WGS84 GeoJSON `[longitude, latitude]`. A point is `{"type":"Point","coordinates":[71.47,30.197]}`. Phase 1 bounding boxes use the four query fields `min_lat`, `max_lat`, `min_lng`, and `max_lng`. Provide all four or omit all four. Minimums must be smaller than maximums. The heatmap also accepts a comma-separated `west,south,east,north` bounding box. Responses return GeoJSON geometries as JSON objects. Temporal windows include their start and exclude their end.

Public evidence endpoints accept optional `mode=live|demo` (default `live`). Demo mode uses explicitly labeled fictional reports and zones. Live queries exclude demos. Writes create live reports only. Required inputs are marked below. Authenticated endpoints require `Authorization: Bearer <Supabase access token>`. The API derives ownership from the verified token.

## GET /api/health

Public. No inputs. Returns 200 with `{"data":{"status":"ok"},"error":null}`. This is a process liveness check.

## GET /api/ready

Public. No inputs. Returns the same success envelope as health after a database connection, PostGIS query, and schema presence check. Returns 503 when persistence is unavailable. Check role permissions and RLS separately during deployment.

## POST /api/incidents

Registered Supabase account required. The body accepts only `category`, `description` (trimmed, 1–2,000 characters), numeric `latitude` and `longitude`, and `occurred_at` (timezone-aware ISO 8601 at or before submission). Valid categories are `robbery`, `theft`, `harassment`, `suspicious_activity`, `road_accident`, `unsafe_road`, `poor_lighting`, `landslide`, `road_closure`, and `other`.

Returns 201 with a `PublicIncident` and a null `public_summary`. Defaults are `pending`, `community`, severity 1, and credibility 0. The bearer token determines ownership. Extra fields, including moderation or identity overrides, return 422. Each account can save ten reports per rolling hour. A subsequent submission returns 429 with `incident_rate_limited`.

## GET /api/incidents

Public. Optional bounding-box fields, `category`, `verification_status` (`pending|corroborated|verified|rejected`), `start_time`, `end_time`, `limit` (1–100, default 50), `offset` (0–10,000, default 0), and `mode`. Time filters are independent. Sort by occurrence time then ID, descending. Returns `{items: PublicIncident[], limit, offset, mode}`. Rejected records never appear, even when that status is requested.

`PublicIncident` has `id`, `category`, `public_summary` (redacted string or null on create), `location` (GeoJSON Point rounded to three decimals), `occurred_at`, `created_at`, `severity` (1–5 or null for older data), `verification_status` (`pending|corroborated|verified`), `source` (`community|demo`), and `is_demo` (boolean). Public reads require a reviewed summary. A reviewed pending record still represents an unverified report.

The map queries its current bounding box with a page limit of 100. The search box filters that response locally. A page at the limit prompts the user to zoom in or narrow their filters.

## GET /api/incidents/nearby

Public. Requires numeric `latitude` and `longitude`. Optional `radius_meters` (greater than 0 through 5,000, default 500), `limit` (1–100, default 50), and `mode`. Returns `{items, mode}`. Items extend `PublicIncident` with `distance_meters`, sorted nearest first. Distances and filters use the same generalized point shown in responses.

## GET /api/incidents/{incident_id}

Public. Accepts a UUID and optional `mode`. Returns one `PublicIncident` or 404 if absent, unreviewed, rejected, or outside the selected mode.

## GET /api/official-zones

Public. Accepts optional bounding-box fields, `active_only` (boolean, default true), `at` (timestamp, default now), and `mode`. Effective windows include the start and exclude the end. Revoked zones are excluded even with `active_only=false`. An empty result indicates no matching stored records.

Returns a GeoJSON FeatureCollection with a top-level `mode`. Each Feature has a UUID `id`, WGS84 MultiPolygon `geometry`, and properties `name`, `description`, `designation` (`restricted|unsafe_advisory|caution|road_closure`), `issuing_authority`, `source_url`, `source_reference`, `effective_from`, `effective_until`, `last_verified_at`, and `is_demo`. Fictional zones have no government source URL.

## GET /api/heatmap

Public. Provide all four viewport bounds or `bbox=west,south,east,north`. Optional `from` and `to` set a half-open UTC window (default 30 days ending now, maximum 90 days). Optional `period` is `full_day`, `morning` (06:00–12:00), `afternoon` (12:00–17:00), `evening` (17:00–22:00), or `night` (22:00–06:00). Periods recur within the date range in the configured timezone (default Asia/Karachi). Use `local_hour` (0–23) with `full_day` for one recurring hour. Optional `mode` defaults to live.

Optional `cell_size` is 500, 750, 1000, 1500, or 2500 nominal Web Mercator metres. When omitted, the server starts at the configured default (750) and coarsens the grid as needed. Requests that exceed 500 cells at the selected resolution return 422 `viewport_too_large`.

The result contains `cells` (GeoJSON FeatureCollection), `window: {from, to}`, `period`, `local_hour`, `timezone`, `generated_at`, `cell_size`, `mode`, `scoring_version`, and `methodology` (minimum reports, moderate and elevated thresholds, and decay half-life in days). Each feature has a stable string ID `size:i:j`, a WGS84 Polygon, and `properties: {security: Evidence, road_hazards: Evidence, is_demo, scoring_version}`.

`Evidence` has `band` (`green|yellow|red|grey`), `score` (integer 0–100 or null), `report_count`, `category_counts`, `latest_report_at`, and `coverage` (`sufficient|limited|unavailable`). An empty area still returns grey polygons with null scores. The feed uses only public corroborated and verified incidents. Review affects the next request. The dashboard provides explicit refresh and displays the response timestamp. Advisory overlays use the separate official-zones API. [Scoring methodology](ARCHITECTURE.md#phase-3-heatmap-scoring)

## GET /api/safety/area

Public. Required query `longitude` and `latitude` (numbers). Optional `radius_m` (integer 100–5,000, default 500), `from`, `to` (default last 30 days through now), `local_hour` (same as heatmap), and `mode`. Returns `{security: Evidence, road_hazards: Evidence, official_zones: ZoneFeature[], official_coverage: "available"|"unavailable", window: {from, to}, local_hour: integer|null, mode, scoring_version: string}`.

## GET /api/routes

Public. Required query `origin` and `destination` (each a comma-separated longitude,latitude pair, 25 m to 500 km apart). Optional `departure_at` (UTC timestamp within 90 days of now, default now) and `alternatives` (integer 1–3, default 3). Returns `{routes: Route[], departure_at, provider: string}`. An empty or single-route response is valid. Provider unavailability returns 503. Departure affects evidence windows. OSRM supplies the distance and estimated driving time.

`Route` has `id` (opaque, short-lived server reference), `geometry` (GeoJSON LineString), `distance_m` (nonnegative number), and `duration_s` (nonnegative number). The reference binds the provider result to its departure and expires after 15 minutes.

## POST /api/routes/compare

Public. Required body `route_ids` (array of one to three distinct opaque IDs returned by the routes endpoint). Optional `preference` (`balanced|shortest|fastest|fewer_reported_incidents`, default `balanced`) and `mode`. The IDs must belong to one trip. Unknown, expired, or mixed-trip references return 404. Returns `{routes: ComparedRoute[], preference, mode, scoring_version: string, corridor_m, evidence_window_days, departure_at}`. Both routing endpoints return `Cache-Control: no-store` on success.

`ComparedRoute` extends `Route` with `security: Evidence`, `road_hazards: Evidence`, `official_zones: ZoneFeature[]`, `official_coverage` (`available|unavailable`), and `trade_offs: string[]`. Evidence uses the rounded public points of eligible reports in the selected mode. Each dimension has its own sample requirement. Official zones match by geometry and trip time window. `official_coverage: unavailable` means there were no stored matches and coverage is unconfirmed. Known restrictions remain visible in all orderings. [Route scoring](ARCHITECTURE.md#phase-5-journey-comparison)

## POST /api/ai/incidents/{incident_id}/analyze

Bearer authentication and an incident UUID are required. The report owner or a configured moderator may start or retry analysis. No request body is used. The first request runs a bounded analysis and returns the stored result. A competing request returns 202 with `processing`. Completed analyses are reused. A rejected report returns 409 if it has no completed analysis. Unauthorized and missing incidents both return 404.

## GET /api/ai/incidents/{incident_id}/analysis

Uses the same authorization and returns the current analysis state with `Cache-Control: no-store`. The data includes `incident_id`, `status` (`not_started|processing|completed|failed|unavailable`), current `review_status`, `suggestion`, `moderation`, `provider`, `model`, `attempts`, `started_at`, `completed_at`, and `processing_error`. Provider failures are stored result states with sanitized codes. A two-minute processing lease lets a later POST reclaim an interrupted job.

`suggestion` includes category, provisional severity, normalized summary, classification confidence, and `requires_review=true`. The owner projection has `moderation=null`. Moderator responses also include verbatim extracted mentions and entities, private candidate incident IDs with reason codes, and an evidence assessment recorded at processing time. The response excludes reporter account IDs, evidence URLs, and exact submitted coordinates.

## POST /api/ai/chat

Live mode requires a registered Supabase bearer token. Unauthenticated demo mode uses fictional evidence and defaults to guided interpretation. Deployments can explicitly opt in to Gemini interpretation for demo requests. Required body `message` (1–2,000 characters). Optional `conversation_id` (returned by the first request), `mode`, `location` (explicitly shared GeoJSON Point), `period`, `start_time`, `end_time`, `cell_size`, and up to three distinct `route_ids` from a planner trip. Date and grid fields preserve selected heatmap context. Nearby incident search also accepts those date bounds, up to 90 days.

The result contains `conversation_id`, `mode`, `interpretation` (`model|guided`), `answer`, resolved `places`, ambiguous `choices`, typed `area`, `incidents` and `incident_window`, `advisories`, `route_options`, `comparison`, `evidence`, and `unavailable_sources`. A numbered reply selects a place from the last ambiguous response. `area.cell` is present for exact heatmap explanations and `area.radius_meters` is present for radius evidence. References include `kind` (`incident|official_zone|route|area`), `reference`, `label`, `source_url`, and `as_of`. Evidence may be partial. Provider errors leave available results intact. A missing, expired, or unauthorized conversation returns 404. A concurrent turn on the same conversation returns 409. Rate limits return 429. Successful responses use `Cache-Control: no-store`.

## POST /api/ai/chat/clear

Uses the same authentication and mode rules. Send the `conversation_id` and `mode`. The server deletes the conversation state and returns `{cleared: true}`. Expired or inaccessible conversations return 404.
