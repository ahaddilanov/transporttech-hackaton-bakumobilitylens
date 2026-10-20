"""Offline contract, preservation, geometry and transaction checks for complete exports."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from pyproj import Transformer
import shapely
from shapely.geometry import LineString, Point, box, mapping

SPEC = importlib.util.spec_from_file_location('complete_export', Path(__file__).resolve().parents[1] / 'scripts/18_export_frontend_complete.py')
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


def recommendation(kind='bus_stop', identifier='full:bus:id'):
    p = {'id': identifier, 'priority': 75, 'reason': ['preliminary'], 'method_version': 'fixture'}
    geometry = Point(49.85, 40.4)
    if kind == 'bus_stop':
        p.update(population_affected=100, current_access_m=700, new_access_m=100, access_improvement_m=600)
    else:
        geometry = LineString([(49.84, 40.4), (49.86, 40.4)])
        p.update(length_m=1700, population_coverage_gain=100, start_name='AYNA', end_name=None,
                 route_edges=[[1, 2, 0]], routing_risk_flags=['requires_field_check'])
    return {'type': 'Feature', 'id': identifier, 'properties': p, 'geometry': mapping(geometry)}


def collection(features):
    return {'type': 'FeatureCollection', 'features': features}


class ContractTests(unittest.TestCase):
    def test_compaction_preserves_contract_nulls_full_ids_and_risk_metadata(self):
        source = collection([recommendation('bike_corridor', 'full:bike:id')])
        source['metadata'] = {'limitations': ['not approved'], 'inputs': {'grid': {'file': 'grid', 'sha256': 'hash', 'fields': ['bulky']}}}
        compact = export.compact_recommendations(source)
        p = compact['features'][0]['properties']
        self.assertNotIn('route_edges', p)
        self.assertEqual(p['id'], 'full:bike:id')
        self.assertIsNone(p['end_name'])
        self.assertEqual(p['routing_risk_flags'], ['requires_field_check'])
        self.assertEqual(compact['metadata']['limitations'], ['not approved'])
        self.assertNotIn('fields', compact['metadata']['inputs']['grid'])
        export.validate_recommendations(compact, 'bike_corridor')
        self.assertIn('route_edges', source['features'][0]['properties'])

    def test_recommendation_fields_types_scores_and_finite_values(self):
        original = collection([recommendation()])
        export.validate_recommendations(original, 'bus_stop')
        for field, value in [('priority', 101), ('priority', True), ('population_affected', float('inf')),
                             ('reason', 'string'), ('id', 123), ('new_access_m', -1)]:
            altered = copy.deepcopy(original)
            altered['features'][0]['properties'][field] = value
            with self.subTest(field=field), self.assertRaises((ValueError, RuntimeError)):
                export.validate_recommendations(altered, 'bus_stop')
        altered = copy.deepcopy(original)
        del altered['features'][0]['properties']['current_access_m']
        with self.assertRaises((ValueError, RuntimeError)):
            export.validate_recommendations(altered, 'bus_stop')

    def test_scenario_envelope_and_exact_one_to_one_full_id_matching(self):
        recs = {'bus_recommendations': collection([recommendation()]),
                'bike_recommendations': collection([recommendation('bike_corridor', 'full:bike:id')])}
        source = {'metadata': {}, 'summary': {}, 'scenarios': [
            {'intervention_id': 'full:bus:id', 'intervention_type': 'bus_stop'},
            {'intervention_id': 'full:bike:id', 'intervention_type': 'bike_corridor'}]}
        export.validate_scenario_links(source, recs)
        for mutate in [lambda d: d['scenarios'].pop(),
                       lambda d: d['scenarios'].append(copy.deepcopy(d['scenarios'][0])),
                       lambda d: d['scenarios'][0].update(intervention_id='full:bus'),
                       lambda d: d['scenarios'][0].update(intervention_type='bike_corridor'),
                       lambda d: d['scenarios'].append({'intervention_id': 'extra', 'intervention_type': 'bus_stop'})]:
            changed = copy.deepcopy(source)
            mutate(changed)
            with self.assertRaises((ValueError, RuntimeError)):
                export.validate_scenario_links(changed, recs)
        with self.assertRaises((ValueError, RuntimeError)):
            export.validate_scenario_links(source['scenarios'], recs)

    def test_geographic_coordinate_order_and_geometry_validity(self):
        for geometry in [Point(40.4, 49.85), Point(500000, 4470000), Point(49.85, 40.4, 3),
                         Point(), LineString([(49.85, 40.4), (49.86, 40.4)])]:
            doc = collection([recommendation()])
            doc['features'][0]['geometry'] = mapping(geometry)
            with self.subTest(geometry=geometry), self.assertRaises((ValueError, RuntimeError)):
                export.validate_recommendations(doc, 'bus_stop')


def fixture_paths(folder):
    project = Transformer.from_crs(32639, 4326, always_xy=True).transform
    x, y = 400000, 4470000

    def feature(identifier, geometry, props):
        return {'type': 'Feature', 'id': identifier, 'properties': {'id': identifier, **props},
                'geometry': mapping(shapely.transform(geometry, project, interleaved=False))}

    def cell(identifier, offset, population):
        props = {'population': population, 'nearest_bus_stop_m': 700, 'nearest_cycleway_m': 700,
                 'nearest_metro_m': 500, 'bus_stops_500m': 0, 'bus_routes_nearby': 1, 'pois_nearby': 0,
                 'bus_priority': 70 if population is not None else None,
                 'bike_priority': 59 if population is not None else None,
                 'mobility_gap': 66 if population is not None else None,
                 'scoring_quality': 'full_population_pixel_coverage' if population is not None else 'unknown_population',
                 'coverage_status': 'covered', 'valid_pixel_fraction': 1 if population is not None else None,
                 'scoring_model_version': 'baku-priority-v1.0', 'area_m2': 400}
        return feature(identifier, box(x + offset - 10, y - 10, x + offset + 10, y + 10), props)

    bus = recommendation()
    bike = recommendation('bike_corridor', 'full:bike:id')
    bus['geometry'] = mapping(shapely.transform(Point(x, y), project, interleaved=False))
    bike['geometry'] = mapping(shapely.transform(LineString([(x - 1000, y), (x + 1000, y)]), project, interleaved=False))
    docs = {
        'grid': collection([cell('grid:known', 100, 100), cell('grid:unknown', 200, None)]),
        'bus_stops': collection([feature('stop:1', Point(x - 1000, y), {'name': None, 'source': 'OSM'})]),
        'bus_routes': collection([feature('route:1', LineString([(x - 500, y), (x - 100, y + 2), (x + 100, y - 2), (x + 500, y)]),
                                         {'name': 'Route', 'route_ref': '43', 'avg_daily_validations': None, 'source': 'AYNA'})]),
        'metro_stations': collection([feature('metro:1', Point(x - 500, y), {'name': 'Metro', 'avg_daily_entries': 0, 'source': 'Metro'})]),
        'cycleways': collection([feature('lane:1', LineString([(x, y - 1000), (x + 500, y - 1000)]), {'name': 'AYNA', 'length_m': 500, 'source': 'AYNA'})]),
        'bus_recommendations': collection([bus]), 'bike_recommendations': collection([bike]),
    }
    paths = {layer: folder / (layer + '.geojson') for layer in docs}
    for layer, document in docs.items():
        paths[layer].write_text(json.dumps(document))
    sim = export.simulation
    ctx, items, audits = sim.load_inputs({'grid': paths['grid'], 'bus_stop': paths['bus_recommendations'], 'bike_corridor': paths['bike_recommendations']})
    paths['intervention_scenarios'] = folder / 'intervention_scenarios.json'
    paths['intervention_scenarios'].write_text(sim.serialize(sim.build_document(ctx, items, audits)))
    return paths


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.paths = fixture_paths(self.folder)
        with patch('sys.stdout', new_callable=io.StringIO):
            self.context = export.load_context(self.paths)
        self.summary = export.make_summary(self.context, '2026-10-19T00:00:00Z')
        self.directory = self.folder / 'complete'
        self.archive = self.folder / 'frontend_complete.zip'
        with patch('sys.stdout', new_callable=io.StringIO):
            export.write_package(self.directory, self.archive, self.context, self.summary)

    def verify(self):
        with patch('sys.stdout', new_callable=io.StringIO):
            return export.verify_package(self.directory, self.archive, self.context)

    def test_package_summary_source_identity_scenarios_and_zip_layout(self):
        self.verify()
        self.assertEqual(set(p.name for p in self.directory.iterdir()), set(export.FILENAMES))
        self.assertEqual(self.summary['grid_cells'], 2)
        self.assertEqual(self.summary['population_estimate'], 100)
        self.assertEqual(self.summary['null_population_cells'], 1)
        self.assertEqual(self.summary['high_bus_priority_cells'], 1)
        self.assertEqual(self.summary['high_bike_priority_cells'], 0)
        self.assertEqual(self.summary['simulation_counts'], {'bus_stop': 1, 'bike_corridor': 1, 'total': 2})
        self.assertEqual((self.directory / 'intervention_scenarios.json').read_bytes(), self.paths['intervention_scenarios'].read_bytes())
        with ZipFile(self.archive) as archive:
            self.assertEqual(set(archive.namelist()), {'data/' + name for name in export.FILENAMES} | {'README.md'})
            self.assertIsNone(archive.testzip())
            self.assertIn('not additive', archive.read('README.md').decode().replace('are not additive', 'not additive'))

    def test_saved_property_null_geometry_and_summary_tampering_fail(self):
        for filename, mutate in [
            ('bus_stops.geojson', lambda d: d['features'][0]['properties'].update(name='Invented')),
            ('metro_stations.geojson', lambda d: d['features'][0]['properties'].update(avg_daily_entries=None)),
            ('grid.geojson', lambda d: d['features'][1]['properties'].update(population=0)),
            ('bus_recommendations.geojson', lambda d: d['features'][0]['properties'].pop('reason')),
            ('bike_recommendations.geojson', lambda d: d['features'][0]['geometry']['coordinates'][0].__setitem__(0, 49.0)),
            ('summary.json', lambda d: d.update(population_estimate=999)),
            ('summary.json', lambda d: d.pop('high_bike_priority_cells')),
            ('intervention_scenarios.json', lambda d: d['scenarios'][0].update(population_improved=100))]:
            path = self.directory / filename
            original = path.read_bytes()
            document = json.loads(original)
            mutate(document)
            path.write_text(json.dumps(document))
            with self.subTest(filename=filename), self.assertRaises((ValueError, RuntimeError)):
                self.verify()
            path.write_bytes(original)

    def test_route_accuracy_is_checked_even_for_an_internally_consistent_bad_builder(self):
        doc = json.loads((self.directory / 'bus_routes.geojson').read_bytes())
        for coordinate in doc['features'][0]['geometry']['coordinates']:
            coordinate[1] += .001
        (self.directory / 'bus_routes.geojson').write_text(json.dumps(doc))
        with self.assertRaisesRegex((ValueError, RuntimeError), 'Route|route'):
            self.verify()

    def test_zip_extra_missing_and_changed_members_are_rejected(self):
        original = self.archive.read_bytes()
        for name in ('data/extra.json', '../unexpected.txt', 'data/grid.geojson'):
            with ZipFile(self.archive, 'a') as archive:
                archive.writestr(name, '{}')
            with self.assertRaises((ValueError, RuntimeError)):
                self.verify()
            self.archive.write_bytes(original)

    def test_offline_verify_only_preserves_all_files_and_mtimes(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in [*self.directory.iterdir(), self.archive, *self.paths.values()]}
        with (patch('socket.socket.connect', side_effect=AssertionError('network forbidden')),
              patch.object(export, 'INPUTS', self.paths), patch.object(export, 'COMPLETE', self.directory),
              patch.object(export, 'ARCHIVE', self.archive),
              patch.object(export, 'mkdtemp', side_effect=AssertionError('staging forbidden')),
              patch.object(export.os, 'replace', side_effect=AssertionError('replacement forbidden')),
              patch.object(Path, 'mkdir', side_effect=AssertionError('mkdir forbidden')),
              patch('sys.stdout', new_callable=io.StringIO)):
            self.assertEqual(export.main(['--verify-only']), 0)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})

    def test_independent_verification_rejects_consistently_tampered_source_and_export(self):
        # A copied error in both processed JSON and export must still be caught
        # by the scalar calculation, rather than only comparing source bytes.
        changed = json.loads(self.paths['intervention_scenarios'].read_bytes())
        changed['scenarios'][0]['population_improved'] = 999
        raw = json.dumps(changed).encode()
        altered_context = dict(self.context, raw={**self.context['raw'], 'intervention_scenarios': raw})
        (self.directory / 'intervention_scenarios.json').write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'independent'):
            export.verify_package(self.directory, self.archive, altered_context)

    def test_missing_exports_verify_only_fails_without_staging(self):
        with (patch.object(export, 'COMPLETE', self.folder / 'missing'),
              patch.object(export, 'load_context', side_effect=AssertionError('unnecessary read')),
              patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as error):
            export.main(['--verify-only'])
        self.assertNotEqual(error.exception.code, 0)

    def test_corrupt_archive_exits_with_a_clear_error(self):
        self.archive.write_bytes(b'corrupt archive')
        with (patch.object(export, 'INPUTS', self.paths), patch.object(export, 'COMPLETE', self.directory),
              patch.object(export, 'ARCHIVE', self.archive), patch('sys.stdout', new_callable=io.StringIO),
              patch('sys.stderr', new_callable=io.StringIO) as stderr, self.assertRaises(SystemExit) as error):
            export.main(['--verify-only'])
        self.assertNotEqual(error.exception.code, 0)
        self.assertIn('ERROR:', stderr.getvalue())
        self.assertNotIn('Traceback', stderr.getvalue())

    def test_staged_validation_failure_preserves_old_package_and_inputs(self):
        before = {p: p.read_bytes() for p in [*self.directory.iterdir(), self.archive, *self.paths.values()]}
        with (patch.object(export, 'INPUTS', self.paths), patch.object(export, 'COMPLETE', self.directory),
              patch.object(export, 'ARCHIVE', self.archive), patch.object(export, 'EXPORT_ROOT', self.folder),
              patch.object(export, 'verify_package', side_effect=ValueError('injected invalid stage')),
              patch('sys.stdout', new_callable=io.StringIO), patch('sys.stderr', new_callable=io.StringIO),
              self.assertRaises(SystemExit) as error):
            export.main([])
        self.assertNotEqual(error.exception.code, 0)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(list(self.folder.glob('.frontend-complete-*')), [])


class PublicationTests(unittest.TestCase):
    def test_every_failed_replacement_restores_previous_complete_package(self):
        for failure in (1, 2, 3, 4):
            with self.subTest(replacement=failure), tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                stage = folder / 'stage'; stage.mkdir()
                complete = folder / 'complete'; complete.mkdir()
                (complete / 'old').write_text('old complete')
                archive = folder / 'frontend_complete.zip'; archive.write_text('old zip')
                (stage / 'complete').mkdir()
                (stage / 'complete' / 'new').write_text('new complete')
                (stage / 'frontend_complete.zip').write_text('new zip')
                original_replace = export.os.replace
                calls = 0

                def fail_once(source, target):
                    nonlocal calls
                    calls += 1
                    if calls == failure:
                        raise OSError('injected publication failure')
                    return original_replace(source, target)

                with patch.object(export.os, 'replace', side_effect=fail_once), self.assertRaises(OSError):
                    export.publish(stage, complete, archive)
                self.assertEqual((complete / 'old').read_text(), 'old complete')
                self.assertEqual(archive.read_text(), 'old zip')
                self.assertFalse((complete / 'new').exists())

    def test_first_publication_failure_leaves_no_partial_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); stage = folder / 'stage'; stage.mkdir()
            (stage / 'complete').mkdir(); (stage / 'complete' / 'new').write_text('new')
            (stage / 'frontend_complete.zip').write_text('zip')
            complete, archive = folder / 'complete', folder / 'frontend_complete.zip'
            original_replace = export.os.replace

            def fail_zip(source, target):
                if Path(source).name == 'frontend_complete.zip':
                    raise OSError('injected ZIP publication failure')
                return original_replace(source, target)

            with patch.object(export.os, 'replace', side_effect=fail_zip), self.assertRaises(OSError):
                export.publish(stage, complete, archive)
            self.assertFalse(complete.exists())
            self.assertFalse(archive.exists())

    def test_rollback_failure_preserves_recovery_backups(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary); stage = folder / 'stage'; stage.mkdir()
            complete = folder / 'complete'; complete.mkdir(); (complete / 'old').write_text('recover me')
            archive = folder / 'frontend_complete.zip'; archive.write_text('old zip')
            (stage / 'complete').mkdir(); (stage / 'frontend_complete.zip').write_text('new zip')
            original_replace = export.os.replace

            def fail_install_and_rollback(source, target):
                if Path(source).name in ('frontend_complete.zip', 'previous-complete'):
                    raise OSError('filesystem unavailable')
                return original_replace(source, target)

            with patch.object(export.os, 'replace', side_effect=fail_install_and_rollback), self.assertRaises(export.RecoveryRequired):
                export.publish(stage, complete, archive)
            self.assertEqual((stage / 'previous-complete' / 'old').read_text(), 'recover me')


if __name__ == '__main__':
    unittest.main()
