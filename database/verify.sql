-- Read-only checks after applying schema.sql in a dedicated staging project.
DO $$
DECLARE
    object_name text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis') THEN
        RAISE EXCEPTION 'PostGIS is missing';
    END IF;

    FOREACH object_name IN ARRAY ARRAY[
        'incidents_public_radius_gix', 'incidents_public_bbox_gix',
        'official_zones_area_gix', 'official_zones_bbox_gix', 'route_references_expiry_idx'
    ] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_index WHERE indexrelid = to_regclass('public.' || object_name) AND indisvalid
        ) THEN
            RAISE EXCEPTION 'Missing or invalid index %', object_name;
        END IF;
    END LOOP;

    FOREACH object_name IN ARRAY ARRAY['profiles', 'incidents', 'official_zones', 'incident_ai_analysis', 'route_references']
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_class WHERE oid = to_regclass('public.' || object_name) AND relrowsecurity
        ) THEN
            RAISE EXCEPTION 'RLS is missing on %', object_name;
        END IF;
    END LOOP;

    IF has_column_privilege('anon', 'public.incidents', 'description', 'SELECT')
        OR has_column_privilege('authenticated', 'public.incidents', 'latitude', 'SELECT')
        OR has_column_privilege('authenticated', 'public.incidents', 'description', 'INSERT')
        OR has_column_privilege('authenticated', 'public.incidents', 'verification_status', 'UPDATE')
        OR has_any_column_privilege('anon', 'public.incident_ai_analysis', 'SELECT')
        OR has_any_column_privilege('authenticated', 'public.incident_ai_analysis', 'SELECT')
        OR has_any_column_privilege('authenticated', 'public.route_references', 'SELECT')
    THEN
        RAISE EXCEPTION 'Unexpected public or authenticated privileges';
    END IF;
END $$;
