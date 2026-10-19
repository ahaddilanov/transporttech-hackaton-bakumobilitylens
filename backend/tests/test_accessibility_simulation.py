"""Independent synthetic numerical expectations; offline and isolated from Baku data."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pyproj import Transformer
import shapely
from shapely.geometry import LineString, MultiLineString, Point, box, mapping

SPEC = importlib.util.spec_from_file_location('simulation', Path(__file__).resolve().parents[1] / 'scripts/17_simulate_accessibility.py')
sim = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sim)


def grid(points, populations, baseline):
    props = [{'id': f'grid:{i}', 'population': p, 'nearest_bus_stop_m': b, 'nearest_cycleway_m': b}
             for i, (p, b) in enumerate(zip(populations, baseline, strict=True))]
    return sim.make_grid(props, points)


def intervention(geometry=None, kind='bus_stop', benefit=0):
    return {'id': 'source:stable-id', 'type': kind, 'geometry': Point(0, 0) if geometry is None else geometry,
            'properties': {'id': 'source:stable-id', sim.BENEFIT_FIELDS[kind]: benefit}}


class NumericalTests(unittest.TestCase):
    def test_population_weighting_and_percentage_points(self):
        # The first cell improves while already covered; the second becomes covered;
        # the third improves but remains outside coverage. All contribute to improvement.
        ctx = grid([Point(0, 0), Point(400, 0), Point(800, 0), Point(100, 0), Point(200, 0)],
                   [100, 300, 100, None, 0], [200, 1000, 1000, 900, 700])
        result = sim.simulate(intervention(), ctx)
        expected = {'population_improved': 500, 'coverage_before_pct': 20, 'coverage_after_pct': 80,
                    'coverage_change_pp': 60, 'avg_access_improvement_m': 440, 'affected_cells': 4,
                    'newly_covered_population': 300, 'newly_covered_cells': 2,
                    'unknown_population_cells_affected': 1, 'unknown_population_cells_newly_covered': 1}
        for key, value in expected.items():
            self.assertEqual(result[key], value, key)

    def test_null_zero_and_undefined_means_are_distinct(self):
        for populations, expected in [([None], None), ([0], 0)]:
            result = sim.simulate(intervention(), grid([Point(100, 0)], populations, [700]))
            self.assertEqual(result['population_improved'], expected)
            self.assertEqual(result['newly_covered_population'], expected)
            for field in ('coverage_before_pct', 'coverage_after_pct', 'coverage_change_pp', 'avg_access_improvement_m'):
                self.assertIsNone(result[field])
            self.assertEqual(result['affected_cells'], int(populations == [0]))

    def test_zero_benefit_has_zero_gain_and_null_mean(self):
        result = sim.simulate(intervention(Point(5000, 0)), grid([Point(0, 0)], [100], [400]))
        self.assertEqual(result['population_improved'], 0)
        self.assertEqual(result['affected_cells'], 0)
        self.assertEqual(result['coverage_change_pp'], 0)
        self.assertEqual(result['newly_covered_population'], 0)
        self.assertEqual(result['coverage_before_pct'], 100)
        self.assertIsNone(result['avg_access_improvement_m'])

    def test_complete_line_and_multiline_not_endpoints_or_gap_connections(self):
        ctx = grid([Point(1000, 100)], [80], [1500])
        line = LineString([(0, 0), (2000, 0)])
        result = sim.simulate(intervention(line, 'bike_corridor'), ctx)
        self.assertEqual(result['newly_covered_population'], 80)
        self.assertEqual(result['avg_access_improvement_m'], 1400)
        parts = MultiLineString([[(0, 0), (200, 0)], [(1800, 0), (2000, 0)]])
        result = sim.simulate(intervention(parts, 'bike_corridor'), ctx)
        self.assertEqual(result['newly_covered_population'], 0)
        self.assertGreater(result['avg_access_improvement_m'], 0)

    def test_inclusive_coverage_and_strict_improvement_tolerance(self):
        ctx = grid([Point(500, 0), Point(500, 0), Point(500.001, 0), Point(100, 0)],
                   [10, 20, 30, 40], [500, 500 + .5e-6, 700, 100 + 2e-6])
        result = sim.simulate(intervention(), ctx)
        self.assertEqual(result['newly_covered_population'], 20)
        self.assertEqual(result['affected_cells'], 2)
        self.assertEqual(result['population_improved'], 70)
        self.assertEqual(result['coverage_change_pp'], 20)


class ReconciliationTests(unittest.TestCase):
    def test_bus_exact_reconciliation_and_wrong_population_rejected(self):
        item = intervention(benefit=100)
        result = sim.simulate(item, grid([Point(100, 0)], [100], [700]))
        self.assertEqual(sim.reconcile(result, item)['status'], 'match')
        item['properties']['population_affected'] = 90
        with self.assertRaisesRegex(ValueError, 'unexplained'):
            sim.reconcile(result, item)

    def test_bike_policy_difference_is_not_silently_forced_to_match(self):
        item = intervention(LineString([(0, 0), (100, 0)]), 'bike_corridor', benefit=100)
        item['properties'].update(method_version='baku-bike-corridors-v1.0', newly_covered_cells=1,
                                  unknown_population_cells=0, existing_osm_coverage_excluded_cells=1)
        result = sim.simulate(item, grid([Point(100, 0), Point(200, 0)], [100, 200], [700, 700]))
        check = sim.reconcile(result, item)
        self.assertEqual(check['difference_population'], 200)
        self.assertEqual(check['status'], 'consistent_with_osm_exclusion')
        self.assertFalse(check['osm_gate_recomputed_by_simulator'])
        self.assertEqual(result['newly_covered_population'], 300)
        for change in ({'existing_osm_coverage_excluded_cells': 2}, {'method_version': 'unknown'},
                       {'population_coverage_gain': 400}, {'unknown_population_cells': 1}):
            altered = copy.deepcopy(item)
            altered['properties'].update(change)
            with self.assertRaises(ValueError):
                sim.reconcile(result, altered)

    def test_unknown_or_zero_population_exclusions_can_change_counts_without_population(self):
        item = intervention(LineString([(0, 0), (100, 0)]), 'bike_corridor', benefit=100)
        item['properties'].update(method_version='baku-bike-corridors-v1.0', newly_covered_cells=1,
                                  unknown_population_cells=0, existing_osm_coverage_excluded_cells=2)
        result = sim.simulate(item, grid([Point(0, 0)] * 3, [100, None, 0], [700] * 3))
        check = sim.reconcile(result, item)
        self.assertEqual(check['status'], 'consistent_with_osm_exclusion')
        self.assertEqual(check['difference_population'], 0)
        self.assertEqual(check['additional_unknown_population_cells'], 1)

    def test_missing_recommendation_population_is_unavailable(self):
        item = intervention(benefit=None)
        result = sim.simulate(item, grid([Point(100, 0)], [100], [700]))
        check = sim.reconcile(result, item)
        self.assertEqual(check['status'], 'unavailable')
        self.assertIsNone(check['difference_population'])
        self.assertEqual(result['population_improved'], 100)

    def test_false_exclusion_count_is_rejected_even_with_equal_population(self):
        item = intervention(LineString([(0, 0), (100, 0)]), 'bike_corridor', benefit=100)
        item['properties'].update(method_version='baku-bike-corridors-v1.0', newly_covered_cells=1,
                                  unknown_population_cells=0, existing_osm_coverage_excluded_cells=2)
        result = sim.simulate(item, grid([Point(100, 0)], [100], [700]))
        with self.assertRaises(ValueError):
            sim.reconcile(result, item)


def write_sources(folder):
    """Realistic metric fixtures exported to geographic coordinates before loading."""
    project = Transformer.from_crs(32639, 4326, always_xy=True).transform

    def feature(identifier, geometry, **properties):
        return {'type': 'Feature', 'id': identifier, 'properties': {'id': identifier, **properties},
                'geometry': mapping(shapely.transform(geometry, project, interleaved=False))}

    x, y = 400000, 4470000
    docs = {
        'grid': [feature('grid:b', box(x + 90, y - 10, x + 110, y + 10), population=100,
                         nearest_bus_stop_m=700, nearest_cycleway_m=700),
                 feature('grid:a', box(x + 190, y - 10, x + 210, y + 10), population=None,
                         nearest_bus_stop_m=700, nearest_cycleway_m=700)],
        'bus_stop': [feature('bus:stable', Point(x, y), population_affected=100)],
        'bike_corridor': [feature('bike:stable', LineString([(x - 1000, y), (x + 1000, y)]), population_coverage_gain=100)],
    }
    paths = {key: folder / (key + '.geojson') for key in docs}
    for key, features in docs.items():
        paths[key].write_text(json.dumps({'type': 'FeatureCollection', 'features': features}))
    return paths


class VerificationAndIOTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.paths = write_sources(self.folder)
        self.ctx, self.items, self.audits = sim.load_inputs(self.paths)
        self.document = sim.build_document(self.ctx, self.items, self.audits)

    def test_load_projects_to_meters_and_reads_each_geojson_once(self):
        reads = []
        original = Path.read_bytes

        def read(path):
            reads.append(path)
            return original(path)

        with patch.object(Path, 'read_bytes', read):
            ctx, items, _ = sim.load_inputs(self.paths)
        self.assertCountEqual(reads, self.paths.values())
        bus = next(i for i in items if i['type'] == 'bus_stop')
        self.assertAlmostEqual(ctx['origins'][1].distance(bus['geometry']), 100, places=6)
        scenario = sim.simulate(bus, ctx)
        self.assertAlmostEqual(scenario['avg_access_improvement_m'], 600, places=6)
        self.assertEqual(scenario['unknown_population_cells_affected'], 1)

    def test_stable_source_ids_ordering_repeatability_and_input_preservation(self):
        snapshots = {p: p.read_bytes() for p in self.paths.values()}
        repeat = sim.build_document(self.ctx, list(reversed(self.items)), self.audits)
        self.assertEqual(sim.serialize(repeat), sim.serialize(self.document))
        self.assertEqual({s['intervention_id'] for s in repeat['scenarios']}, {'bus:stable', 'bike:stable'})
        reordered = sim.make_grid(list(reversed(self.ctx['props'])), list(reversed(self.ctx['origins'])))
        self.assertEqual(sim.build_document(reordered, self.items, self.audits)['scenarios'], self.document['scenarios'])
        for path, content in snapshots.items():
            self.assertEqual(path.read_bytes(), content)

    def test_independent_verifier_detects_bad_core_calculation(self):
        # Even if both saved and regenerated production results share a bug,
        # the scalar oracle must catch it.
        for field, value in [('population_improved', 1), ('coverage_change_pp', 2),
                             ('avg_access_improvement_m', 3), ('affected_cells', True),
                             ('newly_covered_population', 7), ('coverage_before_pct', 8),
                             ('coverage_after_pct', 9), ('unknown_population_cells_affected', 0)]:
            altered = copy.deepcopy(self.document)
            altered['scenarios'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                sim.verify_document(altered, altered, self.ctx, self.items)
        with patch.object(sim, 'simulate', side_effect=AssertionError('production helper reused')):
            sim.verify_document(self.document, self.document, self.ctx, self.items)

    def test_verifier_rejects_ids_missing_scenarios_types_reconciliation_and_provenance(self):
        for mutate in [lambda d: d['scenarios'].pop(),
                       lambda d: d['scenarios'][0].update(intervention_id='invented'),
                       lambda d: d['scenarios'][0].update(intervention_type='bus_stop'),
                       lambda d: d['scenarios'][0].pop('population_improved'),
                       lambda d: d['scenarios'][0]['reconciliation'].update(status='invented'),
                       lambda d: d['metadata'].update(model_version='other')]:
            changed = copy.deepcopy(self.document)
            mutate(changed)
            with self.assertRaises(ValueError):
                sim.verify_document(changed, self.document, self.ctx, self.items)

    def test_save_verify_and_query_are_offline_and_read_only(self):
        output = self.folder / 'scenarios.json'
        with patch('socket.socket.connect', side_effect=AssertionError('network forbidden')):
            sim.save_output(self.document, self.ctx, self.items, output)
            before = (output.read_bytes(), output.stat().st_mtime_ns)
            with (patch.object(sim, 'INPUTS', self.paths), patch.object(sim, 'OUTPUT', output),
                  patch.object(sim, 'NamedTemporaryFile', side_effect=AssertionError('write forbidden')),
                  patch.object(Path, 'mkdir', side_effect=AssertionError('mkdir forbidden')),
                  patch.object(sim.os, 'replace', side_effect=AssertionError('replace forbidden')),
                  patch('sys.stderr', new_callable=io.StringIO), patch('sys.stdout', new_callable=io.StringIO) as stdout):
                self.assertEqual(sim.main(['--verify-only']), 0)
                self.assertEqual(sim.main(['--intervention-id', 'bus:stable']), 0)
                row = json.loads(stdout.getvalue())
                self.assertEqual(row['intervention_id'], 'bus:stable')
                stdout.seek(0); stdout.truncate()
                self.assertEqual(sim.main(['--verify-only', '--intervention-id', 'bike:stable']), 0)
                self.assertEqual(json.loads(stdout.getvalue())['intervention_type'], 'bike_corridor')
                with self.assertRaises(SystemExit) as error:
                    sim.main(['--intervention-id', 'missing'])
                self.assertNotEqual(error.exception.code, 0)
            self.assertEqual(before, (output.read_bytes(), output.stat().st_mtime_ns))

    def test_failed_verification_preserves_existing_output(self):
        output = self.folder / 'saved.json'
        output.write_text('previous output')
        broken = copy.deepcopy(self.document)
        broken['scenarios'][0]['population_improved'] = -1
        with self.assertRaises(ValueError):
            sim.save_output(broken, self.ctx, self.items, output)
        self.assertEqual(output.read_text(), 'previous output')
        self.assertEqual(list(self.folder.glob('.saved.json.*')), [])

    def test_empty_recommendations_and_missing_verification_output(self):
        for key in ('bus_stop', 'bike_corridor'):
            self.paths[key].write_text('{"type":"FeatureCollection","features":[]}')
        ctx, items, audits = sim.load_inputs(self.paths)
        doc = sim.build_document(ctx, items, audits)
        self.assertEqual(doc['scenarios'], [])
        sim.verify_document(doc, doc, ctx, items)
        with (patch.object(sim, 'OUTPUT', self.folder / 'missing.json'),
              patch.object(sim, 'load_inputs', side_effect=AssertionError('should fail before loading')),
              patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit)):
            sim.main(['--verify-only'])

    def test_input_validation_rejects_bad_population_baseline_geometry_and_ids(self):
        original = json.loads(self.paths['grid'].read_text())
        changes = [lambda d: d['features'][0]['properties'].update(population=-1),
                   lambda d: d['features'][0]['properties'].update(population=True),
                   lambda d: d['features'][0]['properties'].update(nearest_bus_stop_m=None),
                   lambda d: d['features'][0]['properties'].update(nearest_cycleway_m=float('inf')),
                   lambda d: d['features'][0].update(geometry=None),
                   lambda d: d['features'][0].update(geometry=mapping(Point(49, 40))),
                   lambda d: d['features'].append(copy.deepcopy(d['features'][0])),
                   lambda d: d.update(crs={'type': 'name', 'properties': {'name': 'EPSG:32639'}})]
        for change in changes:
            doc = copy.deepcopy(original)
            change(doc)
            self.paths['grid'].write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                sim.load_inputs(self.paths)

    def test_stale_recommendation_grid_hash_is_rejected(self):
        doc = json.loads(self.paths['bike_corridor'].read_text())
        doc['metadata'] = {'inputs': {'grid': {'sha256': 'stale'}}}
        self.paths['bike_corridor'].write_text(json.dumps(doc))
        with self.assertRaisesRegex(ValueError, 'different scored grid'):
            sim.load_inputs(self.paths)


if __name__ == '__main__':
    unittest.main()
