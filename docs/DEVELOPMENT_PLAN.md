# Development plan

| Phase | Deliverable | Acceptance |
| --- | --- | --- |
| 0 | Initialize scaffold and contracts | Frontend builds and serves the shell, API health responds, SQL schema and repeatable seed are checked, and local setup is documented. |
| 1 | Database and backend APIs | Apply schema to development Supabase. Verify real Supabase authentication, ownership, submission, reviewed public projections, spatial reads, and live/demo separation. Local PostGIS tests can exercise database and API behavior with Auth substituted. |
| 2 | Interactive safety map | Load attributed tiles, explore Multan, display filtered markers and distinct advisories, and handle loading, error, and empty states. Submit a private pending report through the existing authenticated API. |
| 3 | Dynamic heatmap intelligence | Deterministic fixtures cover all bands, coverage gaps, historical hours, and refresh after authorized review. Duplicate detection remains part of Phase 4. Restrictions remain independently visible. |
| 4 | AI incident processing | Provider adapter returns validated structured results for English, Urdu, and Roman Urdu. Verify retry, moderator-only duplicate candidates, and unchanged public eligibility. Run a live multilingual smoke check once deployment credentials are configured. |
| 5 | Continuous map and journey comparison | Show distinct risk and activity views. Draw actual driving options returned by OSRM and display time, distance, both evidence dimensions, restrictions, and missing coverage. |
| 6 | Agentic assistant | Real tool calls answer representative area and route questions with evidence references. Unavailable tools produce an explicit gap. |
| 7 | Integration and demo | Deploy the frontend and API, rehearse report-to-map-to-route flow, exercise provider failure, and verify separation of live and fictional data. |

Timebox to the Multan pilot. Build one end-to-end slice before expanding coverage. Keep the later Mystery Card challenge behind existing service interfaces.

The Phase 7 local rehearsal is documented in [final status](FINAL_STATUS.md). Use the [deployment runbook](DEPLOYMENT.md) to complete hosted verification and the [demo script](DEMO_SCRIPT.md) to reproduce the local walkthrough.
