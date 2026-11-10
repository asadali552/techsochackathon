import re
from uuid import UUID
from zoneinfo import ZoneInfo

from psycopg import Connection
from psycopg.rows import DictRow

from app.ai.client import normalize, redact
from app.schemas.incident_analysis import Classification, DuplicateCandidate, EvidenceAssessment

RADIUS_METERS = 350
WINDOW_SECONDS = 90 * 60
ALIASES = {
    "mobile": "phone", "mobail": "phone", "موبائل": "phone", "فون": "phone",
    "snatched": "snatch", "snatching": "snatch", "cheen": "snatch", "چھین": "snatch",
    "bazaar": "market", "bazar": "market", "بازار": "market",
    "bike": "motorcycle", "motorbike": "motorcycle", "موٹرسائیکل": "motorcycle",
}
STOP = set("a an the was were is my mein me near to at ke ka ki paas se hogaya gaya کے کی قریب میرا گیا".split())


def words(text: str) -> set[str]:
    return {
        ALIASES.get(token, token)
        for token in re.findall(r"[^\W_]+", normalize(redact(text)))
        if token not in STOP and token != "redacted" and len(token) > 1
    }


def nearby_candidates(db: Connection[DictRow], incident_id: UUID) -> list[DictRow]:
    return db.execute("""
        SELECT other.id, other.description, other.category,
               (other.user_id IS NOT NULL AND target.user_id IS NOT NULL
                    AND other.user_id <> target.user_id) AS other_account,
               ST_Distance(other.location, target.location) AS distance_m,
               abs(extract(epoch FROM (other.occurred_at - target.occurred_at))) AS seconds_apart,
               analysis.result -> 'classification' ->> 'category' AS suggested_category,
               analysis.result -> 'classification' -> 'entities' AS entities
        FROM public.incidents AS target
        JOIN public.incidents AS other
          ON other.id <> target.id AND other.is_demo = target.is_demo
         AND other.verification_status <> 'rejected'
         AND other.occurred_at BETWEEN target.occurred_at - interval '90 minutes'
                                   AND target.occurred_at + interval '90 minutes'
         AND ST_DWithin(other.location, target.location, %s)
        LEFT JOIN public.incident_ai_analysis AS analysis
          ON analysis.incident_id = other.id AND analysis.status = 'completed'
        WHERE target.id = %s
        ORDER BY distance_m, seconds_apart, other.id
        LIMIT 50
    """, (RADIUS_METERS, incident_id)).fetchall()


def find_duplicates(description: str, analysis: Classification, candidates: list[DictRow]) -> list[DuplicateCandidate]:
    terms = words(description)
    entities = words(" ".join(analysis.entities))
    matches = []
    for candidate in candidates:
        other = words(candidate["description"])
        union = terms | other
        overlap = len(terms & other) / len(union) if union else 0
        other_entities = words(" ".join(candidate["entities"] or [])) or other
        shared = entities & other_entities
        same_category = analysis.category in (candidate["category"], candidate["suggested_category"])
        distance = float(candidate["distance_m"])
        seconds = float(candidate["seconds_apart"])
        similarity = (
            0.45 * overlap + 0.10 * bool(shared) + 0.15 * same_category
            + 0.15 * max(0, 1 - distance / RADIUS_METERS)
            + 0.15 * max(0, 1 - seconds / WINDOW_SECONDS)
        )
        if similarity < 0.62 or overlap < 0.20:
            continue
        reasons = ["text_overlap"]
        if shared:
            reasons.append("shared_entities")
        if same_category:
            reasons.append("same_category")
        if distance <= 100:
            reasons.append("within_100m")
        if seconds <= 20 * 60:
            reasons.append("within_20_minutes")
        matches.append(DuplicateCandidate(
            incident_id=candidate["id"], similarity=round(similarity, 3), reasons=reasons,
        ))
    return sorted(matches, key=lambda match: (-match.similarity, match.incident_id))[:5]


def assess_evidence(
    incident: DictRow, analysis: Classification, matches: list[DuplicateCandidate], candidates: list[DictRow],
    timezone: str,
) -> EvidenceAssessment:
    available = ["description", "submitted_location", "submitted_time"]
    missing = []
    if incident["has_evidence_link"]:
        available.append("evidence_link_uninspected")
    else:
        missing.append("supporting_attachment")

    ids = {match.incident_id for match in matches}
    other_accounts = sum(bool(row["other_account"]) for row in candidates if row["id"] in ids)
    status = incident["review_status"]
    corroboration = {
        "verified": "moderator_verified", "corroborated": "moderator_corroborated",
    }.get(status, "potential_related_reports" if matches else "none_identified")
    if status not in ("verified", "corroborated"):
        missing.append("confirmed_independent_corroboration")

    inconsistencies = []
    if incident["category"] != analysis.category:
        inconsistencies.append("category_disagreement")
    clock = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", analysis.mentioned_time or "", flags=re.ASCII)
    if clock:
        local = incident["occurred_at"].astimezone(ZoneInfo(timezone))
        minutes = abs(local.hour * 60 + local.minute - int(clock[1]) * 60 - int(clock[2]))
        if min(minutes, 1440 - minutes) > 90:
            inconsistencies.append("mentioned_time_differs")

    return EvidenceAssessment(
        evidence_available=available, evidence_missing=missing, potential_inconsistencies=inconsistencies,
        completeness="essential_fields_present", corroboration=corroboration,
        related_reports_from_other_accounts=other_accounts,
    )
