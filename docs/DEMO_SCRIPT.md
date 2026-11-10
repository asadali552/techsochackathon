# Hackathon rehearsal

## Prepare

- Use a dedicated fictional staging project and a confirmed reporter account. Keep the password in a password manager. A trusted reviewer needs SQL Editor access for the publication step. Use a configured classifier to show actual AI output and a Gemini key for signed-in assistant interpretation. [Deployment and credentials](DEPLOYMENT.md)
- Start FastAPI and Vite using the [local setup](../README.md#run-locally), or use the deployed HTTPS URLs after verifying them. The map needs tiles and the planner needs an authorized OSRM endpoint. Before presenting, verify `/api/health` and `/api/ready`.
- Run the schema and seed scripts against the dedicated demo database from the repository root, or run each file separately in SQL Editor. Rerun these before the rehearsal to refresh the sample incident timestamps. Keep a note of any rehearsal report UUID for cleanup.

```sh
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 \
  -f database/schema.sql -f database/verify.sql \
  -f database/seed.sql -f database/heatmap_demo.sql -f database/phase5_demo.sql
```

## Present

1. Open the [local fictional demo](http://127.0.0.1:5173/?demo=1#map). Point out **Fictional demo**. Compare **Safety risk** with **Activity**. Select **Night** to show historic filtering, then return to **Full day**. Choose a visible cell to show scores, evidence dates, and coverage. Clear areas represent insufficient evidence.
2. Click a dashed advisory polygon to see **Fictional demo** as the issuing authority and inspect its effective dates.
3. Search `30.205, 71.453` and select the coordinates. Inspect the center cell and note its community risk and eligible count. Choose **Report Incident**, sign in, choose **Robbery**, and use **Choose location on map → Use map center**. Enter `Fictional heatmap demo: sample review` and a recent local time. Choose **Review report → Submit incident**.
4. Read **Pending review** and note the reference UUID. If classification is configured, show the provisional category, severity, and summary. Confirm the public detail endpoint returns 404 in live and demo modes before review.
5. As the database reviewer in the dedicated demo project, replace the UUID below and run the guarded update. Confirm exactly one row was returned. This explicitly fictional exercise labels the approved sample demo-only.

```sql
UPDATE public.incidents
SET public_summary = 'Fictional heatmap demo: sample review',
    verification_status = 'corroborated', severity = 4,
    source = 'demo', is_demo = true, user_id = NULL
WHERE id = '<report UUID>'::uuid
  AND source = 'community' AND NOT is_demo AND verification_status = 'pending'
  AND description = 'Fictional heatmap demo: sample review'
  AND public_summary IS NULL
RETURNING id, verification_status, is_demo;
```

6. Return to **Safety Map** and select **Refresh heatmap**. Inspect the same center cell. The eligible count increases by one. Confirm the marker is labeled fictional and the report stays absent from live results.
7. Open **Plan Journey → Use sample trip → Find routes**. Show the real street geometry, distance, ETA, community and road evidence, and the fictional journey advisory. Select an alternative when the provider supplies one. A single returned option is a valid result.
8. Open **AI Assistant**, select **Use planned routes**, and ask “Which route has fewer reported incidents?” Then ask “Plan a trip from Ghanta Ghar to Multan Cantt” and follow with “What about travelling at night?” Choose **Show route 1 on map**. State whether the deployment used Gemini or guided interpretation. Show the evidence gap by asking for live weather.
9. After the rehearsal, delete only the report UUID from step 3 in the dedicated demo project. The private analysis row is removed by the existing foreign-key cascade.

```sql
DELETE FROM public.incidents
WHERE id = '<report UUID>'::uuid
  AND description = 'Fictional heatmap demo: sample review'
  AND (is_demo OR (verification_status = 'pending' AND public_summary IS NULL));
```

## If a service fails

- **Database or Auth.** Check `/api/ready`, project configuration, and the confirmed test account. Use the previously rehearsed local demo if hosted staging is down.
- **Classifier or Gemini.** A pending report still saves. Show the unavailable state or the guided assistant with real database tools. Describe the provider gap aloud.
- **Routing.** Retry after a pause if the provider rate-limits the request. If the provider stays down, continue with the heatmap and advisory evidence. Present any earlier screenshots as prior rehearsal captures.
- **Tiles.** Reopen the already loaded demo map or retry on a stable connection. Keep tile attribution visible.
