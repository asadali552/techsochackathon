import logging
import re
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from pydantic import ValidationError

from app.assistant import tools
from app.assistant.interpret import guided_plan, model_plan
from app.assistant.places import resolve
from app.assistant.session import Conversation, TTL
from app.core.config import Settings
from app.core.database import database_connection
from app.core.errors import ApiError
from app.schemas.assistant import ChatRequest, ChatResult, EvidenceReference, Place, Plan
from app.schemas.heatmap import CellEvidence
from app.schemas.official_zone import ZoneFeature

logger = logging.getLogger(__name__)
PERIOD_HOUR = {"night": 22, "evening": 19, "afternoon": 14, "morning": 8}


def trip_departure(plan: Plan, previous: datetime | None, now: datetime, config: Settings) -> datetime:
    if plan.day_offset is None and plan.departure_hour is None and plan.period not in PERIOD_HOUR:
        return max(now, previous) if previous else now
    tz = ZoneInfo(config.heatmap_timezone)
    local = now.astimezone(tz)
    reference = (previous or now).astimezone(tz)
    date = local + timedelta(days=plan.day_offset) if plan.day_offset is not None else reference
    hour = plan.departure_hour if plan.departure_hour is not None else PERIOD_HOUR.get(plan.period, 9)
    departure = date.replace(hour=hour, minute=0, second=0, microsecond=0)
    if departure < local and (plan.day_offset is None or plan.period == "night"):
        departure += timedelta(days=1)
    return departure.astimezone(UTC)


def indicator(evidence: CellEvidence) -> str:
    count = evidence.report_count
    value = f"{evidence.score}/100" if evidence.score is not None else "insufficient evidence"
    return f"{value} ({count} eligible {'report' if count == 1 else 'reports'})"


def assist(key: UUID, session: Conversation, request: ChatRequest, config: Settings, *, use_model: bool) -> ChatResult:
    now = datetime.now(UTC)
    deadline = monotonic() + 24
    remaining = 6
    result = ChatResult(conversation_id=key, mode=request.mode, interpretation="guided", answer="")
    answer: list[str] = []

    def finish() -> ChatResult:
        if not answer:
            answer.append("The requested evidence could not be loaded. Try again shortly.")
        if result.mode == "demo":
            answer.append("Demo reports and advisories are fictional.")
        result.answer = " ".join(answer)
        return result

    def run(name, tool, *args, database=True):
        nonlocal remaining
        if remaining <= 0 or monotonic() >= deadline:
            result.unavailable_sources.append(name)
            return None
        remaining -= 1
        try:
            if database:
                with database_connection(config) as db:
                    return tool(db, *args)
            return tool(*args)
        except ValidationError:
            result.unavailable_sources.append(name)
            answer.append("Check the location or trip details and try again.")
        except ApiError as exc:
            result.unavailable_sources.append(name)
            answer.append(exc.detail)
        except psycopg.Error as exc:
            result.unavailable_sources.append(name)
            logger.info("assistant_tool_failed tool=%s sqlstate=%s", name, exc.sqlstate)
        return None

    def get_place(field: str, existing: Place | None, first_endpoint: Place | None = None) -> Place | None:
        if chosen and chosen[0] == field:
            return chosen[1]
        name = getattr(plan, field)
        if not name:
            return existing
        matches = run("geocoding", resolve, name, config, database=False)
        if matches is None:
            return None
        if len(matches) > 1:
            result.choices = matches
            session.pending = (plan, field, matches, first_endpoint)
            answer.append("Several places match. Choose a location to continue.")
            return None
        if not matches:
            answer.append("I couldn't resolve that place. Try a more specific name or latitude, longitude.")
            return None
        return matches[0]

    def cite_zones(zones: list[ZoneFeature]):
        known = {zone.id for zone in result.advisories}
        for zone in zones:
            if zone.id in known:
                continue
            known.add(zone.id)
            p = zone.properties
            result.advisories.append(zone)
            result.evidence.append(EvidenceReference(
                kind="official_zone", reference=str(zone.id), label=p.name, source_url=p.source_url, as_of=p.last_verified_at,
            ))

    chosen = None
    resolved_origin = None
    if session.pending and re.fullmatch(r"[1-5]", request.message):
        plan, field, choices, resolved_origin = session.pending
        index = int(request.message) - 1
        if index >= len(choices):
            answer.append("Choose one of the locations listed below.")
            result.choices = choices
            return finish()
        chosen = field, choices[index]
    else:
        has_trip = bool(request.route_ids or session.route_ids or (session.origin and session.destination))
        plan = model_plan(request.message, config, {
            "has_journey_context": has_trip, "has_location_context": bool(session.area or request.location),
        }, now) if use_model else None
        if plan is not None:
            result.interpretation = "model"
        else:
            plan = guided_plan(request.message, has_trip=has_trip, has_area=bool(session.area))
    session.pending = None

    for label, pattern in (
        ("weather", r"\b(?:weather|forecast|rain|snow)\b"),
        ("emergency facilities", r"\b(?:hospital|ambulance|emergency facilit\w+)\b"),
        ("live road closures", r"\b(?:live|real.time)\b.*\b(?:road closure|traffic)"),
    ):
        if re.search(pattern, request.message, re.IGNORECASE):
            result.unavailable_sources.append(label)

    if plan.intent in {"journey", "compare"}:
        ids = request.route_ids or (session.route_ids if monotonic() < session.routes_expires else [])
        if plan.intent == "journey" or (not ids and session.origin and session.destination):
            origin = resolved_origin or get_place("origin", session.origin)
            if origin is None:
                if not answer:
                    answer.append("What is the starting point?")
                return finish()
            destination = get_place("destination", session.destination, origin)
            if destination is None:
                if not answer:
                    answer.append("What is the destination?")
                return finish()
            session.area = None
            result.places = [origin, destination]
            changing_trip = bool(plan.origin or plan.destination or chosen)
            departure = trip_departure(plan, None if changing_trip else session.departure, now, config)
            session.origin, session.destination, session.departure, session.route_ids = origin, destination, departure, []
            result.route_options = run("routing", tools.get_route_options, origin, destination, departure, config)
            if result.route_options is None:
                return finish()
            ids = [route.id for route in result.route_options.routes]
            session.route_ids, session.routes_expires = ids, monotonic() + TTL
            if not ids:
                answer.append("The routing provider returned no driving routes for these endpoints.")
                return finish()
        elif not request.route_ids or request.route_ids == session.route_ids:
            result.places = [p for p in (session.origin, session.destination) if p is not None]
        if not ids:
            answer.append("Plan a journey first or ask from the route planner so I can use its route references.")
            return finish()
        comparison = run("route evidence", tools.compare_route_risks, ids, request, plan, config)
        result.comparison = comparison
        routes = comparison.routes if comparison else result.route_options.routes if result.route_options else []
        for i, route in enumerate(routes, 1):
            result.evidence.append(EvidenceReference(kind="route", reference=str(route.id), label=f"Route {i}",
                                                     as_of=now, source_url="https://www.openstreetmap.org/copyright"))
        if not routes:
            return finish()
        if len(result.places) == 2:
            answer.append(f"{result.places[0].label} to {result.places[1].label}.")
        answer.append(f"OSRM returned {len(routes)} driving {'option' if len(routes) == 1 else 'options'}.")
        if comparison:
            for route in comparison.routes:
                cite_zones(route.official_zones)
            if plan.preference == "fewer_reported_incidents":
                comparable = [r for r in comparison.routes if r.security.coverage == "sufficient"]
                if len(comparable) > 1:
                    answer.append("Options with enough community evidence are ordered by eligible reports per kilometre.")
                else:
                    answer.append("Too few options have sufficient evidence for a reliable incident comparison.")
            answer.append("Advisory coverage may be incomplete. Verify any listed restrictions with the issuing authority before departure.")
        else:
            answer.append("Route evidence could not be loaded. The travel estimates are still available.")
        return finish()

    if plan.intent == "clarify":
        answer.append("Ask about a place, recent reports, a heatmap cell, or a driving trip between two locations.")
        return finish()

    shared = Place(label="Shared map location", point=request.location, source="shared location") if request.location else None
    place = get_place("place", shared or session.area)
    if place is None:
        if not answer:
            answer.append("Which place should I look up? You can also share a point from the map.")
        return finish()
    session.area = place
    result.places = [place]
    answer.append(f"Location resolved to {place.label}.")
    if plan.intent == "incidents":
        found = run("nearby incidents", tools.get_nearby_incidents, place, request, plan, now)
        if found is not None:
            result.incidents, result.incident_window = found
            for incident in result.incidents:
                result.evidence.append(EvidenceReference(
                    kind="incident", reference=str(incident.id), label=incident.category.replace("_", " ").title(),
                    as_of=incident.occurred_at,
                ))
            count = len(result.incidents)
            displayed = "At least 12" if count == 12 else str(count)
            category = f" matching {plan.category.replace('_', ' ')}" if plan.category else ""
            window_label = "in the selected window" if request.start_time or request.end_time else f"in the last {plan.recent_days} days"
            answer.append(f"{displayed} eligible {'report' if count == 1 else 'reports'}{category} within {plan.radius_meters:,} m {window_label}.")
            answer.append("Local reporting may be incomplete.")
        return finish()

    if plan.intent in {"area", "heatmap"}:
        tool = tools.get_heatmap_explanation if plan.intent == "heatmap" else tools.get_area_safety
        area = run("heatmap" if plan.intent == "heatmap" else "area evidence", tool, place, request, plan, config, now)
        result.area = area
        if area:
            scope = f"{area.cell_size} m map cell" if area.cell else f"{area.radius_meters:,} m radius"
            result.evidence.append(EvidenceReference(
                kind="area", reference=area.cell.id if area.cell else f"radius:{area.radius_meters}", label=scope, as_of=area.generated_at,
            ))
            answer.append(f"For the {scope}, community risk is {indicator(area.security)} and road hazards are {indicator(area.road_hazards)}.")
            answer.append("Scores reflect historical eligible reports and do not predict current or future conditions.")
    if plan.intent in {"area", "advisories"}:
        at = trip_departure(plan, None, now, config)
        zones = run("official advisories", tools.get_official_advisories, place, request, plan, at)
        if zones is not None:
            cite_zones(zones)
            if zones:
                answer.append(f"{len(zones)} stored advisories matched within {plan.radius_meters:,} m for {at.astimezone(ZoneInfo(config.heatmap_timezone)):%d %b %H:%M %Z}. Check the source before travelling.")
            else:
                answer.append("No stored advisories matched the location and time. Official coverage may be incomplete.")
    return finish()
