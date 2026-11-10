# MehfoozAI

Community-powered travel safety intelligence for the FAST TechSoc AI Hackathon 2026. The Multan pilot centers on a safety heatmap, community reporting, official advisories, and evidence-aware route planning.

Phase 0 established the React/Vite shell, FastAPI health check, and architecture. Phase 1 adds authenticated incident submission, public incident list/detail/nearby queries, and official-zone GeoJSON. Phase 2 adds a responsive Multan map, evidence filters and details, and a signed-in reporting form. See the [API contracts](docs/API_CONTRACTS.md) and [database design](docs/DATABASE_DESIGN.md).

## Run locally

Use Node.js 20.19+ on the 20.x line or Node.js 22.12+ and Python 3.12. Run from the repository root.

```sh
cp .env.example .env
npm --prefix frontend ci
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

Start the frontend and API in separate terminals.

```sh
npm --prefix frontend run dev
```

```sh
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend/app --port 8000
```

Open [the frontend](http://localhost:5173) or [API documentation](http://localhost:8000/docs). The full-screen map and API health check work with blank external settings. Reports and zones require a configured database. Select **Demo mode** to see the fictional Multan records in a seeded database. Use the search box to filter reports already returned for the current view.

The base map uses OpenStreetMap tiles by default. Set both `VITE_MAP_TILE_URL` and `VITE_MAP_TILE_ATTRIBUTION` when switching providers. [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/)

## Configure Supabase

1. Use a development Supabase project. Run [database/schema.sql](database/schema.sql) as its administrator through SQL Editor. The same script upgrades a Phase 0 database. Run it against a development copy first. Seed a dedicated demo database with [database/seed.sql](database/seed.sql).
2. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the root `.env`. Use the project URL and a publishable or legacy anon key. Set `DATABASE_URL` to the direct or session-pooler PostgreSQL URI from **Connect** and use TLS. Use a trusted server database role with access to the application tables. Keep the database credentials out of the frontend. [Supabase connection setup](https://supabase.com/docs/guides/database/connecting-to-postgres)
3. Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` to the same project URL and public key for browser sign-in, then restart Vite. Create and confirm a test email/password user under Supabase Auth. Sign in under **Report Incident**, or obtain a token from the password grant below. [Supabase Auth user lookup](https://supabase.com/docs/reference/javascript/auth-getuser)

In the following example, set shell variables `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `TEST_EMAIL`, and `TEST_PASSWORD` for the development project. The command uses `jq`.

```sh
token=$(jq -n --arg email "$TEST_EMAIL" --arg password "$TEST_PASSWORD" \
  '{email:$email,password:$password}' | \
  curl -fsS "$SUPABASE_URL/auth/v1/token?grant_type=password" \
    -H "apikey: $SUPABASE_ANON_KEY" -H 'Content-Type: application/json' --data-binary @- | \
  jq -er '.access_token')

occurred_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
jq -n --arg occurred_at "$occurred_at" \
  '{category:"poor_lighting",description:"Test report in a development project.",latitude:30.1956,longitude:71.4753,occurred_at:$occurred_at}' | \
  curl -fsS http://localhost:8000/api/incidents \
    -H "Authorization: Bearer $token" -H 'Content-Type: application/json' --data-binary @-
unset token
```

The 201 response includes the report ID. A trusted reviewer publishes a redacted `public_summary` in the database before it can be retrieved at `GET /api/incidents/{id}`. Moderation is currently a database operation.

In the development SQL Editor, substitute the returned UUID and a reviewed summary.

```sql
UPDATE public.incidents
SET public_summary = 'Reviewed public summary'
WHERE id = '<report UUID>' AND verification_status = 'pending' AND NOT is_demo;
```

A trusted reviewer can exclude an incident by setting its status to `rejected`. Confirmation requires the verification process in [Safety and trust](docs/SAFETY_AND_TRUST.md).

```sh
curl -fsS http://localhost:8000/api/health
curl -fsS 'http://localhost:8000/api/incidents?mode=demo&limit=10'
curl -fsS 'http://localhost:8000/api/incidents/nearby?mode=demo&latitude=30.195&longitude=71.475&radius_meters=600'
curl -fsS 'http://localhost:8000/api/official-zones?mode=demo'
```

Demo mode is opt-in and only has data after seeding. All seeded records are fictional. Live requests exclude them and an empty zones response means no matching records are stored. Browser sign-in supports existing accounts. Sessions are kept in memory and require sign-in again after reload or expiry. Moderation is an authorized database workflow. Travel Planner and AI Assistant use the configured routing and evidence services.

## Checks

```sh
npm --prefix frontend run build
(cd backend && .venv/bin/python -m pytest -q)
```

For database-backed tests, apply the schema and seed to a dedicated test database, create a confirmed test user, and provide its UUID as `TEST_AUTH_USER_ID` and its database URI as `TEST_DATABASE_URL` in the shell before running pytest. These tests stub the Supabase Auth response and use real database writes and spatial queries. Verify the real Auth service separately with the password-grant example.

For the browser smoke tests, start both apps with the fictional seed installed in a development database. Install Chromium once with `cd frontend && npx playwright install chromium`, then run `npm --prefix frontend run test:browser` from the repository root. Set `MEHFOOZ_TEST_WEB_URL` if Vite uses a different URL.

## Heatmap demo

1. In a dedicated development database, run [seed.sql](database/seed.sql) and then [heatmap_demo.sql](database/heatmap_demo.sql). Start both apps, turn on **Demo mode** (or open [the local demo](http://127.0.0.1:5173/?demo=1)), and leave **Heatmap** on in **Layers**. Full day shows green, yellow, red, and grey around Multan at 750 m resolution. Try Morning, Afternoon, and Night separately. Switch to **Road hazards** in **Layers** for the independent road evidence. The dashed closure remains a separate fictional advisory.
2. Sign in with a development account using the earlier token instructions or the report form. Submit a `robbery` with description `Fictional heatmap demo: sample review` at latitude `30.205`, longitude `71.453`, and a recent timestamp. Use the earlier curl example with these values for exact placement. The report ID should initially return 404 from the public detail endpoint. Refresh the demo heatmap and check that the west green cell has two eligible reports.
3. In the dedicated demo project's SQL Editor, replace the placeholder with the returned UUID and run this authorized review. It moves the explicitly fictional submission into demo-only evidence.

```sql
UPDATE public.incidents
SET public_summary = 'Fictional heatmap demo: sample review',
    verification_status = 'corroborated', severity = 4,
    source = 'demo', is_demo = true, user_id = NULL
WHERE id = '<report UUID>'
  AND source = 'community' AND verification_status = 'pending'
  AND description = 'Fictional heatmap demo: sample review';
```

4. Return to Full day and select **Refresh heatmap**. The west cell should now have three eligible reports and a higher score. Live mode excludes this fictional data. Run all three demo seed scripts before the browser suite. Reruns refresh the known fictional incidents. Use the rehearsal cleanup to remove your submitted sample.

Scores are prototype reported-evidence indicators. See the [scoring formula and limitations](docs/ARCHITECTURE.md#phase-3-heatmap-scoring).

## AI incident analysis

Rerun [schema.sql](database/schema.sql) on an existing development database to add private analysis storage. Configure server-side `LLM_API_KEY` and `LLM_MODEL`. The default provider is `openai`. For a compatible Chat Completions provider, set `LLM_PROVIDER=openai_compatible` and `LLM_BASE_URL` to its API root. The model must accept JSON mode and `max_completion_tokens`. Set `LLM_MODERATOR_IDS` to a JSON array of trusted Supabase Auth user UUIDs. An empty list allows owner access only.

The reporting panel starts analysis after the report is saved. To test manually, use a development user's bearer token and report UUID with `POST /api/ai/incidents/{id}/analyze` and `GET /api/ai/incidents/{id}/analysis`. Without a provider the report still saves and analysis shows as unavailable. Repeating the POST retries a failed or unavailable attempt. Completed results are reused.

Run `cd backend && .venv/bin/python -m pytest -q` for deterministic provider tests, including English, Urdu, and Roman Urdu fixtures. Set `TEST_DATABASE_URL` and `TEST_AUTH_USER_ID` as above for PostGIS integration coverage. Use fictional reports when checking a configured live model. [AI API contracts](docs/API_CONTRACTS.md#post-apiaiincidentsincident_idanalyze)

## Phase 5 local journey demo

1. Rerun [schema.sql](database/schema.sql) on the development database. Apply [seed.sql](database/seed.sql), [heatmap_demo.sql](database/heatmap_demo.sql), and [phase5_demo.sql](database/phase5_demo.sql) for the labeled Multan fixtures.
2. Set the backend's `ROUTING_SERVICE_URL` to a configured OSRM-compatible driving endpoint and start both apps. For low-volume demos use `https://routing.openstreetmap.de/routed-car`. The public service allows at most one request per second and logs the coordinates it receives. [FOSSGIS service policy](https://routing.openstreetmap.de/about.html)
3. Open the [local demo](http://127.0.0.1:5173/?demo=1). Toggle **Safety risk** and **Activity** to compare the two surfaces. Open **Plan Journey**, choose **Use sample trip**, then **Find routes**. The sample uses actual Multan streets. The routing provider may return a single option. Route geometry and driving estimates come from OSRM, while the demo reports and closure are fictional.
4. Run the backend tests and `npm --prefix frontend run test:browser` against the seeded local stack. Set `MEHFOOZ_TEST_WEB_URL` if using a different frontend address. The browser suite tests selection of multiple options and provider errors with controlled responses. [Route comparison and limitations](docs/ARCHITECTURE.md#phase-5-journey-comparison)

## Phase 6 local assistant demo

Open the [assistant demo](http://127.0.0.1:5173/?demo=1#assistant). Try **Plan a trip from Ghanta Ghar to Multan Cantt**, then ask **What about travelling at night?** Use **Show route on map** to view the geometry. From a heatmap cell, choose **Ask about this cell** to share its point, period, grid size, and historical window.

Live chat uses the existing registered-account sign-in. To use Gemini for question interpretation, add `GEMINI_API_KEY` to the server's root `.env` and restart the API. The default model is `gemini-3.5-flash-lite`. For a private local demo, also set `ASSISTANT_GEMINI_IN_DEMO=true`. Without a Gemini key, signed-in chat can use the existing `LLM_*` settings. Guided interpretation is available if the model is disabled or fails. [Google AI Studio API keys](https://aistudio.google.com/apikey) Configure `GEOCODING_SERVICE_URL` with a private or contracted Nominatim-compatible endpoint for places outside the bundled gazetteer. The public Nominatim instance is excluded. No new database migration is needed. [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/)


## Phase 7 handoff

- [Local demo](http://127.0.0.1:5173/?demo=1#map)
- [Rehearsal and recovery steps](docs/DEMO_SCRIPT.md)
- [Supabase, Render, and Vercel deployment](docs/DEPLOYMENT.md)
- [Feature readiness and verification](docs/FINAL_STATUS.md)
- [Mystery Card extension points](docs/MYSTERY_CARD_INTEGRATION.md)
