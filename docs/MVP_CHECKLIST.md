# MVP readiness checklist

- [ ] Supabase schema applied to a development project and ownership verified with two accounts.
- [x] Local PostGIS tests cover pending report persistence, reviewed public retrieval, rejection, and the report rate limit.
- [x] Local browser rehearsal verifies fictional publication changes demo evidence only.
- [x] Deployment configuration and setup are documented. Local readiness checks PostGIS and schema availability.
- [ ] Verify end-to-end submission against hosted Supabase with a real Auth session.
- [x] Map has attribution, a legend, time filtering, and loading, empty, and failure states.
- [x] Mobile map, journey planner, and report location selection are available.
- [x] Heatmap updates after corroboration and refresh. Pending and rejected records are excluded.
- [x] AI duplicate candidates and provisional suggestions are private and available to authorized reviewers.
- [ ] Validate the risk heuristic with real coverage data.
- [x] Grey appears when evidence is insufficient. Restrictions remain visible independently.
- [ ] Real AI provider returns validated classifications and handles invalid or unavailable responses.
- [x] Real OSRM geometry, distance, and ETA appear with separate route evidence and advisories. Multiple provider options are selectable when returned.
- [x] Risk gradient and incident activity use separate legends. Unsupported risk areas remain clear.
- [x] Assistant calls real area and route tools, shows source records, and flags missing coverage.
- [ ] Verify the signed-in assistant end to end with a configured model and external place provider.
- [x] Fictional Multan evidence is visually labeled and excluded from live reads.
- [ ] Frontend and API deployed with correct CORS, server-side secrets, and a rehearsed end-to-end demo.
