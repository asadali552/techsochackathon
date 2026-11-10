BEGIN;

CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA extensions;

-- Respect the existing PostGIS schema on Supabase.
SELECT pg_catalog.set_config('search_path', pg_catalog.format('pg_catalog, %I', n.nspname), true)
FROM pg_catalog.pg_extension AS e
JOIN pg_catalog.pg_namespace AS n ON n.oid = e.extnamespace
WHERE e.extname = 'postgis';

-- Upgrade Phase 0 tables in place. The old owner column identifies the original schema.
DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'incidents' AND column_name = 'reporter_id'
    ) THEN
        ALTER TABLE public.profiles
            ADD COLUMN display_name text CHECK (char_length(btrim(display_name)) BETWEEN 1 AND 80),
            ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now();
        INSERT INTO public.profiles (id)
        SELECT DISTINCT reporter_id FROM public.incidents WHERE reporter_id IS NOT NULL
        ON CONFLICT (id) DO NOTHING;

        ALTER TABLE public.incidents
            DROP CONSTRAINT incidents_reporter_id_fkey,
            DROP CONSTRAINT incidents_category_check,
            DROP CONSTRAINT incidents_verification_status_check,
            ADD COLUMN latitude double precision,
            ADD COLUMN longitude double precision,
            ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
            ADD COLUMN credibility_score numeric NOT NULL DEFAULT 0 CHECK (credibility_score BETWEEN 0 AND 1),
            ADD COLUMN evidence_url text CHECK (evidence_url ~ '^https://[^[:space:]]+$');
        UPDATE public.incidents
        SET latitude = ST_Y(location::geometry), longitude = ST_X(location::geometry),
            category = CASE category
                WHEN 'theft_snatching' THEN 'theft'
                WHEN 'road_condition' THEN 'unsafe_road'
                WHEN 'other_hazard' THEN 'other'
                ELSE category
            END,
            verification_status = CASE verification_status
                WHEN 'unverified' THEN 'pending'
                ELSE verification_status
            END;
        ALTER TABLE public.incidents RENAME COLUMN reporter_id TO user_id;
        ALTER TABLE public.incidents RENAME COLUMN source_type TO source;
        ALTER TABLE public.incidents
            DROP COLUMN location,
            ADD FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE SET NULL;
        DROP INDEX IF EXISTS public.incidents_reporter_idx;

        ALTER TABLE public.official_zones DROP CONSTRAINT official_zones_zone_type_check;
        ALTER TABLE public.official_zones RENAME COLUMN title TO name;
        ALTER TABLE public.official_zones RENAME COLUMN summary TO description;
        ALTER TABLE public.official_zones RENAME COLUMN zone_type TO designation;
        ALTER TABLE public.official_zones RENAME COLUMN area TO geometry;
        ALTER TABLE public.official_zones RENAME COLUMN authority TO issuing_authority;
        ALTER TABLE public.official_zones RENAME COLUMN valid_from TO effective_from;
        ALTER TABLE public.official_zones RENAME COLUMN valid_until TO effective_until;
        ALTER TABLE public.official_zones RENAME COLUMN retrieved_at TO last_verified_at;
        ALTER TABLE public.official_zones
            ALTER COLUMN source_url DROP NOT NULL,
            ALTER COLUMN source_reference DROP NOT NULL,
            ALTER COLUMN issued_at DROP NOT NULL,
            ADD COLUMN is_demo boolean NOT NULL DEFAULT false,
            ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
        UPDATE public.official_zones SET designation = CASE designation
            WHEN 'restriction' THEN 'restricted'
            ELSE 'unsafe_advisory'
        END;
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS public.profiles (
    id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name text CHECK (char_length(btrim(display_name)) BETWEEN 1 AND 80),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.profiles ALTER COLUMN id SET DEFAULT auth.uid();

CREATE TABLE IF NOT EXISTS public.incidents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES public.profiles(id) ON DELETE SET NULL,
    category text NOT NULL,
    description text NOT NULL CHECK (char_length(btrim(description)) BETWEEN 1 AND 2000),
    public_summary text CHECK (char_length(btrim(public_summary)) BETWEEN 1 AND 500),
    latitude double precision NOT NULL,
    longitude double precision NOT NULL,
    occurred_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    severity smallint CHECK (severity BETWEEN 1 AND 5),
    credibility_score numeric NOT NULL DEFAULT 0 CHECK (credibility_score BETWEEN 0 AND 1),
    verification_status text NOT NULL,
    credibility_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(credibility_metadata) = 'object'),
    source text NOT NULL DEFAULT 'community' CHECK (source IN ('community', 'demo')),
    is_demo boolean NOT NULL DEFAULT false,
    evidence_url text CHECK (evidence_url ~ '^https://[^[:space:]]+$'),
    CHECK (is_demo = (source = 'demo')),
    CHECK (NOT is_demo OR user_id IS NULL),
    CHECK (occurred_at <= created_at)
);

ALTER TABLE public.incidents
    ALTER COLUMN user_id SET DEFAULT auth.uid(),
    ALTER COLUMN latitude SET NOT NULL,
    ALTER COLUMN longitude SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT statement_timestamp(),
    ALTER COLUMN verification_status SET DEFAULT 'pending',
    -- Preserve unknown severities on existing records. A new report starts at the scale floor.
    ALTER COLUMN severity SET DEFAULT 1,
    ADD COLUMN IF NOT EXISTS location geography(Point, 4326)
        GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED,
    ADD COLUMN IF NOT EXISTS public_location geography(Point, 4326)
        GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(
            round(longitude::numeric, 3)::double precision,
            round(latitude::numeric, 3)::double precision
        ), 4326)::geography) STORED,
    DROP CONSTRAINT IF EXISTS incidents_coordinates_check,
    ADD CONSTRAINT incidents_coordinates_check
        CHECK (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180),
    DROP CONSTRAINT IF EXISTS incidents_category_check,
    ADD CONSTRAINT incidents_category_check CHECK (category IN (
        'robbery', 'theft', 'harassment', 'suspicious_activity', 'road_accident',
        'unsafe_road', 'poor_lighting', 'landslide', 'road_closure', 'other'
    )),
    DROP CONSTRAINT IF EXISTS incidents_verification_status_check,
    ADD CONSTRAINT incidents_verification_status_check
        CHECK (verification_status IN ('pending', 'corroborated', 'verified', 'rejected'));

CREATE INDEX IF NOT EXISTS incidents_location_gix ON public.incidents USING gist (location);
CREATE INDEX IF NOT EXISTS incidents_public_radius_gix ON public.incidents USING gist (public_location);
CREATE INDEX IF NOT EXISTS incidents_public_bbox_gix ON public.incidents USING gist ((public_location::geometry));
CREATE INDEX IF NOT EXISTS incidents_occurred_idx ON public.incidents (is_demo, occurred_at DESC, id);
CREATE INDEX IF NOT EXISTS incidents_user_idx ON public.incidents (user_id);

CREATE TABLE IF NOT EXISTS public.official_zones (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL CHECK (btrim(name) <> ''),
    description text NOT NULL CHECK (btrim(description) <> ''),
    designation text NOT NULL,
    geometry geography(MultiPolygon, 4326) NOT NULL
        CHECK (NOT ST_IsEmpty(geometry::geometry) AND ST_IsValid(geometry::geometry)),
    issuing_authority text NOT NULL CHECK (btrim(issuing_authority) <> ''),
    source_url text CHECK (source_url ~ '^https://[^[:space:]]+$'),
    source_reference text CHECK (btrim(source_reference) <> ''),
    issued_at timestamptz,
    effective_from timestamptz NOT NULL,
    effective_until timestamptz,
    last_verified_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    is_demo boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issuing_authority, source_reference),
    CHECK (effective_until IS NULL OR effective_until > effective_from)
);

ALTER TABLE public.official_zones
    DROP CONSTRAINT IF EXISTS official_zones_designation_check,
    ADD CONSTRAINT official_zones_designation_check
        CHECK (designation IN ('restricted', 'unsafe_advisory', 'caution', 'road_closure')),
    DROP CONSTRAINT IF EXISTS official_zones_provenance_check,
    ADD CONSTRAINT official_zones_provenance_check CHECK (
        (is_demo AND issuing_authority = 'Fictional demo' AND source_url IS NULL)
        OR (NOT is_demo AND issuing_authority <> 'Fictional demo'
            AND source_url IS NOT NULL AND source_reference IS NOT NULL AND issued_at IS NOT NULL)
    );

CREATE INDEX IF NOT EXISTS official_zones_area_gix ON public.official_zones USING gist (geometry);
CREATE INDEX IF NOT EXISTS official_zones_bbox_gix ON public.official_zones USING gist ((geometry::geometry));

CREATE OR REPLACE FUNCTION public.set_updated_at() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
    NEW.updated_at := statement_timestamp();
    RETURN NEW;
END
$$;
CREATE OR REPLACE TRIGGER profiles_updated_at BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE OR REPLACE TRIGGER incidents_updated_at BEFORE UPDATE ON public.incidents
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.official_zones ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.profiles, public.incidents, public.official_zones FROM PUBLIC, anon, authenticated;
-- Column grants survive a table-level revoke. Clear any grants on private fields.
REVOKE SELECT (user_id, description, latitude, longitude, location, credibility_score,
               credibility_metadata, evidence_url, updated_at)
    ON public.incidents FROM PUBLIC, anon, authenticated;
-- Submit through FastAPI so the account rate limit and validation always apply.
REVOKE INSERT (display_name) ON public.profiles FROM authenticated;
REVOKE INSERT (category, description, latitude, longitude, occurred_at) ON public.incidents FROM authenticated;
GRANT SELECT ON public.profiles TO authenticated;
GRANT SELECT (id, category, public_summary, public_location, occurred_at, created_at,
              severity, verification_status, source, is_demo)
    ON public.incidents TO anon, authenticated;
GRANT SELECT (id, name, description, designation, geometry, issuing_authority, source_url,
              source_reference, effective_from, effective_until, last_verified_at, is_demo)
    ON public.official_zones TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.profiles, public.incidents, public.official_zones TO service_role;

DROP POLICY IF EXISTS profiles_owner_read ON public.profiles;
CREATE POLICY profiles_owner_read ON public.profiles FOR SELECT TO authenticated
    USING (id = (SELECT auth.uid()));
DROP POLICY IF EXISTS profiles_owner_insert ON public.profiles;

DROP POLICY IF EXISTS incidents_owner_read ON public.incidents;
CREATE POLICY incidents_owner_read ON public.incidents FOR SELECT TO authenticated
    USING (user_id = (SELECT auth.uid()) AND NOT is_demo);
DROP POLICY IF EXISTS incidents_public_read ON public.incidents;
CREATE POLICY incidents_public_read ON public.incidents FOR SELECT TO anon, authenticated
    USING (NOT is_demo AND public_summary IS NOT NULL AND verification_status <> 'rejected');
DROP POLICY IF EXISTS incidents_owner_insert ON public.incidents;

DROP POLICY IF EXISTS official_zones_public_read ON public.official_zones;
CREATE POLICY official_zones_public_read ON public.official_zones FOR SELECT TO anon, authenticated
    USING (NOT is_demo AND revoked_at IS NULL);


-- Phase 4 stores suggestions independently of the original and moderated report.
CREATE TABLE IF NOT EXISTS public.incident_ai_analysis (
    incident_id uuid PRIMARY KEY REFERENCES public.incidents(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('processing', 'completed', 'failed', 'unavailable')),
    run_id uuid NOT NULL,
    provider text,
    model text,
    attempts integer NOT NULL CHECK (attempts >= 1),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    result jsonb CHECK (jsonb_typeof(result) = 'object'),
    processing_error text CHECK (processing_error IN (
        'provider_not_configured', 'provider_timeout', 'provider_unavailable', 'invalid_output', 'missing_description'
    )),
    CHECK ((status = 'processing') = (completed_at IS NULL)),
    CHECK ((status = 'completed') = (result IS NOT NULL)),
    CHECK ((status IN ('failed', 'unavailable')) = (processing_error IS NOT NULL))
);

ALTER TABLE public.incident_ai_analysis ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.incident_ai_analysis FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.incident_ai_analysis TO service_role;

-- Short-lived OSRM route references support comparison across API workers.
CREATE TABLE IF NOT EXISTS public.route_references (
    id uuid PRIMARY KEY,
    trip_id uuid NOT NULL,
    departure_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    route jsonb NOT NULL CHECK (jsonb_typeof(route) = 'object')
);
CREATE INDEX IF NOT EXISTS route_references_expiry_idx ON public.route_references(expires_at);
ALTER TABLE public.route_references ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.route_references FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, DELETE ON public.route_references TO service_role;

COMMIT;
