# Mystery Card integration

Once the requirement is revealed, identify the smallest flow that can be demonstrated with real inputs. Add an endpoint or UI control only where that flow needs one.

| Surface | Extension point |
| --- | --- |
| Incident reporting | Add validated input to `schemas/incident.py` and use `incident_service.py` for authenticated writes. Preserve pending review and the existing public projection. |
| Safety intelligence | Add a read function in `services/geospatial_service.py` or `services/heatmap_service.py`. Reuse rounded public coordinates, coverage rules, and mode filters. |
| Map | Add a contextual layer through `SafetyMap.tsx` and a control in `MapWorkspace.tsx`. Add top-level navigation in `HomePage.tsx` only for a standalone flow. Keep source attribution and a mobile layout. |
| Assistant | Extend the typed plan in `schemas/assistant.py`, implement the approved read tool in `assistant/tools.py`, and dispatch it in `assistant/agent.py`. Add a result type and render any map action from typed tool output. |
| Notifications | If requested, define the triggering domain event and recipient consent first. Connect delivery from the existing authorized service after a successful transaction. Define deduplication and a delivery failure state. |
| Travel planning | Reuse `routing/comparison.py` and the planner's route references. Keep advisory provenance and unavailable evidence visible. |

Register new FastAPI routes under `/api` in `main.py` and add matching Pydantic and TypeScript contracts. Put provider secrets in backend settings. Add a repeatable SQL migration only if persistence is required.

Test one representative success path, invalid input, authorization and data separation, and the relevant provider failure. Use a fictional staging fixture. Rehearse the feature as one extra step in the [demo script](DEMO_SCRIPT.md) and verify desktop and mobile behavior.
