# MehfoozAI

MehfoozAI helps commuters, families, and visitors understand reported incidents, travel hazards, and official restrictions around unfamiliar places. The dynamic safety heatmap is the primary interface. Multan is the initial pilot for FAST TechSoc AI Hackathon 2026, under “AI with Purpose — Building Better Societies.”

## Architecture

- Keep a modular monolith. React/Vite owns presentation, FastAPI owns application logic and public projections, and Supabase PostgreSQL/PostGIS owns persistence and spatial queries.
- Use the API and database contracts in `docs/` as shared interfaces. Keep map, routing, and AI adapters behind the backend API where applicable. Keep dependencies and abstractions minimal.
- Leave privileged credentials server-side. Use Supabase Auth for report ownership and PostGIS for spatial evidence.

## AI and safety

- Use validated structured outputs for classification, extraction, provisional severity, and duplicate candidates. Keep moderation decisions and deterministic risk calculations in application code.
- Ground explanations in retrieved evidence. Keep verified facts, community allegations, provisional estimates, and missing data distinct. Never invent incident statistics, advisories, or tool results.
- Green means relatively lower observed risk in sufficiently sampled areas. Grey and clear areas represent insufficient evidence. Keep the reported-risk gradient and incident activity density distinct. Missing reports never establish safety.
- Keep authoritative restrictions identifiable and separate from security and road indicators. Traffic never automatically reduces security risk. Document score inputs, weights, and data coverage.
- Preserve provenance and UTC timestamps. Keep reporter identities, raw descriptions, credibility metadata, and evidence private. Exclude demo records from live queries.

## Development and collaboration

- Read existing code and contracts first. Reuse existing components, preserve established interfaces, and limit changes to the task.
- Coordinate module ownership and shared contract changes before parallel edits. Preserve others’ work. Record architectural decisions and update contracts alongside any change.
- Prefer a small working path over speculative abstractions. Run relevant checks and report only executed results.

## Completion report

Summarize work and files changed, commands run and test results, limitations, and the next recommended action.

## Phase 1 interfaces

- Use `MehfoozAI` for the product, `mehfooz-ai` for technical identifiers, and `/api` for backend endpoints.
- Keep public incident searches on the same generalized coordinates returned to callers. Only reviewed summaries can enter public results. Pending and demo evidence must remain visibly labeled.
- Run integration tests against a dedicated seeded test database. Mock external Auth only when reporting local database integration results.

## Frontend design

MehfoozAI is map-first, minimal, premium, and navigation-oriented. Avoid generic dashboards, unnecessary cards, and large sidebars. Every UI element must contribute to the user's geographical awareness or travel decision. Keep details and reporting contextual. Visual smoothing must preserve the backend's evidence eligibility and separate official advisories from reported risk.

## Incident intelligence

Keep model output in private analysis records. Preserve submitted category, location, time, description, and moderator-controlled fields until an authorized review changes them. Duplicate candidates are moderation hints. Keep their identities out of reporter-facing responses.

## Route planning

Use real provider geometry and compare it with rounded, eligible public evidence. Present travel estimates, community risk, road hazards, and official restrictions independently. Keep trip coordinates out of routine logs and disclose endpoint sharing with the routing provider.

## Travel assistant

Keep tool choice within the validated travel intent schema and tool execution on the server. Build factual responses and map actions from typed service results. Retain only bounded, short-lived conversation context. Keep live and demo sessions separate and require explicit sharing of map points and planner routes.
