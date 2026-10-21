#!/usr/bin/env python3
"""Deterministic standalone accessibility scenarios; see SIMULATION_METHODOLOGY.md."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

import numpy as np
from pyproj import CRS, Transformer
import shapely
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
INPUTS = {
    'grid': ROOT / 'data/processed/grid/baku_grid_scored.geojson',
    'bus_stop': ROOT / 'data/processed/recommendations/bus_recommendations.geojson',
    'bike_corridor': ROOT / 'data/processed/recommendations/bike_recommendations.geojson',
}
OUTPUT = ROOT / 'data/processed/scenarios/intervention_scenarios.json'
MODEL = 'baku-accessibility-simulation-v1.0'
COVERAGE_M = 500.0
IMPROVEMENT_TOLERANCE_M = 1e-6
METRIC_CRS = 'EPSG:32639'
BASELINES = {'bus_stop': 'nearest_bus_stop_m', 'bike_corridor': 'nearest_cycleway_m'}
BENEFIT_FIELDS = {'bus_stop': 'population_affected', 'bike_corridor': 'population_coverage_gain'}
METRICS = ('population_improved', 'coverage_before_pct', 'coverage_after_pct',
           'coverage_change_pp', 'avg_access_improvement_m', 'affected_cells',
           'newly_covered_population', 'newly_covered_cells',
           'unknown_population_cells_affected', 'unknown_population_cells_newly_covered')
LIMITATIONS = [
    'Hypothetical straight-line proximity from grid representative points; not walking or cycling network access.',
    'Modeled population is not ridership; missing population is unknown, never imputed as zero.',
    'Incomplete mapped infrastructure and partial population coverage limit these estimates.',
    'Proposals are not engineering-validated, approved or proven safe or operationally feasible.',
    'Each scenario uses the unchanged baseline independently; overlapping gains must never be summed as a combined citywide gain.',
    'Bicycle simulation uses the AYNA baseline; recommendations additionally exclude residents near mapped existing OSM cycling infrastructure.',
]


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def close(a, b):
    return numeric(a) and numeric(b) and math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-8)


def make_grid(properties, origins):
    """Keep unknowns as NaN plus an explicit mask, never as observed zeros."""
    order = sorted(range(len(properties)), key=lambda i: properties[i]['id'])
    props = [properties[i] for i in order]
    population = np.array([p['population'] for p in props], dtype=float)
    known = ~np.isnan(population)
    return {'props': props, 'origins': np.asarray(origins, dtype=object)[order],
            'population': population, 'known': known, 'known_count': int(known.sum()),
            'total_population': math.fsum(population[known]),
            'baseline': {kind: np.array([p[field] for p in props], dtype=float)
                         for kind, field in BASELINES.items()}}


def simulate(intervention, grid):
    """Vectorized full-geometry distances for all cells, including beyond 500 m."""
    baseline = grid['baseline'][intervention['type']]
    distance = shapely.distance(grid['origins'], intervention['geometry'])
    after = np.minimum(baseline, distance)
    reduction = baseline - after
    improved = reduction > IMPROVEMENT_TOLERANCE_M
    newly = (baseline > COVERAGE_M) & (after <= COVERAGE_M)
    known, population = grid['known'], grid['population']
    improved_population = math.fsum(population[known & improved])
    total = grid['total_population']
    before_pct = 100 * math.fsum(population[known & (baseline <= COVERAGE_M)]) / total if total > 0 else None
    after_pct = 100 * math.fsum(population[known & (after <= COVERAGE_M)]) / total if total > 0 else None
    return {
        'intervention_id': intervention['id'], 'intervention_type': intervention['type'],
        'population_improved': improved_population if grid['known_count'] else None,
        'coverage_before_pct': before_pct, 'coverage_after_pct': after_pct,
        'coverage_change_pp': after_pct - before_pct if total > 0 else None,
        'avg_access_improvement_m': math.fsum(population[known & improved] * reduction[known & improved]) / improved_population
        if improved_population > 0 else None,
        'affected_cells': int(np.count_nonzero(known & improved)),
        'newly_covered_population': math.fsum(population[known & newly]) if grid['known_count'] else None,
        'newly_covered_cells': int(np.count_nonzero(known & newly)),
        'unknown_population_cells_affected': int(np.count_nonzero(~known & improved)),
        'unknown_population_cells_newly_covered': int(np.count_nonzero(~known & newly)),
        'model_version': MODEL, 'coverage_radius_m': COVERAGE_M,
    }


def reject_constant(value):
    raise ValueError(f'Non-finite JSON constant: {value}')


def read_layer(path, kind):
    """Read bytes once for parsing and provenance; RFC 7946 defaults to WGS84."""
    raw = path.read_bytes()
    document = json.loads(raw, parse_constant=reject_constant)
    if type(document) is not dict or document.get('type') != 'FeatureCollection' or type(document.get('features')) is not list:
        raise ValueError(f'{path}: expected a FeatureCollection.')
    if kind == 'grid' and not document['features']:
        raise ValueError('The population grid must not be empty.')
    crs = document.get('crs')
    if crs is not None:
        name = crs.get('properties', {}).get('name') if isinstance(crs, dict) else None
        if not name or not CRS.from_user_input(name).equals(CRS.from_epsg(4326), ignore_axis_order=True):
            raise ValueError(f'{path}: input must be EPSG:4326 longitude/latitude.')
    kinds = {'grid': {'Polygon', 'MultiPolygon'}, 'bus_stop': {'Point'},
             'bike_corridor': {'LineString', 'MultiLineString'}}[kind]
    required = ['id', 'population', *BASELINES.values()] if kind == 'grid' else ['id', BENEFIT_FIELDS[kind]]
    props, geometries, seen = [], [], set()
    for feature in document['features']:
        if type(feature) is not dict or type(feature.get('geometry')) is not dict:
            raise ValueError(f'{path}: malformed feature or missing geometry.')
        p = feature.get('properties')
        if (feature.get('type') != 'Feature' or type(p) is not dict or any(k not in p for k in required)
                or type(p['id']) is not str or not p['id'] or p['id'] in seen
                or ('id' in feature and feature['id'] != p['id'])):
            raise ValueError(f'{path}: missing fields, duplicate or inconsistent string IDs.')
        seen.add(p['id'])
        fields = ['population', *BASELINES.values()] if kind == 'grid' else [BENEFIT_FIELDS[kind]]
        for field in fields:
            value = p[field]
            if value is None and field not in BASELINES.values():
                continue
            if not numeric(value) or value < 0:
                raise ValueError(f'{path}: {field} must be finite and nonnegative; baseline cannot be null.')
        for field in ('newly_covered_cells', 'unknown_population_cells', 'existing_osm_coverage_excluded_cells'):
            if field in p and (type(p[field]) is not int or p[field] < 0):
                raise ValueError(f'{path}: invalid {field}.')
        geometry = shape(feature['geometry'])
        coordinates = shapely.get_coordinates(geometry)
        if (geometry.geom_type not in kinds or geometry.is_empty or not geometry.is_valid
                or shapely.has_z(geometry) or shapely.has_m(geometry)
                or not np.isfinite(coordinates).all()
                or (np.abs(coordinates[:, 0]) > 180).any() or (np.abs(coordinates[:, 1]) > 90).any()):
            raise ValueError(f'{path}: invalid nonempty 2D {sorted(kinds)} geometry or WGS84 bounds.')
        props.append(p)
        geometries.append(geometry)
    project = Transformer.from_crs(4326, METRIC_CRS, always_xy=True).transform
    metric = shapely.transform(np.array(geometries, dtype=object), project, interleaved=False)
    if not np.isfinite(shapely.get_coordinates(metric)).all() or not shapely.is_valid(metric).all():
        raise ValueError(f'{path}: invalid projected geometry.')
    if kind == 'bike_corridor' and any(g.length <= 0 for g in metric):
        raise ValueError(f'{path}: corridor geometry must have positive length.')
    audit = {'file': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
             'sha256': hashlib.sha256(raw).hexdigest(), 'feature_count': len(props),
             'geometry_types': dict(sorted(Counter(g.geom_type for g in geometries).items())),
             'fields': sorted({field for p in props for field in p})}
    return props, metric, document, audit


def load_inputs(paths=None):
    paths = INPUTS if paths is None else paths
    props, polygons, _, grid_audit = read_layer(paths['grid'], 'grid')
    grid = make_grid(props, shapely.point_on_surface(polygons))
    interventions, audits = [], {'grid': grid_audit}
    seen = set()
    for kind in BASELINES:
        recommendations, geometries, source, audits[kind] = read_layer(paths[kind], kind)
        metadata = source.get('metadata', source.get('methodology', {}))
        recorded_hash = metadata.get('inputs', {}).get('grid', {}).get('sha256')
        if recorded_hash is not None and recorded_hash != grid_audit['sha256']:
            raise ValueError(f'{kind}: recommendations refer to a different scored grid.')
        audits[kind]['recommendation_grid_hash_check'] = 'match' if recorded_hash else 'unavailable'
        for p, geometry in zip(recommendations, geometries, strict=True):
            if p['id'] in seen:
                raise ValueError(f'Duplicate intervention ID across datasets: {p["id"]}')
            seen.add(p['id'])
            interventions.append({'id': p['id'], 'type': kind, 'geometry': geometry, 'properties': p})
    return grid, sorted(interventions, key=lambda item: (item['type'], item['id'])), audits


def reconcile(scenario, intervention):
    """Compare equal definitions, or expose the documented bicycle policy difference.

    Three input layers cannot independently identify OSM-excluded cells: count
    consistency is evidence of a policy difference, not verification of that gate.
    """
    p, kind = intervention['properties'], intervention['type']
    field = BENEFIT_FIELDS[kind]
    reported, modeled = p[field], scenario['newly_covered_population']
    result = {'recommendation_field': field, 'recommendation_value': reported,
              'simulation_value': modeled, 'difference_population': None,
              'status': 'unavailable', 'recommendation_method_version': p.get('method_version')}
    if reported is None or modeled is None:
        result['explanation'] = 'A population total is unavailable; null is not treated as zero.'
        return result
    result['difference_population'] = modeled - reported
    count_pairs = [('newly_covered_cells', 'newly_covered_cells'),
                   ('unknown_population_cells_newly_covered', 'unknown_population_cells')]
    differences = [scenario[s] - p[r] for s, r in count_pairs if r in p]
    counts_match = all(value == 0 for value in differences)
    excluded = p.get('existing_osm_coverage_excluded_cells')
    exclusions_recorded = kind == 'bike_corridor' and type(excluded) is int and excluded > 0
    if close(modeled, reported) and counts_match and not exclusions_recorded:
        result['status'] = 'match'
        return result
    if (kind == 'bike_corridor' and p.get('method_version') == 'baku-bike-corridors-v1.0'
            and type(excluded) is int and excluded > 0 and len(differences) == 2
            and all(value >= 0 for value in differences) and sum(differences) == excluded
            and (modeled > reported or close(modeled, reported))):
        result.update(status='consistent_with_osm_exclusion',
                      recommendation_existing_osm_excluded_cells=excluded,
                      additional_known_population_cells=differences[0],
                      additional_unknown_population_cells=differences[1],
                      osm_gate_recomputed_by_simulator=False,
                      explanation='Recommendation additionally requires distance to existing OSM cycling infrastructure >500m. '
                      'Simulation uses the requested AYNA-only baseline. Count differences agree with recorded exclusions; '
                      'these three inputs cannot independently verify which cells OSM excludes. See the source audit in SIMULATION_METHODOLOGY.md.')
        return result
    raise ValueError(f'{intervention["id"]}: unexplained recommendation reconciliation mismatch '
                     f'(simulation={modeled}, recommendation={reported}, cell differences={differences}).')


def build_document(grid, interventions, audits):
    scenarios = []
    for item in sorted(interventions, key=lambda i: (i['type'], i['id'])):
        scenario = simulate(item, grid)
        scenario['reconciliation'] = reconcile(scenario, item)
        scenarios.append(scenario)
    summary = {}
    for kind in BASELINES:
        rows = [s for s in scenarios if s['intervention_type'] == kind]
        summary[kind] = {'scenario_count': len(rows),
                         'reconciliation_status_counts': dict(sorted(Counter(s['reconciliation']['status'] for s in rows).items()))}
        for field in ('population_improved', 'newly_covered_population', 'coverage_change_pp'):
            values = [s[field] for s in rows if s[field] is not None]
            summary[kind][field + '_range'] = [min(values), max(values)] if values else None
    return {'metadata': {'model_version': MODEL, 'distance_crs': METRIC_CRS,
                         'coverage_radius_m': COVERAGE_M, 'improvement_tolerance_m': IMPROVEMENT_TOLERANCE_M,
                         'scenario_scope': 'one intervention against unchanged baseline; not additive',
                         'grid_origin': 'interior representative point after projection to EPSG:32639',
                         'inputs': audits, 'limitations': LIMITATIONS,
                         'population': {'total_known_population': grid['total_population'] if grid['known_count'] else None,
                                        'known_population_cells': grid['known_count'],
                                        'unknown_population_cells': len(grid['props']) - grid['known_count']}},
            'summary': summary, 'scenarios': scenarios}


def independent_metrics(intervention, grid):
    """Scalar all-cell oracle: no vectorized masks, baseline arrays or cached totals."""
    total, improved_pop, before_pop, after_pop, reductions, newly_pop = [], [], [], [], [], []
    affected = newly_count = unknown_affected = unknown_newly = 0
    field = BASELINES[intervention['type']]
    for cell, origin in zip(grid['props'], grid['origins'], strict=True):
        baseline = cell[field]
        after = min(baseline, origin.distance(intervention['geometry']))
        improved = baseline - after > IMPROVEMENT_TOLERANCE_M
        newly = baseline > COVERAGE_M and after <= COVERAGE_M
        p = cell['population']
        if p is None:
            unknown_affected += int(improved)
            unknown_newly += int(newly)
            continue
        total.append(p)
        if baseline <= COVERAGE_M:
            before_pop.append(p)
        if after <= COVERAGE_M:
            after_pop.append(p)
        if improved:
            affected += 1
            improved_pop.append(p)
            if p > 0:
                reductions.append(p * (baseline - after))
        if newly:
            newly_count += 1
            newly_pop.append(p)
    denominator, improved_population = math.fsum(total), math.fsum(improved_pop)
    before = 100 * math.fsum(before_pop) / denominator if denominator > 0 else None
    after = 100 * math.fsum(after_pop) / denominator if denominator > 0 else None
    return {'population_improved': improved_population if total else None,
            'coverage_before_pct': before, 'coverage_after_pct': after,
            'coverage_change_pp': after - before if denominator > 0 else None,
            'avg_access_improvement_m': math.fsum(reductions) / improved_population if improved_population > 0 else None,
            'affected_cells': affected, 'newly_covered_population': math.fsum(newly_pop) if total else None,
            'newly_covered_cells': newly_count, 'unknown_population_cells_affected': unknown_affected,
            'unknown_population_cells_newly_covered': unknown_newly}


def verify_document(saved, expected, grid, interventions):
    if type(saved) is not dict:
        raise ValueError('Saved scenarios must be a JSON object.')
    rows = saved.get('scenarios')
    if type(rows) is not list or len(rows) != len(interventions) or any(type(row) is not dict for row in rows):
        raise ValueError('Scenario count differs from available interventions.')
    by_id = {item['id']: item for item in interventions}
    ids = [row.get('intervention_id') for row in rows]
    if any(type(i) is not str for i in ids) or len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError('Scenario IDs must match each unique recommendation exactly once.')
    for row in rows:
        item = by_id[row['intervention_id']]
        if row.get('intervention_type') != item['type']:
            raise ValueError('Scenario type does not match recommendation.')
        independent = independent_metrics(item, grid)
        for field in METRICS:
            value, reference = row.get(field), independent[field]
            if field not in row:
                raise ValueError(f'Missing simulation field: {field}')
            if field.endswith('cells') or field.startswith('unknown_population_cells'):
                valid = type(value) is int and value == reference and value >= 0
            else:
                valid = value is None if reference is None else close(value, reference)
            if not valid:
                raise ValueError(f'{item["id"]}: independent {field} verification failed.')
        before, after = row['coverage_before_pct'], row['coverage_after_pct']
        if before is not None and not (0 <= before <= after <= 100):
            raise ValueError('Coverage percentages must be nondecreasing and in [0,100].')
        if row.get('reconciliation') != reconcile(independent, item):
            raise ValueError('Recommendation reconciliation metadata mismatch.')
    # Strict equality of serialization also catches bool/int substitutions and stale metadata.
    if serialize(saved) != serialize(expected):
        raise ValueError('Saved scenarios, provenance or summary differ from deterministic recomputation.')


def serialize(document):
    return json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'


def verify_saved(path, expected, grid, interventions):
    saved = json.loads(path.read_bytes(), parse_constant=reject_constant)
    verify_document(saved, expected, grid, interventions)


def save_output(document, grid, interventions, path=OUTPUT):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, prefix='.' + path.name + '.', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(serialize(document))
            handle.flush()
            os.fsync(handle.fileno())
        verify_saved(temporary, document, grid, interventions)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def report(label, value):
    print(label + ': ' + json.dumps(value, ensure_ascii=False, allow_nan=False), file=sys.stderr, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Independently verify saved scenarios without writing.')
    parser.add_argument('--intervention-id', help='Print one scenario as JSON; query mode never writes. With --verify-only, verify the full saved output first.')
    args = parser.parse_args(argv)
    try:
        if args.verify_only and not OUTPUT.is_file():
            raise ValueError(f'No saved scenarios to verify: {OUTPUT}; no files written.')
        grid, interventions, audits = load_inputs()
        selected = next((i for i in interventions if i['id'] == args.intervention_id), None)
        if args.intervention_id is not None and selected is None:
            raise ValueError(f'Unknown intervention ID: {args.intervention_id}; no files written.')
        report('INPUT SCHEMAS', audits)
        if args.intervention_id is not None and not args.verify_only:
            document = build_document(grid, [selected], audits)
            verify_document(document, document, grid, [selected])
        else:
            document = build_document(grid, interventions, audits)
            if args.verify_only:
                verify_saved(OUTPUT, document, grid, interventions)
                report('VERIFIED', {'scenarios': len(interventions), 'independent_scalar_recalculation': True, 'writes': 0})
            else:
                save_output(document, grid, interventions)
                report('SAVED AND INDEPENDENTLY VERIFIED', str(OUTPUT))
        if args.intervention_id is not None:
            print(serialize(next(s for s in document['scenarios'] if s['intervention_id'] == args.intervention_id)), end='')
        else:
            report('POPULATION DENOMINATOR', document['metadata']['population'])
            report('STANDALONE SCENARIO RANGES (NOT ADDITIVE)', document['summary'])
            for kind in BASELINES:
                rows = [s for s in document['scenarios'] if s['intervention_type'] == kind]
                examples = sorted(rows, key=lambda s: (-(s['newly_covered_population'] or 0), s['intervention_id']))[:1]
                report('EXAMPLE ' + kind, examples)
            differences = [{'intervention_id': s['intervention_id'], **s['reconciliation']}
                           for s in document['scenarios'] if s['reconciliation']['status'] != 'match']
            report('RECONCILIATION DIFFERENCES / UNAVAILABLE VALUES', differences)
            if not interventions:
                report('NO SCENARIOS', 'Both recommendation layers are empty; no interventions invented.')
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    sys.exit(main())
