import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest

from app.ai.client import AnalysisFailure
from app.core import security
from app.core.config import Settings, get_settings
from app.main import app
from app.schemas.incident_analysis import Classification

DESCRIPTION = "My mobile was snatched near the market."
SUGGESTION = {
    "language": "en", "category": "theft", "subcategory": "mobile_snatching",
    "severity": 4, "entities": ["mobile"], "mentioned_time": None, "mentioned_location": "market",
    "summary": "The reporter described mobile phone snatching.",
    "classification_confidence": 0.83, "requires_review": True,
}
API = "/api/ai/incidents"


def request(method, path, actor=None, **kwargs):
    async def send():
        headers = {"Authorization": f"Bearer {actor}"} if actor else {}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver",
        ) as client:
            return await client.request(method, path, headers=headers, **kwargs)
    return asyncio.run(send())


@pytest.mark.parametrize(("method", "action"), [("GET", "analysis"), ("POST", "analyze")])
def test_authentication_is_required(method, action):
    assert request(method, f"{API}/{uuid4()}/{action}").status_code == 401


@pytest.fixture
def demo(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    owner_id = os.getenv("TEST_AUTH_USER_ID")
    if not url or not owner_id:
        pytest.skip("Set TEST_DATABASE_URL and TEST_AUTH_USER_ID for a dedicated PostGIS test database")
    owner = UUID(owner_id)
    moderator, outsider = uuid4(), uuid4()
    config = Settings(
        _env_file=None, database_url=url, supabase_url="https://auth.example.test", supabase_anon_key="stub",
        llm_api_key="test-only", llm_provider="openai_compatible", llm_model="test-model",
        llm_base_url="https://ai.example.test/v1", llm_moderator_ids={moderator},
    )
    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_settings] = lambda: config

    def auth(_url, *, headers, timeout):
        assert timeout == 5
        return httpx.Response(200, json={"id": headers["Authorization"].removeprefix("Bearer ")})

    monkeypatch.setattr(security.httpx, "get", auth)
    created = []
    timestamp = (datetime.now(UTC) - timedelta(minutes=8)).isoformat()

    def create(description=DESCRIPTION, category="theft", longitude=70.123, latitude=29.123):
        response = request("POST", "/api/incidents", owner, json={
            "description": description, "category": category, "longitude": longitude,
            "latitude": latitude, "occurred_at": timestamp,
        })
        assert response.status_code == 201, response.text
        report_id = response.json()["data"]["id"]
        created.append(report_id)
        return report_id

    def db_query(sql, params=()):
        with psycopg.connect(url, prepare_threshold=None) as db:
            cursor = db.execute(sql, params)
            return cursor.fetchone() if cursor.description else None

    yield config, owner, moderator, outsider, create, db_query
    app.dependency_overrides.clear()
    app.dependency_overrides.update(overrides)
    db_query("DELETE FROM public.incidents WHERE id = ANY(%s::uuid[])", (created,))


def test_owner_moderator_boundaries_persistence_and_heatmap(demo, monkeypatch):
    _, owner, moderator, outsider, create, db_query = demo
    target = create(category="other")
    duplicate = create("My phone was snatched near the bazaar.", longitude=70.1232)
    unrelated = create("A motorcycle hit a curb near the market.", category="road_accident", longitude=70.1231)
    distant = create(longitude=70.13)
    original = db_query("""
        SELECT category, description, severity, latitude, longitude, occurred_at, verification_status, public_summary, credibility_score
        FROM public.incidents WHERE id = %s
    """, (target,))
    assert request("GET", f"{API}/{target}/analysis", owner).json()["data"]["status"] == "not_started"
    assert request("POST", f"{API}/{target}/analyze", outsider).status_code == 404
    assert request("GET", f"{API}/{target}/analysis", outsider).status_code == 404
    assert request("GET", f"{API}/bad-id/analysis", owner).status_code == 422
    original_client = httpx.Client
    calls = []

    def provider(req):
        calls.append(req.url)
        assert json.loads(json.loads(req.content)["messages"][1]["content"]) == {"description": DESCRIPTION}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(SUGGESTION)}}]})

    monkeypatch.setattr("app.ai.client.httpx.Client", lambda **kw: original_client(transport=httpx.MockTransport(provider), **kw))
    response = request("POST", f"{API}/{target}/analyze", owner)
    assert response.status_code == 200, response.text
    assert response.headers["Cache-Control"] == "no-store"
    owner_view = response.json()["data"]
    assert owner_view["status"] == "completed" and owner_view["review_status"] == "pending"
    assert owner_view["suggestion"]["severity"] == 4 and owner_view["moderation"] is None
    assert duplicate not in response.text and unrelated not in response.text and distant not in response.text
    assert request("POST", f"{API}/{target}/analyze", owner).json()["data"] == owner_view
    assert len(calls) == 1

    moderation = request("GET", f"{API}/{target}/analysis", moderator).json()["data"]["moderation"]
    assert [item["incident_id"] for item in moderation["duplicate_candidates"]] == [duplicate]
    assert moderation["classification"]["mentioned_location"] == "market"
    assert moderation["assessment"]["related_reports_from_other_accounts"] == 0
    assert moderation["assessment"]["potential_inconsistencies"] == ["category_disagreement"]
    assert moderation["assessment"]["corroboration"] == "potential_related_reports"
    assert db_query("""
        SELECT category, description, severity, latitude, longitude, occurred_at, verification_status, public_summary, credibility_score
        FROM public.incidents WHERE id = %s
    """, (target,)) == original
    assert request("GET", f"/api/incidents/{target}").status_code == 404
    result = request("GET", "/api/heatmap", params={"bbox": "70.11,29.11,70.14,29.14"})
    assert result.status_code == 200, result.text
    assert all(cell["properties"]["security"]["report_count"] == 0 for cell in result.json()["data"]["cells"]["features"])
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db_query("SET ROLE authenticated; SELECT result FROM public.incident_ai_analysis")


class ControlledClassifier:
    provider = "openai_compatible"
    model = "test-model"

    def __init__(self, run):
        self.run = run

    def classify(self, _description):
        self.run()
        return Classification.model_validate(SUGGESTION)


def test_unavailable_failure_and_retry_keep_report(demo, monkeypatch):
    config, owner, _, _, create, db_query = demo
    target = create()
    config.llm_api_key = None
    first = request("POST", f"{API}/{target}/analyze", owner)
    assert first.status_code == 200, first.text
    assert (first.json()["data"]["status"], first.json()["data"]["processing_error"]) == ("unavailable", "provider_not_configured")

    def timeout():
        raise AnalysisFailure("provider_timeout")

    monkeypatch.setattr("app.services.incident_analysis.configured_classifier", lambda _: ControlledClassifier(timeout))
    failed = request("POST", f"{API}/{target}/analyze", owner).json()["data"]
    assert (failed["status"], failed["processing_error"], failed["attempts"]) == ("failed", "provider_timeout", 2)
    monkeypatch.setattr("app.services.incident_analysis.configured_classifier", lambda _: ControlledClassifier(lambda: None))
    success = request("POST", f"{API}/{target}/analyze", owner).json()["data"]
    assert success["status"] == "completed" and success["attempts"] == 3
    assert db_query("SELECT description, verification_status FROM public.incidents WHERE id = %s", (target,)) == (DESCRIPTION, "pending")


def test_concurrent_analyze_requests_share_one_claim(demo, monkeypatch):
    _, owner, _, _, create, _ = demo
    target = create()
    started, release = Event(), Event()

    def hold():
        started.set()
        assert release.wait(8)

    monkeypatch.setattr("app.services.incident_analysis.configured_classifier", lambda _: ControlledClassifier(hold))
    with ThreadPoolExecutor(max_workers=1) as pool:
        job = pool.submit(request, "POST", f"{API}/{target}/analyze", owner)
        try:
            assert started.wait(5)
            second = request("POST", f"{API}/{target}/analyze", owner)
            assert second.status_code == 202, second.text
            assert second.json()["data"]["attempts"] == 1
            assert request("GET", f"{API}/{target}/analysis", owner).json()["data"]["status"] == "processing"
        finally:
            release.set()
        assert job.result(timeout=5).json()["data"]["status"] == "completed"
