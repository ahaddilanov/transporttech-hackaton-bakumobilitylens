#!/usr/bin/env python3
"""Step 16A: preliminary route-aligned bus-stop candidates; see methodology.

Run .venv/bin/python scripts/14_recommend_bus_stops.py [--verify-only].
Only the recommendations output is written. No downloads or dependencies added.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import geopandas as gpd
import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / 'data/processed/recommendations/bus_recommendations.geojson'
INPUT_PATHS = {
    'grid': ROOT / 'data/processed/grid/baku_grid_scored.geojson',
    'routes': ROOT / 'data/processed/transport/bus_routes_with_demand.geojson',
    'stops': ROOT / 'data/processed/transport/bus_stops.geojson',
    'boundary': ROOT / 'data/processed/boundaries/baku_boundary.geojson',
}
METRIC_CRS = 'EPSG:32639'
METHOD_VERSION = 'baku-bus-recommendations-v1.0'
MIN_PRIORITY = 60
MAX_ROUTE_DISTANCE_M = 300
MIN_STOP_DISTANCE_M = 300
COVERAGE_DISTANCE_M = 500
MIN_PROPOSAL_DISTANCE_M = 700
MAX_RECOMMENDATIONS = 20
# Only for reprojection/GEOS roundoff in independent verification, not screening.
VERIFY_TOLERANCE_M = 1e-6
TO_WGS84 = Transformer.from_crs(METRIC_CRS, 'EPSG:4326', always_xy=True).transform
TO_METRIC = Transformer.from_crs('EPSG:4326', METRIC_CRS, always_xy=True).transform
RANKING = ('ascending tuple (-population_affected, -priority, '
           '-access_improvement_m, source_grid_id, nearby_route_id, route_part_index); '
           'unrounded values; greedy retain if >=700m from every retained proposal; first 20')
LIMITATIONS = [
    'Straight-line distance, not walking-network distance; grid origins are interior representative points.',
    'OSM bus-stop coverage is incomplete; mapped stops do not establish active service.',
    'Route geometry does not prove permission or feasibility to establish a stop.',
    'Field/engineering assessment is required, including road safety, pedestrian access and operations.',
    'No verified stop-route membership is claimed; nearby_route_ref is geometric context only.',
    'BakuBus validations are route-level only and are not used as stop-level demand or in ranking.',
    'WorldPop population is modeled; null population is excluded and partial coverage is not extrapolated.',
    'Each benefit is standalone against the baseline; overlapping proposal benefits must not be summed.',
]


def report(label, values):
    print(label + ': ' + json.dumps(values, ensure_ascii=False, allow_nan=False), flush=True)


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def transform(project, geometry):
    return shapely.transform(geometry, project, interleaved=False)


def coverage(candidate, origins, props):
    """Evaluate every grid origin, including low-priority and unknown cells."""
    distances = shapely.distance(origins, candidate)
    baseline = np.array([p['nearest_bus_stop_m'] for p in props], dtype=float)
    newly = (baseline > COVERAGE_DISTANCE_M) & (np.minimum(baseline, distances) <= COVERAGE_DISTANCE_M)
    known = [i for i in np.flatnonzero(newly) if props[i]['population'] is not None]
    unknown = sum(props[i]['population'] is None for i in np.flatnonzero(newly))
    population = math.fsum(props[i]['population'] for i in known)
    current = math.fsum(props[i]['population'] * baseline[i] for i in known) / population if population > 0 else None
    after = math.fsum(props[i]['population'] * min(baseline[i], distances[i]) for i in known) / population if population > 0 else None
    partial = sum(p.get('valid_pixel_fraction') is not None and p['valid_pixel_fraction'] < 1
                  for p in (props[i] for i in known))
    unreported = sum(props[i].get('valid_pixel_fraction') is None for i in known)
    return {
        'population_affected': population, 'current_access_m': current, 'new_access_m': after,
        'access_improvement_m': current - after if population > 0 else None,
        'newly_covered_cells': len(known), 'unknown_population_cells': unknown,
        'population_quality_notes': ['modeled_population_not_census_or_ridership',
                                     f'unknown_population_cells_excluded={unknown}',
                                     f'partial_population_cells={partial}',
                                     f'population_coverage_unreported_cells={unreported}'],
    }


def load_layer(path, geometry_types, required_properties):
    raw = path.read_bytes()
    document = json.loads(raw)
    if (document.get('type') != 'FeatureCollection' or not isinstance(document.get('features'), list)
            or not document['features']):
        raise ValueError(f'{path.name}: mandatory nonempty FeatureCollection required.')
    props = []
    for feature in document['features']:
        p = feature.get('properties')
        if (feature.get('type') != 'Feature' or not isinstance(p, dict)
                or any(k not in p for k in required_properties)):
            raise ValueError(f'{path.name}: malformed feature or missing required fields.')
        props.append(p)
    if 'id' in required_properties:
        ids = [p['id'] for p in props]
        if (any(type(i) is not str or not i for i in ids) or len(ids) != len(set(ids))
                or any(f.get('id') != p['id'] for f, p in zip(document['features'], props))):
            raise ValueError(f'{path.name}: unique consistent nonempty string IDs required.')
    frame = gpd.read_file(path)
    coords = shapely.get_coordinates(frame.geometry.array)
    if (len(frame) != len(props) or frame.crs is None or frame.crs.to_epsg() != 4326
            or frame.geometry.isna().any() or frame.is_empty.any() or not frame.is_valid.all()
            or not frame.geom_type.isin(geometry_types).all()
            or shapely.has_z(frame.geometry.array).any() or not np.isfinite(coords).all()
            or (np.abs(coords[:, 0]) > 180).any() or (np.abs(coords[:, 1]) > 90).any()):
        raise ValueError(f'{path.name}: valid nonempty 2D EPSG:4326 {geometry_types} required.')
    if 'id' in required_properties and frame['id'].tolist() != [p['id'] for p in props]:
        raise ValueError(f'{path.name}: reload changed source ID ordering.')
    metric = frame.to_crs(METRIC_CRS).geometry.to_numpy()
    if not np.isfinite(shapely.get_coordinates(metric)).all() or not shapely.is_valid(metric).all():
        raise ValueError(f'{path.name}: invalid metric geometry.')
    audit = {'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest(),
             'feature_count': len(props), 'crs': 'EPSG:4326',
             'geometry_types': frame.geom_type.value_counts().to_dict(),
             'properties': sorted({k for p in props for k in p})}
    report('INPUT SCHEMA', audit)
    return props, metric, frame.geometry.to_numpy(), audit


def route_parts(geometries, props):
    records = []
    for geometry, p in zip(geometries, props, strict=True):
        parts = geometry.geoms if geometry.geom_type == 'MultiLineString' else [geometry]
        for index, line in enumerate(parts):
            if line.length <= 0:
                raise ValueError('AYNA route contains a zero-length part; no silent filtering.')
            records.append(((p['id'], index), line, p))
    records.sort(key=lambda record: record[0])
    return (np.array([r[1] for r in records], dtype=object),
            [r[0] for r in records], [r[2] for r in records])


def load_inputs():
    props, polygons, _, grid_audit = load_layer(
        INPUT_PATHS['grid'], ['Polygon', 'MultiPolygon'],
        ['id', 'population', 'bus_priority', 'nearest_bus_stop_m', 'valid_pixel_fraction'])
    for p in props:
        for field in ('population', 'nearest_bus_stop_m', 'bus_priority', 'valid_pixel_fraction'):
            value = p[field]
            if value is None and field != 'nearest_bus_stop_m':
                continue
            if (not numeric(value) or value < 0 or (field == 'bus_priority' and value > 100)
                    or (field == 'valid_pixel_fraction' and value > 1)):
                raise ValueError(f"{p['id']}: invalid {field}.")
    rp, routes, _, route_audit = load_layer(
        INPUT_PATHS['routes'], ['LineString', 'MultiLineString'], ['id', 'source', 'route_ref'])
    if any(p['source'] != 'AYNA' or (p['route_ref'] is not None and type(p['route_ref']) is not str) for p in rp):
        raise ValueError('Expected actual AYNA lines with string/null source route references.')
    _, stops, _, stop_audit = load_layer(INPUT_PATHS['stops'], ['Point'], ['id'])
    _, boundaries, native_boundaries, boundary_audit = load_layer(
        INPUT_PATHS['boundary'], ['Polygon', 'MultiPolygon'], ['shapeID', 'shapeName'])
    if len(boundaries) != 1:
        raise ValueError('Expected one Baku study boundary.')
    origins = shapely.point_on_surface(polygons)
    if not shapely.contains(polygons, origins).all():
        raise ValueError('Grid origins must be strictly inside their source polygons.')
    baseline = np.array([p['nearest_bus_stop_m'] for p in props])
    nearest = shapely.STRtree(stops).nearest(origins)
    if not np.allclose(baseline, shapely.distance(origins, stops[nearest]), rtol=0, atol=VERIFY_TOLERANCE_M):
        raise ValueError('Grid baseline distances are stale/inconsistent with the mapped-stop input.')
    parts, keys, part_props = route_parts(routes, rp)
    return {'origins': origins, 'props': props, 'routes': parts, 'route_keys': keys,
            'route_props': part_props, 'stops': stops, 'boundary': boundaries[0],
            'boundary_wgs84': native_boundaries[0],
            'input_audits': {'grid': grid_audit, 'routes': route_audit,
                             'stops': stop_audit, 'boundary': boundary_audit}}


def stable_id(seed_id, route_id, part_index, projected):
    # No rank/array position in identity. Six decimal places are micrometers.
    payload = [METHOD_VERSION, seed_id, route_id, part_index,
               f'{projected.x:.6f}', f'{projected.y:.6f}']
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return 'baku:bus-stop-recommendation:' + digest


def ranking_key(feature):
    p = feature['properties']
    return (-p['population_affected'], -p['priority'], -p['access_improvement_m'],
            p['source_grid_id'], p['nearby_route_id'], p['route_part_index'])


def build_document(ctx):
    stats = dict.fromkeys(('total_seeds', 'route_distance_rejections', 'outside_baku_rejections',
                          'existing_stop_rejections', 'zero_gain_rejections',
                          'qualified_before_deduplication', 'duplicates',
                          'qualified_beyond_limit', 'final_count'), 0)
    route_tree, stop_tree = shapely.STRtree(ctx['routes']), shapely.STRtree(ctx['stops'])
    candidates = []
    for origin, seed in zip(ctx['origins'], ctx['props'], strict=True):
        if seed['population'] is None or seed['bus_priority'] is None or seed['bus_priority'] < MIN_PRIORITY:
            continue
        stats['total_seeds'] += 1
        # Exact nearest full line part, never nearest vertex/centroid. Return all
        # equidistant parts so stable source keys resolve spatial-index ties.
        indices = route_tree.query_nearest(origin, all_matches=True)
        index = min(indices, key=lambda i: ctx['route_keys'][i])
        line = ctx['routes'][index]
        if origin.distance(line) > MAX_ROUTE_DISTANCE_M:
            stats['route_distance_rejections'] += 1
            continue
        projected = line.interpolate(line.project(origin))
        geographic = transform(TO_WGS84, projected)
        # Evaluate exactly the serialized WGS84 position after roundtrip.
        point = transform(TO_METRIC, geographic)
        if not ctx['boundary'].contains(point) or not ctx['boundary_wgs84'].contains(geographic):
            stats['outside_baku_rejections'] += 1
            continue
        if point.distance(ctx['stops'][stop_tree.nearest(point)]) < MIN_STOP_DISTANCE_M:
            stats['existing_stop_rejections'] += 1
            continue
        benefit = coverage(point, ctx['origins'], ctx['props'])
        if benefit['population_affected'] <= 0:
            stats['zero_gain_rejections'] += 1
            continue
        route_id, part_index = ctx['route_keys'][index]
        identifier = stable_id(seed['id'], route_id, part_index, projected)
        p = {'id': identifier, 'priority': seed['bus_priority'], **benefit,
             'reason': ['high_bus_priority_seed', 'projected_onto_nearest_AYNA_route_geometry',
                        'at_least_300m_from_mapped_existing_stop',
                        'positive_modeled_population_gain_within_500m',
                        'preliminary_requires_field_and_engineering_assessment'],
             'source_grid_id': seed['id'], 'nearby_route_ref': ctx['route_props'][index]['route_ref'],
             'nearby_route_id': route_id, 'route_part_index': part_index,
             'method_version': METHOD_VERSION}
        candidates.append({'type': 'Feature', 'id': identifier, 'properties': p,
                           'geometry': mapping(geographic)})
    stats['qualified_before_deduplication'] = len(candidates)
    retained, retained_points = [], []
    for feature in sorted(candidates, key=ranking_key):
        point = transform(TO_METRIC, shape(feature['geometry']))
        if any(point.distance(other) < MIN_PROPOSAL_DISTANCE_M for other in retained_points):
            stats['duplicates'] += 1
            continue
        retained.append(feature)
        retained_points.append(point)
    stats['qualified_beyond_limit'] = max(0, len(retained) - MAX_RECOMMENDATIONS)
    selected = retained[:MAX_RECOMMENDATIONS]
    stats['final_count'] = len(selected)
    return {'type': 'FeatureCollection', 'features': selected, 'screening': stats,
            'methodology': {'method_version': METHOD_VERSION, 'distance_crs': METRIC_CRS,
                            'output_crs': 'EPSG:4326', 'distance_units': 'meters',
                            'seed_min_bus_priority': MIN_PRIORITY,
                            'max_seed_route_distance_m': MAX_ROUTE_DISTANCE_M,
                            'min_existing_stop_distance_m': MIN_STOP_DISTANCE_M,
                            'coverage_distance_m': COVERAGE_DISTANCE_M,
                            'min_proposal_distance_m': MIN_PROPOSAL_DISTANCE_M,
                            'max_recommendations': MAX_RECOMMENDATIONS, 'ranking': RANKING,
                            'priority': 'unchanged source seed bus_priority; higher means greater local need',
                            'limitations': LIMITATIONS, 'inputs': ctx['input_audits']},
            'population_summary': {'known_population_cells': sum(p['population'] is not None for p in ctx['props']),
                                   'unknown_population_cells': sum(p['population'] is None for p in ctx['props'])}}


def verify_document(saved, expected, ctx):
    """Independently check EVERY proposal; no index or coverage() reuse here.

    Exhaustive route/stop distances and a scalar all-grid population calculation
    check the indexed generation path. Exact expected-document equality separately
    checks ranking, completeness, screening statistics and input provenance.
    """
    if (saved.get('type') != 'FeatureCollection' or not isinstance(saved.get('features'), list)
            or len(saved['features']) > MAX_RECOMMENDATIONS or 'crs' in saved):
        raise ValueError('Invalid recommendations FeatureCollection/count/CRS declaration.')
    seed_lookup = {p['id']: (p, origin) for p, origin in zip(ctx['props'], ctx['origins'], strict=True)}
    points, ids = [], set()
    for feature in saved['features']:
        p = feature.get('properties', {})
        identifier = p.get('id')
        if (feature.get('type') != 'Feature' or type(identifier) is not str or not identifier
                or identifier in ids or feature.get('id') != identifier):
            raise ValueError('Invalid/duplicate recommendation feature or string ID.')
        ids.add(identifier)
        if (not numeric(p.get('priority')) or not 0 <= p['priority'] <= 100
                or any(not numeric(p.get(k)) or p[k] < 0 for k in (
                    'population_affected', 'current_access_m', 'new_access_m', 'access_improvement_m'))
                or p['population_affected'] <= 0 or p['access_improvement_m'] <= 0
                or type(p.get('reason')) is not list or not p['reason']
                or any(type(r) is not str or not r for r in p['reason'])
                or p.get('method_version') != METHOD_VERSION):
            raise ValueError('Contract V1 field types, range or positive benefit failed.')
        for field in ('newly_covered_cells', 'unknown_population_cells', 'route_part_index'):
            if type(p.get(field)) is not int or p[field] < 0:
                raise ValueError(f'Invalid nonnegative integer {field}.')
        if (type(p.get('population_quality_notes')) is not list
                or any(type(note) is not str for note in p['population_quality_notes'])):
            raise ValueError('Invalid population quality notes.')
        geometry = feature.get('geometry', {})
        xy = geometry.get('coordinates')
        if (geometry.get('type') != 'Point' or type(xy) not in (list, tuple) or len(xy) != 2
                or not all(numeric(v) for v in xy) or not (-180 <= xy[0] <= 180 and -90 <= xy[1] <= 90)):
            raise ValueError('Expected finite 2D EPSG:4326 Point [longitude, latitude].')
        geographic = shape(geometry)
        point = transform(TO_METRIC, geographic)
        if (not point.is_valid or point.is_empty or not ctx['boundary'].contains(point)
                or not ctx['boundary_wgs84'].contains(geographic)):
            raise ValueError('Proposal Point must be strictly inside Baku.')
        if p.get('source_grid_id') not in seed_lookup:
            raise ValueError('Missing source grid seed.')
        seed, origin = seed_lookup[p['source_grid_id']]
        if (seed['population'] is None or seed['bus_priority'] is None
                or seed['bus_priority'] < MIN_PRIORITY or p['priority'] != seed['bus_priority']):
            raise ValueError('Seed eligibility or unchanged local priority failed.')
        # Exhaustive line-part scan checks the spatial index and tie resolution.
        route_index = min(range(len(ctx['routes'])),
                          key=lambda i: (origin.distance(ctx['routes'][i]), *ctx['route_keys'][i]))
        line = ctx['routes'][route_index]
        route_id, part_index = ctx['route_keys'][route_index]
        projection = line.interpolate(line.project(origin))
        if (p.get('nearby_route_id') != route_id or p['route_part_index'] != part_index
                or p.get('nearby_route_ref') != ctx['route_props'][route_index]['route_ref']
                or origin.distance(line) > MAX_ROUTE_DISTANCE_M
                or point.distance(projection) > VERIFY_TOLERANCE_M
                or point.distance(line) > VERIFY_TOLERANCE_M
                or identifier != stable_id(seed['id'], route_id, part_index, projection)):
            raise ValueError('Nearest AYNA line, projection, route context or stable ID failed.')
        if min(point.distance(stop) for stop in ctx['stops']) < MIN_STOP_DISTANCE_M - VERIFY_TOLERANCE_M:
            raise ValueError('Proposal is less than 300m from a mapped existing stop.')
        if any(point.distance(other) < MIN_PROPOSAL_DISTANCE_M - VERIFY_TOLERANCE_M for other in points):
            raise ValueError('Proposal spacing is less than 700m.')
        points.append(point)
        # Intentionally scalar and independent of the vectorized coverage helper.
        residents, weighted_before, weighted_after = [], [], []
        known_count, unknown_count, partial_count, unreported_count = 0, 0, 0, 0
        for cell_origin, cell in zip(ctx['origins'], ctx['props'], strict=True):
            baseline = cell['nearest_bus_stop_m']
            after = min(baseline, cell_origin.distance(point))
            if baseline <= COVERAGE_DISTANCE_M or after > COVERAGE_DISTANCE_M:
                continue
            population = cell['population']
            if population is None:
                unknown_count += 1
                continue
            known_count += 1
            fraction = cell.get('valid_pixel_fraction')
            partial_count += fraction is not None and fraction < 1
            unreported_count += fraction is None
            residents.append(population)
            weighted_before.append(population * baseline)
            weighted_after.append(population * after)
        population = math.fsum(residents)
        if population <= 0:
            raise ValueError('Independent calculation found no positive known-population gain.')
        before = math.fsum(weighted_before) / population
        after = math.fsum(weighted_after) / population
        for field, value in (('population_affected', population), ('current_access_m', before),
                             ('new_access_m', after), ('access_improvement_m', before - after)):
            if not math.isclose(p[field], value, rel_tol=1e-12, abs_tol=VERIFY_TOLERANCE_M):
                raise ValueError(f'Independent calculation mismatch: {identifier} / {field}.')
        if (p['newly_covered_cells'] != known_count or p['unknown_population_cells'] != unknown_count
                or p['population_quality_notes'] != [
                    'modeled_population_not_census_or_ridership',
                    f'unknown_population_cells_excluded={unknown_count}',
                    f'partial_population_cells={partial_count}',
                    f'population_coverage_unreported_cells={unreported_count}']
                or not math.isclose(p['current_access_m'] - p['new_access_m'],
                                    p['access_improvement_m'], rel_tol=0, abs_tol=VERIFY_TOLERANCE_M)):
            raise ValueError('Independent cell counts, quality flags or improvement identity failed.')
    # Canonical JSON equality also distinguishes true from 1 and rejects NaN.
    if json.dumps(saved, sort_keys=True, allow_nan=False) != json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError('Saved output differs from input-derived ranking, candidates, statistics or metadata.')
    print(f'Independent verification PASSED: {len(points)} proposals; geometry, nearest route, '
          'seed eligibility, stop/proposal spacing, fields and all-grid weighted improvements; '
          'complete ranked output matches inputs.', flush=True)


def verify_saved(path, expected, ctx):
    saved = json.loads(path.read_bytes())
    verify_document(saved, expected, ctx)
    if saved['features']:
        frame = gpd.read_file(path)
        if (len(frame) != len(saved['features']) or frame.crs is None or frame.crs.to_epsg() != 4326
                or not frame.geom_type.eq('Point').all() or not frame.is_valid.all()
                or frame['id'].tolist() != [f['id'] for f in saved['features']]):
            raise ValueError('Reload failed EPSG:4326 Point/count/ID checks.')
    print('Saved GeoJSON verification PASSED.', flush=True)


def save_output(document, ctx, path=OUTPUT_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                prefix='.bus-recommendations-', suffix='.geojson', delete=False) as output:
            temporary = Path(output.name)
            json.dump(document, output, ensure_ascii=False, allow_nan=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        verify_saved(temporary, document, ctx)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f'Saved preliminary bus-stop recommendations: {path}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true',
                        help='Recompute and independently verify existing output without writing.')
    args = parser.parse_args()
    if args.verify_only and not OUTPUT_PATH.is_file():
        raise ValueError(f'No saved output to verify: {OUTPUT_PATH}; no files written.')
    ctx = load_inputs()
    document = build_document(ctx)
    report('SCREENING', document['screening'])
    report('POPULATION AVAILABILITY', document['population_summary'])
    if not document['features']:
        print('No candidates pass the fixed thresholds. See SCREENING for rejection counts; '
              'zero seeds means no cell has both known population and bus_priority >=60. '
              'Thresholds have not been relaxed.', flush=True)
    if args.verify_only:
        verify_saved(OUTPUT_PATH, document, ctx)
    else:
        save_output(document, ctx)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
