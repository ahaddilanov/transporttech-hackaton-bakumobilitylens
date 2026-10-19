"""Build a clipped 250 m Baku grid with observed WorldPop population counts.

Grid: EPSG:32639 squares on a fixed (0,0) lattice; row increases northward,
column eastward. IDs use absolute row/column and survive boundary changes.
Cells are intersected with the actual study MultiPolygon, including its holes.
Areas are measured in EPSG:32639; output polygons are EPSG:4326 lon/lat.

Aggregation: read the native raster window once, mask the ORIGINAL boundary
with all_touched=False, transform selected pixel centers to EPSG:32639, and
sum whole population-count pixels by grid index using numpy.bincount. No
raster resampling, density conversion, fractional weighting or census scaling.
Boundary pixels contribute their full count when their center is inside; pixels
crossing cell boundaries go wholly to one cell. Small clipped cells may contain
no centers. Native and projected boundary inclusion are checked for agreement.

NoData=-99999/masked pixels never contribute. Population is null when a cell
has no valid samples, and zero only when valid samples sum to zero. Partial
coverage yields the observed sum, not an estimate for the missing portion.
Valid-pixel fractions describe sample coverage, not area/population coverage.
All uncalculated Contract V1 metrics stay null. The population remains modeled
and provisional, subject to the documented constrained-mask limitations.
"""

import argparse
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
import rasterio
import shapely
from pyproj import Transformer
from rasterio.features import geometry_mask, geometry_window
from shapely.geometry import mapping, box


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = PROJECT_ROOT / 'data/processed/boundaries/baku_boundary.geojson'
RASTER_PATH = PROJECT_ROOT / 'data/raw/population/aze_pop_2026_CN_100m_R2025A_v1.tif'
OUTPUT_PATH = PROJECT_ROOT / 'data/processed/grid/baku_grid_population.geojson'
CELL_SIZE = 250
METRIC_CRS = 'EPSG:32639'
PENDING_METRICS = ('nearest_bus_stop_m', 'nearest_metro_m', 'nearest_cycleway_m',
                   'bus_stops_500m', 'bus_routes_nearby', 'pois_nearby',
                   'bus_priority', 'bike_priority', 'mobility_gap')
AUDITED_TOTAL = 2898185.146993
AUDITED_INSIDE_PIXELS = 322482
AUDITED_VALID_PIXELS = 148659
AREA_TOLERANCE_M2 = 0.1
CELL_AREA_TOLERANCE_M2 = 0.0001


def report(label, values):
    print(label + ': ' + json.dumps(values, ensure_ascii=False, allow_nan=False), flush=True)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_boundary():
    frame = gpd.read_file(BOUNDARY_PATH)
    if (len(frame) != 1 or frame.crs is None or frame.geometry.isna().any()
            or frame.is_empty.any() or not frame.is_valid.all()
            or not frame.geom_type.isin(['Polygon', 'MultiPolygon']).all()):
        raise RuntimeError('Expected one valid nonempty polygonal study boundary with CRS.')
    native = frame.geometry.iloc[0]
    metric = frame.to_crs(METRIC_CRS).geometry.iloc[0]
    metadata = {'file': str(BOUNDARY_PATH.relative_to(PROJECT_ROOT)), 'sha256': sha256(BOUNDARY_PATH),
                'crs': str(frame.crs), 'geometry_type': native.geom_type,
                'properties': frame.drop(columns=frame.geometry.name).iloc[0].to_dict(),
                'area_m2': float(metric.area), 'grid_crs': METRIC_CRS,
                'bounds_native_crs': list(native.bounds)}
    report('BOUNDARY', metadata)
    return native, frame.crs, metric, metadata


def polygonal_part(geometry):
    # An intersection can include isolated boundary lines alongside polygons.
    # Preserve all polygonal pieces; report lower-dimensional touches separately.
    if geometry.geom_type in ('Polygon', 'MultiPolygon'):
        return geometry
    polygons = []
    if geometry.geom_type == 'GeometryCollection':
        for part in geometry.geoms:
            candidate = polygonal_part(part)
            if candidate is not None and not candidate.is_empty:
                polygons.append(candidate)
    return shapely.union_all(polygons) if polygons else None


def create_grid(boundary):
    xmin, ymin, xmax, ymax = boundary.bounds
    row_values = np.arange(math.floor(ymin / CELL_SIZE), math.ceil(ymax / CELL_SIZE), dtype=np.int64)
    col_values = np.arange(math.floor(xmin / CELL_SIZE), math.ceil(xmax / CELL_SIZE), dtype=np.int64)
    cols, rows = np.meshgrid(col_values, row_values)
    rows, cols = rows.ravel(), cols.ravel()
    squares = shapely.box(cols * CELL_SIZE, rows * CELL_SIZE,
                         (cols + 1) * CELL_SIZE, (rows + 1) * CELL_SIZE)
    intersects = shapely.intersects(squares, boundary)
    rows, cols, squares = rows[intersects], cols[intersects], squares[intersects]
    clipped = shapely.intersection(squares, boundary)
    mixed = ~np.isin(shapely.get_type_id(clipped), [3, 6])
    for index in np.flatnonzero(mixed):
        clipped[index] = polygonal_part(clipped[index])
    keep = ~shapely.is_missing(clipped) & ~shapely.is_empty(clipped) & (shapely.area(clipped) > 0)
    report('GRID CLIPPING', {'intersecting_candidates': len(clipped),
           'lower_dimensional_or_empty_touches_excluded': int((~keep).sum()),
           'mixed_intersections_polygon_parts_preserved': int((mixed & keep).sum()),
           'retained_polygonal_cells': int(keep.sum()), 'cell_size_m': CELL_SIZE,
           'lattice_origin_xy_m': [0, 0], 'row_direction': 'north', 'column_direction': 'east'})
    return clipped[keep], rows[keep], cols[keep]


def validate_metric_grid(cells, rows, cols, boundary):
    if (not len(cells) or not shapely.is_valid(cells).all() or shapely.is_empty(cells).any()
            or not np.isin(shapely.get_type_id(cells), [3, 6]).all()):
        raise RuntimeError('Grid contains invalid, empty or non-polygonal geometries.')
    if len(set(zip(rows.tolist(), cols.tolist()))) != len(cells):
        raise RuntimeError('Duplicate grid row/column IDs.')
    areas = shapely.area(cells)
    if (areas <= 0).any() or (areas > CELL_SIZE ** 2 + CELL_AREA_TOLERANCE_M2).any():
        raise RuntimeError('Grid area outside (0, 62500] m² tolerance.')
    outside = shapely.area(shapely.difference(cells, boundary))
    if outside.max() > CELL_AREA_TOLERANCE_M2 or outside.sum() > AREA_TOLERANCE_M2:
        raise RuntimeError('Cells extend outside study boundary beyond numeric tolerance.')
    # Spatial index limits comparisons to neighbours; shared edges are allowed.
    pairs = shapely.STRtree(cells).query(cells, predicate='intersects')
    left, right = pairs[:, pairs[0] < pairs[1]]
    overlap = shapely.area(shapely.intersection(cells[left], cells[right]))
    if len(overlap) and (overlap.max() > CELL_AREA_TOLERANCE_M2 or overlap.sum() > AREA_TOLERANCE_M2):
        raise RuntimeError('Positive-area overlap between grid cells.')
    union = shapely.union_all(cells)
    difference = float(shapely.symmetric_difference(union, boundary).area)
    if difference > AREA_TOLERANCE_M2 or not math.isclose(float(areas.sum()), boundary.area, rel_tol=0, abs_tol=AREA_TOLERANCE_M2):
        raise RuntimeError('Clipped grid does not reconcile to the actual boundary area.')
    checks = {'cell_count': len(cells), 'covered_area_m2': float(areas.sum()),
              'boundary_area_m2': float(boundary.area), 'symmetric_difference_area_m2': difference,
              'outside_area_m2': float(outside.sum()), 'pair_overlap_area_m2': float(overlap.sum()),
              'total_area_tolerance_m2': AREA_TOLERANCE_M2,
              'individual_area_tolerance_m2': CELL_AREA_TOLERANCE_M2}
    report('GEOMETRY VALIDATION PASSED', checks)
    return checks


def aggregate_population(path, native_boundary, boundary_crs, metric_boundary, cells, rows, cols):
    with rasterio.open(path) as dataset:
        if (dataset.count != 1 or dataset.crs is None or dataset.nodata != -99999
                or dataset.scales != (1.0,) or dataset.offsets != (0.0,)
                or dataset.transform.b != 0 or dataset.transform.d != 0
                or dataset.transform.a <= 0 or dataset.transform.e >= 0):
            raise RuntimeError('Raster schema changed: expected north-up, single-band counts with NoData=-99999, scale=1, offset=0.')
        raster_boundary = gpd.GeoSeries([native_boundary], crs=boundary_crs).to_crs(dataset.crs).iloc[0]
        window = geometry_window(dataset, [mapping(raster_boundary)])
        pixels = dataset.read(1, window=window, masked=True)
        transform = dataset.window_transform(window)
        inside = geometry_mask([mapping(raster_boundary)], out_shape=pixels.shape,
                               transform=transform, all_touched=False, invert=True)
        rr, cc = np.nonzero(inside)
        values = pixels.data[rr, cc].astype('float64')
        masked = np.ma.getmaskarray(pixels)[rr, cc] | (values == -99999)
        valid = ~masked
        if not np.isfinite(values[valid]).all() or (values[valid] < 0).any():
            raise RuntimeError('Negative or nonfinite unmasked population values inside Baku.')
        longitude = transform.c + (cc + 0.5) * transform.a
        latitude = transform.f + (rr + 0.5) * transform.e
        x, y = Transformer.from_crs(dataset.crs, METRIC_CRS, always_xy=True).transform(longitude, latitude)
        if not np.isfinite(x).all() or not np.isfinite(y).all():
            raise RuntimeError('Pixel-center transformation produced nonfinite coordinates.')
        covered = shapely.covers(metric_boundary, shapely.points(x, y))
        if not covered.all():
            report('BOUNDARY PROJECTION DISAGREEMENT', {'pixel_centers': int((~covered).sum()),
                   'valid_centers': int((~covered & valid).sum())})
            raise RuntimeError('Native/projected boundary-center inclusion differs; no pixels silently discarded.')
        pixel_rows = np.floor(y / CELL_SIZE).astype(np.int64)
        pixel_cols = np.floor(x / CELL_SIZE).astype(np.int64)
        min_row, min_col = int(rows.min()), int(cols.min())
        height, width = int(rows.max() - min_row + 1), int(cols.max() - min_col + 1)
        lookup = np.full((height, width), -1, dtype=np.int64)
        lookup[rows - min_row, cols - min_col] = np.arange(len(cells))
        pr, pc = pixel_rows - min_row, pixel_cols - min_col
        if ((pr < 0) | (pr >= height) | (pc < 0) | (pc >= width)).any():
            raise RuntimeError('In-boundary pixel center falls outside grid indices.')
        indices = lookup[pr, pc]
        if (indices < 0).any():
            raise RuntimeError('In-boundary pixel center has no retained cell.')
        totals = np.bincount(indices, minlength=len(cells))
        valid_counts = np.bincount(indices[valid], minlength=len(cells))
        populations = np.bincount(indices[valid], weights=values[valid], minlength=len(cells))
        # This direct masked sum is independent of grid assignment/bincount.
        independent_sum = float(values[valid].sum(dtype='float64'))
        assigned_sum = float(math.fsum(populations.tolist()))
        if (totals.sum() != inside.sum() or valid_counts.sum() != valid.sum()
                or not math.isclose(assigned_sum, independent_sum, rel_tol=0, abs_tol=1e-6)):
            raise RuntimeError('Population/pixel count conservation failed.')
        audit = {'file': str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else path.name,
                 'sha256': sha256(path), 'crs': str(dataset.crs), 'dtype': dataset.dtypes[0],
                 'width': dataset.width, 'height': dataset.height, 'resolution_xy': list(dataset.res),
                 'nodata': dataset.nodata, 'scale': dataset.scales[0], 'offset': dataset.offsets[0],
                 'tags': dataset.tags(), 'value_semantics': 'modeled population count per native pixel, not density',
                 'raster_footprint_covers_boundary': bool(box(*dataset.bounds).covers(raster_boundary)),
                 'window': {'col_off': int(window.col_off), 'row_off': int(window.row_off),
                            'width': int(window.width), 'height': int(window.height)},
                 'selected_inside_pixel_centers': int(inside.sum()), 'valid_inside_pixel_centers': int(valid.sum()),
                 'nodata_inside_pixel_centers': int(masked.sum()),
                 'valid_inside_pixel_fraction': float(valid.sum() / len(values)) if len(values) else None,
                 'observed_zero_pixel_count': int((values[valid] == 0).sum()),
                 'independent_inside_population_sum': independent_sum, 'assigned_population_sum': assigned_sum,
                 'assignment_minus_independent_sum': assigned_sum - independent_sum,
                 'native_projected_boundary_disagreement_pixel_count': 0}
        report('RASTER/AGGREGATION', audit)
    return populations, totals, valid_counts, audit


def cell_properties(row, col, area, population, total_pixels, valid_pixels):
    total_pixels, valid_pixels = int(total_pixels), int(valid_pixels)
    status = ('no_pixel_centers' if total_pixels == 0 else 'no_valid_data' if valid_pixels == 0
              else 'partial_valid_data' if valid_pixels < total_pixels else 'all_selected_pixels_valid')
    return {'id': f'baku:250m:r{int(row)}:c{int(col)}', 'grid_row': int(row), 'grid_column': int(col),
            'population': float(population) if valid_pixels else None, 'area_m2': float(area),
            'source': 'WorldPop', 'population_year': 2026,
            'selected_pixel_count': total_pixels, 'valid_pixel_count': valid_pixels,
            'nodata_pixel_count': total_pixels - valid_pixels,
            'valid_pixel_fraction': valid_pixels / total_pixels if total_pixels else None,
            'coverage_status': status, **dict.fromkeys(PENDING_METRICS)}


def build_document():
    native, crs, boundary, boundary_metadata = load_boundary()
    cells, rows, cols = create_grid(boundary)
    geometry_checks = validate_metric_grid(cells, rows, cols, boundary)
    populations, totals, valid, raster_metadata = aggregate_population(
        RASTER_PATH, native, crs, boundary, cells, rows, cols)
    reference = {'source': 'DATA_SOURCES.md independently audited native pixel-center sum inside Baku',
                 'audited_population_sum': AUDITED_TOTAL, 'audited_inside_pixels': AUDITED_INSIDE_PIXELS,
                 'audited_valid_pixels': AUDITED_VALID_PIXELS,
                 'current_minus_audited_population': raster_metadata['independent_inside_population_sum'] - AUDITED_TOTAL,
                 'matches_audited_total_and_counts': bool(
                     math.isclose(raster_metadata['independent_inside_population_sum'], AUDITED_TOTAL, rel_tol=0, abs_tol=1e-6)
                     and int(totals.sum()) == AUDITED_INSIDE_PIXELS and int(valid.sum()) == AUDITED_VALID_PIXELS)}
    report('INDEPENDENT DOCUMENTED AUDIT COMPARISON', reference)
    if not reference['matches_audited_total_and_counts']:
        raise RuntimeError('Inputs no longer reproduce the documented Baku audit; inspect changed sources before publishing grid.')
    geographic = gpd.GeoSeries(cells, crs=METRIC_CRS).to_crs(4326)
    features = []
    for i, geometry in enumerate(geographic):
        properties = cell_properties(rows[i], cols[i], cells[i].area, populations[i], totals[i], valid[i])
        features.append({'type': 'Feature', 'id': properties['id'],
                         'properties': properties, 'geometry': mapping(geometry)})
    summary = {'cell_count': len(cells), 'valid_population_cells': int((valid > 0).sum()),
               'zero_population_cells': int(((valid > 0) & (populations == 0)).sum()),
               'null_population_cells': int((valid == 0).sum()),
               'no_pixel_center_cells': int((totals == 0).sum()),
               'partial_valid_data_cells': int(((valid > 0) & (valid < totals)).sum()),
               'total_estimated_population': raster_metadata['assigned_population_sum'],
               'covered_area_m2': geometry_checks['covered_area_m2'],
               'covered_area_km2': geometry_checks['covered_area_m2'] / 1e6,
               'area_of_cells_with_valid_samples_m2': float(shapely.area(cells)[valid > 0].sum())}
    report('GRID SUMMARY', summary)
    metadata = {'boundary': boundary_metadata, 'raster': raster_metadata, 'cell_size_m': CELL_SIZE,
                'lattice_origin_xy_m': [0, 0], 'geometry_checks': geometry_checks,
                'aggregation_method': 'native all_touched=False study-boundary mask; projected pixel centers; one full count per center-assigned cell; numpy.bincount',
                'boundary_effects': 'whole pixels at selected centers; no fractional splitting; tiny clipped cells may have no centers',
                'coverage_semantics': 'valid_pixel_fraction is selected-center sample coverage, not area or population coverage; partial sums are not extrapolated',
                'null_semantics': 'no valid selected pixels -> null; valid selected pixels summing to zero -> zero',
                'population_limitations': 'WorldPop constrained modeled counts; missing areas not imputed; no census rescaling',
                'documented_audit_comparison': reference, 'summary': summary}
    # Convert tuples to JSON lists for exact read-back comparisons.
    document = json.loads(json.dumps({'type': 'FeatureCollection', 'features': features,
                                     'metadata': metadata}, ensure_ascii=False, allow_nan=False))
    validate_properties(document)
    return document, boundary


def validate_properties(document):
    identifiers, populations, total_pixels, valid_pixels = [], [], 0, 0
    for feature in document['features']:
        p = feature['properties']; identifier = p['id']; value = p['population']
        if (not isinstance(identifier, str) or not identifier or feature['id'] != identifier
                or identifier != f"baku:250m:r{p['grid_row']}:c{p['grid_column']}"):
            raise RuntimeError('Grid IDs are inconsistent or non-string.')
        identifiers.append(identifier)
        expected = cell_properties(p['grid_row'], p['grid_column'], p['area_m2'],
                                   value or 0, p['selected_pixel_count'], p['valid_pixel_count'])
        if (p != expected or (value is None) != (p['valid_pixel_count'] == 0)
                or not 0 <= p['valid_pixel_count'] <= p['selected_pixel_count']
                or type(p['valid_pixel_count']) is not int or type(p['selected_pixel_count']) is not int
                or not math.isfinite(p['area_m2']) or p['area_m2'] <= 0
                or (value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0))):
            raise RuntimeError(f'Population/null/coverage/contract validation failed: {identifier}')
        if value is not None:
            populations.append(value)
        total_pixels += p['selected_pixel_count']; valid_pixels += p['valid_pixel_count']
    raster = document['metadata']['raster']
    if (len(set(identifiers)) != len(identifiers)
            or total_pixels != raster['selected_inside_pixel_centers']
            or valid_pixels != raster['valid_inside_pixel_centers']
            or not math.isclose(math.fsum(populations), raster['independent_inside_population_sum'], rel_tol=0, abs_tol=1e-6)):
        raise RuntimeError('Saved property count/ID/population conservation failed.')


def verify_saved(path, expected, boundary):
    with path.open(encoding='utf-8') as source:
        saved = json.load(source)
    if saved != expected:
        raise RuntimeError('Saved JSON differs from source-derived IDs, geometries, properties or metadata.')
    validate_properties(saved)
    frame = gpd.read_file(path)
    if (len(frame) != len(expected['features']) or frame.crs is None or frame.crs.to_epsg() != 4326
            or not frame.geom_type.isin(['Polygon', 'MultiPolygon']).all()
            or not frame.is_valid.all() or frame.is_empty.any()
            or frame['id'].tolist() != [f['id'] for f in expected['features']]):
        raise RuntimeError('Reload count, ID, CRS or polygon validity check failed.')
    original = shapely.from_geojson(json.dumps(expected))
    if not shapely.equals_exact(frame.geometry.array, shapely.get_parts(original), tolerance=0).all():
        raise RuntimeError('Reload geometry coordinates changed.')
    xy = shapely.get_coordinates(frame.geometry.array)
    if (not np.isfinite(xy).all() or (np.abs(xy[:, 0]) > 180).any() or (np.abs(xy[:, 1]) > 90).any()):
        raise RuntimeError('Invalid longitude/latitude output coordinates.')
    projected = frame.to_crs(METRIC_CRS)
    validate_metric_grid(projected.geometry.array, frame['grid_row'].to_numpy(), frame['grid_column'].to_numpy(), boundary)
    if not np.allclose(projected.area.to_numpy(), frame['area_m2'].to_numpy(), rtol=0, atol=CELL_AREA_TOLERANCE_M2):
        raise RuntimeError('Reload EPSG:32639 cell areas changed.')
    print('Reload verification PASSED: IDs, exact geometries, EPSG:4326, properties, nulls, containment, overlap and conservation', flush=True)


def save_output(document, boundary):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=OUTPUT_PATH.parent,
                                prefix='.population-grid-', suffix='.geojson', delete=False) as output:
            temporary = Path(output.name)
            json.dump(document, output, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            output.write('\n'); output.flush(); os.fsync(output.fileno())
        verify_saved(temporary, document, boundary)
        os.replace(temporary, OUTPUT_PATH)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print(f'Saved intermediate population grid: {OUTPUT_PATH}', flush=True)


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Recompute from unchanged inputs and verify existing output without writing.')
    args = parser.parse_args()
    document, boundary = build_document()
    if args.verify_only:
        verify_saved(OUTPUT_PATH, document, boundary)
    else:
        save_output(document, boundary)
    print(f'Total runtime: {perf_counter() - started:.2f} seconds', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
