"""Synthetic Step 16A regression checks; no real Baku files are needed."""
import importlib.util
import copy
import json
import pathlib
import tempfile
import unittest

import numpy as np
from shapely.geometry import LineString, MultiLineString, Point, box

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'recommendations', ROOT / 'scripts/14_recommend_bus_stops.py')
rec = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rec)


class CoverageTests(unittest.TestCase):
    def test_population_weighted_gain_uses_all_known_cells_and_reports_unknown(self):
        # Cell 1 can be a seed; low-priority/non-seed cells must also contribute.
        origins = np.array([Point(100, 0), Point(300, 0), Point(500, 0),
                            Point(100, 0), Point(0, 0), Point(501, 0)], dtype=object)
        props = [
            {'population': 100, 'nearest_bus_stop_m': 900, 'valid_pixel_fraction': 1},
            {'population': 300, 'nearest_bus_stop_m': 700, 'valid_pixel_fraction': .5},
            {'population': 50, 'nearest_bus_stop_m': 500, 'valid_pixel_fraction': 1},
            {'population': None, 'nearest_bus_stop_m': 800, 'valid_pixel_fraction': 0},
            {'population': 0, 'nearest_bus_stop_m': 800, 'valid_pixel_fraction': 1},
            {'population': 1000, 'nearest_bus_stop_m': 900, 'valid_pixel_fraction': 1},
        ]
        result = rec.coverage(Point(0, 0), origins, props)
        self.assertEqual(result['population_affected'], 400)
        self.assertEqual(result['current_access_m'], 750)
        self.assertEqual(result['new_access_m'], 250)
        self.assertEqual(result['access_improvement_m'], 500)
        self.assertEqual(result['newly_covered_cells'], 3)
        self.assertEqual(result['unknown_population_cells'], 1)
        self.assertIn('partial_population_cells=1', result['population_quality_notes'])

    def test_exact_500m_is_inclusive_and_baseline_500m_is_already_covered(self):
        props = [{'population': 20, 'nearest_bus_stop_m': 501},
                 {'population': 100, 'nearest_bus_stop_m': 500}]
        result = rec.coverage(Point(0, 0), np.array([Point(500, 0), Point(0, 0)]), props)
        self.assertEqual(result['population_affected'], 20)
        self.assertEqual(result['new_access_m'], 500)
        self.assertEqual(result['access_improvement_m'], 1)

    def test_zero_and_unknown_population_do_not_create_positive_gain(self):
        props = [{'population': None, 'nearest_bus_stop_m': 900},
                 {'population': 0, 'nearest_bus_stop_m': 900}]
        result = rec.coverage(Point(0, 0), np.array([Point(0, 0), Point(0, 0)]), props)
        self.assertEqual(result['population_affected'], 0)
        self.assertIsNone(result['current_access_m'])
        self.assertIsNone(result['new_access_m'])
        self.assertIsNone(result['access_improvement_m'])
        self.assertEqual(result['unknown_population_cells'], 1)


def context(points=None, populations=None, priorities=None, routes=None, stops=None):
    points = points if points is not None else [Point(400000, 4470000)]
    populations = populations if populations is not None else [100] * len(points)
    priorities = priorities if priorities is not None else [70] * len(points)
    stops = stops if stops is not None else [Point(400000, 4469000)]
    routes = routes if routes is not None else [LineString([(399000, 4470100), (410000, 4470100)])]
    route_props = [{'id': f'ayna:{i}', 'route_ref': str(i), 'source': 'AYNA'} for i in range(len(routes))]
    parts, keys, part_props = rec.route_parts(routes, route_props)
    props = [{'id': f'grid:{i}', 'population': pop, 'bus_priority': priority,
              'nearest_bus_stop_m': min(point.distance(s) for s in stops), 'valid_pixel_fraction': 1}
             for i, (point, pop, priority) in enumerate(zip(points, populations, priorities))]
    boundary = box(390000, 4460000, 420000, 4480000)
    return {'origins': np.array(points), 'props': props, 'routes': parts,
            'route_keys': keys, 'route_props': part_props, 'stops': np.array(stops),
            'boundary': boundary, 'boundary_wgs84': rec.transform(rec.TO_WGS84, boundary),
            'input_audits': {}}


class ScreeningTests(unittest.TestCase):
    def test_non_seed_population_contributes_and_null_never_becomes_a_seed(self):
        ctx = context(points=[Point(400000, 4470000), Point(400200, 4470000), Point(400300, 4470000)],
                      populations=[100, 300, None], priorities=[70, 10, 99])
        doc = rec.build_document(ctx)
        self.assertEqual(doc['screening']['total_seeds'], 1)
        p = doc['features'][0]['properties']
        self.assertEqual(p['population_affected'], 400)
        self.assertEqual(p['unknown_population_cells'], 1)
        rec.verify_document(doc, doc, ctx)

    def test_route_stop_boundary_and_zero_gain_screening(self):
        for kind in ('route', 'stop', 'boundary', 'gain'):
            with self.subTest(kind=kind):
                ctx = context()
                if kind == 'route':
                    ctx = context(routes=[LineString([(399000, 4470301), (410000, 4470301)])])
                elif kind == 'stop':
                    ctx = context(stops=[Point(400000, 4470200)])
                elif kind == 'boundary':
                    ctx['boundary'] = box(399500, 4469500, 400500, 4470050)
                else:
                    ctx = context(populations=[0])
                doc = rec.build_document(ctx)
                self.assertEqual(doc['features'], [])
                field = {'route': 'route_distance_rejections', 'stop': 'existing_stop_rejections',
                         'boundary': 'outside_baku_rejections', 'gain': 'zero_gain_rejections'}[kind]
                self.assertEqual(doc['screening'][field], 1)
                rec.verify_document(doc, doc, ctx)

    def test_multiline_projection_uses_nearest_part_with_deterministic_ties(self):
        ctx = context(routes=[MultiLineString([
            [(399000, 4470200), (410000, 4470200)],
            [(399000, 4470100), (410000, 4470100)]]),
            LineString([(399000, 4470100), (410000, 4470100)])])
        doc = rec.build_document(ctx)
        p = doc['features'][0]['properties']
        self.assertEqual(p['nearby_route_id'], 'ayna:0')
        self.assertEqual(p['route_part_index'], 1)
        rec.verify_document(doc, doc, ctx)

    def test_route_at_300m_passes_and_inside_boundary_hole_fails(self):
        ctx = context(routes=[LineString([(399000, 4470300), (410000, 4470300)])])
        self.assertEqual(len(rec.build_document(ctx)['features']), 1)
        # The projection lies inside a hole, despite being within outer bounds.
        ctx['boundary'] = ctx['boundary'].difference(box(399950, 4470250, 400050, 4470350))
        ctx['boundary_wgs84'] = rec.transform(rec.TO_WGS84, ctx['boundary'])
        doc = rec.build_document(ctx)
        self.assertEqual(doc['features'], [])
        self.assertEqual(doc['screening']['outside_baku_rejections'], 1)

    def test_existing_stop_at_300m_is_allowed_but_just_under_is_rejected(self):
        ctx = context(points=[Point(400000, 4470000), Point(399600, 4470100)],
                      priorities=[70, 10])
        feature = rec.build_document(ctx)['features'][0]
        point = rec.transform(rec.TO_METRIC, rec.shape(feature['geometry']))
        for distance, count in [(300, 1), (299.99, 0)]:
            with self.subTest(distance=distance):
                stop = Point(point.x + distance, point.y)
                ctx['stops'] = np.array([stop])
                for cell, origin in zip(ctx['props'], ctx['origins']):
                    cell['nearest_bus_stop_m'] = origin.distance(stop)
                self.assertEqual(len(rec.build_document(ctx)['features']), count)

    def test_proposals_just_below_700m_deduplicate_and_just_above_remain(self):
        for distance, count in [(699.99, 1), (700.01, 2)]:
            with self.subTest(distance=distance):
                ctx = context(points=[Point(400000, 4470000), Point(400000 + distance, 4470000)])
                doc = rec.build_document(ctx)
                self.assertEqual(len(doc['features']), count)
                rec.verify_document(doc, doc, ctx)

    def test_deduplication_prefers_coverage_then_local_priority(self):
        # Points 600 m apart; the second gains more population despite lower priority.
        ctx = context(points=[Point(400000, 4470000), Point(400600, 4470000)],
                      populations=[100, 300], priorities=[90, 60])
        doc = rec.build_document(ctx)
        self.assertEqual(doc['screening']['duplicates'], 1)
        self.assertEqual(doc['features'][0]['properties']['source_grid_id'], 'grid:1')
        # Equal coverage: priority breaks the tie.
        ctx['props'][0]['population'] = 300
        doc = rec.build_document(ctx)
        self.assertEqual(doc['features'][0]['properties']['source_grid_id'], 'grid:0')

    def test_stable_ids_and_limit_of_twenty(self):
        points = [Point(400000 + i * 1000, 4470000) for i in range(22)]
        ctx = context(points=points, routes=[LineString([(399000, 4470100), (423000, 4470100)])])
        ctx['boundary'] = box(390000, 4460000, 430000, 4480000)
        ctx['boundary_wgs84'] = rec.transform(rec.TO_WGS84, ctx['boundary'])
        doc = rec.build_document(ctx)
        self.assertEqual(len(doc['features']), 20)
        self.assertEqual(doc['screening']['qualified_beyond_limit'], 2)
        ctx['props'].reverse()
        ctx['origins'] = ctx['origins'][::-1]
        self.assertEqual(doc, rec.build_document(ctx))
        rec.verify_document(doc, doc, ctx)

    def test_verifier_rejects_tampered_geometry_calculations_types_and_omissions(self):
        ctx = context()
        original = rec.build_document(ctx)
        for field, value in [('access_improvement_m', 1), ('population_affected', True),
                             ('priority', 101), ('reason', []), ('id', 'wrong')]:
            with self.subTest(field=field):
                doc = copy.deepcopy(original)
                doc['features'][0]['properties'][field] = value
                # Supplying the same document as expected still exercises independent checks.
                with self.assertRaises(ValueError):
                    rec.verify_document(doc, doc, ctx)
        doc = copy.deepcopy(original)
        doc['features'][0]['geometry']['coordinates'] = [0, 0]
        with self.assertRaises(ValueError):
            rec.verify_document(doc, doc, ctx)
        doc = copy.deepcopy(original)
        doc['features'] = []
        with self.assertRaises(ValueError):
            rec.verify_document(doc, original, ctx)

    def test_verify_saved_does_not_change_output_and_rejects_tampering(self):
        ctx = context()
        doc = rec.build_document(ctx)
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'bus.geojson'
            rec.save_output(doc, ctx, path)
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            rec.verify_saved(path, doc, ctx)
            self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
            changed = copy.deepcopy(doc)
            changed['features'][0]['properties']['new_access_m'] = 0
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                rec.verify_saved(path, doc, ctx)

    def test_independent_verifier_checks_stop_and_proposal_spacing(self):
        ctx = context()
        doc = rec.build_document(ctx)
        point = rec.transform(rec.TO_METRIC, rec.shape(doc['features'][0]['geometry']))
        ctx['stops'] = np.array([Point(point.x + 299, point.y)])
        with self.assertRaisesRegex(ValueError, '300m'):
            rec.verify_document(doc, doc, ctx)
        ctx = context(points=[Point(400000, 4470000), Point(400600, 4470000)])
        # Build each location as the only eligible seed, then combine them to
        # challenge spacing independently of the production deduplication path.
        proposals = []
        for eligible in (0, 1):
            for i, cell in enumerate(ctx['props']):
                cell['bus_priority'] = 70 if i == eligible else 10
            proposals.extend(rec.build_document(ctx)['features'])
        for cell in ctx['props']:
            cell['bus_priority'] = 70
        doc = rec.build_document(ctx)
        doc['features'] = proposals
        with self.assertRaisesRegex(ValueError, '700m'):
            rec.verify_document(doc, doc, ctx)


if __name__ == '__main__':
    unittest.main()
