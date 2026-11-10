import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.assistant import interpret, places, session, tools
from app.core.config import Settings, get_settings
from app.main import app

NOW = datetime(2026, 11, 11, 10, tzinfo=UTC)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(session, "_sessions", {})
    monkeypatch.setattr(session, "_rate", {})
    config = Settings(_env_file=None)
    app.dependency_overrides[get_settings] = lambda: config
    with TestClient(app) as http:
        yield http, config
    app.dependency_overrides.pop(get_settings, None)


def ask(http, message, **options):
    response = http.post("/api/ai/chat", json={"mode": "demo", "message": message, **options})
    assert response.status_code == 200, response.json()
    assert response.headers["Cache-Control"] == "no-store"
    return response.json()["data"]


@pytest.mark.parametrize(("question", "intent"), [
    ("Is Gulgasht safe to visit tonight?", "area"),
    ("Have there been any recent robberies near Multan Cantt?", "incidents"),
    ("Plan my trip from Multan to Lahore tomorrow.", "journey"),
    ("Why is this region coloured red?", "heatmap"),
    ("What about travelling at night?", "journey"),
    ("Which available route has fewer recent incident reports?", "compare"),
    ("Are there any reported road closures along my route?", "compare"),
])
def test_guided_intents(question, intent):
    assert interpret.guided_plan(question, has_trip=intent in {"journey", "compare"}, has_area=False).intent == intent


def test_model_plan_validates_literals_and_ignores_generated_prose(monkeypatch):
    config = Settings(llm_api_key="test", llm_model="test", _env_file=None)
    outputs = iter([
        {"intent": "area", "place": "Multan"}, {"intent": "area", "place": "Invented"},
        {"intent": "area", "place": "Multan", "answer": "Guaranteed safe"},
    ])

    def respond(*args, **kwargs):
        assert kwargs["json"]["max_completion_tokens"] == config.assistant_max_output_tokens
        return httpx.Response(200, request=httpx.Request("POST", args[0]), json={
            "choices": [{"message": {"content": json.dumps(next(outputs))}}],
        })

    monkeypatch.setattr(interpret.httpx, "post", respond)
    assert interpret.model_plan("Is Multan safe?", config, {}, NOW).intent == "area"
    assert interpret.model_plan("Is Multan safe?", config, {}, NOW) is None
    assert interpret.model_plan("Is Multan safe?", config, {}, NOW) is None


def test_owner_mode_expiry_and_clear(client, monkeypatch):
    http, _ = client
    assert http.post("/api/ai/chat", json={"message": "hello"}).status_code == 401
    opened = ask(http, "hello")
    key = opened["conversation_id"]
    assert http.post("/api/ai/chat/clear", json={"mode": "demo", "conversation_id": str(uuid4())}).status_code == 404
    from app.api import assistant
    with monkeypatch.context() as patch:
        patch.setattr(assistant, "owner", lambda *args: "another-user")
        assert http.post("/api/ai/chat", json={"mode": "demo", "conversation_id": key, "message": "hello"}).status_code == 404
    assert http.post("/api/ai/chat/clear", json={"mode": "demo", "conversation_id": key}).status_code == 200
    assert http.post("/api/ai/chat", json={"mode": "demo", "conversation_id": key, "message": "hello"}).status_code == 404


def test_unknown_place_and_unavailable_optional_tools(client):
    http, _ = client
    result = ask(http, "Is Fictionalville safe?")
    assert not result["places"]
    assert result["unavailable_sources"] == ["geocoding"]
    weather = ask(http, "What's the weather near Multan?")
    assert "weather" in weather["unavailable_sources"]


def test_pakistan_geocoding_cache_and_clarification(client, monkeypatch):
    http, config = client
    config.geocoding_service_url = "https://places.example.test"
    monkeypatch.setattr(places, "_cache", {})
    monkeypatch.setattr(places, "_last_request", 0)
    calls = []

    def respond(url, **kwargs):
        calls.append(kwargs["params"])
        return httpx.Response(200, request=httpx.Request("GET", url), json=[
            {"display_name": "Example, Punjab", "lat": 31, "lon": 72},
            {"display_name": "Example, Sindh", "lat": 26, "lon": 68},
        ])

    monkeypatch.setattr(places.httpx, "get", respond)
    answer = ask(http, "Is Example safe?")
    assert len(answer["choices"]) == 2
    assert not answer["evidence"]
    chosen = ask(http, "2", conversation_id=answer["conversation_id"])
    assert chosen["places"][0]["label"] == "Example, Sindh"
    assert len(places.resolve("Example", config)) == 2
    assert len(calls) == 1 and calls[0]["countrycodes"] == "pk"


@pytest.fixture
def postgis(client):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL for a seeded PostGIS database")
    http, config = client
    config.database_url = Settings(database_url=url).database_url
    return http, config


def test_real_heatmap_area_and_public_incidents(postgis):
    http, _ = postgis
    result = ask(http, "Is Multan safe?", period="full_day")
    assert result["area"]["radius_meters"] == 1500
    assert result["area"]["cell"] is None
    assert result["evidence"][0]["kind"] == "area"
    assert not result["unavailable_sources"]
    result = ask(http, "Why is this cell red?", location={"type": "Point", "coordinates": [71.475, 30.196]}, cell_size=750)
    assert result["area"]["cell_size"] == 750
    cell = result["area"]["cell"]
    assert cell["properties"]["security"] == result["area"]["security"]
    result = ask(http, "Have there been recent theft reports near Ghanta Ghar?")
    assert not result["unavailable_sources"]
    assert result["incident_window"]
    assert result["incidents"]
    assert all(item["verification_status"] != "pending" and item["is_demo"] and item["category"] == "theft"
               and "user_id" not in item for item in result["incidents"])


def test_route_chain_follow_up_and_partial_failure(postgis, monkeypatch):
    from app.routing import comparison
    from app.schemas.routes import RouteLine

    http, _ = postgis
    calls = []

    def provider(query, config):
        calls.append(query)
        return [RouteLine(distance_m=3800, duration_s=340, geometry={"type": "LineString",
                          "coordinates": [[71.467842, 30.198803], [71.4446, 30.1804]]})]

    monkeypatch.setattr(comparison, "fetch_routes", provider)
    first = ask(http, "Plan a trip from Ghanta Ghar to Multan Cantt")
    assert len(first["comparison"]["routes"]) == 1
    key = first["conversation_id"]
    again = ask(http, "Which route has fewer reports?", conversation_id=key)
    assert again["comparison"]["preference"] == "fewer_reported_incidents"
    assert len(calls) == 1
    night = ask(http, "What about travelling at night?", conversation_id=key)
    assert len(calls) == 2 and night["comparison"]
    assert calls[1].departure_at.hour == 17
    ambiguous = ask(http, "Plan a trip from Islamabad to Hunza")
    assert len(ambiguous["choices"]) == 2
    chosen = ask(http, "1", conversation_id=ambiguous["conversation_id"])
    assert chosen["places"][0]["label"] == "Islamabad, Pakistan"
    assert chosen["places"][1]["label"] == "Karimabad, Hunza"

    from app.core.errors import ApiError
    def outage(*_):
        raise ApiError(503, "database_unavailable", "Evidence temporarily unavailable")

    monkeypatch.setattr(tools, "compare_route_risks", outage)
    partial = ask(http, "Plan a trip from Ghanta Ghar to Multan Cantt")
    assert partial["route_options"]["routes"] and partial["comparison"] is None
    assert partial["unavailable_sources"] == ["route evidence"]


def test_gemini_demo_opt_in_and_fallback(client, monkeypatch):
    http, config = client
    config.gemini_api_key = Settings(gemini_api_key="test", _env_file=None).gemini_api_key
    requests = []

    def respond(url, **kwargs):
        requests.append(kwargs["json"])
        assert url == f"https://generativelanguage.googleapis.com/v1beta/models/{config.gemini_model}:generateContent"
        assert kwargs["headers"] == {"x-goog-api-key": "test"}
        assert kwargs["json"]["generationConfig"]["maxOutputTokens"] == config.assistant_max_output_tokens
        assert kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"
        if len(requests) > 1:
            return httpx.Response(429, request=httpx.Request("POST", url))
        return httpx.Response(200, request=httpx.Request("POST", url), json={"candidates": [{
            "finishReason": "STOP",
            "content": {"parts": [{"thought": True, "text": "hidden"}, {"text": '{"intent":"clarify"}'}]},
        }]})

    monkeypatch.setattr(interpret.httpx, "post", respond)
    assert ask(http, "Where can I travel?")["interpretation"] == "guided"
    assert requests == []
    config.assistant_gemini_in_demo = True
    assert ask(http, "Where can I travel?")["interpretation"] == "model"
    assert ask(http, "Where can I travel?")["interpretation"] == "guided"
    assert ask(http, "Is 30.19, 71.47 safe?")["interpretation"] == "guided"
    assert len(requests) == 2
