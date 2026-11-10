# Architectural decisions

| Decision | Reason |
| --- | --- |
| React/Vite UI and a FastAPI modular monolith | Separates presentation from contracts and keeps the hackathon deployment small. Target Vercel for the UI and Render for the API. |
| Supabase Auth and PostGIS | Reuses identity and ownership controls. Spatial indexes handle route-corridor and area queries in the same database. |
| Geography in WGS84 | Matches GeoJSON coordinates at the boundary and supports meter-based queries. |
| Backend public projections | Keeps raw user reports, precise locations, and moderation metadata out of public data. |
| Deterministic, coverage-gated scoring | Allows teams to reproduce and explain outcomes. Missing observations remain grey. |
| Official overlays and evidence dimensions stay separate | A traffic advantage cannot hide a restriction or offset security evidence. |
| Interchangeable AI and routing adapters | Tool calling and structured inference can use working providers without locking the API to one vendor. |
| Demo-only seeds with stable UUIDs | Supports a repeatable Multan rehearsal without contaminating live evidence. |
| Tailwind through PostCSS | Keeps configuration small and uses the same stylesheet pipeline in development and builds. |
| MehfoozAI branding | Use MehfoozAI in product copy, `mehfooz-ai` for technical identifiers, and `/api` for the existing API prefix. |
| Phase 1 incident contract | Accept numeric latitude and longitude and bounded offset pagination. Preserve the existing `data` and `error` envelope. Rename the initial categories and pending state in a repeatable database upgrade. |
| Public spatial projection | Index and query generalized incident points so public searches cannot reveal submitted coordinates at higher precision. |
