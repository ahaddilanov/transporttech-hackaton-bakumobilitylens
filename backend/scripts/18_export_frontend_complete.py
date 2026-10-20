#!/usr/bin/env python3
"""Export existing validated datasets for static frontend integration.

Uses the existing baseline export fields and topology-preserving 5 m route display
simplification. Only data/exports/complete and data/exports/frontend_complete.zip
are published. Processed sources, baseline exports and public/data are read-only.
The scenario object (metadata/summary/scenarios) is preserved byte for byte.
Verification independently checks saved fields/geometry against source features,
recalculates scenario metrics with the scalar simulation verifier, checks summary
totals and route deviation, and compares every ZIP member with standalone output.
Staging precedes publication; failed replacements roll back the previous package.
--verify-only has no write or network path. See the ZIP README for integration.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import sys
from tempfile import mkdtemp
from time import perf_counter
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import numpy as np
from pyproj import CRS, Transformer
import shapely
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = load_module('complete_baseline', 'export_frontend_baseline.py')
simulation = load_module('complete_simulation', '17_simulate_accessibility.py')
INPUTS = {**baseline.INPUT_PATHS,
          'bus_recommendations': ROOT / 'data/processed/recommendations/bus_recommendations.geojson',
          'bike_recommendations': ROOT / 'data/processed/recommendations/bike_recommendations.geojson',
          'intervention_scenarios': ROOT / 'data/processed/scenarios/intervention_scenarios.json'}
EXPORT_ROOT = ROOT / 'data/exports'
COMPLETE = EXPORT_ROOT / 'complete'
ARCHIVE = EXPORT_ROOT / 'frontend_complete.zip'
ROUTE_TOLERANCE_M = 5.0
METHOD = 'baku-frontend-complete-v1.0'
REC_KINDS = {'bus_recommendations': 'bus_stop', 'bike_recommendations': 'bike_corridor'}
REQUIRED = {
    'bus_stop': ('id', 'priority', 'population_affected', 'current_access_m', 'new_access_m', 'access_improvement_m', 'reason'),
    'bike_corridor': ('id', 'priority', 'length_m', 'population_coverage_gain', 'start_name', 'end_name', 'reason'),
}
GEO_TYPES = {**baseline.GEOMETRY_TYPES, 'bus_recommendations': ('Point',),
             'bike_recommendations': ('LineString', 'MultiLineString')}
FILENAMES = tuple(f'{layer}.geojson' for layer in GEO_TYPES) + ('summary.json', 'intervention_scenarios.json')
WARNINGS = [
    'Hypothetical straight-line accessibility estimates, not predicted ridership or engineering-validated outcomes.',
    'Missing population remains null; available population is modeled and partial coverage is not extrapolated.',
    'OSM stops and AYNA/OSM cycling infrastructure may be incomplete; proposed infrastructure requires field/engineering assessment.',
    'BakuBus validations are route-level; mapped geometry does not verify stop-route membership or active service.',
    'Bicycle recommendations apply an extra existing-OSM exclusion; the AYNA-baseline simulation preserves documented reconciliation differences.',
    'population_improved includes all distance-improved residents and differs from newly_covered_population within 500m.',
    'Scenarios are independent and can overlap; never sum individual gains into a combined citywide population benefit.',
    'The current frontend does not load intervention_scenarios.json yet; export does not wire simulation UI or change frontend source.',
]


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Non-finite numeric JSON input.')
    return result


def strict_json(raw):
    return json.loads(raw, parse_float=finite_float, parse_constant=simulation.reject_constant)


def numeric(value, nullable=True):
    return (nullable and value is None) or (type(value) in (int, float) and math.isfinite(value) and value >= 0)


def geometry_array(document, kinds):
    if (type(document) is not dict or document.get('type') != 'FeatureCollection'
            or type(document.get('features')) is not list):
        raise ValueError('Expected a GeoJSON FeatureCollection.')
    if document.get('crs') is not None:
        name = document['crs'].get('properties', {}).get('name')
        if not name or not CRS.from_user_input(name).equals(CRS.from_epsg(4326), ignore_axis_order=True):
            raise ValueError('GeoJSON must be EPSG:4326 longitude/latitude.')
    geometries = []
    for feature in document['features']:
        if type(feature) is not dict or feature.get('type') != 'Feature' or type(feature.get('geometry')) is not dict:
            raise ValueError('Malformed GeoJSON feature/geometry.')
        geometry = shape(feature['geometry'])
        if (geometry.geom_type not in kinds or geometry.is_empty or not geometry.is_valid
                or shapely.has_z(geometry) or shapely.has_m(geometry)):
            raise ValueError('Invalid, empty or non-2D geometry/type.')
        geometries.append(geometry)
    array = np.array(geometries, dtype=object)
    coordinates = shapely.get_coordinates(array)
    # Broad Baku/Absheron context check detects swapped axes even when both
    # coordinates fit global WGS84 limits. This is not a municipal-boundary clip.
    if (not np.isfinite(coordinates).all() or (coordinates[:, 0] < 48).any()
            or (coordinates[:, 0] > 52).any() or (coordinates[:, 1] < 38).any()
            or (coordinates[:, 1] > 42).any()):
        raise ValueError('Coordinates must be finite Baku-region [longitude, latitude] in EPSG:4326.')
    return array


def validate_recommendations(document, kind):
    geometry_array(document, ('Point',) if kind == 'bus_stop' else ('LineString', 'MultiLineString'))
    ids = set()
    for feature in document['features']:
        p = feature.get('properties')
        if type(p) is not dict or any(field not in p for field in REQUIRED[kind]):
            raise ValueError('Missing Contract V1 recommendation properties.')
        if (type(p['id']) is not str or not p['id'] or feature.get('id') != p['id'] or p['id'] in ids
                or not numeric(p['priority'], False) or p['priority'] > 100
                or type(p['reason']) is not list or any(type(reason) is not str for reason in p['reason'])):
            raise ValueError('Invalid recommendation ID, priority or reason array.')
        ids.add(p['id'])
        fields = REQUIRED[kind][2:-1] if kind == 'bus_stop' else ('length_m', 'population_coverage_gain')
        if any(not numeric(p[field]) for field in fields):
            raise ValueError('Recommendation numeric fields must be finite nonnegative numbers or null.')
        if kind == 'bike_corridor' and any(p[field] is not None and type(p[field]) is not str for field in ('start_name', 'end_name')):
            raise ValueError('Bicycle start/end names must be strings or null.')
        if kind == 'bus_stop' and all(p[field] is not None for field in ('current_access_m', 'new_access_m', 'access_improvement_m')):
            if not simulation.close(p['current_access_m'] - p['new_access_m'], p['access_improvement_m']):
                raise ValueError('Bus recommendation calculated improvement is inconsistent.')


def compact_recommendations(source):
    result = copy.deepcopy(source)
    for feature in result['features']:
        # Ordered graph traces are useful for engineering audits, not static map
        # display. Every other observed property, including Contract V1, remains.
        feature['properties'].pop('route_edges', None)
    for key in ('metadata', 'methodology'):
        metadata = result.get(key, {})
        if 'inputs' in metadata:
            metadata['inputs'] = {name: {k: value for k, value in audit.items() if k in ('file', 'sha256')}
                                  for name, audit in metadata['inputs'].items()}
    return result


def validate_scenario_links(document, recommendations):
    if (type(document) is not dict or type(document.get('metadata')) is not dict
            or type(document.get('summary')) is not dict or type(document.get('scenarios')) is not list):
        raise ValueError('Scenario source must be an object containing metadata, summary and a scenarios array.')
    expected = {}
    for layer, kind in REC_KINDS.items():
        for feature in recommendations[layer]['features']:
            identifier = feature['properties']['id']
            if identifier in expected:
                raise ValueError('Duplicate recommendation IDs across intervention types.')
            expected[identifier] = kind
    actual = {}
    for scenario in document['scenarios']:
        if type(scenario) is not dict:
            raise ValueError('Malformed scenario.')
        identifier, kind = scenario.get('intervention_id'), scenario.get('intervention_type')
        if type(identifier) is not str or not identifier or identifier in actual:
            raise ValueError('Invalid or duplicate full intervention ID in scenarios.')
        actual[identifier] = kind
    if actual != expected:
        raise ValueError(f'Scenario/recommendation ID mismatch: missing={sorted(set(expected)-set(actual))}, '
                         f'extra={sorted(set(actual)-set(expected))}, or wrong intervention type.')


def load_context(paths=None):
    paths = INPUTS if paths is None else paths
    sources, raw, audits, frames, geometries = {}, {}, {}, {}, {}
    for layer, path in paths.items():
        raw[layer] = path.read_bytes()
        sources[layer] = strict_json(raw[layer])
        audits[layer] = {'file': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
                         'sha256': hashlib.sha256(raw[layer]).hexdigest()}
        if layer == 'intervention_scenarios':
            continue
        geometries[layer] = geometry_array(sources[layer], GEO_TYPES[layer])
        if layer in baseline.INPUT_PATHS:
            frames[layer] = baseline.validate_geometry(layer, path, sources[layer])
        else:
            validate_recommendations(sources[layer], REC_KINDS[layer])
        audits[layer].update(feature_count=len(sources[layer]['features']),
                             geometry_types=dict(Counter(g.geom_type for g in geometries[layer])),
                             fields=sorted({field for f in sources[layer]['features'] for field in f['properties']}))
        baseline.report('INSPECTED INPUT ' + layer, audits[layer])
    scenarios = sources['intervention_scenarios']
    validate_scenario_links(scenarios, sources)
    project = Transformer.from_crs(4326, 32639, always_xy=True).transform
    grid = simulation.make_grid([f['properties'] for f in sources['grid']['features']],
                               shapely.point_on_surface(shapely.transform(geometries['grid'], project, interleaved=False)))
    items, simulation_audits = [], {'grid': dict(audits['grid'])}
    for layer, kind in REC_KINDS.items():
        metadata = sources[layer].get('metadata', sources[layer].get('methodology', {}))
        recorded = metadata.get('inputs', {}).get('grid', {}).get('sha256')
        if recorded is not None and recorded != audits['grid']['sha256']:
            raise ValueError(f'{layer}: stale recommendation grid hash.')
        simulation_audits[kind] = {**audits[layer], 'recommendation_grid_hash_check': 'match' if recorded else 'unavailable'}
        metric = shapely.transform(geometries[layer], project, interleaved=False)
        for feature, geometry in zip(sources[layer]['features'], metric, strict=True):
            items.append({'id': feature['properties']['id'], 'type': kind,
                          'geometry': geometry, 'properties': feature['properties']})
    # Reconstruct only the expected verification result in memory. Never call the
    # simulation CLI or any writer; the existing processed scenario file is read-only.
    expected_scenarios = simulation.build_document(grid, items, simulation_audits)
    return {'sources': sources, 'raw': raw, 'audits': audits, 'frames': frames,
            'grid': grid, 'interventions': items, 'expected_scenarios': expected_scenarios}


def make_summary(context, generated_at):
    sources = context['sources']
    layers = {layer: sources[layer] for layer in GEO_TYPES}
    summary = baseline.make_summary(layers, generated_at, ROUTE_TOLERANCE_M)
    scenarios = sources['intervention_scenarios']
    summary.update(export_method_version=METHOD,
                   simulation_counts={**dict(sorted(Counter(s['intervention_type'] for s in scenarios['scenarios']).items())),
                                      'total': len(scenarios['scenarios'])},
                   simulation_model_version=scenarios['metadata'].get('model_version'),
                   simulation_reconciliation_status_counts=dict(sorted(Counter(s['reconciliation']['status'] for s in scenarios['scenarios']).items())),
                   simulation_scenario_scope=scenarios['metadata'].get('scenario_scope'),
                   limitations=WARNINGS,
                   inputs={name: {key: value for key, value in audit.items() if key in ('file', 'sha256')}
                           for name, audit in context['audits'].items()})
    return summary


def readme_text(summary):
    attribution = baseline.readme_text(summary).split('Sources: ', 1)[1].split('\nScores use', 1)[0]
    return f'''# TransportTech complete frontend data export

Generated: {summary['generated_at']}
Export method: {METHOD}; priority model: {summary['scoring_model_version']}.
Simulation model: {summary['simulation_model_version']}.

ZIP members: data/grid.geojson, data/bus_stops.geojson, data/bus_routes.geojson,
data/metro_stations.geojson, data/cycleways.geojson,
data/bus_recommendations.geojson, data/bike_recommendations.geojson,
data/summary.json and data/intervention_scenarios.json; this README is ZIP-only.
Layer counts: {json.dumps(summary['layer_counts'], sort_keys=True)}
Scenario counts: {json.dumps(summary['simulation_counts'], sort_keys=True)}
Reconciliation statuses: {json.dumps(summary['simulation_reconciliation_status_counts'], sort_keys=True)}
Known modeled population: {summary['population_estimate']}; unknown-population
cells: {summary['null_population_cells']}. JSON null means unavailable, never zero.

Integration (a later, explicit step; the exporter does not edit public/data):
1. Inspect the archive, then extract it into the React project's public/ directory
   when ready to replace its static data: unzip /path/to/frontend_complete.zip -d public/
   All data files are under data/; README.md extracts at public/README.md.
2. Use static mode (VITE_API_BASE_URL unset). Existing dataSources.js paths already
   match the seven GeoJSON files and summary. Check existing data before replacement.
3. Simulations need a later frontend loader. Fetch /data/intervention_scenarios.json;
   it is an OBJECT with metadata, summary and a scenarios ARRAY, not a top-level array.
   Join each scenarios[i].intervention_id to recommendation.properties.id using the
   entire string and the matching intervention_type (bus_stop or bike_corridor).
   Do not truncate/hash IDs, coerce null to zero or substitute population_improved
   for newly_covered_population. The current App.jsx does not load simulations yet.

Geometry: EPSG:4326 [longitude, latitude]; distances and lengths in meters.
Original grid, Point, cycleway and recommendation coordinates are copied exactly.
Only bus route display lines use the existing topology-preserving 5m simplification
in EPSG:32639. Source-to-display deviation, endpoints and line parts are verified.
Raw graph traces (route_edges) and repeated source-schema lists are omitted from
recommendations; required Contract V1 fields, reasons, risk flags, names, IDs,
source references and useful method/coverage metadata are retained.
The complete simulation JSON is copied byte for byte, preserving reconciliation
statuses, differences, unknown counts, model provenance and limitations.

Sources: {attribution}
Methods: backend/SCORING_METHODOLOGY.md, BUS_RECOMMENDATIONS_METHODOLOGY.md,
BIKE_RECOMMENDATIONS_METHODOLOGY.md and SIMULATION_METHODOLOGY.md.
Additional bike route geometry is based on © OpenStreetMap contributors,
https://www.openstreetmap.org/copyright (Open Database License).

Limitations:
''' + ''.join('- ' + warning + '\n' for warning in summary['limitations']) + '''
Distances are straight-line from grid interior representative points, not walking
or cycling-network access. Priorities measure need, not physical safety or approval.
Bicycle recommendations exclude residents near existing OSM cycling infrastructure;
the AYNA-only simulation does not apply that extra exclusion. Preserve its reported
policy differences; do not force the two population measures to match.
OSM-gate populations cannot be independently re-derived from these static files;
the source audit is documented in backend/SIMULATION_METHODOLOGY.md.
Metro station Points are derived from entrances and entries are not OD trips or
unique residents. Route payment validations are not stop-level demand. Passenger
records cover 2026-01-01 through 2026-08-31. AYNA/OSM operational status, completeness,
permission, physical access, crossings and engineering feasibility require review.
Individual scenario benefits overlap and are not additive citywide totals.
'''


def write_package(directory, archive_path, context, summary):
    directory.mkdir()
    for layer in GEO_TYPES:
        source = context['sources'][layer]
        if layer in REC_KINDS:
            document = compact_recommendations(source)
        else:
            geometry = baseline.simplify_routes(context['frames'][layer], ROUTE_TOLERANCE_M) if layer == 'bus_routes' else None
            document = baseline.make_export(layer, source, geometry)
        (directory / (layer + '.geojson')).write_bytes(baseline.encode_json(document))
    (directory / 'summary.json').write_bytes(baseline.encode_json(summary))
    (directory / 'intervention_scenarios.json').write_bytes(context['raw']['intervention_scenarios'])
    timestamp = datetime.fromisoformat(summary['generated_at'].replace('Z', '+00:00'))
    date = (timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second)
    with ZipFile(archive_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in FILENAMES + ('README.md',):
            member = name if name == 'README.md' else 'data/' + name
            content = readme_text(summary).encode('utf-8') if name == 'README.md' else (directory / name).read_bytes()
            info = ZipInfo(member, date_time=date)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=9)


def verify_package(directory, archive_path, context):
    """Validate serialized output against source features, not a writer snapshot."""
    if set(path.name for path in directory.iterdir()) != set(FILENAMES):
        raise ValueError('Complete directory has missing or extra files.')
    saved = {}
    route_maximum = 0.0
    project = Transformer.from_crs(4326, 32639, always_xy=True).transform
    for layer in GEO_TYPES:
        path = directory / (layer + '.geojson')
        saved[layer] = strict_json(path.read_bytes())
        geometries = geometry_array(saved[layer], GEO_TYPES[layer])
        if layer in REC_KINDS:
            validate_recommendations(saved[layer], REC_KINDS[layer])
        else:
            baseline.validate_properties(layer, saved[layer])
        source = context['sources'][layer]
        if len(saved[layer]['features']) != len(source['features']):
            raise ValueError(f'{layer}: exported feature count changed.')
        for original, feature in zip(source['features'], saved[layer]['features'], strict=True):
            fields = tuple(k for k in original['properties'] if k != 'route_edges') if layer in REC_KINDS else baseline.EXPORT_FIELDS[layer]
            expected = {k: original['properties'][k] for k in fields}
            if (feature['id'] != original['id'] or baseline.encode_json(feature['properties']) != baseline.encode_json(expected)):
                raise ValueError(f'{layer}: source ID, Contract V1 fields, optional metadata, numeric types or nulls changed.')
            if layer != 'bus_routes' and baseline.encode_json(feature['geometry']) != baseline.encode_json(original['geometry']):
                raise ValueError(f'{layer}: source geometry changed.')
        if layer == 'bus_routes':
            original = context['frames'][layer].to_crs(32639).geometry.to_numpy()
            display = shapely.transform(geometries, project, interleaved=False)
            deviation = shapely.hausdorff_distance(original, display)
            if (not np.isfinite(deviation).all() or (deviation > ROUTE_TOLERANCE_M + 1e-6).any()
                    or not np.array_equal(shapely.get_type_id(original), shapely.get_type_id(display))
                    or not np.array_equal(shapely.get_num_geometries(original), shapely.get_num_geometries(display))
                    or (shapely.get_num_coordinates(display) > shapely.get_num_coordinates(original)).any()):
                raise ValueError('Route display geometry violates the existing 5m accuracy/type/part-count constraint.')
            for a, b in zip(original, display, strict=True):
                parts_a = a.geoms if a.geom_type == 'MultiLineString' else [a]
                parts_b = b.geoms if b.geom_type == 'MultiLineString' else [b]
                for part_a, part_b in zip(parts_a, parts_b, strict=True):
                    if any(math.dist(part_a.coords[index], part_b.coords[index]) > 1e-6 for index in (0, -1)):
                        raise ValueError('Route display changed line-part endpoints.')
            route_maximum = float(deviation.max()) if len(deviation) else 0.0
        if layer in REC_KINDS:
            expected_top = compact_recommendations(source)
            if {k: v for k, v in saved[layer].items() if k != 'features'} != {k: v for k, v in expected_top.items() if k != 'features'}:
                raise ValueError(f'{layer}: recommendation methodology/limitations changed.')
        elif set(saved[layer]) != {'type', 'features'}:
            raise ValueError(f'{layer}: unexpected bulky export metadata.')

    scenario_raw = (directory / 'intervention_scenarios.json').read_bytes()
    scenarios = strict_json(scenario_raw)
    validate_scenario_links(scenarios, saved)
    if scenario_raw != context['raw']['intervention_scenarios']:
        raise ValueError('Simulation values, reconciliation statuses or limitations changed; preserve source bytes exactly.')
    simulation.verify_document(scenarios, context['expected_scenarios'], context['grid'], context['interventions'])

    summary = strict_json((directory / 'summary.json').read_bytes())
    if type(summary) is not dict or type(summary.get('generated_at')) is not str:
        raise ValueError('Summary must preserve Contract V1 generated_at.')
    # Independently derive the five Contract V1 fields from original grid records.
    props = [f['properties'] for f in context['sources']['grid']['features']]
    known = [p['population'] for p in props if p['population'] is not None]
    independent = {'grid_cells': len(props), 'population_estimate': math.fsum(known) if known else None,
                   'high_bus_priority_cells': sum(p['bus_priority'] is not None and p['bus_priority'] >= 60 for p in props),
                   'high_bike_priority_cells': sum(p['bike_priority'] is not None and p['bike_priority'] >= 60 for p in props)}
    for field, value in independent.items():
        if field not in summary or baseline.encode_json(summary[field]) != baseline.encode_json(value):
            raise ValueError(f'Summary {field} differs from independent source calculation.')
    if baseline.encode_json(summary) != baseline.encode_json(make_summary(context, summary['generated_at'])):
        raise ValueError('Summary counts, provenance, Contract V1 or limitations are inconsistent.')
    expected_members = {'data/' + name: (directory / name).read_bytes() for name in FILENAMES}
    expected_members['README.md'] = readme_text(summary).encode('utf-8')
    with ZipFile(archive_path) as archive:
        if (len(archive.namelist()) != len(expected_members) or set(archive.namelist()) != set(expected_members)
                or archive.testzip() is not None):
            raise ValueError('ZIP member count/names or CRC failed; duplicates, missing and extra entries are rejected.')
        for name, content in expected_members.items():
            if archive.read(name) != content:
                raise ValueError(f'ZIP payload differs from verified standalone output: {name}')
    result = {'layer_counts': summary['layer_counts'], 'simulation_counts': summary['simulation_counts'],
              'reconciliation_status_counts': summary['simulation_reconciliation_status_counts'],
              'max_route_display_deviation_m': route_maximum,
              'independent_scenario_calculations': len(scenarios['scenarios']),
              'sizes_bytes': {name: (directory / name).stat().st_size for name in FILENAMES},
              'zip_bytes': archive_path.stat().st_size}
    baseline.report('INDEPENDENT PACKAGE VERIFICATION PASSED', result)
    return result


class RecoveryRequired(RuntimeError):
    """Preserve staging backups if the operating system also prevents rollback."""


def publish(stage, complete=COMPLETE, archive=ARCHIVE):
    """Rename complete artifacts only; restore both originals on any failure."""
    previous, installed = [], []
    targets = [(stage / 'complete', complete), (stage / 'frontend_complete.zip', archive)]
    try:
        for _, target in targets:
            if target.exists() or target.is_symlink():
                backup = stage / ('previous-' + target.name)
                os.replace(target, backup)
                previous.append((backup, target))
        for source, target in targets:
            os.replace(source, target)
            installed.append(target)
    except BaseException:
        try:
            for target in reversed(installed):
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            for backup, target in reversed(previous):
                os.replace(backup, target)
        except BaseException as error:
            raise RecoveryRequired(f'Publication and rollback failed; preserve/recover previous artifacts in {stage}: {error}') from error
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Independently verify existing complete output and ZIP; no writes or network requests.')
    args = parser.parse_args(argv)
    started = perf_counter()
    stage, preserve_stage = None, False
    try:
        if args.verify_only and (not COMPLETE.is_dir() or not ARCHIVE.is_file()):
            raise ValueError('Complete export or ZIP is missing; no files written.')
        context = load_context()
        if args.verify_only:
            verify_package(COMPLETE, ARCHIVE, context)
        else:
            # A failed source verification cannot replace or create any public output.
            simulation.verify_document(context['sources']['intervention_scenarios'], context['expected_scenarios'],
                                       context['grid'], context['interventions'])
            EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
            if COMPLETE.is_symlink() or ARCHIVE.is_symlink():
                raise ValueError('Refusing to replace symlink export targets.')
            stage = Path(mkdtemp(dir=EXPORT_ROOT, prefix='.frontend-complete-'))
            generated_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
            summary = make_summary(context, generated_at)
            write_package(stage / 'complete', stage / 'frontend_complete.zip', context, summary)
            verify_package(stage / 'complete', stage / 'frontend_complete.zip', context)
            # Detect changes between initial source reads and publication.
            for layer, path in INPUTS.items():
                if hashlib.sha256(path.read_bytes()).hexdigest() != context['audits'][layer]['sha256']:
                    raise ValueError(f'{layer}: source changed during export; publication cancelled.')
            publish(stage, COMPLETE, ARCHIVE)
        baseline.report('WARNINGS / INTEGRATION LIMITATIONS', WARNINGS)
        baseline.report('COMPLETE EXPORT', {'directory': str(COMPLETE), 'archive': str(ARCHIVE),
                                          'verify_only': args.verify_only, 'seconds': round(perf_counter() - started, 2)})
        return 0
    except RecoveryRequired as error:
        preserve_stage = True
        parser.exit(1, f'ERROR: {error}\n')
    except Exception as error:
        parser.exit(1, f'ERROR: {error}\n')
    finally:
        if stage is not None and not preserve_stage:
            shutil.rmtree(stage)


if __name__ == '__main__':
    sys.exit(main())
