BEGIN;

-- Optional Phase 5 demo only. Adjacent fictional samples show how supported cells blend.
WITH cells (ordinal, category, longitude, latitude, local_hour, severity) AS (
    VALUES (1, 'suspicious_activity', 71.453, 30.199, 8, 1),
           (2, 'suspicious_activity', 71.453, 30.210, 8, 1),
           (3, 'theft', 71.460, 30.199, 12, 1),
           (4, 'theft', 71.467, 30.199, 14, 2),
           (5, 'theft', 71.473, 30.199, 14, 3),
           (6, 'harassment', 71.473, 30.187, 23, 4),
           (7, 'theft', 71.480, 30.193, 23, 3),
           (8, 'theft', 71.480, 30.199, 17, 2),
           (9, 'theft', 71.487, 30.199, 17, 1),
           (10, 'theft', 71.494, 30.199, 14, 2)
), offsets (number, delta) AS (VALUES (0, -0.00045), (1, 0.00045))
INSERT INTO public.incidents (
    id, category, description, public_summary, longitude, latitude, occurred_at,
    severity, verification_status, source, is_demo
)
SELECT ('c495c283-0e48-4db4-a0b3-' || lpad((ordinal * 2 + number)::text, 12, '0'))::uuid,
       category, 'Fictional heatmap sample: ' || replace(category, '_', ' '),
       'Fictional heatmap sample: ' || replace(category, '_', ' '), longitude + delta, latitude + delta,
       (date_trunc('day', now() AT TIME ZONE 'Asia/Karachi') - interval '1 day'
         + make_interval(hours => local_hour)) AT TIME ZONE 'Asia/Karachi',
       severity, 'corroborated', 'demo', true
FROM cells CROSS JOIN offsets
ON CONFLICT (id) DO UPDATE
SET occurred_at = EXCLUDED.occurred_at, created_at = EXCLUDED.created_at
WHERE incidents.is_demo AND incidents.source = 'demo';

INSERT INTO public.official_zones (
    id, name, description, designation, geometry, issuing_authority, effective_from, is_demo
) VALUES (
    'c495c283-0e48-4db4-a0b3-000000000090',
    'Fictional journey advisory', 'A fictional closure used to demonstrate route intersections.',
    'road_closure', 'SRID=4326;MULTIPOLYGON(((71.4671 30.1981,71.4683 30.1981,71.4683 30.1995,71.4671 30.1995,71.4671 30.1981)))',
    'Fictional demo', now() - interval '1 day', true
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
