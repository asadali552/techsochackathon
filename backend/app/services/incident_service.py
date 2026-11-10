from uuid import UUID

from psycopg import Connection, sql
from psycopg.rows import DictRow

from app.core.errors import ApiError
from app.schemas.common import Mode
from app.schemas.incident import IncidentCreate
from app.services.geospatial_service import INCIDENT_FIELDS, PUBLIC_REPORTS


def create_incident(db: Connection[DictRow], user_id: UUID, incident: IncidentCreate) -> DictRow:
    # Serialize the account's submissions so concurrent requests cannot bypass the limit.
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 73941))", (str(user_id),))
    rate = db.execute("""
        SELECT EXISTS (
            SELECT 1 FROM public.incidents
            WHERE user_id = %s AND created_at > statement_timestamp() - interval '1 hour'
            OFFSET 9
        ) AS limited
    """, (user_id,)).fetchone()
    if rate and rate["limited"]:
        raise ApiError(429, "incident_rate_limited", "Too many reports. Try again in an hour.")

    db.execute("INSERT INTO public.profiles (id) VALUES (%s) ON CONFLICT (id) DO NOTHING", (user_id,))
    statement = sql.SQL("""
        INSERT INTO public.incidents (user_id, category, description, latitude, longitude, occurred_at)
        VALUES (%(user_id)s, %(category)s, %(description)s, %(latitude)s, %(longitude)s, %(occurred_at)s)
        RETURNING {}
    """).format(INCIDENT_FIELDS)
    row = db.execute(statement, {"user_id": user_id, **incident.model_dump()}).fetchone()
    assert row is not None
    return row


def get_public_incident(db: Connection[DictRow], incident_id: UUID, mode: Mode) -> DictRow | None:
    statement = sql.SQL("""
        SELECT {fields} FROM public.incidents WHERE {visible} AND id = %(incident_id)s
    """).format(fields=INCIDENT_FIELDS, visible=PUBLIC_REPORTS)
    return db.execute(statement, {"incident_id": incident_id, "is_demo": mode == "demo"}).fetchone()
