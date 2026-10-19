"""Select mapped essential destinations and count records near Baku grid cells.

Exact inspected TYPE selection: SCHOOL, HOSPITAL, KINDERGARTEN, PHARMACY,
CUSTOMIZABLE_POINT_5. The latter contains named universities, academies,
colleges and related institutes; it remains its original mixed source category,
not a fabricated UNIVERSITY class. Hospitals include clinics; pharmacies are
related healthcare destinations. Ambiguous names are flagged, not recategorized.

Selection uses the actual Baku polygon (covers includes its boundary), never
CITY. Original properties, names, TYPE, OBJECTID, status and coordinates remain.
Unique OBJECTIDs determine string IDs, then unique source feature IDs; otherwise
source-index IDs retain duplicate-ID records explicitly. Co-located records are
retained and counted separately; counts are mapped records, not unique facilities.

Grid origins are representative_point() after projection to EPSG:32639, matching
Step 14A. STRtree dwithin counts records at planar distance <=500 m. Original
EPSG:4326 grid features/properties remain unchanged except pois_nearby and the
new optional pois_500m_by_type dictionary. No walking-distance, completeness,
operational-status or priority claims are made. Blank/Checking source status
values are preserved; neither establishes current operation.
"""

import argparse
import copy
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import Point


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = PROJECT_ROOT / 'data/raw/opendata/azrbaycanda_obyektlr_v_mkanlar.geojson'
BOUNDARY_PATH = PROJECT_ROOT / 'data/processed/boundaries/baku_boundary.geojson'
GRID_PATH = PROJECT_ROOT / 'data/processed/grid/baku_grid_accessibility.geojson'
POIS_PATH = PROJECT_ROOT / 'data/processed/pois/essential_services.geojson'
OUTPUT_GRID_PATH = PROJECT_ROOT / 'data/processed/grid/baku_grid_pois.geojson'
SELECTED_CATEGORIES = ('SCHOOL', 'HOSPITAL', 'KINDERGARTEN', 'PHARMACY', 'CUSTOMIZABLE_POINT_5')
CATEGORY_COUNT_FIELD = 'pois_500m_by_type'
PENDING_FIELDS = ('bus_routes_nearby', 'bus_priority', 'bike_priority', 'mobility_gap')
METRIC_CRS = 'EPSG:32639'
RADIUS_METERS = 500.0
# Exact ambiguous records found during name inspection, retained for review.
QUESTIONABLE_NAMES = {
    'Zology Inistitute', 'Military chair', 'Scientific research architecture&ginecology inst',
    'Manuscripts Institute', 'State Head Institute of Project', 'Veterinary Clinic',
}
SELECTION_REASONS = {
    'SCHOOL': 'School, lyceum and some college education records in the actual source class.',
    'HOSPITAL': 'Healthcare records including hospitals, clinics and medical centers; source classification retained.',
    'KINDERGARTEN': 'Early-childhood education destinations.',
    'PHARMACY': 'Closely related healthcare destinations for medicines; includes source classification inconsistencies.',
    'CUSTOMIZABLE_POINT_5': 'Inspected university, academy, college and related institute names; mixed class retained, ambiguous records flagged.',
}


def report(label, value):
    print(label + ': ' + json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def read_document(path):
    raw = path.read_bytes()
    document = json.loads(raw.decode('utf-8-sig'))
    if (not isinstance(document, dict) or document.get('type') != 'FeatureCollection'
            or not isinstance(document.get('features'), list) or not document['features']):
        raise RuntimeError(f'{path.name}: missing/empty FeatureCollection; no output written.')
    return document, {'file': str(path.relative_to(PROJECT_ROOT)), 'sha256': hashlib.sha256(raw).hexdigest(),
                      'source_feature_count': len(document['features']), 'source_crs_member': document.get('crs')}


def validate_frame(path, document, geometry_types):
    frame = gpd.read_file(path)
    if (len(frame) != len(document['features']) or frame.crs is None or frame.crs.to_epsg() != 4326
            or frame.geometry.isna().any() or frame.is_empty.any() or not frame.is_valid.all()
            or not frame.geom_type.isin(geometry_types).all()):
        raise RuntimeError(f'{path.name}: count, EPSG:4326 or geometry validation failed.')
    xy = shapely.get_coordinates(frame.geometry.array)
    if (not np.isfinite(xy).all() or (np.abs(xy[:, 0]) > 180).any() or (np.abs(xy[:, 1]) > 90).any()):
        raise RuntimeError(f'{path.name}: invalid longitude/latitude coordinates.')
    return frame


def identifier_key(value):
    return str(value) if type(value) in (str, int) and str(value).strip() else None


def select_pois(features, boundary):
    for index, feature in enumerate(features, 1):
        if (not isinstance(feature, dict) or feature.get('type') != 'Feature'
                or not isinstance(feature.get('properties'), dict)
                or not all(k in feature['properties'] for k in ('TYPE', 'NAME', 'NAME_AZ', 'OBJECTID', 'status'))
                or type(feature['properties']['TYPE']) is not str):
            raise RuntimeError(f'POI schema changed at source index {index}; inspect before selecting.')
    categories = Counter(f['properties']['TYPE'] for f in features)
    statuses = Counter(json.dumps(f['properties']['status'], ensure_ascii=False) for f in features)
    object_ids = Counter(identifier_key(f['properties']['OBJECTID']) for f in features)
    feature_ids = Counter(identifier_key(f.get('id')) for f in features)
    duplicate_ids = {key: count for key, count in object_ids.items() if key is not None and count > 1}
    duplicate_feature_ids = {key: count for key, count in feature_ids.items() if key is not None and count > 1}
    report('REAL TYPE CATEGORIES AND COUNTS', dict(sorted(categories.items())))
    report('EXACT SELECTED CATEGORIES', SELECTION_REASONS)
    report('REAL SOURCE status VALUES', dict(statuses))
    report('DUPLICATE SOURCE IDENTIFIERS', {'OBJECTID': duplicate_ids, 'feature_id': duplicate_feature_ids,
           'missing_OBJECTID': object_ids.get(None, 0), 'missing_feature_id': feature_ids.get(None, 0)})
    selected, invalid, all_coordinates = [], [], defaultdict(list)
    unselected = outside = 0
    category_candidates = Counter()
    id_schemes = Counter()
    for index, source in enumerate(features, 1):
        p = source['properties']; geometry = source.get('geometry')
        xy = geometry.get('coordinates') if isinstance(geometry, dict) else None
        if (not isinstance(geometry, dict) or geometry.get('type') != 'Point'
                or not isinstance(xy, (list, tuple)) or len(xy) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in xy)
                or not (-180 <= xy[0] <= 180 and -90 <= xy[1] <= 90)):
            invalid.append({'source_index': index, 'source_feature_id': source.get('id'),
                            'OBJECTID': p['OBJECTID'], 'TYPE': p['TYPE'], 'reason': 'invalid/missing/non-2D Point longitude/latitude'})
            continue
        point = Point(xy)
        if not point.is_valid or point.is_empty:
            invalid.append({'source_index': index, 'source_feature_id': source.get('id'), 'reason': 'invalid/empty Point'})
            continue
        all_coordinates[tuple(xy)].append(source.get('id'))
        if p['TYPE'] not in SELECTED_CATEGORIES:
            unselected += 1
            continue
        category_candidates[p['TYPE']] += 1
        if not boundary.covers(point):
            outside += 1
            continue
        oid, fid = identifier_key(p['OBJECTID']), identifier_key(source.get('id'))
        if oid is not None and object_ids[oid] == 1:
            identifier, scheme = f'opendata:poi:objectid:{oid}', 'unique_OBJECTID'
        elif fid is not None and feature_ids[fid] == 1:
            identifier, scheme = f'opendata:poi:featureid:{fid}', 'unique_feature_id'
        else:
            identifier, scheme = f'opendata:poi:source-index:{index}', 'source_index_1_based'
        flags = []
        status = p['status']
        if status is None or (isinstance(status, str) and not status.strip()):
            flags.append('source_status_unavailable')
        elif status == 'Checking':
            flags.append('source_status_Checking_unverified')
        else:
            flags.append('unexpected_source_status')
        if oid is not None and object_ids[oid] > 1:
            flags.append('duplicate_source_OBJECTID')
        if fid is not None and feature_ids[fid] > 1:
            flags.append('duplicate_source_feature_id')
        if oid is not None and fid is not None and oid != fid:
            flags.append('OBJECTID_feature_id_disagree')
        name = p['NAME'] if isinstance(p['NAME'], str) and p['NAME'].strip() else None
        if name is None:
            flags.append('missing_source_NAME')
            name = p['NAME_AZ'] if isinstance(p['NAME_AZ'], str) and p['NAME_AZ'].strip() else None
        if p['NAME'] in QUESTIONABLE_NAMES:
            flags.append('ambiguous_name_in_selected_category')
        properties = copy.deepcopy(p)
        properties.update({'id': identifier, 'name': name, 'category': p['TYPE'], 'source': 'OpenData.az',
                           'source_feature_id': source.get('id'), 'source_index': index, 'id_scheme': scheme,
                           'validation_flags': flags})
        selected.append({'type': 'Feature', 'id': identifier, 'properties': properties,
                         'geometry': copy.deepcopy(geometry)})
        id_schemes[scheme] += 1
    for failure in invalid:
        report('EXCLUDED INVALID POI', failure)
    if not selected or len(selected) + outside + unselected + len(invalid) != len(features):
        raise RuntimeError('No selected POIs or POI count reconciliation failed.')
    if len({f['id'] for f in selected}) != len(selected):
        raise RuntimeError('Generated POI IDs are not unique.')
    retained_coordinates = defaultdict(list)
    for feature in selected:
        retained_coordinates[tuple(feature['geometry']['coordinates'])].append(feature)
    retained_duplicates = []
    for xy, records in retained_coordinates.items():
        if len(records) > 1:
            retained_duplicates.append({'coordinates': list(xy), 'ids': [f['id'] for f in records]})
            for feature in records:
                feature['properties']['validation_flags'].append('coordinate_duplicate_retained')
    all_duplicates = [{'coordinates': list(xy), 'source_feature_ids': ids}
                      for xy, ids in all_coordinates.items() if len(ids) > 1]
    flags = Counter(flag for f in selected for flag in f['properties']['validation_flags'])
    audit = {'source_count': len(features), 'real_TYPE_counts': dict(categories), 'selected_categories': SELECTION_REASONS,
             'category_candidates': dict(category_candidates), 'included_count': len(selected),
             'unselected_category_count': unselected, 'outside_boundary_count': outside,
             'invalid_geometry_count': len(invalid), 'invalid_records': invalid,
             'included_TYPE_counts': dict(Counter(f['properties']['TYPE'] for f in selected)),
             'raw_status_values_json_encoded': dict(statuses),
             'included_status_values_json_encoded': dict(Counter(json.dumps(f['properties']['status']) for f in selected)),
             'duplicate_OBJECTIDs': duplicate_ids, 'duplicate_source_feature_ids': duplicate_feature_ids,
             'raw_coordinate_duplicate_groups': all_duplicates, 'retained_coordinate_duplicate_groups': retained_duplicates,
             'id_schemes': dict(id_schemes), 'validation_flag_counts': dict(flags),
             'spatial_filter': 'actual Baku Polygon/MultiPolygon covers; CITY never controls inclusion',
             'status_policy': 'preserve all source status values; blank/Checking do not prove operation',
             'limitations': 'not exhaustive or independently verified; counts are source records, not deduplicated institutions'}
    report('POI SELECTION AUDIT', audit)
    for flag in flags:
        report('QUESTIONABLE RECORD SAMPLE ' + flag, [{'id': f['id'], 'NAME': f['properties']['NAME'], 'TYPE': f['properties']['TYPE']}
               for f in selected if flag in f['properties']['validation_flags']][:5])
    return {'type': 'FeatureCollection', 'features': selected, 'metadata': audit}


def count_pois(origins, points, categories):
    if not len(points):
        raise RuntimeError('Essential POI layer is empty; refusing misleading zero coverage.')
    pairs = shapely.STRtree(points).query(origins, predicate='dwithin', distance=RADIUS_METERS)
    total = np.bincount(pairs[0], minlength=len(origins))
    categories = np.asarray(categories)
    by_type = {category: np.bincount(pairs[0, categories[pairs[1]] == category], minlength=len(origins))
               for category in SELECTED_CATEGORIES}
    if not np.array_equal(sum(by_type.values()), total) or (total < 0).any() or (total > len(points)).any():
        raise RuntimeError('POI category/radius count reconciliation failed.')
    return total, by_type


def verify_grid_preservation(original, result):
    if (len(original['features']) != len(result['features'])
            or {k: v for k, v in original.items() if k != 'features'} !=
               {k: v for k, v in result.items() if k not in ('features', 'poi_metadata')}):
        raise RuntimeError('Grid count or existing metadata changed.')
    for before, after in zip(original['features'], result['features'], strict=True):
        if {k: v for k, v in before.items() if k != 'properties'} != {k: v for k, v in after.items() if k != 'properties'}:
            raise RuntimeError('Grid IDs, geometry or feature foreign members changed.')
        expected = {k: v for k, v in before['properties'].items() if k != 'pois_nearby'}
        preserved = {k: v for k, v in after['properties'].items() if k not in ('pois_nearby', CATEGORY_COUNT_FIELD)}
        if json.dumps(expected, sort_keys=True, allow_nan=False) != json.dumps(preserved, sort_keys=True, allow_nan=False):
            raise RuntimeError('Grid population, accessibility fields or existing flags/properties changed.')
        p = after['properties']; counts = p[CATEGORY_COUNT_FIELD]
        if (type(p['pois_nearby']) is not int or p['pois_nearby'] < 0 or set(counts) != set(SELECTED_CATEGORIES)
                or any(type(v) is not int or v < 0 for v in counts.values()) or sum(counts.values()) != p['pois_nearby']
                or any(p[field] is not None for field in PENDING_FIELDS)):
            raise RuntimeError('POI integer/category counts or pending metric nulls failed validation.')


def build_documents():
    raw, source = read_document(RAW_PATH)
    source_frame = gpd.read_file(RAW_PATH)
    if source_frame.crs is None or source_frame.crs.to_epsg() != 4326 or len(source_frame) != len(raw['features']):
        raise RuntimeError('Unexpected POI CRS/count; inspect source before processing.')
    source.update({'crs': str(source_frame.crs), 'geometry_types': source_frame.geom_type.value_counts(dropna=False).to_dict(),
                   'properties': sorted({k for f in raw['features'] for k in f['properties']})})
    report('RAW POI SCHEMA', source)
    boundary_doc, boundary_source = read_document(BOUNDARY_PATH)
    boundary_frame = validate_frame(BOUNDARY_PATH, boundary_doc, ['Polygon', 'MultiPolygon'])
    if len(boundary_frame) != 1:
        raise RuntimeError('Expected one actual study polygon feature.')
    boundary = boundary_frame.geometry.iloc[0]
    pois = select_pois(raw['features'], boundary)
    pois['metadata'].update({'source': source, 'boundary': boundary_source})
    original, grid_source = read_document(GRID_PATH)
    grid_frame = validate_frame(GRID_PATH, original, ['Polygon', 'MultiPolygon'])
    ids = [f['properties'].get('id') for f in original['features']]
    if (len(ids) != 35029 or len(set(ids)) != len(ids) or any(type(i) is not str or not i for i in ids)
            or any(f.get('id') != i for f, i in zip(original['features'], ids, strict=True))
            or 'poi_metadata' in original):
        raise RuntimeError('Expected 35,029 unique string grid IDs without existing POI metadata.')
    for feature in original['features']:
        p = feature['properties']
        if (CATEGORY_COUNT_FIELD in p or p.get('pois_nearby', 'missing') is not None
                or any(p.get(field, 'missing') is not None for field in PENDING_FIELDS)):
            raise RuntimeError('Expected null POI/routes/scores in input grid and no category counts yet.')
    projected = grid_frame.to_crs(METRIC_CRS)
    origins = projected.representative_point().to_numpy()
    if not shapely.contains(projected.geometry.array, origins).all():
        raise RuntimeError('Grid representative points are not inside their geometries.')
    poi_points = gpd.GeoSeries([Point(f['geometry']['coordinates']) for f in pois['features']], crs=4326).to_crs(METRIC_CRS).to_numpy()
    if not np.isfinite(shapely.get_coordinates(poi_points)).all():
        raise RuntimeError('POI coordinate projection failed.')
    counts, by_type = count_pois(origins, poi_points, [f['properties']['TYPE'] for f in pois['features']])
    result = copy.deepcopy(original)
    for index, feature in enumerate(result['features']):
        feature['properties']['pois_nearby'] = int(counts[index])
        feature['properties'][CATEGORY_COUNT_FIELD] = {category: int(values[index]) for category, values in by_type.items()}
    samples = []
    sample_indices = np.unique(np.linspace(0, len(origins) - 1, 5, dtype=int))
    # Five independent full-target checks only; no all-grid/all-POI loops.
    for index in sample_indices:
        exact = shapely.distance(origins[index], poi_points) <= RADIUS_METERS
        if int(exact.sum()) != counts[index]:
            raise RuntimeError('Independent sample POI radius count failed.')
        samples.append({'id': ids[index], 'population': result['features'][index]['properties']['population'],
                        'pois_nearby': int(counts[index]), CATEGORY_COUNT_FIELD: result['features'][index]['properties'][CATEGORY_COUNT_FIELD]})
    summary = {'cell_count': len(counts), 'minimum': int(counts.min()), 'median': float(np.median(counts)),
               'maximum': int(counts.max()), 'mean': float(counts.mean()), 'zero_count': int((counts == 0).sum()),
               'cells_with_POIs': int((counts > 0).sum()),
               'null_population_cells_preserved': sum(f['properties']['population'] is None for f in original['features'])}
    result['poi_metadata'] = {'method': 'straight_line_500m_from_grid_representative_point',
                              'distance_crs': METRIC_CRS, 'radius_m': RADIUS_METERS, 'inclusive_radius': True,
                              'selected_categories': SELECTION_REASONS, 'poi_source': source, 'grid_source': grid_source,
                              'boundary_source': boundary_source, 'included_POI_count': len(pois['features']),
                              'category_count_field': CATEGORY_COUNT_FIELD,
                              'category_count_definition': 'dictionary of original TYPE -> mapped record count within inclusive 500 m; sums to pois_nearby',
                              'origin_method': 'representative_point inside projected clipped grid Polygon/MultiPolygon, matching Step 14A',
                              'limitations': 'not walking-network access; not exhaustive; co-located IDs counted separately; status not operational verification',
                              'summary': summary, 'deterministic_sample': samples}
    report('GRID POI COUNT STATISTICS', summary)
    report('DETERMINISTIC GRID SAMPLE', samples)
    verify_grid_preservation(original, result)
    return pois, original, result, grid_frame, boundary


def verify_saved(path, expected, geometry_types, original_grid=None, grid_frame=None, boundary=None):
    with path.open(encoding='utf-8') as source:
        saved = json.load(source)
    if saved != expected:
        raise RuntimeError(f'{path.name}: source-derived IDs, geometry, properties or counts changed.')
    frame = validate_frame(path, saved, geometry_types)
    ids = [f['properties']['id'] for f in saved['features']]
    if (any(type(i) is not str or not i for i in ids) or len(set(ids)) != len(ids)
            or frame['id'].tolist() != ids or any(f.get('id') != i for f, i in zip(saved['features'], ids, strict=True))):
        raise RuntimeError('Reload unique/string feature ID validation failed.')
    if original_grid is not None:
        verify_grid_preservation(original_grid, saved)
        if (not shapely.equals_exact(frame.geometry.array, grid_frame.geometry.array, tolerance=0).all()
                or not np.array_equal(frame['pois_nearby'].to_numpy(), np.array([f['properties']['pois_nearby'] for f in saved['features']]))):
            raise RuntimeError('Reload grid geometry or integer count preservation failed.')
    else:
        if not shapely.covers(boundary, frame.geometry.array).all():
            raise RuntimeError('Reloaded essential POI is outside actual study boundary.')
        if not all(f['properties']['TYPE'] in SELECTED_CATEGORIES and f['properties']['category'] == f['properties']['TYPE'] for f in saved['features']):
            raise RuntimeError('Reload selected category preservation failed.')
        if not shapely.equals_exact(frame.geometry.array, np.array([Point(f['geometry']['coordinates']) for f in saved['features']], dtype=object), tolerance=0).all():
            raise RuntimeError('Reload POI coordinates changed.')
    print(f'Reload verification PASSED: {len(frame)} features; {path.name}; IDs, geometry, EPSG:4326 and properties', flush=True)


def save_outputs(pois, original, grid, grid_frame, boundary):
    staged = []
    try:
        for path, document, types in ((POIS_PATH, pois, ['Point']), (OUTPUT_GRID_PATH, grid, ['Polygon', 'MultiPolygon'])):
            path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                    prefix='.pois-', suffix='.geojson', delete=False) as output:
                temporary = Path(output.name); staged.append((temporary, path))
                json.dump(document, output, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
                output.write('\n'); output.flush(); os.fsync(output.fileno())
            verify_saved(temporary, document, types, original if path == OUTPUT_GRID_PATH else None, grid_frame, boundary)
        for temporary, path in staged:
            os.replace(temporary, path)
            print(f'Saved intermediate dataset: {path}', flush=True)
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Recompute selections/counts and validate both existing outputs without writing.')
    args = parser.parse_args()
    pois, original, grid, grid_frame, boundary = build_documents()
    if args.verify_only:
        verify_saved(POIS_PATH, pois, ['Point'], boundary=boundary)
        verify_saved(OUTPUT_GRID_PATH, grid, ['Polygon', 'MultiPolygon'], original, grid_frame, boundary)
    else:
        save_outputs(pois, original, grid, grid_frame, boundary)
    print(f'Total runtime: {perf_counter() - started:.2f} seconds', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
