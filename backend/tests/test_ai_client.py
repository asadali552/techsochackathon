import json
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from app.ai.client import AnalysisFailure, ChatClassifier, configured_classifier, validate_output
from app.core.config import Settings
from app.schemas.incident_analysis import Classification
from app.services.incident_evidence import assess_evidence, find_duplicates

SUGGESTION = {
    "language": "en", "category": "theft", "subcategory": "mobile_snatching",
    "severity": 3, "entities": ["mobile"], "mentioned_time": None, "mentioned_location": None,
    "summary": "The reporter described a mobile phone snatching.",
    "classification_confidence": 0.86, "requires_review": True,
}


@pytest.fixture
def classifier(monkeypatch):
    original = httpx.Client
    monkeypatch.setattr("app.ai.client.time.sleep", lambda _: None)

    def setup(handler):
        monkeypatch.setattr("app.ai.client.httpx.Client",
                            lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
        return ChatClassifier("openai_compatible", "test-model", "https://test.invalid/v1", "fake-key", 5)
    return setup


@pytest.mark.parametrize(("description", "language", "entities", "location"), [
    ("Someone snatched my mobile near the market.", "en", ["mobile"], "market"),
    ("بازار کے قریب میرا موبائل چھین لیا گیا۔", "ur", ["موبائل"], "بازار"),
    ("Gulgasht ke paas mera mobile snatch hogaya.", "roman_ur", ["mobile"], "Gulgasht"),
])
def test_multilingual_request_and_validated_taxonomy(classifier, description, language, entities, location):
    def respond(request):
        body = json.loads(request.content)
        assert request.headers["Authorization"] == "Bearer fake-key"
        assert body["response_format"] == {"type": "json_object"}
        assert json.loads(body["messages"][1]["content"])["description"] == description
        assert "untrusted" in body["messages"][0]["content"]
        content = json.dumps({**SUGGESTION, "language": language, "entities": entities, "mentioned_location": location})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {"total_tokens": 100}})

    result = classifier(respond).classify(description)
    assert (result.category, result.language, result.mentioned_location, result.mentioned_time) == ("theft", language, location, None)


@pytest.mark.parametrize("change", [
    {"category": "burgled"}, {"severity": 6}, {"severity": 0}, {"severity": "3"},
    {"classification_confidence": 1.01}, {"requires_review": False},
    {"verification_status": "verified"}, {"entities": ["invented object"]},
    {"mentioned_location": "Gulgasht"}, {"mentioned_time": "21:00"},
])
def test_invalid_structured_fields_or_fabricated_mentions(change):
    with pytest.raises((ValidationError, AnalysisFailure)):
        validate_output(json.dumps({**SUGGESTION, **change}), "My mobile was snatched.")


def test_verbatim_time_and_location():
    result = validate_output(json.dumps({
        **SUGGESTION, "mentioned_time": "9 pm", "mentioned_location": "Gulgasht",
    }), "My mobile was snatched at 9 pm near Gulgasht.")
    assert (result.mentioned_time, result.mentioned_location) == ("9 pm", "Gulgasht")
    with pytest.raises(AnalysisFailure):
        validate_output(json.dumps({**SUGGESTION, "mentioned_time": "Gulgasht"}), "My mobile was snatched near Gulgasht.")


@pytest.mark.parametrize(("failure", "error_code", "requests"), [
    ("timeout", "provider_timeout", 2), (503, "provider_unavailable", 2),
    (401, "provider_unavailable", 1), ("invalid", "invalid_output", 1),
])
def test_provider_failures_and_bounded_retry(classifier, caplog, failure, error_code, requests):
    attempts = 0

    def respond(request):
        nonlocal attempts
        attempts += 1
        content = json.loads(json.loads(request.content)["messages"][1]["content"])["description"]
        assert "0300-1234567" not in content and "person@example.com" not in content
        if failure == "timeout":
            raise httpx.ReadTimeout("private details", request=request)
        if failure == "invalid":
            return httpx.Response(200, json={"choices": [{"message": {"content": None}}]})
        return httpx.Response(failure, text="sensitive provider diagnostic")

    with pytest.raises(AnalysisFailure) as exc:
        classifier(respond).classify("mobile stolen; 0300-1234567 person@example.com")
    assert exc.value.code == error_code
    assert attempts == requests
    assert "fake-key" not in caplog.text and "private details" not in caplog.text
    assert "person@example.com" not in caplog.text and "sensitive provider diagnostic" not in caplog.text


@pytest.mark.parametrize("description", [" \n", "person@example.com"])
def test_missing_description_avoids_provider(classifier, description):
    def unexpected(_request):
        pytest.fail("No description should reach the provider")
    with pytest.raises(AnalysisFailure, match="missing_description"):
        classifier(unexpected).classify(description)


def test_missing_config_and_insecure_endpoint():
    assert configured_classifier(Settings(_env_file=None, llm_api_key=None, llm_model=None)) is None
    assert configured_classifier(Settings(
        _env_file=None, llm_provider="openai_compatible", llm_model="test",
        llm_api_key="fake", llm_base_url="http://test.invalid/v1",
    )) is None


def test_duplicates_and_evidence_exclude_nearby_independent_incident():
    analysis = Classification.model_validate({**SUGGESTION, "mentioned_time": "23:00"})
    rows = [
        {"id": uuid4(), "description": "mobile snatched near bazaar", "entities": ["mobile"],
         "category": "theft", "suggested_category": None, "distance_m": 30, "seconds_apart": 60, "other_account": True},
        {"id": uuid4(), "description": "motorcycle skidded at an intersection", "entities": None,
         "category": "road_accident", "suggested_category": None, "distance_m": 10, "seconds_apart": 60, "other_account": True},
    ]
    matches = find_duplicates("Phone snatch near market", analysis, rows)
    assert [item.incident_id for item in matches] == [rows[0]["id"]]
    assert set(matches[0].reasons) == {"text_overlap", "shared_entities", "same_category", "within_100m", "within_20_minutes"}
    evidence = assess_evidence({
        "category": "other", "has_evidence_link": True, "review_status": "pending",
        "occurred_at": datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
    }, analysis, matches, rows, "Asia/Karachi")
    assert evidence.corroboration == "potential_related_reports"
    assert evidence.related_reports_from_other_accounts == 1
    assert "evidence_link_uninspected" in evidence.evidence_available
    assert "confirmed_independent_corroboration" in evidence.evidence_missing
    assert evidence.potential_inconsistencies == ["category_disagreement", "mentioned_time_differs"]
