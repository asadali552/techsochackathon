BEGIN;

-- Entirely fictional Multan examples for a dedicated demo database.
INSERT INTO public.incidents (
    id, user_id, category, description, public_summary, longitude, latitude, occurred_at, severity, source, is_demo
) VALUES
    ('b674f9e1-27c4-42f0-82d8-c87a31323e01', NULL, 'poor_lighting',
     'Fictional demo: poor lighting.', 'Fictional demo: poor lighting.',
     71.470, 30.197, now() - interval '1 day', 2, 'demo', true),
    ('b674f9e1-27c4-42f0-82d8-c87a31323e02', NULL, 'unsafe_road',
     'Fictional demo: uneven road surface.', 'Fictional demo: uneven road surface.',
     71.476, 30.192, now() - interval '2 days', 2, 'demo', true),
    ('b674f9e1-27c4-42f0-82d8-c87a31323e03', NULL, 'theft',
     'Fictional demo: example theft.', 'Fictional demo: example theft.',
     71.481, 30.188, now() - interval '3 days', 3, 'demo', true),
    ('b674f9e1-27c4-42f0-82d8-c87a31323e04', NULL, 'robbery',
     'Fictional demo: example robbery.', 'Fictional demo: example robbery.',
     71.474, 30.194, now() - interval '5 hours', 3, 'demo', true),
    ('b674f9e1-27c4-42f0-82d8-c87a31323e05', NULL, 'road_accident',
     'Fictional demo: example road accident.', 'Fictional demo: example road accident.',
     71.483, 30.195, now() - interval '29 hours', 2, 'demo', true),
    ('b674f9e1-27c4-42f0-82d8-c87a31323e06', NULL, 'suspicious_activity',
     'Fictional demo: example suspicious activity.', 'Fictional demo: example suspicious activity.',
     71.478, 30.200, now() - interval '65 hours', 1, 'demo', true),
    ('b674f9e1-27c4-42f0-82d8-c87a31323e07', NULL, 'road_closure',
     'Fictional demo: example road closure.', 'Fictional demo: example road closure.',
     71.477, 30.190, now() - interval '9 hours', 2, 'demo', true)
ON CONFLICT (id) DO UPDATE
SET occurred_at = EXCLUDED.occurred_at, created_at = EXCLUDED.created_at
WHERE incidents.is_demo AND incidents.source = 'demo';

INSERT INTO public.official_zones (
    id, name, description, designation, geometry, issuing_authority, effective_from, is_demo
) VALUES (
    'b674f9e1-27c4-42f0-82d8-c87a31323e08',
    'Fictional demo zone', 'Fictional example for map testing.',
    'road_closure', 'SRID=4326;MULTIPOLYGON(((71.476 30.189,71.478 30.189,71.478 30.191,71.476 30.191,71.476 30.189)))',
    'Fictional demo', now() - interval '1 day', true
)
ON CONFLICT (id) DO NOTHING;

COMMIT;
