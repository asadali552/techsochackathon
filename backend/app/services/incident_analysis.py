import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb

from app.ai.client import AnalysisFailure, configured_classifier
from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.incident_analysis import IncidentAnalysis, ModerationAnalysis, Suggestion
from app.services.incident_evidence import assess_evidence, find_duplicates, nearby_candidates

logger = logging.getLogger(__name__)
LEASE_SECONDS = 120


def read_report(db: Connection[DictRow], incident_id: UUID, actor: UUID, moderator: bool) -> DictRow:
    row = db.execute("""
        SELECT i.id, i.category, i.description, i.occurred_at, i.evidence_url IS NOT NULL AS has_evidence_link,
               i.verification_status AS review_status,
               a.status, a.provider, a.model, a.result, a.processing_error,
               a.attempts, a.started_at, a.completed_at
        FROM public.incidents AS i
        LEFT JOIN public.incident_ai_analysis AS a ON a.incident_id = i.id
        WHERE i.id = %s AND (i.user_id = %s OR %s)
    """, (incident_id, actor, moderator)).fetchone()
    if row is None:
        raise ApiError(404, "not_found", "Incident not found")
    return row


def view_analysis(row: DictRow, moderator: bool) -> IncidentAnalysis:
    details = ModerationAnalysis.model_validate(row["result"]) if row["result"] else None
    suggestion = Suggestion.model_validate(details.classification.model_dump(
        include=set(Suggestion.model_fields)
    )) if details else None
    status = row["status"] or "not_started"
    error = row["processing_error"]
    if status == "processing" and row["started_at"] < datetime.now(UTC) - timedelta(seconds=LEASE_SECONDS):
        status, error = "failed", "processing_interrupted"
    return IncidentAnalysis(
        incident_id=row["id"], status=status, review_status=row["review_status"],
        suggestion=suggestion, moderation=details if moderator else None,
        provider=row["provider"], model=row["model"], attempts=row["attempts"] or 0,
        started_at=row["started_at"], completed_at=row["completed_at"], processing_error=error,
    )


def get_analysis(db: Connection[DictRow], incident_id: UUID, actor: UUID, config: Settings) -> IncidentAnalysis:
    moderator = actor in config.llm_moderator_ids
    return view_analysis(read_report(db, incident_id, actor, moderator), moderator)


def analyze_incident(db: Connection[DictRow], incident_id: UUID, actor: UUID, config: Settings) -> IncidentAnalysis:
    moderator = actor in config.llm_moderator_ids
    incident = read_report(db, incident_id, actor, moderator)
    if incident["status"] == "completed":
        return view_analysis(incident, moderator)
    if incident["review_status"] == "rejected":
        raise ApiError(409, "report_rejected", "A rejected report cannot be processed")

    classifier = configured_classifier(config)
    provider, model = (classifier.provider, classifier.model) if classifier else (None, None)
    run_id = uuid4()
    claim = db.execute("""
        INSERT INTO public.incident_ai_analysis
            (incident_id, status, run_id, provider, model, attempts, started_at)
        VALUES (%s, 'processing', %s, %s, %s, 1, clock_timestamp())
        ON CONFLICT (incident_id) DO UPDATE
        SET status = 'processing', run_id = EXCLUDED.run_id, provider = EXCLUDED.provider,
            model = EXCLUDED.model, attempts = public.incident_ai_analysis.attempts + 1,
            started_at = EXCLUDED.started_at, completed_at = NULL, processing_error = NULL
        WHERE public.incident_ai_analysis.status IN ('failed', 'unavailable')
           OR (public.incident_ai_analysis.status = 'processing'
               AND public.incident_ai_analysis.started_at < clock_timestamp() - make_interval(secs => %s))
        RETURNING run_id
    """, (incident_id, run_id, provider, model, LEASE_SECONDS)).fetchone()
    if claim is None:
        return get_analysis(db, incident_id, actor, config)

    candidates = nearby_candidates(db, incident_id) if classifier and incident["description"].strip() else []
    # Commit the claim and release transaction locks before contacting the provider.
    db.commit()

    result = None
    error = None
    status = "completed"
    try:
        if classifier is None:
            raise AnalysisFailure("provider_not_configured")
        if not incident["description"].strip():
            raise AnalysisFailure("missing_description")
        classification = classifier.classify(incident["description"])
        matches = find_duplicates(incident["description"], classification, candidates)
        result = ModerationAnalysis(
            classification=classification, duplicate_candidates=matches,
            assessment=assess_evidence(incident, classification, matches, candidates, config.heatmap_timezone),
        )
    except AnalysisFailure as exc:
        error = exc.code
        status = "unavailable" if error == "provider_not_configured" else "failed"
        logger.info("incident_analysis outcome=%s code=%s", status, error)

    db.execute("SET LOCAL TIME ZONE 'UTC'")
    db.execute("""
        UPDATE public.incident_ai_analysis
        SET status = %s, result = %s, processing_error = %s, completed_at = clock_timestamp()
        WHERE incident_id = %s AND run_id = %s AND status = 'processing'
    """, (status, Jsonb(result.model_dump(mode="json")) if result else None, error, incident_id, run_id))
    # Preserve the audit result even if moderation changed ownership while the model was working.
    db.commit()
    return get_analysis(db, incident_id, actor, config)
