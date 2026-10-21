#!/usr/bin/env python3
"""Transparent, data-quality-aware 250 m Baku mobility priority model.

Run from the repository root:
  .venv/bin/python scripts/13_calculate_priority.py
  .venv/bin/python scripts/13_calculate_priority.py --verify-only

No dependencies beyond Python's standard library. Input is the Step 15A GeoJSON.
The constants/weights live in config/scoring_v1.json (versioned separately).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path('data/processed/grid/baku_grid_pois.geojson')
DEFAULT_OUTPUT = Path('data/processed/grid/baku_grid_scored.geojson')
DEFAULT_CONFIG = Path('config/scoring_v1.json')
REQUIRED_FIELDS = (
    'id', 'population', 'nearest_bus_stop_m', 'nearest_metro_m',
    'nearest_cycleway_m', 'bus_stops_500m', 'pois_nearby',
    'pois_500m_by_type', 'bus_priority', 'bike_priority', 'mobility_gap',
)
SCORE_FIELDS = ('bus_priority', 'bike_priority', 'mobility_gap')
ADDED_FIELDS = (
    'scoring_model_version', 'population_index', 'essential_destination_index',
    'demand_index', 'bus_access_deficit', 'bike_access_deficit',
    'metro_access_deficit', 'scoring_quality',
)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def positive_finite(value: Any, label: str, *, zero_ok: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{label}: expected numeric value; got {value!r}')
    number = float(value)
    if not math.isfinite(number) or number < 0 or (not zero_ok and number == 0):
        raise ValueError(f'{label}: expected finite nonnegative value; got {value!r}')
    return number


def nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{label}: expected nonnegative integer; got {value!r}')
    return value


def weighted_sum_is_one(weights: dict[str, Any], label: str) -> None:
    values = [positive_finite(v, f'{label}.{k}') for k, v in weights.items()]
    if not math.isclose(sum(values), 1.0, abs_tol=1e-9):
        raise ValueError(f'{label} weights must sum to 1; got {sum(values)}')


def validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config.get('model_version'), str) or not config['model_version']:
        raise ValueError('model_version must be nonempty string')
    positive_finite(config['population_saturation_per_250m_cell'], 'population_saturation', zero_ok=False)
    positive_finite(config['poi_saturation_weighted_count'], 'poi_saturation', zero_ok=False)
    positive_finite(config['high_priority_reporting_threshold'], 'reporting_threshold')
    positive_finite(config['poor_population_coverage_below'], 'poor_coverage')
    if not 0 <= config['poor_population_coverage_below'] <= 1:
        raise ValueError('poor_population_coverage_below must lie in [0,1]')
    for key, value in config['poi_weights'].items():
        if not isinstance(key, str) or not key:
            raise ValueError('POI category names must be strings')
        positive_finite(value, f'poi_weights.{key}')
    weighted_sum_is_one(config['demand_weights'], 'demand_weights')
    weighted_sum_is_one(config['mobility_gap_weights'], 'mobility_gap_weights')
    for mode in ('bus', 'bike', 'metro'):
        data = config[mode]
        low = positive_finite(data['good_distance_m'], f'{mode}.good_distance_m')
        high = positive_finite(data['severe_distance_m'], f'{mode}.severe_distance_m')
        if high <= low:
            raise ValueError(f'{mode}: severe distance must exceed good distance')
    weighted_sum_is_one({
        'distance_weight': config['bus']['distance_weight'],
        'stop_scarcity_weight': config['bus']['stop_scarcity_weight'],
    }, 'bus deficit')
    nonnegative_int(config['bus']['sufficient_stops_500m'], 'sufficient_stops_500m')
    if config['bus']['sufficient_stops_500m'] == 0:
        raise ValueError('sufficient_stops_500m must be positive')


def deficit(distance: Any, thresholds: dict[str, Any], label: str) -> float:
    distance = positive_finite(distance, label)
    return clamp((distance - thresholds['good_distance_m']) /
                 (thresholds['severe_distance_m'] - thresholds['good_distance_m']))


def quality_label(properties: dict[str, Any], config: dict[str, Any]) -> str:
    if properties['population'] is None:
        return 'unknown_population'
    fraction = properties.get('valid_pixel_fraction')
    if fraction is None:
        return 'population_coverage_unreported'
    fraction = positive_finite(fraction, 'valid_pixel_fraction')
    if fraction > 1:
        raise ValueError(f'valid_pixel_fraction cannot exceed 1: {fraction}')
    if fraction < config['poor_population_coverage_below']:
        return 'low_population_pixel_coverage'
    if fraction < 1 - 1e-9:
        return 'partial_population_pixel_coverage'
    return 'full_population_pixel_coverage'


def calculate_scores(properties: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Compute scores for one grid cell without modifying the input dict."""
    for field in REQUIRED_FIELDS:
        if field not in properties:
            raise ValueError(f'{properties.get("id", "<unknown>")}: missing field {field}')
    if not isinstance(properties['id'], str) or not properties['id']:
        raise ValueError('grid id must be a nonempty string')

    # Validate core metrics even if population is unavailable.
    bus_distance = positive_finite(properties['nearest_bus_stop_m'], 'nearest_bus_stop_m')
    bike_distance = positive_finite(properties['nearest_cycleway_m'], 'nearest_cycleway_m')
    metro_distance = positive_finite(properties['nearest_metro_m'], 'nearest_metro_m')
    stops = nonnegative_int(properties['bus_stops_500m'], 'bus_stops_500m')
    poi_total = nonnegative_int(properties['pois_nearby'], 'pois_nearby')
    by_type = properties['pois_500m_by_type']
    if not isinstance(by_type, dict):
        raise ValueError('pois_500m_by_type must be a dictionary, not missing or text')
    for category, count in by_type.items():
        nonnegative_int(count, f'pois_500m_by_type[{category}]')
    if sum(by_type.values()) != poi_total:
        raise ValueError('pois_nearby does not equal the sum of per-category POI counts')
    population = properties['population']
    if population is not None:
        population = positive_finite(population, 'population')

    result: dict[str, Any] = {
        'scoring_model_version': config['model_version'],
        'scoring_quality': quality_label(properties, config),
    }
    if population is None:
        for field in SCORE_FIELDS + (
            'population_index', 'essential_destination_index', 'demand_index',
            'bus_access_deficit', 'bike_access_deficit', 'metro_access_deficit',
        ):
            result[field] = None
        return result

    pop_index = clamp(population / config['population_saturation_per_250m_cell'])
    weighted_pois = sum(
        config['poi_weights'][category] * by_type.get(category, 0)
        for category in config['poi_weights']
    )
    essential_index = clamp(weighted_pois / config['poi_saturation_weighted_count'])
    demand = (config['demand_weights']['population'] * pop_index
              + config['demand_weights']['essential_destinations'] * essential_index)

    bus_distance_deficit = deficit(bus_distance, config['bus'], 'nearest_bus_stop_m')
    scarcity = clamp(1 - stops / config['bus']['sufficient_stops_500m'])
    bus_deficit = (config['bus']['distance_weight'] * bus_distance_deficit
                   + config['bus']['stop_scarcity_weight'] * scarcity)
    bike_deficit = deficit(bike_distance, config['bike'], 'nearest_cycleway_m')
    metro_deficit = deficit(metro_distance, config['metro'], 'nearest_metro_m')
    gap = (config['mobility_gap_weights']['bus'] * bus_deficit
           + config['mobility_gap_weights']['bike'] * bike_deficit
           + config['mobility_gap_weights']['metro'] * metro_deficit)

    result.update({
        'population_index': round(pop_index, 6),
        'essential_destination_index': round(essential_index, 6),
        'demand_index': round(demand, 6),
        'bus_access_deficit': round(bus_deficit, 6),
        'bike_access_deficit': round(bike_deficit, 6),
        'metro_access_deficit': round(metro_deficit, 6),
        'bus_priority': round(100 * demand * bus_deficit, 2),
        'bike_priority': round(100 * demand * bike_deficit, 2),
        'mobility_gap': round(100 * demand * gap, 2),
    })
    return result


def load_feature_collection(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as handle:
        document = json.load(handle)
    if not isinstance(document, dict) or document.get('type') != 'FeatureCollection':
        raise ValueError(f'{path}: expected GeoJSON FeatureCollection')
    if not isinstance(document.get('features'), list):
        raise ValueError(f'{path}: expected features list')
    crs = document.get('crs')
    if crs is not None:
        crs_text = json.dumps(crs)
        if '4326' not in crs_text and 'CRS84' not in crs_text:
            raise ValueError(f'{path}: unsupported CRS metadata: {crs_text}')
    return document


def calculate_document(input_doc: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    validate_config(config)
    seen_ids = set()
    output_features = []
    for feature in input_doc['features']:
        if feature.get('type') != 'Feature' or not isinstance(feature.get('properties'), dict):
            raise ValueError('invalid GeoJSON feature or missing properties')
        if feature.get('geometry', {}).get('type') not in ('Polygon', 'MultiPolygon'):
            raise ValueError(f'{feature["properties"].get("id")}: unsupported grid geometry')
        original = feature['properties']
        uid = original.get('id')
        if uid in seen_ids:
            raise ValueError(f'duplicate grid ID: {uid}')
        seen_ids.add(uid)
        enriched = dict(original)
        enriched.update(calculate_scores(original, config))
        output_features.append({**feature, 'properties': enriched})
    config_canonical = json.dumps(config, ensure_ascii=False, sort_keys=True,
                                  separators=(',', ':')).encode('utf-8')
    output = dict(input_doc)
    output['features'] = output_features
    output['scoring'] = {
        'model_version': config['model_version'],
        'methodology': 'SCORING_METHODOLOGY.md',
        'configuration': 'config/scoring_v1.json',
        'configuration_sha256': hashlib.sha256(config_canonical).hexdigest(),
        'meaning': 'larger score means higher need; not construction feasibility',
        'measurement': 'straight-line proximity from interior grid representative points',
        'missing_population_policy': 'all three scores null when population is null',
    }
    return output


def verify_document(input_doc: dict[str, Any], output_doc: dict[str, Any],
                    config: dict[str, Any]) -> None:
    expected = calculate_document(input_doc, config)
    if output_doc != expected:
        for idx, (actual, correct) in enumerate(zip(output_doc.get('features', []),
                                                     expected['features'])):
            if actual != correct:
                raise ValueError(f'verification mismatch at grid feature {idx}, '
                                 f'id={correct["properties"]["id"]}')
        raise ValueError('verification mismatch: output feature count or metadata differs')
    print('RELOAD / RECOMPUTATION: PASSED; source geometry, IDs, other fields and scores preserved')


def summarize(output_doc: dict[str, Any], config: dict[str, Any]) -> None:
    features = output_doc['features']
    qualities = Counter(f['properties']['scoring_quality'] for f in features)
    print(f'MODEL: {config["model_version"]}; grid features: {len(features)}')
    print(f'QUALITY COUNTS: {dict(qualities)}')
    for field in SCORE_FIELDS:
        rows = [f['properties'] for f in features if f['properties'][field] is not None]
        vals = [p[field] for p in rows]
        threshold = config['high_priority_reporting_threshold']
        print(f'SCORE {field}: count={len(vals)} null={len(features)-len(vals)} '
              f'min={min(vals) if vals else None} '
              f'median={statistics.median(vals) if vals else None} '
              f'p90={sorted(vals)[int(0.90*(len(vals)-1))] if vals else None} '
              f'max={max(vals) if vals else None} '
              f'high_>={threshold}={sum(x>=threshold for x in vals)}')
        leaders = sorted(rows, key=lambda p: (-p[field], p['id']))[:5]
        print(f'TOP 5 {field}: ' + json.dumps([
            {'id': p['id'], 'score': p[field], 'population': p['population'],
             'pois_nearby': p['pois_nearby'],
             'quality': p['scoring_quality']}
            for p in leaders], ensure_ascii=False))


def atomic_write(doc: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8',
                                         dir=path.parent, prefix='.priority_',
                                         suffix='.tmp', delete=False) as handle:
            temp_name = handle.name
            json.dump(doc, handle, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':'))
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.remove(temp_name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    with args.config.open('r', encoding='utf-8') as handle:
        config = json.load(handle)
    validate_config(config)
    source = load_feature_collection(args.input)
    if args.verify_only:
        saved = load_feature_collection(args.output)
        verify_document(source, saved, config)
        summarize(saved, config)
        return
    processed = calculate_document(source, config)
    atomic_write(processed, args.output)
    saved = load_feature_collection(args.output)
    verify_document(source, saved, config)
    summarize(saved, config)
    print(f'Output saved: {args.output}')


if __name__ == '__main__':
    main()
