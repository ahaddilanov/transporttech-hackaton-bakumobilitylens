#!/usr/bin/env python3
"""Download/validate the complete Step 16B-1 OSM bike study network.

Run from the repository root with the existing .venv:
  .venv/bin/python scripts/15_build_bike_network.py
  .venv/bin/python scripts/15_build_bike_network.py --verify-only

Existing outputs are validated/reused. Verification never accesses OSM.
OSMnx API: https://osmnx.readthedocs.io/en/stable/user-reference.html
Version-specific response auditing also inspects OSMnx 2.1.1's Overpass iterator.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
from pyproj import CRS, Transformer
import shapely
from shapely.geometry import LineString, Point, mapping, shape

ROOT = Path(__file__).resolve().parents[1]
CYCLEWAYS = ROOT / 'data/processed/transport/cycleways.geojson'
BOUNDARY = ROOT / 'data/processed/boundaries/baku_boundary.geojson'
AREA_PATH = ROOT / 'data/processed/networks/baku_bike_study_area.geojson'
GRAPH_PATH = ROOT / 'data/processed/networks/baku_bike.graphml'
METHOD = 'baku-bike-study-network-v1.0'
METRIC_CRS = 'EPSG:32639'
BUFFER_M = 3000
TO_GEO = Transformer.from_crs(METRIC_CRS, 4326, always_xy=True).transform
TO_METRIC = Transformer.from_crs(4326, METRIC_CRS, always_xy=True).transform
WAY_TAGS = ['highway', 'bicycle', 'cycleway', 'access', 'oneway', 'bridge', 'tunnel', 'surface',
            'oneway:bicycle', 'bicycle:forward', 'bicycle:backward', 'bicycle:conditional',
            'access:conditional', 'oneway:conditional', 'cycleway:left', 'cycleway:right',
            'cycleway:both', 'cycleway:left:oneway', 'cycleway:right:oneway',
            'cycleway:both:oneway', 'cycleway:width', 'cycleway:surface', 'segregated',
            'smoothness', 'tracktype', 'incline', 'lit', 'foot', 'sidewalk', 'barrier',
            'junction', 'service', 'maxspeed', 'lanes', 'width', 'name', 'ref']
NODE_TAGS = ['bicycle', 'access', 'barrier', 'crossing', 'crossing:signals', 'kerb', 'highway', 'traffic_signals']
SUBDIVISION_ADVICE = (
    'No partial network has been published. Reproducible fallback: intersect the FULL study polygon '
    'with a 5000m EPSG:32639 lattice anchored at (0,0), retain every nonempty tile, request each '
    'with 500m overlap, audit every response, merge raw OSM nodes/ways by OSM IDs and reconcile '
    'duplicates before constructing/truncating one graph. Record every tile and timestamp; '
    'do not drop failed tiles or treat their union as complete.')
LIMITATIONS = [
    'OSM bike-permissible roads are not necessarily safe, separated or verified bicycle lanes.',
    'OSM coverage, access, surfaces and operational status may be incomplete or stale.',
    'OSMnx 2.1.1 bike filter excludes footways even where bicycle access might be explicitly allowed.',
    'OSMnx direction uses general oneway/roundabout tags; bicycle contraflow and conditional exceptions require assessment.',
    'Turn-restriction relations, access schedules, barrier passability, gradients and crossing safety are not modeled.',
    'Study-boundary truncation can disconnect roads; paths outside the study area cannot be routed.',
    'All components and original way segments are retained; no recommended corridors are created.',
]


def report(label, value):
    print(label + ': ' + json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def polygon_parts(geometry):
    if geometry.geom_type == 'Polygon':
        return [geometry]
    if geometry.geom_type in ('MultiPolygon', 'GeometryCollection'):
        return [part for member in geometry.geoms for part in polygon_parts(member)]
    return []


def make_study_area(lines, boundary):
    # Explicit 16 quarter-circle segments matches GeoPandas' default buffer.
    buffers = shapely.buffer(np.array(lines, dtype=object), BUFFER_M, quad_segs=16)
    clipped = shapely.union_all(buffers).intersection(boundary)
    area = shapely.union_all(polygon_parts(clipped))
    if (area.is_empty or not area.is_valid or area.geom_type not in ('Polygon', 'MultiPolygon')
            or area.area <= 0 or area.difference(boundary).area > 1e-6):
        raise ValueError('Study area must be valid, nonempty and wholly inside the actual Baku boundary.')
    return area


def load_inputs():
    frames, audits = [], {}
    for path, kinds in [(CYCLEWAYS, ['LineString', 'MultiLineString']), (BOUNDARY, ['Polygon', 'MultiPolygon'])]:
        frame = gpd.read_file(path)
        coords = shapely.get_coordinates(frame.geometry.array)
        if (frame.empty or frame.crs is None or frame.crs.to_epsg() != 4326
                or frame.geometry.isna().any() or frame.is_empty.any() or not frame.is_valid.all()
                or not frame.geom_type.isin(kinds).all() or not np.isfinite(coords).all()
                or shapely.has_z(frame.geometry.array).any()
                or (np.abs(coords[:, 0]) > 180).any() or (np.abs(coords[:, 1]) > 90).any()):
            raise ValueError(f'{path.name}: expected valid nonempty 2D EPSG:4326 {kinds}.')
        audits[path.name] = {'sha256': digest(path), 'features': len(frame),
                             'geometry_types': frame.geom_type.value_counts().to_dict(),
                             'fields': sorted(frame.columns)}
        frames.append(frame.to_crs(METRIC_CRS))
    lines, boundary = frames
    if (len(lines) != 60 or len(boundary) != 1 or not lines['source'].eq('AYNA').all()
            or lines['id'].isna().any() or not lines['id'].is_unique
            or boundary.iloc[0]['shapeName'] != 'Baku City'):
        raise ValueError('Expected all 60 AYNA lines with unique IDs and the one actual Baku City boundary.')
    area = make_study_area(lines.geometry.to_numpy(), boundary.geometry.iloc[0])
    geographic = shapely.transform(area, TO_GEO, interleaved=False)
    if geographic.is_empty or not geographic.is_valid:
        raise ValueError('Reprojected EPSG:4326 study area is invalid.')
    base = {'method_version': METHOD, 'osmnx_version': ox.__version__, 'buffer_m': BUFFER_M,
            'metric_crs': METRIC_CRS, 'study_area_km2': area.area / 1e6,
            'study_polygon_parts': len(polygon_parts(area)), 'inputs': audits,
            'study_geometry_sha256': hashlib.sha256(canonical(mapping(geographic)).encode()).hexdigest()}
    report('INPUTS AND STUDY AREA', base)
    return area, geographic, base


def audit_responses(responses):
    nodes, ways, timestamps = {}, {}, set()
    for response in responses:
        if response.get('remark'):
            raise ValueError(f"Overpass remark indicates possibly incomplete data: {response['remark']}")
        if not isinstance(response.get('elements'), list):
            raise ValueError('Overpass response has no elements list.')
        timestamp = response.get('osm3s', {}).get('timestamp_osm_base')
        if timestamp:
            timestamps.add(timestamp)
        for element in response['elements']:
            target = nodes if element['type'] == 'node' else ways if element['type'] == 'way' else None
            if target is not None:
                previous = target.get(element['id'])
                if previous is not None and previous != element:
                    raise ValueError('Conflicting OSM objects across query responses; no mixed graph accepted.')
                target[element['id']] = element
    missing = {node for way in ways.values() for node in way['nodes'] if node not in nodes}
    if missing:
        raise ValueError(f'Incomplete Overpass response: {len(missing)} referenced nodes missing.')
    if not ways or not nodes:
        raise ValueError('Overpass returned no complete network nodes/ways.')
    return ways, sorted(timestamps)


def download_graph(geographic, base):
    if ox.__version__ != '2.1.1':
        raise ValueError('Response audit is verified for OSMnx 2.1.1; review a version change before downloading.')
    # Public graph API internally buffers by 500m; preflight the SAME area.
    buffered = shapely.transform(geographic, TO_METRIC, interleaved=False).buffer(500)
    query_geographic = shapely.transform(buffered, TO_GEO, interleaved=False)
    expected_responses = len(ox._overpass._make_overpass_polygon_coord_strs(query_geographic))
    query_km2 = buffered.convex_hull.area / 1e6
    report('DOWNLOAD PREFLIGHT', {'buffered_query_envelope_km2': query_km2,
                                 'expected_responses': expected_responses,
                                 'osmnx_max_query_area_km2': ox.settings.max_query_area_size / 1e6})
    if expected_responses > 16 or query_km2 > 2500:
        raise ValueError('Query exceeds this initial study service budget. ' + SUBDIVISION_ADVICE)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(ROOT / 'cache')
    ox.settings.log_console = True
    ox.settings.useful_tags_way = sorted(set(ox.settings.useful_tags_way) | set(WAY_TAGS))
    ox.settings.useful_tags_node = sorted(set(ox.settings.useful_tags_node) | set(NODE_TAGS))
    if ox.settings.all_oneway or 'bike' in ox.settings.bidirectional_network_types:
        raise ValueError('Unexpected forced directionality settings; refusing to alter bicycle directions silently.')
    responses = []
    original_iterator = ox._overpass._download_overpass_network
    original_cache_read = ox._http._retrieve_from_cache
    cache_hits = 0

    def audited_cache_read(*args, **kwargs):
        nonlocal cache_hits
        response = original_cache_read(*args, **kwargs)
        cache_hits += isinstance(response, dict)
        return response

    def audited_iterator(*args, **kwargs):
        for response in original_iterator(*args, **kwargs):
            if response.get('remark'):
                raise ValueError(f"Overpass remark: {response['remark']}")
            responses.append(response)
            yield response

    started_utc = datetime.now(timezone.utc).isoformat()
    started = perf_counter()
    print(f'OSM source endpoint: {ox.settings.overpass_url}; requesting ALL study components.', flush=True)
    try:
        with (patch.object(ox._overpass, '_download_overpass_network', audited_iterator),
              patch.object(ox._http, '_retrieve_from_cache', audited_cache_read)):
            graph = ox.graph_from_polygon(geographic, network_type='bike', simplify=False,
                                          retain_all=True, truncate_by_edge=False)
        if len(responses) != expected_responses:
            raise ValueError(f'Expected {expected_responses} complete responses, received {len(responses)}.')
        ways, timestamps = audit_responses(responses)
    except Exception as exc:
        raise RuntimeError(f'Bike network retrieval failed: {exc}. {SUBDIVISION_ADVICE}') from exc
    elapsed = perf_counter() - started
    retrieved_utc = datetime.now(timezone.utc).isoformat()
    # Keep every original way segment (no simplification, no ring removal),
    # normalized useful tags AND all raw way tags, including original oneway.
    for _, data in graph.nodes(data=True):
        data['lon'], data['lat'] = data['x'], data['y']
    for _, _, data in graph.edges(data=True):
        data['osm_tags_json'] = canonical(ways[data['osmid']].get('tags', {}))
    graph = ox.project_graph(graph, to_crs=METRIC_CRS)
    for u, v, data in graph.edges(data=True):
        data['geometry'] = LineString([(graph.nodes[u]['x'], graph.nodes[u]['y']),
                                       (graph.nodes[v]['x'], graph.nodes[v]['y'])])
        data['length_utm_m'] = data['geometry'].length
    provenance = {**base, 'source': 'OpenStreetMap via Overpass API',
                  'source_endpoint': ox.settings.overpass_url,
                  'attribution': '© OpenStreetMap contributors',
                  'license': 'Open Database License (ODbL) 1.0',
                  'license_url': 'https://www.openstreetmap.org/copyright',
                  'retrieval_started_utc': started_utc, 'retrieved_at_utc': retrieved_utc,
                  'osm_base_timestamps': timestamps, 'cache_policy': 'OSMnx cache enabled; OSM base timestamps identify response snapshots',
                  'download_seconds': elapsed, 'response_count': len(responses),
                  'cached_response_count': cache_hits, 'fresh_response_count': len(responses) - cache_hits,
                  'expected_response_count': expected_responses, 'all_responses_validated': True,
                  'network_type': 'bike', 'retain_all': True, 'simplify': False, 'truncate_by_edge': False,
                  'way_tags_requested': ox.settings.useful_tags_way, 'node_tags_requested': ox.settings.useful_tags_node,
                  'length_definition': 'length: OSMnx great-circle segment meters; length_utm_m: EPSG:32639 geometry meters',
                  'limitations': LIMITATIONS}
    graph.graph['bike_provenance_json'] = canonical(provenance)
    return graph, provenance


def validate_graph(graph, area):
    if (not isinstance(graph, nx.MultiDiGraph) or not graph.is_directed()
            or CRS(graph.graph.get('crs')).to_epsg() != 32639
            or not graph.number_of_nodes() or not graph.number_of_edges()):
        raise ValueError('Expected nonempty directed metric MultiDiGraph in EPSG:32639.')
    # Reuse one prepared polygon; avoid buffering it once per node/edge.
    tolerant_area = area.buffer(1e-5)
    shapely.prepare(tolerant_area)
    for node, data in graph.nodes(data=True):
        values = [data.get(key) for key in ('x', 'y', 'lon', 'lat')]
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError(f'Node {node}: missing/nonfinite coordinate.')
        x, y, lon, lat = values
        projected = TO_METRIC(lon, lat)
        if (not (-180 <= lon <= 180 and -90 <= lat <= 90)
                or math.hypot(projected[0] - x, projected[1] - y) > 1e-5
                or not tolerant_area.covers(Point(x, y))):
            raise ValueError(f'Node {node}: invalid coordinates or outside study polygon.')
    types, tag_counts = Counter(), Counter()
    lengths, oneway, reverse_missing, outside, exception_edges = [], 0, 0, 0, 0
    for u, v, key, data in graph.edges(keys=True, data=True):
        length, metric_length = data.get('length'), data.get('length_utm_m')
        geometry = data.get('geometry')
        if (type(length) not in (int, float) or not math.isfinite(length) or length <= 0
                or type(metric_length) not in (int, float) or not math.isfinite(metric_length) or metric_length <= 0
                or geometry is None or geometry.geom_type != 'LineString' or geometry.is_empty
                or not geometry.is_valid or not np.isfinite(shapely.get_coordinates(geometry)).all()
                or type(data.get('oneway')) is not bool or 'osmid' not in data):
            raise ValueError(f'Edge {(u, v, key)}: invalid length/geometry/direction/source fields.')
        start, end = Point(geometry.coords[0]), Point(geometry.coords[-1])
        if (start.distance(Point(graph.nodes[u]['x'], graph.nodes[u]['y'])) > 1e-5
                or end.distance(Point(graph.nodes[v]['x'], graph.nodes[v]['y'])) > 1e-5
                or not math.isclose(metric_length, geometry.length, abs_tol=1e-6, rel_tol=1e-12)
                or not math.isclose(length, metric_length, abs_tol=0.02, rel_tol=0.01)):
            raise ValueError(f'Edge {(u, v, key)}: endpoint/topology or meter-length consistency failed.')
        tags = json.loads(data.get('osm_tags_json', '{}'))
        if not tags.get('highway') or tags.get('highway') != data.get('highway'):
            raise ValueError('Original OSM highway tags missing or changed.')
        for tag in WAY_TAGS:
            if tag in data:
                tag_counts[tag] += 1
            if tag in tags and tag != 'oneway' and data.get(tag) != tags[tag]:
                raise ValueError(f'Original OSM tag lost/changed: {tag}.')
        types[data['highway']] += 1
        oneway += data['oneway']
        matching_reverse = any(other.get('osmid') == data['osmid'] for other in graph.get_edge_data(v, u, default={}).values())
        reverse_missing += not matching_reverse
        if not data['oneway'] and not matching_reverse:
            raise ValueError('Bidirectional way segment is missing its reverse edge.')
        outside += not tolerant_area.covers(geometry)
        exception_edges += any(k in tags for k in ('oneway:bicycle', 'bicycle:conditional', 'access:conditional', 'oneway:conditional'))
        lengths.append(length)
    weak = sorted((len(c) for c in nx.weakly_connected_components(graph)), reverse=True)
    strong = sorted((len(c) for c in nx.strongly_connected_components(graph)), reverse=True)
    return {'nodes': graph.number_of_nodes(), 'edges': graph.number_of_edges(), 'directed': True,
            'weak_component_count': len(weak), 'weak_component_node_sizes': weak,
            'strong_component_count': len(strong),
            'strong_component_size_histogram': {str(k): v for k, v in sorted(Counter(strong).items(), reverse=True)},
            'isolated_nodes_retained': nx.number_of_isolates(graph), 'self_loop_edges': nx.number_of_selfloops(graph),
            'oneway_directed_edges': oneway, 'edges_without_same_way_reverse': reverse_missing,
            'edges_with_bicycle_or_conditional_exceptions': exception_edges,
            'edges_not_fully_inside_study': outside, 'highway_directed_edge_counts': dict(sorted(types.items())),
            'tagged_directed_edge_counts': dict(sorted(tag_counts.items())),
            'length_m_min': min(lengths), 'length_m_max': max(lengths),
            'quality_warnings': LIMITATIONS}


def load_graph(path):
    # OSMnx literal-evaluates dictionary-shaped edge strings before dtypes.
    return ox.load_graphml(path, node_dtypes={'lon': float, 'lat': float},
                          edge_dtypes={'length_utm_m': float,
                                       'osm_tags_json': lambda v: canonical(v) if isinstance(v, dict) else v})


def verify_roundtrip(original, loaded):
    if set(original.nodes) != set(loaded.nodes) or set(original.edges) != set(loaded.edges):
        raise ValueError('GraphML roundtrip changed node IDs or edge topology.')
    for before, after in [(original.graph, loaded.graph),
                          *((original.nodes[n], loaded.nodes[n]) for n in original.nodes),
                          *((original.edges[e], loaded.edges[e]) for e in original.edges)]:
        if set(before) != set(after):
            raise ValueError('GraphML roundtrip changed attribute keys.')
        for key, value in before.items():
            other = after[key]
            if key == 'crs':
                equal = CRS(value) == CRS(other)
            elif isinstance(value, shapely.Geometry):
                equal = value.equals_exact(other, tolerance=1e-8)
            else:
                equal = value == other
            if not equal:
                raise ValueError(f'GraphML roundtrip changed attribute: {key}.')


def verify_outputs(area, geographic, base, area_path=AREA_PATH, graph_path=GRAPH_PATH):
    document = json.loads(area_path.read_bytes())
    expected_feature = {'type': 'Feature', 'properties': {'id': 'baku:bike-study-area:3000m'}, 'geometry': mapping(geographic)}
    if document.get('type') != 'FeatureCollection' or canonical(document.get('features')) != canonical([expected_feature]):
        raise ValueError('Study area differs from full input-derived 3000m buffers clipped to Baku.')
    metadata = document['metadata']
    if metadata.get('graphml_sha256') != digest(graph_path):
        raise ValueError('GraphML hash mismatch; saved output pair is incomplete or changed.')
    graph = load_graph(graph_path)
    provenance = json.loads(graph.graph['bike_provenance_json'])
    for key, value in base.items():
        if provenance.get(key) != value:
            raise ValueError(f'Saved graph input/method provenance mismatch: {key}.')
    if (not provenance.get('all_responses_validated') or provenance.get('network_type') != 'bike'
            or provenance.get('retain_all') is not True or provenance.get('simplify') is not False
            or provenance.get('response_count', 0) <= 0
            or provenance['response_count'] != provenance.get('expected_response_count')):
        raise ValueError('Graph does not have complete bicycle-network retrieval provenance.')
    summary = validate_graph(graph, area)
    if canonical(metadata) != canonical({**provenance, 'graphml_sha256': digest(graph_path), 'validation_summary': summary}):
        raise ValueError('Saved metadata differs from graph/provenance/recalculated validation.')
    report('NETWORK VALIDATION', summary)
    report('SAVED OUTPUTS', {'study_area_km2': area.area / 1e6, 'graphml_bytes': graph_path.stat().st_size,
                             'download_seconds': provenance['download_seconds'],
                             'cached_response_count': provenance.get('cached_response_count'),
                             'fresh_response_count': provenance.get('fresh_response_count'),
                             'retrieved_at_utc': provenance['retrieved_at_utc'], 'osm_base_timestamps': provenance['osm_base_timestamps']})
    print('OFFLINE VERIFICATION PASSED: study geometry, input hashes, graph hash, coordinates, topology, lengths, tags and components.', flush=True)


def save_outputs(graph, provenance, area, geographic, base):
    summary = validate_graph(graph, area)
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.bike-network-', dir=GRAPH_PATH.parent) as stage:
        graph_path, area_path = Path(stage) / GRAPH_PATH.name, Path(stage) / AREA_PATH.name
        ox.save_graphml(graph, graph_path)
        verify_roundtrip(graph, load_graph(graph_path))
        document = {'type': 'FeatureCollection', 'features': [{'type': 'Feature',
                    'properties': {'id': 'baku:bike-study-area:3000m'}, 'geometry': mapping(geographic)}],
                    'metadata': {**provenance, 'graphml_sha256': digest(graph_path), 'validation_summary': summary}}
        area_path.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
        verify_outputs(area, geographic, base, area_path, graph_path)
        for path in (graph_path, area_path):
            with path.open('rb') as stream:
                os.fsync(stream.fileno())
        os.replace(graph_path, GRAPH_PATH)
        os.replace(area_path, AREA_PATH)
    print(f'Saved {AREA_PATH} and {GRAPH_PATH}; existing driving network untouched.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true', help='Validate saved outputs locally; no OSM calls or writes.')
    args = parser.parse_args()
    report('ENVIRONMENT', {'osmnx_version': ox.__version__, 'metric_crs': METRIC_CRS})
    area, geographic, base = load_inputs()
    if args.verify_only or AREA_PATH.exists() or GRAPH_PATH.exists():
        if not AREA_PATH.is_file() or not GRAPH_PATH.is_file():
            raise ValueError('Both saved outputs are required for verification/reuse; no incomplete pair accepted.')
        verify_outputs(area, geographic, base)
        return
    graph, provenance = download_graph(geographic, base)
    save_outputs(graph, provenance, area, geographic, base)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr, flush=True)
        sys.exit(1)
