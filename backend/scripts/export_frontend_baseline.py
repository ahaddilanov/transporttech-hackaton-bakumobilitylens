"""Export a compact frontend baseline from validated processed datasets.

Uses the Contract V1 fields established in the processing scripts and preserves
existing names/types (including scoring_quality). Frontend-only whitelists remove
verbose lineage and intermediate scoring components. Grid geometry is copied
exactly. Route display geometry defaults to topology-preserving 5 m simplification
in EPSG:32639 (maximum allowed 10 m); --simplify-routes-m 0 preserves it exactly.
All source layers
must already be EPSG:4326 with longitude/latitude coordinates and valid geometry.

High-priority reporting uses score >=60 per baseline v1 methodology; null scores
are excluded, never zero-filled. Summary population sums available modeled cell
counts and discloses missing cells. Route validations remain route-level. No
recommendation files are generated. ZIP members data/*.geojson and data/summary.json
can be extracted directly into a frontend public directory; README.md is inside
ZIP only. --verify-only reuses the saved generated_at and never writes files.
"""

import argparse
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = PROJECT_ROOT / 'data/exports'
INPUT_PATHS = {
    'grid': PROJECT_ROOT / 'data/processed/grid/baku_grid_scored.geojson',
    'bus_stops': PROJECT_ROOT / 'data/processed/transport/bus_stops.geojson',
    'bus_routes': PROJECT_ROOT / 'data/processed/transport/bus_routes_with_demand.geojson',
    'metro_stations': PROJECT_ROOT / 'data/processed/transport/metro_stations.geojson',
    'cycleways': PROJECT_ROOT / 'data/processed/transport/cycleways.geojson',
}
EXPORT_FIELDS = {
    'grid': ('id', 'population', 'nearest_bus_stop_m', 'nearest_metro_m', 'nearest_cycleway_m',
             'bus_stops_500m', 'bus_routes_nearby', 'pois_nearby', 'bus_priority', 'bike_priority',
             'mobility_gap', 'scoring_quality', 'coverage_status', 'valid_pixel_fraction',
             'scoring_model_version', 'area_m2'),
    'bus_stops': ('id', 'name', 'source'),
    'bus_routes': ('id', 'name', 'route_ref', 'avg_daily_validations', 'source'),
    'metro_stations': ('id', 'name', 'avg_daily_entries', 'source'),
    'cycleways': ('id', 'name', 'length_m', 'source'),
}
GEOMETRY_TYPES = {
    'grid': ('Polygon', 'MultiPolygon'), 'bus_stops': ('Point',),
    'bus_routes': ('LineString', 'MultiLineString'), 'metro_stations': ('Point',),
    'cycleways': ('LineString', 'MultiLineString'),
}
SCORE_FIELDS = ('bus_priority', 'bike_priority', 'mobility_gap')
THRESHOLD = 60
QUALITY_VALUES = {'unknown_population', 'low_population_pixel_coverage',
                  'partial_population_pixel_coverage', 'full_population_pixel_coverage',
                  'population_coverage_unreported'}


def report(label, value):
    print(label + ': ' + json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def read_json(path):
    with path.open(encoding='utf-8') as source:
        return json.load(source)


def encode_json(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')


def validate_properties(layer, document):
    identifiers = []
    for feature in document['features']:
        if feature.get('type') != 'Feature' or not isinstance(feature.get('properties'), dict):
            raise RuntimeError(f'{layer}: malformed feature/properties.')
        p = feature['properties']
        if any(field not in p for field in EXPORT_FIELDS[layer]):
            raise RuntimeError(f'{layer}: missing required export fields at {p.get("id")}.')
        identifier = p['id']
        if type(identifier) is not str or not identifier or feature.get('id') != identifier:
            raise RuntimeError(f'{layer}: feature/property IDs must be consistent nonempty strings.')
        identifiers.append(identifier)
        strings = ('scoring_quality', 'coverage_status', 'scoring_model_version') if layer == 'grid' else ('name', 'source')
        if layer == 'bus_routes':
            strings += ('route_ref',)
        for field in strings:
            if (p[field] is not None and type(p[field]) is not str) or (field not in ('name', 'route_ref') and not p[field]):
                raise RuntimeError(f'{layer}: invalid string/null field {field} at {identifier}.')
        numbers = {
            'grid': ('population', 'nearest_bus_stop_m', 'nearest_metro_m', 'nearest_cycleway_m',
                     *SCORE_FIELDS, 'valid_pixel_fraction', 'area_m2'),
            'bus_stops': (), 'bus_routes': ('avg_daily_validations',),
            'metro_stations': ('avg_daily_entries',), 'cycleways': ('length_m',),
        }[layer]
        for field in numbers:
            value = p[field]
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise RuntimeError(f'{layer}: {field} must be finite nonnegative number or null at {identifier}.')
        if layer == 'grid':
            for field in ('bus_stops_500m', 'bus_routes_nearby', 'pois_nearby'):
                value = p[field]
                if value is not None and (type(value) is not int or value < 0):
                    raise RuntimeError(f'{layer}: {field} must be a nonnegative integer or null.')
            if (p['scoring_quality'] not in QUALITY_VALUES
                    or p['scoring_model_version'] != 'baku-priority-v1.0'
                    or any(p[field] is not None and p[field] > 100 for field in SCORE_FIELDS)
                    or (p['valid_pixel_fraction'] is not None and p['valid_pixel_fraction'] > 1)
                    or p['area_m2'] is None or p['area_m2'] <= 0):
                raise RuntimeError('Grid quality, model, score bounds or coverage/area failed validation.')
            if p['population'] is None and (any(p[field] is not None for field in SCORE_FIELDS) or p['scoring_quality'] != 'unknown_population'):
                raise RuntimeError('Unknown population must preserve null scores and unknown_population status.')
    if len(set(identifiers)) != len(identifiers):
        raise RuntimeError(f'{layer}: duplicate feature IDs.')


def validate_geometry(layer, path, document):
    if (not isinstance(document, dict) or document.get('type') != 'FeatureCollection'
            or not isinstance(document.get('features'), list) or not document['features']):
        raise RuntimeError(f'{layer}: empty or malformed FeatureCollection.')
    validate_properties(layer, document)
    frame = gpd.read_file(path)
    if (len(frame) != len(document['features']) or frame.crs is None or frame.crs.to_epsg() != 4326
            or frame.geometry.isna().any() or frame.is_empty.any() or not frame.is_valid.all()
            or not frame.geom_type.isin(GEOMETRY_TYPES[layer]).all()
            or frame['id'].tolist() != [f['id'] for f in document['features']]):
        raise RuntimeError(f'{layer}: feature count, IDs, valid geometry types or EPSG:4326 failed.')
    coordinates = shapely.get_coordinates(frame.geometry.array)
    if (not np.isfinite(coordinates).all() or (np.abs(coordinates[:, 0]) > 180).any()
            or (np.abs(coordinates[:, 1]) > 90).any() or shapely.has_z(frame.geometry.array).any()):
        raise RuntimeError(f'{layer}: expected finite 2D longitude/latitude coordinates.')
    return frame


def make_export(layer, original, route_geometry=None):
    return {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'id': feature['id'],
         'geometry': route_geometry[index] if route_geometry is not None else feature['geometry'],
         'properties': {field: feature['properties'][field] for field in EXPORT_FIELDS[layer]}}
        for index, feature in enumerate(original['features'])]}


def simplify_routes(frame, tolerance):
    if not math.isfinite(tolerance) or not 0 <= tolerance <= 10:
        raise RuntimeError('Route simplification tolerance must be finite and within 0–10 meters.')
    if tolerance == 0:
        return None
    metric = frame.to_crs('EPSG:32639')
    simplified = metric.geometry.simplify(tolerance, preserve_topology=True)
    if (not simplified.is_valid.all() or simplified.is_empty.any()
            or not simplified.geom_type.eq(metric.geom_type).all()
            or not np.array_equal(shapely.get_num_geometries(simplified.array), shapely.get_num_geometries(metric.geometry.array))):
        raise RuntimeError('Route display simplification changed validity, geometry type or line-part counts.')
    report('ROUTE DISPLAY SIMPLIFICATION', {'tolerance_m': tolerance, 'crs': 'EPSG:32639',
           'original_vertices': int(shapely.get_num_coordinates(metric.geometry.array).sum()),
           'export_vertices': int(shapely.get_num_coordinates(simplified.array).sum()),
           'preserve_topology': True, 'processed_source_unchanged': True})
    return [mapping(geometry) for geometry in gpd.GeoSeries(simplified, crs=metric.crs).to_crs(4326)]


def make_summary(exports, generated_at, route_tolerance=0):
    timestamp = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise RuntimeError('generated_at must be an ISO timestamp in UTC.')
    grid = [feature['properties'] for feature in exports['grid']['features']]
    available = [p['population'] for p in grid if p['population'] is not None]
    return {
        'generated_at': generated_at, 'grid_cells': len(grid),
        'population_estimate': math.fsum(available) if available else None,
        'high_bus_priority_cells': sum(p['bus_priority'] is not None and p['bus_priority'] >= THRESHOLD for p in grid),
        'high_bike_priority_cells': sum(p['bike_priority'] is not None and p['bike_priority'] >= THRESHOLD for p in grid),
        'high_priority_threshold': THRESHOLD, 'high_priority_rule': 'score >=60; null scores excluded',
        'null_population_cells': len(grid) - len(available), 'population_cells_with_estimates': len(available),
        'population_estimate_definition': 'sum of available WorldPop 2026 modeled cell counts; missing coverage not zero or extrapolated',
        'layer_counts': {layer: len(document['features']) for layer, document in exports.items()},
        'scoring_model_version': 'baku-priority-v1.0',
        'scoring_quality_counts': dict(Counter(p['scoring_quality'] for p in grid)),
        'distance_method': 'straight_line_distance_from_grid_representative_point',
        'distance_units': 'meters', 'output_crs': 'EPSG:4326', 'coordinate_order': '[longitude, latitude]',
        'route_display_simplification_m': route_tolerance,
    }


def readme_text(summary):
    counts = summary['layer_counts']
    return f'''# TransportTech frontend baseline v1

Generated: {summary['generated_at']}
Extract this ZIP into the frontend project's public directory. It creates:
  data/grid.geojson, data/bus_stops.geojson, data/bus_routes.geojson,
  data/metro_stations.geojson, data/cycleways.geojson, data/summary.json.
Fetch these as /data/<filename>. No bus/bike recommendation files are included.
All GeoJSON is EPSG:4326 with [longitude, latitude] coordinates. Distances and
cycleway lengths are meters. Grid geometry, Points and cycleways are unchanged.
Route display simplification uses {summary['route_display_simplification_m']} m in
EPSG:32639, preserving topology, feature IDs, geometry types and line-part counts.
Processed source geometry is never modified.

Counts: {counts['grid']} grid cells, {counts['bus_stops']} bus stops,
{counts['bus_routes']} route features, {counts['metro_stations']} metro stations,
{counts['cycleways']} cycleway features. Population estimate:
{summary['population_estimate']} from available modeled counts;
{summary['null_population_cells']} cells have unknown population. JSON null means
unavailable and must not be displayed or scored as zero or "N/A" in the data.

Sources: geoBoundaries AZE ADM2 Baku City (study polygon); WorldPop Azerbaijan
2026 R2025A v1 constrained population counts (embedded CC-BY-4.0); OpenStreetMap
mapped bus stops (© OpenStreetMap contributors, https://www.openstreetmap.org/copyright);
AYNA-attributed route/cycleway KMZ linework; OpenData.az BakuBus route-level
validations and Baku Metro station entry counts and entrance coordinates.
Source details: backend DATA_SOURCES.md. AYNA provenance, vintage, license and
completeness are not independently established. Other source usage terms and
attribution requirements remain as documented in that source log.

Scores use baku-priority-v1.0 from backend SCORING_METHODOLOGY.md:
bus_priority = demand-weighted mapped bus-access deficit; bike_priority =
demand-weighted cycleway-proximity deficit; mobility_gap = combined bus/bike/metro
deficit weighted by demand. Higher 0–100 scores mean greater need for further
investigation, not construction feasibility. High priority uses score >=60
(a reporting assumption): {summary['high_bus_priority_cells']} bus cells and
{summary['high_bike_priority_cells']} bike cells. Unknown population -> null scores.
Preserve scoring_quality, coverage_status and valid_pixel_fraction in the UI;
partial population sample coverage requires review. No census rescaling occurs.

Limitations: straight-line distances from each clipped grid's interior
representative point are not walking-network travel distances. Grid metro
distances use entrances; exported station Points are derived mean entrance
locations, not surveyed station centers. Metro avg_daily_entries is the mean
of recorded station-entry counts, not OD trips or unique people. Bus route
avg_daily_validations is route-level payment validation context, never demand
assigned to stops or grid cells; null indicates unmatched/unavailable data.
Passenger data covers 2026-01-01 through 2026-08-31, not a full year. Neither
mapped stops, POIs nor AYNA lanes are exhaustive or verified operational/safe/
connected. Route lines can extend outside the study polygon and are preserved.
No stop-to-route service relationship, bus frequency or recommendation is inferred.
'''


def verify_exports(directory, exports, frames, summary):
    for layer, expected in exports.items():
        path = directory / f'{layer}.geojson'
        saved = read_json(path)
        if encode_json(saved) != encode_json(expected):
            raise RuntimeError(f'{layer}: exported geometry, IDs, fields/types or null values changed.')
        if set(saved) != {'type', 'features'} or any(set(f['properties']) != set(EXPORT_FIELDS[layer]) for f in saved['features']):
            raise RuntimeError(f'{layer}: unexpected verbose frontend metadata.')
        frame = validate_geometry(layer, path, saved)
        tolerance = summary['route_display_simplification_m']
        if layer == 'bus_routes' and tolerance > 0:
            source_metric = frames[layer].to_crs('EPSG:32639').geometry.array
            display_metric = frame.to_crs('EPSG:32639').geometry.array
            deviations = shapely.hausdorff_distance(source_metric, display_metric)
            if (not np.isfinite(deviations).all() or deviations.max() > tolerance + 1e-6
                    or not frame.geom_type.eq(frames[layer].geom_type).all()
                    or not np.array_equal(shapely.get_num_geometries(source_metric), shapely.get_num_geometries(display_metric))):
                raise RuntimeError('Route display exceeds simplification tolerance or changes geometry types/parts.')
            report('ROUTE DISPLAY DEVIATION VALIDATED', {'maximum_m': float(deviations.max()), 'limit_m': tolerance})
        elif not shapely.equals_exact(frame.geometry.array, frames[layer].geometry.array, tolerance=0).all():
            raise RuntimeError(f'{layer}: export geometry differs from processed source.')
        print(f'Export reload PASSED: {layer}; {len(frame)} features, IDs, validated geometry, EPSG:4326 and property/null types', flush=True)
    if encode_json(read_json(directory / 'summary.json')) != encode_json(summary):
        raise RuntimeError('Summary timestamp, counts, modeled population or high-priority totals differ.')
    expected_members = {f'data/{layer}.geojson': (directory / f'{layer}.geojson').read_bytes() for layer in exports}
    expected_members['data/summary.json'] = (directory / 'summary.json').read_bytes()
    expected_members['README.md'] = readme_text(summary).encode('utf-8')
    with ZipFile(directory / 'frontend_baseline.zip') as archive:
        if len(archive.namelist()) != len(expected_members) or set(archive.namelist()) != set(expected_members) or archive.testzip() is not None:
            raise RuntimeError('ZIP member names/counts or CRC integrity failed.')
        for name, content in expected_members.items():
            if archive.read(name) != content:
                raise RuntimeError(f'ZIP payload differs from validated standalone file/README: {name}.')
    print('Summary and ZIP PASSED: inclusive >=60 threshold, source-derived counts, exact data/* payloads and README', flush=True)


def write_package(directory, exports, summary):
    for layer, document in exports.items():
        (directory / f'{layer}.geojson').write_bytes(encode_json(document))
    (directory / 'summary.json').write_bytes(encode_json(summary))
    generated = datetime.fromisoformat(summary['generated_at'].replace('Z', '+00:00'))
    zip_date = (generated.year, generated.month, generated.day, generated.hour, generated.minute, generated.second)
    with ZipFile(directory / 'frontend_baseline.zip', 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        payloads = [(f'data/{layer}.geojson', (directory / f'{layer}.geojson').read_bytes()) for layer in exports]
        payloads += [('data/summary.json', encode_json(summary)), ('README.md', readme_text(summary).encode('utf-8'))]
        for name, content in payloads:
            info = ZipInfo(name, date_time=zip_date)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=9)


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Rebuild expected frontend data and verify saved files/ZIP without writing or refreshing generated_at.')
    parser.add_argument('--simplify-routes-m', type=float, default=None,
                        help='Route display tolerance 0–10 m; default 5 m when exporting, saved tolerance when verifying. 0 preserves exact geometry.')
    args = parser.parse_args()
    saved_summary = read_json(EXPORT_DIR / 'summary.json') if args.verify_only else None
    route_tolerance = args.simplify_routes_m
    if route_tolerance is None:
        route_tolerance = saved_summary['route_display_simplification_m'] if saved_summary is not None else 5.0
    if not math.isfinite(route_tolerance) or not 0 <= route_tolerance <= 10:
        raise RuntimeError('Route simplification tolerance must be finite and within 0–10 meters.')
    exports, frames = {}, {}
    for layer, path in INPUT_PATHS.items():
        source = read_json(path)
        frames[layer] = validate_geometry(layer, path, source)
        report('INSPECTED INPUT ' + layer, {'features': len(source['features']), 'crs': str(frames[layer].crs),
               'geometry_types': frames[layer].geom_type.value_counts().to_dict(),
               'actual_properties': sorted({k for f in source['features'] for k in f['properties']}),
               'export_properties': EXPORT_FIELDS[layer]})
        route_geometry = simplify_routes(frames[layer], route_tolerance) if layer == 'bus_routes' else None
        exports[layer] = make_export(layer, source, route_geometry)
    if args.verify_only:
        generated_at = saved_summary['generated_at']
    else:
        generated_at = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    summary = make_summary(exports, generated_at, route_tolerance)
    if args.verify_only:
        verify_exports(EXPORT_DIR, exports, frames, summary)
    else:
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        # Stage and fully validate the package before replacing any export file.
        with TemporaryDirectory(dir=EXPORT_DIR, prefix='.frontend-baseline-') as temporary:
            stage = Path(temporary)
            write_package(stage, exports, summary)
            verify_exports(stage, exports, frames, summary)
            for filename in [*(f'{layer}.geojson' for layer in exports), 'summary.json', 'frontend_baseline.zip']:
                os.replace(stage / filename, EXPORT_DIR / filename)
    for layer, path in INPUT_PATHS.items():
        original_size, export_size = path.stat().st_size, (EXPORT_DIR / f'{layer}.geojson').stat().st_size
        report('FILE SIZE ' + layer, {'original_bytes': original_size, 'export_bytes': export_size,
               'reduction_percent': round(100 * (1 - export_size / original_size), 2)})
    report('SUMMARY', summary)
    print(f"ZIP size: {(EXPORT_DIR / 'frontend_baseline.zip').stat().st_size:,} bytes", flush=True)
    print(f'Total runtime: {perf_counter() - started:.2f} seconds', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
