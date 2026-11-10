# Stage MehfoozAI on Supabase, Render, and Vercel

Use a dedicated development project for the fictional demo. This repository includes deployment configuration. Hosted verification requires access to all three services and a Git repository the hosts can read. See [current readiness](FINAL_STATUS.md).

## Supabase

1. Create or select a development project. In SQL Editor, run [schema.sql](../database/schema.sql) as the administrator, then [verify.sql](../database/verify.sql). The schema installs PostGIS and the verification script checks the extension, spatial indexes, RLS, and restricted grants. If PostGIS installation is restricted, enable it under **Database → Extensions** and rerun the schema.
2. In **Authentication → Users**, create and confirm two email/password test users. Keep credentials in a password manager. Use a reporter and a separate account to verify ownership. To inspect AI duplicate candidates as a reviewer, add the reviewer UUID to the server's `LLM_MODERATOR_IDS` JSON array. Publishing still requires an authorized database administrator.
3. From **Connect**, copy the direct PostgreSQL URI or the session pooler URI if the host lacks IPv6. Enable TLS, for example with `sslmode=require`. Use the verified project CA and `sslmode=verify-full` where available. Keep the URI and its password on the backend. The application uses a trusted database connection for authorized writes and explicit public projections.
4. Copy the project URL and **publishable key** or legacy anon key from the dashboard. Use them as `SUPABASE_URL` and `SUPABASE_ANON_KEY` on the API and as `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` on the frontend. The Supabase service-role API key is unnecessary.
5. For a fictional staging demo, run [seed.sql](../database/seed.sql), [heatmap_demo.sql](../database/heatmap_demo.sql), and [phase5_demo.sql](../database/phase5_demo.sql) in that order. Reruns refresh timestamps on known fictional incident IDs. [Supabase PostgreSQL connection](https://supabase.com/docs/guides/database/connecting-to-postgres) · [PostGIS](https://supabase.com/docs/guides/database/extensions/postgis) · [API keys](https://supabase.com/docs/guides/api/api-keys)

## Render API

Import the Git repository as a Blueprint with [render.yaml](../render.yaml). The configuration uses the `backend` root, Python 3.12, `pip install -r requirements.txt`, and one Uvicorn worker. One worker keeps the assistant conversation store and public routing throttle in one process. Start locally with the same import target to verify startup.

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Secret PostgreSQL URI from the development project |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Project URL and publishable key |
| `CORS_ORIGINS` | JSON array of exact HTTPS frontend origins, e.g. `["https://your-staging-app.vercel.app"]` |
| `ROUTING_SERVICE_URL` | Authorized OSRM-compatible driving base URL |
| `LLM_API_KEY`, `LLM_MODEL` | Server-only incident classifier key and JSON-capable model |
| `LLM_PROVIDER`, `LLM_BASE_URL` | Optional classifier selection, see [configuration template](../.env.example) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Server-only Gemini key and optional model override for assistant interpretation |
| `GEOCODING_SERVICE_URL` | Optional private or contracted Nominatim-compatible URL |

Leave unsigned demo Gemini off on a public deployment. Use a signed-in account for Gemini or opt in only for a restricted demo. Configure the public routing service only for low-volume rehearsal under its usage policy. [Render FastAPI setup](https://render.com/docs/deploy-fastapi) · [Blueprint reference](https://render.com/docs/blueprint-spec) · [FOSSGIS routing policy](https://routing.openstreetmap.de/about.html)

Render uses `/api/health` as a process check. Separately verify `/api/ready` after deployment. Free services can take time to wake. Open health and readiness before the timed demo. [Render free service behavior](https://render.com/docs/free)

## Vercel frontend

Import the same Git repository. Set **Root Directory** to `frontend`, framework to **Vite**, and Node.js to **22.x**. The [Vercel configuration](../frontend/vercel.json) sets `npm ci`, `npm run build`, and output `dist`. Use the Render HTTPS origin for `VITE_API_URL`, with no `/api` suffix. Set the two public Supabase variables above in the same deployment environment and rebuild. If Vercel assigns the final URL after the first build, update `CORS_ORIGINS` on Render with that exact origin before opening the app. Preview URLs need their own allowlist entries. [Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite) · [Root directory and build settings](https://vercel.com/docs/builds/configure-a-build)

## Acceptance checks

1. In a trusted terminal, set `API` and `WEB` to the deployed HTTPS origins and run the checks below. Confirm the preflight response includes the exact frontend origin and allows `POST` and `Authorization`. Repeat with an unlisted origin and check that it receives no allow-origin header.
2. Sign in with the reporter and submit a fictional record in the dedicated staging project. Check the pending row and confirm public detail returns 404. As the second account, confirm the reporter's private analysis returns 404. Use the reviewer workflow in the [demo script](DEMO_SCRIPT.md) and verify that the record appears only in demo reads and eligible counts.
3. Verify public incident and advisory responses, route geometry and comparison, and the assistant map handoff in the hosted browser. For live AI checks, use one fictional English, Urdu, and Roman Urdu classifier request each. Confirm a signed-in assistant response returns `interpretation: model` and real typed evidence. Guided interpretation is a working fallback.
4. Review the built frontend and deployment environment. Only the API origin, public Supabase values, and public map settings belong in `VITE_*`. Keep database, model, and moderation credentials in the API environment. Record results in [final status](FINAL_STATUS.md).

```sh
curl -fsS "$API/api/health"
curl -fsS "$API/api/ready"
curl -fsS -i -X OPTIONS "$API/api/incidents" \
  -H "Origin: $WEB" -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: authorization,content-type'
curl -fsS "$API/api/incidents?mode=demo&limit=2"
curl -fsS "$API/api/official-zones?mode=demo"
```
