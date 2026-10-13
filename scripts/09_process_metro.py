"""Process metro entrances and station-level observed daily entry counts.

Inspected inputs: UTF-8 semicolon pathways CSV; UTF-8 BOM comma passenger CSV.
Pathway integer coordinates are microdegrees: divide by 1,000,000 and emit
[longitude, latitude]. This scaling/order puts the inspected 98 locations in
Baku; swapped coordinates put none there. Raw values remain in source_record.

Group by exact station labels after outer-whitespace trimming, never proximity.
The one explicit label correction uses the parallel Station='28 May' field to
resolve Stansiya='28.05.2026 00:00:00'; both originals remain preserved. The
representative point is the arithmetic mean of validated entrance coordinates
in EPSG:32639, transformed to EPSG:4326, not an officially surveyed center.

Passenger dates actually use YYYY-MM-DD 00:00:00,000, despite the header.
Counts are nonnegative base-10 integers. Duplicate station/date or invalid
observations abort before writes; blank counts and absent dates never become
zero. Means use unique dates with numeric observations. Entries are neither
origin-destination trips nor unique people. Valid locations outside the study
boundary and duplicate entrance locations are reported and retained.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import geopandas as gpd
from shapely.geometry import Point


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATHWAYS_PATH = PROJECT_ROOT / 'data/raw/opendata/pathways.csv'
PASSENGERS_PATH = PROJECT_ROOT / 'data/raw/opendata/passenger-2026.csv'
BOUNDARY_PATH = PROJECT_ROOT / 'data/processed/boundaries/baku_boundary.geojson'
STATIONS_PATH = PROJECT_ROOT / 'data/processed/transport/metro_stations.geojson'
ENTRANCES_PATH = PROJECT_ROOT / 'data/processed/transport/metro_entrances.geojson'
PATHWAY_COLUMNS = ['Stansiya', 'Station', 'coğrafi enliyi (latitude)',
                   'coğrafi uzunluğu (longitude)', 'yerləşdiyi ünvan', 'Çıxış nörmələri']
PASSENGER_COLUMNS = ['Tarix (gün.ay.il)', 'Stansiya', 'Gündəlik gediş sayı']
REPRESENTATIVE_METHOD = 'mean of validated entrance XY in EPSG:32639, transformed to EPSG:4326; not an officially surveyed station center'
# Keys are exact inspected pathways Station labels; values are exact passenger
# labels. Dual-language Stansiya/Station fields establish the station identities.
# Only outer whitespace is normalized: no case folding or fuzzy matching.
PASSENGER_ALIASES = {
    'Khojasan': 'Khocasen',                 # Xocəsən
    'Azadliq prospekti': 'Azadlig Prospekti',  # Azadlıq prospekti
    'Insahatchilar': 'Inshaatchilar',       # İnşaatçılar; source spelling
    'Elmler Akademiyasi': 'Elmlar Akademiyasi',  # Elmlər Akademiyası
    '28 May': '28.May',                    # Parallel field resolves date-like AZ label
    'Koroglu': 'Koroghlu',                 # Koroğlu
    'Jafar Jabbarly': 'Jafar Jabbarli',     # Cəfər Cabbarlı
    'Shah Ismail Khatai': 'Khatai',        # Şah İsmayıl Xətai; shortened label
}
LABEL_CORRECTIONS = {('28.05.2026 00:00:00', '28 May'): '28 May'}


def report(label, value):
    print(label + ': ' + json.dumps(value, ensure_ascii=False, allow_nan=False))


def read_csv(path, delimiter, columns):
    raw = path.read_bytes()
    encoding = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
    reader = csv.DictReader(io.StringIO(raw.decode(encoding, errors='strict'), newline=''),
                            delimiter=delimiter, strict=True)
    if reader.fieldnames != columns:
        raise RuntimeError(f'{path.name}: schema/delimiter changed: {reader.fieldnames}')
    rows = list(reader)
    if not rows or any(None in r or any(r[c] is None for c in columns) for r in rows):
        raise RuntimeError(f'{path.name}: empty input or malformed CSV record; no output written.')
    audit = {'file': str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else path.name,
             'sha256': hashlib.sha256(raw).hexdigest(), 'encoding': encoding,
             'delimiter': delimiter, 'columns': columns, 'source_record_count': len(rows),
             'missing_values': {c: sum(not r[c].strip() for r in rows) for c in columns}}
    report('SOURCE CSV', audit)
    return rows, audit


def audit_passengers(path):
    rows, audit = read_csv(path, ',', PASSENGER_COLUMNS)
    observations, row_dates, labels = defaultdict(dict), defaultdict(set), defaultdict(set)
    pairs = defaultdict(list)
    dates, counts, errors = set(), [], []
    missing_counts = negative_counts = 0
    for record_index, row in enumerate(rows, 2):
        label = row['Stansiya'].strip()
        raw_date = row[PASSENGER_COLUMNS[0]].strip()
        raw_count = row[PASSENGER_COLUMNS[2]].strip()
        try:
            if not label:
                raise ValueError('missing station name')
            if not re.fullmatch(r'2026-\d{2}-\d{2} 00:00:00,000', raw_date):
                raise ValueError('expected 2026 YYYY-MM-DD 00:00:00,000 timestamp')
            day = datetime.strptime(raw_date, '%Y-%m-%d %H:%M:%S,%f').date()
            pairs[(label, day)].append(record_index)
            row_dates[label].add(day)
            labels[label].add(row['Stansiya'])
            dates.add(day)
            if not raw_count:
                missing_counts += 1
                continue
            if not re.fullmatch(r'-?\d+', raw_count, flags=re.ASCII):
                raise ValueError('count is not a base-10 integer')
            count = int(raw_count)
            if count < 0:
                negative_counts += 1
                raise ValueError('negative entry count')
            observations[label][day] = count
            counts.append(count)
        except ValueError as exc:
            errors.append({'source_record_index': record_index, 'source_record': row, 'reason': str(exc)})
    duplicates = [{'station': label, 'date': day.isoformat(), 'source_record_indices': indices}
                  for (label, day), indices in sorted(pairs.items()) if len(indices) > 1]
    audit.update({'missing_count_rows': missing_counts, 'negative_count_rows': negative_counts,
                  'invalid_rows': len(errors), 'duplicate_station_date_pairs': len(duplicates)})
    report('PASSENGER VALIDATION', audit)
    for error in errors:
        report('INVALID PASSENGER RECORD', error)
    for duplicate in duplicates:
        report('DUPLICATE STATION DATE', duplicate)
    if errors or duplicates:
        raise RuntimeError('Passenger audit failed; refusing ambiguous averages. Outputs not written/replaced.')
    first, last = min(dates), max(dates)
    span = (last - first).days + 1
    stats = {}
    for label in sorted(row_dates):
        observed = observations[label]
        observed_dates = sorted(observed)
        source_dates = sorted(row_dates[label])
        stats[label] = {
            'passenger_source_names': sorted(labels[label]),
            'avg_daily_entries': sum(observed.values()) / len(observed) if observed else None,
            'observation_days': len(observed), 'source_date_days': len(source_dates),
            'missing_count_days': len(source_dates) - len(observed),
            'first_observation_date': observed_dates[0].isoformat() if observed else None,
            'last_observation_date': observed_dates[-1].isoformat() if observed else None,
            'first_source_date': source_dates[0].isoformat(), 'last_source_date': source_dates[-1].isoformat(),
            'days_without_observation_in_global_span': span - len(observed),
            'observed_entries_sum': sum(observed.values()) if observed else None,
        }
        report('STATION OBSERVATIONS ' + label, stats[label])
    audit.update({'station_count': len(stats), 'date_min': first.isoformat(), 'date_max': last.isoformat(),
                  'calendar_span_days': span, 'distinct_source_dates': len(dates),
                  'numeric_observations': len(counts), 'count_min': min(counts) if counts else None,
                  'count_max': max(counts) if counts else None, 'zero_counts': counts.count(0),
                  'observed_entries_sum': sum(counts) if counts else None,
                  'date_format': '%Y-%m-%d %H:%M:%S,%f', 'numeric_format': 'base-10 integers',
                  'mean_denominator': 'unique dates with numeric counts; missing counts/dates are not zero'})
    if sum(s['observation_days'] for s in stats.values()) != len(counts):
        raise RuntimeError('Passenger observation reconciliation failed.')
    report('PASSENGER COVERAGE', audit)
    return stats, audit


def load_boundary():
    frame = gpd.read_file(BOUNDARY_PATH)
    if len(frame) != 1 or frame.crs is None:
        raise RuntimeError('Expected one study boundary with a declared CRS.')
    polygon = frame.to_crs(4326).geometry.iloc[0]
    if (polygon is None or polygon.is_empty or not polygon.is_valid
            or polygon.geom_type not in {'Polygon', 'MultiPolygon'}):
        raise RuntimeError('Invalid, empty or non-polygonal study boundary.')
    return polygon


def build_locations(rows, boundary):
    groups, entrances, excluded = {}, [], []
    english_identities = {}
    for record_index, row in enumerate(rows, 2):
        try:
            raw_lat, raw_lon = row[PATHWAY_COLUMNS[2]], row[PATHWAY_COLUMNS[3]]
            if not all(re.fullmatch(r'-?\d+', v.strip(), flags=re.ASCII) for v in (raw_lat, raw_lon)):
                raise ValueError('expected integer microdegree coordinates')
            lat, lon = int(raw_lat) / 1_000_000, int(raw_lon) / 1_000_000
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError('scaled latitude/longitude out of range')
            point = Point(lon, lat)
            if point.is_empty or not point.is_valid:
                raise ValueError('invalid/empty point')
        except ValueError as exc:
            excluded.append({'source_record_index': record_index, 'source_record': row, 'reason': str(exc)})
            continue
        az, en = row['Stansiya'].strip(), row['Station'].strip()
        name = LABEL_CORRECTIONS.get((az, en), az or en or None)
        # Unidentified valid entrances remain individual rather than being
        # grouped into an invented station by coordinates or a blank label.
        identity = name or f'unidentified-source-record:{record_index}'
        station_id = 'metro:station:' + quote(identity, safe='')
        if en and en in english_identities and english_identities[en] != station_id:
            raise RuntimeError(f'Ambiguous Station identity {en!r}; inspect source labels before grouping.')
        if en:
            english_identities[en] = station_id
        if station_id not in groups:
            groups[station_id] = {'name': name, 'entrances': [], 'az': set(), 'en': set()}
        group = groups[station_id]
        group['az'].add(row['Stansiya']); group['en'].add(row['Station'])
        entrance_id = f'metro:entrance:pathways:record:{record_index}'
        properties = {'id': entrance_id, 'name': row['Çıxış nörmələri'] or None,
                      'station_id': station_id, 'source': 'OpenData.az', 'source_file': 'pathways.csv',
                      'source_record_index': record_index, 'source_record': row,
                      'address': row['yerləşdiyi ünvan'] or None, 'boundary_covered': bool(boundary.covers(point))}
        entrance = {'type': 'Feature', 'id': entrance_id, 'properties': properties,
                    'geometry': {'type': 'Point', 'coordinates': [lon, lat]}}
        entrances.append(entrance); group['entrances'].append(entrance)
        if not properties['boundary_covered'] or name is None:
            report('LOCATION REVIEW (retained)', properties)
        if (az, en) in LABEL_CORRECTIONS:
            report('EXPLICIT LABEL CORRECTION', {'source_record_index': record_index,
                   'original_name': az, 'parallel_Station': en, 'representative_name': name})
    for failure in excluded:
        report('EXCLUDED ENTRANCE', failure)
    if not entrances or len(entrances) + len(excluded) != len(rows):
        raise RuntimeError('No valid entrances or source count reconciliation failed.')
    stations = []
    for station_id, group in groups.items():
        members = group['entrances']
        projected = gpd.GeoSeries([Point(f['geometry']['coordinates']) for f in members], crs=4326).to_crs(32639)
        mean = Point(math.fsum(p.x for p in projected) / len(members), math.fsum(p.y for p in projected) / len(members))
        representative = gpd.GeoSeries([mean], crs=32639).to_crs(4326).iloc[0]
        properties = {'id': station_id, 'name': group['name'], 'avg_daily_entries': None,
                      'source': 'OpenData.az', 'location_source_file': 'pathways.csv',
                      'source_station_names': sorted(group['az']), 'source_station_names_parallel': sorted(group['en']),
                      'entrance_count': len(members), 'entrance_ids': [f['id'] for f in members],
                      'source_record_indices': [f['properties']['source_record_index'] for f in members],
                      'representative_point_method': REPRESENTATIVE_METHOD,
                      'boundary_covered': bool(boundary.covers(representative))}
        stations.append({'type': 'Feature', 'id': station_id, 'properties': properties,
                         'geometry': {'type': 'Point', 'coordinates': [representative.x, representative.y]}})
        if not properties['boundary_covered']:
            report('STATION BOUNDARY EXCEPTION (retained)', {'id': station_id, 'name': group['name']})
    coordinates = Counter(tuple(f['geometry']['coordinates']) for f in entrances)
    duplicate_groups = [[f['id'] for f in entrances if tuple(f['geometry']['coordinates']) == xy]
                        for xy, count in coordinates.items() if count > 1]
    audit = {'source_records': len(rows), 'retained_entrances': len(entrances), 'excluded_records': len(excluded),
             'exclusions': excluded, 'station_count': len(stations), 'coordinate_scale': 1_000_000,
             'coordinate_order': '[longitude, latitude]', 'crs': 'EPSG:4326',
             'covered_entrances': sum(f['properties']['boundary_covered'] for f in entrances),
             'covered_representatives': sum(f['properties']['boundary_covered'] for f in stations),
             'scaled_bounds': gpd.GeoSeries([Point(f['geometry']['coordinates']) for f in entrances]).total_bounds.tolist(),
             'swapped_order_boundary_covered': sum(boundary.covers(Point(*reversed(f['geometry']['coordinates']))) for f in entrances),
             'duplicate_coordinate_groups_retained': duplicate_groups,
             'representative_point_method': REPRESENTATIVE_METHOD,
             'station_grouping': 'exact source identity after trimming outer whitespace; explicit label correction only',
             'id_method': 'station: URL-encoded identity; entrance: CSV record index including header (stable for unchanged order)',
             'label_corrections': [{'original': az, 'parallel_Station': en, 'name': name}
                                   for (az, en), name in LABEL_CORRECTIONS.items()]}
    report('LOCATION AUDIT', audit)
    return stations, entrances, audit


def join_passengers(stations, stats):
    matched, unmatched, used = [], [], set()
    for station in stations:
        properties = station['properties']
        # Require a single distinct match, including when both language fields
        # could match. Ambiguity leaves demand unavailable rather than guessed.
        candidates = set()
        for label in [properties['name']] + [s.strip() for s in properties['source_station_names_parallel']]:
            if label in stats:
                candidates.add(label)
            alias = PASSENGER_ALIASES.get(label)
            if alias in stats:
                candidates.add(alias)
        properties.update({'avg_daily_entries': None, 'observation_days': None,
                           'source_date_days': None, 'missing_count_days': None,
                           'first_observation_date': None, 'last_observation_date': None,
                           'first_source_date': None, 'last_source_date': None,
                           'observed_entries_sum': None, 'passenger_source_names': None,
                           'days_without_observation_in_global_span': None,
                           'passenger_station_name': None, 'passenger_join_status': 'unmatched',
                           'passenger_source_file': 'passenger-2026.csv',
                           'entries_mean_method': 'mean over unique observed dates with numeric counts; not OD trips or unique people'})
        if len(candidates) == 1:
            label = next(iter(candidates))
            if label in used:
                raise RuntimeError(f'Passenger label {label!r} matched multiple station identities.')
            used.add(label)
            properties.update(stats[label])
            properties['passenger_station_name'] = label
            properties['passenger_join_status'] = 'matched' if stats[label]['observation_days'] else 'matched_without_numeric_counts'
            matched.append({'station_name': properties['name'], 'passenger_name': label})
        else:
            properties['passenger_join_status'] = 'ambiguous' if candidates else 'unmatched'
            unmatched.append({'station_name': properties['name'], 'candidates': sorted(candidates)})
    summary = {'matched': matched, 'unmatched_location_stations': unmatched,
               'unmatched_passenger_names': sorted(set(stats) - used), 'explicit_alias_mapping': PASSENGER_ALIASES}
    report('STATION NAME JOIN', summary)
    return summary


def verify_documents(stations, entrances):
    for document in (stations, entrances):
        identifiers = []
        for feature in document['features']:
            properties = feature['properties']; identifier = properties['id']
            if not isinstance(identifier, str) or not identifier or feature['id'] != identifier:
                raise RuntimeError('Feature IDs must be consistent nonempty strings.')
            identifiers.append(identifier)
            if properties['name'] is not None and not isinstance(properties['name'], str):
                raise RuntimeError('Names must be string or null.')
            xy = feature['geometry']['coordinates']
            if (feature['geometry']['type'] != 'Point' or len(xy) != 2
                    or not all(type(v) in (int, float) and math.isfinite(v) for v in xy)
                    or not (-180 <= xy[0] <= 180 and -90 <= xy[1] <= 90)):
                raise RuntimeError('Invalid longitude/latitude Point.')
        if len(set(identifiers)) != len(identifiers):
            raise RuntimeError('Duplicate output feature IDs.')
    entrance_groups = defaultdict(list)
    for feature in entrances['features']:
        entrance_groups[feature['properties']['station_id']].append(feature['id'])
    station_ids = {f['id'] for f in stations['features']}
    if set(entrance_groups) != station_ids:
        raise RuntimeError('Entrance station_id links failed.')
    for feature in stations['features']:
        props = feature['properties']; value = props['avg_daily_entries']
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise RuntimeError('Entry means must be finite nonnegative numbers or null.')
        if props['entrance_ids'] != entrance_groups[feature['id']] or props['entrance_count'] != len(props['entrance_ids']):
            raise RuntimeError('Station entrance counts/links failed.')


def verify_saved(path, expected):
    with path.open(encoding='utf-8') as source:
        if json.load(source) != expected:
            raise RuntimeError(f'{path.name}: JSON counts, IDs, coordinates, properties or metadata differ from inputs.')
    frame = gpd.read_file(path)
    if (len(frame) != len(expected['features']) or frame.crs is None or frame.crs.to_epsg() != 4326
            or not frame.geom_type.eq('Point').all() or not frame.is_valid.all() or frame.is_empty.any()
            or frame['id'].tolist() != [f['id'] for f in expected['features']]):
        raise RuntimeError(f'{path.name}: reload count, IDs, Point validity or CRS failed.')
    for geometry, feature in zip(frame.geometry, expected['features'], strict=True):
        if list(geometry.coords[0]) != feature['geometry']['coordinates']:
            raise RuntimeError(f'{path.name}: reload coordinates changed.')
    print(f'Reload verification PASSED: {path.name} ({len(frame)} Points, IDs, geometries, EPSG:4326, all properties and metadata)')


def save_outputs(stations, entrances):
    # Stage and reload both files before replacing either existing output.
    staged = []
    try:
        for path, document in ((STATIONS_PATH, stations), (ENTRANCES_PATH, entrances)):
            path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                    prefix='.metro-', suffix='.geojson', delete=False) as output:
                temporary = Path(output.name); staged.append((temporary, path))
                json.dump(document, output, ensure_ascii=False, allow_nan=False, indent=2)
                output.write('\n'); output.flush(); os.fsync(output.fileno())
            verify_saved(temporary, document)
        for temporary, path in staged:
            os.replace(temporary, path)
            print(f'Saved intermediate dataset: {path}')
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Recompute from raw CSVs and validate both existing outputs without writing.')
    args = parser.parse_args()
    rows, pathway_source = read_csv(PATHWAYS_PATH, ';', PATHWAY_COLUMNS)
    stats, passenger_source = audit_passengers(PASSENGERS_PATH)
    station_features, entrance_features, locations = build_locations(rows, load_boundary())
    join = join_passengers(station_features, stats)
    station_document = {'type': 'FeatureCollection', 'features': station_features,
                        'metadata': {'pathways_source': pathway_source, 'passenger_source': passenger_source,
                                     'locations': locations, 'station_name_join': join,
                                     'metric_semantics': 'station-level entry counts; not OD trips or unique people'}}
    entrance_document = {'type': 'FeatureCollection', 'features': entrance_features,
                         'metadata': {'pathways_source': pathway_source, 'locations': locations}}
    verify_documents(station_document, entrance_document)
    if args.verify_only:
        verify_saved(STATIONS_PATH, station_document)
        verify_saved(ENTRANCES_PATH, entrance_document)
    else:
        save_outputs(station_document, entrance_document)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
