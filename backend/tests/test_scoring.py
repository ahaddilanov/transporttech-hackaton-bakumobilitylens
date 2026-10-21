"""Synthetic tests: do not require the real Baku input dataset."""
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('scoring', ROOT / 'scripts' / '13_calculate_priority.py')
scoring = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scoring)
CONFIG = json.loads((ROOT / 'config' / 'scoring_v1.json').read_text(encoding='utf-8'))


def props(**changes):
    record = {
        'id': 'baku:test-cell',
        'population': 200.0,
        'valid_pixel_fraction': 1.0,
        'nearest_bus_stop_m': 700.0,
        'nearest_metro_m': 2500.0,
        'nearest_cycleway_m': 1500.0,
        'bus_stops_500m': 0,
        'pois_nearby': 0,
        'pois_500m_by_type': {
            'SCHOOL': 0, 'HOSPITAL': 0, 'KINDERGARTEN': 0,
            'PHARMACY': 0, 'CUSTOMIZABLE_POINT_5': 0,
        },
        'bus_priority': None,
        'bike_priority': None,
        'mobility_gap': None,
    }
    record.update(changes)
    return record


class ScoringTests(unittest.TestCase):
    def setUp(self):
        scoring.validate_config(CONFIG)

    def test_null_population_never_becomes_zero(self):
        r = scoring.calculate_scores(props(population=None, valid_pixel_fraction=0), CONFIG)
        self.assertEqual(r['scoring_quality'], 'unknown_population')
        self.assertTrue(all(r[f] is None for f in scoring.SCORE_FIELDS))

    def test_zero_demand_means_zero_priority(self):
        r = scoring.calculate_scores(props(population=0), CONFIG)
        self.assertTrue(all(r[f] == 0 for f in scoring.SCORE_FIELDS))

    def test_severe_access_and_full_population_reaches_full_scores(self):
        r = scoring.calculate_scores(props(
            population=450, nearest_bus_stop_m=2000, bus_stops_500m=0,
            nearest_metro_m=5000, nearest_cycleway_m=5000,
            pois_nearby=3, pois_500m_by_type={
                'SCHOOL': 3, 'HOSPITAL': 0, 'KINDERGARTEN': 0,
                'PHARMACY': 0, 'CUSTOMIZABLE_POINT_5': 0,
            },
        ), CONFIG)
        self.assertEqual([r[f] for f in scoring.SCORE_FIELDS], [100, 100, 100])

    def test_better_bus_access_cannot_increase_bus_priority(self):
        far = scoring.calculate_scores(props(nearest_bus_stop_m=1100), CONFIG)
        near = scoring.calculate_scores(props(nearest_bus_stop_m=400, bus_stops_500m=1), CONFIG)
        self.assertGreaterEqual(far['bus_priority'], near['bus_priority'])

    def test_more_population_does_not_reduce_priority(self):
        low = scoring.calculate_scores(props(population=50), CONFIG)
        high = scoring.calculate_scores(props(population=300), CONFIG)
        for f in scoring.SCORE_FIELDS:
            self.assertGreaterEqual(high[f], low[f])

    def test_more_essential_pois_does_not_reduce_priority(self):
        baseline = scoring.calculate_scores(props(), CONFIG)
        with_school = scoring.calculate_scores(props(pois_nearby=1, pois_500m_by_type={
            'SCHOOL': 1, 'HOSPITAL': 0, 'KINDERGARTEN': 0,
            'PHARMACY': 0, 'CUSTOMIZABLE_POINT_5': 0,
        }), CONFIG)
        for f in scoring.SCORE_FIELDS:
            self.assertGreaterEqual(with_school[f], baseline[f])

    def test_ambiguous_mixed_category_does_not_gain_weight(self):
        baseline = scoring.calculate_scores(props(), CONFIG)
        mixed = scoring.calculate_scores(props(pois_nearby=1, pois_500m_by_type={
            'SCHOOL': 0, 'HOSPITAL': 0, 'KINDERGARTEN': 0,
            'PHARMACY': 0, 'CUSTOMIZABLE_POINT_5': 1,
        }), CONFIG)
        self.assertEqual(mixed['essential_destination_index'], baseline['essential_destination_index'])

    def test_partial_population_coverage_is_flagged_not_downweighted(self):
        original = scoring.calculate_scores(props(valid_pixel_fraction=1.0), CONFIG)
        partial = scoring.calculate_scores(props(valid_pixel_fraction=0.4), CONFIG)
        self.assertEqual(partial['scoring_quality'], 'low_population_pixel_coverage')
        self.assertEqual([original[f] for f in scoring.SCORE_FIELDS],
                         [partial[f] for f in scoring.SCORE_FIELDS])

    def test_inconsistent_poi_counts_fail(self):
        with self.assertRaisesRegex(ValueError, 'does not equal'):
            scoring.calculate_scores(props(pois_nearby=1), CONFIG)

    def test_document_recomputation_and_reload(self):
        geometry = {'type': 'Polygon', 'coordinates': [
            [[49.85, 40.4], [49.86, 40.4], [49.86, 40.41],
             [49.85, 40.41], [49.85, 40.4]],
        ]}
        src = {'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': props(), 'geometry': geometry},
        ]}
        output = scoring.calculate_document(src, CONFIG)
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'test.geojson'
            scoring.atomic_write(output, path)
            loaded = scoring.load_feature_collection(path)
            scoring.verify_document(src, loaded, CONFIG)
            loaded['features'][0]['properties']['bus_priority'] += 1
            with self.assertRaisesRegex(ValueError, 'mismatch'):
                scoring.verify_document(src, loaded, CONFIG)


if __name__ == '__main__':
    unittest.main()
