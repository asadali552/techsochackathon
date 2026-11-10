# Phase 7 readiness

The seeded local demo was rehearsed end to end. Hosted acceptance is pending. The workspace has no Git remote or configured hosted Supabase, Render, Vercel, classifier, or Gemini credentials. Use the [deployment runbook](DEPLOYMENT.md) to complete those checks.

| Feature | Status | Evidence |
| --- | --- | --- |
| API and database readiness | Working and verified locally | Health and readiness returned 200. Readiness executed PostGIS and checked schema presence. Migration and the SQL extension, index, RLS, and privilege checks passed. |
| Hosted Supabase and Auth | Blocked | Local tests used PostGIS with a substitute for Supabase Auth. A hosted project URI, publishable key, and confirmed test accounts are needed for hosted verification. |
| Incident reporting and moderation | Working and verified locally | Tablet sign-in through the local Auth substitute, report confirmation, private pending storage, and authorized SQL review. Public detail was 404 before review. After demo publication, the selected 750 m cell increased from 2 to 3 eligible reports and from 15 to 84 in this rehearsal. Live evidence stayed unchanged. The rehearsal rows were cleaned up. |
| Public incident and advisory access | Working and verified locally | API tests verified rounded coordinates, rejected and unreviewed exclusion, effective dates, private analysis authorization, and live/demo separation. Browser showed the fictional advisory and supporting detail. |
| Heatmap and activity | Working and verified locally | Continuous raster, historical Night filter, independent activity view, grey or clear coverage gaps, Canvas fallback, zoom, and refresh after review. Tablet test verified heatmap retry while advisories remained visible. |
| Risk model validation against real coverage | Implemented but externally unverified | The deterministic score and eligibility rules passed fixture tests. Calibration and predictive validation against real coverage remain open. |
| Incident classification | Implemented but externally unverified | English, Urdu, Roman Urdu, duplicate detection, private analysis, and provider failure cases passed with controlled provider responses. Browser confirmed the actual unavailable state without credentials. |
| OSRM route planner and comparison | Working and verified locally | The configured provider returned one real 3.8 km route with a six-minute estimate. PostGIS matched two fictional safety reports and the fictional closure. Multiple route selection and provider failure passed with controlled responses. |
| Travel assistant tools | Working and verified locally | Guided interpretation invoked real PostGIS and OSRM services. The browser compared the planned route, opened it on the map, reused a journey for a 10 p.m. follow-up, and disclosed unavailable weather. Automated checks exercised area, heatmap, nearby reports, ambiguity, isolation, and partial failures. |
| Gemini and external geocoding | Implemented but externally unverified | Provider adapter tests used controlled responses. Bundled place lookup worked in rehearsal. Live Gemini and broader lookup need configured providers. |
| Browser layouts | Working and verified locally | Chromium tests and visual checks covered desktop 1440 × 900, tablet 820 × 1180, and mobile 390 × 844. A map-control event was corrected and the selected report location rechecked. |
| Vercel and Render | Blocked on hosting access | The deployment files parse. The production build and a simulated Vercel build passed. Deployment HTTPS, hosted CORS, and hosted browser-to-API checks remain open. |
| Moderation dashboard, live weather, emergency facilities, live closure feeds, standalone safety-area endpoint | Not implemented | Authorized SQL handles moderation. The assistant explains evidence gaps and retrieves stored advisories. Area evidence is exposed through the assistant. |
| Mystery Card | Extension plan ready | The requirement has yet to be revealed. [Extension points and test approach](MYSTERY_CARD_INTEGRATION.md) |

## Test evidence

- **115 backend tests passed** with the dedicated local PostGIS database. Auth and model responses were substituted in automated tests. The suite reports a Starlette test client dependency deprecation warning.
- **8 browser tests passed** against the running local frontend and API. Visual captures were taken during desktop, tablet, and mobile checks.
- **Type check and production build passed.** The main script was 131 kB gzip. Builds rejected a dummy Supabase secret key and missing Vercel HTTPS settings. The simulated Vercel build used placeholder public settings.
- **Database checks passed.** The schema reapplied, RLS and spatial indexes were verified, and the three seed files were applied twice without increasing the demo row count. The app limit is ten saved reports per account per rolling hour, and browser database roles cannot submit directly.
- **Local timings from the rehearsal.** The sampled heatmap reads took 12–18 ms and the ready check took 44 ms. These are local observations. Hosted latency and free-service cold starts need separate testing.
