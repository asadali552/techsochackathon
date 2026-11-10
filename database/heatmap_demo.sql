BEGIN;

-- Optional fictional scoring fixtures. Run only on a dedicated demo database.
WITH yesterday AS (
    SELECT date_trunc('day', now() AT TIME ZONE 'Asia/Karachi') - interval '1 day' AS midnight
), fixtures (id, category, longitude, latitude, local_hour, severity) AS (
    VALUES
        ('836eed57-1a5d-4654-8593-f2bb583bf001', 'suspicious_activity', 71.451, 30.204, 8, 1),
        ('836eed57-1a5d-4654-8593-f2bb583bf002', 'suspicious_activity', 71.454, 30.205, 8, 1),
        ('836eed57-1a5d-4654-8593-f2bb583bf003', 'theft', 71.493, 30.204, 14, 2),
        ('836eed57-1a5d-4654-8593-f2bb583bf004', 'theft', 71.494, 30.205, 14, 2),
        ('836eed57-1a5d-4654-8593-f2bb583bf005', 'harassment', 71.473, 30.193, 23, 5),
        ('836eed57-1a5d-4654-8593-f2bb583bf006', 'theft', 71.474, 30.192, 3, 5),
        ('836eed57-1a5d-4654-8593-f2bb583bf007', 'road_accident', 71.486, 30.175, 19, 3),
        ('836eed57-1a5d-4654-8593-f2bb583bf008', 'unsafe_road', 71.487, 30.176, 20, 3)
)
INSERT INTO public.incidents (
    id, user_id, category, description, public_summary, longitude, latitude, occurred_at,
    severity, verification_status, source, is_demo
)
SELECT id::uuid, NULL, category, 'Fictional heatmap demo: ' || replace(category, '_', ' '),
       'Fictional heatmap demo: ' || replace(category, '_', ' '), longitude, latitude,
       (midnight + make_interval(hours => local_hour)) AT TIME ZONE 'Asia/Karachi',
       severity, 'corroborated', 'demo', true
FROM fixtures CROSS JOIN yesterday
ON CONFLICT (id) DO UPDATE
SET occurred_at = EXCLUDED.occurred_at, created_at = EXCLUDED.created_at
WHERE incidents.is_demo AND incidents.source = 'demo';

COMMIT;
