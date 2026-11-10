# Database design

| Table | Ownership and purpose |
| --- | --- |
| `profiles` | Optional display name and timestamps. The ID references `auth.users` and cascades on deletion. The API creates the profile on first report. |
| `incidents` | Private description, WGS84 coordinates, report time, moderation status, optional evidence URL, provenance, and demo flag. Reporter references the profile and is cleared on account deletion. |
| `incident_ai_analysis` | One private analysis record per incident. Stores its current status, run ID, attempt count, model, timing, sanitized error, and validated JSON result. Deleting an incident cascades to its analysis. |
| `official_zones` | Multipolygon, designation, authority, source reference, effective window, verification time, and revocation. Live entries require provenance. Fictional entries require an explicit demo label and have no source URL. |

Incident latitude and longitude are validated and drive a stored PostGIS geography point. A second generated geography point rounds to three decimal places. Public filters and distances use this rounded point to avoid revealing the original coordinates through repeated queries. GiST indexes support meter-based searches and geometry bounding boxes. WGS84 coordinates are longitude first in SQL and GeoJSON.

New reports default to pending with severity 1 and credibility 0. Pending reports enter public results only after a reviewer writes a redacted summary. Moderators can corroborate, verify, or reject reports under the process in [Safety and trust](SAFETY_AND_TRUST.md). Metadata, evidence URLs, exact coordinates, and reporter IDs stay private.

Raw tables use RLS and column grants. Public reads expose only reviewed live projections. Registered users submit through the authenticated FastAPI endpoint, which serializes submissions per account and applies the rolling rate limit. Status changes and zone writes require a trusted database role. The FastAPI database connection uses a trusted server role and explicit public projections. A Supabase service-role API key is unnecessary for this flow.

Run [schema.sql](../database/schema.sql) as the administrator. It installs a fresh schema or upgrades the Phase 0 schema in one transaction, preserves existing coordinates and ownership, and maps `unverified` to `pending`, `theft_snatching` to `theft`, `road_condition` to `unsafe_road`, and `other_hazard` to `other`. It preserves Phase 0 zone provenance and uses the earlier retrieval timestamp for legacy `last_verified_at`. Run [seed.sql](../database/seed.sql) only in a dedicated demo database. Repeated seeding refreshes timestamps on known fictional incidents while preserving live rows and existing moderation fields. Run [verify.sql](../database/verify.sql) after migration to check required indexes, RLS, and private grants. [Supabase PostGIS setup](https://supabase.com/docs/guides/database/extensions/postgis) · [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)

Heatmap scoring aggregates eligible records on demand using the existing rounded-point index and the requested date range. Phase 3 requires no schema migration. Optional fictional scoring fixtures are in [heatmap_demo.sql](../database/heatmap_demo.sql).

Phase 4 upgrades existing databases by rerunning `schema.sql`. The new table uses RLS and grants trusted server access only. FastAPI checks report ownership and moderator authorization before returning its projection. Existing `credibility_score` remains a stored moderation value with default zero, which represents an unset baseline. AI leaves it untouched. Neither that field nor model confidence is used by the Phase 3 heatmap.

Phase 5 adds `route_references` through the repeatable schema. It stores the returned route, trip ID, and departure time behind RLS. References expire after 15 minutes. A subsequent route lookup removes expired rows. Corridor evidence still queries the indexed rounded public points in `incidents`.
