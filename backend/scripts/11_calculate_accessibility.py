"""Calculate baseline straight-line accessibility without changing grid geometry.

Origins are representative_point() inside each clipped grid Polygon/MultiPolygon
AFTER projection to EPSG:32639. This is an interior measurement point, not a
population-weighted origin, station centroid or walking-network location.
Shapely STRtree finds nearest bus Points, metro ENTRANCE Points and full
cycleway LineString/MultiLineString geometries. dwithin counts all mapped bus
stop records at distance <=500 m, including distinct co-located identifiers.

All distances are planar meters in EPSG:32639. Original EPSG:4326 grid JSON
coordinates, IDs, population/null flags, other properties and metadata are
preserved exactly. Only the four baseline fields are populated; no routes,
POIs, scores, service relationships or recommendations are inferred. Mandatory
missing/empty/invalid input layers fail explicitly before output replacement.
"""

import argparse
import copy
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

import geopandas as gpd
import numpy as np
import shapely


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRID_PATH = PROJECT_ROOT / 'data/processed/grid/baku_grid_population.geojson'
BUS_PATH = PROJECT_ROOT / 'data/processed/transport/bus_stops.geojson'
METRO_PATH = PROJECT_ROOT / 'data/processed/transport/metro_entrances.geojson'
CYCLEWAY_PATH = PROJECT_ROOT / 'data/processed/transport/cycleways.geojson'
OUTPUT_PATH = PROJECT_ROOT / 'data/processed/grid/baku_grid_accessibility.geojson'
METRIC_CRS = 'EPSG:32639'
COMPUTED_FIELDS = ('nearest_bus_stop_m', 'nearest_metro_m', 'nearest_cycleway_m', 'bus_stops_500m')
PENDING_FIELDS = ('bus_routes_nearby', 'pois_nearby', 'bus_priority', 'bike_priority', 'mobility_gap')
METHOD = 'straight_line_distance_from_grid_representative_point'
RADIUS_METERS = 500.0
SAMPLE_SIZE = 5


def report(label, values):
    print(label + ': ' + json.dumps(values, ensure_ascii=False, allow_nan=False), flush=True)


def load_layer(path, geometry_types, required_properties=()):
    if not path.is_file():
        raise RuntimeError(f'Mandatory input layer missing: {path}; no accessibility output written.')
    raw = path.read_bytes()
    document = json.loads(raw)
    if (not isinstance(document, dict) or document.get('type') != 'FeatureCollection'
            or not isinstance(document.get('features'), list) or not document['features']):
        raise RuntimeError(f'{path.name}: mandatory layer is empty or not a FeatureCollection.')
    identifiers = []
    for index, feature in enumerate(document['features'], 1):
        if (not isinstance(feature, dict) or feature.get('type') != 'Feature'
                or not isinstance(feature.get('properties'), dict)):
            raise RuntimeError(f'{path.name}: malformed feature at source index {index}.')
        properties = feature['properties']; identifier = properties.get('id')
        if (type(identifier) is not str or not identifier or feature.get('id') != identifier
                or any(field not in properties for field in required_properties)):
            raise RuntimeError(f'{path.name}: missing/inconsistent string ID or required properties at index {index}.')
        identifiers.append(identifier)
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError(f'{path.name}: duplicate source IDs; no silent deduplication.')
    frame = gpd.read_file(path)
    if (len(frame) != len(document['features']) or frame.crs is None or frame.crs.to_epsg() != 4326
            or frame.geometry.isna().any() or frame.is_empty.any() or not frame.is_valid.all()
            or not frame.geom_type.isin(geometry_types).all()
            or frame['id'].tolist() != identifiers):
        raise RuntimeError(f'{path.name}: expected EPSG:4326 nonempty valid {geometry_types}, consistent counts/IDs.')
    xy = shapely.get_coordinates(frame.geometry.array)
    if (not np.isfinite(xy).all() or (np.abs(xy[:, 0]) > 180).any() or (np.abs(xy[:, 1]) > 90).any()):
        raise RuntimeError(f'{path.name}: invalid longitude/latitude coordinates.')
    metric = frame.to_crs(METRIC_CRS)
    if not np.isfinite(shapely.get_coordinates(metric.geometry.array)).all() or not metric.is_valid.all():
        raise RuntimeError(f'{path.name}: projected geometries failed validation.')
    audit = {'file': str(path.relative_to(PROJECT_ROOT)), 'sha256': hashlib.sha256(raw).hexdigest(),
             'feature_count': len(frame), 'unique_id_count': len(set(identifiers)), 'crs': str(frame.crs),
             'geometry_types': frame.geom_type.value_counts().to_dict(),
             'properties': sorted({k for f in document['features'] for k in f['properties']}),
             'bounds_lon_lat': frame.total_bounds.tolist(), 'validation': 'passed; no records filtered'}
    report('INPUT LAYER', audit)
    return document, frame, metric.geometry.to_numpy(), audit


def measurement_origins(polygons):
    origins = gpd.GeoSeries(polygons, crs=METRIC_CRS).representative_point().to_numpy()
    if (shapely.is_empty(origins).any() or not shapely.is_valid(origins).all()
            or not shapely.contains(polygons, origins).all()):
        raise RuntimeError('Measurement representative points must be strictly inside their grid geometries.')
    return origins


def compute_metrics(origins, bus_points, metro_points, cycle_lines):
    values = {}
    for field, targets in zip(COMPUTED_FIELDS[:3], (bus_points, metro_points, cycle_lines), strict=True):
        if not len(targets):
            raise RuntimeError(f'Mandatory layer for {field} is empty; zero distances would be misleading.')
        tree = shapely.STRtree(targets)
        nearest = tree.nearest(origins)
        # GEOS computes exact distance to line segments, not vertex proxies.
        values[field] = shapely.distance(origins, targets[nearest])
    pairs = shapely.STRtree(bus_points).query(origins, predicate='dwithin', distance=RADIUS_METERS)
    values['bus_stops_500m'] = np.bincount(pairs[0], minlength=len(origins))
    for field in COMPUTED_FIELDS[:3]:
        if not np.isfinite(values[field]).all() or (values[field] < 0).any():
            raise RuntimeError(f'Nonfinite or negative values for {field}.')
    counts = values['bus_stops_500m']
    if (counts < 0).any() or (counts > len(bus_points)).any() or counts.dtype.kind not in 'iu':
        raise RuntimeError('Bus-stop counts must be nonnegative integers <= source point count.')
    if not np.array_equal(counts > 0, values['nearest_bus_stop_m'] <= RADIUS_METERS):
        raise RuntimeError('500 m counts contradict nearest bus-stop distances.')
    return values


def verify_sample(origins, values, bus_points, metro_points, cycle_lines, indices):
    # Five deterministic cells only: an independent full-target check validates
    # index results without an all-cells/all-targets comparison loop.
    for index in indices:
        for field, targets in zip(COMPUTED_FIELDS[:3], (bus_points, metro_points, cycle_lines), strict=True):
            measured = float(shapely.distance(origins[index], targets).min())
            if not math.isclose(float(values[field][index]), measured, rel_tol=0, abs_tol=1e-6):
                raise RuntimeError(f'Independent sample nearest-distance validation failed: {field}, row {index}.')
        count = int((shapely.distance(origins[index], bus_points) <= RADIUS_METERS).sum())
        if count != values['bus_stops_500m'][index]:
            raise RuntimeError(f'Independent sample radius-count validation failed: row {index}.')
    print(f'Independent spatial checks PASSED: {len(indices)} deterministic sample cells', flush=True)


def summary_statistics(values):
    summary = {}
    for field, array in values.items():
        stats = {'count': len(array), 'null_count': 0, 'minimum': float(array.min()),
                 'median': float(np.median(array)), 'maximum': float(array.max()),
                 'mean': float(array.mean()), 'zero_count': int((array == 0).sum())}
        if field == 'bus_stops_500m':
            stats.update({'minimum': int(array.min()), 'maximum': int(array.max()),
                          'cells_with_one_or_more_stops': int((array > 0).sum())})
        else:
            stats.update({'units': 'meters', 'cells_within_500m': int((array <= 500).sum()),
                          'cells_over_10km': int((array > 10000).sum())})
        summary[field] = stats
        report('FIELD SUMMARY ' + field, stats)
    return summary


def verify_preservation(original, result):
    original_members = {k: v for k, v in original.items() if k != 'features'}
    restored_members = {k: v for k, v in result.items() if k not in ('features', 'accessibility_metadata')}
    if original_members != restored_members or len(original['features']) != len(result['features']):
        raise RuntimeError('Original grid top-level metadata or cell count changed.')
    identifiers = []
    for before, after in zip(original['features'], result['features'], strict=True):
        if ({k: v for k, v in before.items() if k != 'properties'} !=
                {k: v for k, v in after.items() if k != 'properties'}):
            raise RuntimeError(f"Original feature ID/geometry/foreign members changed: {before.get('id')}")
        expected = {k: v for k, v in before['properties'].items() if k not in COMPUTED_FIELDS}
        preserved = {k: v for k, v in after['properties'].items() if k not in COMPUTED_FIELDS}
        # JSON equality also distinguishes false from 0, unlike Python equality.
        if json.dumps(expected, sort_keys=True, allow_nan=False) != json.dumps(preserved, sort_keys=True, allow_nan=False):
            raise RuntimeError(f"Original population/flags/properties changed: {before.get('id')}")
        p = after['properties']; identifiers.append(p['id'])
        for field in COMPUTED_FIELDS[:3]:
            if type(p[field]) not in (int, float) or not math.isfinite(p[field]) or p[field] < 0:
                raise RuntimeError(f'Invalid distance type/value: {field}.')
        if type(p['bus_stops_500m']) is not int or p['bus_stops_500m'] < 0:
            raise RuntimeError('bus_stops_500m must be a nonnegative JSON integer.')
        if any(p[field] is not None for field in PENDING_FIELDS):
            raise RuntimeError('Uncalculated routes, POIs and priority fields must remain null.')
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError('Output grid IDs are not unique.')


def build_document():
    original, grid_frame, polygons, grid_audit = load_layer(
        GRID_PATH, ['Polygon', 'MultiPolygon'], ('population', *COMPUTED_FIELDS, *PENDING_FIELDS))
    if 'accessibility_metadata' in original:
        raise RuntimeError('Unexpected existing accessibility metadata in baseline grid; refusing to overwrite it.')
    for feature in original['features']:
        properties = feature['properties']; population = properties['population']
        if (any(properties[field] is not None for field in (*COMPUTED_FIELDS, *PENDING_FIELDS))
                or (population is not None and (type(population) not in (int, float)
                    or not math.isfinite(population) or population < 0))):
            raise RuntimeError('Baseline grid requires null pending metrics and finite nonnegative population or null.')
    _, _, bus, bus_audit = load_layer(BUS_PATH, ['Point'])
    metro_document, _, metro, metro_audit = load_layer(METRO_PATH, ['Point'], ('station_id',))
    if any(type(f['properties']['station_id']) is not str or not f['properties']['station_id']
           for f in metro_document['features']):
        raise RuntimeError('Metro entrance station_id links must be nonempty strings.')
    _, _, cycleways, cycleway_audit = load_layer(CYCLEWAY_PATH, ['LineString', 'MultiLineString'])
    origins = measurement_origins(polygons)
    values = compute_metrics(origins, bus, metro, cycleways)
    sample_indices = np.unique(np.linspace(0, len(origins) - 1, min(SAMPLE_SIZE, len(origins)), dtype=int))
    verify_sample(origins, values, bus, metro, cycleways, sample_indices)
    result = copy.deepcopy(original)
    for index, feature in enumerate(result['features']):
        feature['properties'].update({field: int(values[field][index]) if field == 'bus_stops_500m'
                                     else float(values[field][index]) for field in COMPUTED_FIELDS})
    sample = [{'id': result['features'][i]['id'], 'population': result['features'][i]['properties']['population'],
               'origin_epsg32639_xy': [origins[i].x, origins[i].y],
               **{field: result['features'][i]['properties'][field] for field in COMPUTED_FIELDS}}
              for i in sample_indices]
    summary = summary_statistics(values)
    report('DETERMINISTIC GRID SAMPLE', sample)
    null_population = sum(f['properties']['population'] is None for f in original['features'])
    report('GRID PRESERVATION', {'input_cells': len(origins), 'output_cells': len(origins),
           'null_population_cells_preserved': null_population,
           'population_sum_preserved': math.fsum(f['properties']['population'] for f in original['features']
                                                if f['properties']['population'] is not None)})
    result['accessibility_metadata'] = {
        'method': METHOD, 'distance_crs': METRIC_CRS, 'output_crs': 'EPSG:4326', 'distance_units': 'meters',
        'measurement_origin': 'representative_point inside each clipped grid geometry after projection to EPSG:32639',
        'nearest_bus_stop_m': 'nearest mapped OSM bus-stop Point',
        'nearest_metro_m': 'nearest metro entrance Point; station representatives not used',
        'nearest_cycleway_m': 'exact planar distance to complete LineString/MultiLineString segments',
        'bus_stops_500m': 'count of distinct mapped stop records at planar distance <=500 m; co-located IDs retained',
        'spatial_index': 'Shapely STRtree nearest and dwithin; no new dependencies',
        'limitations': ['straight-line distances, not walking-network travel distances',
                        'representative point is not population-weighted; distances vary across each cell',
                        'mapped inputs do not establish completeness, safety or operational status',
                        'no stop-to-route service relationship inferred',
                        'null population stays unknown; no zero-population interpretation'],
        'inputs': {'grid': grid_audit, 'bus_stops': bus_audit, 'metro_entrances': metro_audit, 'cycleways': cycleway_audit},
        'summary': summary, 'deterministic_sample': sample, 'null_population_cells_preserved': null_population,
    }
    verify_preservation(original, result)
    return original, result, grid_frame


def verify_saved(path, original, expected, grid_frame):
    with path.open(encoding='utf-8') as source:
        saved = json.load(source)
    if saved != expected:
        raise RuntimeError('Saved output differs from input-derived distances/counts, properties, geometries or metadata.')
    verify_preservation(original, saved)
    frame = gpd.read_file(path)
    if (len(frame) != len(original['features']) or frame.crs is None or frame.crs.to_epsg() != 4326
            or not frame.geom_type.isin(['Polygon', 'MultiPolygon']).all()
            or frame.is_empty.any() or not frame.is_valid.all()
            or frame['id'].tolist() != grid_frame['id'].tolist()
            or not shapely.equals_exact(frame.geometry.array, grid_frame.geometry.array, tolerance=0).all()):
        raise RuntimeError('Reload feature counts/IDs/geometries or EPSG:4326 validation failed.')
    for field in COMPUTED_FIELDS:
        if not np.array_equal(frame[field].to_numpy(), np.array([f['properties'][field] for f in saved['features']])):
            raise RuntimeError(f'Reload numeric properties changed: {field}.')
    if (int(frame['population'].isna().sum()) != sum(f['properties']['population'] is None for f in original['features'])
            or not frame[list(PENDING_FIELDS)].isna().all().all()):
        raise RuntimeError('Reload population/pending null counts changed.')
    print('Reload verification PASSED: all cells, unique IDs, exact geometries, EPSG:4326, population/null flags, properties and integer counts', flush=True)


def save_output(original, result, grid_frame):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=OUTPUT_PATH.parent,
                                prefix='.accessibility-', suffix='.geojson', delete=False) as output:
            temporary = Path(output.name)
            json.dump(result, output, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            output.write('\n'); output.flush(); os.fsync(output.fileno())
        verify_saved(temporary, original, result, grid_frame)
        os.replace(temporary, OUTPUT_PATH)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f'Saved baseline straight-line accessibility: {OUTPUT_PATH}', flush=True)


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Recompute baseline fields and validate existing output without writing.')
    args = parser.parse_args()
    original, result, grid_frame = build_document()
    if args.verify_only:
        verify_saved(OUTPUT_PATH, original, result, grid_frame)
    else:
        save_output(original, result, grid_frame)
    print(f'Total runtime: {perf_counter() - started:.2f} seconds', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
